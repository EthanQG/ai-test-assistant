# Test Analysis Agent 当前开发状态

更新时间：2026-07-29

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.12开发前提交：`0d7c36c 文档：修正学习复盘章节顺序`
- 本轮阶段2.12代码和文档尚未提交
- 开发开始前工作区干净

## 当前阶段

阶段2.12“后端调用边界”已经完成：

- 增加`TestAnalysisApplicationService`
- 增加Command、只读`TaskView`和节点执行指标
- 定义`TaskRepository`并实现会话级`InMemoryTaskRepository`
- Streamlit只通过Application Service创建、推进、补充、确认和反馈
- 移除页面`_task_store()`及对Orchestrator、节点和FeedbackHandler的直接调用
- 页面布局、CSS、测试点分页、Dialog和Agent业务规则保持不变

下一阶段为2.13 MySQL任务持久化与恢复。本轮未实现MySQL、FastAPI、后台任务、SSE或Vue。

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
181 tests passed
```

新增测试覆盖Application Service用例、Repository复制与会话隔离、业务规则门禁、评审与修正
路径、失败指标，以及Streamlit架构边界。自动化测试不访问真实DeepSeek、Milvus或Embedding。

## 当前限制

- InMemory Repository按Streamlit会话装配，只支持当前会话内的rerun和task_id恢复
- 新浏览器会话、硬刷新导致会话重建或Streamlit服务重启后，内存任务不可恢复
- `expected_version`只在Repository接口中预留，当前内存实现没有并发版本控制
- `in_progress`只能保护同一会话的同步调用，不能处理跨进程并发
- AgentState仍只有`to_dict()`，缺少完整快照恢复
- 尚未记录LLM、Embedding、Milvus、Token和重试的分层指标
- 尚未完成知识资产沉淀和真实离线评测

## 下一步：阶段2.13

1. 增加AgentState完整快照序列化与schema version
2. 设计MySQL任务表与独立事件表
3. 实现MySQLTaskRepository
4. 每个节点完成后保存快照与新增事件
5. 实现服务重启恢复
6. 增加version、execution_id和执行租约

进入2.13前不要实现KnowledgeAsset、Milvus V2、FastAPI或Vue。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
