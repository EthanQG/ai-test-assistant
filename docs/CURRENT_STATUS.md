# Test Analysis Agent 当前开发状态

更新时间：2026-08-04

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git 基线

- 分支：`main`
- 当前远端基线：`bb30a5b 阶段2.13.3：验证MySQL任务恢复`
- 阶段2.13.4代码、测试、真实MySQL验收和文档已完成

## 当前阶段：2.13.4 重复执行保护

本阶段在不修改 AgentState、节点顺序和 Streamlit 页面行为的前提下，完成了三层保护：

1. **乐观锁**：Repository 读取任务时同时返回数据库 `version`；保存时使用
   `expected_version` 条件更新。旧快照写入会抛出 `TaskVersionConflictError`，不能覆盖新结果。
2. **execution_id 幂等**：每次节点推进对应一个执行编号。已经完成的同一
   `execution_id` 再次提交时不再执行 Orchestrator 节点。
3. **执行租约**：执行记录包含 worker、开始时间和过期时间。未过期租约阻止其他执行者进入；
   租约过期后可由新执行者接管，旧执行者不能提交结果。

这些元数据属于 Repository 执行控制，不进入 AgentState，也不改变
`TaskSnapshotSerializer` 的 `schema_version=1`。

## 当前依赖方向

```text
views/Streamlit
  → application/TestAnalysisApplicationService
  → repositories/TaskRepository
      → InMemoryTaskRepository
      → MySQLTaskRepository
          → agent_tasks
          → agent_task_events
          → agent_task_executions
  → agent/AgentOrchestrator 与受控节点
  → services/LLM、RAG、Prompt、文档解析
```

页面仍然只持有 `task_id` 和纯 UI 状态，只读取 `TaskView`，没有新增节点级调用入口。

## Repository 契约

- `get_versioned(task_id)`：返回隔离的 `TaskRecord` 和当前持久化版本
- `save(record, expected_version)`：条件保存普通用户动作并返回新版本
- `acquire_execution(...)`：原子领取 `execution_id` 对应的执行租约
- `complete_execution(record, lease, ...)`：校验版本和租约后原子提交快照、事件和执行结果
- `get/list/create/delete`：保留原有任务读取与管理语义

MySQL 新增 `agent_task_executions`，保存执行动作、状态、租约持有者、租约过期时间、错误类型和完成时间。
建表使用 `CREATE TABLE IF NOT EXISTS`，已有 `agent_tasks` 和 `agent_task_events` 无需重建。

## Application Service 行为

- `advance_task(task_id, execution_id=None)` 仍然只表达“推进任务”用户动作；调用方不能指定节点。
- 未显式传入 `execution_id` 时，由 Application Service 生成 UUID；未来 API 可把请求幂等键传入该参数。
- Application Service 领取租约后才调用 Orchestrator，完成后通过同一租约提交结果。
- 同一执行已完成时返回当前任务；其他执行仍持有租约时返回 `in_progress=True` 的只读 View。
- 补充信息、业务规则确认和人工反馈等普通修改也使用 `expected_version` 防止旧数据覆盖。

## 验证状态

```text
python -m unittest discover -s tests -v
260 tests discovered, OK（其中6项真实MySQL集成测试默认跳过）
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m unittest tests.test_mysql_task_repository_integration -v
6 integration tests passed
```

新增证据包括：

- 内存与 Fake MySQL Repository 的旧版本冲突测试
- 相同 `execution_id` 不重复提交测试
- 活跃租约阻断并发执行测试
- 租约过期接管及旧租约失效测试
- Application Service 不重复调用 Orchestrator 节点测试
- 3项新的真实 MySQL 乐观锁、幂等与租约恢复测试

真实MySQL 8.0.32的6项集成测试已经通过，并成功创建`agent_task_executions`；测试临时任务已按精确
`task_id`清理。本轮没有调用真实DeepSeek、Milvus或Embedding。

## 能力边界

- 当前保证的是“节点结果的幂等提交”，不是外部 LLM 请求 Exactly Once。
- 租约默认 600 秒，当前没有后台续租；模型调用超过租约时结果会被拒绝提交，需要后续结合后台任务设计续租。
- `execution_id` 当前由同步 Application Service 自动生成；真正的网络请求重试复用同一编号要等 FastAPI 接入后由 API 层传递。
- 默认 Repository 仍是会话级内存实现；只有显式配置 MySQL 才具备跨进程持久化和租约记录。
- 尚未实现 KnowledgeAsset 沉淀、Milvus V2、ContextBuilder、离线评测、FastAPI、SSE 和 Vue。

## 下一步：阶段2.13.5 测试工程升级

根据当前测试规模，下一小阶段再引入 pytest，目标是：

1. 保留现有 unittest 用例可运行，不一次性重写全部测试；
2. 增加 pytest 配置、marker 和公共 fixture；
3. 区分 unit、AppTest 和显式 MySQL integration 测试；
4. 使用 pytest 统一运行现有 unittest，并选择少量重复样板高的测试做示范迁移；
5. 不修改 Agent 业务逻辑，不在同一阶段实现知识资产或 FastAPI。

完成2.13.5后，再进入阶段2.14的 KnowledgeAsset 与 Milvus 知识沉淀闭环。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让 Codex 按照 `AGENTS.md` 初始化上下文，并读取本文件和秋招路线图。
