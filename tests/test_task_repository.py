import unittest
from datetime import datetime, timedelta, timezone

from agent import TestAnalysisState
from application import TaskRecord
from repositories import (
    InMemoryTaskRepository,
    TaskAlreadyExistsError,
    TaskExecutionAlreadyFinishedError,
    TaskExecutionBusyError,
    TaskExecutionLeaseLostError,
    TaskNotFoundError,
    TaskVersionConflictError,
)


class InMemoryTaskRepositoryTests(unittest.TestCase):
    def test_create_get_save_list_and_delete(self):
        repository = InMemoryTaskRepository()
        state = TestAnalysisState("用户可以提交订单")
        repository.create(TaskRecord(state=state))

        stored = repository.get(state.task_id)
        stored.state.requirement_summary = "订单提交"
        repository.save(stored)

        self.assertEqual(
            repository.get(state.task_id).state.requirement_summary,
            "订单提交",
        )
        self.assertEqual(len(repository.list()), 1)

        repository.delete(state.task_id)
        with self.assertRaises(TaskNotFoundError):
            repository.get(state.task_id)

    def test_repository_returns_isolated_copies(self):
        repository = InMemoryTaskRepository()
        state = TestAnalysisState("用户可以提交订单")
        repository.create(TaskRecord(state=state))

        first = repository.get(state.task_id)
        first.state.requirement_facts.append("未保存的修改")
        second = repository.get(state.task_id)

        self.assertEqual(second.state.requirement_facts, [])

    def test_repository_instances_are_isolated_by_session(self):
        first_repository = InMemoryTaskRepository()
        second_repository = InMemoryTaskRepository()
        state = TestAnalysisState("用户可以提交订单")
        first_repository.create(TaskRecord(state=state))

        with self.assertRaises(TaskNotFoundError):
            second_repository.get(state.task_id)

    def test_duplicate_create_and_unknown_save_are_rejected(self):
        repository = InMemoryTaskRepository()
        state = TestAnalysisState("用户可以提交订单")
        record = TaskRecord(state=state)
        repository.create(record)

        with self.assertRaises(TaskAlreadyExistsError):
            repository.create(record)
        with self.assertRaises(TaskNotFoundError):
            repository.save(
                TaskRecord(TestAnalysisState("另一个任务"))
            )

    def test_versioned_save_rejects_stale_snapshot(self):
        repository = InMemoryTaskRepository()
        record = TaskRecord(TestAnalysisState("versioned task"))
        repository.create(record)
        first = repository.get_versioned(record.state.task_id)
        stale = repository.get_versioned(record.state.task_id)

        first.record.state.requirement_summary = "first update"
        new_version = repository.save(
            first.record,
            expected_version=first.version,
        )

        self.assertEqual(new_version, 2)
        stale.record.state.requirement_summary = "stale update"
        with self.assertRaises(TaskVersionConflictError):
            repository.save(
                stale.record,
                expected_version=stale.version,
            )
        self.assertEqual(
            repository.get(record.state.task_id).state.requirement_summary,
            "first update",
        )

    def test_execution_id_is_committed_only_once(self):
        repository = InMemoryTaskRepository()
        record = TaskRecord(TestAnalysisState("idempotent task"))
        repository.create(record)
        loaded = repository.get_versioned(record.state.task_id)
        lease = repository.acquire_execution(
            record.state.task_id,
            execution_id="execution-1",
            owner_id="worker-1",
            action="analyze_requirement",
            lease_seconds=60,
            expected_version=loaded.version,
        )
        repository.complete_execution(
            loaded.record,
            lease,
            succeeded=True,
        )

        current = repository.get_versioned(record.state.task_id)
        with self.assertRaises(TaskExecutionAlreadyFinishedError):
            repository.acquire_execution(
                record.state.task_id,
                execution_id="execution-1",
                owner_id="worker-1",
                action="analyze_requirement",
                lease_seconds=60,
                expected_version=current.version,
            )

    def test_active_lease_blocks_other_execution_until_expired(self):
        now = datetime(2026, 8, 4, tzinfo=timezone.utc)
        clock_value = [now]
        repository = InMemoryTaskRepository(clock=lambda: clock_value[0])
        record = TaskRecord(TestAnalysisState("leased task"))
        repository.create(record)
        loaded = repository.get_versioned(record.state.task_id)
        first_lease = repository.acquire_execution(
            record.state.task_id,
            execution_id="execution-1",
            owner_id="worker-1",
            action="analyze_requirement",
            lease_seconds=30,
            expected_version=loaded.version,
        )

        current = repository.get_versioned(record.state.task_id)
        with self.assertRaises(TaskExecutionBusyError):
            repository.acquire_execution(
                record.state.task_id,
                execution_id="execution-2",
                owner_id="worker-2",
                action="analyze_requirement",
                lease_seconds=30,
                expected_version=current.version,
            )

        clock_value[0] += timedelta(seconds=31)
        with self.assertRaises(TaskExecutionLeaseLostError):
            repository.complete_execution(
                loaded.record,
                first_lease,
                succeeded=True,
            )
        current = repository.get_versioned(record.state.task_id)
        second_lease = repository.acquire_execution(
            record.state.task_id,
            execution_id="execution-2",
            owner_id="worker-2",
            action="analyze_requirement",
            lease_seconds=30,
            expected_version=current.version,
        )
        repository.complete_execution(
            current.record,
            second_lease,
            succeeded=True,
        )


if __name__ == "__main__":
    unittest.main()
