# Test Analysis Agent 开发与复盘日志

这份文档记录项目从固定 Workflow 向 Agent 架构演进的过程。它不仅记录代码变化，还解释每次调整的原因、解决的问题、验证方式和下一步计划，方便后续复盘及面试表达。

当前产品范围请查看 [PRD V2](product/PRD_AGENT_V2.md)，后续阶段请查看
[秋招项目含金量提升路线图](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)，最新开发接力点请查看
[CURRENT_STATUS.md](CURRENT_STATUS.md)，代码知识与面试复盘请查看
[LEARNING_NOTES.md](LEARNING_NOTES.md)，跨电脑的 Codex 协作规则请查看根目录
[AGENTS.md](../AGENTS.md)。

## 如何维护本文档

每完成一个可以独立验证的小阶段，先更新 `CURRENT_STATUS.md` 和 `LEARNING_NOTES.md`，再在本文档顶部的“阶段索引”中增加入口，并在正文末尾追加一节，至少记录：

1. 本阶段目标
2. 修改内容
3. 核心概念
4. 为什么这样设计
5. 验证结果
6. Git 提交
7. 下一步计划
8. 对应学习笔记、面试问题和动手练习

如果只是修正错别字或样式，不必单独增加阶段；如果改变了架构、模型输入、状态流转或用户行为，则应该记录。

## 阶段索引

| 阶段 | 状态 | 核心成果 | Git 提交 |
|---|---|---|---|
| 阶段 1 | 已完成 | 拆分 Service 层，聚焦测试分析功能 | `5875853` |
| 阶段 1.5 | 已完成 | 整理 System/User Prompt 边界 | `95aba63` |
| 阶段 2.1/2.2 | 已完成 | Agent 状态与执行事件模型 | `e118865` |
| 阶段 2.3 | 已完成 | RequirementAnalyzer 需求分析节点 | `75476ba` |
| 产品范围 V2 | 已完成 | 从三模块 Workflow 收敛为测试分析 Agent | `18f283a` |
| 阶段 2.4 | 已完成 | Agent知识检索节点 | `805a25b` |
| 阶段 2.5 | 已完成 | 结构化测试点生成节点 | `d16dd74` |
| 阶段 2.6 | 已完成 | 测试点质量评审节点 | `4e62f17` |
| 阶段 2.7 | 已完成 | 测试点定向修正节点 | `828794a` |
| 阶段 2.8 | 已完成 | 结构化人工反馈与业务规则确认 | `aefec4c` |
| 阶段 2.9 | 已完成 | 受控Agent编排与循环限制 | `0ad9952` |
| 阶段规划校正 | 已完成 | 调整为先实现Finalizer、再接入页面 | `719a0ad` |
| 阶段 2.10 | 已完成 | Finalizer最终结果整理节点 | `977aab9` |
| 阶段 2.11.1 | 已完成 | Streamlit Agent基础运行页面 | `a66a561` |
| 阶段 2.11.2 | 已完成 | 待确认恢复、逐节点刷新与双栏工作台 | `e9441c6` |
| 阶段 2.11.3 | 已完成 | 结构化人工反馈、业务规则确认与重新评审 | `cf2d1d9` |
| 阶段 2.11.4 | 已完成 | 节点进度与耗时、反馈防重复、增量修正和轨迹稳定性 | `1a4c6bf` |
| 阶段 2.11.5A | 已完成 | 双栏信息架构、阶段进度、只读需求对照和折叠执行详情 | `d2eb741` |
| 阶段 2.11.5B | 已建立检查点 | 统一标题留白、阶段标签、Tab、按钮和测试点摘要视觉 | `6b48817` |
| 阶段 2.11.5C | 已完成 | 固定双栏工作区、有状态结果导航、测试点分页和执行详情Dialog | `2416da4` |
| 阶段 2.11.5D | 已完成 | 动态执行状态、固定操作栏、结果浏览和页面展示收尾 | `c8477b9` |
| 路线图校准 | 已完成（仅文档） | 冻结Streamlit V1，明确MySQL权威数据、Milvus索引和阶段2.12～2.17 | `e9c56b3` |
| 阶段 2.12 | 已完成 | Application Service、TaskRepository、只读TaskView、页面入口迁移和节点耗时基线 | `caeb5af`, `1503e59` |
| 阶段 2.13.1 | 已完成 | schema v1任务快照、严格JSON校验、完整领域恢复和恢复执行验证 | `5f50110` |
| 阶段 2.13.2 | 已完成 | MySQL任务快照、独立事件表、事务保存和可切换Repository装配 | `885c5ca` |
| 阶段 2.13.3 | 已完成 | 真实MySQL CRUD、事件一致性和跨Application Service实例恢复 | `bb30a5b` |
| 阶段 2.13.4 | 已完成 | 乐观锁、execution_id幂等与可过期执行租约 | `77d0ac4` |
| 阶段 2.13.5 | 已完成 | pytest统一测试入口、marker与fixture | `70ea24e` |
| 阶段 2.13.6 | 已完成 | unit、architecture、app与integration测试目录分层 | 本次提交 |
| 阶段 2.13 | 已完成 | 持久化、恢复、重复执行保护和测试工程入口 | - |
| 阶段 2.14 | 规划中 | KnowledgeAsset准入、MySQL权威存储和Milvus V2索引闭环 | - |
| 阶段 2.15 | 规划中 | ContextBuilder、Token预算和分层可观测性 | - |
| 阶段 2.16 | 规划中 | 脱敏离线评测、RAG/Reviewer专项评测和三组消融实验 | - |
| 阶段 2.17 | 远期评估 | FastAPI、后台任务、SSE或轮询和Vue | - |

---

## 阶段 1：基础架构整理

### 本阶段目标

在不改变现有测试点生成行为的前提下，将页面、业务逻辑和外部服务调用分离，为后续 Agent 改造建立清晰边界。

### 修改内容

- 新增 `services/` 应用服务层
- 新增 `LLMService`，统一封装大模型调用
- 新增 `RAGService`，统一封装历史测试资产检索与保存
- 新增 `DocumentService`，统一封装 TXT、Markdown、PDF、DOCX 文档解析
- `TestAssistantManager` 改为通过依赖注入使用 Service
- 暂时隐藏尚未实现的自动化用例生成和日志分析页面
- 项目页面名称调整为 `Test Analysis Agent`
- 增加 `.env.example`、完善 `.gitignore`
- 增加 README 和基础单元测试

### 核心概念

#### LLM

LLM（Large Language Model，大语言模型）是项目负责理解和生成文本的“大脑”。当前底层模型是 DeepSeek。

#### Service

Service 是业务代码访问某项能力的统一入口。例如，业务层调用：

```python
llm_service.generate(prompt)
```

而不需要知道底层使用 DeepSeek、OpenAI 还是其他模型。它的主要价值是降低耦合、方便替换模型，并允许测试时注入 Fake Service，避免真实网络请求和费用。

#### RAG

RAG 会先根据当前需求检索 Milvus 中的历史测试资产，再将相关内容交给 LLM 参考。它相当于 Agent 的“外部长期记忆”。

### 架构变化

改造前：

```text
Streamlit 页面
  → TestAssistantManager
      → DeepSeekClient
      → MilvusRAGManager
```

改造后：

```text
Streamlit 页面
  → TestAssistantManager
      → LLMService
      → RAGService
      → DocumentService
          → 底层客户端
```

### 为什么这样设计

如果页面和具体模型、数据库直接绑定，后续增加 Agent 编排器时会难以测试和替换依赖。Service 层先把已有能力整理成稳定接口，未来它们可以进一步包装为 Agent Tools。

### 验证结果

- 3 个单元测试通过
- Python 编译检查通过
- 模块导入检查通过
- `.env` 未被 Git 跟踪
- 未发现真实 API Key 泄露

### Git 提交

```text
5875853 重构：拆分服务层并为Agent架构做准备
```

---

## 阶段 1.5：Prompt 边界整理

### 本阶段目标

明确 System Prompt 与 User Prompt 的职责，修复动态占位符没有被替换的问题，并消除流式、非流式生成中的重复 Prompt 拼接逻辑。

### 发现的问题

原 `test_points.txt` 中包含：

```text
{prd_content}
{bug_kb_content}
```

但代码只是读取文件，没有执行字符串格式化。模型会看到未替换的占位符，而真实数据又在 User Prompt 中传递一次。

### 修改内容

- 新增 `PromptService`
- System Prompt 只保留稳定的角色、规则和输出规范
- User Prompt 只承载当前需求、本地 Bug 经验和 RAG 召回结果
- 流式与非流式生成复用相同的 Prompt 构建方法
- 空知识库和空 RAG 结果不再产生空区块
- 将信息划分为“需求事实、推导风险、待确认项”

### 核心概念

#### System Prompt

长期稳定的行为规则，例如模型角色、信息边界、测试设计原则和输出格式。

#### User Prompt

本次任务的动态数据，例如当前 PRD、历史 Bug 经验、RAG 检索结果和用户修改要求。

### 为什么区分三类信息

旧规则一方面要求“不能超出 PRD”，另一方面又要求模型分析幂等、并发、弱网等风险，两者容易冲突。

新的边界是：

- 需求事实：PRD 明确给出的内容
- 推导风险：基于真实操作推导出的测试风险，必须说明依据
- 待确认项：信息不足时需要产品或用户确认的问题

这样既能减少业务幻觉，又保留测试人员应有的风险识别能力。

### 验证结果

- 7 个单元测试通过
- System Prompt 中不存在动态占位符
- 每份动态输入只在 User Prompt 中出现一次
- 空的可选上下文会被省略

### Git 提交

```text
95aba63 修复：整理提示词边界并移除无效占位符
```

---

## 阶段 2.1/2.2：Agent 状态与执行事件

### 本阶段目标

为一次测试分析任务建立统一的工作记忆和执行日志，为后续需求分析节点、工具调用、Reviewer 和页面执行轨迹提供基础。

### 修改内容

新增 `agent/`：

```text
agent/
├── __init__.py
├── events.py
└── state.py
```

其中：

- `TestAnalysisState` 保存任务的完整工作状态
- `AgentStatus` 描述任务当前状态
- `AgentStep` 定义标准执行步骤
- `AgentEvent` 记录任务执行过程中发生的事件

### AgentState 是什么

AgentState 可以理解为 Agent 的“工作记忆”或“任务档案”，当前能够保存：

- 唯一任务 ID 和原始需求
- 当前任务状态和执行步骤
- 需求摘要、需求事实、推导风险、待确认项
- 本地 Bug 知识
- RAG 内容、最高相似度和命中数量
- 最终报告与错误信息
- 完整事件历史
- 创建时间与更新时间

### AgentEvent 是什么

AgentEvent 记录“刚刚发生了什么”，例如：

```json
{
  "event_type": "step_completed",
  "step": "analyze_requirement",
  "message": "需求分析完成",
  "data": {
    "fact_count": 5
  }
}
```

未来页面可以根据事件显示实时轨迹，而不需要把进度提示写死在 Streamlit 中。

### 状态流转

```text
pending
  → running
      → waiting_for_user
          → running
      → completed
      → failed
```

系统会拒绝以下错误操作：

- 使用空需求创建任务
- 完成一个不是当前步骤的步骤
- 等待用户输入时绕过 `resume()` 继续执行
- 用空报告完成任务
- 已完成或失败的任务继续执行

### 当前边界

这一阶段只增加状态和事件模型：

- 尚未调用 LLM
- 尚未接入现有 Streamlit 页面
- 尚未实现自主工具选择
- 尚未改变当前报告生成流程

因此项目已经具备 Agent 的状态基础，但还不是完整 Agent。

### 验证结果

- 全量 16 个单元测试通过
- Python 编译检查通过
- 状态可以转换为 JSON
- 任务创建、步骤开始、步骤完成、等待用户、恢复、完成和失败均有测试覆盖

### Git 提交

本阶段提交信息：

```text
功能：新增Agent状态与执行事件模型
```

### 下一步

实现 `RequirementAnalyzer`：

```text
原始 PRD
  → LLM 结构化分析
  → 需求摘要
  → 需求事实
  → 推导风险
  → 待确认项
  → 写入 TestAnalysisState
```

这是第一个真正使用 AgentState 的执行节点。

---

## 阶段 2.3：RequirementAnalyzer 需求分析节点

### 本阶段目标

实现第一个真正调用 LLM 并读写 `TestAnalysisState` 的 Agent 节点，把原始需求转换为可校验的结构化数据，而不是直接生成最终 Markdown 报告。

### 修改内容

