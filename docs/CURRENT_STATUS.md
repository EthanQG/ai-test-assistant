# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md)为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)为准，
完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.14.4提交：`aa2abd9 阶段2.14.4：实现知识资产可信检索`
- 图文PRD路线图校正提交：`ec633e7 文档：调整图文PRD理解开发路线`
- 阶段2.14.5代码、测试与文档已完成，提交见最新Git记录

## 当前阶段：2.14.5 索引失败重试与补偿审计

本阶段只收尾知识资产索引可靠性，不修改Streamlit、Agent节点、Orchestrator和当前
KnowledgeRetriever。主要完成：

1. 只有`index_failed`资产可以通过显式入口重新索引；
2. 每次重试使用独立`request_id`，MySQL保存`running/succeeded/failed`审计记录；
3. 同一`request_id`重复提交不会再次调用Embedding或Milvus；
4. 失败请求必须更换新`request_id`，防止同一请求重复消费；
5. 重试开始时，资产从`index_failed`切回`pending_index`，该状态变化与请求创建在同一MySQL事务中；
6. 继续使用稳定Chunk ID和Milvus upsert，重放不会生成另一组重复主键；
7. 资产停用时先把MySQL状态改为`retired`，再按`asset_id + asset_version`删除Milvus向量；
8. 即使向量清理失败，权威状态已经阻止该资产继续被可信检索，之后可再次执行清理。

## 重试与停用数据流

```text
显式重试(index_failed, request_id)
→ MySQL事务：资产改为pending_index + 创建running审计
→ 构建稳定Chunk ID
→ 一次批量Embedding + Milvus upsert
→ 成功：资产indexed + 请求succeeded
→ 失败：资产index_failed + 请求failed

停用(indexed)
→ MySQL先改为retired
→ Milvus按asset_id和asset_version删除向量
→ 清理失败可重试，但retired资产不会进入可信召回
```

MySQL仍是资产是否有效的权威来源。Milvus清理属于可补偿操作，不与MySQL伪装成跨库ACID事务。

## 新增数据边界

- 新表`knowledge_asset_index_requests`保存请求ID、资产ID、状态、Chunk数量、错误类型/摘要和起止时间
- `KnowledgeAssetRepository`增加开始重试、结束请求和查询审计的方法
- 内存实现用于稳定单元测试，MySQL实现使用事务与行锁保护重试创建
- Milvus V2适配器增加按资产版本删除接口
- 没有新增页面按钮、后台任务、FastAPI或自动重试

## 验证结果

```text
python -m pytest -q
353 passed，9 skipped，共收集362项

python -m unittest discover -s tests -v
260 tests，OK，6 skipped
```

默认测试只使用Fake Embedding、Fake Milvus和Fake MySQL，没有访问真实DeepSeek、Ollama、
Milvus或MySQL。真实MySQL重试审计测试已加入`integration`目录，默认跳过。

## 当前限制

- 页面尚无“保存到知识库”“重试索引”或“停用资产”入口
- V2检索服务尚未接入当前Agent的KnowledgeRetriever
- 没有后台补偿Worker；失败重试和清理必须由未来调用方显式触发
- 进程若在创建`running`请求后、真正索引前崩溃，仍需要后续租约或运维恢复策略；本阶段只自动修复资产已明确为`indexed/index_failed`的中断审计
- 当前只实现已知资产版本的停用清理，没有实现扫描Milvus全部孤儿向量的后台清扫器
- 尚未执行真实MySQL与Milvus联合故障演练
- `0.65`检索阈值尚无离线评测证据
- 当前文档解析仍不支持Word表格、扫描PDF、OCR、流程图或UI图理解

## 下一步：阶段2.15.1 统一DocumentContent

下一阶段先建立统一图文文档输入模型：

1. 表达标题、段落、列表、表格、图片、页码、来源和解析警告；
2. 保留元素原始顺序和稳定来源ID；
3. 将现有TXT/Markdown/PDF/DOCX文字能力适配到新边界；
4. 本小阶段不接OCR和视觉模型，不修改Agent业务规则；
5. 后续再依次实现结构化解析、OCR、受控多模态理解、问题限流、ContextBuilder和可观测性。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
