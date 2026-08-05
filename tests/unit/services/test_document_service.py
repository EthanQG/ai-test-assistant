from io import BytesIO
import unittest

from services.document_service import DocumentService


class UploadedRequirement(BytesIO):
    def __init__(self, name: str, content: str):
        super().__init__(content.encode("utf-8"))
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


if __name__ == "__main__":
    unittest.main()
