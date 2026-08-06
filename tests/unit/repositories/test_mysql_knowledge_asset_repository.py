import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from application.bootstrap import build_knowledge_asset_repository
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetSnapshotSerializer,
    KnowledgeAssetStatus,
)
from repositories import (
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
    KnowledgeAssetIndexRequestConflictError,
    KnowledgeAssetRepositoryError,
    KnowledgeAssetStatusConflictError,
    MySQLKnowledgeAssetRepository,
)
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeMySQLError(Exception):
    pass


class _FakeCursor:
    def __init__(self):
        self.executed = []
        self.fetchone_result = None
        self.fetchone_results = []
        self.fetchall_result = []
        self.fail_exception = None
        self.closed = False
        self.rowcount = 1

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if self.fail_exception is not None:
            raise self.fail_exception

    def fetchone(self):
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return self.fetchone_result

    def fetchall(self):
        return list(self.fetchall_result)

    def close(self):
        self.closed = True


class _FakeConnection:
    def __init__(self):
        self.cursor_instance = _FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _asset(asset_id="asset-mysql-1"):
    return KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime(2026, 8, 5, 3, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )


def _repository(connection):
    return MySQLKnowledgeAssetRepository(
        lambda: connection,
        KnowledgeAssetSnapshotSerializer,
    )


def _row(asset):
    return {"asset_json": KnowledgeAssetSnapshotSerializer.to_json(asset)}


def _request_row(
    *,
    request_id="request-mysql-1",
    asset_id="asset-mysql-1",
    status="running",
    finished_at=None,
):
    return {
        "request_id": request_id,
        "asset_id": asset_id,
        "status": status,
        "chunk_count": 0,
        "omitted_chunk_count": 0,
        "error_type": None,
        "error_message": None,
        "started_at": datetime(2026, 8, 6, 1, 0),
        "finished_at": finished_at,
    }


def test_mysql_asset_repository_initializes_authoritative_table():
    connection = _FakeConnection()

    _repository(connection).initialize_schema()

    asset_sql = connection.cursor_instance.executed[0][0]
    request_sql = connection.cursor_instance.executed[1][0]
    assert "CREATE TABLE IF NOT EXISTS knowledge_assets" in asset_sql
    assert "uq_knowledge_assets_content_hash" in asset_sql
    assert "uq_knowledge_assets_source_version" in asset_sql
    assert "CREATE TABLE IF NOT EXISTS knowledge_asset_index_requests" in request_sql
    assert "request_id VARCHAR(64) NOT NULL PRIMARY KEY" in request_sql
    assert connection.commits == 1
    assert connection.closed is True


def test_mysql_asset_repository_creates_complete_snapshot():
    connection = _FakeConnection()
    asset = _asset()

    _repository(connection).create(asset)

    sql, params = connection.cursor_instance.executed[0]
    snapshot = json.loads(params[9])
    assert "INSERT INTO knowledge_assets" in sql
    assert params[0] == asset.asset_id
    assert params[3] == 1
    assert snapshot["asset_id"] == asset.asset_id
    assert snapshot["asset"]["test_points"]
    assert connection.commits == 1


def test_mysql_asset_repository_maps_duplicate_key():
    connection = _FakeConnection()
    connection.cursor_instance.fail_exception = _FakeMySQLError(
        1062,
        "duplicate",
    )

    with pytest.raises(KnowledgeAssetAlreadyExistsError):
        _repository(connection).create(_asset())

    assert connection.rollbacks == 1


def test_mysql_asset_repository_get_restores_typed_asset():
    connection = _FakeConnection()
    asset = _asset()
    connection.cursor_instance.fetchone_result = _row(asset)

    restored = _repository(connection).get(asset.asset_id)

    assert restored == asset
    assert restored is not asset


def test_mysql_asset_repository_get_missing_raises_domain_error():
    connection = _FakeConnection()

    with pytest.raises(KnowledgeAssetNotFoundError):
        _repository(connection).get("missing")


