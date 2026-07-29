import hashlib
import json
import math
import time
from html import escape

import streamlit as st

from agent import (
    AgentOrchestrator,
    AgentStatus,
    FeedbackStatus,
    HumanFeedbackHandler,
    OrchestratorAction,
    OrchestratorDecision,
    RequirementAnalyzer,
    TestAnalysisState,
)
from services.document_service import DocumentService
from utils.knowledge_base import KnowledgeBaseManager

from .agent_presenter import (
    decision_rows,
    execution_status_content,
    event_rows,
    feedback_rows,
    layout_column_weights,
    recent_progress_items,
    stage_progress_html,
    static_table_html,
    task_header,
    task_overview,
    test_point_summary_html,
)


STATE_KEY = "agent_task_state"
DECISIONS_KEY = "agent_decisions"
AUTO_RUN_KEY = "agent_auto_run"
PENDING_CLARIFICATIONS_KEY = "agent_pending_clarifications"
EXECUTION_STEPS_KEY = "agent_execution_steps"
FEEDBACK_FORM_VERSION_KEY = "agent_feedback_form_version"
FEEDBACK_NOTICE_KEY = "agent_feedback_notice"
RESULT_ACTIVE_TAB_KEY = "agent_ui_active_result_tab"
TEST_POINT_PAGE_KEY = "agent_ui_test_point_page"
TEST_POINT_EXPANDED_KEY = "agent_ui_expanded_test_point"
TEST_POINT_DETAIL_ID_KEY = "agent_ui_test_point_detail_id"
TEST_POINT_SIGNATURE_KEY = "agent_ui_test_point_signature"
PAGINATION_TASK_ID_KEY = "agent_ui_pagination_task_id"
EXECUTION_DIALOG_BUTTON_PREFIX = "agent_ui_execution_details"
UI_STATE_PREFIX = "agent_ui_"
MAX_PAGE_STEPS = 20
TEST_POINT_PAGE_SIZE = 5
WORKSPACE_HEIGHT = 736
LEFT_HEADER_HEIGHT = 56
LEFT_FOOTER_HEIGHT = 120
LEFT_BODY_HEIGHT = (
    WORKSPACE_HEIGHT - LEFT_HEADER_HEIGHT - LEFT_FOOTER_HEIGHT - 48
)
RIGHT_FIXED_HEIGHT = 296
RIGHT_RESULT_HEIGHT = WORKSPACE_HEIGHT - RIGHT_FIXED_HEIGHT - 32
EXECUTION_DETAILS_HEIGHT = 480
TEST_POINT_DETAILS_HEIGHT = 480
RESULT_TABS = (
    "结构化测试点",
    "质量评审",
    "人工反馈",
    "最终报告",
)


@st.cache_resource
def _task_store() -> dict:
    """Keep active tasks while the Streamlit server process is alive."""
    return {}


def render_ui() -> None:
    _initialize_session()
    _initialize_page_view_state()

    state = st.session_state.get(STATE_KEY)
    decisions = st.session_state.get(DECISIONS_KEY, [])
    _sync_page_view_state(state, decisions)
    column_weights = layout_column_weights(
        state,
        decisions,
    )
    workbench, result_panel = st.columns(
        column_weights,
        gap="medium",
    )
    with workbench:
        with st.container(height=WORKSPACE_HEIGHT, border=True):
            st.markdown(
                '<span class="agent-workspace-shell-marker"></span>',
                unsafe_allow_html=True,
            )
            st.subheader("需求工作台")
            st.caption(_workbench_description(state))
            with st.container(
                height=LEFT_BODY_HEIGHT,
                border=False,
            ):
                st.markdown(
                    '<span class="agent-workbench-scroll-marker"></span>',
                    unsafe_allow_html=True,
                )
                _render_workbench_body()
            with st.container(
                height=LEFT_FOOTER_HEIGHT,
                border=False,
            ):
                st.markdown(
                    '<span class="agent-workbench-footer-marker"></span>',
                    unsafe_allow_html=True,
                )
                _render_workbench_footer()

    with result_panel:
        with st.container(height=WORKSPACE_HEIGHT, border=True):
            st.markdown(
                '<span class="agent-workspace-shell-marker"></span>',
                unsafe_allow_html=True,
            )
            execution_placeholder = _render_result_panel(
                state
            )

    _process_agent_step(execution_placeholder)


