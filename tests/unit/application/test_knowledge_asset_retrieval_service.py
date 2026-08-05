from dataclasses import replace
from datetime import datetime, timezone
import hashlib

import pytest

from application import KnowledgeAssetRetrievalError, KnowledgeAssetRetrievalService
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetChunkType,
    KnowledgeAssetStatus,
    KnowledgeAssetVectorHit,
)
from repositories import InMemoryKnowledgeAssetRepository
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeEmbeddingService:
    def __init__(self, vectors=None):
        self.vectors = [[0.1, 0.2]] if vectors is None else vectors
        self.calls = []

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return self.vectors


class _FakeVectorSearch:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query_vector, *, limit):
        self.calls.append((list(query_vector), limit))
        return list(self.hits)


def _asset(asset_id="asset-retrieval", *, status=KnowledgeAssetStatus.INDEXED):
    admitted = KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime(2026, 8, 5, 8, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )
    return replace(
        admitted,
        source_task_id=f"task-{asset_id}",
        content_hash=hashlib.sha256(asset_id.encode("utf-8")).hexdigest(),
        status=status,
    )


def _hit(asset, *, score=0.9, index=0, content_hash=None):
    return KnowledgeAssetVectorHit(
        chunk_id=f"{asset.asset_id}:1:test_point:{index}",
        asset_id=asset.asset_id,
        source_task_id=asset.source_task_id,
        asset_version=asset.asset_version,
        content_hash=content_hash or asset.content_hash,
        chunk_type=KnowledgeAssetChunkType.TEST_POINT,
        chunk_index=index,
        search_text=f"matching chunk {index}",
        score=score,
    )


def _repository(*assets):
    repository = InMemoryKnowledgeAssetRepository()
    for asset in assets:
        repository.create(asset)
    return repository


def test_retrieval_uses_one_embedding_search_and_batch_asset_read():
    asset = _asset()
    embedding = _FakeEmbeddingService()
    search = _FakeVectorSearch(
        [_hit(asset, score=0.91), _hit(asset, score=0.88, index=1)]
    )

    result = KnowledgeAssetRetrievalService(
        _repository(asset), embedding, search
    ).retrieve("merchant withdrawal risk")

    assert embedding.calls == [["merchant withdrawal risk"]]
    assert search.calls == [([0.1, 0.2], 20)]
    assert len(result.candidates) == 1
    assert result.candidates[0].asset == asset
    assert result.candidates[0].score == 0.91
    assert len(result.candidates[0].matched_chunks) == 2


def test_retrieval_filters_threshold_groups_assets_and_limits_top_k():
    first = _asset("asset-first")
    second = _asset("asset-second")
    low = _asset("asset-low")
    hits = [
        _hit(first, score=0.82),
        _hit(first, score=0.80, index=1),
        _hit(second, score=0.93),
        _hit(low, score=0.4),
    ]

    result = KnowledgeAssetRetrievalService(
        _repository(first, second, low),
        _FakeEmbeddingService(),
        _FakeVectorSearch(hits),
        top_k=1,
        raw_limit=8,
        min_score=0.65,
    ).retrieve("query")

    assert [candidate.asset.asset_id for candidate in result.candidates] == [
        "asset-second"
    ]
    assert result.raw_hit_count == 4
    assert result.threshold_hit_count == 3


@pytest.mark.parametrize(
    "stored_asset,hit_factory",
    [
        (None, lambda asset: _hit(asset)),
        (_asset("asset-pending", status=KnowledgeAssetStatus.PENDING_INDEX), lambda asset: _hit(asset)),
        (_asset("asset-version"), lambda asset: replace(_hit(asset), asset_version=2)),
        (_asset("asset-hash"), lambda asset: _hit(asset, content_hash="0" * 64)),
    ],
)
def test_retrieval_discards_orphan_unindexed_or_stale_vector_hits(stored_asset, hit_factory):
    source = stored_asset or _asset("asset-orphan")
    repository = _repository(*([stored_asset] if stored_asset else []))

    result = KnowledgeAssetRetrievalService(
        repository,
        _FakeEmbeddingService(),
        _FakeVectorSearch([hit_factory(source)]),
    ).retrieve("query")

    assert result.candidates == ()
    assert result.stale_hit_count == 1


@pytest.mark.parametrize("vectors", [[], [[], []], [[float("nan")]]])
def test_retrieval_rejects_invalid_query_embedding(vectors):
    with pytest.raises(KnowledgeAssetRetrievalError):
        KnowledgeAssetRetrievalService(
            _repository(),
            _FakeEmbeddingService(vectors=vectors),
            _FakeVectorSearch([]),
        ).retrieve("query")


def test_retrieval_rejects_empty_query_without_external_calls():
    embedding = _FakeEmbeddingService()
    search = _FakeVectorSearch([])
    with pytest.raises(ValueError, match="cannot be empty"):
        KnowledgeAssetRetrievalService(_repository(), embedding, search).retrieve("  ")
    assert embedding.calls == []
    assert search.calls == []
