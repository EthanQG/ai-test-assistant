import unittest

from agent import TestAnalysisState
from application import TaskRecord
from repositories import (
    InMemoryTaskRepository,
    TaskAlreadyExistsError,
    TaskNotFoundError,
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


if __name__ == "__main__":
    unittest.main()
