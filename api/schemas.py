from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1)


class ClarificationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str | None]


class BusinessRuleConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str = Field(min_length=1)
    confirmed: bool


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1)
    feedback_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    content: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class TaskResponse(BaseModel):
    state: dict[str, Any]
    decisions: list[Any]
    auto_run: bool
    has_pending_clarifications: bool
    execution_steps: int
    in_progress: bool
    next_action: str | None
    metrics: list[Any]
    revision_limit_reached: bool
    performance_summary: dict[str, Any]


class BackgroundRunResponse(BaseModel):
    task_id: str
    status: str
    accepted: bool
    error: str | None = None
