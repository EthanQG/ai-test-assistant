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
| 阶段 2.13.6 | 已完成 | unit、architecture、app与integration测试目录分层 | `4d3cdb9` |
| 阶段 2.13 | 已完成 | 持久化、恢复、重复执行保护和测试工程入口 | - |
| 阶段 2.14.1 | 已完成 | KnowledgeAsset模型、准入策略、内容哈希和内存Repository | `549207a` |
| 阶段 2.14.2 | 已完成 | 版本化资产快照、MySQL权威表、唯一索引和Repository实现 | `f88a426` |
| 阶段 2.14.3 | 已完成 | 有界语义Chunk、批量Embedding和Milvus V2索引写入边界 | `66f12fa` |
| 阶段 2.14.4 | 已完成 | Milvus V2阈值召回、资产聚合、MySQL批量回查和来源验证 | `aa2abd9` |
| 图文PRD路线图校正 | 已完成（仅文档） | 将结构化文档、OCR、多模态理解和关键问题限流提升为P0 | `ec633e7` |
| 阶段 2.14.5 | 已完成 | 索引失败显式重试、request_id幂等审计和停用向量清理 | `5ecd956` |
| 阶段 2.14 | 已完成 | KnowledgeAsset准入、MySQL权威存储、Milvus V2索引与补偿闭环 | - |
| 阶段 2.15.1 | 已完成 | DocumentContent、文本/表格/图片元素、来源ID和解析警告 | `785f42e` |
| 阶段 2.15.2 | 已完成 | PDF/DOCX原生结构、真实图片附件、边界警告和覆盖统计 | `7826099` |
| 阶段 2.15.3 | 已完成 | OCR协议、扫描页渲染、置信度分流、失败隔离和真实中文冒烟 | `b823c2d`, `98684e2` |
| 阶段 2.15.4 | 已完成 | 有界视觉候选筛选、结构化多模态协议、调用限额和失败降级 | `ca58c5f` |
| 阶段 2.15.5 | 已完成 | 关键问题结构化分类、Python阻塞策略、去重和非阻塞转风险 | `f6d1650` |
| 阶段 2.15.6 | 已完成 | ContextBuilder、节点字段白名单、输入预算、关键片段保留和上下文指标 | `3961861` |
| 阶段 2.15.7 | 已完成 | 服务调用指标、真实/估算Token、Prompt指纹、错误分类和任务性能摘要 | `039f798` |
| 阶段 2.15 | 已完成 | 图文PRD理解、关键问题限流、ContextBuilder、Token预算和分层可观测性 | - |
| 阶段 2.16.1 | 已完成 | schema v1契约、标注指南和10份单人复核的虚构评测需求 | `abdb0cb`, `143b2a0` |
| 阶段 2.16.2 | 第三小步已完成 | 合成附件及正文、表格、OCR、流程和UI确定性评分 | `744228b`, `7395b8d`，本次提交 |
| 阶段 2.16.3 | 第一小步已完成 | 5份虚构RAG查询、资产级排序指标和Fake测试 | 本次提交 |
| 阶段 2.16.9 | 已完成 | 稳定陈述ID、紧凑分类、全局问题审核和非思考结构化调用 | `f65f08f`, `b7583a1`, 本次提交 |
| 阶段 2.16.10 | 已完成 | 长PRD知识检索分区预算、关键条目保留和裁剪指标 | 本次提交 |
| 阶段 2.16.11 | 已完成 | Reviewer常见字段漂移保守归一化 | 本次提交 |
| 阶段 2.16.12 | 已完成 | 旧RAG读取Embedding配置并禁用环境代理 | 本次提交 |
| 阶段 2.16.13 | 已完成 | 长PRD二次Reviewer使用独立有界输出额度 | 本次提交 |
| 阶段 2.16.14 | 已完成 | 真实长PRD完整链路、修正上限和MySQL恢复验收 | 本次提交 |
| 阶段 2.17.1 | 已完成 | FastAPI同步任务与用户动作接口、Swagger和pytest | 本次提交 |
| 阶段 2.17.2 | 已完成 | 单进程后台执行、幂等启动和执行状态查询 | 本次提交 |
| 阶段 2.17.3 | 已完成 | 聚合任务状态、阶段、指标与最近事件的前端轮询接口 | 本次提交 |
| 阶段 2.17.4 | 已完成 | FastAPI文档上传、输入限制与现有解析用例复用 | 本次提交 |
| 阶段 2.17.5 | 已完成 | FastAPI V1完整Fake链路验收与前端调用顺序 | 本次提交 |
| 阶段 2.18.1 | 已完成 | 原生Web双栏骨架、任务创建、后台启动与进度轮询 | 本次提交 |
| 阶段 2.18.2 | 已完成 | 待确认问题回答、同task_id恢复与视觉层级优化 | 本次提交 |
| 阶段 2.18.3 | 已完成 | 结构化测试点分页、结果刷新和详情Dialog | 本次提交 |
| 阶段 2.18.4 | 已完成 | Reviewer质量结果、Markdown报告预览与下载 | 本次提交 |
| 阶段 2.18.5 | 已完成 | 人工反馈、业务规则二次确认与同任务恢复 | 本次提交 |
| 阶段 2.18.6 | 已完成 | Web主链路HTTP验收与DOM元素契约检查 | 本次提交 |
| 阶段 2.18.7 | 已完成 | 补充恢复轮询竞态与Reviewer有界ID输出修复 | 本次提交 |
| 阶段 2.18.8 | 已完成 | Reviewer幻觉问题附加字段的安全兼容 | 本次提交 |
| 阶段 2.18.9 | 已完成 | TestPoint来源枚举的语义归一化与未知值拒绝 | 本次提交 |
| 阶段 2.18.10 | 已完成 | 历史任务摘要分页、搜索与同task_id页面恢复 | 本次提交 |
| 阶段 2.18.11 | 已完成 | 完成结果显式确认、MySQL资产保存与Milvus索引入口 | 本次提交 |
| 阶段 2.18.12 | 已完成 | 左侧历史任务列表、确定性任务名与报告文件统一命名 | 本次提交 |
| 阶段 2.18.13 | 已完成 | 任务项上方悬浮删除确认与MySQL删除语义说明 | 本次提交 |
| 阶段 2.18.14 | 已完成 | 固定视口等高工作区、面板内滚动与确认层防裁剪 | 本次提交 |
| 阶段 2.18.15 | 已完成 | 显式新建任务入口与任务展示名持久化重命名 | 本次提交 |
| 阶段 2.16 | 进行中 | 图文解析、RAG/Reviewer专项评测和三组消融实验 | - |
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

## 阶段 2.14.1：KnowledgeAsset模型与准入规则

### 本阶段目标

旧Workflow可以把结果直接写入Milvus，但当前Agent缺少“什么结果有资格成为历史资产”的安全边界。
本阶段先建立独立KnowledgeAsset模型、确定性准入策略和Repository抽象，只使用内存实现验证，
不同时创建MySQL资产表或写入Milvus。

### 实际实现

- 新增`knowledge_assets/`领域包，定义KnowledgeAsset、StructuredRequirement和索引状态枚举
- 资产保留source_task_id、asset_version、content_hash、原始需求、结构化需求、测试点、完整Reviewer结果、最终报告和确认时间
- content_hash使用规范JSON和SHA-256计算，只由业务内容决定，不包含asset_id、时间和索引状态
- 准入策略要求任务已经完成、Reviewer通过且分数达到阈值、需求事实全部覆盖、没有无依据断言
- 有待确认问题、待处理人工反馈、非法结构化对象或相对当前测试点已经过期的最终报告都会被拒绝
- 用户必须同时确认允许知识沉淀和数据安全，避免模型自动把未经审核或敏感结果写入知识库
- 新增KnowledgeAssetRepository抽象和InMemory实现，按asset_id、content_hash和来源任务版本防重复
- 新增KnowledgeAssetApplicationService，负责从TaskRepository读取任务、确定资产版本、调用准入策略并保存资产
- Application Service只返回只读摘要View，创建知识资产不会修改原TaskRecord或AgentState

### 状态边界

通过准入的新资产状态固定为`pending_index`，表示“权威资产候选已创建，但还没有向量索引”。
模型同时预留`indexed`、`index_failed`和`retired`稳定值，但本阶段没有实现这些状态转换，也没有声称
资产已经写入MySQL或可以被RAG检索。

### 测试证据

新增26项pytest测试，覆盖：

- JSON兼容结构、时区时间、稳定哈希及业务内容变化
- 双重确认、完成状态、Reviewer分数、覆盖度、幻觉问题和最终结果一致性
- 待确认问题与待处理人工反馈禁止沉淀
- 内存Repository CRUD、隔离副本、内容哈希和来源版本唯一性
- Application Service创建第一版、变更后创建下一版、重复内容拒绝和任务状态不被修改
- 领域层不依赖Application、Repository、Service、View，应用服务不直接依赖MySQL、Milvus、Embedding或LLM

完整验证：

```text
python -m unittest discover -s tests -v
260 tests，OK（6 skipped）

python -m pytest
283 passed，6 skipped，共收集289项
```

本阶段未调用真实DeepSeek、Embedding、Milvus或MySQL，Streamlit页面、AgentState、Orchestrator和节点顺序均未修改。

### 当前限制与下一步

InMemoryKnowledgeAssetRepository只提供边界验证，进程退出后资产会丢失；同一来源任务的版本分配也还没有
数据库事务保护。阶段2.14.2将实现MySQLKnowledgeAssetRepository、权威资产表、唯一索引和真实CRUD验证，
但仍不接入Milvus；Milvus V2索引留到2.14.3。

## 阶段 2.14.2：MySQL KnowledgeAsset权威存储

### 本阶段目标

阶段2.14.1已经能够判断一份测试结果是否有资格成为知识资产，但内存Repository会在进程退出后丢失数据。
本阶段只补齐完整资产的MySQL权威存储，不接入页面按钮、Embedding和Milvus，避免把持久化与向量索引混成一个故障边界。

### 实际实现

- 新增`KnowledgeAssetSnapshotSerializer`，使用独立schema v1把KnowledgeAsset转换为标准JSON并恢复为原领域类型
- 快照严格恢复KnowledgeAssetStatus、StructuredRequirement、InferredRisk、TestPoint和TestPointReviewResult
- 缺少字段、未知字段、非法枚举、无时区时间、错误列表类型、损坏JSON和未来版本都会明确失败
- 新增`knowledge_assets`表，完整`asset_json`作为权威记录，摘要、评分、测试点数量和索引状态独立成列
- `content_hash`建立唯一索引，阻止完全相同的业务内容重复沉淀
- `source_task_id + asset_version`建立联合唯一索引，阻止同一任务出现重复版本
- 新增`MySQLKnowledgeAssetRepository`，实现建表、创建、按ID读取、按哈希查询、查询来源任务最新版和列表查询
- 新增`KNOWLEDGE_ASSET_REPOSITORY_BACKEND`配置，默认`memory`，显式选择`mysql`后才建立真实连接和初始化表
- MySQL读取只使用完整快照恢复领域对象，不依赖摘要列拼装残缺资产

### 为什么资产表不外键关联任务表

`source_task_id`用于审计来源，但没有建立到`agent_tasks`的外键。任务执行记录可能按保留策略清理，而用户确认的历史知识资产需要继续被复用。
如果建立级联删除外键，清理任务会误删知识库；如果建立限制删除外键，又会阻塞正常任务清理。因此保留来源ID和应用级审计关系更符合两类数据不同的生命周期。

