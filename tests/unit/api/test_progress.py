from agent import AgentStep, AgentStatus, TestAnalysisState
from application.background_runner import BackgroundRunStatus
from application.models import TaskRecord, TaskView
from api.progress import build_task_progress


def test_progress_uses_domain_state_and_limits_recent_events():
    state = TestAnalysisState("订单需求")
    state.start_step(AgentStep.ANALYZE_REQUIREMENT, "开始分析")
    state.complete_step(AgentStep.ANALYZE_REQUIREMENT, "分析完成")
    state.add_information("等待补充")
    state.status = AgentStatus.WAITING_FOR_USER
    state.open_questions = ["库存不足如何处理？"]
    state.test_points = [{"id": "TP-1"}]
    state.review_result = {"score": 82}
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
