# Test Analysis Agent 开发与复盘日志

这份文档记录项目从固定 Workflow 向 Agent 架构演进的过程。它不仅记录代码变化，还解释每次调整的原因、解决的问题、验证方式和下一步计划，方便后续复盘及面试表达。

## 如何维护本文档

每完成一个可以独立验证的小阶段，就在文档顶部的“阶段索引”中增加入口，并在正文末尾追加一节，至少记录：

1. 本阶段目标
2. 修改内容
3. 核心概念
4. 为什么这样设计
5. 验证结果
6. Git 提交
7. 下一步计划

如果只是修正错别字或样式，不必单独增加阶段；如果改变了架构、模型输入、状态流转或用户行为，则应该记录。

## 阶段索引

| 阶段 | 状态 | 核心成果 | Git 提交 |
|---|---|---|---|
| 阶段 1 | 已完成 | 拆分 Service 层，聚焦测试分析功能 | `5875853` |
| 阶段 1.5 | 已完成 | 整理 System/User Prompt 边界 | `95aba63` |
| 阶段 2.1/2.2 | 已完成 | Agent 状态与执行事件模型 | 本阶段提交 |
| 阶段 2.3 | 待开始 | RequirementAnalyzer 需求分析节点 | - |

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
