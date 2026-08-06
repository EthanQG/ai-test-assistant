# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以
[PRD_AGENT_V2.md](product/PRD_AGENT_V2.md)为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md)为准，
完整历史见[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 图文PRD路线图校正：`ec633e7 文档：调整图文PRD理解开发路线`
- 阶段2.14.5：`5ecd956 阶段2.14.5：完善知识资产索引重试与补偿`
- 阶段2.15.1代码、测试与文档已完成，提交见最新Git记录

## 当前阶段：2.15.1 统一DocumentContent

本阶段建立文档解析的结构化输入契约，不修改Streamlit布局、AgentState、Orchestrator、Prompt和
节点顺序。主要完成：

1. 新增独立`documents/`模型包，不依赖页面、LLM、OCR或数据库；
2. `DocumentContent`保存稳定文档ID、文件名、格式、兼容纯文本、有序元素和解析警告；
3. 文本元素区分标题、普通段落和列表项；
4. 表格模型使用不可变二维行列，图片模型保存图片ID、MIME类型、内容引用、尺寸和说明；
5. 每个元素保存稳定`source_id`、文档ID、文件名、元素顺序和可选页码；
6. TXT按段落建模，Markdown识别标题、列表和段落；
7. PDF文本层按页提取并保留页码，空白页产生显式警告；
8. DOCX保留段落顺序和标题/列表类型，检测到表格或内嵌图片时明确记录尚未提取警告；
9. `DocumentService.parse()`返回结构化模型，原`extract_text()`继续返回原来的字符串视图；
10. 当前Application Service和Streamlit无需修改，上传创建任务的行为保持不变。

## 当前数据流

```text
上传TXT/MD/PDF/DOCX
→ DocumentService一次读取文件
→ 生成稳定document_id
→ 解析为有序DocumentElement和DocumentSourceRef
→ 保存页码与DocumentParsingWarning
→ DocumentContent
   ├─ to_plain_text()供当前Agent兼容使用
   └─ elements/warnings供2.15.2以后结构化解析使用
```

`extracted_text`暂时与结构化元素并存，是为了冻结当前页面和Agent行为；后续节点不能把它误认为已经
包含表格、扫描页和图片中的全部信息。

## 验证结果

```text
python -m pytest -q
363 passed，9 skipped，共收集372项

python -m unittest discover -s tests -v
266 tests，OK，6 skipped
```

针对性测试还验证了现有Streamlit上传流程。默认测试没有访问真实DeepSeek、Ollama、Milvus、MySQL、
OCR或视觉模型。

## 当前限制

- 当前AgentState仍保存纯文本需求，尚未直接保存`DocumentContent`
- DOCX表格和图片只检测并告警，尚未提取为真实元素
- PDF目前只读取文本层；扫描页、PDF图片和复杂版面尚未处理
- 没有OCR、图片分类、流程图/UI图理解和置信度
- 解析警告尚未进入页面和Agent事件
- `DocumentContent`本阶段没有单独持久化到MySQL快照

## 下一步：阶段2.15.2 PDF/DOCX结构化解析

下一阶段只补充原生结构提取：

1. DOCX标题、段落、列表、表格和内嵌图片按原始顺序输出；
2. PDF保留页码、文本块和可识别表格，并为图片或整页渲染保留引用；
3. 记录元素数量、未提取数量和失败警告，不静默丢失；
4. 不在2.15.2接入OCR或多模态模型；
5. 保持当前页面和Agent纯文本兼容路径可运行。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
