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
};

let currentTaskId = null;
let pollTimer = null;

elements.document.addEventListener("change", () => {
  elements.fileName.textContent = elements.document.files[0]?.name || "尚未选择文件";
});
elements.start.addEventListener("click", startAnalysis);
elements.reset.addEventListener("click", resetWorkspace);

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
    renderProgress(progress);
    if (["completed", "failed", "waiting_for_user"].includes(progress.status)) {
      setBusy(false);
      return;
    }
    pollTimer = window.setTimeout(pollProgress, 1500);
  } catch (error) {
    showError(error.message);
    setBusy(false);
  }
}

function renderProgress(progress) {
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
  elements.requirement.readOnly = busy;
  elements.document.disabled = busy;
  elements.start.textContent = busy ? "Agent执行中…" : "开始分析";
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
  setBusy(false);
  clearMessages();
}
