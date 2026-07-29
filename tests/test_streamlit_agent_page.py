import unittest
from copy import deepcopy

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
    PAGINATION_TASK_ID_KEY,
    RESULT_ACTIVE_TAB_KEY,
    TEST_POINT_DETAIL_ID_KEY,
    TEST_POINT_EXPANDED_KEY,
    TEST_POINT_PAGE_KEY,
    _task_store,
)


def _build_test_points(count: int) -> list[dict]:
    return [
        {
            "title": f"测试点{i}",
            "category": "functional",
            "priority": "P0",
            "scenario": f"场景{i}",
            "preconditions": [f"前置条件{i}"],
            "steps": [f"执行步骤{i}"],
            "expected_results": [f"预期结果{i}"],
            "sources": ["requirement"],
        }
        for i in range(1, count + 1)
    ]


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
        result_navigation = next(
            radio for radio in app.radio
            if radio.label == "结果导航"
        )
        result_navigation.set_value("人工反馈")
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
        self.assertEqual(
            app.status[0].label,
            "任务正在等待用户操作",
        )
        self.assertTrue(
            any(
                "等待补充信息 · 当前阶段：需求分析"
                in markdown.value
                for markdown in app.markdown
            )
        )

    def test_fixed_clarification_action_keeps_required_validation(self):
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)
        next(
            button for button in app.button
            if button.label == "提交补充并继续执行"
        ).click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertTrue(
            any(
                "请回答所有问题" in error.value
                for error in app.error
            )
        )
        self.assertIsNone(
            app.session_state["agent_pending_clarifications"]
        )
        self.assertEqual(state.status, AgentStatus.WAITING_FOR_USER)

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
            self.assertEqual(
                app.status[0].label,
                "任务正在等待用户操作",
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
        next(
            radio for radio in app.radio
            if radio.label == "结果导航"
        ).set_value("人工反馈")
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
            next(
                radio for radio in app.radio
                if radio.label == "结果导航"
            ).options,
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
        self.assertIn("查看详情", [button.label for button in app.button])
        self.assertTrue(
            any(
                "场景摘要：满足使用条件时抵扣订单金额"
                in markdown.value
                for markdown in app.markdown
            )
        )
        self.assertEqual(len(app.dataframe), 0)

    def test_test_points_are_paginated_and_open_details_in_dialog(self):
        state = TestAnalysisState("分页需求")
        state.test_points = _build_test_points(12)
        state.status = AgentStatus.COMPLETED
        original_points = deepcopy(state.test_points)
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertTrue(
            any("第 1/3 页" in item.value for item in app.caption)
        )
        self.assertEqual(
            [button.label for button in app.button].count("查看详情"),
            5,
        )
        self.assertTrue(
            any("测试点5" in item.value for item in app.markdown)
        )
        self.assertFalse(
            any(">6. 测试点6</div>" in item.value for item in app.markdown)
        )

        next(
            button for button in app.button
            if button.label == "查看详情"
        ).click()
        app.run(timeout=10)
        first_identity = app.session_state[TEST_POINT_DETAIL_ID_KEY]
        self.assertTrue(first_identity)
        self.assertTrue(
            any("前置条件1" in item.value for item in app.markdown)
        )

        [
            button for button in app.button
            if button.label == "查看详情"
        ][1].click()
        app.run(timeout=10)
        self.assertNotEqual(
            app.session_state[TEST_POINT_DETAIL_ID_KEY],
            first_identity,
        )
        self.assertFalse(
            any("前置条件1" in item.value for item in app.markdown)
        )
        self.assertTrue(
            any("前置条件2" in item.value for item in app.markdown)
        )

        next(
            button for button in app.button
            if button.label == "下一页"
        ).click()
        app.run(timeout=10)
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 2)
        self.assertIsNone(
            app.session_state[TEST_POINT_EXPANDED_KEY]
        )
        self.assertIsNone(
            app.session_state[TEST_POINT_DETAIL_ID_KEY]
        )
        self.assertTrue(
            any(">6. 测试点6</div>" in item.value for item in app.markdown)
        )
        self.assertFalse(
            any(">1. 测试点1</div>" in item.value for item in app.markdown)
        )
        self.assertEqual(state.test_points, original_points)

    def test_page_state_resets_for_changed_points_and_switched_task(self):
        state = TestAnalysisState("第一项需求")
        state.test_points = _build_test_points(12)
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)
        app.session_state[TEST_POINT_PAGE_KEY] = 3
        app.session_state[TEST_POINT_EXPANDED_KEY] = "测试点11"
        app.run(timeout=10)
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 3)

        state.test_points[0]["scenario"] = "更新后的场景"
        app.run(timeout=10)
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 1)
        self.assertIsNone(
            app.session_state[TEST_POINT_EXPANDED_KEY]
        )

        next_state = TestAnalysisState("第二项需求")
        next_state.test_points = _build_test_points(2)
        next_state.status = AgentStatus.COMPLETED
        app.session_state["agent_task_state"] = next_state
        app.run(timeout=10)

        self.assertEqual(
            app.session_state[PAGINATION_TASK_ID_KEY],
            next_state.task_id,
        )
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 1)
        self.assertIsNone(
            app.session_state[TEST_POINT_EXPANDED_KEY]
        )
        self.assertEqual(
            app.session_state[RESULT_ACTIVE_TAB_KEY],
            "结构化测试点",
        )

    def test_new_analysis_clears_page_only_navigation_state(self):
        state = TestAnalysisState("需要重新开始的需求")
        state.test_points = _build_test_points(12)
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)
        app.session_state[RESULT_ACTIVE_TAB_KEY] = "最终报告"
        app.session_state[TEST_POINT_PAGE_KEY] = 3
        app.session_state[TEST_POINT_EXPANDED_KEY] = "测试点11"
        next(
            button for button in app.button
            if button.label == "新建分析"
        ).click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertIsNone(app.session_state["agent_task_state"])
        self.assertEqual(
            app.session_state[RESULT_ACTIVE_TAB_KEY],
            "结构化测试点",
        )
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 1)
        self.assertIsNone(
            app.session_state[TEST_POINT_EXPANDED_KEY]
        )
        self.assertIsNone(
            app.session_state[PAGINATION_TASK_ID_KEY]
        )

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
            ["新建分析", "查看执行详情"],
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
        self.assertIn(
            "查看执行详情",
            [button.label for button in app.button],
        )
        self.assertFalse(
            any(
                "Agent 事件" in markdown.value
                for markdown in app.markdown
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
        next(
            button for button in app.button
            if button.label == "查看执行详情"
        ).click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.table), 0)
        self.assertTrue(
            any(
                "agent-static-table" in markdown.value
                for markdown in app.markdown
            )
        )

    def test_dialog_keeps_active_tab_page_and_expanded_point(self):
        state = TestAnalysisState("执行详情需求")
        state.test_points = _build_test_points(12)
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = [
            OrchestratorDecision(
                action=OrchestratorAction.ANALYZE_REQUIREMENT,
                reason="需求分析完成",
            )
        ]

        app.run(timeout=10)
        app.session_state[TEST_POINT_PAGE_KEY] = 2
        app.session_state[TEST_POINT_EXPANDED_KEY] = "测试点6"
        app.run(timeout=10)
        next(
            button for button in app.button
            if button.label == "查看执行详情"
        ).click()
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.session_state[RESULT_ACTIVE_TAB_KEY],
            "结构化测试点",
        )
        self.assertEqual(app.session_state[TEST_POINT_PAGE_KEY], 2)
        self.assertEqual(
            app.session_state[TEST_POINT_EXPANDED_KEY],
            "测试点6",
        )
        self.assertTrue(
            any(
                "Orchestrator 决策" in markdown.value
                for markdown in app.markdown
            )
        )

    def test_result_navigation_survives_normal_rerun(self):
        state = TestAnalysisState("结果导航需求")
        state.test_points = _build_test_points(1)
        state.review_result = {"overall_score": 90}
        state.status = AgentStatus.COMPLETED
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = state
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)
        next(
            radio for radio in app.radio
            if radio.label == "结果导航"
        ).set_value("质量评审")
        app.run(timeout=10)
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.session_state[RESULT_ACTIVE_TAB_KEY],
            "质量评审",
        )
        self.assertIn("总分", [metric.label for metric in app.metric])

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
        next(
            radio for radio in app.radio
            if radio.label == "结果导航"
        ).set_value("最终报告")
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
        original_events = list(state.events)
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
            self.assertEqual(len(app.status), 1)
            self.assertEqual(app.status[0].label, "正在分析需求")
            self.assertEqual(app.status[0].state, "running")
            self.assertEqual(
                state.events,
                original_events,
            )
            new_analysis = next(
                button for button in app.button
                if button.label == "新建分析"
            )
            self.assertTrue(new_analysis.disabled)
        finally:
            _task_store().pop(state.task_id, None)

    def test_waiting_and_completed_states_stop_running_status(self):
        waiting = TestAnalysisState("等待补充的需求")
        waiting.wait_for_user(["库存不足时是否允许预占？"])
        app = AppTest.from_file("main.py")
        app.session_state["agent_task_state"] = waiting
        app.session_state["agent_decisions"] = []

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(
            app.status[0].label,
            "任务正在等待用户操作",
        )
        self.assertEqual(app.status[0].state, "complete")

        completed = TestAnalysisState("已经完成的需求")
        completed.test_points = [{"title": "库存校验"}]
        completed.review_result = {"overall_score": 90}
        completed.status = AgentStatus.COMPLETED
        completed.current_step = AgentStep.FINALIZE
        app.session_state["agent_task_state"] = completed
        app.session_state["agent_decisions"] = []
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(app.status[0].label, "测试分析任务已完成")
        self.assertEqual(app.status[0].state, "complete")

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
        self.assertEqual(
            app.status[0].label,
            "任务正在等待用户操作",
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
        result_navigation = next(
            radio for radio in app.radio
            if radio.label == "结果导航"
        )
        result_navigation.set_value("人工反馈")
        app.run(timeout=10)
        feedback_type = next(
            radio for radio in app.radio
            if radio.label == "反馈类型"
        )
        feedback_type.set_value("业务规则")
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
        self.assertEqual(
            app.session_state[RESULT_ACTIVE_TAB_KEY],
            "人工反馈",
        )


if __name__ == "__main__":
    unittest.main()
