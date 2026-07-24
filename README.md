# Test Analysis Agent

一个面向测试工程师的智能测试分析项目。当前版本聚焦于读取 PRD 或需求描述，结合本地 Bug 经验与 Milvus 历史测试资产，生成结构化测试分析报告，并支持人工反馈后迭代修改。

> 当前只有“测试分析报告生成”功能完成。自动化用例生成和异常日志分析仍在规划中，因此暂未在页面展示。

## 当前能力

- 输入文本，或上传 TXT、Markdown、PDF、DOCX 格式的需求文档
- 调用 DeepSeek 兼容接口流式生成测试分析报告
- 使用 Milvus 与 Embedding 服务检索相似历史测试资产
- 展示 RAG 命中数量与最高相似度
- 根据人工意见迭代修改报告
- 将确认后的报告保存回历史测试资产库
- 内部已实现结构化需求分析节点，可识别需求事实、推导风险和待确认项

## 项目结构

```text
.
├── AGENTS.md               # Codex跨设备协作与开发约定
├── main.py                 # Streamlit 应用入口
├── agent/                  # Agent状态、事件及后续节点
├── views/                  # 页面与交互状态
├── services/               # LLM、RAG、文档解析应用服务
├── utils/                  # 基础客户端、配置及兼容业务入口
├── prompts/                # 模型提示词
├── knowledge/              # 本地测试知识
├── docs/                   # 当前接力状态与开发复盘
└── tests/                  # 自动化测试
```

当前阶段保留 `TestAssistantManager` 作为页面兼容入口，底层依赖已经通过 `services` 层隔离，为后续接入 Agent 编排器做准备。

## 开发过程与设计说明

项目从 Workflow 向 Agent 演进的阶段记录、概念解释、设计原因和验证结果，请查看：

- [当前开发状态与跨设备接力](docs/CURRENT_STATUS.md)
- [开发与复盘日志](docs/DEVELOPMENT_LOG.md)
- [代码学习与面试复盘](docs/LEARNING_NOTES.md)

`CURRENT_STATUS.md` 保存最新接力点，`DEVELOPMENT_LOG.md` 保存完整历史，`LEARNING_NOTES.md` 保存代码知识、参考答案和面试练习。Codex 的仓库级协作规则位于 [AGENTS.md](AGENTS.md)。

## 本地运行

建议使用 Python 3.10 或更高版本。

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run main.py
```

运行前请在 `.env` 中填写真实的 `DEEPSEEK_API_KEY`。`.env` 已加入 Git 忽略规则，请勿提交真实密钥。

## 外部依赖

测试资产检索当前依赖：

- Milvus 向量数据库
- 提供 `nomic-embed-text` 模型的 Embedding 服务
- DeepSeek 兼容的 Chat Completions API

Milvus 与 Embedding 地址目前仍由现有 RAG 客户端配置。后续阶段会统一迁移到环境变量。

## 后续计划

1. 将知识检索封装为 Agent 节点并写入 `TestAnalysisState`
2. 将测试点生成封装为结构化 Agent 节点
3. 增加 Agent 编排器与执行轨迹
4. 增加 Reviewer 质量评审与自动修正循环
5. 建立离线评测集，量化 RAG 和 Reviewer 带来的覆盖率提升
6. Agent 核心稳定后，再评估 FastAPI + React/Vue 前后端分离
