"""Explicit real-LLM runner for long-requirement analysis stability."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from agent import RequirementAnalyzer, TestAnalysisState


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "prd"
    / "电商订单履约与优惠结算需求.md"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).parent / "results" / "long_requirement_compact_v1.json"
)


def run_real_long_requirement_evaluation(
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict:
    load_dotenv()
    if os.getenv("RUN_LONG_REQUIREMENT_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_LONG_REQUIREMENT_INTEGRATION_EVALUATION=1 "
            "to use the real LLM"
        )

    requirement = FIXTURE_PATH.read_text(encoding="utf-8")
    state = TestAnalysisState(requirement=requirement)
    started_at = perf_counter()
    try:
        result = RequirementAnalyzer().analyze(state)
    except Exception as exc:
        report = {
            "schema_version": 1,
            "fixture": str(
                FIXTURE_PATH.relative_to(Path(__file__).parents[1])
            ),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            "requirement_chars": len(requirement),
            "completed": False,
            "elapsed_seconds": round(perf_counter() - started_at, 2),
            "status": state.status.value,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report
    elapsed_seconds = round(perf_counter() - started_at, 2)
    completed_event = next(
        event
        for event in reversed(state.events)
        if event.message == "需求结构化分析完成"
    )
    report = {
        "schema_version": 1,
        "fixture": str(FIXTURE_PATH.relative_to(Path(__file__).parents[1])),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        "requirement_chars": len(requirement),
        "completed": True,
        "elapsed_seconds": elapsed_seconds,
        "status": state.status.value,
        "compact_contract": completed_event.data[
            "requirement_compact_contract"
        ],
        "initial_chunk_count": completed_event.data[
            "requirement_chunk_count"
        ],
        "statement_count": completed_event.data[
            "requirement_statement_count"
        ],
        "attempt_count": completed_event.data[
            "requirement_analysis_attempt_count"
        ],
        "adaptive_split_count": completed_event.data[
            "requirement_adaptive_split_count"
        ],
        "result_counts": {
            "requirement_facts": len(result.requirement_facts),
            "business_rules": len(result.business_rules),
            "state_transitions": len(result.state_transitions),
            "inferred_risks": len(result.inferred_risks),
            "open_questions": len(result.open_questions),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(
        json.dumps(
            run_real_long_requirement_evaluation(),
            ensure_ascii=False,
            indent=2,
        )
    )
