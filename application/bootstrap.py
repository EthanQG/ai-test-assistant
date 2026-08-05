import os

from dotenv import load_dotenv

from repositories import (
    InMemoryKnowledgeAssetRepository,
    InMemoryTaskRepository,
    KnowledgeAssetRepository,
    MySQLSettings,
    MySQLKnowledgeAssetRepository,
    MySQLTaskRepository,
    TaskRepository,
    build_mysql_connection_factory,
)

from knowledge_assets import KnowledgeAssetSnapshotSerializer

from .knowledge_asset_service import KnowledgeAssetApplicationService
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


def build_knowledge_asset_repository() -> KnowledgeAssetRepository:
    """Build the configured authoritative KnowledgeAsset repository."""

    load_dotenv()
    backend = os.getenv(
        "KNOWLEDGE_ASSET_REPOSITORY_BACKEND",
        "memory",
    ).strip().lower()
    if backend == "memory":
        return InMemoryKnowledgeAssetRepository()
    if backend == "mysql":
        repository = MySQLKnowledgeAssetRepository(
            build_mysql_connection_factory(MySQLSettings.from_env()),
            KnowledgeAssetSnapshotSerializer,
        )
        repository.initialize_schema()
        return repository
    raise ValueError(
        "KNOWLEDGE_ASSET_REPOSITORY_BACKEND must be either "
        "'memory' or 'mysql'"
    )


def build_knowledge_asset_application_service(
    task_repository: TaskRepository,
) -> KnowledgeAssetApplicationService:
    """Compose asset publishing with the caller's existing task store."""

    return KnowledgeAssetApplicationService(
        task_repository,
        build_knowledge_asset_repository(),
    )