- 新增 `RequirementAnalysisResult` 和 `InferredRisk`
- 新增 `RequirementAnalysisValidationError`
- 新增需求分析 System Prompt
- `PromptService` 增加需求分析 User Prompt 构建方法
- 新增 `RequirementAnalyzer`
- `TestAnalysisState` 增加模块、业务规则和状态流转字段
- 增加 JSON 代码围栏兼容
- 增加未知顶层字段拒绝机制
- 增加成功、待确认、无效 JSON、字段错误和 LLM 超时测试

### 执行流程

```text
TestAnalysisState.requirement
  → start_step(analyze_requirement)
  → PromptService
  → LLMService.generate()
  → RequirementAnalysisResult.from_json()
  → 字段与类型校验
  → 写回TestAnalysisState
  → complete_step()
  → 存在open_questions时wait_for_user()
```

### 关键设计

LLM 只负责生成候选 JSON，代码负责决定该结果是否可信。解析器要求固定顶层字段、正确数组类型、非空字符串以及每条风险同时包含 `risk` 和 `basis`。

分析成功但存在待确认项时，需求分析步骤仍然记录为完成，然后任务进入 `waiting_for_user`。这样既保留已经获得的分析结果，也阻止后续知识检索和测试点生成绕过用户确认。

LLM 超时、JSON 无效或字段校验失败时，节点记录 `TASK_FAILED`，并抛出统一的 `RequirementAnalysisError` 给上层处理。

### 当前边界

- 尚未接入 Streamlit 页面
- 尚未实现 Agent 编排器
- 尚未将 RAG 封装为 Agent 节点
- 尚未生成结构化测试点
- 没有真实模型效果评测

### 验证结果

- 全量 27 个单元测试通过
- Python 编译检查通过
- Fake LLM 覆盖成功、等待用户、解析失败和模型异常
- 不访问真实 DeepSeek、Milvus 或 Embedding 服务

### Git 提交

本阶段提交信息：

```text
功能：实现Agent结构化需求分析节点
```

### 下一步

实现知识检索节点，把 `RAGService` 的上下文、最高相似度和命中数量写入 `TestAnalysisState`，并记录 `retrieve_knowledge` 步骤事件。

---

## 产品范围 V2：测试分析 Agent PRD 重构

### 调整原因

旧 PRD 同时规划测试点生成、pytest 用例生成和日志分析，并以固定 Workflow 作为主体。当前只有测试分析功能形成真实闭环，另外两个模块未完成；同时项目已开始引入 State、Event 和 Agent 节点，旧 PRD 无法准确描述当前范围和验收标准。

### 文档归类

```text
docs/
├── README.md
├── product/PRD_AGENT_V2.md
├── archive/PRD_WORKFLOW_V1.md
├── CURRENT_STATUS.md
├── DEVELOPMENT_LOG.md
└── LEARNING_NOTES.md
```

### V2 核心变化

- 产品范围收敛为“从 PRD 到高质量测试分析报告”
- 自动化用例生成和日志分析移出当前范围
- 定义 RequirementAnalyzer、KnowledgeRetriever、Generator、Reviewer、Reviser 和 Finalizer
- 区分现有 Workflow、Agent 内部已实现和规划中能力
- 将可验证验收标准替代无依据的可用性与性能承诺
- 增加 Agent 状态、分支和安全规则
- 增加离线评测方案和简历表述边界

### 当前产品依据

后续功能范围和验收以 `docs/product/PRD_AGENT_V2.md` 为准。归档的 V1 PRD 只用于说明项目早期设计和范围收敛过程。

### Git 提交

本阶段建议提交信息：

```text
文档：重构测试分析Agent产品需求说明
```

---

## 阶段 2.4：KnowledgeRetriever 历史知识检索节点

### 本阶段目标

将现有 `RAGService` 从页面 Workflow 的辅助调用升级为 Agent 内部的明确节点，使历史知识检索过程能够读取和更新 State，并留下可审计的执行事件。

### 修改内容

- 新增 `KnowledgeRetriever` 与 `KnowledgeRetrievalError`
- `TestAnalysisState` 增加知识检索状态和降级错误原因
- `RAGSearchResult` 增加 `matched`、`no_match`、`failed` 三种明确结果
- 根据需求摘要、模块、事实、业务规则和推导风险构造检索文本
- 把检索上下文、最高相似度和命中数量写回 State
- 记录 `retrieve_knowledge` 步骤开始与完成事件
- 为 Agent 调用增加 RAG 严格错误模式，同时保留旧调用方的空结果兼容行为

### 执行链路

```text
TestAnalysisState 中的需求分析结果
  → KnowledgeRetriever.retrieve()
  → 构造结构化检索查询
  → RAGService.search()
  → MilvusRAGManager.search_similar_cases(raise_on_error=True)
  → 区分 matched / no_match / failed
  → 写回 State
  → complete_step(retrieve_knowledge)
```

### 关键设计

“无匹配”和“服务失败”不是同一件事。无匹配说明检索正常完成，只是知识库没有足够相似的资产；服务失败表示 Milvus、Embedding 或检索链路发生异常。两者都允许后续生成继续，但 State 和 Event 必须保留真实状态，避免页面把故障误报为正常空结果。

需求分析失败会使任务失败，因为后续节点依赖它提供可信的结构化事实；RAG 只是增强信息，失败后仍可基于当前 PRD 生成测试点，因此采用可观测的降级策略，而不是终止整个任务。

### 验证结果

- 全量 35 个单元测试通过
- 覆盖检索命中、正常无匹配、服务失败降级、缺少分析前置条件和等待用户状态
- 单元测试使用 Fake RAG，不访问真实 Milvus 或 Embedding 服务

### 当前边界

- 尚未接入 Streamlit 页面
- 尚未实现 Orchestrator 自动调度
- 尚未生成结构化测试点
- 尚未使用真实知识库进行召回质量评测

### 建议提交信息

```text
功能：实现Agent历史知识检索节点
```

### 下一步

进入阶段 2.5，实现结构化测试点模型与 `TestPointGenerator`，让 LLM 输出经过 Python 校验后再写入 State。

---

## 阶段 2.5：TestPointGenerator 结构化测试点生成节点

### 本阶段目标

将需求分析结果和历史知识转换为机器可校验的测试点集合，替代 Agent 内部直接依赖 Markdown 报告的方式，为后续覆盖度评审、去重和自动修正提供稳定输入。

### 修改内容

- 新增 `TestPoint`、`TestPointGenerationResult` 和校验异常
- 新增测试点分类、优先级和来源枚举
- 新增结构化测试点 System Prompt 和动态 User Prompt
- 新增 `TestPointGenerator`
- `TestAnalysisState` 增加 `test_points`
- 生成成功后记录测试点总数、分类统计和优先级统计
- 增加模型解析、节点前置条件、成功和失败路径测试

### 结构化测试点字段

```text
title
category: functional / boundary / exception / non_functional
priority: P0 / P1 / P2
scenario
preconditions[]
steps[]
expected_results[]
sources[]
source_refs[]
```

`sources` 表示来源类型，`source_refs` 保存具体引用。这样 Reviewer 后续不仅能看到测试点内容，还能判断它来自当前需求、历史资产、通用测试经验还是用户反馈。

### 执行链路

```text
TestAnalysisState 中的需求分析与知识检索结果
  → 校验不存在待确认项且已经尝试知识检索
  → TestPointGenerator.generate()
  → PromptService 构造结构化生成 Prompt
  → LLMService.generate()
  → TestPointGenerationResult.from_json()
  → Python 校验字段、枚举和非空数组
  → 写入 state.test_points
  → complete_step(generate_test_points)
```

### 关键设计

知识检索的 `no_match` 和 `degraded` 都允许生成，因为 RAG 是增强能力；`not_started` 不允许生成，因为受控流程要求节点按顺序执行并留下检索轨迹。

LLM 返回的是候选测试点，不是可信的最终结果。Python 会拒绝未知分类、非法优先级、空步骤、空预期、未知字段和空测试点集合。只有校验通过的数据才能写入 State。

测试点生成是核心产出，无法解析或模型调用失败时任务进入 `failed`，不能像 RAG 一样降级为空测试点继续执行。

### 验证结果

- 全量 49 个单元测试通过
- 覆盖正常生成、无 RAG 命中、RAG 降级、待确认项阻断、未检索阻断、非法 JSON 结果和 LLM 异常
- 单元测试使用 Fake LLM，不访问真实模型

### 当前边界

- 尚未接入 Streamlit 页面
- 尚未实现 Reviewer
- 尚未实现 Orchestrator 自动串联三个节点
- 尚未使用真实模型验证测试点质量
- 当前来源真实性依赖模型按 Prompt 引用，后续 Reviewer 还需核对

### 建议提交信息

```text
功能：实现Agent结构化测试点生成节点
```

### 下一步

进入阶段 2.6，实现 `TestPointReviewer` 和结构化评审结果，检查需求覆盖、重复项、幻觉风险与可执行性。

---

## 阶段 2.6：TestPointReviewer 测试点质量评审节点

### 本阶段目标

对结构化测试点进行独立质量评审，输出可校验的评分、覆盖映射和问题清单，并由 Python 规则决定是否达标，为后续定向修正分支提供依据。

### 修改内容

- 新增 `TestPointReviewResult`、`ReviewDimensionScores`
- 新增 `RequirementCoverage` 和 `HallucinationIssue`
- 新增 Reviewer System Prompt 和动态 User Prompt
- 新增 `TestPointReviewer`
- `TestAnalysisState` 增加评审结果、达标状态和评分阈值
- 增加需求覆盖完整性硬校验
- 增加评分、覆盖、幻觉、前置条件和失败路径测试

### 评审输出

```text
overall_score
dimension_scores:
  requirement_coverage
  boundary_exception
  executability
  traceability
requirement_coverage[]
missing_scenarios[]
duplicate_groups[]
hallucination_issues[]
revision_suggestions[]
```

### 执行链路

```text
结构化需求分析 + 结构化测试点
  → TestPointReviewer.review()
  → PromptService 构造评审 Prompt
  → LLMService.generate()
  → TestPointReviewResult.from_json()
  → Python 校验评分、字段和每条需求事实的覆盖记录
  → Python 计算 review_passed
  → 写入 State 并记录 review_test_points 完成事件
```

### 达标规则

LLM 只提供评审证据，不直接决定流程分支。当前 Python 规则要求：

```text
overall_score >= passing_score
并且所有 requirement_fact 的状态都是 covered
并且 hallucination_issues 为空
```

默认阈值为 80。即使总分达到 80，只要存在部分覆盖、缺失事实或幻觉问题，仍然不达标。Prompt 明确禁止模型返回 `passed` 或 `next_action`，避免把流程控制交给模型。

### 关键设计

结构校验只能确认 Reviewer 输出格式合法。为防止模型漏评需求事实，节点还会比较 State 中的事实集合和评审结果中的事实集合；缺失、额外或重复的事实记录都会使任务失败。

Reviewer 不修改测试点。它只保存问题证据和修正建议，下一阶段 Reviser 才负责定向修改，从而保持“评审”和“修改”的职责分离。

### 验证结果

- 全量 64 个单元测试通过
- 覆盖达标、低分、部分覆盖、幻觉阻断、遗漏事实、非法评分、非法重复组、空测试点和模型异常
- 单元测试使用 Fake LLM，不访问真实模型

### 当前边界

- 尚未接入 Streamlit 页面
- 尚未实现 TestPointReviser
- 尚未实现 Reviewer/Reviser 最大次数循环
- 当前评分质量尚未通过人工标注评测集校准
- 重复和幻觉判断仍依赖 LLM 语义判断，Python只校验结构与关键流程规则

### 建议提交信息

```text
功能：实现Agent测试点质量评审节点
```

### 下一步

进入阶段 2.7，实现 `TestPointReviser`，根据结构化评审结果对当前测试点进行一次定向修正。

---

## 阶段 2.7：TestPointReviser 测试点定向修正节点

### 本阶段目标

根据上一轮 Reviewer 的结构化问题，对当前测试点进行一次受控、定向的修改，同时保留评审依据并强制修正后的结果重新评审。

### 修改内容

- 新增测试点修正 System Prompt
- `PromptService` 增加修正 User Prompt 构建方法
- 新增 `TestPointReviser`
- `TestAnalysisState` 增加 `revision_count`
- 修正结果复用 `TestPointGenerationResult` 严格校验
- 增加修正前置条件、成功、无变化、非法结果和模型异常测试

### 执行链路

```text
review_passed = false
  → TestPointReviser.revise()
  → 需求分析 + 当前测试点 + Reviewer结果
  → LLMService.generate()
  → TestPointGenerationResult.from_json()
  → 拒绝非法结构或完全未变化结果
  → 替换 state.test_points
  → revision_count + 1
  → review_passed = None
  → complete_step(revise_test_points)
```

