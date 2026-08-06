# Test Analysis Agent 代码学习与面试复盘

本文档帮助项目作者真正理解代码，而不是只记住项目用了哪些技术。内容覆盖当前已经完成的阶段，并提供概念解释、代码定位、调用链、面试参考答案和动手练习。

> 使用原则：先阅读对应代码，再尝试不看答案口述，最后完成动手练习。参考答案用于校正理解，不建议逐字背诵。

## 一、学习目标与掌握标准

秋招前应达到以下标准：

- 能在 30 秒内说明项目解决的问题
- 能在 3 分钟内讲清当前架构和执行链路
- 能说明每个核心类的职责、输入和输出
- 能解释 LLM、Prompt、RAG、Embedding、Milvus、Workflow、Agent、State 和 Event
- 能回答为什么使用 Service、依赖注入和 Fake Service
- 能区分已经实现的能力与规划中的能力
- 能独立完成一个小修改并补充测试
- 简历上的每句话都有代码、测试或真实数据支撑

### 当前掌握检查表

- [ ] 能画出现有测试报告生成调用链
- [ ] 能解释 System Prompt 和 User Prompt 如何发送
- [ ] 能解释 RAG 的完整检索流程
- [ ] 能解释 Service 层解决了什么问题
- [ ] 能解释依赖注入为什么有利于测试
- [ ] 能解释 `yield` 为什么适合流式输出
- [ ] 能解释 AgentState 和 AgentEvent 的区别
- [ ] 能解释受控 Agent 与固定 Workflow 的区别
- [ ] 能理解现有245项单元测试分别保护哪些业务边界
- [ ] 能独立增加一个状态字段、事件或测试

---

## 二、项目整体认识

### 2.1 项目解决什么问题

测试工程师需要阅读 PRD、识别业务规则、设计正常/边界/异常场景，还要复用历史 Bug 经验。人工处理耗时且容易遗漏。项目使用 LLM 分析需求，通过 RAG 检索历史测试资产，生成测试分析报告，并逐步加入 Agent 的状态、执行轨迹、质量评审和自动修正能力。

### 2.2 30 秒项目介绍参考答案

> 我实现了一个面向测试工程师的测试分析 Agent。用户输入或上传 PRD 后，RequirementAnalyzer先提取需求事实、业务规则、风险和关键待确认项；信息不足时页面暂停并允许用户回答或选择暂不确定。随后Agent检索Milvus历史测试资产，生成结构化测试点，通过Reviewer评分并在受控次数内由Reviser修正，最后由Finalizer生成可下载的表格化Markdown报告。整个流程由Python Orchestrator根据AgentState逐节点编排，页面能够展示决策和事件轨迹。

### 2.3 当前真实执行链路

```text
用户输入文本或上传PRD
  → views/tab_test_points.py
  → TestAnalysisApplicationService
  → TaskRepository加载/保存TaskRecord
  → Application Service调用AgentOrchestrator
      → RequirementAnalyzer
      → KnowledgeRetriever
          → RAGService / Embedding / Milvus
      → TestPointGenerator
      → TestPointReviewer
      → TestPointReviser（未达标且未达到上限时）
      → Finalizer
  → Application Service返回只读TaskView
  → Streamlit展示状态、轨迹、测试点、评分和报告
```

### 2.4 当前还没有实现什么

以下能力暂时不能写成“已经实现”：

- Agent 自主选择工具
- MySQL Repository代码已经实现，但真实MySQL跨服务重启恢复尚未验收
- 单个LLM响应的Token级流式展示
- 多 Agent 协作
- FastAPI + React/Vue 前后端分离
- 经过评测证明的覆盖率提升
- 真实的自动化用例生成和日志根因分析

---

## 三、阶段 1：Service 层与依赖解耦

### 3.1 核心文件

- `services/llm_service.py`
- `services/rag_service.py`
- `services/document_service.py`
- `utils/test_manager.py`
- `tests/unit/legacy/test_test_manager.py`

### 3.2 Service 是什么

Service 是业务层访问某种能力的稳定入口。

例如业务代码只需要调用：

```python
llm_service.generate(prompt, system_prompt)
```

不需要关心底层使用 DeepSeek、OpenAI 还是本地模型，也不需要在业务层重复构造 HTTP 请求。

### 3.3 为什么要增加 Service 层

改造前：

```text
TestAssistantManager
  → 直接创建DeepSeekClient
  → 直接创建MilvusRAGManager
```

问题：

- 业务逻辑依赖具体实现
- 更换模型需要修改业务代码
- 单元测试容易发起真实网络请求
- 后续包装成 Agent Tool 时边界不清晰

改造后：

```text
TestAssistantManager
  → LLMService
  → RAGService
  → PromptService
```

收益：

- 业务层只依赖稳定接口
- 底层实现可以替换
- 测试可以注入 Fake Service
- Agent 节点以后可以复用相同能力

### 3.4 什么是依赖注入

`TestAssistantManager` 不再把所有依赖写死，而是允许外部传入：

```python
manager = TestAssistantManager(
    llm_service=fake_llm,
    rag_service=fake_rag,
)
```

如果没有传入，再使用默认真实 Service。

依赖注入不是某个框架专属能力。它的核心思想是：

> 一个对象需要的依赖由外部提供，而不是只能在对象内部固定创建。

### 3.5 Fake Service 是什么

Fake Service 是测试中使用的可控替代实现。例如：

```python
class FakeLLMService:
    def generate(self, prompt, system_prompt=""):
        return "generated report"
```

它的作用：

- 不访问真实 DeepSeek
- 不产生费用
- 返回结果稳定
- 可以记录收到的 Prompt
- 可以主动模拟异常

### 3.6 为什么 LLMService 延迟创建客户端

`LLMService` 只有第一次真正调用模型时才创建 `DeepSeekClient`。这样导入模块、创建业务对象和运行不需要模型的测试时，不会立即校验 API Key。

这种方式叫延迟初始化（Lazy Initialization）。

### 3.7 `yield` 和流式输出

DeepSeek 开启 `stream=True` 后，会分段返回内容。`call_stream()` 每收到一段，就：

```python
yield content
```

调用方可以边接收边展示，不必等待完整报告生成。

普通 `return`：

```text
等待全部完成 → 一次返回
```

生成器 `yield`：

```text
收到一段 → 返回一段 → 保留执行位置 → 继续接收
```

### 3.8 面试问题与参考答案

#### 问：为什么不让 TestAssistantManager 直接调用 DeepSeek？

答：

> 如果业务层直接依赖 DeepSeekClient，模型切换、错误处理和测试都会与具体实现耦合。我增加 LLMService 作为稳定边界，业务层只调用 generate 或 generate_stream。单元测试时可以注入 FakeLLMService，避免真实网络请求，也方便后续把模型能力封装为 Agent 节点。

#### 问：增加 Service 会不会只是多套一层？

答：

> 如果 Service 只是机械转发且永远不会替换或测试，确实可能是无意义封装。但这个项目需要切换真实/Fake依赖，还会被多个 Agent 节点复用，因此统一模型调用、RAG 返回结构和文档解析边界有实际价值。

#### 问：什么是依赖注入？项目中如何使用？

答：

> 依赖注入是让对象需要的依赖从外部传入。项目中的 TestAssistantManager 构造函数接受 LLMService 和 RAGService；生产环境不传参数时使用真实服务，测试时传入 Fake 服务。因此业务测试不依赖 DeepSeek 和 Milvus。

#### 问：为什么使用流式输出？

答：

> 测试报告可能较长，如果等待完整响应，用户会长时间看不到结果。流式接口每收到一个增量内容就通过生成器 yield 给 Streamlit，降低用户感知延迟。它没有缩短模型总生成时间，但改善了交互体验。

### 3.9 动手练习

- [ ] 给 `FakeLLMService` 增加调用次数统计
- [ ] 模拟 LLM 抛出异常并编写测试
- [ ] 说明延迟初始化与立即初始化的区别
- [ ] 将 `generate_stream()` 的结果手动拼接成完整字符串

---

## 四、阶段 1.5：System Prompt 与 User Prompt

### 4.1 核心文件

- `prompts/test_points.txt`
- `services/prompt_service.py`
- `utils/test_manager.py`
- `utils/ai_client.py`
- `tests/unit/services/test_prompt_service.py`

### 4.2 两种 Prompt 的职责

System Prompt 保存稳定规则：

- 模型角色
- 信息边界
- 测试设计原则
- 输出结构和格式

User Prompt 保存本次动态数据：

- 当前需求
- 本地 Bug 经验
- RAG 检索结果
- 本次任务指令

### 4.3 两者是否拼接成一个字符串

不会。

代码把它们作为不同角色放入同一次请求：

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]
```

因此准确表述是：

> System Prompt 和 User Prompt 在同一次 LLM 请求中发送，但保持为两条不同角色的消息。

### 4.4 为什么动态内容不放在 System Prompt

System Prompt 应保持稳定，便于复用、测试和理解优先级。PRD 和 RAG 结果每次都会变化，属于本次任务上下文，更适合作为 User Prompt。

把动态内容混入 System Prompt 会导致：

- 模板和任务数据职责混乱
- 占位符容易漏替换
- Prompt 难以单独测试
- 历史资产可能被模型误认为长期规则

### 4.5 原占位符问题

原来的系统提示词包含：

```text
{prd_content}
{bug_kb_content}
```

但代码只读取文本，没有调用 `.format()`，所以模型会看到字面量占位符。真实 PRD 又在 User Prompt 中传入，导致定义重复且容易误导模型。

修复方式：

- 从 System Prompt 删除动态占位符
- 由 `PromptService` 构建 User Prompt
- 流式和非流式生成复用同一构建逻辑

### 4.6 为什么区分需求事实、推导风险、待确认项

测试分析有一个天然矛盾：

- 不能编造 PRD 中不存在的业务规则
- 又需要识别 PRD 未明确描述的异常风险

因此分为：

#### 需求事实

PRD 明确给出的角色、规则、数值、状态和预期。

#### 推导风险

根据真实操作推导的测试风险，必须写出依据。例如需求存在“提交订单”操作，可以提出重复提交和幂等风险，但不能声称系统已经实现了幂等。

#### 待确认项

缺少信息，无法确定预期结果。例如只说“支持文件上传”，但没有说明格式和大小限制，就应该提出确认问题，而不是编造限制。

### 4.7 `Path` 和 `@staticmethod`

`PromptService` 使用 `Path` 定位 Prompt 文件，避免依赖程序从哪个目录启动。

`build_test_points_prompt()` 使用 `@staticmethod`，因为它只根据传入参数构造字符串，不依赖某个实例的属性。

### 4.8 面试问题与参考答案

#### 问：System Prompt 和 User Prompt 有什么区别？

答：

> System Prompt 定义模型的长期角色和行为约束，例如测试方法、信息边界和输出格式；User Prompt 提供本次任务数据，例如 PRD、本地 Bug 经验和 RAG 结果。项目将两者作为不同 role 的 messages 一起发送，而不是拼成一个字符串。

#### 问：为什么 RAG 内容放在 User Prompt？

答：

> RAG 结果是根据当前 PRD 动态检索出来的，只对本次任务有效，因此属于任务上下文。System Prompt 应保持稳定，否则历史内容可能被误认为长期规则，也不利于测试和维护。

#### 问：如何降低大模型幻觉？

答：

> 项目从 Prompt 层明确区分需求事实、推导风险和待确认项；历史资产只能提供测试思路，不能覆盖当前需求事实；缺少业务规则时要求输出待确认项。后续还会通过结构化输出、来源标记和 Reviewer 进一步校验。

#### 问：为什么不把所有内容都放进一个 Prompt？

答：

> 虽然模型仍可能响应，但角色边界会变得模糊。拆分后可以分别测试稳定规则和动态输入，也便于替换 PRD、过滤空的 RAG 区块，并让模型知道哪些是长期指令、哪些是本次数据。

### 4.9 动手练习

- [ ] 手写一份订单需求的 User Prompt
- [ ] 解释为什么空 RAG 结果不应生成空区块
- [ ] 给 PromptService 增加一个可选的用户补充说明
- [ ] 为新增区块编写“有值”和“空值”两个测试

---

## 五、RAG、Embedding 与 Milvus

这部分能力在重构前已经存在，但属于项目面试高频内容，必须掌握。

### 5.1 核心文件

- `services/rag_service.py`
- `utils/knowledge_base.py`

### 5.2 RAG 是什么

RAG（Retrieval-Augmented Generation，检索增强生成）的流程是：

```text
当前PRD
  → Embedding模型
  → 查询向量
  → Milvus相似度检索
  → Top-K历史测试资产
  → 相似度阈值过滤
  → 加入User Prompt
  → LLM生成报告
```

它解决的问题是：通用大模型不知道项目历史 Bug 和团队测试经验。

### 5.3 Embedding 是什么

Embedding 把文本转换为一组浮点数，也就是向量。语义相似的文本，其向量方向通常更接近。

例如：

```text
"支付超时重试"
"支付接口超时后再次发起"
```

即使词语不完全相同，向量仍可能接近。

当前项目使用 `nomic-embed-text` 生成 768 维向量。

### 5.4 为什么使用余弦相似度

余弦相似度关注两个向量的方向是否接近，而不是向量绝对长度，常用于文本语义相似度。

概念公式：

```text
cos(A, B) = A·B / (|A| × |B|)
```

越接近 1，通常表示语义越相似。

### 5.5 Top-K 和阈值

- `top_k=2`：先取最相似的 2 条候选
- `similarity_threshold=0.60`：只有相似度不低于 0.60 才加入上下文

Top-K 控制最多取多少条；阈值控制候选是否足够相关。两者共同减少无关历史资产污染。

这些值目前是经验配置，还没有通过正式评测证明最优，面试时不能说“0.60 是最佳阈值”。

### 5.6 为什么不把整个知识库放进 Prompt

- 可能超过上下文窗口
- Token 成本更高
- 无关内容会干扰模型
- 历史业务词可能污染当前需求
- 难以展示具体召回证据

RAG 的目标是只提供与当前任务相关的少量证据。

### 5.7 RAG 失败时会怎样

当前检索逻辑对 Milvus 连接失败、空库、Embedding 失败或无命中进行了降级，多数情况下返回空上下文，报告仍可只基于当前 PRD 和本地知识生成。

这是“可用性降级”，但也意味着结果可能少了历史经验，需要在后续执行轨迹中明确展示 RAG 是否成功。

### 5.8 面试问题与参考答案

#### 问：为什么使用 RAG，而不是微调模型？

答：

> 历史测试资产会持续增加，RAG 可以增量写入并立即检索，不需要重新训练模型；它还能展示具体召回内容，成本和维护复杂度更低。微调更适合稳定的行为或风格学习，不适合频繁更新的事实型知识。

#### 问：为什么不用关键词搜索？

答：

> 关键词搜索适合精确词匹配，但相同测试风险可能使用不同表达。Embedding 检索能匹配语义相似内容。不过向量检索也可能召回错误领域，所以项目增加了相似度阈值，并通过 Prompt 要求历史资产不能覆盖当前需求事实。

#### 问：RAG 一定能提升测试覆盖率吗？

答：

> 不能直接保证。错误召回反而可能污染结果。目前项目只证明了检索链路可工作，还没有完成覆盖率评测。后续需要准备人工标注需求集，对比基础 LLM、LLM+RAG、RAG+Reviewer 的关键风险覆盖率后才能量化结论。

#### 问：Milvus不可用时怎么办？

答：

> 当前实现会降级为空 RAG 上下文，仍然基于 PRD 调用 LLM，避免整个功能不可用。后续会通过 AgentEvent 显示降级状态，并区分“未命中”和“检索失败”。

### 5.9 动手练习

- [ ] 调整 `top_k` 并说明可能影响
- [ ] 解释阈值过高和过低分别有什么风险
- [ ] 为无命中结果增加测试
- [ ] 设计一个登录需求召回支付案例的错误示例

---

## 六、阶段 2.1/2.2：AgentState 与 AgentEvent

### 6.1 核心文件

- `agent/state.py`
- `agent/events.py`
- `agent/__init__.py`
- `tests/unit/agent/test_agent_state.py`

### 6.2 为什么需要 AgentState

固定 Workflow 可以用局部变量按顺序传递数据；Agent 包含多个节点、条件分支、等待用户和修正循环，需要统一记录：

- 原始需求
- 需求分析结果
- RAG 结果
- 当前步骤
- 任务状态
- 报告
- 错误
- 执行历史

`TestAnalysisState` 相当于一次任务的工作记忆。

### 6.3 AgentStatus

当前状态：

```text
pending           等待执行
running           正在执行
waiting_for_user  等待用户补充
completed         已完成
failed            已失败
```

`completed` 和 `failed` 是终止状态，进入后不允许继续执行。

### 6.4 AgentStep

当前定义的标准步骤：

```text
initialize
analyze_requirement
retrieve_knowledge
generate_test_points
review_test_points
revise_test_points
finalize
```

它们是未来受控 Agent 的工作地图，不代表所有节点已经实现。

### 6.5 AgentEvent 与普通日志的区别

普通日志主要给开发者排错，通常是非结构化文本。

AgentEvent 是业务级、结构化的执行记录，包含：

- 事件类型
- 执行步骤
- 用户可读消息
- 结构化数据
- UTC 时间

它可以用于：

- 页面执行轨迹
- API 响应
- 失败定位
- 任务审计
- 后续评测

### 6.6 状态转换保护

当前代码会拒绝：

- 空需求创建任务
- 完成的步骤不是当前步骤
- 等待用户时不调用 `resume()` 就继续
- 空报告完成任务
- 已完成或失败后继续执行

这些限制让 Agent 具有明确边界，避免模型或编排器随意跳步。

### 6.7 `dataclass`

`@dataclass` 自动生成初始化方法等常用代码，适合主要用于保存数据的类。

例如：

```python
@dataclass
class TestAnalysisState:
    requirement: str
    status: AgentStatus = AgentStatus.PENDING
```

### 6.8 `field(default_factory=...)`

列表不能直接写成共享默认值。正确方式：

```python
events: list[AgentEvent] = field(default_factory=list)
```

这样每个 State 都有自己的列表。

如果错误地让多个实例共享同一列表，一个任务添加事件可能影响另一个任务。

### 6.9 Enum

使用 Enum 代替任意字符串：

```python
AgentStatus.RUNNING
```

好处：

- 减少拼写错误
- 可发现合法取值
- 状态比较更清晰
- 序列化时仍可通过 `.value` 输出字符串

### 6.10 `frozen=True`

`AgentEvent` 使用冻结 dataclass，创建后不能随意修改。事件表示已经发生的事实，保持不可变可以避免历史轨迹被意外篡改。

### 6.11 UUID 与 UTC 时间

每个任务使用 UUID 作为唯一 ID，避免依赖自增数据库。

事件使用带时区的 UTC 时间，便于跨时区存储和排序。页面展示时可以再转换为用户本地时区。

### 6.12 为什么需要 `to_dict()`

Python 的 Enum、datetime 和 dataclass 不能直接作为普通 JSON 返回。`to_dict()` 会把它们转换为：

- Enum → 字符串值
- datetime → ISO 8601 字符串
- AgentEvent → 普通字典

这为后续数据库持久化和 FastAPI 响应做准备。

### 6.13 面试问题与参考答案

#### 问：Workflow 和 Agent 有什么区别？

答：

> Workflow 的执行顺序主要由代码预先固定；Agent 会根据当前状态、模型分析和工具结果决定下一步。这个项目采用受控 Agent，不让模型无限自由执行，而是由代码定义合法步骤、状态和最大迭代范围，以保证测试场景下的稳定性和可审计性。

#### 问：加入 AgentState 后项目就是 Agent 了吗？

答：

> 还不是。AgentState 只是统一工作记忆，AgentEvent 只是执行轨迹。项目还需要 RequirementAnalyzer、工具封装、编排器和 Reviewer 等执行节点。当前准确描述是“已完成向 Agent 演进的状态基础”。

#### 问：为什么不用 Streamlit session_state 直接保存？

答：

> session_state 属于页面框架，适合保存 UI 会话数据。如果核心业务依赖它，就难以做单元测试、API 化和后台任务。TestAnalysisState 是与页面无关的领域状态，Streamlit 以后只负责展示或保存这个对象。

#### 问：为什么完成或失败后禁止继续？

答：

> completed 和 failed 表示本次执行已经终止。如果允许继续修改，会导致报告、事件和状态不一致。需要重试时应该创建明确的重试或恢复机制，而不是绕过终止状态。

#### 问：为什么事件要不可变？

答：

> 事件用于描述已经发生的动作。如果历史事件可以被随意修改，执行轨迹和审计结果就不可信。冻结 dataclass 可以降低意外修改风险。

### 6.14 动手练习

- [ ] 给 State 增加 `modules` 字段并更新 `to_dict()`
- [ ] 增加一个新的 AgentStep 和相应测试
- [ ] 创建两个 State，证明它们的 events 列表互不影响
- [ ] 尝试修改冻结的 AgentEvent，观察错误
- [ ] 设计一个 waiting_for_user → running → completed 的完整例子

---

## 七、单元测试与可测试性

### 7.1 当前测试分组

- `test_test_manager.py`：业务入口与 Fake Service
- `test_prompt_service.py`：Prompt 边界和可选区块
- `test_agent_state.py`：状态生命周期和序列化

### 7.2 一个好的单元测试验证什么

单元测试应该验证可观察行为，例如：

- 输入进入了正确 Prompt
- 空可选内容被省略
- RAG 指标被保存
- 非法状态转换被拒绝
- State 可以序列化

不应该依赖：

- 真实 API Key
- 真实 DeepSeek 输出文字
- 远程 Milvus 是否在线
- 网络速度

### 7.3 面试问题与参考答案

#### 问：为什么单元测试不调用真实模型？

答：

> 模型输出具有随机性，网络和服务状态不稳定，而且会产生费用。单元测试关注代码是否正确组织输入、处理返回和更新状态，因此使用 Fake Service。真实模型和 Milvus 的验证应属于单独的集成测试。

#### 问：如何测试流式输出？

答：

> FakeLLMService 的 generate_stream 返回固定片段，测试代码将片段拼接并断言最终结果，同时检查 Fake 记录的 Prompt，从而验证流式透传和输入构造，而不访问真实模型。

#### 问：单元测试通过是否代表系统能上线？

答：

> 不能。单元测试只验证本地模块行为，还需要集成测试、真实模型效果评测、异常网络测试、安全测试和用户验收。当前 127 个测试证明的是代码边界和状态规则，不代表生成质量已经达到生产标准。

---

## 八、常见 Python 语法速查

### 类与构造函数

```python
class LLMService:
    def __init__(self, client=None):
        self._client = client
```

`self` 表示当前实例，`__init__` 在创建对象时初始化属性。

### 类型注解

```python
def generate(prompt: str) -> str:
```

表示期望输入和输出类型，主要帮助阅读、IDE 和静态检查，默认不会自动做运行时校验。

### 可选类型

```python
str | None
```

表示值可以是字符串，也可以是 `None`。

### 列表与字典泛型

```python
list[str]
dict[str, Any]
```

分别表示字符串列表和键为字符串的字典。

### `yield from`

```python
yield from llm_service.generate_stream(...)
```

把内部生成器产生的每个片段继续向外传递。

### 异常

```python
raise ValueError("requirement cannot be empty")
```

主动拒绝非法输入；测试可以使用 `assertRaises` 验证。

---

## 九、项目面试追问链

### 9.1 LLM 调用

1. 为什么选择 DeepSeek？
2. System/User Prompt 如何组织？
3. 为什么使用流式输出？
4. 模型超时或返回异常怎么办？
5. 如何控制 Token 和成本？

当前可回答 2、3；1 需要结合真实选型原因，4 仍需完善超时和重试，5 尚未建立统计，不能夸大。

### 9.2 RAG

1. 为什么使用 RAG？
2. Embedding 如何生成？
3. 为什么使用余弦相似度？
4. Top-K 和阈值如何选择？
5. 如何防止错误召回？
6. 如何证明 RAG 有效？

第 6 题需要后续评测集支持，目前只能说明计划，不能声称已经证明。

### 9.3 Agent

1. Workflow 和 Agent 有什么区别？
2. 为什么使用受控 Agent？
3. State 保存什么？
4. Tool 如何调用？
5. 如何防止无限循环？
6. Reviewer 如何评分？

目前已实现 State、事件、需求分析、知识检索、结构化生成、Reviewer 和单次 Reviser；循环限制和编排器仍是后续工作。

### 9.4 工程质量

1. 如何测试 LLM 应用？
2. 如何处理密钥？
3. 如何跨电脑恢复环境？
4. 为什么要写开发日志？
5. 如何保证重构没有破坏功能？

参考回答重点：

- Fake Service 和单元测试
- `.env` 与 `.env.example`
- GitHub + AGENTS + CURRENT_STATUS
- 每阶段独立 Commit
- 重构前后保持接口并运行回归测试

---

## 十、简历表述边界

### 当前可以写

- 基于 DeepSeek 实现测试分析报告流式生成
- 支持 TXT、Markdown、PDF、DOCX 需求解析
- 基于 Milvus 与文本 Embedding 检索历史测试资产
- 采用 System/User Prompt 分层管理动态上下文
- 通过 Service 和依赖注入降低业务层与外部服务耦合
- 使用 Fake Service 构建不依赖真实网络的单元测试
- 设计 AgentState、状态转换和结构化执行事件

### 完成后才能写

- 实现 RequirementAnalyzer 结构化需求分析
- Agent 根据状态选择知识检索或请求用户补充
- Reviewer 对测试覆盖率进行多维评分
- 低质量结果自动反思和修正
- 通过评测集将关键场景覆盖率提升到某个真实数值
- 基于 FastAPI 和 React/Vue 实现前后端分离

### 禁止使用的空泛描述

- “大幅提升测试效率”——没有测量数据
- “显著提升覆盖率”——没有评测结果
- “实现多 Agent 协作”——尚未实现
- “自主规划并调用工具”——尚未实现
- “生产级高可用”——没有部署和可靠性验证

---

## 十一、建议复习顺序

### 第一轮：理解调用链

1. 阅读 `views/tab_test_points.py`
2. 阅读 `utils/test_manager.py`
3. 阅读 `services/prompt_service.py`
4. 阅读 `services/llm_service.py`
5. 阅读 `utils/ai_client.py`
6. 阅读 `services/rag_service.py`
7. 阅读 `utils/knowledge_base.py`

目标：能从用户点击按钮讲到模型返回内容。

### 第二轮：理解 Agent 基础

1. 阅读 `agent/events.py`
2. 阅读 `agent/state.py`
3. 阅读 `tests/unit/agent/test_agent_state.py`

目标：能说明状态、步骤、事件和合法转换。

### 第三轮：理解测试

1. 阅读`tests/unit/`中三个相关的`test_*.py`
2. 暂时不看答案，预测每个测试为什么通过
3. 主动修改一处代码，让测试失败
4. 恢复代码并重新运行

目标：能自己为下一阶段增加测试。

---

## 十二、阶段完成后的复盘模板

后续每完成一个阶段，在本文档追加：

```markdown
## 阶段X：名称

