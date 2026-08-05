from dataclasses import replace
from datetime import datetime, timezone

import pytest

from application import (
    KnowledgeAssetIndexingError,
    KnowledgeAssetIndexingService,
)
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetStatus,
)
from repositories import InMemoryKnowledgeAssetRepository
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeEmbeddingService:
    def __init__(self, vectors=None, error=None):
        self.vectors = vectors
        self.error = error
        self.texts = []

    def embed_batch(self, texts):
        self.texts = list(texts)
        if self.error:
            raise self.error
        return self.vectors or [[0.1, 0.2] for _ in texts]


class _FakeVectorIndex:
    def __init__(self, error=None):
        self.error = error
        self.dimension = None
        self.chunks = []
        self.vectors = []

    def ensure_collection(self, vector_dimension):
        self.dimension = vector_dimension
        if self.error:
            raise self.error

    def upsert(self, chunks, vectors):
        self.chunks = list(chunks)
        self.vectors = [list(vector) for vector in vectors]


def _asset(asset_id="asset-index-service"):
    return KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime(2026, 8, 5, 5, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )


def _repository(asset=None):
    repository = InMemoryKnowledgeAssetRepository()
    repository.create(asset or _asset())
    return repository


def test_indexing_service_batches_embeddings_and_marks_asset_indexed():
    asset = _asset()
    repository = _repository(asset)
    embedding = _FakeEmbeddingService()
    vector_index = _FakeVectorIndex()

    result = KnowledgeAssetIndexingService(
        repository,
        embedding,
        vector_index,
    ).index_asset(asset.asset_id)

    assert result.status is KnowledgeAssetStatus.INDEXED
    assert result.chunk_count == len(embedding.texts)
    assert vector_index.dimension == 2
    assert len(vector_index.chunks) == result.chunk_count
    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.INDEXED


def test_indexing_service_keeps_stable_asset_id_in_every_vector_record():
    asset = _asset()
    repository = _repository(asset)
    vector_index = _FakeVectorIndex()

    KnowledgeAssetIndexingService(
        repository,
        _FakeEmbeddingService(),
        vector_index,
    ).index_asset(asset.asset_id)

    assert all(chunk.asset_id == asset.asset_id for chunk in vector_index.chunks)
    assert all(chunk.content_hash == asset.content_hash for chunk in vector_index.chunks)


@pytest.mark.parametrize(
    "dependency_error",
    [RuntimeError("embedding unavailable"), RuntimeError("milvus unavailable")],
)
def test_indexing_failure_marks_mysql_asset_index_failed(dependency_error):
    asset = _asset()
    repository = _repository(asset)
    embedding = (
        _FakeEmbeddingService(error=dependency_error)
        if "embedding" in str(dependency_error)
        else _FakeEmbeddingService()
    )
    vector_index = (
        _FakeVectorIndex(error=dependency_error)
        if "milvus" in str(dependency_error)
        else _FakeVectorIndex()
    )

    with pytest.raises(KnowledgeAssetIndexingError):
        KnowledgeAssetIndexingService(
            repository,
            embedding,
            vector_index,
        ).index_asset(asset.asset_id)

    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.INDEX_FAILED


def test_indexing_service_rejects_mismatched_embedding_count():
    asset = _asset()
    repository = _repository(asset)

    with pytest.raises(KnowledgeAssetIndexingError):
        KnowledgeAssetIndexingService(
            repository,
            _FakeEmbeddingService(vectors=[[0.1, 0.2]]),
            _FakeVectorIndex(),
        ).index_asset(asset.asset_id)

    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.INDEX_FAILED


def test_indexing_service_does_not_repeat_already_indexed_asset():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEXED)
    repository = _repository(asset)
    embedding = _FakeEmbeddingService()
    vector_index = _FakeVectorIndex()

    result = KnowledgeAssetIndexingService(
        repository,
        embedding,
        vector_index,
    ).index_asset(asset.asset_id)

    assert result.already_indexed is True
    assert embedding.texts == []
    assert vector_index.chunks == []


def test_indexing_service_rejects_failed_asset_until_retry_stage_exists():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)

    with pytest.raises(
        KnowledgeAssetIndexingError,
        match="only pending_index",
    ):
        KnowledgeAssetIndexingService(
            _repository(asset),
            _FakeEmbeddingService(),
            _FakeVectorIndex(),
        ).index_asset(asset.asset_id)
