import unittest

from agent import (
    AgentStatus,
    AgentStep,
    HumanFeedbackHandler,
    TestAnalysisState,
)
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
    def test_text_input_creates_task_with_requirement(self):
        app = AppTest.from_file(
            "tests/fixtures/task_creation_app.py"
        ).run(timeout=10)

        self.assertFalse(app.exception, app.exception)
        app.button[0].click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.session_state["agent_task_state"].requirement,
            "用户可以提交订单",
        )
        self.assertIn("用户可以提交订单", [item.value for item in app.markdown])

    def test_uploaded_file_creates_task_with_extracted_requirement(self):
        app = AppTest.from_file(
            "tests/fixtures/task_creation_app.py"
        ).run(timeout=10)

        self.assertFalse(app.exception, app.exception)
        app.button[1].click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.session_state["agent_task_state"].requirement,
            "# 订单需求\n\n库存不足时禁止创建订单。",
        )
        self.assertTrue(
            any(
                "库存不足时禁止创建订单" in item.value
                for item in app.markdown
            )
        )

    def test_page_renders_and_enables_agent_for_requirement_input(self):
        app = AppTest.from_file("main.py").run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            [title.value for title in app.get("title")],
            ["🧪 Test Analysis Agent"],
        )
        self.assertTrue(
            any(
                "agent-empty-result" in markdown.value
                for markdown in app.markdown
            )
        )
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
        self.assertTrue(
            any(
                "等待补充信息 · 当前阶段：需求分析"
                in markdown.value
                for markdown in app.markdown
            )
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
        self.assertEqual(
            [tab.label for tab in app.tabs],
            [
                "结构化测试点",
                "质量评审",
                "人工反馈",
                "最终报告",
            ],
        )
        self.assertEqual(
            [title.value for title in app.get("title")],
            ["🧪 Test Analysis Agent"],
        )

    def test_completed_task_uses_expandable_test_point_list(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [
            {
                "title": "正常使用优惠券",
                "category": "functional",
                "priority": "P0",
                "scenario": "满足使用条件时抵扣订单金额",
                "preconditions": ["优惠券有效"],
                "steps": ["选择优惠券", "提交订单"],
                "expected_results": ["订单金额正确抵扣"],
                "sources": ["requirement"],
            }
        ]
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertIn(
            "查看前置条件、步骤、预期结果与来源",
            [expander.label for expander in app.expander],
        )
        self.assertTrue(
            any(
                "场景摘要：满足使用条件时抵扣订单金额"
                in caption.value
                for caption in app.caption
            )
        )
        self.assertEqual(len(app.dataframe), 0)

    def test_started_task_shows_requirement_as_read_only_source(self):
        state = TestAnalysisState(
            "这是从上传的PDF中解析并保存到State的原始需求。"
        )
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            [code.value for code in app.code],
            ["这是从上传的PDF中解析并保存到State的原始需求。"],
        )
        self.assertEqual(len(app.text_area), 0)
        self.assertEqual(
            [button.label for button in app.button],
            ["清空任务"],
        )

    def test_stage_progress_and_debug_details_are_rendered(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.current_step = AgentStep.REVIEW_TEST_POINTS
        state.status = AgentStatus.RUNNING
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertTrue(
            any(
                "agent-stage-progress" in markdown.value
                for markdown in app.markdown
            )
        )
        self.assertEqual(
            [expander.label for expander in app.expander],
            ["执行详情"],
        )
        self.assertFalse(app.expander[0].proto.expanded)

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

    def test_revision_limit_guides_user_to_feedback_tab(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [{"title": "正常使用优惠券"}]
        state.status = AgentStatus.RUNNING
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = [
            OrchestratorDecision(
                action=OrchestratorAction.REVISION_LIMIT_REACHED,
                reason="达到自动修正次数上限",
            )
        ]

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertTrue(
            any(
                "请进入“人工反馈”Tab" in warning.value
                for warning in app.warning
            )
        )
        self.assertIn(
            "提交人工反馈",
            [button.label for button in app.button],
        )

    def test_failed_state_is_not_presented_as_revision_limit(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.fail("模型服务请求超时")
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertIn(
            "模型服务请求超时",
            [error.value for error in app.error],
        )
        self.assertFalse(
            any(
                "自动修正已达到上限" in warning.value
                for warning in app.warning
            )
        )

    def test_completed_report_keeps_download_action(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.test_points = [{"title": "正常使用优惠券"}]
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        state.report = "# 测试分析报告"
        state.status = AgentStatus.COMPLETED
        state.current_step = AgentStep.FINALIZE
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        download_buttons = app.get("download_button")
        self.assertEqual(len(download_buttons), 1)
        self.assertEqual(
            download_buttons[0].label,
            "下载 Markdown 报告",
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
