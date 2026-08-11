from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from application.models import TaskRecord


class TaskRepositoryError(RuntimeError):
    """Base error for task persistence operations."""


class TaskNotFoundError(TaskRepositoryError):
    def __init__(self, task_id: str):
        super().__init__(f"task not found: {task_id}")
        self.task_id = task_id


class TaskAlreadyExistsError(TaskRepositoryError):
    def __init__(self, task_id: str):
        super().__init__(f"task already exists: {task_id}")
        self.task_id = task_id


class TaskVersionConflictError(TaskRepositoryError):
    def __init__(self, task_id: str, expected: int, actual: int):
        super().__init__(
            f"task version conflict: {task_id}, "
            f"expected {expected}, actual {actual}"
        )
        self.task_id = task_id
        self.expected = expected
        self.actual = actual


class TaskExecutionBusyError(TaskRepositoryError):
    def __init__(self, task_id: str):
        super().__init__(f"task execution lease is active: {task_id}")
        self.task_id = task_id


class TaskExecutionAlreadyFinishedError(TaskRepositoryError):
    def __init__(self, task_id: str, execution_id: str):
        super().__init__(
            f"task execution already finished: {task_id}, {execution_id}"
        )
        self.task_id = task_id
        self.execution_id = execution_id


class TaskExecutionLeaseLostError(TaskRepositoryError):
    def __init__(self, task_id: str, execution_id: str):
        super().__init__(
            f"task execution lease lost: {task_id}, {execution_id}"
        )
        self.task_id = task_id
        self.execution_id = execution_id


@dataclass(frozen=True)
class VersionedTaskRecord:
    record: TaskRecord
    version: int


@dataclass(frozen=True)
class TaskSummary:
    task_id: str
    status: str
    current_step: str
    requirement_summary: str
    event_count: int
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TaskSummaryPage:
    items: tuple[TaskSummary, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class TaskExecutionLease:
    task_id: str
    execution_id: str
    owner_id: str
    action: str
    version: int
    expires_at: datetime


@dataclass
class _InMemoryExecution:
    task_id: str
    execution_id: str
    owner_id: str
    action: str
    status: str
    expires_at: datetime


class TaskRepository(ABC):
    @abstractmethod
    def create(self, record: TaskRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, task_id: str) -> TaskRecord:
        raise NotImplementedError

    @abstractmethod
    def get_versioned(self, task_id: str) -> VersionedTaskRecord:
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        record: TaskRecord,
        expected_version: int | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def complete_execution(
        self,
        record: TaskRecord,
        lease: TaskExecutionLease,
        *,
        succeeded: bool,
        error_type: str | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[TaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_summaries(
        self,
        *,
        query: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> TaskSummaryPage:
        raise NotImplementedError

    @abstractmethod
    def delete(self, task_id: str) -> None:
        raise NotImplementedError


class InMemoryTaskRepository(TaskRepository):
    """Session-scoped repository with optimistic locking and leases."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._records: dict[str, TaskRecord] = {}
        self._versions: dict[str, int] = {}
        self._executions: dict[str, _InMemoryExecution] = {}
        self._lock = RLock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, record: TaskRecord) -> None:
        task_id = record.state.task_id
        with self._lock:
            if task_id in self._records:
                raise TaskAlreadyExistsError(task_id)
            self._records[task_id] = deepcopy(record)
            self._versions[task_id] = 1

    def get(self, task_id: str) -> TaskRecord:
        return self.get_versioned(task_id).record

    def get_versioned(self, task_id: str) -> VersionedTaskRecord:
        with self._lock:
            self._require_task(task_id)
            return VersionedTaskRecord(
                deepcopy(self._records[task_id]),
                self._versions[task_id],
            )

    def save(
        self,
        record: TaskRecord,
        expected_version: int | None = None,
    ) -> int:
        task_id = record.state.task_id
        with self._lock:
            self._require_task(task_id)
            self._check_version(task_id, expected_version)
            self._records[task_id] = deepcopy(record)
            self._versions[task_id] += 1
            return self._versions[task_id]

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
        with self._lock:
            self._require_task(task_id)
            self._check_version(task_id, expected_version)
            now = self._aware_now()
            existing = self._executions.get(execution_id)
            if existing is not None:
                if existing.task_id != task_id:
                    raise TaskRepositoryError(
                        "execution_id belongs to another task"
                    )
                if existing.status != "running":
                    raise TaskExecutionAlreadyFinishedError(
                        task_id,
                        execution_id,
                    )
                if existing.expires_at > now:
                    raise TaskExecutionBusyError(task_id)

            for execution in self._executions.values():
                if (
                    execution.task_id == task_id
                    and execution.status == "running"
                ):
                    if execution.expires_at > now:
                        raise TaskExecutionBusyError(task_id)
                    execution.status = "expired"

            expires_at = now + timedelta(seconds=lease_seconds)
            self._executions[execution_id] = _InMemoryExecution(
                task_id=task_id,
                execution_id=execution_id,
                owner_id=owner_id,
                action=action,
                status="running",
                expires_at=expires_at,
            )
            self._versions[task_id] += 1
            return TaskExecutionLease(
                task_id=task_id,
                execution_id=execution_id,
                owner_id=owner_id,
                action=action,
                version=self._versions[task_id],
                expires_at=expires_at,
            )

    def complete_execution(
        self,
        record: TaskRecord,
        lease: TaskExecutionLease,
        *,
        succeeded: bool,
        error_type: str | None = None,
    ) -> int:
        del error_type
        task_id = record.state.task_id
        with self._lock:
            self._require_task(task_id)
            self._check_version(task_id, lease.version)
            execution = self._executions.get(lease.execution_id)
            if (
                execution is None
                or execution.task_id != task_id
                or execution.owner_id != lease.owner_id
                or execution.status != "running"
                or execution.expires_at <= self._aware_now()
            ):
                raise TaskExecutionLeaseLostError(
                    task_id,
                    lease.execution_id,
                )
            execution.status = "succeeded" if succeeded else "failed"
            self._records[task_id] = deepcopy(record)
            self._versions[task_id] += 1
            return self._versions[task_id]

    def list(self) -> list[TaskRecord]:
        with self._lock:
            return [deepcopy(record) for record in self._records.values()]

    def list_summaries(
        self,
        *,
        query: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> TaskSummaryPage:
        _validate_summary_page(offset, limit)
        normalized = query.strip().casefold()
        with self._lock:
            items = [
                TaskSummary(
                    task_id=record.state.task_id,
                    status=record.state.status.value,
                    current_step=record.state.current_step.value,
                    requirement_summary=record.state.requirement_summary,
                    event_count=len(record.state.events),
                    version=self._versions[record.state.task_id],
                    created_at=record.state.created_at,
                    updated_at=record.state.updated_at,
                )
                for record in self._records.values()
                if not normalized or normalized in (
                    record.state.requirement_summary
                    or record.state.requirement
                    or record.state.task_id
                ).casefold()
            ]
        items.sort(key=lambda item: (item.updated_at, item.task_id), reverse=True)
        return TaskSummaryPage(
            items=tuple(items[offset:offset + limit]),
            total=len(items),
            offset=offset,
            limit=limit,
        )

    def delete(self, task_id: str) -> None:
        with self._lock:
            self._require_task(task_id)
            self._records.pop(task_id)
            self._versions.pop(task_id)
            self._executions = {
                execution_id: execution
                for execution_id, execution in self._executions.items()
                if execution.task_id != task_id
            }

    def _require_task(self, task_id: str) -> None:
        if task_id not in self._records:
            raise TaskNotFoundError(task_id)

    def _check_version(
        self,
        task_id: str,
        expected_version: int | None,
    ) -> None:
        actual = self._versions[task_id]
        if expected_version is not None and expected_version != actual:
            raise TaskVersionConflictError(
                task_id,
                expected_version,
                actual,
            )

    def _aware_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise TaskRepositoryError("repository clock must include timezone")
        return now.astimezone(timezone.utc)


def _validate_summary_page(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("offset cannot be negative")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
