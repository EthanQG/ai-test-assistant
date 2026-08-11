import json

import pytest

from agent.compact_requirement_analysis import (
    CompactGlobalQuestions,
    CompactRequirementBatch,
)
from agent.models import ClarificationCategory
from agent.requirement_chunking import RequirementChunker
from agent.requirement_statements import RequirementStatementExtractor


def _catalog():
    chunks = RequirementChunker(max_chars=500).split(
        "## 库存\n库存充足时创建订单。\n库存不足时拒绝创建订单。"
    )
    statements = RequirementStatementExtractor().extract(chunks)
    return {item.statement_id: item for item in statements}


def test_compact_batch_validates_ids_and_restores_original_text():
    catalog = _catalog()
    payload = {
        "summary": "订单库存校验",
        "modules": ["订单", "库存"],
        "fact_ids": ["S001", "S002"],
        "business_rule_ids": ["S002"],
        "state_transition_ids": [],
        "inferred_risks": [
            {"risk": "并发下单可能超卖", "basis_ids": ["S001"]}
        ],
    }

    batch = CompactRequirementBatch.from_json(
        json.dumps(payload, ensure_ascii=False), set(catalog)
    )
    result = batch.to_requirement_result(catalog)

    assert result.requirement_facts == [
        "库存充足时创建订单。", "库存不足时拒绝创建订单。"
    ]
    assert result.business_rules == ["库存不足时拒绝创建订单。"]
    assert "S001" in result.inferred_risks[0].basis


def test_compact_batch_rejects_unknown_statement_id():
    payload = {
        "summary": "摘要", "modules": [], "fact_ids": ["S999"],
        "business_rule_ids": [], "state_transition_ids": [],
        "inferred_risks": [],
    }
    with pytest.raises(ValueError, match="S999"):
        CompactRequirementBatch.from_json(json.dumps(payload), {"S001"})


def test_global_questions_restore_evidence_and_category():
    catalog = _catalog()
    payload = {
        "open_questions": [
            {
                "question": "库存扣减失败后如何处理？",
                "category": "flow_branch",
                "blocking_reason": "无法判断订单是否创建",
                "evidence_ids": ["S001"],
            }
        ]
    }

    result = CompactGlobalQuestions.from_json(
        json.dumps(payload, ensure_ascii=False), catalog
    )

    assert result.candidates[0].category is ClarificationCategory.FLOW_BRANCH
    assert "库存充足时创建订单" in result.candidates[0].evidence


def test_global_questions_reject_unknown_evidence_id():
    catalog = _catalog()
    payload = {
        "open_questions": [
            {
                "question": "问题？", "category": "core_rule",
                "blocking_reason": "原因", "evidence_ids": ["S999"],
            }
        ]
    }
    with pytest.raises(ValueError, match="evidence IDs"):
        CompactGlobalQuestions.from_json(json.dumps(payload), catalog)