### 关键设计

Reviser 只允许处理明确未达标的结果。`review_passed=True` 时自动修正会破坏已通过内容，因此代码在调用 LLM 前直接拒绝；没有完整 Reviewer 结果时也不能执行。

修正后保留上一轮 `review_result` 作为“为什么修改”的证据，但把 `review_passed` 重置为 `None`。因为测试点已经变化，旧分数不能继续代表新版本，必须重新进入 Reviewer。

LLM必须返回完整测试点集合，而不是只返回增量补丁。完整集合可以继续复用现有结构模型和校验器，避免编写不稳定的自然语言合并逻辑。

如果修正结果与原测试点完全一致，节点会失败。这样可以防止模型表面响应成功、实际没有处理 Reviewer 问题，导致未来循环空转。

### 验证结果

- 全量 72 个单元测试通过
- 覆盖修正成功、已达标阻断、缺少评审阻断、无变化拒绝、非法结构和模型异常
- 单元测试使用 Fake LLM，不访问真实模型

### 当前边界

- 当前只支持显式调用一次 Reviser
- 尚未实现最大修正次数
- 尚未自动重新调用 Reviewer
- 尚未保存每一轮完整测试点快照
- 尚未接入 Streamlit 页面

### 建议提交信息

```text
功能：实现Agent测试点定向修正节点
```

### 下一步

进入阶段 2.8，实现结构化人工反馈模型，让用户的增删改、优先级调整和补充说明可以写入State并驱动Reviser。阶段2.9再实现Orchestrator和最大循环次数。原计划阶段2.10直接接入Streamlit，后续复核时调整为先实现Finalizer，避免页面依赖尚未完成的最终结果契约。

---

## 阶段 2.8：HumanFeedback 结构化人工反馈

### 本阶段目标

让测试工程师的意见成为Agent内部可校验、可确认、可追踪的正式输入，并让Reviser同时处理自动Reviewer问题和人工反馈。

### 修改内容

- 新增 `HumanFeedback`、`HumanFeedbackHandler`
- 新增反馈动作、类型和状态枚举
- `AgentStep` 增加 `collect_human_feedback`
- `TestAnalysisState` 增加 `human_feedback`
- 新业务规则增加确认流程
- 扩展修正Prompt，允许Reviewer结果和人工反馈独立或同时存在
- 扩展Reviser前置条件及反馈应用状态
- 增加反馈模型、确认、等待、Reviser集成和序列化测试

### 反馈结构

```text
feedback_id
action: add / remove / modify / update_priority
feedback_type: test_suggestion / business_rule
target
content
reason
status: pending_confirmation / ready / applied
```

### 两类反馈

普通测试建议不会改变需求事实，例如“增加弱网支付场景”，可以直接进入 `ready` 并交给Reviser。

业务规则会改变测试预期，例如“库存不足时允许创建缺货订单”，提交后先进入 `pending_confirmation`，任务切换为 `waiting_for_user`。只有明确确认后，规则才写入 `state.business_rules`，反馈才变为 `ready`。

### 执行链路

```text
用户反馈
  → HumanFeedback.from_dict()
  → HumanFeedbackHandler.submit()
  → 测试建议：ready
  → 业务规则：pending_confirmation → waiting_for_user
  → confirm_business_rule()
  → 写入business_rules并恢复任务
  → TestPointReviser读取ready反馈
  → 修正成功后标记applied
```

### 关键设计

LLM Reviewer通过不代表人工必须接受。如果存在 `ready` 人工反馈，即使 `review_passed=True`，Reviser也可以执行。人工意见与自动评分是两个独立质量来源。

未确认业务规则不能进入Prompt，避免把用户尚未确认的说明误当成正式预期。反馈只有在修正成功后才标记为 `applied`；模型超时或结构校验失败时仍保留 `ready`，方便后续重试或人工处理。

Reviser现在可以在两种条件下执行：

```text
Reviewer明确未达标
或者
存在已确认、尚未应用的人工反馈
```

### 验证结果

- 全量85个单元测试通过
- 覆盖反馈动作校验、业务规则等待与确认、State更新、人工意见修改已通过结果、未确认反馈阻断和应用状态
- 单元测试不访问真实模型

### 当前边界

- 尚未接入Streamlit反馈输入框和确认按钮
- 尚未实现Orchestrator自动选择反馈与修正分支
- 业务规则确认目前按整条反馈处理，不支持字段级差异确认
- 尚未保存人工操作用户、时间和权限信息

### 建议提交信息

```text
功能：实现Agent结构化人工反馈
```

### 下一步

进入阶段2.9，实现Python Orchestrator和Reviewer/Reviser最大循环次数。

---

## 阶段 2.9：AgentOrchestrator 受控编排与循环限制

### 本阶段目标

用确定性的Python规则串联现有Agent节点，根据共享State选择唯一合法动作，并限制Reviewer/Reviser循环，形成首个内部可自动运行的Agent主链路。

### 修改内容

- 新增 `AgentOrchestrator`
- 新增 `OrchestratorAction`、`OrchestratorDecision`
- 新增单步执行和持续执行到阻塞点两种接口
- State增加最大修正次数、评审历史和修正历史
- Reviewer保存每轮评分和对应修正次数
- Reviser保存修正前后快照、评审依据和人工反馈ID
- 增加分支选择、完整循环、次数上限和总步骤保护测试

### 决策顺序

```text
任务终态 → terminal
等待用户 → wait_for_user
未分析 → RequirementAnalyzer
存在待确认项 → wait_for_user
未检索 → KnowledgeRetriever
未生成 → TestPointGenerator
存在ready人工反馈且未到上限 → TestPointReviser
当前版本未评审 → TestPointReviewer
评审通过 → ready_for_finalization
评审未通过且未到上限 → TestPointReviser
达到上限 → revision_limit_reached
```

顺序本身很重要。例如人工反馈要在“评审通过”判断之前检查，否则自动Reviewer一旦通过，用户意见就不会被执行。

### 两种执行方式

`run_next()`只执行一个节点，适合页面逐步展示和调试。

`run_until_blocked()`连续执行，直到：

- 等待用户补充或确认
- 评审通过，准备最终化
- 达到自动修正上限
- 任务完成或失败

### 双重循环保护

第一层是 `max_revision_count`，默认2次，专门限制Reviewer/Reviser自动修正循环。

第二层是 `max_steps`，默认20步，防止某个节点没有正确更新State，导致Orchestrator不断选择同一动作。超过总步骤上限时任务进入failed并抛出 `OrchestrationError`。

### 历史记录

`review_history`保存：

```text
评审轮次
当时的revision_count
是否达标
完整结构化评审结果
```

`revision_history`保存：

```text
修正次数
修正前测试点
修正后测试点
使用的Reviewer结果
应用的人工反馈ID
```

### 关键设计

LLM负责各节点内部的语义任务，但不返回 `next_action`。是否等待、检索、生成、评审、修正或停止完全由Python读取State决定，体现受控Agent而非无限自由的自主循环。

达到修正上限不是任务执行失败。系统保留当前测试点和评审结果，返回 `revision_limit_reached`，后续页面应提示用户人工处理。

### 验证结果

- 全量96个单元测试通过
- 覆盖所有主要决策分支、人工反馈优先级、完整修正闭环、修正次数上限和总步骤保护
- 使用Fake节点验证编排，不访问真实LLM、Milvus或Embedding

### 当前边界

- 内部Orchestrator尚未接入Streamlit
- 尚未实现Finalizer
- 等待用户后的具体页面恢复操作尚未实现
- 历史快照保存在内存State，尚未持久化

### 建议提交信息

```text
功能：实现Agent受控编排与循环限制
```

### 下一步

进入阶段2.10，实现Finalizer最终结果整理节点，将通过评审或经人工确认的结构化测试点转换为统一交付结果，并由Orchestrator驱动任务进入完成状态。阶段2.11再将完整Agent链路接入Streamlit页面。

---

## 阶段规划校正：Finalizer先于页面集成

### 校正原因

阶段2.9完成后复核发现，开发日志和接力文档原先把Streamlit集成安排在Finalizer之前，但PRD里程碑将Finalizer归属于M3质量闭环，页面属于后续M4。页面如果先接入，只能直接解释零散State字段；Finalizer加入后还需要再次修改页面的数据契约和终止流程。

### 统一后的顺序

```text
阶段2.10：Finalizer
  → 建立统一最终结果模型
  → 汇总覆盖、质量、来源、风险和测试点
  → 写入State并完成任务

阶段2.11：Streamlit Agent页面接入
  → 展示执行轨迹和结构化结果
  → 支持待确认项、人工反馈和最终报告

阶段2.12：离线评测与演示完善
```

### 影响范围

本次只校正后续开发计划，不改变阶段2.9已经实现的Orchestrator行为。下一阶段实现Finalizer时，再把当前的 `ready_for_finalization` 停止结果扩展为可执行的最终化节点。

---

## 阶段 2.10：Finalizer最终结果整理节点

### 本阶段目标

补齐Agent内部最后一个节点，把已经通过质量门禁的结构化测试点整理成稳定的页面数据和Markdown报告，并让Orchestrator真正完成任务。

### 修改内容

- 新增 `FinalizationResult` 和 `Finalizer`
- State新增 `final_result`
- 统计测试点分类、优先级和来源
- 汇总需求覆盖、Reviewer质量结果、评审轮次和修正次数
- 保留推导风险、RAG降级/无命中提示和Reviewer关注项
- 生成确定性的Markdown测试分析报告
- Orchestrator新增 `finalize` 动作并执行Finalizer
- Finalizer完成后任务进入`completed`，下一轮决策返回`terminal`
- 增加Finalizer、State序列化和完整编排闭环测试

### 核心流程

```text
review_passed=True
  → Orchestrator选择finalize
  → Finalizer校验测试点和完整Reviewer结果
  → Python生成final_result和Markdown report
  → status=completed
  → Orchestrator下一轮返回terminal
```

### 关键设计

Finalizer不调用LLM。测试点在Reviewer通过后已经成为当前有效版本，如果Finalizer再次让模型改写内容，新的内容就没有经过评审。因此本节点只做统计、复制、格式化和风险提示。

`final_result`服务于程序和后续页面，保留结构化字段；`report`服务于用户阅读和Markdown下载。两者来自同一份已校验数据，避免页面重新解析Markdown。

达到修正上限仍不进入Finalizer。`revision_limit_reached`表示自动方式未达到质量门槛，应保留当前结果等待人工处理，不能伪装为成功完成。

### 验证结果

- 新增4个Finalizer单元测试
- 全量101个单元测试通过
- 覆盖成功最终化、统计和报告、降级警告、未通过评审阻断、非法输入阻断、Orchestrator终态闭环及最后允许步骤完成任务
- Finalizer不访问LLM、Milvus或Embedding服务

### 当前边界

- Finalizer只接受Reviewer通过的结果，尚未设计“达到上限后人工强制确认”的状态
- Markdown报告暂未接入Streamlit下载入口
- 页面尚未展示`final_result`、事件轨迹和人工反馈

### 建议提交信息

```text
功能：实现Agent最终结果整理节点
```

### 下一步

进入阶段2.11，将AgentState、Orchestrator、执行轨迹、人工反馈和Finalizer结果接入Streamlit页面。

---

## 阶段 2.11.1：Streamlit Agent基础运行页面

### 本阶段目标

把已完成的Agent后端主链路接入当前Streamlit页面，先支持信息完整的需求自动运行到Finalizer完成，并让用户能够看到Agent如何决策和产生结果。

### 修改内容

- 主页面停止直接调用旧 `TestAssistantManager` Workflow
- 页面创建 `TestAnalysisState` 并调用 `AgentOrchestrator.run_until_blocked()`
- State和决策记录保存在 `st.session_state`
- 支持需求文本和需求文档输入；默认测试经验与Milvus检索由Agent自动使用
- 新增任务概览、Orchestrator决策、Agent事件、结构化测试点、质量评审和最终报告四类展示
- 支持Finalizer Markdown报告下载
- 展示等待用户、任务失败和达到修正上限状态
- 新增 `agent_presenter`，将State转换成页面表格数据
- 增加presenter单元测试和Streamlit AppTest冒烟测试
- 取消Git对两个`utils/__pycache__/*.pyc`缓存文件的跟踪
- 结构化LLM调用启用`response_format={"type": "json_object"}`
- 检查`finish_reason=length`并将其明确报告为JSON截断
- 对JSON解析或字段校验失败最多受控重试一次
- 页面移除预先写死的后续步骤提示，只展示真实决策和事件

