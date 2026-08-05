from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, Sequence

from knowledge_assets import (
    KnowledgeAssetChunk,
    KnowledgeAssetChunkBuilder,
    KnowledgeAssetStatus,
)
from repositories import (
    KnowledgeAssetRepository,
    KnowledgeAssetStatusConflictError,
)


class BatchEmbeddingService(Protocol):
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


class KnowledgeAssetVectorIndex(Protocol):
    def ensure_collection(self, vector_dimension: int) -> None: ...

    def upsert(
        self,
        chunks: Sequence[KnowledgeAssetChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None: ...


class KnowledgeAssetIndexingError(RuntimeError):
    """Raised when a pending KnowledgeAsset cannot be indexed."""


@dataclass(frozen=True)
class KnowledgeAssetIndexingResult:
    asset_id: str
    status: KnowledgeAssetStatus
    chunk_count: int
    omitted_chunk_count: int
    duration_seconds: float
    already_indexed: bool = False


class KnowledgeAssetIndexingService:
    """Indexes bounded asset chunks and keeps MySQL status authoritative."""

    def __init__(
        self,
        asset_repository: KnowledgeAssetRepository,
        embedding_service: BatchEmbeddingService,
        vector_index: KnowledgeAssetVectorIndex,
        *,
        chunk_builder: KnowledgeAssetChunkBuilder | None = None,
    ):
        self._asset_repository = asset_repository
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._chunk_builder = chunk_builder or KnowledgeAssetChunkBuilder()

    def index_asset(self, asset_id: str) -> KnowledgeAssetIndexingResult:
        started_at = perf_counter()
        asset = self._asset_repository.get(asset_id)
        if asset.status is KnowledgeAssetStatus.INDEXED:
            return KnowledgeAssetIndexingResult(
                asset_id=asset_id,
                status=asset.status,
                chunk_count=0,
                omitted_chunk_count=0,
                duration_seconds=perf_counter() - started_at,
                already_indexed=True,
            )
        if asset.status is not KnowledgeAssetStatus.PENDING_INDEX:
            raise KnowledgeAssetIndexingError(
                "only pending_index knowledge assets can be indexed"
            )

        build_result = self._chunk_builder.build(asset)
        if not build_result.chunks:
            self._mark_failed(asset_id)
            raise KnowledgeAssetIndexingError(
                "knowledge asset produced no indexable chunks"
            )

        try:
            vectors = self._embedding_service.embed_batch(
                [chunk.search_text for chunk in build_result.chunks]
            )
            vector_dimension = self._validate_vectors(
                vectors,
                len(build_result.chunks),
            )
            self._vector_index.ensure_collection(vector_dimension)
            self._vector_index.upsert(build_result.chunks, vectors)
            updated = self._asset_repository.update_status(
                asset_id,
                KnowledgeAssetStatus.INDEXED,
                expected_status=KnowledgeAssetStatus.PENDING_INDEX,
            )
        except KnowledgeAssetStatusConflictError:
            raise
        except Exception as exc:
            status_error = self._try_mark_failed(asset_id)
            suffix = (
                ""
                if status_error is None
                else "; failed to persist index_failed status"
            )
            raise KnowledgeAssetIndexingError(
                "failed to index knowledge asset: "
                f"{type(exc).__name__}{suffix}"
            ) from exc

        return KnowledgeAssetIndexingResult(
            asset_id=asset_id,
            status=updated.status,
            chunk_count=len(build_result.chunks),
            omitted_chunk_count=build_result.omitted_count,
            duration_seconds=perf_counter() - started_at,
        )

    @staticmethod
    def _validate_vectors(
        vectors: Sequence[Sequence[float]],
        expected_count: int,
    ) -> int:
        if len(vectors) != expected_count:
            raise ValueError("embedding count does not match chunk count")
        if not vectors or not vectors[0]:
            raise ValueError("embedding vectors cannot be empty")
        dimension = len(vectors[0])
        for vector in vectors:
            if len(vector) != dimension:
                raise ValueError("embedding vectors have inconsistent dimensions")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                for value in vector
            ):
                raise ValueError("embedding vectors must contain numbers")
        return dimension

    def _mark_failed(self, asset_id: str) -> None:
        self._asset_repository.update_status(
            asset_id,
            KnowledgeAssetStatus.INDEX_FAILED,
            expected_status=KnowledgeAssetStatus.PENDING_INDEX,
        )

    def _try_mark_failed(self, asset_id: str) -> Exception | None:
        try:
            self._mark_failed(asset_id)
        except Exception as exc:  # keep the original indexing failure primary
            return exc
        return None
