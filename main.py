import streamlit as st
from views import render_test_points, render_test_cases, render_log_analysis

st.set_page_config(
    page_title="AI Test Assistant",
    page_icon="🧪",
    layout="wide",
)

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