const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

let latestSuggestionPayload = null;

function pretty(value) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value ?? null, null, 2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showError(id, message) {
  const target = $(id);
  target.textContent = message;
  target.hidden = !message;
}

function setBusy(control, busyText) {
  const target = typeof control === "string" ? $(control) : control;
  if (!target) {
    return () => {};
  }
  const previousText = target.textContent;
  const previousDisabled = target.disabled;
  target.disabled = true;
  target.classList.add("is-loading");
  if (busyText) {
    target.textContent = busyText;
  }
  return () => {
    target.disabled = previousDisabled;
    target.textContent = previousText;
    target.classList.remove("is-loading");
  };
}

async function withBusy(control, busyText, task) {
  const restore = setBusy(control, busyText);
  try {
    return await task();
  } finally {
    restore();
  }
}

function bindAction(selector, handler, busyText) {
  const target = $(selector);
  if (!target) {
    return;
  }
  target.addEventListener("click", () => withBusy(target, busyText, handler));
}

function statusLabel(status) {
  const labels = {
    success: "成功 success",
    failed: "失败 failed",
    canceled: "已取消 canceled",
    pending: "等待中 pending",
  };
  return labels[status] || status || "-";
}

function statusClass(status) {
  if (status === "success") {
    return "success";
  }
  if (status === "canceled") {
    return "canceled";
  }
  if (status === "failed") {
    return "failed";
  }
  return "";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    const message = data?.error?.message || `请求失败：${response.status}`;
    throw new Error(message);
  }
  return data;
}

function activateTab(tabId) {
  $$(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabId);
  });
  $$(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabId);
  });
}

