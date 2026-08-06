from dataclasses import FrozenInstanceError

import pytest

from documents import (
    DocumentContent,
    DocumentFormat,
    DocumentImage,
    DocumentImageElement,
    DocumentSourceRef,
    DocumentTable,
    DocumentTableElement,
    DocumentTextElement,
    DocumentTextKind,
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
                content_ref="document://doc-1/images/1",
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
    )

    assert content.elements == elements
    assert content.to_plain_text() == "退款规则"
    assert content.elements[1].table.rows[1][1] == "原路退款"
    assert content.elements[2].image.content_ref.endswith("/images/1")


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