### 核心文件
### 新增功能
### 涉及的Python知识
### 调用链
### 为什么这样设计
### 面试问题与参考答案
### 当前限制
### 动手练习
### 掌握检查
```

掌握检查：

- [ ] 我能不看文档解释本阶段目标
- [ ] 我能画出调用链
- [ ] 我能解释核心类和方法
- [ ] 我能说明至少一个设计取舍
- [ ] 我能回答三个连续追问
- [ ] 我能独立完成一个小修改并补测试

---

## 十三、阶段 2.3：RequirementAnalyzer

### 13.1 核心文件

- `agent/models.py`
- `agent/requirement_analyzer.py`
- `prompts/requirement_analysis.txt`
- `services/prompt_service.py`
- `agent/state.py`
- `tests/unit/agent/test_requirement_analyzer.py`

### 13.2 本阶段实现了什么

`RequirementAnalyzer` 接收一个包含原始 PRD 的 `TestAnalysisState`，调用 LLM 获得 JSON，经过代码校验后写回：

- 需求摘要
- 业务模块
- 需求事实
- 业务规则
- 状态流转
- 推导风险及依据
- 待确认项

它是项目第一个真正使用 LLM、State 和 Event 的 Agent 节点。

### 13.3 调用链

```text
RequirementAnalyzer.analyze(state)
  → state.start_step(ANALYZE_REQUIREMENT)
  → PromptService.load_system_prompt()
  → PromptService.build_requirement_analysis_prompt()
  → LLMService.generate()
  → RequirementAnalysisResult.from_json()
  → RequirementAnalyzer._apply_result()
  → state.complete_step()
  → 有open_questions时state.wait_for_user()
```

### 13.4 为什么要求结构化 JSON

如果直接让 LLM 输出 Markdown，后续节点要重新从自然语言中提取模块、事实和风险，容易产生歧义。

JSON 的价值：

- 字段固定
- 可以校验类型
- 方便写入 State
- 方便单元测试
- 方便未来 API 返回
- Reviewer 可以按字段处理

但“要求模型输出 JSON”不等于结果一定合法，所以代码仍需要解析和校验。

### 13.5 结构化模型与普通字典

普通字典可以保存任意键，拼写错误要到运行时很晚才发现。`RequirementAnalysisResult` 明确定义合法字段，并在创建前校验输入。

`InferredRisk` 单独建模，强制每条风险同时包含：

```json
{
  "risk": "重复提交可能重复扣减库存",
  "basis": "需求存在提交和库存扣减操作"
}
```

这能避免模型只给风险结论，却不说明推导依据。

### 13.6 JSON 解析与校验

解析流程：

```text
LLM原始文本
  → 去除首尾空白
  → 兼容```json代码围栏
  → json.loads()
  → 检查顶层必须是对象
  → 拒绝未知顶层字段
  → 检查字符串和数组类型
  → 检查风险结构
  → 生成RequirementAnalysisResult
```

兼容代码围栏是为了处理模型偶尔返回：

````text
```json
{"summary": "..."}
```
````

Prompt 仍明确要求不要输出围栏；解析兼容属于防御性处理，不代表鼓励模型违反格式。

### 13.7 为什么拒绝未知字段

Prompt 要求只能使用固定字段。如果模型额外返回 `confidence`、`recommendation` 等内容，而代码默默忽略，可能掩盖 Prompt 漂移或字段拼写错误。

严格拒绝的好处：

- 尽早发现模型输出变化
- 防止错误字段静默丢失
- 保持节点之间的数据契约稳定

代价是模型轻微偏离格式也会失败。后续可以结合有限重试或结构化输出 API 改善，但不能直接放弃校验。

### 13.8 节点如何更新 State

分析开始：

```python
state.start_step(
    AgentStep.ANALYZE_REQUIREMENT,
    "正在分析需求结构与信息边界",
)
```

校验成功后 `_apply_result()` 将结果复制到 State，再记录完成事件。

使用 `list(...)` 创建新列表，避免 State 和结果对象意外共享可变列表。

### 13.9 为什么先 complete_step 再 wait_for_user

存在待确认项不代表需求分析失败。节点已经成功识别出事实、风险和问题，因此先记录：

```text
STEP_COMPLETED
```

再记录：

```text
INFORMATION：需要用户补充
status = waiting_for_user
```

如果直接进入等待而不完成步骤，执行轨迹会错误地显示需求分析一直没有完成。

### 13.10 异常链 `raise ... from exc`

节点捕获底层异常后：

```python
raise RequirementAnalysisError(...) from exc
```

上层看到统一的节点异常，同时 Python 保留原始原因，例如：

- `TimeoutError`
- `JSONDecodeError`
- `RequirementAnalysisValidationError`

这叫异常链，方便定位根因。

### 13.11 面试问题与参考答案

#### 问：为什么让 LLM 输出 JSON 后还要校验？

答：

> Prompt 只是软约束，模型仍可能返回 Markdown、缺字段或错误类型。RequirementAnalysisResult 会进行 JSON 解析、固定字段、数组类型、非空字符串和风险依据校验，只有通过后才写入 AgentState，避免错误数据污染后续节点。

#### 问：为什么不直接使用字典？

答：

> 字典缺少明确契约，字段拼写和类型错误容易被忽略。结构化模型明确了输入输出，使节点边界更清晰，也便于测试、序列化和后续替换成 Pydantic 等校验方案。

#### 问：模型返回错误 JSON 怎么办？

答：

> 节点不会继续执行。解析器抛出校验异常，RequirementAnalyzer 将 State 标记为 failed，记录 TASK_FAILED 事件，再向上抛出统一的 RequirementAnalysisError。后续可以在编排器中增加有限重试，但本阶段先保证失败可见且不会污染状态。

#### 问：为什么有待确认项时要暂停？

答：

> 如果缺少关键业务规则，继续生成测试点可能会把推测当成预期结果。节点保留已完成的分析结果，并将状态切换为 waiting_for_user，强制后续步骤等待补充信息。这体现了 Agent 根据当前状态决定是否继续。

#### 问：这一步让项目成为完整 Agent 了吗？

答：

> 还没有，但已经从只有状态模型进展到拥有第一个执行节点。当前节点能调用 LLM、校验结果、更新 State 并根据待确认项改变状态；还需要知识检索节点、Generator、Reviewer 和编排器组成完整闭环。

### 13.12 当前限制

- 没有对格式错误进行自动重试
- 没有使用真实 DeepSeek 验证 Prompt 稳定性
- 没有接入页面
- 待确认项还没有 UI 交互
- 没有基于分析结果自动决定是否调用 RAG

### 13.13 动手练习

- [ ] 给分析结果增加一个经过讨论确认的新字段，并同步 Prompt、State、解析器和测试
- [ ] 构造缺少 `summary` 的响应，观察错误
- [ ] 构造包含未知字段的响应，观察严格校验
- [ ] 解释为什么 `open_questions=[]` 时任务保持 running
- [ ] 为模型返回 JSON 数组而不是对象增加测试
- [ ] 画出成功、等待用户和失败三条事件流

### 13.14 掌握检查

- [ ] 能解释 RequirementAnalyzer 的完整调用链
- [ ] 能说明 Prompt 约束与代码校验的区别
- [ ] 能解释为什么风险必须包含 basis
- [ ] 能解释异常链
- [ ] 能说明为什么先完成步骤再等待用户
- [ ] 能独立增加一个解析校验测试

---

## 十四、产品范围重构：从 Workflow V1 到 Agent V2

### 14.1 为什么不能继续沿用旧 PRD

旧 PRD 将测试点生成、pytest 用例生成和日志分析都列为 MVP，但实际只有测试分析功能可用。继续沿用会导致文档、代码和简历表述不一致。

同时旧 PRD 使用固定 Workflow 架构，没有描述：

- AgentState
- AgentEvent
- Node 与 Tool
- 待确认项暂停
- Reviewer 和有限修正
- 离线评测

因此需要保留 V1 作为历史，并用 V2 重新定义当前产品。

### 14.2 为什么归档而不是删除

归档可以保留项目演进证据：

```text
V1：功能范围较宽，但完成度不一致
  → 复盘问题
V2：聚焦测试分析闭环，增加Agent深度
```

面试时可以将它描述为一次真实的范围管理和架构演进，而不是假装项目从一开始就设计完美。

### 14.3 PRD 与技术文档的区别

PRD 主要回答：

- 为谁解决什么问题
- 当前做什么、不做什么
- 用户如何使用
- 功能如何验收

技术与开发文档回答：

- 代码如何组织
- 为什么选择某种架构
- 当前实现到哪里
- 如何测试和继续开发

因此当前分类为：

```text
product/PRD_AGENT_V2.md  产品范围和验收
CURRENT_STATUS.md        当前接力点
DEVELOPMENT_LOG.md       开发历史
LEARNING_NOTES.md        学习与面试复盘
archive/                 历史版本
```

### 14.4 面试问题与参考答案

#### 问：为什么项目中途重写 PRD？

答：

> V1 同时规划测试点、自动化用例和日志分析，范围过大且完成度不一致。开发过程中我决定聚焦最有价值的测试分析链路，把产品重新定义为受控 Agent，并为需求分析、知识检索、生成、评审和修正建立清晰验收标准。旧 PRD 被归档，方便保留决策过程。

#### 问：缩小范围是不是项目能力变少了？

答：

> 表面功能数量减少，但核心功能深度提高。相比三个不完整页面，V2 更关注结构化需求分析、历史资产复用、质量评审、自动修正和效果评测，更容易形成可演示、可验证、可解释的完整闭环。

#### 问：如何避免 PRD 再次和代码脱节？

答：

> 功能需求表明确标记现有 Workflow、Agent 内部已实现和规划中状态；每个开发阶段同步更新 CURRENT_STATUS、DEVELOPMENT_LOG 和 LEARNING_NOTES。AGENTS.md 也要求开始开发前先读取当前 V2 PRD。

### 14.5 掌握检查

- [ ] 能解释为什么 V1 不再适用
- [ ] 能说明为什么保留历史归档
- [ ] 能区分 PRD、当前状态和开发日志
- [ ] 能用范围管理角度解释项目演进

---

## 十五、阶段 2.4：KnowledgeRetriever 历史知识检索节点

### 15.1 这个节点做什么

`KnowledgeRetriever` 不负责生成测试点。它只负责读取已经完成的需求分析结果，整理成适合语义检索的查询，调用 `RAGService`，再把检索结果和执行状态写回 `TestAnalysisState`。

```text
RequirementAnalyzer 的结构化结果
  → KnowledgeRetriever
  → RAGService（节点使用的能力）
  → Milvus / Embedding
  → rag_context、score、count、status
  → TestAnalysisState
```

因此，`KnowledgeRetriever` 是 Agent 节点，`RAGService` 是节点调用的工具能力。节点包含业务职责和状态更新，Service 隔离具体外部系统。

### 15.2 为什么不用原始 PRD 直接检索

原始 PRD 可能很长，也可能包含大量描述性文字。当前节点把需求摘要、模块、事实、业务规则和有依据的推导风险组合成查询，让检索重点更接近测试语义。待确认问题没有加入查询，因为它们还不是已确认事实。

这并不保证召回质量一定提升。真正的效果仍需要离线数据集对比验证，当前实现首先保证查询构造过程明确、可测试。

### 15.3 三种检索结果

- `matched`：服务正常，且存在达到阈值的历史资产
- `no_match`：服务正常，但没有达到阈值的资产
- `failed`：Milvus、Embedding 或搜索过程发生异常

写入 Agent State 时，服务失败使用 `degraded`，表示任务能力降级但没有终止。这样页面或编排器以后可以明确告诉用户：“本次没有使用历史知识，但仍可基于当前需求继续。”

### 15.4 为什么 RAG 失败不让整个任务失败

需求分析是后续节点的基础数据。如果它输出的 JSON 不合法，继续执行会污染所有后续结果，所以任务进入 `failed`。

RAG 是增强能力。即使知识库暂时不可用，当前 PRD、本地测试知识和 LLM 仍然可以生成结果。因此更合理的策略是：

```text
核心前置数据错误 → 失败并停止
可选增强能力错误 → 记录降级并继续
```

这叫“优雅降级”。关键不是吞掉异常，而是把错误原因保存到 State 和 Event，使降级可观察。

### 15.5 为什么增加严格错误模式

旧的 `MilvusRAGManager` 遇到故障和无命中时都会返回空结果，旧页面可以继续运行，但 Agent 无法判断究竟发生了什么。

现在旧调用默认仍保留原行为，避免一次重构破坏现有页面；`RAGService` 则使用 `raise_on_error=True` 获取真实异常，再转换为结构化 `failed` 结果。这是一种渐进式重构和向后兼容策略。

### 15.6 面试问题与参考答案

#### 问：KnowledgeRetriever 是 Tool 还是 Agent 节点？

答：

> 它是 Agent 节点，因为它有明确业务职责，会检查前置状态、组织输入、调用外部能力、更新 AgentState 并记录事件。RAGService 更接近 Tool 或能力边界，它封装 Milvus 和 Embedding 的具体调用。

#### 问：如何区分知识库没有结果和知识库故障？

答：

> RAGService 使用明确的结果状态。检索正常但没有达到阈值的资产是 no_match；连接、向量化或搜索异常是 failed。KnowledgeRetriever 将服务失败记录为 degraded，并保存错误原因，使后续编排和页面能够准确展示，而不是把故障伪装成零命中。

#### 问：为什么服务失败后仍允许继续？

答：

> RAG 是增强能力而不是生成测试点的必要前置。失败后仍能基于当前需求生成，只是缺少历史经验。系统记录降级状态和事件，兼顾可用性与可观测性；结构化需求分析失败则会停止，因为错误基础数据会污染后续结果。

#### 问：这一步体现了 Agent 的什么特点？

答：

> 节点读取共享 State、调用 RAG 能力、根据工具结果更新 State，并为后续节点提供决策依据。目前是否继续仍由受控的 Python 规则决定，而不是让 LLM 任意调度，所以项目正在向可控 Agent 演进，但还缺少完整 Orchestrator。

### 15.7 动手练习

- [ ] 调整 `top_k`，说明它对召回数量和 Prompt 长度的影响
- [ ] 为负相似度或异常返回结构增加防御性测试
- [ ] 打印一份 `_build_query()` 结果，逐段解释为什么加入或排除
- [ ] 画出 matched、no_match、degraded 三条事件流
- [ ] 思考哪些节点失败必须终止，哪些适合降级

### 15.8 掌握检查

- [ ] 能解释 Node 与 RAGService 的区别
- [ ] 能说清三种检索结果
- [ ] 能解释优雅降级不是吞异常
- [ ] 能解释严格模式如何兼容旧页面
- [ ] 能从代码中指出检索结果写入 State 的位置

---

## 十六、阶段 2.5：TestPointGenerator 结构化测试点生成节点

### 16.1 这一阶段真正生成了什么

前两个节点分别解决“读懂当前需求”和“寻找历史经验”。`TestPointGenerator` 才第一次生成测试点：

```text
RequirementAnalyzer：原始 PRD → 结构化需求分析
KnowledgeRetriever：需求分析 → 相似历史资产
TestPointGenerator：需求分析 + 历史资产 → 结构化测试点
```

这里生成的是测试点，不是 pytest 自动化代码，也不是页面最终 Markdown 报告。测试点描述测试人员需要验证的场景、操作和预期。

### 16.2 为什么不用 Markdown 作为 Agent 内部数据

Markdown 适合人阅读，但程序很难稳定判断：

- 一共有多少条测试点
- 哪些测试点覆盖某条需求事实
- 是否缺少预期结果
- 是否存在重复项
- 哪些内容来自历史资产

结构化模型将每条测试点固定为分类、优先级、场景、前置条件、步骤、预期结果和来源。后续 Reviewer 可以直接读取字段，不需要重新解析表格和自然语言标题。

### 16.3 LLM 与 Python 的职责

LLM负责根据上下文提出候选测试点：

```text
需求分析 + RAG上下文 + 测试经验
  → LLM
  → 候选JSON
```

Python负责执行确定性规则：

```text
JSON能否解析
字段是否完整
分类和优先级是否合法
步骤、预期和来源是否非空
是否包含未知字段
```

校验通过后才写入 `state.test_points`。这和 RequirementAnalyzer 的模式一致：模型负责语义推理，代码负责数据契约。

### 16.4 每个字段的意义

- `title`：方便人快速识别测试点
- `category`：functional、boundary、exception、non_functional
- `priority`：P0、P1、P2
- `scenario`：具体要验证什么
- `preconditions`：执行前必须满足什么
- `steps`：如何操作
- `expected_results`：应该观察到什么
- `sources`：信息来源类型
- `source_refs`：具体引用的事实、风险或历史思路

`sources` 和 `source_refs` 共同提供可追踪性。例如 `historical_asset` 只说明来源类别，具体采用了哪条历史经验要写在 `source_refs` 中。

### 16.5 为什么 RAG 降级还能生成

上一阶段已经确定：RAG 是增强能力。因此：

```text
matched → 结合历史资产生成
no_match → 只根据当前需求和测试经验生成
degraded → 记录知识服务故障后继续生成
not_started → 拒绝生成
```

`not_started` 被拒绝不是因为没有 RAG 内容，而是因为受控 Agent 必须保证步骤实际执行过。否则无法区分“知识库没有结果”和“开发者忘记调用检索节点”。

### 16.6 为什么生成失败不能降级为空列表

结构化测试点是本阶段的核心产出。如果 LLM 超时或返回空列表，后续 Reviewer 没有内容可评审，Finalizer 也没有内容可展示。继续执行只会制造“任务成功”的假象，所以任务必须进入 `failed`。

判断方法：

```text
辅助信息缺失但核心结果仍可产生 → 降级
核心结果本身无法产生 → 失败
```

### 16.7 当前还不代表最终结果可信

Python校验能证明数据结构合法，但不能证明测试内容一定正确。例如步骤和预期都是非空字符串，内容仍可能遗漏业务规则或引用错误来源。

因此下一阶段需要 Reviewer 检查：

- 需求事实是否被覆盖
- 是否存在重复测试点
- 推导内容是否被误写成需求事实
- 历史资产是否污染当前业务
- 测试点是否真的可执行

### 16.8 面试问题与参考答案

#### 问：为什么要设计结构化测试点？

答：

> Markdown 适合展示但不适合程序评审。结构化模型为分类、优先级、步骤、预期和来源建立固定契约，使 Reviewer 能检查覆盖度、重复项和可执行性，也便于后续页面表格展示与导出。

#### 问：Prompt 已经规定 JSON，为什么仍要 Python 校验？

答：

> Prompt 是软约束，模型仍可能返回未知分类、空步骤或额外字段。Python解析器执行硬约束，只有合法结构才能进入 State，防止错误数据污染后续 Reviewer 和最终报告。

#### 问：结构校验通过是否代表测试点质量合格？

答：

> 不代表。结构校验只能确认字段与类型合法，不能证明需求覆盖完整或业务预期正确。内容质量需要下一阶段 Reviewer 对照需求事实、风险和来源进一步评审，并最终保留人工审核。

#### 问：为什么记录测试点来源？

答：

> 来源追踪能区分需求明确规定的验证项和历史经验启发的回归项，避免把模型推导或旧业务规则冒充当前需求事实，也为 Reviewer 检查历史资产污染提供依据。

### 16.9 动手练习

- [ ] 增加一条 boundary 测试点并解释为什么不是 functional
- [ ] 将 priority 改成 P3，观察解析器如何拒绝
- [ ] 删除 expected_results，观察错误链
- [ ] 为代码围栏包裹的 JSON 增加兼容测试
- [ ] 思考 `source_refs` 如何与需求事实建立稳定 ID，而不是只保存文本

### 16.10 掌握检查

- [ ] 能讲清三个 Agent 节点的输入和输出
- [ ] 能区分测试点、测试用例代码和最终报告
- [ ] 能解释结构合法与内容正确的区别
- [ ] 能解释为什么 no_match 可以生成而 not_started 不可以
- [ ] 能指出 LLM 与 Python 各自负责什么

---

## 十七、阶段 2.6：TestPointReviewer 测试点质量评审节点

### 17.1 Reviewer 在做什么

Generator 回答“可以设计哪些测试点”，Reviewer 回答“这些测试点是否足够好”。

```text
结构化需求分析
        +
结构化测试点
        ↓
TestPointReviewer
        ↓
评分 + 覆盖映射 + 问题清单 + 修正建议
```

Reviewer 不生成新测试点，也不直接修改已有测试点。职责分离能让执行轨迹明确展示“原始结果有什么问题”和“下一轮具体改了什么”。

### 17.2 四个评审维度

- `requirement_coverage`：需求事实和业务规则是否被覆盖
- `boundary_exception`：边界、异常、状态流转和风险是否充分
- `executability`：前置条件、步骤和预期是否可执行、可观察
- `traceability`：来源和引用是否支持测试点，历史资产是否污染当前业务

每项以及总分都是 0 到 100 的整数。分数是质量信号，不是唯一的流程条件。

### 17.3 为什么不能只看总分

假设 Reviewer 返回 90 分，但仍有一条核心需求完全没有测试点。如果代码只判断：

```python
overall_score >= 80
```

任务会错误地通过。

当前规则要求三个条件同时满足：

```text
总分达到阈值
并且所有需求事实完全覆盖
并且不存在幻觉问题
```

因此高分不能掩盖核心缺陷。

### 17.4 为什么不让 LLM 返回 passed

是否进入 Finalizer 或 Reviser 属于流程控制。LLM适合做语义评审，但不应该自行决定 Agent 下一步。

当前 Prompt 明确禁止返回：

```text
passed
next_action
```

Python读取评分和问题证据，再根据固定规则计算 `state.review_passed`。这体现了受控 Agent 的原则：

> LLM提供判断材料，代码掌握最终流程边界。

### 17.5 需求覆盖的双重校验

LLM为每条需求事实返回：

```json
{
  "requirement_fact": "提交订单时扣减库存",
  "status": "covered",
  "covered_by": ["库存充足时提交订单"],
  "gap": ""
}
```

结构解析器检查字段和状态值，Reviewer 节点还会比较：

```text
State 中的全部 requirement_facts
        是否等于
Review 中的全部 requirement_fact
```

如果模型漏评、多评或重复评审某条事实，任务会失败，而不是使用一份不完整评审继续执行。

### 17.6 missing、partial 和 failed 的区别

- `covered`：当前测试点已完整覆盖事实
- `partial`：有相关测试点，但覆盖不完整
- `missing`：没有对应测试点
- 任务 `failed`：Reviewer输出本身不合法，例如漏评事实、分数越界或JSON错误

`partial` 和 `missing` 是成功完成评审后发现的质量问题，任务仍为 running，但 `review_passed=False`。`failed` 表示连可信的评审结果都没有得到。

### 17.7 幻觉检查是什么

