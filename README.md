# Test Analysis Agent

一个面向测试工程师的智能测试分析项目。当前版本聚焦于读取 PRD 或需求描述，结合本地 Bug 经验与 Milvus 历史测试资产，生成可评审、可追踪的结构化测试分析报告，并支持用户提交结构化反馈后重新修正、评审和生成报告。

> 当前只有“测试分析报告生成”功能完成。自动化用例生成和异常日志分析仍在规划中，因此暂未在页面展示。

## 当前能力

- 输入文本，或上传 TXT、Markdown、PDF、DOCX 格式的需求文档
- 页面调用完整Agent链路生成结构化测试分析结果
- 使用 Milvus 与 Embedding 服务检索相似历史测试资产
- 展示Agent阶段进度；Orchestrator决策和完整节点事件收纳在默认折叠的执行详情中
- 展示结构化测试点和Reviewer多维评分
- 展示并下载Finalizer生成的Markdown报告
- 内部已实现结构化需求分析节点，可识别需求事实、推导风险和待确认项
- 内部已实现知识检索节点，可区分历史资产命中、无匹配和服务降级
- 内部已实现结构化测试点生成节点，支持分类、优先级、执行步骤、预期结果和来源追踪
- 内部已实现测试点质量评审节点，可检查需求覆盖、边界异常、重复项、幻觉风险和可执行性
- 内部已实现测试点定向修正节点，可根据Reviewer问题修正并强制重新评审
- 已实现结构化人工反馈，可区分测试建议与需确认的业务规则并驱动Reviser
- 内部已实现受控Python编排器，可自动串联节点、限制修正次数并保留每轮变化
- 内部已实现Finalizer，可确定性汇总覆盖、质量、来源、风险和最终Markdown报告
- Streamlit已接入Agent自动主路径，采用左侧需求工作台、右侧任务结果区的双栏布局，并以页面外层滚动为主
- 待确认问题每轮最多3个，用户可以回答或选择“暂不确定”，随后恢复同一Agent任务
- Agent按节点逐步执行并自动刷新轨迹；普通浏览器刷新可在服务进程存活期间恢复当前任务
- 执行区显示当前真实节点和预计等待提示，节点完成后在决策轨迹中记录实际耗时
- 页面使用中文步骤与分类标签，最终Markdown报告以表格展示结构化测试点
- 页面支持新增、修改、删除测试点和调整优先级，并展示反馈处理状态
- 任务创建后左侧使用State中的原始需求进行只读对照；人工反馈统一在右侧Tab提交
- 所有任务状态共用最大1360px工作区；完成态扩大结果栏，测试点使用摘要列表与可展开详情
- 新增或修改业务规则需要用户二次确认，取消的规则不会进入需求事实
- 自动修正和人工反馈修正分别计数，人工反馈不会被自动修正次数上限拦截
- 人工反馈修正使用独立最小作用域：不混入已通过的旧Reviewer建议，并限制允许的操作类型和数量
- 人工反馈提交后显示受理提示并重置表单，降低等待期间重复提交的风险
- 结构化LLM节点启用JSON Output、截断检测和一次受控校验重试
- Reviewer会将可选问题列表中的纯空白占位归一化为空列表，同时继续拒绝错误数据类型
- Generator与Reviewer使用8192的大体量输出预算；Reviser只返回增删改操作，由Python校验并原子合并，避免重复输出完整测试点集合

## 项目结构

```text
.
├── AGENTS.md               # Codex跨设备协作与开发约定
├── main.py                 # Streamlit 应用入口
├── agent/                  # Agent状态、事件及后续节点
├── views/                  # 页面与交互状态
├── services/               # LLM、RAG、文档解析应用服务
├── utils/                  # 基础客户端、配置及兼容业务入口
├── prompts/                # 模型提示词
├── knowledge/              # 本地测试知识
├── docs/                   # 当前接力状态与开发复盘
└── tests/                  # 自动化测试
```

当前页面已经不再调用 `TestAssistantManager`。该类只作为旧 Workflow 兼容实现保留；当前主入口由
`TestAnalysisState + AgentOrchestrator` 驱动，LLM、RAG、Prompt 和文档解析继续通过
`services` 层隔离。

## 开发过程与设计说明

当前产品范围与项目从 Workflow 向 Agent 演进的过程，请查看：

- [当前产品需求说明书 V2](docs/product/PRD_AGENT_V2.md)
- [项目文档导航](docs/README.md)
- [当前开发状态与跨设备接力](docs/CURRENT_STATUS.md)
- [开发与复盘日志](docs/DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](docs/LEARNING_NOTES.md)

V1 Workflow PRD 已归档在 [docs/archive/PRD_WORKFLOW_V1.md](docs/archive/PRD_WORKFLOW_V1.md)，不再代表当前产品范围。Codex 的仓库级协作规则位于 [AGENTS.md](AGENTS.md)。

## 本地运行

建议使用 Python 3.10 或更高版本。

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run main.py
```

也可以使用无头模式启动：

```powershell
python -m streamlit run main.py --server.headless=true
```

运行错误会显示在页面任务状态中；结构化JSON校验失败和受控重试信息同时输出到启动命令所在的PowerShell窗口。

运行前请在 `.env` 中填写真实的 `DEEPSEEK_API_KEY`。`.env` 已加入 Git 忽略规则，请勿提交真实密钥。

## 外部依赖

测试资产检索当前依赖：

- Milvus 向量数据库
- 提供 `nomic-embed-text` 模型的 Embedding 服务
- DeepSeek 兼容的 Chat Completions API

Milvus 与 Embedding 地址目前仍由现有 RAG 客户端配置。后续阶段会统一迁移到环境变量。

## 后续计划

1. 设计MySQL历史任务持久化与跨服务重启恢复
2. 完善修正历史、达到修正上限后的人工处理和知识沉淀交互
3. 建立离线评测集，量化 RAG 和 Reviewer 带来的覆盖率提升
4. Agent 核心稳定后，再评估 FastAPI + React/Vue 前后端分离
