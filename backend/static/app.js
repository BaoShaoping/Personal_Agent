const $ = (selector) => document.querySelector(selector);

const state = {
  latestSuggestion: null,
  highlightedTaskId: null,
};

const GENERATE_TODAY_TASK_PROMPT = "根据我的长期计划，生成一个今天可以完成的最小任务。";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function pretty(value) {
  return JSON.stringify(value ?? null, null, 2);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data?.error?.message || `请求失败：${response.status}`);
  }
  return data;
}

function setBusy(button, text) {
  if (!button) {
    return () => {};
  }
  const oldText = button.textContent;
  const oldDisabled = button.disabled;
  button.disabled = true;
  if (text) {
    button.textContent = text;
  }
  return () => {
    button.disabled = oldDisabled;
    button.textContent = oldText;
  };
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}

function statusLabel(status) {
  const labels = {
    success: "成功",
    failed: "失败",
    canceled: "已取消",
    pending: "等待中",
    executed: "已执行",
  };
  return labels[status] || status || "-";
}

function riskLabel(risk) {
  const labels = {
    low: "低风险",
    medium: "中风险",
    high: "高风险",
    critical: "关键风险",
  };
  return labels[risk] || risk || "未知风险";
}

function actionKindLabel(kind) {
  const labels = {
    save_memory_candidate: "保存记忆候选",
    create_plan_candidate: "创建计划候选",
    update_plan_task_status: "更新任务状态",
    create_today_task_candidate: "生成今日最小任务",
    answer_only: "仅回答",
  };
  return labels[kind] || kind || "未知操作";
}

function eventSummary(event) {
  const kindText = actionKindLabel(event.action_kind || "");
  const labels = {
    permission_evaluated: `权限评估完成：${kindText}。`,
    action_confirmed: `已确认操作：${kindText}。`,
    action_canceled: `已取消操作：${kindText}，未执行写入。`,
    action_executed: `已执行操作：${kindText}。`,
    action_failed: `操作失败：${kindText}。`,
  };
  return labels[event.event_type] || event.summary || "";
}

