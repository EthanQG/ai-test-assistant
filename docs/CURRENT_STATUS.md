# Test Analysis Agent 当前开发状态

更新时间：2026-08-11

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.16.9第一小步：`f65f08f 阶段2.16.9：建立稳定需求陈述提取`
- 阶段2.16.9第二小步：`b7583a1 阶段2.16.9：接入紧凑ID需求分析`
- 本地提交尚未推送，由用户手动执行`git push`

## 当前阶段：2.16.10 长PRD检索上下文预算适配（已完成）

V1完整验收发现，长PRD需求分析生成79条事实和61条规则后，知识检索上下文把原始需求及全部分析结果重复拼接，触发`8081 > 4000`输入预算错误。本阶段只调整知识检索的ContextBuilder：

1. 原始需求、事实、规则、状态和风险分别使用明确字符预算；
2. 优先保留包含数字、金额、状态、权限、幂等等关键提示的条目，再按原顺序填充；
3. 风险依据限制为120字符，完全重复的风险在检索视图中去重；
4. 被裁剪分区写入`context_metrics.truncated_sections`；
5. AgentState中的完整需求分析结果不被修改，Generator、Reviewer和最终报告仍读取完整状态。

真实回归中，知识检索查询缩减到2835字符并越过原预算阻断。Embedding服务随后30秒超时，Agent按既有规则降级为无历史上下文并继续；任务生成43条测试点并进入Reviewer/Reviser。最终因第二轮Reviewer返回非法字段类型而失败，该问题属于独立的结构化评审稳定性缺陷，不属于本阶段修复范围。

## 上一阶段：2.16.9 长PRD紧凑ID分析（已完成）

长PRD不再要求模型在每个分片中重复输出完整事实和规则文本：

1. Python从原始分片提取稳定陈述，分配`S001`等ID，并保留章节、分片和字符范围；
2. LLM分片分析只返回事实、规则和状态对应的ID，以及少量带依据ID的风险；
3. Python根据ID回填原文，未知ID会被严格拒绝；
4. 待确认问题改为整份需求的一次全局审核，避免各分片重复提问；
5. 长文仍保留最多3层的有界截断拆分，普通超时和校验错误不会触发无界重试；
6. DeepSeek V4默认开启思考模式。结构化JSON调用现在显式关闭思考模式，避免隐藏推理消耗`max_tokens`并显著拉长同步等待；普通文本调用行为不变。

短PRD仍使用原有完整结构化契约，AgentState、Orchestrator、节点顺序和页面交互未修改。

## 真实验证证据

固定输入：`examples/prd/电商订单履约与优惠结算需求.md`，2735字符，初始2个分片。

| 方案 | 模型 | 结果 | 耗时 | 调用/拆分 |
| --- | --- | --- | ---: | --- |
| 2.16.8截断保护 | deepseek-v4-flash | 完成 | 319.55秒 | 8次 / 2次 |
| 2.16.9紧凑ID，思考模式仍开启 | deepseek-v4-flash | 失败，JSON截断 | 324.30秒 | 失败于全局问题审核 |
| 2.16.9紧凑ID，结构化调用关闭思考 | deepseek-v4-flash | 完成 | 13.38秒 | 3次 / 0次 |

最终结果包含81条稳定陈述、79条事实、61条规则、17条状态流转、18条风险和2个待确认问题，任务进入`waiting_for_user`。报告保存于`evaluation/results/long_requirement_compact_v1.json`。

该结果只证明同一份合成演示PRD上的链路改善，不能外推为任意长度、任意领域PRD均达到相同比例的性能提升。

## 验证结果

阶段收尾前执行：

```text
python -m pytest -q
496 passed，10 skipped

python -m compileall -q agent application repositories services utils views tests main.py evaluation
通过

git diff --check
通过
```

跳过项均为显式环境变量保护的真实MySQL、OCR等外部集成测试。默认全量测试不调用真实LLM、Embedding、Milvus、MySQL、OCR或视觉模型。

## 当前限制

- 当前真实验证只有1份2735字符合成PRD，尚未覆盖更长文档和更多业务领域；
- 两个陈述批次仍为同步串行执行，模型或网络变慢时页面仍会等待；
- ID分类减少输出重复，但模型仍可能漏分类或错误分类，后续应通过离线金标准评测质量；
- 结构化调用关闭思考模式提升了速度和输出稳定性，但可能影响复杂语义判断，需要扩大样本比较；
- 阶段2.17的FastAPI、后台任务、SSE和Vue尚未实现。
- 长PRD完整验收仍可能受Embedding超时和Reviewer结构化字段漂移影响；本次只修复知识检索输入预算。

## 下一步建议

下一小步应单独处理Reviewer结构化字段漂移：保持严格领域校验，同时在LLM边界对可安全归一化的字符串/对象形式建立明确兼容规则。Embedding超时应先检查本地Ollama代理和服务状态，不应通过删除RAG或无限增加超时掩盖。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest -q
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件、PRD和开发日志。
