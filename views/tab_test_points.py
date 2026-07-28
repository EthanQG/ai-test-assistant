import time

import streamlit as st

from agent import (
    AgentOrchestrator,
    AgentStatus,
    OrchestratorAction,
    RequirementAnalyzer,
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
AUTO_RUN_KEY = "agent_auto_run"
PENDING_CLARIFICATIONS_KEY = "agent_pending_clarifications"
EXECUTION_STEPS_KEY = "agent_execution_steps"
MAX_PAGE_STEPS = 20


@st.cache_resource
def _task_store() -> dict:
    """Keep active tasks while the Streamlit server process is alive."""
    return {}


def render_ui() -> None:
    _initialize_session()
    _render_intro()

    workbench, result_panel = st.columns([0.42, 0.58], gap="medium")
    with workbench:
        with st.container(height=760, border=True):
            execution_placeholder = _render_workbench()

    with result_panel:
        with st.container(height=760, border=True):
            _render_result_panel(st.session_state.get(STATE_KEY))

    _process_agent_step(execution_placeholder)


def _initialize_session() -> None:
    st.session_state.setdefault(STATE_KEY, None)
    st.session_state.setdefault(DECISIONS_KEY, [])
    st.session_state.setdefault(AUTO_RUN_KEY, False)
    st.session_state.setdefault(PENDING_CLARIFICATIONS_KEY, None)
    st.session_state.setdefault(EXECUTION_STEPS_KEY, 0)

    if st.session_state[STATE_KEY] is not None:
        return

    task_id = st.query_params.get("task_id")
    if not task_id:
        return
    stored = _task_store().get(task_id)
    if not stored:
        return

    st.session_state[STATE_KEY] = stored["state"]
    st.session_state[DECISIONS_KEY] = stored["decisions"]
    st.session_state[AUTO_RUN_KEY] = stored["auto_run"]
    st.session_state[PENDING_CLARIFICATIONS_KEY] = stored[
        "pending_clarifications"
    ]
    st.session_state[EXECUTION_STEPS_KEY] = stored["execution_steps"]


def _persist_task() -> None:
    state = st.session_state.get(STATE_KEY)
    if state is None:
        return
    _task_store()[state.task_id] = {
        "state": state,
        "decisions": st.session_state[DECISIONS_KEY],
        "auto_run": st.session_state[AUTO_RUN_KEY],
        "pending_clarifications": st.session_state[
            PENDING_CLARIFICATIONS_KEY
        ],
        "execution_steps": st.session_state[EXECUTION_STEPS_KEY],
        "in_progress": _task_store()
        .get(state.task_id, {})
        .get("in_progress", False),
    }
    st.query_params["task_id"] = state.task_id


def _render_intro() -> None:
    st.header("测试分析 Agent 工作台")
    st.caption(
        "左侧输入需求并处理 Agent 的关键追问；右侧持续展示任务状态、执行轨迹和最终报告。"
    )


def _render_workbench():
    state = st.session_state.get(STATE_KEY)
    task_started = state is not None

    st.subheader("需求工作台")
    requirement_text = st.text_area(
        "输入需求描述或粘贴 PRD 内容",
        height=260,
        placeholder=(
            "示例：用户提交订单时系统校验库存，库存充足则创建订单并扣减库存，"
            "库存不足则提示失败。"
        ),
        key="agent_requirement_input",
        disabled=task_started,
    )
    uploaded_prd = st.file_uploader(
        "或者上传 PRD 文档",
        type=["txt", "md", "pdf", "docx"],
        key="agent_prd_uploader",
        disabled=task_started,
    )
    st.caption(
        "历史测试经验由 Agent 自动从默认知识文件和 Milvus 检索，无需在每次任务中重复上传。"
    )

    has_input = bool(requirement_text.strip()) or uploaded_prd is not None
    start_col, reset_col = st.columns([3, 1])
    with start_col:
        start_clicked = st.button(
            "启动测试分析 Agent",
            type="primary",
            disabled=not has_input or task_started,
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
        _create_agent_task(requirement_text, uploaded_prd)
        st.rerun()

    state = st.session_state.get(STATE_KEY)
    if (
        state is not None
        and state.status == AgentStatus.WAITING_FOR_USER
        and state.open_questions
    ):
        st.divider()
        if st.session_state[PENDING_CLARIFICATIONS_KEY] is None:
            _render_clarification_form(state)
        else:
            st.success("补充信息已提交，正在重新分析需求。")
    elif state is not None:
        st.divider()

    if state is not None:
        st.caption(_task_hint(state))

    return st.empty()


def _task_hint(state: TestAnalysisState) -> str:
    if state.status == AgentStatus.COMPLETED:
        return "本次分析已完成。请在右侧查看或下载报告；分析新需求时可清空当前任务。"
    if state.status == AgentStatus.FAILED:
        return "本次分析执行失败。请查看右侧错误信息，确认原因后重新发起任务。"
    if state.status == AgentStatus.WAITING_FOR_USER:
        return "任务正在等待补充信息，请完成上方关键问题后继续。"
    return "Agent 正在执行，节点完成后右侧轨迹会自动更新，请耐心等待。"


def _render_clarification_form(state: TestAnalysisState) -> None:
    st.subheader("需要你确认")
    st.info(
        "Agent 只保留了会影响核心业务结果的问题。每项可以直接回答，"
        "也可以选择“暂不确定”，后者会作为风险写入报告。"
    )

    with st.form(f"clarification_form_{state.task_id}"):
        answer_keys: list[tuple[str, str, str]] = []
        for index, question in enumerate(state.open_questions, start=1):
            st.markdown(f"**{index}. {question}**")
            deferred_key = f"clarification_deferred_{state.task_id}_{index}"
            answer_key = f"clarification_answer_{state.task_id}_{index}"
            deferred = st.checkbox("暂不确定", key=deferred_key)
            st.text_area(
                "补充说明",
                key=answer_key,
                height=80,
                disabled=deferred,
                placeholder="请用业务语言简要回答即可",
                label_visibility="collapsed",
            )
            answer_keys.append((question, answer_key, deferred_key))

        submitted = st.form_submit_button(
            "提交补充并继续执行",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    answers: dict[str, str | None] = {}
    unanswered: list[str] = []
    for question, answer_key, deferred_key in answer_keys:
        if st.session_state.get(deferred_key, False):
            answers[question] = None
            continue
        answer = st.session_state.get(answer_key, "").strip()
        if not answer:
            unanswered.append(question)
        answers[question] = answer

    if unanswered:
        st.error("请回答所有问题，无法确认的项目可以勾选“暂不确定”。")
        return

    st.session_state[PENDING_CLARIFICATIONS_KEY] = answers
    st.session_state[AUTO_RUN_KEY] = False
    _persist_task()
    st.rerun()


def _create_agent_task(requirement_text: str, uploaded_prd) -> None:
    try:
        requirement = requirement_text.strip()
        if uploaded_prd is not None:
            requirement = DocumentService.extract_text(uploaded_prd)

        state = TestAnalysisState(requirement)
        state.local_bug_knowledge = _load_default_knowledge()
        st.session_state[STATE_KEY] = state
        st.session_state[DECISIONS_KEY] = []
        st.session_state[AUTO_RUN_KEY] = True
        st.session_state[PENDING_CLARIFICATIONS_KEY] = None
        st.session_state[EXECUTION_STEPS_KEY] = 0
        _persist_task()
    except Exception as exc:
        _show_execution_error(exc, "Agent 启动失败")


def _process_agent_step(execution_placeholder) -> None:
    state = st.session_state.get(STATE_KEY)
    if state is None:
        return

    stored = _task_store().get(state.task_id, {})
    if stored.get("in_progress"):
        time.sleep(1)
        st.rerun()
    if stored:
        st.session_state[DECISIONS_KEY] = stored["decisions"]
        st.session_state[AUTO_RUN_KEY] = stored["auto_run"]
        st.session_state[PENDING_CLARIFICATIONS_KEY] = stored[
            "pending_clarifications"
        ]
        st.session_state[EXECUTION_STEPS_KEY] = stored[
            "execution_steps"
        ]

    pending_answers = st.session_state.get(PENDING_CLARIFICATIONS_KEY)
    should_run = bool(st.session_state.get(AUTO_RUN_KEY))
    if pending_answers is None and not should_run:
        return

    stored["in_progress"] = True
    _task_store()[state.task_id] = stored
    try:
        if pending_answers is not None:
            with execution_placeholder.container():
                with st.spinner("正在结合补充信息重新分析需求..."):
                    RequirementAnalyzer().reanalyze_with_clarifications(
                        state,
                        pending_answers,
                    )
            st.session_state[PENDING_CLARIFICATIONS_KEY] = None
            st.session_state[AUTO_RUN_KEY] = (
                state.status == AgentStatus.RUNNING
            )
        else:
            _execute_next_orchestrator_node(
                state,
                execution_placeholder,
            )
    except Exception as exc:
        st.session_state[AUTO_RUN_KEY] = False
        _show_execution_error(exc, "Agent 执行失败")
    finally:
        stored = _task_store().get(state.task_id, {})
        stored["in_progress"] = False
        _task_store()[state.task_id] = stored
        _persist_task()

    st.rerun()


def _execute_next_orchestrator_node(
    state: TestAnalysisState,
    execution_placeholder,
) -> None:
    if st.session_state[EXECUTION_STEPS_KEY] >= MAX_PAGE_STEPS:
        state.fail(
            f"orchestration exceeded maximum step count: {MAX_PAGE_STEPS}"
        )
        st.session_state[AUTO_RUN_KEY] = False
        return

    with execution_placeholder.container():
        with st.spinner("正在执行下一个 Agent 节点..."):
            decision = AgentOrchestrator().run_next(state)
    st.session_state[DECISIONS_KEY].append(decision)
    st.session_state[EXECUTION_STEPS_KEY] += 1

    should_stop = (
        decision.action
        in {
            OrchestratorAction.WAIT_FOR_USER,
            OrchestratorAction.REVISION_LIMIT_REACHED,
            OrchestratorAction.TERMINAL,
        }
        or state.status
        in {
            AgentStatus.WAITING_FOR_USER,
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
        }
    )
    st.session_state[AUTO_RUN_KEY] = not should_stop


def _show_execution_error(exc: Exception, prefix: str) -> None:
    state = st.session_state.get(STATE_KEY)
    if state is not None and state.error_message:
        st.error(state.error_message)
    else:
        st.error(f"{prefix}：{exc}")


def _load_default_knowledge() -> str:
    return KnowledgeBaseManager().load_bug_experience()


def _render_result_panel(state: TestAnalysisState | None) -> None:
    st.subheader("任务概览")
    if state is None:
        st.info("在左侧输入需求并启动 Agent，任务状态和分析结果会固定显示在这里。")
        st.caption("尚未创建分析任务。")
        return

    overview = task_overview(state)
    with st.container(border=True):
        metric_columns = st.columns(5)
        metric_columns[0].metric("任务状态", overview["status_label"])
        metric_columns[1].metric("当前步骤", overview["current_step"])
        metric_columns[2].metric("测试点", overview["test_point_count"])
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

    with st.container(height=580, border=True):
        timeline_tab, points_tab, quality_tab, report_tab = st.tabs(
            ["执行轨迹", "结构化测试点", "质量评审", "最终报告"]
        )
        with timeline_tab:
            decisions = st.session_state.get(DECISIONS_KEY, [])
            if decisions:
                st.markdown("#### Orchestrator 决策")
                st.dataframe(
                    decision_rows(decisions),
                    use_container_width=True,
                    hide_index=True,
                )
            st.markdown("#### Agent 事件")
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
                st.download_button(
                    "下载 Markdown 报告",
                    data=state.report,
                    file_name="测试分析报告.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
                st.markdown(state.report)
            else:
                st.caption("任务完成后将在此展示最终报告。")


def _render_blocked_state(state: TestAnalysisState) -> None:
    if state.status == AgentStatus.WAITING_FOR_USER:
        st.warning("任务已暂停，请在左侧工作台回答关键问题后继续。")
    elif state.status == AgentStatus.FAILED:
        st.error(state.error_message or "Agent 执行失败")
    else:
        decisions = st.session_state.get(DECISIONS_KEY, [])
        if (
            decisions
            and decisions[-1].action
            == OrchestratorAction.REVISION_LIMIT_REACHED
        ):
            st.warning(
                "自动修正已达到上限，当前结果会保留并等待人工处理，不会标记为质量通过。"
            )


def _render_quality(state: TestAnalysisState) -> None:
    if not state.review_result:
        st.caption("当前尚未产生 Reviewer 结果。")
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
        st.markdown("#### Reviewer 建议")
        for item in review["revision_suggestions"]:
            st.markdown(f"- {item}")


def _reset_session() -> None:
    state = st.session_state.get(STATE_KEY)
    if state is not None:
        _task_store().pop(state.task_id, None)
    st.query_params.clear()
    for key in list(st.session_state):
        if key in {
            STATE_KEY,
            DECISIONS_KEY,
            AUTO_RUN_KEY,
            PENDING_CLARIFICATIONS_KEY,
            EXECUTION_STEPS_KEY,
            "agent_requirement_input",
            "agent_prd_uploader",
        } or key.startswith("clarification_"):
            st.session_state.pop(key, None)
