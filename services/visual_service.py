from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import json
import os
from typing import Protocol

import requests

from documents import (
    DocumentUiElement,
    DocumentVisualKind,
    DocumentVisualNode,
    DocumentVisualRelation,
)


class VisualUnderstandingError(RuntimeError):
    """Base error raised by bounded visual understanding adapters."""


class VisualUnderstandingUnavailableError(VisualUnderstandingError):
    """Raised when no visual model has been configured."""


@dataclass(frozen=True)
class VisualUnderstandingResult:
    kind: DocumentVisualKind
    summary: str
    confidence: float
    nodes: tuple[DocumentVisualNode, ...] = ()
    relations: tuple[DocumentVisualRelation, ...] = ()
    ui_elements: tuple[DocumentUiElement, ...] = ()
    state_changes: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DocumentVisualKind):
            raise ValueError("visual kind must be DocumentVisualKind")
        if not self.summary.strip():
            raise ValueError("visual summary cannot be empty")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("visual confidence must be between 0 and 1")
        if any(
            not isinstance(items, tuple)
            for items in (
                self.nodes,
                self.relations,
                self.ui_elements,
                self.state_changes,
                self.uncertainties,
            )
        ):
            raise ValueError("visual result collections must be tuples")
        if any(not isinstance(item, DocumentVisualNode) for item in self.nodes):
            raise ValueError("visual nodes must contain DocumentVisualNode")
        if any(
            not isinstance(item, DocumentVisualRelation)
            for item in self.relations
        ):
            raise ValueError(
                "visual relations must contain DocumentVisualRelation"
            )
        if any(
            not isinstance(item, DocumentUiElement)
            for item in self.ui_elements
        ):
            raise ValueError("ui_elements must contain DocumentUiElement")
        node_ids = {item.node_id for item in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("visual node IDs must be unique")
        if any(
            relation.source_node_id not in node_ids
            or relation.target_node_id not in node_ids
            for relation in self.relations
        ):
            raise ValueError("visual relation points to an unknown node")


class VisualUnderstandingEngine(Protocol):
    def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        *,
        context: str,
        ocr_text: str,
    ) -> VisualUnderstandingResult:
        ...


