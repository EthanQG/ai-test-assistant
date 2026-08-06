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
- 阶段2.15.5代码、pytest与文档已完成，尚未创建本阶段提交

## 当前阶段：2.15.5 关键问题筛选与Human-in-the-loop限流

本阶段在RequirementAnalyzer输出和AgentState之间增加确定性问题策略，没有修改Streamlit布局、AgentState、
Orchestrator状态转换或节点顺序：

1. LLM为每个待确认候选返回问题、类别、阻塞原因和当前需求依据；
2. 类别限定为核心规则、关键数字、关键分支、需求冲突、实现细节和低影响问题；
3. Python只允许前四类暂停任务，并保持每轮最多3个；
4. 实现细节、低影响问题和超过3个的候选确定性转为`inferred_risks`继续执行；
5. 本地关键词保护会覆盖模型误分类，数据库、缓存、技术栈、按钮颜色等问题不能阻塞；
6. 问题经过空白、标点和大小写归一化去重；
7. 用户选择“暂不确定”的问题即使标点不同也不会在重新分析后再次询问；
8. 结构化事件记录原始候选数、最终阻塞数和转风险数；
9. AgentState仍只保存问题字符串，页面表单、快照、MySQL恢复和提交答案接口保持兼容；
10. 本阶段没有新增LLM调用，只有原需求分析响应结构发生变化。

## 当前数据流

```text
RequirementAnalyzer的结构化响应
→ ClarificationCandidate（类别、阻塞原因、需求依据）
→ ClarificationQuestionPolicy
   ├─ 核心规则/关键数字/关键分支/需求冲突：最多3个进入open_questions
   └─ 实现细节/低影响/超额候选：转为inferred_risks继续执行
```

## 验证结果

```text
python -m pytest -q
390 passed，10 skipped，共收集400项
```

新增pytest覆盖前三个阻塞项、非阻塞转风险、本地误分类保护、问题去重、暂不确定不再询问、仅非阻塞时
继续执行以及旧字符串/未知类别拒绝。全量测试使用Fake/Mock，没有调用真实LLM或外部服务。

## 当前限制

- 问题类别由LLM生成，Python虽有限制和关键词兜底，但真实分类效果尚未离线评测
- 当前去重只处理文字相同或标点差异，不能完成真正的语义主题合并
- 非阻塞候选统一转为风险，风险文案质量仍受候选问题和evidence质量影响
- 新结构化问题契约需要真实模型冒烟验证，当前只有Fake响应证据
- 单轮总耗时仍受LLM速度、输入长度、输出Token和串行节点数量影响

## 下一步：阶段2.15.6 ContextBuilder与节点预算

下一阶段开始直接控制模型输入长度和节点上下文：

1. 为每个节点定义输入字段白名单；
2. 限制需求正文、RAG单条和总上下文长度；
3. 预留输出Token和安全余量后计算节点输入预算；
4. 超限时优先保留业务数字、规则、状态、来源和用户确认；
5. 不为没有真实触发条件的场景增加复杂自动摘要。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
