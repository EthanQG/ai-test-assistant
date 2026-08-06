# Test Analysis Agent 协作说明

本文件是仓库级 Codex 开发约定。无论在哪台电脑或哪个新任务中开发本项目，都应先读取本文件，并按以下规则恢复上下文、修改代码和交付结果。

## 项目目标

将现有固定 Workflow 逐步重构为可解释、可追踪、可评审的测试分析 Agent，用于：

- 解析 PRD 或需求描述
- 结构化提取图文PRD中的正文、表格、扫描内容、流程图和UI交互，并保留来源与解析不确定性（阶段2.15规划）
- 识别需求事实、推导风险和待确认项
- 检索本地 Bug 经验与 Milvus 历史测试资产
- 生成结构化测试点
- 评审测试覆盖度并进行受控修正
- 保留人工审核和知识沉淀闭环

当前只聚焦“测试分析报告生成”。自动化用例生成与异常日志分析尚未完成，不要在当前阶段扩展这两个功能。

## 每次开始开发前

按顺序完成：

1. 阅读 `README.md`
2. 阅读当前产品 PRD：`docs/product/PRD_AGENT_V2.md`
3. 阅读 `docs/CURRENT_STATUS.md`
4. 阅读 `docs/DEVELOPMENT_LOG.md` 的最新阶段
5. 阅读 `docs/LEARNING_NOTES.md` 的对应阶段
6. 执行 `git status -sb`
7. 执行 `git log -5 --oneline --decorate`
8. 执行 `python -m unittest discover -s tests -v`
9. 先向用户说明当前状态、测试结果和准备修改的范围，再开始编辑

如果文档、Git 状态和代码不一致，以代码与测试结果为完成度依据，以当前 V2 PRD 为产品范围依据，并在本次修改中修正文档。

## 当前架构边界

```text
views/
  Streamlit 页面与交互状态

application/
  创建、推进、补充、确认、反馈等应用用例；向页面返回只读 TaskView

knowledge_assets/
  用户确认后的知识资产模型、准入规则、版本化快照、有界索引Chunk和检索候选

documents/
  DocumentContent、文本/表格/图片元素、稳定来源与解析警告；不依赖页面和外部模型

repositories/
  TaskRepository、KnowledgeAssetRepository 抽象及其 InMemory/MySQL 存储实现

utils/TestAssistantManager
  旧 Workflow 兼容入口；当前 Agent 页面不再调用

services/
  LLM、RAG、Prompt、文档解析、Embedding 和 Milvus 适配服务

agent/
  Agent 状态、执行事件，以及后续的节点和编排器

prompts/
  稳定的系统提示词

tests/
  不依赖真实网络和外部服务的单元测试
```

## 开发原则

- 按可独立验证的小阶段开发，不同时推进多个大模块
- 优先保持现有测试分析功能可运行
- Agent 采用受控编排：代码限制步骤、状态和最大迭代次数
- LLM 负责理解、生成和评审，不直接操作底层数据库或页面状态
- Streamlit 只调用 Application Service，不直接创建或调用 Agent 节点、编排器和 Repository
- Repository 返回隔离副本，页面只读取 TaskView，不直接修改 AgentState
- 外部能力通过 Service 或 Tool 边界调用
- 内部数据优先使用结构化模型，不依赖解析 Markdown
- 需求事实、推导风险和待确认项必须明确区分
- 图文解析默认自动继续；只有核心规则、关键数字、流程分支或图文冲突无法确认时才允许暂停，重复问题需合并且一轮默认最多3个
- OCR或视觉模型的低置信度结果不能直接写入需求事实；必须保留页码、图片来源、置信度或降级说明
- 不编造功能、测试数据、性能数据或评测结论
- 测试使用 Fake Service，不因单元测试调用真实 DeepSeek、Milvus 或 Embedding 服务
- 不擅自进行前后端分离；Agent 核心稳定后再评估

## 修改与验证要求

- 本地文件修改使用小范围、可审查的变更
- 新增状态转换、Prompt 构建或 Agent 节点时必须增加单元测试
- 完成前至少执行：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q agent services utils views tests main.py
git diff --check
git status --short
```

- 不因为外部服务不可用而删除、跳过或弱化已有测试
- 未经用户明确要求，不执行真实 DeepSeek/Milvus 集成测试

## 文档维护

每完成一个小阶段：

1. 如果产品范围或验收标准变化，先更新 `docs/product/PRD_AGENT_V2.md`
2. 更新 `docs/CURRENT_STATUS.md`
3. 在 `docs/DEVELOPMENT_LOG.md` 追加阶段说明
4. 在 `docs/LEARNING_NOTES.md` 补充代码知识、参考答案、面试追问和动手练习
5. 如果启动方式或项目能力变化，同步更新 `README.md`

`CURRENT_STATUS.md` 只保留最新接力信息；`DEVELOPMENT_LOG.md` 保存完整历史和设计原因；`LEARNING_NOTES.md` 保存代码学习与面试复盘。

历史 PRD 位于 `docs/archive/`，只用于理解项目演进，不作为当前开发需求依据。

## Git 规则

- Commit 信息使用中文
- 一个 Commit 对应一个可解释、可验证的小阶段
- 提交前核对暂存文件，避免混入无关修改
- 不提交 `.env`、真实 API Key、虚拟环境、缓存和公司内部数据
- 未经用户明确同意，不执行 `git push`
- 不使用 `git reset --hard`、强制 Push 或破坏用户修改的命令

## 安全与数据边界

- `.env` 只保存在本机，通过 `.env.example` 重建
- 不将公司真实 PRD、日志、Bug、账号、Token 或内部地址提交到个人 GitHub
- `knowledge/history_points/` 默认不由 Git 同步；重要且允许迁移的资产应脱敏后单独处理，或保存到合规的共享知识库

## 当前接力入口

当前开发阶段、最新验证结果、已知限制和下一步任务以 `docs/CURRENT_STATUS.md` 为准。
