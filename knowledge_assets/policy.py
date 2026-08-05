from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from agent import (
    AgentStatus,
    HumanFeedbackHandler,
    InferredRisk,
    TestAnalysisState,
    TestPoint,
    TestPointReviewResult,
)

from .models import (
    KnowledgeAsset,
    KnowledgeAssetStatus,
    StructuredRequirement,
    build_content_hash,
)


class KnowledgeAssetAdmissionError(ValueError):
    """Raised when a task is not safe to publish as reusable knowledge."""


class KnowledgeAssetAdmissionPolicy:
    """Creates immutable asset candidates from explicitly confirmed tasks."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        asset_id_factory: Callable[[], str] | None = None,
    ):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._asset_id_factory = asset_id_factory or (
            lambda: str(uuid4())
        )

    def admit(
        self,
        state: TestAnalysisState,
        *,
        user_confirmed: bool,
        data_safety_confirmed: bool,
        asset_version: int,
    ) -> KnowledgeAsset:
        if user_confirmed is not True:
            raise KnowledgeAssetAdmissionError(
                "user must explicitly confirm knowledge publication"
            )
        if data_safety_confirmed is not True:
            raise KnowledgeAssetAdmissionError(
                "user must confirm data safety before publication"
            )
        if state.status != AgentStatus.COMPLETED:
            raise KnowledgeAssetAdmissionError(
                "only completed tasks can become knowledge assets"
            )
        if state.review_passed is not True or not state.review_result:
            raise KnowledgeAssetAdmissionError(
                "task must pass Reviewer before publication"
            )
        if state.open_questions:
            raise KnowledgeAssetAdmissionError(
                "open questions must be resolved before publication"
            )
        if HumanFeedbackHandler.ready_feedback(state) or (
            HumanFeedbackHandler.pending_confirmation_feedback(state)
        ):
            raise KnowledgeAssetAdmissionError(
                "pending human feedback must be resolved before publication"
            )
        if not state.final_result or not state.report.strip():
            raise KnowledgeAssetAdmissionError(
                "finalized result and report are required"
            )
        if not state.requirement_summary.strip():
            raise KnowledgeAssetAdmissionError(
                "structured requirement summary is required"
            )
        if not state.requirement_facts:
            raise KnowledgeAssetAdmissionError(
                "structured requirement facts are required"
            )

        try:
            test_points = tuple(
                TestPoint.from_dict(payload)
                for payload in state.test_points
            )
            review = TestPointReviewResult.from_dict(state.review_result)
            risks = tuple(
                InferredRisk.from_dict(payload)
                for payload in state.inferred_risks
            )
        except Exception as exc:
            raise KnowledgeAssetAdmissionError(
                f"task contains invalid structured result: {exc}"
            ) from exc

        self._validate_review(state, review)
        self._validate_final_result(state)
        timestamp = self._aware_now()
        structured_requirement = StructuredRequirement(
            summary=state.requirement_summary.strip(),
            modules=tuple(state.modules),
            requirement_facts=tuple(state.requirement_facts),
            business_rules=tuple(state.business_rules),
            state_transitions=tuple(state.state_transitions),
            inferred_risks=risks,
        )
        content_hash = build_content_hash(
            state.requirement,
            structured_requirement,
            test_points,
        )
        return KnowledgeAsset(
            asset_id=self._asset_id_factory(),
            source_task_id=state.task_id,
            asset_version=asset_version,
            content_hash=content_hash,
            status=KnowledgeAssetStatus.PENDING_INDEX,
            original_requirement=state.requirement,
            structured_requirement=structured_requirement,
            test_points=test_points,
            review_result=review,
            final_report=state.report,
            user_confirmed=True,
            data_safety_confirmed=True,
            confirmed_at=timestamp,
            created_at=timestamp,
        )

    @staticmethod
    def _validate_review(
        state: TestAnalysisState,
        review: TestPointReviewResult,
    ) -> None:
        if review.overall_score < state.review_threshold:
            raise KnowledgeAssetAdmissionError(
                "Reviewer score is below the configured threshold"
            )
        if review.uncovered_requirement_count:
            raise KnowledgeAssetAdmissionError(
                "Reviewer coverage still contains uncovered facts"
            )
        if review.hallucination_issues:
            raise KnowledgeAssetAdmissionError(
                "Reviewer still reports unsupported assertions"
            )
        reviewed_facts = {
            item.requirement_fact for item in review.requirement_coverage
        }
        if reviewed_facts != set(state.requirement_facts):
            raise KnowledgeAssetAdmissionError(
                "Reviewer evidence does not match requirement facts"
            )

    @staticmethod
    def _validate_final_result(state: TestAnalysisState) -> None:
        final_test_points = state.final_result.get("test_points")
        if final_test_points != state.test_points:
            raise KnowledgeAssetAdmissionError(
                "final result is stale relative to current test points"
            )
        quality = state.final_result.get("quality_summary")
        if not isinstance(quality, dict) or (
            quality.get("overall_score")
            != state.review_result.get("overall_score")
        ):
            raise KnowledgeAssetAdmissionError(
                "final result is stale relative to Reviewer result"
            )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KnowledgeAssetAdmissionError(
                "knowledge asset clock must include timezone"
            )
        return value.astimezone(timezone.utc)