幻觉问题指测试点包含没有需求、推导风险或合法历史思路支持的业务断言。例如需求只说“支付失败后提示用户”，测试点却把预期写成“支付失败三次永久冻结账号”。

Reviewer需要记录：

- 哪条测试点有问题
- 问题是什么
- 哪个具体断言缺少依据

只要存在幻觉问题，即使总分很高也不能达标。

### 17.8 当前能力边界

Python可以保证：

- 分数范围合法
- 字段结构完整
- 每条需求事实都被评审
- 达标规则稳定执行

Python暂时不能保证：

- LLM给出的分数客观准确
- 重复测试点一定识别完整
- 幻觉判断一定正确

这些内容需要真实模型测试、人工标注数据集和离线评测来验证，不能因为单元测试通过就声称质量已经提升。

### 17.9 面试问题与参考答案

#### 问：为什么 Generator 和 Reviewer 使用不同节点？

答：

> 生成和评审目标不同。Generator偏向扩展候选场景，Reviewer需要严格对照事实查找遗漏和风险。拆分后可以使用不同Prompt、独立测试和清晰事件，也为后续只针对评审问题进行定向修正提供输入。

#### 问：Reviewer 是不是自己决定下一步？

答：

> 不是。LLM返回评分、覆盖映射和问题证据，Python根据阈值、完整覆盖和无幻觉三条规则计算 review_passed。后续 Orchestrator 再读取这个状态决定 Finalizer 或 Reviser，流程控制仍由代码掌握。

#### 问：为什么高于80分还可能不通过？

答：

> 总分是综合信号，可能掩盖单个核心缺陷。项目把所有需求事实完全覆盖和不存在幻觉问题设为硬门槛，因此部分覆盖或幻觉会否决高分结果。

#### 问：单元测试如何测试 Reviewer，而不调用真实模型？

答：

> 使用 FakeLLMService 返回固定评审JSON，分别构造高分、低分、部分覆盖、幻觉、漏评事实和非法结构，验证解析、State更新和达标规则。真实评审质量属于后续集成测试和离线评测。

### 17.10 动手练习

- [ ] 将 passing_score 调整为 90，观察同一结果的达标变化
- [ ] 构造高分但 partial 的结果，解释为什么不通过
- [ ] 删除一条 requirement_coverage，观察硬校验
- [ ] 增加一个 duplicate_groups 示例
- [ ] 设计一条历史业务污染导致的 hallucination_issue

### 17.11 掌握检查

- [ ] 能解释 Generator 和 Reviewer 的职责区别
- [ ] 能说清四个评分维度
- [ ] 能解释为什么 passed 由 Python 计算
- [ ] 能区分质量不达标与任务执行失败
- [ ] 能说明单元测试通过不代表评审效果已经可靠

---

## 十八、阶段 2.7：TestPointReviser 测试点定向修正节点

### 18.1 Reviser负责什么

Reviewer只发现问题，Reviser才修改测试点：

```text
Reviewer
  → 哪些需求未覆盖
  → 哪些测试点重复
  → 哪些预期存在幻觉
  → 应该如何修正
        ↓
TestPointReviser
        ↓
完整的修正后测试点集合
```

Reviser不是重新自由生成一次。Prompt要求它只处理Reviewer指出的问题，并尽量保留已经正确的测试点。

### 18.2 为什么输入中还需要需求分析

如果只把测试点和Reviewer意见发送给LLM，模型可能为了满足建议而编造新的业务预期。加入结构化需求事实、规则、状态流转和风险，可以让修正过程继续受当前需求边界约束。

因此输入是：

```text
结构化需求分析
+ 当前完整测试点
+ 上一轮结构化评审结果
```

### 18.3 为什么只允许未达标结果修正

当前节点要求：

```python
state.review_passed is False
```

如果已经通过仍自动修改，会产生两个问题：

- 破坏已经达标且用户可能认可的内容
- 产生没有明确目标的无意义变化

没有评审结果也不能修改，因为Reviser不知道应该修正什么。

### 18.4 当时为什么先返回完整集合

增量补丁可能描述：

```text
给第三条增加一个预期
删除与第一条重复的第五条
```

代码还需要稳定识别序号、合并字段和处理删除冲突。让LLM返回完整结构化集合后，可以直接复用 `TestPointGenerationResult`：

```text
LLM完整JSON
  → 现有测试点解析器
  → 字段和枚举校验
  → 整体替换State中的测试点
```

代价是Prompt更长，但阶段2.7先用这种方式降低了第一版Reviser的实现复杂度。
阶段2.11.4的真实回归证明：测试点达到12个时，即使8192 token也可能截断完整集合。
项目随后改为结构化增删改操作，并由Python原子应用。这个演进体现了“先建立正确闭环，
再根据真实瓶颈优化协议”，而不是一开始就过度设计。

### 18.5 为什么修正后旧评分必须失效

Reviewer评的是修改前版本。测试点变化以后，原来的80分或90分已经不能代表新结果。

修正成功后：

```python
state.review_result       # 保留上一轮证据
state.review_passed = None
state.revision_count += 1
```

`None`不是未通过，而是“当前版本尚未评审”。后续Orchestrator看到这个状态时，应重新调用Reviewer。

### 18.6 为什么拒绝完全未变化的结果

如果Reviewer指出了问题，但Reviser返回与原来完全相同的测试点，说明修正没有实际发生。

如果代码仍把它当作成功，未来会形成：

```text
Reviewer不通过
→ Reviser不修改
→ Reviewer仍不通过
→ Reviser仍不修改
```

这会浪费模型调用并形成空转循环。因此当前节点把完全未变化视为失败；后续Orchestrator还会增加最大循环次数作为第二层保护。下一阶段先补齐人工反馈，使修正不仅能读取LLM Reviewer意见，也能读取测试工程师的明确建议。

### 18.7 修正失败为什么会终止任务

修正过程中如果LLM超时或返回非法结构，不能把一份不可信的新结果写入State。代码会保留原测试点并将任务标记为 `failed`。

这比静默继续更安全，因为系统明确知道修正动作失败，而不是误以为已经改进。

### 18.8 面试问题与参考答案

#### 问：Reviser和Generator有什么区别？

答：

> Generator根据需求分析和历史知识首次生成候选测试点；Reviser以当前测试点和Reviewer结构化问题为基础，只做定向修改。两者复用同一输出模型，但输入目标和Prompt约束不同。

#### 问：为什么修正后不直接使用上一轮评分？

答：

> 评分对应特定版本。测试点变化后旧评分已经失效，所以保留review_result作为修改依据，同时将review_passed重置为None，强制新版本重新评审。

#### 问：如何避免Reviser无限空转？

答：

> 当前节点先拒绝完全未变化的修正结果，防止无效循环；后续Orchestrator还会设置最大修正次数。两者分别限制“单次必须有变化”和“总体循环必须有上限”。在此之前先实现人工反馈模型，让人工意见成为另一类可追踪的修正依据。

#### 问：为什么不让Reviser直接操作State中的某个字段？

答：

> LLM只返回候选JSON，不直接操作State。Python解析完整集合、校验数据契约后才原子替换test_points，避免模型绕过状态和校验规则。

### 18.9 动手练习

- [ ] 构造一个删除重复项的修正结果
- [ ] 构造一个修复幻觉预期的修正结果
- [ ] 让Fake LLM返回原测试点，观察无变化保护
- [ ] 解释`review_passed=False`与`None`的区别
- [ ] 思考保存每轮测试点快照时如何控制State大小

### 18.10 掌握检查

- [ ] 能区分Generator、Reviewer和Reviser
- [ ] 能解释为什么只允许未达标结果修正
- [ ] 能解释为什么旧评分必须失效
- [ ] 能说明完整集合与增量补丁的取舍
- [ ] 能解释无变化保护和最大次数限制的区别

### 18.11 后续阶段顺序

```text
阶段2.8：HumanFeedback
  人工意见结构化、业务规则确认、Reviser读取反馈

阶段2.9：Orchestrator
  代码选择下一节点、限制Reviewer/Reviser循环次数

阶段2.10：Finalizer
  将通过评审或人工确认的结构化测试点整理为统一最终结果

阶段2.11：Streamlit接入
  展示结构化结果、输入人工意见、最终确认和保存

阶段2.12：离线评测与演示
  建立评测集并整理可验证的项目指标
```

人工Reviewer和LLM Reviewer并不是替代关系。LLM先做快速自动质检；测试工程师负责补充项目经验、纠正真实业务规则、调整优先级并最终确认是否可用。

---

## 十九、阶段 2.8：HumanFeedback 结构化人工反馈

### 19.1 为什么需要人工反馈模型

一段自由文本虽然能直接拼进Prompt，但系统无法确定用户想增加、删除、修改还是调整优先级，也无法追踪这条意见是否确认和应用。

结构化反馈保存：

```text
动作 + 类型 + 目标 + 内容 + 原因 + 状态
```

这让人工意见和LLM Reviewer意见一样，成为AgentState中的正式输入。

### 19.2 四种反馈动作

- `add`：增加测试点或场景
- `remove`：删除不适用内容
- `modify`：修改步骤、预期或描述
- `update_priority`：调整P0/P1/P2优先级

`target`说明修改对象，`content`说明期望变化，`reason`保留人工判断依据。

### 19.3 测试建议和业务规则的区别

测试建议用于扩展验证思路，例如：

```text
增加弱网状态下支付结果未知的场景
```

业务规则会改变系统应有行为，例如：

```text
库存不足时允许创建缺货订单
```

前者可以直接交给Reviser，后者必须先明确确认。否则模型可能把测试人员的假设当成正式产品规则。

### 19.4 三种反馈状态

```text
pending_confirmation
  新业务规则尚未确认

ready
  已确认，可以进入Reviser

applied
  Reviser成功生成并校验了修改后结果
```

只有 `ready` 反馈会进入修正Prompt。修正失败时不会提前标记 `applied`。

### 19.5 为什么LLM Reviewer通过后仍允许人工修改

LLM不了解所有项目经验和真实优先级。自动评审通过只说明满足当前代码门槛，不代表测试工程师必须接受。

当前Reviser条件变为：

```text
review_passed=False
或者
存在ready人工反馈
```

所以人工可以要求修改已经自动通过的测试点，体现最终控制权仍在人。

### 19.6 业务规则确认时发生什么

提交业务规则反馈后：

```text
保存pending_confirmation反馈
→ state.wait_for_user()
→ 用户确认
→ 反馈变为ready
→ 内容写入state.business_rules
→ state.resume()
```

这样后续Reviser看到的不只是用户意见，还能从结构化需求上下文中读取已确认规则。

### 19.7 面试问题与参考答案

#### 问：为什么不把用户意见直接拼到Prompt？

答：

> 自由文本缺少动作、目标和处理状态，难以校验、审计和确认业务规则。我将反馈建模为add、remove、modify、update_priority，并区分测试建议与业务规则；只有ready反馈进入Reviser，成功后再标记applied。

#### 问：人工意见和Reviewer意见冲突怎么办？

答：

> 当前需求事实和明确确认的业务规则优先于模型Reviewer。普通人工测试建议可以补充测试思路，但不能覆盖已确认需求。后续页面还需要展示冲突和修改差异，由用户最终确认。

#### 问：为什么业务规则需要额外确认？

答：

> 业务规则决定预期结果，如果把一句未确认的建议直接写入需求状态，会造成测试用例基于错误预期。确认步骤把“测试想法”和“正式规则”分开，并留下等待、恢复和确认事件。

#### 问：自动评审通过后为什么还能修改？

答：

> LLM评分只是辅助质量门禁，不替代测试工程师。只要有已确认人工反馈，Reviser就允许处理已通过结果；修改后旧评分失效，仍需重新Reviewer。

### 19.8 当前限制

- 内部模型已完成，但页面还不能提交反馈
- 没有记录操作者身份和提交时间
- 暂未支持一次批量反馈的事务处理
- 尚未实现冲突检测和修改前后可视化Diff

### 19.9 动手练习

- [ ] 创建一条update_priority反馈
- [ ] 创建一条business_rule并观察waiting_for_user
- [ ] 确认业务规则后检查business_rules
- [ ] 模拟Reviser失败，确认反馈仍为ready
- [ ] 解释为什么applied不能在调用LLM前设置

### 19.10 掌握检查

- [ ] 能说清四种动作和两类反馈
- [ ] 能解释三种反馈状态
- [ ] 能解释为什么业务规则必须确认
- [ ] 能说明人工意见如何驱动Reviser
- [ ] 能解释为什么人工控制权高于自动评分

---

## 二十、阶段 2.9：AgentOrchestrator 受控编排器

### 20.1 Orchestrator是什么

Orchestrator是Agent的流程控制器。各节点负责具体工作，Orchestrator负责根据State选择下一步：

```text
State
  → Python决策规则
  → 唯一合法节点
  → 节点更新State
  → 再次决策
```

它不是另一个负责聊天的LLM。本项目初期使用Python规则，以获得可预测、可测试和可审计的执行过程。

### 20.2 Node、Tool和Orchestrator的关系

```text
Orchestrator
  决定调用哪个节点

Node
  执行明确业务职责并更新State

Service/Tool
  提供LLM、RAG等外部能力
```

例如Orchestrator选择KnowledgeRetriever节点，该节点再调用RAGService完成检索。

### 20.3 为什么决策顺序很重要

如果先判断 `review_passed=True` 就准备最终化，再检查人工反馈，那么测试工程师对已通过结果提出的修改永远不会执行。

当前规则先检查ready人工反馈，再检查评审通过：

```text
存在ready人工反馈
→ Reviser

否则review_passed=True
→ 准备最终化
```

这体现人工控制权高于自动评分。

### 20.4 run_next与run_until_blocked

`run_next()`只执行一次决策和一个节点，适合：

- 页面展示单步进度
- 调试某个状态分支
- 避免一次请求长时间阻塞

`run_until_blocked()`持续运行，适合：

- 后台任务
- 单元测试完整链路
- 自动执行到需要人工介入的位置

停止点包括等待用户、评审通过、达到修正上限和任务终态。

### 20.5 为什么需要两种次数限制

`max_revision_count`限制有效但未达标的自动修正次数。

`max_steps`防止节点没有正确更新State。例如Reviewer被调用后仍让 `review_passed=None`，Orchestrator会反复选择Reviewer。总步骤保护会终止这种程序错误。

```text
业务循环保护：max_revision_count
系统空转保护：max_steps
```

### 20.6 达到上限为什么不是failed

达到修正上限说明系统已经按规则工作，只是自动方式没有把质量提高到门槛。当前结果仍可供人工审核，所以返回：

```text
revision_limit_reached
```

节点异常、非法JSON或总步骤空转才属于任务执行失败。

### 20.7 为什么保存每轮快照

只保留最终结果无法回答：

- 第一轮评分是多少
- Reviewer指出了什么
- Reviser具体改了什么
- 哪条人工反馈被应用
- 评分是否真的改善

`review_history`和`revision_history`让这些信息可复盘，也为未来页面Diff和离线评测提供数据。

### 20.8 面试问题与参考答案

#### 问：你的Orchestrator内部也是LLM吗？

答：

> 不是。当前Orchestrator使用Python规则读取AgentState并选择唯一合法节点。LLM负责需求分析、测试点生成、评审和修正等语义任务，但不能决定next_action。这样能限制循环、稳定复现并清晰测试每个分支。

#### 问：这和固定Workflow有什么区别？

答：

> 固定Workflow通常无条件按预设顺序执行；当前编排会根据State动态分支，例如需求不足时暂停、RAG降级后继续、人工反馈覆盖自动通过、评审不达标时循环修正、达到上限时停止。路径不是单一线性流程，但合法动作仍受代码控制。

#### 问：为什么不让LLM自由选择Tool？

答：

> 测试分析涉及业务事实、人工确认和有限循环。完全自由选择会增加不可预测调用、无限循环和审计困难。当前先使用白名单节点和Python硬规则，后续即使加入LLM软判断，代码仍应保留合法动作和次数边界。

#### 问：如何证明不会无限循环？

答：

> Reviser拒绝完全未变化结果，Orchestrator限制最大修正次数，同时run_until_blocked还有最大总步骤数。单元测试构造不更新State的假Reviewer，验证超过max_steps后任务进入failed。

### 20.9 当前限制

- 还没有页面调用Orchestrator
- 还没有Finalizer将结构化结果转成最终报告
- 历史记录没有数据库持久化
- 尚未通过真实模型验证完整链路耗时和稳定性

下一阶段先实现Finalizer，再接入页面。这样页面直接依赖稳定的最终结果模型，而不需要先解释零散State字段并在Finalizer完成后重复调整。

### 20.10 动手练习

- [ ] 为每种OrchestratorAction画出对应State条件
- [ ] 将max_revision_count设为0并观察决策
- [ ] 构造ready人工反馈覆盖review_passed=True
- [ ] 构造节点不更新State并观察max_steps保护
- [ ] 比较run_next和run_until_blocked适合的页面调用方式

### 20.11 掌握检查

- [ ] 能解释Orchestrator不是LLM
- [ ] 能说清Node、Tool和Orchestrator关系
- [ ] 能解释决策顺序的重要性
- [ ] 能区分修正次数上限与总步骤上限
- [ ] 能解释为什么达到修正上限不等于任务失败

---

## 二十一、阶段 2.10：Finalizer最终结果整理节点

### 21.1 Finalizer负责什么

Finalizer是Agent内部的交付整理节点。它接收已经通过Reviewer的结构化测试点，生成两份同源结果：

```text
final_result
  给程序和页面使用的结构化字典

report
  给用户阅读和下载的Markdown文本
```

它会统计分类、优先级、来源和需求覆盖，汇总评分、修正次数、推导风险与降级提示，但不会生成新的测试点。

### 21.2 为什么Finalizer不使用LLM

Reviewer评审的是当前测试点版本。如果评审通过后再让LLM润色或改写测试点，实际交付内容就与被评审内容不同。

```text
已评审版本
  → LLM再次改写
  → 新版本没有经过Reviewer
```

因此Finalizer使用Python进行确定性统计和Markdown格式化，保证相同State得到相同语义结果，也更容易测试。

### 21.3 final_result与report的区别

`final_result`保留字段和类型，页面可以直接显示测试点表格、评分卡片和数量统计。`report`适合阅读和下载，但不应该再被程序反向解析。

这延续了项目的结构化原则：

```text
结构化数据是事实来源
Markdown是展示结果
```

### 21.4 为什么达到修正上限不能Finalizer

达到上限只表示系统停止自动修改，不表示质量已经合格。如果`review_passed=False`仍然生成完成报告，会把“停止尝试”误写成“任务成功”。

当前规则是：

```text
review_passed=True
→ Finalizer

review_passed=False且达到上限
→ revision_limit_reached
→ 等待人工处理
```

### 21.5 Finalizer如何更新State

执行成功后依次发生：

```text
start_step(finalize)
→ 写入final_result
→ complete_step(finalize)
→ complete(report)
→ status=completed
```

Orchestrator再次读取State时发现它已经是终态，因此返回`terminal`。

### 21.6 面试问题与参考答案

#### 问：Finalizer也是一个LLM节点吗？

答：

> 不是。Finalizer负责对已评审数据做确定性汇总和格式化。它不调用LLM，也不改写测试点，避免评审通过后产生未重新评审的新内容。

#### 问：为什么同时保存final_result和report？

答：

> final_result是页面和API可以直接消费的结构化契约，report是面向用户的Markdown交付物。页面不需要解析Markdown，下载报告也不需要重新调用模型。

#### 问：Finalizer怎样保证不会交付未通过结果？

答：

> 节点会校验review_passed必须为True、Reviewer结果必须完整、测试点必须通过结构化模型校验，而且不能存在尚未应用的人工反馈。Orchestrator也只在这些前置状态满足时选择finalize。

### 21.7 当前限制

- 尚未接入Streamlit页面
- 尚未提供达到修正上限后的人工强制确认机制
- 报告目前只支持Markdown
- 最终结果尚未持久化到数据库

### 21.8 动手练习

- [ ] 修改一个测试点分类并观察category_counts
- [ ] 将RAG状态改为degraded并检查warnings
- [ ] 将review_passed改为False并观察FinalizationError
- [ ] 对比final_result与report分别适合哪些页面组件

### 21.9 掌握检查

- [ ] 能解释Finalizer为什么不调用LLM
- [ ] 能区分final_result与report
- [ ] 能说清最终化的前置条件
- [ ] 能解释为什么修正上限不等于评审通过
- [ ] 能描述completed到terminal的关系

---

## 二十二、阶段 2.11.1：Streamlit接入Agent主路径

### 22.1 页面现在调用什么

旧页面直接调用 `TestAssistantManager` 生成一整篇Markdown。现在页面创建领域State并启动编排器：

```text
页面输入
→ TestAnalysisState
→ AgentOrchestrator
→ 各Agent节点更新State
→ 页面读取State
```

因此页面不负责分析需求、评审测试点或决定下一节点，只负责输入、触发和展示。

### 22.2 session_state与AgentState的区别

`st.session_state`是Streamlit的浏览器会话容器，用来让页面重新执行后仍能找到当前任务。`TestAnalysisState`是业务领域状态，保存Agent进度与结果。

```text
session_state
  保存当前页面会话中的TestAnalysisState对象

TestAnalysisState
  保存任务本身的事实、步骤、评审和报告
```

不能把业务字段全部散落在session_state里，否则将来迁移API或后台任务时需要重写流程。

### 22.3 为什么增加presenter

State中的字段适合业务处理，不一定适合直接显示。例如测试步骤是数组，页面表格需要换行文本；事件时间也需要格式化。

`agent_presenter`只负责：

- 状态标签转换
- 事件和决策表格行生成
- 测试点列表字段展平
- 概览指标提取

它不修改State，也不决定流程，因此可以脱离Streamlit做普通单元测试。

### 22.4 为什么没有保留旧的报告微调

旧功能把用户一句话和整篇Markdown再次交给LLM重写，可能绕过结构化测试点、Reviewer和修正次数限制。

新流程应该是：

```text
人工意见
→ HumanFeedbackHandler
→ TestPointReviser
→ Reviewer重新评审
→ Finalizer重新整理
```

所以本阶段先移除页面对旧微调入口的依赖，后续再接入已经实现的结构化人工反馈。

### 22.5 当前页面为何还不算完整

`run_until_blocked()`可能停在：

- `waiting_for_user`
- `revision_limit_reached`
- `failed`
- `completed`

本阶段能显示这些状态，但只能完整处理`completed`。下一阶段需要让用户回答待确认问题并恢复同一个State。

### 22.6 为什么移除每次任务的本地经验上传

临时上传只对当前任务生效，会与Agent自动执行的Milvus检索产生理解和功能重叠，也要求用户重复操作。主工作台现在只负责输入PRD，默认经验由后端自动加载。

后续知识上传应作为独立的知识库管理能力：

```text
上传脱敏知识
→ 文档解析与切分
→ 向量化并持久化
→ Agent在不同任务中自动检索复用
```

### 22.7 面试问题与参考答案

#### 问：为什么不把Agent状态直接拆成很多session_state变量？

答：

> session_state属于UI框架，TestAnalysisState属于领域模型。页面只保存一个完整State对象，业务节点仍读取和更新领域状态，这样单元测试、后续API化和任务持久化都不依赖Streamlit。

#### 问：页面为什么不自己根据状态调用某个节点？

答：

> 节点选择属于Orchestrator职责。如果页面也写一套if/else，会形成两份流程规则，导致单元测试通过但页面路径不同。页面只调用run_until_blocked并展示决策结果。

### 22.8 当前限制

- 尚未实现待确认问题提交和恢复
- 尚未接入人工反馈
- 同步执行时无法逐节点实时刷新
- session_state不是持久化存储，浏览器会话丢失后任务也会丢失
- 尚未实现独立的知识库上传和管理页面

### 22.9 掌握检查

- [ ] 能区分session_state与TestAnalysisState
- [ ] 能解释页面、presenter和Orchestrator的职责
- [ ] 能说明旧微调入口为什么不能直接复用
- [ ] 能列出run_until_blocked的四类页面结果

### 22.10 结构化JSON为什么仍可能失败

Prompt中写“只返回JSON”属于自然语言约束，模型仍可能返回未闭合字符串或被输出长度截断。结构化节点现在同时使用三层保护：

```text
API JSON Output
→ finish_reason与空内容检查
→ Python字段模型校验
```

如果JSON或字段校验失败，系统最多重新生成一次；网络错误不会盲目重试。`finish_reason=length`会明确提示`max_tokens`导致JSON截断。

#### 问：为什么不直接用字符串补全残缺JSON？

答：

> 自动补引号或括号只能让语法看似合法，无法证明被截断的业务含义完整。测试分析涉及需求事实，应该重新生成并再次完整校验，而不是修补不可信的半成品。

#### 如何从本地定位错误

页面展示面向用户的任务错误和AgentEvent；启动Streamlit的PowerShell窗口展示结构化校验的尝试次数、具体行列和重试原因。日志不应打印API Key或完整敏感需求。

---

## 二十三、阶段 2.11.2：待确认问题与任务恢复

### 23.0 核心代码地图

