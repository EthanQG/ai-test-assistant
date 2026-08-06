from dataclasses import replace
from datetime import datetime, timezone

import pytest

from application import (
    KnowledgeAssetIndexingBusyError,
    KnowledgeAssetIndexingError,
    KnowledgeAssetIndexingRequestFinishedError,
    KnowledgeAssetIndexingService,
)
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetStatus,
)
from repositories import InMemoryKnowledgeAssetRepository
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeEmbeddingService:
    def __init__(self, vectors=None, error=None):
        self.vectors = vectors
        self.error = error
        self.texts = []
        self.calls = 0

    def embed_batch(self, texts):
        self.calls += 1
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
        self.deletions = []
        self.delete_error = None

    def ensure_collection(self, vector_dimension):
        self.dimension = vector_dimension
        if self.error:
            raise self.error

    def upsert(self, chunks, vectors):
        self.chunks = list(chunks)
        self.vectors = [list(vector) for vector in vectors]

    def delete_asset(self, asset_id, asset_version):
        self.deletions.append((asset_id, asset_version))
        if self.delete_error:
            raise self.delete_error


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


def test_retry_failed_asset_records_success_and_replays_without_external_calls():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    repository = _repository(asset)
    embedding = _FakeEmbeddingService()
    vector_index = _FakeVectorIndex()
    clock_values = iter(
        [
            datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 6, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 6, 1, 2, tzinfo=timezone.utc),
        ]
    )
    service = KnowledgeAssetIndexingService(
        repository,
        embedding,
        vector_index,
        clock=lambda: next(clock_values),
    )

    first = service.retry_failed_asset(asset.asset_id, "retry-request-1")
    first_embedding_calls = embedding.calls
    first_chunk_ids = [chunk.chunk_id for chunk in vector_index.chunks]
    replayed = service.retry_failed_asset(asset.asset_id, "retry-request-1")

    assert first.status is KnowledgeAssetStatus.INDEXED
    assert first.request_id == "retry-request-1"
    assert replayed.replayed_request is True
    assert replayed.chunk_count == first.chunk_count
    assert embedding.calls == first_embedding_calls
    assert [chunk.chunk_id for chunk in vector_index.chunks] == first_chunk_ids
    request = repository.list_index_requests(asset.asset_id)[0]
    assert request.status is KnowledgeAssetIndexRequestStatus.SUCCEEDED
    assert request.chunk_count == first.chunk_count


def test_retry_failure_is_audited_and_requires_a_new_request_id():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    repository = _repository(asset)
    embedding = _FakeEmbeddingService(error=RuntimeError("unavailable"))
    service = KnowledgeAssetIndexingService(
        repository,
        embedding,
        _FakeVectorIndex(),
    )

    with pytest.raises(KnowledgeAssetIndexingError):
        service.retry_failed_asset(asset.asset_id, "failed-request")
    with pytest.raises(KnowledgeAssetIndexingRequestFinishedError):
        service.retry_failed_asset(asset.asset_id, "failed-request")

    request = repository.list_index_requests(asset.asset_id)[0]
    assert request.status is KnowledgeAssetIndexRequestStatus.FAILED
    assert request.error_type == "KnowledgeAssetIndexingError"
    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.INDEX_FAILED

    embedding.error = None
    recovered = service.retry_failed_asset(asset.asset_id, "new-request")
    assert recovered.status is KnowledgeAssetStatus.INDEXED


def test_retry_running_request_is_not_executed_twice():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    repository = _repository(asset)
    repository.begin_index_retry(
        asset.asset_id,
        "running-request",
        started_at=datetime.now(timezone.utc),
    )
    embedding = _FakeEmbeddingService()

    with pytest.raises(KnowledgeAssetIndexingBusyError):
        KnowledgeAssetIndexingService(
            repository,
            embedding,
            _FakeVectorIndex(),
        ).retry_failed_asset(asset.asset_id, "running-request")

    assert embedding.texts == []


def test_retry_repairs_running_audit_after_asset_was_marked_failed():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    repository = _repository(asset)
    repository.begin_index_retry(
        asset.asset_id,
        "interrupted-request",
        started_at=datetime.now(timezone.utc),
    )
    repository.update_status(
        asset.asset_id,
        KnowledgeAssetStatus.INDEX_FAILED,
        expected_status=KnowledgeAssetStatus.PENDING_INDEX,
    )

    with pytest.raises(KnowledgeAssetIndexingRequestFinishedError):
        KnowledgeAssetIndexingService(
            repository,
            _FakeEmbeddingService(),
            _FakeVectorIndex(),
        ).retry_failed_asset(asset.asset_id, "interrupted-request")

    request = repository.list_index_requests(asset.asset_id)[0]
    assert request.status is KnowledgeAssetIndexRequestStatus.FAILED
    assert request.error_type == "RecoveredIndexFailure"


def test_retire_asset_marks_mysql_first_and_deletes_vectors():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEXED)
    repository = _repository(asset)

    class _AssertingVectorIndex(_FakeVectorIndex):
        def delete_asset(self, asset_id, asset_version):
            assert repository.get(asset_id).status is KnowledgeAssetStatus.RETIRED
            super().delete_asset(asset_id, asset_version)

    vector_index = _AssertingVectorIndex()
    result = KnowledgeAssetIndexingService(
        repository,
        _FakeEmbeddingService(),
        vector_index,
    ).retire_asset(asset.asset_id)

    assert result.status is KnowledgeAssetStatus.RETIRED
    assert result.vector_cleanup_completed is True
    assert vector_index.deletions == [(asset.asset_id, asset.asset_version)]


def test_retire_asset_cleanup_can_be_retried_after_milvus_failure():
    asset = replace(_asset(), status=KnowledgeAssetStatus.INDEXED)
    repository = _repository(asset)
    vector_index = _FakeVectorIndex()
    vector_index.delete_error = RuntimeError("milvus unavailable")
    service = KnowledgeAssetIndexingService(
        repository,
        _FakeEmbeddingService(),
        vector_index,
    )

    with pytest.raises(KnowledgeAssetIndexingError, match="cleanup failed"):
        service.retire_asset(asset.asset_id)

    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.RETIRED
    vector_index.delete_error = None
    result = service.retire_asset(asset.asset_id)
    assert result.vector_cleanup_completed is True
    assert len(vector_index.deletions) == 2


def test_retire_asset_rejects_non_indexed_asset_without_vector_deletion():
    asset = _asset()
    vector_index = _FakeVectorIndex()

    with pytest.raises(KnowledgeAssetIndexingError, match="only indexed"):
        KnowledgeAssetIndexingService(
            _repository(asset),
            _FakeEmbeddingService(),
            vector_index,
        ).retire_asset(asset.asset_id)

    assert vector_index.deletions == []
