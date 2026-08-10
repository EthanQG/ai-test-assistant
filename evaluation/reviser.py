"""Deterministic fixtures and metrics for Reviser evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from agent import TestAnalysisState


@dataclass(frozen=True)
class ReviserEvaluationCase:
    case_id: str
    defect_type: str
    requirement_facts: tuple[str, ...]
    before_test_points: tuple[dict, ...]
    expected_test_points: tuple[dict, ...]
    changed_titles: tuple[str, ...]


class ReviserBoundary(Protocol):
    def revise(self, state: TestAnalysisState) -> object: ...


def load_reviser_cases(path: Path) -> tuple[str, tuple[ReviserEvaluationCase, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported Reviser fixture schema_version")
    cases = tuple(
        ReviserEvaluationCase(
            case_id=item["case_id"],
            defect_type=item["defect_type"],
            requirement_facts=tuple(item["requirement_facts"]),
            before_test_points=tuple(item["before_test_points"]),
            expected_test_points=tuple(item["expected_test_points"]),
            changed_titles=tuple(item["changed_titles"]),
        )
        for item in payload["cases"]
    )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Reviser case_id values must be unique")
    return payload["fixture_set_id"], cases


def reviser_case_to_state(case: ReviserEvaluationCase) -> TestAnalysisState:
    state = TestAnalysisState("\n".join(case.requirement_facts), task_id=case.case_id)
    state.requirement_summary = case.defect_type
    state.requirement_facts = list(case.requirement_facts)
    state.test_points = [_full_test_point(item) for item in case.before_test_points]
    state.review_result = {
        "overall_score": 60,
        "missing_scenarios": list(case.changed_titles),
        "duplicate_groups": [],
        "hallucination_issues": [],
        "revision_suggestions": [f"修正{case.defect_type}: {title}" for title in case.changed_titles],
    }
    state.review_passed = False
    return state


def run_reviser_evaluation(
    path: Path,
    reviser: ReviserBoundary,
    *,
    dependency_mode: str,
    continue_on_error: bool = False,
) -> dict:
    fixture_set_id, cases = load_reviser_cases(path)
    results = []
    errors = []
    fixed = preserved = fixed_total = preserved_total = 0
    for case in cases:
        state = reviser_case_to_state(case)
        try:
            reviser.revise(state)
        except Exception as exc:
            if not continue_on_error:
                raise
            errors.append({
                "case_id": case.case_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            })
        actual = {_compact(item)["title"]: _compact(item) for item in state.test_points}
        expected = {item["title"]: item for item in case.expected_test_points}
        before_titles = {item["title"] for item in case.before_test_points}
        changed = set(case.changed_titles)
        fixed_count = sum(actual.get(title) == expected.get(title) for title in changed)
        protected_titles = before_titles - changed
        preserved_count = sum(actual.get(title) == expected.get(title) for title in protected_titles)
        fixed += fixed_count
        fixed_total += len(changed)
        preserved += preserved_count
        preserved_total += len(protected_titles)
        results.append({
            "case_id": case.case_id,
            "fixed": fixed_count == len(changed),
            "preserved": preserved_count == len(protected_titles),
            "unexpected_titles": sorted(set(actual) - set(expected)),
        })
    return {
        "schema_version": 1,
        "fixture_set_id": fixture_set_id,
        "dependency_mode": dependency_mode,
        "target_fix_rate": round(fixed / fixed_total, 4),
        "preservation_rate": round(preserved / preserved_total, 4),
        "failed_case_count": len(errors),
        "results": results,
        "errors": errors,
    }


def _full_test_point(item: dict) -> dict:
    return {
        "title": item["title"], "category": "functional", "priority": "P0",
        "scenario": item["scenario"], "preconditions": ["准备测试数据"],
        "steps": [item["scenario"]], "expected_results": [item["expected"]],
        "sources": ["requirement"] if item["sources"] else [],
        "source_refs": list(item["sources"]),
    }


def _compact(item: dict) -> dict:
    return {
        "title": item["title"], "scenario": item["scenario"],
        "expected": item["expected_results"][0], "sources": list(item["source_refs"]),
    }
