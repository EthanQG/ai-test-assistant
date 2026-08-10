import pytest

from evaluation.reviewer_integration import run_real_reviewer_evaluation


def test_real_reviewer_runner_is_disabled_without_explicit_environment_flag(
    monkeypatch,
):
    monkeypatch.setenv("RUN_REVIEWER_INTEGRATION_EVALUATION", "0")

    with pytest.raises(
        RuntimeError,
        match="RUN_REVIEWER_INTEGRATION_EVALUATION=1",
    ):
        run_real_reviewer_evaluation()
