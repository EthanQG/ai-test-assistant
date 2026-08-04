# Test Analysis Agent 当前开发状态

更新时间：2026-08-04

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git 基线

- 分支：`main`
- 当前远端基线：`77d0ac4 阶段2.13.4：实现任务重复执行保护`
- 阶段2.13.5代码、双测试入口和文档已完成

## 当前阶段：2.13.5 pytest测试工程升级

本阶段没有改写Agent业务代码，也没有一次性迁移原有unittest。主要完成：

1. 新增`requirements-dev.txt`，pytest只作为开发依赖，不进入生产运行依赖。
2. 新增`pytest.ini`，统一测试目录、严格marker和测试类命名规则。
3. 新增`tests/conftest.py`，提供隔离的内存Repository和TaskRecord工厂fixture。
4. 自动将测试分为`unit`、`app`和`integration`，不需要给260项旧测试逐个添加装饰器。
5. 新增3项pytest原生示例，展示fixture、普通`assert`和`pytest.raises`。
6. 修正3个只在pytest收集时暴露的命名冲突，生产代码未修改。

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
pytest完整：257 passed，6 skipped，共收集263项
pytest unit：234 passed，29 deselected
pytest app：23 passed，240 deselected
pytest integration：6 skipped，257 deselected
```

新增的3项pytest原生测试不由unittest收集，因此两个入口的总数相差3项，这是预期行为。

## 当前架构能力

- Streamlit只调用Application Service并读取TaskView
- TaskRepository隔离InMemory和MySQL实现
- schema v1快照可恢复完整TaskRecord和领域类型
- MySQL保存任务快照、AgentEvent和执行租约记录
- version乐观锁、execution_id幂等和可过期租约已通过真实MySQL验证
- unittest与pytest双入口均可运行，外部数据库测试保持显式隔离

## 当前限制

- 当前只保证节点结果幂等提交，不保证外部LLM请求Exactly Once
- 租约默认600秒且没有后台续租
- pytest只是统一入口和渐进迁移起点，绝大多数测试仍使用unittest.TestCase
- 尚未配置CI流水线；等仓库测试命令稳定后再单独评估
- 尚未实现KnowledgeAsset沉淀、Milvus V2、ContextBuilder、离线评测、FastAPI、SSE和Vue

## 下一步：阶段2.14.1 KnowledgeAsset模型与准入规则

下一阶段只设计并实现可沉淀的知识资产模型和准入条件：

1. 只有Reviewer通过且用户明确确认的任务才能沉淀；
2. 资产记录来源task_id、内容哈希、版本、结构化需求和测试点；
3. 先定义Repository边界和Fake测试，不同时接入Milvus索引；
4. 不修改现有Agent节点顺序，不实现FastAPI或Vue。

MySQL知识资产表和Milvus V2索引分别留到2.14.2、2.14.3。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件和秋招路线图。
