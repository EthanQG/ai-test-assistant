from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from .events import (
    AgentEvent,
    AgentEventType,
    AgentStep,
    utc_now,
)


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeRetrievalStatus(str, Enum):
    NOT_STARTED = "not_started"
    MATCHED = "matched"
    NO_MATCH = "no_match"
    DEGRADED = "degraded"


TERMINAL_STATUSES = {AgentStatus.COMPLETED, AgentStatus.FAILED}


@dataclass
class TestAnalysisState:
    requirement: str
    task_id: str = field(default_factory=lambda: str(uuid4()))

    status: AgentStatus = AgentStatus.PENDING
    current_step: AgentStep = AgentStep.INITIALIZE

    requirement_summary: str = ""
    modules: list[str] = field(default_factory=list)
    requirement_facts: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    state_transitions: list[str] = field(default_factory=list)
    inferred_risks: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    local_bug_knowledge: str = ""
    rag_context: str = ""
    rag_max_score: float = 0.0
    rag_matched_count: int = 0
    knowledge_retrieval_status: KnowledgeRetrievalStatus = (
        KnowledgeRetrievalStatus.NOT_STARTED
    )
    rag_error_message: str | None = None

    test_points: list[dict[str, Any]] = field(default_factory=list)
    review_result: dict[str, Any] | None = None
    review_passed: bool | None = None
    review_threshold: int = 80
    revision_count: int = 0
    report: str = ""
    error_message: str | None = None
    events: list[AgentEvent] = field(default_factory=list)

    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.requirement = self.requirement.strip()
        if not self.requirement:
            raise ValueError("requirement cannot be empty")

        if not self.events:
            self._append_event(
                AgentEventType.TASK_CREATED,
                AgentStep.INITIALIZE,
                "测试分析任务已创建",
            )

    def start_step(self, step: AgentStep, message: str) -> AgentEvent:
        self._ensure_active()
        self.status = AgentStatus.RUNNING
        self.current_step = step
        self.error_message = None
        return self._append_event(AgentEventType.STEP_STARTED, step, message)

    def complete_step(
        self,
        step: AgentStep,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> AgentEvent:
        self._ensure_active()
        if self.current_step != step:
            raise ValueError(
                f"cannot complete step {step.value}; "
                f"current step is {self.current_step.value}"
            )
        return self._append_event(
            AgentEventType.STEP_COMPLETED,
            step,
            message,
            data,
        )

    def add_information(
        self,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> AgentEvent:
        self._ensure_active()
        return self._append_event(
            AgentEventType.INFORMATION,
            self.current_step,
            message,
            data,
        )

    def wait_for_user(self, questions: list[str]) -> AgentEvent:
        self._ensure_active()
        self.open_questions = list(questions)
        self.status = AgentStatus.WAITING_FOR_USER
        return self._append_event(
            AgentEventType.INFORMATION,
            self.current_step,
            "需要用户补充需求信息",
            {"questions": self.open_questions},
        )

    def resume(self) -> AgentEvent:
        if self.status != AgentStatus.WAITING_FOR_USER:
            raise ValueError("only a task waiting for user input can be resumed")
        self.status = AgentStatus.RUNNING
        return self._append_event(
            AgentEventType.INFORMATION,
            self.current_step,
            "已收到补充信息，继续执行任务",
        )

    def complete(self, report: str) -> AgentEvent:
        self._ensure_active()
        cleaned_report = report.strip()
        if not cleaned_report:
            raise ValueError("report cannot be empty when completing a task")

        self.report = cleaned_report
        self.status = AgentStatus.COMPLETED
        self.current_step = AgentStep.FINALIZE
        return self._append_event(
            AgentEventType.TASK_COMPLETED,
            AgentStep.FINALIZE,
            "测试分析任务已完成",
        )

    def fail(self, error_message: str) -> AgentEvent:
        self._ensure_not_terminal()
        self.error_message = error_message.strip() or "unknown error"
        self.status = AgentStatus.FAILED
        return self._append_event(
            AgentEventType.TASK_FAILED,
            self.current_step,
            "测试分析任务执行失败",
            {"error": self.error_message},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "requirement": self.requirement,
            "status": self.status.value,
            "current_step": self.current_step.value,
            "requirement_summary": self.requirement_summary,
            "modules": self.modules,
            "requirement_facts": self.requirement_facts,
            "business_rules": self.business_rules,
            "state_transitions": self.state_transitions,
            "inferred_risks": self.inferred_risks,
            "open_questions": self.open_questions,
            "local_bug_knowledge": self.local_bug_knowledge,
            "rag_context": self.rag_context,
            "rag_max_score": self.rag_max_score,
            "rag_matched_count": self.rag_matched_count,
            "knowledge_retrieval_status": (
                self.knowledge_retrieval_status.value
            ),
            "rag_error_message": self.rag_error_message,
            "test_points": self.test_points,
            "review_result": self.review_result,
            "review_passed": self.review_passed,
            "review_threshold": self.review_threshold,
            "revision_count": self.revision_count,
            "report": self.report,
            "error_message": self.error_message,
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def _ensure_active(self) -> None:
        self._ensure_not_terminal()
        if self.status == AgentStatus.WAITING_FOR_USER:
            raise ValueError(
                "task is waiting for user input and must be resumed first"
            )

    def _ensure_not_terminal(self) -> None:
        if self.status in TERMINAL_STATUSES:
            raise ValueError(
                f"task {self.task_id} is already {self.status.value}"
            )

    def _append_event(
        self,
        event_type: AgentEventType,
        step: AgentStep,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> AgentEvent:
        event = AgentEvent(
            event_type=event_type,
            step=step,
            message=message,
            data=data or {},
        )
        self.events.append(event)
        self.updated_at = event.occurred_at
        return event