### 页面调用链

```text
Streamlit输入
  → TestAnalysisState
  → AgentOrchestrator.run_until_blocked()
  → State与decisions写入session_state
  → presenter转换展示数据
  → 页面展示轨迹、测试点、评分和报告
```

### 关键设计

`st.session_state`只负责保存当前浏览器会话中的任务对象，Agent业务规则仍然位于State、节点和Orchestrator中。页面不重新判断下一步，也不直接修改评审结果。

本阶段没有复用旧页面的自然语言“整篇报告重写”，因为新Agent已经使用结构化测试点和HumanFeedback模型。后续人工交互必须接入结构化反馈，避免页面再次绕过Reviewer和Reviser。

临时测试经验上传不放在每次任务的主页面。当前自动加载项目默认经验，后续如需上传、更新和删除知识资产，应设计独立知识库管理功能并持久化到合适的数据库，避免用户每次分析都重复上传。

真实页面调试发现RequirementAnalyzer可能收到未闭合JSON。根因诊断能力不足：旧客户端没有启用JSON Output、没有检查`finish_reason`，解析异常也丢失了行列位置。修复后所有结构化节点统一使用JSON Output，校验失败只重试一次，传输错误不盲目重试；终端日志不记录API Key和完整需求原文。

### 验证结果

- 全量110个单元测试通过
- Streamlit AppTest确认首页无异常、空输入禁用启动按钮、有效输入启用按钮
- presenter测试覆盖任务概览、决策/事件表和测试点字段展平
- Python编译与差异格式检查通过
- 使用真实DeepSeek验证RequirementAnalyzer成功返回结构化结果
- 使用Streamlit AppTest真实点击启动，页面无异常并正确展示等待用户状态

### 当前边界

- 页面只能展示待确认问题，尚不能回答并恢复
- 尚未提供结构化人工反馈表单
- 达到修正上限后尚未提供人工决策入口
- Agent同步执行，页面不能在每个真实节点完成后立即刷新

### 建议提交信息

```text
功能：接入Streamlit Agent基础运行页面
```

### 下一步

进入阶段2.11.2，实现待确认问题回答、需求上下文更新和任务恢复。

---

## 阶段 2.11.2：待确认恢复与双栏工作台

### 本阶段目标

解决 RequirementAnalyzer 暂停后用户没有输入入口的问题，并将页面调整为更适合持续查看结果的左右布局。

### 需求澄清与任务恢复

- RequirementAnalyzer 每轮只允许最多 3 个阻塞核心业务判断的问题
- Prompt 要求合并同类问题，技术细节和低影响未知项转为推导风险
- State 新增 `user_clarifications` 和 `deferred_questions`
- 用户回答会作为确认事实重新参与需求分析
- 用户选择“暂不确定”时不编造答案、不重复追问，并在最终报告中保留风险
- 页面新增逐项回答和“暂不确定”表单
- 恢复后继续使用同一个 State，由 Orchestrator 执行后续节点

### 逐节点执行与刷新恢复

- Streamlit 页面不再一次调用 `run_until_blocked()` 跑完整条链路，而是逐次调用 `AgentOrchestrator.run_next()`
- 每个节点完成后保存 State 并通过受控 `st.rerun()` 刷新页面，使决策和事件可以逐步展示
- 页面设置 20 步保护上限，防止异常状态导致无限重跑；Agent 自身仍保留编排器最大步骤和修正次数约束
- 补充信息提交后先设置待处理标记并立即刷新，避免重复点击和嵌套动态组件造成的 React 渲染异常
- URL 保存 `task_id`，`st.cache_resource` 维护服务进程内任务表，支持浏览器刷新后恢复当前任务
- 任务记录带有 `in_progress` 标记，降低页面重跑时重复执行同一节点的风险

### 页面与报告

- 页面改成左侧需求工作台、右侧任务概览与固定高度结果区
- 执行 Spinner、输入提示和补充问题都位于左侧；右侧持续展示状态、决策、事件和结果
- 左右栏使用一致的外层高度，轨迹、结构化测试点、质量评审和最终报告在右侧内部滚动
- 概览中的内部步骤名和测试点分类转换为中文展示，但 State 中继续保存稳定英文枚举
- 左侧提示会根据执行中、等待补充、失败和完成状态变化
- Finalizer 将结构化测试点输出为 Markdown 表格，报告下载按钮位于正文上方

### 结构化输出稳定性

- LLM JSON 请求优先使用结构化响应格式
- 对空响应、长度截断和非法 JSON 给出可识别错误，并执行一次受控重试
- 测试点生成节点单独使用 8192 的输出 token 上限，降低大型 JSON 被截断的概率
- 结构化模型继续作为最终数据边界，失败输出不会直接写入 Agent State

### 设计原因

问题数量不能只靠 Prompt 约束，因此 Python 模型同时校验最多 3 项。用户无法回答并不意味着 Agent 可以猜测，暂缓项必须作为不确定性保留到报告中。

页面只负责收集输入、展示状态和触发下一次执行，后续节点选择仍由 Orchestrator 负责，避免 UI 复制一套流程规则。逐节点刷新改善的是“节点之间的可见进度”，单个 LLM 请求仍为同步调用。

`task_id + st.cache_resource` 是刷新恢复方案，不是历史持久化。它不会把任务写入磁盘或数据库，因此 Streamlit 服务重启、进程切换或换电脑后无法恢复。

### 主要文件

- `agent/models.py`、`agent/state.py`、`agent/requirement_analyzer.py`
- `agent/finalizer.py`、`agent/test_point_generator.py`
- `services/llm_service.py`、`services/prompt_service.py`、`services/structured_output.py`
- `views/tab_test_points.py`、`views/agent_presenter.py`
- `tests/` 中对应的 Agent、Service、Presenter 和 Streamlit 页面测试

### 验证结果

- 119 项单元测试通过
- Streamlit AppTest 验证普通输入页面无异常
- Streamlit AppTest 验证等待状态表单、暂不确定选项和暂停提示正常
- 未调用真实 DeepSeek、Milvus 或 Embedding 服务

### 当前边界

- 单个 LLM 节点执行期间页面仍需同步等待，不是后台异步任务
- 刷新恢复只在当前 Streamlit 服务进程有效，服务重启后任务会丢失
- 结构化人工反馈尚未接入页面，达到自动修正上限后仍需后续阶段处理
- MySQL 历史任务持久化尚未实现；后续需单独设计任务表、State 快照、事件、报告、连接配置、迁移和失败降级
- 不把用户截图中的服务器地址、数据库账号或凭据写入仓库

### Git 提交

```text
e9441c6 功能：实现待确认恢复与双栏Agent工作台
```

### 下一步

阶段 2.11.3：将结构化人工反馈、业务规则确认和 Reviser 重新评审链路接入页面。

---

## 阶段 2.11.3：结构化人工反馈页面闭环

### 本阶段目标

把已经完成的 `HumanFeedbackHandler` 接入 Streamlit 页面，让用户可以在报告生成后提交结构化意见，并由 Agent 重新修正、评审和整理报告。

### 页面交互

- 已完成任务和达到自动修正上限的任务显示人工反馈入口
- 测试建议支持新增、修改、删除测试点和调整 P0/P1/P2 优先级
- 修改、删除和优先级调整从当前测试点标题中选择目标，减少手工输入错误
- 业务规则支持新增、修改和删除，并与普通测试建议明确区分
- 右侧新增“人工反馈”标签，显示类型、动作、目标、内容、原因和处理状态
- 页面清空任务时同步清理人工反馈组件状态

### 业务规则二次确认

业务规则不是普通测试建议，因为它会改变后续测试预期。页面提交业务规则后：

```text
HumanFeedback.status=pending_confirmation
  → State进入waiting_for_user
  → 页面展示规则内容与依据
  → 用户确认：写入business_rules并进入ready
  → 用户取消：标记rejected且不修改需求事实
```

确认或取消都由 `HumanFeedbackHandler` 处理，页面不直接修改 `business_rules`。

### 已完成任务重新打开

Finalizer完成后State原本属于终态，不能继续启动节点。本阶段新增 `state.reopen_for_feedback()`：

- 只允许已完成且仍保留测试点和评审结果的任务重新打开
- 将状态恢复为`running`并进入`collect_human_feedback`
- 清空旧`final_result`和`report`，避免页面继续展示已经过期的报告
- 保留需求分析、测试点、历史评审、事件和任务ID

普通测试建议进入以下闭环：

```text
completed
  → reopen_for_feedback
  → HumanFeedback ready
  → Reviser
  → Reviewer
  → Finalizer
  → completed（新报告）
```

### 修正次数拆分

原有`revision_count`同时承担总次数展示和自动上限判断。接入人工反馈后会导致人工修正错误占用自动额度。本阶段拆分为：

- `revision_count`：全部修正的总次数
- `automatic_revision_count`：Reviewer未达标触发的自动修正次数
- `human_revision_count`：人工反馈触发的修正次数
- `max_revision_count`：只约束`automatic_revision_count`

人工反馈可以在自动修正达到上限后继续提交，但人工修改重新评审后，如果仍不达标，后续自动修正仍受剩余额度控制。

### 大体量结构化输出预算修复

阶段2.11.2曾为首次生成测试点的`TestPointGenerator`单独配置8192输出
token，但`TestPointReviewer`和`TestPointReviser`仍使用默认4096。Reviser需要返回
修正后的完整测试点集合，真实任务包含约10个测试点时可能触发
`finish_reason=length`，导致JSON被截断并使任务失败。

本阶段将8192收口为`LARGE_STRUCTURED_OUTPUT_MAX_TOKENS`，由以下节点共同使用：

- `TestPointGenerator`：返回首次生成的完整测试点集合
- `TestPointReviewer`：返回每条需求事实的覆盖结果和质量问题
- `TestPointReviser`：返回修正后的完整测试点集合

RequirementAnalyzer的响应体相对较小，仍使用默认预算。节点单元测试直接断言
`max_tokens=8192`已传给`LLMService.generate_json()`，避免以后新增或重构节点时再次遗漏。

### 主要文件

- `agent/state.py`
- `agent/human_feedback.py`
- `agent/orchestrator.py`
- `agent/test_point_reviser.py`
- `agent/test_point_reviewer.py`
- `agent/finalizer.py`
- `views/tab_test_points.py`
- `views/agent_presenter.py`
- 对应Agent、Presenter和Streamlit页面测试

### 验证结果

- 127项单元测试通过
- 覆盖已完成任务重新打开、业务规则确认与取消、人工反馈超过自动上限仍可执行
- 覆盖“人工反馈→Reviser→Reviewer→Finalizer→新报告”的完整受控编排
- Streamlit AppTest覆盖人工反馈表单和业务规则确认入口
- 覆盖Generator、Reviewer和Reviser统一传递8192结构化输出预算
- 测试不调用真实DeepSeek、Milvus或Embedding服务

### 当前边界

- 人工反馈仍依赖LLM Reviser，不提供页面直接编辑整张测试点表格
- 当前一次提交一条反馈，不支持批量草稿后统一提交
- 历史任务和反馈只保存在Streamlit服务进程内，服务重启后仍会丢失
- MySQL持久化和历史任务列表尚未实现

### 建议提交信息

```text
功能：接入结构化人工反馈与重新评审闭环
```

### 下一步

先设计MySQL历史任务持久化的数据模型、配置边界、恢复流程和失败降级，再进入实现阶段。

---

## 阶段 2.11.4：Agent执行体验与人工反馈稳定性优化

### 本阶段目标

根据真实页面测试中单个LLM节点需要约1–2分钟、用户容易误判“卡死”的现象，
改善同步执行的可理解性，同时修复人工反馈处理完成后旧输入仍保留的问题。

### 具体节点进度

页面在调用`run_next()`前先使用同一个`AgentOrchestrator`执行`decide_next()`，
因此可以显示即将运行的真实节点，而不是笼统的“执行下一个节点”：

- 需求分析、测试点生成、质量评审、测试点修正：提示模型通常需要1–2分钟
- 知识检索：说明外部服务慢或失败时会降级继续
- Finalizer：显示正在整理报告

这只是等待预期，不是伪造的进度百分比。页面仍采用同步请求，单个节点执行期间
不会实时刷新右侧State。

### 节点耗时

`AgentOrchestrator.run_next()`使用单调时钟测量实际执行时间，并把
`duration_seconds`写入返回的`OrchestratorDecision`。Presenter负责：

- 将内部动作枚举转换为中文节点名称
- 将耗时格式化为“x.xx 秒”
- 在右侧决策轨迹中统一展示

