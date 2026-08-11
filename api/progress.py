from __future__ import annotations

from typing import Any

from application.background_runner import BackgroundRunStatus
from application.models import TaskView


STEP_LABELS = {
    "initialize": "初始化",
    "analyze_requirement": "需求分析",
    "retrieve_knowledge": "知识检索",
    "generate_test_points": "生成测试点",
    "review_test_points": "质量评审",
    "collect_human_feedback": "人工反馈",
    "revise_test_points": "修正测试点",
    "finalize": "整理报告",
}

STATUS_LABELS = {
    "pending": "等待开始",
    "running": "执行中",
    "waiting_for_user": "等待用户",
    "completed": "已完成",
    "failed": "执行失败",
}


def build_task_progress(
    view: TaskView,
    execution: BackgroundRunStatus,
) -> dict[str, Any]:
    events = view.events[-3:]
    review_result = view.review_result or {}
    revision_limit_reached = view.revision_limit_reached
    return {
        "task_id": view.task_id,
        "status": view.status.value,
        "status_label": (
            "等待人工反馈"
            if revision_limit_reached
            else STATUS_LABELS[view.status.value]
        ),
        "current_step": view.current_step.value,
        "stage_label": (
            "人工反馈"
            if revision_limit_reached
            else STEP_LABELS[view.current_step.value]
        ),
        "execution_status": execution.status,
        "next_action": view.next_action,
        "waiting_for_clarifications": view.has_pending_clarifications,
        "waiting_for_business_rules": bool(view.pending_business_feedback),
        "revision_limit_reached": revision_limit_reached,
        "test_point_count": len(view.test_points),
        "reviewer_score": review_result.get("score"),
        "automatic_revision_count": view.automatic_revision_count,
        "human_revision_count": view.human_revision_count,
        "recent_events": [event.to_dict() for event in events],
        "error": view.error_message or execution.error,
    }
