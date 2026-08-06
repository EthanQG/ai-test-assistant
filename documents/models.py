from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import TypeAlias


class DocumentFormat(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"


class DocumentTextKind(str, Enum):
    TITLE = "title"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"


class DocumentWarningCode(str, Enum):
    EMPTY_DOCUMENT = "empty_document"
    EMPTY_PAGE = "empty_page"
    TABLE_NOT_EXTRACTED = "table_not_extracted"
    IMAGE_NOT_EXTRACTED = "image_not_extracted"
    TABLE_EXTRACTION_FAILED = "table_extraction_failed"
    IMAGE_EXTRACTION_FAILED = "image_extraction_failed"
    IMAGE_TOO_LARGE = "image_too_large"
    IMAGE_LIMIT_EXCEEDED = "image_limit_exceeded"
    PAGE_RENDER_REQUIRED = "page_render_required"
    OCR_UNAVAILABLE = "ocr_unavailable"
    OCR_FAILED = "ocr_failed"
    OCR_LOW_CONFIDENCE = "ocr_low_confidence"
    VISION_UNAVAILABLE = "vision_unavailable"
    VISION_FAILED = "vision_failed"
    VISION_LIMIT_EXCEEDED = "vision_limit_exceeded"
    VISION_LOW_CONFIDENCE = "vision_low_confidence"


class DocumentOcrDisposition(str, Enum):
    ACCEPTED = "accepted"
    REVIEW_REQUIRED = "review_required"


class DocumentVisualKind(str, Enum):
    FLOWCHART = "flowchart"
    STATE_DIAGRAM = "state_diagram"
    SEQUENCE_DIAGRAM = "sequence_diagram"
    UI_MOCKUP = "ui_mockup"
    OTHER = "other"


@dataclass(frozen=True)
class DocumentAttachment:
    attachment_id: str
    mime_type: str
    content: bytes
    sha256: str

    def __post_init__(self) -> None:
        if not self.attachment_id.strip():
            raise ValueError("attachment_id cannot be empty")
        if not self.mime_type.strip():
            raise ValueError("attachment mime_type cannot be empty")
        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("attachment content must be non-empty bytes")
        actual_hash = hashlib.sha256(self.content).hexdigest()
        if self.sha256 != actual_hash:
            raise ValueError("attachment sha256 does not match content")


@dataclass(frozen=True)
class DocumentParseStats:
    page_count: int = 0
    text_element_count: int = 0
    table_count: int = 0
    image_count: int = 0
    warning_count: int = 0
    skipped_table_count: int = 0
    skipped_image_count: int = 0
    ocr_element_count: int = 0
    low_confidence_ocr_count: int = 0
    failed_ocr_count: int = 0
    visual_candidate_count: int = 0
    visual_analyzed_count: int = 0
    failed_visual_count: int = 0

    def __post_init__(self) -> None:
        values = (
            self.page_count,
            self.text_element_count,
            self.table_count,
            self.image_count,
            self.warning_count,
            self.skipped_table_count,
            self.skipped_image_count,
            self.ocr_element_count,
            self.low_confidence_ocr_count,
            self.failed_ocr_count,
            self.visual_candidate_count,
            self.visual_analyzed_count,
            self.failed_visual_count,
        )
        if any(isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("document parse statistics cannot be negative")
        if self.visual_analyzed_count > self.visual_candidate_count:
            raise ValueError("visual analyzed count cannot exceed candidates")
        if self.failed_visual_count > self.visual_candidate_count:
            raise ValueError("failed visual count cannot exceed candidates")
        if (
            self.visual_analyzed_count + self.failed_visual_count
            > self.visual_candidate_count
        ):
            raise ValueError("visual outcomes cannot exceed candidate count")


@dataclass(frozen=True)
class DocumentSourceRef:
    source_id: str
    document_id: str
    filename: str
    element_index: int
    page_number: int | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id cannot be empty")
        if not self.document_id.strip():
            raise ValueError("document_id cannot be empty")
        if not self.filename.strip():
            raise ValueError("filename cannot be empty")
        if self.element_index < 0:
            raise ValueError("element_index cannot be negative")
        if self.page_number is not None and self.page_number <= 0:
            raise ValueError("page_number must be positive")


@dataclass(frozen=True)
class DocumentTextElement:
    source: DocumentSourceRef
    kind: DocumentTextKind
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DocumentTextKind):
            raise ValueError("kind must be a DocumentTextKind")
        if not self.text.strip():
            raise ValueError("document text element cannot be empty")


@dataclass(frozen=True)
class DocumentTable:
    rows: tuple[tuple[str, ...], ...]
    caption: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or any(
            not isinstance(row, tuple) for row in self.rows
        ):
            raise ValueError("document table rows must be immutable tuples")
        if not self.rows:
            raise ValueError("document table requires at least one row")
        width = len(self.rows[0])
        if width == 0:
            raise ValueError("document table rows cannot be empty")
        if any(len(row) != width for row in self.rows):
            raise ValueError("document table rows must have equal width")
        if any(not isinstance(cell, str) for row in self.rows for cell in row):
            raise ValueError("document table cells must be strings")


@dataclass(frozen=True)
class DocumentTableElement:
    source: DocumentSourceRef
    table: DocumentTable


@dataclass(frozen=True)
class DocumentImage:
    image_id: str
    mime_type: str
    content_ref: str
    caption: str | None = None
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        if not self.image_id.strip():
            raise ValueError("image_id cannot be empty")
        if not self.mime_type.strip():
            raise ValueError("mime_type cannot be empty")
        if not self.content_ref.strip():
            raise ValueError("content_ref cannot be empty")
        if self.width is not None and (
            isinstance(self.width, bool) or self.width <= 0
        ):
            raise ValueError("image width must be positive")
        if self.height is not None and (
            isinstance(self.height, bool) or self.height <= 0
        ):
            raise ValueError("image height must be positive")


@dataclass(frozen=True)
class DocumentImageElement:
    source: DocumentSourceRef
    image: DocumentImage


@dataclass(frozen=True)
class DocumentOcrElement:
    source: DocumentSourceRef
    text: str
    confidence: float
    image_id: str
    disposition: DocumentOcrDisposition

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("OCR text cannot be empty")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("OCR confidence must be between 0 and 1")
        if not self.image_id.strip():
            raise ValueError("OCR image_id cannot be empty")
        if not isinstance(self.disposition, DocumentOcrDisposition):
            raise ValueError("OCR disposition must be DocumentOcrDisposition")


@dataclass(frozen=True)
class DocumentVisualNode:
    node_id: str
    label: str
    node_type: str

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("visual node_id cannot be empty")
        if not self.label.strip():
            raise ValueError("visual node label cannot be empty")
        if not self.node_type.strip():
            raise ValueError("visual node type cannot be empty")


@dataclass(frozen=True)
class DocumentVisualRelation:
    source_node_id: str
    target_node_id: str
    label: str | None = None
    condition: str | None = None

    def __post_init__(self) -> None:
        if not self.source_node_id.strip():
            raise ValueError("visual relation source_node_id cannot be empty")
        if not self.target_node_id.strip():
            raise ValueError("visual relation target_node_id cannot be empty")
        if self.label is not None and not isinstance(self.label, str):
            raise ValueError("visual relation label must be a string or None")
        if self.condition is not None and not isinstance(self.condition, str):
            raise ValueError(
                "visual relation condition must be a string or None"
            )


@dataclass(frozen=True)
class DocumentUiElement:
    name: str
    element_type: str
    action: str | None = None
    state_change: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("UI element name cannot be empty")
        if not self.element_type.strip():
            raise ValueError("UI element type cannot be empty")
        if self.action is not None and not isinstance(self.action, str):
            raise ValueError("UI element action must be a string or None")
        if self.state_change is not None and not isinstance(
            self.state_change, str
        ):
            raise ValueError("UI state_change must be a string or None")


@dataclass(frozen=True)
class DocumentVisualAnalysis:
    image_id: str
    kind: DocumentVisualKind
    summary: str
    confidence: float
    nodes: tuple[DocumentVisualNode, ...] = ()
    relations: tuple[DocumentVisualRelation, ...] = ()
    ui_elements: tuple[DocumentUiElement, ...] = ()
    state_changes: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.image_id.strip():
            raise ValueError("visual analysis image_id cannot be empty")
        if not isinstance(self.kind, DocumentVisualKind):
            raise ValueError("visual analysis kind must be DocumentVisualKind")
        if not self.summary.strip():
            raise ValueError("visual analysis summary cannot be empty")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("visual confidence must be between 0 and 1")
        collections = (
            self.nodes,
            self.relations,
            self.ui_elements,
            self.state_changes,
            self.uncertainties,
        )
        if any(not isinstance(items, tuple) for items in collections):
            raise ValueError("visual analysis collections must be tuples")
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
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.state_changes
        ):
            raise ValueError("state_changes must contain non-empty strings")
        if any(
            not isinstance(item, str) or not item.strip()
            for item in self.uncertainties
        ):
            raise ValueError("uncertainties must contain non-empty strings")
        node_ids = {item.node_id for item in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("visual node IDs must be unique")
        if any(
            relation.source_node_id not in node_ids
            or relation.target_node_id not in node_ids
            for relation in self.relations
        ):
            raise ValueError("visual relation points to an unknown node")


@dataclass(frozen=True)
class DocumentVisualElement:
    source: DocumentSourceRef
    analysis: DocumentVisualAnalysis


DocumentElement: TypeAlias = (
    DocumentTextElement
    | DocumentTableElement
    | DocumentImageElement
    | DocumentOcrElement
    | DocumentVisualElement
)


@dataclass(frozen=True)
class DocumentParsingWarning:
    code: DocumentWarningCode
    message: str
    source: DocumentSourceRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, DocumentWarningCode):
            raise ValueError("code must be a DocumentWarningCode")
        if not self.message.strip():
            raise ValueError("warning message cannot be empty")


