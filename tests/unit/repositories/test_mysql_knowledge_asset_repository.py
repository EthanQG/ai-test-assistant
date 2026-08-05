import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from application.bootstrap import build_knowledge_asset_repository
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetSnapshotSerializer,
)
from repositories import (
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
    KnowledgeAssetRepositoryError,
    MySQLKnowledgeAssetRepository,
)
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeMySQLError(Exception):
    pass


class _FakeCursor:
    def __init__(self):
        self.executed = []
        self.fetchone_result = None
        self.fetchall_result = []
        self.fail_exception = None
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if self.fail_exception is not None:
            raise self.fail_exception

    def fetchone(self):
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


def test_mysql_asset_repository_initializes_authoritative_table():
    connection = _FakeConnection()

    _repository(connection).initialize_schema()

    sql = connection.cursor_instance.executed[0][0]
    assert "CREATE TABLE IF NOT EXISTS knowledge_assets" in sql
    assert "uq_knowledge_assets_content_hash" in sql
    assert "uq_knowledge_assets_source_version" in sql
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
