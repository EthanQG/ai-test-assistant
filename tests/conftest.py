from __future__ import annotations

from collections.abc import Callable

import pytest

from agent import TestAnalysisState
from application import TaskRecord
from repositories import InMemoryTaskRepository


@pytest.fixture
def in_memory_task_repository() -> InMemoryTaskRepository:
    """Return a fresh repository so tests never share task state."""

    return InMemoryTaskRepository()


@pytest.fixture
def task_record_factory() -> Callable[[str], TaskRecord]:
    """Build independent TaskRecords without copying setup boilerplate."""

    def build(requirement: str = "用户提交订单") -> TaskRecord:
        return TaskRecord(state=TestAnalysisState(requirement))

    return build


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Classify tests by their physical layer without editing every test."""

    for item in items:
        path_parts = set(item.path.parts)
        if "integration" in path_parts:
            item.add_marker(pytest.mark.integration)
        elif "app" in path_parts:
            item.add_marker(pytest.mark.app)
        else:
            item.add_marker(pytest.mark.unit)
