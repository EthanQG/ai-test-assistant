from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable, Protocol, Sequence

from knowledge_assets import (
    KnowledgeAssetChunk,
    KnowledgeAssetChunkBuilder,
    KnowledgeAssetIndexRequest,
    KnowledgeAssetIndexRequestStatus,
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

    def delete_asset(self, asset_id: str, asset_version: int) -> None: ...


class KnowledgeAssetIndexingError(RuntimeError):
    """Raised when a pending KnowledgeAsset cannot be indexed."""


class KnowledgeAssetIndexingBusyError(KnowledgeAssetIndexingError):
    """Raised when the same retry request is still running."""


class KnowledgeAssetIndexingRequestFinishedError(KnowledgeAssetIndexingError):
    """Raised when a failed request_id is submitted again."""


@dataclass(frozen=True)
class KnowledgeAssetIndexingResult:
    asset_id: str
    status: KnowledgeAssetStatus
    chunk_count: int
    omitted_chunk_count: int
    duration_seconds: float
    already_indexed: bool = False
    request_id: str | None = None
    replayed_request: bool = False


@dataclass(frozen=True)
class KnowledgeAssetRetirementResult:
    asset_id: str
    status: KnowledgeAssetStatus
    vector_cleanup_completed: bool


class KnowledgeAssetIndexingService:
    """Indexes bounded asset chunks and keeps MySQL status authoritative."""

    def __init__(
        self,
        asset_repository: KnowledgeAssetRepository,
        embedding_service: BatchEmbeddingService,
        vector_index: KnowledgeAssetVectorIndex,
        *,
        chunk_builder: KnowledgeAssetChunkBuilder | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self._asset_repository = asset_repository
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._chunk_builder = chunk_builder or KnowledgeAssetChunkBuilder()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

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

    def retry_failed_asset(
        self,
        asset_id: str,
        request_id: str,
    ) -> KnowledgeAssetIndexingResult:
        started_at = self._clock()
        request, created = self._asset_repository.begin_index_retry(
            asset_id,
            request_id,
            started_at=started_at,
        )
        if not created:
            return self._replay_index_request(request)

        try:
            result = self.index_asset(asset_id)
        except Exception as exc:
            try:
                self._asset_repository.finish_index_request(
                    request_id,
                    KnowledgeAssetIndexRequestStatus.FAILED,
                    chunk_count=0,
                    omitted_chunk_count=0,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    finished_at=self._clock(),
                )
            except Exception as audit_exc:
                raise KnowledgeAssetIndexingError(
                    "knowledge asset indexing failed and its retry audit "
                    f"could not be saved: {type(audit_exc).__name__}"
                ) from exc
            raise

        self._asset_repository.finish_index_request(
            request_id,
            KnowledgeAssetIndexRequestStatus.SUCCEEDED,
            chunk_count=result.chunk_count,
            omitted_chunk_count=result.omitted_chunk_count,
            error_type=None,
            error_message=None,
            finished_at=self._clock(),
        )
        return KnowledgeAssetIndexingResult(
            asset_id=result.asset_id,
            status=result.status,
            chunk_count=result.chunk_count,
            omitted_chunk_count=result.omitted_chunk_count,
            duration_seconds=result.duration_seconds,
            request_id=request_id,
        )

    def retire_asset(
        self,
        asset_id: str,
    ) -> KnowledgeAssetRetirementResult:
        asset = self._asset_repository.get(asset_id)
        if asset.status is KnowledgeAssetStatus.INDEXED:
            asset = self._asset_repository.update_status(
                asset_id,
                KnowledgeAssetStatus.RETIRED,
                expected_status=KnowledgeAssetStatus.INDEXED,
            )
        elif asset.status is not KnowledgeAssetStatus.RETIRED:
            raise KnowledgeAssetIndexingError(
                "only indexed knowledge assets can be retired"
            )
        try:
            self._vector_index.delete_asset(
                asset.asset_id,
                asset.asset_version,
            )
        except Exception as exc:
            raise KnowledgeAssetIndexingError(
                "knowledge asset was retired but vector cleanup failed: "
                f"{type(exc).__name__}"
            ) from exc
        return KnowledgeAssetRetirementResult(
            asset_id=asset.asset_id,
            status=KnowledgeAssetStatus.RETIRED,
            vector_cleanup_completed=True,
        )

    def restore_asset(self, asset_id: str) -> KnowledgeAssetIndexingResult:
        """Restore a retired asset by rebuilding its vector index."""

        self._asset_repository.update_status(
            asset_id,
            KnowledgeAssetStatus.PENDING_INDEX,
            expected_status=KnowledgeAssetStatus.RETIRED,
        )
        return self.index_asset(asset_id)

    def _replay_index_request(
        self,
        request: KnowledgeAssetIndexRequest,
    ) -> KnowledgeAssetIndexingResult:
        if request.status is KnowledgeAssetIndexRequestStatus.SUCCEEDED:
            return KnowledgeAssetIndexingResult(
                asset_id=request.asset_id,
                status=KnowledgeAssetStatus.INDEXED,
                chunk_count=request.chunk_count,
                omitted_chunk_count=request.omitted_chunk_count,
                duration_seconds=0.0,
                already_indexed=True,
                request_id=request.request_id,
                replayed_request=True,
            )
        if request.status is KnowledgeAssetIndexRequestStatus.FAILED:
            raise KnowledgeAssetIndexingRequestFinishedError(
                "index retry request already failed; use a new request_id"
            )

        asset = self._asset_repository.get(request.asset_id)
        if asset.status is KnowledgeAssetStatus.INDEXED:
            recovered = self._asset_repository.finish_index_request(
                request.request_id,
                KnowledgeAssetIndexRequestStatus.SUCCEEDED,
                chunk_count=request.chunk_count,
                omitted_chunk_count=request.omitted_chunk_count,
                error_type=None,
                error_message=None,
                finished_at=self._clock(),
            )
            return KnowledgeAssetIndexingResult(
                asset_id=request.asset_id,
                status=KnowledgeAssetStatus.INDEXED,
                chunk_count=recovered.chunk_count,
                omitted_chunk_count=recovered.omitted_chunk_count,
                duration_seconds=0.0,
                already_indexed=True,
                request_id=request.request_id,
                replayed_request=True,
            )
        if asset.status is KnowledgeAssetStatus.INDEX_FAILED:
            self._asset_repository.finish_index_request(
                request.request_id,
                KnowledgeAssetIndexRequestStatus.FAILED,
                chunk_count=request.chunk_count,
                omitted_chunk_count=request.omitted_chunk_count,
                error_type="RecoveredIndexFailure",
                error_message=(
                    "asset was already index_failed when a running retry "
                    "request was recovered"
                ),
                finished_at=self._clock(),
            )
            raise KnowledgeAssetIndexingRequestFinishedError(
                "index retry request was recovered as failed; "
                "use a new request_id"
            )
        raise KnowledgeAssetIndexingBusyError(
            "index retry request is still running"
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
