from copy import deepcopy
from datetime import datetime, timezone

import pytest

from agent import TestPoint, TestPointReviewResult
from knowledge_assets import (
    KnowledgeAssetAdmissionPolicy,
    KnowledgeAssetSnapshotSerializer,
    KnowledgeAssetSnapshotValidationError,
    KnowledgeAssetStatus,
    UnsupportedKnowledgeAssetSnapshotVersionError,
)
from tests.unit.knowledge_assets.support import make_eligible_state


def _asset():
    return KnowledgeAssetAdmissionPolicy(
        asset_id_factory=lambda: "asset-snapshot-1",
        clock=lambda: datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc),
    ).admit(
        make_eligible_state(),
        user_confirmed=True,
        data_safety_confirmed=True,
        asset_version=1,
    )


def test_knowledge_asset_snapshot_round_trip_restores_domain_types():
    original = _asset()

    restored = KnowledgeAssetSnapshotSerializer.from_json(
        KnowledgeAssetSnapshotSerializer.to_json(original)
    )

    assert restored == original
    assert isinstance(restored.status, KnowledgeAssetStatus)
    assert isinstance(restored.test_points[0], TestPoint)
    assert isinstance(restored.review_result, TestPointReviewResult)
    assert restored.confirmed_at.tzinfo is not None


def test_knowledge_asset_snapshot_is_standard_json_and_isolated():
    original = _asset()
    payload = KnowledgeAssetSnapshotSerializer.to_dict(original)
    restored = KnowledgeAssetSnapshotSerializer.from_dict(payload)

    payload["asset"]["test_points"][0]["steps"].append("tampered")

    assert "tampered" not in restored.test_points[0].steps
    assert payload["schema_version"] == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.pop("schema_version"), "schema_version"),
        (lambda value: value["asset"].pop("status"), "status"),
        (
            lambda value: value["asset"].update(status="unknown"),
            "asset.status",
        ),
        (
            lambda value: value["asset"].update(
                confirmed_at="2026-08-05T02:00:00"
            ),
            "timezone",
        ),
        (
            lambda value: value["asset"].update(test_points="invalid"),
            "asset.test_points",
        ),
    ],
)
def test_knowledge_asset_snapshot_rejects_invalid_fields(mutate, message):
    payload = deepcopy(KnowledgeAssetSnapshotSerializer.to_dict(_asset()))
    mutate(payload)

    with pytest.raises(
        KnowledgeAssetSnapshotValidationError,
        match=message,
    ):
        KnowledgeAssetSnapshotSerializer.from_dict(payload)


def test_knowledge_asset_snapshot_rejects_future_version():
    payload = KnowledgeAssetSnapshotSerializer.to_dict(_asset())
    payload["schema_version"] = 2

    with pytest.raises(UnsupportedKnowledgeAssetSnapshotVersionError):
        KnowledgeAssetSnapshotSerializer.from_dict(payload)


def test_knowledge_asset_snapshot_rejects_broken_json():
    with pytest.raises(
        KnowledgeAssetSnapshotValidationError,
        match="JSON is invalid",
    ):
        KnowledgeAssetSnapshotSerializer.from_json("{")
