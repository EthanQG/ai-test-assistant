import pytest

from agent.requirement_chunking import RequirementChunker
from agent.requirement_statements import (
    RequirementStatement,
    RequirementStatementExtractor,
)


def _extract(text: str):
    chunks = RequirementChunker(max_chars=500).split(text)
    return RequirementStatementExtractor().extract(chunks)


def test_extracts_list_and_sentence_statements_with_stable_ids():
    text = (
        "# 订单需求\n"
        "## 1. 库存规则\n"
        "1. 库存充足时创建订单。库存不足时拒绝创建。\n"
        "2. 同一request_id只创建一张订单。\n"
    )

    first = _extract(text)
    second = _extract(text)

    assert first == second
    assert [item.statement_id for item in first] == ["S001", "S002", "S003"]
    assert [item.text for item in first] == [
        "库存充足时创建订单。",
        "库存不足时拒绝创建。",
        "同一request_id只创建一张订单。",
    ]
    assert all(item.section == "1. 库存规则" for item in first)


def test_preserves_chunk_and_absolute_character_source():
    text = "## 第一部分\n" + ("库存规则。" * 80) + "\n## 第二部分\n支付成功。"
    chunks = RequirementChunker(max_chars=500).split(text)

    statements = RequirementStatementExtractor().extract(chunks)

    assert {item.chunk_id for item in statements} == {chunk.chunk_id for chunk in chunks}
    for statement in statements:
        assert text[statement.start_char:statement.end_char] == statement.text


def test_table_rows_are_compacted_and_separator_is_ignored():
    statements = _extract(
        "## 状态表\n| 当前状态 | 操作 | 目标状态 |\n| --- | --- | --- |\n"
        "| 待支付 | 支付成功 | 已支付 |"
    )

    assert [item.text for item in statements] == [
        "当前状态；操作；目标状态",
        "待支付；支付成功；已支付",
    ]


def test_heading_and_code_fence_are_not_business_statements():
    statements = _extract("# 标题\n```json\n规则必须保留。\n```\n")

    assert [item.text for item in statements] == ["规则必须保留。"]


def test_statement_validation_and_empty_chunks():
    with pytest.raises(ValueError, match="S001"):
        RequirementStatement("bad", "规则", "章节", "chunk-001", 0, 2)
    with pytest.raises(ValueError, match="cannot be empty"):
        RequirementStatementExtractor().extract(())

