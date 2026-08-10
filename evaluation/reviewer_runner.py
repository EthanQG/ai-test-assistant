"""Run Reviewer evaluation through the current state and review boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agent import TestAnalysisState, TestPointReviewResult

from .reviewer import (
    ReviewerEvaluationCase,
    load_reviewer_dataset,
    review_result_to_defects,
    score_reviewer_predictions,
)


class ReviewerBoundary(Protocol):
    def review(self, state: TestAnalysisState) -> TestPointReviewResult: ...


def reviewer_case_to_state(case: ReviewerEvaluationCase) -> TestAnalysisState:
    """Convert one compact fixture into the input used by Reviewer."""

    state = TestAnalysisState(
        requirement="\n".join(case.requirement_facts),
        task_id=case.case_id,
    )
    state.requirement_summary = case.title
    state.requirement_facts = list(case.requirement_facts)
    state.test_points = [
        {
            "title": item["title"],
            "category": "functional",
            "priority": "P0",
            "scenario": item["scenario"],
            "preconditions": ["已准备对应测试数据"],
            "steps": [item["scenario"]],
            "expected_results": [item["expected"]],
            "sources": ["requirement"] if item["sources"] else [],
            "source_refs": list(item["sources"]),
        }
        for item in case.test_points
    ]
    return state


def run_reviewer_evaluation(
    fixture_path: Path,
    reviewer: ReviewerBoundary,
    *,
    dependency_mode: str,
) -> dict:
    """Run every case and score the Reviewer's structured output."""

    dataset = load_reviewer_dataset(fixture_path)
    predictions = {}
    for case in dataset.cases:
        state = reviewer_case_to_state(case)
        review = reviewer.review(state)
        predictions[case.case_id] = review_result_to_defects(
            review,
            test_point_titles=[item["title"] for item in state.test_points],
        )

    return {
        "schema_version": 1,
        "fixture_set_id": dataset.fixture_set_id,
        "dependency_mode": dependency_mode,
        "metrics": score_reviewer_predictions(dataset, predictions),
    }
