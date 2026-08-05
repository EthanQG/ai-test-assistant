from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from knowledge_assets import (
    KnowledgeAsset,
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetStatus,
)
from repositories import KnowledgeAssetRepository, TaskRepository

from .commands import ConfirmKnowledgeAssetCommand


@dataclass(frozen=True)
class KnowledgeAssetView:
    asset_id: str
    source_task_id: str
    asset_version: int
    content_hash: str
    status: KnowledgeAssetStatus
    requirement_summary: str
    test_point_count: int
    reviewer_score: int
    confirmed_at: datetime

    @classmethod
    def from_asset(cls, asset: KnowledgeAsset) -> "KnowledgeAssetView":
        return cls(
            asset_id=asset.asset_id,
            source_task_id=asset.source_task_id,
            asset_version=asset.asset_version,
            content_hash=asset.content_hash,
            status=asset.status,
            requirement_summary=asset.structured_requirement.summary,
            test_point_count=len(asset.test_points),
            reviewer_score=asset.review_result.overall_score,
            confirmed_at=asset.confirmed_at,
        )


class KnowledgeAssetApplicationService:
    """Publishes confirmed task results without exposing repositories."""

    def __init__(
        self,
        task_repository: TaskRepository,
        asset_repository: KnowledgeAssetRepository,
        *,
        admission_policy: KnowledgeAssetAdmissionPolicy | None = None,
    ):
        self._task_repository = task_repository
        self._asset_repository = asset_repository
        self._admission_policy = (
            admission_policy or KnowledgeAssetAdmissionPolicy()
        )

    def confirm_task_result(
        self,
        task_id: str,
        command: ConfirmKnowledgeAssetCommand,
    ) -> KnowledgeAssetView:
        task = self._task_repository.get(task_id)
        latest = self._asset_repository.find_latest_by_source_task_id(
            task_id
        )
        asset_version = 1 if latest is None else latest.asset_version + 1
        asset = self._admission_policy.admit(
            task.state,
            user_confirmed=command.user_confirmed,
            data_safety_confirmed=command.data_safety_confirmed,
            asset_version=asset_version,
        )
        self._asset_repository.create(asset)
        return KnowledgeAssetView.from_asset(asset)

    def get_asset(self, asset_id: str) -> KnowledgeAssetView:
        return KnowledgeAssetView.from_asset(
            self._asset_repository.get(asset_id)
        )

    def list_assets(self) -> tuple[KnowledgeAssetView, ...]:
        return tuple(
            KnowledgeAssetView.from_asset(asset)
            for asset in self._asset_repository.list()
        )