async function buildContext() {
  showError("#context-error", "");
  const payload = {
    user_message: $("#context-message").value,
    max_chars: Number($("#context-max-chars").value || 6000),
    max_memories: Number($("#context-max-memories").value || 8),
  };

  try {
    const data = await requestJson("/api/context/build", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    $("#context-markdown").textContent = data.context_markdown || "";
    $("#context-profile").textContent = pretty(data.profile_summary);
    $("#context-goals").textContent = pretty(data.active_goals);
    $("#context-projects").textContent = pretty(data.active_projects);
    $("#context-constraints").textContent = pretty(data.constraints);
    $("#context-decisions").textContent = pretty(data.relevant_decisions);
    $("#context-memories").textContent = pretty(data.relevant_memories);
    $("#context-sources").textContent = pretty(data.sources);
    $("#context-omitted").textContent = pretty(data.omitted);
    $("#context-stats").textContent = pretty(data.stats);
    $("#context-json").textContent = pretty(data);
  } catch (error) {
    showError("#context-error", error.message);
  }
}

async function refreshMemory() {
  showError("#memory-error", "");
  try {
    const data = await requestJson("/api/memory/summary");
    $("#memory-files").textContent = pretty(data.files);
    $("#memory-profile").textContent = pretty(data.profile);
    $("#memory-goals").textContent = pretty(data.goals);
    $("#memory-projects").textContent = pretty(data.projects);
    $("#memory-constraints").textContent = pretty(data.constraints);
    $("#memory-counts").textContent = pretty(data.counts);
    $("#memory-diagnostics").textContent = pretty({
      missing_files: data.missing_files,
      load_errors: data.load_errors,
    });
    $("#memory-json").textContent = pretty(data);
  } catch (error) {
    showError("#memory-error", error.message);
  }
}

async function refreshSettings() {
  showError("#settings-error", "");
  try {
    const data = await requestJson("/api/settings");
    $("#settings-notice").hidden = data.found !== false;
    $("#settings-data").textContent = data.found ? pretty(data.settings) : "未找到 settings.yaml";
    $("#settings-json").textContent = pretty(data);
  } catch (error) {
    showError("#settings-error", error.message);
  }
}

async function refreshModelConfig() {
  showError("#model-error", "");
  try {
    const data = await requestJson("/api/model/config");
    $("#model-config-json").textContent = pretty(data.model_config);
    $("#model-mode").textContent = data.model_config?.mode || "-";
  } catch (error) {
    showError("#model-error", error.message);
  }
}

async function runAsk() {
  showError("#model-error", "");
  const payload = {
    user_message: $("#ask-message").value,
    max_chars: Number($("#ask-max-chars").value || 6000),
    max_memories: Number($("#ask-max-memories").value || 8),
  };

  try {
    const data = await requestJson("/api/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("#ask-answer").textContent = data.answer || "";
    $("#ask-model-info").textContent = pretty(data.model_info);
    $("#ask-context-markdown").textContent = data.context_pack?.context_markdown || "";
    $("#ask-json").textContent = pretty(data);
  } catch (error) {
    showError("#model-error", error.message);
  }
}

async function testModel() {
  showError("#model-error", "");
  try {
    const data = await requestJson("/api/model/test", {
      method: "POST",
      body: JSON.stringify({ user_message: $("#ask-message").value || "测试模型网关" }),
    });
    $("#model-test-json").textContent = pretty(data);
  } catch (error) {
    showError("#model-error", error.message);
  }
}

function renderSuggestionCard(suggestion) {
  const card = $("#suggestion-card");
  const summary = $("#suggestion-summary");
  const buttons = $("#suggestion-buttons");
  const type = suggestion?.type || "answer_only";
  card.classList.toggle("answer-only", type === "answer_only");
  card.classList.toggle("suggested-action", type === "suggested_action");

  if (type === "suggested_action") {
    const action = suggestion.action || {};
    summary.innerHTML = `
      <p class="suggestion-title">${escapeHtml(suggestion.title || "建议操作")}</p>
      <div class="suggestion-meta">${escapeHtml(suggestion.message || "")}</div>
      <div class="suggestion-meta">
        action.kind: ${escapeHtml(action.kind || "")} | risk_level: ${escapeHtml(action.risk_level || "")}
      </div>
    `;
    buttons.innerHTML = `
      <button id="confirm-suggested-action" type="button">确认执行 Confirm</button>
      <button id="cancel-suggested-action" type="button">取消 Cancel</button>
    `;
    $("#confirm-suggested-action").addEventListener("click", () =>
      withBusy("#confirm-suggested-action", "执行中...", confirmSuggestedAction)
    );
    $("#cancel-suggested-action").addEventListener("click", () =>
      withBusy("#cancel-suggested-action", "取消中...", cancelSuggestedAction)
    );
    return;
  }

  summary.innerHTML = `
    <p class="suggestion-title">无建议操作 answer_only</p>
    <div class="suggestion-meta">${escapeHtml(suggestion?.answer || "没有建议操作。")}</div>
  `;
  buttons.innerHTML = "";
}

function renderExecutionResult(execution, prefix = "action") {
  const card = $(`#${prefix}-execution-card`);
  if (card) {
    const status = execution?.status || "";
    card.classList.toggle("success", status === "success" || execution?.ok === true);
    card.classList.toggle("canceled", status === "canceled");
    card.classList.toggle("failed", status === "failed" || execution?.ok === false);
  }
  const summary = $(`#${prefix}-execution-summary`);
  if (summary) {
    summary.innerHTML = `
      <p class="suggestion-title">${escapeHtml(statusLabel(execution?.status))}</p>
      <div class="suggestion-meta">
        ok: ${escapeHtml(execution?.ok ?? "")} |
        action_kind: ${escapeHtml(execution?.action_kind || "")} |
        target: ${escapeHtml(execution?.target || "")}
      </div>
      <div class="suggestion-meta">${escapeHtml(execution?.error?.message || "")}</div>
    `;
  }
}

function renderActionStatus(execution, permissionDecision = null) {
  const card = $("#action-status-card");
  const summary = $("#action-status-summary");
  if (!card || !summary) {
    return;
  }
  const status = execution?.status || "pending";
  card.classList.toggle("success", status === "success" || execution?.ok === true);
  card.classList.toggle("canceled", status === "canceled");
  card.classList.toggle("failed", status === "failed" || execution?.ok === false);
  summary.innerHTML = `
    <p class="suggestion-title">${escapeHtml(statusLabel(status))}</p>
    <div class="suggestion-meta">
      action_kind: ${escapeHtml(execution?.action_kind || permissionDecision?.action_kind || "")} |
      target: ${escapeHtml(execution?.target || "")} |
      requires_confirmation: ${escapeHtml(permissionDecision?.requires_confirmation ?? "")}
    </div>
    <div class="suggestion-meta">${escapeHtml(execution?.error?.message || "")}</div>
  `;
}

function renderPermissionDecision(decision, prefix = "permission") {
  const card = $(`#${prefix}-card`);
  const summary = $(`#${prefix}-summary`);
  if (!card || !summary) {
    return;
  }
  card.classList.toggle("allowed", Boolean(decision?.allowed_without_confirmation));
  card.classList.toggle("confirm", Boolean(decision?.requires_confirmation) && !decision?.hard_block);
  card.classList.toggle("blocked", Boolean(decision?.hard_block));
  summary.innerHTML = `
    <p class="suggestion-title">${escapeHtml(decision?.requires_confirmation ? "需要确认" : "无需确认")}</p>
    <div class="suggestion-meta">
      mode: ${escapeHtml(decision?.permission_mode || "")} |
      action_kind: ${escapeHtml(decision?.action_kind || "")} |
      risk_level: ${escapeHtml(decision?.risk_level || "")} |
      hard_block: ${escapeHtml(decision?.hard_block || false)}
    </div>
    <div class="suggestion-meta">${escapeHtml(decision?.reason || "")}</div>
  `;
}

async function runSuggest() {
  showError("#suggestion-error", "");
  const payload = {
    user_message: $("#suggest-message").value,
    max_chars: Number($("#suggest-max-chars").value || 6000),
    max_memories: Number($("#suggest-max-memories").value || 8),
    include_ask: $("#suggest-include-ask").checked,
    permission_mode: $("#suggest-permission-mode")?.value || "ask_first",
  };

  try {
    const data = await requestJson("/api/suggest/with-permission", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    latestSuggestionPayload = data;
    renderSuggestionCard(data.suggestion || {});
    renderPermissionDecision(data.permission_decision || {}, "suggestion");
    $("#suggestion-action-json").textContent = pretty(data.suggestion?.action || null);
    $("#suggestion-permission-json").textContent = pretty(data.permission_decision || null);
    $("#suggestion-reason").textContent = data.suggestion?.reason || "";
    $("#suggestion-context-markdown").textContent = data.context_pack?.context_markdown || "";
    $("#suggestion-ask-json").textContent = pretty(data.ask_result || null);
    $("#suggestion-execution-json").textContent = "";
    renderExecutionResult(null, "suggestion");
    $("#suggestion-json").textContent = pretty(data);
  } catch (error) {
    showError("#suggestion-error", error.message);
  }
}

async function confirmSuggestedAction() {
  showError("#suggestion-error", "");
  const action = latestSuggestionPayload?.suggestion?.action;
  if (!action) {
    showError("#suggestion-error", "没有可确认的建议操作。");
    return;
  }
  try {
    const data = await requestJson("/api/actions/confirm", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_decision: latestSuggestionPayload?.permission_decision || {},
      }),
    });
    renderExecutionResult(data.execution || {}, "suggestion");
    $("#suggestion-execution-json").textContent = pretty(data);
    await refreshAuditLog();
    await refreshPlans();
    await refreshMemory();
  } catch (error) {
    showError("#suggestion-error", error.message);
  }
}

