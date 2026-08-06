from __future__ import annotations

import hashlib
import os
import re
from io import BytesIO
from typing import Iterable

from documents import (
    DocumentContent,
    DocumentFormat,
    DocumentParsingWarning,
    DocumentSourceRef,
    DocumentTextElement,
    DocumentTextKind,
    DocumentWarningCode,
)


class DocumentService:
    """Parses uploaded requirements into a source-aware document model."""

    _FORMATS = {
        ".txt": DocumentFormat.TEXT,
        ".md": DocumentFormat.MARKDOWN,
        ".pdf": DocumentFormat.PDF,
        ".docx": DocumentFormat.DOCX,
    }

    @classmethod
    def parse(cls, uploaded_file) -> DocumentContent:
        if uploaded_file is None:
            raise ValueError("上传文件不能为空")
        filename = str(getattr(uploaded_file, "name", "")).strip()
        if not filename:
            raise ValueError("上传文件缺少文件名")
        extension = os.path.splitext(filename)[1].lower()
        document_format = cls._FORMATS.get(extension)
        if document_format is None:
            raise ValueError(f"不支持的文件格式: {extension}")
        try:
            payload = uploaded_file.read()
            if not isinstance(payload, bytes):
                raise TypeError("上传文件必须提供二进制内容")
            identity = filename.encode("utf-8") + b"\0" + payload
            document_id = "doc-" + hashlib.sha256(identity).hexdigest()
            if document_format in {DocumentFormat.TEXT, DocumentFormat.MARKDOWN}:
                return cls._parse_text_document(
                    filename,
                    document_id,
                    document_format,
                    payload,
                )
            if document_format is DocumentFormat.PDF:
                return cls._parse_pdf(filename, document_id, payload)
            return cls._parse_docx(filename, document_id, payload)
        except Exception as exc:
            raise ValueError(f"文件解析失败: {type(exc).__name__}") from exc

    @classmethod
    def extract_text(cls, uploaded_file) -> str:
        """Compatibility view used by the current Application Service."""

        if uploaded_file is None:
            return ""
        return cls.parse(uploaded_file).to_plain_text()

    @classmethod
    def _parse_text_document(
        cls,
        filename: str,
        document_id: str,
        document_format: DocumentFormat,
        payload: bytes,
    ) -> DocumentContent:
        text = payload.decode("utf-8")
        blocks = (
            cls._markdown_blocks(text)
            if document_format is DocumentFormat.MARKDOWN
            else [
                (DocumentTextKind.PARAGRAPH, block)
                for block in re.split(r"\r?\n\s*\r?\n", text)
                if block.strip()
            ]
        )
        elements = cls._text_elements(
            filename,
            document_id,
            blocks,
        )
        return cls._content(
            filename,
            document_id,
            document_format,
            text,
            elements,
            (),
        )

    @classmethod
    def _parse_pdf(
        cls,
        filename: str,
        document_id: str,
        payload: bytes,
    ) -> DocumentContent:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
        elements: list[DocumentTextElement] = []
        warnings: list[DocumentParsingWarning] = []
        page_texts: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                warnings.append(
                    cls._warning(
                        filename,
                        document_id,
                        len(elements),
                        DocumentWarningCode.EMPTY_PAGE,
                        f"第{page_number}页没有可提取的文本层",
                        page_number=page_number,
                        warning_index=len(warnings),
                    )
                )
                continue
            cleaned = page_text.strip()
            page_texts.append(cleaned)
            blocks = [
                (DocumentTextKind.PARAGRAPH, block)
                for block in re.split(r"\r?\n\s*\r?\n", cleaned)
                if block.strip()
            ]
            elements.extend(
                cls._text_elements(
                    filename,
                    document_id,
                    blocks,
                    start_index=len(elements),
                    page_number=page_number,
                )
            )
        return cls._content(
            filename,
            document_id,
            DocumentFormat.PDF,
            "\n\n".join(page_texts),
            elements,
            warnings,
        )

    @classmethod
    def _parse_docx(
        cls,
        filename: str,
        document_id: str,
        payload: bytes,
    ) -> DocumentContent:
        from docx import Document

        document = Document(BytesIO(payload))
        elements: list[DocumentTextElement] = []
        paragraphs: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = str(getattr(getattr(paragraph, "style", None), "name", ""))
            kind = cls._docx_text_kind(style_name)
            elements.extend(
                cls._text_elements(
                    filename,
                    document_id,
                    [(kind, text)],
                    start_index=len(elements),
                )
            )
            paragraphs.append(text)

        warnings: list[DocumentParsingWarning] = []
        if getattr(document, "tables", ()):
            warnings.append(
                cls._warning(
                    filename,
                    document_id,
                    len(elements),
                    DocumentWarningCode.TABLE_NOT_EXTRACTED,
                    "检测到DOCX表格；阶段2.15.1尚未提取表格内容",
                    warning_index=len(warnings),
                )
            )
        if getattr(document, "inline_shapes", ()):
            warnings.append(
                cls._warning(
                    filename,
                    document_id,
                    len(elements),
                    DocumentWarningCode.IMAGE_NOT_EXTRACTED,
                    "检测到DOCX内嵌图片；阶段2.15.1尚未解析图片内容",
                    warning_index=len(warnings),
                )
            )
        return cls._content(
            filename,
            document_id,
            DocumentFormat.DOCX,
            "\n\n".join(paragraphs),
            elements,
            warnings,
        )

    @staticmethod
    def _markdown_blocks(text: str) -> list[tuple[DocumentTextKind, str]]:
        blocks: list[tuple[DocumentTextKind, str]] = []
        paragraph_lines: list[str] = []

        def flush_paragraph() -> None:
            if paragraph_lines:
                blocks.append(
                    (DocumentTextKind.PARAGRAPH, "\n".join(paragraph_lines))
                )
                paragraph_lines.clear()

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
            elif re.match(r"^#{1,6}\s+", stripped):
                flush_paragraph()
                blocks.append((DocumentTextKind.TITLE, stripped))
            elif re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", stripped):
                flush_paragraph()
                blocks.append((DocumentTextKind.LIST_ITEM, stripped))
            else:
                paragraph_lines.append(line)
        flush_paragraph()
        return blocks

    @staticmethod
    def _docx_text_kind(style_name: str) -> DocumentTextKind:
        normalized = style_name.casefold()
        if normalized.startswith("title") or normalized.startswith("heading"):
            return DocumentTextKind.TITLE
        if "list" in normalized:
            return DocumentTextKind.LIST_ITEM
        return DocumentTextKind.PARAGRAPH

    @classmethod
    def _text_elements(
        cls,
        filename: str,
        document_id: str,
        blocks: Iterable[tuple[DocumentTextKind, str]],
        *,
        start_index: int = 0,
        page_number: int | None = None,
    ) -> list[DocumentTextElement]:
        elements: list[DocumentTextElement] = []
        for offset, (kind, text) in enumerate(blocks):
            index = start_index + offset
            elements.append(
                DocumentTextElement(
                    source=cls._source(
                        filename,
                        document_id,
                        index,
                        page_number=page_number,
                    ),
                    kind=kind,
                    text=text,
                )
            )
        return elements

    @staticmethod
    def _source(
        filename: str,
        document_id: str,
        element_index: int,
        *,
        page_number: int | None = None,
    ) -> DocumentSourceRef:
        return DocumentSourceRef(
            source_id=f"{document_id}:element:{element_index}",
            document_id=document_id,
            filename=filename,
            element_index=element_index,
            page_number=page_number,
        )

    @staticmethod
    def _warning(
        filename: str,
        document_id: str,
        element_index: int,
        code: DocumentWarningCode,
        message: str,
        *,
        page_number: int | None = None,
        warning_index: int,
    ) -> DocumentParsingWarning:
        return DocumentParsingWarning(
            code=code,
            message=message,
            source=DocumentSourceRef(
                source_id=f"{document_id}:warning:{warning_index}",
                document_id=document_id,
                filename=filename,
                element_index=element_index,
                page_number=page_number,
            ),
        )

    @classmethod
    def _content(
        cls,
        filename: str,
        document_id: str,
        document_format: DocumentFormat,
        extracted_text: str,
        elements: Iterable[DocumentTextElement],
        warnings: Iterable[DocumentParsingWarning],
    ) -> DocumentContent:
        element_tuple = tuple(elements)
        warning_list = list(warnings)
        if not extracted_text.strip():
            warning_list.append(
                cls._warning(
                    filename,
                    document_id,
                    len(element_tuple),
                    DocumentWarningCode.EMPTY_DOCUMENT,
                    "文档没有可供需求分析使用的文字内容",
                    warning_index=len(warning_list),
                )
            )
        return DocumentContent(
            document_id=document_id,
            filename=filename,
            document_format=document_format,
            extracted_text=extracted_text,
            elements=element_tuple,
            warnings=tuple(warning_list),
        )
