import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from agent import TestAnalysisState
from application.commands import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
    UploadedDocument,
)
from api.main import FRONTEND_DIR, MAX_UPLOAD_BYTES
from application.background_runner import BackgroundRunStatus
from application.models import TaskRecord, TaskView
from application.service import TestAnalysisApplicationService
from api.main import create_app
from repositories import InMemoryTaskRepository, TaskNotFoundError
from repositories import TaskSummary, TaskSummaryPage


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

    def list_task_summaries(self, *, query="", offset=0, limit=20):
        self.calls.append(("summaries", query, offset, limit))
        summary = TaskSummary(
            task_id=self.view.task_id,
            status="completed",
            current_step="finalize",
            requirement_summary="订单测试分析",
            event_count=8,
            version=3,
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        return TaskSummaryPage((summary,), 1, offset, limit)

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


def test_native_frontend_is_served_by_fastapi():
    client, _ = _client()

    home = client.get("/", follow_redirects=False)
    page = client.get("/app/")
    script = client.get("/app/app.js")

    assert home.status_code == 307
    assert home.headers["location"] == "/app/"
    assert page.status_code == 200
    assert "Test Analysis Agent" in page.text
    assert script.status_code == 200
    assert "pollProgress" in script.text
    assert "submitClarifications" in script.text
    assert "renderTestPoints" in script.text
    assert "renderQuality" in script.text
    assert "downloadReport" in script.text
    assert "submitFeedback" in script.text
    assert "confirmBusinessRule" in script.text
    assert "质量评审" in page.text
    assert "最终报告" in page.text
    assert "人工反馈" in page.text
    assert "确认规则并继续" in page.text


def test_frontend_keeps_polling_while_resumed_task_is_queued_or_running():
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    waiting_guard = re.search(
        r'progress\.status === "waiting_for_user"\s*'
        r'&&\s*!\["queued", "running"\]\.includes\('
        r'progress\.execution_status\)',
        script,
    )

    assert waiting_guard is not None


def test_frontend_javascript_element_ids_exist_in_page():
    page = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    page_ids = set(re.findall(r'\bid="([^"]+)"', page))
    script_ids = set(re.findall(r'querySelector\("#([^"]+)"\)', script))

    assert script_ids
    assert script_ids <= page_ids


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


def test_list_task_summaries_supports_search_and_pagination():
    client, service = _client()

    response = client.get(
        "/api/v1/task-summaries",
        params={"query": "订单", "offset": 10, "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["requirement_summary"] == "订单测试分析"
    assert response.json()["total"] == 1
    assert ("summaries", "订单", 10, 5) in service.calls


def test_native_frontend_exposes_history_and_restore_entry():
    page = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="history-button"' in page
    assert 'id="history-dialog"' in page
    assert "/api/v1/task-summaries" in script
    assert "restoreTask" in script


def test_blank_requirement_is_rejected_before_application_service():
    client, service = _client()

    response = client.post("/api/v1/tasks", json={"requirement": ""})

    assert response.status_code == 422
    assert service.calls == []


def test_document_upload_builds_application_command():
    client, service = _client()

    response = client.post(
        "/api/v1/tasks/from-document",
        files={
            "file": (
                "订单需求.md",
                "# 订单需求".encode(),
                "text/markdown",
            )
        },
    )

    command = service.calls[0][1]
    assert response.status_code == 201
    assert isinstance(command, CreateTaskCommand)
    assert command.requirement == ""
    assert command.uploaded_document == UploadedDocument(
        filename="订单需求.md",
        content="# 订单需求".encode(),
    )


def test_document_upload_rejects_empty_and_oversized_files():
    client, service = _client()

    empty = client.post(
        "/api/v1/tasks/from-document",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    oversized = client.post(
        "/api/v1/tasks/from-document",
        files={
            "file": (
                "large.txt",
                b"x" * (MAX_UPLOAD_BYTES + 1),
                "text/plain",
            )
        },
    )

    assert empty.status_code == 422
    assert oversized.status_code == 413
    assert service.calls == []


def test_document_upload_uses_existing_document_parser_to_create_task():
    service = TestAnalysisApplicationService(
        InMemoryTaskRepository(),
        knowledge_loader=lambda: "",
    )
    client = TestClient(create_app(service))

    response = client.post(
        "/api/v1/tasks/from-document",
        files={
            "file": (
                "订单需求.md",
                "# 订单需求\n\n库存不足时拒绝创建订单。".encode(),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["state"]["requirement"] == (
        "# 订单需求\n\n库存不足时拒绝创建订单。"
    )


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


def test_progress_endpoint_returns_polling_friendly_summary():
    class Runner:
        def get_status(self, task_id):
            return BackgroundRunStatus(task_id, "running", False)

    service = FakeApplicationService()
    client = TestClient(create_app(service, Runner()))

    response = client.get(f"/api/v1/tasks/{service.view.task_id}/progress")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": service.view.task_id,
        "status": "pending",
        "status_label": "等待开始",
        "current_step": "initialize",
        "stage_label": "初始化",
        "execution_status": "running",
        "next_action": "analyze_requirement",
        "waiting_for_clarifications": False,
        "waiting_for_business_rules": False,
        "revision_limit_reached": False,
        "test_point_count": 0,
        "reviewer_score": None,
        "automatic_revision_count": 0,
        "human_revision_count": 0,
        "recent_events": [service.view.events[0].to_dict()],
        "error": None,
    }
