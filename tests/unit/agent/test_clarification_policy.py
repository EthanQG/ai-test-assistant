import json

import pytest

from agent import (
    AgentStatus,
    ClarificationCandidate,
    ClarificationCategory,
    ClarificationQuestionPolicy,
    RequirementAnalysisResult,
    RequirementAnalysisValidationError,
    RequirementAnalyzer,
    TestAnalysisState,
)


def _candidate(
    question: str,
    category: ClarificationCategory,
    *,
    evidence: str = "原始需求缺少对应规则",
) -> ClarificationCandidate:
    return ClarificationCandidate(
        question=question,
        category=category,
        blocking_reason="不确认就无法判断核心结果",
        evidence=evidence,
    )


def _payload(candidates):
    return {
        "summary": "用户提交订单",
        "modules": ["订单"],
        "requirement_facts": ["用户可以提交订单"],
        "business_rules": [],
        "state_transitions": [],
        "inferred_risks": [],
        "open_questions": [item.to_dict() for item in candidates],
    }


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt, system_prompt=""):
        return json.dumps(self.payload, ensure_ascii=False)


def test_policy_keeps_only_first_three_blocking_questions():
    candidates = [
        _candidate("失败后是否回滚？", ClarificationCategory.CORE_RULE),
        _candidate("单笔金额上限是多少？", ClarificationCategory.CRITICAL_VALUE),
        _candidate("审核拒绝后进入什么状态？", ClarificationCategory.FLOW_BRANCH),
        _candidate("正文和表格哪个限额有效？", ClarificationCategory.REQUIREMENT_CONFLICT),
    ]

    selection = ClarificationQuestionPolicy().select(candidates)

    assert [item.question for item in selection.blocking] == [
        "失败后是否回滚？",
        "单笔金额上限是多少？",
        "审核拒绝后进入什么状态？",
    ]
    assert len(selection.non_blocking_risks) == 1
    assert "正文和表格" in selection.non_blocking_risks[0].risk


def test_policy_converts_implementation_and_low_impact_items_to_risks():
    candidates = [
        _candidate("数据库使用什么锁？", ClarificationCategory.IMPLEMENTATION_DETAIL),
        _candidate("按钮使用什么颜色？", ClarificationCategory.LOW_IMPACT),
    ]

    selection = ClarificationQuestionPolicy().select(candidates)

    assert selection.blocking == ()
    assert len(selection.non_blocking_risks) == 2


def test_local_safeguard_overrides_misclassified_technical_question():
    candidates = [
        _candidate(
            "数据库表结构应该如何设计？",
            ClarificationCategory.CORE_RULE,
        ),
        _candidate(
            "失败后资金是否退回？",
            ClarificationCategory.CORE_RULE,
        ),
    ]

    selection = ClarificationQuestionPolicy().select(candidates)

    assert [item.question for item in selection.blocking] == [
        "失败后资金是否退回？"
    ]
    assert len(selection.non_blocking_risks) == 1


def test_policy_deduplicates_and_does_not_repeat_deferred_question():
    candidates = [
        _candidate("优惠券是否允许叠加？", ClarificationCategory.CORE_RULE),
        _candidate(" 优惠券是否允许叠加 ", ClarificationCategory.CORE_RULE),
        _candidate("退款后优惠券是否返还？", ClarificationCategory.CORE_RULE),
    ]

    selection = ClarificationQuestionPolicy().select(
        candidates,
        deferred_questions=["退款后优惠券是否返还"],
    )

    assert [item.question for item in selection.blocking] == [
        "优惠券是否允许叠加？"
    ]


def test_analyzer_only_waits_for_policy_selected_questions():
    candidates = [
        _candidate("库存不足是否允许下单？", ClarificationCategory.CORE_RULE),
        _candidate("缓存使用什么结构？", ClarificationCategory.IMPLEMENTATION_DETAIL),
    ]
    analyzer = RequirementAnalyzer(llm_service=_FakeLLM(_payload(candidates)))
    state = TestAnalysisState(requirement="用户提交订单")

    result = analyzer.analyze(state)

    assert state.status is AgentStatus.WAITING_FOR_USER
    assert state.open_questions == ["库存不足是否允许下单？"]
    assert result.open_questions == state.open_questions
    assert any("缓存使用什么结构" in item["risk"] for item in state.inferred_risks)


def test_only_non_blocking_candidates_do_not_pause_task():
    candidates = [
        _candidate("日志保留多少天？", ClarificationCategory.IMPLEMENTATION_DETAIL),
        _candidate("提示文案使用什么标点？", ClarificationCategory.LOW_IMPACT),
    ]
    analyzer = RequirementAnalyzer(llm_service=_FakeLLM(_payload(candidates)))
    state = TestAnalysisState(requirement="用户提交订单")

    analyzer.analyze(state)

    assert state.status is AgentStatus.RUNNING
    assert state.open_questions == []
    assert len(state.inferred_risks) == 2


def test_requirement_result_rejects_legacy_string_or_unknown_category():
    payload = _payload([])
    payload["open_questions"] = ["是否允许叠加？"]
    with pytest.raises(RequirementAnalysisValidationError, match="object"):
        RequirementAnalysisResult.from_dict(payload)

    payload["open_questions"] = [
        {
            "question": "是否允许叠加？",
            "category": "unknown",
            "blocking_reason": "影响结果",
            "evidence": "需求未说明",
        }
    ]
    with pytest.raises(RequirementAnalysisValidationError, match="unsupported"):
        RequirementAnalysisResult.from_dict(payload)
