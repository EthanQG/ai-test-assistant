from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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


DocumentElement: TypeAlias = (
    DocumentTextElement | DocumentTableElement | DocumentImageElement
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
        source_ids: set[str] = set()
        for index, element in enumerate(self.elements):
            if not isinstance(
                element,
                (DocumentTextElement, DocumentTableElement, DocumentImageElement),
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

    def to_plain_text(self) -> str:
        """Returns the legacy text view without discarding structured data."""

        return self.extracted_text
