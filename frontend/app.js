const elements = {
  requirement: document.querySelector("#requirement"),
  document: document.querySelector("#document"),
  fileName: document.querySelector("#file-name"),
  start: document.querySelector("#start-button"),
  reset: document.querySelector("#reset-button"),
  formError: document.querySelector("#form-error"),
  status: document.querySelector("#status-badge"),
  activity: document.querySelector("#activity"),
  stage: document.querySelector("#stage-label"),
  description: document.querySelector("#stage-description"),
  testPoints: document.querySelector("#test-point-count"),
  reviewerScore: document.querySelector("#reviewer-score"),
  revisions: document.querySelector("#revision-count"),
  events: document.querySelector("#recent-events"),
  taskMessage: document.querySelector("#task-message"),
  taskId: document.querySelector("#task-id"),
  clarificationSection: document.querySelector("#clarification-section"),
  clarificationList: document.querySelector("#clarification-list"),
  clarificationButton: document.querySelector("#clarification-button"),
  businessRuleSection: document.querySelector("#business-rule-section"),
  businessRuleContent: document.querySelector("#business-rule-content"),
  confirmBusinessRule: document.querySelector("#confirm-business-rule"),
  rejectBusinessRule: document.querySelector("#reject-business-rule"),
  flowSteps: [...document.querySelectorAll("#agent-flow span")],
  testPointSection: document.querySelector("#test-point-section"),
  testPointList: document.querySelector("#test-point-list"),
  pageLabel: document.querySelector("#page-label"),
  previousPage: document.querySelector("#previous-page"),
  nextPage: document.querySelector("#next-page"),
  detailDialog: document.querySelector("#test-point-dialog"),
  detailTitle: document.querySelector("#detail-title"),
  detailContent: document.querySelector("#detail-content"),
  closeDialog: document.querySelector("#close-dialog"),
  resultNavigation: document.querySelector("#result-navigation"),
  resultTabs: [...document.querySelectorAll(".result-tab")],
  qualitySection: document.querySelector("#quality-section"),
  qualityScore: document.querySelector("#quality-score"),
  qualityDimensions: document.querySelector("#quality-dimensions"),
  qualityFindings: document.querySelector("#quality-findings"),
  reportSection: document.querySelector("#report-section"),
  reportPreview: document.querySelector("#report-preview"),
  downloadReport: document.querySelector("#download-report"),
  feedbackSection: document.querySelector("#feedback-section"),
  feedbackForm: document.querySelector("#feedback-form"),
  feedbackType: document.querySelector("#feedback-type"),
  feedbackAction: document.querySelector("#feedback-action"),
  feedbackTargetLabel: document.querySelector("#feedback-target-label"),
  feedbackTarget: document.querySelector("#feedback-target"),
  feedbackContentLabel: document.querySelector("#feedback-content-label"),
  feedbackContent: document.querySelector("#feedback-content"),
  feedbackPriorityLabel: document.querySelector("#feedback-priority-label"),
  feedbackPriority: document.querySelector("#feedback-priority"),
  feedbackReason: document.querySelector("#feedback-reason"),
  feedbackMessage: document.querySelector("#feedback-message"),
  feedbackHistory: document.querySelector("#feedback-history"),
  knowledgePublish: document.querySelector("#knowledge-publish"),
  dataSafetyConfirmed: document.querySelector("#data-safety-confirmed"),
  publishKnowledge: document.querySelector("#publish-knowledge"),
  knowledgeMessage: document.querySelector("#knowledge-message"),
  historyButton: document.querySelector("#history-button"),
  historyDialog: document.querySelector("#history-dialog"),
  closeHistoryDialog: document.querySelector("#close-history-dialog"),
  historyQuery: document.querySelector("#history-query"),
  searchHistory: document.querySelector("#search-history"),
  historyList: document.querySelector("#history-list"),
  previousHistoryPage: document.querySelector("#previous-history-page"),
  nextHistoryPage: document.querySelector("#next-history-page"),
  historyPageLabel: document.querySelector("#history-page-label"),
};

