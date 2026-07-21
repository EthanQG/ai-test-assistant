import streamlit as st
from utils.knowledge_base import KnowledgeBaseManager
from utils.test_manager import TestAssistantManager
from utils.file_parser import extract_text_from_file


def render_ui():
    st.header("生成测试分析报告")

    if "test_points_result" not in st.session_state:
        st.session_state.test_points_result = ""
    if "test_points_prd_title" not in st.session_state:
        st.session_state.test_points_prd_title = ""
    if "test_points_prd_content" not in st.session_state:
        st.session_state.test_points_prd_content = ""
    if "rag_info" not in st.session_state:
        st.session_state.rag_info = {}
    if "current_report" not in st.session_state:
        st.session_state.current_report = ""

    col1, col2 = st.columns([2, 1])

    requirement_text = ""
    uploaded_prd = None
    uploaded_knowledge = None

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
        
        has_input = bool(requirement_text.strip()) or uploaded_prd is not None
        generate_btn = st.button("🚀 生成测试分析报告", type="primary", disabled=not has_input)

    with col2:
        st.subheader("知识库配置")
        st.markdown("### 📚 Bug经验知识库（可选）")
        st.markdown("""
        上传历史Bug经验文档，AI在生成测试点时会参考这些经验，帮助你发现更多潜在问题。
        
        **支持格式**: txt, md, pdf, docx
        
        **示例内容**:
        - 历史线上故障案例
        - 常见缺陷模式
        - 业务易错点总结
        """)
        uploaded_knowledge = st.file_uploader(
            "上传知识库文件",
            type=["txt", "md", "pdf", "docx"]
        )
        
        st.markdown("---")
        st.markdown("### 🧠 Milvus向量库（自动）")
        st.markdown("""
        系统会自动从远程Milvus向量库中检索相似的历史测试分析报告，作为参考上下文。
        
        **检索逻辑**:
        1. 将当前需求转换为向量
        2. 在向量库中搜索最相似的历史记录
        3. 相似度 > 1% 才会作为参考
        """)

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

        rag_count = test_manager.get_rag_count()

        st.session_state.rag_info = {
            "bug_kb_source": bug_kb_source,
            "bug_kb_length": len(bug_kb_content),
            "rag_count": rag_count,
            "rag_used": False,
        }

        with st.spinner("正在分析需求并生成测试分析报告..."):
            result_container = st.empty()
            full_result = ""

            for chunk in test_manager.generate_test_points_stream(prd_content, bug_kb_content):
                full_result += chunk
                result_container.markdown(full_result)

            st.session_state.test_points_result = full_result
            st.session_state.current_report = full_result
            st.session_state.test_points_prd_title = prd_title
            st.session_state.test_points_prd_content = prd_content
            st.session_state.rag_info["rag_used"] = test_manager.get_rag_used()
            
            st.rerun()

    if st.session_state.test_points_result:
        st.subheader("生成结果")
        st.markdown(st.session_state.test_points_result)

        if st.session_state.rag_info:
            with st.expander("🔍 RAG 上下文信息（验证知识库使用情况）"):
                rag_info = st.session_state.rag_info
                st.markdown(f"""
                **知识库使用情况：**
                - 📚 Bug经验知识库：{rag_info['bug_kb_source']}（{rag_info['rag_count']} 字符）
                - 🧠 Milvus向量库存储：{'已存储 ' + str(rag_info['rag_count']) + ' 条测试分析报告' if rag_info['rag_count'] > 0 else '未存储'}
                - 🔍 本次检索使用：{'✅ 已检索到相似历史测试点并作为参考' if rag_info.get('rag_used', False) else '❌ 未检索到相似历史测试点'}
                """)

        col_download, col_save = st.columns(2)
        with col_download:
            download_filename = f"{st.session_state.test_points_prd_title}需求测试分析报告.md" if st.session_state.test_points_prd_title else "需求测试分析报告.md"
            st.download_button(
                "📥 下载测试点文档",
                data=st.session_state.test_points_result,
                file_name=download_filename,
                mime="text/markdown"
            )
        with col_save:
            if st.button("💾 保存分析测试报告到向量库"):
                test_manager = TestAssistantManager()
                success, message = test_manager.save_to_rag(
                    st.session_state.test_points_prd_content,
                    st.session_state.test_points_result
                )
                if success:
                    st.success(f"🎉 {message}")
                    new_count = test_manager.get_rag_count()
                    st.session_state.rag_info["rag_count"] = new_count
                else:
                    st.error(f"保存失败: {message}")

        st.markdown("---")
        st.subheader("💬 意见微调")
        
        refine_input = st.text_input("输入修改或补充意见：", key="refine_input")
        refine_btn = st.button("🔄 根据意见重新生成", type="secondary", disabled=not refine_input.strip())
        
        if refine_btn:
            test_manager = TestAssistantManager()
            
            with st.spinner("正在根据您的意见修正报告..."):
                result_container = st.empty()
                full_result = ""
                
                for chunk in test_manager.refine_test_points_stream(
                    st.session_state.test_points_prd_content,
                    st.session_state.current_report,
                    refine_input
                ):
                    full_result += chunk
                    result_container.markdown(full_result)
                
                st.session_state.current_report = full_result
                st.session_state.test_points_result = full_result
                
                st.rerun()