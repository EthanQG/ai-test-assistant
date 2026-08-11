from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Callable, Protocol

from utils.task_naming import derive_task_name

from .task_repository import (
    TaskExecutionAlreadyFinishedError,
    TaskExecutionBusyError,
    TaskExecutionLease,
    TaskExecutionLeaseLostError,
    TaskAlreadyExistsError,
    TaskNotFoundError,
    TaskRepository,
    TaskRepositoryError,
    TaskSummary,
    TaskSummaryPage,
    TaskVersionConflictError,
    VersionedTaskRecord,
    _validate_task_name,
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
    task_name VARCHAR(160) NOT NULL DEFAULT '',
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


CREATE_EXECUTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_task_executions (
    execution_id VARCHAR(36) NOT NULL PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    action VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    lease_owner VARCHAR(64) NOT NULL,
    lease_expires_at DATETIME(6) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6) NULL,
    error_type VARCHAR(128) NULL,
    INDEX idx_agent_task_executions_active (
        task_id, status, lease_expires_at
    ),
    CONSTRAINT fk_agent_task_executions_task
        FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()


ADD_TASK_NAME_COLUMN_SQL = """
ALTER TABLE agent_tasks
ADD COLUMN task_name VARCHAR(160) NOT NULL DEFAULT ''
AFTER current_step
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
            cursor.execute(CREATE_EXECUTIONS_TABLE_SQL)
            cursor.execute("SHOW COLUMNS FROM agent_tasks LIKE 'task_name'")
            if cursor.fetchone() is None:
                cursor.execute(ADD_TASK_NAME_COLUMN_SQL)
            cursor.execute(
                "UPDATE agent_tasks SET task_name = "
                "LEFT(requirement_summary, 160) WHERE task_name = ''"
            )
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
                    task_name, requirement_summary, snapshot_json,
                    event_count, version, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
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
        return self.get_versioned(task_id).record

    def get_versioned(self, task_id: str) -> VersionedTaskRecord:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT snapshot_json, version
                FROM agent_tasks
                WHERE task_id = %s
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            return VersionedTaskRecord(
                record=self._record_from_snapshot(row["snapshot_json"]),
                version=int(row["version"]),
            )
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
    ) -> int:
        snapshot = self._snapshot_codec.to_dict(record)
        task_id = record.state.task_id
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT event_count, version
                FROM agent_tasks
                WHERE task_id = %s
                FOR UPDATE
                """,
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            stored_version = int(row["version"])
            if (
                expected_version is not None
                and expected_version != stored_version
            ):
                raise TaskVersionConflictError(
                    task_id,
                    expected_version,
                    stored_version,
                )
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
                WHERE task_id = %s AND version = %s
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
                    stored_version,
                ),
            )
            if cursor.rowcount != 1:
                raise TaskVersionConflictError(
                    task_id,
                    stored_version,
                    stored_version + 1,
                )
            self._insert_events(
                cursor,
                task_id,
                snapshot,
                stored_event_count,
            )
            connection.commit()
            return stored_version + 1
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

    def acquire_execution(
        self,
        task_id: str,
        *,
        execution_id: str,
        owner_id: str,
        action: str,
        lease_seconds: int,
        expected_version: int,
    ) -> TaskExecutionLease:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=lease_seconds)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT version
                FROM agent_tasks
                WHERE task_id = %s
                FOR UPDATE
                """,
                (task_id,),
            )
            task_row = cursor.fetchone()
            if task_row is None:
                raise TaskNotFoundError(task_id)
            stored_version = int(task_row["version"])
            if stored_version != expected_version:
                raise TaskVersionConflictError(
                    task_id,
                    expected_version,
                    stored_version,
                )

            cursor.execute(
                """
                SELECT task_id, status, lease_expires_at
                FROM agent_task_executions
                WHERE execution_id = %s
                FOR UPDATE
                """,
                (execution_id,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                if existing["task_id"] != task_id:
                    raise TaskRepositoryError(
                        "execution_id belongs to another task"
                    )
                if existing["status"] != "running":
                    raise TaskExecutionAlreadyFinishedError(
                        task_id,
                        execution_id,
                    )
                if _aware_mysql_datetime(
                    existing["lease_expires_at"]
                ) > now:
                    raise TaskExecutionBusyError(task_id)

            cursor.execute(
                """
                SELECT execution_id, lease_expires_at
                FROM agent_task_executions
                WHERE task_id = %s AND status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
                FOR UPDATE
                """,
                (task_id,),
            )
            active = cursor.fetchone()
            if active is not None:
                if _aware_mysql_datetime(active["lease_expires_at"]) > now:
                    raise TaskExecutionBusyError(task_id)
                cursor.execute(
                    """
                    UPDATE agent_task_executions
                    SET status = 'expired', finished_at = %s
                    WHERE execution_id = %s AND status = 'running'
                    """,
                    (_mysql_datetime(now), active["execution_id"]),
                )

            if existing is None:
                cursor.execute(
                    """
                    INSERT INTO agent_task_executions (
                        execution_id, task_id, action, status,
                        lease_owner, lease_expires_at, started_at
                    ) VALUES (%s, %s, %s, 'running', %s, %s, %s)
                    """,
                    (
                        execution_id,
                        task_id,
                        action,
                        owner_id,
                        _mysql_datetime(expires_at),
                        _mysql_datetime(now),
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE agent_task_executions
                    SET action = %s, status = 'running',
                        lease_owner = %s, lease_expires_at = %s,
                        started_at = %s, finished_at = NULL,
                        error_type = NULL
                    WHERE execution_id = %s
                    """,
                    (
                        action,
                        owner_id,
                        _mysql_datetime(expires_at),
                        _mysql_datetime(now),
                        execution_id,
                    ),
                )

            cursor.execute(
                """
                UPDATE agent_tasks
                SET version = version + 1, updated_at = %s
                WHERE task_id = %s AND version = %s
                """,
                (_mysql_datetime(now), task_id, stored_version),
            )
            if cursor.rowcount != 1:
                raise TaskVersionConflictError(
                    task_id,
                    stored_version,
                    stored_version + 1,
                )
            connection.commit()
            return TaskExecutionLease(
                task_id=task_id,
                execution_id=execution_id,
                owner_id=owner_id,
                action=action,
                version=stored_version + 1,
                expires_at=expires_at,
            )
        except (
            TaskNotFoundError,
            TaskRepositoryError,
        ):
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise TaskRepositoryError(
                "failed to acquire MySQL execution lease"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def complete_execution(
        self,
        record: TaskRecord,
        lease: TaskExecutionLease,
        *,
        succeeded: bool,
        error_type: str | None = None,
    ) -> int:
        snapshot = self._snapshot_codec.to_dict(record)
        task_id = record.state.task_id
        now = datetime.now(timezone.utc)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT event_count, version
                FROM agent_tasks
                WHERE task_id = %s
                FOR UPDATE
                """,
                (task_id,),
            )
            task_row = cursor.fetchone()
            if task_row is None:
                raise TaskNotFoundError(task_id)
            stored_version = int(task_row["version"])
            if stored_version != lease.version:
                raise TaskVersionConflictError(
                    task_id,
                    lease.version,
                    stored_version,
                )

            cursor.execute(
                """
                SELECT task_id, status, lease_owner, lease_expires_at
                FROM agent_task_executions
                WHERE execution_id = %s
                FOR UPDATE
                """,
                (lease.execution_id,),
            )
            execution = cursor.fetchone()
            if (
                execution is None
                or execution["task_id"] != task_id
                or execution["status"] != "running"
                or execution["lease_owner"] != lease.owner_id
                or _aware_mysql_datetime(
                    execution["lease_expires_at"]
                ) <= now
            ):
                raise TaskExecutionLeaseLostError(
                    task_id,
                    lease.execution_id,
                )

            stored_event_count = int(task_row["event_count"])
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
                WHERE task_id = %s AND version = %s
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
                    stored_version,
                ),
            )
            if cursor.rowcount != 1:
                raise TaskVersionConflictError(
                    task_id,
                    stored_version,
                    stored_version + 1,
                )
            self._insert_events(
                cursor,
                task_id,
                snapshot,
                stored_event_count,
            )
            cursor.execute(
                """
                UPDATE agent_task_executions
                SET status = %s, finished_at = %s, error_type = %s
                WHERE execution_id = %s
                  AND status = 'running'
                  AND lease_owner = %s
                """,
                (
                    "succeeded" if succeeded else "failed",
                    _mysql_datetime(now),
                    error_type,
                    lease.execution_id,
                    lease.owner_id,
                ),
            )
            if cursor.rowcount != 1:
                raise TaskExecutionLeaseLostError(
                    task_id,
                    lease.execution_id,
                )
            connection.commit()
            return stored_version + 1
        except (
            TaskNotFoundError,
            TaskRepositoryError,
        ):
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise TaskRepositoryError(
                "failed to complete MySQL execution"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def list(self) -> list[TaskRecord]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            # Legacy full-list API keeps compatibility without asking MySQL to
            # sort large JSON snapshots. New UIs should use list_summaries().
            cursor.execute("SELECT snapshot_json FROM agent_tasks")
            return [
                self._record_from_snapshot(row["snapshot_json"])
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            raise TaskRepositoryError("failed to list MySQL tasks") from exc
        finally:
            cursor.close()
            connection.close()

    def list_summaries(
        self,
        *,
        query: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> TaskSummaryPage:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid task summary page")
        normalized = query.strip()
        where = ""
        params: list[Any] = []
        if normalized:
            where = (
                "WHERE task_name LIKE %s OR requirement_summary LIKE %s "
                "OR task_id LIKE %s"
            )
            pattern = f"%{normalized}%"
            params.extend((pattern, pattern, pattern))
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) AS total FROM agent_tasks {where}", params)
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                SELECT task_id, task_name, status, current_step,
                       requirement_summary,
                       event_count, version, created_at, updated_at
                FROM agent_tasks
                {where}
                ORDER BY updated_at DESC, task_id ASC
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )
            items = tuple(
                TaskSummary(
                    **{
                        **row,
                        "task_name": derive_task_name(
                            str(row.get("task_name") or ""),
                            str(row.get("requirement_summary") or ""),
                        ),
                    }
                )
                for row in cursor.fetchall()
            )
            return TaskSummaryPage(items, total, offset, limit)
        except Exception as exc:
            raise TaskRepositoryError("failed to list MySQL task summaries") from exc
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

    def rename(self, task_id: str, task_name: str) -> None:
        cleaned = _validate_task_name(task_name)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE agent_tasks
                SET task_name = %s,
                    version = version + 1,
                    updated_at = UTC_TIMESTAMP(6)
                WHERE task_id = %s
                """,
                (cleaned, task_id),
            )
            if cursor.rowcount == 0:
                raise TaskNotFoundError(task_id)
            connection.commit()
        except TaskNotFoundError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise TaskRepositoryError("failed to rename MySQL task") from exc
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
            derive_task_name(
                record.state.requirement,
                record.state.requirement_summary,
                max_length=160,
            ),
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


def _aware_mysql_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise TaskRepositoryError(
                "MySQL lease datetime is invalid"
            ) from exc
    if not isinstance(value, datetime):
        raise TaskRepositoryError("MySQL lease datetime is invalid")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
