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
- 待确认候选按核心规则、关键数字、关键分支、需求冲突、实现细节和低影响问题分类；Python最多保留3个真正阻塞项，其余转为风险继续
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
- MySQL Repository已经通过真实CRUD和跨Application Service实例恢复验证，可按同一`task_id`恢复等待补充、完成和失败任务
- 后端已建立KnowledgeAsset准入、版本化JSON、MySQL权威存储、Milvus V2索引写入与可信候选回查边界；尚未接入页面按钮或当前Agent节点

当前 Agent 页面只接入了 Milvus 历史资产检索，尚未接入“用户确认后沉淀知识资产”的入口。
阶段2.14.3已经完成有界语义Chunk、一次批量Embedding和Milvus V2 upsert；阶段2.14.4已经完成
一次查询Embedding、Milvus阈值召回、按资产聚合和MySQL批量回查；阶段2.14.5增加了显式失败重试、
`request_id`幂等审计和资产停用后的向量清理。页面和当前KnowledgeRetriever尚未触发这些用例，
因此现在仍不能描述为用户主流程已经使用V2历史资产。
旧 Workflow 仍保留 `RAGService.save_case()` 兼容能力，但这不代表当前 Agent 已经形成可靠的
知识闭环。后续将由 MySQL 保存完整、可审计的知识资产，Milvus 只承担向量候选检索。

阶段2.15.3已经在统一`DocumentContent`上增加扫描页与内嵌图片OCR：保留文字、置信度、图片ID、页码
和处置状态，单张图片失败不会中断整份文档。高置信度文字进入兼容文本，低置信度只作为待复核候选。
默认适配本地Tesseract；未安装运行时会明确降级。阶段2.15.4新增了有界视觉理解边界：只对文档上下文
明确标记的流程图、状态图、时序图和UI原型候选调用显式配置的多模态端点，每份文档最多5张，并以
结构化节点、关系、UI元素、状态变化和不确定性保存结果。当前只有Fake测试证据，尚未验证真实视觉模型
效果，因此仍不能描述为已经完成完整图文PRD理解。

## 项目结构

