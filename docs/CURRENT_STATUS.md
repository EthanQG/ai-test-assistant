# Test Analysis Agent 当前开发状态

更新时间：2026-08-05

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)
为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.14.1本地提交：`549207a 阶段2.14.1：建立知识资产准入边界`
- 阶段2.14.2本地提交：`f88a426 阶段2.14.2：实现知识资产MySQL权威存储`
- 阶段2.14.3代码、测试和文档已完成，尚未提交

## 当前阶段：2.14.3 Milvus V2知识资产索引

本阶段只建立已确认KnowledgeAsset的向量索引写入边界，不修改Streamlit、Agent节点和现有RAG检索节点。主要完成：

1. 新增确定性的KnowledgeAssetChunkBuilder，不调用LLM拆分内容。
2. 按需求概览、需求事实、业务规则、风险和测试点构建语义完整Chunk。
3. 每个Chunk保留`asset_id`、来源任务、资产版本、`content_hash`、类型和序号。
4. 默认最多32个Chunk、单条最多1600字符，并记录省略数量和文本截断标记。
5. 使用Ollama`/api/embed`批量接口，一次请求生成本批次全部向量。
6. 新建独立`knowledge_assets_v2`集合，旧`ai_test_cases`集合保持不动。
7. Milvus只保存检索文本、向量和关联元数据，不保存完整报告。
8. Milvus写入成功后将MySQL资产从`pending_index`更新为`indexed`；失败时更新为`index_failed`。
9. 已经是`indexed`的资产不会重复生成Embedding和写入Milvus。
10. MySQL状态更新使用期望状态保护，避免旧调用覆盖新状态。

## 索引数据流

```text
MySQL读取pending_index KnowledgeAsset
→ ChunkBuilder生成有界语义Chunk
→ Ollama一次批量生成Embedding
→ Milvus V2按稳定chunk_id执行upsert
→ MySQL状态更新为indexed
```

如果Embedding或Milvus失败：

```text
完整KnowledgeAsset继续保留在MySQL
→ 状态改为index_failed
→ 不会把未完成索引的资产用于后续检索
```

Milvus与MySQL通过`asset_id + asset_version + content_hash`关联。后续检索命中Milvus后必须按`asset_id`回查MySQL，并验证版本、哈希和状态。

## 性能边界

- Chunk拆分是确定性Python处理，不增加LLM调用
- 一份资产默认最多32个Chunk，防止长PRD导致无界Embedding请求
- 全部Chunk通过一次批量`/api/embed`请求提交，不逐条请求
- 单条检索文本最多1600字符，完整原始内容仍只保存在MySQL
- 当前只记录整个索引用例耗时；Embedding与Milvus分层耗时留到2.15

## 验证结果

```text
unittest：260 tests，OK，6项真实MySQL任务测试默认跳过
pytest完整：322 passed，8 skipped，共收集330项
2.14.3新增：20 passed
compileall：通过
git diff --check：通过
```

默认测试使用Fake Embedding和Fake Milvus，没有调用真实DeepSeek、Ollama、Milvus或MySQL。

## 当前架构能力

- KnowledgeAsset准入、版本化JSON、MySQL权威存储和V2索引写入边界已经分层
- Application层只依赖Embedding和VectorIndex Protocol，不直接调用requests或MilvusClient
- Ollama和Milvus具体实现位于services适配层
- MySQL Repository支持带期望状态的原子状态更新
- Milvus Chunk使用稳定ID执行upsert，为跨存储失败后的安全重放保留基础
- 旧Workflow Milvus集合继续只读兼容，新资产不会写入旧集合

## 当前限制

- 本轮没有连接真实Ollama、Milvus或MySQL执行端到端索引测试
- 还没有实现Milvus查询、相似度阈值、Top-K聚合和MySQL批量回查
- `index_failed`资产的显式重试、request_id和索引清理留到2.14.5
- MySQL与Milvus无法使用同一数据库事务；当前依赖稳定chunk_id的upsert为后续补偿重试提供基础
- Streamlit仍没有“保存到知识库”按钮，也不会自动执行索引服务
- 尚未实现ContextBuilder、Token统计、离线评测、FastAPI、SSE和Vue

## 下一步：阶段2.14.4 历史资产检索与上下文组装

下一阶段只实现：

1. 将当前结构化需求转换为查询文本并生成一次查询向量；
2. 从`knowledge_assets_v2`执行Top-K余弦相似度检索；
3. 按阈值过滤，并按`asset_id`聚合多个Chunk命中；
4. 批量回查MySQL完整KnowledgeAsset；
5. 校验`indexed`状态、版本和`content_hash`，丢弃孤立或过期索引；
6. 返回带来源的结构化候选，不增加LLM精排；
7. ContextBuilder的完整Token预算与裁剪仍留在2.15。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
