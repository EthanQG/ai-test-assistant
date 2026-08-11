# Test Analysis Agent 当前开发状态

更新时间：2026-08-11

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，完整历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.16.9第一小步：`f65f08f 阶段2.16.9：建立稳定需求陈述提取`
- 阶段2.16.9第二小步：`b7583a1 阶段2.16.9：接入紧凑ID需求分析`
- 本地提交尚未推送，由用户手动执行`git push`

## 当前阶段：2.17.1 FastAPI同步薄接口（已完成）

新增`api/`传输适配层，复用`TestAnalysisApplicationService`，提供健康检查、Swagger以及任务创建、列表、详情、同步推进、补充信息、业务规则确认、人工反馈、失败重试和删除接口。API只构造现有Command并返回`TaskView.to_dict()`的隔离传输结果，不接受节点名称，也不复制Orchestrator状态机。

当前`POST /advance`仍同步执行一个Agent节点；后台Worker、轮询进度和SSE尚未实现。Streamlit页面未改动，仍可作为V1演示入口。

## 上一阶段：2.16.14 V1长PRD完整功能验收（已完成）

使用2735字符电商PRD执行真实Application Service主链路，任务`25858f12-28c2-42ad-a37c-f85868fc9224`完成需求分析、2项补充恢复、Milvus检索、测试点生成、3轮Reviewer和2轮Reviser。Embedding生成768维向量，Milvus从5条数据中命中1条（0.6274）；测试点42条，经两轮修正后57条，最终Reviewer为82分。任务按设计达到自动修正上限并转入人工反馈入口，没有异常、JSON截断或Embedding超时。

总执行约416秒，记录34次服务调用，provider Token为135375。MySQL使用新Application Service实例按同一task_id恢复成功；再次`advance_task`没有新增指标或重复执行节点。长PRD因仍有未覆盖项未生成最终报告，这是质量门禁的预期结果；短需求完成态和报告下载已有自动化与真实验收证据。

## 上一阶段：2.16.13 长PRD二次评审输出预算（已完成）

真实验收在33条测试点经Reviser扩展为52条后，第二轮Reviewer需要同时返回79条需求覆盖映射，合法JSON达到原8192输出上限。仅Reviewer节点改用16384的有界输出额度；Generator、Reviser和其他结构化调用保持原限制。更大规模任务若仍超限，应改为ID化覆盖映射，不继续无界提高额度。

## 上一阶段：2.16.12 Embedding直连配置修复（已完成）

真实验收中的Embedding请求超时目标为`127.0.0.1:7890`，说明旧RAG客户端继承了启动进程的环境代理，没有直连`.env`配置的Ollama。旧`MilvusRAGManager`现读取`OLLAMA_BASE_URL`、`EMBEDDING_MODEL`和`EMBEDDING_TIMEOUT`，并使用不继承环境代理的独立Session。对配置端点执行只读健康检查耗时0.09秒，确认`nomic-embed-text:latest`可用。

## 上一阶段：2.16.11 Reviewer结构化字段稳定性（已完成）

真实长PRD第二轮评审先后出现`missing_scenarios`对象项和`hallucination_issues`字符串项。Reviewer契约现在进一步明确两类字段格式，并只兼容可安全解释的常见漂移：缺失场景对象仅提取明确文本字段；字符串幻觉问题转换为保守的领域问题，仍会阻止评审通过。未知对象结构继续拒绝，不放宽分数、覆盖率和必填字段校验。

## 上一阶段：2.16.10 长PRD检索上下文预算适配（已完成）

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

下一阶段2.17.2实现受控后台任务执行和幂等启动，使HTTP请求不再等待真实Agent节点。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest -q
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文件、PRD和开发日志。
