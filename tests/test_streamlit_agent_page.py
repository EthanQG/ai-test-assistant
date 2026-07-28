import unittest

from agent import AgentStatus, HumanFeedbackHandler, TestAnalysisState
from agent.orchestrator import (
    OrchestratorAction,
    OrchestratorDecision,
)
from streamlit.testing.v1 import AppTest
from views.tab_test_points import (
    FEEDBACK_FORM_VERSION_KEY,
    _task_store,
)


class StreamlitAgentPageTests(unittest.TestCase):
    def test_page_renders_and_enables_agent_for_requirement_input(self):
        app = AppTest.from_file("main.py").run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_area), 1)
        self.assertEqual(len(app.button), 2)
        self.assertTrue(app.button[0].disabled)

        app.text_area[0].set_value("用户可以提交订单")
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertFalse(app.button[0].disabled)

    def test_waiting_task_renders_clarification_form(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(
            ["优惠券是否允许叠加？", "失效时间如何计算？"]
        )
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            [checkbox.label for checkbox in app.checkbox],
            ["暂不确定", "暂不确定"],
        )
        self.assertIn(
            "提交补充并继续执行",
            [button.label for button in app.button],
        )
        self.assertIn(
            "任务已暂停，请在左侧工作台回答关键问题后继续。",
            [warning.value for warning in app.warning],
        )

    def test_task_can_be_restored_from_query_parameter(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])
        _task_store()[state.task_id] = {
            "state": state,
            "decisions": [],
            "auto_run": False,
            "pending_clarifications": None,
            "execution_steps": 1,
            "in_progress": False,
        }
        app = AppTest.from_file("main.py")
        app.query_params["task_id"] = state.task_id

        try:
            app.run(timeout=10)

            self.assertFalse(app.exception)
            self.assertTrue(
                any(
                    "优惠券是否允许叠加？" in markdown.value
                    for markdown in app.markdown
                )
            )
            self.assertIn(
                "任务已暂停，请在左侧工作台回答关键问题后继续。",
                [warning.value for warning in app.warning],
            )
        finally:
            _task_store().pop(state.task_id, None)

    def test_completed_task_renders_human_feedback_form(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [{"title": "正常使用优惠券"}]
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertIn(
            "提交人工反馈",
            [button.label for button in app.button],
        )
        self.assertIn(
            "反馈类型",
            [radio.label for radio in app.radio],
        )
        self.assertTrue(
            any(
                "测试建议会直接进入修正" in info.value
                for info in app.info
            )
        )

    def test_timeline_uses_static_tables(self):
        state = TestAnalysisState("用户可以使用优惠券")
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = [
            OrchestratorDecision(
                action=OrchestratorAction.ANALYZE_REQUIREMENT,
                reason="尚未完成结构化需求分析",
                duration_seconds=1.5,
            )
        ]

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.table), 0)
        self.assertTrue(
            any(
                "agent-static-table" in markdown.value
                for markdown in app.markdown
            )
        )

    def test_in_progress_task_does_not_start_duplicate_polling(self):
        state = TestAnalysisState("用户可以使用优惠券")
        _task_store()[state.task_id] = {
            "state": state,
            "decisions": [],
            "auto_run": True,
            "pending_clarifications": None,
            "execution_steps": 1,
            "in_progress": True,
        }
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        try:
            app.run(timeout=10)

            self.assertFalse(app.exception)
            self.assertTrue(
                any(
                    "当前 Agent 节点仍在执行" in info.value
                    for info in app.info
                )
            )
        finally:
            _task_store().pop(state.task_id, None)

    def test_pending_business_rule_renders_confirmation_actions(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [{"title": "正常使用优惠券"}]
        HumanFeedbackHandler().submit(
            state,
            {
                "action": "add",
                "feedback_type": "business_rule",
                "target": "新增业务规则",
                "content": "优惠券最多叠加两张",
                "reason": "用户补充规则",
            },
        )
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        labels = [button.label for button in app.button]
        self.assertIn("确认规则并继续", labels)
        self.assertIn("取消该规则", labels)
        self.assertIn(
            "任务已暂停，请在左侧确认或取消新增业务规则。",
            [warning.value for warning in app.warning],
        )

    def test_submitted_feedback_advances_form_version(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [{"title": "正常使用优惠券"}]
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)
        app.radio[0].set_value("业务规则")
        app.run(timeout=10)
        feedback_content = next(
            item
            for item in app.text_area
            if item.label == "反馈内容"
        )
        feedback_reason = next(
            item
            for item in app.text_area
            if item.label == "原因或依据"
        )
        feedback_content.set_value("优惠券最多叠加两张")
        feedback_reason.set_value("用户补充业务规则")
        next(
            button
            for button in app.button
            if button.label == "提交人工反馈"
        ).click()

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.session_state[FEEDBACK_FORM_VERSION_KEY],
            1,
        )
        self.assertEqual(len(state.human_feedback), 1)
        self.assertEqual(
            state.human_feedback[0]["status"],
            "pending_confirmation",
        )
        self.assertTrue(
            any(
                "人工反馈已接收" in success.value
                for success in app.success
            )
        )


if __name__ == "__main__":
    unittest.main()
