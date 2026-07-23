import streamlit as st
from views import render_test_points, render_test_cases, render_log_analysis

st.set_page_config(
    page_title="AI Test Assistant",
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
    padding-top: 4rem;
    padding-bottom: 3rem;
    max-width: 1200px;
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

st.title("🧪 AI Test Assistant")

tab1, tab2, tab3 = st.tabs([
    "📋 生成测试分析报告",
    "🧑‍💻 自动化用例生成",
    "🔍 异常日志分析"
])

with tab1:
    render_test_points()

with tab2:
    render_test_cases()

with tab3:
    render_log_analysis()
