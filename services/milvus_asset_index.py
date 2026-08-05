from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Sequence

from knowledge_assets import KnowledgeAssetChunk


@dataclass(frozen=True)
class MilvusAssetIndexSettings:
    uri: str
    collection_name: str = "knowledge_assets_v2"
    token: str = ""

    @classmethod
    def from_env(cls) -> "MilvusAssetIndexSettings":
        uri = os.getenv(
            "MILVUS_URI",
            "http://127.0.0.1:19530",
        ).strip().rstrip("/")
        collection_name = os.getenv(
            "MILVUS_ASSET_COLLECTION",
            "knowledge_assets_v2",
        ).strip()
        if not uri:
            raise ValueError("MILVUS_URI cannot be empty")
        if not collection_name:
            raise ValueError("MILVUS_ASSET_COLLECTION cannot be empty")
        return cls(
            uri=uri,
            collection_name=collection_name,
            token=os.getenv("MILVUS_TOKEN", "").strip(),
        )


class MilvusKnowledgeAssetIndex:
    """Stores searchable chunks and stable MySQL association metadata."""

    def __init__(
        self,
        settings: MilvusAssetIndexSettings,
        *,
        client: Any | None = None,
    ):
        self._settings = settings
        self._client = client
        self._loaded = False

    def ensure_collection(self, vector_dimension: int) -> None:
        if vector_dimension <= 0:
            raise ValueError("vector_dimension must be positive")
        client, data_type, client_type = self._dependencies()
        if not client.has_collection(
            collection_name=self._settings.collection_name
        ):
            schema = client_type.create_schema(
                auto_id=False,
                enable_dynamic_field=False,
            )
            schema.add_field(
                field_name="chunk_id",
                datatype=data_type.VARCHAR,
                is_primary=True,
                max_length=160,
            )
            schema.add_field(
                field_name="vector",
                datatype=data_type.FLOAT_VECTOR,
                dim=vector_dimension,
            )
            for field_name, max_length in (
                ("asset_id", 36),
                ("source_task_id", 36),
                ("content_hash", 64),
                ("chunk_type", 32),
                ("search_text", 4096),
            ):
                schema.add_field(
                    field_name=field_name,
                    datatype=data_type.VARCHAR,
                    max_length=max_length,
                )
            schema.add_field(
                field_name="asset_version",
                datatype=data_type.INT64,
            )
            schema.add_field(
                field_name="chunk_index",
                datatype=data_type.INT64,
            )
            schema.add_field(
                field_name="was_truncated",
                datatype=data_type.BOOL,
            )
            index_params = client_type.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                metric_type="COSINE",
                index_type="IVF_FLAT",
                index_name="vector_index",
                params={"nlist": 128},
            )
            client.create_collection(
                collection_name=self._settings.collection_name,
                schema=schema,
                index_params=index_params,
            )
        if not self._loaded:
            client.load_collection(self._settings.collection_name)
            self._loaded = True

    def upsert(
        self,
        chunks: Sequence[KnowledgeAssetChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunk and vector counts must match")
        client, _, _ = self._dependencies()
        data = [
            {
                "chunk_id": chunk.chunk_id,
                "vector": list(vector),
                "asset_id": chunk.asset_id,
                "source_task_id": chunk.source_task_id,
                "asset_version": chunk.asset_version,
                "content_hash": chunk.content_hash,
                "chunk_type": chunk.chunk_type.value,
                "chunk_index": chunk.chunk_index,
                "search_text": chunk.search_text,
                "was_truncated": chunk.was_truncated,
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        if not data:
            raise ValueError("at least one chunk is required")
        client.upsert(
            collection_name=self._settings.collection_name,
            data=data,
        )
        client.flush(collection_name=self._settings.collection_name)

    def _dependencies(self):
        try:
            from pymilvus import DataType, MilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus is required for asset indexing") from exc
        if self._client is None:
            arguments = {"uri": self._settings.uri}
            if self._settings.token:
                arguments["token"] = self._settings.token
            self._client = MilvusClient(**arguments)
        return self._client, DataType, MilvusClient
