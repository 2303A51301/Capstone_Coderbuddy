const $ = id => document.getElementById(id);
let activeRun = null;
let toastTimer;
let summaries = [];
let selectionVersion = 0;
let fileVersion = 0;
let submitting = false;
let refreshing = false;
let historySignature = "";

function stored(key, value) {
  try {
    if (value !== undefined) localStorage.setItem(key, value);
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function statusText(run) {
  if (run.mode === "recovered") return "Source recovered";
  if (run.status === "running") return ({
    planning: "Planning", building: "Building", testing: "Testing", repairing: "Repairing",
  })[run.phase] || "Working";
  if (run.status === "completed") return run.mode?.includes("fallback") || run.mode === "deterministic" ? "Starter ready" : "Checks passed";
  return ({ queued: "Queued", failed: "Failed", cancelled: "Cancelled" })[run.status] || run.status;
}

function stamp(value) {
  return new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function esc(value) {
  const node = document.createElement("span");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 4200);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) throw Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function setStatus(run) {
  const node = $("status");
  node.className = `run-status ${run.status}`;
  node.querySelector("span").textContent = statusText(run);
}

function renderPlan(plan = []) {
  $("plan").innerHTML = plan.map((step, index) => `
    <li class="${esc(step.status)}">
      <span class="step-dot">${step.status === "succeeded" ? "✓" : step.status === "failed" ? "!" : step.status === "running" ? "↻" : String(index + 1).padStart(2, "0")}</span>
      <div class="step-copy"><b>${esc(step.title)}</b><p>${esc(step.description)}</p></div>
    </li>`).join("");
}

function renderLogs(logs = []) {
  $("logs").innerHTML = logs.slice().reverse().map(event => `
    <article class="activity-item ${event.status === "failed" ? "failed" : ""}">
      <div><b>${esc(event.agent)}</b><span>${esc(String(event.action).replaceAll("_", " "))}</span></div>
      <p>${esc(event.detail)}</p>${event.tool ? `<code>${esc(event.tool)}</code>` : ""}
    </article>`).join("") || `<p class="muted">Workflow events will appear here as the build progresses.</p>`;
}

function renderFeatures(features = []) {
  $("feature-list").innerHTML = features.length
    ? features.map(feature => `<li>${esc(feature)}</li>`).join("")
    : "<li>Requirement analysis pending</li>";
}

function render(run) {
  if (activeRun?.id !== run.id) {
    fileVersion++;
    $("file-list").dataset.files = "";
    $("preview-frame").dataset.runId = "";
    $("preview-frame").removeAttribute("src");
    $("code-name").textContent = "Choose a file";
    $("code-content").textContent = "Source for this request will appear after generation.";
    $("code-lines").textContent = "1";
  }
  activeRun = run;
  $("current-project").textContent = run.requirement.split("\n")[0];
  document.body.classList.add("workspace-active");
  stored("coderbuddy.selectedBuild", run.id);
  $("welcome").hidden = true;
  $("dashboard").hidden = false;
  $("run-title").textContent = run.requirement.split("\n")[0].slice(0, 130);
  $("run-id").textContent = `#${run.id}`;
  $("run-analysis").textContent = run.analysis_summary || "Interpreting the requested app…";
  $("pane-project-name").textContent = run.project_type || "project";
  $("type").textContent = run.project_type || "Analyzing…";
  $("files").textContent = run.generated_files?.length || 0;
  $("retries").textContent = run.retries || 0;
  $("duration").textContent = run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : "Running";
  $("model-used").textContent = run.model_name ? `${run.provider_name || "Ollama"} · ${run.model_name}` : "OFFLINE STARTER";
  setStatus(run);
  $("sequence-label").textContent = `REQUEST #${run.sequence}`;
  $("saved-at").textContent = `Saved ${stamp(run.updated_at)}`;
  $("cancel-run").hidden = run.status !== "queued";
  $("retry-run").hidden = !["failed", "cancelled"].includes(run.status);
  renderRevisions();
  renderPlan(run.plan);
  renderLogs(run.logs);
  renderFeatures(run.features);

  $("validation").textContent = run.validation_output || run.error || "Running checks…";
  const badge = $("test-badge");
  badge.className = `test-badge ${run.status === "completed" ? "pass" : run.status === "failed" ? "fail" : "pending"}`;
  badge.textContent = run.status === "completed" ? "PASSED" : run.status === "cancelled" ? "NOT RUN" : run.status === "failed" ? "REVIEW" : run.status === "queued" ? "WAITING" : "RUNNING";
  $("validation-summary").textContent = run.status === "completed"
    ? "The recorded checks passed. Review output for coverage; passing checks do not prove every requested feature."
    : run.status === "cancelled" ? "Cancelled before execution. No checks were run."
    : run.status === "queued" ? "Waiting for earlier requests to finish."
    : run.status === "failed"
      ? (run.error || "Tests did not pass. Source is available for inspection.")
      : "The agent is building and executing checks. Follow its progress in Activity.";

  const fallback = run.mode?.includes("fallback");
  $("fallback-notice").hidden = !fallback;
  if (fallback) {
    $("fallback-notice").textContent = run.project_type === "ecommerce-store"
      ? "Naveen storefront generated in offline mode and validated with a working product catalog, filters, size-aware bag, and demo checkout. The exported Docker/Nginx bundle prepares static hosting; connect payments and order services before launch."
      : "Offline fallback delivered. The configured model was unavailable or could not repair the build; the starter may not implement every requirement-specific feature. Review the interpreted scope and validation results before presenting it as complete.";
  }

  $("download").href = `/api/runs/${encodeURIComponent(run.id)}/download`;
  const previewUrl = `/api/runs/${encodeURIComponent(run.id)}/preview`;
  const running = ["queued", "running"].includes(run.status);
  const downloadable = !running && Boolean(run.generated_files?.length);
  $("download").hidden = !downloadable;
  $("open-preview").href = running ? "#" : previewUrl;
  $("open-preview").setAttribute("aria-disabled", String(running));
  $("preview-address").textContent = `${run.project_type || "project"} / live preview`;
  const hasPreview = !running && (run.generated_files || []).includes("index.html");
  $("preview-state").textContent = hasPreview ? "STATIC PREVIEW" : running ? statusText(run).toUpperCase() : "NO PREVIEW";
  $("preview-state").classList.toggle("waiting", !hasPreview);
  $("refresh-preview").disabled = !hasPreview;
  $("preview-empty").hidden = hasPreview;
  $("preview-empty").querySelector("p").textContent = running ? "Updating your application…" : "Your running app will appear here";
  $("preview-empty").querySelector("small").textContent = running ? "Your code is being regenerated and tested." : "Generate a project to interact with its live preview.";
  $("preview-frame").hidden = !hasPreview;
  if (hasPreview && $("preview-frame").dataset.runId !== run.id) {
    $("preview-frame").dataset.runId = run.id;
    $("preview-frame").src = previewUrl;
  }

  $("refine").disabled = submitting || running || !hasPreview;
  renderFiles(running ? { ...run, generated_files: [] } : run);
}

async function renderFiles(run) {
  const files = (run.generated_files || []).filter(file => file !== "CODER_BUDDY_REQUEST.txt");
  const key = `${run.id}:${files.join("|")}`;
  if ($("file-list").dataset.files === key) return;
  $("file-list").dataset.files = key;
  if (!files.length) {
    $("file-list").innerHTML = `<p class="muted">Files appear after generation.</p>`;
    $("code-name").textContent = "Choose a file";
    $("code-content").textContent = "Generated source will be shown here.";
    $("code-lines").textContent = "1";
    return;
  }
  $("file-list").innerHTML = files.map((file, index) => `
    <button class="${index === 0 ? "selected" : ""}" data-file="${esc(file)}">
      <span class="file-icon">${file.endsWith(".py") ? "◆" : file.endsWith(".html") ? "◇" : file.endsWith(".css") ? "◈" : "⌘"}</span>${esc(file)}
    </button>`).join("");
  await openFile(run.id, files[0]);
}

async function openFile(runId, file) {
  const version = ++fileVersion;
  $("code-name").textContent = `Loading ${file}…`;
  try {
    const data = await api(`/api/runs/${encodeURIComponent(runId)}/file?path=${encodeURIComponent(file)}`);
    if (version !== fileVersion || activeRun?.id !== runId) return;
    $("code-name").textContent = data.path;
    highlight(data.content, data.path);
    $("code-lines").textContent = Array.from({ length: Math.max(1, data.content.split("\n").length) }, (_, index) => index + 1).join("\n");
    $("code-content").parentElement.scrollTop = 0;
    $("code-lines").scrollTop = 0;
    document.querySelectorAll(".file-list button").forEach(button => button.classList.toggle("selected", button.dataset.file === file));
  } catch (error) {
    if (version === fileVersion) {
      $("code-content").textContent = `Unable to load source: ${error.message}`;
      toast(error.message);
    }
  }
}

function highlight(content, path) {
  if (!/\.(js|py|html|css|json)$/.test(path)) {
    $("code-content").textContent = content;
    return;
  }
  const tokens = /<!--[\s\S]*?-->|\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|<\/?[\w-]+|\b(?:const|let|var|function|return|if|else|for|while|class|import|from|def|assert|True|False|None|true|false|null|async|await|try|except|raise|export|new)\b|\b\d+(?:\.\d+)?\b/g;
  let html = "", cursor = 0;
  for (const match of content.matchAll(tokens)) {
    html += esc(content.slice(cursor, match.index));
    const token = match[0];
    const kind = /^(<!--|\/\*|\/\/)/.test(token) ? "comment"
      : /^["']/.test(token) ? "string" : /^</.test(token) ? "tag"
      : /^\d/.test(token) ? "number" : "keyword";
    html += `<span class="syntax-${kind}">${esc(token)}</span>`;
    cursor = match.index + token.length;
  }
  $("code-content").innerHTML = html + esc(content.slice(cursor));
}

function requestToken(action, text) {
  const key = "coderbuddy.pendingSubmission";
  let prior;
  try { prior = JSON.parse(stored(key) || "null"); } catch { prior = null; }
  if (prior?.action === action && prior?.text === text) return prior.id;
  const id = crypto.randomUUID();
  stored(key, JSON.stringify({ action, text, id }));
  return id;
}

async function submitRequest(url, body) {
  if (submitting) return null;
  submitting = true;
  $("build").disabled = true;
  $("refine").disabled = true;
  try {
    const text = JSON.stringify(body);
    const response = await api(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, request_id: requestToken(url, text) }),
    });
    stored("coderbuddy.pendingSubmission", "");
    selectionVersion++;
    render(response.run);
    await history();
    toast(`Request #${response.run.sequence} saved to the build queue.`);
    return response.run;
  } finally {
    submitting = false;
    $("build").disabled = false;
    if (activeRun) $("refine").disabled = ["queued", "running"].includes(activeRun.status) || !activeRun.generated_files?.includes("index.html");
  }
}