def test_mysql_asset_repository_batch_reads_assets_with_one_query():
    connection = _FakeConnection()
    first = _asset("asset-batch-1")
    second = _asset("asset-batch-2")
    connection.cursor_instance.fetchall_result = [
        {"asset_id": first.asset_id, **_row(first)},
        {"asset_id": second.asset_id, **_row(second)},
    ]

    assets = _repository(connection).get_many(
        [first.asset_id, second.asset_id, first.asset_id]
    )

    sql, params = connection.cursor_instance.executed[0]
    assert "WHERE asset_id IN (%s, %s)" in sql
    assert params == (first.asset_id, second.asset_id)
    assert assets == {first.asset_id: first, second.asset_id: second}
    assert len(connection.cursor_instance.executed) == 1


def test_mysql_asset_repository_empty_batch_does_not_open_connection():
    opened = []
    repository = MySQLKnowledgeAssetRepository(
        lambda: opened.append(True),
        KnowledgeAssetSnapshotSerializer,
    )

    assert repository.get_many([]) == {}
    assert opened == []


def test_mysql_asset_repository_finds_hash_and_latest_source():
    hash_connection = _FakeConnection()
    latest_connection = _FakeConnection()
    asset = _asset()
    hash_connection.cursor_instance.fetchone_result = _row(asset)
    latest_connection.cursor_instance.fetchone_result = _row(asset)

    by_hash = _repository(hash_connection).find_by_content_hash(
        asset.content_hash
    )
    latest = _repository(latest_connection).find_latest_by_source_task_id(
        asset.source_task_id
    )

    assert by_hash == asset
    assert latest == asset
    assert "content_hash = %s" in hash_connection.cursor_instance.executed[0][0]
    assert "ORDER BY asset_version DESC" in latest_connection.cursor_instance.executed[0][0]


def test_mysql_asset_repository_list_restores_all_rows():
    connection = _FakeConnection()
    first = _asset("asset-mysql-1")
    second = _asset("asset-mysql-2")
    connection.cursor_instance.fetchall_result = [_row(first), _row(second)]

    assets = _repository(connection).list()

    assert assets == [first, second]


def test_mysql_asset_repository_rolls_back_failed_schema_initialization():
    connection = _FakeConnection()
    connection.cursor_instance.fail_exception = RuntimeError("ddl failed")

    with pytest.raises(KnowledgeAssetRepositoryError):
        _repository(connection).initialize_schema()

    assert connection.rollbacks == 1


def test_mysql_asset_repository_updates_status_and_snapshot_atomically():
    connection = _FakeConnection()
    asset = _asset()
    connection.cursor_instance.fetchone_result = _row(asset)

    updated = _repository(connection).update_status(
        asset.asset_id,
        KnowledgeAssetStatus.INDEXED,
        expected_status=KnowledgeAssetStatus.PENDING_INDEX,
    )

    select_sql, _ = connection.cursor_instance.executed[0]
    update_sql, params = connection.cursor_instance.executed[1]
    snapshot = json.loads(params[1])
    assert "FOR UPDATE" in select_sql
    assert "UPDATE knowledge_assets" in update_sql
    assert params[0] == "indexed"
    assert snapshot["asset"]["status"] == "indexed"
    assert updated.status is KnowledgeAssetStatus.INDEXED
    assert connection.commits == 1


def test_mysql_asset_repository_rejects_stale_status_update():
    connection = _FakeConnection()
    connection.cursor_instance.fetchone_result = _row(_asset())

    with pytest.raises(KnowledgeAssetStatusConflictError):
        _repository(connection).update_status(
            "asset-mysql-1",
            KnowledgeAssetStatus.RETIRED,
            expected_status=KnowledgeAssetStatus.INDEXED,
        )

    assert connection.rollbacks == 1


