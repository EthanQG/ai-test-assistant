import re
from datetime import datetime, timezone
from types import SimpleNamespace

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
            task_name="订单履约需求",
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

    def rename_task(self, task_id, task_name):
        self.calls.append(("rename", task_id, task_name))


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
    assert "AI 测试分析助手" in page.text
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
    assert "知识库" in page.text


def test_native_knowledge_page_is_served_and_uses_asset_api():
    client, _ = _client()

    page = client.get("/app/knowledge.html")
    script = client.get("/app/knowledge.js")

    assert page.status_code == 200
    assert "历史测试资产" in page.text
    assert 'id="asset-list"' in page.text
    assert 'id="knowledge-detail"' in page.text
    assert script.status_code == 200
    assert "/api/v1/knowledge-assets" in script.text
    assert "loadDetail" in script.text


def test_hidden_knowledge_empty_state_does_not_push_detail_below_viewport():
    styles = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert "[hidden] { display: none !important; }" in styles


def test_frontend_keeps_polling_while_resumed_task_is_queued_or_running():
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    waiting_guard = re.search(
        r'progress\.status === "waiting_for_user"\s*'
        r'&&\s*!\["queued", "running"\]\.includes\('
        r'progress\.execution_status\)',
        script,
    )

    assert waiting_guard is not None


def test_frontend_stops_polling_when_revision_limit_is_reached():
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert "if (progress.revision_limit_reached)" in script
    assert 'showResultTab("feedback")' in script


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


def test_rename_task():
    client, service = _client()
    task_id = service.view.task_id

    response = client.patch(
        f"/api/v1/tasks/{task_id}/name",
        json={"task_name": "订单回归分析"},
    )

    assert response.status_code == 204
    assert ("rename", task_id, "订单回归分析") in service.calls


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

    assert 'class="panel history-sidebar"' in page
    assert 'id="history-list"' in page
    assert 'id="new-task-button"' in page
    assert "renameHistoryTask" in script
    assert "/api/v1/task-summaries" in script
    assert "restoreTask" in script
    assert "deleteHistoryTask" in script
    assert 'method: "DELETE"' in script
    assert "deleteConfirmation" in script
    assert "window.confirm" not in script
    assert "document.body.append(popover)" in script
    assert "getBoundingClientRect" in script


def test_completed_result_can_be_confirmed_and_indexed_as_knowledge():
    task_service = FakeApplicationService()

    class AssetService:
        def __init__(self):
            self.calls = []

        def confirm_task_result(self, task_id, command):
            self.calls.append((task_id, command))
            return SimpleNamespace(
                asset_id="asset-1",
                source_task_id=task_id,
                asset_version=1,
                test_point_count=12,
                reviewer_score=90,
            )

    class IndexingService:
        def __init__(self):
            self.calls = []

        def index_asset(self, asset_id):
            self.calls.append(asset_id)
            return SimpleNamespace(
                status=SimpleNamespace(value="indexed"),
                chunk_count=18,
                omitted_chunk_count=0,
            )

    asset_service = AssetService()
    indexing_service = IndexingService()
    client = TestClient(create_app(
        task_service,
        knowledge_asset_service=asset_service,
        knowledge_indexing_service=indexing_service,
    ))

    response = client.post(
        f"/api/v1/tasks/{task_service.view.task_id}/knowledge-assets",
        json={"user_confirmed": True, "data_safety_confirmed": True},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "indexed"
    assert response.json()["chunk_count"] == 18
    assert asset_service.calls[0][0] == task_service.view.task_id
    assert indexing_service.calls == ["asset-1"]


def test_knowledge_asset_summary_and_detail_endpoints():
    task_service = FakeApplicationService()
    confirmed_at = datetime(2026, 8, 12, tzinfo=timezone.utc)

    class AssetService:
        def list_asset_summaries(self, **kwargs):
            self.list_kwargs = kwargs
            item = SimpleNamespace(
                asset_id="asset-1",
                source_task_id="task-1",
                asset_version=1,
                status="indexed",
                requirement_summary="订单履约测试资产",
                reviewer_score=91,
                test_point_count=12,
                confirmed_at=confirmed_at,
                created_at=confirmed_at,
            )
            return SimpleNamespace(items=(item,), total=1, offset=0, limit=10)

        def get_asset(self, asset_id):
            assert asset_id == "asset-1"
            return SimpleNamespace(
                asset_id=asset_id,
                source_task_id="task-1",
                asset_version=1,
                content_hash="a" * 64,
                status="indexed",
                requirement_summary="订单履约测试资产",
                reviewer_score=91,
                test_point_count=12,
                confirmed_at=confirmed_at,
                created_at=confirmed_at,
                original_requirement="订单履约需求",
                structured_requirement={"summary": "订单履约测试资产", "modules": []},
                test_points=[],
                review_result={"overall_score": 91},
                final_report="# 订单履约测试报告",
            )

    asset_service = AssetService()
    client = TestClient(create_app(
        task_service,
        knowledge_asset_service=asset_service,
        knowledge_indexing_service=SimpleNamespace(),
    ))

    listed = client.get(
        "/api/v1/knowledge-assets",
        params={"query": "订单", "status": "indexed", "limit": 10},
    )
    detail = client.get("/api/v1/knowledge-assets/asset-1")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["asset_id"] == "asset-1"
    assert asset_service.list_kwargs["status"].value == "indexed"
    assert detail.status_code == 200
    assert detail.json()["content_hash"] == "a" * 64
    assert detail.json()["final_report"] == "# 订单履约测试报告"


def test_native_frontend_requires_explicit_knowledge_safety_confirmation():
    page = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="publish-knowledge"' in page
    assert 'id="data-safety-confirmed"' in page
    assert "/knowledge-assets" in script
    assert "dataSafetyConfirmed.checked" in script


def test_native_frontend_uses_viewport_workspace_and_internal_panel_scroll():
    styles = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    assert "height: calc(100vh - 108px)" in styles
    assert "html, body { height: 100%; overflow: hidden; }" in styles
    assert "overflow-y: auto" in styles


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
