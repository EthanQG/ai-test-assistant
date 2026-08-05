from datetime import datetime, timezone

from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetChunkBuilder,
    KnowledgeAssetChunkType,
)
from tests.unit.knowledge_assets.support import make_eligible_state


def _asset():
    return KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: "asset-index-chunks",
        clock=lambda: datetime(2026, 8, 5, 4, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )


def test_chunk_builder_creates_self_contained_typed_chunks():
    result = KnowledgeAssetChunkBuilder().build(_asset())

    assert result.chunks
    assert result.chunks[0].chunk_type is KnowledgeAssetChunkType.OVERVIEW
    assert all("需求主题：" in chunk.search_text for chunk in result.chunks)
    assert all(chunk.asset_id == "asset-index-chunks" for chunk in result.chunks)
    assert {chunk.chunk_type for chunk in result.chunks} >= {
        KnowledgeAssetChunkType.REQUIREMENT_FACT,
        KnowledgeAssetChunkType.BUSINESS_RULE,
        KnowledgeAssetChunkType.RISK,
        KnowledgeAssetChunkType.TEST_POINT,
    }


def test_chunk_builder_uses_stable_real_asset_association_metadata():
    asset = _asset()
    first = KnowledgeAssetChunkBuilder().build(asset)
    second = KnowledgeAssetChunkBuilder().build(asset)

    assert first == second
    assert all(chunk.source_task_id == asset.source_task_id for chunk in first.chunks)
    assert all(chunk.content_hash == asset.content_hash for chunk in first.chunks)
    assert all(chunk.asset_version == asset.asset_version for chunk in first.chunks)


def test_chunk_builder_bounds_chunk_count_and_reports_omissions():
    result = KnowledgeAssetChunkBuilder(max_chunks=2).build(_asset())

    assert len(result.chunks) == 2
    assert result.candidate_count > 2
    assert result.omitted_count == result.candidate_count - 2


def test_chunk_builder_bounds_text_length_and_marks_truncation():
    asset = _asset()
    object.__setattr__(asset, "original_requirement", "长需求" * 1000)

    result = KnowledgeAssetChunkBuilder(max_text_chars=220).build(asset)

    overview = result.chunks[0]
    assert overview.was_truncated is True
    assert len(overview.search_text) <= 221