### MySQL与Milvus的职责

MySQL保存完整需求、测试点、评审证据和报告，是可以恢复与审计的权威数据源。Milvus在后续2.14.3只保存向量和`asset_id`等少量元数据，
搜索命中后必须再按`asset_id`回查MySQL。当前资产保持`pending_index`，不能描述为“已经可以被RAG检索”。

### 测试证据

本阶段新增19项默认执行的pytest测试和2项默认跳过的真实MySQL测试，覆盖：

- 版本化JSON往返、领域类型恢复和可变对象隔离
- 快照缺失字段、非法状态、无时区时间、错误列表、未来版本和损坏JSON
- MySQL DDL、完整JSON写入、重复键错误映射、读取恢复、按哈希/来源查询和列表查询
- MySQL装配选择、未知后端拒绝以及事务提交/回滚
- 真实MySQL环境下的KnowledgeAsset CRUD和缺失资产行为（需显式开启）

完整验证：

```text
python -m unittest discover -s tests
260 tests，OK，6 skipped

python -m pytest -q
302 passed，8 skipped，共收集310项

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```


默认测试没有访问真实DeepSeek、Embedding、Milvus或MySQL。本阶段没有修改Streamlit、AgentState、Orchestrator、节点顺序和提示词。

### 当前限制与下一步

页面尚未组装KnowledgeAssetApplicationService，因此用户现在还看不到“保存到知识库”按钮。真实MySQL资产集成测试已经写入仓库，
但本轮遵守外部服务隔离约定，没有主动连接用户数据库执行。阶段2.14.3将建立MySQL资产状态与Milvus V2索引闭环；页面按钮在后端闭环稳定后再接入。

## 阶段 2.14.3：Milvus V2知识资产索引

### 本阶段目标

MySQL已经保存完整KnowledgeAsset，但后续任务还无法通过语义检索找到它。本阶段只实现从`pending_index`资产到Milvus V2的索引写入，
不同时实现查询、LLM精排、ContextBuilder、页面按钮和后台任务。

### 实际实现

- 新增KnowledgeAssetChunk、ChunkType和ChunkBuilder，确定性构建需求概览、事实、规则、风险和测试点Chunk
- 每条Chunk都包含稳定`chunk_id`、`asset_id`、来源任务、资产版本、`content_hash`、类型、序号和检索文本
- 默认最多32条Chunk、单条最多1600字符；超过上限记录省略数量，文本截断时设置`was_truncated`
- 新增OllamaBatchEmbeddingService，使用`/api/embed`的数组输入在一次HTTP请求中生成整批向量
- 新增独立`knowledge_assets_v2`集合适配器，不修改旧`ai_test_cases`兼容集合
- V2集合只保存向量、短检索文本和关联元数据，不保存完整需求、评审结果或报告
- 新增KnowledgeAssetIndexingService，编排MySQL读取、Chunk构建、Embedding、Milvus upsert和MySQL状态更新
- 索引成功后状态由`pending_index`变为`indexed`；Embedding或Milvus失败时变为`index_failed`
- 已经`indexed`的资产直接返回，不重复调用外部服务
- Repository新增带`expected_status`的状态更新，MySQL使用`SELECT ... FOR UPDATE`和条件UPDATE保持快照状态与摘要状态一致

### 为什么使用批量Embedding

长PRD可能产生多个事实、规则、风险和测试点。如果逐条请求Embedding，外部网络往返次数会随Chunk数量线性增长。
V2索引先在Python中生成有界Chunk，再将文本数组一次提交给Ollama`/api/embed`。这不会减少模型计算量，但减少了网络往返，
并且最多32条的硬上限防止单份资产产生无界工作量。

### 跨MySQL与Milvus的一致性

MySQL与Milvus无法加入同一个ACID事务，因此采用以下可补偿设计：

1. MySQL先存在`pending_index`完整资产；
2. Milvus使用稳定`chunk_id`执行upsert；
3. 全部向量写入完成后，MySQL才更新为`indexed`；
4. 如果MySQL状态更新暂时失败，后续使用相同Chunk ID重放不会制造重复记录；
5. 后续检索只接受MySQL状态仍为`indexed`且版本、哈希一致的资产。

本阶段只建立安全重放基础，`index_failed`显式重试、request_id和孤立索引清理仍属于2.14.5。

### 测试证据

本阶段新增20项pytest测试，覆盖：

- Chunk类型、关联元数据、稳定ID、数量上限、文本长度和截断标记
- 一次批量Embedding请求及环境配置
- Milvus V2 upsert中的asset_id、版本、哈希和检索文本
- 成功索引、Embedding失败、Milvus失败、向量数量错误和重复索引保护
- InMemory/MySQL状态更新、期望状态冲突、JSON快照与摘要状态原子更新
- Application索引用例不直接依赖requests、Ollama或MilvusClient

完整验证：

```text
python -m unittest discover -s tests
260 tests，OK，6 skipped

python -m pytest -q
322 passed，8 skipped，共收集330项

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

默认测试未访问真实DeepSeek、Ollama、Milvus或MySQL；Streamlit、AgentState、Orchestrator、Prompt和节点顺序均未修改。

### 当前限制与下一步

当前只实现索引写入，还没有实现V2查询和MySQL回查，因此不能宣称新资产已经被当前KnowledgeRetriever使用。
阶段2.14.4将实现Top-K候选召回、阈值过滤、按资产聚合、MySQL回查和来源验证，不增加LLM精排。

## 阶段 2.14.4：Milvus V2候选召回与MySQL权威回查

### 本阶段目标

阶段2.14.3已经能把确认资产拆成有界Chunk并写入Milvus，但“向量能被找到”还不等于“完整资产可信”。
本阶段补齐查询侧边界：Milvus只负责召回短片段，完整内容必须按稳定`asset_id`回查MySQL，并再次校验状态、来源、版本和内容哈希。

### 实际实现

- 新增`KnowledgeAssetVectorHit`，明确Milvus返回的短片段、相似度和关联元数据
- 新增`KnowledgeAssetRetrievalCandidate/Result`，返回完整权威资产、最高分数和有界命中片段
- 新增`KnowledgeAssetRetrievalService`，完成一次查询Embedding、一次Milvus搜索、阈值过滤、资产聚合和一次MySQL批量回查
- `KnowledgeAssetRepository`增加`get_many()`，内存实现返回隔离副本，MySQL实现使用单条`IN`查询
- `MilvusKnowledgeAssetIndex`增加COSINE搜索并恢复稳定关联字段
- 默认`raw_limit=20`、`top_k=3`、`min_score=0.65`，同一资产最多保留3条匹配Chunk
- 新增环境配置和Bootstrap装配入口，但未修改当前Agent节点或Streamlit

### 为什么必须回查MySQL

Milvus中的向量可能因为跨存储失败而成为孤儿，也可能对应已经停用或重新发布的旧版本。如果直接把命中的短文本交给LLM，旧业务规则可能污染新的测试分析。
因此检索服务只接受满足以下全部条件的候选：

```text
MySQL中存在相同asset_id
AND status == indexed
AND source_task_id一致
AND asset_version一致
AND content_hash一致
```

任何一项不满足都按过期或孤立命中丢弃。最终返回的完整内容来自MySQL，而不是Milvus短文本。

### 时长控制

本阶段刻意不加入LLM精排。一次检索固定为：

```text
1次查询Embedding + 1次Milvus搜索 + 1次MySQL批量查询
```

同一资产的多个Chunk先在内存聚合，MySQL不按命中逐条查询。该设计减少网络往返，但尚未执行真实环境性能测试，不能声明具体毫秒数。

### 测试证据

新增或加强测试覆盖：

- 查询只调用一次Embedding和一次向量搜索
- 阈值过滤、同资产多Chunk聚合、Top-K排序和数量限制
- 孤儿向量、未索引资产、版本不一致和哈希不一致全部丢弃
- 非法查询向量和空查询明确失败
- MySQL批量回查只执行一条SQL并去除重复ID
- Milvus搜索结果恢复稳定关联元数据
- Application检索用例不直接依赖Ollama、MilvusClient、requests、pymilvus或LLM

完整验证：

```text
python -m unittest discover -s tests -v
260 tests，OK，6 skipped

python -m pytest -q
337 passed，8 skipped，共收集345项

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

默认测试只使用Fake服务，不访问真实DeepSeek、Ollama、Milvus或MySQL。

### 当前限制与下一步

本阶段提供的是可被Agent或未来FastAPI复用的后端检索用例，尚未替换当前KnowledgeRetriever，也没有实现ContextBuilder裁剪。
`0.65`只是可配置基线，需要阶段2.16离线评测后才能判断效果。阶段2.14.5继续处理`index_failed`重试、重复请求保护和跨MySQL/Milvus补偿审计。

## 路线图校正：图文PRD理解前置于ContextBuilder

### 校正原因

当前`utils/file_parser.py`只读取TXT/Markdown、PDF文本层和DOCX普通段落。真实PRD中的业务表格、
扫描内容、流程分支、状态图和UI交互经常位于图片中。如果上游输入已经残缺，ContextBuilder只能更高效地传递残缺信息，
RAG、Generator和Reviewer也无法发现自己从未接收到的业务事实。

因此图文混合PRD理解被提升为秋招版本P0，并安排在ContextBuilder之前。

### 调整后的2.15

```text
2.15.1 统一DocumentContent
→ 2.15.2 PDF/DOCX结构化解析
→ 2.15.3 OCR与扫描文档
→ 2.15.4 流程图和UI图理解
→ 2.15.5 关键问题筛选与限流
→ 2.15.6 ContextBuilder与节点预算
→ 2.15.7 分层耗时、Token、错误和降级
```

2.16继续负责离线评测，但增加正文、表格、OCR、流程关系、UI操作、关键问题数量和视觉调用成本等指标。
2.17 FastAPI、后台任务、SSE和Vue顺序不变。

### Human-in-the-loop边界

人工确认不等于逐图审核：

- 高置信度且有正文印证的内容自动使用；
- 中置信度内容作为风险继续，不阻塞任务；
- 低置信度的非核心图片只记录解析警告；
- 只有核心规则、关键数字、流程分支或图文冲突才允许暂停；
- 重复问题合并，一轮默认最多3个，并支持“暂不确定并继续”。

该策略既保留安全边界，也避免用户替AI完成需求分析。

### 当前与规划边界

本次只修改文档，没有增加OCR、视觉模型、表格解析或页面交互。README和PRD继续明确当前版本只能处理可提取文字，
不得把规划中的图文理解写成已实现能力。直接下一步仍为2.14.5知识资产可靠性收尾。

### 验证结果

