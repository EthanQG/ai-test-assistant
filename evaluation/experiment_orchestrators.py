"""Variant-specific dependency assembly without changing the orchestrator."""

from __future__ import annotations

from agent import (
    AgentOrchestrator,
    AgentStep,
    KnowledgeRetrievalStatus,
    TestAnalysisState,
    TestPointReviewResult,
)

from .experiment_execution import ExperimentExecutionPolicy


class NoKnowledgeRetriever:
    """Record that historical knowledge is intentionally disabled."""

    def retrieve(self, state: TestAnalysisState) -> None:
        state.start_step(AgentStep.RETRIEVE_KNOWLEDGE, "实验组未启用历史资产")
        state.local_bug_knowledge = ""
        state.rag_context = ""
        state.rag_max_score = 0.0
        state.rag_matched_count = 0
        state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
        state.complete_step(
            AgentStep.RETRIEVE_KNOWLEDGE,
            "实验组历史资产旁路完成",
            {"evaluation_bypass": True, "capability": "rag"},
        )


class QualityLoopBypassReviewer:
    """Produce a valid neutral review while marking the evaluation bypass."""

    def review(self, state: TestAnalysisState) -> TestPointReviewResult:
        state.start_step(AgentStep.REVIEW_TEST_POINTS, "实验组未启用质量闭环")
        result = TestPointReviewResult.from_dict({
            "overall_score": 100,
            "dimension_scores": {
                "requirement_coverage": 100,
                "boundary_exception": 100,
                "executability": 100,
                "traceability": 100,
            },
            "requirement_coverage": [
                {
                    "requirement_fact": fact,
                    "status": "covered",
                    "covered_by": ["evaluation_bypass"],
                    "gap": "",
                }
                for fact in state.requirement_facts
            ],
            "missing_scenarios": [],
            "duplicate_groups": [],
            "hallucination_issues": [],
            "revision_suggestions": [],
        })
        state.review_result = result.to_dict()
        state.review_passed = True
        state.complete_step(
            AgentStep.REVIEW_TEST_POINTS,
            "实验组质量闭环旁路完成",
            {"evaluation_bypass": True, "capability": "quality_loop"},
        )
        return result


def build_experiment_orchestrator(
    policy: ExperimentExecutionPolicy,
    *,
    requirement_analyzer=None,
    knowledge_retriever=None,
    test_point_generator=None,
    test_point_reviewer=None,
    test_point_reviser=None,
    finalizer=None,
) -> AgentOrchestrator:
    retriever = (
        knowledge_retriever if policy.use_rag else NoKnowledgeRetriever()
    )
    reviewer = (
        test_point_reviewer
        if policy.use_quality_loop
        else QualityLoopBypassReviewer()
    )
    return AgentOrchestrator(
        requirement_analyzer=requirement_analyzer,
        knowledge_retriever=retriever,
        test_point_generator=test_point_generator,
        test_point_reviewer=reviewer,
        test_point_reviser=test_point_reviser,
        finalizer=finalizer,
    )
