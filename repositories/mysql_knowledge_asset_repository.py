from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from knowledge_assets import KnowledgeAsset

from .knowledge_asset_repository import (
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
    KnowledgeAssetRepository,
    KnowledgeAssetRepositoryError,
)


class KnowledgeAssetSnapshotCodec(Protocol):
    @classmethod
    def to_dict(cls, asset: KnowledgeAsset) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeAsset: ...

    @classmethod
    def from_json(cls, payload: str) -> KnowledgeAsset: ...


CREATE_KNOWLEDGE_ASSETS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_assets (
    asset_id VARCHAR(36) NOT NULL PRIMARY KEY,
    source_task_id VARCHAR(36) NOT NULL,
    asset_version INT UNSIGNED NOT NULL,
    schema_version SMALLINT UNSIGNED NOT NULL,
    content_hash CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    requirement_summary VARCHAR(512) NOT NULL,
    reviewer_score TINYINT UNSIGNED NOT NULL,
    test_point_count INT UNSIGNED NOT NULL,
    asset_json JSON NOT NULL,
    confirmed_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_knowledge_assets_content_hash (content_hash),
    UNIQUE KEY uq_knowledge_assets_source_version (
        source_task_id, asset_version
    ),
    INDEX idx_knowledge_assets_source_created (
        source_task_id, created_at
    ),
    INDEX idx_knowledge_assets_status_updated (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()


class MySQLKnowledgeAssetRepository(KnowledgeAssetRepository):
    """Stores complete KnowledgeAsset JSON as the authoritative record."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        snapshot_codec: type[KnowledgeAssetSnapshotCodec],
    ):
        self._connection_factory = connection_factory
        self._snapshot_codec = snapshot_codec

    def initialize_schema(self) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(CREATE_KNOWLEDGE_ASSETS_TABLE_SQL)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise KnowledgeAssetRepositoryError(
                "failed to initialize MySQL knowledge asset schema"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def create(self, asset: KnowledgeAsset) -> None:
        snapshot = self._snapshot_codec.to_dict(asset)
        now = datetime.now(timezone.utc)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO knowledge_assets (
                    asset_id, source_task_id, asset_version,
                    schema_version, content_hash, status,
                    requirement_summary, reviewer_score,
                    test_point_count, asset_json, confirmed_at,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    asset.asset_id,
                    asset.source_task_id,
                    asset.asset_version,
                    snapshot["schema_version"],
                    asset.content_hash,
                    asset.status.value,
                    asset.structured_requirement.summary,
                    asset.review_result.overall_score,
                    len(asset.test_points),
                    _json_text(snapshot),
                    _mysql_datetime(asset.confirmed_at),
                    _mysql_datetime(asset.created_at),
                    _mysql_datetime(now),
                ),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            if _mysql_error_code(exc) == 1062:
                raise KnowledgeAssetAlreadyExistsError(
                    "asset_id, content_hash, or source task version"
                ) from exc
            raise KnowledgeAssetRepositoryError(
                "failed to create MySQL knowledge asset"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def get(self, asset_id: str) -> KnowledgeAsset:
        asset = self._fetch_one(
            """
            SELECT asset_json
            FROM knowledge_assets
            WHERE asset_id = %s
            """,
            (asset_id,),
        )
        if asset is None:
            raise KnowledgeAssetNotFoundError(asset_id)
        return asset

    def find_by_content_hash(
        self,
        content_hash: str,
    ) -> KnowledgeAsset | None:
        return self._fetch_one(
            """
            SELECT asset_json
            FROM knowledge_assets
            WHERE content_hash = %s
            """,
            (content_hash,),
        )

    def find_latest_by_source_task_id(
        self,
        task_id: str,
    ) -> KnowledgeAsset | None:
        return self._fetch_one(
            """
            SELECT asset_json
            FROM knowledge_assets
            WHERE source_task_id = %s
            ORDER BY asset_version DESC
            LIMIT 1
            """,
            (task_id,),
        )

    def list(self) -> list[KnowledgeAsset]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT asset_json
                FROM knowledge_assets
                ORDER BY created_at DESC, asset_id DESC
                """
            )
            rows = cursor.fetchall()
            return [self._asset_from_row(row) for row in rows]
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "failed to list MySQL knowledge assets"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def _fetch_one(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> KnowledgeAsset | None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return None if row is None else self._asset_from_row(row)
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "failed to read MySQL knowledge asset"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def _asset_from_row(self, row: Any) -> KnowledgeAsset:
        if not isinstance(row, dict) or "asset_json" not in row:
            raise KnowledgeAssetRepositoryError(
                "MySQL knowledge asset row is invalid"
            )
        value = row["asset_json"]
        try:
            if isinstance(value, dict):
                return self._snapshot_codec.from_dict(value)
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            if not isinstance(value, str):
                raise KnowledgeAssetRepositoryError(
                    "MySQL asset_json must be an object or JSON text"
                )
            return self._snapshot_codec.from_json(value)
        except KnowledgeAssetRepositoryError:
            raise
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "stored MySQL knowledge asset snapshot is invalid"
            ) from exc


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _mysql_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KnowledgeAssetRepositoryError(
            "persisted datetime must include timezone"
        )
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _mysql_error_code(exc: Exception) -> int | None:
    if not exc.args:
        return None
    return exc.args[0] if isinstance(exc.args[0], int) else None
