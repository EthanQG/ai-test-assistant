import unittest

from agent.events import AgentStep
from agent.orchestrator import (
    OrchestratorAction,
    OrchestratorDecision,
)
from agent.state import (
    AgentStatus,
    KnowledgeRetrievalStatus,
    TestAnalysisState,
)
from views.agent_presenter import (
    action_progress_message,
    decision_rows,
    execution_status_content,
    event_rows,
    feedback_rows,
    layout_column_weights,
    recent_progress_items,
    stage_progress,
    stage_progress_html,
    static_table_html,
    task_header,
    task_overview,
    test_point_summary_html,
    test_point_rows,
)


class AgentPresenterTests(unittest.TestCase):
    def test_execution_status_uses_deterministic_node_copy(self):
        state = TestAnalysisState("订单需求")
        state.current_step = AgentStep.REVIEW_TEST_POINTS

        review = execution_status_content(state)
        revision = execution_status_content(
            state,
            "revise_test_points",
        )

        self.assertEqual(review["title"], "正在评审测试点质量")
        self.assertIn("覆盖度", review["description"])
        self.assertEqual(revision["title"], "正在进行第1轮测试点修正")
        self.assertIn("1～2分钟", revision["waiting"])

    def test_recent_progress_filters_and_translates_events(self):
        state = TestAnalysisState("订单需求")
        state.start_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "正在分析需求结构与信息边界",
        )
        state.complete_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "需求结构化分析完成",
        )
        state.add_information("已收到补充信息，继续执行任务")

        progress = recent_progress_items(state)

        self.assertEqual(
            progress,
            [
                "已开始需求分析",
                "需求分析已完成",
                "已提交用户补充信息",
            ],
        )

    def test_llm_action_progress_message_sets_waiting_expectation(self):
        message = action_progress_message("revise_test_points")

        self.assertIn("修正测试点", message)
        self.assertIn("1–2 分钟", message)
        self.assertIn("请勿重复点击", message)

    def test_task_overview_prefers_final_quality_summary(self):
        state = TestAnalysisState("订单需求")
        state.status = AgentStatus.COMPLETED
        state.current_step = AgentStep.FINALIZE
        state.test_points = [{"title": "提交订单"}]
        state.review_result = {"overall_score": 88}
        state.final_result = {
            "quality_summary": {"overall_score": 92}
        }
        state.revision_count = 1
        state.automatic_revision_count = 1
        state.knowledge_retrieval_status = (
            KnowledgeRetrievalStatus.MATCHED
        )

        overview = task_overview(state)

        self.assertEqual(overview["status_label"], "已完成")
        self.assertEqual(overview["current_step"], "整理报告")
        self.assertEqual(overview["test_point_count"], 1)
        self.assertEqual(overview["overall_score"], 92)
        self.assertEqual(overview["automatic_revision_count"], 1)
        self.assertEqual(overview["human_revision_count"], 0)
        self.assertEqual(overview["rag_status"], "matched")

    def test_event_and_decision_rows_are_display_ready(self):
        state = TestAnalysisState("订单需求")
        decisions = [
            OrchestratorDecision(
                OrchestratorAction.ANALYZE_REQUIREMENT,
                "尚未分析需求",
                duration_seconds=1.25,
            )
        ]

        events = event_rows(state)
        decision_data = decision_rows(decisions)

        self.assertEqual(events[0]["事件"], "task_created")
        self.assertEqual(events[0]["序号"], "1")
        self.assertEqual(events[0]["步骤"], "initialize")
        self.assertEqual(decision_data[0]["序号"], "1")
        self.assertEqual(decision_data[0]["动作"], "需求分析")
        self.assertEqual(decision_data[0]["耗时"], "1.25 秒")

    def test_static_table_has_no_index_and_escapes_content(self):
        html = static_table_html(
            [{"序号": "1", "说明": "<script>alert(1)</script>"}]
        )

        self.assertIn("<th", html)
        self.assertIn(">序号</th>", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<th></th>", html)

    def test_stage_progress_maps_revision_to_quality_stage(self):
        state = TestAnalysisState("订单需求")
        state.current_step = AgentStep.REVISE_TEST_POINTS
        state.status = AgentStatus.RUNNING

        stages = stage_progress(state)
        html = stage_progress_html(state)

        self.assertEqual(
            [stage["status"] for stage in stages],
            [
                "completed",
                "completed",
                "completed",
                "current",
                "pending",
            ],
        )
        self.assertIn("评审与修正", html)
        self.assertIn("agent-stage-progress", html)

    def test_failed_stage_is_distinct_from_pending(self):
        state = TestAnalysisState("订单需求")
        state.current_step = AgentStep.GENERATE_TEST_POINTS
        state.status = AgentStatus.FAILED

        stages = stage_progress(state)

        self.assertEqual(stages[2]["status"], "failed")
        self.assertEqual(stages[3]["status"], "pending")

    def test_layout_uses_more_result_space_for_completed_task(self):
        state = TestAnalysisState("订单需求")

        self.assertEqual(layout_column_weights(None, []), (0.42, 0.58))
        self.assertEqual(
            layout_column_weights(state, []),
            (0.42, 0.58),
        )

        state.status = AgentStatus.COMPLETED

        self.assertEqual(
            layout_column_weights(state, []),
            (0.33, 0.67),
        )

    def test_layout_uses_more_result_space_at_revision_limit(self):
        state = TestAnalysisState("订单需求")
        decisions = [
            OrchestratorDecision(
                OrchestratorAction.REVISION_LIMIT_REACHED,
                "达到自动修正上限",
            )
        ]

        self.assertEqual(
            layout_column_weights(state, decisions),
            (0.33, 0.67),
        )

    def test_task_header_uses_product_language_for_main_states(self):
        state = TestAnalysisState("订单需求")

        cases = []
        cases.append(("未开始", task_header(state, [])))

        state.status = AgentStatus.RUNNING
        state.current_step = AgentStep.RETRIEVE_KNOWLEDGE
        cases.append(("执行中", task_header(state, [])))

        state.wait_for_user(["库存锁定时机是什么？"])
        cases.append(("等待补充", task_header(state, [])))

        state.status = AgentStatus.RUNNING
        state.current_step = AgentStep.REVISE_TEST_POINTS
        state.human_feedback = [
            {
                "feedback_type": "test_suggestion",
                "status": "ready",
            }
        ]
        cases.append(("人工反馈", task_header(state, [])))

        state.human_feedback = []
        decisions = [
            OrchestratorDecision(
                OrchestratorAction.REVISION_LIMIT_REACHED,
                "达到自动修正上限",
            )
        ]
        cases.append(("修正上限", task_header(state, decisions)))

        state.status = AgentStatus.COMPLETED
        state.current_step = AgentStep.FINALIZE
        cases.append(("已完成", task_header(state, [])))

        state.status = AgentStatus.FAILED
        state.current_step = AgentStep.GENERATE_TEST_POINTS
        cases.append(("执行失败", task_header(state, [])))

        expected = {
            "未开始": ("等待开始", "需求分析"),
            "执行中": ("执行中", "知识检索"),
            "等待补充": ("等待补充信息", "需求分析"),
            "人工反馈": ("人工反馈处理中", "评审与修正"),
            "修正上限": ("已达自动修正上限", "评审与修正"),
            "已完成": ("已完成", "整理报告"),
            "执行失败": ("执行失败", "生成测试点"),
        }
        for name, header in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    (
                        header["status_label"],
                        header["stage_label"],
                    ),
                    expected[name],
                )

    def test_task_header_distinguishes_business_rule_confirmation(self):
        state = TestAnalysisState("订单需求")
        state.status = AgentStatus.WAITING_FOR_USER
        state.human_feedback = [
            {
                "feedback_type": "business_rule",
                "status": "pending_confirmation",
            }
        ]

        header = task_header(state, [])

        self.assertEqual(header["status_label"], "等待规则确认")
        self.assertEqual(header["stage_label"], "评审与修正")

    def test_test_point_rows_flatten_list_fields(self):
        state = TestAnalysisState("订单需求")
        state.test_points = [
            {
                "title": "重复提交",
                "category": "exception",
                "priority": "P0",
                "scenario": "重复点击提交",
                "steps": ["第一次提交", "再次提交"],
                "expected_results": ["只创建一个订单"],
                "sources": ["requirement", "test_experience"],
            }
        ]

        rows = test_point_rows(state)

        self.assertEqual(rows[0]["分类"], "异常")
        self.assertEqual(rows[0]["步骤"], "第一次提交\n再次提交")
        self.assertEqual(
            rows[0]["来源"],
            "requirement, test_experience",
        )

    def test_test_point_summary_html_is_aligned_and_escaped(self):
        html = test_point_summary_html(
            {
                "title": "<script>异常标题</script>",
                "category": "exception",
                "priority": "P0",
                "scenario": "重复提交",
            },
            2,
        )

        self.assertIn("agent-test-point-summary", html)
        self.assertIn("分类：异常", html)
        self.assertIn("优先级：P0", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_feedback_rows_translate_internal_values(self):
        state = TestAnalysisState("订单需求")
        state.human_feedback = [
            {
                "feedback_id": "feedback-1",
                "action": "update_priority",
                "feedback_type": "test_suggestion",
                "target": "重复提交",
                "content": "将测试点优先级调整为 P0",
                "reason": "属于资金风险",
                "status": "applied",
            }
        ]

        rows = feedback_rows(state)

        self.assertEqual(rows[0]["类型"], "测试建议")
        self.assertEqual(rows[0]["动作"], "调整优先级")
        self.assertEqual(rows[0]["状态"], "已应用")


if __name__ == "__main__":
    unittest.main()
