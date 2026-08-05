from __future__ import annotations

import math
from collections import defaultdict
from time import monotonic
from typing import Protocol, Sequence

from knowledge_assets import (
    KnowledgeAssetRetrievalCandidate,
    KnowledgeAssetRetrievalResult,
    KnowledgeAssetStatus,
    KnowledgeAssetVectorHit,
)
from repositories import KnowledgeAssetRepository


class QueryEmbeddingService(Protocol):
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


class KnowledgeAssetVectorSearch(Protocol):
    def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
    ) -> list[KnowledgeAssetVectorHit]: ...


class KnowledgeAssetRetrievalError(RuntimeError):
    """Raised when the retrieval dependencies return unusable data."""


class KnowledgeAssetRetrievalService:
    """Recalls chunks, then verifies and restores authoritative full assets."""

    def __init__(
        self,
        repository: KnowledgeAssetRepository,
        embedding_service: QueryEmbeddingService,
        vector_search: KnowledgeAssetVectorSearch,
        *,
        top_k: int = 3,
        raw_limit: int = 20,
        min_score: float = 0.65,
        max_chunks_per_asset: int = 3,
    ):
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if raw_limit < top_k:
            raise ValueError("raw_limit must be at least top_k")
        if not -1.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between -1 and 1")
        if max_chunks_per_asset <= 0:
            raise ValueError("max_chunks_per_asset must be positive")
        self._repository = repository
        self._embedding_service = embedding_service
        self._vector_search = vector_search
        self._top_k = top_k
        self._raw_limit = raw_limit
        self._min_score = min_score
        self._max_chunks_per_asset = max_chunks_per_asset

    def retrieve(self, query_text: str) -> KnowledgeAssetRetrievalResult:
        query = query_text.strip()
        if not query:
            raise ValueError("query_text cannot be empty")
        started = monotonic()
        vectors = self._embedding_service.embed_batch([query])
        query_vector = self._validate_query_vector(vectors)
        raw_hits = self._vector_search.search(
            query_vector,
            limit=self._raw_limit,
        )
        eligible_hits = [
            hit
            for hit in raw_hits
            if math.isfinite(hit.score) and hit.score >= self._min_score
        ]
        grouped: dict[str, list[KnowledgeAssetVectorHit]] = defaultdict(list)
        for hit in eligible_hits:
            grouped[hit.asset_id].append(hit)

        assets = self._repository.get_many(list(grouped))
        candidates: list[KnowledgeAssetRetrievalCandidate] = []
        stale_count = 0
        for asset_id, hits in grouped.items():
            asset = assets.get(asset_id)
            ordered_hits = sorted(hits, key=lambda item: item.score, reverse=True)
            if asset is None or not self._matches_authoritative_asset(
                asset,
                ordered_hits,
            ):
                stale_count += len(hits)
                continue
            candidates.append(
                KnowledgeAssetRetrievalCandidate(
                    asset=asset,
                    score=ordered_hits[0].score,
                    matched_chunks=tuple(
                        ordered_hits[: self._max_chunks_per_asset]
                    ),
                )
            )
        candidates.sort(
            key=lambda item: (item.score, len(item.matched_chunks)),
            reverse=True,
        )
        return KnowledgeAssetRetrievalResult(
            candidates=tuple(candidates[: self._top_k]),
            raw_hit_count=len(raw_hits),
            threshold_hit_count=len(eligible_hits),
            stale_hit_count=stale_count,
            duration_ms=max(0, round((monotonic() - started) * 1000)),
        )

    @staticmethod
    def _validate_query_vector(
        vectors: Sequence[Sequence[float]],
    ) -> list[float]:
        if len(vectors) != 1 or not vectors[0]:
            raise KnowledgeAssetRetrievalError(
                "query embedding must return exactly one non-empty vector"
            )
        vector = list(vectors[0])
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in vector
        ):
            raise KnowledgeAssetRetrievalError(
                "query embedding contains an invalid number"
            )
        return [float(value) for value in vector]

    @staticmethod
    def _matches_authoritative_asset(asset, hits) -> bool:
        return (
            asset.status is KnowledgeAssetStatus.INDEXED
            and all(hit.source_task_id == asset.source_task_id for hit in hits)
            and all(hit.asset_version == asset.asset_version for hit in hits)
            and all(hit.content_hash == asset.content_hash for hit in hits)
        )
