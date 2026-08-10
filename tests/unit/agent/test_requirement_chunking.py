import pytest

from agent.requirement_chunking import RequirementChunker


def test_short_requirement_stays_in_one_chunk():
    text = "# 订单需求\n库存充足时创建订单。"

    chunks = RequirementChunker(max_chars=500).split(text)

    assert len(chunks) == 1
    assert chunks[0].content == text
    assert chunks[0].title == "订单需求"


def test_markdown_sections_are_packed_without_losing_order():
    text = "".join(
        f"## {index}. 章节{index}\n" + (f"规则{index}。" * 60) + "\n"
        for index in range(1, 7)
    )

    chunks = RequirementChunker(max_chars=500).split(text)

    assert len(chunks) > 1
    assert "".join(chunk.content for chunk in chunks) == text
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    assert [chunk.chunk_id for chunk in chunks] == [
        f"chunk-{index:03d}" for index in range(1, len(chunks) + 1)
    ]


def test_oversized_section_prefers_paragraph_or_sentence_boundary():
    text = "# 超长章节\n\n" + ("库存规则。" * 140) + "\n\n支付规则。"

    chunks = RequirementChunker(max_chars=500).split(text)

    assert len(chunks) >= 2
    assert "".join(chunk.content for chunk in chunks) == text
    assert all(len(chunk.content) <= 500 for chunk in chunks)
    assert chunks[0].end_char == chunks[1].start_char


def test_plain_text_uses_bounded_sentence_splits():
    text = "订单创建成功。" * 120

    chunks = RequirementChunker(max_chars=500).split(text)

    assert len(chunks) > 1
    assert "".join(chunk.content for chunk in chunks) == text
    assert all(chunk.content.endswith("。") for chunk in chunks[:-1])


def test_invalid_input_and_too_small_limit_are_rejected():
    with pytest.raises(ValueError, match="at least 500"):
        RequirementChunker(max_chars=100)
    with pytest.raises(ValueError, match="cannot be empty"):
        RequirementChunker().split("  ")

