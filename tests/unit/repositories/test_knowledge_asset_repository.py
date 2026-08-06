from dataclasses import replace
from datetime import datetime, timezone

import pytest

from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetStatus,
)
from repositories import (
    InMemoryKnowledgeAssetRepository,
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
    KnowledgeAssetIndexRequestConflictError,
    KnowledgeAssetStatusConflictError,
)

from tests.unit.knowledge_assets.support import make_eligible_state


def _make_asset(asset_id="asset-1", version=1):
    return KnowledgeAssetAdmissionPolicy(
        clock=lambda: datetime(2026, 8, 5, tzinfo=timezone.utc),
        asset_id_factory=lambda: asset_id,
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=version,
    )


def test_repository_creates_reads_lists_and_finds_asset():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()

    repository.create(asset)

    assert repository.get(asset.asset_id) == asset
    assert repository.find_by_content_hash(asset.content_hash) == asset
    assert (
        repository.find_latest_by_source_task_id(asset.source_task_id)
        == asset
    )
    assert repository.list() == [asset]


def test_repository_returns_isolated_copies():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()
    repository.create(asset)

    loaded = repository.get(asset.asset_id)
    loaded.test_points[0].steps.append("页面侧修改")

    assert repository.get(asset.asset_id).test_points[0].steps == [
        "提交包含该商品的订单"
    ]


def test_repository_batch_reads_existing_assets_only():
    first = _make_asset("asset-batch-1")
    second = replace(
        first,
        asset_id="asset-batch-2",
        asset_version=2,
        content_hash="b" * 64,
    )
    repository = InMemoryKnowledgeAssetRepository()
    repository.create(first)
    repository.create(second)

    result = repository.get_many(
        [first.asset_id, "stale-vector-id", second.asset_id, first.asset_id]
    )

    assert set(result) == {first.asset_id, second.asset_id}
    assert result[first.asset_id] == first
    assert result[first.asset_id] is not first


def test_repository_rejects_duplicate_identity_hash_and_source_version():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()
    repository.create(asset)

    with pytest.raises(KnowledgeAssetAlreadyExistsError, match="asset_id"):
        repository.create(asset)
    with pytest.raises(KnowledgeAssetAlreadyExistsError, match="content_hash"):
        repository.create(replace(asset, asset_id="asset-2"))
    with pytest.raises(
        KnowledgeAssetAlreadyExistsError,
        match="source task version",
    ):
        repository.create(
            replace(
                asset,
                asset_id="asset-3",
                content_hash="f" * 64,
            )
        )


def test_repository_returns_latest_source_version():
    repository = InMemoryKnowledgeAssetRepository()
    first = _make_asset()
    second = replace(
        first,
        asset_id="asset-2",
        asset_version=2,
        content_hash="a" * 64,
    )

    repository.create(first)
    repository.create(second)

    assert (
        repository.find_latest_by_source_task_id(first.source_task_id)
        == second
    )


def test_repository_missing_lookup_semantics_are_explicit():
    repository = InMemoryKnowledgeAssetRepository()

    assert repository.find_by_content_hash("a" * 64) is None
    assert repository.find_latest_by_source_task_id("missing-task") is None
    with pytest.raises(KnowledgeAssetNotFoundError, match="missing-asset"):
        repository.get("missing-asset")


def test_repository_updates_status_with_expected_state_guard():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()
    repository.create(asset)

    updated = repository.update_status(
        asset.asset_id,
        KnowledgeAssetStatus.INDEXED,
        expected_status=KnowledgeAssetStatus.PENDING_INDEX,
    )

    assert updated.status is KnowledgeAssetStatus.INDEXED
    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.INDEXED


def test_repository_rejects_stale_status_update():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()
    repository.create(asset)

    with pytest.raises(KnowledgeAssetStatusConflictError):
        repository.update_status(
            asset.asset_id,
            KnowledgeAssetStatus.RETIRED,
            expected_status=KnowledgeAssetStatus.INDEXED,
        )


def test_repository_index_retry_is_atomic_idempotent_and_auditable():
    repository = InMemoryKnowledgeAssetRepository()
    asset = replace(_make_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    repository.create(asset)
    started_at = datetime(2026, 8, 6, 2, 0, tzinfo=timezone.utc)

    request, created = repository.begin_index_retry(
        asset.asset_id,
        "request-1",
        started_at=started_at,
    )
    replayed, replay_created = repository.begin_index_retry(
        asset.asset_id,
        "request-1",
        started_at=started_at,
    )

    assert created is True
    assert replay_created is False
    assert replayed == request
    assert request.status is KnowledgeAssetIndexRequestStatus.RUNNING
    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.PENDING_INDEX
    assert repository.list_index_requests(asset.asset_id) == [request]

    finished = repository.finish_index_request(
        request.request_id,
        KnowledgeAssetIndexRequestStatus.SUCCEEDED,
        chunk_count=8,
        omitted_chunk_count=2,
        error_type=None,
        error_message=None,
        finished_at=datetime(2026, 8, 6, 2, 1, tzinfo=timezone.utc),
    )
    duplicate_finish = repository.finish_index_request(
        request.request_id,
        KnowledgeAssetIndexRequestStatus.FAILED,
        chunk_count=0,
        omitted_chunk_count=0,
        error_type="ignored",
        error_message="ignored",
        finished_at=datetime(2026, 8, 6, 2, 2, tzinfo=timezone.utc),
    )

    assert finished.status is KnowledgeAssetIndexRequestStatus.SUCCEEDED
    assert finished.chunk_count == 8
    assert duplicate_finish == finished


def test_repository_retry_request_id_cannot_be_reused_for_another_asset():
    first = replace(_make_asset("asset-retry-1"), status=KnowledgeAssetStatus.INDEX_FAILED)
    second = replace(
        first,
        asset_id="asset-retry-2",
        content_hash="c" * 64,
        source_task_id="task-retry-2",
    )
    repository = InMemoryKnowledgeAssetRepository()
    repository.create(first)
    repository.create(second)
    started_at = datetime(2026, 8, 6, 2, 0, tzinfo=timezone.utc)
    repository.begin_index_retry(
        first.asset_id,
        "shared-request",
        started_at=started_at,
    )

    with pytest.raises(KnowledgeAssetIndexRequestConflictError):
        repository.begin_index_retry(
            second.asset_id,
            "shared-request",
            started_at=started_at,
        )


def test_repository_rejects_retry_for_asset_that_has_not_failed():
    repository = InMemoryKnowledgeAssetRepository()
    asset = _make_asset()
    repository.create(asset)

    with pytest.raises(KnowledgeAssetStatusConflictError):
        repository.begin_index_retry(
            asset.asset_id,
            "invalid-retry",
            started_at=datetime.now(timezone.utc),
        )

    assert repository.get(asset.asset_id).status is KnowledgeAssetStatus.PENDING_INDEX
    assert repository.list_index_requests(asset.asset_id) == []
