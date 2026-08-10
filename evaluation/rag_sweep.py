"""Explicit Top-K and score-threshold comparison using real RAG services."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from application import KnowledgeAssetRetrievalService, build_knowledge_asset_repository
from repositories import InMemoryKnowledgeAssetRepository
from services.embedding_service import OllamaBatchEmbeddingService, OllamaEmbeddingSettings
from services.milvus_asset_index import MilvusAssetIndexSettings, MilvusKnowledgeAssetIndex

from .rag import run_rag_parameter_sweep


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "rag_v1.json"
REPORT_PATH = Path(__file__).parent / "results" / "rag_parameter_sweep_v1.json"
TOP_K_VALUES = (1, 2, 3)
MIN_SCORE_VALUES = (0.65, 0.70, 0.75)


class _CachedEmbeddingService:
    def __init__(self, delegate):
        self._delegate = delegate
        self._cache = {}

    def embed_batch(self, texts):
        key = tuple(texts)
        if key not in self._cache:
            self._cache[key] = self._delegate.embed_batch(texts)
        return self._cache[key]


def run_real_parameter_sweep() -> dict:
    load_dotenv()
    if os.getenv("RUN_RAG_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_RAG_INTEGRATION_EVALUATION=1 to use real services"
        )
    if os.getenv("KNOWLEDGE_ASSET_REPOSITORY_BACKEND", "memory").lower() != "mysql":
        raise RuntimeError("real RAG parameter sweep requires MySQL")

    mysql_repository = build_knowledge_asset_repository()
    seed_data = json.loads(
        (Path(__file__).parent / "fixtures" / "rag_assets_v1.json").read_text(
            encoding="utf-8"
        )
    )
    asset_ids = [item["asset_id"] for item in seed_data["assets"]]
    authoritative_assets = mysql_repository.get_many(asset_ids)
    missing = set(asset_ids) - set(authoritative_assets)
    if missing:
        raise RuntimeError(f"evaluation assets are missing: {sorted(missing)}")
    repository = InMemoryKnowledgeAssetRepository()
    for asset_id in asset_ids:
        asset = authoritative_assets[asset_id]
        if asset.status.value != "indexed":
            raise RuntimeError(f"evaluation asset is not indexed: {asset_id}")
        repository.create(asset)

    embedding = _CachedEmbeddingService(
        OllamaBatchEmbeddingService(OllamaEmbeddingSettings.from_env())
    )
    vector_search = MilvusKnowledgeAssetIndex(MilvusAssetIndexSettings.from_env())

    def service_factory(top_k: int, min_score: float):
        return KnowledgeAssetRetrievalService(
            repository,
            embedding,
            vector_search,
            top_k=top_k,
            raw_limit=20,
            min_score=min_score,
        )

    report = run_rag_parameter_sweep(
        FIXTURE_PATH,
        service_factory,
        top_k_values=TOP_K_VALUES,
        min_score_values=MIN_SCORE_VALUES,
    )
    report["evidence_scope"] = "real_embedding_milvus_mysql_snapshot"
    report["embedding_model"] = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    report["milvus_collection"] = os.getenv(
        "MILVUS_ASSET_COLLECTION", "knowledge_assets_v2"
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = run_real_parameter_sweep()
    for item in result["combinations"]:
        print(item["top_k"], item["min_score"], item["summary"])
