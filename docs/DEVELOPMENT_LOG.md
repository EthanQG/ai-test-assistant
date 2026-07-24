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
