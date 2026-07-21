import streamlit as st
from utils.config import ConfigManager
from views import render_test_points, render_test_cases, render_log_analysis

st.set_page_config(
    page_title="AI Test Assistant",
    page_icon="🧪",
    layout="wide",
)

config = ConfigManager()

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

with st.sidebar:
    st.header("⚙️ 配置")

    if not config.is_api_configured:
        st.warning("API Key 未配置")
    else:
        st.success("✅ API Key 已配置")
        st.info(f"模型: {config.model}")

    st.markdown("---")
    st.markdown("### 📖 使用说明")
    st.markdown("1. 在左侧Tab选择功能")
    st.markdown("2. 输入或上传相关文件")
    st.markdown("3. 点击生成/分析按钮")
    st.markdown("4. 查看结果并导出")