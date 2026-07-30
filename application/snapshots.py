from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, TypeVar

from agent import (
    AgentEvent,
    AgentEventType,
    AgentStatus,
    AgentStep,
    FeedbackStatus,
    HumanFeedback,
    InferredRisk,
    KnowledgeRetrievalStatus,
    OrchestratorAction,
    OrchestratorDecision,
    ReviewDimensionScores,
    TestAnalysisState,
    TestPoint,
    TestPointReviewResult,
)

from .models import NodeExecutionMetric, TaskRecord


SNAPSHOT_SCHEMA_VERSION = 1


class SnapshotError(ValueError):
    """Base error for invalid or unsupported task snapshots."""


class SnapshotValidationError(SnapshotError):
    """Raised when a snapshot violates the declared schema."""


class UnsupportedSnapshotVersionError(SnapshotError):
    """Raised when no reader exists for a snapshot schema version."""


EnumType = TypeVar("EnumType")


class TaskSnapshotSerializer:
    """Serializes a complete restorable task without runtime services."""

    _TOP_LEVEL_FIELDS = {
        "schema_version",
        "task_id",
        "state",
        "application",
    }
    _STATE_FIELDS = {
        "requirement",
        "status",
        "current_step",
        "requirement_summary",
        "modules",
        "requirement_facts",
        "business_rules",
        "state_transitions",
        "inferred_risks",
        "open_questions",
        "user_clarifications",
        "deferred_questions",
        "local_bug_knowledge",
        "rag_context",
        "rag_max_score",
        "rag_matched_count",
        "knowledge_retrieval_status",
        "rag_error_message",
        "test_points",
        "review_result",
        "review_passed",
        "review_threshold",
        "review_history",
        "revision_count",
        "automatic_revision_count",
        "human_revision_count",
        "max_revision_count",
        "revision_history",
        "human_feedback",
        "final_result",
        "report",
        "error_message",
        "events",
        "created_at",
        "updated_at",
    }
    _APPLICATION_FIELDS = {
        "decisions",
        "auto_run",
        "pending_clarifications",
        "execution_steps",
        "next_action",
        "metrics",
    }
    _EVENT_FIELDS = {
        "event_type",
        "step",
        "message",
        "data",
        "occurred_at",
    }
    _DECISION_FIELDS = {"action", "reason", "duration_seconds"}
    _METRIC_FIELDS = {
        "action",
        "started_at",
        "finished_at",
        "duration_seconds",
        "succeeded",
        "error_type",
    }

    @classmethod
    def to_dict(cls, record: TaskRecord) -> dict[str, Any]:
        state = record.state
        cls._require_exact_fields(
            vars(state),
            cls._STATE_FIELDS | {"task_id"},
            "AgentState runtime fields",
        )
        cls._require_exact_fields(
            vars(record),
            cls._APPLICATION_FIELDS | {"state", "in_progress"},
            "TaskRecord runtime fields",
        )
        payload = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "task_id": state.task_id,
            "state": {
                "requirement": state.requirement,
                "status": state.status.value,
                "current_step": state.current_step.value,
                "requirement_summary": state.requirement_summary,
                "modules": list(state.modules),
                "requirement_facts": list(state.requirement_facts),
                "business_rules": list(state.business_rules),
                "state_transitions": list(state.state_transitions),
                "inferred_risks": deepcopy(state.inferred_risks),
                "open_questions": list(state.open_questions),
                "user_clarifications": deepcopy(
                    state.user_clarifications
                ),
                "deferred_questions": list(state.deferred_questions),
                "local_bug_knowledge": state.local_bug_knowledge,
                "rag_context": state.rag_context,
                "rag_max_score": state.rag_max_score,
                "rag_matched_count": state.rag_matched_count,
                "knowledge_retrieval_status": (
                    state.knowledge_retrieval_status.value
                ),
                "rag_error_message": state.rag_error_message,
                "test_points": deepcopy(state.test_points),
                "review_result": deepcopy(state.review_result),
                "review_passed": state.review_passed,
                "review_threshold": state.review_threshold,
                "review_history": deepcopy(state.review_history),
                "revision_count": state.revision_count,
                "automatic_revision_count": (
                    state.automatic_revision_count
                ),
                "human_revision_count": state.human_revision_count,
                "max_revision_count": state.max_revision_count,
                "revision_history": deepcopy(state.revision_history),
                "human_feedback": deepcopy(state.human_feedback),
                "final_result": deepcopy(state.final_result),
                "report": state.report,
                "error_message": state.error_message,
                "events": [
                    cls._event_to_dict(event) for event in state.events
                ],
                "created_at": cls._datetime_to_text(
                    state.created_at,
                    "state.created_at",
                ),
                "updated_at": cls._datetime_to_text(
                    state.updated_at,
                    "state.updated_at",
                ),
            },
            "application": {
                "decisions": [
                    {
                        "action": decision.action.value,
                        "reason": decision.reason,
                        "duration_seconds": decision.duration_seconds,
                    }
                    for decision in record.decisions
                ],
                "auto_run": record.auto_run,
                "pending_clarifications": deepcopy(
                    record.pending_clarifications
                ),
                "execution_steps": record.execution_steps,
                "next_action": record.next_action,
                "metrics": [
                    cls._metric_to_dict(metric)
                    for metric in record.metrics
                ],
            },
        }
        cls._ensure_json_value(payload, "snapshot")
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        root = cls._mapping(data, "snapshot")
        cls._require_exact_fields(
            root,
            cls._TOP_LEVEL_FIELDS,
            "snapshot",
        )
        version = cls._integer(
            root["schema_version"],
            "schema_version",
            minimum=1,
        )
        if version != SNAPSHOT_SCHEMA_VERSION:
            raise UnsupportedSnapshotVersionError(
                f"unsupported snapshot schema_version: {version}"
            )

        task_id = cls._non_empty_text(root["task_id"], "task_id")
        state_data = cls._mapping(root["state"], "state")
        cls._require_exact_fields(
            state_data,
            cls._STATE_FIELDS,
            "state",
        )
        application_data = cls._mapping(
            root["application"],
            "application",
        )
        cls._require_exact_fields(
            application_data,
            cls._APPLICATION_FIELDS,
            "application",
        )

        state = cls._state_from_dict(task_id, state_data)
        decisions = cls._decisions_from_list(
            application_data["decisions"]
        )
        pending_clarifications = cls._pending_clarifications(
            application_data["pending_clarifications"]
        )
        next_action = cls._optional_enum_text(
            application_data["next_action"],
            OrchestratorAction,
            "application.next_action",
        )
        metrics = cls._metrics_from_list(application_data["metrics"])

        return TaskRecord(
            state=state,
            decisions=decisions,
            auto_run=cls._boolean(
                application_data["auto_run"],
                "application.auto_run",
            ),
            pending_clarifications=pending_clarifications,
            execution_steps=cls._integer(
                application_data["execution_steps"],
                "application.execution_steps",
                minimum=0,
            ),
            # A process-local execution guard is never restored as a lease.
            in_progress=False,
            next_action=next_action,
            metrics=metrics,
        )

    @classmethod
    def to_json(cls, record: TaskRecord) -> str:
        return json.dumps(
            cls.to_dict(record),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> TaskRecord:
        if not isinstance(payload, str) or not payload.strip():
            raise SnapshotValidationError(
                "snapshot JSON must be a non-empty string"
            )
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SnapshotValidationError(
                "snapshot JSON is invalid: "
                f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
            ) from exc
        return cls.from_dict(data)

    @staticmethod
    def migrate_snapshot(
        data: dict[str, Any],
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        if (
            from_version == SNAPSHOT_SCHEMA_VERSION
            and to_version == SNAPSHOT_SCHEMA_VERSION
        ):
            return deepcopy(data)
        raise UnsupportedSnapshotVersionError(
            "no snapshot migration path from "
            f"{from_version} to {to_version}"
        )

    @classmethod
    def _state_from_dict(
        cls,
        task_id: str,
        data: dict[str, Any],
    ) -> TestAnalysisState:
        requirement = cls._non_empty_text(
            data["requirement"],
            "state.requirement",
        )
        status = cls._enum(
            data["status"],
            AgentStatus,
            "state.status",
        )
        current_step = cls._enum(
            data["current_step"],
            AgentStep,
            "state.current_step",
        )
        try:
            inferred_risks = [
                InferredRisk.from_dict(item).to_dict()
                for item in cls._list(
                    data["inferred_risks"],
                    "state.inferred_risks",
                )
            ]
        except Exception as exc:
            raise SnapshotValidationError(
                f"state.inferred_risks is invalid: {exc}"
            ) from exc
        user_clarifications = cls._user_clarifications(
            data["user_clarifications"]
        )
        test_points = cls._test_point_list(
            data["test_points"],
            "state.test_points",
        )
        review_result = cls._review_result(data["review_result"])
        review_history = cls._review_history(data["review_history"])
        revision_history = cls._revision_history(
            data["revision_history"]
        )
        human_feedback = [
            cls._human_feedback(item)
            for item in cls._list(
                data["human_feedback"],
                "human_feedback",
            )
        ]
        final_result = cls._final_result(data["final_result"])
        events = cls._events_from_list(data["events"])
        created_at = cls._datetime_from_text(
            data["created_at"],
            "state.created_at",
        )
        updated_at = cls._datetime_from_text(
            data["updated_at"],
            "state.updated_at",
        )

        state = TestAnalysisState(requirement=requirement, task_id=task_id)
        state.status = status
        state.current_step = current_step
        state.requirement_summary = cls._text(
            data["requirement_summary"],
            "state.requirement_summary",
        )
        state.modules = cls._text_list(data["modules"], "state.modules")
        state.requirement_facts = cls._text_list(
            data["requirement_facts"],
            "state.requirement_facts",
        )
        state.business_rules = cls._text_list(
            data["business_rules"],
            "state.business_rules",
        )
        state.state_transitions = cls._text_list(
            data["state_transitions"],
            "state.state_transitions",
        )
        state.inferred_risks = inferred_risks
        state.open_questions = cls._text_list(
            data["open_questions"],
            "state.open_questions",
        )
        state.user_clarifications = user_clarifications
        state.deferred_questions = cls._text_list(
            data["deferred_questions"],
            "state.deferred_questions",
        )
        state.local_bug_knowledge = cls._text(
            data["local_bug_knowledge"],
            "state.local_bug_knowledge",
        )
        state.rag_context = cls._text(
            data["rag_context"],
            "state.rag_context",
        )
        state.rag_max_score = cls._number(
            data["rag_max_score"],
            "state.rag_max_score",
            minimum=0,
        )
        state.rag_matched_count = cls._integer(
            data["rag_matched_count"],
            "state.rag_matched_count",
            minimum=0,
        )
        state.knowledge_retrieval_status = cls._enum(
            data["knowledge_retrieval_status"],
            KnowledgeRetrievalStatus,
            "state.knowledge_retrieval_status",
        )
        state.rag_error_message = cls._optional_text(
            data["rag_error_message"],
            "state.rag_error_message",
        )
        state.test_points = test_points
        state.review_result = review_result
        state.review_passed = cls._optional_boolean(
            data["review_passed"],
            "state.review_passed",
        )
        state.review_threshold = cls._integer(
            data["review_threshold"],
            "state.review_threshold",
            minimum=0,
            maximum=100,
        )
        state.review_history = review_history
        state.revision_count = cls._integer(
            data["revision_count"],
            "state.revision_count",
            minimum=0,
        )
        state.automatic_revision_count = cls._integer(
            data["automatic_revision_count"],
            "state.automatic_revision_count",
            minimum=0,
        )
        state.human_revision_count = cls._integer(
            data["human_revision_count"],
            "state.human_revision_count",
            minimum=0,
        )
        state.max_revision_count = cls._integer(
            data["max_revision_count"],
            "state.max_revision_count",
            minimum=0,
        )
        state.revision_history = revision_history
        state.human_feedback = human_feedback
        state.final_result = final_result
        state.report = cls._text(data["report"], "state.report")
        state.error_message = cls._optional_text(
            data["error_message"],
            "state.error_message",
        )
        state.events = events
        state.created_at = created_at
        state.updated_at = updated_at
        return state

    @classmethod
    def _event_to_dict(cls, event: AgentEvent) -> dict[str, Any]:
        return {
            "event_type": event.event_type.value,
            "step": event.step.value,
            "message": event.message,
            "data": deepcopy(event.data),
            "occurred_at": cls._datetime_to_text(
                event.occurred_at,
                "event.occurred_at",
            ),
        }

    @classmethod
    def _events_from_list(cls, value: Any) -> list[AgentEvent]:
        events = []
        for index, item in enumerate(cls._list(value, "state.events")):
            path = f"state.events[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(
                payload,
                cls._EVENT_FIELDS,
                path,
            )
            events.append(
                AgentEvent(
                    event_type=cls._enum(
                        payload["event_type"],
                        AgentEventType,
                        f"{path}.event_type",
                    ),
                    step=cls._enum(
                        payload["step"],
                        AgentStep,
                        f"{path}.step",
                    ),
                    message=cls._non_empty_text(
                        payload["message"],
                        f"{path}.message",
                    ),
                    data=cls._json_mapping(
                        payload["data"],
                        f"{path}.data",
                    ),
                    occurred_at=cls._datetime_from_text(
                        payload["occurred_at"],
                        f"{path}.occurred_at",
                    ),
                )
            )
        return events

    @classmethod
    def _decisions_from_list(
        cls,
        value: Any,
    ) -> list[OrchestratorDecision]:
        decisions = []
        for index, item in enumerate(
            cls._list(value, "application.decisions")
        ):
            path = f"application.decisions[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(
                payload,
                cls._DECISION_FIELDS,
                path,
            )
            decisions.append(
                OrchestratorDecision(
                    action=cls._enum(
                        payload["action"],
                        OrchestratorAction,
                        f"{path}.action",
                    ),
                    reason=cls._non_empty_text(
                        payload["reason"],
                        f"{path}.reason",
                    ),
                    duration_seconds=cls._optional_number(
                        payload["duration_seconds"],
                        f"{path}.duration_seconds",
                        minimum=0,
                    ),
                )
            )
        return decisions

    @classmethod
    def _metric_to_dict(
        cls,
        metric: NodeExecutionMetric,
    ) -> dict[str, Any]:
        return {
            "action": metric.action,
            "started_at": cls._datetime_to_text(
                metric.started_at,
                "metric.started_at",
            ),
            "finished_at": cls._datetime_to_text(
                metric.finished_at,
                "metric.finished_at",
            ),
            "duration_seconds": metric.duration_seconds,
            "succeeded": metric.succeeded,
            "error_type": metric.error_type,
        }

    @classmethod
    def _metrics_from_list(
        cls,
        value: Any,
    ) -> list[NodeExecutionMetric]:
        metrics = []
        for index, item in enumerate(
            cls._list(value, "application.metrics")
        ):
            path = f"application.metrics[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(
                payload,
                cls._METRIC_FIELDS,
                path,
            )
            started_at = cls._datetime_from_text(
                payload["started_at"],
                f"{path}.started_at",
            )
            finished_at = cls._datetime_from_text(
                payload["finished_at"],
                f"{path}.finished_at",
            )
            if finished_at < started_at:
                raise SnapshotValidationError(
                    f"{path}.finished_at cannot precede started_at"
                )
            metrics.append(
                NodeExecutionMetric(
                    action=cls._non_empty_text(
                        payload["action"],
                        f"{path}.action",
                    ),
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=cls._number(
                        payload["duration_seconds"],
                        f"{path}.duration_seconds",
                        minimum=0,
                    ),
                    succeeded=cls._boolean(
                        payload["succeeded"],
                        f"{path}.succeeded",
                    ),
                    error_type=cls._optional_text(
                        payload["error_type"],
                        f"{path}.error_type",
                    ),
                )
            )
        return metrics

    @classmethod
    def _review_result(
        cls,
        value: Any,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        try:
            return TestPointReviewResult.from_dict(
                cls._mapping(value, "state.review_result")
            ).to_dict()
        except Exception as exc:
            raise SnapshotValidationError(
                f"state.review_result is invalid: {exc}"
            ) from exc

    @classmethod
    def _review_history(cls, value: Any) -> list[dict[str, Any]]:
        history = []
        expected = {
            "review_round",
            "revision_count",
            "automatic_revision_count",
            "human_revision_count",
            "passed",
            "result",
        }
        for index, item in enumerate(
            cls._list(value, "state.review_history")
        ):
            path = f"state.review_history[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(payload, expected, path)
            history.append(
                {
                    "review_round": cls._integer(
                        payload["review_round"],
                        f"{path}.review_round",
                        minimum=1,
                    ),
                    "revision_count": cls._integer(
                        payload["revision_count"],
                        f"{path}.revision_count",
                        minimum=0,
                    ),
                    "automatic_revision_count": cls._integer(
                        payload["automatic_revision_count"],
                        f"{path}.automatic_revision_count",
                        minimum=0,
                    ),
                    "human_revision_count": cls._integer(
                        payload["human_revision_count"],
                        f"{path}.human_revision_count",
                        minimum=0,
                    ),
                    "passed": cls._boolean(
                        payload["passed"],
                        f"{path}.passed",
                    ),
                    "result": cls._required_review_result(
                        payload["result"],
                        f"{path}.result",
                    ),
                }
            )
        return history

    @classmethod
    def _revision_history(cls, value: Any) -> list[dict[str, Any]]:
        history = []
        expected = {
            "revision_count",
            "revision_source",
            "before_test_points",
            "after_test_points",
            "review_result",
            "applied_feedback_ids",
        }
        for index, item in enumerate(
            cls._list(value, "state.revision_history")
        ):
            path = f"state.revision_history[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(payload, expected, path)
            source = cls._non_empty_text(
                payload["revision_source"],
                f"{path}.revision_source",
            )
            if source not in {"automatic_review", "human_feedback"}:
                raise SnapshotValidationError(
                    f"{path}.revision_source is invalid: {source}"
                )
            history.append(
                {
                    "revision_count": cls._integer(
                        payload["revision_count"],
                        f"{path}.revision_count",
                        minimum=1,
                    ),
                    "revision_source": source,
                    "before_test_points": cls._test_point_list(
                        payload["before_test_points"],
                        f"{path}.before_test_points",
                    ),
                    "after_test_points": cls._test_point_list(
                        payload["after_test_points"],
                        f"{path}.after_test_points",
                    ),
                    "review_result": cls._required_review_result(
                        payload["review_result"],
                        f"{path}.review_result",
                    ),
                    "applied_feedback_ids": cls._text_list(
                        payload["applied_feedback_ids"],
                        f"{path}.applied_feedback_ids",
                    ),
                }
            )
        return history

    @classmethod
    def _required_review_result(
        cls,
        value: Any,
        path: str,
    ) -> dict[str, Any]:
        result = cls._review_result(value)
        if result is None:
            raise SnapshotValidationError(f"{path} must be an object")
        return result

    @classmethod
    def _final_result(
        cls,
        value: Any,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        path = "state.final_result"
        payload = cls._mapping(value, path)
        expected = {
            "requirement_summary",
            "modules",
            "test_point_count",
            "category_counts",
            "priority_counts",
            "source_counts",
            "coverage_summary",
            "quality_summary",
            "inferred_risks",
            "warnings",
            "test_points",
        }
        cls._require_exact_fields(payload, expected, path)

        coverage = cls._mapping(
            payload["coverage_summary"],
            f"{path}.coverage_summary",
        )
        cls._require_exact_fields(
            coverage,
            {"total", "covered", "partial", "missing"},
            f"{path}.coverage_summary",
        )
        quality = cls._mapping(
            payload["quality_summary"],
            f"{path}.quality_summary",
        )
        quality_fields = {
            "overall_score",
            "review_threshold",
            "dimension_scores",
            "review_rounds",
            "revision_count",
            "automatic_revision_count",
            "human_revision_count",
        }
        cls._require_exact_fields(
            quality,
            quality_fields,
            f"{path}.quality_summary",
        )
        try:
            dimension_scores = ReviewDimensionScores.from_dict(
                quality["dimension_scores"]
            ).to_dict()
            risks = [
                InferredRisk.from_dict(item).to_dict()
                for item in cls._list(
                    payload["inferred_risks"],
                    f"{path}.inferred_risks",
                )
            ]
        except Exception as exc:
            raise SnapshotValidationError(
                f"{path} contains invalid domain data: {exc}"
            ) from exc

        test_points = cls._test_point_list(
            payload["test_points"],
            f"{path}.test_points",
        )
        test_point_count = cls._integer(
            payload["test_point_count"],
            f"{path}.test_point_count",
            minimum=0,
        )
        if test_point_count != len(test_points):
            raise SnapshotValidationError(
                f"{path}.test_point_count does not match test_points"
            )
        return {
            "requirement_summary": cls._non_empty_text(
                payload["requirement_summary"],
                f"{path}.requirement_summary",
            ),
            "modules": cls._text_list(
                payload["modules"],
                f"{path}.modules",
            ),
            "test_point_count": test_point_count,
            "category_counts": cls._count_mapping(
                payload["category_counts"],
                f"{path}.category_counts",
            ),
            "priority_counts": cls._count_mapping(
                payload["priority_counts"],
                f"{path}.priority_counts",
            ),
            "source_counts": cls._count_mapping(
                payload["source_counts"],
                f"{path}.source_counts",
            ),
            "coverage_summary": {
                key: cls._integer(
                    coverage[key],
                    f"{path}.coverage_summary.{key}",
                    minimum=0,
                )
                for key in ("total", "covered", "partial", "missing")
            },
            "quality_summary": {
                "overall_score": cls._integer(
                    quality["overall_score"],
                    f"{path}.quality_summary.overall_score",
                    minimum=0,
                    maximum=100,
                ),
                "review_threshold": cls._integer(
                    quality["review_threshold"],
                    f"{path}.quality_summary.review_threshold",
                    minimum=0,
                    maximum=100,
                ),
                "dimension_scores": dimension_scores,
                "review_rounds": cls._integer(
                    quality["review_rounds"],
                    f"{path}.quality_summary.review_rounds",
                    minimum=0,
                ),
                "revision_count": cls._integer(
                    quality["revision_count"],
                    f"{path}.quality_summary.revision_count",
                    minimum=0,
                ),
                "automatic_revision_count": cls._integer(
                    quality["automatic_revision_count"],
                    (
                        f"{path}.quality_summary"
                        ".automatic_revision_count"
                    ),
                    minimum=0,
                ),
                "human_revision_count": cls._integer(
                    quality["human_revision_count"],
                    f"{path}.quality_summary.human_revision_count",
                    minimum=0,
                ),
            },
            "inferred_risks": risks,
            "warnings": cls._text_list(
                payload["warnings"],
                f"{path}.warnings",
            ),
            "test_points": test_points,
        }

    @classmethod
    def _count_mapping(
        cls,
        value: Any,
        path: str,
    ) -> dict[str, int]:
        payload = cls._mapping(value, path)
        return {
            cls._non_empty_text(key, f"{path} key"): cls._integer(
                count,
                f"{path}.{key}",
                minimum=0,
            )
            for key, count in payload.items()
        }

    @classmethod
    def _test_point_list(
        cls,
        value: Any,
        path: str,
    ) -> list[dict[str, Any]]:
        try:
            return [
                TestPoint.from_dict(item).to_dict()
                for item in cls._list(value, path)
            ]
        except Exception as exc:
            raise SnapshotValidationError(
                f"{path} is invalid: {exc}"
            ) from exc

    @classmethod
    def _human_feedback(cls, value: Any) -> dict[str, str]:
        payload = cls._mapping(value, "state.human_feedback[]")
        cls._require_exact_fields(
            payload,
            {
                "feedback_id",
                "action",
                "feedback_type",
                "target",
                "content",
                "reason",
                "status",
            },
            "state.human_feedback[]",
        )
        try:
            feedback = HumanFeedback.from_state_dict(
                payload
            )
        except Exception as exc:
            raise SnapshotValidationError(
                f"stored human feedback is invalid: {exc}"
            ) from exc
        if not isinstance(feedback.status, FeedbackStatus):
            raise SnapshotValidationError(
                "stored human feedback status is invalid"
            )
        return feedback.to_dict()

    @classmethod
    def _user_clarifications(
        cls,
        value: Any,
    ) -> list[dict[str, str]]:
        result = []
        for index, item in enumerate(
            cls._list(value, "state.user_clarifications")
        ):
            path = f"state.user_clarifications[{index}]"
            payload = cls._mapping(item, path)
            cls._require_exact_fields(
                payload,
                {"question", "answer"},
                path,
            )
            result.append(
                {
                    "question": cls._non_empty_text(
                        payload["question"],
                        f"{path}.question",
                    ),
                    "answer": cls._non_empty_text(
                        payload["answer"],
                        f"{path}.answer",
                    ),
                }
            )
        return result

    @classmethod
    def _pending_clarifications(
        cls,
        value: Any,
    ) -> dict[str, str | None] | None:
        if value is None:
            return None
        payload = cls._mapping(value, "application.pending_clarifications")
        result: dict[str, str | None] = {}
        for question, answer in payload.items():
            cleaned_question = cls._non_empty_text(
                question,
                "application.pending_clarifications question",
            )
            if answer is None:
                result[cleaned_question] = None
            else:
                result[cleaned_question] = cls._non_empty_text(
                    answer,
                    (
                        "application.pending_clarifications"
                        f"[{cleaned_question!r}]"
                    ),
                )
        return result

    @classmethod
    def _datetime_to_text(
        cls,
        value: datetime,
        path: str,
    ) -> str:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise SnapshotValidationError(
                f"{path} must be a timezone-aware datetime"
            )
        return value.astimezone(timezone.utc).isoformat()

    @classmethod
    def _datetime_from_text(
        cls,
        value: Any,
        path: str,
    ) -> datetime:
        if not isinstance(value, str):
            raise SnapshotValidationError(
                f"{path} must be an ISO 8601 string"
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise SnapshotValidationError(
                f"{path} must be a valid ISO 8601 datetime"
            ) from exc
        if parsed.utcoffset() is None:
            raise SnapshotValidationError(
                f"{path} must include a timezone offset"
            )
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _require_exact_fields(
        payload: dict[str, Any],
        expected: set[str],
        path: str,
    ) -> None:
        missing = expected - set(payload)
        unknown = set(payload) - expected
        if missing:
            raise SnapshotValidationError(
                f"{path} is missing required fields: "
                + ", ".join(sorted(missing))
            )
        if unknown:
            raise SnapshotValidationError(
                f"{path} contains unknown fields: "
                + ", ".join(sorted(unknown))
            )

    @staticmethod
    def _mapping(value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise SnapshotValidationError(f"{path} must be an object")
        if any(not isinstance(key, str) for key in value):
            raise SnapshotValidationError(
                f"{path} object keys must be strings"
            )
        return value

    @classmethod
    def _json_mapping(
        cls,
        value: Any,
        path: str,
    ) -> dict[str, Any]:
        payload = cls._mapping(value, path)
        cls._ensure_json_value(payload, path)
        return deepcopy(payload)

    @classmethod
    def _optional_json_mapping(
        cls,
        value: Any,
        path: str,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return cls._json_mapping(value, path)

    @staticmethod
    def _list(value: Any, path: str) -> list[Any]:
        if not isinstance(value, list):
            raise SnapshotValidationError(f"{path} must be a list")
        return value

    @classmethod
    def _text_list(cls, value: Any, path: str) -> list[str]:
        result = []
        for index, item in enumerate(cls._list(value, path)):
            result.append(
                cls._non_empty_text(item, f"{path}[{index}]")
            )
        return result

    @staticmethod
    def _text(value: Any, path: str) -> str:
        if not isinstance(value, str):
            raise SnapshotValidationError(f"{path} must be a string")
        return value

    @classmethod
    def _non_empty_text(cls, value: Any, path: str) -> str:
        text = cls._text(value, path)
        if not text.strip():
            raise SnapshotValidationError(
                f"{path} must be a non-empty string"
            )
        return text.strip()

    @classmethod
    def _optional_text(cls, value: Any, path: str) -> str | None:
        if value is None:
            return None
        return cls._text(value, path)

    @staticmethod
    def _boolean(value: Any, path: str) -> bool:
        if not isinstance(value, bool):
            raise SnapshotValidationError(f"{path} must be a boolean")
        return value

    @classmethod
    def _optional_boolean(
        cls,
        value: Any,
        path: str,
    ) -> bool | None:
        if value is None:
            return None
        return cls._boolean(value, path)

    @staticmethod
    def _integer(
        value: Any,
        path: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SnapshotValidationError(f"{path} must be an integer")
        if minimum is not None and value < minimum:
            raise SnapshotValidationError(
                f"{path} must be at least {minimum}"
            )
        if maximum is not None and value > maximum:
            raise SnapshotValidationError(
                f"{path} must be at most {maximum}"
            )
        return value

    @staticmethod
    def _number(
        value: Any,
        path: str,
        *,
        minimum: float | None = None,
    ) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SnapshotValidationError(f"{path} must be a number")
        number = float(value)
        if minimum is not None and number < minimum:
            raise SnapshotValidationError(
                f"{path} must be at least {minimum}"
            )
        return number

    @classmethod
    def _optional_number(
        cls,
        value: Any,
        path: str,
        *,
        minimum: float | None = None,
    ) -> float | None:
        if value is None:
            return None
        return cls._number(value, path, minimum=minimum)

    @staticmethod
    def _enum(value: Any, enum_type: type[EnumType], path: str) -> EnumType:
        if not isinstance(value, str):
            raise SnapshotValidationError(
                f"{path} must be a string enum value"
            )
        try:
            return enum_type(value)
        except ValueError as exc:
            raise SnapshotValidationError(
                f"{path} contains an invalid enum value: {value}"
            ) from exc

    @classmethod
    def _optional_enum_text(
        cls,
        value: Any,
        enum_type: type[EnumType],
        path: str,
    ) -> str | None:
        if value is None:
            return None
        return cls._enum(value, enum_type, path).value

    @classmethod
    def _ensure_json_value(cls, value: Any, path: str) -> None:
        if value is None or isinstance(value, (str, bool, int)):
            return
        if isinstance(value, float):
            if value != value or value in {float("inf"), float("-inf")}:
                raise SnapshotValidationError(
                    f"{path} contains a non-finite number"
                )
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                cls._ensure_json_value(item, f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise SnapshotValidationError(
                        f"{path} object keys must be strings"
                    )
                cls._ensure_json_value(item, f"{path}.{key}")
            return
        raise SnapshotValidationError(
            f"{path} contains unsupported runtime value "
            f"{type(value).__name__}"
        )


def migrate_snapshot(
    data: dict[str, Any],
    from_version: int,
    to_version: int,
) -> dict[str, Any]:
    return TaskSnapshotSerializer.migrate_snapshot(
        data,
        from_version,
        to_version,
    )