```text
python -m unittest discover -s tests -v
260 tests，OK，6 skipped

python -m pytest -q
337 passed，8 skipped

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

本次没有修改生产代码、测试代码、页面或依赖配置，也没有调用真实外部服务。

## 阶段 2.14.5：索引失败重试与补偿审计

### 本阶段目标

阶段2.14.3已经使用稳定Chunk ID和upsert建立了安全重放基础，但`index_failed`资产没有正式重试入口，
重复请求也缺少持久化审计。阶段2.14.5补齐失败恢复和停用清理边界，不增加页面或后台任务。

### 实际实现

- 增加`KnowledgeAssetIndexRequest`及`running/succeeded/failed`状态
- 新增MySQL表`knowledge_asset_index_requests`，保存请求ID、资产、结果、Chunk数量、错误摘要和起止时间
- Repository提供`begin_index_retry()`、`finish_index_request()`和`list_index_requests()`
- MySQL在同一事务内锁定资产、创建重试审计并把`index_failed`切回`pending_index`
- Application Service提供显式`retry_failed_asset(asset_id, request_id)`用例
- 已成功请求重放时直接返回已有结果，不再次调用Embedding或Milvus
- 已失败请求重放时明确拒绝并要求新`request_id`，避免同一批动作重复消费
- 中断后若资产已经是`indexed`或`index_failed`，重放会修复仍为`running`的请求审计
- 资产停用时先将MySQL状态改为`retired`，再按资产ID和版本删除Milvus V2向量
- Milvus清理失败不会恢复资产为可检索状态，可再次调用停用用例补偿清理

### 为什么不做跨库事务

MySQL和Milvus无法共享同一个本地ACID事务。项目采用“权威状态 + 幂等副作用 + 可审计补偿”：

```text
MySQL状态决定资产是否可信
+ 稳定Chunk ID保证Milvus upsert可重放
+ request_id保证同一用户动作不重复执行
+ 失败审计说明哪一步需要补偿
```

检索侧仍会回查MySQL状态，所以即使Milvus暂时残留已停用向量，也不会把它返回为可信资产。

### 测试证据

自动化测试覆盖：

- 成功重试和同一请求重放不重复调用外部服务
- 失败请求审计、新请求恢复和运行中请求保护
- Repository重试状态变化、请求归属冲突和重复结束保护
- MySQL同事务更新资产与创建请求、行锁读取和请求结果写入
- Milvus按`asset_id + asset_version`定向删除及集合不存在时幂等返回
- MySQL先`retired`、Milvus后清理，以及清理失败后的再次补偿
- 可选真实MySQL重试审计集成测试，默认不访问外部数据库

完整验证：

```text
python -m pytest -q
353 passed，9 skipped，共收集362项

python -m unittest discover -s tests -v
260 tests，OK，6 skipped

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

### 范围边界

本阶段没有修改Streamlit、AgentState、Orchestrator、Prompt、节点顺序和当前KnowledgeRetriever，
也没有实现自动重试Worker、FastAPI、SSE或LLM重排。页面仍未提供知识资产管理按钮。
进程若在创建`running`请求后、真正开始索引前崩溃，仍需未来租约或运维恢复策略；Milvus全量孤儿
扫描清理器也未实现，本阶段只提供已知资产版本的定向停用清理。

### 下一步

阶段2.15.1建立统一`DocumentContent`，先完整表达段落、表格、图片、页码、来源和解析警告，
再逐步实现PDF/DOCX结构化解析、OCR和受控多模态理解。

## 阶段 2.15.1：统一DocumentContent文档输入契约

### 本阶段目标

原有`utils/file_parser.py`把所有文档直接压平成字符串。进入Agent前，段落顺序、页码、表格、图片和
解析失败信息已经丢失。阶段2.15.1先建立统一、不可变、可追踪来源的文档模型，同时保留现有纯文本
入口，避免在一个阶段同时改动页面、AgentState和节点Prompt。

### 实际实现

- 新增独立`documents/`包和`DocumentContent`
- 新增`DocumentTextElement`，区分标题、段落和列表项
- 新增`DocumentTableElement/DocumentTable`，用不可变等宽二维元组表达表格
- 新增`DocumentImageElement/DocumentImage`，表达图片ID、MIME、内容引用、尺寸和说明
- 新增`DocumentSourceRef`，保存稳定来源ID、文档ID、文件名、元素顺序和页码
- 新增`DocumentParsingWarning`及空文档、空白页、表格未提取、图片未提取四类警告
- `DocumentService.parse()`统一解析TXT、Markdown、PDF文本层和DOCX普通段落
- `DocumentService.extract_text()`保留当前Application Service使用的字符串兼容视图
- 旧`utils.extract_text_from_file()`降为兼容包装，不再维护另一套解析实现

### 为什么同时保留extracted_text和elements

当前AgentState、任务快照和Prompt都依赖字符串。如果本阶段直接把它们全部换成`DocumentContent`，
会把输入模型、状态持久化和节点上下文三个问题混在一个提交中。因此先采用双视图：

```text
DocumentContent.elements/warnings
→ 新结构化能力

DocumentContent.to_plain_text()
→ 当前页面和Agent兼容能力
```

后续迁移必须显式选择结构化字段，不能因为保留纯文本就声称已经理解图片或表格。

### 当前解析语义

- TXT：按空行拆分普通段落，兼容文本保持原内容
- Markdown：识别标题、列表项和普通段落，保留原始顺序
- PDF：按页读取已有文本层，元素保留页码；空页生成警告
- DOCX：读取普通段落并根据样式识别标题/列表；表格和内嵌图片只检测并告警

表格、图片模型本阶段已经可表达真实结果，但解析器尚未填充这些元素；这部分属于2.15.2。

### 测试证据

- 文本、表格和图片元素能在同一DocumentContent中保持顺序和来源
- 模型及嵌套表格使用不可变结构，拒绝跨文档、乱序和非法页码
- Markdown标题/列表识别和稳定文档/来源ID
- PDF页码保留和空白页警告
- DOCX标题/段落类型以及表格/图片未提取警告
- 不支持格式、非法UTF-8和空文档错误边界
- 当前Streamlit文件上传创建任务回归不变

完整验证：

```text
python -m pytest -q
363 passed，9 skipped，共收集372项

python -m unittest discover -s tests -v
266 tests，OK，6 skipped

python -m compileall -q agent application documents knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

默认测试使用内存文件和Fake PDF/DOCX模块，没有调用真实外部服务。

### 范围边界与下一步

本阶段没有修改Streamlit、AgentState、Orchestrator、Prompt和任务快照，也没有接入OCR、视觉模型或
MySQL文档存储。阶段2.15.2将在该模型上实现PDF/DOCX原生结构提取，仍不接OCR和多模态理解。

## 阶段 2.15.2：PDF与DOCX结构化解析

### 阶段目标

让阶段2.15.1定义的表格和图片模型承载真实解析结果，同时保持当前Agent纯文本入口和页面行为不变。

### 修改内容

- 引入`pdfplumber 0.11.7`提取PDF页文本和可识别表格，并保持`pypdf`负责内嵌图片读取
- DOCX改为使用`iter_inner_content()`保持标题、段落、列表和表格的正文块顺序
- 新增`DocumentAttachment`，保存图片MIME、二进制内容和SHA-256，图片元素使用稳定引用关联附件
- 新增`DocumentParseStats`，记录页、文本、表格、图片、警告和跳过数量
- 为表格失败、图片失败、超限图片及PDF矢量图增加明确警告
- 图片解析限制为单图5MB、最多20个图片元素、附件总量25MB
- DOCX表格文字进入`to_plain_text()`兼容视图，现有Agent无需修改即可读取

### 核心设计

```text
DocumentImageElement
→ content_ref
→ DocumentAttachment
   ├─ MIME
   ├─ bytes
   └─ SHA-256
```

附件与元素分离，既避免在每个元素里重复保存大段二进制，也给后续OCR和视觉模型提供真实输入。
PDF矢量图不能可靠拆成有业务意义的单张图片，因此只记录整页渲染提示，不把零散线条误报为流程图。

### 验证

- 真实内存DOCX验证标题、表格和PNG图片的顺序与附件关联
- Fake PDF边界验证页码、表格、位图、矢量图警告、表格失败和超限图片
- `python -m pytest -q`：367 passed，9 skipped
- `python -m unittest discover -s tests -v`：269 tests，OK，6 skipped
- `compileall`、`git diff --check`和`pip check`通过
- Streamlit、Agent状态机、Application Service和Repository均未修改

### 下一步

阶段2.15.3只增加OCR与扫描文档处理，不在同一阶段实现流程图和UI图语义理解。

## 阶段 2.15.3：OCR与扫描文档

### 阶段目标

让扫描PDF和文档图片能够产生带置信度、页码和图片来源的文字结果，并保证低置信度结果不会直接成为
需求事实，单张图片失败也不会拖垮整份PRD解析。

### 修改内容

- 新增`OcrEngine`协议、`OcrTextLine`结果和OCR异常边界
- 新增`TesseractOcrEngine`，通过标准TSV读取文字行与置信度
- PDF无文本层页面以150 DPI渲染后执行OCR
- PDF/DOCX内嵌图片逐张执行OCR
- 新增`DocumentOcrElement`和`DocumentOcrDisposition`
- 置信度阈值暂定0.80，高置信度进入兼容文本，低置信度只保留为待复核候选
- Tesseract不可用、单图失败和低置信度结果均记录结构化警告
- 统计OCR元素、低置信度候选和失败数量
- `.env.example`补充本地OCR命令、语言和超时配置

### 核心设计

```text
DocumentService
→ OcrEngine（协议）
   └─ TesseractOcrEngine（当前适配器）
→ DocumentOcrElement
   ├─ ACCEPTED
   └─ REVIEW_REQUIRED
