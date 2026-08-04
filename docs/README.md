# Test Analysis Agent 文档导航

项目文档按“当前产品定义、开发协作、历史归档”分类。阅读时以当前产品 PRD 和当前状态文档为准，归档文档只用于了解历史设计。

## 当前产品定义

- [Test Analysis Agent 产品需求说明书 V2.10](product/PRD_AGENT_V2.md)

V2.10 PRD 是当前有效的产品范围和验收依据。新增 Agent 节点、用户流程或产品能力前，应先确认与 V2.10 PRD 一致。

## 当前路线图

- [秋招项目含金量提升路线图](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)：阶段2.12～2.17的优先级、范围、证据和简历边界

路线图负责回答“接下来按什么顺序做”；PRD负责回答“产品需要具备什么能力”。规划中的能力
不得因为写入路线图而视为已经实现。

## 开发协作

- [当前开发状态](CURRENT_STATUS.md)：当前完成度、测试基线、限制和下一步
- [开发与复盘日志](DEVELOPMENT_LOG.md)：每个阶段的改动、原因和验证结果
- [代码学习与面试复盘](LEARNING_NOTES.md)：核心概念、代码讲解、参考答案和练习
- [Codex 协作规则](../AGENTS.md)：跨电脑和跨任务的长期开发约定

## 历史归档

- [AI Test Assistant Workflow PRD V1](archive/PRD_WORKFLOW_V1.md)

V1 PRD 同时规划了测试点生成、pytest 用例生成和日志分析，采用固定 Workflow。该版本已不代表当前产品范围，不应作为当前功能完成度或验收依据。

## 文档维护规则

- 产品目标、用户范围或验收标准变化：更新当前 PRD
- 当前开发接力点变化：覆盖更新 `CURRENT_STATUS.md`
- 完成一个可独立验证的阶段：追加 `DEVELOPMENT_LOG.md`
- 新增代码概念或面试知识：追加 `LEARNING_NOTES.md`
- 阶段范围、优先级或证据要求变化：更新 `roadmap/AUTUMN_RECRUITMENT_ROADMAP.md`
- 历史文档不覆盖修改；产生新版本时移动到 `archive/`
