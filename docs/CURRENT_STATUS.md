# Test Analysis Agent 当前开发状态

更新时间：2026-08-04

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.12提交：`caeb5af 阶段2.12：建立后端调用边界`
- 阶段2.12验收修正提交：`1503e59 修复：补充恢复统一经过编排器`
- 阶段2.13.1版本化任务快照及恢复执行测试已经完成
- 阶段2.13.1提交：`5f50110 阶段2.13.1：实现版本化任务快照与恢复验证`
- 阶段2.13.2 MySQL任务与事件Repository代码、真实连接和建表验证已经完成

## 当前阶段

阶段2.13.2“MySQL任务与事件表”已经完成代码、Fake数据库测试和真实建表验证：

- 新增`agent_tasks`任务表，保存schema v1完整JSON快照和常用查询摘要
- 新增`agent_task_events`事件表，使用`task_id + sequence_no`保证事件顺序唯一
- 新增`MySQLTaskRepository`，实现`create/get/save/list/delete`统一契约
- 创建和保存时在同一事务中写入快照与新增Agent事件，任一步失败均回滚
- 保存时只追加快照中尚未写入的事件，并拒绝事件历史倒退
- 数据库`version`列已预留并随保存递增，但尚未启用`expected_version`冲突校验
- 通过`TASK_REPOSITORY_BACKEND`选择`memory`或`mysql`，默认仍为内存模式
- MySQL连接参数只从环境变量读取，不提交真实账号和密码
- 已连接真实MySQL 8.0.32并成功创建`agent_tasks`和`agent_task_events`，两表初始为空

本轮尚未使用真实MySQL验证TaskRecord的create/save/get/delete和服务重启恢复，也未实现乐观锁、execution_id、执行租约、
FastAPI、后台任务、SSE或Vue。

## 当前依赖方向

```text
views/
  → application/TestAnalysisApplicationService
  → repositories/TaskRepository
  → agent/AgentOrchestrator、节点与HumanFeedbackHandler
  → services/LLM、RAG、Prompt与文档解析

Streamlit会话装配
  → TASK_REPOSITORY_BACKEND=memory：InMemoryTaskRepository
  → TASK_REPOSITORY_BACKEND=mysql：MySQLTaskRepository
      → TaskSnapshotSerializer
      → agent_tasks + agent_task_events
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
245 tests passed
```

新增15项MySQL Repository与配置测试，覆盖建表、快照与事件同事务写入、增量事件、读取恢复、
列表、删除、重复任务、回滚、配置校验以及默认内存/显式MySQL装配。测试使用Fake DB-API，
不访问真实DeepSeek、Milvus、Embedding或MySQL。

## 当前限制

- 默认仍为InMemory Repository；只有显式配置MySQL后才会持久化任务
- MySQL建表SQL已在真实MySQL 8.0.32执行成功；Repository真实CRUD和跨实例恢复尚未验证
- `expected_version`仍未执行并发版本校验；当前`version`只递增，不能阻止旧快照覆盖
- `in_progress`只能保护同一会话的同步调用，不能处理跨进程并发
- 快照只定义结构版本`schema_version=1`，尚无历史版本迁移
- `in_progress`不持久化；跨进程执行保护留给后续执行租约
- MySQL Repository可以按task_id读取快照，但服务重启恢复场景尚未进行正式集成验收
- RAG当前只保存拼接后的`rag_context`、命中数、最高分、状态和错误，没有逐条来源对象
- 尚未记录LLM、Embedding、Milvus、Token和重试的分层指标
- 尚未完成知识资产沉淀和真实离线评测

## 下一步：阶段2.13.3

1. 在隔离测试数据库验证建表SQL和MySQLTaskRepository真实读写
2. 通过第一个Application Service实例创建并推进任务
3. 销毁应用实例后重新装配，通过同一task_id加载快照
4. 验证等待用户、完成和失败任务的恢复语义
5. version冲突、execution_id和执行租约仍留到2.13.4

进入2.13.3时不要同时实现KnowledgeAsset、Milvus V2、FastAPI或Vue。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
