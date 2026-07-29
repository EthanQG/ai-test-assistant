# Test Analysis Agent 当前开发状态

更新时间：2026-07-29

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 当前提交：`c8477b9 优化：完成Streamlit演示页面收尾`
- 当前提交与`origin/main`一致
- 文档同步开始前工作区干净

## 当前阶段

阶段2.11 Streamlit V1功能演示页面已经收尾。页面继续用于演示：

- PRD文本和文档输入
- Agent逐节点执行
- 待确认问题暂停和恢复
- 业务规则二次确认
- 结构化测试点、质量评审和受控修正
- 人工反馈和最终报告下载
- 当前节点、关键进展和完整执行详情

页面布局和视觉冻结。后续除Application Service调用入口替换，以及阶段2.14最小知识资产
确认入口外，不继续调整Streamlit布局和CSS。

## 当前真实能力边界

### 已实现

- 受控单Agent Agentic Workflow
- AgentState、AgentEvent和Python Orchestrator
- RequirementAnalyzer、KnowledgeRetriever、Generator、Reviewer、Reviser、Finalizer
- Human-in-the-loop暂停、恢复和业务规则确认
- Milvus历史资产检索，以及无命中和服务失败降级
- 结构化JSON校验、截断识别和一次受控重试
- Streamlit V1完整功能演示

### 尚未实现

- Application Service和TaskRepository
- MySQL任务快照、独立事件和跨服务重启恢复
- version、execution_id和执行租约
- 当前Agent结果经确认后沉淀为KnowledgeAsset
- MySQL权威知识资产与Milvus V2索引闭环
- ContextBuilder和节点级Token预算
- LLM、Embedding和Milvus分层耗时与真实Token统计
- 脱敏离线评测和三组消融实验
- FastAPI、后台任务、SSE和Vue

旧Workflow仍保留`RAGService.save_case()`和`TestAssistantManager.save_to_rag()`兼容方法，
但当前Agent页面没有调用，因此不能把知识资产沉淀描述为已实现。当前Milvus历史数据来自
既有集合或旧方式写入，本地Bug经验来自静态知识文件。

## 后续阶段

1. 阶段2.12：Application Service、TaskRepository和Streamlit调用入口迁移
2. 阶段2.13：MySQL任务持久化、服务重启恢复和重复执行保护
3. 阶段2.14：用户确认后的KnowledgeAsset、MySQL权威存储和Milvus V2索引
4. 阶段2.15：ContextBuilder、Token预算和分层可观测性
5. 阶段2.16：10～20份脱敏需求评测集、RAG/Reviewer评测和三组消融实验
6. 阶段2.17：前述阶段稳定后再评估FastAPI、后台任务、SSE和Vue

下一次代码开发从`2.12.1 Application Service接口`开始，不直接接MySQL或Milvus。

## 数据职责

- MySQL任务表：保存完整AgentState快照、决策、版本和恢复信息
- MySQL事件表：保存Agent、Orchestrator和外部调用事件
- MySQL知识资产表：保存用户确认后的完整结构化KnowledgeAsset
- Milvus：保存向量、asset_id、版本和必要索引元数据
- Streamlit session_state：只保存Tab、分页、Dialog、表单草稿和页面调度状态

检索时由Milvus比较当前需求向量和历史资产检索向量，返回相似`asset_id`；随后从MySQL读取
完整资产，由ContextBuilder完成阈值过滤、裁剪和来源标记。

## 验证状态

本次文档同步开始前和完成后均已执行：

```text
python -m unittest discover -s tests -v
166 tests passed
```

自动化测试不访问真实DeepSeek、Milvus或Embedding服务。

## 当前限制

- Streamlit仍同步执行LLM节点，单次模型调用可能持续较长时间，尚未建立正式性能基线
- 当前任务仍只保存在Streamlit服务进程内
- 当前`in_progress`不能处理跨进程并发和服务重启
- AgentState只有`to_dict()`，缺少完整快照恢复
- 当前Milvus实现同时存储向量和文本，尚未迁移为MySQL权威资产加Milvus索引的V2结构
- 尚无真实质量、Token、RAG召回或Reviewer效果数据

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
