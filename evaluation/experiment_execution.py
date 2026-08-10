"""Controlled application-level execution policy for offline experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent import AgentStatus
from application import (
    CreateTaskCommand,
    SubmitClarificationsCommand,
    TaskView,
)

from .dataset import EvaluationCase
from .experiments import EXPERIMENT_VARIANTS


@dataclass(frozen=True)
class ExperimentExecutionPolicy:
    variant: str
    use_rag: bool
    use_quality_loop: bool


EXECUTION_POLICIES = {
    "baseline_llm": ExperimentExecutionPolicy(
        "baseline_llm", use_rag=False, use_quality_loop=False
    ),
    "llm_with_rag": ExperimentExecutionPolicy(
        "llm_with_rag", use_rag=True, use_quality_loop=False
    ),
    "llm_with_rag_reviewer_reviser": ExperimentExecutionPolicy(
        "llm_with_rag_reviewer_reviser",
        use_rag=True,
        use_quality_loop=True,
    ),
}


class ExperimentApplicationService(Protocol):
    def create_task(self, command: CreateTaskCommand) -> TaskView: ...
    def advance_task(self, task_id: str) -> TaskView: ...
    def submit_clarifications(
        self,
        task_id: str,
        command: SubmitClarificationsCommand,
    ) -> TaskView: ...


def run_application_experiment_case(
    service: ExperimentApplicationService,
    case: EvaluationCase,
    *,
    max_advances: int = 20,
    max_clarification_rounds: int = 2,
) -> TaskView:
    """Run one case with the same deterministic pause policy for all groups."""

    task = service.create_task(CreateTaskCommand(requirement=case.requirement))
    clarification_rounds = 0
    for _ in range(max_advances):
        if task.status in {AgentStatus.COMPLETED, AgentStatus.FAILED}:
            return task
        if task.status is AgentStatus.WAITING_FOR_USER:
            clarification_rounds += 1
            if clarification_rounds > max_clarification_rounds:
                raise RuntimeError("experiment exceeded clarification round limit")
            answers = {question: None for question in task.open_questions}
            service.submit_clarifications(
                task.task_id,
                SubmitClarificationsCommand(answers=answers),
            )
        task = service.advance_task(task.task_id)
        if not task.auto_run and task.status is AgentStatus.RUNNING:
            return task
    raise RuntimeError("experiment exceeded application advance limit")


def validate_execution_policies() -> None:
    if set(EXECUTION_POLICIES) != set(EXPERIMENT_VARIANTS):
        raise ValueError("execution policies must match experiment variants")
