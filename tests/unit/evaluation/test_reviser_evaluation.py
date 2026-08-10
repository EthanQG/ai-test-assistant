from copy import deepcopy
import json
from pathlib import Path

from evaluation.reviser import (
    load_reviser_cases,
    reviser_case_to_state,
    run_reviser_evaluation,
    _full_test_point,
)


FIXTURE = Path("evaluation/fixtures/reviser_v1.json")
REPORT = Path("evaluation/results/reviser_fake_v1.json")


class GoldFakeReviser:
    def __init__(self):
        _, cases = load_reviser_cases(FIXTURE)
        self.cases = {case.case_id: case for case in cases}
        self.received_states = []

    def revise(self, state):
        self.received_states.append(deepcopy(state))
        case = self.cases[state.task_id]
        state.test_points = [_full_test_point(item) for item in case.expected_test_points]


def test_reviser_fixture_covers_six_defect_types():
    fixture_set_id, cases = load_reviser_cases(FIXTURE)

    assert fixture_set_id == "reviser-fixes-v1"
    assert len(cases) == 6
    assert {case.defect_type for case in cases} == {
        "requirement_omission", "boundary_missing", "duplicate_test_point",
        "unsupported_assertion", "vague_expectation", "missing_source",
    }


def test_reviser_case_builds_failed_review_state():
    _, cases = load_reviser_cases(FIXTURE)

    state = reviser_case_to_state(cases[0])

    assert state.review_passed is False
    assert state.review_result["overall_score"] == 60
    assert state.test_points[0]["expected_results"]


def test_fake_reviser_fixes_targets_without_changing_protected_points():
    reviser = GoldFakeReviser()

    report = run_reviser_evaluation(
        FIXTURE, reviser, dependency_mode="fake_gold_reviser_only"
    )

    assert len(reviser.received_states) == 6
    assert report["target_fix_rate"] == 1.0
    assert report["preservation_rate"] == 1.0
    assert report["failed_case_count"] == 0
    assert all(item["fixed"] and item["preserved"] for item in report["results"])
    assert all(not item["unexpected_titles"] for item in report["results"])
    assert json.loads(REPORT.read_text(encoding="utf-8")) == report


def test_reviser_metrics_expose_unfixed_target_and_collateral_change():
    class BadReviser(GoldFakeReviser):
        def revise(self, state):
            case = self.cases[state.task_id]
            state.test_points = [_full_test_point(item) for item in case.before_test_points]
            if len(state.test_points) > 1:
                state.test_points[-1]["expected_results"] = ["错误修改"]

    report = run_reviser_evaluation(
        FIXTURE, BadReviser(), dependency_mode="fake_bad_reviser"
    )

    assert report["target_fix_rate"] < 1.0
    assert report["preservation_rate"] < 1.0


def test_reviser_runner_records_one_failure_and_continues():
    class FailingReviser(GoldFakeReviser):
        def revise(self, state):
            if state.task_id == "revise-omission-001":
                raise ValueError("invalid revision plan")
            super().revise(state)

    report = run_reviser_evaluation(
        FIXTURE,
        FailingReviser(),
        dependency_mode="fake_with_failure",
        continue_on_error=True,
    )

    assert report["failed_case_count"] == 1
    assert report["target_fix_rate"] < 1.0
    assert report["errors"] == [{
        "case_id": "revise-omission-001",
        "error_type": "ValueError",
        "error_message": "invalid revision plan",
    }]
