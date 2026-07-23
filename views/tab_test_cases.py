import streamlit as st
from utils.test_manager import TestAssistantManager


def render_ui():
    st.header("自动化用例生成")

    col1, col2 = st.columns([2, 1])

    with col1:
        with st.container(border=True):
            st.subheader("测试点输入")
            test_points_text = st.text_area(
                "请粘贴测试点文档内容",
                height=300,
                placeholder="在这里输入测试点文档..."
            )
            uploaded_test_points = st.file_uploader("或者上传测试点文档", type=["md", "txt"])

    with col2:
        with st.container(border=True):
            st.subheader("项目配置")
            module_name = st.text_input("模块名称", placeholder="例如：user_service")
            class_name = st.text_input("类名", placeholder="例如：UserService")
            method_name = st.text_input("方法名", placeholder="例如：login")

    has_input = bool(test_points_text and test_points_text.strip()) or uploaded_test_points is not None
    generate_cases_btn = st.button("🚀 生成测试用例", type="primary", disabled=not has_input)

    if generate_cases_btn:
        test_manager = TestAssistantManager()

        test_points_content = test_points_text
        if uploaded_test_points:
            test_points_content = uploaded_test_points.read().decode("utf-8")

        with st.status("正在生成测试用例...", expanded=True) as status:
            status.write("📝 正在解析测试点文档...")
            status.write("⚙️ 正在生成 pytest 用例骨架...")

        result_container = st.empty()
        chunks = []
        for chunk in test_manager.generate_test_cases_stream(
            test_points_content, module_name, class_name, method_name
        ):
            chunks.append(chunk)
            result_container.markdown("".join(chunks))

        status.update(label="✅ 测试用例生成完毕！", state="complete", expanded=False)

        with st.container(border=True):
            st.subheader("生成结果")
            st.code("".join(chunks), language="python")
            st.download_button(
                "📥 下载测试用例",
                data="".join(chunks),
                file_name="test_cases.py",
                mime="text/x-python"
            )
