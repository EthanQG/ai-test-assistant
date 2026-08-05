from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from agent import InferredRisk, TestPoint, TestPointReviewResult


class KnowledgeAssetStatus(str, Enum):
    PENDING_INDEX = "pending_index"
    INDEXED = "indexed"
    INDEX_FAILED = "index_failed"
    RETIRED = "retired"


@dataclass(frozen=True)
class StructuredRequirement:
    summary: str
    modules: tuple[str, ...]
    requirement_facts: tuple[str, ...]
    business_rules: tuple[str, ...]
    state_transitions: tuple[str, ...]
    inferred_risks: tuple[InferredRisk, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "modules": list(self.modules),
            "requirement_facts": list(self.requirement_facts),
            "business_rules": list(self.business_rules),
            "state_transitions": list(self.state_transitions),
            "inferred_risks": [
                risk.to_dict() for risk in self.inferred_risks
            ],
        }


@dataclass(frozen=True)
class KnowledgeAsset:
    asset_id: str
    source_task_id: str
    asset_version: int
    content_hash: str
    status: KnowledgeAssetStatus
    original_requirement: str
    structured_requirement: StructuredRequirement
    test_points: tuple[TestPoint, ...]
    review_result: TestPointReviewResult
    final_report: str
    user_confirmed: bool
    data_safety_confirmed: bool
    confirmed_at: datetime
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id cannot be empty")
        if not self.source_task_id.strip():
            raise ValueError("source_task_id cannot be empty")
        if (
            isinstance(self.asset_version, bool)
            or not isinstance(self.asset_version, int)
            or self.asset_version <= 0
        ):
            raise ValueError("asset_version must be positive")
        if len(self.content_hash) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.content_hash
        ):
            raise ValueError("content_hash must be a SHA-256 hex digest")
        if not isinstance(self.status, KnowledgeAssetStatus):
            raise ValueError("status must be KnowledgeAssetStatus")
        if not self.original_requirement.strip():
            raise ValueError("original_requirement cannot be empty")
        if not self.structured_requirement.summary.strip():
            raise ValueError("requirement summary cannot be empty")
        if not self.test_points:
            raise ValueError("knowledge asset must contain test points")
        if not self.final_report.strip():
            raise ValueError("final_report cannot be empty")
        if (
            self.user_confirmed is not True
            or self.data_safety_confirmed is not True
        ):
            raise ValueError("knowledge asset requires explicit confirmation")
        _require_aware_datetime(self.confirmed_at, "confirmed_at")
        _require_aware_datetime(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_task_id": self.source_task_id,
            "asset_version": self.asset_version,
            "content_hash": self.content_hash,
            "status": self.status.value,
            "original_requirement": self.original_requirement,
            "structured_requirement": self.structured_requirement.to_dict(),
            "test_points": [point.to_dict() for point in self.test_points],
            "review_result": self.review_result.to_dict(),
            "final_report": self.final_report,
            "user_confirmed": self.user_confirmed,
            "data_safety_confirmed": self.data_safety_confirmed,
            "confirmed_at": self.confirmed_at.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


def build_content_hash(
    original_requirement: str,
    structured_requirement: StructuredRequirement,
    test_points: tuple[TestPoint, ...],
) -> str:
    """Hash authoritative asset content, excluding identity and timestamps."""

    payload = {
        "original_requirement": original_requirement.strip(),
        "structured_requirement": structured_requirement.to_dict(),
        "test_points": [point.to_dict() for point in test_points],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone")
