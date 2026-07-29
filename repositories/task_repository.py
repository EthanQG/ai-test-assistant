from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from threading import RLock
from typing import TYPE_CHECKING

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


class TaskRepository(ABC):
    @abstractmethod
    def create(self, record: TaskRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, task_id: str) -> TaskRecord:
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        record: TaskRecord,
        expected_version: int | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[TaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, task_id: str) -> None:
        raise NotImplementedError


class InMemoryTaskRepository(TaskRepository):
    """Session-scoped in-memory repository returning isolated copies."""

    def __init__(self):
        self._records: dict[str, TaskRecord] = {}
        self._lock = RLock()

    def create(self, record: TaskRecord) -> None:
        task_id = record.state.task_id
        with self._lock:
            if task_id in self._records:
                raise TaskAlreadyExistsError(task_id)
            self._records[task_id] = deepcopy(record)

    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            if task_id not in self._records:
                raise TaskNotFoundError(task_id)
            return deepcopy(self._records[task_id])

    def save(
        self,
        record: TaskRecord,
        expected_version: int | None = None,
    ) -> None:
        del expected_version
        task_id = record.state.task_id
        with self._lock:
            if task_id not in self._records:
                raise TaskNotFoundError(task_id)
            self._records[task_id] = deepcopy(record)

    def list(self) -> list[TaskRecord]:
        with self._lock:
            return [
                deepcopy(record)
                for record in self._records.values()
            ]

    def delete(self, task_id: str) -> None:
        with self._lock:
            if task_id not in self._records:
                raise TaskNotFoundError(task_id)
            self._records.pop(task_id)
