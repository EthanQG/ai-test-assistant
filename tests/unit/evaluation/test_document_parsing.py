import json
from io import BytesIO
from pathlib import Path

from documents import (
    DocumentContent,
    DocumentFormat,
    DocumentImage,
    DocumentImageElement,
    DocumentOcrDisposition,
    DocumentOcrElement,
    DocumentSourceRef,
)
from evaluation.document_parsing import (
    run_document_parsing_evaluation,
    score_content,
)
from services.document_service import DocumentService


FIXTURE_DIR = Path(__file__).parents[3] / "evaluation" / "fixtures"
MANIFEST_PATH = FIXTURE_DIR / "gold_v1.json"


class UploadedFixture(BytesIO):
    def __init__(self, path: Path):
        super().__init__(path.read_bytes())
        self.name = path.name


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fixture(target: str) -> dict:
    return next(
        item
        for item in _manifest()["fixtures"]
        if item["evaluation_target"] == target
    )


def _source(filename: str, index: int) -> DocumentSourceRef:
    return DocumentSourceRef(
        source_id=f"doc-{filename}:element:{index}",
        document_id=f"doc-{filename}",
        filename=filename,
        element_index=index,
    )


def _ocr_content(filename: str, text: str) -> DocumentContent:
    image_id = f"doc-{filename}:image:1"
    elements = [
        DocumentImageElement(
            source=_source(filename, 0),
            image=DocumentImage(
                image_id=image_id,
                mime_type="image/png",
                content_ref="memory://fixture",
            ),
        )
    ]
    elements.extend(
        DocumentOcrElement(
            source=_source(filename, index),
            text=line,
            confidence=0.95,
            image_id=image_id,
            disposition=DocumentOcrDisposition.ACCEPTED,
        )
        for index, line in enumerate(text.splitlines(), start=1)
    )
    return DocumentContent(
        document_id=f"doc-{filename}",
        filename=filename,
        document_format=DocumentFormat.PDF,
        extracted_text=text,
        elements=tuple(elements),
    )


def test_native_pdf_is_scored_against_real_document_parser_output():
    fixture = _fixture("native_text")
    content = DocumentService.parse(
        UploadedFixture(FIXTURE_DIR / fixture["path"])
    )

    score = score_content(fixture, content)

    assert score.metrics == {
        "text_line_recall": 1.0,
        "character_accuracy": 1.0,
    }
    assert score.missing_items == ()


def test_docx_table_is_scored_by_position_against_real_parser_output():
    fixture = _fixture("table_structure")
    content = DocumentService.parse(
        UploadedFixture(FIXTURE_DIR / fixture["path"])
    )

    score = score_content(fixture, content)

    assert score.metrics == {
        "text_line_recall": 1.0,
        "table_cell_accuracy": 1.0,
    }
    assert score.missing_items == ()


def test_ocr_score_reports_missing_line_and_character_difference():
    fixture = _fixture("ocr_text")
    actual_text = "\n".join(fixture["gold"]["text_lines"]).replace(
        "退款单号", "退款编号"
    )

    score = score_content(
        fixture,
        _ocr_content("scanned_refund_requirement.pdf", actual_text),
    )

    assert score.metrics["text_line_recall"] == 0.8
    assert 0 < score.metrics["character_accuracy"] < 1
    assert score.missing_items == (
        "退款成功后记录退款单号和累计退款金额。",
    )


def test_runner_evaluates_only_supported_targets_without_external_services():
    scanned_fixture = _fixture("ocr_text")
    scanned_text = "\n".join(scanned_fixture["gold"]["text_lines"])

    def fake_ocr_parser(uploaded):
        if uploaded.name == "scanned_refund_requirement.pdf":
            return _ocr_content(uploaded.name, scanned_text)
        return DocumentService.parse(uploaded)

    report = run_document_parsing_evaluation(
        MANIFEST_PATH,
        parser=fake_ocr_parser,
    )

    assert report["evaluated_fixture_count"] == 3
    assert [item["evaluation_target"] for item in report["results"]] == [
        "native_text",
        "table_structure",
        "ocr_text",
    ]
    assert all(not item["missing_items"] for item in report["results"])
