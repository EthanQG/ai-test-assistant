from io import BytesIO
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from documents import DocumentFormat, DocumentTextKind, DocumentWarningCode
from services.document_service import DocumentService


class UploadedRequirement(BytesIO):
    def __init__(self, name: str, content: str | bytes):
        super().__init__(
            content if isinstance(content, bytes) else content.encode("utf-8")
        )
        self.name = name


class DocumentServiceTests(unittest.TestCase):
    def test_uploaded_text_requirement_is_extracted(self):
        uploaded = UploadedRequirement(
            "订单需求.txt",
            "用户提交订单时需要校验库存。",
        )

        result = DocumentService.extract_text(uploaded)

        self.assertEqual(result, "用户提交订单时需要校验库存。")

    def test_uploaded_markdown_requirement_is_extracted(self):
        uploaded = UploadedRequirement(
            "订单需求.md",
            "# 订单需求\n\n库存不足时禁止提交。",
        )

        result = DocumentService.extract_text(uploaded)

        self.assertEqual(
            result,
            "# 订单需求\n\n库存不足时禁止提交。",
        )

    def test_markdown_is_parsed_into_source_aware_ordered_elements(self):
        uploaded = UploadedRequirement(
            "订单需求.md",
            "# 订单需求\n\n- 校验库存\n- 扣减库存\n\n失败时提示用户。",
        )

        content = DocumentService.parse(uploaded)

        self.assertEqual(content.document_format, DocumentFormat.MARKDOWN)
        self.assertEqual(
            [element.kind for element in content.elements],
            [
                DocumentTextKind.TITLE,
                DocumentTextKind.LIST_ITEM,
                DocumentTextKind.LIST_ITEM,
                DocumentTextKind.PARAGRAPH,
            ],
        )
        self.assertEqual(
            [element.source.element_index for element in content.elements],
            [0, 1, 2, 3],
        )
        self.assertTrue(
            all(
                element.source.source_id.startswith(content.document_id)
                for element in content.elements
            )
        )

    def test_same_file_produces_stable_document_and_source_ids(self):
        first = DocumentService.parse(
            UploadedRequirement("需求.txt", "第一段\n\n第二段")
        )
        second = DocumentService.parse(
            UploadedRequirement("需求.txt", "第一段\n\n第二段")
        )

        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(
            [element.source.source_id for element in first.elements],
            [element.source.source_id for element in second.elements],
        )

    def test_empty_text_document_returns_explicit_warning(self):
        content = DocumentService.parse(UploadedRequirement("空需求.txt", ""))

        self.assertEqual(content.elements, ())
        self.assertEqual(
            [warning.code for warning in content.warnings],
            [DocumentWarningCode.EMPTY_DOCUMENT],
        )

    def test_pdf_keeps_page_numbers_and_reports_empty_page(self):
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _: SimpleNamespace(
            pages=[
                SimpleNamespace(extract_text=lambda: "第一页需求"),
                SimpleNamespace(extract_text=lambda: ""),
                SimpleNamespace(extract_text=lambda: "第三页规则"),
            ]
        )

        with patch.dict(sys.modules, {"pypdf": pypdf}):
            content = DocumentService.parse(
                UploadedRequirement("需求.pdf", b"fake-pdf")
            )

        self.assertEqual(content.to_plain_text(), "第一页需求\n\n第三页规则")
        self.assertEqual(
            [element.source.page_number for element in content.elements],
            [1, 3],
        )
        self.assertEqual(content.warnings[0].code, DocumentWarningCode.EMPTY_PAGE)
        self.assertEqual(content.warnings[0].source.page_number, 2)

    def test_docx_keeps_paragraph_types_and_warns_about_deferred_content(self):
        docx = ModuleType("docx")
        docx.Document = lambda _: SimpleNamespace(
            paragraphs=[
                SimpleNamespace(
                    text="支付需求",
                    style=SimpleNamespace(name="Heading 1"),
                ),
                SimpleNamespace(
                    text="支持银行卡支付",
                    style=SimpleNamespace(name="Normal"),
                ),
            ],
            tables=[object()],
            inline_shapes=[object()],
        )

        with patch.dict(sys.modules, {"docx": docx}):
            content = DocumentService.parse(
                UploadedRequirement("需求.docx", b"fake-docx")
            )

        self.assertEqual(
            [element.kind for element in content.elements],
            [DocumentTextKind.TITLE, DocumentTextKind.PARAGRAPH],
        )
        self.assertEqual(
            [warning.code for warning in content.warnings],
            [
                DocumentWarningCode.TABLE_NOT_EXTRACTED,
                DocumentWarningCode.IMAGE_NOT_EXTRACTED,
            ],
        )

    def test_unsupported_format_and_parser_errors_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "不支持的文件格式"):
            DocumentService.parse(UploadedRequirement("需求.xlsx", b"data"))

        with self.assertRaisesRegex(ValueError, "UnicodeDecodeError"):
            DocumentService.parse(UploadedRequirement("需求.txt", b"\xff"))


if __name__ == "__main__":
    unittest.main()
