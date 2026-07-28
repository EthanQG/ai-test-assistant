# Test Analysis Agent 当前开发状态

更新时间：2026-07-28

本文件只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)，学习复盘见
[LEARNING_NOTES.md](LEARNING_NOTES.md)。

## Git 基线

- 分支：`main`
- 最新提交：`ea8d39f 文档：修正开发日志阶段顺序与索引`
- 本地 `main` 与 `origin/main` 已同步
- 阶段 2.11.3 已完成开发，当前尚未提交

## 当前阶段

阶段 2.11.3：结构化人工反馈页面闭环。

已完成：

- 已完成任务和达到自动修正上限的任务可以提交人工反馈
- 测试建议支持新增、修改、删除测试点和调整优先级
- 业务规则反馈进入 `pending_confirmation`，用户确认后才写入需求事实
- 用户取消的业务规则标记为 `rejected`，不会进入需求事实或驱动Reviser
- 已完成任务收到反馈后通过 `reopen_for_feedback()` 重新进入运行状态
- 人工反馈驱动Reviser修改测试点、Reviewer重新评审、Finalizer更新报告
- 页面新增“人工反馈”结果标签，展示反馈类型、动作、内容、原因和状态
- 自动修正次数与人工反馈修正次数分别记录和展示
- 人工反馈本身不受自动修正次数上限阻断，后续自动修正仍受独立上限控制
- Generator、Reviewer、Reviser统一使用8192的结构化输出预算，修复Reviser返回完整测试点集合时沿用默认4096而被截断的问题

人工反馈闭环：

```text
completed / revision_limit_reached
  → 页面提交 HumanFeedback
  → 测试建议直接进入 ready
  → 业务规则等待用户确认或取消
  → TestPointReviser
  → TestPointReviewer
  → Finalizer
  → 更新结构化结果与 Markdown 报告
```

## 测试基线

验证日期：2026-07-28

```text
127 tests passed
```

已额外使用 Streamlit AppTest 验证：

- 已完成任务显示结构化人工反馈表单
- 业务规则反馈显示“确认规则并继续”和“取消该规则”
- 右侧人工反馈标签能够显示中文状态
- 原有需求补充、刷新恢复和双栏页面测试继续通过

本阶段领域规则：

- `revision_count`记录总修正次数
- `automatic_revision_count`只记录Reviewer驱动的自动修正
- `human_revision_count`只记录人工反馈驱动的修正
- `max_revision_count=2`只限制自动修正，不阻止新的人工反馈
- 大体量结构化节点的输出预算由`LARGE_STRUCTURED_OUTPUT_MAX_TOKENS`统一定义，节点测试会校验预算是否正确传递

单元测试不访问真实 DeepSeek、Milvus 或 Embedding 服务。

## 下一步任务

提交阶段 2.11.3 后，先设计MySQL历史任务持久化方案，再开始编码。

目标：

- 明确任务主表、State快照、事件、决策和最终报告的数据模型
- 数据库连接只通过`.env`或部署环境变量配置
- 支持服务重启后按`task_id`恢复任务
- 设计写入失败时不影响当前Agent执行的降级策略
- 增加历史任务列表与查看入口

本阶段继续使用 Streamlit，不进行前后端分离。

## 当前限制

- Agent 尚不能自主选择 Tool，节点仍由 Python Orchestrator 受控编排
- 单个LLM节点执行期间仍是同步等待，节点完成后才会刷新页面
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
