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
    decision_rows,
    event_rows,
    feedback_rows,
    task_overview,
    test_point_rows,
)


class AgentPresenterTests(unittest.TestCase):
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
            )
        ]

        events = event_rows(state)
        decision_data = decision_rows(decisions)

        self.assertEqual(events[0]["事件"], "task_created")
        self.assertEqual(events[0]["步骤"], "initialize")
        self.assertEqual(decision_data[0]["序号"], "1")
        self.assertEqual(decision_data[0]["动作"], "analyze_requirement")

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
