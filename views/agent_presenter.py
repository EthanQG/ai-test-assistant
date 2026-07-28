from typing import Any

from agent.orchestrator import OrchestratorDecision
from agent.state import TestAnalysisState


STATUS_LABELS = {
    "pending": "等待开始",
    "running": "执行中",
    "waiting_for_user": "等待用户",
    "completed": "已完成",
    "failed": "执行失败",
}

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

CATEGORY_LABELS = {
    "functional": "功能",
    "boundary": "边界",
    "exception": "异常",
    "non_functional": "非功能",
}


def task_overview(state: TestAnalysisState) -> dict[str, Any]:
    final_result = state.final_result or {}
    quality = final_result.get("quality_summary", {})
    return {
        "status": state.status.value,
        "status_label": STATUS_LABELS[state.status.value],
        "current_step": STEP_LABELS[state.current_step.value],
        "test_point_count": len(state.test_points),
        "overall_score": quality.get(
            "overall_score",
            (state.review_result or {}).get("overall_score"),
        ),
        "revision_count": state.revision_count,
        "rag_status": state.knowledge_retrieval_status.value,
    }


def event_rows(state: TestAnalysisState) -> list[dict[str, Any]]:
    return [
        {
            "时间": event.occurred_at.astimezone().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "步骤": event.step.value,
            "事件": event.event_type.value,
            "说明": event.message,
        }
        for event in state.events
    ]


def decision_rows(
    decisions: list[OrchestratorDecision],
) -> list[dict[str, str]]:
    return [
        {
            "序号": str(index),
            "动作": decision.action.value,
            "原因": decision.reason,
        }
        for index, decision in enumerate(decisions, start=1)
    ]


def test_point_rows(state: TestAnalysisState) -> list[dict[str, str]]:
    rows = []
    for test_point in state.test_points:
        rows.append(
            {
                "标题": str(test_point.get("title", "")),
                "分类": CATEGORY_LABELS.get(
                    str(test_point.get("category", "")),
                    str(test_point.get("category", "")),
                ),
                "优先级": str(test_point.get("priority", "")),
                "场景": str(test_point.get("scenario", "")),
                "步骤": "\n".join(test_point.get("steps", [])),
                "预期结果": "\n".join(
                    test_point.get("expected_results", [])
                ),
                "来源": ", ".join(test_point.get("sources", [])),
            }
        )
    return rows