async function cancelSuggestedAction() {
  showError("#suggestion-error", "");
  const action = latestSuggestionPayload?.suggestion?.action;
  if (!action) {
    showError("#suggestion-error", "没有可取消的建议操作。");
    return;
  }
  try {
    const data = await requestJson("/api/actions/cancel", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_decision: latestSuggestionPayload?.permission_decision || {},
        reason: "user canceled from suggestion tab",
      }),
    });
    renderExecutionResult(data.execution || {}, "suggestion");
    $("#suggestion-execution-json").textContent = pretty(data);
    await refreshAuditLog();
  } catch (error) {
    showError("#suggestion-error", error.message);
  }
}

async function evaluatePermission() {
  showError("#permission-error", "");
  let action = null;
  try {
    const text = $("#permission-action-json").value.trim();
    action = text ? JSON.parse(text) : null;
  } catch (error) {
    showError("#permission-error", `操作 JSON 无效：${error.message}`);
    return;
  }

  try {
    const data = await requestJson("/api/permission/evaluate", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_mode: $("#permission-mode").value,
      }),
    });
    renderPermissionDecision(data.decision || {}, "permission");
    $("#permission-decision-json").textContent = pretty(data.decision);
    $("#permission-json").textContent = pretty(data);
  } catch (error) {
    showError("#permission-error", error.message);
  }
}

function parseActionJson(selector, errorSelector) {
  try {
    const text = $(selector).value.trim();
    return text ? JSON.parse(text) : {};
  } catch (error) {
    showError(errorSelector, `操作 JSON 无效：${error.message}`);
    return null;
  }
}

