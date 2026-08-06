# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.15.2：`7826099 阶段2.15.2：完善PDF与DOCX结构化解析`
- 阶段2.15.3代码、测试与文档已完成，尚未创建本阶段提交

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
373 passed，9 skipped，共收集382项
python -m unittest discover -s tests -v
271 tests，OK，6 skipped
```

Fake OCR已验证扫描PDF、置信度分流、页码与图片来源、单图失败隔离；Tesseract TSV适配器已通过Mock
子进程测试。本机尚未安装Tesseract，因此没有把真实OCR识别精度描述为已验证。默认测试没有访问真实
DeepSeek、Ollama、Milvus、MySQL或视觉模型。

## 当前限制

- 本机没有Tesseract与`chi_sim`语言数据，真实OCR集成仍需安装后验证
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

进入2.15.4前，建议先在安装Tesseract的环境执行一份脱敏扫描PRD冒烟验证。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