let currentTaskId = null;
let pollTimer = null;
let testPoints = [];
let currentPage = 1;
let testPointVersion = "";
let activeResultTab = "test-points";
let reportMarkdown = "";
let businessRules = [];
let humanFeedback = [];
let pendingBusinessFeedback = null;
let currentTaskStatus = null;
const pageSize = 5;
const historyPageSize = 10;
let historyOffset = 0;

elements.document.addEventListener("change", () => {
  elements.fileName.textContent = elements.document.files[0]?.name || "尚未选择文件";
});
elements.start.addEventListener("click", startAnalysis);
elements.reset.addEventListener("click", resetWorkspace);
elements.clarificationButton.addEventListener("click", submitClarifications);
elements.previousPage.addEventListener("click", () => changePage(-1));
elements.nextPage.addEventListener("click", () => changePage(1));
elements.closeDialog.addEventListener("click", () => elements.detailDialog.close());
elements.resultTabs.forEach((tab) => {
  tab.addEventListener("click", () => showResultTab(tab.dataset.resultTab));
});
elements.downloadReport.addEventListener("click", downloadReport);
elements.feedbackType.addEventListener("change", renderFeedbackOptions);
elements.feedbackAction.addEventListener("change", renderFeedbackTarget);
elements.feedbackForm.addEventListener("submit", submitFeedback);
elements.confirmBusinessRule.addEventListener("click", () => confirmBusinessRule(true));
elements.rejectBusinessRule.addEventListener("click", () => confirmBusinessRule(false));
elements.publishKnowledge.addEventListener("click", publishKnowledgeAsset);
elements.historyButton.addEventListener("click", openHistory);
elements.closeHistoryDialog.addEventListener("click", () => elements.historyDialog.close());
elements.searchHistory.addEventListener("click", () => { historyOffset = 0; loadHistory(); });
elements.historyQuery.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { historyOffset = 0; loadHistory(); }
});
elements.previousHistoryPage.addEventListener("click", () => changeHistoryPage(-1));
elements.nextHistoryPage.addEventListener("click", () => changeHistoryPage(1));

async function openHistory() {
  historyOffset = 0;
  elements.historyDialog.showModal();
  await loadHistory();
}

async function loadHistory() {
  const query = encodeURIComponent(elements.historyQuery.value.trim());
  try {
    const page = await request(
      `/api/v1/task-summaries?query=${query}&offset=${historyOffset}&limit=${historyPageSize}`,
    );
    renderHistory(page);
  } catch (error) {
    elements.historyList.replaceChildren();
    appendEmpty(elements.historyList, error.message);
  }
}

function renderHistory(page) {
  elements.historyList.replaceChildren();
  if (!page.items.length) appendEmpty(elements.historyList, "没有找到历史任务。");
  page.items.forEach((summary) => elements.historyList.append(historyItem(summary)));
  const current = Math.floor(page.offset / page.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(page.total / page.limit));
  elements.historyPageLabel.textContent = `第 ${current} / ${totalPages} 页`;
  elements.previousHistoryPage.disabled = page.offset === 0;
  elements.nextHistoryPage.disabled = page.offset + page.items.length >= page.total;
}

function historyItem(summary) {
  const item = document.createElement("article");
  item.className = "history-item";
  const header = document.createElement("header");
  const title = document.createElement("h3");
  title.textContent = summary.requirement_summary || "未命名需求";
  const status = document.createElement("span");
  status.className = `status ${statusClass(summary.status)}`;
  status.textContent = statusLabel(summary.status);
  const meta = document.createElement("div");
  meta.className = "history-meta";
  meta.textContent = `更新：${new Date(summary.updated_at).toLocaleString()} · 事件 ${summary.event_count}`;
  const id = document.createElement("p");
  id.textContent = `任务ID：${summary.task_id}`;
  const button = document.createElement("button");
  button.className = "button secondary";
  button.type = "button";
  button.textContent = "恢复任务";
  button.addEventListener("click", () => restoreTask(summary.task_id));
  header.append(title, status);
  item.append(header, meta, id, button);
  return item;
}

