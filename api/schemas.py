from datetime import datetime
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


class TaskProgressResponse(BaseModel):
    task_id: str
    status: str
    status_label: str
    current_step: str
    stage_label: str
    execution_status: str
    next_action: str | None
    waiting_for_clarifications: bool
    waiting_for_business_rules: bool
    revision_limit_reached: bool
    test_point_count: int
    reviewer_score: int | float | None
    automatic_revision_count: int
    human_revision_count: int
    recent_events: list[dict[str, Any]]
    error: str | None


class TaskSummaryResponse(BaseModel):
    task_id: str
    task_name: str
    status: str
    current_step: str
    requirement_summary: str
    event_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class TaskSummaryPageResponse(BaseModel):
    items: list[TaskSummaryResponse]
    total: int
    offset: int
    limit: int


class KnowledgeAssetConfirmationRequest(BaseModel):
    user_confirmed: bool
    data_safety_confirmed: bool


class KnowledgeAssetPublicationResponse(BaseModel):
    asset_id: str
    source_task_id: str
    asset_version: int
    status: str
    test_point_count: int
    reviewer_score: int
    chunk_count: int
    omitted_chunk_count: int
