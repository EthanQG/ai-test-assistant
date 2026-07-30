# Test Analysis Agent 当前开发状态

更新时间：2026-07-30

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.12提交：`caeb5af 阶段2.12：建立后端调用边界`
- 阶段2.12验收修正提交：`1503e59 修复：补充恢复统一经过编排器`
- 阶段2.13.1版本化任务快照及恢复执行测试已经完成
- 阶段开始前工作区干净

## 当前阶段

阶段2.13.1“AgentState版本化快照序列化”已经完成代码与测试：

- 增加独立`TaskSnapshotSerializer`
- 快照顶层固定为`schema_version`、`task_id`、`state`和`application`
- AgentState全部业务字段、事件、枚举和时间可从JSON恢复为原领域类型
- TaskRecord的决策、自动推进、待消费补充答案、执行步数、下一动作和节点指标可恢复
- 时间强制带时区并统一输出UTC ISO 8601
- 缺字段、未知字段、非法枚举、非法时间和未来未知版本均明确拒绝
- `in_progress`属于进程内临时执行保护，不进入快照，恢复后固定为`False`
- 不使用pickle、Python类路径、`default=str`或Streamlit状态

下一阶段为2.13.2 MySQL任务与事件表。本轮未实现MySQL、乐观锁、execution_id、执行租约、
FastAPI、后台任务、SSE或Vue。

## 当前依赖方向

```text
views/
  → application/TestAnalysisApplicationService
  → repositories/TaskRepository
  → agent/AgentOrchestrator、节点与HumanFeedbackHandler
  → services/LLM、RAG、Prompt与文档解析

Streamlit会话装配
  → InMemoryTaskRepository
```

页面只能获得`TaskView`。View从Repository隔离副本生成；页面读取列表或字典后进行修改，不会
改变Repository中的AgentState。

## Application Service公开用例

- `create_task(command)`
- `get_task(task_id)`
- `list_tasks()`
- `advance_task(task_id)`
- `submit_clarifications(task_id, command)`
- `confirm_business_rules(task_id, command)`
- `submit_feedback(task_id, command)`
- `retry_task(task_id)`
- `delete_task(task_id)`

没有提供任意节点执行接口。合法下一步仍由`AgentOrchestrator`决定。

## Streamlit session_state边界

保留：

- 会话级Application Service依赖实例
- 当前`task_id`
- Tab、页码、Dialog、展开项
- 输入框、上传控件、澄清回答和人工反馈表单草稿
- 表单版本和一次性页面提示

已移除：

- 可变AgentState
- Orchestrator决策列表
- 自动运行标记
- 待处理澄清命令
- 执行步数
- 进程级`_task_store()`字典

后五项现在由Application Service与TaskRepository内部管理。

## 性能基线

Application Service在每次`advance_task()`时记录：

- 节点动作
- UTC开始与结束时间
- 实际耗时
- 成功或失败
- 失败异常类型
- 单任务累计节点执行耗时

LLM Token、模型、重试次数、Embedding和Milvus分层耗时尚未记录，留到2.15。

## 验证状态

```text
python -m unittest discover -s tests -v
230 tests passed
```

新增33项快照格式与异常测试，以及5项恢复执行测试，覆盖完整字典/JSON往返、领域类型恢复、
等待/完成/失败状态、人工反馈、RAG、性能指标、严格版本与字段校验、运行时对象拒绝和可变
引用隔离。恢复任务会实际经过Application Service和AgentOrchestrator继续执行；自动化测试
不访问真实DeepSeek、Milvus、Embedding或MySQL。

## 当前限制

- InMemory Repository按Streamlit会话装配，只支持当前会话内的rerun和task_id恢复
- 新浏览器会话、硬刷新导致会话重建或Streamlit服务重启后，内存任务不可恢复
- `expected_version`只在Repository接口中预留，当前内存实现没有并发版本控制
- `in_progress`只能保护同一会话的同步调用，不能处理跨进程并发
- 快照只定义结构版本`schema_version=1`，尚无历史版本迁移
- `in_progress`不持久化；跨进程执行保护留给后续执行租约
- 快照尚未接入Repository，服务重启后仍无法恢复
- RAG当前只保存拼接后的`rag_context`、命中数、最高分、状态和错误，没有逐条来源对象
- 尚未记录LLM、Embedding、Milvus、Token和重试的分层指标
- 尚未完成知识资产沉淀和真实离线评测

## 下一步：阶段2.13.2

1. 设计`agent_tasks`任务快照表与`agent_task_events`独立事件表
2. 选择MySQL JSON列保存schema v1快照
3. 实现MySQLTaskRepository并保持TaskRepository契约
4. 在同一事务中保存快照与新增事件
5. 服务重启恢复、version和execution_id仍按后续2.13.3/2.13.4实施

进入2.13.2时不要同时实现KnowledgeAsset、Milvus V2、FastAPI或Vue。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
