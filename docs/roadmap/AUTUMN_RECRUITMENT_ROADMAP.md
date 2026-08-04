# Test Analysis Agent 秋招项目含金量提升路线图

更新时间：2026-07-29

## 1. 文档目的

本路线图用于约束 Streamlit V1 演示页面收尾后的开发范围。后续不以增加多 Agent、
自主规划、任意工具调用或复杂前端为目标，而是把项目完善为一个具有工程证据和质量评测
能力的 AI 测试分析项目。

当前项目的准确定位是：

> 面向 PRD 测试分析场景的受控单 Agent Agentic Workflow。

Python Orchestrator 负责合法步骤、状态转换、最大修正次数和终止条件；LLM 负责需求理解、
结构化测试点生成、质量评审和定向修正。项目不是固定顺序 Workflow，也不是可以任意规划和
调用工具的自主 Agent。

## 2. 项目核心价值

后续建设集中在以下能力：

1. 受控 Agent 编排和安全边界
2. Human-in-the-loop 暂停、恢复和业务规则确认
3. RAG 历史测试资产检索及错误召回控制
4. Reviewer/Reviser 质量闭环
5. MySQL 任务恢复和重复执行保护
6. 节点级上下文构建与 Token 预算
7. 离线评测和方案对比
8. 节点、LLM、Embedding 和 Milvus 的可观测性
9. 人工确认后的知识资产沉淀与再检索闭环

## 3. 当前能力边界

### 3.1 已实现且有自动化测试

- AgentState、AgentEvent 和受控状态转换
- RequirementAnalyzer、KnowledgeRetriever、TestPointGenerator
- Reviewer、Reviser、HumanFeedbackHandler 和 Finalizer
- 待确认暂停、用户补充恢复、业务规则二次确认
- 最大自动修正次数和人工反馈独立修正
- Milvus 检索的命中、无匹配和失败降级
- 结构化 JSON 校验、截断检测和一次受控重试
- Streamlit V1 功能演示链路
- Application Service用户用例边界与只读TaskView
- TaskRepository契约、会话级InMemory实现和隔离副本
- 页面入口不再直接调用Orchestrator、节点或FeedbackHandler

### 3.2 已实现但缺少真实效果验证

- DeepSeek 真实生成质量
- Milvus 真实检索效果
- Reviewer/Reviser 带来的质量变化
- RAG 对错误历史规则的污染控制效果
- Prompt 和输出预算的真实成本收益

单元测试使用 Fake Service，不代表已经获得真实 RAG、生成质量或性能指标。

### 3.3 部分实现

- MySQL已支持任务持久化和跨Application Service实例恢复，但尚无乐观锁、execution_id和执行租约
- `in_progress` 只在单会话内防止重复节点
- schema v1快照可完整恢复，尚无历史schema迁移样本
- Application Service已记录节点成功/失败耗时，缺少外部调用分层耗时
- PromptService 已按节点构造输入，但尚无集中 ContextBuilder 和输入预算
- 旧 Workflow 仍保留写入 Milvus 的兼容方法，当前 Agent 页面没有知识沉淀入口

### 3.4 暂不实现

- 多 Agent 自由协作
- LLM 任意调用工具
- 不受控自主规划和反思
- 为展示概念而增加长期记忆
- 后端边界稳定前重写 Vue 页面
- 没有真实超长输入触发条件的复杂上下文摘要

### 3.5 价值和优先级

评分范围为1～5；实现成本和回归风险分数越高，表示代价越大。

