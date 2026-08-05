from __future__ import annotations

from dataclasses import dataclass

from .indexing import KnowledgeAssetChunkType
from .models import KnowledgeAsset


@dataclass(frozen=True)
class KnowledgeAssetVectorHit:
    """A lightweight Milvus hit that still points to authoritative MySQL data."""

    chunk_id: str
    asset_id: str
    source_task_id: str
    asset_version: int
    content_hash: str
    chunk_type: KnowledgeAssetChunkType
    chunk_index: int
    search_text: str
    score: float


@dataclass(frozen=True)
class KnowledgeAssetRetrievalCandidate:
    """A verified full asset plus the bounded chunks that caused its recall."""

    asset: KnowledgeAsset
    score: float
    matched_chunks: tuple[KnowledgeAssetVectorHit, ...]


@dataclass(frozen=True)
class KnowledgeAssetRetrievalResult:
    candidates: tuple[KnowledgeAssetRetrievalCandidate, ...]
    raw_hit_count: int
    threshold_hit_count: int
    stale_hit_count: int
    duration_ms: int
