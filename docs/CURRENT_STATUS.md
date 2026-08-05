# Test Analysis Agent 当前开发状态

更新时间：2026-08-05

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.14.1本地提交：`549207a 阶段2.14.1：建立知识资产准入边界`
- 阶段2.14.2代码、测试和文档已完成，尚未提交

## 当前阶段：2.14.2 MySQL KnowledgeAsset权威存储

本阶段只将2.14.1的KnowledgeAsset Repository契约接入MySQL，不接入页面按钮、Embedding或Milvus。主要完成：

1. 新增schema v1知识资产JSON快照，可将完整KnowledgeAsset恢复为原领域类型。
2. 新增`knowledge_assets`权威表，完整资产保存在`asset_json`，常用摘要字段独立成列。
3. 使用`content_hash`唯一索引阻止相同内容重复沉淀。
4. 使用`source_task_id + asset_version`唯一索引保护同一任务的资产版本。
5. 新增`MySQLKnowledgeAssetRepository`，实现建表、创建、按ID读取、按哈希查询、按来源任务查询最新版和列表查询。
6. 新增`KNOWLEDGE_ASSET_REPOSITORY_BACKEND`独立配置，默认仍为`memory`，显式设为`mysql`才连接数据库。
7. 新增Fake MySQL单元测试和默认跳过的真实MySQL CRUD集成测试。

新建资产仍保持`pending_index`，只表示完整权威内容已经具备持久化条件，不代表Milvus索引已完成。

## 数据库职责

`knowledge_assets`保存：

- 完整版本化`asset_json`；
- 来源任务、资产版本和内容哈希；
- 当前索引状态；
- 需求摘要、Reviewer评分和测试点数量；
- 用户确认时间、创建时间和数据库更新时间。

没有给`source_task_id`增加外键：历史知识资产一旦通过确认，应在原任务被清理后继续保留。MySQL是完整资产的权威数据源；Milvus后续只保存向量和`asset_id`等检索元数据。

## 测试入口

```powershell
pip install -r requirements-dev.txt
python -m pytest
python -m pytest -m unit
python -m pytest -m app
python -m pytest -m integration
python -m unittest discover -s tests -v
```

真实MySQL测试必须显式开启：

```powershell
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m pytest -m integration
```

## 验证结果

```text
unittest：260 tests，OK，6项真实MySQL任务测试默认跳过
pytest完整：302 passed，8 skipped，共收集310项
2.14.2新增：19 passed，2项真实MySQL知识资产测试默认跳过
compileall：通过
git diff --check：通过
```

默认测试没有调用真实DeepSeek、Embedding、Milvus或MySQL。

## 当前架构能力

- Streamlit只调用Application Service并读取TaskView
- TaskRepository隔离InMemory和MySQL任务实现
- schema v1任务快照、事件、version、execution_id和执行租约已经可用
- KnowledgeAsset具备准入策略、稳定内容哈希、版本化JSON快照和Repository抽象
- KnowledgeAsset Repository可以在内存和MySQL实现之间切换
- MySQL通过唯一索引为内容去重和来源任务版本提供最终约束
- Application Service不依赖具体MySQL实现

## 当前限制

- Streamlit还没有“保存到知识库”按钮，当前页面不会触发KnowledgeAsset发布
- `.env`默认使用内存资产Repository；只有显式配置MySQL并组装资产服务时才会创建资产表
- 真实MySQL KnowledgeAsset CRUD测试已经编写，但本轮未主动连接用户数据库执行
- 同一来源任务的“查询最新版后加一”不是单条原子操作；并发冲突会由唯一索引拒绝，调用方重试策略尚未实现
- 尚未实现索引状态更新、Embedding、Milvus V2写入、失败重试和后续RAG检索
- 尚未实现ContextBuilder、离线评测、FastAPI、SSE和Vue

## 下一步：阶段2.14.3 Milvus V2索引边界

下一阶段建议只实现：

1. 从MySQL读取`pending_index`资产；
2. 为结构化需求和测试点构建受控索引文本；
3. 生成Embedding并将向量、`asset_id`、版本和来源写入Milvus V2集合；
4. 成功后把MySQL状态更新为`indexed`，失败时记录`index_failed`和可重试错误；
5. 按`asset_id`回查MySQL完整内容，Milvus不保存完整报告；
6. 不修改Agent节点顺序，不接入FastAPI、SSE或Vue。

页面“保存到知识库”按钮建议在MySQL与Milvus闭环稳定后再接入，避免用户看到虚假的保存成功。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
