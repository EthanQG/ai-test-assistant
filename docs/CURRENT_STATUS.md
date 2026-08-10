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

## 当前阶段：2.16.2 图文解析评测（第三小步已完成）

本轮补齐流程图和UI图的确定性评分，不修改Agent主流程，也不调用真实视觉模型：

1. 流程节点按节点文字计算召回率；
2. 流程关系按起点、终点和分支条件共同匹配；
3. UI元素按控件类型和显示名称共同匹配；
4. 关系和UI准确率使用实际项与预期项的较大数量作分母，额外编造内容也会扣分；
5. 缺失节点和关系进入`missing_items`，便于定位具体错误；
6. Runner可注入结构化视觉结果，但不会自行调用视觉模型；
7. 无视觉结果时，报告明确记录2份跳过样本；
8. 新增pytest覆盖完整命中、缺失分支、额外UI控件和Runner注入。

## 当前数据流

```text
结构化视觉结果（Fake或未来真实模型）
→ 节点/关系/UI元素集合
→ 与gold_v1.json逐项比较
→ 分项指标与缺失内容
```

## 验证结果

```text
python -m pytest tests/unit/evaluation/test_visual_parsing.py tests/unit/evaluation/test_document_parsing.py -q
8 passed

python -m pytest -q
433 passed，10 skipped
```

全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 视觉评分代码已完成，但当前没有真实视觉模型输出
- 本机JSON基线只评测3份正文/表格/OCR样本，并明确跳过流程图和UI图
- 流程和UI测试使用Fake结构化结果，只证明评分规则正确
- 当前没有复杂脱敏样本或消融实验结果

## 下一步：阶段2.16.3 RAG专项评测

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 准备少量查询与期望KnowledgeAsset对应关系；
2. 计算Recall@K、Precision@K和无关资产召回；
3. 单元测试继续使用Fake检索结果；
4. 真实Milvus评测必须获得用户明确同意后单独运行。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