function changeHistoryPage(direction) {
  historyOffset = Math.max(0, historyOffset + direction * historyPageSize);
  loadHistory();
}

async function restoreTask(taskId) {
  clearMessages();
  if (pollTimer) window.clearTimeout(pollTimer);
  pollTimer = null;
  try {
    const task = await request(`/api/v1/tasks/${taskId}`);
    currentTaskId = taskId;
    elements.requirement.value = task.state.requirement || "";
    elements.taskId.textContent = `任务ID：${taskId}`;
    lockTaskInput(true);
    testPointVersion = "";
    await loadResults();
    const progress = await request(`/api/v1/tasks/${taskId}/progress`);
    await renderProgress(progress);
    elements.historyDialog.close();
    if (progress.status === "waiting_for_user") {
      setBusy(false);
      lockTaskInput(true);
      elements.start.disabled = true;
      await loadWaitingAction();
    } else if (["queued", "running"].includes(progress.execution_status)) {
      setBusy(true);
      await pollProgress();
    } else {
      setBusy(false);
      lockTaskInput(true);
    }
  } catch (error) {
    showError(error.message);
  }
}

function statusLabel(status) {
  return {
    running: "执行中", waiting_for_user: "等待用户",
    completed: "已完成", failed: "执行失败",
  }[status] || "等待开始";
}

async function startAnalysis() {
  clearMessages();
  const file = elements.document.files[0];
  const requirement = elements.requirement.value.trim();
  if (!file && !requirement) {
    showError("请输入需求文本或选择一份PRD文档。");
    return;
  }

  setBusy(true);
  try {
    const task = file ? await createFromFile(file) : await createFromText(requirement);
    currentTaskId = task.state.task_id;
    elements.taskId.textContent = `任务ID：${currentTaskId}`;
    await request(`/api/v1/tasks/${currentTaskId}/run`, { method: "POST" });
    await pollProgress();
  } catch (error) {
    showError(error.message);
    setBusy(false);
  }
}

async function createFromText(requirement) {
  return request("/api/v1/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
}

async function createFromFile(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/v1/tasks/from-document", { method: "POST", body: form });
}

async function pollProgress() {
  if (!currentTaskId) return;
  try {
    const progress = await request(`/api/v1/tasks/${currentTaskId}/progress`);
    await renderProgress(progress);
    if (
      progress.status === "waiting_for_user"
      && !["queued", "running"].includes(progress.execution_status)
    ) {
      setBusy(false);
      lockTaskInput(true);
      elements.start.disabled = true;
      elements.start.textContent = "等待补充信息";
      await loadWaitingAction();
      return;
    }
    if (["completed", "failed"].includes(progress.status)) {
      setBusy(false);
      return;
    }
    pollTimer = window.setTimeout(pollProgress, 1500);
  } catch (error) {
    showError(error.message);
    setBusy(false);
  }
}

async function renderProgress(progress) {
  currentTaskStatus = progress.status;
  const running = ["queued", "running"].includes(progress.execution_status);
  elements.status.textContent = progress.status_label;
  elements.status.className = `status ${statusClass(progress.status)}`;
  elements.activity.hidden = !running;
  elements.stage.textContent = progress.stage_label;
  elements.description.textContent = progress.error || stageDescription(progress);
  elements.testPoints.textContent = progress.test_point_count;
  elements.reviewerScore.textContent = progress.reviewer_score ?? "待评审";
  elements.revisions.textContent = progress.automatic_revision_count;
  elements.events.replaceChildren(...progress.recent_events.map(eventItem));
  renderFlow(progress.current_step, progress.status);
  const resultVersion = [
    progress.test_point_count, progress.automatic_revision_count,
    progress.human_revision_count, progress.status,
  ].join(":");
  if (progress.test_point_count > 0 && testPointVersion !== resultVersion) {
    await loadResults();
    testPointVersion = resultVersion;
  }

  if (progress.waiting_for_clarifications) {
    showNotice("补充信息已提交，任务等待重新启动。");
  } else if (progress.status === "waiting_for_user") {
    showNotice("Agent已暂停，请在左侧完成需求补充或业务规则确认。");
  } else if (progress.status === "completed") {
    showNotice("分析已完成，可以查看测试点、质量评审、人工反馈和最终报告。");
  } else if (progress.status === "failed") {
    showNotice("任务执行失败，请查看上方错误信息后重新创建任务。");
  }
  renderKnowledgePublish();
}

async function loadResults() {
  const task = await request(`/api/v1/tasks/${currentTaskId}`);
  testPoints = task.state.test_points || [];
  reportMarkdown = task.state.report || "";
  businessRules = task.state.business_rules || [];
  humanFeedback = task.state.human_feedback || [];
  currentPage = 1;
  renderTestPoints();
  renderQuality(task.state.review_result);
  renderReport();
  renderFeedback();
  elements.resultNavigation.hidden = !(
    testPoints.length || task.state.review_result || reportMarkdown
  );
  showResultTab(activeResultTab);
}

function showResultTab(name) {
  activeResultTab = name;
  elements.resultTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.resultTab === name);
  });
  elements.testPointSection.hidden = name !== "test-points" || testPoints.length === 0;
  elements.qualitySection.hidden = name !== "quality";
  elements.feedbackSection.hidden = name !== "feedback";
  elements.reportSection.hidden = name !== "report";
}