用户补充需求后的重新分析虽然是页面恢复入口直接调用RequirementAnalyzer，
也会追加一条需求分析决策和耗时，避免恢复路径成为观测盲区。

### 人工反馈防误重复

真实测试发现反馈应用完成后，旧内容仍留在文本框，用户可能再次点击提交。
页面现在维护`agent_feedback_form_version`：

```text
提交成功
→ HumanFeedback写入State
→ form_version加1
→ 页面使用一组新的Widget key
→ 旧输入不再出现在新表单
```

提交后同时显示“人工反馈已接收”，运行期间不再展示反馈表单。该机制解决页面
误重复，不替代HumanFeedback的领域校验。

### 真实回归：完整集合修正仍会被截断

真实人工反馈任务包含12个测试点。即使Reviser已使用8192 token，模型为了应用一条
新增业务规则仍需要重写全部测试点，最终再次触发`finish_reason=length`。这说明继续
提高预算只能延后问题，不能消除响应规模随测试点数量线性增长的根因。

本阶段将Reviser输出契约改为最小化操作：

```text
LLM返回 add / replace / remove
→ Python校验操作字段和完整TestPoint
→ target_title必须精确命中一个现有测试点
→ 在临时副本中按顺序应用全部操作
→ 全部成功后一次性写入State
```

未变化的测试点不再出现在模型响应中。任何操作非法、目标不存在、产生重复标题、
删除全部测试点或最终没有变化时，整组操作失败，State继续保留原始测试点，避免
“只应用一半”的不一致状态。

### 真实回归：React #185

人工反馈恢复执行时，页面同时维护动态DataFrame、嵌套info/spinner和每秒rerun轮询，
连续组件树变化会触发Streamlit前端React #185。修复后：

- 决策和事件轨迹不再使用动态DataFrame
- 同一节点已执行时显示单一提示并返回，不再每秒轮询
- 节点执行提示只使用一个placeholder，不再重复渲染info和spinner

结构化测试点和反馈列表仍保留可滚动DataFrame，因为它们不参与节点级高频刷新。

真实页面复核又发现`st.table`会强制显示DataFrame索引列。最终改为由Presenter
生成安全转义的静态HTML表格：不显示默认索引，不引入动态表格组件，并对事件说明
等模型相关文本进行HTML转义。

同一次真实任务中，Reviewer返回了`missing_scenarios: [""]`。它表达的是“没有缺失
场景”，但原严格校验将空字符串视为非法并在两次响应后终止任务。本阶段采用有边界
的兼容策略：

- `missing_scenarios`和`revision_suggestions`允许过滤纯空白字符串
- 非字符串元素仍然失败，不放宽JSON类型契约
- `covered_by`、重复组和幻觉问题继续使用严格校验
- Prompt明确要求无问题时直接返回`[]`

后续真实回归还发现两个问题：

1. 去掉组件默认索引后，Agent事件也失去了用户需要的业务顺序。Presenter现在为
   每条事件显式生成从1开始的`序号`，与无意义的DataFrame索引明确区分。
2. 已通过85分的任务提交一条人工反馈时，Reviser仍携带旧Reviewer结果，模型可能
   同时处理旧建议并返回过多操作，再次达到8192 token。

人工反馈Reviser因此改为独立最小作用域：

```text
存在ready人工反馈
→ 本轮Prompt不携带旧Reviewer结果
→ 根据反馈action计算允许的add/replace/remove
→ 新增反馈最多3个操作，其他反馈通常最多1个操作
→ Parser同时校验操作类型与数量
→ 应用后重新进入Reviewer
```

旧Reviewer并没有丢失，仍保存在State和评审历史中；这里只是不再把已经通过的旧建议
作为本轮人工修正目标。人工修改后的新版本会重新评审，如果未达标，下一轮自动
Reviser再单独处理新的Reviewer问题。

### 主要文件

- `agent/orchestrator.py`
- `agent/models.py`
- `agent/test_point_reviser.py`
- `prompts/test_point_revision.txt`
- `services/prompt_service.py`
- `views/agent_presenter.py`
- `views/tab_test_points.py`
- `tests/unit/agent/test_orchestrator.py`
- `tests/unit/views/test_agent_presenter.py`
- `tests/app/test_streamlit_agent_page.py`

### 验证结果

- 140项单元测试通过
- 覆盖节点耗时的确定性计时测试
- 覆盖中文动作和耗时格式化
- 覆盖人工反馈提交后表单版本递增、单条反馈写入和受理提示
- 覆盖增删改操作解析、未修改测试点保留和无效目标原子回滚
- 覆盖轨迹静态表格和执行中任务不重复轮询
- 覆盖静态表格无索引、内容转义和Reviewer空白可选项归一化
- 覆盖Agent事件业务序号、人工反馈Prompt硬约束和越界操作拒绝
- 不调用真实DeepSeek、Milvus或Embedding服务

### 当前边界

- Streamlit仍同步执行LLM调用，不提供实时Token流、百分比或后台任务
- “1–2分钟”来自当前真实测试的等待预期，不是服务等级承诺
- 节点失败时State和事件会记录错误，但失败节点当前不会产生完成耗时
- 增量操作目前使用测试点标题定位；标题必须唯一，后续持久化阶段可评估稳定ID

### 建议提交信息

```text
优化：增强Agent执行轨迹与人工反馈修正稳定性
```

### 下一步

进入MySQL历史任务持久化设计，先确定数据模型、连接配置、恢复语义和写入失败降级，
再开始数据库实现。

---

## 阶段 2.11.5A：Streamlit信息架构调整

### 本阶段目标

在不改变Agent业务逻辑、State、任务恢复和rerun顺序的前提下，降低双栏页面的信息拥挤，
让用户优先看到原始需求、当前阶段和主要分析结果，把调试轨迹降为按需查看的信息。

本阶段只做信息架构和必要布局调整，不实现侧边栏、MySQL或阶段2.11.5B视觉规范。

### 修改内容

- 保留左右双栏，取消左右栏和结果区的固定高度
- 左侧只负责PRD输入、原始需求对照、待确认问题、业务规则确认和主要任务操作
- 任务创建后不再保留禁用的空输入控件，改为从`state.requirement`只读展示原始需求
- 右侧合并状态、当前步骤和修正计数等重复提示
- 增加五阶段指示器：需求分析、知识检索、生成测试点、评审与修正、整理报告
- 主结果只保留结构化测试点、质量评审、人工反馈、最终报告四个Tab
- 人工反馈表单和受理提示统一移入右侧“人工反馈”Tab
- Orchestrator决策与完整Agent事件移入默认折叠的“执行详情”
- 自动修正达到上限时明确引导用户进入人工反馈Tab；普通节点失败继续显示具体错误

### 信息架构边界

```text
左侧需求工作台
├─ 创建前：文本输入 / 文件上传 / 启动
└─ 创建后：只读原始需求 / 待确认回答 / 业务规则确认 / 清空

右侧任务结果
├─ 任务状态 + 当前步骤 + 五阶段进度
├─ 测试点 / 质量评审 / 人工反馈 / 最终报告
└─ 执行详情（默认折叠）
   ├─ Orchestrator决策
   └─ 完整Agent事件
```

### 为什么使用`state.requirement`作为只读来源

文件上传控件属于页面临时输入，rerun或刷新后不适合作为任务事实来源。任务创建时，
`DocumentService`已经把文本、Markdown、PDF或DOCX解析为字符串并写入
`TestAnalysisState.requirement`。因此任务开始后的对照内容统一读取State，文本输入和
文件上传走同一显示契约，也与后续MySQL保存State快照的方向一致。

### 红线复核

本阶段没有修改：

- State字段、状态转换和Orchestrator决策顺序
- `_initialize_session`、`_persist_task`和`_task_store`
- `_create_agent_task`与`_reset_session`
- `_process_agent_step`与`_execute_next_orchestrator_node`
- `task_id`刷新恢复
- 需求补充、业务规则确认、人工反馈提交后的rerun顺序

页面仍在原有位置调用`_process_agent_step()`，只是把唯一的执行提示占位符放入右侧状态区。

### 测试设计

- Presenter测试验证当前步骤到五阶段的映射，以及失败阶段与未开始阶段的区别
- AppTest验证文本输入和内存上传文件都能创建任务并写入稳定需求文本
- AppTest验证四个主Tab、只读需求、默认折叠执行详情、自动修正上限提示、失败提示和报告下载
- DocumentService测试独立验证TXT和Markdown上传内容解析
- 既有Agent、Orchestrator和页面测试继续验证逐节点执行、需求补充、业务规则、自动修正、
  人工反馈、最终报告、刷新恢复和防重复执行
- 所有自动化测试继续使用Fake Service或预置State，不调用真实外部服务

### 验证结果

- 154项全量测试通过
- Python编译检查和`git diff --check`通过
- 浏览器验证空任务和完成任务双栏页面无异常
- 完成任务页面只检测到页面外层一个纵向滚动容器
- 浏览器验证“人工反馈”Tab包含唯一反馈表单
- 浏览器验证“最终报告”Tab保留顶部Markdown下载按钮
- 浏览器验证“执行详情”默认折叠

### 当前边界

- Streamlit同步调用LLM的限制不变，单节点执行中没有实时百分比
- 结构化测试点DataFrame等局部内容仍可能出现组件自身滚动
- 暂不添加`st.sidebar`；历史任务入口与MySQL在阶段2.12一起实现
- 暂不统一字号、阴影、边框和按钮视觉层级，这些属于阶段2.11.5B

### 2.11.5A布局修正

首次页面截图中，未开始状态来自正式`main.py`，完成状态却来自只调用
`views.tab_test_points.render_ui()`的临时预览入口。临时入口绕过了：

- `st.set_page_config(layout="wide")`
- `main.py`中的工作区宽度CSS
- `main.py`中的产品标题和说明

因此完成态截图落入Streamlit默认窄容器，同时缺少产品头部。这不是State导致正式页面
切换容器，而是验证入口不一致。修正后，四种状态截图都通过同一个临时包装器执行完整
`main.py`，包装器只在正式`render_test_points()`调用前注入测试State。

正式页面同步完成以下布局修正：

- 所有状态共用最大1360px的主工作区和唯一产品头部
- 删除页面内部重复的“测试分析 Agent 工作台”同级标题
- 未开始状态右侧改为完整高度的居中空结果面板
- 未开始、执行中和需求补充使用约42/58双栏
- 已完成、达到修正上限和人工反馈处理使用约33/67双栏
- 结构化测试点从超宽DataFrame改为摘要列表和逐项折叠详情
- 状态区、Tab内容不再额外套明显边框，减少右侧卡片嵌套
- 清空任务继续使用次要按钮，并缩小为左栏右侧操作

浏览器在统一1280px宽度下验证四种状态，测得工作区CSS最大宽度为1360px，页面无横向
溢出；完成态左右栏实际约352/730px，未开始和普通执行态约452/630px。

### 2.11.5A状态标题收尾

`TestAnalysisState.current_step`记录的是内部执行位置。RequirementAnalyzer在
`initialize`阶段发现待确认项时，任务会暂停为`waiting_for_user`，因此直接把
`current_step`翻译为页面标题会得到“等待用户 · 初始化”，但用户实际正在完成需求分析。

Presenter新增只读映射，根据State和已有决策生成产品文案：

- 新任务：等待开始 · 需求分析
- 普通执行：执行中 · 对应五阶段
- 需求待确认：等待补充信息 · 需求分析
- 业务规则待确认：等待规则确认 · 评审与修正
- 人工反馈应用中：人工反馈处理中 · 评审与修正
- 自动修正上限：已达自动修正上限 · 评审与修正
- 完成：已完成 · 整理报告
- 失败：执行失败 · 失败节点所属阶段

该映射不回写State，不参与Orchestrator决策，也不改变暂停和恢复逻辑。

### 建议提交信息

```text
优化：调整Agent双栏页面信息架构
```

### 下一步

先由用户确认阶段2.11.5A的页面行为和信息位置。确认后再单独进入2.11.5B视觉规范统一，
不得与MySQL历史任务阶段混合提交。

---

## 阶段 2.11.5B：Streamlit视觉规范统一（第一轮）

### 本阶段目标

保持2.11.5A已经确认的左右分栏、四个主Tab、执行详情和测试点展开方式不变，只统一页面
的字号、间距、圆角、颜色和操作层级，降低默认Streamlit组件拼凑感。

### 第一轮修改

