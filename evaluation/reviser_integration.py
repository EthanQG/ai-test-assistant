"""Explicit real-LLM runner for the synthetic Reviser evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from agent import TestPointReviser

from .reviser import run_reviser_evaluation


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reviser_v1.json"
DEFAULT_REPORT_PATH = Path(__file__).parent / "results" / "reviser_real_v1.json"


def run_real_reviser_evaluation(report_path: Path = DEFAULT_REPORT_PATH) -> dict:
    load_dotenv()
    if os.getenv("RUN_REVISER_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_REVISER_INTEGRATION_EVALUATION=1 to use the real LLM"
        )
    report = run_reviser_evaluation(
        FIXTURE_PATH,
        TestPointReviser(),
        dependency_mode="real_deepseek_reviser",
        continue_on_error=True,
    )
    report["model"] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    result = run_real_reviser_evaluation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
