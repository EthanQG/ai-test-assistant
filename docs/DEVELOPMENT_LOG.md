# Test Analysis Agent 开发与复盘日志

这份文档记录项目从固定 Workflow 向 Agent 架构演进的过程。它不仅记录代码变化，还解释每次调整的原因、解决的问题、验证方式和下一步计划，方便后续复盘及面试表达。

当前产品范围请查看 [PRD V2](product/PRD_AGENT_V2.md)，最新开发接力点请查看 [CURRENT_STATUS.md](CURRENT_STATUS.md)，代码知识与面试复盘请查看 [LEARNING_NOTES.md](LEARNING_NOTES.md)，跨电脑的 Codex 协作规则请查看根目录 [AGENTS.md](../AGENTS.md)。

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
| 阶段 2.3 | 已完成 | RequirementAnalyzer 需求分析节点 | 本阶段提交 |
| 产品范围 V2 | 已完成 | 从三模块 Workflow 收敛为测试分析 Agent | 本阶段提交 |
| 阶段 2.4 | 已完成 | Agent知识检索节点 | 本阶段提交 |
| 阶段 2.5 | 已完成 | 结构化测试点生成节点 | 本阶段提交 |
| 阶段 2.6 | 已完成 | 测试点质量评审节点 | 本阶段提交 |
| 阶段 2.7 | 已完成 | 测试点定向修正节点 | 本阶段提交 |
| 阶段 2.8 | 已完成 | 结构化人工反馈与业务规则确认 | 本阶段提交 |
| 阶段 2.9 | 已完成 | 受控Agent编排与循环限制 | 本阶段提交 |

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
