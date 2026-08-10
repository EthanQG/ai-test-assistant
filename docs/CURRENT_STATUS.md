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

## 当前阶段：2.16.3 RAG专项评测（第一小步已完成）

本轮先固定RAG查询金标准和资产级指标，不修改在线检索逻辑，也不连接真实Milvus：

1. 新增5份完全虚构查询，覆盖订单库存、退款、登录锁定、文件上传和角色权限；
2. 每份查询标注期望召回资产和明确不应召回资产；
3. `Recall@K`衡量相关资产是否找全；
4. `Precision@K`衡量前K个位置中相关资产占比；
5. `MRR`衡量第一个相关资产出现得是否足够靠前；
6. `forbidden_hit_rate`衡量已知无关资产是否污染结果；
7. Runner按case输出明细并计算平均指标；
8. pytest只使用Fake资产ID列表，不调用Embedding、Milvus或MySQL。

## 当前数据流

```text
虚构查询 + 相关/禁止资产标注
→ retrieve(query, k)返回排序后的asset_id
→ 资产级逐项比较
→ Recall@K / Precision@K / MRR / forbidden_hit_rate
```

## 验证结果

```text
python -m pytest tests/unit/evaluation/test_rag_evaluation.py -q
5 passed

python -m pytest -q
438 passed，10 skipped
```

全量回归未调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 5份查询和资产ID均为合成数据，还没有对应的真实MySQL/Milvus资产
- Fake测试只证明指标计算正确，不证明现有Embedding或阈值效果
- 当前没有真实Recall@K、Precision@K或MRR结果
- `k=3`是当前评测参数，不代表已经证明最优

## 下一步：阶段2.16.3 RAG专项评测（第二小步）

下一阶段不再继续扩张在线功能，开始建立可对比的质量证据：

1. 将现有`KnowledgeAssetRetrievalResult.candidates`适配为排序asset_id；
2. 用Fake Embedding、VectorSearch和内存Repository跑通真实Retrieval Service边界；
3. 输出受控链路报告，不连接外部服务；
4. 真实Milvus评测仍需用户明确同意。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
