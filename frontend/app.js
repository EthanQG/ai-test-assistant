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
};

let currentTaskId = null;
let pollTimer = null;
let testPoints = [];
let currentPage = 1;
let testPointVersion = "";
const pageSize = 5;

elements.document.addEventListener("change", () => {
  elements.fileName.textContent = elements.document.files[0]?.name || "尚未选择文件";
});
elements.start.addEventListener("click", startAnalysis);
elements.reset.addEventListener("click", resetWorkspace);
elements.clarificationButton.addEventListener("click", submitClarifications);
elements.previousPage.addEventListener("click", () => changePage(-1));
elements.nextPage.addEventListener("click", () => changePage(1));
elements.closeDialog.addEventListener("click", () => elements.detailDialog.close());

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
    if (progress.status === "waiting_for_user") {
      setBusy(false);
      lockTaskInput(true);
      elements.start.disabled = true;
      elements.start.textContent = "等待补充信息";
      await loadClarifications();
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
    await loadTestPoints();
    testPointVersion = resultVersion;
  }

  if (progress.waiting_for_clarifications) {
    showNotice("补充信息已提交，任务等待重新启动。");
  } else if (progress.status === "waiting_for_user") {
    showNotice("Agent需要补充信息。问答交互将在下一小阶段接入。");
  } else if (progress.status === "completed") {
    showNotice("分析已完成。测试点和报告展示将在后续小阶段接入。");
  } else if (progress.status === "failed") {
    showNotice("任务执行失败，请查看上方错误信息后重新创建任务。");
  }
}

async function loadTestPoints() {
  const task = await request(`/api/v1/tasks/${currentTaskId}`);
  testPoints = task.state.test_points || [];
  currentPage = 1;
  renderTestPoints();
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
  const questions = task.state.open_questions || [];
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
  elements.clarificationList.replaceChildren();
  elements.clarificationButton.disabled = false;
  elements.flowSteps.forEach((step) => { step.className = ""; });
  testPoints = [];
  currentPage = 1;
  testPointVersion = "";
  elements.testPointSection.hidden = true;
  elements.testPointList.replaceChildren();
  if (elements.detailDialog.open) elements.detailDialog.close();
  setBusy(false);
  clearMessages();
}
