import unittest

from agent import (
    AgentEventType,
    AgentStatus,
    AgentStep,
    KnowledgeRetrievalError,
    KnowledgeRetrievalStatus,
    KnowledgeRetriever,
    TestAnalysisState,
)
from services.rag_service import (
    RAGSearchResult,
    RAGSearchStatus,
)


class FakeRAGService:
    def __init__(self, result: RAGSearchResult):
        self.result = result
        self.last_query = ""
        self.last_top_k = 0
        self.last_threshold = 0.0
        self.call_count = 0

    def search(
        self,
        requirement: str,
        top_k: int = 2,
        similarity_threshold: float = 0.60,
    ) -> RAGSearchResult:
        self.call_count += 1
        self.last_query = requirement
        self.last_top_k = top_k
        self.last_threshold = similarity_threshold
        return self.result


def analyzed_state() -> TestAnalysisState:
    state = TestAnalysisState(requirement="用户提交订单后扣减库存")
    state.requirement_summary = "订单提交与库存扣减"
    state.modules = ["订单", "库存"]
    state.requirement_facts = [
        "用户可以提交订单",
        "订单提交后扣减库存",
    ]
    state.business_rules = ["库存不足时不能提交订单"]
    state.inferred_risks = [
        {
            "risk": "重复提交可能重复扣减库存",
            "basis": "存在提交和库存扣减操作",
        }
    ]
    return state


class KnowledgeRetrieverTests(unittest.TestCase):
    def test_matched_result_updates_state_and_event(self):
        rag = FakeRAGService(
            RAGSearchResult(
                context="历史重复扣减测试点",
                max_score=0.91,
                matched_count=2,
                status=RAGSearchStatus.MATCHED,
            )
        )
        retriever = KnowledgeRetriever(rag_service=rag)
        state = analyzed_state()

        result = retriever.retrieve(
            state,
            top_k=3,
            similarity_threshold=0.70,
        )

        self.assertEqual(result.status, RAGSearchStatus.MATCHED)
        self.assertEqual(state.rag_context, "历史重复扣减测试点")
        self.assertEqual(state.rag_max_score, 0.91)
        self.assertEqual(state.rag_matched_count, 2)
        self.assertEqual(
            state.knowledge_retrieval_status,
            KnowledgeRetrievalStatus.MATCHED,
        )
        self.assertIsNone(state.rag_error_message)
        self.assertEqual(state.current_step, AgentStep.RETRIEVE_KNOWLEDGE)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(rag.last_top_k, 3)
        self.assertEqual(rag.last_threshold, 0.70)
        self.assertIn("订单提交与库存扣减", rag.last_query)
        self.assertIn("库存不足时不能提交订单", rag.last_query)
        self.assertIn("重复提交可能重复扣减库存", rag.last_query)
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.STEP_COMPLETED,
        )
        self.assertEqual(
            state.events[-1].data["status"],
            "matched",
        )

    def test_no_match_records_no_match_and_can_continue(self):
        retriever = KnowledgeRetriever(
            rag_service=FakeRAGService(
                RAGSearchResult(
                    context="",
                    max_score=0.0,
                    matched_count=0,
                    status=RAGSearchStatus.NO_MATCH,
                )
            )
        )
        state = analyzed_state()

        retriever.retrieve(state)

        self.assertEqual(
            state.knowledge_retrieval_status,
            KnowledgeRetrievalStatus.NO_MATCH,
        )
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(state.rag_context, "")
        self.assertIn("无历史上下文", state.events[-1].message)

    def test_service_failure_is_recorded_as_degraded(self):
        retriever = KnowledgeRetriever(
            rag_service=FakeRAGService(
                RAGSearchResult(
                    context="",
                    max_score=0.0,
                    matched_count=0,
                    status=RAGSearchStatus.FAILED,
                    error_message="milvus unavailable",
                )
            )
        )
        state = analyzed_state()

        retriever.retrieve(state)

        self.assertEqual(
            state.knowledge_retrieval_status,
            KnowledgeRetrievalStatus.DEGRADED,
        )
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(
            state.rag_error_message,
            "milvus unavailable",
        )
        self.assertEqual(
            state.events[-1].data["error"],
            "milvus unavailable",
        )
        self.assertIn("检索失败", state.events[-1].message)

    def test_requirement_analysis_is_required(self):
        rag = FakeRAGService(
            RAGSearchResult(
                context="",
                max_score=0.0,
                matched_count=0,
                status=RAGSearchStatus.NO_MATCH,
            )
        )
        retriever = KnowledgeRetriever(rag_service=rag)
        state = TestAnalysisState(requirement="用户提交订单")

        with self.assertRaisesRegex(
            KnowledgeRetrievalError,
            "requirement analysis must be completed",
        ):
            retriever.retrieve(state)

        self.assertEqual(rag.call_count, 0)
        self.assertEqual(
            state.knowledge_retrieval_status,
            KnowledgeRetrievalStatus.NOT_STARTED,
        )

    def test_waiting_task_cannot_retrieve_knowledge(self):
        rag = FakeRAGService(
            RAGSearchResult(
                context="",
                max_score=0.0,
                matched_count=0,
                status=RAGSearchStatus.NO_MATCH,
            )
        )
        retriever = KnowledgeRetriever(rag_service=rag)
        state = analyzed_state()
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "分析需求")
        state.wait_for_user(["库存失败后是否回滚？"])

        with self.assertRaisesRegex(ValueError, "must be resumed first"):
            retriever.retrieve(state)

        self.assertEqual(rag.call_count, 0)


if __name__ == "__main__":
    unittest.main()
