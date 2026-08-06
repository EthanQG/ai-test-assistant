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
- 阶段2.15.7：`039f798 阶段2.15.7：增加分层性能指标与错误分类`

## 当前阶段：2.16.1 脱敏评测集与人工标注契约（单人复核完成）

本阶段先建立稳定的人工金标准格式，不修改Agent主流程，也不运行真实模型实验：

1. 新增schema v1评测数据集契约，严格校验字段、类型、未知字段、版本和重复case_id；
2. 人工金标准区分事实、业务规则、风险、关键问题、必要场景和禁止断言；
3. 事实、规则、风险和必要场景必须记录来源依据，不能只保存主观结论；
4. 关键问题类别复用Agent已有`ClarificationCategory`，避免评测口径与线上模型漂移；
5. 已覆盖登录权限、订单库存、文件上传、支付、优惠券、退款、搜索、消息、重复提交和角色权限10份虚构需求；
6. 用户已逐项修订并接受精简版金标准，数据集标记为`review_status=reviewed`；
7. 当前采用单人复核，没有双人标注一致性数据，不允许另一个LLM代替人工金标准；
8. 真实图文附件和真实模型结果仍未完成。

## 当前数据流

```text
脱敏需求 + 人工标注
→ schema v1 JSON数据集
→ load_evaluation_dataset严格校验
→ EvaluationDataset领域对象
→ 后续2.16评测Runner消费
```

## 验证结果

```text
python -m pytest -q
420 passed，10 skipped
```

新增定向测试当前为15项，并增加10个业务域、输入特征覆盖和非法复核状态检查。
全量测试未调用真实外部服务。

## 当前限制

- 当前10份内容由Codex辅助起草并由用户单人复核，没有双人标注一致性指标
- 样例仍以JSON中的文字需求为输入，真实扫描页、流程图和UI图片附件尚未加入
- 当前没有评测Runner、自动指标计算、真实模型输出或消融结果
- 不能根据本阶段宣称RAG、Reviewer或ContextBuilder带来任何质量提升

## 下一步：阶段2.16.2 图文解析评测

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 增加少量完全虚构的PDF、DOCX、扫描页、流程图和UI图附件；
2. 为附件定义正文、表格、OCR、流程节点和UI操作的解析金标准；
3. 先实现确定性指标，不提前建设评测平台；
4. 双人标注一致性作为当前明确限制，不阻塞后续单人评测。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
