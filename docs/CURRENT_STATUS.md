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
- 阶段2.13.2提交：`885c5ca 阶段2.13.2：实现MySQL任务与事件持久化`
- 阶段2.13.3真实MySQL CRUD与跨Application Service实例恢复验证已经完成，待提交

## 当前阶段

阶段2.13.3“真实MySQL CRUD与任务恢复”已经完成：

- 使用真实MySQL 8.0.32验证TaskRecord的create/get/save/list/delete
- 验证`agent_tasks.version`随保存从1递增到2，`event_count`与事件表记录数量一致
- 验证删除任务后外键级联删除对应`agent_task_events`
- 第一个Application Service创建任务、推进到等待状态并提交用户补充后，重新创建Repository和Application Service，仍可按同一task_id恢复并通过Orchestrator继续
- 新Application Service可恢复completed和failed任务，调用`advance_task`不会创建Orchestrator或重复执行节点
- 新增3项显式开启的真实MySQL集成测试，使用独立UUID并在结束后精确清理
- 日常完整测试默认跳过真实MySQL集成测试，避免单元测试依赖网络和本机配置

本轮没有实现乐观锁、execution_id、执行租约、FastAPI、后台任务、SSE或Vue。

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
248 tests discovered, OK（其中3项真实MySQL测试默认跳过）

$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m unittest tests.test_mysql_task_repository_integration -v
3 integration tests passed
```

3项真实MySQL测试只访问MySQL，不调用DeepSeek、Milvus或Embedding；测试数据使用独立UUID并已清理。

## 当前限制

- 默认仍为InMemory Repository；只有显式配置MySQL后才会持久化任务
- `expected_version`仍未执行并发版本校验；当前`version`只递增，不能阻止旧快照覆盖
- `in_progress`只能保护同一会话的同步调用，不能处理跨进程并发
- 快照只定义结构版本`schema_version=1`，尚无历史版本迁移
- `in_progress`不持久化；跨进程执行保护留给后续执行租约
- 当前证据验证了销毁并重建Repository/Application Service后的恢复；尚未引入独立Worker或多进程执行模型
- RAG当前只保存拼接后的`rag_context`、命中数、最高分、状态和错误，没有逐条来源对象
- 尚未记录LLM、Embedding、Milvus、Token和重试的分层指标
- 尚未完成知识资产沉淀和真实离线评测

## 下一步：阶段2.13.4

1. 让Repository的`expected_version`参与条件更新，旧快照保存时明确冲突
2. 设计并保存`execution_id`，避免同一执行请求重复提交节点结果
3. 增加有过期时间的执行租约，处理进程异常后的任务释放
4. 明确只能保证节点结果幂等提交，不宣称外部LLM请求Exactly Once
5. 增加并发、重复请求和租约过期恢复测试

进入2.13.4时不要同时实现KnowledgeAsset、Milvus V2、FastAPI或Vue。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
