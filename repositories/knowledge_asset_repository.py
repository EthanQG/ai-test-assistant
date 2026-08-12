from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock

from knowledge_assets import (
    KnowledgeAsset,
    KnowledgeAssetIndexRequest,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetStatus,
)


@dataclass(frozen=True)
class KnowledgeAssetSummary:
    asset_id: str
    source_task_id: str
    asset_version: int
    status: KnowledgeAssetStatus
    requirement_summary: str
    reviewer_score: int
    test_point_count: int
    confirmed_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class KnowledgeAssetSummaryPage:
    items: tuple[KnowledgeAssetSummary, ...]
    total: int
    offset: int
    limit: int


class KnowledgeAssetRepositoryError(RuntimeError):
    """Base error for knowledge asset persistence."""


class KnowledgeAssetNotFoundError(KnowledgeAssetRepositoryError):
    def __init__(self, asset_id: str):
        super().__init__(f"knowledge asset not found: {asset_id}")
        self.asset_id = asset_id


class KnowledgeAssetAlreadyExistsError(KnowledgeAssetRepositoryError):
    def __init__(self, reason: str):
        super().__init__(f"knowledge asset already exists: {reason}")
        self.reason = reason


class KnowledgeAssetStatusConflictError(KnowledgeAssetRepositoryError):
    def __init__(
        self,
        asset_id: str,
        expected: KnowledgeAssetStatus,
        actual: KnowledgeAssetStatus,
    ):
        super().__init__(
            "knowledge asset status conflict: "
            f"{asset_id}, expected={expected.value}, actual={actual.value}"
        )
        self.asset_id = asset_id
        self.expected = expected
        self.actual = actual


class KnowledgeAssetIndexRequestConflictError(KnowledgeAssetRepositoryError):
    def __init__(self, request_id: str, reason: str):
        super().__init__(f"knowledge asset index request conflict: {reason}")
        self.request_id = request_id
        self.reason = reason


class KnowledgeAssetIndexRequestNotFoundError(KnowledgeAssetRepositoryError):
    def __init__(self, request_id: str):
        super().__init__(f"knowledge asset index request not found: {request_id}")
        self.request_id = request_id


