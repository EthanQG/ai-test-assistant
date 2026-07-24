from dataclasses import dataclass, replace
from enum import Enum
from typing import Any
from uuid import uuid4

from .events import AgentStep
from .state import AgentStatus, TestAnalysisState


class HumanFeedbackValidationError(ValueError):
    """Raised when human feedback violates the feedback contract."""


class FeedbackAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"
    UPDATE_PRIORITY = "update_priority"


class FeedbackType(str, Enum):
    TEST_SUGGESTION = "test_suggestion"
    BUSINESS_RULE = "business_rule"


class FeedbackStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    READY = "ready"
    APPLIED = "applied"


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HumanFeedbackValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


@dataclass(frozen=True)
class HumanFeedback:
    action: FeedbackAction
    feedback_type: FeedbackType
    target: str
    content: str
    reason: str
    status: FeedbackStatus
    feedback_id: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HumanFeedback":
        if not isinstance(payload, dict):
            raise HumanFeedbackValidationError(
                "feedback must be an object"
            )
        expected_fields = {
            "action",
            "feedback_type",
            "target",
            "content",
            "reason",
        }
        if set(payload) != expected_fields:
            raise HumanFeedbackValidationError(
                "feedback fields are invalid"
            )
        try:
            action = FeedbackAction(_required_text(payload, "action"))
        except ValueError as exc:
            raise HumanFeedbackValidationError(
                "action must be add, remove, modify, or update_priority"
            ) from exc
        try:
            feedback_type = FeedbackType(
                _required_text(payload, "feedback_type")
            )
        except ValueError as exc:
            raise HumanFeedbackValidationError(
                "feedback_type must be test_suggestion or business_rule"
            ) from exc
        if (
            feedback_type == FeedbackType.BUSINESS_RULE
            and action == FeedbackAction.UPDATE_PRIORITY
        ):
            raise HumanFeedbackValidationError(
                "business rule feedback cannot update test point priority"
            )

        status = (
            FeedbackStatus.PENDING_CONFIRMATION
            if feedback_type == FeedbackType.BUSINESS_RULE
            else FeedbackStatus.READY
        )
        return cls(
            action=action,
            feedback_type=feedback_type,
            target=_required_text(payload, "target"),
            content=_required_text(payload, "content"),
            reason=_required_text(payload, "reason"),
            status=status,
            feedback_id=str(uuid4()),
        )

    def confirm(self) -> "HumanFeedback":
        if self.feedback_type != FeedbackType.BUSINESS_RULE:
            raise HumanFeedbackValidationError(
                "only business rule feedback requires confirmation"
            )
        if self.status != FeedbackStatus.PENDING_CONFIRMATION:
            raise HumanFeedbackValidationError(
                "feedback is not pending confirmation"
            )
        return replace(self, status=FeedbackStatus.READY)

    def mark_applied(self) -> "HumanFeedback":
        if self.status != FeedbackStatus.READY:
            raise HumanFeedbackValidationError(
                "only ready feedback can be marked applied"
            )
        return replace(self, status=FeedbackStatus.APPLIED)

    def to_dict(self) -> dict[str, str]:
        return {
            "feedback_id": self.feedback_id,
            "action": self.action.value,
            "feedback_type": self.feedback_type.value,
            "target": self.target,
            "content": self.content,
            "reason": self.reason,
            "status": self.status.value,
        }

    @classmethod
    def from_state_dict(cls, payload: dict[str, Any]) -> "HumanFeedback":
        try:
            return cls(
                feedback_id=_required_text(payload, "feedback_id"),
                action=FeedbackAction(
                    _required_text(payload, "action")
                ),
                feedback_type=FeedbackType(
                    _required_text(payload, "feedback_type")
                ),
                target=_required_text(payload, "target"),
                content=_required_text(payload, "content"),
                reason=_required_text(payload, "reason"),
                status=FeedbackStatus(
                    _required_text(payload, "status")
                ),
            )
        except ValueError as exc:
            raise HumanFeedbackValidationError(
                f"stored feedback is invalid: {exc}"
            ) from exc


class HumanFeedbackHandler:
    """Validates, stores, and confirms feedback before revision."""

    def submit(
        self,
        state: TestAnalysisState,
        payload: dict[str, Any],
    ) -> HumanFeedback:
        if not state.test_points:
            raise HumanFeedbackValidationError(
                "test points must exist before feedback"
            )
        feedback = HumanFeedback.from_dict(payload)
        state.start_step(
            AgentStep.COLLECT_HUMAN_FEEDBACK,
            "正在记录人工测试反馈",
        )
        state.human_feedback.append(feedback.to_dict())
        state.complete_step(
            AgentStep.COLLECT_HUMAN_FEEDBACK,
            "人工测试反馈已记录",
            {
                "feedback_id": feedback.feedback_id,
                "action": feedback.action.value,
                "feedback_type": feedback.feedback_type.value,
                "status": feedback.status.value,
            },
        )
        if feedback.status == FeedbackStatus.PENDING_CONFIRMATION:
            state.wait_for_user(
                [
                    "请确认以下内容是否作为正式业务规则："
                    + feedback.content
                ]
            )
        return feedback

    def confirm_business_rule(
        self,
        state: TestAnalysisState,
        feedback_id: str,
    ) -> HumanFeedback:
        index, feedback = self._find_feedback(state, feedback_id)
        confirmed = feedback.confirm()
        self._apply_business_rule(state, confirmed)
        state.human_feedback[index] = confirmed.to_dict()
        if state.status == AgentStatus.WAITING_FOR_USER:
            state.resume()
            state.open_questions = []
        state.add_information(
            "人工补充的业务规则已确认",
            {
                "feedback_id": confirmed.feedback_id,
                "business_rule": confirmed.content,
            },
        )
        return confirmed

    @staticmethod
    def _apply_business_rule(
        state: TestAnalysisState,
        feedback: HumanFeedback,
    ) -> None:
        if feedback.action == FeedbackAction.ADD:
            if feedback.content not in state.business_rules:
                state.business_rules.append(feedback.content)
            return
        if feedback.target not in state.business_rules:
            raise HumanFeedbackValidationError(
                "target business rule does not exist"
            )
        index = state.business_rules.index(feedback.target)
        if feedback.action == FeedbackAction.MODIFY:
            state.business_rules[index] = feedback.content
        elif feedback.action == FeedbackAction.REMOVE:
            state.business_rules.pop(index)

    @staticmethod
    def ready_feedback(state: TestAnalysisState) -> list[HumanFeedback]:
        return [
            feedback
            for payload in state.human_feedback
            if (
                feedback := HumanFeedback.from_state_dict(payload)
            ).status
            == FeedbackStatus.READY
        ]

    @staticmethod
    def mark_ready_as_applied(state: TestAnalysisState) -> int:
        applied_count = 0
        updated = []
        for payload in state.human_feedback:
            feedback = HumanFeedback.from_state_dict(payload)
            if feedback.status == FeedbackStatus.READY:
                feedback = feedback.mark_applied()
                applied_count += 1
            updated.append(feedback.to_dict())
        state.human_feedback = updated
        return applied_count

    @staticmethod
    def _find_feedback(
        state: TestAnalysisState,
        feedback_id: str,
    ) -> tuple[int, HumanFeedback]:
        for index, payload in enumerate(state.human_feedback):
            feedback = HumanFeedback.from_state_dict(payload)
            if feedback.feedback_id == feedback_id:
                return index, feedback
        raise HumanFeedbackValidationError(
            f"feedback not found: {feedback_id}"
        )
