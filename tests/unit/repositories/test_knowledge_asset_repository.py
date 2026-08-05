from dataclasses import replace
from datetime import datetime, timezone

import pytest

from knowledge_assets import KnowledgeAssetAdmissionPolicy
from repositories import (
    InMemoryKnowledgeAssetRepository,
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
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