function renderFeedback() {
  renderFeedbackOptions();
  elements.feedbackHistory.replaceChildren();
  if (!humanFeedback.length) {
    appendEmpty(elements.feedbackHistory, "当前尚未提交人工反馈。");
    return;
  }
  humanFeedback.forEach((feedback) => {
    const item = document.createElement("article");
    item.className = "feedback-item";
    const title = document.createElement("strong");
    title.textContent = `${feedbackTypeLabel(feedback.feedback_type)} · ${actionLabel(feedback.action)}`;
    const content = document.createElement("p");
    content.textContent = `${feedback.target}：${feedback.content}`;
    const status = document.createElement("span");
    status.textContent = feedbackStatusLabel(feedback.status);
    item.append(title, content, status);
    elements.feedbackHistory.append(item);
  });
}

function renderFeedbackOptions() {
  const type = elements.feedbackType.value;
  const actions = type === "test_suggestion"
    ? [["add", "新增"], ["modify", "修改"], ["remove", "删除"], ["update_priority", "调整优先级"]]
    : [["add", "新增"], ["modify", "修改"], ["remove", "删除"]];
  const selected = elements.feedbackAction.value;
  elements.feedbackAction.replaceChildren(...actions.map(([value, label]) => option(value, label)));
  if (actions.some(([value]) => value === selected)) elements.feedbackAction.value = selected;
  renderFeedbackTarget();
}