async function build() {
  const requirement = $("requirement").value.trim();
  if (requirement.length < 5) {
    toast("Please describe the app in a little more detail.");
    $("requirement").focus();
    return;
  }
  try {
    await submitRequest("/api/runs", { requirement });
    $("dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message);
  }
}

async function refine(event) {
  event.preventDefault();
  const instruction = $("iteration").value.trim();
  if (!activeRun || instruction.length < 3) {
    toast("Describe a specific change to make.");
    $("iteration").focus();
    return;
  }
  try {
    const run = await submitRequest(`/api/runs/${encodeURIComponent(activeRun.id)}/iterate`, { instruction });
    if (run) $("iteration").value = "";
  } catch (error) {
    toast(error.message);
  }
}

function historyButton(run, inline = false) {
  const title = esc(run.requirement.split("\n")[0].slice(0, 75));
  return inline
    ? `<button class="history-chip" data-run="${esc(run.id)}"><b>${title}</b><span>${esc(run.project_type || "build")} · ${esc(run.status)}</span></button>`
    : `<button class="history-item" data-run="${esc(run.id)}"><span>#${run.sequence} ${title}</span><i class="${esc(run.status)}"></i></button>`;
}

async function history() {
  const runs = await api("/api/runs");
  summaries = runs;
  const signature = JSON.stringify(runs.map(run => [run.id, run.status, run.phase, run.updated_at]));
  if (signature !== historySignature) {
    historySignature = signature;
    const recorded = runs.filter(run => run.mode !== "recovered");
    $("history-count").textContent = recorded.length;
    $("history-list").innerHTML = recorded.length ? recorded.slice(0, 5).map(run => historyButton(run)).join("")
    : '<p class="muted">No builds yet. Your work will be saved here.</p>';
    $("history-inline-list").innerHTML = recorded.slice(0, 12).map(run => historyButton(run, true)).join("");
    const waiting = runs.filter(run => ["queued", "running"].includes(run.status)).sort((a, b) => a.sequence - b.sequence);
    $("queue-count").textContent = waiting.length;
    $("queue-list").innerHTML = waiting.length ? waiting.map((run, index) => `
    <article class="queue-item ${esc(run.status)}">
      <button data-run="${esc(run.id)}"><b>#${run.sequence} · ${esc(statusText(run))}</b><br>${esc(run.requirement.split("\n")[0].slice(0, 70))}
      <small>${run.status === "running" ? "Active request" : `Waiting · position ${index + 1}`}</small></button>
      ${run.status === "queued" ? `<button class="queue-cancel" data-cancel="${esc(run.id)}">Cancel waiting request #${run.sequence}</button>` : ""}
    </article>`).join("") : '<p class="sidebar-hint">Queue is clear. Submit an application above.</p>';
    renderProjects();
    renderRevisions();
  }
}

function renderProjects() {
  const projects = new Map();
  for (const run of summaries) {
    const key = run.project_id || run.id;
    if (!projects.has(key)) projects.set(key, run);
  }
  $("project-count").textContent = projects.size;
  const query = $("project-search").value.toLowerCase().trim();
  const filtered = [...projects.values()].filter(run =>
    ($("show-recovered").checked || run.mode !== "recovered") && run.requirement.toLowerCase().includes(query));
  $("project-list").innerHTML = filtered.length ? filtered.map(run => `
    <button class="project-item ${(activeRun?.project_id || activeRun?.id) === (run.project_id || run.id) ? "selected" : ""}" data-run="${esc(run.id)}">
    <strong>${esc(run.requirement.split("\n")[0].slice(0, 75))}</strong>
    <small>${esc(statusText(run))} · ${esc(stamp(run.updated_at))}</small>
    </button>`).join("") : `<p class="sidebar-hint">${query ? "No matching projects." : "Your first project starts with a request."}</p>`;
}

function renderRevisions() {
  if (!activeRun) return;
  const projectId = activeRun.project_id || activeRun.id;
  const versions = summaries.filter(run => (run.project_id || run.id) === projectId);
  if (!versions.some(run => run.id === activeRun.id)) versions.unshift(activeRun);
  const select = $("build-revision");
  const key = versions.map(run => `${run.id}:${run.status}:${run.phase}`).join("|");
  if (select.dataset.versions !== key) {
    select.innerHTML = versions.map(run => `<option value="${esc(run.id)}">#${run.sequence} · ${esc(statusText(run))}${run.source_run_id ? " · refinement" : ""}</option>`).join("");
    select.dataset.versions = key;
  }
  select.value = activeRun.id;
}

async function loadRun(runId) {
  const version = ++selectionVersion;
  try {
    const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
    if (version !== selectionVersion) return;
    $("file-list").dataset.files = "";
    $("preview-frame").dataset.runId = "";
    render(run);
    $("dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
    renderProjects();
  } catch (error) {
    toast(error.message);
  }
}

async function modelStatus() {
  const chip = $("model-status");
  chip.classList.remove("ready", "offline");
  try {
    const data = await api("/api/health");
    if (data.queue_error) toast(data.queue_error);
    if (data.model_ready) {
      chip.classList.add("ready");
      chip.querySelector("span").textContent = `${data.provider_name} ready · ${data.model}`;
    } else if (String(data.provider).startsWith("azure-foundry")) {
      chip.classList.add("offline");
      const states = {
        "azure-foundry-key-missing": "Set AZURE_OPENAI_API_KEY in .env",
        "azure-foundry-configuration-invalid": "Check Azure endpoint and deployment in .env",
        "azure-foundry-auth-failed": "Azure authentication failed · check key/access",
        "azure-foundry-deployment-missing": "Azure deployment not found · check deployment name",
        "azure-foundry-rate-limited": "Azure rate limit reached · retry later",
      };
      chip.querySelector("span").textContent = states[data.provider] || "Azure Foundry unavailable · fallback available";
    } else if (String(data.provider).includes("offline")) {
      chip.classList.add("offline");
      chip.querySelector("span").textContent = "Ollama offline · fallback available";
    } else if (String(data.provider).includes("missing")) {
      chip.classList.add("offline");
      chip.querySelector("span").textContent = `Model missing · ${data.model}`;
    } else {
      chip.querySelector("span").textContent = "Offline starter mode";
    }
  } catch {
    chip.classList.add("offline");
    chip.querySelector("span").textContent = "Local service unavailable";
  }
}

$("build").addEventListener("click", build);
$("iteration-form").addEventListener("submit", refine);
$("requirement").addEventListener("input", event => $("char-count").textContent = `${event.target.value.length} / 4000`);
$("requirement").dispatchEvent(new Event("input"));
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => {
  $("requirement").value = button.dataset.prompt;
  $("requirement").dispatchEvent(new Event("input"));
  $("requirement").focus();
}));
document.querySelectorAll("[data-change]").forEach(button => button.addEventListener("click", () => {
  $("iteration").value = button.dataset.change;
  $("iteration").focus();
}));
document.addEventListener("click", event => {
  const fileButton = event.target.closest("[data-file]");
  if (fileButton && activeRun) openFile(activeRun.id, fileButton.dataset.file);
  const runButton = event.target.closest("[data-run]");
  if (runButton) loadRun(runButton.dataset.run);
  const cancelButton = event.target.closest("[data-cancel]");
  if (cancelButton) cancelRun(cancelButton.dataset.cancel);
  const sectionButton = event.target.closest("[data-section]");
  if (sectionButton) {
    const section = $(sectionButton.dataset.section);
    if (section.closest(".studio-sidebar")) {
      document.querySelector(".studio-sidebar").classList.add("mobile-panels-open");
      $("toggle-sidebar").setAttribute("aria-expanded", "true");
    }
    if (section.hidden || (section.closest("#dashboard") && $("dashboard").hidden)) {
      toast("Open or create a project first.");
      return;
    }
    if (section.tagName === "DETAILS") section.open = true;
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});
$("code-content").parentElement.addEventListener("scroll", event => $("code-lines").scrollTop = event.target.scrollTop);
$("refresh-preview").addEventListener("click", () => {
  if (activeRun) $("preview-frame").src = `/api/runs/${encodeURIComponent(activeRun.id)}/preview?t=${Date.now()}`;
});
$("open-preview").addEventListener("click", event => {
  if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
});
$("expand-preview").addEventListener("click", () => {
  const expanded = $("workbench").classList.toggle("preview-expanded");
  $("expand-preview").setAttribute("aria-pressed", String(expanded));
  $("expand-preview").innerHTML = expanded ? "⤡ <span>Show code</span>" : "⤢ <span>Expand app</span>";
  $("expand-preview").title = expanded ? "Show code and preview" : "Expand app preview";
});
$("project-search").addEventListener("input", renderProjects);
$("toggle-sidebar").addEventListener("click", () => {
  const expanded = document.querySelector(".studio-sidebar").classList.toggle("mobile-panels-open");
  $("toggle-sidebar").setAttribute("aria-expanded", String(expanded));
});
$("show-recovered").addEventListener("change", renderProjects);
$("build-revision").addEventListener("change", event => loadRun(event.target.value));
$("cancel-run").addEventListener("click", () => { if (activeRun) cancelRun(activeRun.id); });
$("retry-run").addEventListener("click", async () => {
  if (!activeRun) return;
  try {
    await submitRequest(`/api/runs/${encodeURIComponent(activeRun.id)}/retry`, { requirement: activeRun.requirement });
  } catch (error) { toast(error.message); }
});
$("download").addEventListener("click", event => {
  if ($("download").hidden) event.preventDefault();
});
$("new-project").addEventListener("click", () => {
  selectionVersion++;
  fileVersion++;
  activeRun = null;
  $("current-project").textContent = "";
  stored("coderbuddy.selectedBuild", "");
  document.body.classList.remove("workspace-active");
  $("dashboard").hidden = true;
  $("welcome").hidden = false;
  $("requirement").value = "";
  $("requirement").dispatchEvent(new Event("input"));
  $("requirement").focus();
  $("requirement").scrollIntoView({ behavior: "smooth", block: "center" });
  renderProjects();
});

async function cancelRun(runId) {
  try {
    const run = await api(`/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
    if (activeRun?.id === runId) render(run);
    await history();
    toast(`Request #${run.sequence} cancelled.`);
  } catch (error) { toast(error.message); }
}

async function refreshWorkspace() {
  if (refreshing) return;
  refreshing = true;
  const version = selectionVersion;
  const runId = activeRun?.id;
  try {
    await history();
    if (runId && version === selectionVersion && ["queued", "running"].includes(activeRun?.status)) {
      const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
      if (version === selectionVersion && activeRun?.id === runId) render(run);
    }
  } catch (error) { toast(`Connection issue: ${error.message}. Saved work is retained; reconnecting.`); }
  finally { refreshing = false; }
}

async function initialize() {
  modelStatus();
  try {
    await history();
    const selected = stored("coderbuddy.selectedBuild");
    if (selected && summaries.some(run => run.id === selected)) await loadRun(selected);
  } catch (error) { toast(`Could not load saved work: ${error.message}`); }
  setInterval(refreshWorkspace, 1800);
  setInterval(modelStatus, 65000);
}
initialize();
