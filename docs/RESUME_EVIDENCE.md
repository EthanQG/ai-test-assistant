# 秋招项目证据与面试讲解

本文只汇总仓库中已经存在的代码、测试和评测报告。没有数据支撑的效果提升不得写入简历。

## 推荐项目定位

**面向图文PRD的AI测试分析助手**：通过受控Agent编排完成需求分析、历史测试资产检索、结构化测试点生成、质量评审与人工修正，并支持任务持久化恢复和离线评测。

准确分类是“受控 Agentic Workflow”，不是能够任意规划和调用工具的自主Agent。

## 可以写入简历的能力

1. 设计受控Agent状态机，将需求分析、知识检索、测试点生成、Reviewer/Reviser和报告整理拆分为职责明确的节点，并通过最大步数、修正上限和终态保护限制执行边界。
2. 实现Human-in-the-loop暂停与恢复：信息不足和业务规则不确定时暂停，用户补充或确认后由Orchestrator恢复同一任务。
3. 通过Application Service和Repository隔离Streamlit与Agent核心；使用MySQL保存版本化AgentState快照和事件，支持按`task_id`恢复。
4. 建立MySQL知识资产与Milvus向量索引的关联：MySQL保存完整资产，Milvus保存检索Chunk和资产标识，召回后回查完整内容及来源。
5. 支持PDF/DOCX正文、表格、扫描页OCR和业务图片的结构化解析，并保留来源、警告和降级信息。
6. 针对长PRD单轮JSON易截断的问题，实现章节感知Map-Merge分析：片段有界调用、Python确定性合并去重，并保留风险和问题的片段来源。
7. 为LLM节点建立最小上下文和Token预算，记录节点耗时、Token、重试和错误降级信息。
8. 建立离线评测集和可重复Runner，覆盖文档解析、RAG、Reviewer、Reviser及三方案实验边界。
9. 使用pytest构建分层测试；当前默认回归结果以`docs/CURRENT_STATUS.md`为准，跳过项均为显式开关保护的真实外部集成测试。

## 已有量化证据

| 证据 | 范围 | 结果 | 可得出的结论 |
| --- | --- | --- | --- |
| 文档解析评测 | 3个可自动评测样本 | 正文/表格/OCR目标项均为1.0 | 解析评测链路可运行；样本规模小 |
| 真实RAG评测 | 5个合成查询，Top-K=3 | Recall@K 1.0，Precision@K 0.3333，MRR 1.0，错误召回率0.1 | MySQL→Embedding→Milvus真实链路可测；Top-K=3存在噪声 |
| RAG参数对比 | 9组Top-K/阈值组合 | 当前合成集Top-K=1时Precision为1.0 | 参数选择有数据依据；不能外推到真实公司数据 |
| 真实Reviewer基线 | 12个缺陷样本 | Precision 0.3636，Recall 0.3333，3例结构化输出失败 | 已建立真实基线，并发现契约稳定性和识别能力不足 |
| 真实Reviser基线 | 6个修正样本 | 严格修复率0.1667，保留率1.0，1例失败 | Reviser不会破坏保留项，但修复能力仍需改进 |
| 三方案真实烟测 | 1份需求×3组 | 146.60s / 122.53s / 243.42s；完整组修正1次 | 三组真实执行、耗时与Token采集已连通 |
| 长PRD需求分析 | 2735字符、2片段 | 222.75秒完成，未发生JSON截断 | Map-Merge链路可运行；问题跨片段精度仍需优化 |
| 自动化回归 | 默认本地测试 | 结果见`CURRENT_STATUS.md` | 核心流程具备稳定回归保护 |

## 暂时不能写入简历的结论

- 不能写“RAG显著提高测试覆盖率”：当前三方案只烟测1份需求，且该次RAG受修复前控制台编码问题影响。
- 不能写“Reviewer准确率达到较高水平”：真实基线Precision和Recall仍较低。
- 不能写“Reviser显著提升质量”：严格修复率当前只有0.1667。
- 不能写“支持生产级高并发”：尚未实现后台任务、执行租约、SSE和完整并发压测。
- 不能写“多Agent自主协作”：当前是代码控制节点选择和边界的受控编排。

## 推荐简历表述

> 设计并实现面向图文PRD的AI测试分析助手，采用受控Agent编排串联需求结构化、RAG历史资产检索、测试点生成及Reviewer/Reviser质量闭环；针对长PRD单轮JSON易截断问题实现章节感知Map-Merge分析，通过Application Service与Repository隔离页面和领域逻辑，使用MySQL版本化快照与事件实现任务恢复，并以Milvus建立可追溯知识检索。构建文档解析、RAG、评审和修正离线评测及pytest回归体系，并基于真实模型实验记录耗时、Token和失败降级证据。

面试时应主动补充：三方案当前只完成1份真实烟测，质量收益仍需扩大样本验证。

## 三分钟讲解顺序

1. 痛点：PRD信息复杂、历史用例难复用、LLM容易遗漏或无依据扩写。
2. 方案：受控状态机拆成分析、检索、生成、评审、修正和报告节点。
3. 安全边界：信息不足暂停，人工确认后恢复；Orchestrator决定节点，LLM不直接操作数据库。
4. 工程化：Application Service、Repository、MySQL快照、事件和重复执行保护。
5. 知识闭环：确认后的完整资产存MySQL，检索Chunk存Milvus，通过资产ID回查来源。
6. 质量证据：展示真实RAG、Reviewer/Reviser基线和三方案烟测，同时说明限制。
7. 下一步：优先扩充脱敏样本和改进语义评分，不急于增加多Agent或复杂前端。

## 最值得准备的面试问题

1. 为什么称为受控Agentic Workflow，而不是自主Agent？
2. Orchestrator、Application Service和Repository分别负责什么？
3. 用户补充信息后如何恢复同一任务且不绕过状态机？
4. MySQL快照和事件表为什么要分开？
5. 如何避免Streamlit rerun导致节点重复执行？
6. Milvus只保存Chunk时，如何关联MySQL中的完整知识资产？
7. 为什么RAG必须评估错误召回，而不只看Recall？
8. ContextBuilder如何控制每个节点的输入和Token预算？
9. Reviewer/Reviser真实基线不好看，为什么仍有项目价值？
10. 如果迁移FastAPI和后台任务，状态机与幂等设计如何复用？

## 证据入口

- 当前进度：`docs/CURRENT_STATUS.md`
- 完整开发记录：`docs/DEVELOPMENT_LOG.md`
- 学习与面试复盘：`docs/LEARNING_NOTES.md`
- 评测结果：`evaluation/results/`
- 秋招路线图：`docs/roadmap/AUTUMN_RECRUITMENT_ROADMAP.md`
