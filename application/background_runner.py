from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock

from .service import TestAnalysisApplicationService


@dataclass(frozen=True)
class BackgroundRunStatus:
    task_id: str
    status: str
    accepted: bool
    error: str | None = None


class TaskBackgroundRunner:
    """Runs existing application actions without owning Agent decisions."""

    def __init__(
        self,
        service: TestAnalysisApplicationService,
        *,
        max_workers: int = 2,
    ):
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._service = service
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="test-analysis",
        )
        self._futures: dict[str, Future] = {}
        self._lock = Lock()

    def start(self, task_id: str) -> BackgroundRunStatus:
        view = self._service.get_task(task_id)
        if not view.auto_run and not view.has_pending_clarifications:
            return BackgroundRunStatus(task_id, "stopped", False)
        with self._lock:
            current = self._futures.get(task_id)
            if current is not None and not current.done():
                return BackgroundRunStatus(task_id, "running", False)
            self._futures[task_id] = self._executor.submit(
                self._run_until_pause,
                task_id,
            )
        return BackgroundRunStatus(task_id, "queued", True)

    def get_status(self, task_id: str) -> BackgroundRunStatus:
        self._service.get_task(task_id)
        with self._lock:
            future = self._futures.get(task_id)
        if future is None:
            return BackgroundRunStatus(task_id, "idle", False)
        if not future.done():
            return BackgroundRunStatus(task_id, "running", False)
        error = future.exception()
        if error is not None:
            return BackgroundRunStatus(
                task_id,
                "failed",
                False,
                f"{type(error).__name__}: {error}",
            )
        return BackgroundRunStatus(task_id, "stopped", False)

    def _run_until_pause(self, task_id: str) -> None:
        while True:
            view = self._service.get_task(task_id)
            if not view.auto_run and not view.has_pending_clarifications:
                return
            self._service.advance_task(task_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)
