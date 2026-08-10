from collections import Counter
from pathlib import Path

import pytest

from evaluation.reviewer import (
    DEFECT_TYPES,
    ReviewerDefect,
    load_reviewer_dataset,
    score_reviewer_predictions,
)


DATASET_PATH = Path("evaluation/fixtures/reviewer_v1.json")


def test_reviewer_dataset_has_balanced_defects_and_clean_cases():
    dataset = load_reviewer_dataset(DATASET_PATH)
    defects = [defect for case in dataset.cases for defect in case.expected_defects]
    counts = Counter(defect.defect_type for defect in defects)

    assert len(dataset.cases) == 12
    assert len(defects) == 12
    assert sum(not case.expected_defects for case in dataset.cases) == 2
    assert set(counts) == DEFECT_TYPES
    assert all(case.requirement_facts and case.test_points for case in dataset.cases)


def test_perfect_reviewer_predictions_score_full_precision_and_recall():
    dataset = load_reviewer_dataset(DATASET_PATH)
    predictions = {
        case.case_id: case.expected_defects
        for case in dataset.cases
        if case.expected_defects
    }

    score = score_reviewer_predictions(dataset, predictions)

    assert score["true_positive"] == 12
    assert score["false_positive"] == 0
    assert score["false_negative"] == 0
    assert score["precision"] == 1.0
    assert score["recall"] == 1.0
    assert score["clean_case_false_positive_rate"] == 0.0


def test_missed_defect_and_clean_case_finding_reduce_quality_metrics():
    dataset = load_reviewer_dataset(DATASET_PATH)
    first_case = dataset.cases[0]
    predictions = {
        first_case.case_id: first_case.expected_defects,
        "review-clean-001": (
            ReviewerDefect(
                defect_type="unsupported_assertion",
                target="库存充足",
                evidence="误报示例",
            ),
        ),
    }

    score = score_reviewer_predictions(dataset, predictions)

    assert score["true_positive"] == 1
    assert score["false_positive"] == 1
    assert score["false_negative"] == 11
    assert score["precision"] == 0.5
    assert score["recall"] == pytest.approx(1 / 12, abs=0.0001)
    assert score["clean_case_false_positive_rate"] == 0.5


def test_reviewer_scoring_rejects_unknown_case_id():
    dataset = load_reviewer_dataset(DATASET_PATH)

    with pytest.raises(ValueError, match="unknown Reviewer case_id"):
        score_reviewer_predictions(dataset, {"unknown": ()})