class OpenAICompatibleVisualUnderstandingEngine:
    """Calls an explicitly configured OpenAI-compatible vision endpoint."""

    _MAX_DIMENSION = 1600
    _MAX_CONTEXT_CHARS = 2000
    _MAX_OCR_CHARS = 3000
    _MAX_NODES = 50
    _MAX_RELATIONS = 80
    _MAX_UI_ELEMENTS = 50
    _MAX_STATE_CHANGES = 50
    _MAX_UNCERTAINTIES = 20

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
        max_tokens: int = 1500,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleVisualUnderstandingEngine":
        return cls(
            api_key=os.getenv("VISION_API_KEY", ""),
            base_url=os.getenv("VISION_BASE_URL", ""),
            model=os.getenv("VISION_MODEL", ""),
            timeout_seconds=int(os.getenv("VISION_TIMEOUT_SECONDS", "60")),
            max_tokens=int(os.getenv("VISION_MAX_TOKENS", "1500")),
        )

    def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        *,
        context: str,
        ocr_text: str,
    ) -> VisualUnderstandingResult:
        if not self._api_key or not self._base_url or not self._model:
            raise VisualUnderstandingUnavailableError(
                "visual model is not configured"
            )
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise ValueError("visual image content must be non-empty bytes")
        prepared, prepared_mime = self._prepare_image(image_bytes, mime_type)
        encoded = base64.b64encode(prepared).decode("ascii")
        prompt = self._prompt(context=context, ocr_text=ocr_text)
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是测试需求图像分析器。只提取图片中可见的信息，"
                        "不得补造业务规则；不确定内容必须写入uncertainties。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{prepared_mime};base64,{encoded}"
                                )
                            },
                        },
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise VisualUnderstandingError(
                "visual model request failed"
            ) from exc
        try:
            return self._parse_result(json.loads(content))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VisualUnderstandingError(
                "visual model returned invalid structured output"
            ) from exc

    @classmethod
    def _prepare_image(
        cls, image_bytes: bytes, mime_type: str
    ) -> tuple[bytes, str]:
        from PIL import Image

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                if max(image.size) <= cls._MAX_DIMENSION:
                    return image_bytes, mime_type
                copy = image.convert("RGB")
                copy.thumbnail((cls._MAX_DIMENSION, cls._MAX_DIMENSION))
                output = BytesIO()
                copy.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue(), "image/jpeg"
        except Exception as exc:
            raise VisualUnderstandingError(
                "visual image preparation failed"
            ) from exc

    @classmethod
    def _prompt(cls, *, context: str, ocr_text: str) -> str:
        return (
            "分析该流程图、状态图、时序图或UI原型，返回单个JSON对象。\n"
            "kind只能是flowchart、state_diagram、sequence_diagram、"
            "ui_mockup或other。\n"
            "字段必须包含kind、summary、confidence、nodes、relations、"
            "ui_elements、state_changes、uncertainties。\n"
            "nodes项包含node_id、label、node_type；relations项包含"
            "source_node_id、target_node_id、label、condition；ui_elements项"
            "包含name、element_type、action、state_change。\n"
            "relations引用的节点必须存在；看不清或无法确认的内容不要猜测。\n"
            f"相邻文档上下文：{context[: cls._MAX_CONTEXT_CHARS]}\n"
            f"OCR参考文字：{ocr_text[: cls._MAX_OCR_CHARS]}"
        )

    @classmethod
    def _parse_result(cls, data: object) -> VisualUnderstandingResult:
        if not isinstance(data, dict):
            raise ValueError("visual response must be an object")
        required = {
            "kind",
            "summary",
            "confidence",
            "nodes",
            "relations",
            "ui_elements",
            "state_changes",
            "uncertainties",
        }
        if set(data) != required:
            raise ValueError("visual response fields do not match contract")
        nodes = cls._object_list(
            data["nodes"],
            "nodes",
            cls._MAX_NODES,
            {"node_id", "label", "node_type"},
        )
        relations = cls._object_list(
            data["relations"],
            "relations",
            cls._MAX_RELATIONS,
            {"source_node_id", "target_node_id", "label", "condition"},
        )
        ui_elements = cls._object_list(
            data["ui_elements"],
            "ui_elements",
            cls._MAX_UI_ELEMENTS,
            {"name", "element_type", "action", "state_change"},
        )
        state_changes = cls._string_list(
            data["state_changes"], "state_changes", cls._MAX_STATE_CHANGES
        )
        uncertainties = cls._string_list(
            data["uncertainties"], "uncertainties", cls._MAX_UNCERTAINTIES
        )
        return VisualUnderstandingResult(
            kind=DocumentVisualKind(str(data["kind"])),
            summary=cls._required_string(data["summary"], "summary"),
            confidence=cls._confidence(data["confidence"]),
            nodes=tuple(
                DocumentVisualNode(
                    node_id=cls._required_string(item.get("node_id"), "node_id"),
                    label=cls._required_string(item.get("label"), "label"),
                    node_type=cls._required_string(
                        item.get("node_type"), "node_type"
                    ),
                )
                for item in nodes
            ),
            relations=tuple(
                DocumentVisualRelation(
                    source_node_id=cls._required_string(
                        item.get("source_node_id"), "source_node_id"
                    ),
                    target_node_id=cls._required_string(
                        item.get("target_node_id"), "target_node_id"
                    ),
                    label=cls._optional_string(item.get("label"), "label"),
                    condition=cls._optional_string(
                        item.get("condition"), "condition"
                    ),
                )
                for item in relations
            ),
            ui_elements=tuple(
                DocumentUiElement(
                    name=cls._required_string(item.get("name"), "name"),
                    element_type=cls._required_string(
                        item.get("element_type"), "element_type"
                    ),
                    action=cls._optional_string(item.get("action"), "action"),
                    state_change=cls._optional_string(
                        item.get("state_change"), "state_change"
                    ),
                )
                for item in ui_elements
            ),
            state_changes=tuple(state_changes),
            uncertainties=tuple(uncertainties),
        )

    @staticmethod
    def _object_list(
        value: object, field: str, limit: int, expected_fields: set[str]
    ) -> list[dict]:
        if not isinstance(value, list) or len(value) > limit:
            raise ValueError(f"{field} must be a bounded list")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field} must contain objects")
        if any(set(item) != expected_fields for item in value):
            raise ValueError(f"{field} item fields do not match contract")
        return value

    @staticmethod
    def _string_list(value: object, field: str, limit: int) -> list[str]:
        if (
            not isinstance(value, list)
            or len(value) > limit
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            raise ValueError(f"{field} must be a bounded string list")
        return [item.strip() for item in value]

    @staticmethod
    def _required_string(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _optional_string(value: object, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string or null")
        return value.strip() or None

    @staticmethod
    def _confidence(value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("confidence must be a number")
        normalized = float(value)
        if not 0 <= normalized <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return normalized
