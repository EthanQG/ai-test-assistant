import streamlit as st
from utils.knowledge_base import KnowledgeBaseManager
from utils.test_manager import TestAssistantManager
from utils.file_parser import extract_text_from_file


def render_ui():
    st.header("需求转测试点")

    if "test_points_result" not in st.session_state:
        st.session_state.test_points_result = ""
    if "test_points_prd_title" not in st.session_state:
        st.session_state.test_points_prd_title = ""
    if "rag_info" not in st.session_state:
        st.session_state.rag_info = {}

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("需求输入")
        requirement_text = st.text_area(
            "请输入需求描述或粘贴PRD内容",
            height=300,
            placeholder="在这里输入需求描述..."
        )
        uploaded_prd = st.file_uploader(
            "或者上传PRD文档",
            type=["txt", "md", "pdf", "docx"]
        )

    with col2:
        st.subheader("知识库配置")
        st.markdown("选择本地Bug经验知识库（可选）")
        uploaded_knowledge = st.file_uploader(
            "上传知识库文件",
            type=["txt", "md", "pdf", "docx"]
        )

    has_input = bool(requirement_text.strip()) or uploaded_prd is not None
    generate_btn = st.button("🚀 生成测试点", type="primary", disabled=not has_input)

    if generate_btn:
        kb_manager = KnowledgeBaseManager()
        test_manager = TestAssistantManager()

        prd_content = requirement_text.strip()
        prd_title = requirement_text.strip().split('\n')[0] if requirement_text.strip() else ""
        
        if uploaded_prd:
            try:
                prd_content = extract_text_from_file(uploaded_prd)
                if not prd_title:
                    prd_title = uploaded_prd.name.replace('.md', '').replace('.txt', '').replace('.pdf', '').replace('.docx', '')
            except ValueError as e:
                st.error(f"PRD文档解析失败: {str(e)}")
                return

        bug_kb_content = ""
        bug_kb_source = "未使用"
        if uploaded_knowledge:
            try:
                bug_kb_content = extract_text_from_file(uploaded_knowledge)
                bug_kb_source = f"上传文件: {uploaded_knowledge.name}"
            except ValueError as e:
                st.error(f"知识库文件解析失败: {str(e)}")
                return
        else:
            bug_kb_content = kb_manager.load_bug_experience()
            if bug_kb_content:
                bug_kb_source = "默认Bug经验库"

        history_kb_content = kb_manager.load_history_test_points()
        history_count = len(history_kb_content.split("【历史测试点")) - 1 if history_kb_content else 0

        st.session_state.rag_info = {
            "bug_kb_source": bug_kb_source,
            "bug_kb_length": len(bug_kb_content),
            "history_count": history_count,
            "history_length": len(history_kb_content)
        }

        with st.spinner("AI正在分析需求并生成测试点..."):
            st.subheader("生成结果")
            result_container = st.empty()
            full_result = ""

            for chunk in test_manager.generate_test_points_stream(
                prd_content, bug_kb_content, history_kb_content
            ):
                full_result += chunk
                result_container.markdown(full_result)

            st.session_state.test_points_result = full_result
            st.session_state.test_points_prd_title = prd_title

    if st.session_state.test_points_result:
        st.subheader("生成结果")
        st.markdown(st.session_state.test_points_result)

        if st.session_state.rag_info:
            with st.expander("🔍 RAG 上下文信息（验证知识库使用情况）"):
                rag_info = st.session_state.rag_info
                st.markdown(f"""
                **知识库使用情况：**
                - Bug经验知识库：{rag_info['bug_kb_source']}（{rag_info['bug_kb_length']} 字符）
                - 历史测试点：{'已加载 ' + str(rag_info['history_count']) + ' 个文件' if rag_info['history_count'] > 0 else '未加载'}（{rag_info['history_length']} 字符）
                """)

        col_download, col_save = st.columns(2)
        with col_download:
            st.download_button(
                "📥 下载测试点文档",
                data=st.session_state.test_points_result,
                file_name="test_points.md",
                mime="text/markdown"
            )
        with col_save:
            if st.button("💾 保存到本地用例库"):
                try:
                    kb_manager = KnowledgeBaseManager()
                    kb_manager.save_test_points(st.session_state.test_points_result, st.session_state.test_points_prd_title)
                    st.success("🎉 已成功保存至本地测试资产库！")
                except ValueError as e:
                    st.error(f"保存失败: {str(e)}")