import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from agent import AgentStep, TestAnalysisState
from application import TaskRecord, TaskSnapshotSerializer
from application.bootstrap import build_task_repository
from repositories import (
    InMemoryTaskRepository,
    MySQLSettings,
    MySQLTaskRepository,
    TaskAlreadyExistsError,
    TaskExecutionAlreadyFinishedError,
    TaskExecutionBusyError,
    TaskNotFoundError,
    TaskRepositoryError,
    TaskVersionConflictError,
)


class _FakeMySQLError(Exception):
    pass


class _FakeCursor:
    def __init__(self):
        self.executed = []
        self.fetchone_results = []
        self.fetchall_result = []
        self.rowcount = 1
        self.fail_on = None
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if self.fail_on and self.fail_on in normalized:
            raise self.fail_on_exception

    def fetchone(self):
        if not self.fetchone_results:
            return None
        return self.fetchone_results.pop(0)

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


def _repository(connection):
    return MySQLTaskRepository(
        lambda: connection,
        TaskSnapshotSerializer,
    )


def _record(requirement="用户提交订单"):
    return TaskRecord(state=TestAnalysisState(requirement))


class MySQLTaskRepositoryTests(unittest.TestCase):
    def test_initialize_schema_creates_task_and_event_tables(self):
        connection = _FakeConnection()

        _repository(connection).initialize_schema()

        statements = [item[0] for item in connection.cursor_instance.executed]
        self.assertIn("CREATE TABLE IF NOT EXISTS agent_tasks", statements[0])
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS agent_task_events",
            statements[1],
        )
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS agent_task_executions",
            statements[2],
        )
        self.assertIn("SHOW COLUMNS FROM agent_tasks", statements[3])
        self.assertIn("ADD COLUMN task_name", statements[4])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)

    def test_create_commits_snapshot_and_events_in_one_transaction(self):
        connection = _FakeConnection()
        record = _record()

        _repository(connection).create(record)

        executed = connection.cursor_instance.executed
        task_insert = next(item for item in executed if "agent_tasks" in item[0])
        event_inserts = [
            item for item in executed if "agent_task_events" in item[0]
        ]
        snapshot = json.loads(task_insert[1][6])
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["task_id"], record.state.task_id)
        self.assertEqual(len(event_inserts), len(record.state.events))
        self.assertEqual(connection.commits, 1)

    def test_create_maps_mysql_duplicate_key_to_domain_error(self):
        connection = _FakeConnection()
        cursor = connection.cursor_instance
        cursor.fail_on = "INSERT INTO agent_tasks"
        cursor.fail_on_exception = _FakeMySQLError(1062, "duplicate")

        with self.assertRaises(TaskAlreadyExistsError):
            _repository(connection).create(_record())

        self.assertEqual(connection.rollbacks, 1)

    def test_create_rolls_back_snapshot_when_event_insert_fails(self):
        connection = _FakeConnection()
        cursor = connection.cursor_instance
        cursor.fail_on = "INSERT INTO agent_task_events"
        cursor.fail_on_exception = _FakeMySQLError(1205, "write failed")

        with self.assertRaisesRegex(
            TaskRepositoryError,
            "failed to create MySQL task",
        ):
            _repository(connection).create(_record())

        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)

    def test_get_restores_task_record_from_snapshot(self):
        connection = _FakeConnection()
        record = _record()
        record.state.requirement_summary = "订单提交"
        connection.cursor_instance.fetchone_results.append(
            {
                "snapshot_json": TaskSnapshotSerializer.to_json(record),
                "version": 1,
            }
        )

        restored = _repository(connection).get(record.state.task_id)

        self.assertIsInstance(restored, TaskRecord)
        self.assertEqual(restored.state.task_id, record.state.task_id)
        self.assertEqual(restored.state.requirement_summary, "订单提交")
        self.assertIsInstance(restored.state.current_step, AgentStep)

    def test_get_unknown_task_raises_not_found(self):
        connection = _FakeConnection()

        with self.assertRaises(TaskNotFoundError):
            _repository(connection).get("missing")

    def test_save_updates_snapshot_and_only_appends_new_events(self):
        connection = _FakeConnection()
        record = _record()
        record.state.start_step(AgentStep.ANALYZE_REQUIREMENT, "开始分析")
        connection.cursor_instance.fetchone_results.append(
            {"event_count": 1, "version": 1}
        )

        _repository(connection).save(record)

        executed = connection.cursor_instance.executed
        updates = [item for item in executed if item[0].startswith("UPDATE")]
        event_inserts = [
            item for item in executed if "INSERT INTO agent_task_events" in item[0]
        ]
        self.assertEqual(len(updates), 1)
        self.assertIn("version = version + 1", updates[0][0])
        self.assertEqual(len(event_inserts), 1)
        self.assertEqual(event_inserts[0][1][1], 2)
        self.assertEqual(connection.commits, 1)

    def test_save_rejects_shrinking_audit_history_and_rolls_back(self):
        connection = _FakeConnection()
        connection.cursor_instance.fetchone_results.append(
            {"event_count": 2, "version": 1}
        )

        with self.assertRaisesRegex(
            TaskRepositoryError,
            "event history cannot shrink",
        ):
            _repository(connection).save(_record())

        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)

    def test_save_rejects_stale_expected_version(self):
        connection = _FakeConnection()
        connection.cursor_instance.fetchone_results.append(
            {"event_count": 1, "version": 3}
        )

        with self.assertRaises(TaskVersionConflictError) as context:
            _repository(connection).save(
                _record(),
                expected_version=2,
            )

        self.assertEqual(context.exception.actual, 3)
        self.assertEqual(connection.rollbacks, 1)

    def test_acquire_and_complete_execution_use_lease_transaction(self):
        connection = _FakeConnection()
        record = _record()
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        connection.cursor_instance.fetchone_results.extend(
            [
                {"version": 1},
                None,
                None,
                {"event_count": 1, "version": 2},
                {
                    "task_id": record.state.task_id,
                    "status": "running",
                    "lease_owner": "worker-1",
                    "lease_expires_at": future,
                },
            ]
        )
        repository = _repository(connection)

        lease = repository.acquire_execution(
            record.state.task_id,
            execution_id="execution-1",
            owner_id="worker-1",
            action="analyze_requirement",
            lease_seconds=300,
            expected_version=1,
        )
        new_version = repository.complete_execution(
            record,
            lease,
            succeeded=True,
        )

        self.assertEqual(lease.version, 2)
        self.assertEqual(new_version, 3)
        statements = [
            sql for sql, _ in connection.cursor_instance.executed
        ]
        self.assertTrue(
            any("INSERT INTO agent_task_executions" in sql for sql in statements)
        )
        self.assertTrue(
            any(
                "SET status = %s, finished_at" in sql
                for sql in statements
            )
        )
        self.assertEqual(connection.commits, 2)

    def test_acquire_rejects_finished_execution_id(self):
        connection = _FakeConnection()
        record = _record()
        connection.cursor_instance.fetchone_results.extend(
            [
                {"version": 4},
                {
                    "task_id": record.state.task_id,
                    "status": "succeeded",
                    "lease_expires_at": datetime.now(timezone.utc),
                },
            ]
        )

        with self.assertRaises(TaskExecutionAlreadyFinishedError):
            _repository(connection).acquire_execution(
                record.state.task_id,
                execution_id="execution-1",
                owner_id="worker-1",
                action="analyze_requirement",
                lease_seconds=60,
                expected_version=4,
            )
        self.assertEqual(connection.rollbacks, 1)

    def test_acquire_rejects_unexpired_active_lease(self):
        connection = _FakeConnection()
        record = _record()
        connection.cursor_instance.fetchone_results.extend(
            [
                {"version": 2},
                None,
                {
                    "execution_id": "other-execution",
                    "lease_expires_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=5)
                    ),
                },
            ]
        )

        with self.assertRaises(TaskExecutionBusyError):
            _repository(connection).acquire_execution(
                record.state.task_id,
                execution_id="execution-2",
                owner_id="worker-2",
                action="analyze_requirement",
                lease_seconds=60,
                expected_version=2,
            )
        self.assertEqual(connection.rollbacks, 1)

    def test_list_restores_records_in_database_order(self):
        connection = _FakeConnection()
        first = _record("第一个需求")
        second = _record("第二个需求")
        connection.cursor_instance.fetchall_result = [
            {"snapshot_json": TaskSnapshotSerializer.to_json(second)},
            {"snapshot_json": TaskSnapshotSerializer.to_dict(first)},
        ]

        records = _repository(connection).list()

        self.assertEqual(
            [record.state.task_id for record in records],
            [second.state.task_id, first.state.task_id],
        )

    def test_list_summaries_queries_small_columns_and_returns_page(self):
        connection = _FakeConnection()
        cursor = connection.cursor_instance
        now = datetime(2026, 8, 11, tzinfo=timezone.utc)
        cursor.fetchone_results = [{"total": 1}]
        cursor.fetchall_result = [{
            "task_id": "task-1",
            "task_name": "订单履约需求",
            "status": "completed",
            "current_step": "finalize",
            "requirement_summary": "订单分析",
            "event_count": 9,
            "version": 2,
            "created_at": now,
            "updated_at": now,
        }]

        page = _repository(connection).list_summaries(
            query="订单", offset=0, limit=10,
        )

        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].task_id, "task-1")
        self.assertEqual(page.items[0].task_name, "订单履约需求")
        statements = [sql for sql, _ in cursor.executed]
        self.assertTrue(all("snapshot_json" not in sql for sql in statements))
        self.assertIn("ORDER BY updated_at DESC", statements[-1])

    def test_delete_commits_and_unknown_task_rolls_back(self):
        connection = _FakeConnection()
        repository = _repository(connection)

        repository.delete("task-1")
        self.assertEqual(connection.commits, 1)

        missing_connection = _FakeConnection()
        missing_connection.cursor_instance.rowcount = 0
        with self.assertRaises(TaskNotFoundError):
            _repository(missing_connection).delete("missing")
        self.assertEqual(missing_connection.rollbacks, 1)