function renderFeedbackTarget() {
  const type = elements.feedbackType.value;
  const action = elements.feedbackAction.value;
  const targets = type === "test_suggestion"
    ? testPoints.map((point) => point.title).filter(Boolean)
    : businessRules;
  const isAdd = action === "add";
  elements.feedbackTargetLabel.hidden = isAdd;
  elements.feedbackTarget.replaceChildren(...targets.map((value) => option(value, value)));
  elements.feedbackContentLabel.hidden = action === "remove" || action === "update_priority";
  elements.feedbackPriorityLabel.hidden = action !== "update_priority";
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

async function submitFeedback(event) {
  event.preventDefault();
  clearMessages();
  const type = elements.feedbackType.value;
  const action = elements.feedbackAction.value;
  const targets = type === "test_suggestion" ? testPoints : businessRules;
  let target = action === "add"
    ? (type === "test_suggestion" ? "新增测试点" : "新增业务规则")
    : elements.feedbackTarget.value;
  let content = elements.feedbackContent.value.trim();
  if (action === "remove") content = `删除：${target}`;
  if (action === "update_priority") {
    content = `将测试点优先级调整为 ${elements.feedbackPriority.value}`;
  }
  const reason = elements.feedbackReason.value.trim();
  if ((!target && action !== "add") || !targets || !content || !reason) {
    showFeedbackMessage("请填写完整的反馈目标、内容和原因。", true);
    return;
  }
  activeResultTab = "feedback";
  elements.feedbackForm.querySelector("button").disabled = true;
  try {
    const task = await request(`/api/v1/tasks/${currentTaskId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, feedback_type: type, target, content, reason }),
    });
    humanFeedback = task.state.human_feedback || [];
    businessRules = task.state.business_rules || [];
    renderFeedback();
    elements.feedbackForm.reset();
    renderFeedbackOptions();
    if (type === "business_rule") {
      pendingBusinessFeedback = humanFeedback.find((item) => item.status === "pending_confirmation");
      renderBusinessRuleConfirmation();
      lockTaskInput(true);
      elements.start.disabled = true;
      elements.start.textContent = "等待规则确认";
      showFeedbackMessage("业务规则已记录，请在左侧确认后继续。", false);
      return;
    }
    showFeedbackMessage("反馈已接收，Agent正在修正并重新评审。", false);
    await request(`/api/v1/tasks/${currentTaskId}/run`, { method: "POST" });
    setBusy(true);
    await pollProgress();
  } catch (error) {
    showFeedbackMessage(error.message, true);
  } finally {
    elements.feedbackForm.querySelector("button").disabled = false;
  }
}

function showFeedbackMessage(message, error) {
  elements.feedbackMessage.textContent = message;
  elements.feedbackMessage.className = `message ${error ? "error" : "notice"}`;
  elements.feedbackMessage.hidden = false;
}

async function loadWaitingAction() {
  const task = await request(`/api/v1/tasks/${currentTaskId}`);
  humanFeedback = task.state.human_feedback || [];
  pendingBusinessFeedback = humanFeedback.find((item) => item.status === "pending_confirmation") || null;
  if (pendingBusinessFeedback) {
    elements.clarificationSection.hidden = true;
    renderBusinessRuleConfirmation();
  } else {
    elements.businessRuleSection.hidden = true;
    renderClarifications(task.state.open_questions || []);
  }
}

function renderBusinessRuleConfirmation() {
  if (!pendingBusinessFeedback) {
    elements.businessRuleSection.hidden = true;
    return;
  }
  const lines = [
    `操作：${actionLabel(pendingBusinessFeedback.action)}`,
    `目标：${pendingBusinessFeedback.target}`,
    `规则：${pendingBusinessFeedback.content}`,
    `依据：${pendingBusinessFeedback.reason}`,
  ];
  elements.businessRuleContent.replaceChildren(...lines.map((line) => {
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    return paragraph;
  }));
  elements.businessRuleSection.hidden = false;
}

async function confirmBusinessRule(confirmed) {
  if (!pendingBusinessFeedback) return;
  elements.confirmBusinessRule.disabled = true;
  elements.rejectBusinessRule.disabled = true;
  try {
    await request(`/api/v1/tasks/${currentTaskId}/business-rules/confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback_id: pendingBusinessFeedback.feedback_id, confirmed }),
    });
    pendingBusinessFeedback = null;
    elements.businessRuleSection.hidden = true;
    await request(`/api/v1/tasks/${currentTaskId}/run`, { method: "POST" });
    setBusy(true);
    await pollProgress();
  } catch (error) {
    showError(error.message);
  } finally {
    elements.confirmBusinessRule.disabled = false;
    elements.rejectBusinessRule.disabled = false;
  }
}

function feedbackTypeLabel(value) {
  return value === "business_rule" ? "业务规则" : "测试建议";
}

function actionLabel(value) {
  return { add: "新增", modify: "修改", remove: "删除", update_priority: "调整优先级" }[value] || value;
}

