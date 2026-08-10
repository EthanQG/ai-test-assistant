from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from application import KnowledgeAssetRetrievalService
from evaluation.rag import run_retrieval_service_evaluation
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetChunkType,
    KnowledgeAssetStatus,
    KnowledgeAssetVectorHit,
)
from repositories import InMemoryKnowledgeAssetRepository
from tests.unit.knowledge_assets.support import make_eligible_state


DATASET_PATH = Path("evaluation/fixtures/rag_v1.json")
REPORT_PATH = Path("evaluation/results/rag_fake_service_v1.json")
ASSET_IDS = (
    "asset-order-inventory",
    "asset-refund-cumulative",
    "asset-login-lock",
    "asset-file-upload",
    "asset-role-permission",
)


def _asset(asset_id: str):
    admitted = KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: asset_id,
        clock=lambda: datetime(2026, 8, 10, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )
    return replace(
        admitted,
        source_task_id=f"task-{asset_id}",
        content_hash=hashlib.sha256(asset_id.encode()).hexdigest(),
        status=KnowledgeAssetStatus.INDEXED,
    )


def _hit(asset):
    return KnowledgeAssetVectorHit(
        chunk_id=f"{asset.asset_id}:1:overview:0",
        asset_id=asset.asset_id,
        source_task_id=asset.source_task_id,
        asset_version=asset.asset_version,
        content_hash=asset.content_hash,
        chunk_type=KnowledgeAssetChunkType.OVERVIEW,
        chunk_index=0,
        search_text="synthetic relevant chunk",
        score=0.95,
    )


class _QueryEmbedding:
    def __init__(self):
        self.calls = []

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return [[float(len(self.calls))]]


class _QueryVectorSearch:
    def __init__(self, assets):
        self.assets = assets
        self.calls = []

    def search(self, query_vector, *, limit):
        self.calls.append((list(query_vector), limit))
        index = int(query_vector[0]) - 1
        return [_hit(self.assets[index])]


def test_rag_runner_uses_real_retrieval_service_boundary_with_fake_dependencies():
    assets = [_asset(asset_id) for asset_id in ASSET_IDS]
    repository = InMemoryKnowledgeAssetRepository()
    for asset in assets:
        repository.create(asset)
    embedding = _QueryEmbedding()
    vector_search = _QueryVectorSearch(assets)
    service = KnowledgeAssetRetrievalService(
        repository,
        embedding,
        vector_search,
        top_k=3,
    )

    report = run_retrieval_service_evaluation(DATASET_PATH, service, k=3)

    assert report["retrieval_boundary"] == "KnowledgeAssetRetrievalService"
    assert report["case_count"] == 5
    assert report["summary"] == {
        "mean_recall_at_k": 1.0,
        "mean_precision_at_k": 0.3333,
        "mean_reciprocal_rank": 1.0,
        "mean_forbidden_hit_rate": 0.0,
    }
    assert len(embedding.calls) == 5
    assert len(vector_search.calls) == 5
    assert [item["retrieved_asset_ids"][0] for item in report["results"]] == list(
        ASSET_IDS
    )
    expected_report = dict(report)
    expected_report["evidence_scope"] = "fake_dependencies_only"
    assert json.loads(REPORT_PATH.read_text(encoding="utf-8")) == expected_report
