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

PRIMARY_STAGE_LABELS = [
    "需求分析",
    "知识检索",
    "生成测试点",
    "评审与修正",
    "整理报告",
]

STEP_STAGE_INDEX = {
    "initialize": 0,
    "analyze_requirement": 0,
    "retrieve_knowledge": 1,
    "generate_test_points": 2,
    "review_test_points": 3,
    "collect_human_feedback": 3,
    "revise_test_points": 3,
    "finalize": 4,
}

EXECUTION_CONTENT = {
    "initialize": {
        "title": "正在分析需求",
        "description": (
            "Agent正在提取需求事实、业务规则、风险和待确认项。"
        ),
        "waiting": "模型响应通常需要1～2分钟，请勿重复提交。",
    },
    "analyze_requirement": {
        "title": "正在分析需求",
        "description": (
            "Agent正在分析需求结构、信息边界、业务规则和关键风险。"
        ),
        "waiting": "模型响应通常需要1～2分钟，请勿重复提交。",
    },
    "retrieve_knowledge": {
        "title": "正在检索历史测试资产",
        "description": (
            "Agent正在检索相关历史测试点、缺陷经验和可复用风险。"
        ),
        "waiting": (
            "检索服务较慢或不可用时会记录降级，并继续后续分析。"
        ),
    },
    "generate_test_points": {
        "title": "正在生成结构化测试点",
        "description": (
            "Agent正在根据需求事实、风险和历史资产生成可执行测试点。"
        ),
        "waiting": "模型响应通常需要1～2分钟，请勿重复提交。",
    },
    "review_test_points": {
        "title": "正在评审测试点质量",
        "description": (
            "Agent正在检查需求覆盖度、重复项、异常边界和无依据断言。"
        ),
        "waiting": "模型响应通常需要1～2分钟，请勿重复提交。",
    },
    "collect_human_feedback": {
        "title": "正在处理人工反馈",
        "description": (
            "Agent正在记录反馈范围，并准备进入定向修正与重新评审。"
        ),
        "waiting": "请等待当前节点完成，不要重复提交反馈。",
    },
    "revise_test_points": {
        "title": "正在修正测试点",
        "description": (
            "Agent正在根据评审意见或人工反馈定向修正测试点。"
        ),
        "waiting": "模型响应通常需要1～2分钟，请勿重复提交。",
    },
    "finalize": {
        "title": "正在整理最终报告",
        "description": (
            "Agent正在汇总测试点、覆盖情况、质量结论和风险说明。"
        ),
        "waiting": "报告整理完成后，页面会立即刷新最终结果。",
    },
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


def execution_status_content(
    state: TestAnalysisState,
    action: str | None = None,
) -> dict[str, str]:
    step = action or state.current_step.value
    content = dict(
        EXECUTION_CONTENT.get(
            step,
            EXECUTION_CONTENT["initialize"],
        )
    )
    if step == "revise_test_points":
        next_round = state.revision_count + 1
        content["title"] = f"正在进行第{next_round}轮测试点修正"
    return content


def recent_progress_items(
    state: TestAnalysisState,
    limit: int = 3,
) -> list[str]:
    if limit <= 0:
        return []

    items: list[str] = []
    seen: set[str] = set()
    for event in reversed(state.events):
        text = _event_progress_text(event)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= limit:
            break
    return list(reversed(items))


def _event_progress_text(event) -> str | None:
    event_type = event.event_type.value
    step = event.step.value
    step_label = STEP_LABELS.get(step, "")

    if event_type == "task_created":
        return "任务已创建"
    if event_type == "task_completed":
        return "测试分析和报告整理已完成"
    if event_type == "task_failed":
        return f"{step_label or '当前节点'}执行失败"
    if event_type == "step_started" and step_label:
        return f"已开始{step_label}"
    if event_type == "step_completed" and step_label:
        return f"{step_label}已完成"
    if event_type != "information":
        return None

    message = event.message
    if "已收到补充信息" in message:
        return "已提交用户补充信息"
    if "需要用户补充需求信息" in message:
        return "需求分析发现需要补充的信息"
    if "需要用户确认人工补充的业务规则" in message:
        return "新增业务规则等待用户确认"
    if "人工补充的业务规则已确认" in message:
        return "用户已确认新增业务规则"
    if "用户取消了业务规则补充" in message:
        return "用户已取消业务规则补充"
    if "已重新打开任务" in message:
        return "已提交人工反馈，准备修正测试点"
    return None


def layout_column_weights(
    state: TestAnalysisState | None,
    decisions: list[OrchestratorDecision],
) -> tuple[float, float]:
    if state is None:
        return (0.42, 0.58)

    current_step = state.current_step.value
    last_action = (
        decisions[-1].action.value
        if decisions
        else ""
    )
    result_focused = (
        state.status.value == "completed"
        or last_action == "revision_limit_reached"
        or current_step
        in {
            "collect_human_feedback",
            "revise_test_points",
        }
        or bool(state.human_feedback)
    )
    return (0.33, 0.67) if result_focused else (0.42, 0.58)


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


def task_header(
    state: TestAnalysisState,
    decisions: list[OrchestratorDecision],
) -> dict[str, str]:
    stage_index = STEP_STAGE_INDEX.get(state.current_step.value, 0)
    stage_label = PRIMARY_STAGE_LABELS[stage_index]
    status_label = STATUS_LABELS[state.status.value]

    pending_business_rule = any(
        item.get("feedback_type") == "business_rule"
        and item.get("status") == "pending_confirmation"
        for item in state.human_feedback
    )
    feedback_processing = (
        state.status.value == "running"
        and any(
            item.get("status") in {"ready", "applied"}
            for item in state.human_feedback
        )
    )
    revision_limit_reached = bool(
        decisions
        and decisions[-1].action.value == "revision_limit_reached"
    )

    if state.status.value == "waiting_for_user":
        if pending_business_rule:
            status_label = "等待规则确认"
            stage_label = "评审与修正"
        else:
            status_label = "等待补充信息"
            stage_label = "需求分析"
    elif revision_limit_reached:
        status_label = "已达自动修正上限"
        stage_label = "评审与修正"
    elif feedback_processing:
        status_label = "人工反馈处理中"
        stage_label = "评审与修正"
    elif state.status.value == "completed":
        stage_label = "整理报告"

    return {
        "status_label": status_label,
        "stage_label": stage_label,
    }


def stage_progress(state: TestAnalysisState) -> list[dict[str, str]]:
    current_index = STEP_STAGE_INDEX[state.current_step.value]
    if state.status.value == "completed":
        current_index = len(PRIMARY_STAGE_LABELS) - 1

    stages = []
    for index, label in enumerate(PRIMARY_STAGE_LABELS):
        if state.status.value == "completed" or index < current_index:
            stage_status = "completed"
        elif index == current_index:
            stage_status = (
                "failed"
                if state.status.value == "failed"
                else "current"
            )
        else:
            stage_status = "pending"
        stages.append({"label": label, "status": stage_status})
    return stages


def stage_progress_html(state: TestAnalysisState) -> str:
    status_symbols = {
        "completed": "✓",
        "current": "●",
        "failed": "!",
        "pending": "○",
    }
    items = []
    for stage in stage_progress(state):
        symbol = status_symbols[stage["status"]]
        items.append(
            f'<span class="agent-stage agent-stage--{stage["status"]}">'
            f"{symbol} {escape(stage['label'])}</span>"
        )
    return (
        '<div class="agent-stage-progress">'
        + "".join(items)
        + "</div>"
    )


def test_point_summary_html(
    test_point: dict[str, Any],
    index: int,
) -> str:
    title = str(test_point.get("title", "")).strip() or "未命名测试点"
    category = str(test_point.get("category", ""))
    category_label = CATEGORY_LABELS.get(category, category or "-")
    priority = str(test_point.get("priority", "")).strip() or "-"
    scenario = str(test_point.get("scenario", "")).strip() or "未提供"
    return (
        '<div class="agent-test-point-summary">'
        f'<div class="agent-test-point-title">{index}. {escape(title)}</div>'
        f'<div class="agent-test-point-meta">分类：{escape(category_label)}</div>'
        f'<div class="agent-test-point-meta">优先级：{escape(priority)}</div>'
        f'<div class="agent-test-point-scenario">场景摘要：{escape(scenario)}</div>'
        "</div>"
    )


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