- 缩小页面顶部留白、产品标题和副标题间距
- 将Tab激活文字与下划线从红色统一为产品蓝色
- 将五阶段进度从胶囊按钮样式调整为轻量文字状态
- 主区域、按钮和展开项统一使用6～8px圆角
- 移除按钮悬浮位移和大面积阴影，只保留轻量边框反馈
- 任务已创建时将次要操作显示为“新建分析”，未开始时显示“重置输入”
- 测试点摘要按标题、中文分类、优先级和场景摘要对齐
- 对模型生成的测试点摘要进行HTML转义

### 保持不变

- 左右分栏及不同状态下的栏宽比例
- 结构化测试点、质量评审、人工反馈、最终报告四个Tab
- 测试点逐项展开和完整结构化字段
- 默认折叠的执行详情
- AgentState、Orchestrator、任务恢复、人工反馈和rerun执行顺序

### 验证方式

- Presenter测试检查测试点摘要样式类、中文分类、优先级和HTML转义
- AppTest检查按钮文案、等待补充状态和既有页面组件
- 在同一1280px浏览器宽度下保存未开始、等待补充和已完成三种状态截图
- 157项全量测试、Python编译和`git diff --check`通过

### Git状态

第一轮视觉修改暂不提交。先提供页面截图并等待用户确认，避免将尚未确认的视觉方案固化
到阶段提交中。

### 下一步

用户确认第一轮视觉方向后，只处理明确的视觉细节反馈；确认完成后创建2.11.5B独立提交。
本阶段不进入MySQL历史任务和侧边栏开发。

---

## 阶段 2.11.5C：固定工作区与结果浏览

### 背景

2.11.5A取消固定高度后，页面只剩一个外层滚动位置，但测试点、执行轨迹和最终报告会继续
向下撑高整个浏览器页面。用户需要的是类似翻译工作台的固定左右区域：页面头部和右侧任务
状态保持可见，长需求与当前结果分别在各自正文区域浏览。

本阶段因此恢复有边界的内容高度，但严格限制为两个业务滚动区，不恢复外层卡片、表格和
Tab等多级嵌套滚动。

### 页面滚动模型

```text
产品头部
└─ 左右工作区（适配浏览器可视高度）
   ├─ 左侧固定标题
   │  └─ 需求正文滚动区（唯一左侧滚动）
   └─ 右侧
      ├─ 固定状态、阶段、统计、导航和执行详情入口
      └─ 当前结果正文滚动区（唯一右侧滚动）
```

- 使用Streamlit 1.38原生有高度`st.container`建立两个正文边界
- CSS只通过自定义标记和稳定的`data-testid`定位容器，并用`100dvh`和`clamp`适配视窗
- 不依赖Streamlit自动生成的Emotion类名
- 1280×720浏览器验证中，未开始、等待补充、分页、展开、Dialog和最终报告状态的页面
  `clientHeight`与`scrollHeight`都为720，没有长外层页面

### 有状态结果导航

Streamlit 1.38的`st.tabs`不提供可控的活动Tab值，普通rerun或反馈提交后无法保证仍停留在
用户正在浏览的结果。页面改用带独立key的单选导航，并通过集中CSS呈现为Tab样式。

活动导航只写入`agent_ui_active_result_tab`，不写入AgentState。普通rerun保持当前选择；
新建或切换任务时根据任务状态选择合适的默认结果页；人工反馈提交后继续停留在人工反馈页。

### 页面专用状态与重置

新增状态全部使用`agent_ui_`前缀：

- `agent_ui_active_result_tab`：当前结果导航
- `agent_ui_test_point_page`：测试点当前页
- `agent_ui_expanded_test_point`：当前展开测试点的真实身份
- `agent_ui_test_point_signature`：测试点集合内容签名
- `agent_ui_pagination_task_id`：分页所属任务
- `agent_ui_execution_details_*`：任务级Dialog入口状态

任务ID变化会重置导航、页码和展开项；测试点集合变化只重置页码和展开项；清空或新建任务
会删除全部`agent_ui_`页面键。原有业务session_state键、task_id恢复和rerun顺序不变。

### 测试点分页与展开

- 默认每页5条，只对当前State集合做切片展示
- 页码显示当前页和总页数，支持上一页和下一页
- 翻页后关闭上一页展开项
- 默认全部收起，同一时间只保存一个真实测试点身份
- 展开区继续显示前置条件、步骤、预期结果和来源
- 人工反馈目标仍使用完整测试点集合中的稳定标题，不使用当前页序号
- 集合签名变化后重置分页，避免上一批测试点的页码落到新集合

分页前后不会修改`state.test_points`，也不改变测试点模型。

### 执行详情Dialog

Streamlit 1.38和当前AppTest均能稳定使用`st.dialog`，因此没有降级为第五个Tab。
“查看执行详情”位于右侧固定状态区域；Dialog内部使用有界容器展示原有Orchestrator决策和
Agent事件。关闭Dialog后，活动结果导航、测试点页码和展开项保持不变。

### 测试与红线

新增AppTest覆盖：

- 12条测试点按5条分页，只渲染当前页
- 单项展开、切换展开项和翻页自动收起
- 分页不改变AgentState中的测试点集合
- 测试点集合变化、task_id切换、新建和清空任务的页面状态重置
- 普通rerun、人工反馈提交和Dialog关闭后的结果导航保持
- Dialog打开后展示原有决策和事件数据

本阶段通过162项全量测试、Python编译和`git diff --check`。AST复核确认以下红线函数与
阶段检查点完全一致：

- `_initialize_session`
- `_persist_task`
- `_process_agent_step`
- `_execute_next_orchestrator_node`
- `_create_agent_task`
- `_reset_session`

AgentState、Orchestrator、节点顺序、暂停恢复、Reviewer、Reviser、测试点模型、人工反馈
业务逻辑和task_id恢复机制均未修改。

### 当前状态

代码、文档和页面滚动行为已通过用户确认，准备创建独立中文提交。后续小型修正单独处理
执行中动态反馈与左右工作区高度一致性，不自动继续2.11.5B，也不进入MySQL历史任务。

---

## 阶段 2.11.5D：执行状态反馈与工作区高度统一

### 问题

固定工作区完成后，右侧只在节点调用前显示一条临时静态提示，用户需要打开执行详情Dialog
才能判断任务是否仍在运行。同时左右外框仍由不同内部高度和内容共同撑开，状态变化时底部
不能始终对齐。

### 同步Streamlit的反馈边界

当前页面与LLM调用运行在同一条同步脚本中。Streamlit可以在进入阻塞式模型调用前将组件
增量发送给浏览器，因此节点调用前创建的`st.status(state="running")`可以显示并保持原生
Spinner。模型请求期间没有新的Python执行机会，所以本阶段不伪造百分比、剩余时间或
Token级进展；节点返回后的既有rerun立即更新阶段、事件摘要和结果。

### 确定性节点文案

Presenter根据现有State、current_step和下一条OrchestratorAction映射：

- RequirementAnalyzer：分析需求结构、信息边界、业务规则和风险
- KnowledgeRetriever：检索历史测试资产和缺陷经验
- TestPointGenerator：生成结构化、可执行测试点
- Reviewer：检查覆盖度、重复项、异常边界和无依据断言
- Reviser：按第N轮评审或人工反馈定向修正
- Finalizer：整理测试点、覆盖情况、质量结论和最终报告

这些文案没有LLM调用，也不写入AgentState。

### 最近进展

主页面最多展示最近3条用户可理解的进展。数据只来自现有AgentEvent：

- `task_created`
- `step_started`
- `step_completed`
- 与需求补充、业务规则和人工反馈有关的少量`information`
- `task_completed`
- `task_failed`

Presenter过滤其他技术事件，使用步骤中文名转换、去重并按时间顺序展示。完整枚举、原消息、
数据字段和堆栈继续只在执行详情Dialog中查看。

### 操作与防重复

- `PENDING/RUNNING`且页面即将执行、已提交补充信息或任务存储标记`in_progress`时显示Spinner
- 等待用户、达到修正上限、完成和失败时停止Spinner
- 执行中禁用“新建分析”，并说明需要等待当前节点结束
- 原`in_progress`锁继续阻止重复节点；AppTest确认页面rerun后AgentEvent集合未增加
- 活动结果导航、测试点页码和展开项的重置规则未修改

### 统一工作区高度

原布局中左侧正文高度为480，右侧结果正文高度为330，且正常与阻塞状态又使用不同CSS高度；
外层容器自动跟随内容，所以右侧状态、统计和导航会造成底部不一致。

现在左右外层在同一`st.columns`层级中统一使用：

```python
WORKSPACE_HEIGHT = 560
```

外层容器固定为560px并隐藏自身滚动，内部使用稳定的自定义标记和`data-testid`让需求正文、
当前结果正文分别占用剩余高度并设置`overflow-y: auto`。没有使用Emotion自动类名，也没有
通过空白文本或多个`margin-bottom`补齐。

1280×720浏览器实测未开始、执行中、等待用户和完成四种状态：

- 左右外框：`top=156`、`bottom=716`、`height=560`
- 浏览器页面：`clientHeight=720`、`scrollHeight=720`
- 执行中可见原生Spinner
- 等待问题和完成测试点均保留在各自内部滚动区

### 测试与红线

- 新增Presenter测试验证节点文案和最近进展映射
- AppTest验证执行中Spinner状态、禁用新建分析和防重复事件
- AppTest验证等待与完成状态停止Spinner
- 165项全量测试通过

本阶段没有修改AgentOrchestrator、AgentState转换、LLM调用、节点顺序、人工反馈、分页和
rerun时机。`_process_agent_step`和`_execute_next_orchestrator_node`只在原来的提示语调用点
换成展示函数，节点调用和状态写入顺序保持不变。

### 固定操作栏与结果浏览修正

真实浏览器复核发现，左侧待确认问题和提交按钮仍在同一滚动容器中；右侧虽然配置了结果
容器高度，但Streamlit固定组件和默认间距会把结果容器下半部分推到外框之外。修正后：

- 统一工作区高度调整为736px，左右仍使用同一个外框高度
- 左侧由56px标题预算、512px正文滚动区和120px固定操作区组成
- 初始启动、执行中禁用、补充提交、规则确认、新建和失败重试均在固定操作区
- 补充问题控件使用稳定页面key，底部按钮继续执行原必填和“暂不确定”校验
- 右侧固定区域使用确定性紧凑摘要，结果正文实际可见408px且是唯一右侧滚动区
- 测试点完整详情移入第二个`st.dialog`；身份优先取已有ID，否则使用完整内容哈希
- Dialog关闭后保留活动结果页、分页和列表位置，测试点集合未被修改

1280×900浏览器实测页面`clientHeight`与`scrollHeight`均为900；左右外框
`top=156`、`bottom=892`，左侧正文`scrollTop=0`时提交按钮仍在视口内。
全量测试增加到166项。

### 当前状态

代码、测试、浏览器截图和文档已完成。Streamlit页面至此定位为V1功能演示界面：用于演示
完整Agent链路和人工反馈闭环，不继续追求完全复刻DeepL或生产级固定工作台。本阶段不再
恢复2.11.5B视觉精修；下一小阶段优先处理LLM调用耗时、输出预算和自动修正成本。

---

## 路线图校准：后端边界、任务持久化与知识资产闭环

### 校准原因

阶段2.11完成后，继续直接在Streamlit中接入MySQL、Milvus写回和性能逻辑，会让页面再次
承担任务创建、节点推进、状态保存和外部服务调用。与此同时，项目虽然能够从Milvus检索
历史资产，但当前Agent页面没有把审核后的结果重新沉淀为历史资产，知识来源仍依赖旧集合、
旧Workflow或手动写入。

本次只调整文档和阶段顺序，不修改代码，不把规划能力描述为已实现。

### 当前代码事实

- `RAGService.save_case()`仍保留写入Milvus的方法
- `TestAssistantManager.save_to_rag()`仍作为旧Workflow兼容入口
- 当前Agent页面没有调用上述保存方法
- 当前Milvus实现同时保存向量、PRD文本和测试点文本
- 当前Agent任务只保存在Streamlit进程内
- 166项离线自动化测试通过，但没有真实RAG和质量评测结论

### 数据职责校准

后续明确区分：

```text
MySQL任务快照
→ 保存Agent执行和恢复所需的完整状态

MySQL KnowledgeAsset
→ 保存用户确认后的完整、权威、可版本化测试资产

Milvus V2索引
→ 保存向量、asset_id和必要元数据，负责找出语义相似候选
```

Milvus比较的是当前需求查询向量与历史知识资产检索向量。命中后返回`asset_id`和相似度，
Application Service再从MySQL读取完整资产，由ContextBuilder决定哪些内容进入Generator。

### 新阶段顺序

