import unittest

from agent.events import AgentEventType, AgentStep
from agent.human_feedback import (
    FeedbackAction,
    FeedbackStatus,
    FeedbackType,
    HumanFeedback,
    HumanFeedbackHandler,
    HumanFeedbackValidationError,
)
from agent.state import AgentStatus, TestAnalysisState


def feedback_payload(
    *,
    action: str = "add",
    feedback_type: str = "test_suggestion",
) -> dict:
    return {
        "action": action,
        "feedback_type": feedback_type,
        "target": "支付异常测试",
        "content": "增加弱网下支付结果未知的场景",
        "reason": "历史线上出现过类似问题",
    }


def state_with_test_points() -> TestAnalysisState:
    state = TestAnalysisState("用户可以提交支付订单")
    state.test_points = [{"title": "正常支付"}]
    return state


class HumanFeedbackModelTests(unittest.TestCase):
    def test_test_suggestion_is_ready_immediately(self):
        feedback = HumanFeedback.from_dict(feedback_payload())

        self.assertEqual(feedback.action, FeedbackAction.ADD)
        self.assertEqual(
            feedback.feedback_type,
            FeedbackType.TEST_SUGGESTION,
        )
        self.assertEqual(feedback.status, FeedbackStatus.READY)
        self.assertTrue(feedback.feedback_id)

    def test_business_rule_requires_confirmation(self):
        feedback = HumanFeedback.from_dict(
            feedback_payload(feedback_type="business_rule")
        )

        self.assertEqual(
            feedback.status,
            FeedbackStatus.PENDING_CONFIRMATION,
        )
        self.assertEqual(
            feedback.confirm().status,
            FeedbackStatus.READY,
        )

    def test_invalid_action_is_rejected(self):
        with self.assertRaisesRegex(
            HumanFeedbackValidationError,
            "action must be",
        ):
            HumanFeedback.from_dict(
                feedback_payload(action="approve")
            )

    def test_unknown_field_is_rejected(self):
        payload = feedback_payload()
        payload["priority"] = "P0"
        with self.assertRaisesRegex(
            HumanFeedbackValidationError,
            "feedback fields are invalid",
        ):
            HumanFeedback.from_dict(payload)

    def test_business_rule_cannot_update_test_point_priority(self):
        with self.assertRaisesRegex(
            HumanFeedbackValidationError,
            "cannot update test point priority",
        ):
            HumanFeedback.from_dict(
                feedback_payload(
                    action="update_priority",
                    feedback_type="business_rule",
                )
            )


class HumanFeedbackHandlerTests(unittest.TestCase):
    def test_suggestion_is_stored_and_ready_for_revision(self):
        state = state_with_test_points()

        feedback = HumanFeedbackHandler().submit(
            state,
            feedback_payload(),
        )

        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(
            state.current_step,
            AgentStep.COLLECT_HUMAN_FEEDBACK,
        )
        self.assertEqual(state.human_feedback[0]["status"], "ready")
        self.assertEqual(
            HumanFeedbackHandler.ready_feedback(state)[0].feedback_id,
            feedback.feedback_id,
        )
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.STEP_COMPLETED,
        )

    def test_completed_task_reopens_when_feedback_is_submitted(self):
        state = state_with_test_points()
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        state.final_result = {"test_point_count": 1}
        state.complete("已完成报告")

        feedback = HumanFeedbackHandler().submit(
            state,
            feedback_payload(),
        )

        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(feedback.status, FeedbackStatus.READY)
        self.assertEqual(state.report, "")
        self.assertIsNone(state.final_result)

    def test_business_rule_waits_for_confirmation(self):
        state = state_with_test_points()

        feedback = HumanFeedbackHandler().submit(
            state,
            feedback_payload(feedback_type="business_rule"),
        )

        self.assertEqual(
            state.status,
            AgentStatus.WAITING_FOR_USER,
        )
        self.assertEqual(
            state.human_feedback[0]["status"],
            "pending_confirmation",
        )
        self.assertIn(feedback.content, state.open_questions[0])
        self.assertEqual(
            HumanFeedbackHandler.ready_feedback(state),
            [],
        )
        self.assertEqual(
            state.events[-1].message,
            "需要用户确认人工补充的业务规则",
        )

    def test_confirmed_business_rule_updates_requirement_state(self):
        state = state_with_test_points()
        feedback = HumanFeedbackHandler().submit(
            state,
            feedback_payload(feedback_type="business_rule"),
        )

        confirmed = HumanFeedbackHandler().confirm_business_rule(
            state,
            feedback.feedback_id,
        )

        self.assertEqual(confirmed.status, FeedbackStatus.READY)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(state.open_questions, [])
        self.assertIn(confirmed.content, state.business_rules)
        self.assertEqual(state.human_feedback[0]["status"], "ready")

    def test_business_rule_can_be_rejected_without_updating_requirement(self):
        state = state_with_test_points()
        feedback = HumanFeedbackHandler().submit(
            state,
            feedback_payload(feedback_type="business_rule"),
        )

        rejected = HumanFeedbackHandler().reject_business_rule(
            state,
            feedback.feedback_id,
        )

        self.assertEqual(rejected.status, FeedbackStatus.REJECTED)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(state.open_questions, [])
        self.assertNotIn(rejected.content, state.business_rules)
        self.assertEqual(
            HumanFeedbackHandler.pending_confirmation_feedback(state),
            [],
        )

    def test_feedback_requires_existing_test_points(self):
        state = TestAnalysisState("支付需求")

        with self.assertRaisesRegex(
            HumanFeedbackValidationError,
            "test points must exist",
        ):
            HumanFeedbackHandler().submit(
                state,
                feedback_payload(),
            )

        self.assertEqual(state.events[-1].event_type.value, "task_created")

    def test_unknown_feedback_cannot_be_confirmed(self):
        state = state_with_test_points()

        with self.assertRaisesRegex(
            HumanFeedbackValidationError,
            "feedback not found",
        ):
            HumanFeedbackHandler().confirm_business_rule(
                state,
                "missing-id",
            )

    def test_confirmed_modify_replaces_existing_business_rule(self):
        state = state_with_test_points()
        state.business_rules = ["库存不足时禁止提交"]
        payload = feedback_payload(
            action="modify",
            feedback_type="business_rule",
        )
        payload["target"] = "库存不足时禁止提交"
        payload["content"] = "库存不足时允许创建缺货订单"
        feedback = HumanFeedbackHandler().submit(state, payload)

        HumanFeedbackHandler().confirm_business_rule(
            state,
            feedback.feedback_id,
        )

        self.assertEqual(
            state.business_rules,
            ["库存不足时允许创建缺货订单"],
        )


if __name__ == "__main__":
    unittest.main()
