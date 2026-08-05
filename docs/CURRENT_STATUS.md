# Test Analysis Agent 当前开发状态

更新时间：2026-08-05

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git 基线

- 分支：`main`
- 当前远端基线：`4d3cdb9 阶段2.13.6：整理测试目录分层`
- 阶段2.14.1代码、测试和文档已完成，尚未提交

## 当前阶段：2.14.1 KnowledgeAsset模型与准入规则

本阶段只建立知识资产后端边界，没有接入页面、MySQL资产表或Milvus索引。主要完成：

1. 新增KnowledgeAsset、StructuredRequirement和KnowledgeAssetStatus领域模型。
2. 保存来源task_id、资产版本、原始需求、结构化需求、测试点、Reviewer证据、最终报告和确认时间。
3. 使用规范JSON和SHA-256生成稳定content_hash，不把asset_id、状态和时间混入内容身份。
4. 准入策略要求任务已完成、Reviewer通过、覆盖完整、无幻觉问题、无待处理反馈、最终结果未过期。
5. 用户必须同时确认知识沉淀和数据安全，任一确认缺失都会拒绝创建资产。
6. 新增KnowledgeAssetRepository抽象和返回隔离副本的InMemory实现。
7. 新增独立KnowledgeAssetApplicationService，页面未来只需表达确认动作，不直接访问Repository。

## 测试入口

安装开发依赖：

```powershell
pip install -r requirements-dev.txt
```

完整pytest入口：

```powershell
python -m pytest
```

按层运行：

```powershell
python -m pytest -m unit
python -m pytest -m app
python -m pytest -m integration
```

真实MySQL仍需显式开启：

```powershell
$env:RUN_MYSQL_INTEGRATION_TESTS='1'
python -m pytest -m integration
```

原unittest入口继续保留：

```powershell
python -m unittest discover -s tests -v
```

## 验证结果

```text
unittest：260 tests，OK（6项真实MySQL测试默认跳过）
pytest完整：283 passed，6 skipped，共收集289项
2.14.1新增pytest：26 passed
```

2.14.1新测试均采用pytest函数风格，因此不会被unittest discover收集；原有260项unittest回归保持不变。

## 当前架构能力

- Streamlit只调用Application Service并读取TaskView
- TaskRepository隔离InMemory和MySQL实现
- schema v1快照可恢复完整TaskRecord和领域类型
- MySQL保存任务快照、AgentEvent和执行租约记录
- version乐观锁、execution_id幂等和可过期租约已通过真实MySQL验证
- unittest与pytest双入口均可运行，外部数据库测试保持显式隔离
- KnowledgeAsset准入和存储已通过独立领域、Application Service与Repository边界隔离

## 当前限制

- 当前只保证节点结果幂等提交，不保证外部LLM请求Exactly Once
- 租约默认600秒且没有后台续租
- pytest只是统一入口和渐进迁移起点，绝大多数测试仍使用unittest.TestCase
- 公共fixture当前数量较少，继续保留在根`tests/conftest.py`；只有出现明确的层级专用fixture时再下沉
- 尚未配置CI流水线；等仓库测试命令稳定后再单独评估
- KnowledgeAsset当前只保存在进程内存，服务重启后丢失，页面也没有确认入口
- content_hash和来源版本的并发唯一性尚未由数据库约束保证
- 尚未实现KnowledgeAsset MySQL存储、Milvus V2、ContextBuilder、离线评测、FastAPI、SSE和Vue

## 下一步：阶段2.14.2 MySQL KnowledgeAsset权威存储

下一阶段只把现有KnowledgeAsset Repository契约接入MySQL：

1. 增加knowledge_assets权威表和必要唯一索引；
2. 完整资产JSON、摘要字段、content_hash、来源任务和索引状态原子保存；
3. 实现MySQLKnowledgeAssetRepository和显式开启的真实MySQL CRUD测试；
4. 不接入Milvus，不修改Agent节点、Streamlit页面、FastAPI或Vue。

Milvus V2索引和页面确认入口继续留在后续独立阶段。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