function friendlyPermissionReason(reason) {
  return String(reason || "")
    .replaceAll("low 风险", "低风险")
    .replaceAll("medium 风险", "中风险")
    .replaceAll("high 风险", "高风险")
    .replaceAll("critical 风险", "关键风险");
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function progressSummary(item) {
  const summary = String(item.summary || item.note || "进展记录");
  const match = summary.match(/^Task\s+(.+?)\s+marked as\s+(.+)\.$/i);
  if (match) {
    const statusText = {
      done: "已完成",
      skipped: "已跳过",
      blocked: "已阻塞",
      todo: "待处理",
    }[match[2]] || match[2];
    return `任务 ${match[1]} ${statusText}。`;
  }
  return summary;
}

function friendlyAgentText(text) {
  return String(text || "")
    .replace("[mock answer] ", "")
    .replaceAll("context_markdown", "当前上下文");
}

async function refreshDashboard() {
  const restore = setBusy($("#refresh-dashboard"), "刷新中");
  try {
    const [plans, audit, settings] = await Promise.all([
      requestJson("/api/plans/summary"),
      requestJson("/api/audit/summary"),
      requestJson("/api/settings"),
    ]);
    renderSettings(settings);
    renderPlans(plans);
    renderAudit(audit.recent_events || []);
  } catch (error) {
    showToast(error.message);
  } finally {
    restore();
  }
}

function renderSettings(data) {
  const permission = data.permission_mode || data.settings?.permission_mode || "ask_first";
  const modelMode = data.model_config?.mode || data.settings?.model?.mode || "mock";
  $("#runtime-mode").textContent = `模型 ${modelMode}`;
  $("#permission-mode").textContent = `权限 ${permission}`;
}

function renderPlans(data) {
  const plans = data.active_plans || [];
  const tasks = data.today_tasks || [];
  const progress = data.recent_progress || [];
  $("#active-plan-count").textContent = String(plans.length);
  $("#today-task-count").textContent = String(tasks.length);
  $("#plan-status-label").textContent = plans.length ? "运行中" : "暂无";
  document.body.classList.toggle("has-today-task", tasks.length > 0);
  renderTodayFocus(plans, tasks);
  renderPlanList(plans);
  renderTaskList(tasks, plans);
  renderProgressList(progress);
}

function renderTodayFocus(plans, tasks) {
  const target = $("#today-focus-copy");
  if (!target) {
    return;
  }
  const nextTask = tasks.find((task) => task.status !== "done") || tasks[0];
  if (nextTask) {
    target.textContent = `今日下一步：${nextTask.title || nextTask.id}`;
    return;
  }
  const leadingPlan = plans[0];
  if (leadingPlan) {
    target.textContent = `今日下一步：从「${leadingPlan.title || leadingPlan.id}」挑一个最小推进点。`;
    return;
  }
  target.textContent = "今日下一步：先记录一个想推进的长期方向。";
}

function renderPlanList(plans) {
  const target = $("#plan-list");
  if (!plans.length) {
    target.innerHTML = `<div class="empty">暂无活跃计划</div>`;
    return;
  }
  target.innerHTML = plans
    .map((plan) => {
      const progress = Math.max(0, Math.min(Number(plan.progress_percent || 0), 100));
      const tags = (plan.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
      return `
        <article class="plan-item">
          <div class="plan-head">
            <div>
              <div class="plan-title">${escapeHtml(plan.title || plan.id)}</div>
              <div class="plan-meta">${escapeHtml(plan.kind || "")} · ${escapeHtml(plan.status || "")} · ${escapeHtml(plan.reminder_mode || "")}</div>
            </div>
            <strong>${progress}%</strong>
          </div>
          <div class="progress-track" aria-label="计划进度">
            <div class="progress-fill" style="width:${progress}%"></div>
          </div>
          <div class="plan-meta">${escapeHtml(plan.current_stage || plan.goal || "")}</div>
          <div class="tag-row">${tags}</div>
        </article>
      `;
    })
    .join("");
}

function renderTaskList(tasks, plans = []) {
  const target = $("#task-list");
  if (!tasks.length) {
    const button = plans.length
      ? `<button class="secondary-action" id="generate-today-task" type="button">生成今日最小任务</button>`
      : "";
    target.innerHTML = `
      <div class="empty task-empty">
        <p>今天没有到期任务。可以从长期计划挑一个最小推进点。</p>
        ${button}
      </div>
    `;
    const generateButton = $("#generate-today-task");
    if (generateButton) {
      generateButton.addEventListener("click", requestTodayTaskSuggestion);
    }
    return;
  }
  target.innerHTML = tasks
    .map((task) => {
      const done = task.status === "done";
      const fresh = state.highlightedTaskId && task.id === state.highlightedTaskId;
      return `
        <article class="task-item ${done ? "task-done" : ""} ${fresh ? "task-fresh" : ""}">
          <label class="task-left">
            <input class="task-checkbox" type="checkbox" data-task-id="${escapeHtml(task.id)}" ${done ? "checked" : ""} />
            <span>
              <span class="task-title">${escapeHtml(task.title || task.id)}</span>
              <span class="plan-meta">${escapeHtml(task.plan_id || "")} · ${escapeHtml(task.status || "")}</span>
            </span>
          </label>
        </article>
      `;
    })
    .join("");
  document.querySelectorAll(".task-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", () => updateTaskStatus(checkbox.dataset.taskId, checkbox.checked));
  });
  if (state.highlightedTaskId) {
    const freshTask = document.querySelector(".task-fresh");
    if (freshTask) {
      window.setTimeout(() => freshTask.scrollIntoView({ block: "nearest", behavior: "smooth" }), 0);
    }
  }
}

function renderProgressList(progress) {
  const target = $("#progress-list");
  if (!progress.length) {
    target.innerHTML = `<div class="empty">暂无进展记录</div>`;
    return;
  }
  target.innerHTML = progress
    .slice(0, 4)
    .map(
      (item) => `
        <article class="progress-item">
          <div>${escapeHtml(progressSummary(item))}</div>
          <div class="progress-meta">${escapeHtml(item.plan_id || "")} · ${formatTime(item.created_at)}</div>
        </article>
      `
    )
    .join("");
}

