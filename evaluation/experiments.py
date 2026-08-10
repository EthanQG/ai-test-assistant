"""Shared contract and deterministic metrics for three-way experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol

from application import TaskView
from .dataset import EvaluationCase, load_evaluation_dataset


EXPERIMENT_VARIANTS = (
    "baseline_llm",
    "llm_with_rag",
    "llm_with_rag_reviewer_reviser",
)


@dataclass(frozen=True)
class ExperimentOutput:
    facts: tuple[str, ...]
    business_rules: tuple[str, ...]
    risks: tuple[str, ...]
    clarification_questions: tuple[str, ...]
    scenarios: tuple[str, ...]
    assertions: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    revision_count: int = 0


class ExperimentVariant(Protocol):
    def analyze(self, case: EvaluationCase) -> ExperimentOutput: ...


class TaskViewExperimentVariant:
    """Adapt an application use case returning TaskView to the shared output."""

    def __init__(self, execute: Callable[[EvaluationCase], TaskView]):
        self._execute = execute

    def analyze(self, case: EvaluationCase) -> ExperimentOutput:
        return experiment_output_from_task_view(self._execute(case))


def experiment_output_from_task_view(view: TaskView) -> ExperimentOutput:
    performance = view.performance_summary
    token_totals = performance["token_totals_by_source"]
    provider = token_totals["provider"]
    estimated = token_totals["estimated"]
    selected = provider if provider["total"] else estimated
    questions = tuple(dict.fromkeys(
        [*view.open_questions, *view.deferred_questions]
    ))
    risks = tuple(
        item["risk"]
        for item in view.inferred_risks
        if isinstance(item, dict) and isinstance(item.get("risk"), str)
    )
    scenarios = []
    assertions = []
    for point in view.test_points:
        scenarios.extend((point["title"], point["scenario"]))
        assertions.extend(point["expected_results"])
    return ExperimentOutput(
        facts=tuple(view.requirement_facts),
        business_rules=tuple(view.business_rules),
        risks=risks,
        clarification_questions=questions,
        scenarios=tuple(scenarios),
        assertions=tuple(assertions),
        elapsed_seconds=float(performance["task_execution_seconds"]),
        input_tokens=selected["input"] or None,
        output_tokens=selected["output"] or None,
        revision_count=int(view.revision_count),
    )


def run_three_way_experiment(
    dataset_path: Path,
    variants: Mapping[str, ExperimentVariant],
    *,
    dependency_mode: str,
) -> dict:
    if set(variants) != set(EXPERIMENT_VARIANTS):
        raise ValueError("three-way experiment variants are incomplete")
    dataset = load_evaluation_dataset(dataset_path)
    reports = {}
    for name in EXPERIMENT_VARIANTS:
        case_results = [
            _score_case(case, variants[name].analyze(case))
            for case in dataset.cases
        ]
        reports[name] = _summarize(case_results)
    return {
        "schema_version": 1,
        "dataset_id": dataset.dataset_id,
        "dependency_mode": dependency_mode,
        "matching_policy": "normalized_exact_text_v1",
        "variants": reports,
    }


def _score_case(case: EvaluationCase, output: ExperimentOutput) -> dict:
    gold = case.gold
    recalls = {
        "fact_recall": _recall(
            (item.text for item in gold.facts), output.facts
        ),
        "business_rule_recall": _recall(
            (item.text for item in gold.business_rules), output.business_rules
        ),
        "risk_recall": _recall(
            (item.text for item in gold.risks), output.risks
        ),
        "question_recall": _recall(
            (item.question for item in gold.clarification_questions),
            output.clarification_questions,
        ),
        "scenario_recall": _recall(
            (item.text for item in gold.necessary_scenarios), output.scenarios
        ),
    }
    forbidden = {_normalize(item) for item in gold.forbidden_assertions}
    assertions = {_normalize(item) for item in output.assertions}
    return {
        "case_id": case.case_id,
        **recalls,
        "forbidden_assertion_count": len(forbidden & assertions),
        "elapsed_seconds": output.elapsed_seconds,
        "input_tokens": output.input_tokens,
        "output_tokens": output.output_tokens,
        "revision_count": output.revision_count,
    }


def _summarize(results: list[dict]) -> dict:
    recall_names = (
        "fact_recall", "business_rule_recall", "risk_recall",
        "question_recall", "scenario_recall",
    )
    count = len(results)
    return {
        "case_count": count,
        **{
            name: round(sum(item[name] for item in results) / count, 4)
            for name in recall_names
        },
        "forbidden_assertion_count": sum(
            item["forbidden_assertion_count"] for item in results
        ),
        "total_elapsed_seconds": round(
            sum(item["elapsed_seconds"] for item in results), 4
        ),
        "input_tokens": _optional_sum(results, "input_tokens"),
        "output_tokens": _optional_sum(results, "output_tokens"),
        "average_revision_count": round(
            sum(item["revision_count"] for item in results) / count, 4
        ),
        "results": results,
    }


def _recall(expected, actual) -> float:
    expected_set = {_normalize(item) for item in expected}
    actual_set = {_normalize(item) for item in actual}
    if not expected_set:
        return 1.0 if not actual_set else 0.0
    return round(len(expected_set & actual_set) / len(expected_set), 4)


def _normalize(value: str) -> str:
    return "".join(value.split()).lower()


def _optional_sum(results: list[dict], field: str) -> int | None:
    values = [item[field] for item in results]
    return sum(values) if all(value is not None for value in values) else None
