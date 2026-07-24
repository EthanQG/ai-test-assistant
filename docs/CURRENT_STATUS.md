# Test Analysis Agent 当前开发状态

更新时间：2026-07-24

这是一份跨电脑、跨 Codex 任务的开发接力文档。开始工作时先阅读本文件；完成一个小阶段后，用最新事实覆盖更新，不在这里累积历史记录。

相关文档：

- [开发与复盘日志](DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](LEARNING_NOTES.md)
- [Codex 协作规则](../AGENTS.md)

## Git 基线

- 分支：`main`
- 本次提交前最新提交：`f1e7cc0 文档：完善代码学习与面试复盘指南`
- 最新已提交功能：`e118865 功能：新增Agent状态与执行事件模型`
- 核对时状态：`main` 与 `origin/main` 同步
- 远程仓库：`https://github.com/EthanQG/ai-test-assistant.git`

切换电脑后先执行：

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
```

## 当前阶段

阶段 2.3 已完成：已经实现第一个真正使用 LLM 和 `TestAnalysisState` 的需求分析节点 `RequirementAnalyzer`。

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

### 阶段 2.3：RequirementAnalyzer

- 新增结构化需求分析结果与推导风险模型
- 新增需求分析 System Prompt 和 User Prompt 构建方法
- LLM 输出经过 JSON 解析、字段类型和未知字段校验
- 分析结果写入 `TestAnalysisState`
- 有待确认项时任务进入 `waiting_for_user`
- LLM 超时或 JSON 无效时任务进入 `failed`
- 使用 Fake LLM 覆盖成功、待确认和失败路径

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
  RequirementAnalysisResult
  RequirementAnalyzer
  后续加入知识检索节点和编排器
```

## 当前测试基线

验证日期：2026-07-24

```text
27 tests passed
```

验证命令：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q agent services utils views tests main.py
```

单元测试不得访问真实 DeepSeek、Milvus 或 Embedding 服务。

## 下一步任务：知识检索节点

阶段 2.3 提交后，建议进入阶段 2.4：把现有 RAG 能力接入 AgentState 和事件模型。

目标流程：

```text
完成需求分析
  → 启动 retrieve_knowledge 步骤
  → RAGService 检索历史测试资产
  → 写入 rag_context / score / count
  → 记录步骤完成或降级事件
```

本阶段只实现知识检索节点，不同时实现测试点 Generator 或 Reviewer。

## 当前限制

- 现有 Streamlit 页面尚未使用 `TestAnalysisState`
- Agent 尚不能自主选择 Tool
- RAG 尚未通过 Agent 节点写入 State
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
