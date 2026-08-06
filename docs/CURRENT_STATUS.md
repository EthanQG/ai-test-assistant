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
- 阶段2.15.6代码、pytest与文档已完成，尚未创建本阶段提交

## 当前阶段：2.15.6 ContextBuilder与节点输入预算

本阶段为五个LLM/RAG节点增加统一`ContextBuilder`，没有修改Streamlit、AgentState、Orchestrator状态转换、
节点顺序或LLM调用次数：

1. 需求分析、知识检索、测试点生成、质量评审和测试点修正分别使用字段白名单；
2. 不再由各节点重复拼装完整需求分析字典，也不会把完整State、事件、报告和无关历史发送给模型；
3. 原始需求、检索需求、本地缺陷知识和RAG上下文设置确定性字符上限；
4. 裁剪优先保留含数值、业务规则、状态、权限、幂等、来源、OCR和视觉标记的片段；
5. Reviewer/Reviser使用的测试点和反馈属于受保护结构化上下文，超过预算会明确失败，不静默删测试点；
6. 以64K上下文基线，预留节点输出Token和4096安全余量，再叠加节点输入策略上限；
7. 当前Token数是确定性的本地估算，不冒充模型API返回的真实usage；
8. 每个节点完成事件记录裁剪前后字符数、估算Token、输入预算和裁剪区段；
9. ContextBuilder返回深拷贝的列表和字典，节点不能通过上下文副本意外修改State；
10. 当前RAG仍保持`top_k=2`基线，真实Token、模型耗时和外部服务耗时留到2.15.7。

## 当前数据流

```text
AgentState
→ ContextBuilder按节点读取字段白名单
→ 长文本按区段上限裁剪并保留关键规则/数字/来源
→ 校验节点输入预算
→ PromptService构造Prompt
→ LLM或RAG服务
→ 节点完成事件记录context_metrics
```

## 验证结果

```text
python -m pytest -q
396 passed，10 skipped，共收集406项
```

新增pytest覆盖节点字段白名单、需求关键规则保留、本地知识与RAG上限、来源标识保留、预算指标、
受保护结构超预算失败以及嵌套可变对象隔离。全量测试使用Fake/Mock，没有调用真实LLM或外部服务。

## 当前限制

- 估算Token采用中日韩字符按1、其他非空字符约按4:1估算，不等于模型Tokenizer结果
- 当前只对原始需求、本地缺陷知识和RAG总文本做确定性裁剪，尚未实现单资产独立配额
- 关键片段保护基于本地信号，不代表已经证明长PRD裁剪后事实零丢失
- 结构化测试点超过Reviewer/Reviser预算时会明确失败，尚未实现安全的分批评审
- 单轮总耗时仍受模型服务速度、输出Token、串行节点数和自动修正轮次影响
- 真实时延改善和信息保留效果必须在2.15.7埋点与2.16离线评测中验证

## 下一步：阶段2.15.7 分层耗时、Token与错误分类

下一阶段补足真实性能证据：

1. 记录节点、LLM、Embedding、Milvus、文档解析、OCR和视觉调用耗时；
2. 模型返回usage时记录真实输入/输出Token，否则明确标记为估算；
3. 记录模型、Prompt版本、重试次数和错误类型；
4. 区分输入超预算、输出截断、JSON校验、传输和外部服务错误；
5. 不修改当前同步执行架构，不实现后台任务或SSE。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
