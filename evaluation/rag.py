"""Deterministic asset-level metrics for offline RAG evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Callable, Protocol, Sequence

from knowledge_assets import KnowledgeAssetRetrievalResult


class KnowledgeAssetRetriever(Protocol):
    def retrieve(self, query_text: str) -> KnowledgeAssetRetrievalResult: ...


@dataclass(frozen=True)
class RagCaseScore:
    case_id: str
    retrieved_asset_ids: tuple[str, ...]
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    forbidden_hit_rate: float

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "retrieved_asset_ids": list(self.retrieved_asset_ids),
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "reciprocal_rank": self.reciprocal_rank,
            "forbidden_hit_rate": self.forbidden_hit_rate,
        }


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def score_rag_case(
    case: dict,
    retrieved_asset_ids: Sequence[str],
    *,
    k: int = 3,
) -> RagCaseScore:
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = set(case["relevant_asset_ids"])
    forbidden = set(case["forbidden_asset_ids"])
    retrieved = _unique(retrieved_asset_ids)[:k]
    relevant_hits = relevant.intersection(retrieved)
    first_relevant_rank = next(
        (
            rank
            for rank, asset_id in enumerate(retrieved, start=1)
            if asset_id in relevant
        ),
        None,
    )
    return RagCaseScore(
        case_id=case["case_id"],
        retrieved_asset_ids=retrieved,
        recall_at_k=round(len(relevant_hits) / len(relevant), 4),
        precision_at_k=round(len(relevant_hits) / k, 4),
        reciprocal_rank=(
            round(1 / first_relevant_rank, 4) if first_relevant_rank else 0.0
        ),
        forbidden_hit_rate=(
            round(len(forbidden.intersection(retrieved)) / len(forbidden), 4)
            if forbidden
            else 0.0
        ),
    )


def run_rag_evaluation(
    dataset_path: Path,
    retrieve: Callable[[str, int], Sequence[str]],
    *,
    k: int = 3,
) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    scores = [
        score_rag_case(case, retrieve(case["query"], k), k=k)
        for case in dataset["cases"]
    ]
    return {
        "schema_version": 1,
        "fixture_set_id": dataset["fixture_set_id"],
        "k": k,
        "case_count": len(scores),
        "summary": {
            "mean_recall_at_k": round(mean(item.recall_at_k for item in scores), 4),
            "mean_precision_at_k": round(
                mean(item.precision_at_k for item in scores), 4
            ),
            "mean_reciprocal_rank": round(
                mean(item.reciprocal_rank for item in scores), 4
            ),
            "mean_forbidden_hit_rate": round(
                mean(item.forbidden_hit_rate for item in scores), 4
            ),
        },
        "results": [item.to_dict() for item in scores],
    }


def run_retrieval_service_evaluation(
    dataset_path: Path,
    retrieval_service: KnowledgeAssetRetriever,
    *,
    k: int = 3,
) -> dict:
    """Evaluate ranked authoritative assets returned by the service boundary."""

    def retrieve_asset_ids(query: str, limit: int) -> tuple[str, ...]:
        result = retrieval_service.retrieve(query)
        return tuple(
            candidate.asset.asset_id
            for candidate in result.candidates[:limit]
        )

    report = run_rag_evaluation(dataset_path, retrieve_asset_ids, k=k)
    report["retrieval_boundary"] = "KnowledgeAssetRetrievalService"
    return report