| 文件 | 本阶段职责 |
|---|---|
| `agent/requirement_analyzer.py` | 解析用户补充信息并重新生成结构化需求 |
| `agent/state.py` | 保存回答、暂缓问题、运行状态、事件和最终结果 |
| `agent/models.py` | 对最多 3 个待确认问题等结构化字段执行 Python 校验 |
| `services/prompt_service.py` | 将原始需求、历史回答和暂缓项构造成 LLM 输入 |
| `services/structured_output.py` | 清洗、校验并有限重试被截断或不合法的 JSON |
| `views/tab_test_points.py` | 双栏页面、逐节点执行、补充表单和刷新恢复入口 |
| `views/agent_presenter.py` | 将内部状态、步骤和分类转换为页面中文展示 |
| `agent/finalizer.py` | 生成表格化 Markdown 报告并保留未确认风险 |

### 23.1 为什么不能让 LLM 一次追问很多问题

LLM 很容易把所有未知细节都列成问题，但用户未必知道技术实现，也不需要在开始测试分析前回答全部细节。本阶段只允许询问会阻塞核心业务结果判断的问题，并限制每轮最多 3 个。

这个限制有两层：

```text
Prompt：告诉 LLM 合并同类问题并按重要性排序
Python：校验 open_questions 数量不能超过 3
```

Prompt 提升正常输出质量，Python 保证错误输出不能进入 State。

### 23.2 回答和“暂不确定”分别如何处理

回答会保存到 `state.user_clarifications`，下一轮需求分析把它当作用户明确确认的事实。选择“暂不确定”的问题保存到 `state.deferred_questions`：

- 不再次追问同一个问题
- 不允许模型自行假设答案
- 测试生成可以继续
- Finalizer 将它写入报告注意事项

这体现了 Agent 的一个重要原则：允许带着显式不确定性继续，但不能把未知内容伪装成事实。

### 23.3 为什么要重新执行 RequirementAnalyzer

用户回答可能改变业务规则、状态流转、风险和待确认项。只把答案追加到文本里而不更新结构化状态，会导致后续 Generator 仍然读取旧分析。因此恢复时先记录答案并把状态恢复为运行中，随后立即重新分析，再交还 Orchestrator：

```text
waiting_for_user
  → 收集回答/暂缓项
  → state.resume()
  → RequirementAnalyzer 重新构建结构化需求
  → Orchestrator 选择后续节点
```

### 23.4 页面为什么不自己决定下一个节点

Streamlit 页面只负责输入、展示和触发。它调用
`reanalyze_with_clarifications()` 后，通过受控页面循环逐次调用
`run_next()`。每次调用仍由 Orchestrator 根据 State 决定唯一合法动作，
页面不直接选择检索、生成、评审或最终化节点，避免页面和后端各维护一套
if/else。

### 23.5 左右布局的职责

- 左侧是工作台：需求输入、文件上传、启动、清空和关键问题回答
- 右侧是结果台：任务概览固定在上方，详细结果在固定高度容器中滚动

右侧不是数据库意义上的“固定保存”。当前任务同时保存在
`st.session_state` 和 `st.cache_resource` 进程内任务表中，URL 使用
`task_id` 帮助刷新后恢复。Streamlit 服务重启后仍会丢失，真正的历史记忆
需要后续接入 MySQL。

### 23.6 面试问题与参考答案

#### 问：限制 3 个问题为什么同时使用 Prompt 和 Python？

答：

> Prompt 是生成指导，不能作为可靠约束；Python 校验是系统边界，可以拒绝不合格输出并触发有限重试。两者结合既提高首次成功率，也保证非法数据不会污染 AgentState。

#### 问：用户不知道答案时为什么不直接让 LLM 推测？

答：

> 推测可以作为带依据的风险，但不能作为需求事实。系统把暂不确定项显式保存并写入报告，使后续使用者知道测试结论依赖哪些未知条件，避免幻觉。

#### 问：恢复任务时为什么还要重新分析需求？

答：

> 用户补充可能改变结构化需求的多个字段。重新运行 RequirementAnalyzer 可以让事实、规则、状态流转和风险保持一致，后续节点只消费更新后的 State。

#### 问：双栏页面是否等于前后端分离？

答：

> 不是。它只是 Streamlit 页面布局变化。业务状态、节点和编排器仍在 Python 进程中，当前阶段没有引入 FastAPI 或独立前端。

### 23.7 动手练习

- [ ] 把问题上限临时改成 2，观察模型校验测试如何变化
- [ ] 回答一个问题并检查 `user_clarifications`
- [ ] 将一个问题选为暂不确定并检查最终报告 warnings
- [ ] 说明页面、RequirementAnalyzer 和 Orchestrator 各自负责什么

### 23.8 掌握检查

- [ ] 能解释 Prompt 约束和 Python 校验的差别
- [ ] 能说明回答与暂缓项写入 State 的不同字段
- [ ] 能画出 waiting、resume、reanalyze、continue 的状态流
- [ ] 能解释为什么页面不直接调用后续业务节点

### 23.9 为什么页面看起来卡住但后端仍在运行

原页面在一次Streamlit脚本运行中调用`run_until_blocked()`。它会连续执行多个耗时LLM节点，State里的事件虽然持续增加，但Streamlit只有等函数返回后才能重新渲染，所以用户只能看到旧画面。

现在页面循环使用`run_next()`：

```text
渲染当前State
→ 执行一个节点
→ 保存State
→ st.rerun()
→ 展示刚完成节点的事件
→ 再执行下一个节点
```

这不是后台异步任务。单个节点调用LLM时页面仍需等待，但节点之间的进度已经可见。

### 23.10 为什么刷新后可以恢复但重启服务仍会丢失

当前URL保存`task_id`，服务进程通过`st.cache_resource`维护任务对象。浏览器刷新建立新会话时，可以用`task_id`重新找到State。

它属于进程内恢复，不是数据库持久化：

- 浏览器刷新：可以恢复
- 新开相同任务URL：可以恢复
- 重启Streamlit：不能恢复
- 换电脑：不能恢复

真正的生产方案需要将`state.to_dict()`保存到数据库，并实现可靠的反序列化、并发控制和任务锁。

### 23.11 页面展示值为什么不直接使用内部枚举

内部使用`functional`、`boundary`等稳定英文枚举，便于代码比较、JSON传输和数据库存储；页面通过Presenter转换为“功能”“边界”等中文标签。这样不会为了修改文案而改变领域数据协议。

Markdown报告也在Finalizer格式化阶段转换展示标签。State中仍保留原始英文枚举，因此后续接入MySQL或API时数据含义稳定。

### 23.12 MySQL历史任务不能只保存最终报告

如果只保存Markdown，历史页面可以阅读，但无法恢复Agent状态或分析每个节点。完整历史至少需要考虑：

- 任务ID、原始需求、状态和当前节点
- AgentState结构化快照
- Orchestrator决策与Agent事件
- 结构化测试点、Reviewer结果和最终报告
- 创建、更新时间与错误信息

数据库密码、服务器地址等配置只能放在本机`.env`或部署环境变量中，不能提交到GitHub。

---

## 二十四、阶段 2.11.3：结构化人工反馈页面闭环

### 24.1 核心代码地图

| 文件 | 职责 |
|---|---|
| `agent/state.py` | 重新打开已完成任务，分别记录自动与人工修正次数 |
| `agent/human_feedback.py` | 校验、保存、确认或取消结构化人工反馈 |
| `agent/orchestrator.py` | 优先处理已确认反馈，并继续选择Reviser、Reviewer和Finalizer |
| `agent/test_point_reviser.py` | 将人工反馈加入Prompt，修改测试点并标记反馈已应用 |
| `views/tab_test_points.py` | 收集反馈、展示业务规则确认页并恢复逐节点执行 |
| `views/agent_presenter.py` | 将反馈内部枚举转换成中文表格 |

### 24.2 需求补充和人工反馈有什么不同

需求补充发生在测试点生成前，解决“原始需求信息不足”：

```text
RequirementAnalyzer提出问题
→ 用户回答或暂不确定
→ 重新分析需求
→ 首次生成测试点
```

人工反馈发生在测试点或报告生成后，解决“结果需要调整”：

```text
用户审阅测试点
→ 提交增删改或优先级意见
→ Reviser修改
→ Reviewer重新评审
→ Finalizer更新报告
```

两者都需要用户参与，但更新的State字段和后续节点不同。

### 24.3 为什么完成状态需要重新打开

`completed`是终态，普通节点不能继续执行。这可以防止任务完成后被意外修改。但用户主动提交反馈属于明确授权的继续操作，因此使用专门的`reopen_for_feedback()`：

- 只允许`completed`任务调用
- 保留测试点、评审历史和事件
- 清空已经过期的`final_result`与`report`
- 将状态恢复为`running`
- 记录任务因人工反馈被重新打开

不能直接把`state.status`赋值为`running`，因为那会绕过前置条件、旧报告清理和事件记录。

### 24.4 为什么业务规则必须二次确认

“增加弱网测试”是测试建议，只改变测试设计；“支付最多重试三次”是业务规则，会改变正确结果的判断标准。

业务规则的状态变化是：

```text
pending_confirmation
  → 用户确认 → ready → applied
  → 用户取消 → rejected
```

只有`ready`反馈能驱动Reviser。`rejected`会留在历史记录中，但不会写入`business_rules`。

### 24.5 为什么自动修正和人工修正要分开计数

原来的`revision_count`既用于展示，又用于限制自动循环。人工反馈接入后，如果仍只使用一个计数器，可能出现：

- 人工反馈错误占用自动修正额度
- 页面显示“自动修正3/2”
- 用户明确提交的反馈被自动上限拒绝

现在分别记录：

```text
revision_count = 全部修正总数
automatic_revision_count = Reviewer驱动的自动修正
human_revision_count = 用户反馈驱动的修正
max_revision_count = 自动修正上限
```

这体现了“系统自主动作受严格限制，用户明确授权的动作可以继续执行”。

### 24.6 完整状态流转

```text
completed
→ 用户提交测试建议
→ reopen_for_feedback()
→ feedback=ready
→ Orchestrator选择revise_test_points
→ Reviser应用反馈并将其标记为applied
→ review_passed=None
→ Reviewer重新评审
→ 通过：Finalizer生成新报告
→ 未通过：按剩余自动额度决定修正或等待人工
```

业务规则会在`reopen_for_feedback`之后先进入`waiting_for_user`，确认后才进入相同闭环。

### 24.7 面试问题与参考答案

#### 问：为什么人工反馈后还要经过Reviewer？

> Reviser根据反馈生成的是一组新的测试点。新内容可能解决了原问题，也可能引入重复、遗漏或无依据断言，因此旧评分已经失效，必须重新评审后才能生成最终报告。

#### 问：为什么不用页面直接修改State里的测试点？

> 页面直接修改会绕过结构化校验、修改历史、来源记录和Reviewer质量门禁。页面只提交HumanFeedback，由领域层校验并让Reviser生成完整的新测试点集合。

#### 问：为什么取消的业务规则还要保存在State？

> 保留`rejected`记录可以解释用户曾提出但没有确认的规则，避免重复处理，也为后续审计和数据库持久化提供完整历史。

### 24.8 动手练习

- [ ] 提交一条新增测试场景，观察反馈状态从`ready`变为`applied`
- [ ] 提交业务规则并取消，确认`business_rules`没有变化
- [ ] 在自动修正达到2次后提交人工反馈，观察它仍能进入Reviser
- [ ] 比较旧报告和人工反馈后的新报告

### 24.9 掌握检查

- [ ] 能解释需求补充与测试结果反馈的区别
- [ ] 能说明`reopen_for_feedback()`为什么不能用直接赋值替代
- [ ] 能画出业务规则确认和取消的状态流
- [ ] 能解释自动修正次数与人工修正次数为什么分开
- [ ] 能说明人工反馈后为什么必须重新经过Reviewer和Finalizer

### 24.10 为什么Reviser比普通问答更容易达到max_tokens

阶段2.11.3时，Reviser不是只返回“修改了什么”，而是返回修正后的完整测试点集合。测试点越多，
每项的前置条件、步骤、预期结果和来源引用越长，JSON响应就越大。此前只有
Generator使用8192，Reviser仍沿用默认4096，因此真实任务在自动修正阶段出现：

```text
Reviewer发现问题
→ Reviser需要重写完整测试点集合
→ 输出达到默认4096
→ finish_reason=length
→ JSON被截断
→ State进入failed
```

阶段2.11.3先将“大体量结构化输出”预算统一为8192，解决了原4096预算过小的问题。
但阶段2.11.4真实任务包含12个测试点时仍然截断，因此最终方案不是继续增加预算，
而是让Reviser只返回增删改操作。8192仍作为安全上限，但响应不再随全部测试点内容
一起膨胀。

#### 问：现在为什么可以让Reviser返回差异内容？

> 因为现在差异不是自然语言，而是严格的`add`、`replace`、`remove` JSON操作。
> Python会校验操作字段、完整TestPoint、目标唯一性和重复标题，并先在临时列表中
> 应用全部操作；只有全部成功才写入State。因此既节省token，也保留了原子性。

#### 问：把max_tokens调大是否代表一定不会失败？

> 不是。8192降低了当前规模下被截断的概率，但仍需要保留`finish_reason=length`检测和结构化模型校验。输出规模如果继续增长，应该减少冗余、拆分批次或采用结构化差异协议，而不是无限提高上限。

#### 动手练习

- [ ] 查看三个节点如何复用同一个输出预算常量
- [ ] 将Fake LLM记录的预算临时改成错误值，确认测试能够失败
- [ ] 对比“返回完整集合”和“返回增删改差异”两种Reviser协议的优缺点

---

## 二十五、阶段 2.11.4：Agent执行体验与人工反馈稳定性

### 25.1 为什么页面看起来像卡死

Streamlit从上到下执行页面代码。右侧概览先根据旧State渲染，然后页面才调用
LLM节点。如果一次请求耗时80秒，这80秒内右侧仍可能显示调用前的“初始化”，
但服务器实际正在等待模型返回。

这不是Agent无限循环，而是同步阻塞：

```text
页面渲染旧State
→ 调用一个LLM节点
→ 同步等待响应
→ 节点更新State
→ st.rerun()
→ 页面展示新State
```

### 25.2 为什么先调用decide_next

页面需要知道将要执行什么，但不能自己重写一套`if/else`流程。现在页面先调用
Orchestrator的`decide_next()`取得动作，再由同一个Orchestrator调用
`run_next()`：

```text
Orchestrator决定下一步
→ 页面把动作翻译为中文提示
→ Orchestrator执行节点
```

这样页面只负责展示，不拥有业务路由权。

### 25.3 节点耗时为什么放在Decision

Decision描述“为什么选择这个动作”，完成后再附带实际耗时，可以让执行轨迹同时回答：

- Agent选择了什么
- 为什么选择
- 这一步用了多久

使用`time.perf_counter()`而不是系统时间，是因为单调时钟不会受用户修改电脑时间
或系统校时影响，适合计算时间间隔。

### 25.4 为什么不是实时倒计时

同步请求期间Python线程正在等待外部服务，Streamlit无法通过普通`st.rerun()`
持续刷新同一个节点的秒数。当前方案提供：

- 执行前：具体节点和1–2分钟等待预期
- 执行后：真实耗时

如果需要实时秒数、取消任务或多用户并发，后续需要后台任务队列或独立后端，
不能只靠增加一个循环刷新页面。

### 25.5 表单版本键如何清空反馈

Streamlit组件状态与Widget key绑定。提交后直接修改一个已经创建的组件状态，
容易触发Streamlit限制；保留同一个key又会让旧内容重新出现。

因此提交成功后递增`form_version`：

```text
feedback_content_task_0
→ 提交成功，form_version=1
→ feedback_content_task_1
```

新key代表新表单，默认值为空。旧key仍属于旧页面运行，不会造成同一反馈再次出现。

### 25.6 面试问题与参考答案

#### 问：显示具体节点是不是页面参与了Agent决策？

> 不是。动作仍由Orchestrator的`decide_next()`计算，页面只把返回的稳定枚举转换成中文。真正执行时仍调用同一个Orchestrator，页面没有复制状态流转规则。

#### 问：为什么使用perf_counter而不是datetime.now？

> perf_counter是单调高精度计时器，适合测量持续时间；datetime适合记录发生时间，但可能受到系统时钟调整影响。

#### 问：当前优化是否解决了性能问题？

> 没有缩短模型响应本身，而是让等待可解释、结果可观测，并减少重复提交。真正降低总耗时还需要减少LLM调用、优化Prompt与输出规模，或采用后台异步执行。

### 25.7 动手练习

- [ ] 查看一次完整任务的决策耗时，找出最慢节点
- [ ] 验证人工反馈提交后文本框恢复为空
- [ ] 临时让RecordingNode等待少量时间，观察耗时测试
- [ ] 说明同步等待与后台异步任务的区别

### 25.8 掌握检查

- [ ] 能解释页面为什么会显示旧State
- [ ] 能说明页面为什么不能自行判断下一节点
- [ ] 能说明perf_counter适合测量耗时的原因
- [ ] 能解释Widget key版本化如何重置表单
- [ ] 能说明当前优化解决的是可解释性而不是模型性能

### 25.9 为什么动态轨迹会出现React #185

Streamlit会把每次Python运行生成的组件树发送到浏览器。节点执行期间如果同时出现：

- 动态DataFrame组件反复变化
- 同一个placeholder内嵌套info和spinner
- `in_progress`状态每秒触发一次`st.rerun()`

浏览器端可能在短时间内重复协调组件更新，表现为React #185。当前轨迹只是只读记录，
不需要排序和搜索，因此改用静态`st.table`；执行提示只保留一个placeholder；
检测到节点已在执行时直接返回，不再主动轮询。

### 25.10 Reviser增量操作如何保证安全

模型不再返回完整集合，而是返回：

```json
{
  "operations": [
    {
      "action": "remove",
      "target_title": "需要删除的现有标题"
    }
  ]
}
```

Python负责最终控制：

1. 校验action及其允许字段
2. add和replace中的测试点必须通过完整结构模型
3. replace和remove必须精确命中一个标题
4. 在临时副本中应用全部操作
5. 检查非空、无重复且确实发生变化
6. 全部成功后一次性替换State

这叫原子应用：要么全部修改成功，要么一条都不写入。LLM负责判断“应该改什么”，
代码负责保证“怎样改都不会破坏状态一致性”。

#### 面试追问：增量协议还有什么限制？

> 当前通过标题定位测试点，因此标题必须唯一。如果后续MySQL持久化引入稳定的
> `test_point_id`，可以改用ID定位，避免标题被修改或同名时产生歧义。

#### 动手练习

- [ ] 构造一个不存在的`target_title`，确认State保持不变
- [ ] 只replace一个测试点，确认其他测试点没有经过LLM重写
- [ ] 比较完整集合响应和增量操作响应的JSON长度

### 25.11 严格校验为什么仍需要有边界的归一化

严格结构化输出不代表对所有格式瑕疵都必须终止任务。例如：

```json
{"missing_scenarios": [""]}
```

这通常是模型用空字符串表达“没有内容”，与`[]`语义相同。系统现在只对
`missing_scenarios`和`revision_suggestions`这两个可选问题列表过滤纯空白项。
非字符串、错误对象结构、非法分数和缺失需求覆盖仍会失败。

这种做法叫有边界的归一化：

- 可以确定语义等价时转换
- 无法确定语义时拒绝
- 不用“尽量猜”的方式掩盖真实数据错误

#### 面试追问：为什么不对所有字符串列表统一过滤？

> 因为有些列表是关键证据。例如已覆盖测试点标题、测试步骤和预期结果中的空白项
> 可能意味着数据缺失，不能静默删除。归一化必须限定在允许为空、且空白项没有业务
> 含义的字段。

### 25.12 为什么不用st.table隐藏索引

`st.table`是稳定的静态组件，但会显示DataFrame索引，而且没有`hide_index`参数。
`st.dataframe`可以隐藏索引，却在本次节点连续刷新场景中触发过React #185。因此执行
轨迹使用Presenter生成的静态HTML：

- 表头只来自业务字段，不生成默认索引
- 单元格统一HTML转义，避免模型文本被当成标签执行
- 外层允许横向滚动，长内容不会撑破右侧面板

结构化测试点仍使用`st.dataframe`，因为它需要滚动查看且不会在节点执行中高频更新。

### 25.13 默认索引与业务序号有什么区别

默认索引是DataFrame或表格组件为了定位行自动生成的`0、1、2...`，不属于业务数据。
Agent事件的序号则表达事件发生顺序，应由Presenter显式生成`1、2、3...`。

因此正确做法不是保留默认索引，而是：

```text
State事件列表
→ Presenter enumerate(start=1)
→ 生成“序号”业务字段
→ 静态表格按字段展示
```

这样即使以后更换页面组件，事件顺序仍然存在于展示模型中。

### 25.14 为什么人工反馈不能混入旧Reviewer建议

一份85分、已经通过的结果提交人工反馈时，本轮目标是处理用户的新意见。如果仍把
上一轮Reviewer的全部建议放入Prompt，模型可能同时“顺手优化”其他测试点：

```text
一条人工反馈
+ 旧Reviewer建议
→ 模型扩大修改范围
→ 返回过多replace操作
→ 输出再次达到max_tokens
```

现在人工反馈和自动评审使用分离的修正轮次。人工反馈轮只读取ready反馈，并根据
反馈动作限制允许的操作类型和最大数量；修改后重新Reviewer。如果新版本未达标，
后续自动轮次再处理新的评审结果。

#### 面试追问：为什么只靠Prompt限制还不够？

> LLM指令不是强制执行代码。Prompt会告诉模型最多返回几项，但Python解析器仍必须
> 检查实际操作数量和action。模型越界时进行一次受控重试，仍不合规则整次失败，
> 原State保持不变。

---

## 二十六、阶段 2.11.5A：Streamlit信息架构调整

### 26.1 这次为什么不是“单纯改样式”

样式解决的是颜色、字号、边框等视觉问题；信息架构决定用户先看到什么、在哪里操作。
原页面把任务状态、执行提示、决策、事件和结果同时铺在右侧，人工反馈又可能在左右两处
出现。即使换一套颜色，用户仍然难以判断下一步。

本阶段先重新分配职责：

```text
左侧：需求事实和必须由用户完成的输入
右侧：Agent进度、结果、反馈和报告
折叠区：排错时才需要的完整执行证据
```

视觉规范放到2.11.5B，避免一次改动同时改变结构、行为和样式，导致问题难以定位。

### 26.2 为什么任务开始后读取`state.requirement`

文本框和上传控件是临时页面输入，`TestAnalysisState.requirement`才是任务已经接受的
需求事实。文件上传时流程为：

```text
UploadedFile
→ DocumentService.extract_text()
→ requirement字符串
→ TestAnalysisState.requirement
→ 左侧只读展示
```

这样无论输入来自文本、Markdown、PDF还是DOCX，任务开始后都只依赖同一字段。页面rerun
或未来从MySQL恢复State时，也不需要重新依赖浏览器里的上传控件。

#### 面试追问：为什么不继续显示一个disabled文本框？

> disabled控件仍像一个可以输入但被禁用的表单，而且文件上传任务可能没有对应的文本框
> 默认值。直接展示State中的只读内容，可以明确表达“这是本任务已接收的原始需求”，
> 并避免页面控件状态成为业务数据来源。

### 26.3 五阶段指示器是否改变Agent节点

没有。阶段指示器是Presenter层的显示映射：

| 页面阶段 | 对应内部步骤 |
|---|---|
| 需求分析 | initialize、analyze_requirement |
| 知识检索 | retrieve_knowledge |
| 生成测试点 | generate_test_points |
| 评审与修正 | review_test_points、collect_human_feedback、revise_test_points |
| 整理报告 | finalize |

内部仍然保留完整节点和事件。页面把多个相关节点归为用户容易理解的阶段，不会修改
Orchestrator的动作选择、State转换或执行顺序。

#### 面试追问：Presenter为什么不能决定下一个节点？

> Presenter只把State转换为显示数据。如果Presenter参与流程决策，UI改动就可能改变
> Agent行为，也难以在没有Streamlit时测试编排。下一步动作必须继续由Orchestrator根据
> State决定。

### 26.4 为什么执行详情默认折叠

Orchestrator决策和Agent事件对开发排错、项目答辩和可解释性非常重要，但普通使用者每次
主要关心的是当前阶段和结果。默认折叠不是删除信息，而是建立层级：

```text
第一层：当前状态和五阶段进度
第二层：测试点、评审、人工反馈、报告
第三层：完整决策与事件证据
```

需要排错时展开第三层，平时不会挤占主结果区域。

### 26.5 “执行失败”和“达到修正上限”有什么区别

- 执行失败：某个节点发生异常或输出无法通过结构化校验，State进入`FAILED`，页面展示错误。
- 达到修正上限：自动Reviser已经用完允许次数，Agent受控停止自动循环，现有测试点和评审
  结果仍保留，用户可以进入“人工反馈”Tab提出明确意见。