```

DocumentService只依赖协议，因此以后替换云OCR或其他本地引擎时，不需要修改文档解析规则。低置信度结果
仍保留原文和来源，但不进入当前Agent使用的`extracted_text`，从输入边界防止模糊文字被当成确定事实。

### 测试证据

- 扫描PDF渲染后产生OCR元素、页码、图片ID和置信度
- 高低置信度确定性分流
- 第一张图片OCR失败后第二张仍正常识别
- Tesseract TSV分行、置信度归一化、运行时缺失和失败返回
- `python -m pytest -q`：373 passed，9 skipped
- `python -m unittest discover -s tests -v`：271 tests，OK，6 skipped

### 未完成证据

当前已完成真实Tesseract合成中文图片冒烟，但尚无真实扫描PRD数据集的准确率、召回率和耗时分布。
该限制必须保留在README和简历表述中，不能用单份合成样本替代评测结论。

### 真实OCR验收补充

- 运行时：Tesseract 5.5.3，语言包`chi_sim+eng`
- 两行合成中文图片识别置信度约0.95、0.92，调用耗时约0.30秒
- DOCX完整链路识别“商户单日提现上限为二十万元”，置信度约0.95
- 图片数1、OCR元素1、低置信度0、失败0、警告0
- 新增`RUN_OCR_INTEGRATION_TESTS=1`显式开启的真实集成测试，结果`1 passed`
- 默认pytest结果：373 passed，10 skipped；unittest结果：272 tests，OK，7 skipped

### 下一步

进入2.15.4图片分类与有界多模态理解；真实PRD批量评测留在2.16。

## 阶段 2.15.4：流程图与UI图有界理解

### 本阶段目标

在不修改Agent状态机和页面的前提下，为已提取的图片建立可替换、有限额、可降级的多模态理解边界，
避免把每张图片都发送给模型，也避免把不确定视觉结论直接当成需求事实。

### 修改内容

1. 增加`VisualUnderstandingEngine`协议和OpenAI兼容视觉适配器；
2. 增加`DocumentVisualKind`、节点、关系、UI元素、结构化分析和文档元素模型；
3. 使用相邻正文、图片名和OCR信号确定性选择流程、状态、时序和UI候选；
4. 小图、装饰图和无视觉流程信号的纯文字图片不调用视觉模型；
5. 每份文档最多调用5张，图片最长边限制1600px，默认输出上限1500 Token；
6. 模型结果严格校验字段集合、类型、数量上限和节点关系引用；
7. 高置信度结果带图片来源进入兼容文本，低置信度只保留结构化候选；
8. 未配置、单图失败、低置信度和调用超限分别记录结构化警告；
9. PDF文本页中的矢量流程候选支持整页渲染后分析；
10. `.env.example`与README增加独立视觉端点配置和数据边界说明。

### 设计原因

OCR只能识别文字，无法表达箭头方向、条件分支、页面操作和状态变化。但直接把整份PRD的所有图片发给
视觉模型会增加耗时、费用和数据泄露面。因此先用本地确定性证据筛选候选，再对有限图片调用模型，并让
结构化结果保留来源、置信度和不确定性。视觉模型没有权力直接修改Agent状态。

### 验证结果

```text
python -m pytest -q
383 passed，10 skipped
python -m unittest discover -s tests -v
277 tests，OK，7 skipped
```

新增测试验证结构化类型、来源关联、纯文字图片跳过、单图失败隔离、5张调用上限、严格JSON和非法关系
拒绝。所有测试使用Fake或Mock，没有调用真实视觉端点；真实图文效果评测仍属于2.16。

### Git提交

`3961861 阶段2.15.6：增加节点上下文构建与输入预算`

### 下一步

阶段2.15.5实现关键问题筛选和Human-in-the-loop限流，减少用户被低价值问题频繁打断。

## 阶段 2.15.5：关键问题筛选与Human-in-the-loop限流

### 本阶段目标

解决“LLM只要返回问题就暂停任务”的过度询问问题，让代码而不是模型最终决定哪些问题有权打断用户。

### 修改内容

1. 将待确认候选升级为包含`question`、`category`、`blocking_reason`和`evidence`的结构化对象；
2. 类别限定为核心规则、关键数字、关键分支、需求冲突、实现细节和低影响；
3. 新增`ClarificationQuestionPolicy`，最多选择前三个阻塞候选；
4. 实现细节、低影响和超额候选转为`InferredRisk`，不暂停任务；
5. 使用本地关键词覆盖明显误分类的数据库、缓存、技术栈和纯视觉样式问题；
6. 对问题做空白、标点和大小写归一化去重；
7. `deferred_questions`使用相同归一化规则，防止暂不确定的问题变换标点后重新出现；
8. 完成事件记录原候选数、阻塞数和非阻塞转风险数；
9. State、页面、快照和Orchestrator仍使用原来的问题字符串；
10. 更新仓库测试约定：新增测试使用pytest，开发中运行目标模块，阶段结束运行一次全量pytest。

### 核心设计

```text
LLM提出候选并给出依据
→ Python校验候选结构
→ Python按类别、关键词、去重、deferred和数量上限筛选
→ 最多3个问题暂停 / 其余作为风险继续
```

这不是让Python理解全部业务语义，而是建立最低安全边界。LLM仍负责语义分析，代码负责类别白名单、数量、
明显技术问题、重复消费和状态暂停权限。

### 验证结果

```text
python -m pytest tests/unit/agent/test_requirement_analyzer.py \
  tests/unit/agent/test_clarification_policy.py \
  tests/unit/agent/test_orchestrator.py \
  tests/unit/application/test_application_service.py -q
55 passed

python -m pytest -q
390 passed，10 skipped
```

所有测试使用Fake LLM，没有真实网络请求。

### Git提交

待创建本地提交。

### 下一步

阶段2.15.6实现ContextBuilder和节点输入预算，开始减少长PRD、完整State和RAG上下文造成的Token与时延。

## 阶段 2.15.6：ContextBuilder与节点输入预算

### 本阶段目标

把“每个节点需要什么上下文”从节点内部重复拼装提升为统一、可测试的代码边界，并在不增加LLM调用、
不改变Agent状态机的前提下限制长PRD和检索上下文。

### 修改内容

1. 新增`ContextBuilder`、`ContextNode`、`BuiltContext`、`ContextMetrics`和`ContextBuildError`；
2. 为需求分析、知识检索、测试点生成、质量评审和测试点修正定义不同字段白名单；
3. 限制原始需求、检索需求、本地缺陷知识和RAG总上下文字符数；
4. 裁剪时优先保留数值、规则、状态、金额、权限、幂等、来源、OCR和视觉信号；
5. Reviewer/Reviser的测试点与反馈不静默裁剪，受保护上下文超预算时明确抛错；
6. 按64K上下文基线预留输出Token和4096安全余量，再应用节点输入策略上限；
7. 节点完成事件增加`context_metrics`，记录裁剪前后字符数、估算Token、预算和裁剪区段；
8. 移除Generator、Reviewer和Reviser中重复的需求分析payload构造；
9. 当前RAG检索继续保持`top_k=2`，没有增加外部服务请求；
10. 新增pytest验证字段白名单、关键内容保留、长度限制、预算拒绝与深拷贝隔离。

### 设计说明

第一版没有增加“LLM自动摘要”，因为当前没有离线证据能证明摘要不会丢失金额、阈值、状态流转和来源引用。
可安全裁剪的原始文本采用本地确定性规则；不可安全裁剪的结构化测试点选择明确失败。`estimated_input_tokens`
只是统一的本地估算口径，不等于模型API usage，真实Token记录留到2.15.7。

### 验证结果

```text
定向节点与ContextBuilder测试：63 passed
python -m pytest -q：396 passed，10 skipped
```

全量测试未调用真实LLM、Embedding、Milvus、MySQL或OCR；显式集成测试保持跳过。

### Git提交

待创建本地提交。

### 下一步

阶段2.15.7增加分层耗时、真实/估算Token标记、重试次数和错误分类，不改成后台任务或SSE。

## 阶段 2.15.7：分层耗时、Token与错误分类

### 本阶段目标

在现有节点总耗时基础上回答“时间具体花在哪一层”，并建立可以随任务快照恢复的性能证据，
不修改同步执行架构、Agent状态机和页面。

### 修改内容

1. 新增任务级`telemetry_scope`、`ServiceCallMetric`、`TokenUsage`和统一错误类别；
2. Application Service在节点执行时关联`task_id`和Orchestrator动作；
3. 指标附加到已有任务创建、节点完成或任务失败事件，不增加AgentState字段和快照版本；
4. 文档解析、OCR、视觉模型、ContextBuilder、LLM、结构化JSON校验、RAG、Embedding和Milvus接入统一指标；
5. LLM和视觉API有usage时记录provider Token，没有时记录estimated Token；
6. 记录模型、输入输出字符数、Prompt指纹、重试次数、耗时、错误类型和错误类别；
7. Prompt指纹使用内容哈希截断值，不保存Prompt、API Key、服务地址、响应原文和图片二进制；
8. `TaskView.service_metrics`返回只读明细，`performance_summary`按依赖、Token来源、重试和错误汇总；
9. 服务指标跟随AgentEvent完成schema v1 JSON快照往返，可由现有MySQL TaskRepository持久化；
10. 不增加页面面板、后台任务、SSE、轮询或独立时序数据库。

### 错误分类

当前类别包括超时、传输、输出截断、结构校验、输入预算、文档解析、OCR、视觉、Embedding、Milvus和未知错误。
分类只用于诊断，不改变原有异常传播和降级决策。

### 验证结果

```text
定向Telemetry与受影响模块：102 passed
python -m pytest -q：405 passed，10 skipped
```

全量测试没有调用真实LLM、Embedding、Milvus、MySQL或OCR。新增测试验证provider/estimated Token区分、
敏感信息隔离、JSON重试、错误分类、事件附加、文档创建指标、只读汇总和快照往返。

### 当前限制

1. 当前没有多份真实PRD的性能分布，不能声称已经降低多少耗时或Token；
2. 视觉API无usage时，文本估算不包含图片Token并会明确标记；
3. 旧MilvusRAGManager只能记录组合RAG耗时，V2链路才可拆分Embedding和Milvus；
4. 指标保存在任务事件快照中，不是生产监控平台。

### Git提交

待创建本地提交。

### 下一步

进入2.16.1，先定义脱敏评测数据和人工标注契约，不立即运行昂贵的真实模型批量实验。

## 阶段 2.16.1：脱敏评测数据契约与种子样例

### 本阶段目标

先固定“人工金标准长什么样”，避免在格式不稳定时一次编写大量样例。本轮不调用真实模型、不实现评分Runner，
也不修改Agent、页面和在线服务。

### 修改内容

1. 新增`EvaluationDataset`、`EvaluationCase`和`GoldAnnotations`不可变数据契约；
2. schema v1严格校验版本、字段、列表、问题类别和重复case_id；
3. 金标准包含事实、规则、风险、关键问题、必要场景和禁止断言；
4. 每条事实、规则、风险和场景必须包含人工可核对的`evidence`；
5. 新增登录权限、订单库存、文件上传3份完全虚构种子样例；
6. 增加人工标注指南、双人复核流程和测试点可执行性0～2分规则；
7. 新增pytest契约测试，不调用LLM、Embedding、Milvus、MySQL或OCR。

### 代码量控制

本轮生产代码约250行，只建立一个加载和校验边界。3份样例用于先验证格式；达到正式验收仍需扩充至至少10份并完成双人复核，
当前不能作为模型效果证据。

### 验证结果

```text
python -m pytest tests/unit/evaluation/test_dataset.py -q
13 passed

python -m pytest -q
418 passed，10 skipped
```

### 下一步

继续扩充并复核2.16.1数据集；契约稳定并达到至少10份后，再进入2.16.2图文解析指标。

### 第二小步：扩充到10份草案

在不增加生产模块的前提下，补充支付、优惠券、退款、搜索、消息通知、重复提交和角色权限7个业务域。
pytest新增数量、领域和输入特征覆盖断言。当前10份均为Codex辅助生成的虚构草案，数量达到最低要求，
但没有经过两位人工标注者独立复核，也没有真实图片附件，因此仍不能用于生成效果结论。数据集显式保存
`review_status=draft`，非法状态会被契约拒绝，避免未来Runner误用未复核草案。

下一步先完成人工复核和图文附件补齐，再进入2.16.2；不因为数据数量达到10份就跳过质量验收。

```text
python -m pytest tests/unit/evaluation/test_dataset.py -q
15 passed

python -m pytest -q
420 passed，10 skipped
```

### 第三小步：用户复核与金标准精简

用户逐项修订10份需求的事实、规则、风险、关键问题、必要场景和禁止断言，并完成最终接受。facts只保留确定事实，
未定义规则只保留在clarification_questions；necessary_scenarios精简为每份4～7个最低必要场景。
数据集更新为`review_status=reviewed`。该状态只代表用户单人复核完成，项目没有双人独立标注一致性证据。

## 阶段 2.16.2：图文解析评测样本底座

### 第一小步目标

用户暂时没有可安全使用的真实PDF用例，因此先用完全虚构且可重复生成的样本建立评测输入。本轮不实现评分Runner，
不调用真实OCR、视觉模型、LLM、Embedding、Milvus或MySQL，也不修改在线Agent流程。

### 修改内容

1. 增加原生文字PDF、DOCX权限表、扫描PDF、订单流程图和上传UI图5份样本；
2. 增加schema v1金标准，分别描述预期文字、表格、流程节点/关系和UI元素；
3. 增加可重复构建脚本，中文字体路径可通过`EVAL_CJK_FONT`覆盖；
4. 增加pytest，确认原生PDF可抽取文字、扫描PDF无文本层、DOCX表格保持结构、PNG格式和尺寸正确；
5. PDF和PNG已完成渲染目检；当前环境缺少Word/LibreOffice，DOCX仅完成领域结构读取验证；
6. `reportlab`只加入开发依赖，用于重建评测PDF，不进入线上运行依赖。

### 范围与证据边界

本轮证明的是评测样本可读、可重复、具有确定金标准，不证明现有解析器已经达到准确率要求。合成样本数量少、版式简单，
后续指标必须逐样本报告，不能把结果外推到所有真实PRD。

### 验证结果

```text
python -m pytest tests/unit/evaluation/test_document_fixtures.py -q
5 passed

