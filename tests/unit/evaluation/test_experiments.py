from pathlib import Path

import pytest

from evaluation.dataset import load_evaluation_dataset
from evaluation.experiments import ExperimentOutput, run_three_way_experiment
from evaluation.experiments import (
    TaskViewExperimentVariant,
    experiment_output_from_task_view,
)
from agent import TestAnalysisState
from application import NodeExecutionMetric, TaskRecord, TaskView
from datetime import datetime, timezone
from agent.events import AgentEventType, AgentStep


DATASET = Path("evaluation/datasets/seed_v1.json")


class GoldFakeVariant:
    def __init__(self, *, omit_first_fact=False):
        self.omit_first_fact = omit_first_fact
        self.calls = []

    def analyze(self, case):
        self.calls.append(case.case_id)
        facts = [item.text for item in case.gold.facts]
        if self.omit_first_fact:
            facts = facts[1:]
        return ExperimentOutput(
            facts=tuple(facts),
            business_rules=tuple(item.text for item in case.gold.business_rules),
            risks=tuple(item.text for item in case.gold.risks),
            clarification_questions=tuple(
                item.question for item in case.gold.clarification_questions
            ),
            scenarios=tuple(item.text for item in case.gold.necessary_scenarios),
            elapsed_seconds=1.5,
            input_tokens=100,
            output_tokens=50,
            revision_count=1,
        )


def _variants(**overrides):
    return {
        "baseline_llm": overrides.get("baseline_llm", GoldFakeVariant()),
        "llm_with_rag": overrides.get("llm_with_rag", GoldFakeVariant()),
        "llm_with_rag_reviewer_reviser": overrides.get(
            "llm_with_rag_reviewer_reviser", GoldFakeVariant()
        ),
    }


def test_three_way_runner_uses_same_ten_cases_and_shared_metrics():
    variants = _variants()

    report = run_three_way_experiment(
        DATASET, variants, dependency_mode="fake_gold_outputs_only"
    )

    expected_ids = [case.case_id for case in load_evaluation_dataset(DATASET).cases]
    assert all(variant.calls == expected_ids for variant in variants.values())
    assert report["matching_policy"] == "normalized_exact_text_v1"
    for result in report["variants"].values():
        assert result["case_count"] == 10
        assert result["fact_recall"] == 1.0
        assert result["scenario_recall"] == 1.0
        assert result["forbidden_assertion_count"] == 0
        assert result["total_elapsed_seconds"] == 15.0
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["average_revision_count"] == 1.0
        assert result["failed_case_count"] == 0
        assert result["errors"] == []


def test_metrics_expose_one_variant_with_missing_facts():
    report = run_three_way_experiment(
        DATASET,
        _variants(baseline_llm=GoldFakeVariant(omit_first_fact=True)),
        dependency_mode="fake_partial_output",
    )

    assert report["variants"]["baseline_llm"]["fact_recall"] < 1.0
    assert report["variants"]["llm_with_rag"]["fact_recall"] == 1.0


def test_runner_rejects_missing_or_extra_variant():
    with pytest.raises(ValueError, match="variants are incomplete"):
        run_three_way_experiment(
            DATASET,
            {"baseline_llm": GoldFakeVariant()},
            dependency_mode="fake",
        )


def test_runner_can_limit_cases_and_record_one_variant_failure():
    class FailingVariant(GoldFakeVariant):
        def analyze(self, case):
            raise RuntimeError("model failed")

    report = run_three_way_experiment(
        DATASET,
        _variants(baseline_llm=FailingVariant()),
        dependency_mode="fake_failure",
        case_limit=1,
        continue_on_error=True,
    )

    baseline = report["variants"]["baseline_llm"]
    assert baseline["case_count"] == 1
    assert baseline["failed_case_count"] == 1
    assert baseline["fact_recall"] == 0.0
    assert report["variants"]["llm_with_rag"]["case_count"] == 1


def _task_view():
    state = TestAnalysisState("库存不足时拒绝创建订单")
    state.requirement_facts = ["库存不足时拒绝创建订单"]
    state.business_rules = ["库存不足时，不创建订单"]
    state.inferred_risks = [{"risk": "并发超卖", "basis": "库存会被扣减"}]
    state.open_questions = ["库存扣减失败如何处理？"]
    state.deferred_questions = ["是否记录失败原因？"]
    state.test_points = [{
        "title": "库存不足",
        "scenario": "库存小于购买数量",
        "expected_results": ["拒绝创建订单"],
    }]
    state.revision_count = 1
    state.events.append(type(state.events[0])(
        event_type=AgentEventType.STEP_COMPLETED,
        step=AgentStep.GENERATE_TEST_POINTS,
        message="完成",
        data={"service_metrics": [{
            "dependency": "llm", "duration_ms": 20,
            "token_usage": {
                "source": "provider", "input_tokens": 120,
                "output_tokens": 30, "total_tokens": 150,
            },
        }]},
    ))
    now = datetime.now(timezone.utc)
    record = TaskRecord(state=state, metrics=[
        NodeExecutionMetric("generate", now, now, 1.25, True)
    ])
    return TaskView.from_record(record)


def test_task_view_adapter_uses_read_only_results_and_provider_metrics():
    output = experiment_output_from_task_view(_task_view())

    assert output.facts == ("库存不足时拒绝创建订单",)
    assert output.risks == ("并发超卖",)
    assert output.clarification_questions == (
        "库存扣减失败如何处理？", "是否记录失败原因？"
    )
    assert output.scenarios == ("库存不足", "库存小于购买数量")
    assert output.assertions == ("拒绝创建订单",)
    assert output.elapsed_seconds == 1.25
    assert output.input_tokens == 120
    assert output.output_tokens == 30
    assert output.revision_count == 1


def test_task_view_variant_wraps_application_execution_callable():
    calls = []
    variant = TaskViewExperimentVariant(
        lambda case: calls.append(case.case_id) or _task_view()
    )
    case = load_evaluation_dataset(DATASET).cases[0]

    output = variant.analyze(case)

    assert calls == [case.case_id]
    assert output.facts