达到上限是保护机制生效，不等同于程序崩溃。页面必须给出不同文案和下一步入口。

#### 面试追问：为什么达到上限后还允许人工反馈？

> 自动修正次数限制的是模型根据Reviewer意见自行循环，防止空转和无限消耗。人工反馈是
> 测试工程师主动提供的新约束，使用独立计数，并仍要经过Reviser、Reviewer和Finalizer，
> 因此可以在自动上限后继续受控处理。

### 26.6 为什么人工反馈只放右侧

待确认问题和业务规则确认是在补齐需求，属于左侧需求工作台；人工反馈是在修改已经生成的
测试结果，属于右侧结果区。把人工反馈同时放在两侧会产生两个入口和两份组件状态，增加误
重复提交风险，也让用户分不清是在补需求还是改结果。

### 26.7 为什么本阶段不加入侧边栏

侧边栏的核心内容是新建分析、搜索历史和恢复历史任务，这些功能必须依赖阶段2.13的MySQL
数据模型和恢复语义。现在加入空壳或假历史数据会制造不可用入口。本阶段只保证主页面没有
依赖整页宽度的硬编码，未来可以在不改变Agent核心逻辑的情况下加入`st.sidebar`。

### 26.8 红线函数为什么保持不动

页面逐节点执行依赖固定顺序：

```text
渲染当前State
→ 获得唯一执行提示placeholder
→ _process_agent_step()
→ Orchestrator选择并执行一个节点
→ 持久化进程内任务
→ rerun展示新State
```

如果为了布局顺手调整`_process_agent_step()`、任务缓存或rerun顺序，就可能重新引入节点
重复执行、刷新后状态丢失或人工反馈重复提交。因此2.11.5A只改变展示位置，不改变控制流。

### 26.9 AppTest验证了什么

AppTest用预置State检查Streamlit组件树，适合验证：

- 任务创建前文本输入可启用启动按钮
- 任务创建后只读展示`state.requirement`
- 四个主Tab和默认折叠的执行详情
- 等待需求补充、业务规则确认、人工反馈和报告下载入口
- 自动修正上限与普通失败使用不同提示
- `in_progress`任务不会因rerun重复启动节点

文件上传控件目前不提供稳定的AppTest文件注入接口，因此测试辅助页面使用内存中的
UploadedFile等价对象调用原任务创建入口，验证“解析文件→创建State”；TXT和Markdown解析
同时由`DocumentService`单元测试独立覆盖。主页面再用预置的解析后State验证只读显示。
测试不调用真实DeepSeek、Milvus或Embedding服务。

### 26.10 动手练习

- [ ] 给`AgentStep.RETRIEVE_KNOWLEDGE`构造State，确认“知识检索”为当前阶段
- [ ] 给`AgentStatus.FAILED`构造State，确认当前阶段显示失败而不是已完成
- [ ] 上传TXT或Markdown后确认左侧显示解析文本，而不是文件名或空文本框
- [ ] 展开“执行详情”，对照决策序号、事件序号和State当前步骤
- [ ] 达到自动修正上限后进入“人工反馈”Tab提交一条新增测试建议
- [ ] 刷新执行中的任务，确认不会重复产生同一节点的`step_started`

### 26.11 自测答案

#### 问：这次为什么没有修改Orchestrator？

> 因为目标是调整页面的信息层级，不是改变Agent能力。当前节点顺序和分支已经由测试验证，
> 只需根据现有State生成更清晰的展示。

#### 问：外层滚动和组件滚动有什么区别？

> 外层滚动是浏览器页面整体上下移动，用户只维护一个滚动位置。组件滚动是某个固定高度
> 容器内部再滚动；左右栏和结果区同时固定高度时会出现多套滚动位置。本阶段移除栏级固定
> 高度，但长表格仍可能保留局部滚动以避免一次渲染过高。

#### 问：这次改动如何为MySQL历史任务做准备？

> 页面创建任务后只依赖State展示原始需求和结果，而不是依赖上传控件的临时值。阶段2.13
> 从MySQL恢复同样的State快照后，可以复用当前右侧结果展示和左侧只读需求对照。

### 26.12 为什么初始态和完成态截图宽度曾经不一致

原因不在Agent状态，也不在`st.columns()`本身，而是两张截图使用了不同页面入口：

```text
初始态：main.py
→ layout="wide"
→ 全局工作区CSS
→ 产品头部
→ render_test_points()

旧完成态预览：render_ui()
→ 绕过main.py
→ Streamlit默认窄容器
→ 缺少产品头部
```

这说明UI回归测试必须从相同应用入口开始。修正后的四态截图都执行完整`main.py`，只在
调用页面函数前注入不同测试State，因此宽度、CSS和头部保持一致。

#### 面试追问：为什么完成态还要动态扩大右栏？

> 页面总工作区保持不变，但不同阶段的主要任务不同。需求输入和确认阶段需要较宽左栏，
> 所以使用约42/58；结果阅读、人工反馈和报告阶段需要更宽右栏，所以使用约33/67。
> 这只是Presenter层布局映射，不会改变State或Orchestrator。

#### 面试追问：为什么测试点不用一张包含所有字段的表格？

> 步骤、预期结果、前置条件和来源都是长文本，横向表格会迫使用户滚动且压缩标题。
> 摘要列表先展示用于扫描的标题、分类、优先级和场景，再按需展开完整结构化字段。
> 数据来源仍是原来的测试点字典，没有修改模型或报告数据。

### 26.13 内部步骤与产品阶段为什么不能直接等同

State需要准确记录代码执行位置，页面需要解释用户此刻正在做什么。RequirementAnalyzer
可能在内部`initialize`步骤产出待确认项并暂停。如果页面机械翻译字段，就会出现：

```text
State.current_step = initialize
State.status = waiting_for_user
实际阻塞原因 = RequirementAnalyzer等待需求答案
```

用户界面因此应显示“等待补充信息 · 当前阶段：需求分析”，而不是“等待用户 · 初始化”。
Presenter可以组合State、反馈状态和最近决策生成文案，但不能修改这些业务数据。

#### 面试追问：这种映射会不会掩盖真实执行信息？

> 不会。主状态区使用产品阶段帮助用户操作；默认折叠的执行详情仍保留原始AgentStep、
> Orchestrator决策和事件。两个层级分别服务普通使用和技术排错。

---

## 二十七、阶段 2.11.5B：视觉规范为什么要与信息架构分开

### 27.1 两类改动的边界

信息架构决定“内容放在哪里、先看什么、如何展开”，视觉规范决定“这些内容看起来是否
属于同一套产品”。2.11.5B只修改CSS、展示文案和Presenter生成的摘要HTML，不移动：

- 左右需求与结果区域
- 四个主结果Tab
- 默认折叠的执行详情
- 测试点详情字段

这样可以把页面行为回归和视觉验收分开，出现问题时也更容易定位。

### 27.2 为什么流程阶段不应该像五个按钮

阶段指示器用于展示状态，不是让用户点击跳转。胶囊背景、明显边框和高对比填充容易制造
“可以点击”的暗示。改为文字、圆点和颜色差异后，仍能表达完成、当前和待执行三种状态，
但不会与“启动分析”“新建分析”等真实操作竞争。

### 27.3 为什么测试点摘要由Presenter生成

测试点模型继续保存完整结构化字段。Presenter只读取标题、分类、优先级和场景，生成适合
列表扫描的四列摘要；前置条件、步骤、预期结果和来源仍由原展开区域展示。这样不会为了
页面对齐修改业务模型。

模型内容可能包含`<`、`>`或HTML片段，因此Presenter在拼接HTML前必须转义字段。否则模型
文本可能破坏DOM结构，甚至产生不应执行的标签。

### 27.4 AppTest关注什么

AppTest不适合断言每个像素，但可以确认视觉调整没有改变行为：

- 未开始状态仍能看到启动入口和“重置输入”
- 已创建任务显示次要操作“新建分析”
- 等待补充仍显示正确状态标题和问题表单
- 四个主Tab、测试点展开和执行详情仍存在

像Tab颜色、圆角和间距则通过同一浏览器宽度下的截图进行人工验收。

### 27.5 面试自测

#### 问：为什么不在同一个阶段同时改布局和视觉？

> 布局影响信息位置与操作路径，视觉影响呈现层。拆开后，2.11.5A先用AppTest验证页面行为，
> 2.11.5B再用既有测试和截图验证视觉，不会把业务回归问题与CSS问题混在一起。

#### 问：CSS统一会不会影响Agent执行？

> 不会。样式只作用于页面元素；任务推进仍由State和Orchestrator决定。项目还用红线复核
> 确认关键执行函数的代码没有变化。

### 27.6 动手练习

- [ ] 分别查看完成、当前、待执行三个阶段标签，确认它们可区分但没有按钮感
- [ ] 在测试点标题中加入`<异常>`，确认页面显示文本而不是创建HTML标签
- [ ] 切换四个主Tab，确认蓝色激活态一致
- [ ] 展开两个测试点详情，确认摘要列对齐且完整字段仍可查看

---

## 二十八、阶段 2.11.5C：固定工作区、分页与页面状态

### 28.1 为什么又需要固定高度

2.11.5A移除多层固定高度，是为了解决页面、左右栏、结果卡片和表格同时滚动的问题。
但完全依赖页面外层滚动，会让长测试点和报告把整个页面不断撑高，状态和导航也会离开视野。

本阶段不是恢复所有旧滚动条，而是只给两类正文建立边界：

```text
左侧：需求正文
右侧：当前结果正文
```

标题、状态、阶段和结果导航不进入这两个滚动内容，从而始终可见。

### 28.2 为什么不用原生`st.tabs`

Streamlit 1.38的`st.tabs`能显示Tab，但页面无法通过稳定接口读取和设置当前活动项。
Streamlit每次交互都会从上到下rerun，人工反馈提交后原生Tab容易回到第一项。

因此使用带`session_state` key的单选导航表达“当前结果页”，CSS只负责把它显示成Tab。
这不是业务状态：它只决定用户正在看哪一块结果，不参与Orchestrator决策。

### 28.3 分页状态为什么需要任务ID和集合签名

只保存页码会出现两个错误：

1. 用户切换到另一个任务，仍停留在旧任务的第3页；
2. Reviser生成了新的测试点集合，旧页码或展开项指向已经不存在的内容。

页面同时记录分页所属`task_id`和测试点集合签名：

- task_id改变：重置活动导航、页码和展开项；
- 集合签名改变：保留当前导航，但重置页码和展开项；
- 普通rerun：都不改变，继续用户当前浏览位置。

集合签名只用于识别展示数据是否变化，不回写AgentState。

### 28.4 为什么展开项不能使用当前页序号

“第1条”只是当前页的位置，翻到下一页又会出现新的“第1条”。如果把页内序号作为身份，
展开状态和人工反馈目标都会错位。

页面使用测试点的稳定业务身份维护展开项，分页序号只负责显示。人工反馈仍从完整集合中
选择真实测试点标题，不使用分页后的临时位置。

### 28.5 Dialog为什么不会改变Agent流程

Dialog读取的是原有Orchestrator决策和Agent事件，只调整展示位置。打开和关闭Dialog都会
触发页面交互，但执行节点仍受原有防重复条件、State和rerun顺序控制。页面专用key与业务
session_state分开后，关闭Dialog只影响可见性，不会推进Agent。

### 28.6 面试自测

#### 问：如何判断固定工作区没有产生新的多层滚动？

> 真实浏览器同时检查页面外层高度和局部容器的`clientHeight`、`scrollHeight`及
> `overflow-y`。长需求与长报告场景下，页面外层高度不增长，只应有左侧需求和右侧结果
> 两个`overflow-y: auto`正文容器。

#### 问：为什么分页不放进AgentState？

> AgentState描述任务事实和执行状态；页码、活动导航和展开项只是单个浏览器的阅读位置。
> 把它们写入AgentState会污染持久化数据，也可能让未来的MySQL任务恢复依赖具体页面实现。

#### 问：测试点集合签名有什么作用？

> 它让页面识别“数据内容已经换了一批”，即使task_id没有改变，也能把页码和展开项恢复到
> 安全初始值，避免Reviser完成后继续引用旧测试点。

### 28.7 动手练习

- [ ] 构造12条测试点，确认三页分别显示5、5、2条
- [ ] 在第1页展开测试点后翻页，确认展开状态被清除
- [ ] 打开并关闭执行详情，确认当前结果页、页码和展开项不变
- [ ] 提交人工反馈，确认仍停留在人工反馈结果页
- [ ] 比较分页前后的`state.test_points`，确认集合内容完全一致

---

## 二十九、阶段 2.11.5D：同步任务如何提供可信的动态反馈

### 29.1 Spinner能表示什么

`st.status(state="running")`表示“当前节点尚未返回”，属于不确定进度动画。它不能说明已经
完成百分之多少，也不能预测剩余时间。同步脚本可以在调用LLM前把这个组件发送给浏览器，
但阻塞调用期间无法继续追加新事件。

因此可信的页面反馈是：

```text
调用前：显示节点、处理内容、等待说明和Spinner
调用中：Spinner持续动画，不伪造百分比
调用后：现有rerun刷新阶段、事件和结果
```

### 29.2 主页面进展与完整事件的区别

完整AgentEvent是技术审计数据，包含内部步骤、类型和原始消息。主页面摘要是Presenter对
现有事件的只读映射，只保留用户关心的任务创建、节点开始/完成、需求补充、人工反馈、完成
和失败，并限制为最近3条。

Presenter不创建新事件，也不把中文摘要写回State，所以不会影响Agent判断。

### 29.3 为什么左右外框要统一，而正文高度不能统一

左右外框表达一个完整工作台，应共用`WORKSPACE_HEIGHT`。但两侧固定区域不同：

- 左侧有标题，剩余空间全部给需求和操作；
- 右侧有状态、阶段、执行状态、统计和导航，剩余空间给当前结果。

因此统一的是外层560px边界，正文通过Flex占用各自剩余空间，而不是再分别硬编码两个正文
高度。这样既能底部对齐，也不会产生外层滚动。

### 29.4 为什么执行中必须禁用“新建分析”

同步节点正在使用当前State。如果此时清空任务，页面状态、内存任务存储和正在返回的节点
结果可能发生竞争。页面禁用按钮是第一层操作约束，原有`in_progress`标记是第二层防重复
约束。两者都不需要改变AgentState状态机。

### 29.5 面试自测

#### 问：Spinner是否等于流式执行？

> 不是。Spinner只说明同步调用仍未返回。真正的流式执行需要模型Token流、后台任务、SSE
> 或轮询等架构，本阶段没有实现这些能力。

#### 问：为什么最近进展不直接显示最后3个Event？

> 最后3个Event可能包含内部枚举、重复完成事件或技术错误细节。Presenter先按白名单过滤、
> 中文转换和去重，再截取3条，主页面保持可理解，完整信息仍在Dialog。

### 29.6 为什么固定底部操作不使用浏览器position: fixed

`position: fixed`会把按钮固定到整个浏览器窗口，容易脱离左侧栏边界，也无法自然适配左右
列宽。页面改为按Streamlit容器顺序渲染标题、定高正文和操作栏：只有正文容器滚动，操作栏
仍属于左侧工作区的正常文档流。

待确认问题原先依赖`st.form_submit_button`，按钮必须位于表单内部。拆分后使用带任务ID和
问题序号的普通控件保存页面输入，固定操作按钮读取这些值并调用同一校验逻辑，因此没有
绕过必填项、“暂不确定”、State恢复或rerun顺序。

测试点详情Dialog同样只保存页面身份：优先使用测试点已有ID，无ID时使用完整结构化内容的
确定性哈希。分页序号不是身份，Dialog键也不写入AgentState。

### 29.7 动手练习

- [ ] 分别构造六个节点的current_step，核对中文处理说明
- [ ] 构造5条混合Event，确认主页面只展示最近3条关键进展
- [ ] 将任务存储设为`in_progress=True`，确认Spinner和禁用按钮同时出现
- [ ] 对比等待、完成和失败状态，确认Spinner已经停止
- [ ] 在浏览器中测量左右外框的top、bottom和height是否完全一致

### 29.8 为什么在这里停止继续打磨Streamlit页面

当前页面已经能够完整演示需求输入、Agent节点执行、暂停恢复、测试点生成、质量评审、
受控修正、人工反馈和报告下载。继续追求完全复刻DeepL或生产级固定工作台，会把时间投入
到响应式布局、浏览器兼容和前端组件细节，而不是项目简历更重要的Agent编排、质量控制和
性能优化。

因此将Streamlit定位为V1功能演示界面是一种范围管理：功能链路必须完整、状态必须可解释、
错误必须可观察；生产级后台任务、高可用、复杂响应式布局和独立前端留到真正需要时再做。

---

## 三十、路线图校准：MySQL、Milvus与知识资产闭环

本节解释阶段2.12之后采用的新规划。旧章节中出现的“阶段2.12直接接MySQL”或“阶段2.12
直接做离线评测”属于当时计划，不再作为当前执行顺序；最新顺序以秋招路线图为准。

### 30.1 当前保存功能到底在哪里

项目仍保留两层旧兼容能力：

```text
TestAssistantManager.save_to_rag()
→ RAGService.save_case()
→ MilvusRAGManager.save_case()
```

但当前Agent页面没有调用这条链路。因此：

- “从Milvus检索历史资产”已经接入Agent节点；
- “把当前Agent结果沉淀为历史资产”尚未接入；
- 当前Milvus内容只能来自旧Workflow、手动写入或既有数据；
- 本地`bug_experience.txt`是静态经验，不是Agent任务自动积累的长期知识。

面试时不能把旧兼容方法说成当前Agent已经完成知识闭环。

### 30.2 MySQL和Milvus的区别

可以把MySQL理解为完整档案库，把Milvus理解为语义索引：

```text
MySQL
→ 保存完整KnowledgeAsset、版本、来源、确认状态和索引状态

Milvus
→ 保存向量、asset_id、版本和少量检索元数据
```

Milvus技术上可以保存文本，当前旧实现也确实保存了`prd_content`和`test_points`。但完整业务
数据只保存在Milvus会导致版本、人工确认、停用、事务和复杂查询难以管理。新设计因此让
MySQL成为权威数据源，Milvus只负责“找出哪些资产可能相关”。

#### 面试追问：既然完整资产在MySQL，Milvus怎么比较？

> 保存知识资产时，系统从需求摘要、模块、事实、规则和风险构建一段稳定的检索文本，
> 再由Embedding服务把它变成向量并写入Milvus。新需求到来时也先变成查询向量，Milvus
> 使用余弦相似度比较查询向量与历史资产向量，返回Top-K的asset_id和相似度。Application
> Service随后根据asset_id从MySQL读取完整测试点，不需要逐份读取MySQL文档再比较。

### 30.3 为什么第一版一条资产只需要一个检索向量

当前检索目标是先找到“业务语义、规则和风险相近的历史需求”，再读取它关联的完整测试点。
第一版可以采用：

```text
一个KnowledgeAsset
→ 一个需求与风险检索文本
→ 一个向量
→ 一个asset_id
```

只有离线评测证明资产级检索粒度太粗时，才按模块或测试场景拆分多个Chunk。提前拆分会增加
去重、版本、召回合并和来源追踪复杂度，没有评测证据前不实现。

### 30.4 为什么不能自动把生成结果写入Milvus

模型生成结果可能存在：

- 未解决的需求问题；
- 无依据业务规则；
- Reviewer尚未通过；
- 待处理人工反馈；
- 公司内部或敏感内容；
- 重复资产。

因此知识沉淀必须满足：

```text
Reviewer通过
AND 任务完成
AND 没有待处理反馈或规则确认
AND 用户明确确认内容与数据边界
→ 才允许创建KnowledgeAsset
```

MySQL先保存`pending_index`资产，再调用Embedding和Milvus。索引失败时改为`index_failed`，
保留完整资产和错误原因，后续可以幂等重试。

### 30.5 version和execution_id为什么都需要

- `version`解决两个调用同时基于旧State写入的问题；
- `execution_id`解决重复点击、网络重试或API重发的问题。

两者只能保证同一节点结果最多提交一次。服务在LLM已经返回但数据库尚未保存时崩溃，重试
仍可能再次调用LLM，因此不能宣称对外部模型实现Exactly Once。

### 30.6 新阶段为什么拆成2.12～2.17

这些阶段解决的是不同问题：

```text
2.12：页面和应用用例边界
2.13：任务快照、恢复和重复保护
2.14：知识资产准入、存储和向量索引
2.15：上下文预算和可观测性
2.16：质量评测与消融实验
2.17：可选API和异步执行
```

如果全部塞进阶段2.12，就无法做到一个提交对应一个可解释、可验证的小目标。后续小阶段统一
使用`2.12.1`、`2.12.2`编号，历史2.11.5A～2.11.5D名称不修改。

### 30.7 面试参考答案

#### 问：你的项目是否实现了长期记忆？

> 当前只实现了Milvus历史资产检索，还没有完成当前Agent结果的可靠知识沉淀，所以我不会
> 把它描述为已经实现长期记忆。规划中的知识闭环会由MySQL保存人工确认后的完整资产，
> Milvus保存语义索引；这比笼统地说长期记忆更准确，也能进行版本、来源和污染控制。

#### 问：为什么任务表和知识资产表要分开？

> 任务快照用于恢复执行，包含中间状态、错误和待确认信息；知识资产用于后续RAG，只能保存
> 通过质量门禁并经用户确认的结果。如果直接把所有任务都作为知识，失败任务和模型幻觉会
> 污染后续检索。

#### 问：Milvus返回结果后为什么还要查询MySQL？

> Milvus擅长向量近邻搜索，但MySQL更适合保存完整结构化资产、版本、确认状态和索引状态。
> Milvus返回asset_id和相似度，MySQL提供权威内容，ContextBuilder再决定传给模型的最小
> 上下文，三层职责清晰。

### 30.8 动手练习

- [ ] 画出“任务快照”和“知识资产”的两条独立写入链路
- [ ] 用自己的话解释Milvus如何在不读取MySQL全文的情况下完成相似度比较
- [ ] 列出五种禁止自动沉淀知识资产的情况
- [ ] 解释Milvus写入失败后为什么不能删除MySQL中的完整资产
- [ ] 解释为什么没有评测前不做按测试点Chunk的复杂索引

---

## 三十一、阶段 2.12：Application Service与TaskRepository

### 31.1 为什么页面不能直接调用Agent节点

旧页面同时做了四件事：

```text
收集按钮输入
→ 修改AgentState
→ 选择并调用节点
→ 把可变State保存到进程字典
```

这会导致未来增加MySQL或FastAPI时，页面中的创建、恢复、反馈和推进逻辑需要再复制一次。
更重要的是，如果页面能够调用任意节点，就可能绕过Orchestrator的状态检查。

Application Service把“用户想做什么”转换为应用用例：

```text
页面：继续任务
→ Application Service.advance_task(task_id)
→ Repository加载隔离副本
→ Orchestrator决定合法下一节点
→ 执行并保存
→ 返回只读TaskView
```

页面没有`execute_node("review")`之类的接口，因此不能跳过需求分析或生成步骤。

### 31.2 Application Service和普通Service有什么区别

项目原有`LLMService`、`RAGService`和`DocumentService`封装某一种外部能力；Application
Service编排一个完整用户用例。

```text
Application Service：创建任务、继续任务、提交补充、确认规则
LLM Service：调用模型
RAG Service：检索历史资产
Document Service：解析上传文件
```

Application Service不是新的Orchestrator。它负责事务边界式的“加载—执行—保存”，节点
顺序和分支条件仍由AgentOrchestrator负责。

### 31.3 Command为什么比很多位置参数更清楚

`SubmitFeedbackCommand`把一次用户操作所需字段放在不可变对象中：

```python
SubmitFeedbackCommand(
    action="add",
    feedback_type="test_suggestion",
    target="新增测试点",
    content="增加并发核销场景",
    reason="历史缺陷",
)
```

好处包括：

- 调用语义清楚
- 未来API可以把请求体转换成同一个Command
- 测试可以独立构造用例输入
- 不把Streamlit控件对象传入Agent核心

上传文件也先转换为`UploadedDocument(filename, content)`，Application Service再交给
DocumentService，核心层不依赖Streamlit的UploadedFile类型。

### 31.4 Repository为什么必须返回隔离副本

如果Repository直接返回内部保存的可变State，调用方即使不执行`save()`也能修改数据：

```python
state = repository.get(task_id)
state.test_points.clear()  # 内部对象可能已经被改掉
```

InMemory实现使用深复制：

```text
create：保存副本
get：返回副本
save：再次保存副本
list：每项返回副本
```

这样Application Service必须显式保存，行为更接近未来MySQL Repository。单元测试也验证：
修改第一次`get()`得到的对象，不会影响第二次读取。

### 31.5 TaskView为什么不是AgentState

AgentState包含`start_step()`、`wait_for_user()`、`fail()`等可变业务方法。页面如果获得它，
可以绕过Application Service直接改变状态。

TaskView只用于读取：

