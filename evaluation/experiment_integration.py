"""Explicit real-service entry point for the three-way smoke experiment."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from application import TestAnalysisApplicationService
from repositories import InMemoryTaskRepository

from .experiment_execution import (
    EXECUTION_POLICIES,
    run_application_experiment_case,
)
from .experiment_orchestrators import build_experiment_orchestrator
from .experiments import TaskViewExperimentVariant, run_three_way_experiment


DATASET_PATH = Path(__file__).parent / "datasets" / "seed_v1.json"
REPORT_PATH = Path(__file__).parent / "results" / "three_way_smoke_v1.json"


def run_real_three_way_smoke(report_path: Path = REPORT_PATH) -> dict:
    load_dotenv()
    if os.getenv("RUN_THREE_WAY_INTEGRATION_EVALUATION") != "1":
        raise RuntimeError(
            "set RUN_THREE_WAY_INTEGRATION_EVALUATION=1 to use real services"
        )
    case_limit = int(os.getenv("THREE_WAY_EVALUATION_CASE_LIMIT", "1"))
    variants = {
        name: _build_variant(policy)
        for name, policy in EXECUTION_POLICIES.items()
    }
    report = run_three_way_experiment(
        DATASET_PATH,
        variants,
        dependency_mode="real_deepseek_current_rag",
        case_limit=case_limit,
        continue_on_error=True,
    )
    report["model"] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    report["requested_case_limit"] = case_limit
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _build_variant(policy):
    service = TestAnalysisApplicationService(
        InMemoryTaskRepository(),
        orchestrator_factory=lambda: build_experiment_orchestrator(policy),
    )
    return TaskViewExperimentVariant(
        lambda case: run_application_experiment_case(service, case)
    )


if __name__ == "__main__":
    result = run_real_three_way_smoke()
    print(json.dumps(result["variants"], ensure_ascii=False, indent=2))
