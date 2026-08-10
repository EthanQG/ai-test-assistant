# Test Analysis Agent 当前开发状态

更新时间：2026-08-10

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
- 阶段2.15.7：`039f798 阶段2.15.7：增加分层性能指标与错误分类`
- 阶段2.16.1：`143b2a0 阶段2.16.1：完成十份评测金标准复核`
- 阶段2.16.2第一小步：`744228b 阶段2.16.2：建立图文解析评测样本`
- 阶段2.16.2第二小步：`7395b8d 阶段2.16.2：增加文档解析确定性评分`
- 阶段2.16.2第三小步：`5a32bc6 阶段2.16.2：增加流程与UI语义评分`
- 阶段2.16.3第一小步：`2760923 阶段2.16.3：建立RAG资产级评测指标`
- 阶段2.16.3第二小步：`1f6537b 阶段2.16.3：接入RAG检索服务评测边界`
- 阶段2.16.3第三小步：`2533806 阶段2.16.3：完成真实RAG链路评测`
- 阶段2.16.3第四小步：`28b6942 阶段2.16.3：完成RAG参数对比评测`
- 阶段2.16.4第一小步：`2cf636a 阶段2.16.4：建立Reviewer缺陷评测基线`
- 阶段2.16.4第二小步：`ed6be71 阶段2.16.4：适配Reviewer结构化缺陷输出`

## 当前阶段：2.16.7 长PRD分段需求分析（已完成）

### V1验收修复：长PRD需求分析输出截断

真实演示发现`RequirementAnalyzer`未显式传入大结构化输出额度，长PRD生成事实、规则、风险和待确认项时使用默认`max_tokens`，导致JSON被截断。现已与Generator、Reviewer和Reviser统一为8192输出Token，并增加参数传递测试。该修复不改变Prompt、AgentState、Orchestrator和页面行为；8192是有界修复，不承诺任意长度文档均可单轮完成。

单纯提高输出上限后同一PRD仍被截断，因此已完成章节感知Map-Merge：

1. Markdown标题、短数字章节、段落和句子边界形成有序片段，普通编号业务语句不会误判为标题；
2. 默认每段最多约1800字符，超长章节继续有界拆分；
3. 每段独立生成结构化分析，任一失败会报告chunk ID和章节；
4. Python确定性合并摘要、模块、事实、规则、状态、风险和问题，并按标准化文本去重；
5. 风险依据和问题证据保留chunk ID及章节来源；
6. 全部候选问题合并后仍只经过一次现有ClarificationQuestionPolicy，最多阻塞3个；
7. 2735字符演示PRD真实分析拆为2段，222.75秒完成，生成57条事实、27条规则、14条状态流转、21条风险和3个待确认问题；未再发生输出截断；
8. 已知限制：片段当前顺序执行；问题尚无跨片段语义复核，本次出现一条原文已有答案的重复确认。

本轮先建立Reviewer可重复缺陷数据和确定性指标，不调用真实LLM：