- 由State隔离快照构建
- 列表与字典属性读取时返回副本
- 决策和性能指标使用不可变元组
- 提供页面所需的派生信息，例如待确认规则和修正上限

页面仍可以使用`task.status`、`task.test_points`等熟悉字段，但不能通过这些值修改Repository
中的真实任务。

### 31.6 为什么InMemory Repository按会话装配

旧`st.cache_resource`任务字典由整个Streamlit进程共享。它能让新会话凭task_id找到任务，
但也意味着不同用户可能拿到同一份可变对象。

阶段2.12选择会话级装配：

```text
一个Streamlit会话
→ 一个Application Service
→ 一个InMemoryTaskRepository
```

这保证会话之间不会意外共享内存任务。代价是新会话、硬刷新导致会话重建或服务重启后无法
恢复。该问题不能再用全局字典假装解决，阶段2.13会使用MySQL保存权威快照。

### 31.7 最小性能指标记录在哪里

每次`advance_task()`在Application Service边界记录：

```text
调用前：action、started_at
调用后：finished_at、duration、succeeded
异常时：error_type
任务级：累加所有节点duration
```

这个位置能够覆盖RequirementAnalyzer、Retriever、Generator、Reviewer、Reviser和Finalizer，
也能记录节点失败，不需要侵入每个节点。

它目前不能区分一个节点内部的LLM、Embedding、Milvus和JSON重试分别用了多久，也没有真实
Token usage。这些需要在统一外部调用封装中记录，属于2.15，而不是伪造估算数据。

### 31.8 面试问题与参考答案

#### 问：Application Service会不会只是多套了一层？

> 不只是转发。它定义用户用例边界，负责从Repository加载隔离任务、调用受控Orchestrator、
> 保存结果、记录节点指标并返回只读TaskView。页面和未来FastAPI都能复用同一套用例，
> 而节点顺序仍只有Orchestrator维护。

#### 问：为什么Repository接口现在就保留expected_version？

> 阶段2.12只使用单会话内存实现，没有可靠数据库版本，所以参数只是兼容点，不能宣称已经
> 实现乐观锁。阶段2.13的MySQL Repository会读取version并在条件更新失败时报告并发冲突。

#### 问：页面完全不依赖Agent了吗？

> 页面不再依赖可变AgentState、Orchestrator、节点或FeedbackHandler，但仍读取状态枚举用于
> 展示。真正的业务调用只有Application Service，Presenter消费只读TaskView。这属于调用
> 边界解耦，不代表领域概念从页面完全消失。

#### 问：为什么不在2.12直接接MySQL？

> 如果同时修改调用边界和存储实现，出现回归时很难判断是应用用例还是数据库问题。先用
> InMemory Repository证明接口和页面行为，再在2.13替换为MySQL，风险更可控。

#### 问：节点指标为什么不直接写进AgentState？

> AgentState保存任务业务事实和执行状态；当前指标属于应用执行元数据。先由TaskRecord保存，
> 避免为了最小基线修改领域模型。2.13设计事件表时再确定长期持久化结构。

### 31.9 动手练习

- [ ] 从“提交人工反馈”按钮开始，画出页面到Repository保存的调用链
- [ ] 修改`repository.get()`返回的test_points，确认再次读取没有变化
- [ ] 创建两个InMemoryTaskRepository，确认任务不会跨实例出现
- [ ] 构造失败节点，检查NodeExecutionMetric中的错误类型
- [ ] 搜索页面代码，确认不存在AgentOrchestrator和HumanFeedbackHandler直接调用

### 31.10 掌握检查

- [ ] 能区分Application Service、AgentOrchestrator和外部能力Service
- [ ] 能解释Command、TaskRecord、TaskView和TaskRepository的职责
- [ ] 能说明为什么页面只保存task_id和UI状态
- [ ] 能解释会话隔离与刷新恢复之间的取舍
- [ ] 能说明当前性能基线能证明什么、不能证明什么

### 31.11 验收修正：特殊恢复路径也不能绕过Orchestrator

首次2.12实现中，普通节点由Orchestrator执行，但补充答案后的重新分析由Application Service
直接调用RequirementAnalyzer。这虽然已经让页面解耦，却仍留下了一个特殊节点入口：

```text
Application Service → RequirementAnalyzer
```

修正后，Orchestrator提供面向业务语义的恢复入口：

```text
Application Service
→ AgentOrchestrator.resume_with_clarifications
→ RequirementAnalyzer.reanalyze_with_clarifications
```

这个入口不是`execute_node(node_name)`。调用方不能选择任意节点，Orchestrator会检查：

- 当前任务是否确实在等待用户
- 答案是否覆盖当前全部问题
- 非空答案是否包含有效内容

Application Service仍负责Repository的加载和保存、自动推进、最大步数保护与耗时记录，但不再
持有RequirementAnalyzer工厂。待处理答案在节点调用前被消费；如果重新分析再次提出问题，
用户必须针对新问题提交新的一批答案，旧答案不会在rerun时重复执行。

面试时可以这样解释：

> Application Service负责“用例边界”，Orchestrator负责“节点执行权”。即使补充恢复属于特殊
> 用户动作，也不能让Application Service直接调用节点，否则未来增加持久化和幂等保护时会
> 出现两条执行链。通过语义明确的Orchestrator恢复入口，可以保持页面接口不变，同时把状态
> 校验和具体节点执行收口到同一处。

## 三十二、阶段2.13.1：版本化任务快照

### 32.1 快照和普通`to_dict()`有什么区别

旧`AgentState.to_dict()`主要用于展示和证明当前对象能变成JSON兼容数据，它没有反向恢复、
结构版本和严格校验。可靠快照必须回答：

- 这个JSON属于哪个结构版本
- 哪些字段必须存在
- 枚举和时间如何恢复
- 遇到未来字段或非法值怎么办
- 是否包含继续执行所需的应用元数据

因此阶段2.13.1使用独立`TaskSnapshotSerializer`，避免把数据库契约和迁移职责继续塞进
AgentState。

### 32.2 为什么快照对象是TaskRecord而不只是AgentState

AgentState能回答“任务业务上走到哪里”，但不能完整回答“应用接下来如何安全继续”。例如
以下字段位于TaskRecord：

- `pending_clarifications`：已经提交但尚未被Orchestrator消费的答案
- `auto_run`：是否继续自动推进
- `next_action`：供恢复和展示使用的下一动作
- `decisions`：已经发生的编排决策
- `metrics`：节点执行耗时和失败类型

所以快照以TaskRecord为恢复边界，同时把AgentState放在独立`state`节点，保持业务状态和
应用元数据的概念分层。

### 32.3 schema_version和数据库version为什么不是一回事

`schema_version=1`表示“这份JSON使用第1版字段结构”，决定使用哪个反序列化和迁移规则。

数据库`version`表示“这条任务记录已经被更新了几次”，用于乐观锁判断当前写入是否基于旧
数据。前者解决格式兼容，后者解决并发覆盖。本阶段只实现前者。

### 32.4 为什么时间统一为UTC

项目当前事件和指标本来就使用带时区datetime。序列化时统一转换为UTC ISO 8601，例如：

```text
2026-07-30T00:03:00+00:00
```

这样跨电脑、容器和数据库时不会把本地时间误认为另一个时区。反序列化会拒绝
`2026-07-30T08:03:00`这类没有时区的信息。

### 32.5 为什么未知字段选择严格拒绝

如果旧代码静默忽略新字段，它可能恢复出“看起来成功、实际丢状态”的任务。例如新版本增加
暂停原因，旧代码忽略后可能错误推进节点。当前阶段尚无多版本迁移，因此顶层、state、
application、事件、决策和指标都采用严格字段集合；未来升级时先显式增加迁移路径。

### 32.6 为什么`in_progress`不持久化

`in_progress`是当前进程内防止同步重复调用的临时标记。服务在执行中崩溃时，如果把`True`
原样恢复，任务可能永久卡住；如果直接写`False`，又不能证明旧执行已经停止。

可靠方案需要数据库执行租约、过期时间和execution_id。本阶段不提前实现这些能力，因此
快照排除`in_progress`，恢复固定为`False`，并把跨进程重复保护明确留给2.13.4。

### 32.7 快照里哪些类型会被重建

- State状态、当前步骤、RAG状态恢复为枚举
- Agent事件恢复为`AgentEvent`
- Orchestrator决策恢复为`OrchestratorDecision`
- 节点指标恢复为`NodeExecutionMetric`
- datetime恢复为带UTC时区的datetime
- TestPoint、ReviewResult、HumanFeedback等先由现有领域模型严格校验

注意：AgentState当前约定把测试点、评审结果和反馈保存为结构化字典，所以恢复后仍按这个
领域存储约定放回字典，而不是擅自改变AgentState字段类型。

### 32.8 面试问题与参考答案

#### 问：为什么不用pickle保存AgentState？

> pickle依赖Python类路径和代码版本，内容不可读，还存在反序列化安全风险。项目使用显式
> JSON契约、稳定枚举值、schema_version和严格字段校验，便于审计、跨服务读取和版本迁移。

#### 问：为什么事件既在快照中，又计划放独立事件表？

> 快照中的事件保证一次读取即可完整恢复TaskRecord；独立事件表用于按顺序增量审计、性能
> 查询和故障排查。后续保存时两者必须在同一事务提交，避免快照和审计轨迹不一致。

#### 问：如果未来增加AgentState字段怎么办？

> 先提升schema_version，再为旧版本提供明确迁移函数，迁移到当前结构后再走统一校验。
> 不能给缺失字段随意填默认值，否则可能改变暂停、修正或完成语义。

#### 问：当前快照能否证明已经支持服务重启恢复？

> 不能。它只证明任务可以可靠转换为JSON并重建领域对象。只有MySQL Repository接入、节点后
> 原子保存和按task_id重新加载验证完成后，才能描述服务重启恢复。

### 32.9 动手练习

- [ ] 找出快照中AgentState与application字段的边界
- [ ] 把一个等待用户任务序列化，检查open_questions和pending_clarifications的区别
- [ ] 将status改为非法值，观察专用校验错误
- [ ] 删除schema_version，解释为什么不能默认按v1恢复
- [ ] 修改恢复对象的test_points，确认原对象不受影响
- [ ] 说明MySQL保存快照和新增事件为什么必须在同一事务

### 32.10 掌握检查

- [ ] 能区分schema_version、数据库version和execution_id
- [ ] 能解释TaskRecord为什么是完整恢复边界
- [ ] 能说明UTC、严格未知字段和深复制分别防什么问题
- [ ] 能说明哪些运行时对象不能进入快照
- [ ] 能准确描述2.13.1已完成什么、尚未完成什么

### 32.11 为什么必须验证“恢复后继续执行”

只验证`JSON → AgentState`说明对象能被读取，不能证明恢复后的任务仍满足原状态机。阶段
2.13.1收尾增加了正式集成测试，让恢复任务继续经过Application Service和真实
AgentOrchestrator边界：

- 等待补充任务恢复后，补充答案仍由Orchestrator交给RequirementAnalyzer
- 待确认业务规则恢复后，确认和拒绝仍经过HumanFeedbackHandler校验
- Reviewer未通过任务恢复后，仍按Reviser再Reviewer的顺序执行
- completed和failed任务恢复后，Orchestrator和所有节点调用次数保持为0

节点使用Fake避免真实外部调用，但“下一动作由谁决定”仍由生产AgentOrchestrator验证。这比
只比较JSON字符串更能证明快照具有可继续执行的业务语义。

## 三十三、阶段2.13.2：MySQL任务与事件持久化边界

### 33.1 为什么MySQL只需要替换Repository

Application Service只依赖`TaskRepository`抽象，所以创建、推进、补充和反馈用例不需要知道
任务保存在字典还是MySQL：

```text
Streamlit → Application Service → TaskRepository
                                 ├─ InMemoryTaskRepository
                                 └─ MySQLTaskRepository
```

这就是阶段2.12先做调用边界的价值。阶段2.13.2没有把SQL写进页面或Agent节点，也没有重新实现
一套状态机。

### 33.2 为什么快照和事件要保存两份

`agent_tasks.snapshot_json`用于一次读取后完整恢复TaskRecord；`agent_task_events`用于按顺序查询
执行轨迹和审计。前者偏向恢复，后者偏向检索与排障。事件虽然在快照内也存在，但独立表避免
每次查看轨迹都解析整份快照。

### 33.3 为什么必须同一事务提交

如果先更新快照后写事件，而事件插入失败，系统会出现“任务已经前进，但审计轨迹缺失”；反过来
则可能出现“轨迹显示完成，但任务快照仍停留在旧状态”。所以一次`save()`遵循：

```text
锁定任务行并读取event_count
→ 更新完整快照
→ 追加新增事件
→ 全部成功才commit
→ 任一步失败都rollback
```

### 33.4 event_count解决什么问题

快照里保存全部AgentEvent，事件表只需要追加数据库尚未拥有的部分。`event_count`记录已提交的
事件数量。保存时从该位置之后追加，并拒绝当前事件数小于数据库值，避免程序错误删除历史审计。

### 33.5 当前version为什么还不是乐观锁

数据库表中的`version`目前会随保存递增，但SQL尚未使用
`WHERE task_id = ? AND version = expected_version`，因此还不能检测调用方是否基于旧快照写入。
阶段2.13.4加入条件更新并检查受影响行数后，才能称为乐观锁。`schema_version`仍只表示JSON
结构版本，两者不能混淆。

### 33.6 为什么测试不连接真实云MySQL

单元测试需要快速、稳定且不依赖网络。Fake DB-API用于验证SQL调用顺序、参数、commit、rollback
和异常映射。本阶段已经额外验证真实MySQL 8.0.32连接和两张表的DDL，但仍未验证TaskRecord
真实CRUD和跨Application Service实例恢复，因此不能描述成已经完成服务重启恢复。

### 33.7 面试问题与参考答案

#### 问：为什么不用MySQL每个字段拆一列？

> AgentState结构复杂且仍可能演进，第一版用版本化JSON保存完整权威快照，减少恢复时的多表拼装。
> status、current_step、version和时间等高频查询或并发字段独立成列，兼顾恢复可靠性与查询效率。

#### 问：MySQL和Milvus在项目中分别负责什么？

> MySQL保存完整、可审计、可恢复的任务和未来KnowledgeAsset；Milvus只保存向量及asset_id等
> 检索索引。向量命中后再按asset_id从MySQL读取完整资产，不能把Milvus当权威文档数据库。

#### 问：当前MySQL能力已经能防止重复节点执行吗？

> 不能。当前阶段完成了持久化与事务边界，version只有递增记录。跨进程并发还需要2.13.4的
> expected_version条件更新、execution_id幂等和执行租约。

### 33.8 动手练习

- [ ] 从Application Service的`advance_task()`追踪到MySQL Repository的两次save
- [ ] 解释为什么节点开始前和结束后都可能保存快照
- [ ] 找出创建任务时初始`task_created`事件如何进入事件表
- [ ] 让Fake事件插入失败，观察任务事务为何回滚
- [ ] 对比schema_version、数据库version、event_count和execution_id的职责

### 33.9 掌握检查

- [ ] 能画出MySQLTaskRepository的依赖方向
- [ ] 能解释完整快照和独立事件表为什么同时存在
- [ ] 能说明事务、event_count和version分别解决什么问题
- [ ] 能准确说明Fake数据库测试能证明什么、不能证明什么
- [ ] 能说明2.13.3和2.13.4还需要补哪些证据

## 三十四、阶段2.13.3：真实MySQL恢复验证

### 34.1 这一阶段为什么几乎不改生产代码

2.13.2已经实现了MySQLTaskRepository，2.13.3的任务是验证这个边界在真实MySQL中成立。测试
能够直接通过，说明Application Service只依赖TaskRepository抽象的设计有效，不需要为了连接
真实数据库再改页面、Agent节点或状态机。

### 34.2 “跨实例恢复”是什么意思

可以把Application Service理解为一次应用运行期间的业务入口：

```text
Service实例A提交补充信息
→ MySQL保存TaskRecord快照
→ 丢弃实例A
→ 创建Repository实例B和Service实例B
→ B使用同一个task_id读取快照
→ Orchestrator继续合法下一步
```

实例B没有使用实例A的内存对象，所以恢复依据确实来自MySQL。这个测试近似验证应用重启后的
装配过程，但不涉及后台Worker和多进程并发。

### 34.3 两张表在真实测试里如何配合

- `agent_tasks`读取完整`snapshot_json`，一次重建TaskRecord
- `agent_task_events`独立保存事件顺序，便于审计和排障
- `event_count`连接二者：它应等于当前快照事件数和事件表记录数
- 删除任务时，外键`ON DELETE CASCADE`自动删除对应事件

真实CRUD测试在保存一次后看到version从1变成2、event_count等于3、事件表也有3条，说明快照
和审计轨迹在这个样本中保持一致。

### 34.4 为什么真实MySQL测试默认跳过

单元测试应该在没有网络、没有云数据库账号的电脑上也能稳定运行。因此真实集成测试只有设置
`RUN_MYSQL_INTEGRATION_TESTS=1`才执行；默认测试仍会发现这些用例，但标记为skip。这样既保留
真实证据，又不会让CI或新电脑因为外部环境不可用而失败。

### 34.5 为什么测试数据使用UUID并主动清理

每个TestAnalysisState自动产生独立task_id。测试只删除自己记录下来的精确ID，不使用清空表、
模糊条件或批量删除。这可以避免集成测试误删已有任务，也是测试外部数据库时的重要安全习惯。

### 34.6 当前还不能解决什么

跨实例“读取并继续”不等于跨进程“不会重复执行”。如果两个实例同时读取相同旧快照，它们仍
可能分别调用同一节点。2.13.4需要：

- `expected_version`检测旧快照写入
- `execution_id`识别重复执行请求
- 执行租约声明当前由哪个执行者处理，并支持超时释放

### 34.7 面试问题与参考答案

#### 问：如何证明任务不是从原进程内存恢复的？

> 第一个Application Service保存后被丢弃，测试重新创建MySQL Repository和Application
> Service，只传入原task_id。新实例能恢复待确认答案、领域枚举和下一动作，并继续经过真实
> Orchestrator边界，因此恢复来源是数据库快照，不是原内存对象。

#### 问：为什么集成测试不直接跑真实LLM？

> 本阶段验证的是持久化和恢复边界。节点使用Fake可以稳定断言下一动作由Orchestrator决定，
> 同时避免模型延迟、费用和输出波动掩盖数据库问题。真实模型质量属于后续离线评测范围。

#### 问：完成任务恢复后为什么还要调用advance_task？

> 这是为了证明终态保护仍然有效。completed和failed快照被新Service读取后，advance_task不会
> 构造Orchestrator或执行节点，最终报告和错误信息保持不变。

### 34.8 动手练习

- [ ] 手动画出Service A、MySQL、Service B之间的数据流
- [ ] 找出集成测试中如何核对version、event_count和事件表数量
- [ ] 解释为什么删除任务后事件应自动删除
- [ ] 关闭集成测试开关，观察3项测试为什么显示skip
- [ ] 说明跨实例恢复与重复执行保护的区别

### 34.9 掌握检查

- [ ] 能解释真实CRUD测试比Fake DB测试多证明了什么
- [ ] 能说明跨Application Service实例恢复的步骤
- [ ] 能说明为什么集成测试必须隔离和清理数据
- [ ] 能准确描述2.13.3已完成、2.13.4未完成的能力

## 三十五、阶段2.13.4：为什么需要三层重复执行保护

### 35.1 先看一个重复执行例子

假设任务当前数据库version是5，下一步是生成测试点：

```text
服务A读取 version=5
服务B也读取 version=5
服务A调用LLM并保存，数据库变成 version=6
服务B随后也调用LLM，想用旧的 version=5 保存
```

没有保护时，B可能覆盖A的测试点和事件。有了乐观锁，B的条件更新找不到
`task_id相同且version仍为5`的记录，因此明确冲突，不能覆盖version=6的结果。

### 35.2 version解决什么

`version`回答：“你要保存的内容，是不是基于数据库最新状态计算出来的？”

Repository读取时返回`VersionedTaskRecord(record, version)`；保存时传回`expected_version`。
MySQL更新条件包含：

```sql
WHERE task_id = ? AND version = ?
```

如果受影响行数不是1，说明读取后已有其他执行者改过任务，抛出`TaskVersionConflictError`。
这叫乐观锁，因为读取时不长期占用数据库锁，只在提交时检查数据有没有变化。

### 35.3 execution_id解决什么

`execution_id`回答：“这是不是同一次请求的重发？”

例如浏览器超时后重试同一个API请求，如果仍携带原来的execution_id，Repository发现该编号已经
完成，就直接返回已经保存的任务，不再调用一次LLM。当前Streamlit没有网络幂等键，因此未传入时
Application Service自动生成UUID；未来FastAPI可以从请求头或请求体接收并复用该编号。

### 35.4 执行租约解决什么

租约回答：“现在谁有权执行和提交这个节点？”

```text
worker-A领取租约，10分钟内拥有执行权
worker-B发现租约未过期，不能执行节点
如果worker-A进程崩溃，租约到期
worker-B把旧记录标记为expired，再领取新租约
worker-A即使晚到，也不能提交旧结果
```

它与永久锁不同：进程崩溃后不需要人工解锁，到期即可恢复。但租约时间必须覆盖常见模型调用时长；
未来改成后台任务后，还应由worker定期续租。

### 35.5 为什么要新增第三张表

三张表职责如下：

| 表 | 保存内容 | 主要用途 |
|---|---|---|
| `agent_tasks` | 最新TaskRecord快照、状态、version | 恢复任务与并发版本校验 |
| `agent_task_events` | 按序追加的AgentEvent | 审计完整执行轨迹 |
| `agent_task_executions` | execution_id、worker、租约、执行结果 | 幂等和跨进程执行权控制 |

执行记录不属于Agent的业务判断，所以没有放进AgentState快照。这样数据库并发策略变化时，不需要升级
`schema_version=1`的业务快照。

### 35.6 一次推进的完整调用链

```text
页面调用 advance_task(task_id)
→ Service读取TaskRecord和version
→ Repository领取execution_id租约，并递增version
→ Service让Orchestrator选择并执行节点
→ Repository校验version、execution_id、owner和过期时间
→ 同一事务保存快照、新事件和执行完成状态
→ 页面收到只读TaskView
```

页面仍然不知道具体执行哪个节点，Orchestrator的受控编排边界没有变化。

### 35.7 这是否等于Exactly Once

不等于。当前能保证的是：合法的节点结果只提交一次。

如果LLM请求已经发出后进程崩溃，租约到期后新worker可能再次调用LLM。数据库可以拒绝旧worker提交，
但无法撤回已经发送到外部模型的请求。因此简历和面试中应描述为“幂等结果提交与租约保护”，不能说
“LLM Exactly Once”。

### 35.8 面试问题与参考答案

#### 问：乐观锁和执行租约是否重复？

> 不重复。乐观锁防止旧快照覆盖新状态；执行租约在耗时节点开始前分配执行权，尽量避免两个worker
> 同时调用节点。即使租约边界发生竞争，最终保存仍要经过version校验。

#### 问：为什么不把`in_progress=True`写进AgentState？

> `in_progress`不是业务事实，而是运行时执行控制。简单布尔值无法表达由谁持有、何时过期，也可能在
> 进程崩溃后永远残留。独立执行记录包含owner和expires_at，才能安全恢复。

#### 问：为什么租约领取也要递增version？

> 领取租约改变了任务的持久化执行状态。递增version可以让领取前读到的旧副本全部失效，防止它们
> 在节点完成后绕过当前执行者提交结果。

### 35.9 动手练习

- [ ] 画出两个worker同时读取version=5时的冲突过程
- [ ] 在`InMemoryTaskRepository`中找到版本递增的三个位置
- [ ] 在MySQL Repository中找到领取租约和完成租约的两个事务
- [ ] 解释相同execution_id与不同execution_id并发请求的处理差异
- [ ] 说明租约过期后旧执行者为什么不能覆盖新执行者

### 35.10 掌握检查

- [ ] 能区分schema_version、数据库version和execution_id
- [ ] 能解释乐观锁、幂等键和租约各自解决的问题
- [ ] 能说明第三张表为什么不属于AgentState快照
- [ ] 能准确描述“结果幂等提交”与“外部请求Exactly Once”的区别
- [ ] 能指出当前600秒固定租约和无后台续租的限制

## 三十六、阶段2.13.5：为什么从unittest渐进升级到pytest

### 36.1 unittest和pytest是什么关系

它们不是只能二选一。现有测试继承：

```python
class AgentStateTests(unittest.TestCase):
    ...
```

pytest可以直接收集并执行这些用例。因此本阶段没有删除unittest，而是让pytest成为上层统一入口：

```text
现有unittest.TestCase ─┐
                       ├→ pytest统一收集、分类和报告
新增pytest函数测试 ────┘
```

原来的`python -m unittest discover`仍然可以运行，便于确认迁移没有破坏历史测试。

### 36.2 fixture解决什么问题

测试经常重复创建Repository和TaskRecord。pytest fixture把公共准备逻辑集中起来：

