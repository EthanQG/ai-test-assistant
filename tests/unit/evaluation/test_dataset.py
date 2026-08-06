from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent.models import ClarificationCategory
from evaluation import (
    EvaluationDataset,
    EvaluationDatasetError,
    ReviewStatus,
    load_evaluation_dataset,
)


DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "evaluation"
    / "datasets"
    / "seed_v1.json"
)


@pytest.fixture
def valid_payload() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def test_seed_dataset_loads_as_typed_human_annotations() -> None:
    dataset = load_evaluation_dataset(DATASET_PATH)

    assert dataset.schema_version == 1
    assert dataset.dataset_id == "seed-v1"
    assert dataset.review_status is ReviewStatus.REVIEWED
    assert len(dataset.cases) == 10
    assert {case.domain for case in dataset.cases} == {
        "登录与权限",
        "订单与库存",
        "文件上传",
        "支付",
        "优惠券",
        "退款",
        "搜索",
        "消息通知",
        "高并发与重复提交",
        "角色权限",
    }
    assert dataset.cases[0].gold.facts[0].evidence
    assert (
        dataset.cases[0].gold.clarification_questions[0].category
        is ClarificationCategory.CORE_RULE
    )


def test_draft_dataset_covers_text_table_ui_and_state_diagram_inputs() -> None:
    dataset = load_evaluation_dataset(DATASET_PATH)
    features = {
        feature for case in dataset.cases for feature in case.document_features
    }

    assert {case.source_format for case in dataset.cases} >= {
        "text",
        "markdown",
        "docx",
    }
    assert features >= {"table", "ui_screenshot", "state_diagram"}


def test_contract_uses_immutable_collections() -> None:
    dataset = load_evaluation_dataset(DATASET_PATH)

    assert isinstance(dataset.cases, tuple)
    assert isinstance(dataset.cases[0].gold.facts, tuple)
    with pytest.raises(FrozenInstanceError):
        dataset.cases[0].title = "changed"


def test_duplicate_case_id_is_rejected(valid_payload: dict) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]

    with pytest.raises(EvaluationDatasetError, match="case_id values must be unique"):
        EvaluationDataset.from_dict(payload)


@pytest.mark.parametrize("invalid_version", [2, True, "1"])
def test_unknown_schema_version_is_rejected(
    valid_payload: dict,
    invalid_version: object,
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["schema_version"] = invalid_version

    with pytest.raises(EvaluationDatasetError, match="unsupported schema_version"):
        EvaluationDataset.from_dict(payload)


def test_unknown_review_status_is_rejected(valid_payload: dict) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["review_status"] = "approved_by_model"

    with pytest.raises(EvaluationDatasetError, match="review_status"):
        EvaluationDataset.from_dict(payload)


def test_invalid_clarification_category_reports_field_path(valid_payload: dict) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["cases"][0]["gold"]["clarification_questions"][0][
        "category"
    ] = "database_detail"

    with pytest.raises(
        EvaluationDatasetError,
        match=r"dataset\.cases\[0\]\.gold\.clarification_questions\[0\]\.category",
    ):
        EvaluationDataset.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    ["facts", "business_rules", "risks", "necessary_scenarios"],
)
def test_required_gold_lists_cannot_be_empty(
    valid_payload: dict,
    field: str,
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["cases"][0]["gold"][field] = []

    with pytest.raises(EvaluationDatasetError, match=f"gold.{field}"):
        EvaluationDataset.from_dict(payload)


def test_annotation_without_evidence_is_rejected(valid_payload: dict) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["cases"][0]["gold"]["facts"][0]["evidence"] = ""

    with pytest.raises(EvaluationDatasetError, match=r"facts\[0\]\.evidence"):
        EvaluationDataset.from_dict(payload)


def test_unknown_fields_are_rejected(valid_payload: dict) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["cases"][0]["gold"]["model_score"] = 100

    with pytest.raises(EvaluationDatasetError, match="unknown fields: model_score"):
        EvaluationDataset.from_dict(payload)
