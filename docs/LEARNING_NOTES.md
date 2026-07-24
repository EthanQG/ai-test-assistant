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
- [ ] 能读懂现有 16 个单元测试
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

> 不能。单元测试只验证本地模块行为，还需要集成测试、真实模型效果评测、异常网络测试、安全测试和用户验收。当前 16 个测试证明的是代码边界和状态规则，不代表生成质量已经达到生产标准。

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

目前已实现 State 和事件；Tool、循环限制和 Reviewer 仍是后续工作。

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
