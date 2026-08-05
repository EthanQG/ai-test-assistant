from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from threading import RLock

from knowledge_assets import KnowledgeAsset, KnowledgeAssetStatus


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
    def update_status(
        self,
        asset_id: str,
        status: KnowledgeAssetStatus,
        *,
        expected_status: KnowledgeAssetStatus,
    ) -> KnowledgeAsset:
        raise NotImplementedError


class InMemoryKnowledgeAssetRepository(KnowledgeAssetRepository):
    """Process-local asset repository used before MySQL is introduced."""

    def __init__(self):
        self._assets: dict[str, KnowledgeAsset] = {}
        self._content_hashes: dict[str, str] = {}
        self._source_versions: dict[tuple[str, int], str] = {}
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

    def update_status(
        self,
        asset_id: str,
        status: KnowledgeAssetStatus,
        *,
        expected_status: KnowledgeAssetStatus,
    ) -> KnowledgeAsset:
        from dataclasses import replace

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