```python
def test_example(in_memory_task_repository, task_record_factory):
    record = task_record_factory("订单需求")
    in_memory_task_repository.create(record)
```

每个测试都会获得新的Repository，因此不会共享任务状态。它类似JUnit中的测试前置方法和依赖注入，
但可以按参数名组合使用，不必让测试类继承统一基类。

### 36.3 marker为什么有用

项目现在包含三种成本不同的测试：

- `unit`：快速、没有真实外部依赖
- `app`：启动Streamlit AppTest，速度稍慢
- `integration`：连接真实MySQL，必须显式开启

通过marker可以选择运行：

```powershell
python -m pytest -m unit
python -m pytest -m app
python -m pytest -m integration
```

以后CI可以先跑unit，再跑app；integration只在配置了安全测试数据库的环境中运行。

### 36.4 为什么pytest第一次收集会报错

pytest默认会收集测试文件里名字以`test_`开头的函数。原测试中存在：

- 从Presenter导入的`test_point_rows`
- 从Presenter导入的`test_point_summary_html`
- 名为`test_point`、实际只是构造数据的辅助函数

unittest只寻找`TestCase`方法，所以以前没有问题；pytest把这些函数误认为测试，并把函数参数当成fixture，
于是报告“fixture不存在”。解决方法是给导入函数使用普通别名，并把辅助函数改名为`make_test_point`，
而不是伪造无意义fixture。

### 36.5 为什么不重写全部260项测试

测试的价值来自断言和覆盖场景，不来自使用哪一种语法。一次性重写会带来：

- 大量难审查的机械diff
- 可能遗漏setUp、patch和异常断言
- 业务代码没有收益，却增加回归风险

因此当前策略是：旧测试不动，新测试优先使用pytest；发现某个测试文件重复setup过多时，再局部迁移。

### 36.6 面试问题与参考答案

#### 问：为什么项目同时保留unittest和pytest？

> pytest原生兼容unittest.TestCase。保留旧用例可以避免一次性重写造成回归，同时使用pytest提供fixture、
> marker和统一报告。新用例采用pytest风格，旧用例按维护收益逐步迁移。

#### 问：如何保证集成测试不会误连真实数据库？

> 文件被标记为integration还不等于允许连接。测试内部继续检查`RUN_MYSQL_INTEGRATION_TESTS=1`，默认会
> skip。因此marker负责分类，环境开关负责授权，两层边界同时存在。

#### 问：为什么pytest完整数量比unittest多3项？

> 新增3项pytest原生函数测试不会被unittest discover收集，但pytest会同时收集旧TestCase和新函数。
> 所以unittest是260项，pytest总计263项，其中6项真实MySQL默认跳过。

### 36.7 动手练习

- [ ] 运行`python -m pytest -m unit`并观察deselected数量
- [ ] 查看`tests/conftest.py`，解释两个fixture为什么不会共享状态
- [ ] 故意把marker拼错，观察`--strict-markers`如何报错，然后撤销修改
- [ ] 对比一个unittest异常断言与`pytest.raises`写法
- [ ] 说明marker分类和真实MySQL环境开关为什么不能互相替代

### 36.8 掌握检查

- [ ] 能解释pytest如何兼容现有unittest
- [ ] 能说明fixture、marker和普通assert的作用
- [ ] 能解释为什么采用渐进迁移而不是全部重写
- [ ] 能说清unit、app和integration三类测试边界
- [ ] 能解释pytest首次收集错误的根因和修复方式

## 三十七、阶段2.13.6：测试目录为什么要分层

### 37.1 为什么不能一直把测试放在`tests/`根目录

测试较少时，平铺文件容易查找；当项目同时包含Agent节点、Application Service、Repository、
Streamlit页面和真实MySQL测试后，单看文件名已经难以判断测试所属职责和运行成本。目录分层让
开发者先按代码边界定位，再查看具体场景。

### 37.2 当前目录分别放什么

```text
tests/
├── unit/          # 不访问真实外部服务的快速测试
│   ├── agent/     # 状态、节点、Orchestrator和人工反馈
│   ├── application/ # Application Service与任务快照
│   ├── repositories/ # 内存Repository与Fake MySQL测试
│   ├── services/  # LLM、RAG、Prompt、文档与结构化输出边界
│   ├── views/     # Presenter和展示数据转换
│   └── legacy/    # 旧Workflow兼容入口
├── architecture/  # 通过AST或源码检查依赖红线
├── app/           # Streamlit AppTest
└── integration/   # 需要显式授权的真实基础设施测试
```

这里的Fake MySQL测试仍属于unit，因为它不连接真实数据库；只有实际访问MySQL的测试才进入
`integration/mysql`。

### 37.3 目录分类和pytest marker有什么区别

- 目录用于代码导航和职责归属，例如Repository测试放在哪里。
- marker用于选择运行集合，例如只运行快速unit，或者单独运行app。

pytest现在根据目录自动添加marker。新建测试时只要放入正确目录，就不需要每个函数重复写
`@pytest.mark.unit`。`integration`目录中的测试仍需要环境变量开关，marker不会代替外部服务授权。

### 37.4 为什么每层需要`__init__.py`

项目仍保留`python -m unittest discover -s tests -v`作为兼容入口。`unittest`递归发现子目录时，
需要这些目录可以作为Python包导入，因此各层保留轻量`__init__.py`。pytest本身对目录要求更宽松，
但兼容旧入口时不能只考虑pytest。

### 37.5 为什么没有立刻拆很多`conftest.py`

当前公共fixture只有内存Repository和TaskRecord工厂，所有快速测试都可能复用，继续放在根
`tests/conftest.py`最清晰。只有未来出现“仅Agent使用”或“仅MySQL集成测试使用”的公共准备逻辑时，
才把fixture下沉到对应目录。提前建立空的多层conftest只会增加查找成本。

### 37.6 面试问题与参考答案

#### 问：为什么既按目录分层，又使用pytest marker？

> 目录表达代码职责，marker表达运行成本和外部依赖。真实MySQL与Fake MySQL都属于Repository测试，
> 但前者需要外部环境，后者是快速单元测试，所以它们应在不同运行层中。

#### 问：移动测试文件后如何证明没有漏测？

> 移动前后分别运行unittest和pytest，并比较收集数量与结果。此次移动前后unittest都是260项，
> pytest都是263项，其中6项真实MySQL默认跳过；数量和分类结果一致。

#### 问：为什么不把旧unittest一起改成pytest函数？

> 目录整理解决导航问题，语法迁移解决维护方式问题，两者风险不同。把它们混在一次提交中会让
> 测试丢失时难以定位原因，所以先只移动文件并保持断言不变。

### 37.7 动手练习

- [ ] 找出RequirementAnalyzer测试所在目录，并解释它为什么不放在Application目录
- [ ] 分别运行`python -m pytest -m unit`和`python -m pytest -m app`
- [ ] 说明Fake MySQL测试与真实MySQL测试为什么位于不同目录
- [ ] 新增一个不访问外部服务的Service测试，并确认它自动获得unit marker
- [ ] 删除一个子目录的`__init__.py`后观察unittest discover差异，再撤销实验修改

### 37.8 掌握检查

- [ ] 能画出当前测试目录树
- [ ] 能区分代码职责分层与运行成本分层
- [ ] 能解释`__init__.py`对旧unittest入口的作用
- [ ] 能说明什么时候应该新增子级`conftest.py`
- [ ] 能用测试数量证明目录迁移没有造成漏收集

## 三十八、阶段2.14.1：KnowledgeAsset如何防止知识污染

### 38.1 KnowledgeAsset是什么

AgentState记录“一次任务现在执行到哪里”，KnowledgeAsset记录“经过审核后可以被后续任务复用的稳定知识”。
两者不能混为一体：任务可能失败、等待补充或继续被人工修改，而知识资产必须是已经完成、可审计的版本。

一个KnowledgeAsset主要包含：

- 来源`task_id`和资产版本
- 原始需求及结构化摘要、事实、规则、状态和风险
- 结构化测试点
- Reviewer完整评审证据
- 最终报告
- 用户确认和数据安全确认时间
- `content_hash`及后续索引状态

### 38.2 为什么需要准入策略

如果“任务完成”后直接写入知识库，以下内容可能污染后续RAG：

- Reviewer没有通过的遗漏测试点
- 模型生成的无依据业务规则
- 用户刚提交但尚未处理的反馈
- 测试点已经修改、最终报告却还是旧版本
- 用户没有确认可以沉淀的敏感需求

`KnowledgeAssetAdmissionPolicy`把这些检查集中在一个确定性Python边界中，不调用LLM判断是否允许发布。

### 38.3 双重确认解决什么问题

`user_confirmed`表示用户认可当前结果可以作为知识；`data_safety_confirmed`表示用户确认内容符合数据安全要求。
两个值必须都为True。Reviewer只负责测试质量，不能替用户决定公司需求是否允许进入历史知识库。

### 38.4 content_hash是什么

content_hash由原始需求、结构化需求和测试点构成规范JSON，再使用SHA-256计算：

```text
业务内容
→ JSON字段排序、固定分隔符
→ UTF-8字节
→ SHA-256
→ 64位十六进制content_hash
```

asset_id、创建时间和索引状态不参与哈希，否则同一份业务内容每次确认都会得到不同哈希，无法查重。
当前第一版包含原始需求，因此原文变化会产生新哈希；更复杂的语义去重留到有真实样本后评估。

### 38.5 为什么新资产是pending_index

2.14.1只证明资产有资格被保存，并没有调用Embedding和Milvus。因此新资产状态是`pending_index`：

```text
已通过准入并创建资产 ≠ 已建立向量索引 ≠ 已能被RAG检索
```

后续2.14.2先写入MySQL权威存储，2.14.3再索引到Milvus。即使Milvus失败，MySQL中的完整资产仍可重试。

### 38.6 Repository和Application Service如何配合

```text
用户确认动作
→ KnowledgeAssetApplicationService按task_id读取TaskRecord
→ AdmissionPolicy校验并创建KnowledgeAsset
→ KnowledgeAssetRepository保存隔离副本
→ 返回KnowledgeAssetView摘要
```

页面未来只调用Application Service，不直接操作Repository；准入策略也不依赖MySQL、Milvus或页面。

### 38.7 面试问题与参考答案

#### 问：为什么Reviewer通过后还要用户确认？

> Reviewer验证覆盖度、可执行性和无依据断言，但不能判断公司数据是否允许沉淀，也不能代替业务负责人承担确认责任。
> 因此质量评审和用户授权是两个独立门槛。

#### 问：MySQL和Milvus在知识资产中分别负责什么？

> MySQL保存完整、可审计、可恢复的KnowledgeAsset，是权威数据源；Milvus只保存向量和asset_id等少量索引信息。
> 检索时先由Milvus找到候选ID，再回MySQL读取完整资产。

#### 问：content_hash为什么不包含创建时间？

> content_hash表达业务内容身份。时间每次都不同，如果加入哈希，相同内容将无法被识别为重复。

#### 问：当前阶段能否写“实现知识库闭环”？

> 不能。当前只完成模型、准入和内存Repository边界，尚未写入MySQL、建立Milvus V2索引或让后续任务检索。

### 38.8 动手练习

- [ ] 阅读`knowledge_assets/policy.py`并列出所有拒绝沉淀的条件
- [ ] 修改一个测试点但不更新final_result，观察准入策略为什么拒绝
- [ ] 使用相同内容创建两个资产，观察Repository的content_hash冲突
- [ ] 说明同一task_id为什么可能产生asset_version=2
- [ ] 画出TaskRepository与KnowledgeAssetRepository的职责边界

### 38.9 掌握检查

- [ ] 能区分AgentState、TaskRecord和KnowledgeAsset
- [ ] 能解释Reviewer通过与用户双重确认的不同职责
- [ ] 能说明content_hash包含和不包含哪些字段
- [ ] 能解释pending_index不代表已经可检索
- [ ] 能准确描述2.14.1已经实现和尚未实现的范围

## 三十九、阶段2.14.2：为什么MySQL保存完整资产，Milvus只保存索引

### 39.1 用户点击一次保存，后端为什么需要多层代码

对用户来说，未来只有一个“保存到知识库”按钮。后端仍要依次完成：

```text
用户确认
→ KnowledgeAssetApplicationService
→ AdmissionPolicy准入校验
→ KnowledgeAssetSnapshotSerializer生成版本化JSON
→ MySQLKnowledgeAssetRepository保存完整资产
→ 后续Milvus索引
```

按钮是交互入口，不等于底层只有一条简单INSERT。分层的价值是让准入、序列化、数据库和向量索引分别可测试、可替换、可失败。

### 39.2 asset_json和独立列分别解决什么问题

`asset_json`保存完整KnowledgeAsset，包括需求、测试点、Reviewer证据和最终报告。读取时一次恢复完整领域对象，不需要从很多表重新拼装。

以下字段同时独立成列：

- `source_task_id`：按来源任务查询；
- `asset_version`：区分同一任务的多次确认结果；
- `content_hash`：识别完全相同的内容；
- `status`：查询待索引或索引失败资产；
- `requirement_summary`：历史列表展示；
- `reviewer_score`、`test_point_count`：筛选和统计；
- 时间字段：审计和排序。

这种设计叫“完整快照 + 查询摘要列”。完整JSON负责恢复，独立列负责高效查询，两者职责不同。

### 39.3 schema_version和asset_version不要混淆

- `schema_version`表示JSON结构的版本。例如以后快照增加字段，需要schema v2读取器。
- `asset_version`表示同一个任务发布了第几版知识资产。例如用户修改测试点后重新确认，可能形成资产第2版。

前者解决代码兼容，后者解决业务历史。

### 39.4 两个唯一索引的作用

```text
UNIQUE(content_hash)
UNIQUE(source_task_id, asset_version)
```

第一个阻止相同内容重复保存；第二个阻止同一个任务并发创建两个相同版本。Python在写入前可以提前检查，但真正面对并发时，最终防线必须是数据库唯一约束。

### 39.5 为什么没有给source_task_id增加外键

任务记录和知识资产生命周期不同：

- 任务记录可能按时间清理；
- 已确认知识资产需要长期复用。

如果外键级联删除，清理任务会误删知识；如果限制删除，又会让任务无法正常清理。因此资产只保留`source_task_id`作为审计来源，不使用数据库外键绑定生命周期。

### 39.6 MySQL和Milvus如何配合

```text
Milvus返回asset_id和相似度
→ Repository按asset_id查询MySQL
→ 获得完整需求、测试点和来源证据
```

Milvus适合“找到相似内容”，不适合保存完整报告和复杂审计数据。MySQL负责权威内容，Milvus负责候选召回。即使Milvus损坏，也可以根据MySQL中的`pending_index`或`index_failed`资产重新构建索引。

### 39.7 代码阅读顺序

1. `knowledge_assets/snapshots.py`：观察领域对象如何变成JSON以及如何严格恢复。
2. `repositories/mysql_knowledge_asset_repository.py`：观察Repository如何只依赖快照Codec。
3. `application/bootstrap.py`：观察环境配置如何选择内存或MySQL实现。
4. `tests/unit/repositories/test_mysql_knowledge_asset_repository.py`：观察Fake连接如何验证SQL和事务。
5. `tests/integration/mysql/test_mysql_knowledge_asset_repository_integration.py`：观察真实数据库测试如何隔离和清理数据。

### 39.8 面试问题与参考答案

**问题1：为什么不把KnowledgeAsset拆成十几张关系表？**

参考答案：第一版主要需求是可靠保存和完整恢复，资产内部结构仍可能演进。使用版本化JSON降低迁移和关联查询成本，同时把需要筛选、排序和唯一约束的字段独立成列。等出现稳定的跨资产统计需求后，再根据真实查询模式拆表。

**问题2：为什么Python提前查重后还要数据库唯一索引？**

参考答案：两个请求可能同时完成“未查到重复”的判断，然后同时写入。数据库唯一索引能在并发情况下提供最终一致的约束，Repository再把MySQL 1062转换为领域异常。

**问题3：当前是否已经完成知识库闭环？**

参考答案：没有。当前完成了准入和MySQL权威存储实现，资产状态仍为`pending_index`。还需要Embedding、Milvus V2索引、索引失败重试、检索回查和用户按钮，才能形成完整闭环。

### 39.9 动手练习

1. 画出用户点击保存后Application、Domain、Repository和MySQL的调用方向。
2. 在不看代码的情况下解释`asset_json`和`requirement_summary`为什么同时存在。
3. 修改一份测试快照的`schema_version`为2，观察为什么会被拒绝。
4. 说明MySQL重复键1062为什么应该转换成KnowledgeAssetAlreadyExistsError。

### 39.10 掌握检查

- [ ] 能解释schema_version与asset_version的区别
- [ ] 能解释完整JSON和摘要列的分工
- [ ] 能说明两个唯一索引防止的重复类型
- [ ] 能解释为什么MySQL是权威数据而Milvus只是索引
- [ ] 能准确说明2.14.2还没有页面按钮和Milvus检索

## 四十、阶段2.14.3：一份完整资产如何变成可检索向量

### 40.1 为什么不对完整报告只生成一个向量

完整报告同时包含需求事实、业务规则、风险和多个测试场景。只生成一个向量会把多个主题混合，导致某个具体场景的语义被稀释。

因此先拆成语义完整Chunk：

```text
需求概览Chunk
需求事实Chunk
业务规则Chunk
风险Chunk
测试点Chunk
```

每条Chunk都重复少量必要上下文，例如需求主题和所属模块，使它离开完整报告后仍然可以独立理解。

### 40.2 为什么Chunk不能无限增加

测试点越多，Embedding计算量越大。V2第一版定义：

- 一份资产最多32个Chunk；
- 单条检索文本最多1600字符；
- 记录候选总数、实际数量、省略数量和截断标记。

这不是认为32一定最优，而是先建立明确、可测量的成本上限。后续离线评测再根据Recall@K和耗时调整。

### 40.3 批量Embedding如何减少等待

错误方式：

```text
Chunk1 → HTTP请求
Chunk2 → HTTP请求
Chunk3 → HTTP请求
...
```

当前方式：

```text
[Chunk1, Chunk2, Chunk3, ...]
→ 一次POST /api/embed
→ [Vector1, Vector2, Vector3, ...]
```

批量请求不会消除模型计算，但减少了多次网络连接和往返等待。索引阶段也没有调用LLM。

### 40.4 Milvus每条记录保存什么

```text
chunk_id
vector
asset_id
source_task_id
asset_version
content_hash
chunk_type
chunk_index
search_text
was_truncated
```

`asset_id`负责回查MySQL，`asset_version + content_hash`负责确认索引仍然对应当前资产，`chunk_type`说明命中的是事实、规则、风险还是测试点。

### 40.5 为什么使用稳定chunk_id和upsert

MySQL和Milvus不能共享一个事务。可能发生：

```text
Milvus已经写入成功
→ MySQL更新indexed时网络中断
```

如果每次重试生成随机Chunk ID，会制造重复向量。稳定ID由资产ID、版本、类型和序号构成，同一资产重试会写入相同主键；使用upsert可以覆盖原记录。

### 40.6 状态如何流转

```text
pending_index
  ├─ 索引成功 → indexed
  └─ Embedding/Milvus失败 → index_failed
```

已经`indexed`的资产再次调用索引服务时直接返回，不重复执行。`index_failed`的正式重试策略留在2.14.5，本阶段不会偷偷重试。

### 40.7 代码阅读顺序

1. `knowledge_assets/indexing.py`：看Chunk如何确定性构建和限制数量。
2. `application/knowledge_asset_indexing_service.py`：看跨Repository、Embedding和VectorIndex的用例编排。
3. `services/embedding_service.py`：看一次批量HTTP请求。
4. `services/milvus_asset_index.py`：看V2集合字段和upsert数据。
5. `repositories/knowledge_asset_repository.py`：看期望状态保护。

### 40.8 面试问题与参考答案

**问题1：为什么Milvus不保存完整报告？**

参考答案：Milvus负责近似向量召回，MySQL负责完整、可审计、可恢复的数据。Milvus命中后通过asset_id回查MySQL，避免向量库承担版本、事务和复杂结构化数据管理。

**问题2：多道索引工序是否会让用户等待更久？**

参考答案：索引与测试分析主流程分离，Chunk构建不调用LLM，Embedding使用一次批量请求并限制最多32条。未来页面先确认MySQL保存成功，再由后台索引，不让用户等待完整索引；当前阶段只实现同步、可测试的后端用例，尚未宣称后台执行。

**问题3：如何保证Milvus记录和MySQL内容没有错位？**

参考答案：Milvus保存asset_id、asset_version和content_hash。检索阶段必须回查MySQL并同时校验状态、版本和哈希，不一致的记录作为过期或孤立索引丢弃。

### 40.9 动手练习

1. 使用测试资产打印所有Chunk，说明每条为什么可以独立理解。
2. 将`max_chunks`设为2，观察`omitted_count`。
3. 让Fake Embedding少返回一个向量，观察资产为什么进入`index_failed`。
4. 画出Milvus成功但MySQL状态更新失败后的安全重放过程。

### 40.10 掌握检查

- [ ] 能解释完整报告单向量的语义稀释问题
- [ ] 能解释批量Embedding减少的是网络往返而不是模型计算
- [ ] 能说明稳定chunk_id和upsert如何支持补偿重试
- [ ] 能说明pending_index、indexed和index_failed的含义
- [ ] 能准确说明2.14.3尚未实现历史资产查询

## 四十一、阶段2.14.4：Milvus找到片段后，如何安全取回完整资产

### 41.1 最简单的理解

Milvus像“书的搜索目录”，MySQL像“存放整本书的书架”。

```text
用户新需求
→ Milvus找到几个相似段落，并返回asset_id
→ 用asset_id一次去MySQL取回完整资产
→ 检查版本和哈希确实一致
→ 才允许作为历史知识候选
```

Milvus中的短文本只负责帮助找到候选，最终可信内容始终来自MySQL。

### 41.2 为什么不能只相信asset_id

假设旧资产版本1已经写入Milvus，后来MySQL中保存了版本2。如果只比较`asset_id`，旧向量可能错误关联新内容。
因此本项目同时比较：

- `asset_id`：是哪一份资产
- `source_task_id`：来自哪一次任务
- `asset_version`：资产是第几版
- `content_hash`：业务内容是否完全一致
- `status`：当前是否仍允许检索

这组校验让“找到谁”和“取回的完整内容是谁”保持一致。

### 41.3 为什么增加get_many

如果Milvus返回20条命中后逐条调用Repository：

```text
1次Milvus + 最多20次MySQL
```

这叫N+1查询，会增加网络往返。`get_many(asset_ids)`把它变成：

```text
1次Milvus + 1次MySQL IN批量查询
```

同一资产的多个命中Chunk还会先按`asset_id`合并，不重复取完整文档。

### 41.4 阈值和Top-K分别做什么

- `raw_limit=20`：Milvus最多先返回20个短片段
- `min_score=0.65`：低于基线的片段先丢弃
- `top_k=3`：最终最多返回3份完整资产

阈值是安全基线，不代表已经证明最佳。后续必须使用脱敏评测集统计错误召回和漏召回，再调整参数。

### 41.5 为什么本阶段不加LLM精排

LLM精排会增加一次模型请求、时长、成本和输出不稳定性。当前先用确定性的相似度、状态、版本和哈希规则建立可测试基线。
只有离线评测证明简单方案不足，并且LLM精排能稳定改善指标时，才值得加入。

### 41.6 代码阅读顺序

1. `knowledge_assets/retrieval.py`：看Milvus命中和最终候选的数据结构。
2. `application/knowledge_asset_retrieval_service.py`：看过滤、聚合、回查和校验顺序。
3. `repositories/knowledge_asset_repository.py`：看`get_many()`抽象和内存实现。
4. `repositories/mysql_knowledge_asset_repository.py`：看一条`IN`查询如何恢复完整资产。
5. `services/milvus_asset_index.py`：看COSINE搜索和元数据恢复。

### 41.7 面试问题与参考答案

**问题1：Milvus不保存完整文档，如何保证关联正确？**

参考答案：Milvus保存稳定asset_id、来源任务、资产版本和内容哈希。命中后按asset_id批量回查MySQL，并校验indexed状态、来源、版本和哈希；最终上下文使用MySQL完整资产，校验失败的向量命中直接丢弃。

**问题2：这条检索链路会不会很慢？**

参考答案：第一版固定为一次查询Embedding、一次Milvus搜索和一次MySQL批量查询，不进行逐条回查，也不加入LLM精排。真实耗时尚未测量，后续会分层记录Embedding、Milvus和MySQL耗时。

**问题3：为什么不能直接把Milvus命中的search_text给LLM？**

参考答案：短文本可能是孤儿索引或旧版本，也缺少完整评审证据。先回查权威存储可以防止过期业务规则污染新任务，并保留可审计来源。

### 41.8 动手练习