async function confirmActionFromTab() {
  showError("#action-error", "");
  const action = parseActionJson("#action-json", "#action-error");
  if (!action) {
    return;
  }
  try {
    const data = await requestJson("/api/actions/confirm", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_mode: $("#action-permission-mode").value,
      }),
    });
    $("#action-execution-json").textContent = pretty(data.execution);
    $("#action-permission-json").textContent = pretty(data.permission_decision);
    $("#action-audit-json").textContent = pretty(data.execution?.audit_events || []);
    $("#action-json-output").textContent = pretty(data);
    renderActionStatus(data.execution || {}, data.permission_decision || {});
    await refreshAuditLog();
    await refreshPlans();
    await refreshMemory();
  } catch (error) {
    showError("#action-error", error.message);
  }
}

async function cancelActionFromTab() {
  showError("#action-error", "");
  const action = parseActionJson("#action-json", "#action-error");
  if (!action) {
    return;
  }
  try {
    const data = await requestJson("/api/actions/cancel", {
      method: "POST",
      body: JSON.stringify({
        action,
        reason: "user canceled from action executor tab",
      }),
    });
    $("#action-execution-json").textContent = pretty(data.execution);
    $("#action-permission-json").textContent = pretty(data.execution?.permission_decision || {});
    $("#action-audit-json").textContent = pretty(data.execution?.audit_events || []);
    $("#action-json-output").textContent = pretty(data);
    renderActionStatus(data.execution || {}, data.execution?.permission_decision || {});
    await refreshAuditLog();
  } catch (error) {
    showError("#action-error", error.message);
  }
}

function renderAuditEvents(events) {
  const target = $("#audit-events");
  if (!events.length) {
    target.innerHTML = `<div class="notice">暂无审计事件。</div>`;
    return;
  }
  target.innerHTML = events
    .map(
      (event) => `
        <article class="audit-event ${statusClass(event.status)}">
          <div class="audit-event-header">
            <strong>${escapeHtml(event.event_type || "unknown")}</strong>
            <span>${escapeHtml(statusLabel(event.status))}</span>
          </div>
          <div class="suggestion-meta">
            ${escapeHtml(event.created_at || "")} |
            module: ${escapeHtml(event.module || "")} |
            action_kind: ${escapeHtml(event.action_kind || "")}
          </div>
          <div class="suggestion-meta">${escapeHtml(event.summary || "")}</div>
        </article>
      `
    )
    .join("");
}

async function refreshAuditLog() {
  showError("#audit-error", "");
  try {
    const data = await requestJson("/api/audit/summary");
    renderAuditEvents(data.recent_events || []);
    $("#audit-counts-type").textContent = pretty(data.counts_by_type || {});
    $("#audit-counts-status").textContent = pretty(data.counts_by_status || {});
    $("#audit-json").textContent = pretty(data);
  } catch (error) {
    showError("#audit-error", error.message);
  }
}

async function appendAuditEvent() {
  showError("#audit-error", "");
  let payload = {};
  try {
    const text = $("#audit-payload-json").value.trim();
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    showError("#audit-error", `payload JSON 无效：${error.message}`);
    return;
  }

  try {
    const data = await requestJson("/api/audit/events", {
      method: "POST",
      body: JSON.stringify({
        event_type: $("#audit-event-type").value,
        module: $("#audit-module").value,
        summary: $("#audit-summary").value,
        status: "success",
        payload,
      }),
    });
    $("#audit-append-json").textContent = pretty(data.event);
    await refreshAuditLog();
  } catch (error) {
    showError("#audit-error", error.message);
  }
}

function renderPlans(plans) {
  const target = $("#plans-list");
  if (!plans.length) {
    target.innerHTML = `<div class="notice">暂无活跃计划</div>`;
    return;
  }
  target.innerHTML = plans
    .map((plan) => {
      const progress = Math.max(0, Math.min(Number(plan.progress_percent || 0), 100));
      const tags = (plan.tags || []).map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("");
      return `
        <article class="plan-card">
          <div class="plan-card-header">
            <div>
              <h4>${escapeHtml(plan.title || plan.id)}</h4>
              <div class="plan-meta">
                kind: ${escapeHtml(plan.kind)} | status: ${escapeHtml(plan.status)} | reminder_mode: ${escapeHtml(
        plan.reminder_mode
      )}
              </div>
            </div>
            <strong>${progress}%</strong>
          </div>
          <div class="progress-track" aria-label="计划进度">
            <div class="progress-fill" style="width:${progress}%"></div>
          </div>
          <div class="plan-meta">
            current_stage: ${escapeHtml(plan.current_stage || "")}
          </div>
          <div class="plan-meta">
            goal: ${escapeHtml(plan.goal || "")}
          </div>
          <div class="pill-row">${tags}</div>
        </article>
      `;
    })
    .join("");
}

