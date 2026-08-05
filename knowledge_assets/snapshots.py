from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from agent import InferredRisk, TestPoint, TestPointReviewResult

from .models import (
    KnowledgeAsset,
    KnowledgeAssetStatus,
    StructuredRequirement,
)


KNOWLEDGE_ASSET_SCHEMA_VERSION = 1


class KnowledgeAssetSnapshotError(ValueError):
    """Base error for invalid knowledge asset snapshots."""


class KnowledgeAssetSnapshotValidationError(KnowledgeAssetSnapshotError):
    """Raised when a knowledge asset snapshot violates schema version 1."""


class UnsupportedKnowledgeAssetSnapshotVersionError(
    KnowledgeAssetSnapshotError
):
    """Raised when no reader exists for the declared schema version."""


class KnowledgeAssetSnapshotSerializer:
    """Converts a KnowledgeAsset to a strict, versioned JSON snapshot."""

    _TOP_LEVEL_FIELDS = {"schema_version", "asset_id", "asset"}
    _ASSET_FIELDS = {
        "source_task_id",
        "asset_version",
        "content_hash",
        "status",
        "original_requirement",
        "structured_requirement",
        "test_points",
        "review_result",
        "final_report",
        "user_confirmed",
        "data_safety_confirmed",
        "confirmed_at",
        "created_at",
    }
    _STRUCTURED_REQUIREMENT_FIELDS = {
        "summary",
        "modules",
        "requirement_facts",
        "business_rules",
        "state_transitions",
        "inferred_risks",
    }

    @classmethod
    def to_dict(cls, asset: KnowledgeAsset) -> dict[str, Any]:
        raw = asset.to_dict()
        asset_id = raw.pop("asset_id")
        payload = {
            "schema_version": KNOWLEDGE_ASSET_SCHEMA_VERSION,
            "asset_id": asset_id,
            "asset": raw,
        }
        cls._ensure_json_value(payload, "snapshot")
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeAsset:
        root = cls._mapping(data, "snapshot")
        cls._require_exact_fields(root, cls._TOP_LEVEL_FIELDS, "snapshot")
        version = cls._integer(
            root["schema_version"],
            "schema_version",
            minimum=1,
        )
        if version != KNOWLEDGE_ASSET_SCHEMA_VERSION:
            raise UnsupportedKnowledgeAssetSnapshotVersionError(
                "unsupported knowledge asset schema_version: "
                f"{version}"
            )

        asset_data = cls._mapping(root["asset"], "asset")
        cls._require_exact_fields(
            asset_data,
            cls._ASSET_FIELDS,
            "asset",
        )
        structured_data = cls._mapping(
            asset_data["structured_requirement"],
            "asset.structured_requirement",
        )
        cls._require_exact_fields(
            structured_data,
            cls._STRUCTURED_REQUIREMENT_FIELDS,
            "asset.structured_requirement",
        )

        try:
            structured_requirement = StructuredRequirement(
                summary=cls._non_empty_text(
                    structured_data["summary"],
                    "asset.structured_requirement.summary",
                ),
                modules=cls._text_tuple(
                    structured_data["modules"],
                    "asset.structured_requirement.modules",
                ),
                requirement_facts=cls._text_tuple(
                    structured_data["requirement_facts"],
                    "asset.structured_requirement.requirement_facts",
                ),
                business_rules=cls._text_tuple(
                    structured_data["business_rules"],
                    "asset.structured_requirement.business_rules",
                ),
                state_transitions=cls._text_tuple(
                    structured_data["state_transitions"],
                    "asset.structured_requirement.state_transitions",
                ),
                inferred_risks=tuple(
                    InferredRisk.from_dict(item)
                    for item in cls._list(
                        structured_data["inferred_risks"],
                        "asset.structured_requirement.inferred_risks",
                    )
                ),
            )
            test_points = tuple(
                TestPoint.from_dict(item)
                for item in cls._list(
                    asset_data["test_points"],
                    "asset.test_points",
                )
            )
            review_result = TestPointReviewResult.from_dict(
                cls._mapping(
                    asset_data["review_result"],
                    "asset.review_result",
                )
            )
            return KnowledgeAsset(
                asset_id=cls._non_empty_text(
                    root["asset_id"],
                    "asset_id",
                ),
                source_task_id=cls._non_empty_text(
                    asset_data["source_task_id"],
                    "asset.source_task_id",
                ),
                asset_version=cls._integer(
                    asset_data["asset_version"],
                    "asset.asset_version",
                    minimum=1,
                ),
                content_hash=cls._non_empty_text(
                    asset_data["content_hash"],
                    "asset.content_hash",
                ),
                status=cls._enum(
                    asset_data["status"],
                    KnowledgeAssetStatus,
                    "asset.status",
                ),
                original_requirement=cls._non_empty_text(
                    asset_data["original_requirement"],
                    "asset.original_requirement",
                ),
                structured_requirement=structured_requirement,
                test_points=test_points,
                review_result=review_result,
                final_report=cls._non_empty_text(
                    asset_data["final_report"],
                    "asset.final_report",
                ),
                user_confirmed=cls._boolean(
                    asset_data["user_confirmed"],
                    "asset.user_confirmed",
                ),
                data_safety_confirmed=cls._boolean(
                    asset_data["data_safety_confirmed"],
                    "asset.data_safety_confirmed",
                ),
                confirmed_at=cls._datetime(
                    asset_data["confirmed_at"],
                    "asset.confirmed_at",
                ),
                created_at=cls._datetime(
                    asset_data["created_at"],
                    "asset.created_at",
                ),
            )
        except KnowledgeAssetSnapshotError:
            raise
        except Exception as exc:
            raise KnowledgeAssetSnapshotValidationError(
                f"knowledge asset snapshot is invalid: {exc}"
            ) from exc

    @classmethod
    def to_json(cls, asset: KnowledgeAsset) -> str:
        return json.dumps(
            cls.to_dict(asset),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, payload: str) -> KnowledgeAsset:
        if not isinstance(payload, str) or not payload.strip():
            raise KnowledgeAssetSnapshotValidationError(
                "knowledge asset JSON must be a non-empty string"
            )
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise KnowledgeAssetSnapshotValidationError(
                "knowledge asset JSON is invalid: "
                f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
            ) from exc
        return cls.from_dict(data)

    @staticmethod
    def migrate_snapshot(
        data: dict[str, Any],
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        if (
            from_version == KNOWLEDGE_ASSET_SCHEMA_VERSION
            and to_version == KNOWLEDGE_ASSET_SCHEMA_VERSION
        ):
            return deepcopy(data)
        raise UnsupportedKnowledgeAssetSnapshotVersionError(
            "no knowledge asset migration path from "
            f"{from_version} to {to_version}"
        )

    @staticmethod
    def _mapping(value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be an object"
            )
        return value

    @staticmethod
    def _list(value: Any, path: str) -> list[Any]:
        if not isinstance(value, list):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be a list"
            )
        return value

    @classmethod
    def _text_tuple(cls, value: Any, path: str) -> tuple[str, ...]:
        items = cls._list(value, path)
        return tuple(
            cls._non_empty_text(item, f"{path}[{index}]")
            for index, item in enumerate(items)
        )

    @staticmethod
    def _non_empty_text(value: Any, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be a non-empty string"
            )
        return value.strip()

    @staticmethod
    def _integer(value: Any, path: str, *, minimum: int) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
        ):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be an integer >= {minimum}"
            )
        return value

    @staticmethod
    def _boolean(value: Any, path: str) -> bool:
        if not isinstance(value, bool):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be a boolean"
            )
        return value

    @staticmethod
    def _enum(value: Any, enum_type, path: str):
        if not isinstance(value, str):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be a string"
            )
        try:
            return enum_type(value)
        except ValueError as exc:
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} contains an unsupported value"
            ) from exc

    @staticmethod
    def _datetime(value: Any, path: str) -> datetime:
        if not isinstance(value, str):
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be an ISO 8601 string"
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must be a valid ISO 8601 datetime"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} must include timezone"
            )
        return parsed

    @staticmethod
    def _require_exact_fields(
        value: dict[str, Any],
        expected: set[str],
        path: str,
    ) -> None:
        missing = expected - set(value)
        unexpected = set(value) - expected
        if missing or unexpected:
            details = []
            if missing:
                details.append("missing " + ", ".join(sorted(missing)))
            if unexpected:
                details.append(
                    "unexpected " + ", ".join(sorted(unexpected))
                )
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} fields are invalid: {'; '.join(details)}"
            )

    @classmethod
    def _ensure_json_value(cls, value: Any, path: str) -> None:
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise KnowledgeAssetSnapshotValidationError(
                f"{path} contains a non-JSON value"
            ) from exc
