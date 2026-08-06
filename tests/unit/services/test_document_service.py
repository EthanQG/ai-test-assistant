from io import BytesIO
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from documents import (
    DocumentFormat,
    DocumentImageElement,
    DocumentTableElement,
    DocumentTextElement,
    DocumentTextKind,
    DocumentWarningCode,
)
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
        class Pdf:
            pages = [
                SimpleNamespace(
                    extract_text=lambda: "第一页需求",
                    extract_tables=lambda: [],
                    curves=[],
                ),
                SimpleNamespace(
                    extract_text=lambda: "",
                    extract_tables=lambda: [],
                    curves=[],
                ),
                SimpleNamespace(
                    extract_text=lambda: "第三页规则",
                    extract_tables=lambda: [],
                    curves=[],
                ),
            ]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

        pdfplumber = ModuleType("pdfplumber")
        pdfplumber.open = lambda _: Pdf()
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _: SimpleNamespace(
            pages=[
                SimpleNamespace(images=[]),
                SimpleNamespace(images=[]),
                SimpleNamespace(images=[]),
            ]
        )

        with patch.dict(
            sys.modules, {"pdfplumber": pdfplumber, "pypdf": pypdf}
        ):
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

    def test_docx_extracts_ordered_paragraph_table_and_embedded_image(self):
        from docx import Document
        from docx.shared import Inches
        from PIL import Image

        image_buffer = BytesIO()
        Image.new("RGB", (8, 6), "blue").save(image_buffer, format="PNG")
        image_buffer.seek(0)
        document = Document()
        document.add_heading("支付需求", level=1)
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "状态"
        table.cell(0, 1).text = "行为"
        table.cell(1, 0).text = "成功"
        table.cell(1, 1).text = "创建订单"
        paragraph = document.add_paragraph("支付流程图")
        paragraph.add_run().add_picture(image_buffer, width=Inches(1))
        payload = BytesIO()
        document.save(payload)

        content = DocumentService.parse(
            UploadedRequirement("需求.docx", payload.getvalue())
        )

        self.assertEqual(
            [type(element) for element in content.elements],
            [
                DocumentTextElement,
                DocumentTableElement,
                DocumentTextElement,
                DocumentImageElement,
            ],
        )
        self.assertEqual(content.elements[0].kind, DocumentTextKind.TITLE)
        self.assertEqual(content.elements[1].table.rows[1][1], "创建订单")
        self.assertEqual(content.elements[3].image.mime_type, "image/png")
        self.assertEqual(len(content.attachments), 1)
        self.assertIn("状态 | 行为", content.to_plain_text())
        self.assertEqual(content.stats.table_count, 1)
        self.assertEqual(content.stats.image_count, 1)

    def test_pdf_extracts_recognizable_table_image_and_vector_warning(self):
        class Pdf:
            pages = [
                SimpleNamespace(
                    extract_text=lambda: "退款规则",
                    extract_tables=lambda: [
                        [["状态", "行为"], ["成功", "原路退款"]]
                    ],
                    curves=[{"object_type": "curve"}],
                )
            ]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

        pdfplumber = ModuleType("pdfplumber")
        pdfplumber.open = lambda _: Pdf()
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _: SimpleNamespace(
            pages=[
                SimpleNamespace(
                    images=[SimpleNamespace(data=b"png", name="figure.png")]
                )
            ]
        )

        with patch.dict(
            sys.modules, {"pdfplumber": pdfplumber, "pypdf": pypdf}
        ):
            content = DocumentService.parse(
                UploadedRequirement("需求.pdf", b"fake-pdf")
            )

        self.assertEqual(content.stats.page_count, 1)
        self.assertEqual(content.stats.table_count, 1)
        self.assertEqual(content.stats.image_count, 1)
        self.assertEqual(content.elements[1].source.page_number, 1)
        self.assertEqual(content.elements[1].table.rows[1][1], "原路退款")
        self.assertEqual(content.attachments[0].content, b"png")
        self.assertIn(
            DocumentWarningCode.PAGE_RENDER_REQUIRED,
            [warning.code for warning in content.warnings],
        )

    def test_oversized_image_is_skipped_with_coverage_warning(self):
        class Pdf:
            pages = [
                SimpleNamespace(
                    extract_text=lambda: "图片需求",
                    extract_tables=lambda: [],
                    curves=[],
                )
            ]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

        pdfplumber = ModuleType("pdfplumber")
        pdfplumber.open = lambda _: Pdf()
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _: SimpleNamespace(
            pages=[
                SimpleNamespace(
                    images=[
                        SimpleNamespace(
                            data=b"x" * (DocumentService._MAX_IMAGE_BYTES + 1),
                            name="large.png",
                        )
                    ]
                )
            ]
        )

        with patch.dict(
            sys.modules, {"pdfplumber": pdfplumber, "pypdf": pypdf}
        ):
            content = DocumentService.parse(
                UploadedRequirement("需求.pdf", b"fake-pdf")
            )

        self.assertEqual(content.attachments, ())
        self.assertEqual(content.stats.image_count, 0)
        self.assertEqual(content.stats.skipped_image_count, 1)
        self.assertIn(
            DocumentWarningCode.IMAGE_TOO_LARGE,
            [warning.code for warning in content.warnings],
        )

    def test_pdf_table_failure_is_reported_without_losing_page_text(self):
        def fail_tables():
            raise RuntimeError("table parser failed")

        class Pdf:
            pages = [
                SimpleNamespace(
                    extract_text=lambda: "订单需求",
                    extract_tables=fail_tables,
                    curves=[],
                )
            ]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

        pdfplumber = ModuleType("pdfplumber")
        pdfplumber.open = lambda _: Pdf()
        pypdf = ModuleType("pypdf")
        pypdf.PdfReader = lambda _: SimpleNamespace(
            pages=[SimpleNamespace(images=[])]
        )

        with patch.dict(
            sys.modules, {"pdfplumber": pdfplumber, "pypdf": pypdf}
        ):
            content = DocumentService.parse(
                UploadedRequirement("需求.pdf", b"fake-pdf")
            )

        self.assertEqual(content.to_plain_text(), "订单需求")
        self.assertEqual(content.stats.skipped_table_count, 1)
        self.assertIn(
            DocumentWarningCode.TABLE_EXTRACTION_FAILED,
            [warning.code for warning in content.warnings],
        )

    def test_unsupported_format_and_parser_errors_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "不支持的文件格式"):
            DocumentService.parse(UploadedRequirement("需求.xlsx", b"data"))

        with self.assertRaisesRegex(ValueError, "UnicodeDecodeError"):
            DocumentService.parse(UploadedRequirement("需求.txt", b"\xff"))


if __name__ == "__main__":
    unittest.main()
