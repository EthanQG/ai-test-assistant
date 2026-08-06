# Test Analysis Agent 当前开发状态

更新时间：2026-08-06

本文档只保存最新接力信息。产品范围以 [PRD_AGENT_V2.md](product/PRD_AGENT_V2.md) 为准，后续阶段以
[AUTUMN_RECRUITMENT_ROADMAP.md](roadmap/AUTUMN_RECRUITMENT_ROADMAP.md) 为准，完整历史见
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## Git基线

- 分支：`main`
- 阶段2.15.1：`785f42e 阶段2.15.1：建立统一文档内容模型`
- 阶段2.15.2代码、测试和文档已完成，尚未创建本阶段提交

## 当前阶段：2.15.2 PDF与DOCX结构化解析

本阶段在`DocumentContent`契约上补齐原生文档结构提取，没有修改Streamlit、AgentState、
Orchestrator、Prompt和节点顺序：

1. DOCX按正文块顺序提取标题、段落、列表和表格；
2. DOCX内嵌图片提取为真实二进制`DocumentAttachment`，图片元素通过稳定引用关联附件；
3. PDF按页提取文本、可识别表格和内嵌位图，并保留页码；
4. PDF矢量图输出`PAGE_RENDER_REQUIRED`，为后续整页渲染和视觉理解保留边界；
5. 单图最大5MB、最多20个图片元素、附件总量最大25MB，超限时输出警告而非无限占用内存；
6. `DocumentParseStats`记录页数、文本/表格/图片数量、警告和跳过数量；
7. 表格被加入兼容纯文本视图，当前Agent无需修改即可读取DOCX表格文字；
8. `DocumentService.extract_text()`兼容入口继续可用，页面调用链不变。

## 当前数据流

```text
上传TXT/MD/PDF/DOCX
→ DocumentService一次读取文件并生成稳定document_id
→ PDF/DOCX原生结构提取
→ DocumentContent
   ├─ elements：文本、表格、图片及来源
   ├─ attachments：带哈希的真实图片二进制
   ├─ warnings/stats：失败与覆盖统计
   └─ to_plain_text()：供当前Agent兼容使用
```

## 验证结果

```text
python -m pytest -q
367 passed，9 skipped，共收集376项
python -m unittest discover -s tests -v
269 tests，OK，6 skipped
```

跳过项均为需要显式环境开关的真实MySQL集成测试。默认测试没有访问真实DeepSeek、Ollama、
Milvus、MySQL、OCR或视觉模型。`compileall`、`git diff --check`和`pip check`均已通过。

## 当前限制

- 当前AgentState仍保存兼容纯文本，没有直接持有`DocumentContent`
- PDF文字块顺序和表格识别受PDF内部排版质量影响
- PDF矢量图、组合图仅产生整页渲染提示，本阶段不理解图形语义
- 扫描PDF和图片文字尚未OCR
- DOCX图片已提取，但尚未分类或理解流程图、UI图语义
- 解析警告和统计尚未进入页面、Agent事件或MySQL任务快照
- 图片附件当前只存在于本次解析结果内，尚未设计持久化

## 下一步：阶段2.15.3 OCR与扫描文档

下一阶段只处理扫描文档和图片文字：

1. 为扫描PDF、页面截图和文档图片增加OCR边界；
2. 保存OCR置信度、页码、图片ID和来源；
3. 低置信度文字只能作为风险或待确认候选，不能直接成为需求事实；
4. 单张图片失败不导致整份文档失败；
5. 不在2.15.3实现流程图或UI图语义理解。

## 新电脑恢复方式

```powershell
git pull --ff-only origin main
pip install -r requirements-dev.txt
git status -sb
git log -5 --oneline --decorate
python -m pytest
```

然后让Codex按照`AGENTS.md`初始化上下文，并读取本文档和路线图。
