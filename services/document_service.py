from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from io import BytesIO
from typing import Iterable

from documents import (
    DocumentAttachment,
    DocumentContent,
    DocumentElement,
    DocumentFormat,
    DocumentImage,
    DocumentImageElement,
    DocumentParseStats,
    DocumentParsingWarning,
    DocumentSourceRef,
    DocumentTable,
    DocumentTableElement,
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
    _MAX_IMAGE_COUNT = 20
    _MAX_IMAGE_BYTES = 5 * 1024 * 1024
    _MAX_TOTAL_IMAGE_BYTES = 25 * 1024 * 1024

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
        import pdfplumber
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
        elements: list[DocumentElement] = []
        warnings: list[DocumentParsingWarning] = []
        attachments: list[DocumentAttachment] = []
        page_texts: list[str] = []
        skipped_tables = 0
        skipped_images = 0
        total_image_bytes = 0
        with pdfplumber.open(BytesIO(payload)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                cleaned = page_text.strip()
                if cleaned:
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
                else:
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
                try:
                    for raw_table in page.extract_tables() or []:
                        table = cls._table_from_rows(raw_table)
                        if table is None:
                            continue
                        elements.append(
                            DocumentTableElement(
                                source=cls._source(
                                    filename,
                                    document_id,
                                    len(elements),
                                    page_number=page_number,
                                ),
                                table=table,
                            )
                        )
                        if not cleaned:
                            page_texts.append(cls._table_plain_text(table))
                except Exception:
                    skipped_tables += 1
                    warnings.append(
                        cls._warning(
                            filename,
                            document_id,
                            len(elements),
                            DocumentWarningCode.TABLE_EXTRACTION_FAILED,
                            f"第{page_number}页表格提取失败，已保留页面来源",
                            page_number=page_number,
                            warning_index=len(warnings),
                        )
                    )
                if getattr(page, "curves", None):
                    warnings.append(
                        cls._warning(
                            filename,
                            document_id,
                            len(elements),
                            DocumentWarningCode.PAGE_RENDER_REQUIRED,
                            f"第{page_number}页包含矢量图形，后续视觉阶段需按整页渲染",
                            page_number=page_number,
                            warning_index=len(warnings),
                        )
                    )

                pdf_page = reader.pages[page_number - 1]
                try:
                    page_images = list(getattr(pdf_page, "images", ()) or ())
                except Exception:
                    page_images = []
                    skipped_images += 1
                    warnings.append(
                        cls._warning(
                            filename,
                            document_id,
                            len(elements),
                            DocumentWarningCode.IMAGE_EXTRACTION_FAILED,
                            f"第{page_number}页内嵌图片提取失败",
                            page_number=page_number,
                            warning_index=len(warnings),
                        )
                    )
                for image in page_images:
                    blob = getattr(image, "data", b"")
                    name = str(getattr(image, "name", "image.bin"))
                    accepted, total_image_bytes = cls._append_image(
                        filename=filename,
                        document_id=document_id,
                        page_number=page_number,
                        name=name,
                        blob=blob,
                        mime_type=cls._image_mime_type(name, image),
                        elements=elements,
                        attachments=attachments,
                        warnings=warnings,
                        total_image_bytes=total_image_bytes,
                    )
                    if not accepted:
                        skipped_images += 1
        return cls._content(
            filename,
            document_id,
            DocumentFormat.PDF,
            "\n\n".join(page_texts),
            elements,
            warnings,
            attachments=attachments,
            page_count=len(reader.pages),
            skipped_table_count=skipped_tables,
            skipped_image_count=skipped_images,
        )

    @classmethod
    def _parse_docx(
        cls,
        filename: str,
        document_id: str,
        payload: bytes,
    ) -> DocumentContent:
        from docx import Document

        from docx.table import Table

        document = Document(BytesIO(payload))
        elements: list[DocumentElement] = []
        plain_text_parts: list[str] = []
        warnings: list[DocumentParsingWarning] = []
        attachments: list[DocumentAttachment] = []
        total_image_bytes = 0
        skipped_images = 0
        blocks = (
            document.iter_inner_content()
            if hasattr(document, "iter_inner_content")
            else list(getattr(document, "paragraphs", ()))
            + list(getattr(document, "tables", ()))
        )
        for block in blocks:
            if isinstance(block, Table) or hasattr(block, "rows"):
                table = cls._table_from_rows(
                    [[cell.text for cell in row.cells] for row in block.rows]
                )
                if table is not None:
                    elements.append(
                        DocumentTableElement(
                            source=cls._source(
                                filename, document_id, len(elements)
                            ),
                            table=table,
                        )
                    )
                    plain_text_parts.append(cls._table_plain_text(table))
                continue

            text = str(getattr(block, "text", "")).strip()
            if text:
                style_name = str(
                    getattr(getattr(block, "style", None), "name", "")
                )
                kind = cls._docx_text_kind(style_name)
                elements.extend(
                    cls._text_elements(
                        filename,
                        document_id,
                        [(kind, text)],
                        start_index=len(elements),
                    )
                )
                plain_text_parts.append(text)
            for name, mime_type, blob in cls._docx_paragraph_images(
                document, block
            ):
                accepted, total_image_bytes = cls._append_image(
                    filename=filename,
                    document_id=document_id,
                    page_number=None,
                    name=name,
                    blob=blob,
                    mime_type=mime_type,
                    elements=elements,
                    attachments=attachments,
                    warnings=warnings,
                    total_image_bytes=total_image_bytes,
                )
                if not accepted:
                    skipped_images += 1
        return cls._content(
            filename,
            document_id,
            DocumentFormat.DOCX,
            "\n\n".join(plain_text_parts),
            elements,
            warnings,
            attachments=attachments,
            page_count=1,
            skipped_image_count=skipped_images,
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

    @staticmethod
    def _table_from_rows(rows) -> DocumentTable | None:
        normalized = [
            tuple("" if cell is None else str(cell).strip() for cell in row)
            for row in rows
            if row is not None
        ]
        normalized = [row for row in normalized if any(row)]
        if not normalized:
            return None
        width = max(len(row) for row in normalized)
        if width == 0:
            return None
        padded = tuple(row + ("",) * (width - len(row)) for row in normalized)
        return DocumentTable(rows=padded)

    @staticmethod
    def _table_plain_text(table: DocumentTable) -> str:
        return "\n".join(" | ".join(row) for row in table.rows)

    @staticmethod
    def _docx_paragraph_images(document, paragraph):
        from docx.oxml.ns import qn

        for run in getattr(paragraph, "runs", ()):
            element = getattr(run, "_element", None)
            if element is None:
                continue
            for blip in element.xpath(".//a:blip"):
                relationship_id = blip.get(qn("r:embed"))
                part = document.part.related_parts.get(relationship_id)
                blob = getattr(part, "blob", b"")
                if not blob:
                    continue
                name = str(getattr(part, "partname", "image.bin")).rsplit(
                    "/", 1
                )[-1]
                yield name, str(
                    getattr(part, "content_type", "application/octet-stream")
                ), blob

    @classmethod
    def _append_image(
        cls,
        *,
        filename: str,
        document_id: str,
        page_number: int | None,
        name: str,
        blob: bytes,
        mime_type: str,
        elements: list[DocumentElement],
        attachments: list[DocumentAttachment],
        warnings: list[DocumentParsingWarning],
        total_image_bytes: int,
    ) -> tuple[bool, int]:
        if not isinstance(blob, bytes) or not blob:
            warnings.append(
                cls._warning(
                    filename,
                    document_id,
                    len(elements),
                    DocumentWarningCode.IMAGE_EXTRACTION_FAILED,
                    "图片内容为空，已跳过该图片",
                    page_number=page_number,
                    warning_index=len(warnings),
                )
            )
            return False, total_image_bytes
        if len(blob) > cls._MAX_IMAGE_BYTES:
            warnings.append(
                cls._warning(
                    filename,
                    document_id,
                    len(elements),
                    DocumentWarningCode.IMAGE_TOO_LARGE,
                    "单张图片超过5MB限制，已保留警告并跳过",
                    page_number=page_number,
                    warning_index=len(warnings),
                )
            )
            return False, total_image_bytes
        if (
            sum(
                isinstance(element, DocumentImageElement)
                for element in elements
            )
            >= cls._MAX_IMAGE_COUNT
            or total_image_bytes + len(blob) > cls._MAX_TOTAL_IMAGE_BYTES
        ):
            warnings.append(
                cls._warning(
                    filename,
                    document_id,
                    len(elements),
                    DocumentWarningCode.IMAGE_LIMIT_EXCEEDED,
                    "文档图片数量或总大小超过解析限制，剩余图片已跳过",
                    page_number=page_number,
                    warning_index=len(warnings),
                )
            )
            return False, total_image_bytes

        digest = hashlib.sha256(blob).hexdigest()
        attachment_id = f"{document_id}:attachment:{digest[:16]}"
        if not any(item.attachment_id == attachment_id for item in attachments):
            attachments.append(
                DocumentAttachment(
                    attachment_id=attachment_id,
                    mime_type=mime_type,
                    content=blob,
                    sha256=digest,
                )
            )
            total_image_bytes += len(blob)
        image_index = sum(
            isinstance(element, DocumentImageElement) for element in elements
        )
        elements.append(
            DocumentImageElement(
                source=cls._source(
                    filename,
                    document_id,
                    len(elements),
                    page_number=page_number,
                ),
                image=DocumentImage(
                    image_id=f"{document_id}:image:{image_index}",
                    mime_type=mime_type,
                    content_ref=f"attachment://{attachment_id}",
                    caption=name,
                ),
            )
        )
        return True, total_image_bytes

    @staticmethod
    def _image_mime_type(name: str, image) -> str:
        guessed = mimetypes.guess_type(name)[0]
        if guessed:
            return guessed
        pil_image = getattr(image, "image", None)
        image_format = str(getattr(pil_image, "format", "")).lower()
        if image_format:
            return f"image/{'jpeg' if image_format == 'jpg' else image_format}"
        return "application/octet-stream"

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
        elements: Iterable[DocumentElement],
        warnings: Iterable[DocumentParsingWarning],
        *,
        attachments: Iterable[DocumentAttachment] = (),
        page_count: int = 0,
        skipped_table_count: int = 0,
        skipped_image_count: int = 0,
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
        attachment_tuple = tuple(attachments)
        return DocumentContent(
            document_id=document_id,
            filename=filename,
            document_format=document_format,
            extracted_text=extracted_text,
            elements=element_tuple,
            warnings=tuple(warning_list),
            attachments=attachment_tuple,
            stats=DocumentParseStats(
                page_count=page_count,
                text_element_count=sum(
                    isinstance(element, DocumentTextElement)
                    for element in element_tuple
                ),
                table_count=sum(
                    isinstance(element, DocumentTableElement)
                    for element in element_tuple
                ),
                image_count=sum(
                    isinstance(element, DocumentImageElement)
                    for element in element_tuple
                ),
                warning_count=len(warning_list),
                skipped_table_count=skipped_table_count,
                skipped_image_count=skipped_image_count,
            ),
        )
