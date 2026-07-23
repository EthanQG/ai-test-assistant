import streamlit as st
from utils.test_manager import TestAssistantManager


def render_ui():
    st.header("异常日志分析")

    with st.container(border=True):
        st.subheader("日志上传")
        uploaded_log = st.file_uploader("上传日志文件", type=["log", "txt"])

    analyze_btn = st.button("🚀 分析日志", type="primary", disabled=not uploaded_log)

    if analyze_btn:
        test_manager = TestAssistantManager()
        log_content = uploaded_log.read().decode("utf-8")

        with st.status("正在分析日志...", expanded=True) as status:
            status.write("📋 正在预过滤日志...")
            status.write("🔍 提取异常堆栈...")
            status.write("🤖 正在分析问题根因...")

        result_container = st.empty()
        chunks = []
        for chunk in test_manager.analyze_log_stream(log_content):
            chunks.append(chunk)
            result_container.markdown("".join(chunks))

        status.update(label="✅ 日志分析完毕！", state="complete", expanded=False)

        with st.container(border=True):
            st.subheader("分析结果")
            st.markdown("".join(chunks))
            st.download_button(
                "📥 下载分析报告",
                data="".join(chunks),
                file_name="log_analysis_report.md",
                mime="text/markdown"
            )