class KnowledgeAssetRepository(ABC):
    @abstractmethod
    def create(self, asset: KnowledgeAsset) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, asset_id: str) -> KnowledgeAsset:
        raise NotImplementedError

    @abstractmethod
    def get_many(
        self,
        asset_ids: list[str],
    ) -> dict[str, KnowledgeAsset]:
        """Return existing assets keyed by id without failing on stale ids."""

        raise NotImplementedError

    @abstractmethod
    def find_by_content_hash(
        self,
        content_hash: str,
    ) -> KnowledgeAsset | None:
        raise NotImplementedError

    @abstractmethod
    def find_latest_by_source_task_id(
        self,
        task_id: str,
    ) -> KnowledgeAsset | None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[KnowledgeAsset]:
        raise NotImplementedError

    @abstractmethod
    def list_summaries(
        self,
        *,
        query: str = "",
        status: KnowledgeAssetStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> KnowledgeAssetSummaryPage:
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        asset_id: str,
        status: KnowledgeAssetStatus,
        *,
        expected_status: KnowledgeAssetStatus,
    ) -> KnowledgeAsset:
        raise NotImplementedError

    @abstractmethod
    def begin_index_retry(
        self,
        asset_id: str,
        request_id: str,
        *,
        started_at: datetime,
    ) -> tuple[KnowledgeAssetIndexRequest, bool]:
        """Atomically create a retry request and reset index_failed state."""

        raise NotImplementedError

    @abstractmethod
    def finish_index_request(
        self,
        request_id: str,
        status: KnowledgeAssetIndexRequestStatus,
        *,
        chunk_count: int,
        omitted_chunk_count: int,
        error_type: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> KnowledgeAssetIndexRequest:
        raise NotImplementedError

    @abstractmethod
    def list_index_requests(
        self,
        asset_id: str,
    ) -> list[KnowledgeAssetIndexRequest]:
        raise NotImplementedError


class InMemoryKnowledgeAssetRepository(KnowledgeAssetRepository):
    """Process-local asset repository used before MySQL is introduced."""

    def __init__(self):
        self._assets: dict[str, KnowledgeAsset] = {}
        self._content_hashes: dict[str, str] = {}
        self._source_versions: dict[tuple[str, int], str] = {}
        self._index_requests: dict[str, KnowledgeAssetIndexRequest] = {}
        self._lock = RLock()

    def create(self, asset: KnowledgeAsset) -> None:
        with self._lock:
            if asset.asset_id in self._assets:
                raise KnowledgeAssetAlreadyExistsError(
                    f"asset_id={asset.asset_id}"
                )
            if asset.content_hash in self._content_hashes:
                raise KnowledgeAssetAlreadyExistsError(
                    f"content_hash={asset.content_hash}"
                )
            source_version = (
                asset.source_task_id,
                asset.asset_version,
            )
            if source_version in self._source_versions:
                raise KnowledgeAssetAlreadyExistsError(
                    "source task version="
                    f"{asset.source_task_id}:{asset.asset_version}"
                )
            self._assets[asset.asset_id] = deepcopy(asset)
            self._content_hashes[asset.content_hash] = asset.asset_id
            self._source_versions[source_version] = asset.asset_id

    def get(self, asset_id: str) -> KnowledgeAsset:
        with self._lock:
            if asset_id not in self._assets:
                raise KnowledgeAssetNotFoundError(asset_id)
            return deepcopy(self._assets[asset_id])

    def get_many(
        self,
        asset_ids: list[str],
    ) -> dict[str, KnowledgeAsset]:
        with self._lock:
            return {
                asset_id: deepcopy(self._assets[asset_id])
                for asset_id in dict.fromkeys(asset_ids)
                if asset_id in self._assets
            }

    def find_by_content_hash(
        self,
        content_hash: str,
    ) -> KnowledgeAsset | None:
        with self._lock:
            asset_id = self._content_hashes.get(content_hash)
            if asset_id is None:
                return None
            return deepcopy(self._assets[asset_id])

    def find_latest_by_source_task_id(
        self,
        task_id: str,
    ) -> KnowledgeAsset | None:
        with self._lock:
            matching = [
                asset
                for asset in self._assets.values()
                if asset.source_task_id == task_id
            ]
            if not matching:
                return None
            latest = max(matching, key=lambda asset: asset.asset_version)
            return deepcopy(latest)

    def list(self) -> list[KnowledgeAsset]:
        with self._lock:
            return [deepcopy(asset) for asset in self._assets.values()]

    def list_summaries(
        self,
        *,
        query: str = "",
        status: KnowledgeAssetStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> KnowledgeAssetSummaryPage:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be non-negative and limit must be positive")
        normalized_query = query.strip().casefold()
        with self._lock:
            matching = [
                asset
                for asset in self._assets.values()
                if (status is None or asset.status is status)
                and (
                    not normalized_query
                    or normalized_query
                    in asset.structured_requirement.summary.casefold()
                    or normalized_query in asset.source_task_id.casefold()
                )
            ]
            matching.sort(
                key=lambda asset: (asset.created_at, asset.asset_id),
                reverse=True,
            )
            items = tuple(
                _summary_from_asset(asset)
                for asset in matching[offset : offset + limit]
            )
        return KnowledgeAssetSummaryPage(items, len(matching), offset, limit)

    def update_status(
        self,
        asset_id: str,
        status: KnowledgeAssetStatus,
        *,
        expected_status: KnowledgeAssetStatus,
    ) -> KnowledgeAsset:
        with self._lock:
            if asset_id not in self._assets:
                raise KnowledgeAssetNotFoundError(asset_id)
            current = self._assets[asset_id]
            if current.status is not expected_status:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    expected_status,
                    current.status,
                )
            updated = replace(current, status=status)
            self._assets[asset_id] = updated
            return deepcopy(updated)

    def begin_index_retry(
        self,
        asset_id: str,
        request_id: str,
        *,
        started_at: datetime,
    ) -> tuple[KnowledgeAssetIndexRequest, bool]:
        with self._lock:
            existing = self._index_requests.get(request_id)
            if existing is not None:
                if existing.asset_id != asset_id:
                    raise KnowledgeAssetIndexRequestConflictError(
                        request_id,
                        "request_id belongs to another asset",
                    )
                return deepcopy(existing), False
            if asset_id not in self._assets:
                raise KnowledgeAssetNotFoundError(asset_id)
            current = self._assets[asset_id]
            if current.status is not KnowledgeAssetStatus.INDEX_FAILED:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    KnowledgeAssetStatus.INDEX_FAILED,
                    current.status,
                )
            request = KnowledgeAssetIndexRequest(
                request_id=request_id,
                asset_id=asset_id,
                status=KnowledgeAssetIndexRequestStatus.RUNNING,
                chunk_count=0,
                omitted_chunk_count=0,
                error_type=None,
                error_message=None,
                started_at=started_at,
            )
            self._assets[asset_id] = replace(
                current,
                status=KnowledgeAssetStatus.PENDING_INDEX,
            )
            self._index_requests[request_id] = request
            return deepcopy(request), True

    def finish_index_request(
        self,
        request_id: str,
        status: KnowledgeAssetIndexRequestStatus,
        *,
        chunk_count: int,
        omitted_chunk_count: int,
        error_type: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> KnowledgeAssetIndexRequest:
        if status is KnowledgeAssetIndexRequestStatus.RUNNING:
            raise ValueError("finished index request cannot remain running")
        with self._lock:
            current = self._index_requests.get(request_id)
            if current is None:
                raise KnowledgeAssetIndexRequestNotFoundError(request_id)
            if current.status is not KnowledgeAssetIndexRequestStatus.RUNNING:
                return deepcopy(current)
            updated = replace(
                current,
                status=status,
                chunk_count=chunk_count,
                omitted_chunk_count=omitted_chunk_count,
                error_type=error_type,
                error_message=error_message,
                finished_at=finished_at,
            )
            self._index_requests[request_id] = updated
            return deepcopy(updated)

    def list_index_requests(
        self,
        asset_id: str,
    ) -> list[KnowledgeAssetIndexRequest]:
        with self._lock:
            matching = [
                deepcopy(request)
                for request in self._index_requests.values()
                if request.asset_id == asset_id
            ]
        return sorted(matching, key=lambda request: request.started_at)


def _summary_from_asset(asset: KnowledgeAsset) -> KnowledgeAssetSummary:
    return KnowledgeAssetSummary(
        asset_id=asset.asset_id,
        source_task_id=asset.source_task_id,
        asset_version=asset.asset_version,
        status=asset.status,
        requirement_summary=asset.structured_requirement.summary,
        reviewer_score=asset.review_result.overall_score,
        test_point_count=len(asset.test_points),
        confirmed_at=asset.confirmed_at,
        created_at=asset.created_at,
    )
