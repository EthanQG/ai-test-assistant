import streamlit as st

from agent import (
    AgentOrchestrator,
    AgentStatus,
    OrchestratorAction,
    TestAnalysisState,
)
from services.document_service import DocumentService
from utils.knowledge_base import KnowledgeBaseManager

from .agent_presenter import (
    decision_rows,
    event_rows,
    task_overview,
    test_point_rows,
)


STATE_KEY = "agent_task_state"
DECISIONS_KEY = "agent_decisions"


def render_ui() -> None:
    _initialize_session()
    _render_intro()
    requirement_text, uploaded_prd = _render_inputs()

    start_col, reset_col = st.columns([3, 1])
    has_input = bool(requirement_text.strip()) or uploaded_prd is not None
    with start_col:
        start_clicked = st.button(
            "🚀 启动测试分析 Agent",
            type="primary",
            disabled=not has_input,
            use_container_width=True,
        )
    with reset_col:
        reset_clicked = st.button(
            "清空任务",
            type="secondary",
            use_container_width=True,
        )

    if reset_clicked:
        _reset_session()
        st.rerun()

    if start_clicked:
        _start_agent(requirement_text, uploaded_prd)

    state = st.session_state.get(STATE_KEY)
    if state is not None:
        _render_agent_workspace(state)


def _initialize_session() -> None:
    st.session_state.setdefault(STATE_KEY, None)
    st.session_state.setdefault(DECISIONS_KEY, [])


def _render_intro() -> None:
    st.header("测试分析 Agent 工作台")
    st.caption(
        "输入需求后，Agent将按受控流程完成需求分析、历史知识检索、"
        "测试点生成、质量评审、有限修正和最终报告整理。"
    )


def _render_inputs():
    requirement_text = ""
    uploaded_prd = None

    with st.container(border=True):
        st.subheader("需求输入")
        requirement_text = st.text_area(
            "请输入需求描述或粘贴PRD内容",
            height=260,
            placeholder=(
                "示例：用户提交订单时系统校验库存，库存充足则"
                "创建订单并扣减库存，库存不足则提示失败。"
            ),
            key="agent_requirement_input",
        )
        uploaded_prd = st.file_uploader(
            "或者上传PRD文档",
            type=["txt", "md", "pdf", "docx"],
            key="agent_prd_uploader",
        )
        st.caption(
            "历史测试经验由Agent自动从默认知识文件和Milvus"
            "知识库检索，无需在每次任务中重复上传。"
        )
    return requirement_text, uploaded_prd


def _start_agent(
    requirement_text: str,
    uploaded_prd,
) -> None:
    try:
        requirement = requirement_text.strip()
        if uploaded_prd is not None:
            requirement = DocumentService.extract_text(uploaded_prd)

        state = TestAnalysisState(requirement)
        state.local_bug_knowledge = _load_default_knowledge()
        st.session_state[STATE_KEY] = state
        st.session_state[DECISIONS_KEY] = []

        orchestrator = AgentOrchestrator()
        with st.status(
            "Agent正在执行受控分析流程...",
            expanded=True,
        ) as status:
            decisions = orchestrator.run_until_blocked(state)
            st.session_state[DECISIONS_KEY] = decisions
            status.update(
                label=_completion_message(state, decisions),
                state=(
                    "complete"
                    if state.status == AgentStatus.COMPLETED
                    else "error"
                    if state.status == AgentStatus.FAILED
                    else "running"
                ),
                expanded=False,
            )
    except Exception as exc:
        state = st.session_state.get(STATE_KEY)
        if state is not None and state.error_message:
            st.error(state.error_message)
        else:
            st.error(f"Agent启动失败：{exc}")


def _load_default_knowledge() -> str:
    return KnowledgeBaseManager().load_bug_experience()