function feedbackStatusLabel(value) {
  return { pending_confirmation: "待确认", ready: "待执行", applied: "已应用", rejected: "已取消" }[value] || value;
}

function renderQuality(review) {
  elements.qualityScore.textContent = review ? `${review.overall_score}/100` : "待评审";
  elements.qualityDimensions.replaceChildren();
  elements.qualityFindings.replaceChildren();
  if (!review) {
    appendEmpty(elements.qualityFindings, "当前尚未产生 Reviewer 结果。");
    return;
  }
  const dimensions = [
    ["需求覆盖", "requirement_coverage"], ["边界异常", "boundary_exception"],
    ["可执行性", "executability"], ["可追踪性", "traceability"],
  ];
  dimensions.forEach(([label, key]) => {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    term.textContent = label;
    value.textContent = review.dimension_scores?.[key] ?? "-";
    wrapper.append(term, value);
    elements.qualityDimensions.append(wrapper);
  });
  appendFinding("缺失或关注场景", review.missing_scenarios);
  appendFinding("无依据断言风险", (review.hallucination_issues || []).map(
    (item) => item.issue || item.unsupported_claim,
  ));
  appendFinding("Reviewer 建议", review.revision_suggestions);
  if (!elements.qualityFindings.children.length) {
    appendEmpty(elements.qualityFindings, "本轮评审未发现需要额外展示的问题。");
  }
}

function appendFinding(title, items = []) {
  if (!items.length) return;
  const section = document.createElement("section");
  const heading = document.createElement("h4");
  const list = document.createElement("ul");
  heading.textContent = title;
  items.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    list.append(item);
  });
  section.append(heading, list);
  elements.qualityFindings.append(section);
}

function appendEmpty(target, message) {
  const empty = document.createElement("p");
  empty.className = "muted";
  empty.textContent = message;
  target.append(empty);
}

function renderReport() {
  elements.reportPreview.textContent = reportMarkdown || "任务完成后将在这里生成 Markdown 报告。";
  elements.downloadReport.disabled = !reportMarkdown;
  renderKnowledgePublish();
}

function renderKnowledgePublish() {
  elements.knowledgePublish.hidden = !(
    currentTaskStatus === "completed" && reportMarkdown
  );
}

async function publishKnowledgeAsset() {
  if (!currentTaskId || currentTaskStatus !== "completed") return;
  if (!elements.dataSafetyConfirmed.checked) {
    elements.knowledgeMessage.textContent = "请先确认内容已脱敏且允许沉淀。";
    elements.knowledgeMessage.hidden = false;
    return;
  }
  elements.publishKnowledge.disabled = true;
  elements.publishKnowledge.textContent = "正在保存并建立索引…";
  elements.knowledgeMessage.hidden = true;
  try {
    const result = await request(
      `/api/v1/tasks/${currentTaskId}/knowledge-assets`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_confirmed: true,
          data_safety_confirmed: true,
        }),
      },
    );
    elements.knowledgeMessage.textContent =
      `已保存到知识库，共建立 ${result.chunk_count} 个检索片段。`;
    elements.knowledgeMessage.hidden = false;
    elements.publishKnowledge.textContent = "已保存到知识库";
  } catch (error) {
    elements.knowledgeMessage.textContent = error.message;
    elements.knowledgeMessage.hidden = false;
    elements.publishKnowledge.disabled = false;
    elements.publishKnowledge.textContent = "保存到知识库";
  }
}

