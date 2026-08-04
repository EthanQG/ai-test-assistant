from datetime import datetime, timezone
from io import BytesIO
from time import perf_counter
from typing import Callable
from uuid import uuid4

from agent import (
    AgentOrchestrator,
    AgentStatus,
    FeedbackStatus,
    HumanFeedbackHandler,
    OrchestratorAction,
    TestAnalysisState,
)
from services.document_service import DocumentService
from utils.knowledge_base import KnowledgeBaseManager

from repositories.task_repository import (
    TaskExecutionAlreadyFinishedError,
    TaskExecutionBusyError,
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
        knowledge_loader: Callable[[], str] | None = None,
        max_execution_steps: int = 20,
        worker_id: str | None = None,
        execution_lease_seconds: int = 600,
    ):
        if max_execution_steps <= 0:
            raise ValueError("max_execution_steps must be positive")
        if execution_lease_seconds <= 0:
            raise ValueError("execution_lease_seconds must be positive")
        self._repository = repository
        self._orchestrator_factory = (
            orchestrator_factory or AgentOrchestrator
        )
        self._knowledge_loader = (
            knowledge_loader
            or KnowledgeBaseManager().load_bug_experience
        )
        self._max_execution_steps = max_execution_steps
        self._worker_id = worker_id or str(uuid4())
        self._execution_lease_seconds = execution_lease_seconds

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

    def advance_task(
        self,
        task_id: str,
        *,
        execution_id: str | None = None,
    ) -> TaskView:
        loaded = self._repository.get_versioned(task_id)
        record = loaded.record
        if record.in_progress:
            return TaskView.from_record(record)
        if (
            record.pending_clarifications is None
            and not record.auto_run
        ):
            return TaskView.from_record(record)

        action = self._next_action(record)
        request_execution_id = execution_id or str(uuid4())
        try:
            lease = self._repository.acquire_execution(
                task_id,
                execution_id=request_execution_id,
                owner_id=self._worker_id,
                action=action,
                lease_seconds=self._execution_lease_seconds,
                expected_version=loaded.version,
            )
        except TaskExecutionAlreadyFinishedError:
            return TaskView.from_record(self._repository.get(task_id))
        except TaskExecutionBusyError:
            busy_record = self._repository.get(task_id)
            busy_record.in_progress = True
            return TaskView.from_record(busy_record)

        record.in_progress = True
        started_at = datetime.now(timezone.utc)
        started_counter = perf_counter()
        succeeded = False
        error: Exception | None = None

        try:
            if record.pending_clarifications is not None:
                self._resume_with_clarifications(record)
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
            self._repository.complete_execution(
                record,
                lease,
                succeeded=succeeded,
                error_type=(
                    None if error is None else type(error).__name__
                ),
            )

        if error is not None:
            raise error
        return TaskView.from_record(record)

    def submit_clarifications(
        self,
        task_id: str,
        command: SubmitClarificationsCommand,
    ) -> TaskView:
        loaded = self._repository.get_versioned(task_id)
        record = loaded.record
        if record.state.status != AgentStatus.WAITING_FOR_USER:
            raise ValueError("task is not waiting for clarifications")
        expected_questions = set(record.state.open_questions)
        if set(command.answers) != expected_questions:
            raise ValueError(
                "clarification answers must match current open questions"
            )
        if any(
            answer is not None
            and (
                not isinstance(answer, str)
                or not answer.strip()
            )
            for answer in command.answers.values()
        ):
            raise ValueError(
                "clarification answers cannot contain blank strings"
            )
        record.pending_clarifications = dict(command.answers)
        record.auto_run = False
        record.next_action = OrchestratorAction.ANALYZE_REQUIREMENT.value
        self._repository.save(record, expected_version=loaded.version)
        return TaskView.from_record(record)

    def confirm_business_rules(
        self,
        task_id: str,
        command: ConfirmBusinessRulesCommand,
    ) -> TaskView:
        loaded = self._repository.get_versioned(task_id)
        record = loaded.record
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
        self._repository.save(record, expected_version=loaded.version)
        return TaskView.from_record(record)

    def submit_feedback(
        self,
        task_id: str,
        command: SubmitFeedbackCommand,
    ) -> TaskView:
        loaded = self._repository.get_versioned(task_id)
        record = loaded.record
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
        self._repository.save(record, expected_version=loaded.version)
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

    def _resume_with_clarifications(self, record: TaskRecord) -> None:
        answers = record.pending_clarifications
        if answers is None:
            raise ValueError("no pending clarification answers")

        record.pending_clarifications = None
        decision = (
            self._orchestrator_factory().resume_with_clarifications(
                record.state,
                answers,
            )
        )
        record.decisions.append(decision)
        record.execution_steps += 1
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