| 改造项 | 测开价值 | AI价值 | 可讲述 | 可验证 | 成本 | 风险 | 优先级 | 判断 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Application Service | 5 | 4 | 5 | 5 | 3 | 3 | P0 | 页面和后端解耦基础 |
| TaskRepository | 5 | 4 | 4 | 5 | 2 | 2 | P0 | 内存与MySQL切换基础 |
| MySQL任务持久化 | 5 | 4 | 5 | 5 | 4 | 4 | P0 | 恢复和审计证据 |
| version与execution_id | 5 | 4 | 5 | 5 | 3 | 4 | P0 | 重复执行保护 |
| KnowledgeAsset准入 | 5 | 5 | 5 | 5 | 3 | 3 | P0 | 防止知识污染 |
| Milvus V2索引 | 5 | 5 | 5 | 4 | 4 | 3 | P0 | 形成知识闭环 |
| ContextBuilder | 4 | 5 | 5 | 5 | 3 | 3 | P0 | 节点上下文工程 |
| Token和耗时统计 | 4 | 5 | 5 | 5 | 2 | 2 | P0 | 性能和成本证据 |
| RAG裁剪和来源追踪 | 4 | 5 | 4 | 5 | 2 | 2 | P0 | 错误召回控制 |
| 离线评测集 | 5 | 5 | 5 | 5 | 4 | 2 | P0 | 质量结论基础 |
| RAG专项评测 | 5 | 5 | 5 | 4 | 4 | 2 | P0 | 证明检索有效 |
| Reviewer/Reviser评测 | 5 | 5 | 5 | 4 | 4 | 2 | P0 | 证明闭环有效 |
| FastAPI | 4 | 3 | 4 | 5 | 3 | 3 | P1 | 核心稳定后服务化 |
| 后台任务 | 4 | 4 | 4 | 4 | 4 | 4 | P1 | 同步耗时影响演示时再做 |
| SSE或轮询 | 3 | 4 | 4 | 4 | 4 | 4 | P2 | 不影响核心质量价值 |
| Vue | 3 | 2 | 3 | 4 | 5 | 4 | P2 | 不阻塞秋招版本 |
| 自动上下文摘要 | 2 | 4 | 3 | 3 | 4 | 4 | P2 | 有真实超预算样本后再做 |
| LLM自主选择节点 | 1 | 3 | 2 | 2 | 4 | 5 | 不建议 | 削弱现有安全边界 |
| 多Agent | 1 | 3 | 2 | 2 | 5 | 5 | 不建议 | 当前场景属于概念堆砌 |
| 展示型长期记忆 | 2 | 3 | 3 | 2 | 4 | 4 | 不建议 | 应实现可审计KnowledgeAsset |

## 4. 数据职责

### 4.1 MySQL

MySQL 是权威数据源，负责保存：

- AgentState 完整任务快照
- Orchestrator 决策和 Agent 事件
- version、execution_id 和执行租约
- 用户确认后的完整 KnowledgeAsset
- 知识资产版本、状态、来源任务和索引状态

### 4.2 Milvus

Milvus 是语义检索索引，负责保存：

- KnowledgeAsset 的检索向量
- asset_id、asset_version 和 content_hash
- 少量用于过滤和排错的摘要元数据

第一版不再把 Milvus 当成完整业务数据源。检索时先由 Milvus 返回相似 `asset_id` 和分数，
再从 MySQL 读取完整、已确认的结构化知识资产。

### 4.3 知识闭环

```text
任务完成并通过Reviewer
→ 用户明确确认符合数据安全和知识沉淀要求
→ MySQL创建KnowledgeAsset，状态pending_index
→ 构建确定性检索文本
→ Embedding生成向量
→ 写入Milvus V2集合
→ 成功后状态改为indexed
→ 后续任务通过Milvus找到asset_id
→ 从MySQL读取完整资产
→ ContextBuilder裁剪并交给Generator
```

未通过评审、存在待处理反馈、存在待确认业务规则或关键问题未解决的结果不能自动沉淀。

## 5. 阶段规划

## 2.12 后端调用边界（已完成）

完成证据：Streamlit只调用Application Service；TaskRepository提供会话级内存实现并返回
隔离副本；页面只保存task_id和UI状态；schema v1任务快照已可严格恢复并继续受控执行；
245项离线自动化测试通过。阶段2.13.2～2.13.3另已完成MySQL Repository和真实恢复验证；
本节保留的是2.12自身的交付边界。

### 2.12.1 Application Service 接口

- 增加创建、查询、推进、需求补充、反馈和规则确认用例
- Streamlit 只能调用 Application Service
- 不改变 Agent 节点顺序和业务规则

### 2.12.2 Repository 接口与内存实现

- 定义 TaskRepository 契约
- 使用 InMemoryTaskRepository 替换页面 `_task_store()`
- Repository 返回隔离副本，避免绕过版本控制修改可变 State

### 2.12.3 Streamlit 调用入口迁移

- 页面不再直接创建 Orchestrator、节点、FeedbackHandler 或外部服务
- 页面只保留输入、Tab、分页、Dialog、表单草稿和 rerun 调度
- 不修改现有布局和 CSS

## 2.13 MySQL 任务持久化与恢复

