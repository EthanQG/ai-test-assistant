from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.ocr_service import (
    OcrError,
    OcrUnavailableError,
    TesseractOcrEngine,
)


def test_tesseract_ocr_groups_words_and_normalizes_confidence():
    payload = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t95\t退款\n"
        "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t85\t成功\n"
        "5\t1\t1\t1\t2\t1\t0\t0\t1\t1\t60\t待确认\n"
    ).encode()
    completed = SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

    with patch("services.ocr_service.shutil.which", return_value="tesseract"), patch(
        "services.ocr_service.subprocess.run", return_value=completed
    ) as run:
        lines = TesseractOcrEngine().recognize(b"png", "image/png")

    assert [line.text for line in lines] == ["退款 成功", "待确认"]
    assert lines[0].confidence == pytest.approx(0.90)
    assert lines[1].confidence == pytest.approx(0.60)
    assert run.call_args.kwargs["input"] == b"png"


def test_tesseract_ocr_reports_unavailable_runtime_without_subprocess_call():
    with patch("services.ocr_service.shutil.which", return_value=None), patch(
        "services.ocr_service.subprocess.run"
    ) as run:
        with pytest.raises(OcrUnavailableError, match="not available"):
            TesseractOcrEngine().recognize(b"png", "image/png")

    run.assert_not_called()


def test_tesseract_ocr_rejects_failed_or_invalid_tsv_response():
    with patch("services.ocr_service.shutil.which", return_value="tesseract"), patch(
        "services.ocr_service.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=b"error"),
    ):
        with pytest.raises(OcrError, match="execution failed"):
            TesseractOcrEngine().recognize(b"png", "image/png")

    with pytest.raises(OcrError, match="required columns"):
        TesseractOcrEngine._parse_tsv("text\nhello")
