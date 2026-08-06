import os
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetSnapshotSerializer,
    KnowledgeAssetStatus,
)
from repositories import (
    KnowledgeAssetNotFoundError,
    MySQLKnowledgeAssetRepository,
    MySQLSettings,
    build_mysql_connection_factory,
)
from tests.unit.knowledge_assets.support import make_eligible_state


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MYSQL_INTEGRATION_TESTS", "").strip() != "1",
    reason="set RUN_MYSQL_INTEGRATION_TESTS=1 to run real MySQL tests",
)


@pytest.fixture
def mysql_asset_repository():
    load_dotenv()
    connection_factory = build_mysql_connection_factory(
        MySQLSettings.from_env()
    )
    repository = MySQLKnowledgeAssetRepository(
        connection_factory,
        KnowledgeAssetSnapshotSerializer,
    )
    repository.initialize_schema()
    created_ids = []
    yield repository, connection_factory, created_ids
    connection = connection_factory()
    cursor = connection.cursor()
    try:
        for asset_id in created_ids:
            cursor.execute(
                "DELETE FROM knowledge_asset_index_requests WHERE asset_id = %s",
                (asset_id,),
            )
            cursor.execute(
                "DELETE FROM knowledge_assets WHERE asset_id = %s",
                (asset_id,),
            )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def test_real_mysql_knowledge_asset_crud(mysql_asset_repository):
    repository, _, created_ids = mysql_asset_repository
    asset_id = str(uuid4())
    state = make_eligible_state()
    state.requirement = f"{state.requirement}\n测试资产标识：{asset_id}"
    asset = KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime.now(timezone.utc),
    ).admit(
        state,
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )
    created_ids.append(asset_id)

    repository.create(asset)
    restored = repository.get(asset_id)

    assert restored == asset
    assert restored.status is KnowledgeAssetStatus.PENDING_INDEX
    assert repository.find_by_content_hash(asset.content_hash) == asset
    assert repository.find_latest_by_source_task_id(state.task_id) == asset
    assert repository.get_many([asset_id, str(uuid4())]) == {asset_id: asset}

    updated = repository.update_status(
        asset_id,
        KnowledgeAssetStatus.INDEXED,
        expected_status=KnowledgeAssetStatus.PENDING_INDEX,
    )
    assert updated.status is KnowledgeAssetStatus.INDEXED
    assert repository.get(asset_id).status is KnowledgeAssetStatus.INDEXED


def test_real_mysql_knowledge_asset_missing(mysql_asset_repository):
    repository, _, _ = mysql_asset_repository

    with pytest.raises(KnowledgeAssetNotFoundError):
        repository.get(str(uuid4()))


def test_real_mysql_knowledge_asset_retry_audit_is_idempotent(
    mysql_asset_repository,
):
    repository, _, created_ids = mysql_asset_repository
    asset_id = str(uuid4())
    request_id = str(uuid4())
    asset = KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime.now(timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )
    asset = replace(asset, status=KnowledgeAssetStatus.INDEX_FAILED)
    created_ids.append(asset_id)
    repository.create(asset)

    request, created = repository.begin_index_retry(
        asset_id,
        request_id,
        started_at=datetime.now(timezone.utc),
    )
    replayed, replay_created = repository.begin_index_retry(
        asset_id,
        request_id,
        started_at=datetime.now(timezone.utc),
    )
    finished = repository.finish_index_request(
        request_id,
        KnowledgeAssetIndexRequestStatus.SUCCEEDED,
        chunk_count=5,
        omitted_chunk_count=1,
        error_type=None,
        error_message=None,
        finished_at=datetime.now(timezone.utc),
    )

    assert created is True
    assert replay_created is False
    assert replayed == request
    assert repository.get(asset_id).status is KnowledgeAssetStatus.PENDING_INDEX
    assert finished.status is KnowledgeAssetIndexRequestStatus.SUCCEEDED
    assert repository.list_index_requests(asset_id) == [finished]
