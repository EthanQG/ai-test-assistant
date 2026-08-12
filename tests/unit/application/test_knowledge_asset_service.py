from copy import deepcopy

import pytest

from application import (
    ConfirmKnowledgeAssetCommand,
    KnowledgeAssetApplicationService,
    TaskRecord,
)
from repositories import (
    InMemoryKnowledgeAssetRepository,
    InMemoryTaskRepository,
    KnowledgeAssetAlreadyExistsError,
    TaskNotFoundError,
)

from tests.unit.knowledge_assets.support import (
    make_eligible_state,
    make_test_point,
)


def _create_service():
    task_repository = InMemoryTaskRepository()
    asset_repository = InMemoryKnowledgeAssetRepository()
    service = KnowledgeAssetApplicationService(
        task_repository,
        asset_repository,
    )
    return service, task_repository, asset_repository


def _confirmation():
    return ConfirmKnowledgeAssetCommand(
        user_confirmed=True,
        data_safety_confirmed=True,
    )


def test_confirm_task_result_publishes_first_asset_version():
    service, task_repository, asset_repository = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))

    view = service.confirm_task_result(state.task_id, _confirmation())

    assert view.source_task_id == state.task_id
    assert view.asset_version == 1
    assert view.test_point_count == 1
    assert view.reviewer_score == 92
    detail = service.get_asset(view.asset_id)
    assert detail.asset_id == view.asset_id
    assert detail.final_report == state.report
    assert len(detail.test_points) == view.test_point_count
    assert service.list_assets() == (view,)
    assert len(asset_repository.list()) == 1


def test_confirm_task_result_does_not_mutate_task_state():
    service, task_repository, _ = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))
    before = deepcopy(task_repository.get(state.task_id).state.to_dict())

    service.confirm_task_result(state.task_id, _confirmation())

    after = task_repository.get(state.task_id).state.to_dict()
    assert after == before


def test_confirm_task_result_rejects_missing_confirmation():
    service, task_repository, asset_repository = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))

    with pytest.raises(ValueError, match="explicitly confirm"):
        service.confirm_task_result(
            state.task_id,
            ConfirmKnowledgeAssetCommand(
                user_confirmed=False,
                data_safety_confirmed=True,
            ),
        )

    assert asset_repository.list() == []


def test_confirm_task_result_rejects_duplicate_content():
    service, task_repository, asset_repository = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))
    service.confirm_task_result(state.task_id, _confirmation())

    with pytest.raises(KnowledgeAssetAlreadyExistsError, match="content_hash"):
        service.confirm_task_result(state.task_id, _confirmation())

    assert len(asset_repository.list()) == 1


def test_changed_confirmed_result_creates_next_source_version():
    service, task_repository, _ = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))
    first = service.confirm_task_result(state.task_id, _confirmation())
    loaded = task_repository.get_versioned(state.task_id)
    changed = loaded.record
    changed.state.test_points.append(
        make_test_point("库存不足时拒绝创建订单")
    )
    changed.state.final_result["test_points"] = list(
        changed.state.test_points
    )
    task_repository.save(changed, expected_version=loaded.version)

    second = service.confirm_task_result(state.task_id, _confirmation())

    assert first.asset_version == 1
    assert second.asset_version == 2
    assert second.content_hash != first.content_hash


def test_unknown_task_is_not_publishable():
    service, _, _ = _create_service()

    with pytest.raises(TaskNotFoundError, match="missing-task"):
        service.confirm_task_result("missing-task", _confirmation())


def test_service_exposes_paginated_asset_summaries():
    service, task_repository, _ = _create_service()
    state = make_eligible_state()
    task_repository.create(TaskRecord(state=state))
    published = service.confirm_task_result(state.task_id, _confirmation())

    page = service.list_asset_summaries(query=state.task_id, limit=5)

    assert page.total == 1
    assert page.limit == 5
    assert page.items[0].asset_id == published.asset_id