function downloadReport() {
  if (!reportMarkdown) return;
  const url = URL.createObjectURL(new Blob([reportMarkdown], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `测试分析报告-${currentTaskId || "task"}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function renderTestPoints() {
  const totalPages = Math.max(1, Math.ceil(testPoints.length / pageSize));
  currentPage = Math.min(currentPage, totalPages);
  const start = (currentPage - 1) * pageSize;
  const visible = testPoints.slice(start, start + pageSize);
  elements.testPointList.replaceChildren(...visible.map(testPointCard));
  elements.pageLabel.textContent = `第 ${currentPage} / ${totalPages} 页`;
  elements.previousPage.disabled = currentPage === 1;
  elements.nextPage.disabled = currentPage === totalPages;
  elements.testPointSection.hidden = testPoints.length === 0;
}

function testPointCard(point, index) {
  const card = document.createElement("article");
  card.className = "test-point-card";
  const heading = document.createElement("div");
  const title = document.createElement("h4");
  title.textContent = `${(currentPage - 1) * pageSize + index + 1}. ${point.title || "未命名测试点"}`;
  const meta = document.createElement("p");
  meta.className = "test-point-meta";
  meta.textContent = `${categoryLabel(point.category)} · ${point.priority || "-"}`;
  const scenario = document.createElement("p");
  scenario.className = "test-point-scenario";
  scenario.textContent = point.scenario || "暂无场景摘要";
  const button = document.createElement("button");
  button.className = "button secondary detail-button";
  button.type = "button";
  button.textContent = "查看详情";
  button.addEventListener("click", () => openTestPoint(point));
  heading.append(title, meta);
  card.append(heading, scenario, button);
  return card;
}

function changePage(offset) {
  currentPage += offset;
  renderTestPoints();
}

function openTestPoint(point) {
  elements.detailTitle.textContent = point.title || "未命名测试点";
  const sections = [
    ["前置条件", point.preconditions], ["执行步骤", point.steps],
    ["预期结果", point.expected_results], ["来源", point.sources],
  ];
  elements.detailContent.replaceChildren(...sections.map(detailSection));
  elements.detailDialog.showModal();
}

function detailSection([title, values]) {
  const section = document.createElement("section");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("ol");
  (values || []).forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  });
  if (!list.children.length) list.append(Object.assign(document.createElement("li"), { textContent: "无" }));
  section.append(heading, list);
  return section;
}

function categoryLabel(category) {
  return { functional: "功能", boundary: "边界", exception: "异常", non_functional: "非功能" }[category] || category || "未分类";
}

async function loadClarifications() {
  const task = await request(`/api/v1/tasks/${currentTaskId}`);
  renderClarifications(task.state.open_questions || []);
}

function renderClarifications(questions) {
  elements.clarificationList.replaceChildren(...questions.map(questionField));
  elements.clarificationSection.hidden = questions.length === 0;
}

function questionField(question, index) {
  const wrapper = document.createElement("div");
  wrapper.className = "question-field";
  wrapper.dataset.question = question;

  const title = document.createElement("p");
  title.textContent = `${index + 1}. ${question}`;
  const answer = document.createElement("textarea");
  answer.rows = 2;
  answer.placeholder = "请输入产品或业务答案";
  const unknownLabel = document.createElement("label");
  unknownLabel.className = "unknown-option";
  const unknown = document.createElement("input");
  unknown.type = "checkbox";
  unknown.addEventListener("change", () => {
    answer.disabled = unknown.checked;
    if (unknown.checked) answer.value = "";
  });
  unknownLabel.append(unknown, " 暂不确定");
  wrapper.append(title, answer, unknownLabel);
  return wrapper;
}

async function submitClarifications() {
  clearMessages();
  const answers = {};
  for (const field of elements.clarificationList.children) {
    const answer = field.querySelector("textarea");
    const unknown = field.querySelector("input[type=checkbox]");
    if (!unknown.checked && !answer.value.trim()) {
      showError("请回答所有问题，或选择“暂不确定”。");
      return;
    }
    answers[field.dataset.question] = unknown.checked ? null : answer.value.trim();
  }
  setBusy(true);
  elements.clarificationButton.disabled = true;
  try {
    await request(`/api/v1/tasks/${currentTaskId}/clarifications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    elements.clarificationSection.hidden = true;
    await request(`/api/v1/tasks/${currentTaskId}/run`, { method: "POST" });
    await pollProgress();
  } catch (error) {
    showError(error.message);
    setBusy(false);
    lockTaskInput(true);
    elements.start.disabled = true;
    elements.start.textContent = "等待补充信息";
    elements.clarificationButton.disabled = false;
  }
}

function renderFlow(currentStep, status) {
  const stageByStep = {
    initialize: 0, analyze_requirement: 1, retrieve_knowledge: 2,
    generate_test_points: 3, review_test_points: 4,
    revise_test_points: 4, collect_human_feedback: 4, finalize: 5,
  };
  const current = stageByStep[currentStep] || 0;
  elements.flowSteps.forEach((step) => {
    const index = Number(step.dataset.stage);
    step.className = index < current || status === "completed" ? "done" : index === current ? "active" : "";
  });
}

function eventItem(event) {
  const item = document.createElement("li");
  item.textContent = event.message;
  return item;
}

function stageDescription(progress) {
  if (progress.execution_status === "running") return "Agent正在处理当前节点，请勿重复提交。";
  return "任务状态已更新。";
}

function statusClass(status) {
  return {
    running: "running",
    waiting_for_user: "waiting",
    completed: "completed",
    failed: "failed",
  }[status] || "neutral";
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (response.ok) return response.status === 204 ? null : response.json();
  let detail = `请求失败（${response.status}）`;
  try { detail = (await response.json()).detail || detail; } catch (_) { /* 使用默认错误 */ }
  throw new Error(detail);
}

function setBusy(busy) {
  elements.start.disabled = busy;
  lockTaskInput(busy);
  elements.start.textContent = busy ? "Agent执行中…" : "开始分析";
}

function lockTaskInput(locked) {
  elements.requirement.readOnly = locked;
  elements.document.disabled = locked;
}

function showError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = false;
}

