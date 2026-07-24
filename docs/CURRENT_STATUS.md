# Test Analysis Agent 当前开发状态

更新时间：2026-07-24

这是一份跨电脑、跨 Codex 任务的开发接力文档。开始工作时先阅读本文件；完成一个小阶段后，用最新事实覆盖更新，不在这里累积历史记录。

相关文档：

- [开发与复盘日志](DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](LEARNING_NOTES.md)
- [Codex 协作规则](../AGENTS.md)

## Git 基线

- 分支：`main`
- 最新功能提交：`e118865 功能：新增Agent状态与执行事件模型`
- 核对时状态：`main` 与 `origin/main` 同步
- 远程仓库：`https://github.com/EthanQG/ai-test-assistant.git`

切换电脑后先执行：

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
```

## 当前阶段

阶段 2.3 待开始：实现第一个真正使用 LLM 和 `TestAnalysisState` 的需求分析节点 `RequirementAnalyzer`。

## 已完成

### 阶段 1：基础架构整理

- 拆分 `LLMService`、`RAGService` 和 `DocumentService`
- `TestAssistantManager` 支持依赖注入
- 隐藏未完成的自动化用例与日志分析页面
- 增加 README、`.env.example` 和基础测试

### 阶段 1.5：Prompt 边界整理

- 新增 `PromptService`
- System Prompt 只保存稳定规则
- User Prompt 承载当前需求和动态上下文
- 移除未替换的 `{prd_content}`、`{bug_kb_content}`
- 区分需求事实、推导风险和待确认项

### 阶段 2.1/2.2：Agent 状态与事件

- 新增 `TestAnalysisState`
- 新增 `AgentStatus`、`AgentStep` 和 `AgentEvent`
- 支持任务创建、步骤开始/完成、等待用户、恢复、完成和失败
- 支持转换为可保存或通过 API 返回的字典/JSON
- 已限制非法跳步、终态继续执行和等待用户时绕过恢复

## 当前架构

```text
main.py / views/
  Streamlit 页面
        ↓
utils/TestAssistantManager
  现有 Workflow 兼容入口
        ↓
services/
  LLM / RAG / Prompt / Document

agent/
  TestAnalysisState
  AgentEvent
  AgentStatus
  AgentStep
  后续加入 RequirementAnalyzer 和编排器
```

## 当前测试基线

验证日期：2026-07-24

```text
16 tests passed
```

验证命令：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q agent services utils views tests main.py
```

单元测试不得访问真实 DeepSeek、Milvus 或 Embedding 服务。

## 下一步任务：RequirementAnalyzer

本阶段建议只完成需求分析节点，不同时实现 RAG Tool、Generator 或 Reviewer。

目标流程：

```text
原始需求
  → 构建需求分析 Prompt
  → LLM 返回结构化 JSON
  → 校验和解析 JSON
  → 更新 TestAnalysisState
  → 记录步骤开始/完成/失败事件
```

建议输出字段：

- `summary`：需求摘要
- `modules`：业务模块
- `requirement_facts`：需求明确事实
- `business_rules`：业务规则
- `states`：状态及流转
- `inferred_risks`：风险与推导依据
- `open_questions`：因信息不足需要确认的问题

建议开发范围：

1. 定义结构化需求分析结果模型
2. 新增需求分析 System Prompt
3. 在 `PromptService` 增加需求分析 User Prompt
4. 实现 `RequirementAnalyzer`
5. 使用 Fake LLM 编写成功、解析失败和 LLM 失败测试
6. 将结果写入 `TestAnalysisState`
7. 更新本文件、`DEVELOPMENT_LOG.md` 和 `LEARNING_NOTES.md`

## 当前限制

- 现有 Streamlit 页面尚未使用 `TestAnalysisState`
- `RequirementAnalyzer` 尚未实现
- Agent 尚不能自主选择 Tool
- 尚未实现 Reviewer 和自动修正循环
- 内部测试点输出仍然是 Markdown，而不是结构化数据
- Milvus 与 Embedding 地址仍在现有客户端中硬编码
- 自动化用例生成和异常日志分析仍是未完成功能

## 新电脑上的 Codex 启动提示

在新电脑 Clone/Pull 后，可以向 Codex发送：

```text
请按照 AGENTS.md 初始化本次开发上下文。
读取 README.md、docs/CURRENT_STATUS.md 和
docs/DEVELOPMENT_LOG.md、docs/LEARNING_NOTES.md 的最新阶段，
检查 Git 状态和最近提交，
运行现有测试，然后说明当前进度和下一步任务。
暂时不要修改代码。
```

## 环境恢复提醒

Git 不会同步 `.env` 和 `.venv`。新电脑需要执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中重新填写个人 API 配置，不要把真实密钥提交到 Git。