1. 新增12份完全虚构Reviewer样本；
2. 覆盖需求遗漏、边界缺失、重复测试点、无依据断言、模糊预期和来源缺失六类问题；
3. 8份单缺陷、2份多缺陷，共12个缺陷；
4. 额外保留2份正确样本，用于检查Reviewer误报；
5. 每个缺陷包含稳定类型、目标和具体证据；
6. 指标输出TP、FP、FN、Precision、Recall和正确样本误报率；
7. pytest只使用确定性Fake预测，不调用真实LLM。
8. 新增`TestPointReviewResult`到六类稳定缺陷的适配器；
9. 覆盖状态、重复组和幻觉问题直接读取结构化字段；
10. 边界、模糊预期和来源缺失只在出现明确关键词时分类；
11. 无法确定的自由文本建议保持未分类，不强行制造命中。
12. 新增Reviewer Runner，将fixture转换为真实`TestAnalysisState`；
13. Runner只依赖可注入的`review(state)`边界，可接Fake或现有Reviewer；
14. Fake报告经过结构化评审结果适配和统一评分器，未绕过生产输入结构；
15. 当前Fake链路检出11/12个缺陷，保守边界规则漏掉“上传6个文件”。
16. 新增显式环境开关保护的真实Reviewer入口，默认pytest不会调用LLM；
17. 单样本两次结构校验仍失败时记录错误并继续，不丢失整批实验；
18. `deepseek-v4-pro`真实运行12份样本约439秒，3份结构化输出失败；
19. 真实基线TP=4、FP=7、FN=8，Precision=0.3636、Recall=0.3333；
20. 2份正确样本未产生已分类误报，但其中1份因结构化输出失败。
21. 新增6份Reviser最小修复样本，逐一覆盖六类Reviewer缺陷；
22. 每份样本同时保留至少一个正确测试点作为副作用保护对象；
23. 指标分别计算目标修复率和正确测试点保留率；
24. Fake报告两项均为1.0，只证明评测接线和评分公式；
25. 错误Fake可同时暴露未修复目标和误改保护测试点。
26. 新增显式开关保护的真实Reviser入口，默认pytest不访问LLM；
27. `deepseek-v4-pro`运行6份样本约72秒，严格目标修复率0.1667；
28. 正确测试点保留率1.0，说明当前样本中未破坏保护测试点；
29. 1份来源缺失样本因模型仍返回空`source`而被生产校验拒绝；
30. 3份样本生成不同标题，严格全字段匹配会将语义接近结果判为未命中。
31. 固定`baseline_llm`、`llm_with_rag`和`llm_with_rag_reviewer_reviser`三组名称；
32. 三组强制使用相同10份`seed-v1`需求，缺组或多组直接拒绝；
33. 统一输出事实、规则、风险、问题、场景、断言、耗时、Token和修正次数；
34. 第一版采用去空白、大小写归一后的严格文本匹配；
35. Fake测试完成10×3实验矩阵，并能暴露某一组的事实漏检。
36. 新增`TaskViewExperimentVariant`，只接收Application Service只读结果；
37. 统一提取事实、规则、风险、问题、测试场景和预期断言；
38. 从`TaskView.performance_summary`读取节点总耗时和Token；
39. Token优先使用供应商返回值，不可用时才使用已有估算值；
40. 评测适配层不读取Repository，也不直接修改`AgentState`。
41. 固定三组仅在`use_rag`和`use_quality_loop`两个能力开关上不同；
42. 三组都通过Application Service创建和推进任务；
43. 待确认问题统一回答`None`，表示“暂不确定”，不向任一组额外泄露答案；
44. 补充恢复始终使用同一个`task_id`；
45. 默认最多2轮待确认、20次推进，防止离线任务无限循环。
46. 基础组通过`NoKnowledgeRetriever`清空本地经验和RAG上下文；
47. 基础组和RAG组通过`QualityLoopBypassReviewer`跳过真实质量闭环；
48. 两种旁路都在AgentEvent中写入`evaluation_bypass=true`；
49. RAG组继续使用注入的真实Retriever，完整组继续使用真实Reviewer/Reviser；
50. 三组复用原`AgentOrchestrator`，未复制或修改状态机。
51. 新增显式开关保护的真实三方案入口，默认只运行1份需求；
52. 首次运行遇到临时HTTPS证书校验失败，重试后完成三组；
53. 基础/RAG/完整组耗时分别为146.60、122.53、243.42秒；
54. 三组输入/输出Token分别为3025/10046、2815/8737、9941/16488；
55. 严格文本召回均为0，不作为业务质量优劣结论；
56. 烟测发现旧RAG打印完整结果时被GBK特殊字符中断并降级；
57. 已改为只打印结果数量，避免日志编码影响业务并减少内容泄露。

## 当前数据流

```text
虚构需求事实 + 注入缺陷测试点
→ TestAnalysisState
→ 可注入Reviewer.review(state)
→ TestPointReviewResult缺陷适配
→ 按case_id + defect_type + target匹配
→ TP / FP / FN
→ Precision / Recall / 正确样本误报率
```

## 验证结果

```text
python -m pytest -q
482 passed，10 skipped

python -m compileall -q agent application repositories services utils views tests main.py evaluation
通过

git diff --check
通过
```

默认全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型；真实三方案烟测由独立环境变量显式开启。

## 当前限制

- 当前12份均为小型合成样本，尚未覆盖长测试点集合
- Fake Runner只证明输入转换、调用边界、适配和评分已连通，尚无真实Reviewer效果
- `review-boundary-002`暴露保守适配漏检，当前Fake Recall为0.9167
- 真实Reviewer输出存在对象/字符串类型不稳定，3/12样本最终失败
- 当前指标混合了Reviewer判断能力、输出契约稳定性和保守适配规则影响
- 当前Reviser修复率是严格结构匹配，不等同于人工语义正确率
- 真实报告没有保存完整模型输出，尚不能人工复核3个改名结果是否语义等价
- 三方案第一小步只有Fake接线证据，尚无三组真实结果
- 严格文本匹配会漏掉同义表达，需要在最终报告中同时保留人工复核口径
- 已完成1份需求真实三组烟测，未运行完整10×3
- QualityBypass的100分只是Finalizer结构通行值，不能计入真实Reviewer质量
- 本次RAG烟测受修复前控制台编码降级影响，不能用于证明RAG质量变化
- 严格文本召回无法识别同义表达，三组全0不代表没有有效输出
- 自由文本映射依赖明确关键词，Reviewer换一种表达可能造成漏检
- Reviser修复正确率和副作用尚未评测

## 下一步：完整页面体验与长PRD质量复核

已新增`docs/RESUME_EVIDENCE.md`，并完成长PRD需求分析稳定性修复。下一步优先完成一次页面全流程体验，不继续扩张架构：

1. 重新上传演示PRD，回答最多3个问题并完成生成、评审和报告；
2. 人工核对57条事实是否存在明显重复或遗漏；
3. 将跨片段问题语义复核和有限并行列为后续可选优化；
4. FastAPI、异步执行和Vue继续留在2.17，不在简历版本前强行实现。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
