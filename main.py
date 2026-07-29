import streamlit as st
from views import render_test_points

st.set_page_config(
    page_title="Test Analysis Agent",
    page_icon="🧪",
    layout="wide",
)

# ── 全局现代 UI 样式 ──
st.markdown("""
<style>
/* 整体背景 */
.stApp {
    background-color: #F8F9FA;
}
/* 所有任务状态共用同一个宽屏工作区 */
[data-testid="stAppViewBlockContainer"],
.block-container {
    padding-top: 3rem;
    padding-bottom: 1.5rem;
    width: 100%;
    max-width: 1360px;
    margin-left: auto;
    margin-right: auto;
}
/* 未创建任务时让右侧保持完整结果面板，而不是顶部矮卡片 */
.agent-empty-result {
    min-height: 470px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
}
.agent-empty-result__content {
    max-width: 32rem;
}
/* 全局字体 */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.5;
    color: #172033;
}
h1 {
    font-size: 2rem !important;
    line-height: 1.15 !important;
    margin-bottom: 0.15rem !important;
    padding-top: 0 !important;
}
h3 {
    font-size: 1.35rem !important;
    line-height: 1.3 !important;
}

/* ── 按钮统一样式 ── */
.stButton > button,
.stDownloadButton > button {
    width: 100% !important;
    border-radius: 7px !important;
    padding: 0.45rem 1rem !important;
    font-weight: 500 !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
    box-shadow: none !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    box-shadow: none !important;
}
/* 主按钮 — 深蓝主题色 */
.stButton > button[kind="primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1D4ED8 !important;
}
/* 次按钮 */
.stButton > button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #475569 !important;
    border: 1px solid #CBD5E1 !important;
}
.stButton > button[kind="secondary"]:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
}

/* ── 输入框美化 ── */
div[data-testid="stTextArea"] textarea,
div[data-testid="stTextInput"] input {
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    padding: 0.6rem 0.75rem !important;
    transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
}
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stTextInput"] input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}

/* ── 卡片容器圆角与阴影 ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 8px !important;
    border-color: #DCE2EA !important;
    box-shadow: none !important;
}

/* ── 文件上传组件 ── */
div[data-testid="stFileUploader"] {
    border-radius: 8px;
    transition: border-color 0.25s ease;
}

/* 概览卡片在窄列中保持可读，避免状态和步骤被截断 */
div[data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    line-height: 1.25 !important;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
}

/* ── Tab 标签美化 ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 0;
    padding: 0.45rem 1rem;
    font-weight: 500;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #2563EB !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #2563EB !important;
}

/* ── 流程标签弱化为状态文本 ── */
.agent-stage-progress {
    display: flex;
    gap: 0.9rem;
    flex-wrap: wrap;
    margin: 0.55rem 0 0.3rem;
}
.agent-stage {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.15rem 0;
    border-radius: 0;
    background: transparent;
    font-size: 0.875rem;
    white-space: nowrap;
}
.agent-stage--completed { color: #47705A; }
.agent-stage--current { color: #2563EB; font-weight: 600; }
.agent-stage--failed { color: #B42318; font-weight: 600; }
.agent-stage--pending { color: #94A3B8; }

/* ── 测试点摘要对齐 ── */
.agent-test-point-summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    column-gap: 1.1rem;
    row-gap: 0.3rem;
    align-items: baseline;
    padding: 0.35rem 0 0.25rem;
}
.agent-test-point-title {
    min-width: 0;
    font-weight: 600;
    color: #172033;
}
.agent-test-point-meta {
    font-size: 0.8rem;
    color: #64748B;
    white-space: nowrap;
}
.agent-test-point-scenario {
    grid-column: 1 / -1;
    font-size: 0.875rem;
    color: #64748B;
}
div[data-testid="stExpander"] details {
    border-radius: 7px !important;
    border-color: #DCE2EA !important;
    box-shadow: none !important;
}

/* ── 标题间距 ── */
h2, h3 {
    padding-top: 0.15rem;
}

/* ── 分割线 ── */
hr {
    border: none;
    border-top: 1px solid #E2E8F0;
    margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🧪 Test Analysis Agent")
st.caption("基于大模型与历史测试资产检索的智能测试分析助手")

render_test_points()
