from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agent import (
    AgentStatus,
    AgentStep,
    OrchestratorDecision,
    TestAnalysisState,
)


@dataclass(frozen=True)
class NodeExecutionMetric:
    action: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    succeeded: bool
    error_type: str | None = None


@dataclass
class TaskRecord:
    state: TestAnalysisState
    decisions: list[OrchestratorDecision] = field(default_factory=list)
    auto_run: bool = False
    pending_clarifications: dict[str, str | None] | None = None
    execution_steps: int = 0
    in_progress: bool = False
    next_action: str | None = None
    metrics: list[NodeExecutionMetric] = field(default_factory=list)


@dataclass(frozen=True)
class FeedbackView:
    feedback_id: str
    action: str
    feedback_type: str
    target: str
    content: str
    reason: str
    status: str


@dataclass(frozen=True)
class TaskView:
    """Read-only application view built from an isolated State snapshot."""

    _state_data: dict[str, Any] = field(repr=False)
    decisions: tuple[OrchestratorDecision, ...]
    auto_run: bool
    has_pending_clarifications: bool
    execution_steps: int
    in_progress: bool
    next_action: str | None
    metrics: tuple[NodeExecutionMetric, ...]

    @classmethod
    def from_record(cls, record: TaskRecord) -> "TaskView":
        state_data = deepcopy(vars(record.state))
        return cls(
            _state_data=state_data,
            decisions=tuple(deepcopy(record.decisions)),
            auto_run=record.auto_run,
            has_pending_clarifications=(
                record.pending_clarifications is not None
            ),
            execution_steps=record.execution_steps,
            in_progress=record.in_progress,
            next_action=record.next_action,
            metrics=tuple(deepcopy(record.metrics)),
        )

    def __getattr__(self, name: str) -> Any:
        if name not in self._state_data:
            raise AttributeError(name)
        return deepcopy(self._state_data[name])

    @property
    def task_id(self) -> str:
        return str(self._state_data["task_id"])

    @property
    def status(self) -> AgentStatus:
        return self._state_data["status"]

    @property
    def current_step(self) -> AgentStep:
        return self._state_data["current_step"]

    @property
    def pending_business_feedback(self) -> tuple[FeedbackView, ...]:
        return tuple(
            FeedbackView(
                feedback_id=str(payload["feedback_id"]),
                action=str(payload["action"]),
                feedback_type=str(payload["feedback_type"]),
                target=str(payload["target"]),
                content=str(payload["content"]),
                reason=str(payload["reason"]),
                status=str(payload["status"]),
            )
            for payload in self._state_data["human_feedback"]
            if payload.get("status") == "pending_confirmation"
        )

    @property
    def revision_limit_reached(self) -> bool:
        return bool(
            self.decisions
            and self.decisions[-1].action.value
            == "revision_limit_reached"
        )

    @property
    def total_execution_seconds(self) -> float:
        return round(
            sum(metric.duration_seconds for metric in self.metrics),
            2,
        )
