import time
from threading import Event

from agent import TestAnalysisState
from application.background_runner import TaskBackgroundRunner
from application.models import TaskRecord, TaskView


def _view(*, auto_run: bool) -> TaskView:
    return TaskView.from_record(TaskRecord(
        state=TestAnalysisState("订单需求"),
        auto_run=auto_run,
        next_action=("analyze_requirement" if auto_run else "wait_for_user"),
    ))


def _wait_for_status(runner, task_id, expected):
    for _ in range(100):
        status = runner.get_status(task_id)
        if status.status == expected:
            return status
        time.sleep(0.01)
    raise AssertionError(f"background task did not reach {expected}")


def test_runner_advances_until_application_service_pauses():
    class Service:
        def __init__(self):
            self.view = _view(auto_run=True)
            self.advance_calls = 0

        def get_task(self, task_id):
            return self.view

        def advance_task(self, task_id):
            self.advance_calls += 1
            self.view = _view(auto_run=False)
            return self.view

    service = Service()
    runner = TaskBackgroundRunner(service, max_workers=1)

    result = runner.start("task-1")
    stopped = _wait_for_status(runner, "task-1", "stopped")

    assert result.accepted is True
    assert stopped.error is None
    assert service.advance_calls == 1
    runner.shutdown()


def test_duplicate_start_does_not_create_second_worker():
    release = Event()

    class Service:
        def __init__(self):
            self.view = _view(auto_run=True)
            self.advance_calls = 0

        def get_task(self, task_id):
            return self.view

        def advance_task(self, task_id):
            self.advance_calls += 1
            release.wait(timeout=2)
            self.view = _view(auto_run=False)
            return self.view

    service = Service()
    runner = TaskBackgroundRunner(service, max_workers=1)

    first = runner.start("task-1")
    second = runner.start("task-1")
    release.set()
    _wait_for_status(runner, "task-1", "stopped")

    assert first.accepted is True
    assert second.accepted is False
    assert second.status == "running"
    assert service.advance_calls == 1
    runner.shutdown()


def test_worker_failure_is_observable_without_retry_loop():
    class Service:
        def get_task(self, task_id):
            return _view(auto_run=True)

        def advance_task(self, task_id):
            raise RuntimeError("model unavailable")

    runner = TaskBackgroundRunner(Service(), max_workers=1)

    runner.start("task-1")
    failed = _wait_for_status(runner, "task-1", "failed")

    assert failed.error == "RuntimeError: model unavailable"
    runner.shutdown()


def test_paused_task_is_not_submitted_to_thread_pool():
    class Service:
        def get_task(self, task_id):
            return _view(auto_run=False)

        def advance_task(self, task_id):
            raise AssertionError("paused task must not advance")

    runner = TaskBackgroundRunner(Service(), max_workers=1)

    result = runner.start("task-1")

    assert result.status == "stopped"
    assert result.accepted is False
    runner.shutdown()
