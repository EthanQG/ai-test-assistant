import streamlit as st
from utils.config import is_api_configured, get_deepseek_api_key

st.set_page_config(
    page_title="AI Test Assistant",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 AI Test Assistant")

tab1, tab2, tab3 = st.tabs([
    "📋 需求转测试点",
    "🧑‍💻 自动化用例生成",
    "🔍 异常日志分析"
])

with tab1:
    st.header("需求转测试点")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("需求输入")
        requirement_text = st.text_area(
            "请输入需求描述或粘贴PRD内容",
            height=300,
            placeholder="在这里输入需求描述...\n\n例如：\n用户登录功能：\n1. 用户可以通过手机号+验证码登录\n2. 支持密码登录\n3. 登录失败5次后锁定账户15分钟\n4. 支持第三方登录（微信/支付宝）"
        )

        uploaded_prd = st.file_uploader("或者上传PRD文档", type=["md", "txt"])

    with col2:
        st.subheader("知识库配置")
        st.markdown("选择本地Bug经验知识库（可选）")
        uploaded_knowledge = st.file_uploader("上传知识库文件", type=["txt"])

        if uploaded_knowledge:
            st.success(f"已上传知识库: {uploaded_knowledge.name}")

    generate_btn = st.button("🚀 生成测试点", type="primary", disabled=not requirement_text and not uploaded_prd)

    if generate_btn:
        with st.spinner("AI正在分析需求..."):
            st.info("测试点生成功能正在开发中，敬请期待！")

    st.subheader("生成结果")
    result_area = st.empty()
    result_area.markdown("生成的测试点将在这里显示...")

    download_btn = st.download_button(
        "📥 导出测试点文档",
        data="# 测试点文档\n\n待生成...",
        file_name="test_points.md",
        mime="text/markdown",
        disabled=True
    )

with tab2:
    st.header("自动化用例生成")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("测试点输入")
        test_points_text = st.text_area(
            "请粘贴测试点文档内容",
            height=300,
            placeholder="在这里输入测试点文档...\n\n例如：\n# 测试点文档\n\n## 功能测试点\n| 编号 | 测试场景 |\n|------|----------|\n| F001 | 用户正常登录 |"
        )

        uploaded_test_points = st.file_uploader("或者上传测试点文档", type=["md", "txt"])

    with col2:
        st.subheader("项目配置")
        module_name = st.text_input("模块名称", placeholder="例如：user_service")
        class_name = st.text_input("类名", placeholder="例如：UserService")
        method_name = st.text_input("方法名", placeholder="例如：login")

    generate_cases_btn = st.button("🚀 生成测试用例", type="primary", disabled=not test_points_text and not uploaded_test_points)

    if generate_cases_btn:
        with st.spinner("AI正在生成测试用例..."):
            st.info("测试用例生成功能正在开发中，敬请期待！")

    st.subheader("生成结果")
    code_result = st.empty()
    code_result.code("# pytest测试用例将在这里显示...", language="python")

    download_cases_btn = st.download_button(
        "📥 导出测试用例",
        data="# pytest测试用例\n\n待生成...",
        file_name="test_cases.py",
        mime="text/python",
        disabled=True
    )

with tab3:
    st.header("异常日志分析")

    st.subheader("日志上传")
    uploaded_log = st.file_uploader("上传日志文件", type=["log", "txt"])

    if uploaded_log:
        st.info(f"已上传日志文件: {uploaded_log.name}")
        st.info(f"文件大小: {uploaded_log.size / 1024:.2f} KB")

        log_content = uploaded_log.read().decode("utf-8", errors="ignore")
        if len(log_content) > 5000:
            st.info("日志内容较多，系统将自动预过滤后再分析")

    analyze_btn = st.button("🚀 分析日志", type="primary", disabled=not uploaded_log)

    if analyze_btn:
        with st.spinner("AI正在分析日志..."):
            st.info("日志分析功能正在开发中，敬请期待！")

    st.subheader("分析结果")
    analysis_result = st.empty()
    analysis_result.markdown("分析报告将在这里显示...")

    download_report_btn = st.download_button(
        "📥 导出分析报告",
        data="# 日志分析报告\n\n待生成...",
        file_name="log_analysis.md",
        mime="text/markdown",
        disabled=True
    )

with st.sidebar:
    st.header("⚙️ 配置")

    if not is_api_configured():
        st.warning("API Key 未配置")
        api_key_input = st.text_input(
            "DeepSeek API Key",
            type="password",
            placeholder="在此输入您的 API Key"
        )

        if api_key_input:
            st.success("API Key 已配置（临时）")
    else:
        st.success("✅ API Key 已配置")
        st.info(f"模型: deepseek-chat")

    st.markdown("---")
    st.markdown("### 📖 使用说明")
    st.markdown("1. 在左侧Tab选择功能")
    st.markdown("2. 输入或上传相关文件")
    st.markdown("3. 点击生成/分析按钮")
    st.markdown("4. 查看结果并导出")

    st.markdown("---")
    st.markdown("### 📞 联系我们")
    st.markdown("如有问题，请联系开发团队")