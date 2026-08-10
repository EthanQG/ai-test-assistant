"""Explicit real-LLM runner for the synthetic Reviewer evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from agent import TestPointReviewer

from .reviewer_runner import run_reviewer_evaluation


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reviewer_v1.json"
DEFAULT_REPORT_PATH = Path(__file__).parent / "results" / "reviewer_real_v1.json"


def run_real_reviewer_evaluation(
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    load_dotenv()
    if os.getenv("RUN_REVIEWER_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_REVIEWER_INTEGRATION_EVALUATION=1 to use the real LLM"
        )

    report = run_reviewer_evaluation(
        FIXTURE_PATH,
        TestPointReviewer(),
        dependency_mode="real_deepseek_reviewer",
        continue_on_error=True,
    )
    report["model"] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = run_real_reviewer_evaluation()
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