function requestTodayTaskSuggestion() {
  const input = $("#prompt-input");
  input.value = GENERATE_TODAY_TASK_PROMPT;
  $("#prompt-form").requestSubmit();
}

async function updateTaskStatus(taskId, checked) {
  try {
    await requestJson("/api/plans/tasks/status", {
      method: "POST",
      body: JSON.stringify({
        task_id: taskId,
        status: checked ? "done" : "todo",
        note: checked ? "用户在 /app 勾选完成。" : "用户在 /app 取消完成。",
      }),
    });
    await refreshDashboard();
  } catch (error) {
    showToast(error.message);
    await refreshDashboard();
  }
}

function appendMessage(role, text) {
  const messages = $("#messages");
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="message-meta">${role === "user" ? "你" : "Agent"}</div>
    <p>${escapeHtml(text || "")}</p>
  `;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $("#prompt-input");
  const message = input.value.trim();
  if (!message) {
    return;
  }
  const restore = setBusy($("#send-message"), "发送中");
  $("#loop-status").textContent = "思考中";
  hideActionCard();
  appendMessage("user", message);
  input.value = "";
  try {
    const data = await requestJson("/api/suggest/with-permission", {
      method: "POST",
      body: JSON.stringify({
        user_message: message,
        include_ask: true,
        max_chars: 6000,
        max_memories: 8,
      }),
    });
    state.latestSuggestion = data;
    renderAgentResult(data);
    await refreshDashboard();
  } catch (error) {
    appendMessage("agent", error.message);
    showToast(error.message);
  } finally {
    $("#loop-status").textContent = "待命";
    restore();
  }
}

function renderAgentResult(data) {
  const suggestion = data.suggestion || {};
  const answer = suggestion.answer || data.ask_result?.answer || "";
  if (answer) {
    appendMessage("agent", friendlyAgentText(answer));
  }
  if (suggestion.type === "suggested_action") {
    renderActionCard(data);
    return;
  }
  if (!answer) {
    appendMessage("agent", suggestion.reason || "当前没有建议操作。");
  }
}

function renderActionCard(data) {
  const suggestion = data.suggestion || {};
  const decision = data.permission_decision || {};
  const action = suggestion.action || {};
  const card = $("#action-card");
  card.hidden = false;
  card.classList.remove("action-card-complete", "action-card-canceled", "action-card-failed");
  $("#action-title").textContent = suggestion.title || action.title || "建议操作";
  $("#action-message").textContent = suggestion.message || action.summary || "";
  $("#action-reason").textContent = suggestion.reason || "";
  $("#action-risk").textContent = riskLabel(decision.risk_level || action.risk_level);
  const strip = $("#permission-strip");
  strip.className = `permission-strip ${decision.risk_level || ""}`;
  strip.innerHTML = `
    <strong>${decision.requires_confirmation ? "需要确认" : "无需确认"}</strong>
    <div>风险等级：${riskLabel(decision.risk_level)}（${escapeHtml(decision.risk_level || "")}）</div>
    <div>确认要求：${decision.requires_confirmation ? "需要确认" : "无需确认"} · 权限模式：${escapeHtml(decision.permission_mode || "")}</div>
    <div>${escapeHtml(friendlyPermissionReason(decision.reason))}</div>
  `;
  $("#action-controls").hidden = false;
  $("#execution-result").hidden = true;
  $("#action-json").textContent = pretty({
    suggestion,
    permission_decision: decision,
  });
}

function hideActionCard() {
  state.latestSuggestion = null;
  $("#action-card").hidden = true;
  $("#action-card").classList.remove("action-card-complete", "action-card-canceled", "action-card-failed");
}

async function confirmLatestAction() {
  const data = state.latestSuggestion;
  const action = data?.suggestion?.action;
  if (!action) {
    return;
  }
  const restore = setBusy($("#confirm-action"), "执行中");
  try {
    const result = await requestJson("/api/actions/confirm", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_decision: data.permission_decision || {},
      }),
    });
    const execution = result.execution || {};
    const createdTask = execution.execution_result?.created_task;
    if (execution.status === "executed" && createdTask?.id) {
      state.highlightedTaskId = createdTask.id;
    }
    renderExecution(execution);
    await refreshDashboard();
    if (execution.status === "executed") {
      pulseTodayTaskCount();
      showToast("已确认执行，今日任务和 Audit 已刷新。");
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    restore();
  }
}

async function cancelLatestAction() {
  const data = state.latestSuggestion;
  const action = data?.suggestion?.action;
  if (!action) {
    return;
  }
  const restore = setBusy($("#cancel-action"), "取消中");
  try {
    const result = await requestJson("/api/actions/cancel", {
      method: "POST",
      body: JSON.stringify({
        action,
        permission_decision: data.permission_decision || {},
        reason: "用户在 /app 取消。",
      }),
    });
    renderExecution(result.execution || {});
    await refreshDashboard();
  } catch (error) {
    showToast(error.message);
  } finally {
    restore();
  }
}

function renderExecution(execution) {
  const target = $("#execution-result");
  const status = execution.status || (execution.ok ? "success" : "failed");
  const kind = execution.action_kind;
  target.hidden = false;
  target.className = `execution-result ${status === "executed" ? "success" : status}`;
  $("#action-card").classList.toggle("action-card-complete", status === "executed");
  $("#action-card").classList.toggle("action-card-canceled", status === "canceled");
  $("#action-card").classList.toggle("action-card-failed", status === "failed");

  if (status === "canceled") {
    target.textContent = `已取消：${actionKindLabel(kind)}。已写入最近记录，未执行操作。`;
  } else if (status === "executed" && kind === "create_today_task_candidate") {
    target.textContent = "已确认执行：今日最小任务已创建，任务列表和 Audit 记录已刷新。";
  } else if (status === "executed") {
    target.textContent = `已确认执行：${actionKindLabel(kind)} 已完成。`;
  } else if (status === "failed") {
    target.textContent = `执行失败：${actionKindLabel(kind)}。${execution.error?.message || ""}`;
  } else {
    target.textContent = `${statusLabel(status)}：${actionKindLabel(kind)}`;
  }
  $("#action-controls").hidden = true;
  $("#action-json").textContent = pretty({
    suggestion: state.latestSuggestion?.suggestion || {},
    permission_decision: state.latestSuggestion?.permission_decision || {},
    execution,
  });
}

function pulseTodayTaskCount() {
  const metric = $("#today-task-count")?.parentElement;
  if (!metric) {
    return;
  }
  metric.classList.remove("metric-highlight");
  void metric.offsetWidth;
  metric.classList.add("metric-highlight");
}

function renderAudit(events) {
  const target = $("#audit-list");
  if (!events.length) {
    target.innerHTML = `<div class="empty">暂无记录</div>`;
    return;
  }
  target.innerHTML = events
    .slice(0, 8)
    .map(
      (event) => `
        <article class="audit-item ${escapeHtml(event.status || "")}">
          <div class="section-title">
            <span class="audit-type">${escapeHtml(event.event_type || "event")}</span>
            <span>${statusLabel(event.status)}</span>
          </div>
          <div class="audit-summary">${escapeHtml(eventSummary(event))}</div>
          <div class="audit-meta">created_at: ${formatTime(event.created_at)} · ${escapeHtml(event.action_kind || event.module || "")}</div>
          <details class="json-details">
            <summary>查看 JSON</summary>
            <pre>${escapeHtml(pretty(event))}</pre>
          </details>
        </article>
      `
    )
    .join("");
}

$("#prompt-form").addEventListener("submit", sendMessage);
$("#confirm-action").addEventListener("click", confirmLatestAction);
$("#cancel-action").addEventListener("click", cancelLatestAction);
$("#refresh-dashboard").addEventListener("click", refreshDashboard);
$("#refresh-audit").addEventListener("click", refreshDashboard);

refreshDashboard();
