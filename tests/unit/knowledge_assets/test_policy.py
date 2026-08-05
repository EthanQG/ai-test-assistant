from datetime import datetime, timezone

import pytest

from agent import AgentStatus
from knowledge_assets import (
    KnowledgeAssetAdmissionError,
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetStatus,
)

from .support import make_eligible_state


@pytest.fixture
def admission_policy():
    return KnowledgeAssetAdmissionPolicy(
        clock=lambda: datetime(2026, 8, 5, tzinfo=timezone.utc),
        asset_id_factory=lambda: "asset-confirmed",
    )


def _admit(admission_policy, state=None, **overrides):
    arguments = {
        "user_confirmed": True,
        "data_safety_confirmed": True,
        "asset_version": 1,
    }
    arguments.update(overrides)
    return admission_policy.admit(
        state or make_eligible_state(),
        **arguments,
    )


def test_admission_creates_pending_index_asset_with_audit_evidence(
    admission_policy,
):
    state = make_eligible_state()

    asset = _admit(admission_policy, state)

    assert asset.source_task_id == state.task_id
    assert asset.status is KnowledgeAssetStatus.PENDING_INDEX
    assert asset.user_confirmed is True
    assert asset.data_safety_confirmed is True
    assert asset.review_result.overall_score == 92
    assert asset.structured_requirement.requirement_facts == (
        "库存充足时创建订单",
    )
    assert asset.test_points[0].title == "库存充足时创建订单"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"user_confirmed": False}, "explicitly confirm"),
        ({"data_safety_confirmed": False}, "data safety"),
    ],
)
def test_admission_requires_both_explicit_confirmations(
    admission_policy,
    overrides,
    message,
):
    with pytest.raises(KnowledgeAssetAdmissionError, match=message):
        _admit(admission_policy, **overrides)


@pytest.mark.parametrize(
    "status",
    [AgentStatus.PENDING, AgentStatus.RUNNING, AgentStatus.FAILED],
)
def test_admission_rejects_non_completed_task(admission_policy, status):
    state = make_eligible_state()
    state.status = status

    with pytest.raises(KnowledgeAssetAdmissionError, match="completed"):
        _admit(admission_policy, state)


def test_admission_rejects_failed_or_inconsistent_review(admission_policy):
    failed = make_eligible_state()
    failed.review_passed = False
    stale_score = make_eligible_state()
    stale_score.review_result["overall_score"] = 60
    uncovered = make_eligible_state()
    uncovered.review_result["requirement_coverage"][0]["status"] = "partial"
    hallucinated = make_eligible_state()
    hallucinated.review_result["hallucination_issues"] = [
        {
            "test_point_title": "库存充足时创建订单",
            "issue": "包含无依据规则",
            "unsupported_claim": "订单自动拆单",
        }
    ]

    with pytest.raises(KnowledgeAssetAdmissionError, match="pass Reviewer"):
        _admit(admission_policy, failed)
    with pytest.raises(KnowledgeAssetAdmissionError, match="threshold"):
        _admit(admission_policy, stale_score)
    with pytest.raises(KnowledgeAssetAdmissionError, match="coverage"):
        _admit(admission_policy, uncovered)
    with pytest.raises(KnowledgeAssetAdmissionError, match="unsupported"):
        _admit(admission_policy, hallucinated)


def test_admission_rejects_open_questions_and_stale_final_result(
    admission_policy,
):
    waiting = make_eligible_state()
    waiting.open_questions = ["库存不足是否允许预占？"]
    stale = make_eligible_state()
    stale.test_points[0]["title"] = "已被人工改动的测试点"

    with pytest.raises(KnowledgeAssetAdmissionError, match="open questions"):
        _admit(admission_policy, waiting)
    with pytest.raises(KnowledgeAssetAdmissionError, match="stale"):
        _admit(admission_policy, stale)


def test_admission_rejects_pending_human_feedback(admission_policy):
    state = make_eligible_state()
    state.human_feedback = [
        {
            "feedback_id": "feedback-1",
            "action": "add",
            "feedback_type": "test_suggestion",
            "target": "新增测试点",
            "content": "增加并发扣减场景",
            "reason": "历史缺陷",
            "status": "ready",
        }
    ]

    with pytest.raises(KnowledgeAssetAdmissionError, match="feedback"):
        _admit(admission_policy, state)


def test_admission_rejects_naive_clock():
    policy = KnowledgeAssetAdmissionPolicy(
        clock=lambda: datetime(2026, 8, 5),
    )

    with pytest.raises(KnowledgeAssetAdmissionError, match="timezone"):
        _admit(policy)