### 2.13.1 AgentState 快照序列化

- **已完成（2026-07-30）**
- 独立`TaskSnapshotSerializer`保存AgentState业务状态和TaskRecord恢复元数据
- 恢复枚举、UTC时间、AgentEvent、决策和节点指标
- 引入`schema_version=1`并严格拒绝未知版本、缺失字段和非法数据
- 进程内`in_progress`不作为数据库租约持久化
- 恢复任务通过Application Service和AgentOrchestrator继续执行的Fake集成测试

### 2.13.2 MySQL 任务与事件表

- **已完成（2026-08-04）**
- `agent_tasks` 保存完整 State 快照和决策
- `agent_task_events` 保存独立事件和执行元数据
- 实现 MySQLTaskRepository
- 快照与新增事件在同一事务提交，失败时整体回滚

### 2.13.3 服务重启恢复

- **已完成（2026-08-04）**
- 每个节点完成后原子保存快照和新增事件
- 等待用户、完成和失败任务均可按 task_id 恢复
- 真实MySQL验证create/get/save/list/delete、version递增、事件数量一致和外键级联删除
- 销毁并重建Repository与Application Service后，同一task_id仍按原状态机继续或保持终态
- 3项真实数据库测试需显式开关运行，日常单元测试不依赖外部数据库

### 2.13.4 重复执行保护

- version 负责检测基于旧快照的并发写入
- execution_id 负责请求幂等
- 执行租约负责进程异常后的锁恢复
- 第一版保证节点结果最多提交一次，不宣称外部 LLM 请求 Exactly Once

## 2.14 知识资产沉淀与 Milvus 闭环

### 2.14.1 KnowledgeAsset 模型和准入规则

- 只允许通过 Reviewer 且经过用户明确确认的结果沉淀
- 保存来源任务、资产版本、内容哈希、结构化需求和测试点

### 2.14.2 MySQL 知识资产存储

- 增加 `knowledge_assets`
- MySQL 保存完整权威资产
- 支持 `pending_index`、`indexed`、`index_failed`、`retired`

### 2.14.3 Milvus V2 向量索引

- 从需求摘要、模块、事实、规则和风险构建检索文本
- Milvus 保存向量、asset_id、版本和必要元数据
- 旧集合保留为 legacy，只读使用，不直接视为已确认高质量资产

### 2.14.4 历史资产检索与上下文组装

- 当前需求生成查询向量
- Milvus 使用余弦相似度返回 Top-K 资产 ID
- 相似度阈值过滤后从 MySQL读取完整资产
- ContextBuilder 负责裁剪和来源标记

### 2.14.5 发布、去重和失败重试

- request_id 防止重复发布
- content_hash 防止相同内容重复建资产
- Embedding 或 Milvus 失败时保留 MySQL 资产并允许重试

## 2.15 上下文工程与可观测性

### 2.15.1 ContextBuilder

- 为每个节点定义输入字段白名单
- 不把完整 AgentState、事件和无关历史发送给 LLM

### 2.15.2 节点预算和 RAG 裁剪

- 根据模型上下文窗口、输出预算和安全余量计算输入预算
- 保持当前 Top-K=2 作为第一版基线
- 限制单条资产和 RAG 总长度，保留 asset_id、来源和相似度
- 业务事实、数字、规则、状态和来源不能静默裁剪

### 2.15.3 耗时和 Token

- 记录节点、LLM、Embedding、Milvus 和 JSON 校验耗时
- 记录模型、Prompt 版本、输入输出字符数、API Token usage 和重试次数
- API 未返回 Token 时标记为估算，不伪造精确值

### 2.15.4 错误分类和降级

- 区分输入超预算、输出截断、传输失败、校验失败、Embedding 失败和 Milvus 失败
- 降级必须进入事件和性能报告

## 2.16 离线评测与消融实验

### 2.16.1 脱敏数据集和人工标注

- 准备 10～20 份脱敏需求
- 标注事实、规则、关键问题、风险、必要场景和禁止断言

### 2.16.2 RAG 评测

- Recall@K、Precision@K、MRR
- 无关资产召回率和历史规则污染数量
- legacy 资产与用户确认资产分别统计

### 2.16.3 Reviewer/Reviser 评测

- 向测试点注入遗漏、重复、幻觉、模糊预期和缺失来源
- 计算 Reviewer 缺陷检测 Precision、Recall、误报和漏报

