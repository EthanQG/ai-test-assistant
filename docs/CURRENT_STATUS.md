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
- 阶段2.15.4代码、Fake测试与文档已完成，尚未创建本阶段提交

## 当前阶段：2.15.4 流程图与UI图理解

本阶段在`DocumentContent`上增加有界视觉理解结果和安全降级，没有修改Streamlit布局、AgentState、
Orchestrator、Prompt或节点顺序：

1. 新增`VisualUnderstandingEngine`协议，文档解析不绑定具体视觉模型；
2. 提供显式配置的OpenAI兼容多模态适配器，不复用或猜测当前文本模型能力；
3. 相邻文字、图片名和OCR信号确定性筛选流程图、状态图、时序图和UI原型候选；
4. Logo、图标、小图以及OCR已足够表达且无流程/UI信号的图片不调用视觉模型；
5. 每份文档最多调用5张，输入图片最长边压缩至1600px，输出预算默认1500 Token；
6. 严格JSON恢复图片类型、摘要、节点、关系、条件、UI元素、状态变化和不确定性；
7. 结构化结果保留图片ID、页码、置信度和来源，关系必须引用已存在节点；
8. 低于0.70的视觉结果只保留为待复核候选，不进入兼容需求文本；
9. 单图失败、未配置端点和超出调用上限均降级为结构化警告，不中断正文/OCR解析；
10. PDF文本页中的矢量流程候选可按整页渲染后进入同一视觉边界。

## 当前数据流

```text
PDF矢量页 / PDF图片 / DOCX图片
→ DocumentImageElement + DocumentAttachment
→ 确定性候选筛选
   ├─ 装饰图、小图、纯文字图：不调用视觉模型
   └─ 流程/状态/时序/UI候选：VisualUnderstandingEngine（最多5张）
      → DocumentVisualElement
         ├─ 高置信度：带来源进入兼容文本
         └─ 低置信度：只保留为待复核候选和警告
```

## 验证结果

```text
python -m pytest -q
383 passed，10 skipped，共收集393项
python -m unittest discover -s tests -v
277 tests，OK，7 skipped
```

新增测试覆盖视觉结构类型、图片来源关联、纯文字图片跳过、单图失败隔离、每文档5张上限、严格JSON、
未知字段和非法关系拒绝。默认测试使用Fake/Mock，没有向真实视觉模型发送图片。

## 当前限制

- 视觉理解只有Fake/Mock证据，尚未选择并验证真实多模态模型
- 候选筛选目前依赖相邻文字、图片名和OCR信号，可能漏掉没有文字提示的关键图片
- 真实流程节点召回率、关系准确率、UI操作准确率、耗时和Token尚未评测
- 当前AgentState仍只保存兼容纯文本，没有持有完整`DocumentContent`
- 图片附件、OCR元素和视觉元素尚未持久化到MySQL任务快照
- 低置信度OCR/视觉结果页面尚未提供单独确认入口
- OCR和视觉调用耗时尚未进入阶段2.15.7统一Telemetry
- 企业PRD图片发送到外部视觉端点前仍需确认数据合规

## 下一步：阶段2.15.5 关键问题筛选与Human-in-the-loop限流

下一阶段应减少RequirementAnalyzer对用户的过度打扰：

1. 只让核心规则、关键数字、关键流程分支或图文冲突暂停任务；
2. 重复问题合并并保持一轮最多3个；
3. 中低风险不确定性作为报告风险继续，不强制用户回答；
4. 保留“暂不确定并继续”，避免同一问题恢复后重复询问；
5. 使用确定性规则和测试证明筛选行为，不新增LLM调用。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
