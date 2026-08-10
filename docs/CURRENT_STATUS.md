# Test Analysis Agent 当前开发状态

更新时间：2026-08-10

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.15.2：`7826099 阶段2.15.2：完善PDF与DOCX结构化解析`
- 阶段2.15.3：`b823c2d 阶段2.15.3：增加扫描文档OCR与置信度分流`
- 阶段2.15.3验收：`98684e2 阶段2.15.3：完成真实OCR运行验收`
- 阶段2.15.4：`ca58c5f 阶段2.15.4：增加有界多模态理解`
- 阶段2.15.5：`f6d1650 阶段2.15.5：增加关键问题筛选与限流`
- 阶段2.15.6：`3961861 阶段2.15.6：增加节点上下文构建与输入预算`
- 阶段2.15.7：`039f798 阶段2.15.7：增加分层性能指标与错误分类`
- 阶段2.16.1：`143b2a0 阶段2.16.1：完成十份评测金标准复核`
- 阶段2.16.2第一小步：`744228b 阶段2.16.2：建立图文解析评测样本`
- 阶段2.16.2第二小步：`7395b8d 阶段2.16.2：增加文档解析确定性评分`
- 阶段2.16.2第三小步：`5a32bc6 阶段2.16.2：增加流程与UI语义评分`
- 阶段2.16.3第一小步：`2760923 阶段2.16.3：建立RAG资产级评测指标`
- 阶段2.16.3第二小步：`1f6537b 阶段2.16.3：接入RAG检索服务评测边界`
- 阶段2.16.3第三小步：`2533806 阶段2.16.3：完成真实RAG链路评测`

## 当前阶段：2.16.3 RAG专项评测（第四小步已完成）

本轮为真实RAG实验准备可重复资产和显式执行入口：

1. 新增5份完全虚构查询，覆盖订单库存、退款、登录锁定、文件上传和角色权限；
2. 每份查询标注期望召回资产和明确不应召回资产；
3. `Recall@K`衡量相关资产是否找全；
4. `Precision@K`衡量前K个位置中相关资产占比；
5. `MRR`衡量第一个相关资产出现得是否足够靠前；
6. `forbidden_hit_rate`衡量已知无关资产是否污染结果；
7. Runner按case输出明细并计算平均指标；
8. 新增5份与查询金标准一一对应的合成KnowledgeAsset种子；
9. 种子包含需求、事实、规则、风险、测试点和Reviewer结果，不包含公司数据；
10. 真实Runner已依次写入MySQL、索引Milvus、调用Retrieval Service并输出独立报告；
11. 必须显式设置`RUN_RAG_INTEGRATION_EVALUATION=1`和MySQL资产Repository，默认pytest不会访问外部服务。

## 当前数据流

```text
虚构查询 + 相关/禁止资产标注
→ Fake Embedding / Fake VectorSearch
→ KnowledgeAssetRetrievalService
→ InMemoryKnowledgeAssetRepository权威回查
→ candidates转换为排序asset_id
→ 资产级逐项比较
→ Recall@K / Precision@K / MRR / forbidden_hit_rate
```

## 验证结果

```text
python -m pytest -q tests/unit/evaluation/test_rag_evaluation.py tests/unit/evaluation/test_rag_retrieval_service_evaluation.py
6 passed

python -m pytest -q
444 passed，10 skipped
```

默认全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型；真实RAG评测通过独立命令显式运行。

真实RAG结果（5份合成资产，Top-K=3，`nomic-embed-text`）：

- Mean Recall@3：1.0
- Mean Precision@3：0.3333
- Mean MRR：1.0
- Mean forbidden hit rate：0.1
- 权限查询召回了明确禁止的订单库存资产，因此不能只报告Recall和MRR

参数对比结果：

- Top-K：1、2、3；阈值：0.65、0.70、0.75，共9组；
- 阈值0.65且Top-K为2或3时，宏平均禁止命中率为0.1；
- 阈值0.70和0.75的9项组合中，Recall均保持1.0且禁止命中率为0；
- 当前每个查询只标注1个相关资产，所以Top-K=1的Precision=1不能外推到真实多相关资产场景；
- 不自动修改线上默认阈值，0.70只作为后续扩大样本后的候选值。

## 当前限制

- 5份查询、KnowledgeAsset和向量命中均为合成数据
- Fake链路只证明服务边界接线、权威回查和指标计算正确，不证明现有Embedding或阈值效果
- 当前只有5份简单合成资产的真实结果，不能外推到真实PRD和大规模知识库
- `k=3`是当前评测参数，不代表已经证明最优

## 下一步：阶段2.16.4 Reviewer/Reviser专项评测

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 构造遗漏、重复、幻觉、模糊预期和缺失来源等可控缺陷；
2. 评估Reviewer的缺陷检测Precision、Recall、误报和漏报；
3. 再验证Reviser是否按建议修复且没有破坏已正确测试点；
4. 默认使用Fake模型输出固定缺陷，不调用真实LLM。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
