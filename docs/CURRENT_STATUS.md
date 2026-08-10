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

## 当前阶段：2.16.2 图文解析评测（第二小步已完成）

本轮在已有合成样本上增加最小确定性评分，不修改Agent主流程，也不调用真实视觉模型：

1. 新增`evaluation.document_parsing`最小Runner，只消费现有`DocumentContent`和`gold_v1.json`；
2. 正文按预期行计算召回率，并记录具体缺失行；
3. 原生PDF和OCR按去除空白后的编辑距离计算字符准确率；
4. DOCX表格按单元格位置计算准确率；
5. 报告保留解析警告，扫描PDF的`empty_page`表示没有原生文本层；
6. 流程图和UI图本轮明确跳过，不会触发视觉API；
7. 本机真实Tesseract已运行3份样本并保存逐样本报告；
8. 新增pytest覆盖真实PDF/DOCX解析、OCR差异评分和无外部服务Runner。

## 当前数据流

```text
3份PDF/DOCX样本
→ 现有DocumentService解析
→ DocumentContent
→ 与gold_v1.json逐项比较
→ document_parsing_v1.json逐样本报告
```

## 验证结果

```text
python -m pytest tests/unit/evaluation/test_document_parsing.py -q
4 passed

python -m pytest -q
429 passed，10 skipped
```

全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 当前100%结果只来自3份简单合成样本，不代表真实复杂PRD准确率
- 字符准确率会忽略OCR产生的多余空白，但不会忽略文字替换、缺失或新增
- 流程图节点、分支关系和UI操作尚未进入评分
- 当前没有视觉模型结果、复杂脱敏样本或消融实验结果

## 下一步：阶段2.16.2 图文解析评测（第三小步）

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 为已有流程节点、分支关系和UI元素定义确定性评分；
2. pytest只使用Fake视觉结果，不调用真实端点；
3. 是否运行真实视觉模型由可用端点、费用和用户授权决定；
4. 不扩张为通用评测平台。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
