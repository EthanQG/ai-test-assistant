import json
from pathlib import Path

import pytest

from evaluation.rag_assets import load_rag_seed_assets
from evaluation.rag_integration import run_real_rag_evaluation
from knowledge_assets import KnowledgeAssetStatus


ASSET_PATH = Path("evaluation/fixtures/rag_assets_v1.json")
QUERY_PATH = Path("evaluation/fixtures/rag_v1.json")


def test_rag_seed_assets_match_all_relevant_gold_asset_ids():
    assets = load_rag_seed_assets(ASSET_PATH)
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))

    assert len(assets) == 5
    assert {asset.asset_id for asset in assets} == {
        case["relevant_asset_ids"][0] for case in queries["cases"]
    }
    assert all(asset.status is KnowledgeAssetStatus.PENDING_INDEX for asset in assets)
    assert all(asset.test_points and asset.review_result.overall_score == 90 for asset in assets)
    assert len({asset.content_hash for asset in assets}) == 5


def test_real_rag_runner_is_disabled_without_explicit_environment_flag(
    monkeypatch,
):
    monkeypatch.setenv("RUN_RAG_INTEGRATION_EVALUATION", "0")

    with pytest.raises(RuntimeError, match="RUN_RAG_INTEGRATION_EVALUATION=1"):
        run_real_rag_evaluation()
