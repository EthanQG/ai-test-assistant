import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetStatus,
    build_content_hash,
)

from .support import make_eligible_state, make_test_point


def _policy() -> KnowledgeAssetAdmissionPolicy:
    timestamp = datetime(2026, 8, 5, tzinfo=timezone.utc)
    return KnowledgeAssetAdmissionPolicy(
        clock=lambda: timestamp,
        asset_id_factory=lambda: "asset-1",
    )


def _asset():
    return _policy().admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )


def test_knowledge_asset_is_json_compatible_and_typed():
    asset = _asset()
    payload = asset.to_dict()

    json.dumps(payload, ensure_ascii=False)

    assert asset.status is KnowledgeAssetStatus.PENDING_INDEX
    assert asset.asset_version == 1
    assert len(asset.content_hash) == 64
    assert payload["structured_requirement"]["modules"] == [
        "订单",
        "库存",
    ]
    assert payload["review_result"]["overall_score"] == 92
    assert payload["confirmed_at"].endswith("+00:00")


def test_content_hash_is_deterministic_and_tracks_business_content():
    first = _asset()
    same = _asset()
    changed_state = make_eligible_state()
    changed_state.test_points = [make_test_point("库存不足时拒绝订单")]
    changed_state.final_result["test_points"] = [
        make_test_point("库存不足时拒绝订单")
    ]
    changed = _policy().admit(
        changed_state,
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )

    recalculated = build_content_hash(
        first.original_requirement,
        first.structured_requirement,
        first.test_points,
    )

    assert first.content_hash == same.content_hash == recalculated
    assert changed.content_hash != first.content_hash


def test_model_rejects_invalid_identity_version_hash_and_time():
    asset = _asset()

    with pytest.raises(ValueError, match="asset_id"):
        replace(asset, asset_id=" ")
    with pytest.raises(ValueError, match="asset_version"):
        replace(asset, asset_version=0)
    with pytest.raises(ValueError, match="SHA-256"):
        replace(asset, content_hash="not-a-hash")
    with pytest.raises(ValueError, match="timezone"):
        replace(asset, confirmed_at=datetime(2026, 8, 5))
