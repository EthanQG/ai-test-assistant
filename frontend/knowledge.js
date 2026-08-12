const elements = {
  query: document.querySelector("#asset-query"),
  status: document.querySelector("#asset-status"),
  search: document.querySelector("#search-assets"),
  list: document.querySelector("#asset-list"),
  total: document.querySelector("#asset-total"),
  previous: document.querySelector("#previous-assets"),
  next: document.querySelector("#next-assets"),
  page: document.querySelector("#asset-page-label"),
  empty: document.querySelector("#knowledge-empty"),
  detail: document.querySelector("#knowledge-detail"),
  error: document.querySelector("#knowledge-error"),
  title: document.querySelector("#asset-title"),
  detailStatus: document.querySelector("#asset-detail-status"),
  score: document.querySelector("#asset-score"),
  count: document.querySelector("#asset-test-point-count"),
  version: document.querySelector("#asset-version"),
  confirmedAt: document.querySelector("#asset-confirmed-at"),
  requirement: document.querySelector("#asset-requirement"),
  testPoints: document.querySelector("#asset-test-points"),
  report: document.querySelector("#asset-report"),
};

const pageSize = 10;
let offset = 0;
let activeAssetId = null;

elements.search.addEventListener("click", () => { offset = 0; loadAssets(); });
elements.status.addEventListener("change", () => { offset = 0; loadAssets(); });
elements.query.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { offset = 0; loadAssets(); }
});
elements.previous.addEventListener("click", () => { offset -= pageSize; loadAssets(); });
elements.next.addEventListener("click", () => { offset += pageSize; loadAssets(); });

async function loadAssets() {
  const params = new URLSearchParams({
    query: elements.query.value.trim(), offset: String(offset), limit: String(pageSize),
  });
  if (elements.status.value) params.set("status", elements.status.value);
  try {
    const page = await request(`/api/v1/knowledge-assets?${params}`);
    renderList(page);
  } catch (error) { showError(error.message); }
}

function renderList(page) {
  elements.list.replaceChildren();
  elements.total.textContent = `${page.total} 项`;
  const pageNumber = Math.floor(page.offset / page.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(page.total / page.limit));
  elements.page.textContent = `第 ${pageNumber} / ${totalPages} 页`;
  elements.previous.disabled = page.offset === 0;
  elements.next.disabled = page.offset + page.items.length >= page.total;
  if (!page.items.length) appendEmpty(elements.list, "没有找到知识资产。");
  page.items.forEach((asset) => elements.list.append(assetItem(asset)));
}

function assetItem(asset) {
  const button = document.createElement("button");
  button.className = "knowledge-asset-item";
  if (asset.asset_id === activeAssetId) button.classList.add("active");
  const title = document.createElement("strong");
  title.textContent = asset.requirement_summary;
  const meta = document.createElement("span");
  meta.textContent = `${statusLabel(asset.status)} · ${asset.test_point_count}个测试点 · ${asset.reviewer_score}分`;
  button.append(title, meta);
  button.addEventListener("click", () => loadDetail(asset.asset_id));
  return button;
}

async function loadDetail(assetId) {
  try {
    const asset = await request(`/api/v1/knowledge-assets/${assetId}`);
    activeAssetId = assetId;
    elements.empty.hidden = true;
    elements.detail.hidden = false;
    elements.error.hidden = true;
    elements.title.textContent = asset.requirement_summary;
    elements.detailStatus.textContent = statusLabel(asset.status);
    elements.detailStatus.className = `status ${asset.status === "indexed" ? "completed" : "neutral"}`;
    elements.score.textContent = `${asset.reviewer_score}/100`;
    elements.count.textContent = asset.test_point_count;
    elements.version.textContent = `V${asset.asset_version}`;
    elements.confirmedAt.textContent = new Date(asset.confirmed_at).toLocaleString("zh-CN");
    renderRequirement(asset.structured_requirement);
    renderTestPoints(asset.test_points || []);
    elements.report.textContent = asset.final_report || "暂无最终报告";
    await loadAssets();
  } catch (error) { showError(error.message); }
}

function renderRequirement(requirement) {
  const groups = [
    ["涉及模块", requirement.modules], ["需求事实", requirement.requirement_facts],
    ["业务规则", requirement.business_rules], ["状态流转", requirement.state_transitions],
  ];
  elements.requirement.replaceChildren(...groups.map(([title, values]) => listSection(title, values)));
}

function renderTestPoints(points) {
  elements.testPoints.replaceChildren(...points.map((point, index) => {
    const item = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${index + 1}. ${point.title} · ${categoryLabel(point.category)} · ${point.priority}`;
    const content = document.createElement("div");
    content.className = "knowledge-test-point-detail";
    content.append(
      listSection("前置条件", point.preconditions),
      listSection("执行步骤", point.steps),
      listSection("预期结果", point.expected_results),
    );
    item.append(summary, content);
    return item;
  }));
}

function listSection(title, values = []) {
  const section = document.createElement("section");
  const heading = document.createElement("h4");
  const list = document.createElement("ul");
  heading.textContent = title;
  (values || []).forEach((value) => {
    const item = document.createElement("li");
    item.textContent = typeof value === "string" ? value : JSON.stringify(value);
    list.append(item);
  });
  if (!list.children.length) list.append(Object.assign(document.createElement("li"), { textContent: "无" }));
  section.append(heading, list);
  return section;
}

function appendEmpty(target, message) {
  const paragraph = document.createElement("p");
  paragraph.className = "muted";
  paragraph.textContent = message;
  target.append(paragraph);
}

function statusLabel(status) {
  return { indexed: "已索引", pending_index: "待索引", index_failed: "索引失败", retired: "已停用" }[status] || status;
}

function categoryLabel(category) {
  return { functional: "功能", boundary: "边界", exception: "异常", non_functional: "非功能" }[category] || category;
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

async function request(url) {
  const response = await fetch(url);
  if (response.ok) return response.json();
  let detail = `请求失败（${response.status}）`;
  try { detail = (await response.json()).detail || detail; } catch (_) { /* 默认错误 */ }
  throw new Error(detail);
}

loadAssets();