@dataclass(frozen=True)
class DocumentContent:
    document_id: str
    filename: str
    document_format: DocumentFormat
    extracted_text: str
    elements: tuple[DocumentElement, ...]
    warnings: tuple[DocumentParsingWarning, ...] = ()
    attachments: tuple[DocumentAttachment, ...] = ()
    stats: DocumentParseStats = DocumentParseStats()

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id cannot be empty")
        if not self.filename.strip():
            raise ValueError("filename cannot be empty")
        if not isinstance(self.document_format, DocumentFormat):
            raise ValueError("document_format must be a DocumentFormat")
        if not isinstance(self.extracted_text, str):
            raise ValueError("extracted_text must be a string")
        if not isinstance(self.elements, tuple):
            raise ValueError("elements must be an immutable tuple")
        if not isinstance(self.warnings, tuple):
            raise ValueError("warnings must be an immutable tuple")
        if not isinstance(self.attachments, tuple):
            raise ValueError("attachments must be an immutable tuple")
        if not isinstance(self.stats, DocumentParseStats):
            raise ValueError("stats must be DocumentParseStats")
        source_ids: set[str] = set()
        for index, element in enumerate(self.elements):
            if not isinstance(
                element,
                (
                    DocumentTextElement,
                    DocumentTableElement,
                    DocumentImageElement,
                    DocumentOcrElement,
                    DocumentVisualElement,
                ),
            ):
                raise ValueError("elements must contain document element types")
            if element.source.document_id != self.document_id:
                raise ValueError("element source belongs to another document")
            if element.source.filename != self.filename:
                raise ValueError("element source filename does not match")
            if element.source.element_index != index:
                raise ValueError("element source indexes must be contiguous")
            if element.source.source_id in source_ids:
                raise ValueError("document source IDs must be unique")
            source_ids.add(element.source.source_id)
        for warning in self.warnings:
            if not isinstance(warning, DocumentParsingWarning):
                raise ValueError("warnings must contain parsing warnings")
            if warning.source is None:
                continue
            if warning.source.document_id != self.document_id:
                raise ValueError("warning source belongs to another document")
            if warning.source.filename != self.filename:
                raise ValueError("warning source filename does not match")
            if warning.source.source_id in source_ids:
                raise ValueError("document source IDs must be unique")
            source_ids.add(warning.source.source_id)
        attachment_ids: set[str] = set()
        for attachment in self.attachments:
            if not isinstance(attachment, DocumentAttachment):
                raise ValueError("attachments must contain DocumentAttachment")
            if attachment.attachment_id in attachment_ids:
                raise ValueError("attachment IDs must be unique")
            attachment_ids.add(attachment.attachment_id)
        for element in self.elements:
            if not isinstance(element, DocumentImageElement):
                continue
            prefix = "attachment://"
            if element.image.content_ref.startswith(prefix):
                attachment_id = element.image.content_ref[len(prefix) :]
                if attachment_id not in attachment_ids:
                    raise ValueError("image content_ref points to missing attachment")
        image_ids = {
            element.image.image_id
            for element in self.elements
            if isinstance(element, DocumentImageElement)
        }
        for element in self.elements:
            if (
                isinstance(element, DocumentOcrElement)
                and element.image_id not in image_ids
            ):
                raise ValueError("OCR element points to missing image")
            if (
                isinstance(element, DocumentVisualElement)
                and element.analysis.image_id not in image_ids
            ):
                raise ValueError("visual element points to missing image")

    def to_plain_text(self) -> str:
        """Returns the legacy text view without discarding structured data."""

        return self.extracted_text