function showNotice(message) {
  elements.taskMessage.textContent = message;
  elements.taskMessage.hidden = false;
}

function clearMessages() {
  elements.formError.hidden = true;
  elements.taskMessage.hidden = true;
}

function resetWorkspace() {
  if (pollTimer) window.clearTimeout(pollTimer);
  currentTaskId = null;
  currentTaskStatus = null;
  pollTimer = null;
  elements.requirement.value = "";
  elements.document.value = "";
  elements.fileName.textContent = "尚未选择文件";
  elements.taskId.textContent = "";
  elements.status.textContent = "等待开始";
  elements.status.className = "status neutral";
  elements.activity.hidden = true;
  elements.stage.textContent = "尚未创建任务";
  elements.description.textContent = "提交需求后，这里会持续展示Agent执行状态。";
  elements.testPoints.textContent = "0";
  elements.reviewerScore.textContent = "待评审";
  elements.revisions.textContent = "0";
  elements.events.innerHTML = "<li>等待提交需求</li>";
  elements.clarificationSection.hidden = true;
  elements.businessRuleSection.hidden = true;
  elements.clarificationList.replaceChildren();
  elements.clarificationButton.disabled = false;
  elements.flowSteps.forEach((step) => { step.className = ""; });
  testPoints = [];
  currentPage = 1;
  testPointVersion = "";
  activeResultTab = "test-points";
  reportMarkdown = "";
  businessRules = [];
  humanFeedback = [];
  pendingBusinessFeedback = null;
  elements.resultNavigation.hidden = true;
  elements.testPointSection.hidden = true;
  elements.qualitySection.hidden = true;
  elements.feedbackSection.hidden = true;
  elements.reportSection.hidden = true;
  elements.feedbackMessage.hidden = true;
  elements.knowledgePublish.hidden = true;
  elements.dataSafetyConfirmed.checked = false;
  elements.knowledgeMessage.hidden = true;
  elements.publishKnowledge.disabled = false;
  elements.publishKnowledge.textContent = "保存到知识库";
  elements.feedbackHistory.replaceChildren();
  elements.testPointList.replaceChildren();
  if (elements.detailDialog.open) elements.detailDialog.close();
  setBusy(false);
  clearMessages();
}
