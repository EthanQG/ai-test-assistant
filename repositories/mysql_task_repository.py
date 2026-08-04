from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Protocol

from .task_repository import (
    TaskAlreadyExistsError,
    TaskNotFoundError,
    TaskRepository,
    TaskRepositoryError,
)

if TYPE_CHECKING:
    from application.models import TaskRecord


class TaskSnapshotCodec(Protocol):
    @classmethod
    def to_dict(cls, record: TaskRecord) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord: ...

    @classmethod
    def from_json(cls, payload: str) -> TaskRecord: ...


CREATE_TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id VARCHAR(36) NOT NULL PRIMARY KEY,
    schema_version SMALLINT UNSIGNED NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_step VARCHAR(64) NOT NULL,
    requirement_summary VARCHAR(512) NOT NULL DEFAULT '',
    snapshot_json JSON NOT NULL,
    event_count INT UNSIGNED NOT NULL DEFAULT 0,
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_agent_tasks_status_updated (status, updated_at),
    INDEX idx_agent_tasks_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()


CREATE_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_task_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    sequence_no INT UNSIGNED NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    step VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    data_json JSON NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_agent_task_events_sequence (task_id, sequence_no),
    INDEX idx_agent_task_events_occurred (task_id, occurred_at),
    CONSTRAINT fk_agent_task_events_task
        FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()


@dataclass(frozen=True)
class MySQLSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "MySQLSettings":
        required = {
            "MYSQL_HOST": os.getenv("MYSQL_HOST", "").strip(),
            "MYSQL_USER": os.getenv("MYSQL_USER", "").strip(),
            "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
            "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "missing MySQL configuration: " + ", ".join(missing)
            )
        return cls(
            host=required["MYSQL_HOST"],
            port=_positive_int_env("MYSQL_PORT", 3306),
            user=required["MYSQL_USER"],
            password=required["MYSQL_PASSWORD"],
            database=required["MYSQL_DATABASE"],
            connect_timeout=_positive_int_env(
                "MYSQL_CONNECT_TIMEOUT",
                10,
            ),
        )


def build_mysql_connection_factory(
    settings: MySQLSettings,
) -> Callable[[], Any]:
    """Build a lazy PyMySQL connection factory without opening a socket."""

    def connect() -> Any:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise TaskRepositoryError(
                "PyMySQL is required when TASK_REPOSITORY_BACKEND=mysql"
            ) from exc
        return pymysql.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=settings.connect_timeout,
        )

    return connect


