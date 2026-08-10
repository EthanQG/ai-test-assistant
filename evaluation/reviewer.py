"""Deterministic defect labels and metrics for Reviewer evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence


DEFECT_TYPES = {
    "requirement_omission",
    "boundary_missing",
    "duplicate_test_point",
    "unsupported_assertion",
    "vague_expectation",
    "missing_source",
}


@dataclass(frozen=True)
class ReviewerDefect:
    defect_type: str
    target: str
    evidence: str

    @property
    def key(self) -> tuple[str, str]:
        return self.defect_type, self.target


@dataclass(frozen=True)
class ReviewerEvaluationCase:
    case_id: str
    title: str
    requirement_facts: tuple[str, ...]
    test_points: tuple[dict, ...]
    expected_defects: tuple[ReviewerDefect, ...]


@dataclass(frozen=True)
class ReviewerEvaluationDataset:
    fixture_set_id: str
    cases: tuple[ReviewerEvaluationCase, ...]


def load_reviewer_dataset(path: Path) -> ReviewerEvaluationDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported Reviewer fixture schema_version")
    cases = tuple(_load_case(item) for item in payload["cases"])
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Reviewer case_id values must be unique")
    return ReviewerEvaluationDataset(
        fixture_set_id=payload["fixture_set_id"],
        cases=cases,
    )


def score_reviewer_predictions(
    dataset: ReviewerEvaluationDataset,
    predictions: Mapping[str, Sequence[ReviewerDefect]],
) -> dict:
    known_case_ids = {case.case_id for case in dataset.cases}
    unknown = set(predictions) - known_case_ids
    if unknown:
        raise ValueError(f"unknown Reviewer case_id: {sorted(unknown)}")

    true_positive = false_positive = false_negative = 0
    clean_cases = clean_cases_with_findings = 0
    case_results = []
    for case in dataset.cases:
        expected = {item.key for item in case.expected_defects}
        actual = {item.key for item in predictions.get(case.case_id, ())}
        case_tp = len(expected & actual)
        case_fp = len(actual - expected)
        case_fn = len(expected - actual)
        true_positive += case_tp
        false_positive += case_fp
        false_negative += case_fn
        if not expected:
            clean_cases += 1
            clean_cases_with_findings += bool(actual)
        case_results.append(
            {
                "case_id": case.case_id,
                "true_positive": case_tp,
                "false_positive": case_fp,
                "false_negative": case_fn,
            }
        )

    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    return {
        "case_count": len(dataset.cases),
        "expected_defect_count": true_positive + false_negative,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(true_positive / precision_denominator, 4)
        if precision_denominator
        else 0.0,
        "recall": round(true_positive / recall_denominator, 4)
        if recall_denominator
        else 0.0,
        "clean_case_false_positive_rate": round(
            clean_cases_with_findings / clean_cases, 4
        )
        if clean_cases
        else 0.0,
        "results": case_results,
    }


def _load_case(item: dict) -> ReviewerEvaluationCase:
    defects = tuple(
        ReviewerDefect(
            defect_type=raw["defect_type"],
            target=raw["target"],
            evidence=raw["evidence"],
        )
        for raw in item["expected_defects"]
    )
    unsupported = {defect.defect_type for defect in defects} - DEFECT_TYPES
    if unsupported:
        raise ValueError(f"unsupported Reviewer defect type: {sorted(unsupported)}")
    return ReviewerEvaluationCase(
        case_id=item["case_id"],
        title=item["title"],
        requirement_facts=tuple(item["requirement_facts"]),
        test_points=tuple(item["test_points"]),
        expected_defects=defects,
    )
