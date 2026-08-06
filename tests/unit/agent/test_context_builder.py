from copy import deepcopy

import pytest

from agent import (
    ContextBuildError,
    ContextBuilder,
    ContextNode,
    TestAnalysisState,
)


def populated_state() -> TestAnalysisState:
    state = TestAnalysisState(requirement="用户提交订单后扣减库存。")
    state.requirement_summary = "订单提交与库存扣减"
    state.modules = ["订单", "库存"]
    state.requirement_facts = ["库存充足时创建订单"]
    state.business_rules = ["库存不足时不得创建订单"]
    state.state_transitions = ["待提交 -> 已创建"]
    state.inferred_risks = [
        {"risk": "重复扣减", "basis": "提交接口可能重试"}
    ]
    state.user_clarifications = [
        {"question": "是否允许重试？", "answer": "允许一次"}
    ]
    state.deferred_questions = ["超时时间是多少？"]
    state.local_bug_knowledge = "历史缺陷：重复请求导致重复扣减。"
    state.rag_context = "asset_id=A-1 source=history similarity=0.91"
    state.test_points = [
        {
            "id": "TP-001",
            "title": "库存充足创建订单",
            "steps": ["提交订单", "检查库存"],
        }
    ]
    state.review_result = {"overall_score": 70}
    state.human_feedback = [{"feedback_id": "F-1", "content": "补充幂等"}]
    state.report = "不应进入节点上下文的最终报告"
    return state


def test_node_context_uses_explicit_field_whitelists():
    state = populated_state()
    builder = ContextBuilder()

    analysis = builder.build_requirement_analysis(state).values
    retrieval = builder.build_knowledge_retrieval(state).values
    generation = builder.build_test_point_generation(state).values

    assert set(analysis) == {
        "requirement",
        "user_clarifications",
        "deferred_questions",
    }
    assert "test_points" not in retrieval
    assert "review_result" not in retrieval
    assert set(generation) == {
        "requirement_analysis",
        "local_bug_knowledge",
        "rag_context",
    }
    assert "report" not in repr((analysis, retrieval, generation))


def test_long_requirement_is_clipped_and_keeps_important_rule(monkeypatch):
    state = populated_state()
    state.requirement = (
        "普通描述。" * 400
        + "金额上限必须为5000元，失败后最多重试2次。"
        + "后续说明。" * 400
    )
    monkeypatch.setitem(ContextBuilder.SECTION_CHAR_LIMITS, "requirement", 900)

    context = ContextBuilder().build_requirement_analysis(state)

    assert "5000" in context.values["requirement"]
    assert "最多重试2次" in context.values["requirement"]
    assert "[上下文已按节点预算裁剪]" in context.values["requirement"]
    assert context.metrics.truncated_sections == ("requirement",)
    assert context.metrics.final_chars < context.metrics.original_chars


def test_generation_context_caps_rag_and_local_knowledge(monkeypatch):
    state = populated_state()
    state.local_bug_knowledge = "缺陷信息" * 500
    state.rag_context = "asset_id=A-9 source=mysql 退款规则必须保留\n" + (
        "召回正文" * 500
    )
    monkeypatch.setitem(
        ContextBuilder.SECTION_CHAR_LIMITS, "local_bug_knowledge", 300
    )
    monkeypatch.setitem(ContextBuilder.SECTION_CHAR_LIMITS, "rag_context", 500)

    context = ContextBuilder().build_test_point_generation(state)

    assert len(context.values["local_bug_knowledge"]) <= 300
    assert len(context.values["rag_context"]) <= 500
    assert "asset_id=A-9" in context.values["rag_context"]
    assert "source=mysql" in context.values["rag_context"]
    assert set(context.metrics.truncated_sections) == {
        "local_bug_knowledge",
        "rag_context",
    }


def test_context_metrics_are_explicit_estimates_not_provider_usage():
    context = ContextBuilder().build_knowledge_retrieval(populated_state())

    assert context.metrics.node is ContextNode.KNOWLEDGE_RETRIEVAL
    assert context.metrics.estimated_input_tokens > 0
    assert context.metrics.input_token_budget == 4_000
    assert "actual" not in context.metrics.to_dict()


def test_protected_review_context_over_budget_fails_explicitly(monkeypatch):
    state = populated_state()
    state.test_points = [
        {"id": f"TP-{index}", "title": "测试点" * 50}
        for index in range(20)
    ]
    monkeypatch.setitem(
        ContextBuilder.INPUT_TOKEN_BUDGETS,
        ContextNode.TEST_POINT_REVIEW,
        10,
    )

    with pytest.raises(ContextBuildError, match="protected context exceeds"):
        ContextBuilder().build_test_point_review(state)


def test_built_context_does_not_share_nested_mutable_state():
    state = populated_state()
    original_points = deepcopy(state.test_points)

    context = ContextBuilder().build_test_point_revision(
        state,
        review_result=state.review_result,
        human_feedback=state.human_feedback,
    )
    context.values["test_points"][0]["steps"].append("新增步骤")
    context.values["human_feedback"][0]["content"] = "已修改"

    assert state.test_points == original_points
    assert state.human_feedback[0]["content"] == "补充幂等"