def test_mysql_asset_repository_begins_retry_in_one_transaction():
    connection = _FakeConnection()
    failed_asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    connection.cursor_instance.fetchone_results = [_row(failed_asset), None]
    started_at = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)

    request, created = _repository(connection).begin_index_retry(
        failed_asset.asset_id,
        "request-mysql-1",
        started_at=started_at,
    )

    statements = [sql for sql, _ in connection.cursor_instance.executed]
    assert created is True
    assert request.status is KnowledgeAssetIndexRequestStatus.RUNNING
    assert any("UPDATE knowledge_assets" in sql for sql in statements)
    assert any("INSERT INTO knowledge_asset_index_requests" in sql for sql in statements)
    update_params = next(
        params
        for sql, params in connection.cursor_instance.executed
        if "UPDATE knowledge_assets" in sql
    )
    assert json.loads(update_params[1])["asset"]["status"] == "pending_index"
    assert connection.commits == 1


def test_mysql_asset_repository_replays_existing_retry_without_mutation():
    connection = _FakeConnection()
    failed_asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    connection.cursor_instance.fetchone_results = [
        _row(failed_asset),
        _request_row(),
    ]

    request, created = _repository(connection).begin_index_retry(
        failed_asset.asset_id,
        "request-mysql-1",
        started_at=datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc),
    )

    assert created is False
    assert request.request_id == "request-mysql-1"
    assert len(connection.cursor_instance.executed) == 2
    assert connection.commits == 1


def test_mysql_asset_repository_rejects_request_id_for_another_asset():
    connection = _FakeConnection()
    failed_asset = replace(_asset(), status=KnowledgeAssetStatus.INDEX_FAILED)
    connection.cursor_instance.fetchone_results = [
        _row(failed_asset),
        _request_row(asset_id="another-asset"),
    ]

    with pytest.raises(KnowledgeAssetIndexRequestConflictError):
        _repository(connection).begin_index_retry(
            failed_asset.asset_id,
            "request-mysql-1",
            started_at=datetime.now(timezone.utc),
        )

    assert connection.rollbacks == 1


def test_mysql_asset_repository_finishes_and_lists_retry_audit():
    finish_connection = _FakeConnection()
    finish_connection.cursor_instance.fetchone_result = _request_row()
    finished_at = datetime(2026, 8, 6, 1, 1, tzinfo=timezone.utc)

    finished = _repository(finish_connection).finish_index_request(
        "request-mysql-1",
        KnowledgeAssetIndexRequestStatus.SUCCEEDED,
        chunk_count=6,
        omitted_chunk_count=1,
        error_type=None,
        error_message=None,
        finished_at=finished_at,
    )

    assert finished.status is KnowledgeAssetIndexRequestStatus.SUCCEEDED
    assert finished.chunk_count == 6
    assert any(
        "UPDATE knowledge_asset_index_requests" in sql
        for sql, _ in finish_connection.cursor_instance.executed
    )
    assert finish_connection.commits == 1

    list_connection = _FakeConnection()
    list_connection.cursor_instance.fetchall_result = [
        _request_row(
            status="succeeded",
            finished_at=datetime(2026, 8, 6, 1, 1),
        )
    ]
    requests = _repository(list_connection).list_index_requests(
        "asset-mysql-1"
    )
    assert requests[0].status is KnowledgeAssetIndexRequestStatus.SUCCEEDED
    assert requests[0].started_at.tzinfo is not None


@patch("application.bootstrap.MySQLKnowledgeAssetRepository")
@patch("application.bootstrap.build_mysql_connection_factory")
@patch("application.bootstrap.MySQLSettings.from_env")
def test_asset_repository_bootstrap_selects_mysql(
    settings,
    build_connection_factory,
    repository_type,
):
    repository = repository_type.return_value

    with patch.dict(
        "os.environ",
        {"KNOWLEDGE_ASSET_REPOSITORY_BACKEND": "mysql"},
        clear=False,
    ):
        result = build_knowledge_asset_repository()

    assert result is repository
    build_connection_factory.assert_called_once_with(settings.return_value)
    repository.initialize_schema.assert_called_once_with()


def test_asset_repository_bootstrap_rejects_unknown_backend():
    with patch.dict(
        "os.environ",
        {"KNOWLEDGE_ASSET_REPOSITORY_BACKEND": "redis"},
        clear=False,
    ):
        with pytest.raises(ValueError, match="must be either"):
            build_knowledge_asset_repository()
