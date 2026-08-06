# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git 基线

- 分支：`main`
- 阶段2.14.3提交：`66f12fa 阶段2.14.3：建立Milvus V2知识资产索引`
- 阶段2.14.4提交：`aa2abd9 阶段2.14.4：实现知识资产可信检索`
- 本次图文PRD路线图校正只修改文档，尚未提交

## 当前阶段：2.14.4 V2候选召回与权威来源回查

本阶段建立了独立的历史知识资产查询边界，不修改Streamlit、Agent节点、
Orchestrator和现有legacy RAG流程。主要完成：

1. 当前查询文本只执行一次批量Embedding调用；
2. 从`knowledge_assets_v2`执行一次COSINE向量检索；
3. 对原始命中按最低分数阈值过滤；
4. 同一`asset_id`的多个Chunk聚合为一个候选资产；
5. 使用`KnowledgeAssetRepository.get_many()`一次批量读取完整资产；
6. 只接受MySQL中仍为`indexed`的资产；
7. 校验`source_task_id + asset_version + content_hash`，丢弃孤儿或过期向量；
8. 返回完整权威资产、最高相似度和最多3条匹配Chunk；
9. 不增加LLM精排，不逐条查询MySQL，不修改AgentState。

## 检索数据流

```text
查询文本
→ Ollama一次Embedding请求
→ Milvus V2一次Top-N短片段召回
→ 分数阈值过滤并按asset_id聚合
→ MySQL一次批量回查完整KnowledgeAsset
→ 校验indexed状态、来源任务、版本和content_hash
→ 返回最多Top-K个可信候选及命中来源
```

Milvus负责“快速找到可能相关的短片段”，MySQL负责“确认这个片段对应的完整
资产仍然真实、有效且版本一致”。Milvus中的短文本不作为最终权威内容使用。

## 性能边界

- 默认`raw_limit=20`、`top_k=3`、`min_score=0.65`
- 一次查询只发起一次Embedding请求、一次Milvus搜索和一次MySQL批量查询
- 不使用LLM重排，因此本阶段没有新增一次聊天模型调用
- 同一资产最多向后续层提供3条匹配Chunk，完整ContextBuilder裁剪留到2.15
- `0.65`只是可配置基线，不是经过离线评测证明的最佳阈值

## 验证结果

```text
python -m pytest -q
337 passed，8 skipped，共收集345项

python -m unittest discover -s tests -v
260 tests，OK，6 skipped

python -m compileall -q agent application knowledge_assets repositories services utils views tests main.py
通过

git diff --check
通过
```

默认测试使用Fake Embedding、Fake Milvus和Fake MySQL，没有调用真实DeepSeek、
Ollama、Milvus或MySQL。

## 当前架构能力

- MySQL保存完整、可恢复、可审计的KnowledgeAsset JSON
- Milvus V2保存向量、短检索文本和稳定关联元数据
- Repository提供单次批量回查，避免N+1查询
- Application检索用例只依赖Embedding、VectorSearch和Repository抽象
- 孤儿、未索引、已过期版本和哈希不一致的向量命中不会进入可信候选
- legacy `ai_test_cases`集合和当前KnowledgeRetriever保持不动

## 当前限制

- 本轮没有连接真实Ollama、Milvus或MySQL执行端到端检索
- V2检索服务尚未接入当前Agent的KnowledgeRetriever，当前主流程行为不变
- 查询文本目前由调用方提供；节点级ContextBuilder与字段白名单留到2.15
- 当前文档解析只支持TXT/Markdown文本、PDF文本层和DOCX普通段落；尚不支持Word表格、扫描PDF、OCR、流程图或UI图理解
- `index_failed`重试、request_id和孤立索引清理留到2.14.5
- 页面仍没有“保存到知识库”按钮，也不会自动发布知识资产
- 尚未实现RAG离线评测，不能声称`0.65`阈值或V2召回效果优于旧方案

## 下一步：阶段2.14.5 发布补偿与失败重试

下一阶段只处理知识资产闭环可靠性：

1. 为`index_failed`资产提供显式、受控的重试入口；
2. 使用稳定Chunk ID保证重试upsert不制造重复向量；
3. 增加发布/索引请求标识和重复请求保护；
4. 定义MySQL成功但Milvus失败时的补偿和审计结果；
5. 设计孤立或过期V2向量的清理边界；
6. 不在该阶段接入页面、FastAPI、后台任务或LLM重排。

## 后续顺序校正：阶段2.15优先完善图文PRD输入

阶段2.14.5完成后，不再直接从纯文本进入原计划的ContextBuilder。阶段2.15调整为：

1. `2.15.1`：统一`DocumentContent`，表达段落、表格、图片、页码、来源和解析警告；
2. `2.15.2`：PDF/DOCX结构化解析与图片提取；
3. `2.15.3`：扫描PDF和图片OCR，保留置信度；
4. `2.15.4`：流程图、状态图、时序图和UI图的受控多模态理解；
5. `2.15.5`：关键问题筛选与限流，默认一轮最多3个阻塞问题；
6. `2.15.6`：ContextBuilder与节点Token预算；
7. `2.15.7`：文档解析、OCR、视觉模型和现有外部服务的分层可观测性。

当前这些能力均为规划中，不能描述为已经支持所有PDF图片。目标是自动处理高置信度内容，
对中置信度内容带风险继续，仅在核心规则、关键数字、流程分支或图文冲突无法确认时集中询问用户。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
