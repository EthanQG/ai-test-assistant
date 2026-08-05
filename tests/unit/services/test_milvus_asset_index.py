from datetime import datetime, timezone

from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetChunkBuilder,
)
from services.milvus_asset_index import (
    MilvusAssetIndexSettings,
    MilvusKnowledgeAssetIndex,
)
from tests.unit.knowledge_assets.support import make_eligible_state


class _FakeMilvusClient:
    def __init__(self):
        self.loaded = []
        self.upserts = []
        self.flushes = []
        self.search_result = []
        self.search_calls = []

    def has_collection(self, collection_name):
        return True

    def load_collection(self, collection_name):
        self.loaded.append(collection_name)

    def upsert(self, collection_name, data):
        self.upserts.append((collection_name, data))

    def flush(self, collection_name):
        self.flushes.append(collection_name)

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_result


def _chunk():
    asset = KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: "asset-milvus-v2",
        clock=lambda: datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )
    return KnowledgeAssetChunkBuilder(max_chunks=1).build(asset).chunks[0]


def test_milvus_v2_upsert_keeps_mysql_association_metadata():
    client = _FakeMilvusClient()
    index = MilvusKnowledgeAssetIndex(
        MilvusAssetIndexSettings("http://milvus", "knowledge_assets_v2"),
        client=client,
    )
    chunk = _chunk()

    index.ensure_collection(2)
    index.upsert([chunk], [[0.1, 0.2]])

    row = client.upserts[0][1][0]
    assert row["chunk_id"] == chunk.chunk_id
    assert row["asset_id"] == chunk.asset_id
    assert row["asset_version"] == chunk.asset_version
    assert row["content_hash"] == chunk.content_hash
    assert row["search_text"] == chunk.search_text
    assert client.loaded == ["knowledge_assets_v2"]
    assert client.flushes == ["knowledge_assets_v2"]


def test_milvus_v2_search_restores_stable_asset_association():
    client = _FakeMilvusClient()
    chunk = _chunk()
    client.search_result = [[{
        "id": chunk.chunk_id,
        "distance": 0.87,
        "entity": {
            "asset_id": chunk.asset_id,
            "source_task_id": chunk.source_task_id,
            "asset_version": chunk.asset_version,
            "content_hash": chunk.content_hash,
            "chunk_type": chunk.chunk_type.value,
            "chunk_index": chunk.chunk_index,
            "search_text": chunk.search_text,
        },
    }]]
    index = MilvusKnowledgeAssetIndex(
        MilvusAssetIndexSettings("http://milvus", "knowledge_assets_v2"),
        client=client,
    )

    hits = index.search([0.1, 0.2], limit=10)

    assert len(hits) == 1
    assert hits[0].asset_id == chunk.asset_id
    assert hits[0].content_hash == chunk.content_hash
    assert hits[0].score == 0.87
    assert client.search_calls[0]["limit"] == 10
    assert client.search_calls[0]["search_params"]["metric_type"] == "COSINE"
