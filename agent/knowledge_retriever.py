from services.rag_service import (
    RAGSearchResult,
    RAGSearchStatus,
    RAGService,
)

from .events import AgentStep
from .state import (
    KnowledgeRetrievalStatus,
    TestAnalysisState,
)


class KnowledgeRetrievalError(RuntimeError):
    """Raised when knowledge retrieval is called with invalid agent state."""


class KnowledgeRetriever:
    """Retrieves historical test assets and records a controlled result."""

    def __init__(self, rag_service: RAGService | None = None):
        self.rag_service = rag_service or RAGService()

    def retrieve(
        self,
        state: TestAnalysisState,
        top_k: int = 2,
        similarity_threshold: float = 0.60,
    ) -> RAGSearchResult:
        if not state.requirement_summary and not state.requirement_facts:
            raise KnowledgeRetrievalError(
                "requirement analysis must be completed before retrieval"
            )

        state.start_step(
            AgentStep.RETRIEVE_KNOWLEDGE,
            "正在检索相似历史测试资产",
        )
        query = self._build_query(state)
        result = self.rag_service.search(
            query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )
        self._apply_result(state, result)

        if result.status == RAGSearchStatus.MATCHED:
            message = "历史测试资产检索完成"
        elif result.status == RAGSearchStatus.NO_MATCH:
            message = "未命中相关历史测试资产，按无历史上下文继续"
        else:
            message = "历史测试资产检索失败，已降级为无历史上下文"

        state.complete_step(
            AgentStep.RETRIEVE_KNOWLEDGE,
            message,
            {
                "status": state.knowledge_retrieval_status.value,
                "matched_count": state.rag_matched_count,
                "max_score": state.rag_max_score,
                "error": state.rag_error_message,
            },
        )
        return result

    @staticmethod
    def _build_query(state: TestAnalysisState) -> str:
        sections = [f"原始需求：{state.requirement}"]

        if state.requirement_summary:
            sections.append(f"需求摘要：{state.requirement_summary}")
        if state.modules:
            sections.append("业务模块：" + "、".join(state.modules))
        if state.requirement_facts:
            sections.append(
                "需求事实：\n- " + "\n- ".join(state.requirement_facts)
            )
        if state.business_rules:
            sections.append(
                "业务规则：\n- " + "\n- ".join(state.business_rules)
            )
        if state.inferred_risks:
            risk_lines = []
            for item in state.inferred_risks:
                risk = item.get("risk", "").strip()
                basis = item.get("basis", "").strip()
                if risk:
                    risk_lines.append(
                        f"{risk}（依据：{basis or '未提供'}）"
                    )
            if risk_lines:
                sections.append("推导风险：\n- " + "\n- ".join(risk_lines))

        return "\n\n".join(sections)

    @staticmethod
    def _apply_result(
        state: TestAnalysisState,
        result: RAGSearchResult,
    ) -> None:
        state.rag_context = result.context
        state.rag_max_score = result.max_score
        state.rag_matched_count = result.matched_count
        state.rag_error_message = result.error_message

        status_mapping = {
            RAGSearchStatus.MATCHED: KnowledgeRetrievalStatus.MATCHED,
            RAGSearchStatus.NO_MATCH: KnowledgeRetrievalStatus.NO_MATCH,
            RAGSearchStatus.FAILED: KnowledgeRetrievalStatus.DEGRADED,
        }
        state.knowledge_retrieval_status = status_mapping[result.status]
