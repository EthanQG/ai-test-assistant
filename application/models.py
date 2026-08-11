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

    def to_dict(self) -> dict[str, Any]:
        """Return a detached transport representation for UI/API adapters."""
        return {
            "state": deepcopy(self._state_data),
            "decisions": deepcopy(list(self.decisions)),
            "auto_run": self.auto_run,
            "has_pending_clarifications": self.has_pending_clarifications,
            "execution_steps": self.execution_steps,
            "in_progress": self.in_progress,
            "next_action": self.next_action,
            "metrics": deepcopy(list(self.metrics)),
            "revision_limit_reached": self.revision_limit_reached,
            "performance_summary": self.performance_summary,
        }

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

    @property
    def service_metrics(self) -> tuple[dict[str, Any], ...]:
        metrics: list[dict[str, Any]] = []
        for event in self._state_data["events"]:
            raw_metrics = event.data.get("service_metrics", [])
            if isinstance(raw_metrics, list):
                metrics.extend(
                    deepcopy(item)
                    for item in raw_metrics
                    if isinstance(item, dict)
                )
        return tuple(metrics)

    @property
    def performance_summary(self) -> dict[str, Any]:
        duration_by_dependency: dict[str, int] = {}
        token_totals = {
            "provider": {"input": 0, "output": 0, "total": 0},
            "estimated": {"input": 0, "output": 0, "total": 0},
        }
        error_counts: dict[str, int] = {}
        retry_count = 0
        for metric in self.service_metrics:
            dependency = str(metric.get("dependency") or "unknown")
            duration_by_dependency[dependency] = (
                duration_by_dependency.get(dependency, 0)
                + int(metric.get("duration_ms") or 0)
            )
            retry_count += int(metric.get("retry_count") or 0)
            error_category = metric.get("error_category")
            if error_category:
                key = str(error_category)
                error_counts[key] = error_counts.get(key, 0) + 1
            usage = metric.get("token_usage")
            if not isinstance(usage, dict):
                continue
            source = usage.get("source")
            if source not in token_totals:
                continue
            target = token_totals[source]
            target["input"] += int(usage.get("input_tokens") or 0)
            target["output"] += int(usage.get("output_tokens") or 0)
            target["total"] += int(usage.get("total_tokens") or 0)
        return {
            "task_execution_seconds": self.total_execution_seconds,
            "service_call_count": len(self.service_metrics),
            "duration_by_dependency_ms": duration_by_dependency,
            "token_totals_by_source": token_totals,
            "retry_count": retry_count,
            "error_counts": error_counts,
        }
