from pathlib import Path

import pytest

from evaluation.dataset import load_evaluation_dataset
from evaluation.experiments import ExperimentOutput, run_three_way_experiment


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
