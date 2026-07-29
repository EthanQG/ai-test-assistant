from datetime import datetime, timezone
from io import BytesIO
from time import perf_counter
from typing import Callable

from agent import (
    AgentOrchestrator,
    AgentStatus,
    FeedbackStatus,
    HumanFeedbackHandler,
    OrchestratorAction,
    OrchestratorDecision,
    RequirementAnalyzer,
    TestAnalysisState,
)
from services.document_service import DocumentService
from utils.knowledge_base import KnowledgeBaseManager

from repositories.task_repository import (
    TaskNotFoundError,
    TaskRepository,
)

from .commands import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
)
from .models import NodeExecutionMetric, TaskRecord, TaskView


class TestAnalysisApplicationService:
    """Runs test-analysis use cases without exposing mutable Agent State."""

    def __init__(
        self,
        repository: TaskRepository,
        *,
        orchestrator_factory: Callable[[], AgentOrchestrator] | None = None,
        requirement_analyzer_factory: (
            Callable[[], RequirementAnalyzer] | None
        ) = None,
        knowledge_loader: Callable[[], str] | None = None,
        max_execution_steps: int = 20,
    ):
        if max_execution_steps <= 0:
            raise ValueError("max_execution_steps must be positive")
        self._repository = repository
        self._orchestrator_factory = (
            orchestrator_factory or AgentOrchestrator
        )
        self._requirement_analyzer_factory = (
            requirement_analyzer_factory or RequirementAnalyzer
        )
        self._knowledge_loader = (
            knowledge_loader
            or KnowledgeBaseManager().load_bug_experience
        )
        self._max_execution_steps = max_execution_steps

    def create_task(self, command: CreateTaskCommand) -> TaskView:
        requirement = command.requirement.strip()
        if command.uploaded_document is not None:
            uploaded = _UploadedDocumentBuffer(
                command.uploaded_document.filename,
                command.uploaded_document.content,
            )
            requirement = DocumentService.extract_text(uploaded)

        state = TestAnalysisState(requirement)
        state.local_bug_knowledge = self._knowledge_loader()
        record = TaskRecord(
            state=state,
            auto_run=True,
            next_action=OrchestratorAction.ANALYZE_REQUIREMENT.value,
        )
        self._repository.create(record)
        return TaskView.from_record(record)

    def get_task(self, task_id: str) -> TaskView:
        return TaskView.from_record(self._repository.get(task_id))

    def list_tasks(self) -> tuple[TaskView, ...]:
        return tuple(
            TaskView.from_record(record)
            for record in self._repository.list()
        )

    def advance_task(self, task_id: str) -> TaskView:
        record = self._repository.get(task_id)
        if record.in_progress:
            return TaskView.from_record(record)
        if (
            record.pending_clarifications is None
            and not record.auto_run
        ):
            return TaskView.from_record(record)

        record.in_progress = True
        self._repository.save(record)
        action = self._next_action(record)
        started_at = datetime.now(timezone.utc)
        started_counter = perf_counter()
        succeeded = False
        error: Exception | None = None

        try:
            if record.pending_clarifications is not None:
                self._reanalyze_with_clarifications(record)
            else:
                self._run_next_orchestrator_node(record)
            succeeded = True
        except Exception as exc:
            error = exc
            record.auto_run = False
        finally:
            finished_at = datetime.now(timezone.utc)
            duration = round(perf_counter() - started_counter, 2)
            record.metrics.append(
                NodeExecutionMetric(
                    action=action,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    succeeded=succeeded,
                    error_type=(
                        None if error is None else type(error).__name__
                    ),
                )
            )
            record.in_progress = False
            self._repository.save(record)

        if error is not None:
            raise error
        return TaskView.from_record(record)

    def submit_clarifications(
        self,
        task_id: str,
        command: SubmitClarificationsCommand,
    ) -> TaskView:
        record = self._repository.get(task_id)
        if record.state.status != AgentStatus.WAITING_FOR_USER:
            raise ValueError("task is not waiting for clarifications")
        expected_questions = set(record.state.open_questions)
        if set(command.answers) != expected_questions:
            raise ValueError(
                "clarification answers must match current open questions"
            )
        record.pending_clarifications = dict(command.answers)
        record.auto_run = False
        record.next_action = OrchestratorAction.ANALYZE_REQUIREMENT.value
        self._repository.save(record)
        return TaskView.from_record(record)

    def confirm_business_rules(
        self,
        task_id: str,
        command: ConfirmBusinessRulesCommand,
    ) -> TaskView:
        record = self._repository.get(task_id)
        handler = HumanFeedbackHandler()
        if command.confirmed:
            handler.confirm_business_rule(
                record.state,
                command.feedback_id,
            )
        else:
            handler.reject_business_rule(
                record.state,
                command.feedback_id,
            )
        record.auto_run = True
        record.execution_steps = 0
        record.next_action = self._decide_next(record)
        self._repository.save(record)
        return TaskView.from_record(record)

    def submit_feedback(
        self,
        task_id: str,
        command: SubmitFeedbackCommand,
    ) -> TaskView:
        record = self._repository.get(task_id)
        feedback = HumanFeedbackHandler().submit(
            record.state,
            {
                "action": command.action,
                "feedback_type": command.feedback_type,
                "target": command.target,
                "content": command.content,
                "reason": command.reason,
            },
        )
        record.auto_run = feedback.status == FeedbackStatus.READY
        record.pending_clarifications = None
        record.execution_steps = 0
        record.next_action = self._decide_next(record)
        self._repository.save(record)
        return TaskView.from_record(record)

    def retry_task(self, task_id: str) -> TaskView:
        record = self._repository.get(task_id)
        if record.state.status != AgentStatus.FAILED:
            raise ValueError("only failed tasks can be retried")
        return self.create_task(
            CreateTaskCommand(requirement=record.state.requirement)
        )

    def delete_task(self, task_id: str) -> None:
        self._repository.delete(task_id)

    def _reanalyze_with_clarifications(self, record: TaskRecord) -> None:
        started_at = perf_counter()
        self._requirement_analyzer_factory().reanalyze_with_clarifications(
            record.state,
            record.pending_clarifications or {},
        )
        record.decisions.append(
            OrchestratorDecision(
                action=OrchestratorAction.ANALYZE_REQUIREMENT,
                reason="已收到用户补充信息，重新执行结构化需求分析",
                duration_seconds=round(perf_counter() - started_at, 2),
            )
        )
        record.execution_steps += 1
        record.pending_clarifications = None
        record.auto_run = record.state.status == AgentStatus.RUNNING
        record.next_action = self._decide_next(record)

    def _run_next_orchestrator_node(self, record: TaskRecord) -> None:
        if record.execution_steps >= self._max_execution_steps:
            record.state.fail(
                "orchestration exceeded maximum step count: "
                f"{self._max_execution_steps}"
            )
            record.auto_run = False
            return

        orchestrator = self._orchestrator_factory()
        decision = orchestrator.run_next(record.state)
        record.decisions.append(decision)
        record.execution_steps += 1
        record.next_action = orchestrator.decide_next(
            record.state
        ).action.value
        record.auto_run = not (
            decision.action
            in {
                OrchestratorAction.WAIT_FOR_USER,
                OrchestratorAction.REVISION_LIMIT_REACHED,
                OrchestratorAction.TERMINAL,
            }
            or record.state.status
            in {
                AgentStatus.WAITING_FOR_USER,
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
            }
        )

    def _next_action(self, record: TaskRecord) -> str:
        return record.next_action or record.state.current_step.value

    def _decide_next(self, record: TaskRecord) -> str:
        return (
            self._orchestrator_factory()
            .decide_next(record.state)
            .action.value
        )


class _UploadedDocumentBuffer(BytesIO):
    def __init__(self, filename: str, content: bytes):
        super().__init__(content)
        self.name = filename


__all__ = [
    "TaskNotFoundError",
    "TestAnalysisApplicationService",
]
