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
/* 主内容区宽度与间距 */
.block-container {
    padding-top: 3.75rem;
    padding-bottom: 2rem;
    max-width: 1600px;
}
/* 全局字体 */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
}

/* ── 按钮统一样式 ── */
.stButton > button,
.stDownloadButton > button {
    width: 100% !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.5rem 1.5rem !important;
    font-weight: 500 !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.14) !important;
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
    background-color: #E2E8F0 !important;
    color: #1E293B !important;
}
.stButton > button[kind="secondary"]:hover {
    background-color: #CBD5E1 !important;
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
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
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
    gap: 0.5rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1.2rem;
    font-weight: 500;
}

/* ── 标题间距 ── */
h1, h2, h3 {
    padding-top: 0.3rem;
}

/* ── 分割线 ── */
hr {
    border: none;
    border-top: 1px solid #E2E8F0;
    margin: 16px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🧪 Test Analysis Agent")
st.caption("基于大模型与历史测试资产检索的智能测试分析助手")

render_test_points()