def _initialize_session() -> None:
    st.session_state.setdefault(STATE_KEY, None)
    st.session_state.setdefault(DECISIONS_KEY, [])
    st.session_state.setdefault(AUTO_RUN_KEY, False)
    st.session_state.setdefault(PENDING_CLARIFICATIONS_KEY, None)
    st.session_state.setdefault(EXECUTION_STEPS_KEY, 0)
    st.session_state.setdefault(FEEDBACK_FORM_VERSION_KEY, 0)
    st.session_state.setdefault(FEEDBACK_NOTICE_KEY, None)

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


def _initialize_page_view_state() -> None:
    st.session_state.setdefault(
        RESULT_ACTIVE_TAB_KEY,
        RESULT_TABS[0],
    )
    st.session_state.setdefault(TEST_POINT_PAGE_KEY, 1)
    st.session_state.setdefault(TEST_POINT_EXPANDED_KEY, None)
    st.session_state.setdefault(TEST_POINT_DETAIL_ID_KEY, None)
    st.session_state.setdefault(TEST_POINT_SIGNATURE_KEY, "")
    st.session_state.setdefault(PAGINATION_TASK_ID_KEY, None)


def _clear_page_view_state() -> None:
    for key in list(st.session_state):
        if key.startswith(UI_STATE_PREFIX):
            st.session_state.pop(key, None)


def _sync_page_view_state(
    state: TestAnalysisState | None,
    decisions: list[OrchestratorDecision],
) -> None:
    task_id = state.task_id if state is not None else None
    previous_task_id = st.session_state.get(PAGINATION_TASK_ID_KEY)
    signature = _test_point_signature(state)

    if previous_task_id != task_id:
        st.session_state[PAGINATION_TASK_ID_KEY] = task_id
        st.session_state[RESULT_ACTIVE_TAB_KEY] = _default_result_tab(
            state,
            decisions,
        )
        st.session_state[TEST_POINT_PAGE_KEY] = 1
        st.session_state[TEST_POINT_EXPANDED_KEY] = None
        st.session_state[TEST_POINT_DETAIL_ID_KEY] = None
        st.session_state[TEST_POINT_SIGNATURE_KEY] = signature
        return

    if st.session_state.get(TEST_POINT_SIGNATURE_KEY) != signature:
        st.session_state[TEST_POINT_PAGE_KEY] = 1
        st.session_state[TEST_POINT_EXPANDED_KEY] = None
        st.session_state[TEST_POINT_DETAIL_ID_KEY] = None
        st.session_state[TEST_POINT_SIGNATURE_KEY] = signature

    if st.session_state.get(RESULT_ACTIVE_TAB_KEY) not in RESULT_TABS:
        st.session_state[RESULT_ACTIVE_TAB_KEY] = _default_result_tab(
            state,
            decisions,
        )


def _default_result_tab(
    state: TestAnalysisState | None,
    decisions: list[OrchestratorDecision],
) -> str:
    if state is None:
        return RESULT_TABS[0]
    revision_limit_reached = bool(
        decisions
        and decisions[-1].action
        == OrchestratorAction.REVISION_LIMIT_REACHED
    )
    feedback_processing = (
        state.current_step.value
        in {"collect_human_feedback", "revise_test_points"}
        or revision_limit_reached
    )
    return "人工反馈" if feedback_processing else RESULT_TABS[0]


