from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from time import perf_counter
from typing import Protocol

from utils.telemetry import (
    MetricErrorCategory,
    record_service_call,
    service_metric,
    utc_now,
)


class OcrError(RuntimeError):
    """Base error raised by an OCR adapter."""


class OcrUnavailableError(OcrError):
    """Raised when the configured OCR runtime is unavailable."""


@dataclass(frozen=True)
class OcrTextLine:
    text: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("OCR text line cannot be empty")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1:
            raise ValueError("OCR confidence must be between 0 and 1")


class OcrEngine(Protocol):
    def recognize(
        self, image_bytes: bytes, mime_type: str
    ) -> tuple[OcrTextLine, ...]:
        """Recognizes ordered text lines without mutating document state."""


class TesseractOcrEngine:
    """Subprocess adapter around a locally installed Tesseract runtime."""

    def __init__(
        self,
        command: str = "tesseract",
        languages: str = "chi_sim+eng",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._command = command.strip()
        self._languages = languages.strip()
        self._timeout_seconds = timeout_seconds
        if not self._command:
            raise ValueError("Tesseract command cannot be empty")
        if not self._languages:
            raise ValueError("OCR languages cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("OCR timeout must be positive")

    @classmethod
    def from_environment(cls) -> "TesseractOcrEngine":
        return cls(
            command=os.getenv("TESSERACT_CMD", "tesseract"),
            languages=os.getenv("OCR_LANGUAGES", "chi_sim+eng"),
            timeout_seconds=float(os.getenv("OCR_TIMEOUT_SECONDS", "30")),
        )

    def recognize(
        self, image_bytes: bytes, mime_type: str
    ) -> tuple[OcrTextLine, ...]:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise ValueError("OCR image content must be non-empty bytes")
        started_at = utc_now()
        started_counter = perf_counter()
        try:
            executable = shutil.which(self._command)
            if executable is None:
                raise OcrUnavailableError(
                    "Tesseract executable is not available"
                )
            completed = subprocess.run(
                [
                    executable,
                    "stdin",
                    "stdout",
                    "-l",
                    self._languages,
                    "tsv",
                ],
                input=image_bytes,
                capture_output=True,
                check=False,
                timeout=self._timeout_seconds,
            )
            if completed.returncode != 0:
                raise OcrError("Tesseract OCR execution failed")
            result = self._parse_tsv(
                completed.stdout.decode("utf-8", errors="replace")
            )
            record_service_call(
                service_metric(
                    operation="recognize_image",
                    dependency="ocr",
                    started_at=started_at,
                    started_counter=started_counter,
                    succeeded=True,
                    output_chars=sum(len(line.text) for line in result),
                    metadata={
                        "engine": "tesseract",
                        "input_bytes": len(image_bytes),
                        "line_count": len(result),
                        "mime_type": mime_type,
                    },
                )
            )
            return result
        except Exception as exc:
            error = (
                OcrError("Tesseract OCR timed out")
                if isinstance(exc, subprocess.TimeoutExpired)
                else exc
            )
            record_service_call(
                service_metric(
                    operation="recognize_image",
                    dependency="ocr",
                    started_at=started_at,
                    started_counter=started_counter,
                    succeeded=False,
                    error=error,
                    error_category=(
                        MetricErrorCategory.TIMEOUT
                        if isinstance(exc, subprocess.TimeoutExpired)
                        else MetricErrorCategory.OCR
                    ),
                    metadata={
                        "engine": "tesseract",
                        "input_bytes": len(image_bytes),
                        "mime_type": mime_type,
                    },
                )
            )
            if isinstance(exc, subprocess.TimeoutExpired):
                raise error from exc
            raise

    @staticmethod
    def _parse_tsv(payload: str) -> tuple[OcrTextLine, ...]:
        groups: dict[tuple[str, str, str], list[tuple[str, float]]] = {}
        lines = payload.splitlines()
        if not lines:
            return ()
        headers = lines[0].split("\t")
        indexes = {name: index for index, name in enumerate(headers)}
        required = {"block_num", "par_num", "line_num", "conf", "text"}
        if not required.issubset(indexes):
            raise OcrError("Tesseract TSV response is missing required columns")
        for raw_line in lines[1:]:
            columns = raw_line.split("\t")
            if len(columns) < len(headers):
                columns.extend([""] * (len(headers) - len(columns)))
            text = columns[indexes["text"]].strip()
            if not text:
                continue
            try:
                confidence = float(columns[indexes["conf"]])
            except ValueError:
                continue
            if confidence < 0:
                continue
            key = (
                columns[indexes["block_num"]],
                columns[indexes["par_num"]],
                columns[indexes["line_num"]],
            )
            groups.setdefault(key, []).append((text, confidence / 100.0))
        return tuple(
            OcrTextLine(
                text=" ".join(word for word, _ in words),
                confidence=sum(score for _, score in words) / len(words),
            )
            for words in groups.values()
        )