function renderTasks(tasks) {
  const target = $("#today-tasks");
  if (!tasks.length) {
    target.innerHTML = `<div class="notice">今天没有任务</div>`;
    return;
  }
  target.innerHTML = tasks
    .map(
      (task) => `
        <article class="task-row" data-task-id="${escapeHtml(task.id)}">
          <div>
            <p class="task-title">${escapeHtml(task.title || task.id)}</p>
            <div class="task-meta">
              plan_id: ${escapeHtml(task.plan_id)} | date: ${escapeHtml(task.date)}
            </div>
          </div>
          <select class="task-status" data-task-id="${escapeHtml(task.id)}">
            ${["todo", "done", "skipped", "blocked"]
              .map(
                (status) =>
                  `<option value="${status}" ${task.status === status ? "selected" : ""}>${status}</option>`
              )
              .join("")}
          </select>
        </article>
      `
    )
    .join("");

  $$(".task-status").forEach((select) => {
    select.addEventListener("change", () => updateTaskStatus(select.dataset.taskId, select.value));
  });
}

async function refreshPlans() {
  showError("#plans-error", "");
  try {
    const data = await requestJson("/api/plans/summary");
    renderPlans(data.active_plans || []);
    renderTasks(data.today_tasks || []);
    $("#plan-progress").textContent = pretty(data.recent_progress || []);
    $("#plans-json").textContent = pretty(data);
  } catch (error) {
    showError("#plans-error", error.message);
  }
}

async function updateTaskStatus(taskId, status) {
  showError("#plans-error", "");
  try {
    await requestJson("/api/plans/tasks/status", {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, status }),
    });
    await refreshPlans();
  } catch (error) {
    showError("#plans-error", error.message);
  }
}

async function buildPlanContext() {
  showError("#plans-error", "");
  const message = encodeURIComponent($("#plan-context-message").value || "");
  try {
    const data = await requestJson(`/api/plan/context?message=${message}`);
    $("#plan-context-json").textContent = pretty(data);
  } catch (error) {
    showError("#plans-error", error.message);
  }
}

function renderPlaceholders(modules) {
  modules
    .filter((module) => module.status === "not implemented")
    .forEach((module) => {
      const panel = document.getElementById(module.id);
      if (!panel) {
        return;
      }
      const moduleName = module.display_name_zh || module.name;
      const statusText = module.status_label_zh || module.status;
      const plannedInterface = module.planned_interface_zh || module.planned_interface;
      panel.innerHTML = `
        <div class="placeholder-shell">
          <h2>${moduleName}</h2>
          <dl>
            <dt>模块名称</dt>
            <dd>${moduleName}</dd>
            <dt>状态</dt>
            <dd><span class="status pending">${statusText}</span></dd>
            <dt>计划接口</dt>
            <dd><code>${plannedInterface}</code></dd>
          </dl>
        </div>
      `;
    });
}

async function refreshModules() {
  const data = await requestJson("/api/modules");
  renderPlaceholders(data.modules || []);
}

async function refreshAll() {
  await Promise.all([
    buildContext(),
    refreshMemory(),
    refreshSettings(),
    refreshModules(),
    refreshPlans(),
    buildPlanContext(),
    refreshModelConfig(),
    runAsk(),
    testModel(),
    runSuggest(),
    evaluatePermission(),
    refreshAuditLog(),
  ]);
}

$$(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
});

bindAction("#build-context", buildContext, "构建中...");
bindAction("#refresh-memory", refreshMemory, "刷新中...");
bindAction("#refresh-settings", refreshSettings, "刷新中...");
bindAction("#refresh-model", refreshModelConfig, "刷新中...");
bindAction("#run-ask", runAsk, "运行中...");
bindAction("#test-model", testModel, "测试中...");
bindAction("#run-suggest", runSuggest, "生成中...");
bindAction("#evaluate-permission", evaluatePermission, "评估中...");
bindAction("#confirm-action", confirmActionFromTab, "执行中...");
bindAction("#cancel-action", cancelActionFromTab, "取消中...");
bindAction("#refresh-audit", refreshAuditLog, "刷新中...");
bindAction("#append-audit", appendAuditEvent, "追加中...");
bindAction("#refresh-plans", refreshPlans, "刷新中...");
bindAction("#build-plan-context", buildPlanContext, "构建中...");
bindAction("#refresh-all", refreshAll, "刷新中...");

refreshAll();
