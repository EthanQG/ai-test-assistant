from pathlib import Path

import pytest

from agent import AgentStatus, TestAnalysisState
from application import TaskRecord, TaskView
from evaluation.dataset import load_evaluation_dataset
from evaluation.experiment_execution import (
    EXECUTION_POLICIES,
    run_application_experiment_case,
    validate_execution_policies,
)


CASE = load_evaluation_dataset(Path("evaluation/datasets/seed_v1.json")).cases[0]


def _view(state, *, auto_run):
    return TaskView.from_record(TaskRecord(state=state, auto_run=auto_run))


class FakeExperimentService:
    def __init__(self, *, wait_twice=False):
        self.state = None
        self.wait_twice = wait_twice
        self.advance_calls = 0
        self.answers = []

    def create_task(self, command):
        self.state = TestAnalysisState(command.requirement, task_id="fixed-task")
        return _view(self.state, auto_run=True)

    def advance_task(self, task_id):
        assert task_id == "fixed-task"
        self.advance_calls += 1
        if self.advance_calls == 1 or (
            self.wait_twice and self.advance_calls == 2
        ):
            self.state.wait_for_user([f"问题{self.advance_calls}"])
            return _view(self.state, auto_run=False)
        self.state.status = AgentStatus.COMPLETED
        return _view(self.state, auto_run=False)

    def submit_clarifications(self, task_id, command):
        assert task_id == "fixed-task"
        self.answers.append(command.answers)
        self.state.resume()
        self.state.open_questions = []
        return _view(self.state, auto_run=False)


def test_policies_only_change_rag_and_quality_loop():
    validate_execution_policies()

    assert not EXECUTION_POLICIES["baseline_llm"].use_rag
    assert not EXECUTION_POLICIES["baseline_llm"].use_quality_loop
    assert EXECUTION_POLICIES["llm_with_rag"].use_rag
    assert not EXECUTION_POLICIES["llm_with_rag"].use_quality_loop
    assert EXECUTION_POLICIES["llm_with_rag_reviewer_reviser"].use_rag
    assert EXECUTION_POLICIES[
        "llm_with_rag_reviewer_reviser"
    ].use_quality_loop


def test_driver_defers_questions_and_resumes_the_same_task():
    service = FakeExperimentService(wait_twice=True)

    result = run_application_experiment_case(service, CASE)

    assert result.task_id == "fixed-task"
    assert result.status is AgentStatus.COMPLETED
    assert service.answers == [{"问题1": None}, {"问题2": None}]


def test_driver_rejects_more_than_two_clarification_rounds():
    service = FakeExperimentService(wait_twice=True)
    original_advance = service.advance_task

    def always_wait(task_id):
        service.wait_twice = True
        service.advance_calls %= 2
        return original_advance(task_id)

    service.advance_task = always_wait

    with pytest.raises(RuntimeError, match="clarification round limit"):
        run_application_experiment_case(service, CASE)
