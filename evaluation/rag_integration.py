"""Explicit real-infrastructure runner for the synthetic RAG evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from application import (
    build_knowledge_asset_indexing_service,
    build_knowledge_asset_repository,
    build_knowledge_asset_retrieval_service,
)
from knowledge_assets import KnowledgeAssetStatus
from repositories import KnowledgeAssetNotFoundError

from .rag import run_retrieval_service_evaluation
from .rag_assets import load_rag_seed_assets


FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEFAULT_REPORT_PATH = Path(__file__).parent / "results" / "rag_real_v1.json"


def run_real_rag_evaluation(report_path: Path = DEFAULT_REPORT_PATH) -> dict:
    load_dotenv()
    if os.getenv("RUN_RAG_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_RAG_INTEGRATION_EVALUATION=1 to use real services"
        )
    if os.getenv("KNOWLEDGE_ASSET_REPOSITORY_BACKEND", "memory").lower() != "mysql":
        raise RuntimeError("real RAG evaluation requires the MySQL asset repository")

    repository = build_knowledge_asset_repository()
    assets = load_rag_seed_assets(FIXTURE_DIR / "rag_assets_v1.json")
    for asset in assets:
        try:
            existing = repository.get(asset.asset_id)
        except KnowledgeAssetNotFoundError:
            repository.create(asset)
            continue
        if existing.content_hash != asset.content_hash:
            raise RuntimeError(
                f"existing evaluation asset differs: {asset.asset_id}"
            )

    indexing_service = build_knowledge_asset_indexing_service(repository)
    for seed in assets:
        current = repository.get(seed.asset_id)
        if current.status is KnowledgeAssetStatus.PENDING_INDEX:
            indexing_service.index_asset(current.asset_id)
        elif current.status is KnowledgeAssetStatus.INDEX_FAILED:
            indexing_service.retry_failed_asset(
                current.asset_id,
                f"rag-eval-{uuid4()}",
            )
        elif current.status is not KnowledgeAssetStatus.INDEXED:
            raise RuntimeError(
                f"evaluation asset is not searchable: {current.asset_id}"
            )

    retrieval_service = build_knowledge_asset_retrieval_service(repository)
    report = run_retrieval_service_evaluation(
        FIXTURE_DIR / "rag_v1.json",
        retrieval_service,
        k=int(os.getenv("KNOWLEDGE_RETRIEVAL_TOP_K", "3")),
    )
    report["evidence_scope"] = "real_embedding_milvus_mysql"
    report["embedding_model"] = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    report["milvus_collection"] = os.getenv(
        "MILVUS_ASSET_COLLECTION", "knowledge_assets_v2"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = run_real_rag_evaluation()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