```text
.
├── AGENTS.md               # Codex跨设备协作与开发约定
├── main.py                 # Streamlit 应用入口
├── application/            # 应用用例、Command、只读TaskView与会话装配
├── agent/                  # Agent状态、事件及后续节点
├── knowledge_assets/       # 知识资产模型、准入、快照与有界语义Chunk
├── documents/              # 图文文档模型、元素来源与解析警告
├── repositories/           # Task/KnowledgeAsset Repository抽象与实现
├── views/                  # 页面与交互状态
├── services/               # LLM、RAG、文档解析应用服务
├── utils/                  # 基础客户端、配置及兼容业务入口
├── prompts/                # 模型提示词
├── knowledge/              # 本地测试知识
├── docs/                   # 当前接力状态与开发复盘
│   └── roadmap/           # 秋招目标、阶段范围和证据要求
└── tests/                  # 分层自动化测试
    ├── unit/               # Agent、Application、Repository、Service与Presenter单元测试
    ├── architecture/       # 静态依赖边界测试
    ├── app/                # Streamlit AppTest与页面fixture
    └── integration/        # 需显式开启的真实基础设施集成测试
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

如需运行完整开发测试，安装包含pytest的开发依赖：

```powershell
pip install -r requirements-dev.txt
```

也可以使用无头模式启动：

```powershell
python -m streamlit run main.py --server.headless=true
```

运行错误会显示在页面任务状态中；结构化JSON校验失败和受控重试信息同时输出到启动命令所在的PowerShell窗口。

运行前请在 `.env` 中填写真实的 `DEEPSEEK_API_KEY`。`.env` 已加入 Git 忽略规则，请勿提交真实密钥。

扫描PDF和图片文字OCR需要另外安装本地Tesseract及中文`chi_sim`、英文`eng`语言数据，然后在`.env`配置：

```text
TESSERACT_CMD=tesseract
OCR_LANGUAGES=chi_sim+eng
OCR_TIMEOUT_SECONDS=30
```

如果没有安装Tesseract，正文和表格解析仍会继续，系统会记录`OCR_UNAVAILABLE`，不会伪造OCR结果。
Windows自定义路径建议使用正斜杠，例如`TESSERACT_CMD=D:/Tesseract-OCR-5/tesseract.exe`，避免`.env`
双引号中的`\t`被解析为制表符。

如需显式启用流程图和UI图理解，需要配置一个支持图片输入与JSON Output的OpenAI兼容端点：

```text
VISION_API_KEY=your_vision_api_key
VISION_BASE_URL=https://your-vision-endpoint.example/v1
VISION_MODEL=your-vision-model
VISION_TIMEOUT_SECONDS=60
VISION_MAX_TOKENS=1500
```

未配置视觉端点时，普通文字、表格和OCR解析不受影响；视觉候选只记录`VISION_UNAVAILABLE`。图片不会全部
发送给模型：装饰图和小图会跳过，OCR已足够表达且没有流程/UI信号的图片不会重复调用视觉模型。

任务存储默认使用会话级内存。如需启用阶段2.13.2新增的MySQL Repository，在本机`.env`中设置：

```text
TASK_REPOSITORY_BACKEND=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=ai_test_assistant
```

应用启动时会创建`agent_tasks`、`agent_task_events`和`agent_task_executions`。建表SQL、TaskRecord真实CRUD、事件级联删除
以及等待补充/完成/失败任务的跨Application Service实例恢复已在真实MySQL 8.0.32验证。

KnowledgeAsset存储使用独立开关。需要让资产Repository使用同一MySQL时设置：

```text
KNOWLEDGE_ASSET_REPOSITORY_BACKEND=mysql
```

资产Repository初始化时会创建`knowledge_assets`表。当前Streamlit尚未接入“保存到知识库”按钮，因此启动页面不会自动发布资产；
本阶段提供的是可由后续页面或FastAPI复用的MySQL存储边界。

KnowledgeAsset V2索引使用独立配置：

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_TIMEOUT=60
MILVUS_URI=http://127.0.0.1:19530
MILVUS_ASSET_COLLECTION=knowledge_assets_v2
MILVUS_TOKEN=
KNOWLEDGE_RETRIEVAL_TOP_K=3
KNOWLEDGE_RETRIEVAL_RAW_LIMIT=20
KNOWLEDGE_RETRIEVAL_MIN_SCORE=0.65
```

索引用例使用一次批量`/api/embed`请求并限制最多32个Chunk；旧`ai_test_cases`集合保持不动。
检索用例每次只执行一次查询Embedding、一次Milvus搜索和一次MySQL批量回查；`0.65`只是待离线评测的可配置基线。

日常单元测试不会访问MySQL。如需在本机显式运行真实数据库集成测试：

```powershell
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m unittest tests.integration.mysql.test_mysql_task_repository_integration -v
```

集成测试使用独立UUID并在结束后按`task_id`清理测试数据。2.13.4已实现并通过真实MySQL验证乐观锁、
`execution_id`和可过期执行租约；当前保证节点结果幂等提交，但不宣称外部LLM请求Exactly Once。

### 测试命令

pytest现在是推荐的统一测试入口，同时继续兼容原有unittest：

```powershell
python -m pytest
python -m pytest -m unit
python -m pytest -m app
python -m pytest -m integration
python -m unittest discover -s tests -v
```

`integration`默认不会访问真实MySQL；仍需设置`RUN_MYSQL_INTEGRATION_TESTS=1`才会执行。

## 外部依赖

测试资产检索当前依赖：

- Milvus 向量数据库
- 提供 `nomic-embed-text` 模型的 Embedding 服务
- DeepSeek 兼容的 Chat Completions API

Milvus 与 Embedding 地址目前仍由现有 RAG 客户端配置。后续阶段会统一迁移到环境变量。

## 后续计划

