import os
from dataclasses import dataclass

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
from services.embedding_service import (
    OllamaBatchEmbeddingService,
    OllamaEmbeddingSettings,
)
from services.milvus_asset_index import (
    MilvusAssetIndexSettings,
    MilvusKnowledgeAssetIndex,
)

from .knowledge_asset_indexing_service import KnowledgeAssetIndexingService
from .knowledge_asset_retrieval_service import KnowledgeAssetRetrievalService
from .knowledge_asset_service import KnowledgeAssetApplicationService
from .service import TestAnalysisApplicationService
from .snapshots import TaskSnapshotSerializer


@dataclass(frozen=True)
class ApplicationServices:
    task_service: TestAnalysisApplicationService
    knowledge_asset_service: KnowledgeAssetApplicationService
    knowledge_indexing_service: KnowledgeAssetIndexingService


def build_application_services() -> ApplicationServices:
    """Build API services with shared task and knowledge repositories."""

    task_repository = build_task_repository()
    asset_repository = build_knowledge_asset_repository()
    return ApplicationServices(
        task_service=TestAnalysisApplicationService(task_repository),
        knowledge_asset_service=KnowledgeAssetApplicationService(
            task_repository,
            asset_repository,
        ),
        knowledge_indexing_service=build_knowledge_asset_indexing_service(
            asset_repository
        ),
    )


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


def build_knowledge_asset_indexing_service(
    asset_repository: KnowledgeAssetRepository,
) -> KnowledgeAssetIndexingService:
    """Compose the explicit KnowledgeAsset indexing use case."""

    load_dotenv()
    return KnowledgeAssetIndexingService(
        asset_repository,
        OllamaBatchEmbeddingService(OllamaEmbeddingSettings.from_env()),
        MilvusKnowledgeAssetIndex(MilvusAssetIndexSettings.from_env()),
    )


def build_knowledge_asset_retrieval_service(
    asset_repository: KnowledgeAssetRepository,
) -> KnowledgeAssetRetrievalService:
    """Compose bounded V2 recall and authoritative asset verification."""

    load_dotenv()
    return KnowledgeAssetRetrievalService(
        asset_repository,
        OllamaBatchEmbeddingService(OllamaEmbeddingSettings.from_env()),
        MilvusKnowledgeAssetIndex(MilvusAssetIndexSettings.from_env()),
        top_k=int(os.getenv("KNOWLEDGE_RETRIEVAL_TOP_K", "3")),
        raw_limit=int(os.getenv("KNOWLEDGE_RETRIEVAL_RAW_LIMIT", "20")),
        min_score=float(os.getenv("KNOWLEDGE_RETRIEVAL_MIN_SCORE", "0.65")),
    )