python -m pytest -q
425 passed，10 skipped
```

全量回归没有调用真实外部服务。

### 下一步

在保持小代码量的前提下，为现有文档解析输出增加最小评测适配和正文、表格、OCR确定性指标；暂不建设通用评测平台。

### 第二小步：正文、表格和OCR确定性评分

新增约190行的`evaluation.document_parsing`，直接复用现有`DocumentService`和`DocumentContent`，没有再建立Parser接口或评测平台。
Runner只处理`native_text`、`table_structure`和`ocr_text`三类样本：

1. 正文按金标准行计算召回率，并输出缺失行；
2. 原生文字与OCR文字使用去空白后的编辑距离计算字符准确率；
3. DOCX表格按行列位置比较单元格；
4. OCR只读取`DocumentOcrElement.text`，不把来源标签计入字符准确率；
5. 流程图和UI图明确跳过，`_NoVisualEngine`确保本轮不会误调用视觉API；
6. 输出逐样本JSON，不计算会掩盖错误类型的综合总分。

本机使用已配置Tesseract实际运行后，3份简单合成样本的对应指标均为1.0。该结果只证明当前样本链路可工作，
不能外推为真实PRD准确率。扫描PDF保留`empty_page`警告，这是“没有原生文本层并进入OCR”的预期事实。

```text
python -m pytest tests/unit/evaluation/test_document_parsing.py -q
4 passed

python -m pytest -q
429 passed，10 skipped
```

下一步只补流程节点、分支关系和UI元素的确定性评分；真实视觉模型调用继续受费用和显式授权约束。

### 第三小步：流程与UI确定性评分

本轮在已有Runner中增加约110行视觉评分代码，没有增加视觉模型适配器或通用评测框架：

1. 流程节点使用标签召回率；
2. 分支关系同时比较起点标签、终点标签和条件；
3. UI元素同时比较类型和名称；
4. 关系和UI指标会同时惩罚缺失项与额外编造项；
5. Runner只接收已生成的`DocumentVisualAnalysis`，不负责调用外部模型；
6. 无视觉结果时，JSON报告通过`skipped_fixture_ids`明确记录未评测样本。

pytest使用Fake结构化视觉结果验证完整流程、漏掉失败分支和额外编造“删除文件”按钮，不调用真实端点。
因此本阶段证明评分逻辑可工作，但没有流程图或UI图的真实识别准确率。

```text
python -m pytest tests/unit/evaluation/test_visual_parsing.py tests/unit/evaluation/test_document_parsing.py -q
8 passed

python -m pytest -q
433 passed，10 skipped
```

阶段2.16.2的确定性评分代码到此收尾。真实视觉运行作为外部集成证据保留，下一阶段进入2.16.3 RAG专项评测。

## 阶段 2.16.3：RAG专项评测

### 第一小步：查询金标准与资产级指标

本轮先建立约100行的纯指标模块，不连接真实Embedding、Milvus或MySQL：

1. 新增5份完全虚构查询；
2. 每份查询标注相关KnowledgeAsset ID和明确禁止召回的资产ID；
3. 实现Recall@K、Precision@K、MRR和禁止资产命中率；
4. 对重复asset_id先按排序去重，保持资产级检索口径；
5. 输出逐case结果和宏平均，不制造综合加权总分；
6. pytest验证相关资产排名、错误召回、缺失召回和Fake Runner汇总。

这里的Fake全命中结果只验证公式和数据流，不能写成真实RAG效果。下一小步再复用现有
`KnowledgeAssetRetrievalService`边界；真实Milvus实验仍需要显式授权。

```text
python -m pytest tests/unit/evaluation/test_rag_evaluation.py -q
5 passed

python -m pytest -q
438 passed，10 skipped
```

### 第二小步：接入真实Retrieval Service边界

本轮没有连接真实Embedding、Milvus或MySQL，而是让离线评测实际经过生产代码中的
`KnowledgeAssetRetrievalService`：

1. Runner将服务返回的完整候选资产转换为排序后的`asset_id`；
2. Fake Embedding与Fake VectorSearch只替代外部基础设施；
3. InMemory Repository保存5份合成`indexed`资产；
4. 检索服务仍执行阈值过滤、资产聚合、状态/版本/哈希校验和权威回查；
5. 报告保存为`rag_fake_service_v1.json`并标记`fake_dependencies_only`；
6. 测试校验报告文件与Runner输出一致，避免手工结果漂移。

该报告证明评测Runner已经接上现有查询边界，不能证明真实向量相似度质量。真实Milvus实验继续保持显式授权和独立集成入口。

```text
python -m pytest -q tests/unit/evaluation/test_rag_evaluation.py tests/unit/evaluation/test_rag_retrieval_service_evaluation.py
6 passed

python -m pytest -q
439 passed，10 skipped
```

### 第三小步：合成资产种子与真实评测入口

本轮增加5份与查询金标准一一对应的合成KnowledgeAsset种子，并新增显式真实运行入口：

1. 种子数据包含完整需求、结构化事实/规则/风险、测试点和Reviewer结果；
2. Loader构造标准`KnowledgeAsset`并计算真实内容哈希；
3. Runner只在`RUN_RAG_INTEGRATION_EVALUATION=1`时运行；
4. Runner强制使用MySQL资产Repository，先保存资产，再通过现有Indexing Service写入Milvus；
5. 相同资产重复运行会校验内容哈希，避免悄悄覆盖不同内容；
6. 检索报告标记`real_embedding_milvus_mysql`并记录模型和集合名，不记录密码或Token。

真实运行首次暴露PyMilvus返回对象兼容问题：真实`Hit`通过`.id`和`.distance`属性提供主键与分数，
Fake测试使用的是字典键。适配器现同时兼容两种形式，并增加属性式Hit回归测试。

修复后真实链路成功写入MySQL和Milvus并完成5份查询：Mean Recall@3=1.0、Mean Precision@3=0.3333、
Mean MRR=1.0、Mean forbidden hit rate=0.1。权限查询虽然第一名正确，但同时召回了明确禁止的订单库存资产，
说明只看召回率会掩盖知识污染风险。完整结果保存于`evaluation/results/rag_real_v1.json`。

默认pytest仅验证种子、适配器和真实入口关闭保护，不访问外部服务。

```text
python -m pytest -q
442 passed，10 skipped
```

### 第四小步：Top-K与阈值对比

本轮固定相同5份MySQL权威资产和查询，比较Top-K为1/2/3、最小相似度为0.65/0.70/0.75的9组组合。
首次运行因每个查询都重新连接远程MySQL而在约40秒后超时，因此调整为：

1. 启动时一次批量读取MySQL权威资产；
2. 实验期间使用同一份只读内存快照，保证各组合的数据一致；
3. 每条查询只调用一次真实Embedding并复用向量；
4. 每个组合仍独立执行真实Milvus搜索、阈值过滤、排序和指标计算。

优化后9组实验约8.5秒完成。阈值0.65且Top-K≥2时禁止命中率为0.1；阈值提高到0.70后，
5份样本Recall仍为1.0且禁止命中率降为0。由于每个查询仅有1个相关资产且数据量很小，0.70只记录为候选，
没有自动修改线上默认配置。完整报告位于`evaluation/results/rag_parameter_sweep_v1.json`。

## 阶段 2.16.4：Reviewer/Reviser专项评测

### 第一小步：缺陷注入数据与确定性评分

本轮新增12份合成Reviewer样本，没有调用真实LLM：

1. 六类缺陷固定为需求遗漏、边界缺失、重复测试点、无依据断言、模糊预期和来源缺失；
2. 8份单缺陷样本便于定位每类能力；
3. 2份多缺陷样本验证同一测试点集合中的组合问题；
4. 2份正确样本用于统计误报，防止“报告问题越多分越高”；
5. 共12个缺陷，每个缺陷使用`defect_type + target`作为稳定评分键并保留人工证据；
6. 评分器计算TP、FP、FN、Precision、Recall和正确样本误报率。

第一小步只固定考卷、答案和评分方式，不表示当前Reviewer已经达到任何准确率。下一小步再把现有
`TestPointReviewResult`结构化字段适配成这些稳定缺陷类型。

### 第二小步：Reviewer结构化输出适配

本轮新增从现有`TestPointReviewResult`到六类评测缺陷的确定性适配，没有修改Reviewer节点和Prompt：

1. `requirement_coverage`中的partial/missing映射为需求遗漏；
2. `duplicate_groups`映射为重复测试点；
3. `hallucination_issues`映射为无依据断言；
4. `missing_scenarios`只有包含边界、上限、下限、最大、最小等明确词时才映射为边界缺失；
5. `revision_suggestions`必须同时提到具体测试点标题和来源/预期关键词，才映射为来源缺失或预期模糊；
6. 无法确定的自由文本保持未分类，避免通过宽泛关键词制造假阳性。

pytest使用Fake结构化评审一次覆盖六类映射，并验证普通优化建议不会误分类；未调用真实LLM。

```text
python -m pytest -q
450 passed，10 skipped
```

### 第三小步：Reviewer评测Runner

本轮把12份fixture转换为当前Reviewer实际使用的`TestAnalysisState`，并新增只依赖
`review(state)`协议的评测Runner。Runner统一执行结构化输出适配和TP/FP/FN评分，既可注入Fake，
后续也可复用现有`TestPointReviewer`，没有修改Reviewer节点、Prompt或状态机。

Fake接线报告明确标记`fake_gold_predictions_only`。报告命中11/12个缺陷：上传6个文件虽然是数值
超限场景，但文本未包含当前适配器要求的边界关键词，因此被保守规则忽略。这里保留漏检证据，
没有为了满分放宽映射并引入潜在误报。

```text
python -m pytest -q tests/unit/evaluation/test_reviewer_runner.py tests/unit/evaluation/test_reviewer_adapter.py tests/unit/evaluation/test_reviewer_evaluation.py
8 passed

python -m pytest -q
452 passed，10 skipped
```

### 第四小步：真实Reviewer基线

新增`RUN_REVIEWER_INTEGRATION_EVALUATION=1`保护的真实入口，默认pytest不访问DeepSeek。首次运行在约175秒后
因单份样本连续两次输出错误的`hallucination_issues`类型而中止。评测层随后增加“记录单样本失败并继续”能力，
没有放宽生产Reviewer校验，也没有修改Prompt。

第二次使用`deepseek-v4-pro`完成12份合成样本，命中4个、误报7个、漏检8个，Precision=0.3636、
Recall=0.3333；3份样本在受控重试后仍不符合结构化契约。2份正确样本没有产生已分类误报，但其中
`review-clean-001`本身执行失败，因此不能把误报率0解释为Reviewer完全可靠。完整报告保存于
`evaluation/results/reviewer_real_v1.json`，本次串行运行约439秒。

这组结果同时受模型判断、JSON契约稳定性和保守适配器影响，只作为当前12份样本的基线，不写成泛化结论。

```text
python -m pytest -q
454 passed，10 skipped
```

### 第五小步：Reviser修复样本与副作用指标

本轮新增6份最小修复样本，对应需求遗漏、边界缺失、重复测试点、无依据断言、模糊预期和来源缺失。
每份样本除待修目标外，还保留至少一个正确测试点作为保护对象。

评测Runner使用现有`TestAnalysisState`和可注入的`revise(state)`边界，分别统计：

- `target_fix_rate`：待修目标是否达到金标准；
- `preservation_rate`：不相关的正确测试点是否保持不变；
- `unexpected_titles`：是否产生金标准外的新测试点。

Fake报告两项均为1.0，只证明数据流和指标可工作。错误Fake测试会故意保留缺陷并修改保护测试点，验证两类问题都会被指标发现。

```text
python -m pytest -q tests/unit/evaluation/test_reviser_evaluation.py
4 passed

