import json
from pathlib import Path

from evaluation.rag import run_rag_evaluation, score_rag_case


DATASET_PATH = (
    Path(__file__).parents[3] / "evaluation" / "fixtures" / "rag_v1.json"
)


def _case() -> dict:
    return {
        "case_id": "rag-test",
        "query": "订单库存",
        "relevant_asset_ids": ["asset-order"],
        "forbidden_asset_ids": ["asset-coupon"],
    }


def test_rag_dataset_contains_five_unique_synthetic_cases():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    assert dataset["schema_version"] == 1
    assert len(dataset["cases"]) == 5
    assert len({case["case_id"] for case in dataset["cases"]}) == 5
    assert all(case["relevant_asset_ids"] for case in dataset["cases"])


def test_score_rag_case_calculates_recall_precision_and_rank():
    score = score_rag_case(
        _case(),
        ["asset-other", "asset-order", "asset-third"],
        k=3,
    )

    assert score.recall_at_k == 1.0
    assert score.precision_at_k == 0.3333
    assert score.reciprocal_rank == 0.5
    assert score.forbidden_hit_rate == 0.0


def test_score_rag_case_counts_forbidden_asset_and_ignores_duplicates():
    score = score_rag_case(
        _case(),
        ["asset-coupon", "asset-coupon", "asset-order"],
        k=3,
    )

    assert score.retrieved_asset_ids == ("asset-coupon", "asset-order")
    assert score.recall_at_k == 1.0
    assert score.precision_at_k == 0.3333
    assert score.reciprocal_rank == 0.5
    assert score.forbidden_hit_rate == 1.0


def test_score_rag_case_returns_zero_when_relevant_asset_is_missing():
    score = score_rag_case(_case(), ["asset-other"], k=3)

    assert score.recall_at_k == 0.0
    assert score.precision_at_k == 0.0
    assert score.reciprocal_rank == 0.0


def test_runner_aggregates_fake_retrieval_without_external_services():
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    expected_by_query = {
        case["query"]: case["relevant_asset_ids"][0]
        for case in dataset["cases"]
    }

    report = run_rag_evaluation(
        DATASET_PATH,
        lambda query, k: [expected_by_query[query]],
        k=3,
    )

    assert report["case_count"] == 5
    assert report["summary"] == {
        "mean_recall_at_k": 1.0,
        "mean_precision_at_k": 0.3333,
        "mean_reciprocal_rank": 1.0,
        "mean_forbidden_hit_rate": 0.0,
    }
