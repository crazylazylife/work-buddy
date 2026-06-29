const state = { ledger: null, connectors: null };

const subtitles = {
  inbox: "Paste messy work context and turn it into tracked work.",
  tasks: "Review reconciled tasks with owners, deadlines, and evidence.",
  approvals: "Draft external updates and enforce human-in-the-loop approval.",
  prs: "Create GitHub-ready PR drafts without opening live PRs.",
  connectors: "Check optional live connector configuration.",
  memory: "Inspect durable project memory and recent audit events.",
};

function $(id) {
  return document.getElementById(id);
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${body}`);
  }
  return response.json();
}

function switchView(name) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${name}`);
  });
  $("view-title").textContent = name[0].toUpperCase() + name.slice(1);
  $("view-subtitle").textContent = subtitles[name];
}

function renderTasks() {
  const tasks = state.ledger?.tasks || [];
  $("tasks-list").innerHTML = tasks.length
    ? tasks
        .map(
          (task) => `
          <article class="item">
            <h4>${task.id}: ${task.summary}</h4>
            <div class="meta">
              <span class="pill">${task.status}</span>
              <span>owner: ${task.owner}</span>
              <span>deadline: ${task.deadline}</span>
              <span>evidence: ${(task.source_evidence || []).length}</span>
            </div>
          </article>`
        )
        .join("")
    : '<p class="status">No tasks yet. Process a source from Inbox.</p>';
}

function renderApprovals() {
  const approvals = state.ledger?.approvals || [];
  $("approvals-list").innerHTML = approvals.length
    ? approvals
        .map(
          (approval) => `
          <article class="item">
            <h4>${approval.id}: ${approval.action_type}</h4>
            <div class="meta">
              <span class="pill ${approval.status === "approved" ? "good" : "warn"}">${approval.status}</span>
              <span>${approval.target_system}</span>
              <span>risk: ${approval.risk_level}</span>
            </div>
            <pre>${pretty(approval.payload_preview)}</pre>
            <div class="actions">
              <button data-approve="${approval.id}">Approve</button>
              <button class="secondary" data-reject="${approval.id}">Reject</button>
              <button class="secondary" data-execute="${approval.id}">Execute</button>
            </div>
          </article>`
        )
        .join("")
    : '<p class="status">No approval requests yet.</p>';

  document.querySelectorAll("[data-approve]").forEach((button) => {
    button.addEventListener("click", () => decide(button.dataset.approve, "approved"));
  });
  document.querySelectorAll("[data-reject]").forEach((button) => {
    button.addEventListener("click", () => decide(button.dataset.reject, "rejected"));
  });
  document.querySelectorAll("[data-execute]").forEach((button) => {
    button.addEventListener("click", () => execute(button.dataset.execute));
  });
}

function renderPrs() {
  const prs = state.ledger?.prs || [];
  $("prs-list").innerHTML = prs.length
    ? prs
        .map(
          (pr) => `
          <article class="item">
            <h4>${pr.id}: ${pr.title}</h4>
            <div class="meta">
              <span class="pill">${pr.status}</span>
              <span>${pr.branch_name}</span>
              <span>${pr.task_id}</span>
            </div>
            <pre>${pr.body}</pre>
          </article>`
        )
        .join("")
    : '<p class="status">No PR drafts yet.</p>';
}

function renderConnectors() {
  const connectors = state.connectors || {};
  $("connectors-list").innerHTML = Object.entries(connectors)
    .map(
      ([name, info]) => `
      <article class="item">
        <h4>${name}</h4>
        <span class="pill ${info.configured ? "good" : "danger"}">
          ${info.configured ? "configured" : "missing"}
        </span>
        ${info.missing ? `<p class="status">${info.missing}</p>` : ""}
      </article>`
    )
    .join("");
}

function renderMemory() {
  $("memory-view").textContent = state.ledger?.memory || "No memory yet.";
  const events = state.ledger?.events || [];
  $("events-list").innerHTML = events.length
    ? events
        .map(
          (event) => `
          <article class="item">
            <h4>${event.id}: ${event.event_type}</h4>
            <div class="meta"><span>${event.created_at}</span></div>
            <pre>${pretty(event.payload)}</pre>
          </article>`
        )
        .join("")
    : '<p class="status">No events yet.</p>';
}

async function refresh() {
  state.ledger = await request("/api/ledger");
  state.connectors = await request("/api/connectors");
  renderTasks();
  renderApprovals();
  renderPrs();
  renderConnectors();
  renderMemory();
}

async function processSource() {
  $("process-status").textContent = "Processing...";
  try {
    const result = await request("/api/ingest", {
      method: "POST",
      body: JSON.stringify({
        source_type: $("source-type").value,
        metadata_json: $("metadata-json").value,
        content: $("source-content").value,
      }),
    });
    $("latest-result").textContent = pretty(result);
    $("process-status").textContent = "Processed";
    await refresh();
  } catch (error) {
    $("process-status").textContent = error.message;
  }
}

async function createDraft() {
  const type = $("draft-type").value;
  const target = $("draft-target").value;
  const message = $("draft-message").value;
  let path = "/api/drafts/slack";
  let payload = { channel: target, message };
  if (type === "jira") {
    path = "/api/drafts/jira";
    payload = { issue_key: target, update_text: message };
  }
  if (type === "email") {
    path = "/api/drafts/email";
    payload = { recipient: target, subject: $("draft-subject").value, body: message };
  }
  const result = await request(path, { method: "POST", body: JSON.stringify(payload) });
  $("latest-result").textContent = pretty(result);
  await refresh();
}

async function createPr() {
  const result = await request("/api/pr-drafts", {
    method: "POST",
    body: JSON.stringify({ task_id: $("pr-task-id").value, repo_path: $("repo-path").value }),
  });
  $("latest-result").textContent = pretty(result);
  await refresh();
}

async function inspectRepo() {
  const result = await request(`/api/repo?repo_path=${encodeURIComponent($("repo-path").value)}`);
  $("latest-result").textContent = pretty(result);
}

async function decide(id, decision) {
  const result = await request(`/api/approvals/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      approved_by: "dashboard-user",
      human_confirmation:
        decision === "approved" ? "I approve this external action" : "rejected",
    }),
  });
  $("latest-result").textContent = pretty(result);
  await refresh();
}

async function execute(id) {
  const result = await request(`/api/approvals/${id}/execute`, { method: "POST" });
  $("latest-result").textContent = pretty(result);
  await refresh();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});
$("refresh").addEventListener("click", refresh);
$("process-source").addEventListener("click", processSource);
$("create-draft").addEventListener("click", createDraft);
$("create-pr").addEventListener("click", createPr);
$("inspect-repo").addEventListener("click", inspectRepo);

refresh();
