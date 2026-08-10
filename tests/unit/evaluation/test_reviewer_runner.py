import json
from pathlib import Path

from agent import TestAnalysisState, TestPointReviewResult
from evaluation.reviewer import load_reviewer_dataset
from evaluation.reviewer_runner import (
    reviewer_case_to_state,
    run_reviewer_evaluation,
)


FIXTURE = Path("evaluation/fixtures/reviewer_v1.json")
REPORT = Path("evaluation/results/reviewer_fake_runner_v1.json")


class GoldFakeReviewer:
    """Returns deterministic structured output derived from fixture gold."""

    def __init__(self):
        dataset = load_reviewer_dataset(FIXTURE)
        self.cases = {case.case_id: case for case in dataset.cases}
        self.received_states = []

    def review(self, state: TestAnalysisState) -> TestPointReviewResult:
        self.received_states.append(state)
        case = self.cases[state.task_id]
        defects = case.expected_defects
        omitted = {
            item.target
            for item in defects
            if item.defect_type == "requirement_omission"
        }
        return TestPointReviewResult.from_dict(
            {
                "overall_score": 100 if not defects else 60,
                "dimension_scores": {
                    "requirement_coverage": 100,
                    "boundary_exception": 100,
                    "executability": 100,
                    "traceability": 100,
                },
                "requirement_coverage": [
                    {
                        "requirement_fact": fact,
                        "status": "missing" if fact in omitted else "covered",
                        "covered_by": [] if fact in omitted else ["Fake覆盖"],
                        "gap": "Fake标记为遗漏" if fact in omitted else "",
                    }
                    for fact in case.requirement_facts
                ],
                "missing_scenarios": [
                    item.target
                    for item in defects
                    if item.defect_type == "boundary_missing"
                ],
                "duplicate_groups": [
                    item.target.split("|")
                    for item in defects
                    if item.defect_type == "duplicate_test_point"
                ],
                "hallucination_issues": [
                    {
                        "test_point_title": item.target,
                        "issue": item.evidence,
                        "unsupported_claim": item.evidence,
                    }
                    for item in defects
                    if item.defect_type == "unsupported_assertion"
                ],
                "revision_suggestions": [
                    _suggestion(item.defect_type, item.target)
                    for item in defects
                    if item.defect_type in {"vague_expectation", "missing_source"}
                ],
            }
        )


def _suggestion(defect_type: str, target: str) -> str:
    if defect_type == "missing_source":
        return f"测试点{target}缺少来源引用"
    return f"测试点{target}预期模糊，需要明确预期"


def test_reviewer_case_is_converted_to_current_agent_state():
    case = load_reviewer_dataset(FIXTURE).cases[0]

    state = reviewer_case_to_state(case)

    assert isinstance(state, TestAnalysisState)
    assert state.task_id == case.case_id
    assert state.requirement_facts == list(case.requirement_facts)
    assert state.test_points[0]["expected_results"]
    assert state.test_points[0]["source_refs"] == case.test_points[0]["sources"]


def test_runner_uses_injected_reviewer_and_writes_stable_fake_report():
    reviewer = GoldFakeReviewer()

    report = run_reviewer_evaluation(
        FIXTURE,
        reviewer,
        dependency_mode="fake_gold_predictions_only",
    )

    assert len(reviewer.received_states) == 12
    assert all(isinstance(state, TestAnalysisState) for state in reviewer.received_states)
    assert report["dependency_mode"] == "fake_gold_predictions_only"
    assert report["errors"] == []
    metrics = report["metrics"]
    assert metrics["case_count"] == 12
    assert metrics["expected_defect_count"] == 12
    assert metrics["true_positive"] == 11
    assert metrics["false_positive"] == 0
    assert metrics["false_negative"] == 1
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.9167
    assert metrics["clean_case_false_positive_rate"] == 0.0
    assert metrics["failed_case_count"] == 0
    assert next(
        item for item in metrics["results"]
        if item["case_id"] == "review-boundary-002"
    )["false_negative"] == 1
    assert json.loads(REPORT.read_text(encoding="utf-8")) == report


def test_runner_can_record_one_reviewer_failure_and_continue():
    reviewer = GoldFakeReviewer()
    original_review = reviewer.review

    def review_with_one_failure(state):
        if state.task_id == "review-omission-001":
            raise ValueError("invalid structured output")
        return original_review(state)

    reviewer.review = review_with_one_failure
    report = run_reviewer_evaluation(
        FIXTURE,
        reviewer,
        dependency_mode="fake_with_failure",
        continue_on_error=True,
    )

    assert report["metrics"]["failed_case_count"] == 1
    assert report["metrics"]["false_negative"] == 2
    assert report["errors"] == [
        {
            "case_id": "review-omission-001",
            "error_type": "ValueError",
            "error_message": "invalid structured output",
        }
    ]
