# Test Analysis Agent 当前开发状态

更新时间：2026-07-24

这是一份跨电脑、跨 Codex 任务的开发接力文档。开始工作时先阅读本文件；完成一个小阶段后，用最新事实覆盖更新，不在这里累积历史记录。

相关文档：

- [当前产品需求说明书 V2](product/PRD_AGENT_V2.md)
- [项目文档导航](README.md)
- [开发与复盘日志](DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](LEARNING_NOTES.md)
- [Codex 协作规则](../AGENTS.md)

## Git 基线

- 分支：`main`
- 本阶段提交前基线：`d16dd74 功能：实现Agent结构化测试点生成节点`
- 最新已提交功能：`d16dd74 功能：实现Agent结构化测试点生成节点`
- 核对时状态：`main` 与 `origin/main` 同步
- 远程仓库：`https://github.com/EthanQG/ai-test-assistant.git`

切换电脑后先执行：

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
```

## 当前阶段

阶段 2.6 已完成：已经实现对结构化测试点进行多维质量检查的 `TestPointReviewer`。

产品范围已按 V2 PRD 收敛为测试分析 Agent。旧版三模块 Workflow PRD 已归档，不再作为当前需求依据。

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

### 阶段 2.4：KnowledgeRetriever

- 根据结构化需求分析结果构造历史资产检索查询
- 将 RAG 上下文、最高相似度、命中数量写入 `TestAnalysisState`
- 使用明确状态区分 `matched`、`no_match` 和 `degraded`
- 无历史命中时记录结果并继续，不把正常空结果误判为故障
- Milvus 或 Embedding 服务失败时记录降级原因，当前任务仍可继续
- 记录 `retrieve_knowledge` 步骤的开始与完成事件
- 保留旧 RAG 调用的兼容行为，Agent 调用使用严格错误模式

### 阶段 2.5：TestPointGenerator

- 新增结构化 `TestPoint` 和 `TestPointGenerationResult`
- 支持 functional、boundary、exception、non_functional 四类测试点
- 支持 P0、P1、P2 优先级
- 记录 requirement、historical_asset、test_experience、user_feedback 来源及引用
- 每条测试点包含场景、前置条件、步骤和可观察预期结果
- LLM 返回 JSON 后由 Python 严格校验，非法字段和空数组会使任务失败
- 检索无匹配或服务降级时仍可生成；未执行检索或存在待确认项时禁止生成
- 合法测试点写入 `TestAnalysisState` 并记录数量、分类和优先级统计事件

### 阶段 2.6：TestPointReviewer

- 新增结构化评审结果、维度评分、需求覆盖和幻觉问题模型
- 评审需求覆盖、边界异常、可执行性和来源可追踪性
- 输出重复测试点组、缺失场景、幻觉问题和修正建议
- Python 强制检查每条需求事实都被评审且不存在重复覆盖记录
- 达标由代码计算：总分达到阈值、所有需求事实完全覆盖且无幻觉问题
- LLM 不允许直接返回 passed 或 next_action
- 评审结果、阈值和达标状态写入 `TestAnalysisState`

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
  KnowledgeRetriever
  TestPointGenerator
  TestPointReviewer
  后续加入 Reviser 和编排器
```

## 当前测试基线

验证日期：2026-07-24

```text
64 tests passed
```

验证命令：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q agent services utils views tests main.py
```

单元测试不得访问真实 DeepSeek、Milvus 或 Embedding 服务。

## 下一步任务：测试点定向修正节点

阶段 2.6 提交后，建议进入阶段 2.7：实现 `TestPointReviser`，只根据 Reviewer 指出的缺失项、重复项和幻觉问题定向修正测试点。

目标流程：

```text
评审未达标
  → 启动 revise_test_points 步骤
  → 将当前测试点和结构化评审意见发送给 LLM
  → LLM 返回完整的修正后测试点集合
  → Python 重新校验测试点结构
  → 写入 State 并等待下一轮 Reviewer
```

本阶段只实现一次定向修正，不同时实现循环编排或页面接入。

## 当前限制

- 现有 Streamlit 页面尚未使用 `TestAnalysisState`
- Agent 尚不能自主选择 Tool
- 尚未实现自动修正节点和最大次数受控循环
- 现有 Streamlit 页面仍使用旧 Workflow 的 Markdown 报告，尚未展示 Agent 内部结构化测试点
- Milvus 与 Embedding 地址仍在现有客户端中硬编码
- 自动化用例生成和异常日志分析仍是未完成功能

## 新电脑上的 Codex 启动提示

在新电脑 Clone/Pull 后，可以向 Codex发送：

```text
请按照 AGENTS.md 初始化本次开发上下文。
读取 README.md、docs/product/PRD_AGENT_V2.md、
docs/CURRENT_STATUS.md 和
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
