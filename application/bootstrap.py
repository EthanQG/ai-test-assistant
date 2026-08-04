import os

from dotenv import load_dotenv

from repositories import (
    InMemoryTaskRepository,
    MySQLSettings,
    MySQLTaskRepository,
    TaskRepository,
    build_mysql_connection_factory,
)

from .service import TestAnalysisApplicationService
from .snapshots import TaskSnapshotSerializer


def build_session_application_service() -> TestAnalysisApplicationService:
    """Build configured persistence and application dependencies."""
    return TestAnalysisApplicationService(build_task_repository())


def build_task_repository() -> TaskRepository:
    load_dotenv()
    backend = os.getenv("TASK_REPOSITORY_BACKEND", "memory").strip().lower()
    if backend == "memory":
        return InMemoryTaskRepository()
    if backend == "mysql":
        repository = MySQLTaskRepository(
            build_mysql_connection_factory(MySQLSettings.from_env()),
            TaskSnapshotSerializer,
        )
        repository.initialize_schema()
        return repository
    raise ValueError(
        "TASK_REPOSITORY_BACKEND must be either 'memory' or 'mysql'"
    )