python -m pytest -q
458 passed，10 skipped
```

### 第六小步：真实Reviser严格基线

新增`RUN_REVISER_INTEGRATION_EVALUATION=1`保护的真实入口。评测复用生产`TestPointReviser`，单样本失败会记录错误并继续，
没有放宽增量操作、来源非空和原子合并校验。

`deepseek-v4-pro`运行6份样本约72秒，严格目标修复率为0.1667，正确测试点保留率为1.0，1份来源缺失样本因
返回空来源而失败。3份样本产生了不同于金标准的新标题。

当前目标修复率要求标题、场景、预期和来源精确一致，因此会把语义接近但表述不同的结果判为未命中。它是可复现的
保守结构基线，不能直接解释为模型业务修复能力只有16.67%；当前报告也没有保存完整模型输出，不能补做人工作弊式改分。

```text
python -m pytest -q
460 passed，10 skipped
```

## 阶段 2.16.5：三方案消融实验

### 第一小步：统一实验契约与Fake矩阵

本轮固定三组实验为基础LLM、LLM+RAG、LLM+RAG+Reviewer/Reviser。Runner强制三组使用相同10份
`seed-v1`需求，统一接收事实、规则、风险、待确认问题、必要场景和断言，并汇总耗时、输入/输出Token与修正次数。

第一版评分采用去除空白、统一大小写后的严格文本匹配，优点是可复现，限制是同义表达不会自动算对。Fake测试验证
10×3调用矩阵、全量汇总和单组漏事实场景，没有调用真实LLM或RAG。为避免提交大量全为Fake满分的重复JSON，
本小步以自动化测试作为接线证据，不额外保存冗余结果文件。

```text
python -m pytest -q tests/unit/evaluation/test_experiments.py
3 passed

python -m pytest -q
463 passed，10 skipped
```

### 第二小步：TaskView生产结果适配

本轮新增`TaskViewExperimentVariant`，把返回只读`TaskView`的应用用例包装为统一实验组。适配器读取需求事实、
业务规则、推导风险、待确认问题、测试点标题/场景/预期，并复用`performance_summary`中的节点耗时和Token。

Token优先选择模型供应商实际返回值；没有供应商值时才使用现有估算值。适配层不访问Repository、不读取LLM客户端，
也不获得可修改的`AgentState`。Fake `TaskView`测试验证字段和指标映射，不运行真实模型。

```text
python -m pytest -q tests/unit/evaluation/test_experiments.py
5 passed

python -m pytest -q
465 passed，10 skipped
```

### 第三小步：三组执行策略与暂停处理

本轮固定三组只在`use_rag`和`use_quality_loop`两个开关上存在差异，原始需求、数据集和用户补充策略保持一致。
统一应用驱动器通过Application Service创建和推进任务；遇到待确认问题时，对每个问题提交`None`表示“暂不确定”，
并恢复同一个`task_id`，避免人工答案污染组间对比。

驱动器默认最多允许2轮待确认和20次推进，超过即明确失败，防止离线实验卡死。Fake Application Service测试验证
两轮暂停恢复、同任务继续和限额拒绝；本轮尚未改变真实Orchestrator节点装配。

```text
python -m pytest -q tests/unit/evaluation/test_experiment_execution.py tests/unit/evaluation/test_experiments.py
8 passed

python -m pytest -q
468 passed，10 skipped
```

### 第四小步：三组Orchestrator依赖装配

本轮没有修改生产`AgentOrchestrator`，而是通过依赖注入装配三组：基础组使用`NoKnowledgeRetriever`和
`QualityLoopBypassReviewer`，RAG组使用真实Retriever和质量旁路，完整组使用真实Retriever、Reviewer和Reviser。

NoKnowledge会清空本地经验/RAG上下文并标记未命中；QualityBypass生成Finalizer可读取的合法覆盖结构。
两者都在完成事件中记录`evaluation_bypass=true`和被关闭的能力，避免把旁路的100分误写成真实Reviewer结果。
Fake依赖测试验证三组只启用策略允许的组件，状态机仍由原Orchestrator控制。

```text
python -m pytest -q tests/unit/evaluation/test_experiment_orchestrators.py tests/unit/evaluation/test_experiment_execution.py tests/unit/evaluation/test_experiments.py
11 passed

python -m pytest -q
471 passed，10 skipped
```

### 第五小步：真实三方案烟测与旧RAG日志修复

新增`RUN_THREE_WAY_INTEGRATION_EVALUATION=1`保护的真实入口，默认只运行`seed-v1`第一份需求。首次请求因
当前网络证书链临时不满足OpenSSL安全策略而失败；未关闭SSL校验，原条件重试后完成三组。

基础、RAG和完整组耗时分别为146.60、122.53和243.42秒，输入/输出Token分别为3025/10046、
2815/8737和9941/16488，完整组发生1轮修正。严格文本召回均为0，说明机器严格匹配无法识别模型同义表达，
不能据此比较三组业务质量。

烟测同时发现旧`MilvusRAGManager`把完整命中对象打印到Windows GBK控制台，特殊字符导致`UnicodeEncodeError`，
使原本成功的Milvus检索被误判为降级。现改为只打印结果数量并删除完整Hit输出；回归测试模拟GBK控制台和特殊字符，
确认检索上下文仍能正常返回。由于本次RAG结果发生过降级，报告只作为链路、耗时和Token烟测证据，不作为RAG增益数据。

```text
python -m pytest -q
474 passed，10 skipped

python -m compileall -q agent application repositories services utils views tests main.py evaluation
通过

git diff --check
通过
```

## 阶段 2.16.8：长PRD截断稳定性保护

页面重复验收时，第二个949字符片段仍被`deepseek-v4-pro`以`finish_reason=length`截断，证明固定8192输出Token和静态分段不能保证稳定。本阶段让JSON模式固定使用温度0，普通文本调用不受影响；Prompt同时限制各字段数量和单条长度。RequirementAnalyzer只对明确的输出截断执行自适应拆分，失败片段减半、最多3层、最小250字符，其他异常立即失败，避免无界重试掩盖真实故障。

真实复验结果并不理想：Pro在480秒工具上限内未完成；Flash最终以8次调用和2次自适应拆分在319.55秒完成，得到75条事实、45条规则、15条状态、46条风险和3个问题。结果证明失败保护有效，但同步延迟过高，而且3个问题中仍有2个可以从原文找到答案。下一步若继续，应改用statement_id紧凑分类协议，避免模型重复输出完整需求句子；本阶段不引入并行和后台任务。

```text
python -m pytest -q
485 passed，10 skipped
```

## 阶段 2.16.6：秋招证据汇总与项目冻结

为了优先满足秋招投递，本阶段没有继续增加Agent节点或运行耗时较高的完整10×3实验，而是把仓库中已经存在的代码、测试和真实评测结果整理为`docs/RESUME_EVIDENCE.md`。文档明确区分“可以描述的工程能力”和“尚不能声称的效果提升”，并提供推荐简历表述、三分钟讲解顺序与10个高频面试问题。

当前秋招版本默认冻结在线功能。完整10×3、语义评分、FastAPI、后台任务和Vue均为后续可选增强，不再阻塞项目学习、演示和投递。

## V1验收修复：长PRD需求分析输出截断

使用长篇订单履约PRD进行首次用户验收时，RequirementAnalyzer返回`finish_reason=length`。检查发现生成、评审和修正节点已使用8192输出Token，而需求分析节点仍使用全局默认值。现仅在RequirementAnalyzer调用统一结构化输出工具时传入`LARGE_STRUCTURED_OUTPUT_MAX_TOKENS`，并通过Fake LLM断言8192已被向下传递。该修复不会改变业务状态机；若未来出现超过8192的合法结构化结果，应另行设计分段分析，不能继续无限抬高上限。

## 阶段 2.16.7：长PRD章节感知Map-Merge分析

提高到8192输出Token后，规则密集型PRD仍可能被服务商以`finish_reason=length`截断。本阶段新增纯Python `RequirementChunker`，优先按Markdown章节和短数字标题分段，超长章节按段落或句子继续拆分；普通编号业务语句不会被当作章节。RequirementAnalyzer对每段调用原结构化Prompt，随后由Python按标准化文本合并去重，不额外要求LLM输出一份超大汇总JSON。

2735字符电商订单演示PRD被拆为2段，真实`deepseek-v4-pro`需求分析耗时222.75秒，得到57条事实、27条规则、14条状态流转、21条风险和3个待确认问题，未再截断。烟测也暴露跨片段问题精度限制：模型再次询问原文已经明确的30分钟超时规则。因此本阶段证明长输入链路能够完成，不声称待确认问题100%准确；全局语义复核与有限并行留作后续优化。

```text
python -m pytest -q
482 passed，10 skipped

python -m compileall -q agent application repositories services utils views tests main.py evaluation
通过

git diff --check
通过
```

## 阶段 2.16.9：长PRD稳定陈述ID与紧凑分析

本阶段按三个可独立验证的小步完成。

第一步由Python从需求分片中提取稳定陈述，为每条陈述分配`S001`等ID，同时保存章节、分片和字符范围。标题只作为上下文，不作为事实；列表项、段落句子和表格行可以形成陈述。该层不调用LLM。

第二步将长PRD的分片输出改为紧凑契约：LLM只返回事实、规则和状态对应的ID，以及少量带`basis_ids`的风险；Python校验ID并回填原始文字。待确认问题不再由每个分片分别生成，而是在全部陈述上执行一次全局审核。短PRD继续使用原契约，AgentState和Orchestrator未改变。

第三步真实运行发现，DeepSeek V4默认思考模式会让全局问题审核连续在2048和4096输出上限处截断，两次均约324秒。根据官方API契约，结构化JSON请求增加`thinking.type=disabled`，普通文本调用不变。随后同一2735字符PRD使用`deepseek-v4-flash`在13.38秒完成：2个初始分片、81条陈述、3次模型调用、0次自适应拆分，任务生成79条事实、61条规则、17条状态、18条风险和2个待确认问题。

这组数据证明当前单样本的截断和时延问题得到改善，但不能证明所有长PRD均达到相同效果。非思考模式对复杂分类质量的影响仍需在现有金标准上扩样评测。

验证：默认pytest使用Fake，不调用外部服务；真实长PRD入口由`RUN_LONG_REQUIREMENT_INTEGRATION_EVALUATION=1`显式保护，成功或失败都会保存脱敏指标。

## 阶段 2.16.10：长PRD知识检索上下文预算适配

V1完整功能验收发现，长PRD虽然已完成紧凑ID需求分析，但进入知识检索时仍会同时拼接原始需求、79条事实、61条规则、状态和风险，导致受保护上下文达到8081个估算Token，超过知识检索节点4000 Token预算。该问题不是模型输出长度限制，而是下游检索输入重复且无界。

本阶段只调整`ContextBuilder.build_knowledge_retrieval()`生成的检索视图：为原始需求、事实、规则、状态和风险分别设置字符预算；先保留包含金额、数字、权限、状态、时限和幂等等关键提示的条目，再按原顺序填充剩余额度；风险依据限制为120字符，并对完全相同的风险和依据去重。完整`AgentState`不被裁剪，Generator、Reviewer和Finalizer仍读取完整领域状态。裁剪结果通过`context_metrics.truncated_sections`留存，便于后续离线评测检索质量。

使用同一长PRD重新验收，知识检索查询缩减至2835字符，成功越过原`8081 > 4000`阻断。随后Embedding请求发生30秒超时，现有RAG降级逻辑使任务继续生成43条测试点；任务最终因第二轮Reviewer返回非法字段类型而失败。后两项属于外部服务可用性和Reviewer结构化契约问题，不混入本次预算修复。

```text
python -m pytest -q
496 passed，10 skipped

