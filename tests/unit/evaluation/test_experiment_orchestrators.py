from agent import AgentStep, KnowledgeRetrievalStatus, TestAnalysisState
from evaluation.experiment_execution import EXECUTION_POLICIES
from evaluation.experiment_orchestrators import (
    NoKnowledgeRetriever,
    QualityLoopBypassReviewer,
    build_experiment_orchestrator,
)


def _ready_state():
    state = TestAnalysisState("库存不足时拒绝创建订单")
    state.requirement_summary = "库存校验"
    state.requirement_facts = ["库存不足时拒绝创建订单"]
    state.test_points = [{
        "title": "库存不足",
        "category": "functional",
        "priority": "P0",
        "scenario": "库存小于购买数量",
        "preconditions": ["库存为0"],
        "steps": ["提交订单"],
        "expected_results": ["拒绝创建订单"],
        "sources": ["requirement"],
        "source_refs": ["库存不足时拒绝创建订单"],
    }]
    return state


def test_no_knowledge_retriever_clears_context_and_marks_bypass():
    state = _ready_state()
    state.local_bug_knowledge = "旧经验"
    state.rag_context = "旧RAG"

    NoKnowledgeRetriever().retrieve(state)

    assert state.knowledge_retrieval_status is KnowledgeRetrievalStatus.NO_MATCH
    assert state.local_bug_knowledge == ""
    assert state.rag_context == ""
    assert state.events[-1].data == {
        "evaluation_bypass": True, "capability": "rag"
    }


def test_quality_bypass_produces_valid_review_and_explicit_event():
    state = _ready_state()

    result = QualityLoopBypassReviewer().review(state)

    assert result.overall_score == 100
    assert state.review_passed is True
    assert state.review_result["requirement_coverage"][0]["status"] == "covered"
    assert state.events[-1].step is AgentStep.REVIEW_TEST_POINTS
    assert state.events[-1].data["evaluation_bypass"] is True


def test_builder_only_enables_dependencies_selected_by_policy():
    fake_retriever = object()
    fake_reviewer = object()
    fake_reviser = object()

    baseline = build_experiment_orchestrator(
        EXECUTION_POLICIES["baseline_llm"],
        knowledge_retriever=fake_retriever,
        test_point_reviewer=fake_reviewer,
        test_point_reviser=fake_reviser,
    )
    rag = build_experiment_orchestrator(
        EXECUTION_POLICIES["llm_with_rag"],
        knowledge_retriever=fake_retriever,
        test_point_reviewer=fake_reviewer,
        test_point_reviser=fake_reviser,
    )
    full = build_experiment_orchestrator(
        EXECUTION_POLICIES["llm_with_rag_reviewer_reviser"],
        knowledge_retriever=fake_retriever,
        test_point_reviewer=fake_reviewer,
        test_point_reviser=fake_reviser,
    )

    assert isinstance(baseline.knowledge_retriever, NoKnowledgeRetriever)
    assert isinstance(baseline.test_point_reviewer, QualityLoopBypassReviewer)
    assert rag.knowledge_retriever is fake_retriever
    assert isinstance(rag.test_point_reviewer, QualityLoopBypassReviewer)
    assert full.knowledge_retriever is fake_retriever
    assert full.test_point_reviewer is fake_reviewer
    assert full.test_point_reviser is fake_reviser
