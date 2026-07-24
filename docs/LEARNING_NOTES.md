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
- [ ] 能读懂现有 96 个单元测试
- [ ] 能独立增加一个状态字段、事件或测试

---

## 二、项目整体认识

### 2.1 项目解决什么问题

测试工程师需要阅读 PRD、识别业务规则、设计正常/边界/异常场景，还要复用历史 Bug 经验。人工处理耗时且容易遗漏。项目使用 LLM 分析需求，通过 RAG 检索历史测试资产，生成测试分析报告，并逐步加入 Agent 的状态、执行轨迹、质量评审和自动修正能力。

### 2.2 30 秒项目介绍参考答案

> 我实现了一个面向测试工程师的智能测试分析助手。用户可以输入或上传 PRD，系统解析文档后，通过 Milvus 检索相似的历史测试资产，再结合本地 Bug 经验构造 Prompt，调用 DeepSeek 流式生成测试分析报告。为了从固定 Workflow 演进为 Agent，我把 LLM、RAG、Prompt 和文档解析拆成独立 Service，并加入 AgentState 和执行事件，为后续需求分析、工具调用、Reviewer 和自动修正循环做准备。

### 2.3 当前真实执行链路

```text
用户输入文本或上传PRD
  → views/tab_test_points.py
  → DocumentService（上传文件时）
  → TestAssistantManager
      → RAGService.search()
          → MilvusRAGManager
          → Embedding服务
          → Milvus相似度检索
      → PromptService
          → 读取System Prompt
          → 构建User Prompt
      → LLMService.generate_stream()
          → DeepSeekClient.call_stream()
          → DeepSeek Chat Completions API
  → Streamlit逐段展示结果
  → 用户修改或确认
  → 确认后保存到Milvus
```

### 2.4 当前还没有实现什么

以下能力暂时不能写成“已经实现”：

- Agent 自主选择工具
- RequirementAnalyzer 结构化需求分析节点
- Reviewer 自动质量评审
- 自动反思与修正循环
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
- `tests/test_test_manager.py`

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
- `tests/test_prompt_service.py`

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
- `tests/test_agent_state.py`

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

> 不能。单元测试只验证本地模块行为，还需要集成测试、真实模型效果评测、异常网络测试、安全测试和用户验收。当前 96 个测试证明的是代码边界和状态规则，不代表生成质量已经达到生产标准。

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
3. 阅读 `tests/test_agent_state.py`

目标：能说明状态、步骤、事件和合法转换。

### 第三轮：理解测试

1. 阅读三个 `tests/test_*.py`
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
- `tests/test_requirement_analyzer.py`

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

### 18.4 为什么返回完整集合而不是增量补丁

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

代价是Prompt更长，但当前阶段更容易保证数据契约一致。

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

阶段2.10：Streamlit接入
  展示结构化结果、输入人工意见、最终确认和保存
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
