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
    """Classify existing unittest and pytest tests without editing every file."""

    for item in items:
        path = item.path.name
        if path == "test_mysql_task_repository_integration.py":
            item.add_marker(pytest.mark.integration)
        elif path == "test_streamlit_agent_page.py":
            item.add_marker(pytest.mark.app)
        else:
            item.add_marker(pytest.mark.unit)