1. 把同一资产构造两个高分Chunk，观察最终为什么只返回一份资产。
2. 把Milvus命中的`content_hash`改成全0，观察候选被丢弃。
3. 将资产状态改成`retired`，观察即使相似度很高也不会返回。
4. 阅读MySQL `get_many()`，说明为什么它不是N+1查询。

### 41.9 掌握检查

- [ ] 能解释Milvus与MySQL各自保存什么
- [ ] 能说明asset_id、version和content_hash为什么要一起校验
- [ ] 能解释阈值过滤、Chunk聚合和Top-K的先后顺序
- [ ] 能说明为什么第一版不使用LLM精排
- [ ] 能准确说明2.14.4尚未接入当前Agent节点

## 四十二、为什么图文PRD理解必须放在ContextBuilder之前

### 42.1 核心结论

ContextBuilder解决“把哪些已知信息发给节点”，图文解析解决“系统到底知道了哪些信息”。

```text
图片中的关键流程没有被读取
→ Document内容先天缺失
→ ContextBuilder无法选中不存在的信息
→ LLM、RAG和Reviewer全部基于残缺需求工作
```

所以必须先建立完整、带来源的文档内容，再做上下文裁剪。

### 42.2 当前解析能力

- TXT和Markdown：读取UTF-8文本
- PDF：使用`pypdf`读取已有文本层
- DOCX：使用`python-docx`读取普通段落
- 暂不支持：Word表格、扫描PDF、图片文字、流程箭头、状态图和UI交互

“PDF上传成功”不等于“PDF中的所有内容都被理解”。

### 42.3 OCR和视觉理解的区别

OCR回答“图片里写了什么字”。视觉理解还要回答：

- 箭头从哪个节点指向哪个节点；
- 条件“是/否”分别进入哪个分支；
- UI操作会让页面或业务状态如何变化；
- 正文、表格和图片是否存在冲突。

流程图即使OCR文字全部正确，也可能错误理解分支关系，因此两者不能混为一谈。

### 42.4 为什么不能每张图都让用户确认

Human-in-the-loop应只处理少数高影响不确定项：

| 业务影响 | 解析置信度 | 行为 |
|---|---|---|
| 低 | 低 | 忽略装饰内容或记录警告 |
| 中 | 中 | 按风险继续，不暂停 |
| 高 | 高 | 带来源自动使用 |
| 高 | 中 | 作为关键风险继续 |
| 高 | 低 | 合并后询问用户 |
| 图文冲突 | 任意 | 优先询问用户 |

一轮默认最多3个阻塞问题，并支持“暂不确定并继续”。

### 42.5 离线评测在这里做什么

准备包含正文、表格、扫描页、流程图和UI截图的脱敏PRD，人工标注正确内容，然后评测：

- 正文和表格是否提取完整；
- OCR文字是否正确；
- 流程节点和分支关系是否正确；
- UI操作和状态变化是否正确；
- 关键问题是否被召回；
- 是否提出过多无价值问题；
- 解析耗时和视觉模型调用次数。

没有这些数据，不能声称“支持所有PDF图片”或“显著提高理解准确率”。

### 42.6 面试问题与参考答案

**问题1：为什么不直接把整个PDF交给多模态模型？**

参考答案：整份长文档会增加时长、Token和不稳定性。第一版先提取文本和表格，只对流程图、状态图和UI原型等信息密集图片调用视觉模型，并限制数量、尺寸和输出预算。

**问题2：图片识别错误如何避免污染需求事实？**

参考答案：每个结果保留页码、图片ID、解析方式和置信度。高置信度且有正文印证的内容才进入事实；中置信度进入风险，低置信度核心内容集中询问用户。

**问题3：为什么图文解析是测试开发项目的亮点？**

参考答案：真实PRD的流程和交互不只存在于文字中。项目不仅调用LLM生成测试点，还对输入完整性、解析来源、低置信度降级和关键问题数量建立了可测试边界。

### 42.7 掌握检查

- [ ] 能说明当前PDF和DOCX解析的真实边界
- [ ] 能区分OCR与流程/UI图理解
- [ ] 能解释为什么图文解析必须早于ContextBuilder
- [ ] 能说明哪些不确定项需要人工确认，哪些不应打扰用户
- [ ] 能说明图文解析需要哪些离线评测指标

## 四十三、阶段2.14.5：为什么失败重试需要request_id和补偿

### 43.1 这次解决了什么

以前索引失败后，MySQL会留下`index_failed`，但系统没有一个受控入口说明“谁发起了哪次重试、是否执行过、结果是什么”。
现在每次重试都携带`request_id`并保存审计记录。

```text
index_failed资产
→ request_id创建running记录
→ 资产切回pending_index
→ Embedding和Milvus upsert
→ succeeded或failed
```

### 43.2 request_id和asset_id有什么区别

- `asset_id`标识哪一份知识资产；
- `request_id`标识用户或系统发起的某一次重试动作。

同一资产可以先后发生多次重试，因此可能对应多个`request_id`。同一个`request_id`只能属于一份资产，
重复提交成功请求时只返回原结果，不会重复访问外部服务。

### 43.3 为什么失败后必须换request_id

如果失败请求可以直接再次执行，就无法分辨这是网络重放、用户重复点击，还是一次真正的新尝试。
当前规则是：失败记录保持不变，新尝试使用新`request_id`。这样每一次尝试都有独立、可追踪的结果。

### 43.4 为什么MySQL和Milvus不能一起回滚

它们是两个独立系统，没有共享事务。项目不假装能够做到跨库原子提交，而是：

1. 用MySQL状态作为权威判断；
2. 用稳定Chunk ID让Milvus upsert可以安全重放；
3. 用请求审计记录失败；
4. 用显式重试或清理完成补偿。

这叫可补偿一致性，不等于Exactly Once。

### 43.5 为什么停用时先改MySQL

如果先删除Milvus、再修改MySQL，而MySQL更新失败，资产仍被视为`indexed`，但暂时搜不到。反过来先标记
`retired`，即使删除向量失败，检索回查MySQL时也会拒绝它，不会让过期规则继续污染新任务。

### 43.6 两张相关表分别保存什么

| 表 | 保存内容 | 作用 |
|---|---|---|
| `knowledge_assets` | 完整知识资产JSON、状态、版本、哈希和摘要 | 权威业务内容 |
| `knowledge_asset_index_requests` | 每次重试的请求ID、状态、错误和时间 | 幂等与补偿审计 |

Milvus仍只保存向量、短检索文本和关联元数据，不替代这两张MySQL表。

### 43.7 代码阅读顺序

1. `knowledge_assets/indexing.py`：请求状态和审计对象。
2. `repositories/knowledge_asset_repository.py`：内存事务语义。
3. `repositories/mysql_knowledge_asset_repository.py`：行锁、状态更新和审计插入。
4. `application/knowledge_asset_indexing_service.py`：重试、重放和停用用例。
5. `services/milvus_asset_index.py`：定向删除向量。

### 43.8 面试问题与参考答案

**问题1：如何防止用户重复点击导致重复索引？**

参考答案：每次动作携带request_id并持久化。相同request_id成功后再次提交只返回已保存结果；运行中返回忙；失败后要求新request_id。Milvus使用稳定Chunk ID upsert，提供第二层重复保护。

**问题2：MySQL成功但Milvus失败怎么办？**

参考答案：资产回到index_failed并保存失败审计，之后使用新request_id显式重试。MySQL是权威状态，未indexed的资产不会被可信检索。

**问题3：停用资产时向量删除失败会不会继续被召回？**

参考答案：Milvus可能暂时仍命中，但检索服务会批量回查MySQL并拒绝retired资产，因此不会进入最终可信上下文。向量删除可稍后重试。

### 43.9 掌握检查

- [ ] 能区分asset_id与request_id
- [ ] 能解释为什么同一失败请求不能直接重复执行
- [ ] 能说明稳定Chunk ID如何配合upsert
- [ ] 能说明为什么停用时先写MySQL
- [ ] 能准确说明本阶段没有后台自动补偿和页面入口

## 四十四、阶段2.15.1：为什么文档不能只用一个字符串

### 44.1 原来的问题

旧解析器最终只返回：

```python
"需求标题\n业务说明\n退款规则..."
```

这段文字无法回答：

- 某条规则来自第几页；
- 原文是标题、列表还是表格单元格；
- 图片位于哪个位置；
- 哪一页没有文本层；
- 哪些内容解析失败或尚未处理。

所以字符串适合发给当前LLM，却不适合作为图文PRD的长期内部模型。

### 44.2 DocumentContent是什么

`DocumentContent`相当于一份文档解析结果对象：

```text
DocumentContent
├── document_id
├── filename / document_format
├── extracted_text（兼容旧流程）
├── elements（结构化元素）
└── warnings（解析警告）
```

它和Java里的DTO或领域值对象类似，由多个明确类型组合而成，不用一个随意的字典传递全部字段。

### 44.3 三种元素

1. `DocumentTextElement`：标题、段落或列表项；
2. `DocumentTableElement`：不可变的二维表格；
3. `DocumentImageElement`：图片ID、MIME、内容引用、尺寸和说明。

每个元素都携带`DocumentSourceRef`，因此后续OCR、视觉理解和测试点来源可以回到具体文件、页码和元素。

### 44.4 为什么本阶段没有直接解析表格和图片

数据模型和解析算法是两个不同问题：

```text
2.15.1：先定义结果应该长什么样
2.15.2：再让PDF/DOCX解析器产生这些结果
2.15.3：OCR补充扫描文字
2.15.4：视觉模型理解流程和UI关系
```

如果同时开发，出现错误时很难判断是模型设计、文件提取还是视觉理解的问题。

### 44.5 为什么仍然保留extracted_text

当前AgentState和Prompt都接收字符串。`to_plain_text()`让现有页面与Agent继续运行，结构化元素则为后续能力
提供入口。这是一种兼容迁移，不是两套互相独立的业务逻辑。

### 44.6 稳定来源ID有什么用

相同文件重复解析会得到相同`document_id`和元素`source_id`。以后可以用于：

- 测试点标注“来源于第3页元素5”；
- 去重OCR与正文重复内容；
- 评测某个表格或图片是否被正确识别；
- 文档重新解析后比较元素变化。

### 44.7 代码阅读顺序

1. `documents/models.py`：看文档、元素、来源和警告模型。
2. `services/document_service.py`：看一次读取后如何按格式解析。
3. `utils/file_parser.py`：看旧字符串接口如何兼容。
4. `application/service.py`：确认当前页面仍只使用兼容文本视图。
5. `tests/unit/services/test_document_service.py`：看页码和警告如何验证。

### 44.8 面试问题与参考答案

**问题1：为什么不继续把PDF直接解析成字符串？**

参考答案：字符串会丢失元素类型、顺序、页码和解析警告，无法支撑OCR、多模态理解、来源追踪和离线评测。因此先建立DocumentContent，同时保留纯文本兼容视图，分阶段迁移现有Agent。

**问题2：为什么表格和图片模型已经存在，但当前还不能说支持图文PRD？**

参考答案：模型只定义结果结构，当前解析器还没有真正提取DOCX表格、PDF图片、扫描文字和流程关系。检测到DOCX表格或图片时只产生警告，不能把规划能力描述为已实现。

**问题3：稳定source_id解决了什么？**

参考答案：它让每条解析结果都有可复现来源，后续测试点、OCR结果和视觉结论可以引用具体元素，也能用于去重、差异比较和解析评测。

### 44.9 掌握检查

- [ ] 能画出DocumentContent和三类元素的关系
- [ ] 能解释extracted_text为什么是兼容视图
- [ ] 能说明DocumentSourceRef保存哪些信息
- [ ] 能区分“模型能表达图片”和“系统已经理解图片”
- [ ] 能准确说明2.15.2才开始提取PDF/DOCX原生结构

## 四十五、阶段2.15.2：原生文档结构是怎样被提取的

### 45.1 这一阶段解决了什么

2.15.1只是定义了“文档解析结果长什么样”，2.15.2才真正把DOCX表格、DOCX图片、PDF表格和
PDF内嵌图片填入这些模型。它仍然不是OCR，也没有让大模型理解流程图。

### 45.2 为什么图片元素和附件要分开

`DocumentImageElement`描述图片位于文档的什么位置，`DocumentAttachment`保存真正的二进制：

```text
图片元素：来源、顺序、页码、说明、content_ref
附件：attachment_id、MIME、bytes、SHA-256
```

这样同一张图片可以被稳定引用，后续OCR或视觉模型也能拿到真实内容，而不是依赖临时文件路径。

### 45.3 为什么PDF同时使用pdfplumber和pypdf

- `pdfplumber`更适合从页面布局中提取文字和可识别表格；
- `pypdf`继续用于读取PDF对象中的内嵌位图；
- 两者都不能保证理解矢量流程图的业务含义，所以矢量图只产生整页渲染警告。

这叫职责分离，不是为了增加依赖数量。每个库只负责它更稳定的部分。

### 45.4 为什么要限制图片大小和数量

长PRD可能包含几十张大图。如果没有边界，一次解析会大量占用内存。当前限制为：

- 单张最多5MB；
- 最多20个图片元素；
- 附件总量最多25MB。

超过限制不会静默丢失，而是记录结构化警告和跳过数量。后续可以在评测数据支持下再调整阈值。

### 45.5 当前Agent实际能用到什么

当前Agent仍接收`to_plain_text()`：正文和DOCX表格文字已经可用；图片虽然被提取成真实附件，但尚未经过
OCR或视觉理解，因此图片里的文字和流程关系还不会进入需求事实。

### 45.6 代码阅读顺序

1. `documents/models.py`：先看Attachment、Stats和ImageElement如何关联；
2. `services/document_service.py::_parse_docx`：看正文块顺序和图片提取；
3. `services/document_service.py::_parse_pdf`：看页、表格、位图和警告；
4. `services/document_service.py::_append_image`：看资源上限与哈希；
5. `tests/unit/services/test_document_service.py`：看真实DOCX与失败边界证据。

### 45.7 面试问题与参考答案

**问题1：为什么不把图片直接Base64塞进DocumentImageElement？**

参考答案：元素主要表达顺序和来源，大二进制单独作为附件可以减少重复、保持模型清晰，也方便后续独立
持久化或送入OCR。元素通过稳定ID关联附件即可。

**问题2：PDF里检测到图片，为什么仍不能说已经理解图文PRD？**

参考答案：提取二进制只证明拿到了图片，不等于识别了图片文字或理解了流程关系。扫描文字属于OCR，
流程图和UI关系属于视觉语义理解，必须分别实现和评测。

**问题3：为什么失败后要继续解析，而不是让整个任务失败？**

参考答案：一份PRD中某张图片或某页表格失败，不应丢掉其他可用正文。系统保留成功结果，同时通过警告和
覆盖统计暴露缺口，让后续降级或人工判断有证据。

### 45.8 动手练习

1. 找出DOCX表格是如何进入兼容纯文本的；
2. 说明PDF矢量图为什么只记录`PAGE_RENDER_REQUIRED`；
3. 修改测试中的图片大小，观察超限警告和`skipped_image_count`；
4. 画出ImageElement、Attachment、SourceRef三者关系。

### 45.9 掌握检查

- [ ] 能解释结构提取、OCR和视觉理解的区别
- [ ] 能解释为什么图片元素不直接保存重复二进制
- [ ] 能说出三个图片资源边界
- [ ] 能说明当前Agent已经能读到表格文字，但还不能理解图片

## 四十六、阶段2.15.3：OCR为什么要有置信度和降级边界

### 46.1 OCR和视觉理解不是一回事

OCR回答“图片里写了什么字”，视觉理解回答“节点、箭头、页面元素和操作之间是什么关系”。因此本阶段只
处理文字，不让OCR承担流程图理解职责。

### 46.2 为什么定义OcrEngine协议

DocumentService不应该写死Tesseract、云OCR或某一家模型。它只依赖：

```python
recognize(image_bytes, mime_type) -> tuple[OcrTextLine, ...]
```

当前Tesseract只是一个适配器。将来切换引擎时，扫描页渲染、来源追踪、置信度分流和失败隔离都可以复用。

### 46.3 低置信度为什么不能直接进入需求事实

例如图片实际写“退款上限500元”，OCR误识别为“退款上限5000元”。如果直接拼进Prompt，LLM可能基于
错误数字生成测试点。本阶段把置信度低于0.80的结果标成`REVIEW_REQUIRED`，保留证据但不进入兼容文本。

阈值0.80只是初始工程配置，后续必须通过脱敏样本评测再调整，不能宣称它天然最优。

### 46.4 扫描PDF如何处理

```text
页面没有文本层
→ 以150 DPI渲染为PNG
→ 保存为DocumentImageElement和Attachment
→ OCR
→ 保存DocumentOcrElement、置信度、页码和图片ID
```

有文本层的PDF不会整页重复OCR，只对其中的内嵌图片执行OCR，减少重复文字和额外耗时。

### 46.5 为什么单图失败不能让任务失败

一份PRD可能有20页正文和1张损坏图片。如果因为图片失败而丢弃全部正文，代价太大。当前处理方式是：

- 记录`OCR_FAILED`或`OCR_UNAVAILABLE`；
- 增加失败统计；
- 继续处理其他页面和图片；
- 最终让调用方知道文档内容并不完整。

### 46.6 Tesseract适配器做了什么

适配器通过子进程读取TSV，而不只读取一个大字符串。TSV可以提供每个词的置信度，代码再按行组合并将
0～100转换为0～1。外部程序不存在、超时或返回失败时，适配器抛出明确异常，由DocumentService降级。

### 46.7 代码阅读顺序

1. `services/ocr_service.py`：协议、Tesseract调用和TSV解析；
2. `documents/models.py`：OCR元素、处置状态和统计；
3. `services/document_service.py::_append_ocr_elements`：置信度分流；
4. `services/document_service.py::_parse_pdf`：扫描页渲染；
5. `tests/unit/services/test_ocr_service.py`：适配器边界；
6. `tests/unit/services/test_document_service.py`：完整文档链路。

### 46.8 面试问题与参考答案

**问题1：为什么不用LLM直接识别所有图片？**

参考答案：纯文字图片优先使用OCR成本更低、结果更容易获得字符级置信度；只有OCR无法表达的流程和UI关系
才进入有界多模态调用，避免不必要的耗时和Token。

**问题2：Fake OCR测试通过，能否说明真实中文OCR效果很好？**

参考答案：不能。Fake只证明编排、来源、置信度和失败边界正确；真实精度必须用安装好的OCR运行时和脱敏
扫描样本测量，项目当前明确记录这项证据尚缺失。

**问题3：为什么高置信度OCR文本还要标记来源？**

参考答案：置信度高不等于绝对正确。来源标识让Reviewer、人工用户和离线评测可以追溯到具体图片和页码，
也方便后续重新识别或替换引擎。

### 46.9 动手练习

1. 阅读`_parse_tsv`，说明多个词如何组合成一行；
2. 把Fake置信度从0.79改为0.80，观察处置状态变化；
3. 让Fake OCR第一张图抛异常，确认第二张图仍被处理；
4. 安装Tesseract和中文语言数据后，用一份脱敏扫描页做冒烟验证并记录耗时。

### 46.10 掌握检查

- [ ] 能区分OCR、文档结构提取和多模态理解
- [ ] 能解释为什么低置信度文本不能直接成为事实
- [ ] 能说明OcrEngine协议带来的替换能力
- [ ] 能准确区分Fake链路证据和真实OCR效果证据

### 46.11 真实OCR验收记录

本机使用Tesseract 5.5.3和`chi_sim+eng`完成了两层验证：

1. OCR适配器直接识别两行合成中文，置信度约0.95和0.92，耗时约0.30秒；
2. 中文图片嵌入DOCX后通过DocumentService完整解析，产生1个图片元素、1个OCR元素、0个失败警告。

Windows路径最初写成`"D:\Tesseract-OCR-5\tesseract.exe"`时，python-dotenv把`\t`解释成制表符，
导致`shutil.which()`找不到程序。改用`D:/Tesseract-OCR-5/tesseract.exe`后恢复正常。这个问题说明环境配置
也需要真实集成测试，Mock无法发现路径转义错误。

仓库新增了默认跳过的真实集成测试，只有设置`RUN_OCR_INTEGRATION_TESTS=1`才调用本机Tesseract。
单份合成样本只证明运行链路可用，不能证明面对真实PRD时已经达到某个准确率。

## 47. 阶段2.15.4：有界多模态理解

### 47.1 为什么OCR之后还需要视觉模型

OCR回答“图片上写了什么字”，但不知道箭头从哪里指向哪里，也不知道按钮点击后页面或状态如何变化。
视觉模型用于补充流程节点、分支关系、UI元素、用户操作和状态变化。

### 47.2 为什么不能把所有图片都发给模型

PRD中常有Logo、图标、二维码和纯文字截图。全部发送会增加等待时间、Token费用和敏感数据暴露范围。
本阶段先使用相邻正文、图片名、尺寸和OCR信号筛选候选，每份文档最多调用5张。

### 47.3 新增代码边界

```text
DocumentService
→ 本地候选筛选
→ VisualUnderstandingEngine协议
→ OpenAI兼容适配器或测试Fake
→ DocumentVisualElement
```

`DocumentVisualElement`保存图片ID、类型、摘要、置信度、节点、关系、UI元素、状态变化和不确定性。
关系必须引用已经存在的节点，避免模型返回一条无法落到具体节点的悬空连线。

### 47.4 安全与降级

- 未配置视觉端点：记录`VISION_UNAVAILABLE`，正文和OCR继续；
- 单张失败：记录`VISION_FAILED`，其他图片继续；
- 超过5张：记录`VISION_LIMIT_EXCEEDED`；
- 置信度低于0.70：结构化保留，但不进入当前需求文本；
- 未知字段、错误类型和非法关系：拒绝该模型响应。

### 47.5 面试问题与参考答案

问题：为什么候选筛选不用另一个LLM？

参考答案：如果为了判断是否调用视觉模型先调用一次LLM，仍然会增加外部请求和时延。本阶段使用本地
确定性信号做低成本前置筛选，真实漏识别率在离线评测后再决定是否需要升级分类器。

问题：当前可以说项目已经支持图文PRD理解了吗？

参考答案：只能说建立了有界多模态调用和结构化结果边界，并有Fake测试证明控制逻辑。尚无真实视觉模型
和脱敏PRD评测数据，不能声称图文理解准确率已经达标。

### 47.6 动手练习

1. 把测试中的“流程图”改为普通“规则说明”，观察视觉Fake不再被调用；
2. 构造6张UI原型，解释为什么只调用5次；
3. 将Fake置信度改为0.69，确认结果不进入兼容文本；
4. 给关系设置一个不存在的目标节点，确认结构化校验拒绝。

### 47.7 掌握检查

- [ ] 能区分OCR和视觉理解的职责
- [ ] 能解释候选筛选、调用限额和图片压缩的意义
- [ ] 能说明低置信度结果为什么不能直接成为事实
- [ ] 能准确说明当前只有Fake证据，没有真实视觉效果结论

## 48. 阶段2.15.5：关键问题限流

### 48.1 原来的问题

原来`open_questions`只是字符串数组。Python只检查数量不超过3个，无法阻止模型把数据库、缓存、按钮颜色
等细节放进数组。一旦数组非空，State就进入`WAITING_FOR_USER`。

### 48.2 现在的数据结构

每个候选包含：

```json
{
  "question": "库存不足时是否允许创建订单？",
  "category": "core_rule",
  "blocking_reason": "不确认就无法判断创建订单是否正确",
  "evidence": "需求只描述了库存充足分支"
}
```

类别让Python可以执行稳定白名单，阻塞原因和需求依据则用于校验、追踪和后续评测。

### 48.3 策略如何工作

- `core_rule`、`critical_value`、`flow_branch`、`requirement_conflict`有资格阻塞；
- `implementation_detail`和`low_impact`转为风险；
- 明显的数据库、缓存、技术栈、按钮颜色等问题即使被模型误分类，也由本地规则降级；
- 最多保留3个阻塞问题；
- 重复问题和用户已选择暂不确定的问题不会再次出现。

### 48.4 和等待时间的关系

本阶段没有减少一次LLM请求自身的耗时，但减少了用户回答低价值问题后重新分析带来的额外轮次。后续
ContextBuilder与Token预算才会直接减少长输入和模型生成时间。

### 48.5 面试问题

问题：为什么不完全相信LLM决定是否暂停？

参考答案：暂停会改变任务状态并打断用户，属于高影响控制权。LLM适合提出语义候选，Python负责类别白名单、
数量上限、明显技术问题、去重和重复消费保护，使Human-in-the-loop保持可控。

问题：当前策略有什么不足？

参考答案：类别仍由LLM生成，本地关键词只能兜底明显错误；当前去重不是语义去重。需要通过离线标注集统计
关键问题召回率和不必要提问数量，再决定是否增加更复杂分类器。

### 48.6 动手练习

1. 将数据库问题故意标成`core_rule`，确认仍转为风险；
2. 构造4个阻塞候选，确认只有前3个暂停；
3. 给同一个问题增加不同标点，确认只保留一次；
4. 把问题放入`deferred_questions`，确认重新分析后不会再问。
