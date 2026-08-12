from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from knowledge_assets import (
    KnowledgeAsset,
    KnowledgeAssetIndexRequest,
    KnowledgeAssetIndexRequestStatus,
    KnowledgeAssetStatus,
)

from .knowledge_asset_repository import (
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetIndexRequestConflictError,
    KnowledgeAssetIndexRequestNotFoundError,
    KnowledgeAssetNotFoundError,
    KnowledgeAssetRepository,
    KnowledgeAssetRepositoryError,
    KnowledgeAssetSummary,
    KnowledgeAssetSummaryPage,
    KnowledgeAssetStatusConflictError,
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


CREATE_KNOWLEDGE_ASSET_INDEX_REQUESTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_asset_index_requests (
    request_id VARCHAR(64) NOT NULL PRIMARY KEY,
    asset_id VARCHAR(36) NOT NULL,
    status VARCHAR(16) NOT NULL,
    chunk_count INT UNSIGNED NOT NULL DEFAULT 0,
    omitted_chunk_count INT UNSIGNED NOT NULL DEFAULT 0,
    error_type VARCHAR(128) NULL,
    error_message VARCHAR(512) NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6) NULL,
    INDEX idx_asset_index_requests_asset_started (asset_id, started_at),
    INDEX idx_asset_index_requests_status_started (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()


def _summary_from_row(row: dict[str, Any]) -> KnowledgeAssetSummary:
    try:
        return KnowledgeAssetSummary(
            asset_id=str(row["asset_id"]),
            source_task_id=str(row["source_task_id"]),
            asset_version=int(row["asset_version"]),
            status=KnowledgeAssetStatus(str(row["status"])),
            requirement_summary=str(row["requirement_summary"]),
            reviewer_score=int(row["reviewer_score"]),
            test_point_count=int(row["test_point_count"]),
            confirmed_at=_aware_mysql_datetime(row["confirmed_at"]),
            created_at=_aware_mysql_datetime(row["created_at"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise KnowledgeAssetRepositoryError(
            "MySQL knowledge asset summary row is invalid"
        ) from exc


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
            cursor.execute(CREATE_KNOWLEDGE_ASSET_INDEX_REQUESTS_TABLE_SQL)
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

    def get_many(
        self,
        asset_ids: list[str],
    ) -> dict[str, KnowledgeAsset]:
        unique_ids = list(dict.fromkeys(asset_ids))
        if not unique_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(unique_ids))
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT asset_id, asset_json
                FROM knowledge_assets
                WHERE asset_id IN ({placeholders})
                """,
                tuple(unique_ids),
            )
            assets: dict[str, KnowledgeAsset] = {}
            for row in cursor.fetchall():
                if not isinstance(row, dict) or "asset_id" not in row:
                    raise KnowledgeAssetRepositoryError(
                        "MySQL knowledge asset batch row is invalid"
                    )
                asset = self._asset_from_row(row)
                assets[str(row["asset_id"])] = asset
            return assets
        except KnowledgeAssetRepositoryError:
            raise
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "failed to batch read MySQL knowledge assets"
            ) from exc
        finally:
            cursor.close()
            connection.close()

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
        conditions: list[str] = []
        params: list[Any] = []
        normalized_query = query.strip()
        if normalized_query:
            conditions.append(
                "(requirement_summary LIKE %s OR source_task_id LIKE %s)"
            )
            pattern = f"%{normalized_query}%"
            params.extend((pattern, pattern))
        if status is not None:
            conditions.append("status = %s")
            params.append(status.value)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM knowledge_assets{where_clause}",
                tuple(params),
            )
            count_row = cursor.fetchone()
            if not isinstance(count_row, dict) or "total" not in count_row:
                raise KnowledgeAssetRepositoryError(
                    "MySQL knowledge asset summary count row is invalid"
                )
            cursor.execute(
                "SELECT asset_id, source_task_id, asset_version, status, "
                "requirement_summary, reviewer_score, test_point_count, "
                "confirmed_at, created_at FROM knowledge_assets"
                f"{where_clause} ORDER BY created_at DESC, asset_id DESC "
                "LIMIT %s OFFSET %s",
                (*params, limit, offset),
            )
            items = tuple(_summary_from_row(row) for row in cursor.fetchall())
            return KnowledgeAssetSummaryPage(
                items=items,
                total=int(count_row["total"]),
                offset=offset,
                limit=limit,
            )
        except KnowledgeAssetRepositoryError:
            raise
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "failed to list MySQL knowledge asset summaries"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def update_status(
        self,
        asset_id: str,
        status: KnowledgeAssetStatus,
        *,
        expected_status: KnowledgeAssetStatus,
    ) -> KnowledgeAsset:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT asset_json
                FROM knowledge_assets
                WHERE asset_id = %s
                FOR UPDATE
                """,
                (asset_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KnowledgeAssetNotFoundError(asset_id)
            current = self._asset_from_row(row)
            if current.status is not expected_status:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    expected_status,
                    current.status,
                )
            updated = replace(current, status=status)
            snapshot = self._snapshot_codec.to_dict(updated)
            cursor.execute(
                """
                UPDATE knowledge_assets
                SET status = %s, asset_json = %s, updated_at = %s
                WHERE asset_id = %s AND status = %s
                """,
                (
                    status.value,
                    _json_text(snapshot),
                    _mysql_datetime(datetime.now(timezone.utc)),
                    asset_id,
                    expected_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    expected_status,
                    current.status,
                )
            connection.commit()
            return updated
        except (KnowledgeAssetNotFoundError, KnowledgeAssetStatusConflictError):
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise KnowledgeAssetRepositoryError(
                "failed to update MySQL knowledge asset status"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def begin_index_retry(
        self,
        asset_id: str,
        request_id: str,
        *,
        started_at: datetime,
    ) -> tuple[KnowledgeAssetIndexRequest, bool]:
        _validate_index_request_identity(request_id, asset_id, started_at)
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT asset_json
                FROM knowledge_assets
                WHERE asset_id = %s
                FOR UPDATE
                """,
                (asset_id,),
            )
            asset_row = cursor.fetchone()
            if asset_row is None:
                raise KnowledgeAssetNotFoundError(asset_id)
            asset = self._asset_from_row(asset_row)

            cursor.execute(
                """
                SELECT request_id, asset_id, status, chunk_count,
                       omitted_chunk_count, error_type, error_message,
                       started_at, finished_at
                FROM knowledge_asset_index_requests
                WHERE request_id = %s
                FOR UPDATE
                """,
                (request_id,),
            )
            request_row = cursor.fetchone()
            if request_row is not None:
                request = _index_request_from_row(request_row)
                if request.asset_id != asset_id:
                    raise KnowledgeAssetIndexRequestConflictError(
                        request_id,
                        "request_id belongs to another asset",
                    )
                connection.commit()
                return request, False

            if asset.status is not KnowledgeAssetStatus.INDEX_FAILED:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    KnowledgeAssetStatus.INDEX_FAILED,
                    asset.status,
                )
            pending = replace(
                asset,
                status=KnowledgeAssetStatus.PENDING_INDEX,
            )
            snapshot = self._snapshot_codec.to_dict(pending)
            cursor.execute(
                """
                UPDATE knowledge_assets
                SET status = %s, asset_json = %s, updated_at = %s
                WHERE asset_id = %s AND status = %s
                """,
                (
                    KnowledgeAssetStatus.PENDING_INDEX.value,
                    _json_text(snapshot),
                    _mysql_datetime(started_at),
                    asset_id,
                    KnowledgeAssetStatus.INDEX_FAILED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise KnowledgeAssetStatusConflictError(
                    asset_id,
                    KnowledgeAssetStatus.INDEX_FAILED,
                    asset.status,
                )
            cursor.execute(
                """
                INSERT INTO knowledge_asset_index_requests (
                    request_id, asset_id, status, chunk_count,
                    omitted_chunk_count, error_type, error_message,
                    started_at, finished_at
                ) VALUES (%s, %s, %s, 0, 0, NULL, NULL, %s, NULL)
                """,
                (
                    request_id,
                    asset_id,
                    KnowledgeAssetIndexRequestStatus.RUNNING.value,
                    _mysql_datetime(started_at),
                ),
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
            connection.commit()
            return request, True
        except (
            KnowledgeAssetNotFoundError,
            KnowledgeAssetStatusConflictError,
            KnowledgeAssetIndexRequestConflictError,
        ):
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise KnowledgeAssetRepositoryError(
                "failed to begin MySQL knowledge asset index retry"
            ) from exc
        finally:
            cursor.close()
            connection.close()

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
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT request_id, asset_id, status, chunk_count,
                       omitted_chunk_count, error_type, error_message,
                       started_at, finished_at
                FROM knowledge_asset_index_requests
                WHERE request_id = %s
                FOR UPDATE
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KnowledgeAssetIndexRequestNotFoundError(request_id)
            current = _index_request_from_row(row)
            if current.status is not KnowledgeAssetIndexRequestStatus.RUNNING:
                connection.commit()
                return current
            cursor.execute(
                """
                UPDATE knowledge_asset_index_requests
                SET status = %s, chunk_count = %s,
                    omitted_chunk_count = %s, error_type = %s,
                    error_message = %s, finished_at = %s
                WHERE request_id = %s AND status = %s
                """,
                (
                    status.value,
                    chunk_count,
                    omitted_chunk_count,
                    error_type,
                    _bounded_error_message(error_message),
                    _mysql_datetime(finished_at),
                    request_id,
                    KnowledgeAssetIndexRequestStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                raise KnowledgeAssetIndexRequestConflictError(
                    request_id,
                    "request is no longer running",
                )
            updated = replace(
                current,
                status=status,
                chunk_count=chunk_count,
                omitted_chunk_count=omitted_chunk_count,
                error_type=error_type,
                error_message=_bounded_error_message(error_message),
                finished_at=finished_at,
            )
            connection.commit()
            return updated
        except (
            KnowledgeAssetIndexRequestNotFoundError,
            KnowledgeAssetIndexRequestConflictError,
        ):
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise KnowledgeAssetRepositoryError(
                "failed to finish MySQL knowledge asset index request"
            ) from exc
        finally:
            cursor.close()
            connection.close()

    def list_index_requests(
        self,
        asset_id: str,
    ) -> list[KnowledgeAssetIndexRequest]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT request_id, asset_id, status, chunk_count,
                       omitted_chunk_count, error_type, error_message,
                       started_at, finished_at
                FROM knowledge_asset_index_requests
                WHERE asset_id = %s
                ORDER BY started_at ASC, request_id ASC
                """,
                (asset_id,),
            )
            return [_index_request_from_row(row) for row in cursor.fetchall()]
        except Exception as exc:
            raise KnowledgeAssetRepositoryError(
                "failed to list MySQL knowledge asset index requests"
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


def _validate_index_request_identity(
    request_id: str,
    asset_id: str,
    started_at: datetime,
) -> None:
    KnowledgeAssetIndexRequest(
        request_id=request_id,
        asset_id=asset_id,
        status=KnowledgeAssetIndexRequestStatus.RUNNING,
        chunk_count=0,
        omitted_chunk_count=0,
        error_type=None,
        error_message=None,
        started_at=started_at,
    )


def _index_request_from_row(row: Any) -> KnowledgeAssetIndexRequest:
    required = {
        "request_id",
        "asset_id",
        "status",
        "chunk_count",
        "omitted_chunk_count",
        "error_type",
        "error_message",
        "started_at",
        "finished_at",
    }
    if not isinstance(row, dict) or not required.issubset(row):
        raise KnowledgeAssetRepositoryError(
            "MySQL knowledge asset index request row is invalid"
        )
    try:
        return KnowledgeAssetIndexRequest(
            request_id=str(row["request_id"]),
            asset_id=str(row["asset_id"]),
            status=KnowledgeAssetIndexRequestStatus(row["status"]),
            chunk_count=int(row["chunk_count"]),
            omitted_chunk_count=int(row["omitted_chunk_count"]),
            error_type=row["error_type"],
            error_message=row["error_message"],
            started_at=_aware_mysql_datetime(row["started_at"]),
            finished_at=(
                None
                if row["finished_at"] is None
                else _aware_mysql_datetime(row["finished_at"])
            ),
        )
    except (TypeError, ValueError) as exc:
        raise KnowledgeAssetRepositoryError(
            "MySQL knowledge asset index request row is invalid"
        ) from exc


def _aware_mysql_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise KnowledgeAssetRepositoryError(
            "MySQL knowledge asset index datetime is invalid"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bounded_error_message(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned[:512] or None