- 2.12：先增加Application Service和Repository边界
- 2.13：再实现MySQL任务快照、事件、恢复和重复保护
- 2.14：再实现用户确认后的KnowledgeAsset与Milvus V2闭环
- 2.15：在稳定数据边界上增加ContextBuilder、Token和耗时
- 2.16：建立离线评测与三组消融实验
- 2.17：最后才评估FastAPI、后台任务、SSE和Vue

后续小阶段统一使用`2.12.1`、`2.12.2`等数字编号，不再使用A、B、C、D。历史已经提交的
2.11.5A～2.11.5D名称保持不变，用于保留真实开发记录。

### 范围控制

当前P0不包含：

- 多Agent自由协作
- LLM自主选择任意节点或工具
- 不受控自主规划
- 为展示而增加长期记忆
- 后端边界未稳定前重写Vue
- 没有真实超预算样本的复杂自动摘要

### 下一步

先提交本次文档校准。用户确认后，从阶段`2.12.1 Application Service接口`开始代码开发，
不直接跳到MySQL或Milvus写回。

---

## 阶段 2.12：后端调用边界

### 本阶段目标

在不改变Agent节点顺序、状态转换、Reviewer/Reviser规则和Streamlit页面结构的前提下，
隔离页面与Agent核心。Streamlit只能表达用户动作，Application Service负责加载任务、
调用受控编排器、保存结果并返回只读视图。

### 开发前问题

`views/tab_test_points.py`原来直接承担：

- 创建`TestAnalysisState`
- 创建并调用`AgentOrchestrator`
- 直接调用`RequirementAnalyzer.reanalyze_with_clarifications()`
- 直接调用`HumanFeedbackHandler`
- 使用`st.cache_resource`中的`_task_store()`保存可变State
- 在session_state中保存决策、自动运行、待补充命令和执行步数

`_task_store()`属于Streamlit进程级共享资源，不是会话级存储。不同会话只要知道task_id，
理论上可以访问同一份可变State；同时页面、存储和业务控制耦合，未来接MySQL或FastAPI会
重复改写页面逻辑。

### Application Service

新增`TestAnalysisApplicationService`，公开：

```text
create_task
get_task
list_tasks
advance_task
submit_clarifications
confirm_business_rules
submit_feedback
retry_task
delete_task
```

接口只表达创建、继续、补充、确认、反馈和重试等用户用例，没有提供
`execute_node(node_name)`。`advance_task()`仍调用既有Orchestrator，由Orchestrator根据
AgentState选择唯一合法节点；Application Service没有复制状态机。

上传文档也通过`CreateTaskCommand + UploadedDocument`进入Application Service，再调用既有
DocumentService解析，页面不再直接调用文档、知识、LLM或RAG服务。

### TaskRepository与会话隔离

新增`TaskRepository`契约：

```text
create(record)
get(task_id)
save(record, expected_version=None)
list()
delete(task_id)
```

`InMemoryTaskRepository`使用锁保护单实例读写，并在创建、读取、保存和列表时使用深复制。
Application Service修改的是加载出的隔离副本，完成用例后显式保存；页面无法通过
`TaskView`绕过Repository修改AgentState。

当前Repository在每个Streamlit会话初始化时单独装配，不再使用模块级或进程级任务字典。
因此同一会话的普通rerun可以继续任务，但跨新会话、硬刷新会话重建和服务重启恢复明确留给
2.13 MySQL，不再用全局可变字典模拟持久化。

### 只读TaskView

页面session_state不再保存AgentState。Application Service把Repository中的State复制为
`TaskView`，列表和字典字段在读取时再次返回副本。TaskView还提供：

- Orchestrator决策只读元组
- 是否自动推进、是否处理中
- 待补充命令状态
- 执行步数
- 待确认业务规则的只读视图
- 是否达到自动修正上限
- 节点执行指标与累计执行耗时

Presenter改为接收TaskView，但展示映射、文案、CSS、布局、分页和Dialog行为没有改变。

### 页面保留的session_state

页面继续保存：

- 会话级Application Service依赖
- 当前task_id
- 结果Tab、测试点页码、Dialog和展开项
- 需求输入、上传控件、问题回答和反馈表单草稿
- 表单版本和一次性成功提示

页面不再保存可变State、决策列表、自动运行、待处理补充命令或执行步数。

### 最小性能基线

Application Service在每次推进前后记录`NodeExecutionMetric`：

- action
- started_at与finished_at
- duration_seconds
- succeeded
- error_type

`TaskView.total_execution_seconds`汇总节点实际执行时间。指标包装不会改变节点输入或结果。
LLM Token、模型、重试次数、Embedding和Milvus耗时需要统一外部调用埋点，按范围留到2.15。

### 自动化测试

新增：

- Application Service创建、推进、补充、规则确认、反馈、完成、修正和失败测试
- Repository创建、读取、保存、删除、隔离副本和会话实例隔离测试
- AST架构测试，禁止页面引用Orchestrator、节点、FeedbackHandler、AgentState和`_task_store()`
- AppTest改为通过会话级Application Service与Repository注入任务

完整结果：

```text
python -m unittest discover -s tests -v
181 tests passed
```

已有文本/文件创建、等待补充、业务规则确认、人工反馈、分页、Dialog、失败、完成和防重复
页面测试全部通过。测试不访问真实DeepSeek、Milvus或Embedding。

### 依赖方向

```text
views
→ application
→ repositories.TaskRepository
→ agent.AgentOrchestrator / nodes / HumanFeedbackHandler
→ services
```

会话启动位置只调用`build_session_application_service()`，具体内存Repository的装配位于
Application bootstrap中，页面不访问Repository。

### 当前限制与下一步

- `expected_version`已预留但内存实现不执行版本校验
- `in_progress`只覆盖同一会话同步调用
- 新会话和服务重启后不能恢复内存任务
- State缺少可靠`from_dict()`和快照schema version
- 节点指标尚未分解到LLM、Embedding和Milvus

下一阶段只进入2.13 MySQL任务快照、事件、恢复和重复执行保护，不同时实现KnowledgeAsset、
Milvus V2、FastAPI、后台任务、SSE或Vue。

## 阶段 2.12 验收修正：补充恢复统一经过Orchestrator

### 验收发现

阶段2.12首次验收确认页面已经只调用Application Service，但补充信息后的重新分析仍由
Application Service私有方法直接创建并调用RequirementAnalyzer。这条特殊路径绕过了
AgentOrchestrator，与“所有Agent节点执行权统一收口到Orchestrator”的边界不一致。

### 最小修正

- AgentOrchestrator增加`resume_with_clarifications(state, answers)`语义入口
- Orchestrator校验任务必须处于等待用户状态、答案问题集合必须完整匹配、非空答案不能是空白
- Application Service移除RequirementAnalyzer导入和工厂，只调用Orchestrator恢复入口
- 待处理补充答案在Orchestrator调用前从TaskRecord消费；成功、再次等待或失败后不会重复消费
- 页面继续只调用`submit_clarifications()`和`advance_task()`，没有节点级接口或交互变化

修正后的调用链：

```text
Streamlit
→ TestAnalysisApplicationService
→ AgentOrchestrator.resume_with_clarifications
→ RequirementAnalyzer.reanalyze_with_clarifications
```

### 测试证据

新增或加强：

- Orchestrator恢复入口的合法状态、问题集合和空白答案校验
- 补充恢复同一task_id、再次等待、充分后继续和失败保存
- 同一批答案只消费一次
- in_progress与终态不重复执行节点
- retry_task、list_tasks和delete_task
- 从创建、等待补充、重新分析、检索、生成、评审到最终完成的Application Service Fake主流程
- AST边界测试：页面不得导入Repository和外部能力Service，Application Service不得引用
  RequirementAnalyzer

完整结果：

```text
python -m unittest discover -s tests -v
192 tests passed
```

本次没有修改Streamlit页面、CSS、AgentState、节点业务规则或rerun节奏，也没有进入2.13。

## 阶段 2.13.1：AgentState版本化快照序列化

### 本阶段目标

在不连接MySQL、不修改页面和Agent执行规则的前提下，先建立稳定、可读、可校验的任务快照
契约。后续MySQL Repository只负责保存和读取该契约，不需要自行猜测如何重建领域对象。

### 实际实现

新增独立`TaskSnapshotSerializer`，以`TaskRecord`为完整恢复单元：

```text
TaskRecord
├─ state：AgentState全部业务状态
└─ application：决策、自动推进、待消费补充、执行步数、下一动作和节点指标
```

快照顶层固定为：

```json
{
  "schema_version": 1,
  "task_id": "task-id",
  "state": {},
  "application": {}
}
```

序列化器提供`to_dict`、`from_dict`、`to_json`、`from_json`和预留的
`migrate_snapshot`。它不使用pickle、Python类路径或`default=str`，所有枚举保存稳定value，
所有时间强制带时区并统一输出UTC ISO 8601。

### 恢复与校验边界

- AgentStatus、AgentStep、KnowledgeRetrievalStatus、AgentEventType和OrchestratorAction恢复为枚举
- AgentEvent、OrchestratorDecision和NodeExecutionMetric恢复为原类型
- TestPoint、Reviewer结果、推导风险和HumanFeedback先通过现有领域模型校验，再写回State约定的
  结构化字典
- 评审历史、修正历史和Finalizer结果按当前真实字段严格校验
- 缺少schema_version、未知版本、缺少必填字段、未知字段、非法枚举和无时区时间均拒绝
- 快照恢复产生独立可变对象，不与原任务或输入字典共享引用

`in_progress`没有进入快照。它只是当前Python进程中的同步重入保护，不是可靠的数据库执行
租约；恢复时固定为`False`。数据库乐观锁version、execution_id、执行租约和数据库时间也不
属于schema v1，本阶段没有把这些未来概念伪装成已实现能力。

### AgentState与TaskRecord关系

AgentState保存需求、RAG、测试点、评审、修正、反馈、报告、错误和事件等业务状态。
TaskRecord在其外部补充应用执行元数据。仅保存AgentState会丢失待消费的补充答案、自动推进
开关、下一动作、Orchestrator决策和节点耗时，因此快照以TaskRecord为边界，但仍把
AgentState放在明确的`state`节点中。

### 自动化测试

新增33项快照格式与异常测试，覆盖：

- 完整dict与JSON往返
- 全部核心枚举、UTC时间和AgentEvent类型恢复
- 测试点嵌套步骤、Reviewer结果、人工反馈、RAG和节点指标
- 等待需求补充、等待业务规则确认、评审失败待修正、完成和失败任务
- 空列表与可选字段
- 缺失字段、非法枚举、非法时间、未知字段和未来版本
- 标准`json.dumps`兼容、运行时对象拒绝和深复制隔离

验收收尾另增加5项恢复执行测试，实际经过：

```text
TaskSnapshotSerializer
→ InMemoryTaskRepository
→ TestAnalysisApplicationService
→ AgentOrchestrator
→ Fake节点
```

覆盖补充信息后重新分析、业务规则确认与拒绝、Reviewer未通过后的Reviser/Reviewer闭环，
以及completed/failed恢复后不重复调用Orchestrator和节点。

完整回归结果：

```text
python -m unittest discover -s tests -v
230 tests passed
```

Streamlit文件、页面布局、Agent节点、Orchestrator和Repository均未修改。

### 对2.13.2的输入

- 合成全字段测试任务的UTF-8快照约5.9 KB，仅用于结构验证，不代表真实生产分布
- MySQL建议优先使用原生`JSON`列保存快照，便于合法JSON约束和必要字段排查；若真实大样本
  证明频繁接近JSON列限制，再根据数据测量调整，而不是提前使用LONGTEXT
- `task_id`、status、current_step、schema_version、version、created_at、updated_at和
  error_type等查询/并发字段应独立成列，不依赖JSON路径完成常用查询
- AgentEvent和节点执行记录应进入独立事件表，快照内事件用于完整恢复，事件表用于增量审计
- Repository保存需要task_id、快照、expected_version和待追加事件；version仍留到后续实现
- 快照更新与新增事件必须在同一数据库事务中提交
- 首批索引应围绕task_id唯一键、status+updated_at和事件task_id+sequence设计

### 下一步

阶段2.13.2只设计并实现MySQL任务与事件持久化，不同时引入KnowledgeAsset、Milvus V2、
FastAPI、SSE或Vue。服务重启恢复和重复执行保护继续按2.13.3、2.13.4独立验收。

## 阶段 2.13.2：MySQL任务快照与独立事件Repository

### 本阶段目标

在不修改Agent业务规则、不实现乐观锁和执行租约的前提下，把阶段2.13.1的schema v1快照接入
可替换的MySQL Repository，并保证任务快照与新增Agent事件原子保存。