python -m compileall -q agent application repositories services utils views tests main.py evaluation
通过

git diff --check
通过
```

## 阶段 2.16.11：Reviewer结构化字段稳定性

真实长PRD第二轮Reviewer在两次受控生成中分别返回`missing_scenarios`对象项和`hallucination_issues`字符串项。Prompt现明确前者必须为字符串数组、后者必须为三字段对象数组；解析边界只兼容包含`scenario`、`description`或`issue`文本的缺失场景对象，以及非空的字符串幻觉问题。字符串幻觉问题采用保守占位标题恢复，仍会阻止评审通过；未知对象、错误分数和缺失覆盖仍严格拒绝。

定向测试共33项通过，覆盖兼容形式、未知对象拒绝以及字符串幻觉问题不得误判通过。

## 阶段 2.16.12：Embedding直连配置修复

长PRD验收中的Embedding超时实际指向本地代理`127.0.0.1:7890`。旧Agent RAG仍使用硬编码Ollama地址和30秒超时，并由`requests`继承启动进程代理。现改为读取现有`OLLAMA_BASE_URL`、`EMBEDDING_MODEL`和`EMBEDDING_TIMEOUT`配置，内部服务Session明确禁用环境代理；未配置时保留原兼容默认值。对配置端点执行只读健康检查返回200，耗时0.09秒，并发现`nomic-embed-text:latest`模型。

新增Fake Session测试验证地址、模型、超时参数和禁用代理行为，不在默认测试中连接真实Ollama或Milvus。

## 阶段 2.16.13：长PRD二次评审输出预算

完整验收中，33条测试点经第一轮82分评审和Reviser修正后增加到52条；第二轮Reviewer需输出79条需求覆盖映射及测试点标题引用，在原8192 Token处截断。Reviewer现单独使用16384的有界输出额度，其他结构化节点不变。该修复面向当前V1长PRD规模；若更大任务仍超限，后续应使用稳定ID压缩覆盖映射，而不是继续提高全局上限。

## 阶段 2.16.14：V1长PRD完整功能验收

同一2735字符电商PRD通过真实Application Service执行：需求分析后提出2项关键问题，以“暂不确定”恢复同一任务；知识检索查询2836字符，Ollama返回768维向量，Milvus从5条资产中命中1条，相似度0.6274。Generator生成42条测试点，三轮Reviewer分数依次为88、82、82，两轮Reviser将测试点修正为52和57条。

最终任务达到2轮自动修正上限，按受控状态机停止并等待人工反馈，没有发生异常、结构化JSON截断或Embedding超时。总执行约416秒，34次服务调用，provider Token 135375。新Application Service实例从MySQL按task_id恢复任务后再次推进，指标和节点均未增加，证明修正上限任务不会因恢复而重复执行。本样本未通过质量门禁，因此不生成报告；这是预期安全行为，不应伪装为完成态。

## 阶段 2.17.1：FastAPI同步薄接口

新增`api/main.py`和Pydantic请求模型，以HTTP用户动作调用现有Application Service。接口覆盖创建、查询、列表、同步推进、补充信息、业务规则确认、人工反馈、失败重试和删除，并由FastAPI自动生成OpenAPI/Swagger。`TaskView.to_dict()`提供隔离的传输字典，页面和API都无法通过返回值修改Repository中的AgentState。

本阶段没有增加节点级执行接口，没有复制状态机，也没有修改Streamlit、Agent节点和Orchestrator。`advance`仍同步执行一个节点；后台任务和进度查询留到2.17.2。接口测试使用Fake Application Service，不调用真实LLM、MySQL、Ollama或Milvus。

## 阶段 2.17.2：受控后台执行与状态查询

### 本阶段目标

让HTTP请求不再等待完整Agent链路，同时继续由Application Service和Orchestrator控制业务执行，不为后台任务复制状态机。

### 修改内容

- 新增`TaskBackgroundRunner`，用有界线程池循环调用现有`advance_task`，直到任务暂停、完成或失败。
- 新增`POST /api/v1/tasks/{task_id}/run`，接受后台执行后立即返回202。
- 新增`GET /api/v1/tasks/{task_id}/execution`，查询`idle/queued/running/stopped/failed`执行状态。
- 同一API进程内，同一个`task_id`已有未结束Future时不会重复提交。
- 保留原同步`advance`接口，便于调试和兼容；Streamlit、Agent节点与Orchestrator均未修改。

### 为什么只做小重构

后台Runner只负责“何时继续调用应用用例”，不判断具体节点。具体下一步仍由Orchestrator根据AgentState决定，节点重复执行仍受Repository执行租约保护。因此没有必要重构Agent状态机，也没有引入Celery、Redis或新的消息系统。

### 验证结果

- Runner推进至暂停后停止；
- 重复启动不会创建第二个线程任务；
- Worker异常可通过执行状态查询；
- 已暂停任务不会被错误提交；
- API后台启动与状态查询使用Fake Runner验证。

阶段完成时全量pytest为515 passed、10 skipped；默认测试未调用真实LLM、MySQL、Embedding或Milvus。

### 当前限制

当前Runner和Future注册表只存在于单个API进程内。多进程部署时，不同进程无法共享执行状态；进程退出后排队任务也不会自动恢复。本阶段不是生产级分布式任务队列，也未实现SSE。

## 阶段 2.17.3：前端轮询进度接口

### 本阶段目标

为后续独立前端提供稳定、轻量的轮询结果，避免前端从完整AgentState中自行推断状态和中文阶段。

### 修改内容

- 新增`GET /api/v1/tasks/{task_id}/progress`；
- 同时返回领域任务状态和后台Runner执行状态，避免混淆“等待用户”与“线程停止”；
- 返回中文状态、中文阶段、关键结果计数、修正次数和等待原因；
- 最近事件只保留3条，完整事件仍通过任务详情读取；
- 映射逻辑集中在`api/progress.py`，不写入领域状态。

### 代码边界

进度接口只组合`TaskView`与`BackgroundRunStatus`。它没有推进任务、选择节点、修改状态或访问Repository，因此不需要重构Application Service和Agent核心。

### 验证结果

API测试覆盖响应字段、中文映射、等待补充状态、Reviewer评分和最近事件上限。默认测试使用Fake Service与Fake Runner，不调用外部服务。

## 阶段 2.17.4：FastAPI文档上传入口

### 本阶段目标

让未来独立前端可以上传PRD文件创建任务，同时保持Streamlit和FastAPI共用同一套文档解析与任务创建逻辑。

### 修改内容

- 新增`POST /api/v1/tasks/from-document` multipart接口；
- 接受TXT、Markdown、PDF和DOCX，具体格式校验仍由DocumentService负责；
- API输入上限为20MB，空文件返回422，超限返回413；
- 上传内容转换为`UploadedDocument`并交给现有`CreateTaskCommand`；
- 增加`python-multipart`运行依赖。

### 代码边界

FastAPI不解析正文、表格或图片，也不直接创建AgentState。Application Service继续负责文档解析、指标收集、TaskRecord创建和Repository保存，因此页面与API不会形成两套业务实现。

### 验证结果

测试覆盖Command转换、空文件、20MB上限，并通过真实Application Service和现有Markdown解析器验证上传后创建的任务保存了解析正文。默认测试不调用真实OCR、视觉模型、LLM、MySQL或Milvus。

## 阶段 2.17.5：FastAPI V1完整链路验收

### 本阶段目标

证明已有接口可以组成一条供独立前端使用的完整链路，而不是继续增加新功能。

### 验收链路

```text
上传Markdown创建任务
→ 后台启动
→ 轮询至等待补充
→ 提交答案并保持同一task_id
→ 再次后台启动
→ 知识检索、生成、评审、整理报告
→ 轮询完成并读取完整报告
```

### 验证边界

测试使用真实FastAPI路由、Application Service、TaskBackgroundRunner和InMemory Repository；Agent节点结果由脚本化Orchestrator提供，因此不会访问真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。断言覆盖暂停恢复、测试点数量、Reviewer评分、用户答案和最终报告。

### 阶段结论

FastAPI V1已经具备文本/文件创建、后台执行、进度轮询、用户动作、暂停恢复和完整结果读取能力。当前秋招版本不需要为了技术名词继续增加SSE、Celery/Redis或Vue；这些能力应由真实部署需求驱动。

## 阶段 2.18.1：原生Web前端骨架

### 本阶段目标

在不引入Vue、npm和构建工具的前提下建立真正的前后端调用边界，先跑通创建任务、后台启动和进度轮询。

### 修改内容

- 新增`frontend/index.html`、`styles.css`和`app.js`三文件结构；
- 左侧支持需求文本或TXT、Markdown、PDF、DOCX文件输入；
- 右侧显示中文状态、当前阶段、测试点数、评分、修正次数和最近3条事件；
- 前端每1.5秒轮询轻量`progress`接口，终态或等待用户时自动停止；
- FastAPI同源托管`/app/`，根路径重定向至Web页面；
- 页面使用`textContent`展示服务端内容，避免把需求事件作为HTML插入。

### 范围控制

本阶段没有加入问答表单、测试点详情、报告预览和人工反馈，也没有修改Agent业务逻辑。原生三文件结构保留前端职责分离，同时避免单一HTML长期混合结构、样式和交互。

### 验证结果

API测试确认根路径重定向、Web页面与脚本可访问；现有FastAPI、Application Service和Agent测试保持通过。

## 阶段 2.18.2：Web待确认问答与视觉层级

### 本阶段目标

让原生Web前端完成Human-in-the-loop暂停与恢复，并在不重写页面结构的前提下提升状态可读性。

### 修改内容

- 任务等待用户时读取完整任务中的`open_questions`；
- 为每个问题动态创建答案输入和“暂不确定”选项；
- 未回答且未选择暂不确定时阻止提交；
- 提交补充后调用现有`clarifications`和`run`接口，保持同一`task_id`继续轮询；
- 等待期间锁定原始输入和启动按钮，避免意外创建另一任务；
- 增加五阶段流程条、柔和背景、轻量阴影和问答分区。

### 边界

问答字段全部使用DOM节点与`textContent`构造，没有拼接服务端HTML。后端Application Service、Orchestrator、暂停恢复和补充答案校验均未修改。

### 验证结果

静态页面路由测试确认问答提交逻辑随脚本提供；后端完整Fake链路继续覆盖等待补充、同task_id恢复和最终完成。完整浏览器交互验收按计划后置。

## 阶段 2.18.3：Web结构化测试点浏览

### 本阶段目标

让用户在原生Web工作台直接浏览Agent生成的结构化测试点，同时避免长结果把页面无限撑高。

### 修改内容

- 测试点生成后按需读取完整任务详情；
- 每页固定5条，显示标题、中文分类、优先级和场景摘要；
- 上一页/下一页只改变前端展示，不修改后端集合；
- 原生Dialog展示前置条件、执行步骤、预期结果和来源；
- 测试点数量、自动/人工修正次数或任务状态变化时重新加载结果。

### 数据与安全边界

分页序号只用于展示，详情按钮闭包持有原始测试点对象，没有用页内序号替代真实ID。所有服务端字段继续通过`textContent`创建DOM，不拼接HTML。

### 验证结果

静态资源测试确认分页与详情逻辑随脚本发布；后端测试点模型、Agent流程和FastAPI链路测试保持通过。完整浏览器分页与Dialog验收后置到Web主要功能完成后统一执行。

## 阶段 2.18.4：Web质量评审与最终报告

### 本阶段目标

让用户不离开原生Web工作台即可查看Reviewer质量结论和Finalizer报告，同时避免重复读取完整任务或引入Markdown渲染安全风险。

### 修改内容

- 结果区增加结构化测试点、质量评审、最终报告三个有状态导航；
- 展示Reviewer总分、4个维度分数、缺失场景、无依据断言风险和修正建议；
- 最终报告使用纯文本预览，避免将模型内容作为HTML执行；
- 使用浏览器Blob下载UTF-8 Markdown文件；
- 测试点、质量结果和报告复用同一次任务详情请求。

### 边界与验证

本阶段未修改FastAPI、Application Service、Agent状态机和报告内容，只增加前端展示。API静态资源测试确认质量评审与报告逻辑已发布；完整浏览器交互验收继续留到Web主要功能完成后统一执行。

## 阶段 2.18.5：Web人工反馈与业务规则确认

### 本阶段目标

补齐原生Web的Human-in-the-loop质量修正入口，复用现有Application Service动作，不在前端建立第二套状态机。

### 修改内容

- 右侧增加人工反馈导航、结构化表单和历史处理状态；
- 测试建议支持新增、修改、删除和P0/P1/P2优先级调整；
- 业务规则支持新增、修改和删除，提交后先进入待确认状态；
- 左侧展示待确认规则的操作、目标、内容和依据，并提供确认或取消；
- 可执行反馈和确认结果通过既有`run`入口恢复同一任务。

### 业务与安全边界

前端只提交`SubmitFeedbackCommand`和`ConfirmBusinessRulesCommand`所需字段，不传节点名称。是否修正、重新评审或整理报告仍由Application Service和Orchestrator决定。所有反馈内容继续通过DOM与`textContent`展示。

### 验证结果

API、Application Service和HumanFeedback领域专项测试通过；静态资源测试确认反馈提交与业务规则确认逻辑已发布。真实浏览器完整交互验收留到2.18.6统一执行。

## 阶段 2.18.6：原生Web主链路自动化验收

### 验收链路

```text
Markdown上传 → 后台运行 → 等待需求补充 → 同task_id恢复
→ 测试点/评审/报告 → 测试建议 → Reviser/Reviewer/Finalizer
→ 业务规则待确认 → 确认并修正 → 取消另一条未确认规则
```

### 自动化证据

- 使用真实FastAPI路由、Application Service、TaskBackgroundRunner和InMemory Repository；
- 使用脚本化Orchestrator隔离LLM、Embedding、Milvus和MySQL；
- 断言反馈状态从`ready`变为`applied`，人工修正次数递增；
- 断言业务规则确认后写入，取消后保持`rejected`且不写入；
- 前端DOM契约测试核对JavaScript查询的所有元素ID；
- 本地HTTP检查确认页面、脚本及新增交互标识返回成功。

### 未形成的证据

Codex桌面浏览器控制环境因组件路径缺失无法启动，因此本阶段没有自动生成真实浏览器点击截图。该限制不影响HTTP和应用链路测试结果，但在冻结V1前仍需用户手动完成一次页面点击体验。

## 阶段 2.18.7：Web恢复轮询与Reviewer有界输出修复

### 问题与根因

提交补充信息后，后台Runner刚入队时业务状态仍可能是`waiting_for_user`。旧前端立即停止轮询，因此没有展示后端后续的知识检索、测试点生成和失败结果。实际任务随后在Reviewer失败：79条事实和30个测试点要求模型逐字回传覆盖映射，最终达到`max_tokens`并截断JSON。

### 修改内容

- 前端仅在后台状态不为`queued/running`时停止等待用户轮询；
- Reviewer输入使用紧凑JSON，并明确限制问题、幻觉和建议的数量与单项长度；
- 需求事实使用`F001`等稳定ID参与评审，解析后由Python恢复原文再执行完整覆盖校验；
- Reviewer只对明确的`max_tokens`截断受控重试一次，其他节点的既有截断策略和调用错误处理保持不变；
- 增加轮询保护、紧凑Prompt、事实ID还原和截断重试测试。

### 边界

没有修改AgentState、Orchestrator、Reviewer评分门槛、Reviser流程或页面布局。事实ID只存在于LLM传输层，Repository快照、页面结果和报告仍保存原事实。失败任务的Reviewer输入从约24776字符缩减至19042字符；这是同一任务的字符测量，不代表Token或成功率提升。真实LLM复验尚未执行。

## 阶段 2.18.8：Reviewer附加字段安全兼容

2.18.7后的真实任务完成79条事实和34个测试点的评审生成，模型两次均以`stop`结束且单次输出约3830 tokens，证明本次失败不再是长度截断。新的阻断来自`hallucination_issues`对象附带额外字段，而三个核心业务字段仍由Prompt明确要求。

校验器现在从“字段集合必须完全相等”调整为“核心字段必须全部存在”：`test_point_title`、`issue`和`unsupported_claim`继续逐项做非空文本校验，额外定位字段不会保存到领域结果；缺少核心字段仍明确报错。测试覆盖额外字段被忽略和核心字段缺失被拒绝，没有修改Reviewer评分、状态机或页面。

## 阶段 2.18.9：测试点来源枚举归一化

真实任务在需求分析和RAG检索完成后，TestPointGenerator两次输出完整JSON，但`sources`含契约外来源值，严格枚举校验使任务失败。根因是Prompt只列合法值，没有说明`inferred_risk`和RAG等上下文分区应映射到哪个领域来源。

本阶段补充来源语义说明，并在`TestPoint.from_dict`中将`requirement_fact`、`inferred_risk`、`rag`、`local_bug_knowledge`、`user_clarification`等明确同义传输值归一化为现有四种枚举。归一化后按原顺序去重；未知值继续拒绝，错误信息显示非法标签以便诊断。没有增加新的领域枚举，也没有修改AgentState和来源追踪结构。

## 阶段 2.18.10：历史任务摘要与页面恢复

### 本阶段目标

让用户从原生Web找回MySQL中已经持久化的任务，而不是只能保存、不能再次进入；列表查询不能反序列化或排序全部大快照。

### 修改内容

- `TaskRepository`增加只读的`TaskSummary`、分页结果和摘要查询契约；
- InMemory与MySQL实现支持按任务ID、需求摘要搜索，并按更新时间分页；
- FastAPI增加`GET /api/v1/task-summaries`；
- 页面头部增加历史任务Dialog，可搜索、翻页和恢复原`task_id`；
- 恢复后重新读取详情与进度，终态不执行节点，等待态展示原确认动作，运行态继续轮询；
- 旧完整列表不再要求MySQL排序大JSON字段，规避云端排序内存错误。

### 边界

本阶段没有增加历史任务删除、批量操作和知识库管理，也没有修改Agent状态机。摘要只负责定位任务，完整AgentState仍通过既有版本化快照按`task_id`恢复。

## 阶段 2.18.11：知识资产显式保存入口

### 本阶段目标

把已经实现的知识资产准入、MySQL存储和Milvus索引能力接入原生Web，让历史资产来源形成用户可见闭环，同时避免自动沉淀未确认或敏感内容。

### 修改内容

- FastAPI默认装配共享的任务Repository和知识资产Repository；
- 增加`POST /api/v1/tasks/{task_id}/knowledge-assets`；
- API先调用`KnowledgeAssetApplicationService`执行完成态、Reviewer、问题和反馈准入校验，再调用索引服务；
- 最终报告页增加脱敏确认和保存按钮；
- 成功后展示实际索引片段数，索引失败明确说明MySQL已保存但Milvus失败；
- API测试使用Fake资产与索引服务，不访问真实MySQL、Embedding和Milvus。

### 边界

入口只对完成任务显示，用户点击等价于发布确认，但数据安全仍需单独勾选。当前没有知识资产列表、删除、下线和失败重试页面；这些不是本阶段完成能力。

## 阶段 2.18.12：左侧历史任务与统一命名

### 修改内容

- 历史任务由顶部Dialog改为工作区最左侧的紧凑会话列表，每项只显示标题和状态；
- 列表支持按任务名称、需求摘要或任务ID搜索，点击标题恢复，并在确认后删除任务；
- 确定性命名器优先提取Markdown标题，再使用首个有效需求文本行，不增加模型耗时；
- MySQL增加独立`task_name`摘要列，新任务创建时写入，旧任务以已有摘要回填；
- 当前任务说明、历史任务标题和报告下载文件名使用同一名称；
- 文件名过滤Windows非法字符，不改变报告正文。

### 边界

本阶段未修改AgentState快照schema、节点顺序和LLM Prompt。任务名属于任务查询元数据，不参与需求分析和测试点生成。

## 阶段 2.18.13：历史任务悬浮删除确认

浏览器原生`confirm()`替换为任务项内部的悬浮确认层，提供取消和确认删除两个动作。确认后仍调用Application Service已有删除用例；页面不直接操作Repository。MySQL删除`agent_tasks`记录后，数据库外键级联清理任务事件和执行记录。知识资产是用户独立确认发布的版本化资产，不随任务导航记录删除。

## 阶段 2.18.14：固定视口工作区与悬浮层防裁剪

桌面端将页面外层锁定为视口高度，产品头部下方的三栏工作区统一使用`calc(100vh - 108px)`，面板长内容在内部滚动。删除确认层不再作为历史列表子元素，而是挂载到`body`并用按钮视口坐标定位，从根因上避免`overflow`裁剪；移动端仍使用自然滚动，避免小屏固定高度影响操作。
## 阶段 2.18.15：新建任务入口与任务重命名

### 功能变更

- 左侧历史栏增加“新建任务”，复用既有工作区重置逻辑，不创建空任务记录；
- 每条历史任务增加重命名入口，使用任务项附近的轻量确认层输入新名称；
- FastAPI新增任务名称PATCH接口，Application Service校验任务状态后调用Repository；
- InMemory和MySQL Repository均持久化展示名并递增任务版本；
- 运行中的任务拒绝重命名，避免重命名和节点快照保存并发覆盖；
- 重命名只改变列表、当前标题及下载文件名，不修改AgentState和报告正文。

### 验证边界

Repository、Application Service、API和前端静态契约测试覆盖新入口与重命名链路。任务名称限制为清理空白后1～48个字符；不存在任务返回404，非法或运行中状态返回409。
