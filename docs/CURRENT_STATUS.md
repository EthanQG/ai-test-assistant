# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.15.2：`7826099 阶段2.15.2：完善PDF与DOCX结构化解析`
- 阶段2.15.3：`b823c2d 阶段2.15.3：增加扫描文档OCR与置信度分流`
- 真实Tesseract冒烟验收与集成测试已完成，尚未创建验收提交

## 当前阶段：2.15.3 OCR与扫描文档

本阶段在`DocumentContent`上增加OCR结果和安全降级，没有修改Streamlit布局、AgentState、
Orchestrator、Prompt或节点顺序：

1. 新增`OcrEngine`协议，文档解析不绑定具体OCR供应商；
2. 新增本地`TesseractOcrEngine`适配器，通过TSV获得文字行和真实置信度；
3. PDF没有文本层时，以150 DPI渲染整页后执行OCR；
4. PDF/DOCX内嵌图片逐张执行OCR，单张失败不终止其他内容；
5. `DocumentOcrElement`保存文字、置信度、图片ID、页码和处置状态；
6. 置信度不低于0.80的文字进入兼容文本，并明确标注OCR来源；
7. 低置信度文字只保存为`REVIEW_REQUIRED`候选，不直接进入当前Agent需求事实；
8. Tesseract不可用、调用失败和低置信度均产生结构化警告；
9. 解析统计增加OCR结果数、低置信度数和失败数；
10. `.env.example`增加Tesseract命令、语言与超时配置。

## 当前数据流

```text
PDF扫描页 / PDF图片 / DOCX图片
→ DocumentImageElement + DocumentAttachment
→ OcrEngine
→ DocumentOcrElement
   ├─ ACCEPTED：带来源标识进入兼容文本
   └─ REVIEW_REQUIRED：只保留为待复核候选和警告
```

## 验证结果

```text
python -m pytest -q
373 passed，10 skipped，共收集383项
python -m unittest discover -s tests -v
272 tests，OK，7 skipped
RUN_OCR_INTEGRATION_TESTS=1（真实Tesseract）
1 passed
```

本机Tesseract 5.5.3、`chi_sim`和`eng`已验证。合成中文图片识别两行置信度约0.95和0.92、耗时约
0.30秒；DOCX真实链路识别“商户单日提现上限为二十万元”，置信度约0.95，无失败警告。新增显式开启的
真实OCR集成测试，默认测试仍不会调用外部OCR程序。该冒烟结果不能替代真实PRD样本集的准确率评测。

## 当前限制

- 当前仅完成合成中文图片冒烟，真实扫描PRD准确率、召回率和耗时分布尚未评测
- 当前AgentState仍只保存兼容纯文本，没有持有完整`DocumentContent`
- 低置信度OCR已安全标为待复核候选，但页面尚未提供单独确认入口
- OCR只识别文字，不理解流程节点、箭头、页面操作或状态变化
- 图片附件和OCR元素尚未持久化到MySQL任务快照
- OCR耗时尚未进入阶段2.15.7统一Telemetry

## 下一步：阶段2.15.4 流程图与UI图理解

下一阶段应先设计图片分类与有界多模态调用：

1. OCR可解决的纯文字图片不重复调用视觉模型；
2. Logo、图标和装饰图直接忽略；
3. 只对流程图、状态图、时序图和UI原型调用视觉模型；
4. 限制单文档调用数量、图片尺寸和输出Token；
5. 结构化保存节点、箭头、条件、页面元素、操作、状态变化、来源与不确定性。

真实OCR运行边界已经打通，可以进入2.15.4；真实脱敏PRD样本的系统评测仍留在2.16。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