def _test_point_signature(state: TestAnalysisState | None) -> str:
    if state is None or not state.test_points:
        return ""
    payload = json.dumps(
        state.test_points,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _workbench_description(state: TestAnalysisState | None) -> str:
    if state is None:
        return "输入需求或上传PRD，准备创建测试分析任务。"
    if state.status == AgentStatus.WAITING_FOR_USER:
        return "查看原始需求，并完成当前待确认内容。"
    return "原始需求保持只读，便于与右侧分析结果对照。"


def _render_workbench_body() -> None:
    state = st.session_state.get(STATE_KEY)

    if state is not None:
        st.caption("原始需求（任务创建后保持只读）")
        st.code(
            state.requirement,
            language=None,
            wrap_lines=True,
        )
    else:
        st.text_area(
            "输入需求描述或粘贴 PRD 内容",
            height=260,
            placeholder=(
                "示例：用户提交订单时系统校验库存，库存充足则创建订单并扣减库存，"
                "库存不足则提示失败。"
            ),
            key="agent_requirement_input",
        )
        st.file_uploader(
            "或者上传 PRD 文档",
            type=["txt", "md", "pdf", "docx"],
            key="agent_prd_uploader",
        )
        st.caption(
            "历史测试经验由 Agent 自动从默认知识文件和 Milvus 检索，"
            "无需在每次任务中重复上传。"
        )

    pending_business_feedback = (
        HumanFeedbackHandler.pending_confirmation_feedback(state)
        if state is not None
        else []
    )
    if (
        state is not None
        and state.status == AgentStatus.WAITING_FOR_USER
        and pending_business_feedback
    ):
        st.divider()
        _render_business_rule_confirmation_content(
            state,
            pending_business_feedback[0],
        )
    elif (
        state is not None
        and state.status == AgentStatus.WAITING_FOR_USER
        and state.open_questions
    ):
        st.divider()
        if st.session_state[PENDING_CLARIFICATIONS_KEY] is None:
            _render_clarification_content(state)
        else:
            st.success("补充信息已提交，正在重新分析需求。")


def _render_workbench_footer() -> None:
    state = st.session_state.get(STATE_KEY)
    if state is None:
        requirement_text = st.session_state.get(
            "agent_requirement_input",
            "",
        )
        uploaded_prd = st.session_state.get("agent_prd_uploader")
        has_input = bool(requirement_text.strip()) or uploaded_prd is not None
        start_col, reset_col = st.columns([2.2, 1])
        with start_col:
            start_clicked = st.button(
                "启动测试分析 Agent",
                type="primary",
                disabled=not has_input,
                use_container_width=True,
            )
        with reset_col:
            reset_clicked = st.button(
                "重置输入",
                type="secondary",
                use_container_width=True,
            )
        if reset_clicked:
            _clear_page_view_state()
            _reset_session()
            st.rerun()
        if start_clicked:
            _create_agent_task(requirement_text, uploaded_prd)
            st.rerun()
        return

    pending_business_feedback = (
        HumanFeedbackHandler.pending_confirmation_feedback(state)
    )
    if (
        state.status == AgentStatus.WAITING_FOR_USER
        and pending_business_feedback
    ):
        _render_business_rule_confirmation_actions(
            state,
            pending_business_feedback[0],
        )
        return
    if (
        state.status == AgentStatus.WAITING_FOR_USER
        and state.open_questions
        and st.session_state[PENDING_CLARIFICATIONS_KEY] is None
    ):
        if st.button(
            "提交补充并继续执行",
            type="primary",
            use_container_width=True,
            key=f"submit_clarifications_{state.task_id}",
        ):
            _submit_clarifications(state)
        return

    execution_active = _execution_is_active(state)
    if execution_active:
        st.button(
            "新建分析",
            type="secondary",
            disabled=True,
            use_container_width=True,
        )
        st.caption("当前节点结束后即可新建分析。")
        return

    label = "重新开始" if state.status == AgentStatus.FAILED else "新建分析"
    if st.button(
        label,
        type="secondary",
        use_container_width=True,
    ):
        _clear_page_view_state()
        _reset_session()
        st.rerun()


def _execution_is_active(
    state: TestAnalysisState | None,
) -> bool:
    if state is None:
        return False
    stored = _task_store().get(state.task_id, {})
    if stored.get("in_progress"):
        return True
    if st.session_state.get(PENDING_CLARIFICATIONS_KEY) is not None:
        return True
    if state.status in {
        AgentStatus.WAITING_FOR_USER,
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
    }:
        return False
    return bool(st.session_state.get(AUTO_RUN_KEY))


def _can_collect_feedback(state: TestAnalysisState) -> bool:
    if not state.test_points:
        return False
    if state.status == AgentStatus.COMPLETED:
        return True
    decisions = st.session_state.get(DECISIONS_KEY, [])
    return bool(
        state.status == AgentStatus.RUNNING
        and decisions
        and decisions[-1].action
        == OrchestratorAction.REVISION_LIMIT_REACHED
    )


def _render_clarification_content(state: TestAnalysisState) -> None:
    st.subheader("需要你确认")
    st.info(
        "Agent 只保留了会影响核心业务结果的问题。每项可以直接回答，"
        "也可以选择“暂不确定”，后者会作为风险写入报告。"
    )

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


def _submit_clarifications(state: TestAnalysisState) -> None:
    answers: dict[str, str | None] = {}
    unanswered: list[str] = []
    for index, question in enumerate(state.open_questions, start=1):
        deferred_key = f"clarification_deferred_{state.task_id}_{index}"
        answer_key = f"clarification_answer_{state.task_id}_{index}"
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


def _render_human_feedback_form(state: TestAnalysisState) -> None:
    form_version = st.session_state[FEEDBACK_FORM_VERSION_KEY]
    st.subheader("人工反馈")
    st.info(
        "测试建议会直接进入修正；新增或修改业务规则需要再次确认，"
        "确认前不会写入需求事实。"
    )

    feedback_type_label = st.radio(
        "反馈类型",
        ["测试建议", "业务规则"],
        horizontal=True,
        key=f"feedback_type_{state.task_id}_{form_version}",
    )
    feedback_type = (
        "test_suggestion"
        if feedback_type_label == "测试建议"
        else "business_rule"
    )
    action_labels = (
        ["新增", "修改", "删除", "调整优先级"]
        if feedback_type == "test_suggestion"
        else ["新增", "修改", "删除"]
    )
    action_label = st.selectbox(
        "希望 Agent 如何处理",
        action_labels,
        key=(
            f"feedback_action_{state.task_id}_{form_version}_"
            f"{feedback_type}"
        ),
    )
    action = {
        "新增": "add",
        "修改": "modify",
        "删除": "remove",
        "调整优先级": "update_priority",
    }[action_label]

    target_options = (
        [
            str(test_point.get("title", "")).strip()
            for test_point in state.test_points
            if str(test_point.get("title", "")).strip()
        ]
        if feedback_type == "test_suggestion"
        else list(state.business_rules)
    )
    target_unavailable = action != "add" and not target_options
    if action == "add":
        target = (
            "新增测试点"
            if feedback_type == "test_suggestion"
            else "新增业务规则"
        )
    elif target_unavailable:
        target = ""
        st.warning("当前没有可供修改或删除的目标，请改为“新增”。")
    else:
        target = st.selectbox(
            "选择目标",
            target_options,
            key=(
                f"feedback_target_{state.task_id}_"
                f"{form_version}_{feedback_type}_{action}"
            ),
        )

    if action == "update_priority":
        priority = st.selectbox(
            "调整后的优先级",
            ["P0", "P1", "P2"],
            key=f"feedback_priority_{state.task_id}_{form_version}",
        )
        content = f"将测试点优先级调整为 {priority}"
    elif action == "remove":
        content = f"删除：{target}" if target else ""
    else:
        content = st.text_area(
            "反馈内容",
            height=90,
            placeholder=(
                "请说明希望新增或修改的场景、步骤、预期结果或业务规则。"
            ),
            key=(
                f"feedback_content_{state.task_id}_"
                f"{form_version}_{feedback_type}_{action}"
            ),
        ).strip()

    reason = st.text_area(
        "原因或依据",
        height=70,
        placeholder="例如：需求原文、线上问题、遗漏风险或评审结论。",
        key=f"feedback_reason_{state.task_id}_{form_version}",
    ).strip()
    submitted = st.button(
        "提交人工反馈",
        type="primary",
        use_container_width=True,
        disabled=target_unavailable,
        key=f"submit_feedback_{state.task_id}_{form_version}",
    )
    if not submitted:
        return
    if not content or not reason:
        st.error("请填写反馈内容及原因或依据。")
        return

    try:
        feedback = HumanFeedbackHandler().submit(
            state,
            {
                "action": action,
                "feedback_type": feedback_type,
                "target": target,
                "content": content,
                "reason": reason,
            },
        )
        st.session_state[AUTO_RUN_KEY] = (
            feedback.status == FeedbackStatus.READY
        )
        st.session_state[PENDING_CLARIFICATIONS_KEY] = None
        st.session_state[EXECUTION_STEPS_KEY] = 0
        st.session_state[FEEDBACK_FORM_VERSION_KEY] += 1
        st.session_state[FEEDBACK_NOTICE_KEY] = (
            "人工反馈已接收。Agent 将按“修正测试点 → 重新评审 → "
            "更新报告”继续执行。"
        )
        _persist_task()
        st.rerun()
    except Exception as exc:
        st.error(f"人工反馈提交失败：{exc}")


def _render_business_rule_confirmation_content(state, feedback) -> None:
    st.subheader("确认业务规则")
    st.warning(
        "下面的内容会改变正式需求事实。只有确认后，Agent 才会据此修改测试点。"
    )
    st.markdown(f"**操作：** {feedback.action.value}")
    st.markdown(f"**目标：** {feedback.target}")
    st.markdown(f"**规则内容：** {feedback.content}")
    st.markdown(f"**依据：** {feedback.reason}")



def _render_business_rule_confirmation_actions(state, feedback) -> None:
    confirm_col, reject_col = st.columns(2)
    with confirm_col:
        confirmed = st.button(
            "确认规则并继续",
            type="primary",
            use_container_width=True,
            key=f"confirm_business_rule_{feedback.feedback_id}",
        )
    with reject_col:
        rejected = st.button(
            "取消该规则",
            use_container_width=True,
            key=f"reject_business_rule_{feedback.feedback_id}",
        )
    if not confirmed and not rejected:
        return

    try:
        handler = HumanFeedbackHandler()
        if confirmed:
            handler.confirm_business_rule(state, feedback.feedback_id)
        else:
            handler.reject_business_rule(state, feedback.feedback_id)
        st.session_state[AUTO_RUN_KEY] = True
        st.session_state[EXECUTION_STEPS_KEY] = 0
        _persist_task()
        st.rerun()
    except Exception as exc:
        st.error(f"业务规则确认失败：{exc}")


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
        st.session_state[FEEDBACK_FORM_VERSION_KEY] = 0
        st.session_state[FEEDBACK_NOTICE_KEY] = None
        _persist_task()
    except Exception as exc:
        _show_execution_error(exc, "Agent 启动失败")


def _process_agent_step(execution_placeholder) -> None:
    state = st.session_state.get(STATE_KEY)
    if state is None:
        return

    stored = _task_store().get(state.task_id, {})
    if stored.get("in_progress"):
        _render_execution_status(
            execution_placeholder,
            state,
            active=True,
        )
        return
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
            _render_execution_status(
                execution_placeholder,
                state,
                active=True,
                action=OrchestratorAction.ANALYZE_REQUIREMENT.value,
            )
            started_at = time.perf_counter()
            RequirementAnalyzer().reanalyze_with_clarifications(
                state,
                pending_answers,
            )
            st.session_state[DECISIONS_KEY].append(
                OrchestratorDecision(
                    action=OrchestratorAction.ANALYZE_REQUIREMENT,
                    reason="已收到用户补充信息，重新执行结构化需求分析",
                    duration_seconds=round(
                        time.perf_counter() - started_at,
                        2,
                    ),
                )
            )
            st.session_state[EXECUTION_STEPS_KEY] += 1
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

    orchestrator = AgentOrchestrator()
    next_decision = orchestrator.decide_next(state)
    _render_execution_status(
        execution_placeholder,
        state,
        active=True,
        action=next_decision.action.value,
    )
    decision = orchestrator.run_next(state)
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


def _render_result_panel(state: TestAnalysisState | None):
    if state is None:
        st.subheader("任务概览")
        with st.container(height=RIGHT_RESULT_HEIGHT, border=False):
            st.markdown(
                '<span class="agent-empty-scroll-marker"></span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class="agent-empty-result">
                  <div class="agent-empty-result__content">
                    <strong>分析结果将在这里持续展示</strong>
                    <p>
                      在左侧输入需求或上传PRD并启动分析。任务开始后，
                      这里会显示阶段进度、结构化测试点、质量评审和最终报告。
                    </p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return st.empty()

    overview = task_overview(state)
    decisions = st.session_state.get(DECISIONS_KEY, [])
    header = task_header(
        state,
        decisions,
    )
    title_col, state_col = st.columns([1, 2.4])
    with title_col:
        st.subheader("任务概览")
    with state_col:
        st.markdown(
            f"**{header['status_label']} · "
            f"当前阶段：{header['stage_label']}**"
        )
    st.markdown(
        stage_progress_html(state),
        unsafe_allow_html=True,
    )
    execution_placeholder = st.empty()
    _render_execution_status(
        execution_placeholder,
        state,
        active=_execution_is_active(state),
    )
    score = (
        overview["overall_score"]
        if overview["overall_score"] is not None
        else "待评审"
    )
    summary_col, details_col = st.columns([3.2, 1])
    with summary_col:
        st.caption(
            f"测试点 {overview['test_point_count']} · "
            f"Reviewer {score} · "
            f"自动修正 {overview['automatic_revision_count']}"
            f"/{state.max_revision_count} · "
            f"人工修正 {overview['human_revision_count']}"
        )
    with details_col:
        if st.button(
            "查看执行详情",
            type="secondary",
            use_container_width=True,
            key=f"{EXECUTION_DIALOG_BUTTON_PREFIX}_{state.task_id}",
        ):
            _render_execution_details_dialog(state, decisions)
    _render_blocked_state(state)

    active_tab = st.radio(
        "结果导航",
        RESULT_TABS,
        horizontal=True,
        label_visibility="collapsed",
        key=RESULT_ACTIVE_TAB_KEY,
    )
    compact_result_body = (
        state.status
        in {
            AgentStatus.WAITING_FOR_USER,
            AgentStatus.FAILED,
        }
        or bool(
            decisions
            and decisions[-1].action
            == OrchestratorAction.REVISION_LIMIT_REACHED
        )
    )
    scroll_marker_class = "agent-result-scroll-marker"
    if compact_result_body:
        scroll_marker_class += " agent-blocked-result-scroll-marker"
    with st.container(height=RIGHT_RESULT_HEIGHT, border=False):
        st.markdown(
            f'<span class="{scroll_marker_class}"></span>',
            unsafe_allow_html=True,
        )
        if active_tab == "结构化测试点":
            _render_test_points_tab(state)
        elif active_tab == "质量评审":
            _render_quality(state)
        elif active_tab == "人工反馈":
            _render_feedback_tab(state)
        else:
            _render_report_tab(state)

    return execution_placeholder


def _render_execution_status(
    placeholder,
    state: TestAnalysisState,
    *,
    active: bool,
    action: str | None = None,
) -> None:
    content = execution_status_content(state, action)
    progress_items = recent_progress_items(state)

    if active:
        title = content["title"]
        status_state = "running"
        description = content["description"]
        waiting = content["waiting"]
    elif state.status == AgentStatus.FAILED:
        title = "当前节点执行失败"
        status_state = "error"
        description = (
            state.error_message
            or "任务执行失败，请查看错误信息后重新发起分析。"
        )
        waiting = "动态执行状态已停止。"
    elif state.status == AgentStatus.COMPLETED:
        title = "测试分析任务已完成"
        status_state = "complete"
        description = "结构化测试点、质量评审和最终报告已经生成。"
        waiting = "可以继续浏览结果、下载报告或提交人工反馈。"
    elif state.status == AgentStatus.WAITING_FOR_USER:
        title = "任务正在等待用户操作"
        status_state = "complete"
        description = (
            "Agent已暂停执行，请在左侧完成需求补充或业务规则确认。"
        )
        waiting = "提交后会恢复同一任务，不会重新创建AgentState。"
    else:
        title = "自动执行已暂停"
        status_state = "complete"
        description = (
            "当前没有正在执行的Agent节点，请根据页面提示继续操作。"
        )
        waiting = "动态执行状态已停止。"

    with placeholder.container():
        st.status(
            title,
            state=status_state,
            expanded=False,
        )
        recent = progress_items[-1] if progress_items else waiting
        st.markdown(
            f"<div class='agent-execution-summary'>{escape(description)}"
            f"<br><span>最近进展：{escape(recent)}</span></div>",
            unsafe_allow_html=True,
        )


def _render_test_points_tab(state: TestAnalysisState) -> None:
    if state.test_points:
        _render_test_point_list(state)
    else:
        st.caption("当前尚未生成结构化测试点。")


def _render_report_tab(state: TestAnalysisState) -> None:
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


@st.dialog("执行详情", width="large")
def _render_execution_details_dialog(
    state: TestAnalysisState,
    decisions: list[OrchestratorDecision],
) -> None:
    with st.container(height=EXECUTION_DETAILS_HEIGHT, border=False):
        if decisions:
            st.markdown("#### Orchestrator 决策")
            st.markdown(
                static_table_html(decision_rows(decisions)),
                unsafe_allow_html=True,
            )
        st.markdown("#### Agent 事件")
        st.markdown(
            static_table_html(event_rows(state)),
            unsafe_allow_html=True,
        )


@st.dialog("测试点详情", width="large")
def _render_test_point_details_dialog(test_point: dict) -> None:
    st.markdown(f"### {test_point.get('title', '未命名测试点')}")
    with st.container(height=TEST_POINT_DETAILS_HEIGHT, border=False):
        _render_detail_items(
            "前置条件",
            test_point.get("preconditions", []),
        )
        _render_detail_items("执行步骤", test_point.get("steps", []))
        _render_detail_items(
            "预期结果",
            test_point.get("expected_results", []),
        )
        _render_detail_items("来源", test_point.get("sources", []))


def _render_test_point_list(state: TestAnalysisState) -> None:
    total_points = len(state.test_points)
    total_pages = max(1, math.ceil(total_points / TEST_POINT_PAGE_SIZE))
    current_page = min(
        max(int(st.session_state.get(TEST_POINT_PAGE_KEY, 1)), 1),
        total_pages,
    )
    st.session_state[TEST_POINT_PAGE_KEY] = current_page

    page_start = (current_page - 1) * TEST_POINT_PAGE_SIZE
    page_end = min(page_start + TEST_POINT_PAGE_SIZE, total_points)
    visible_points = state.test_points[page_start:page_end]

    st.caption(
        f"共 {total_points} 条 · 第 {current_page}/{total_pages} 页 · "
        f"每页 {TEST_POINT_PAGE_SIZE} 条"
    )
    for absolute_index, test_point in enumerate(
        visible_points,
        start=page_start + 1,
    ):
        point_identity = _test_point_identity(test_point)
        st.markdown(
            test_point_summary_html(test_point, absolute_index),
            unsafe_allow_html=True,
        )
        if st.button(
            "查看详情",
            type="secondary",
            key=_test_point_toggle_key(state, point_identity),
        ):
            st.session_state[TEST_POINT_DETAIL_ID_KEY] = point_identity
            _render_test_point_details_dialog(test_point)
        if absolute_index < page_end:
            st.divider()

    previous_col, page_col, next_col = st.columns([1, 1.2, 1])
    with previous_col:
        previous_clicked = st.button(
            "上一页",
            disabled=current_page <= 1,
            use_container_width=True,
            key=f"agent_ui_previous_page_{state.task_id}",
        )
    with page_col:
        st.markdown(
            f"<div style='text-align:center;padding-top:0.5rem;'>"
            f"第 {current_page}/{total_pages} 页</div>",
            unsafe_allow_html=True,
        )
    with next_col:
        next_clicked = st.button(
            "下一页",
            disabled=current_page >= total_pages,
            use_container_width=True,
            key=f"agent_ui_next_page_{state.task_id}",
        )

    if previous_clicked or next_clicked:
        st.session_state[TEST_POINT_PAGE_KEY] = (
            current_page - 1 if previous_clicked else current_page + 1
        )
        st.session_state[TEST_POINT_EXPANDED_KEY] = None
        st.session_state[TEST_POINT_DETAIL_ID_KEY] = None
        st.rerun()


def _test_point_identity(test_point: dict) -> str:
    explicit_id = (
        test_point.get("test_point_id")
        or test_point.get("id")
    )
    if explicit_id is not None and str(explicit_id).strip():
        return str(explicit_id).strip()
    payload = json.dumps(
        test_point,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _test_point_toggle_key(
    state: TestAnalysisState,
    point_identity: str,
) -> str:
    digest = hashlib.sha256(
        point_identity.encode("utf-8")
    ).hexdigest()[:16]
    return f"agent_ui_toggle_test_point_{state.task_id}_{digest}"


def _render_detail_items(label: str, values) -> None:
    st.markdown(f"**{label}**")
    items = [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]
    if not items:
        st.caption("未提供")
        return
    for item in items:
        st.markdown(f"- {item}")


def _render_feedback_tab(state: TestAnalysisState) -> None:
    feedback_notice = st.session_state.pop(FEEDBACK_NOTICE_KEY, None)
    if feedback_notice:
        st.success(feedback_notice)

    rows = feedback_rows(state)
    if rows:
        st.markdown(
            static_table_html(rows),
            unsafe_allow_html=True,
        )
    else:
        st.caption("当前尚未提交人工反馈。")

    pending_business_feedback = (
        HumanFeedbackHandler.pending_confirmation_feedback(state)
    )
    if pending_business_feedback:
        st.info("请先在左侧需求工作台确认或取消待处理的业务规则。")
    elif _can_collect_feedback(state):
        st.divider()
        _render_human_feedback_form(state)
    elif state.status == AgentStatus.RUNNING and rows:
        st.info("Agent 正在应用人工反馈，完成后会更新评审结果和最终报告。")


def _render_blocked_state(state: TestAnalysisState) -> None:
    if state.status == AgentStatus.WAITING_FOR_USER:
        return
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
                "自动修正已达到上限，当前结果会保留且不会标记为质量通过。"
                "请进入“人工反馈”Tab补充处理意见。"
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
            FEEDBACK_FORM_VERSION_KEY,
            FEEDBACK_NOTICE_KEY,
            "agent_requirement_input",
            "agent_prd_uploader",
        } or key.startswith(
            (
                "clarification_",
                "feedback_",
                "submit_feedback_",
                "confirm_business_rule_",
                "reject_business_rule_",
            )
        ):
            st.session_state.pop(key, None)
