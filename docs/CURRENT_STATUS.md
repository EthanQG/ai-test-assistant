# Test Analysis Agent 当前开发状态

更新时间：2026-07-28

本文件只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)，学习复盘见
[LEARNING_NOTES.md](LEARNING_NOTES.md)。

## Git 基线

- 分支：`main`
- 阶段 2.11.2 已完成并纳入本地提交
- 本地 `main` 领先 `origin/main` 1 个提交，尚未 Push

## 当前阶段

阶段 2.11.2：待确认问题、任务恢复与双栏工作台。

已完成：

- 页面调整为左侧需求工作台、右侧任务概览与结果区
- 右侧概览保持在结果区上方，轨迹、测试点、评审和报告在固定高度容器内滚动
- RequirementAnalyzer 每轮最多返回 3 个会阻塞核心业务判断的问题
- 用户可以逐项回答，也可以选择“暂不确定”
- 用户回答作为明确事实重新进入需求分析 Prompt
- 暂不确定的问题不会重复追问，也不会被 Agent 自行假设
- 暂不确定项会作为风险提示进入 Finalizer 报告
- 重新分析后复用同一个 State，并由 Orchestrator 继续执行到下一个阻塞点或终态

当前 Agent 主链路：

```text
Streamlit 输入
  → TestAnalysisState
  → 页面循环调用 AgentOrchestrator.run_next()
  → RequirementAnalyzer / KnowledgeRetriever / Generator / Reviewer / Reviser
  → Finalizer
  → 页面展示结构化结果与 Markdown 报告
```

待确认恢复链路：

```text
open_questions（最多 3 个）
  → waiting_for_user
  → 用户回答或选择暂不确定
  → 回答/暂缓项写入 State
  → state.resume()
  → RequirementAnalyzer 重新分析
  → 页面继续逐节点调用 Orchestrator.run_next()
```

## 测试基线

验证日期：2026-07-28

```text
119 tests passed
```

已额外使用 Streamlit AppTest 验证等待状态页面：

- 页面无异常，且等待状态已纳入自动化测试
- 两个问题对应两个“暂不确定”选项
- 存在“提交补充并继续执行”按钮
- 右侧显示任务暂停提示

本阶段追加修复：

- 恢复页面顶部安全间距，避免 Streamlit 顶栏遮挡标题图标
- 左右两栏统一使用 760px 外层容器
- 移除恢复执行时嵌套的动态 `st.status`，避免重跑时出现 React 渲染异常
- 测试点生成单独使用 8192 的输出 token 上限，降低大型结构化 JSON 被截断的概率
- 页面由一次执行完整链路改为每次执行一个节点，节点完成后自动刷新事件与决策
- URL保存`task_id`，服务进程内任务缓存支持浏览器刷新后恢复当前任务
- 概览卡片缩小字号，并将内部步骤名称转换为中文
- 执行Spinner固定显示在左侧工作台底部
- 右侧详细结果区使用固定高度填满下方空间
- 左侧提示根据执行中、等待补充、失败和完成状态动态变化
- 页面测试点分类显示为功能、边界、异常和非功能
- 最终Markdown报告使用测试点表格，下载按钮位于报告内容上方

单元测试不访问真实 DeepSeek、Milvus 或 Embedding 服务。

## 下一步任务

提交阶段 2.11.2 后进入阶段 2.11.3：把已经完成的
`HumanFeedbackHandler` 接入页面。

目标：

- 对已生成测试点提交增加、删除、修改和优先级调整意见
- 新业务规则必须二次确认后才能写入需求事实
- 人工反馈驱动 Reviser，并重新经过 Reviewer
- 页面展示反馈状态和修正结果

本阶段继续使用 Streamlit，不进行前后端分离。

## 当前限制

- Agent 尚不能自主选择 Tool，节点仍由 Python Orchestrator 受控编排
- 单个LLM节点执行期间仍是同步等待，节点完成后才会刷新页面
- 达到自动修正上限后仍缺少页面人工处理入口
- 当前任务只保存在Streamlit服务进程内，服务重启后任务会丢失
- MySQL历史任务持久化尚未实现，计划在后续独立阶段设计
- 知识资产上传与持久化尚未设计为独立知识库管理功能
- Milvus 与 Embedding 地址仍在现有客户端中硬编码
- 自动化用例生成和异常日志分析不在当前产品范围

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
git status -sb
git log -5 --oneline --decorate
python -m unittest discover -s tests -v
```

然后让 Codex 按 `AGENTS.md` 初始化上下文，并读取本文件。
