import pytest

from evaluation.reviser_integration import run_real_reviser_evaluation


def test_real_reviser_runner_requires_explicit_environment_flag(monkeypatch):
    monkeypatch.setenv("RUN_REVISER_INTEGRATION_EVALUATION", "0")

    with pytest.raises(
        RuntimeError, match="RUN_REVISER_INTEGRATION_EVALUATION=1"
    ):
        run_real_reviser_evaluation()
