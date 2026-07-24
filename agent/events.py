from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStep(str, Enum):
    INITIALIZE = "initialize"
    ANALYZE_REQUIREMENT = "analyze_requirement"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    GENERATE_TEST_POINTS = "generate_test_points"
    REVIEW_TEST_POINTS = "review_test_points"
    COLLECT_HUMAN_FEEDBACK = "collect_human_feedback"
    REVISE_TEST_POINTS = "revise_test_points"
    FINALIZE = "finalize"


class AgentEventType(str, Enum):
    TASK_CREATED = "task_created"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    INFORMATION = "information"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


@dataclass(frozen=True)
class AgentEvent:
    event_type: AgentEventType
    step: AgentStep
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "step": self.step.value,
            "message": self.message,
            "data": self.data,
            "occurred_at": self.occurred_at.isoformat(),
        }
