import pytest

from evaluation.experiment_integration import run_real_three_way_smoke


def test_real_three_way_runner_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("RUN_THREE_WAY_INTEGRATION_EVALUATION", "0")

    with pytest.raises(
        RuntimeError, match="RUN_THREE_WAY_INTEGRATION_EVALUATION=1"
    ):
        run_real_three_way_smoke()