1. 阶段2.13.1：已完成版本化JSON任务快照，可恢复AgentState、事件、决策和节点指标
2. 阶段2.13.2：已实现MySQL任务快照与独立事件Repository，真实连接和建表已验证
3. 阶段2.13.3：已完成真实MySQL CRUD和跨Application Service实例恢复验证
4. 阶段2.13.4：已实现version、execution_id与执行租约保护
5. 阶段2.13.5：已使用pytest统一测试入口、marker与fixture，并保留现有unittest兼容
6. 阶段2.13.6：已按unit、architecture、app和integration整理测试目录，测试内容保持不变
7. 阶段2.14.1：已完成KnowledgeAsset模型、准入策略、内容哈希和内存Repository边界
8. 阶段2.14.2：已完成完整KnowledgeAsset的MySQL权威存储实现
9. 阶段2.14.3：已完成有界Chunk、批量Embedding和Milvus V2索引写入边界
10. 阶段2.14.4：已完成V2候选召回、阈值过滤、MySQL批量回查和来源验证
11. 阶段2.14.5：已实现索引失败的显式重试、重复请求保护、补偿审计和停用清理
12. 阶段2.15.1：已完成统一DocumentContent、稳定来源和现有文本解析兼容
13. 阶段2.15.2：已完成PDF/DOCX原生结构、图片附件和解析覆盖统计
14. 阶段2.15.3：已完成OCR协议、Tesseract适配、扫描页渲染、置信度分流和失败隔离
15. 阶段2.15.4：已完成有界视觉候选筛选、结构化多模态协议、调用限额和失败降级
16. 阶段2.15.5：已完成关键问题筛选与Human-in-the-loop限流
17. 阶段2.15.6：已完成ContextBuilder、节点字段白名单、输入预算和裁剪指标
18. 阶段2.15.7：已完成真实/估算Token、分层耗时、Prompt指纹和错误分类记录
19. 阶段2.16.1：已建立schema v1人工标注契约和10份单人复核的脱敏评测需求；尚无双人一致性数据
20. 阶段2.16.2：已建立5份合成图文样本及正文、表格、OCR、流程和UI确定性评分；真实视觉端点尚未运行
21. 阶段2.16.3：已建立5份虚构RAG查询和资产级指标，并用Fake外部依赖跑通真实Retrieval Service边界；尚无真实Milvus效果结果
22. 阶段2.16.3真实实验：5份合成KnowledgeAsset已通过MySQL、`nomic-embed-text`和Milvus完成端到端评测；Recall@3=1.0，但禁止资产命中率为0.1，仍需阈值对比
23. 阶段2.16.3参数对比：9组真实实验中阈值0.70保持Recall=1.0并消除当前样本的禁止命中；样本过少，尚未修改线上默认参数
24. 阶段2.16.4第一小步：已建立12份Reviewer缺陷注入样本和Precision、Recall、正确样本误报率；尚未运行真实Reviewer
25. 阶段2.16.4第二小步：已将现有结构化评审结果保守映射为六类缺陷；无法确定的自由文本不会强行分类
26. 阶段2.16.4第三小步：已建立`TestAnalysisState → Reviewer → 缺陷适配 → 指标`Runner，并生成Fake接线报告；尚未运行真实Reviewer
27. 阶段2.16.4真实基线：已用`deepseek-v4-pro`运行12份合成样本，Precision=0.3636、Recall=0.3333，3份结构化输出失败；结果只代表当前小样本
28. 阶段2.16.4 Reviser第一小步：已建立6份最小修复样本、目标修复率和正确测试点保留率；当前只有Fake接线报告
29. 阶段2.16.4真实Reviser：6份样本严格目标修复率0.1667、保护率1.0、1份结构校验失败；严格匹配不代表人工语义正确率
30. 阶段2.16.5第一小步：已固定三方案实验契约、相同10份输入和统一质量/耗时/Token指标；当前仅Fake接线
31. 阶段2.16.5第二小步：已将Application Service只读`TaskView`适配为统一实验输出，复用真实耗时、Token和修正次数
32. 阶段2.16.5第三小步：已固定三组能力开关及相同的待确认问题自动延期策略，并通过Application Service同task_id恢复
33. 阶段2.16.5第四小步：已在不修改Orchestrator的前提下装配无RAG和质量旁路节点，三组差异留有显式事件证据
34. 阶段2.16.5真实烟测：已完成1份需求三组运行并记录耗时/Token；严格文本指标全0且RAG受旧控制台编码降级影响，禁止用作质量提升结论
35. 阶段2.16.6：汇总现有真实证据和简历材料，完整10×3降为可选增强
36. 阶段2.17：只有前述阶段稳定后，再评估FastAPI、后台任务、SSE和Vue

详细范围、验收证据和明确不做的功能见
[秋招项目含金量提升路线图](docs/roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)。
