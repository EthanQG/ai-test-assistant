from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from knowledge_assets import (
    KnowledgeAsset,
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetStatus,
)
from repositories import (
    KnowledgeAssetRepository,
    KnowledgeAssetSummary,
    TaskRepository,
)

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
    created_at: datetime

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
            created_at=asset.created_at,
        )


@dataclass(frozen=True)
class KnowledgeAssetSummaryView:
    asset_id: str
    source_task_id: str
    asset_version: int
    status: KnowledgeAssetStatus
    requirement_summary: str
    reviewer_score: int
    test_point_count: int
    confirmed_at: datetime
    created_at: datetime

    @classmethod
    def from_summary(
        cls,
        summary: KnowledgeAssetSummary,
    ) -> "KnowledgeAssetSummaryView":
        return cls(**summary.__dict__)


@dataclass(frozen=True)
class KnowledgeAssetSummaryPageView:
    items: tuple[KnowledgeAssetSummaryView, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class KnowledgeAssetDetailView(KnowledgeAssetView):
    original_requirement: str
    structured_requirement: dict[str, Any]
    test_points: tuple[dict[str, Any], ...]
    review_result: dict[str, Any]
    final_report: str

    @classmethod
    def from_asset(cls, asset: KnowledgeAsset) -> "KnowledgeAssetDetailView":
        base = KnowledgeAssetView.from_asset(asset)
        return cls(
            **base.__dict__,
            original_requirement=asset.original_requirement,
            structured_requirement=asset.structured_requirement.to_dict(),
            test_points=tuple(point.to_dict() for point in asset.test_points),
            review_result=asset.review_result.to_dict(),
            final_report=asset.final_report,
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

    def get_asset(self, asset_id: str) -> KnowledgeAssetDetailView:
        return KnowledgeAssetDetailView.from_asset(
            self._asset_repository.get(asset_id)
        )

    def list_assets(self) -> tuple[KnowledgeAssetView, ...]:
        return tuple(
            KnowledgeAssetView.from_asset(asset)
            for asset in self._asset_repository.list()
        )

    def list_asset_summaries(
        self,
        *,
        query: str = "",
        status: KnowledgeAssetStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> KnowledgeAssetSummaryPageView:
        page = self._asset_repository.list_summaries(
            query=query,
            status=status,
            offset=offset,
            limit=limit,
        )
        return KnowledgeAssetSummaryPageView(
            items=tuple(
                KnowledgeAssetSummaryView.from_summary(item)
                for item in page.items
            ),
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )
