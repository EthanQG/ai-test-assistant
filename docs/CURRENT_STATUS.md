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

## 当前阶段：2.16.4 Reviewer/Reviser专项评测（第二小步已完成）

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

## 当前数据流

```text
虚构需求事实 + 注入缺陷测试点
→ Reviewer缺陷预测（下一小步接入）
→ 按case_id + defect_type + target匹配
→ TP / FP / FN
→ Precision / Recall / 正确样本误报率
```

## 验证结果

```text
python -m pytest -q tests/unit/evaluation/test_reviewer_evaluation.py
4 passed

python -m pytest -q
450 passed，10 skipped
```

默认全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 当前12份均为小型合成样本，尚未覆盖长测试点集合
- 第一小步只证明数据契约和评分公式，尚无真实Reviewer效果
- 自由文本映射依赖明确关键词，Reviewer换一种表达可能造成漏检
- Reviser修复正确率和副作用尚未评测

## 下一步：阶段2.16.4 Reviewer评测Runner

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 将12份fixture转换为Reviewer需要的结构化输入；
2. 通过可注入Reviewer callable逐case运行并接入现有适配器；
3. 先用Fake结果生成完整基线报告；
4. 再决定是否显式调用真实DeepSeek，默认pytest继续隔离外部服务。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
