from datetime import datetime, timezone

from agent import AgentStep, OrchestratorAction, OrchestratorDecision
from application import (
    CreateTaskCommand,
    TaskSnapshotSerializer,
    TestAnalysisApplicationService,
    UploadedDocument,
)
from repositories import InMemoryTaskRepository
from utils.telemetry import ServiceCallMetric, record_service_call


class _TelemetryOrchestrator:
    def decide_next(self, state):
        del state
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "分析需求",
        )

    def run_next(self, state):
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "开始分析")
        record_service_call(
            ServiceCallMetric(
                operation="chat_completion",
                dependency="llm",
                started_at=datetime.now(timezone.utc),
                duration_ms=30,
                succeeded=True,
                model="fake-model",
            )
        )
        state.requirement_summary = "结构化需求"
        state.complete_step(AgentStep.ANALYZE_REQUIREMENT, "分析完成")
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "分析需求",
            duration_seconds=0.03,
        )


def test_application_attaches_service_metrics_to_completed_node_event():
    repository = InMemoryTaskRepository()
    service = TestAnalysisApplicationService(
        repository,
        orchestrator_factory=_TelemetryOrchestrator,
        knowledge_loader=lambda: "",
    )
    task = service.create_task(CreateTaskCommand(requirement="提交订单"))

    view = service.advance_task(task.task_id)

    restored = repository.get(task.task_id)
    completed_event = next(
        event
        for event in reversed(restored.state.events)
        if event.step is AgentStep.ANALYZE_REQUIREMENT
        and event.event_type.value == "step_completed"
    )
    metrics = completed_event.data["service_metrics"]
    assert len(metrics) == 1
    assert metrics[0]["task_id"] == task.task_id
    assert metrics[0]["action"] == "analyze_requirement"
    assert metrics[0]["dependency"] == "llm"
    assert metrics[0]["model"] == "fake-model"
    assert view.service_metrics[0]["duration_ms"] == 30
    assert view.performance_summary["service_call_count"] == 1
    assert view.performance_summary["duration_by_dependency_ms"] == {
        "llm": 30
    }
    restored_snapshot = TaskSnapshotSerializer.from_json(
        TaskSnapshotSerializer.to_json(restored)
    )
    snapshot_metrics = next(
        event.data["service_metrics"]
        for event in restored_snapshot.state.events
        if "service_metrics" in event.data
    )
    assert snapshot_metrics[0]["task_id"] == task.task_id


def test_uploaded_document_metric_is_attached_to_task_created_event():
    repository = InMemoryTaskRepository()
    service = TestAnalysisApplicationService(
        repository,
        orchestrator_factory=_TelemetryOrchestrator,
        knowledge_loader=lambda: "",
    )

    task = service.create_task(
        CreateTaskCommand(
            uploaded_document=UploadedDocument(
                filename="requirement.md",
                content="# 需求\n\n用户可以提交订单".encode("utf-8"),
            )
        )
    )

    created_event = repository.get(task.task_id).state.events[0]
    metric = created_event.data["service_metrics"][0]
    assert metric["task_id"] == task.task_id
    assert metric["action"] == "document_parse"
    assert metric["dependency"] == "document_parser"
    assert metric["metadata"]["format"] == "markdown"
