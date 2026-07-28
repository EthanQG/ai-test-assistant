from html import escape
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

FEEDBACK_ACTION_LABELS = {
    "add": "新增",
    "remove": "删除",
    "modify": "修改",
    "update_priority": "调整优先级",
}

FEEDBACK_TYPE_LABELS = {
    "test_suggestion": "测试建议",
    "business_rule": "业务规则",
}

FEEDBACK_STATUS_LABELS = {
    "pending_confirmation": "待确认",
    "ready": "待处理",
    "applied": "已应用",
    "rejected": "已取消",
}

ACTION_LABELS = {
    "analyze_requirement": "需求分析",
    "retrieve_knowledge": "知识检索",
    "generate_test_points": "生成测试点",
    "review_test_points": "质量评审",
    "revise_test_points": "修正测试点",
    "finalize": "整理报告",
    "wait_for_user": "等待用户",
    "revision_limit_reached": "达到修正上限",
    "terminal": "任务结束",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def action_progress_message(action: str) -> str:
    label = action_label(action)
    if action in {
        "analyze_requirement",
        "generate_test_points",
        "review_test_points",
        "revise_test_points",
    }:
        return f"正在执行：{label}。模型响应通常需要 1–2 分钟，请勿重复点击。"
    if action == "retrieve_knowledge":
        return (
            "正在执行：知识检索。外部检索服务较慢或不可用时，"
            "Agent 会记录降级并继续。"
        )
    return f"正在执行：{label}。"


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
        "automatic_revision_count": state.automatic_revision_count,
        "human_revision_count": state.human_revision_count,
        "rag_status": state.knowledge_retrieval_status.value,
    }


def event_rows(state: TestAnalysisState) -> list[dict[str, Any]]:
    return [
        {
            "序号": str(index),
            "时间": event.occurred_at.astimezone().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "步骤": event.step.value,
            "事件": event.event_type.value,
            "说明": event.message,
        }
        for index, event in enumerate(state.events, start=1)
    ]


def decision_rows(
    decisions: list[OrchestratorDecision],
) -> list[dict[str, str]]:
    return [
        {
            "序号": str(index),
            "动作": action_label(decision.action.value),
            "原因": decision.reason,
            "耗时": (
                f"{duration_seconds:.2f} 秒"
                if (
                    duration_seconds := getattr(
                        decision,
                        "duration_seconds",
                        None,
                    )
                )
                is not None
                else "-"
            ),
        }
        for index, decision in enumerate(decisions, start=1)
    ]


def static_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    headers = list(rows[0])
    header_cells = "".join(
        (
            '<th style="padding:8px;border:1px solid #dfe3ea;'
            'background:#f7f8fa;text-align:left;white-space:nowrap;">'
            f"{escape(str(header))}</th>"
        )
        for header in headers
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            (
                '<td style="padding:8px;border:1px solid #dfe3ea;'
                'text-align:left;vertical-align:top;">'
                f"{escape(str(row.get(header, ''))).replace(chr(10), '<br>')}"
                "</td>"
            )
            for header in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        '<div style="width:100%;overflow-x:auto;">'
        '<table class="agent-static-table" '
        'style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


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


def feedback_rows(state: TestAnalysisState) -> list[dict[str, str]]:
    return [
        {
            "类型": FEEDBACK_TYPE_LABELS.get(
                str(item.get("feedback_type", "")),
                str(item.get("feedback_type", "")),
            ),
            "动作": FEEDBACK_ACTION_LABELS.get(
                str(item.get("action", "")),
                str(item.get("action", "")),
            ),
            "目标": str(item.get("target", "")),
            "反馈内容": str(item.get("content", "")),
            "原因": str(item.get("reason", "")),
            "状态": FEEDBACK_STATUS_LABELS.get(
                str(item.get("status", "")),
                str(item.get("status", "")),
            ),
        }
        for item in state.human_feedback
    ]
