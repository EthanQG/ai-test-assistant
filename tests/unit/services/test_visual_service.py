import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from documents import DocumentVisualKind
from services.visual_service import (
    OpenAICompatibleVisualUnderstandingEngine,
    VisualUnderstandingError,
    VisualUnderstandingUnavailableError,
)


def _valid_response():
    return {
        "kind": "flowchart",
        "summary": "用户提交后进入审核",
        "confidence": 0.93,
        "nodes": [
            {"node_id": "submit", "label": "提交", "node_type": "action"},
            {"node_id": "review", "label": "审核", "node_type": "state"},
        ],
        "relations": [
            {
                "source_node_id": "submit",
                "target_node_id": "review",
                "label": "进入",
                "condition": None,
            }
        ],
        "ui_elements": [],
        "state_changes": ["待提交变为审核中"],
        "uncertainties": ["失败分支未展示"],
    }


def test_visual_engine_requires_explicit_configuration():
    engine = OpenAICompatibleVisualUnderstandingEngine(
        api_key="", base_url="", model=""
    )

    with pytest.raises(VisualUnderstandingUnavailableError, match="configured"):
        engine.analyze(b"image", "image/png", context="流程图", ocr_text="")


def test_visual_engine_sends_bounded_image_request_and_restores_types():
    from PIL import Image
    from io import BytesIO

    image = BytesIO()
    Image.new("RGB", (200, 160), "white").save(image, format="PNG")
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "choices": [
                {"message": {"content": json.dumps(_valid_response())}}
            ]
        },
    )
    engine = OpenAICompatibleVisualUnderstandingEngine(
        api_key="secret",
        base_url="https://vision.example/v1",
        model="vision-model",
    )

    with patch("services.visual_service.requests.post", return_value=response) as post:
        result = engine.analyze(
            image.getvalue(),
            "image/png",
            context="退款流程图",
            ocr_text="提交 审核",
        )

    assert result.kind is DocumentVisualKind.FLOWCHART
    assert result.nodes[1].label == "审核"
    assert result.relations[0].source_node_id == "submit"
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 1500
    assert payload["temperature"] == 0
    assert payload["response_format"] == {"type": "json_object"}
    image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")


def test_visual_engine_rejects_unknown_fields_and_broken_relations():
    invalid = _valid_response()
    invalid["unexpected"] = True
    with pytest.raises(ValueError, match="fields"):
        OpenAICompatibleVisualUnderstandingEngine._parse_result(invalid)

    broken = _valid_response()
    broken["relations"][0]["target_node_id"] = "missing"
    with pytest.raises(ValueError, match="unknown node"):
        OpenAICompatibleVisualUnderstandingEngine._parse_result(broken)


def test_visual_engine_wraps_invalid_json_without_leaking_payload():
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": "not-json"}}]},
    )
    engine = OpenAICompatibleVisualUnderstandingEngine(
        api_key="secret",
        base_url="https://vision.example/v1",
        model="vision-model",
    )

    with patch("services.visual_service.requests.post", return_value=response), patch.object(
        engine, "_prepare_image", return_value=(b"image", "image/png")
    ):
        with pytest.raises(VisualUnderstandingError, match="invalid structured"):
            engine.analyze(b"image", "image/png", context="", ocr_text="")