class MySQLTaskRepository(TaskRepository):
    """Persists a schema-versioned task snapshot and append-only events."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        snapshot_codec: type[TaskSnapshotCodec],
    ):
        self._connection_factory = connection_factory
        self._snapshot_codec = snapshot_codec

    def initialize_schema(self) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(CREATE_TASKS_TABLE_SQL)
            cursor.execute(CREATE_EVENTS_TABLE_SQL)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise TaskRepositoryError(
                "failed to initialize MySQL task schema"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def create(self, record: TaskRecord) -> None:
        snapshot = self._snapshot_codec.to_dict(record)
        task_id = record.state.task_id
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO agent_tasks (
                    task_id, schema_version, status, current_step,
                    requirement_summary, snapshot_json, event_count,
                    version, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
                """,
                self._task_values(record, snapshot),
            )
            self._insert_events(cursor, task_id, snapshot, 0)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if _mysql_error_code(exc) == 1062:
                raise TaskAlreadyExistsError(task_id) from exc
            if isinstance(exc, TaskRepositoryError):
                raise
            raise TaskRepositoryError("failed to create MySQL task") from exc
        finally:
            cursor.close()
            connection.close()

    def get(self, task_id: str) -> TaskRecord:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT snapshot_json FROM agent_tasks WHERE task_id = %s",
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            return self._record_from_snapshot(row["snapshot_json"])
        except TaskNotFoundError:
            raise
        except Exception as exc:
            raise TaskRepositoryError("failed to read MySQL task") from exc
        finally:
            cursor.close()
            connection.close()

    def save(
        self,
        record: TaskRecord,
        expected_version: int | None = None,
    ) -> None:
        # Version conflict detection is intentionally deferred to stage 2.13.4.
        del expected_version
        snapshot = self._snapshot_codec.to_dict(record)
        task_id = record.state.task_id
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT event_count
                FROM agent_tasks
                WHERE task_id = %s
                FOR UPDATE
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            stored_event_count = int(row["event_count"])
            current_event_count = len(snapshot["state"]["events"])
            if current_event_count < stored_event_count:
                raise TaskRepositoryError(
                    "task event history cannot shrink during save"
                )

            cursor.execute(
                """
                UPDATE agent_tasks
                SET schema_version = %s,
                    status = %s,
                    current_step = %s,
                    requirement_summary = %s,
                    snapshot_json = %s,
                    event_count = %s,
                    version = version + 1,
                    updated_at = %s
                WHERE task_id = %s
                """,
                (
                    int(snapshot["schema_version"]),
                    record.state.status.value,
                    record.state.current_step.value,
                    record.state.requirement_summary[:512],
                    _json_text(snapshot),
                    current_event_count,
                    _mysql_datetime(record.state.updated_at),
                    task_id,
                ),
            )
            self._insert_events(
                cursor,
                task_id,
                snapshot,
                stored_event_count,
            )
            connection.commit()
        except TaskNotFoundError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            if isinstance(exc, TaskRepositoryError):
                raise
            raise TaskRepositoryError("failed to save MySQL task") from exc
        finally:
            cursor.close()
            connection.close()

    def list(self) -> list[TaskRecord]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT snapshot_json
                FROM agent_tasks
                ORDER BY updated_at DESC, task_id ASC
                """
            )
            return [
                self._record_from_snapshot(row["snapshot_json"])
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            raise TaskRepositoryError("failed to list MySQL tasks") from exc
        finally:
            cursor.close()
            connection.close()

    def delete(self, task_id: str) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "DELETE FROM agent_tasks WHERE task_id = %s",
                (task_id,),
            )
            if cursor.rowcount == 0:
                raise TaskNotFoundError(task_id)
            connection.commit()
        except TaskNotFoundError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise TaskRepositoryError("failed to delete MySQL task") from exc
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _task_values(
        record: TaskRecord,
        snapshot: dict[str, Any],
    ) -> tuple[Any, ...]:
        return (
            record.state.task_id,
            int(snapshot["schema_version"]),
            record.state.status.value,
            record.state.current_step.value,
            record.state.requirement_summary[:512],
            _json_text(snapshot),
            len(snapshot["state"]["events"]),
            _mysql_datetime(record.state.created_at),
            _mysql_datetime(record.state.updated_at),
        )

    @staticmethod
    def _insert_events(
        cursor: Any,
        task_id: str,
        snapshot: dict[str, Any],
        start_index: int,
    ) -> None:
        events = snapshot["state"]["events"]
        for index, event in enumerate(
            events[start_index:],
            start=start_index + 1,
        ):
            cursor.execute(
                """
                INSERT INTO agent_task_events (
                    task_id, sequence_no, event_type, step,
                    message, data_json, occurred_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    task_id,
                    index,
                    event["event_type"],
                    event["step"],
                    event["message"],
                    _json_text(event["data"]),
                    _mysql_datetime_text(event["occurred_at"]),
                ),
            )

    def _record_from_snapshot(self, value: Any) -> TaskRecord:
        if isinstance(value, dict):
            return self._snapshot_codec.from_dict(value)
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            raise TaskRepositoryError(
                "MySQL snapshot_json must be an object or JSON text"
            )
        return self._snapshot_codec.from_json(value)


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _mysql_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TaskRepositoryError("persisted datetime must include timezone")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _mysql_datetime_text(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise TaskRepositoryError("event datetime is invalid") from exc
    return _mysql_datetime(parsed)


def _mysql_error_code(exc: Exception) -> int | None:
    if not exc.args:
        return None
    return exc.args[0] if isinstance(exc.args[0], int) else None


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
