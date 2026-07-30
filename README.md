# Test Analysis Agent

一个面向测试工程师的智能测试分析项目。当前版本聚焦于读取 PRD 或需求描述，结合本地 Bug 经验与 Milvus 历史测试资产，生成可评审、可追踪的结构化测试分析报告，并支持用户提交结构化反馈后重新修正、评审和生成报告。

> 当前只有“测试分析报告生成”功能完成。自动化用例生成和异常日志分析仍在规划中，因此暂未在页面展示。
>
> 当前 Streamlit 页面定位为 V1 功能演示界面，用于完整展示 Agent 能力、状态流转和人工反馈闭环；不以完全复刻 DeepL 或生产级固定工作台为目标。

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
- Streamlit已接入Agent自动主路径，采用固定高度的左右工作区；左侧正文独立滚动且主要操作固定在栏底，右侧结果正文独立滚动
- 待确认问题每轮最多3个，用户可以回答或选择“暂不确定”，随后恢复同一Agent任务
- Agent按节点逐步执行并自动刷新轨迹；普通浏览器刷新可在服务进程存活期间恢复当前任务
- 执行区使用原生动态状态显示当前中文节点、处理内容、合理等待说明和最近3条关键进展，节点完成后在决策轨迹中记录实际耗时
- 页面使用中文步骤与分类标签，最终Markdown报告以表格展示结构化测试点
- 页面支持新增、修改、删除测试点和调整优先级，并展示反馈处理状态
- 结构化测试点默认每页5条，完整前置条件、步骤、预期结果和来源通过详情Dialog查看
- 任务创建后左侧使用State中的原始需求进行只读对照；人工反馈统一在右侧Tab提交
- 所有任务状态共用最大1360px工作区；完成态扩大结果栏，测试点使用摘要列表与可展开详情
- 新增或修改业务规则需要用户二次确认，取消的规则不会进入需求事实
- 自动修正和人工反馈修正分别计数，人工反馈不会被自动修正次数上限拦截
- 人工反馈修正使用独立最小作用域：不混入已通过的旧Reviewer建议，并限制允许的操作类型和数量
- 人工反馈提交后显示受理提示并重置表单，降低等待期间重复提交的风险
- 结构化LLM节点启用JSON Output、截断检测和一次受控校验重试
- Reviewer会将可选问题列表中的纯空白占位归一化为空列表，同时继续拒绝错误数据类型
- Generator与Reviewer使用8192的大体量输出预算；Reviser只返回增删改操作，由Python校验并原子合并，避免重复输出完整测试点集合
- Streamlit只调用Application Service表达创建、推进、补充、确认、反馈和重试等用户动作
- TaskRepository隔离任务存储，当前InMemory实现按Streamlit会话装配并返回隔离副本
- 页面只持有当前task_id和纯UI状态，通过只读TaskView渲染Agent结果
- Application Service记录每次节点执行的开始、结束、耗时、成功/失败和错误类型，并汇总单任务执行耗时

当前 Agent 页面只接入了 Milvus 历史资产检索，尚未接入“用户确认后沉淀知识资产”的入口。
旧 Workflow 仍保留 `RAGService.save_case()` 兼容能力，但这不代表当前 Agent 已经形成可靠的
知识闭环。后续将由 MySQL 保存完整、可审计的知识资产，Milvus 只承担向量候选检索。

## 项目结构

```text
.
├── AGENTS.md               # Codex跨设备协作与开发约定
├── main.py                 # Streamlit 应用入口
├── application/            # 应用用例、Command、只读TaskView与会话装配
├── agent/                  # Agent状态、事件及后续节点
├── repositories/           # TaskRepository抽象与内存实现
├── views/                  # 页面与交互状态
├── services/               # LLM、RAG、文档解析应用服务
├── utils/                  # 基础客户端、配置及兼容业务入口
├── prompts/                # 模型提示词
├── knowledge/              # 本地测试知识
├── docs/                   # 当前接力状态与开发复盘
│   └── roadmap/           # 秋招目标、阶段范围和证据要求
└── tests/                  # 自动化测试
```

当前页面已经不再调用 `TestAssistantManager`，也不直接创建AgentState、Orchestrator、节点
或FeedbackHandler。页面通过`TestAnalysisApplicationService`进入应用用例，由Application
Service加载Repository中的隔离副本、调用受控Orchestrator并保存结果，再返回只读`TaskView`。
旧`TestAssistantManager`只作为Workflow兼容实现保留。

## 开发过程与设计说明

当前产品范围与项目从 Workflow 向 Agent 演进的过程，请查看：

- [当前产品需求说明书 V2](docs/product/PRD_AGENT_V2.md)
- [项目文档导航](docs/README.md)
- [当前开发状态与跨设备接力](docs/CURRENT_STATUS.md)
- [开发与复盘日志](docs/DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](docs/LEARNING_NOTES.md)
- [秋招项目含金量提升路线图](docs/roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)

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

1. 阶段2.13.1：已完成版本化JSON任务快照，可恢复AgentState、事件、决策和节点指标
2. 阶段2.13.2～2.13.4：使用MySQL保存任务快照和事件，实现重启恢复、version与execution_id保护
3. 阶段2.14：完成用户确认后的KnowledgeAsset沉淀；MySQL保存完整资产，Milvus建立向量索引
4. 阶段2.15：增加ContextBuilder、节点Token预算和分层耗时记录
5. 阶段2.16：建立10～20份脱敏需求评测集，完成RAG、Reviewer和三方案消融实验
6. 阶段2.17：只有前述阶段稳定后，再评估FastAPI、后台任务、SSE和Vue

详细范围、验收证据和明确不做的功能见
[秋招项目含金量提升路线图](docs/roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)。
