import unittest

from agent.events import AgentEventType, AgentStep
from agent.finalizer import FinalizationError, Finalizer
from agent.state import (
    AgentStatus,
    KnowledgeRetrievalStatus,
    TestAnalysisState,
)


def finalizable_state() -> TestAnalysisState:
    state = TestAnalysisState("用户提交订单时扣减库存")
    state.status = AgentStatus.RUNNING
    state.requirement_summary = "订单提交与库存扣减"
    state.modules = ["订单", "库存"]
    state.requirement_facts = ["提交订单时扣减库存"]
    state.business_rules = ["库存不足时不允许提交"]
    state.inferred_risks = [
        {
            "risk": "并发提交可能超卖",
            "basis": "提交订单会修改库存",
        }
    ]
    state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
    state.test_points = [
        {
            "title": "库存充足时提交订单",
            "category": "functional",
            "priority": "P0",
            "scenario": "库存充足时正常提交",
            "preconditions": ["库存为1"],
            "steps": ["提交订单"],
            "expected_results": ["订单提交成功", "库存变为0"],
            "sources": ["requirement", "test_experience"],
            "source_refs": [
                "提交订单时扣减库存",
                "库存变更需验证最终值",
            ],
        },
        {
            "title": "库存不足时提交订单",
            "category": "exception",
            "priority": "P0",
            "scenario": "库存为0时提交",
            "preconditions": ["库存为0"],
            "steps": ["提交订单"],
            "expected_results": ["订单提交失败", "库存保持为0"],
            "sources": ["requirement"],
            "source_refs": ["库存不足时不允许提交"],
        },
    ]
    state.review_result = {
        "overall_score": 92,
        "dimension_scores": {
            "requirement_coverage": 100,
            "boundary_exception": 90,
            "executability": 90,
            "traceability": 88,
        },
        "requirement_coverage": [
            {
                "requirement_fact": "提交订单时扣减库存",
                "status": "covered",
                "covered_by": ["库存充足时提交订单"],
                "gap": "",
            }
        ],
        "missing_scenarios": [],
        "duplicate_groups": [],
        "hallucination_issues": [],
        "revision_suggestions": [],
    }
    state.review_passed = True
    state.review_threshold = 80
    state.review_history = [{"review_round": 1, "passed": True}]
    state.revision_count = 1
    state.automatic_revision_count = 1
    return state


class FinalizerTests(unittest.TestCase):
    def test_finalize_builds_result_report_and_completes_task(self):
        state = finalizable_state()
        original_points = [dict(point) for point in state.test_points]

        result = Finalizer().finalize(state)

        self.assertEqual(state.status, AgentStatus.COMPLETED)
        self.assertEqual(state.current_step, AgentStep.FINALIZE)
        self.assertEqual(result.test_point_count, 2)
        self.assertEqual(result.category_counts["functional"], 1)
        self.assertEqual(result.category_counts["exception"], 1)
        self.assertEqual(result.priority_counts["P0"], 2)
        self.assertEqual(result.source_counts["requirement"], 2)
        self.assertEqual(result.coverage_summary["covered"], 1)
        self.assertEqual(result.quality_summary["overall_score"], 92)
        self.assertEqual(state.final_result, result.to_dict())
        self.assertIn("# 测试分析报告", state.report)
        self.assertIn("自动修正次数：1", state.report)
        self.assertIn("人工反馈修正次数：0", state.report)
        self.assertIn(
            "| 序号 | 标题 | 分类 | 优先级 | 场景 |",
            state.report,
        )
        self.assertIn("| 1 | 库存充足时提交订单 | 功能 | P0 |", state.report)
        self.assertNotIn("### 1. 库存充足时提交订单", state.report)
        self.assertIn("库存充足时提交订单", state.report)
        self.assertEqual(state.test_points, original_points)
        self.assertEqual(
            state.events[-2].event_type,
            AgentEventType.STEP_COMPLETED,
        )
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.TASK_COMPLETED,
        )

    def test_retrieval_degradation_and_review_concerns_become_warnings(self):
        state = finalizable_state()
        state.knowledge_retrieval_status = (
            KnowledgeRetrievalStatus.DEGRADED
        )
        state.rag_error_message = "Milvus连接失败"
        state.review_result["missing_scenarios"] = ["关注批量提交"]
        state.deferred_questions = ["批量提交的最大数量是多少？"]

        result = Finalizer().finalize(state)

        self.assertIn(
            "历史知识检索已降级：Milvus连接失败",
            result.warnings,
        )
        self.assertIn(
            "评审仍建议关注：关注批量提交",
            result.warnings,
        )
        self.assertIn(
            "用户暂未确认：批量提交的最大数量是多少？",
            result.warnings,
        )
        self.assertIn("## 注意事项", state.report)

    def test_unreviewed_task_cannot_be_finalized(self):
        state = finalizable_state()
        state.review_passed = None
        state.review_result = None

        with self.assertRaisesRegex(FinalizationError, "must be reviewed"):
            Finalizer().finalize(state)

        self.assertNotEqual(state.status, AgentStatus.COMPLETED)
        self.assertIsNone(state.final_result)

    def test_failed_review_below_revision_limit_cannot_be_finalized(self):
        state = finalizable_state()
        state.review_passed = False
        state.automatic_revision_count = 1
        state.max_revision_count = 2

        with self.assertRaisesRegex(FinalizationError, "revision limit"):
            Finalizer().finalize(state)

        self.assertNotEqual(state.status, AgentStatus.COMPLETED)

    def test_failed_review_at_revision_limit_builds_risk_report(self):
        state = finalizable_state()
        state.review_passed = False
        state.review_result["overall_score"] = 78
        state.automatic_revision_count = 2
        state.max_revision_count = 2

        result = Finalizer().finalize(state)

        self.assertEqual(state.status, AgentStatus.COMPLETED)
        self.assertFalse(result.quality_summary["review_passed"])
        self.assertIn("未达到推荐质量门槛", state.report)
        self.assertIn("可提交人工反馈后生成新版", state.report)

    def test_invalid_test_point_is_rejected_without_completing_task(self):
        state = finalizable_state()
        state.test_points[0] = {"title": "不完整测试点"}

        with self.assertRaisesRegex(
            FinalizationError,
            "input is invalid",
        ):
            Finalizer().finalize(state)

        self.assertNotEqual(state.status, AgentStatus.COMPLETED)
        self.assertFalse(state.report)


if __name__ == "__main__":
    unittest.main()
