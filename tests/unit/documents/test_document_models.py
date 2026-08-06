from dataclasses import FrozenInstanceError
import hashlib

import pytest

from documents import (
    DocumentContent,
    DocumentAttachment,
    DocumentFormat,
    DocumentImage,
    DocumentImageElement,
    DocumentSourceRef,
    DocumentTable,
    DocumentTableElement,
    DocumentTextElement,
    DocumentTextKind,
    DocumentParseStats,
)


def _source(index=0, *, document_id="doc-1"):
    return DocumentSourceRef(
        source_id=f"{document_id}:element:{index}",
        document_id=document_id,
        filename="需求.docx",
        element_index=index,
        page_number=1,
    )


def test_document_content_expresses_text_table_image_and_source_order():
    image_bytes = b"image-bytes"
    attachment_id = "doc-1:attachment:image"
    elements = (
        DocumentTextElement(
            source=_source(0),
            kind=DocumentTextKind.TITLE,
            text="退款规则",
        ),
        DocumentTableElement(
            source=_source(1),
            table=DocumentTable(
                rows=(("状态", "行为"), ("已支付", "原路退款")),
                caption="退款状态表",
            ),
        ),
        DocumentImageElement(
            source=_source(2),
            image=DocumentImage(
                image_id="image-1",
                mime_type="image/png",
                content_ref=f"attachment://{attachment_id}",
                caption="退款流程图",
                width=800,
                height=600,
            ),
        ),
    )

    content = DocumentContent(
        document_id="doc-1",
        filename="需求.docx",
        document_format=DocumentFormat.DOCX,
        extracted_text="退款规则",
        elements=elements,
        attachments=(
            DocumentAttachment(
                attachment_id=attachment_id,
                mime_type="image/png",
                content=image_bytes,
                sha256=hashlib.sha256(image_bytes).hexdigest(),
            ),
        ),
        stats=DocumentParseStats(
            page_count=1,
            text_element_count=1,
            table_count=1,
            image_count=1,
        ),
    )

    assert content.elements == elements
    assert content.to_plain_text() == "退款规则"
    assert content.elements[1].table.rows[1][1] == "原路退款"
    assert content.elements[2].image.content_ref.endswith(attachment_id)
    assert content.attachments[0].content == image_bytes
    assert content.stats.table_count == 1


def test_document_models_are_immutable_and_use_immutable_nested_rows():
    table = DocumentTable(rows=(("字段", "说明"),))

    with pytest.raises(FrozenInstanceError):
        table.caption = "修改"
    with pytest.raises(TypeError):
        table.rows[0][0] = "修改"


def test_document_content_rejects_foreign_or_out_of_order_sources():
    foreign = DocumentTextElement(
        source=_source(0, document_id="another-document"),
        kind=DocumentTextKind.PARAGRAPH,
        text="内容",
    )
    with pytest.raises(ValueError, match="another document"):
        DocumentContent(
            document_id="doc-1",
            filename="需求.docx",
            document_format=DocumentFormat.DOCX,
            extracted_text="内容",
            elements=(foreign,),
        )

    out_of_order = DocumentTextElement(
        source=_source(2),
        kind=DocumentTextKind.PARAGRAPH,
        text="内容",
    )
    with pytest.raises(ValueError, match="contiguous"):
        DocumentContent(
            document_id="doc-1",
            filename="需求.docx",
            document_format=DocumentFormat.DOCX,
            extracted_text="内容",
            elements=(out_of_order,),
        )


def test_table_and_source_validation_reject_invalid_structure():
    with pytest.raises(ValueError, match="equal width"):
        DocumentTable(rows=(("a", "b"), ("c",)))
    with pytest.raises(ValueError, match="immutable tuples"):
        DocumentTable(rows=[["a", "b"]])
    with pytest.raises(ValueError, match="page_number"):
        DocumentSourceRef(
            source_id="source-1",
            document_id="doc-1",
            filename="需求.pdf",
            element_index=0,
            page_number=0,
        )


def test_image_attachment_reference_must_resolve():
    image = DocumentImageElement(
        source=_source(0),
        image=DocumentImage(
            image_id="image-1",
            mime_type="image/png",
            content_ref="attachment://missing",
        ),
    )

    with pytest.raises(ValueError, match="missing attachment"):
        DocumentContent(
            document_id="doc-1",
            filename="需求.docx",
            document_format=DocumentFormat.DOCX,
            extracted_text="需求",
            elements=(image,),
        )
