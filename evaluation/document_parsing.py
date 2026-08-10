"""Small deterministic evaluator for the document parsing fixtures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from documents import (
    DocumentContent,
    DocumentOcrElement,
    DocumentTableElement,
    DocumentVisualAnalysis,
)
from services.document_service import DocumentService


SUPPORTED_TARGETS = {"native_text", "table_structure", "ocr_text"}


class _UploadedFixture(BytesIO):
    def __init__(self, path: Path):
        super().__init__(path.read_bytes())
        self.name = path.name


class _NoVisualEngine:
    def analyze(self, *args, **kwargs):
        raise AssertionError("document parsing evaluation must not call vision")


@dataclass(frozen=True)
class FixtureScore:
    fixture_id: str
    evaluation_target: str
    metrics: dict[str, float]
    missing_items: tuple[str, ...]
    warning_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "evaluation_target": self.evaluation_target,
            "metrics": self.metrics,
            "missing_items": list(self.missing_items),
            "warning_codes": list(self.warning_codes),
        }


def _normalize_text(value: str) -> str:
    return "".join(value.split()).casefold()


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _character_accuracy(expected: str, actual: str) -> float:
    expected = _normalize_text(expected)
    actual = _normalize_text(actual)
    if not expected:
        return 1.0 if not actual else 0.0
    distance = _edit_distance(expected, actual)
    return round(max(0.0, 1 - distance / max(len(expected), len(actual))), 4)


def _line_recall(expected_lines: list[str], actual_text: str) -> tuple[float, tuple[str, ...]]:
    normalized_actual = _normalize_text(actual_text)
    missing = tuple(
        line
        for line in expected_lines
        if _normalize_text(line) not in normalized_actual
    )
    recall = (len(expected_lines) - len(missing)) / len(expected_lines)
    return round(recall, 4), missing


def _table_cell_accuracy(expected_rows: list[list[str]], content: DocumentContent) -> float:
    tables = [
        element.table.rows
        for element in content.elements
        if isinstance(element, DocumentTableElement)
    ]
    actual_cells = [cell for row in (tables[0] if tables else ()) for cell in row]
    expected_cells = [cell for row in expected_rows for cell in row]
    total = max(len(expected_cells), len(actual_cells))
    if total == 0:
        return 1.0
    matches = sum(
        _normalize_text(expected) == _normalize_text(actual)
        for expected, actual in zip(expected_cells, actual_cells)
    )
    return round(matches / total, 4)


def _scored_text(target: str, content: DocumentContent) -> str:
    if target != "ocr_text":
        return content.to_plain_text()
    return "\n".join(
        element.text
        for element in content.elements
        if isinstance(element, DocumentOcrElement)
    )


def score_content(fixture: dict, content: DocumentContent) -> FixtureScore:
    target = fixture["evaluation_target"]
    gold = fixture["gold"]
    expected_lines = gold["text_lines"]
    expected_text = "\n".join(expected_lines)
    actual_text = _scored_text(target, content)
    line_recall, missing = _line_recall(expected_lines, actual_text)
    metrics = {"text_line_recall": line_recall}
    if target != "table_structure":
        metrics["character_accuracy"] = _character_accuracy(
            expected_text, actual_text
        )
    if target == "table_structure":
        expected_rows = [gold["table"]["headers"], *gold["table"]["rows"]]
        metrics["table_cell_accuracy"] = _table_cell_accuracy(
            expected_rows, content
        )
    return FixtureScore(
        fixture_id=fixture["fixture_id"],
        evaluation_target=target,
        metrics=metrics,
        missing_items=missing,
        warning_codes=tuple(warning.code.value for warning in content.warnings),
    )


def _ratio(matched: int, expected: int, actual: int | None = None) -> float:
    total = expected if actual is None else max(expected, actual)
    return round(matched / total, 4) if total else 1.0


def score_visual_analysis(
    fixture: dict,
    analysis: DocumentVisualAnalysis,
) -> FixtureScore:
    target = fixture["evaluation_target"]
    gold = fixture["gold"]
    missing: list[str] = []
    metrics: dict[str, float]
    if target == "flow_semantics":
        node_labels = {
            _normalize_text(node.label): node.label for node in analysis.nodes
        }
        expected_nodes = gold["nodes"]
        missing.extend(
            f"节点：{label}"
            for label in expected_nodes
            if _normalize_text(label) not in node_labels
        )
        labels_by_id = {
            node.node_id: _normalize_text(node.label) for node in analysis.nodes
        }
        actual_relations = {
            (
                labels_by_id[item.source_node_id],
                labels_by_id[item.target_node_id],
                _normalize_text(item.condition or ""),
            )
            for item in analysis.relations
        }
        expected_relations = {
            (
                _normalize_text(item["from"]),
                _normalize_text(item["to"]),
                _normalize_text(item["condition"]),
            )
            for item in gold["relations"]
        }
        missing_relations = expected_relations - actual_relations
        missing.extend(
            f"关系：{source}->{target}（{condition or '无条件'}）"
            for source, target, condition in sorted(missing_relations)
        )
        metrics = {
            "flow_node_recall": _ratio(
                len(expected_nodes) - sum(item.startswith("节点：") for item in missing),
                len(expected_nodes),
            ),
            "flow_relation_accuracy": _ratio(
                len(expected_relations & actual_relations),
                len(expected_relations),
                len(actual_relations),
            ),
        }
    elif target == "ui_semantics":
        expected_elements = {
            (_normalize_text(item["type"]), _normalize_text(item["label"]))
            for item in gold["ui_elements"]
        }
        actual_elements = {
            (_normalize_text(item.element_type), _normalize_text(item.name))
            for item in analysis.ui_elements
        }
        missing_elements = expected_elements - actual_elements
        missing.extend(
            f"UI元素：{element_type}/{label}"
            for element_type, label in sorted(missing_elements)
        )
        metrics = {
            "ui_element_accuracy": _ratio(
                len(expected_elements & actual_elements),
                len(expected_elements),
                len(actual_elements),
            )
        }
    else:
        raise ValueError(f"unsupported visual target: {target}")
    return FixtureScore(
        fixture_id=fixture["fixture_id"],
        evaluation_target=target,
        metrics=metrics,
        missing_items=tuple(missing),
        warning_codes=(),
    )


def run_document_parsing_evaluation(
    manifest_path: Path,
    *,
    parser: Callable[[object], DocumentContent] | None = None,
    visual_results: dict[str, DocumentVisualAnalysis] | None = None,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture_dir = manifest_path.parent
    parse = parser or (
        lambda uploaded: DocumentService.parse(
            uploaded,
            visual_engine=_NoVisualEngine(),
        )
    )
    results = []
    for fixture in manifest["fixtures"]:
        target = fixture["evaluation_target"]
        if target in {"flow_semantics", "ui_semantics"}:
            analysis = (visual_results or {}).get(fixture["fixture_id"])
            if analysis is not None:
                results.append(score_visual_analysis(fixture, analysis).to_dict())
            continue
        if target not in SUPPORTED_TARGETS:
            continue
        content = parse(_UploadedFixture(fixture_dir / fixture["path"]))
        results.append(score_content(fixture, content).to_dict())
    return {
        "schema_version": 1,
        "fixture_set_id": manifest["fixture_set_id"],
        "total_fixture_count": len(manifest["fixtures"]),
        "evaluated_fixture_count": len(results),
        "skipped_fixture_ids": [
            fixture["fixture_id"]
            for fixture in manifest["fixtures"]
            if fixture["fixture_id"]
            not in {result["fixture_id"] for result in results}
        ],
        "results": results,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "gold_v1.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_document_parsing_evaluation(args.manifest)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