class MySQLConfigurationTests(unittest.TestCase):
    def test_settings_require_complete_configuration(self):
        environment = {
            "MYSQL_HOST": "db.example.test",
            "MYSQL_PORT": "3307",
            "MYSQL_USER": "agent",
            "MYSQL_PASSWORD": "secret",
            "MYSQL_DATABASE": "assistant",
            "MYSQL_CONNECT_TIMEOUT": "8",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = MySQLSettings.from_env()

        self.assertEqual(settings.host, "db.example.test")
        self.assertEqual(settings.port, 3307)
        self.assertEqual(settings.connect_timeout, 8)

    def test_settings_reject_missing_password(self):
        environment = {
            "MYSQL_HOST": "db.example.test",
            "MYSQL_USER": "agent",
            "MYSQL_DATABASE": "assistant",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "MYSQL_PASSWORD"):
                MySQLSettings.from_env()

    def test_bootstrap_keeps_memory_as_default(self):
        with patch("application.bootstrap.load_dotenv"), patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            repository = build_task_repository()

        self.assertIsInstance(repository, InMemoryTaskRepository)

    def test_bootstrap_rejects_unknown_backend(self):
        with patch("application.bootstrap.load_dotenv"), patch.dict(
            os.environ,
            {"TASK_REPOSITORY_BACKEND": "unknown"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "memory.*mysql"):
                build_task_repository()

    @patch("application.bootstrap.MySQLTaskRepository")
    @patch("application.bootstrap.build_mysql_connection_factory")
    @patch("application.bootstrap.MySQLSettings.from_env")
    def test_bootstrap_builds_and_initializes_mysql_repository(
        self,
        settings_from_env,
        build_connection_factory,
        repository_type,
    ):
        settings = MagicMock()
        connection_factory = MagicMock()
        repository = MagicMock()
        settings_from_env.return_value = settings
        build_connection_factory.return_value = connection_factory
        repository_type.return_value = repository

        with patch("application.bootstrap.load_dotenv"), patch.dict(
            os.environ,
            {"TASK_REPOSITORY_BACKEND": "mysql"},
            clear=True,
        ):
            result = build_task_repository()

        repository_type.assert_called_once_with(
            connection_factory,
            TaskSnapshotSerializer,
        )
        repository.initialize_schema.assert_called_once_with()
        self.assertIs(result, repository)


if __name__ == "__main__":
    unittest.main()