### 实际实现

- 新增`MySQLTaskRepository`，实现`TaskRepository`的`create/get/save/list/delete`契约
- `agent_tasks`使用MySQL原生JSON列保存完整TaskRecord快照，同时独立保存status、current_step、
  requirement_summary、schema_version、version和UTC数据库时间等查询字段
- `agent_task_events`按`task_id + sequence_no`保存事件类型、步骤、说明、data和发生时间
- 创建任务时，任务快照和初始事件在同一事务写入
- 更新任务时先锁定任务行并读取`event_count`，只追加尚未持久化的新事件
- 如果待保存快照的事件数量小于数据库记录，明确拒绝审计历史倒退
- 快照更新或事件插入任一步失败时回滚整个事务
- 通过`TASK_REPOSITORY_BACKEND`选择`memory`或`mysql`；未配置时继续使用会话级内存实现
- MySQL账号、密码、库名和连接超时只通过`.env`读取

### 数据库version的当前边界

任务表已经预留`version`并在每次保存时递增，但本阶段没有使用`expected_version`生成条件更新。
因此它当前只能记录更新次数，不能阻止两个旧快照互相覆盖。可靠乐观锁、execution_id和执行租约
仍属于2.13.4，文档和简历不能提前描述为已实现。

### 测试证据

新增15项不访问真实数据库的测试，使用Fake DB-API验证：

- 两张表的建表语句和初始化事务
- schema v1快照与初始事件同事务创建
- 事件写入失败时快照整体回滚
- 重复task_id映射为领域重复错误
- 从JSON列恢复完整TaskRecord及领域枚举
- save只追加新增事件并递增数据库version
- 审计事件历史不能倒退
- list、delete和不存在任务语义
- MySQL环境变量校验
- 默认内存装配、显式MySQL装配和非法后端拒绝
- Streamlit AppTest显式固定为内存Repository，避免本机`.env`选择MySQL后让单元测试误连真实数据库

完整回归结果：

```text
python -m unittest discover -s tests -v
245 tests passed
```

测试没有连接真实DeepSeek、Milvus、Embedding或MySQL。页面布局、AgentState、Orchestrator、
节点顺序和人工反馈规则均未修改。

### 当前限制与下一步

本阶段除Fake事务测试外，还使用本机`.env`连接真实MySQL 8.0.32，成功创建`ai_test_assistant`
数据库以及`agent_tasks`、`agent_task_events`两张空表，确认网络、认证和DDL可用。真实账号、
密码和服务器地址均未写入代码或文档。

阶段2.13.3仍需在隔离测试数据上完成TaskRecord真实CRUD，并通过销毁和重新装配Application
Service验证同一task_id的等待、完成和失败任务可以恢复。随后2.13.4再处理version冲突、
execution_id和执行租约，不同时进入FastAPI或知识资产沉淀。

## 阶段 2.13.3：真实MySQL CRUD与跨实例任务恢复

### 本阶段目标

不修改Agent业务规则和页面，通过真实MySQL证明阶段2.13.2的Repository不仅能建表，还能保存、
恢复和清理完整TaskRecord，并证明新的Application Service实例可以继续同一个task_id。

### 实际实现

- 新增显式开启的真实MySQL集成测试，默认单元测试不会连接外部数据库
- 使用独立UUID验证`create/get/save/list/delete`完整CRUD
- 保存后核对`agent_tasks.version`从1递增到2，`event_count`与事件表实际记录数一致
- 删除任务后核对外键级联清理`agent_task_events`
- 第一个Application Service创建任务、推进到等待状态并提交用户补充信息后，重新创建Repository和Application Service
- 新实例按同一task_id恢复待消费答案，通过Orchestrator恢复需求分析并进入知识检索
- 新实例恢复completed和failed任务后，调用`advance_task`不会创建Orchestrator或重复执行节点
- 每项集成测试结束后按精确task_id清理数据，不修改或扫描其他任务内容

### 测试分层

日常回归仍然快速且不依赖网络：

```text
python -m unittest discover -s tests -v
248 tests discovered, OK (skipped=3)
```

真实MySQL验证必须显式开启：

```text
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m unittest tests.integration.mysql.test_mysql_task_repository_integration -v
3 integration tests passed
```

真实测试没有调用DeepSeek、Embedding或Milvus，也没有使用公司需求或其他敏感业务数据。

### 能力边界

本阶段证明的是“持久化后的任务可以由新的应用服务实例读取并按原状态继续”。它不等于已经
解决两个进程同时推进一个任务的问题。数据库version当前仍只是递增记录；可靠冲突检测、
execution_id和执行租约留到2.13.4，也不宣称外部LLM请求Exactly Once。

### 下一步

阶段2.13.4只处理重复执行保护：让expected_version参与条件更新，增加execution_id和可过期
执行租约及其并发测试。知识资产、Milvus V2、FastAPI和Vue不进入该阶段。

## 阶段 2.13.4：乐观锁、execution_id与执行租约

### 本阶段目标

解决“任务能够从MySQL恢复，但两个应用实例仍可能读取同一旧快照并重复执行节点”的问题。
本阶段只增加Repository和Application Service执行保护，不修改AgentState、Orchestrator决策、节点顺序或页面布局。

### 实际实现

- `TaskRepository`增加`get_versioned`，同时返回隔离的`TaskRecord`和数据库版本
- InMemory与MySQL的`save(record, expected_version)`都执行版本校验并返回新版本
- MySQL保存使用`WHERE task_id = ? AND version = ?`条件更新，受影响行数不为1时报告版本冲突
- 新增`agent_task_executions`表，记录execution_id、task_id、动作、状态、worker、租约时间、错误和完成时间
- Repository增加`acquire_execution`与`complete_execution`，领取和提交都在数据库事务中完成
- Application Service推进节点前领取租约，节点结束后使用同一租约保存快照、增量事件和执行状态
- 相同execution_id已经完成时直接返回当前任务；存在其他未过期租约时不调用Orchestrator
- 补充需求、业务规则确认和人工反馈等普通写操作也使用读取到的expected_version

### 三个编号的区别

- `schema_version`：JSON快照结构版本，当前仍为1
- `version`：某条数据库任务记录的并发版本，每次持久化控制操作递增
- `execution_id`：一次推进请求的幂等编号，用于识别网络重试或重复请求

三者互相独立。本阶段没有修改快照schema，也没有把数据库租约塞进AgentState。

### 租约恢复规则

执行者领取租约时写入owner和过期时间。其他执行者在租约有效期内只能看到任务正在执行，不能调用节点；
租约过期后，新执行者可以将旧记录标记为`expired`并领取新租约。旧执行者即使稍后返回，也会因版本或租约校验失败而不能覆盖新结果。

默认租约为600秒，当前同步架构没有后台续租。因此它用于进程异常后的可恢复互斥，但不保证外部LLM只被调用一次：
如果调用超过租约并发生接管，外部请求可能重复，最终只有仍持有合法租约的结果可以提交。

### 自动化测试

新增或加强的测试覆盖：

- 旧TaskRecord保存时触发`TaskVersionConflictError`
- 相同execution_id完成后不能再次领取
- 未过期租约阻止另一执行进入
- 租约过期后新执行者接管，旧租约不能提交
- Application Service重复请求不再次调用Orchestrator节点
- Fake MySQL事务包含执行记录创建、快照提交和执行状态完成
- 新增3项显式真实MySQL用例：乐观锁冲突、execution_id幂等和过期租约接管

验证结果：

```text
python -m unittest discover -s tests -v
260 tests passed（6项真实MySQL测试默认跳过）
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m unittest tests.integration.mysql.test_mysql_task_repository_integration -v
6 integration tests passed
```

真实MySQL 8.0.32已完成6项集成验证，`agent_task_executions`建表、乐观锁冲突、execution_id幂等和
租约过期接管均通过；临时任务已精确清理。本轮未访问真实DeepSeek、Embedding或Milvus。

### 下一步

阶段2.13.5进行低风险pytest测试工程升级：先让pytest兼容收集现有unittest，增加marker和fixture，
不一次性重写260项测试。完成后再进入2.14 KnowledgeAsset和Milvus知识沉淀闭环。

## 阶段 2.13.5：pytest统一测试入口

### 本阶段目标

在不修改Agent业务行为、不废弃原有unittest的前提下，为持续增长的测试建立统一分类、公共fixture和
pytest运行入口。本阶段只升级测试工程，不实施KnowledgeAsset、FastAPI或前端改造。

### 实际实现

- 新增`requirements-dev.txt`，通过`-r requirements.txt`复用运行依赖，并单独声明pytest 8.x
- 新增`pytest.ini`，固定`tests/`为收集目录，启用严格marker校验
- 将测试类规则收紧为`*Tests`，避免把导入的`TestAnalysisState`等领域类误当测试类
- 新增`tests/conftest.py`，集中提供全新InMemoryTaskRepository和TaskRecord工厂fixture
- 通过`pytest_collection_modifyitems`按文件自动标记unit、app和integration
- 新增3项pytest原生示例，演示fixture注入、普通assert和`pytest.raises`
- 对Presenter导入函数使用不以`test_`开头的别名，并将Reviser测试辅助构造器从`test_point`改为
  `make_test_point`，解决pytest比unittest更广的函数收集规则

### 为什么不一次迁移全部测试

pytest能够直接运行`unittest.TestCase`，因此没有必要为了语法统一重写260项稳定用例。批量改写会制造
大量无业务价值的diff并增加误删断言的风险。当前采用渐进策略：旧测试继续提供回归证据，新测试优先使用
pytest fixture和assert；只有某个旧文件确实因重复setup难维护时再局部迁移。

### 测试分类

```text
unit：不访问真实基础设施的快速测试，包括Repository Fake和Agent节点Fake
app：Streamlit AppTest页面行为测试
integration：必须显式开启的真实MySQL测试
```

分类由测试文件确定，不依赖人工逐项标注；`--strict-markers`可防止拼错marker后悄悄失效。

### 验证结果

```text
python -m unittest discover -s tests -v
260 tests，OK（6 skipped）

python -m pytest
257 passed，6 skipped，共收集263项

python -m pytest -m unit
234 passed，29 deselected

python -m pytest -m app
23 passed，240 deselected

python -m pytest -m integration
6 skipped，257 deselected
```

pytest比unittest多3项，是新增的pytest原生基础设施测试；真实MySQL、DeepSeek、Embedding和Milvus均未
被默认测试调用。

### 下一步

阶段2.14.1只实现KnowledgeAsset领域模型、准入规则和Repository边界；2.14.2再接MySQL权威存储，
2.14.3再建立Milvus V2索引，避免把模型、数据库和向量索引一次性混在同一提交中。

## 阶段 2.13.6：测试目录分层

### 本阶段目标

阶段2.13.5已经让pytest统一收集原有unittest，并提供marker与fixture，但所有测试文件仍平铺在
`tests/`根目录。随着Agent、Application、Repository和外部集成测试继续增加，文件职责不直观，
新测试也容易继续堆积。本阶段只整理物理目录，不改生产代码和测试业务断言。

### 实际实现

- `tests/unit/`按`agent`、`application`、`repositories`、`services`、`views`和`legacy`分组
- `tests/architecture/`保存静态依赖边界测试
- `tests/app/`保存Streamlit AppTest及其小型fixture应用
- `tests/integration/mysql/`保存必须显式开启的真实MySQL测试
- 各层增加`__init__.py`，继续兼容`python -m unittest discover -s tests -v`
- pytest收集钩子按目录自动添加`unit`、`app`和`integration` marker，不再依赖特定文件名
- 只修正测试间相对导入和AppTest fixture路径，没有改变测试场景与断言

### 为什么目录和marker同时保留

目录回答“这份测试属于哪个代码职责”，marker回答“运行这份测试需要多少成本、是否依赖外部环境”。
例如MySQL Fake测试位于`unit/repositories`，真实MySQL测试位于`integration/mysql`；二者都测试
Repository，但运行边界不同。两种分类不是重复，而是分别服务代码导航和测试执行。

### 验证结果

```text
python -m unittest discover -s tests -v
260 tests，OK（6 skipped）

python -m pytest
257 passed，6 skipped，共收集263项
```

测试数量与阶段2.13.5完全一致，说明目录移动没有造成漏收集。真实MySQL、DeepSeek、Embedding和
Milvus均未被默认测试调用，生产代码未修改。

### 下一步

阶段2.14.1开始KnowledgeAsset领域模型、准入规则和Repository边界。后续新增测试直接放入对应层，
旧unittest只在局部维护收益明确时逐步改为pytest风格，不进行批量机械重写。