### 2.16.4 三组消融实验

1. 基础 LLM
2. LLM + RAG
3. LLM + RAG + Reviewer/Reviser

### 2.16.5 结果报告

- 事实准确率、风险覆盖率、待确认项召回率
- 无依据断言、重复率、可执行性
- 平均耗时、Token 和修正次数
- 在真实数据产生前不写“显著提升”或固定百分比

## 2.17 API 和异步执行评估

### 2.17.1 FastAPI 接口

### 2.17.2 后台任务

### 2.17.3 SSE 或轮询

### 2.17.4 Vue 迁移评估

阶段 2.17 不属于当前 P0，不阻塞秋招版本。

## 6. P0 完成标准

- Application Service 和 TaskRepository 已落地
- MySQL 支持任务快照、事件、重启恢复和重复执行保护
- 用户确认后的 KnowledgeAsset 可以可靠写入 MySQL 并索引到 Milvus
- 后续任务能够检索确认资产并保留来源
- ContextBuilder、节点预算、耗时和 Token 统计可用
- 至少 10 份脱敏需求完成三组消融实验
- README 只展示真实结果和明确限制
- 全量离线自动化测试通过

FastAPI、后台任务、SSE、Vue、多 Agent 和自主规划不属于最小完成标准。

## 7. 各阶段证据要求

| 阶段 | 可运行代码 | 自动化测试 | 演示或数据 | 架构决策 | 完成后可写简历 | 完成前不能写 |
|---|---|---|---|---|---|---|
| 2.12 | Application Service、Repository、页面入口迁移 | Repository契约和完整页面回归 | Streamlit功能行为不变 | 页面与应用用例分离 | 应用服务与Repository解耦 | MySQL恢复 |
| 2.13 | MySQL Repository和快照恢复 | 序列化、重启恢复、并发和幂等 | 重启后继续同一task_id | version与execution_id分工 | MySQL任务恢复和重复保护 | Exactly Once |
| 2.14 | KnowledgeAsset发布和Milvus V2索引 | 准入、去重、失败重试和检索来源 | 已确认资产被后续任务检索 | MySQL权威数据、Milvus语义索引 | 人工确认后的知识资产闭环 | RAG提升比例 |
| 2.15 | ContextBuilder和Telemetry | 字段白名单、预算、裁剪、错误分类 | 节点耗时瀑布和Token记录 | 最小必要上下文 | 节点级预算和可观测性 | Token降低比例 |
| 2.16 | 数据集、Runner和Metrics | 指标脚本确定性测试 | 三组原始结果和报告 | 人工标注与消融实验 | 真实评测范围内的指标 | 超出样本范围的泛化结论 |
| 2.17 | 可选API、Worker和事件流 | API幂等和失败恢复 | 后台执行演示 | 同步到异步迁移 | 只描述实际完成部分 | 生产级高可用 |

每个阶段都必须同步README、CURRENT_STATUS、DEVELOPMENT_LOG和LEARNING_NOTES。涉及产品范围
或验收标准变化时同步更新PRD。

## 8. 建议六周顺序

| 周次 | 阶段 | 可验收成果 |
|---|---|---|
| 第1周 | 2.12 | Application Service、Repository和页面入口迁移 |
| 第2周 | 2.13 | MySQL快照、重启恢复、version和execution_id |
| 第3周 | 2.14 | 用户确认、KnowledgeAsset、Milvus V2索引和失败重试 |
| 第4周 | 2.15 | ContextBuilder、Token预算和分层耗时 |
| 第5周 | 2.16.1～2.16.3 | 评测集、标注规范、RAG和Reviewer指标 |
| 第6周 | 2.16.4～2.16.5 | 三组实验、结果报告、README和简历材料 |

## 9. 简历边界

### 完成对应阶段后可以描述

- 受控 Agentic Workflow 和 Human-in-the-loop
- Application Service 与 Repository 解耦
- MySQL 任务恢复和幂等保护
- 人工确认后的知识资产沉淀与 Milvus 检索
- 节点上下文预算、Token 和耗时可观测性
- 基于脱敏评测集的真实消融实验结果

### 尚未完成前不能描述

- version、execution_id和执行租约的重复执行保护
- 可靠知识资产闭环
- RAG 或 Reviewer 的具体提升比例
- 后台任务、SSE 和前后端分离
- 自主 Agent、多 Agent 或任意工具调用
