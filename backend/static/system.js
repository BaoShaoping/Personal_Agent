/* System Edition panel — step 1 UI prototype.
 *
 * Renders entirely from an embedded STUB that mirrors the signed data
 * contract (`GET /api/system/summary` + `data/system_state.yaml`). No backend,
 * no GLM. The "complete task" interaction settles rewards client-side so the
 * full loop (complete -> exp/magic/attribute -> forest growth -> 「叮！」) can be
 * seen and felt. Step 2 swaps this STUB for a real fetch of the same shape.
 */

(function () {
  "use strict";

  // ----- contract-shaped stub state (raw; derived fields computed below) -----
  const state = {
    character: { name: "系统", theme: "default" },
    total_exp: 520,
    magic_points: 145,
    attributes: {
      intellect: { exp: 1600 },
      constitution: { exp: 400 },
      willpower: { exp: 1225 },
      creativity: { exp: 900 },
      spirit: { exp: 625 },
    },
    forest: {
      growth: 12,
      decorations: [
        { id: "tree_sakura", label: "樱花树", kind: "tree" },
        { id: "house_small", label: "小屋", kind: "building" },
      ],
    },
    quest_lines: [
      { plan_id: "plan_personal_agent_001", title: "成为 AI 建造者", kind: "main", progress_percent: 38 },
      { plan_id: "plan_english_001", title: "英语能力", kind: "side", progress_percent: 71 },
    ],
    today_tasks: [
      { id: "task_1", plan_id: "plan_english_001", title: "背 10 个单词并造 3 个句子", status: "todo",
        rewards: { exp: 10, magic_points: 5, attribute: "intellect", attribute_exp: 15 } },
      { id: "task_2", plan_id: "plan_personal_agent_001", title: "给系统面板写一段渲染逻辑", status: "todo",
        rewards: { exp: 15, magic_points: 8, attribute: "creativity", attribute_exp: 20 } },
      { id: "task_3", plan_id: "plan_english_001", title: "慢跑 20 分钟", status: "todo",
        rewards: { exp: 10, magic_points: 5, attribute: "constitution", attribute_exp: 15 } },
    ],
    recent_dings: [
      { at: "09:10", text: "叮！宿主完成「晨间阅读」，经验 +12，智识 ↑" },
      { at: "昨天", text: "叮！成长之地新增一棵樱花树 🌸" },
    ],
  };

  const ATTRS = [
    { key: "intellect", label: "智识" },
    { key: "constitution", label: "体魄" },
    { key: "willpower", label: "自律" },
    { key: "creativity", label: "创造" },
    { key: "spirit", label: "心境" },
  ];
  const TREE_EMOJI = ["🌲", "🌳"];
  const DECO_EMOJI = {
    tree_sakura: "🌸", tree_pine: "🌲", tree_maple: "🍁",
    house_small: "🏠", castle: "🏰", stele: "🗿",
    lake: "💧", path: "🛤️", starry: "✨",
  };

  let pendingTreePop = false; // flag so the newest tree animates after a completion
  let proposedTitles = []; // titles rejected via "换一个" this round, fed back as avoid-list
  let currentProposal = null;

  // ----------------- derived helpers (mirror future backend) -----------------
  function levelThreshold(level) { return 100 + (level - 1) * 50; }

  function levelInfo(totalExp) {
    let level = 1;
    let remaining = Math.max(0, totalExp);
    while (remaining >= levelThreshold(level)) {
      remaining -= levelThreshold(level);
      level += 1;
    }
    const forNext = levelThreshold(level);
    return { level, into: remaining, forNext, pct: Math.round((remaining / forNext) * 100) };
  }

  function attrValue(exp) { return Math.floor(Math.sqrt(Math.max(0, exp))); }

  // Seven attribute levels, each a rainbow colour (赤橙黄绿青蓝紫). Level is
  // derived from attribute exp so every task completion visibly fills the bar,
  // and crossing a tier changes the colour.
  const RAINBOW = ["#ff5a5a", "#ff9f43", "#ffd93d", "#4ade80", "#34c8ff", "#5b8cff", "#c264ff"];
  const ATTR_EXP_PER_LEVEL = 300;
  function attrLevelInfo(exp) {
    exp = Math.max(0, exp || 0);
    const raw = exp / ATTR_EXP_PER_LEVEL;
    const level = Math.min(7, Math.floor(raw) + 1);
    const radar = Math.min(7, 1 + raw); // 1..7 continuous, drives the radar shape
    const within = level >= 7 ? 1 : (exp - (level - 1) * ATTR_EXP_PER_LEVEL) / ATTR_EXP_PER_LEVEL;
    return { level: level, radar: radar, progress: Math.round(within * 100), color: RAINBOW[level - 1] };
  }

  function forestStage(growth) {
    if (growth <= 0) return "种子";
    if (growth < 4) return "萌芽";
    if (growth < 10) return "树苗";
    if (growth < 20) return "小林";
    return "森林";
  }

  function $(id) { return document.getElementById(id); }

  // --------------------------------- render ---------------------------------
  function renderHeader() {
    document.body.setAttribute("data-theme", (state.character && state.character.theme) || "default");
    const lvl = levelInfo(state.total_exp);
    $("character-name").textContent = state.character.name;
    $("level-badge").textContent = "Lv." + lvl.level;
    $("exp-text").textContent = lvl.into + " / " + lvl.forNext;
    $("exp-fill").style.width = Math.min(100, lvl.pct) + "%";
    $("magic-points").textContent = state.magic_points;
    // Show the small yellow "Mock" badge only when not running live (no GLM key).
    $("mock-badge").hidden = !!(state.model && state.model.live);
    if (window.avatarSvg) {
      $("sys-avatar").innerHTML = window.avatarSvg((state.character && state.character.avatar) || "cyber");
    }
  }

  function renderRadar() {
    const infos = ATTRS.map((a) => Object.assign({ label: a.label }, attrLevelInfo(state.attributes[a.key].exp)));
    const MAX = 7;
    const cx = 100, cy = 100, R = 70;
    const n = infos.length;
    const ang = (i) => ((-90 + (i * 360) / n) * Math.PI) / 180;
    const pt = (i, r) => [(cx + Math.cos(ang(i)) * r).toFixed(1), (cy + Math.sin(ang(i)) * r).toFixed(1)];

    let svg = "";
    [0.25, 0.5, 0.75, 1].forEach((ring) => {
      const pts = infos.map((_, i) => pt(i, R * ring).join(",")).join(" ");
      svg += '<polygon class="radar-grid-line" points="' + pts + '" />';
    });
    infos.forEach((_, i) => {
      const [x, y] = pt(i, R);
      svg += '<line class="radar-axis" x1="' + cx + '" y1="' + cy + '" x2="' + x + '" y2="' + y + '" />';
    });
    const areaPts = infos.map((v, i) => pt(i, R * (v.radar / MAX)).join(",")).join(" ");
    svg += '<polygon class="radar-area" points="' + areaPts + '" />';
    infos.forEach((v, i) => {
      const [x, y] = pt(i, R * (v.radar / MAX));
      svg += '<circle r="3" cx="' + x + '" cy="' + y + '" fill="' + v.color + '" stroke="#0b1220" stroke-width="1" />';
    });
    infos.forEach((v, i) => {
      const [x, y] = pt(i, R + 16);
      svg += '<text class="radar-label" x="' + x + '" y="' + y + '" text-anchor="middle" dominant-baseline="middle">' + v.label + "</text>";
    });
    $("radar-svg").innerHTML = svg;

    const legend = infos
      .map((v) =>
        '<div class="attr-row"><span class="attr-name">' + v.label + "</span>" +
        '<span class="attr-track"><span class="attr-fill" style="width:' + v.progress + "%;background:" + v.color +
        ";box-shadow:0 0 8px " + v.color + '"></span></span>' +
        '<span class="attr-lv" style="color:' + v.color + ";border-color:" + v.color + '">Lv.' + v.level + "</span></div>"
      )
      .join("");
    $("attr-legend").innerHTML = legend;
  }

  function renderForest() {
    const growth = state.forest.growth;
    $("forest-stage").textContent = forestStage(growth);
    $("forest-growth-text").textContent = "生长度 " + growth;

    const hasStarry = state.forest.decorations.some((d) => d.id === "starry");
    $("forest-sky").innerHTML = (hasStarry ? "✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧" : "✦ ✧ ✦ ✧ ✦ ✧")
      .split(" ").map((c) => "<span>" + c + "</span>").join("");

    const treeCount = Math.max(0, Math.min(growth, 26));
    let trees = "";
    for (let i = 0; i < treeCount; i++) {
      const last = pendingTreePop && i === treeCount - 1;
      trees += '<span class="tree' + (last ? " pop" : "") + '">' + TREE_EMOJI[i % TREE_EMOJI.length] + "</span>";
    }
    const decos = state.forest.decorations
      .map((d) => '<span class="deco" title="' + d.label + '">' + (DECO_EMOJI[d.id] || "🌟") + "</span>")
      .join("");
    $("forest-ground").innerHTML = trees + decos;
    pendingTreePop = false;
  }

  function renderQuests() {
    $("quest-list").innerHTML = state.quest_lines
      .map((q) => {
        const kindLabel = q.kind === "main" ? "主线" : "支线";
        return (
          '<div class="quest"><div class="quest-head">' +
          '<span class="quest-title">' + q.title + "</span>" +
          '<span class="quest-kind ' + q.kind + '">' + kindLabel + "</span></div>" +
          '<div class="quest-track"><div class="quest-fill" style="width:' + q.progress_percent + '%"></div></div>' +
          '<div class="quest-pct">' + q.progress_percent + "%</div></div>"
        );
      })
      .join("");
  }

  function renderTasks() {
    const tasks = state.today_tasks;
    const remaining = tasks.filter((t) => t.status !== "done").length;
    $("today-count").textContent = remaining + " 项待完成 / 共 " + tasks.length + " 项";

    if (!tasks.length) {
      $("task-list").innerHTML = '<p class="muted">今日暂无任务。</p>';
      return;
    }
    $("task-list").innerHTML = tasks
      .map((t) => {
        const r = t.rewards || {};
        const attrLabel = (ATTRS.find((a) => a.key === r.attribute) || {}).label || "";
        const badges =
          '<span class="reward-badge exp">经验 +' + (r.exp || 0) + "</span>" +
          '<span class="reward-badge magic">✦ +' + (r.magic_points || 0) + "</span>" +
          (attrLabel ? '<span class="reward-badge attr">' + attrLabel + " +" + (r.attribute_exp || 0) + "</span>" : "");
        const done = t.status === "done";
        const btn = done
          ? '<button class="task-do" disabled>已完成</button>'
          : '<button class="task-do" data-task="' + t.id + '">完成</button>';
        return (
          '<div class="sys-task' + (done ? " done" : "") + '">' +
          '<div class="task-main"><div class="task-name">' + t.title + "</div>" +
          '<div class="reward-row">' + badges + "</div></div>" + btn + "</div>"
        );
      })
      .join("");

    $("task-list").querySelectorAll("button[data-task]").forEach((b) => {
      b.addEventListener("click", () => completeTask(b.getAttribute("data-task")));
    });
  }

  function renderDings() {
    $("ding-feed").innerHTML = state.recent_dings
      .map((d) => '<div class="ding-item"><span class="at">' + d.at + "</span><span>" + d.text + "</span></div>")
      .join("");
  }

  function renderAll() {
    renderHeader();
    renderRadar();
    renderForest();
    renderQuests();
    renderTasks();
    renderDings();
  }

  // ------------------------------ interaction -------------------------------
  function nowHHMM() {
    const d = new Date();
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  async function completeTask(taskId) {
    const task = state.today_tasks.find((t) => t.id === taskId);
    if (!task || task.status === "done") return;
    try {
      const res = await fetch("/api/system/tasks/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId }),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (!data.ok) throw new Error((data.error && data.error.message) || "settle failed");
      const s = data.settlement || {};
      pendingTreePop = true;
      await loadSummary(); // re-render from persisted server state
      const big = s.leveled_up ? "升级！ Lv." + s.level : "叮！";
      const sub = (s.ding_text || "").replace(/^叮！/, "") || task.title;
      showDingBurst(big, sub);
      if (s.leveled_up) {
        $("level-badge").classList.add("levelup-flash");
        setTimeout(() => $("level-badge").classList.remove("levelup-flash"), 1300);
      }
    } catch (err) {
      console.warn("[system] complete via API failed, optimistic local update:", err);
      settleLocally(taskId);
    }
  }

  // Offline/dev fallback: optimistic client-side settlement (not persisted).
  function settleLocally(taskId) {
    const task = state.today_tasks.find((t) => t.id === taskId);
    if (!task || task.status === "done") return;

    const before = levelInfo(state.total_exp).level;
    const r = task.rewards || {};
    task.status = "done";
    state.total_exp += r.exp || 0;
    state.magic_points += r.magic_points || 0;
    if (r.attribute && state.attributes[r.attribute]) {
      state.attributes[r.attribute].exp += r.attribute_exp || 0;
    }
    state.forest.growth += 1;
    pendingTreePop = true;

    const attrLabel = (ATTRS.find((a) => a.key === r.attribute) || {}).label || "";
    const dingText =
      "叮！宿主完成「" + task.title + "」，经验 +" + (r.exp || 0) +
      "，✦ +" + (r.magic_points || 0) + (attrLabel ? "，" + attrLabel + " ↑" : "");
    state.recent_dings.unshift({ at: nowHHMM(), text: dingText });

    const after = levelInfo(state.total_exp).level;
    const leveledUp = after > before;

    renderAll();
    showDingBurst(leveledUp ? "升级！ Lv." + after : "叮！", dingText.replace(/^叮！/, ""));
    if (leveledUp) $("level-badge").classList.add("levelup-flash");
    setTimeout(() => $("level-badge").classList.remove("levelup-flash"), 1300);
  }

  function showDingBurst(big, sub) {
    const overlay = $("ding-overlay");
    overlay.innerHTML = '<div class="ding-burst"><span class="big">' + big + '</span><span class="sub">' + sub + "</span></div>";
    overlay.hidden = false;
    clearTimeout(showDingBurst._t);
    showDingBurst._t = setTimeout(() => { overlay.hidden = true; overlay.innerHTML = ""; }, 1500);
  }

  function showToast(text) {
    const toast = $("toast");
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { toast.hidden = true; }, 2400);
  }

  // ----------------------------- live data load -----------------------------
  function applySummary(data) {
    if (data.character) state.character = data.character;
    if (data.level && typeof data.level.total_exp === "number") state.total_exp = data.level.total_exp;
    if (typeof data.magic_points === "number") state.magic_points = data.magic_points;
    if (Array.isArray(data.attributes)) {
      data.attributes.forEach((a) => {
        if (a && a.key && state.attributes[a.key]) state.attributes[a.key] = { exp: a.exp || 0 };
      });
    }
    if (data.forest) {
      state.forest = { growth: data.forest.growth || 0, decorations: data.forest.decorations || [] };
    }
    if (Array.isArray(data.quest_lines)) state.quest_lines = data.quest_lines;
    if (Array.isArray(data.today_tasks)) state.today_tasks = data.today_tasks;
    if (Array.isArray(data.recent_dings)) state.recent_dings = data.recent_dings;
    if (data.model) state.model = data.model;
    if (data.shop) state.shop = data.shop;
  }

  async function loadSummary() {
    try {
      const res = await fetch("/api/system/summary", { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (!data || data.ok === false) throw new Error("bad payload");
      applySummary(data);
    } catch (err) {
      // Offline / dev fallback: keep the embedded stub so the panel still renders.
      console.warn("[system] /api/system/summary unavailable, using embedded stub:", err);
    }
    renderAll();
  }

  // ----------------------------- system quest -------------------------------
  function rewardBadges(r) {
    r = r || {};
    const attrLabel = (ATTRS.find((a) => a.key === r.attribute) || {}).label || "";
    return (
      '<span class="reward-badge exp">经验 +' + (r.exp || 0) + "</span>" +
      '<span class="reward-badge magic">✦ +' + (r.magic_points || 0) + "</span>" +
      (attrLabel ? '<span class="reward-badge attr">' + attrLabel + " +" + (r.attribute_exp || 0) + "</span>" : "")
    );
  }

  async function generateQuest() {
    const btn = $("quest-gen-btn");
    btn.disabled = true;
    btn.textContent = "系统生成中…";
    try {
      const avoid = proposedTitles.concat((state.today_tasks || []).map((t) => t.title).filter(Boolean));
      const res = await fetch("/api/system/quest/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avoid: avoid }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error((data.error && data.error.message) || "生成失败");
      renderProposal(data.quest, data.source);
    } catch (err) {
      showToast("生成任务失败：" + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "✦ 系统生成任务";
    }
  }

  function clearProposal() {
    const box = $("quest-proposal");
    box.hidden = true;
    box.innerHTML = "";
    proposedTitles = [];
    currentProposal = null;
  }

  function renderProposal(quest, source) {
    currentProposal = quest;
    const box = $("quest-proposal");
    const srcLabel = source === "llm" ? "系统（GLM）生成" : "系统生成";
    box.innerHTML =
      '<div class="qp-voice">' + (quest.system_voice || "") + "</div>" +
      '<div class="qp-title">' + quest.title + "</div>" +
      '<div class="reward-row">' + rewardBadges(quest.rewards) + "</div>" +
      '<div class="qp-actions">' +
      '<button class="qp-accept" id="qp-accept" type="button">接受任务</button>' +
      '<button id="qp-regen" type="button">换一个</button>' +
      '<button id="qp-cancel" type="button">取消</button>' +
      "</div>" +
      '<div class="qp-source">来源：' + srcLabel + "</div>";
    box.hidden = false;
    $("qp-accept").addEventListener("click", () => acceptQuest(quest));
    $("qp-regen").addEventListener("click", () => {
      if (currentProposal && currentProposal.title) proposedTitles.push(currentProposal.title);
      generateQuest();
    });
    $("qp-cancel").addEventListener("click", clearProposal);
  }

  async function acceptQuest(quest) {
    try {
      const res = await fetch("/api/system/quest/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quest: quest }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error((data.error && data.error.message) || "接受失败");
      clearProposal();
      await loadSummary();
      showToast("叮！任务已加入今日清单");
    } catch (err) {
      showToast("接受任务失败：" + err.message);
    }
  }

  // ----------------------------- shop / avatar ------------------------------
  function openShop() {
    renderShopGrid();
    $("shop-magic").textContent = state.magic_points;
    $("shop-modal").hidden = false;
  }

  function closeShop() {
    $("shop-modal").hidden = true;
  }

  function renderShopGrid() {
    const avatars = (state.shop && state.shop.avatars) || [];
    $("avatar-grid").innerHTML = avatars
      .map((a) => {
        let status;
        let btn;
        if (a.equipped) {
          status = '<span class="av-tag equipped">已装备</span>';
          btn = "<button disabled>当前形象</button>";
        } else if (a.unlocked) {
          status = '<span class="av-tag owned">已解锁</span>';
          btn = '<button class="av-equip" data-av="' + a.id + '">装备</button>';
        } else {
          status = '<span class="av-tag cost">✦ ' + a.cost + "</span>";
          btn = '<button class="av-equip" data-av="' + a.id + '">解锁 ✦' + a.cost + "</button>";
        }
        return (
          '<div class="avatar-tile' + (a.equipped ? " is-equipped" : "") + '">' +
          '<div class="av-art">' + (window.avatarSvg ? window.avatarSvg(a.id) : "") + "</div>" +
          '<div class="av-name">' + a.name + "</div>" +
          status +
          btn +
          "</div>"
        );
      })
      .join("");
    $("avatar-grid").querySelectorAll("button[data-av]").forEach((b) => {
      b.addEventListener("click", () => setAvatar(b.getAttribute("data-av")));
    });
  }

  async function setAvatar(avatarId) {
    try {
      const res = await fetch("/api/system/avatar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar_id: avatarId }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error((data.error && data.error.message) || "操作失败");
      await loadSummary(); // refresh equipped avatar + magic points + shop flags
      renderShopGrid();
      $("shop-magic").textContent = state.magic_points;
      showToast(data.purchased ? "叮！已解锁并装备新形象 ✦" : "已切换系统形象");
    } catch (err) {
      showToast(err.message);
    }
  }

  // --------------------------------- init -----------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    $("shop-btn").addEventListener("click", openShop);
    $("shop-close").addEventListener("click", closeShop);
    $("shop-modal").addEventListener("click", (e) => { if (e.target.id === "shop-modal") closeShop(); });
    $("quest-gen-btn").addEventListener("click", () => { proposedTitles = []; generateQuest(); });
    loadSummary();
  });
})();
