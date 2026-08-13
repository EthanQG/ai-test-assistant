from agent import (
    AgentStep,
    AgentStatus,
    OrchestratorAction,
    OrchestratorDecision,
    TestAnalysisState,
)
from application.background_runner import BackgroundRunStatus
from application.models import TaskRecord, TaskView
from api.progress import build_task_progress


def test_progress_presents_revision_limit_as_waiting_for_human_feedback():
    state = TestAnalysisState("smart lock requirement")
    state.status = AgentStatus.RUNNING
    state.current_step = AgentStep.REVIEW_TEST_POINTS
    record = TaskRecord(
        state=state,
        next_action="revision_limit_reached",
        decisions=[OrchestratorDecision(
            OrchestratorAction.REVISION_LIMIT_REACHED,
            "automatic revision limit reached",
        )],
    )

    progress = build_task_progress(
        TaskView.from_record(record),
        BackgroundRunStatus(state.task_id, "stopped", False),
    )

    assert progress["status"] == "running"
    assert progress["status_label"] == "等待人工反馈"
    assert progress["stage_label"] == "人工反馈"
    assert progress["revision_limit_reached"] is True


def test_progress_uses_domain_state_and_limits_recent_events():
    state = TestAnalysisState("订单需求")
    state.start_step(AgentStep.ANALYZE_REQUIREMENT, "开始分析")
    state.complete_step(AgentStep.ANALYZE_REQUIREMENT, "分析完成")
    state.add_information("等待补充")
    state.status = AgentStatus.WAITING_FOR_USER
    state.open_questions = ["库存不足如何处理？"]
    state.test_points = [{"id": "TP-1"}]
    state.review_result = {"overall_score": 82}
    record = TaskRecord(
        state=state,
        pending_clarifications={"库存不足如何处理？": None},
    )

    progress = build_task_progress(
        TaskView.from_record(record),
        BackgroundRunStatus(state.task_id, "stopped", False),
    )

    assert progress["status_label"] == "等待用户"
    assert progress["stage_label"] == "需求分析"
    assert progress["waiting_for_clarifications"] is True
    assert progress["test_point_count"] == 1
    assert progress["reviewer_score"] == 82
    assert len(progress["recent_events"]) == 3
    assert progress["recent_events"][-1]["message"] == "等待补充"


def test_progress_keeps_legacy_reviewer_score_compatible():
    state = TestAnalysisState("订单需求")
    state.review_result = {"score": 81}

    progress = build_task_progress(
        TaskView.from_record(TaskRecord(state=state)),
        BackgroundRunStatus(state.task_id, "stopped", False),
    )

    assert progress["reviewer_score"] == 81
