import pytest

from repositories import TaskVersionConflictError


def test_repository_fixture_is_isolated(
    in_memory_task_repository,
    task_record_factory,
):
    first = task_record_factory("第一个任务")
    in_memory_task_repository.create(first)

    assert in_memory_task_repository.get(first.state.task_id).state.requirement == (
        "第一个任务"
    )


def test_factory_creates_independent_task_records(task_record_factory):
    first = task_record_factory()
    second = task_record_factory()

    first.state.requirement_facts.append("只属于第一个任务")

    assert first.state.task_id != second.state.task_id
    assert second.state.requirement_facts == []


def test_pytest_style_asserts_repository_version_conflict(
    in_memory_task_repository,
    task_record_factory,
):
    record = task_record_factory("并发保存任务")
    in_memory_task_repository.create(record)
    current = in_memory_task_repository.get_versioned(record.state.task_id)
    stale = in_memory_task_repository.get_versioned(record.state.task_id)
    in_memory_task_repository.save(
        current.record,
        expected_version=current.version,
    )

    with pytest.raises(TaskVersionConflictError) as context:
        in_memory_task_repository.save(
            stale.record,
            expected_version=stale.version,
        )

    assert context.value.expected == 1
    assert context.value.actual == 2
