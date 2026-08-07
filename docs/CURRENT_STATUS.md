# Test Analysis Agent 当前开发状态

更新时间：2026-08-07

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

## 当前阶段：2.16.2 图文解析评测（第一小步已完成）

本轮先补齐可安全提交到仓库的图文解析评测输入，不修改Agent主流程，也不运行真实视觉模型：

1. 新增原生文字PDF，验证PDF文本层可直接抽取；
2. 新增带权限矩阵的DOCX，验证正文与表格结构；
3. 新增无文本层扫描PDF，作为OCR路径样本；
4. 新增订单库存流程图和发票上传UI图，作为视觉语义样本；
5. 新增`gold_v1.json`，记录文字、表格、流程关系和UI元素金标准；
6. 新增确定性pytest，验证样本存在、格式有效、原生/扫描PDF差异、DOCX表格和图片尺寸；
7. 样本全部为脚本生成的虚构内容，不包含公司PRD；
8. 当前还没有评分Runner、真实OCR批量结果、视觉模型结果或准确率指标。

## 当前数据流

```text
build_fixtures.py
→ 5份脱敏合成PDF/DOCX/PNG
→ gold_v1.json解析金标准
→ 确定性结构测试
→ 后续图文解析Runner消费
```

## 验证结果

```text
python -m pytest tests/unit/evaluation/test_document_fixtures.py -q
5 passed

python -m pytest -q
425 passed，10 skipped
```

全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 5份图文附件是小型合成样本，不代表真实复杂PRD分布
- DOCX已做结构读取验证；当前机器没有Word或LibreOffice，未生成DOCX页面渲染截图
- 当前没有评测Runner、自动指标计算、真实OCR/视觉输出或消融结果
- 不能根据样本存在就宣称图文解析准确率达到某个数值

## 下一步：阶段2.16.2 图文解析评测（第二小步）

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 定义最小解析结果适配和评分输入，不搭建通用评测平台；
2. 实现正文、表格和OCR等确定性指标；
3. 视觉语义只在真实端点和成本边界确认后运行；
4. 输出逐样本明细，避免用一个总分掩盖失败类型。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
