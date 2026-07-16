import streamlit as st
from utils.test_manager import TestAssistantManager


def render_ui():
    st.header("异常日志分析")

    st.subheader("日志上传")
    uploaded_log = st.file_uploader("上传日志文件", type=["log", "txt"])

    analyze_btn = st.button("🚀 分析日志", type="primary", disabled=not uploaded_log)

    if analyze_btn:
        test_manager = TestAssistantManager()
        log_content = uploaded_log.read().decode("utf-8")

        st.subheader("分析结果")
        st.write_stream(test_manager.analyze_log_stream(log_content))