def _completion_message(
    state: TestAnalysisState,
    decisions,
) -> str:
    if state.status == AgentStatus.COMPLETED:
        return "Agent分析完成"
    if state.status == AgentStatus.WAITING_FOR_USER:
        return "Agent正在等待用户补充信息"
    if state.status == AgentStatus.FAILED:
        return "Agent执行失败"
    if (
        decisions
        and decisions[-1].action
        == OrchestratorAction.REVISION_LIMIT_REACHED
    ):
        return "已达到自动修正上限，等待人工处理"
    return "Agent已暂停"


def _render_agent_workspace(state: TestAnalysisState) -> None:
    overview = task_overview(state)
    st.divider()
    st.subheader("任务概览")
    metric_columns = st.columns(5)
    metric_columns[0].metric("任务状态", overview["status_label"])
    metric_columns[1].metric("当前步骤", overview["current_step"])
    metric_columns[2].metric(
        "测试点",
        overview["test_point_count"],
    )
    metric_columns[3].metric(
        "Reviewer评分",
        overview["overall_score"]
        if overview["overall_score"] is not None
        else "待评审",
    )
    metric_columns[4].metric(
        "自动修正",
        f"{overview['revision_count']}/{state.max_revision_count}",
    )

    _render_blocked_state(state)

    timeline_tab, points_tab, quality_tab, report_tab = st.tabs(
        ["执行轨迹", "结构化测试点", "质量评审", "最终报告"]
    )
    with timeline_tab:
        decisions = st.session_state.get(DECISIONS_KEY, [])
        if decisions:
            st.markdown("#### Orchestrator决策")
            st.dataframe(
                decision_rows(decisions),
                use_container_width=True,
                hide_index=True,
            )
        st.markdown("#### Agent事件")
        st.dataframe(
            event_rows(state),
            use_container_width=True,
            hide_index=True,
        )

    with points_tab:
        rows = test_point_rows(state)
        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("当前尚未生成结构化测试点。")

    with quality_tab:
        _render_quality(state)

    with report_tab:
        if state.report:
            st.markdown(state.report)
            st.download_button(
                "📥 下载Markdown报告",
                data=state.report,
                file_name="测试分析报告.md",
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.caption("任务完成后将在此展示最终报告。")


def _render_blocked_state(state: TestAnalysisState) -> None:
    if state.status == AgentStatus.WAITING_FOR_USER:
        st.warning(
            "Agent发现需求信息不足，当前任务已暂停。"
            "下一小阶段将提供回答和恢复入口。"
        )
        for question in state.open_questions:
            st.markdown(f"- {question}")
    elif state.status == AgentStatus.FAILED:
        st.error(state.error_message or "Agent执行失败")
    else:
        decisions = st.session_state.get(DECISIONS_KEY, [])
        if (
            decisions
            and decisions[-1].action
            == OrchestratorAction.REVISION_LIMIT_REACHED
        ):
            st.warning(
                "自动修正已达到上限，当前结果保留等待人工处理，"
                "不会被标记为质量通过。"
            )


def _render_quality(state: TestAnalysisState) -> None:
    if not state.review_result:
        st.caption("当前尚未产生Reviewer结果。")
        return

    review = state.review_result
    scores = review.get("dimension_scores", {})
    score_columns = st.columns(5)
    score_columns[0].metric("总分", review.get("overall_score", "-"))
    score_columns[1].metric(
        "需求覆盖",
        scores.get("requirement_coverage", "-"),
    )
    score_columns[2].metric(
        "边界异常",
        scores.get("boundary_exception", "-"),
    )
    score_columns[3].metric(
        "可执行性",
        scores.get("executability", "-"),
    )
    score_columns[4].metric(
        "可追踪性",
        scores.get("traceability", "-"),
    )

    if review.get("missing_scenarios"):
        st.markdown("#### 缺失或关注场景")
        for item in review["missing_scenarios"]:
            st.markdown(f"- {item}")
    if review.get("revision_suggestions"):
        st.markdown("#### Reviewer建议")
        for item in review["revision_suggestions"]:
            st.markdown(f"- {item}")


def _reset_session() -> None:
    for key in (
        STATE_KEY,
        DECISIONS_KEY,
        "agent_requirement_input",
        "agent_prd_uploader",
    ):
        st.session_state.pop(key, None)
