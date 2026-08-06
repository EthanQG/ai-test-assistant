# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.15.2：`7826099 阶段2.15.2：完善PDF与DOCX结构化解析`
- 阶段2.15.3：`b823c2d 阶段2.15.3：增加扫描文档OCR与置信度分流`
- 阶段2.15.3验收：`98684e2 阶段2.15.3：完成真实OCR运行验收`
- 阶段2.15.4：`ca58c5f 阶段2.15.4：增加有界多模态理解`
- 阶段2.15.5：`f6d1650 阶段2.15.5：增加关键问题筛选与限流`
- 阶段2.15.6：`3961861 阶段2.15.6：增加节点上下文构建与输入预算`
- 阶段2.15.7代码、pytest与文档已完成，尚未创建本阶段提交

## 当前阶段：2.15.7 分层耗时、Token与错误分类

本阶段在不修改Streamlit、AgentState字段、快照schema、Orchestrator和节点顺序的前提下建立统一性能证据：

1. 新增`ServiceCallMetric`、`TokenUsage`、任务级`telemetry_scope`和统一错误类别；
2. Application Service按任务和当前动作采集指标，附加到已有完成/失败事件的`service_metrics`；
3. 上传文档解析指标附加到任务创建事件，可随schema v1快照和MySQL任务快照保存恢复；
4. 记录ContextBuilder、结构化JSON校验、LLM、RAG、Embedding、Milvus、文档解析、OCR和视觉调用耗时；
5. LLM/视觉API返回usage时标记`provider`，否则使用同一估算口径并标记`estimated`，两类不混算；
6. LLM记录模型和Prompt指纹，不保存Prompt正文、API Key、服务地址或响应原文；
7. JSON校验记录重试次数，ContextBuilder超预算、输出截断、传输、校验、OCR、视觉、Embedding和Milvus错误明确分类；
8. `TaskView.service_metrics`提供只读明细，`performance_summary`汇总依赖耗时、Token来源、重试和错误；
9. 节点总耗时继续使用既有`NodeExecutionMetric`，服务耗时用于解释节点内部时间分布；
10. 当前仍为同步串行执行，没有实现后台任务、SSE、轮询或页面性能面板。

## 当前数据流

```text
Application Service为task_id和action开启telemetry_scope
→ ContextBuilder / LLM / JSON校验 / RAG等服务记录ServiceCallMetric
→ 节点完成或失败
→ 指标附加到对应AgentEvent.service_metrics
→ TaskRepository保存原有TaskRecord快照
→ TaskView提供明细与performance_summary
```

## 验证结果

```text
python -m pytest -q
405 passed，10 skipped，共收集415项
```

新增pytest覆盖任务/action关联、provider与estimated Token区分、Prompt敏感信息隔离、JSON重试、错误分类、
节点事件附加、上传文档指标以及快照往返。全量测试使用Fake/Mock，没有调用真实LLM或外部服务。

## 当前限制

- Fake/Mock验证的是指标链路，当前尚无多份真实PRD的耗时分布和Token成本数据
- 视觉API未返回usage时，文本估算不包含图片Token，指标中会明确标记图片Token未计入
- 旧版`MilvusRAGManager`只能记录组合RAG耗时，内部Embedding与Milvus拆分依赖V2检索链路
- 当前指标保存在任务事件快照中，尚未建设独立时序指标表或监控平台
- 同步串行架构没有改变，埋点只能解释等待时间，不能直接消除等待
- ContextBuilder裁剪后的质量、RAG召回和Reviewer效果仍需2.16离线评测

## 下一步：阶段2.16.1 脱敏评测集与人工标注契约

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 定义10～20份脱敏图文需求的数据结构；
2. 定义事实、规则、风险、关键问题、必要场景和禁止断言的人工标注格式；
3. 明确客观指标和主观指标评分规则；
4. 先建立小型样例与校验器，再运行真实模型实验；
5. 不使用另一个LLM随意代替人工金标准。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
