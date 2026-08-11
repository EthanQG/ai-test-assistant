from fastapi.testclient import TestClient

from agent import TestAnalysisState
from application.commands import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
)
from application.background_runner import BackgroundRunStatus
from application.models import TaskRecord, TaskView
from api.main import create_app
from repositories import TaskNotFoundError


def _view(requirement: str = "订单需求") -> TaskView:
    return TaskView.from_record(TaskRecord(
        state=TestAnalysisState(requirement),
        auto_run=True,
        next_action="analyze_requirement",
    ))


class FakeApplicationService:
    def __init__(self):
        self.view = _view()
        self.calls = []

    def create_task(self, command):
        self.calls.append(("create", command))
        return self.view

    def list_tasks(self):
        self.calls.append(("list", None))
        return (self.view,)

    def get_task(self, task_id):
        self.calls.append(("get", task_id))
        if task_id == "missing":
            raise TaskNotFoundError(task_id)
        return self.view

    def advance_task(self, task_id):
        self.calls.append(("advance", task_id))
        return self.view

    def submit_clarifications(self, task_id, command):
        self.calls.append(("clarifications", task_id, command))
        return self.view

    def confirm_business_rules(self, task_id, command):
        self.calls.append(("confirmation", task_id, command))
        return self.view

    def submit_feedback(self, task_id, command):
        self.calls.append(("feedback", task_id, command))
        return self.view

    def retry_task(self, task_id):
        self.calls.append(("retry", task_id))
        return self.view

    def delete_task(self, task_id):
        self.calls.append(("delete", task_id))


def _client():
    service = FakeApplicationService()
    return TestClient(create_app(service)), service


def test_health_and_openapi_are_available():
    client, _ = _client()

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/openapi.json").status_code == 200


def test_create_get_list_and_delete_task():
    client, service = _client()

    created = client.post(
        "/api/v1/tasks",
        json={"requirement": "库存不足时拒绝创建订单"},
    )
    task_id = service.view.task_id
    fetched = client.get(f"/api/v1/tasks/{task_id}")
    listed = client.get("/api/v1/tasks")
    deleted = client.delete(f"/api/v1/tasks/{task_id}")

    assert created.status_code == 201
    assert created.json()["state"]["task_id"] == task_id
    assert fetched.status_code == 200
    assert len(listed.json()) == 1
    assert deleted.status_code == 204
    assert isinstance(service.calls[0][1], CreateTaskCommand)


def test_blank_requirement_is_rejected_before_application_service():
    client, service = _client()

    response = client.post("/api/v1/tasks", json={"requirement": ""})

    assert response.status_code == 422
    assert service.calls == []


def test_advance_expresses_task_action_without_node_name():
    client, service = _client()

    response = client.post("/api/v1/tasks/task-1/advance")

    assert response.status_code == 200
    assert service.calls == [("advance", "task-1")]


def test_submit_clarifications_builds_application_command():
    client, service = _client()

    response = client.post(
        "/api/v1/tasks/task-1/clarifications",
        json={"answers": {"库存不足如何处理？": "拒绝创建订单"}},
    )

    _, task_id, command = service.calls[0]
    assert response.status_code == 200
    assert task_id == "task-1"
    assert isinstance(command, SubmitClarificationsCommand)
    assert command.answers["库存不足如何处理？"] == "拒绝创建订单"


def test_confirmation_and_feedback_build_application_commands():
    client, service = _client()

    confirmation = client.post(
        "/api/v1/tasks/task-1/business-rules/confirmation",
        json={"feedback_id": "feedback-1", "confirmed": True},
    )
    feedback = client.post(
        "/api/v1/tasks/task-1/feedback",
        json={
            "action": "add",
            "feedback_type": "test_suggestion",
            "target": "订单创建",
            "content": "补充并发提交场景",
            "reason": "验证幂等",
        },
    )

    assert confirmation.status_code == 200
    assert feedback.status_code == 200
    assert isinstance(service.calls[0][2], ConfirmBusinessRulesCommand)
    assert isinstance(service.calls[1][2], SubmitFeedbackCommand)


def test_retry_and_not_found_mapping():
    client, service = _client()

    retried = client.post("/api/v1/tasks/failed-task/retry")
    missing = client.get("/api/v1/tasks/missing")

    assert retried.status_code == 201
    assert service.calls[0] == ("retry", "failed-task")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "task not found: missing"


def test_application_value_error_maps_to_conflict():
    class InvalidStateService(FakeApplicationService):
        def advance_task(self, task_id):
            raise ValueError("task cannot advance from current state")

    client = TestClient(create_app(InvalidStateService()))

    response = client.post("/api/v1/tasks/task-1/advance")

    assert response.status_code == 409
    assert "cannot advance" in response.json()["detail"]


def test_background_run_and_execution_status_endpoints():
    class Runner:
        def start(self, task_id):
            return BackgroundRunStatus(task_id, "queued", True)

        def get_status(self, task_id):
            return BackgroundRunStatus(task_id, "running", False)

    service = FakeApplicationService()
    client = TestClient(create_app(service, Runner()))

    started = client.post("/api/v1/tasks/task-1/run")
    execution = client.get("/api/v1/tasks/task-1/execution")

    assert started.status_code == 202
    assert started.json() == {
        "task_id": "task-1",
        "status": "queued",
        "accepted": True,
        "error": None,
    }
    assert execution.json()["status"] == "running"
