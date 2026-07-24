const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function renderModules(modules) {
  $("#moduleGrid").innerHTML = modules
    .map(
      (module, index) => `
        <article class="module-card">
          <div class="module-topline">
            <span class="module-index">${String(index + 1).padStart(2, "0")} / ${escapeHtml(module.group)}</span>
            <span class="module-health ${escapeHtml(module.health)}">${escapeHtml(module.health)}</span>
          </div>
          <h3>${escapeHtml(module.name)}</h3>
          <p>${escapeHtml(module.description)}</p>
          <div class="module-footer">
            <span>${escapeHtml(module.upkeep)}</span>
            <span>${escapeHtml(module.declared_status)}</span>
          </div>
        </article>
      `
    )
    .join("");
}

function renderRoutes(routes) {
  $("#routeList").innerHTML = routes
    .map(
      (route) => `
        <div class="route-row">
          <strong>${escapeHtml(route.route.replaceAll("_", " "))}</strong>
          <span>${escapeHtml(route.model_key)}</span>
          <div class="route-models">${escapeHtml(route.candidates.join(" → "))}</div>
          <div class="token-pill">${escapeHtml(route.max_tokens || "—")} max</div>
        </div>
      `
    )
    .join("");
}

function renderUpkeep(upkeep) {
  const badge = $("#auditBadge");
  badge.textContent = upkeep.status === "pass" ? "Gate clear" : "Blocked";
  badge.className = `status-badge ${upkeep.status}`;

  const issues = [...upkeep.blockers, ...upkeep.warnings];
  $("#issueList").innerHTML = issues.length
    ? issues
        .map(
          (issue) => `
            <div class="issue">
              <strong>${escapeHtml(issue.module)}</strong>
              <p>${escapeHtml(issue.message)}</p>
            </div>
          `
        )
        .join("")
    : '<p class="empty-state">All active module seams are intact.</p>';
}

function renderSnapshot(snapshot) {
  $("#ecosystemPromise").textContent = snapshot.ecosystem.promise;
  $("#defaultSpend").textContent = `£${snapshot.cost.default_cost_usd}`;
  $("#healthyModules").textContent = snapshot.summary.modules_healthy;
  $("#moduleTotal").textContent = `${snapshot.summary.modules_total} registered modules`;
  $("#upkeepStatus").textContent = snapshot.summary.upkeep_status.toUpperCase();
  $("#costGuardCopy").textContent = snapshot.cost.cloud_locked
    ? "Local providers are the only default route. OpenAI and other cloud bridges remain locked."
    : "A cloud gate is open for one explicitly approved task.";
  renderModules(snapshot.modules);
  renderRoutes(snapshot.rotation);
  renderUpkeep(snapshot.upkeep);
}

function statePayload(response) {
  return response?.data || response || {};
}

function renderOracleState(response) {
  const state = statePayload(response);
  $("#oracleState").textContent = state.visualState || state.visual_state || "Listening";
  const next = state.nextBestAction || state.next_best_action || {};
  $("#oracleAction").textContent = next.description || next.label || "Waiting for a clear objective";
}

async function decideConfirmation(id, decision) {
  await request(`/api/confirmations/${encodeURIComponent(id)}/${decision}`, {
    method: "POST",
    body: JSON.stringify({ decisionNote: `Decision from Hermes control plane: ${decision}` }),
  });
  await refresh();
}

function renderConfirmations(response) {
  const items = statePayload(response).items || [];
  const pending = items.filter((item) => item.status === "pending");
  $("#pendingCount").textContent = pending.length;
  $("#consentBadge").textContent = `${pending.length} pending`;
  $("#confirmationList").innerHTML = pending.length
    ? pending
        .map(
          (item) => `
            <div class="confirmation">
              <strong>${escapeHtml(item.action_label || "Review action")}</strong>
              <p>${escapeHtml(item.reason || "Operator confirmation required.")}</p>
              <div class="confirmation-actions">
                <button class="mini-button" data-confirm="${escapeHtml(item.id)}" data-decision="approve">Approve once</button>
                <button class="mini-button reject" data-confirm="${escapeHtml(item.id)}" data-decision="reject">Reject</button>
              </div>
            </div>
          `
        )
        .join("")
    : '<p class="empty-state">No pending decisions. The boundary is quiet.</p>';

  document.querySelectorAll("[data-confirm]").forEach((button) => {
    button.addEventListener("click", () => decideConfirmation(button.dataset.confirm, button.dataset.decision));
  });
}

async function refresh() {
  $("#refreshButton").disabled = true;
  try {
    const [snapshot, oracleState, confirmations] = await Promise.all([
      request("/api/ecosystem"),
      request("/api/oracle/state"),
      request("/api/confirmations"),
    ]);
    renderSnapshot(snapshot);
    renderOracleState(oracleState);
    renderConfirmations(confirmations);
    $("#lastUpdated").textContent = `SYNCED ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  } catch (error) {
    $("#lastUpdated").textContent = `LOCAL API UNAVAILABLE · ${error.message}`;
  } finally {
    $("#refreshButton").disabled = false;
  }
}

$("#oracleForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#oracleInput");
  const resultPanel = $("#commandResult");
  const text = input.value.trim();
  if (!text) return;

  resultPanel.hidden = false;
  resultPanel.textContent = "Oracle is compressing the direction…";
  try {
    const response = await request("/api/oracle/intake", {
      method: "POST",
      body: JSON.stringify({
        mode: "architect",
        text,
        objective: "Convert this direction into the smallest safe, useful checkpoint.",
        metadata: { source: "hermes-control-plane" },
      }),
    });
    const data = statePayload(response);
    const next = data.nextAction || {};
    resultPanel.textContent = data.requiresConfirmation
      ? `Held for approval: ${next.description || "Review the consent queue."}`
      : `Next action: ${next.description || next.label || "Direction recorded."}`;
    input.value = "";
    await refresh();
  } catch (error) {
    resultPanel.textContent = `Oracle could not record the direction: ${error.message}`;
  }
});

$("#refreshButton").addEventListener("click", refresh);

document.querySelectorAll(".rail-link").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".rail-link").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

function updateClock() {
  $("#clock").textContent = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

updateClock();
setInterval(updateClock, 1000);
refresh();
