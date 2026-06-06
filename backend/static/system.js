/* System Edition panel — Phase 1 of the hosted beta: browser-side data.
 *
 * localStorage is the single source of truth (no server needed for data). All
 * logic runs client-side: completion settlement, level/attribute/forest, the
 * cosmetics shop, and rule-based quest generation + template narration. The GLM
 * brain (live quests/narration via a thin proxy) arrives in Phase 2.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "personal_agent_system_v1";

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
  const RAINBOW = ["#ff5a5a", "#ff9f43", "#ffd93d", "#4ade80", "#34c8ff", "#5b8cff", "#c264ff"];
  const ATTR_EXP_PER_LEVEL = 300;

  // Avatar catalog (mirrors backend AVATARS; SVGs in system_avatars.js).
  const AVATAR_CATALOG = [
    { id: "cyber", name: "赛博少女", cost: 0 },
    { id: "genki", name: "元气少女", cost: 60 },
    { id: "cool", name: "冷静系", cost: 80 },
    { id: "elf", name: "精灵系", cost: 120 },
  ];

  const RULE_TEMPLATES = [
    "推进「{t}」：完成一个 25 分钟专注块",
    "为「{t}」做一件最小但具体的小事",
    "围绕「{t}」复盘 5 分钟，并记下一条心得",
    "在「{t}」上前进一小步，哪怕只用 15 分钟",
    "为「{t}」整理一个清晰的下一步",
  ];
  const ATTR_KEYWORDS = [
    ["constitution", ["跑", "运动", "健身", "锻炼", "步", "睡", "健康"]],
    ["creativity", ["写", "项目", "建造", "代码", "设计", "创作", "渲染", "面板", "做"]],
    ["spirit", ["反思", "冥想", "休息", "复盘", "日记", "放松", "整理"]],
    ["intellect", ["英语", "单词", "学习", "阅读", "读", "复习", "句子", "知识", "课"]],
  ];

  // Phase 2: GLM proxy (Cloudflare Worker). Override via localStorage "proxy_url";
  // empty -> pure rule mode (no GLM).
  const DEFAULT_PROXY_URL = "https://glm-proxy.1421608856.workers.dev/";
  function proxyUrl() {
    try { return localStorage.getItem("proxy_url") || DEFAULT_PROXY_URL; } catch (e) { return DEFAULT_PROXY_URL; }
  }
  const QUEST_SYSTEM_PROMPT = [
    "你是绑定在宿主身上的专属「系统」——像网络小说里的那种「系统」：温暖、鼓励、带一点游戏仪式感，称用户为「宿主」。",
    "你根据宿主的长期计划和已有任务，提出 ONE 个今天就能完成的最小任务（quest）。",
    "硬性要求：",
    "- 必须用简体中文输出 title 和 system_voice。",
    "- 任务要小、具体、今天能完成（约 15-30 分钟），且要新颖，不要重复已有任务。",
    "- 只输出一个 JSON 对象，不要任何额外文字或解释。",
    "- JSON 字段：title(字符串), attribute(intellect/constitution/willpower/creativity/spirit 之一), exp(整数5-30), magic_points(整数3-15), attribute_exp(整数10-40), system_voice(一句简体中文系统口吻台词，可用「叮！」开头)。",
    "语气温暖鼓励，绝不惩罚或施压。",
  ].join("\n");

  // Phase 3: external collectors (e.g. Formspree) for the beta email list + feedback.
  // Server stores nothing; empty = skip network (entry/feedback still work locally).
  // Set per deployment, or override in console: localStorage.setItem("signup_url", "https://formspree.io/f/xxxx").
  const REGISTERED_KEY = "pa_registered";
  const DEFAULT_SIGNUP_URL = "";
  const DEFAULT_FEEDBACK_URL = "";
  function signupUrl() { try { return localStorage.getItem("signup_url") || DEFAULT_SIGNUP_URL; } catch (e) { return DEFAULT_SIGNUP_URL; } }
  function feedbackUrl() { try { return localStorage.getItem("feedback_url") || DEFAULT_FEEDBACK_URL; } catch (e) { return DEFAULT_FEEDBACK_URL; } }

  // Fresh starting state for a new tester (level 1, two starter plans).
  const SEED = {
    character: { name: "系统", theme: "default", avatar: "cyber" },
    total_exp: 0,
    magic_points: 0,
    attributes: { intellect: { exp: 0 }, constitution: { exp: 0 }, willpower: { exp: 0 }, creativity: { exp: 0 }, spirit: { exp: 0 } },
    forest: { growth: 0, decorations: [] },
    unlocked_cosmetics: [],
    quest_lines: [
      { plan_id: "plan_growth", title: "成为更好的自己", kind: "main", progress_percent: 0 },
      { plan_id: "plan_health", title: "保持健康", kind: "side", progress_percent: 0 },
    ],
    today_tasks: [],
    recent_dings: [{ at: "现在", text: "叮！欢迎宿主。完成任务可获得经验与魔法点，让森林生长、在商城解锁外形。" }],
  };

  let state = null;
  let pendingTreePop = false;
  let proposedTitles = [];
  let currentProposal = null;

  function $(id) { return document.getElementById(id); }

  // ----------------------------- persistence --------------------------------
  function mergeSeed(s) {
    s = s && typeof s === "object" ? s : {};
    s.character = Object.assign({ name: "系统", theme: "default", avatar: "cyber" }, s.character || {});
    s.total_exp = s.total_exp || 0;
    s.magic_points = s.magic_points || 0;
    s.attributes = s.attributes || {};
    ATTRS.forEach((a) => { if (!s.attributes[a.key] || typeof s.attributes[a.key].exp !== "number") s.attributes[a.key] = { exp: (s.attributes[a.key] || {}).exp || 0 }; });
    s.forest = Object.assign({ growth: 0, decorations: [] }, s.forest || {});
    s.unlocked_cosmetics = Array.isArray(s.unlocked_cosmetics) ? s.unlocked_cosmetics : [];
    s.quest_lines = Array.isArray(s.quest_lines) && s.quest_lines.length ? s.quest_lines : JSON.parse(JSON.stringify(SEED.quest_lines));
    s.today_tasks = Array.isArray(s.today_tasks) ? s.today_tasks : [];
    s.recent_dings = Array.isArray(s.recent_dings) ? s.recent_dings : [];
    return s;
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return mergeSeed(JSON.parse(raw));
    } catch (e) {
      console.warn("[system] loadState failed, using seed:", e);
    }
    return JSON.parse(JSON.stringify(SEED));
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn("[system] saveState failed:", e);
    }
  }

  // ------------------------------ derivations -------------------------------
  function levelThreshold(level) { return 100 + (Math.max(1, level) - 1) * 50; }
  function levelInfo(totalExp) {
    let level = 1;
    let remaining = Math.max(0, totalExp || 0);
    while (remaining >= levelThreshold(level)) { remaining -= levelThreshold(level); level += 1; }
    const forNext = levelThreshold(level);
    return { level: level, into: remaining, forNext: forNext, pct: forNext ? Math.round((remaining / forNext) * 100) : 0 };
  }
  function attrLevelInfo(exp) {
    exp = Math.max(0, exp || 0);
    const raw = exp / ATTR_EXP_PER_LEVEL;
    const level = Math.min(7, Math.floor(raw) + 1);
    const radar = Math.min(7, 1 + raw);
    const within = level >= 7 ? 1 : (exp - (level - 1) * ATTR_EXP_PER_LEVEL) / ATTR_EXP_PER_LEVEL;
    return { level: level, radar: radar, progress: Math.round(within * 100), color: RAINBOW[level - 1] };
  }
  function forestStage(growth) {
    growth = Math.max(0, growth || 0);
    if (growth <= 0) return "种子";
    if (growth < 4) return "萌芽";
    if (growth < 10) return "树苗";
    if (growth < 20) return "小林";
    return "森林";
  }
  function inferAttribute(text) {
    text = text || "";
    for (let i = 0; i < ATTR_KEYWORDS.length; i++) {
      const attr = ATTR_KEYWORDS[i][0];
      if (ATTR_KEYWORDS[i][1].some((k) => text.indexOf(k) >= 0)) return attr;
    }
    return "willpower";
  }
  function defaultRewards(title, plan) {
    return { exp: 10, magic_points: 5, attribute: inferAttribute(title + " " + ((plan && plan.title) || "")), attribute_exp: 15 };
  }
  function nowHHMM() {
    const d = new Date();
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  // --------------------------------- render ---------------------------------
  function renderHeader() {
    document.body.setAttribute("data-theme", (state.character && state.character.theme) || "default");
    const lvl = levelInfo(state.total_exp);
    $("character-name").textContent = state.character.name;
    $("level-badge").textContent = "Lv." + lvl.level;
    $("exp-text").textContent = lvl.into + " / " + lvl.forNext;
    $("exp-fill").style.width = Math.min(100, lvl.pct) + "%";
    $("magic-points").textContent = state.magic_points;
    $("mock-badge").hidden = true; // Phase 1 is intentionally local; badge returns with GLM in Phase 2.
    if (window.avatarSvg) $("sys-avatar").innerHTML = window.avatarSvg((state.character && state.character.avatar) || "cyber");
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

    $("attr-legend").innerHTML = infos
      .map((v) =>
        '<div class="attr-row"><span class="attr-name">' + v.label + "</span>" +
        '<span class="attr-track"><span class="attr-fill" style="width:' + v.progress + "%;background:" + v.color +
        ";box-shadow:0 0 8px " + v.color + '"></span></span>' +
        '<span class="attr-lv" style="color:' + v.color + ";border-color:" + v.color + '">Lv.' + v.level + "</span></div>"
      )
      .join("");
  }

  function renderForest() {
    const growth = state.forest.growth;
    $("forest-stage").textContent = forestStage(growth);
    $("forest-growth-text").textContent = "生长度 " + growth;
    const hasStarry = state.forest.decorations.some((d) => d.id === "starry");
    $("forest-sky").innerHTML = (hasStarry ? "✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧" : "✦ ✧ ✦ ✧ ✦ ✧").split(" ").map((c) => "<span>" + c + "</span>").join("");
    const treeCount = Math.max(0, Math.min(growth, 26));
    let trees = "";
    for (let i = 0; i < treeCount; i++) {
      const last = pendingTreePop && i === treeCount - 1;
      trees += '<span class="tree' + (last ? " pop" : "") + '">' + TREE_EMOJI[i % TREE_EMOJI.length] + "</span>";
    }
    const decos = state.forest.decorations.map((d) => '<span class="deco" title="' + d.label + '">' + (DECO_EMOJI[d.id] || "🌟") + "</span>").join("");
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
          '<div class="quest-track"><div class="quest-fill" style="width:' + (q.progress_percent || 0) + '%"></div></div>' +
          '<div class="quest-pct">' + (q.progress_percent || 0) + "%</div></div>"
        );
      })
      .join("");
  }

  function rewardBadges(r) {
    r = r || {};
    const attrLabel = (ATTRS.find((a) => a.key === r.attribute) || {}).label || "";
    return (
      '<span class="reward-badge exp">经验 +' + (r.exp || 0) + "</span>" +
      '<span class="reward-badge magic">✦ +' + (r.magic_points || 0) + "</span>" +
      (attrLabel ? '<span class="reward-badge attr">' + attrLabel + " +" + (r.attribute_exp || 0) + "</span>" : "")
    );
  }

  function renderTasks() {
    const tasks = state.today_tasks;
    const remaining = tasks.filter((t) => t.status !== "done").length;
    $("today-count").textContent = remaining + " 项待完成 / 共 " + tasks.length + " 项";
    if (!tasks.length) {
      $("task-list").innerHTML = '<p class="muted">今日暂无任务。点「✦ 系统生成任务」开始。</p>';
      return;
    }
    $("task-list").innerHTML = tasks
      .map((t) => {
        const done = t.status === "done";
        const btn = done ? '<button class="task-do" disabled>已完成</button>' : '<button class="task-do" data-task="' + t.id + '">完成</button>';
        return (
          '<div class="sys-task' + (done ? " done" : "") + '">' +
          '<div class="task-main"><div class="task-name">' + t.title + "</div>" +
          '<div class="reward-row">' + rewardBadges(t.rewards) + "</div></div>" + btn + "</div>"
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
  function completeTask(taskId) {
    const task = state.today_tasks.find((t) => t.id === taskId);
    if (!task || task.status === "done") return;

    const before = levelInfo(state.total_exp).level;
    const r = task.rewards || defaultRewards(task.title, {});
    task.status = "done";
    state.total_exp += r.exp || 0;
    state.magic_points += r.magic_points || 0;
    if (r.attribute && state.attributes[r.attribute]) state.attributes[r.attribute].exp += r.attribute_exp || 0;
    state.forest.growth += 1;
    pendingTreePop = true;

    const after = levelInfo(state.total_exp).level;
    const leveledUp = after > before;
    const attrLabel = (ATTRS.find((a) => a.key === r.attribute) || {}).label || "";
    let text = "叮！宿主完成「" + task.title + "」，经验 +" + (r.exp || 0) + "，✦ +" + (r.magic_points || 0);
    if (attrLabel) text += "，" + attrLabel + " ↑";
    if (leveledUp) text += "（升级！Lv." + after + "）";
    state.recent_dings.unshift({ at: nowHHMM(), text: text });
    state.recent_dings = state.recent_dings.slice(0, 12);

    saveState();
    renderAll();
    showDingBurst(leveledUp ? "升级！ Lv." + after : "叮！", text.replace(/^叮！/, ""));
    if (leveledUp) {
      $("level-badge").classList.add("levelup-flash");
      setTimeout(() => $("level-badge").classList.remove("levelup-flash"), 1300);
    }
  }

  // ----------------------------- system quest -------------------------------
  function ruleQuest(plan, avoid) {
    avoid = avoid || [];
    const options = RULE_TEMPLATES.map((tpl) => tpl.replace("{t}", plan.title));
    const title = options.find((o) => avoid.indexOf(o) < 0) || options[Math.floor(Math.random() * options.length)];
    return {
      plan_id: plan.plan_id,
      title: title,
      rewards: defaultRewards(title, plan),
      system_voice: "叮！宿主，今日推荐任务：" + title + "。完成它，离目标更近一步。",
    };
  }

  function extractJson(text) {
    text = (text || "").trim();
    const fenced = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
    if (fenced) return fenced[1];
    const m = text.match(/\{[\s\S]*\}/);
    return m ? m[0] : null;
  }
  function clampInt(v, lo, hi, def) {
    const n = parseInt(v, 10);
    return isNaN(n) ? def : Math.max(lo, Math.min(n, hi));
  }
  function parseQuest(answer, plan) {
    const cand = extractJson(answer);
    if (!cand) return null;
    let d;
    try { d = JSON.parse(cand); } catch (e) { return null; }
    if (!d || typeof d !== "object") return null;
    const title = String(d.title || "").trim();
    if (!title) return null;
    let attr = d.attribute;
    if (!ATTRS.some((a) => a.key === attr)) attr = inferAttribute(title + " " + plan.title);
    return {
      plan_id: plan.plan_id,
      title: title,
      rewards: {
        exp: clampInt(d.exp, 5, 30, 10),
        magic_points: clampInt(d.magic_points, 3, 15, 5),
        attribute: attr,
        attribute_exp: clampInt(d.attribute_exp, 10, 40, 15),
      },
      system_voice: String(d.system_voice || "").trim() || ("叮！宿主，今日推荐任务：" + title + "。"),
    };
  }
  function questUserPrompt(plan, avoid) {
    const lines = ["长期计划：" + plan.title, "进度：" + (plan.progress_percent || 0) + "%"];
    const skip = (state.today_tasks || []).map((t) => t.title).filter(Boolean).slice(-8).concat(avoid || []);
    if (skip.length) {
      lines.push("", "宿主最近已有的任务，请【不要重复】，换一个不同角度：");
      skip.slice(0, 12).forEach((t) => lines.push("- " + t));
    }
    lines.push("", "请按要求只返回一个 JSON 对象。");
    return lines.join("\n");
  }

  // Try the GLM proxy (Cloudflare Worker); fall back to a rule quest on any failure.
  async function llmQuest(plan, avoid) {
    const url = proxyUrl();
    if (!url) return { quest: ruleQuest(plan, avoid), source: "mock" };
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [
            { role: "system", content: QUEST_SYSTEM_PROMPT },
            { role: "user", content: questUserPrompt(plan, avoid) },
          ],
          thinking: { type: "disabled" },
          max_tokens: 600,
          temperature: 0.9,
        }),
      });
      const data = await res.json();
      if (!data || !data.ok || !data.answer) throw new Error("proxy not ok");
      const parsed = parseQuest(data.answer, plan);
      if (!parsed) throw new Error("unparseable quest");
      return { quest: parsed, source: "llm" };
    } catch (e) {
      console.warn("[system] GLM quest failed, rule fallback:", e);
      return { quest: ruleQuest(plan, avoid), source: "mock" };
    }
  }

  async function generateQuest() {
    if (!state.quest_lines || !state.quest_lines.length) { showToast("还没有长期计划"); return; }
    const avoid = proposedTitles.concat((state.today_tasks || []).map((t) => t.title).filter(Boolean));
    const plan = state.quest_lines[Math.floor(Math.random() * state.quest_lines.length)];
    const btn = $("quest-gen-btn");
    btn.disabled = true;
    btn.textContent = "系统生成中…";
    try {
      const result = await llmQuest(plan, avoid);
      renderProposal(result.quest, result.source);
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

  function acceptQuest(quest) {
    const task = {
      id: "task_" + Date.now() + "_" + Math.floor(Math.random() * 1000),
      plan_id: quest.plan_id,
      title: quest.title,
      status: "todo",
      rewards: quest.rewards,
    };
    state.today_tasks.push(task);
    saveState();
    clearProposal();
    renderAll();
    showToast("已加入今日清单");
  }

  // ----------------------------- shop / avatar ------------------------------
  function openShop() {
    renderShopGrid();
    $("shop-magic").textContent = state.magic_points;
    $("shop-modal").hidden = false;
  }
  function closeShop() { $("shop-modal").hidden = true; }

  function renderShopGrid() {
    const equipped = state.character.avatar;
    $("avatar-grid").innerHTML = AVATAR_CATALOG
      .map((a) => {
        const unlocked = a.cost === 0 || state.unlocked_cosmetics.indexOf(a.id) >= 0;
        const isEquipped = a.id === equipped;
        let status;
        let btn;
        if (isEquipped) {
          status = '<span class="av-tag equipped">已装备</span>';
          btn = "<button disabled>当前形象</button>";
        } else if (unlocked) {
          status = '<span class="av-tag owned">已解锁</span>';
          btn = '<button class="av-equip" data-av="' + a.id + '">装备</button>';
        } else {
          status = '<span class="av-tag cost">✦ ' + a.cost + "</span>";
          btn = '<button class="av-equip" data-av="' + a.id + '">解锁 ✦' + a.cost + "</button>";
        }
        return (
          '<div class="avatar-tile' + (isEquipped ? " is-equipped" : "") + '">' +
          '<div class="av-art">' + (window.avatarSvg ? window.avatarSvg(a.id) : "") + "</div>" +
          '<div class="av-name">' + a.name + "</div>" + status + btn + "</div>"
        );
      })
      .join("");
    $("avatar-grid").querySelectorAll("button[data-av]").forEach((b) => {
      b.addEventListener("click", () => setAvatar(b.getAttribute("data-av")));
    });
  }

  function setAvatar(avatarId) {
    const avatar = AVATAR_CATALOG.find((a) => a.id === avatarId);
    if (!avatar) return;
    const unlocked = avatar.cost === 0 || state.unlocked_cosmetics.indexOf(avatar.id) >= 0;
    if (!unlocked) {
      if (state.magic_points < avatar.cost) {
        showToast("魔法点不足：需要 " + avatar.cost + "，现有 " + state.magic_points);
        return;
      }
      state.magic_points -= avatar.cost;
      state.unlocked_cosmetics.push(avatar.id);
      showToast("叮！已解锁并装备新形象 ✦");
    } else {
      showToast("已切换系统形象");
    }
    state.character.avatar = avatar.id;
    saveState();
    renderAll();
    renderShopGrid();
    $("shop-magic").textContent = state.magic_points;
  }

  // -------------------------------- effects ---------------------------------
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

  // ----------------------------- email gate ---------------------------------
  function isRegistered() { try { return !!localStorage.getItem(REGISTERED_KEY); } catch (e) { return false; } }
  function validEmail(s) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s); }

  async function submitGate() {
    const email = ($("gate-email").value || "").trim();
    const err = $("gate-err");
    if (!validEmail(email)) { err.textContent = "请输入有效的邮箱"; err.hidden = false; return; }
    err.hidden = true;
    const btn = $("gate-start");
    btn.disabled = true;
    btn.textContent = "进入中…";
    const url = signupUrl();
    if (url) {
      // Best-effort: record the email to the external collector, never block entry on it.
      try {
        await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ email: email, kind: "beta_signup" }),
        });
      } catch (e) {
        console.warn("[system] signup post failed (entering anyway):", e);
      }
    }
    try { localStorage.setItem(REGISTERED_KEY, email); } catch (e) {}
    btn.disabled = false;
    btn.textContent = "开始内测";
    $("gate-overlay").hidden = true;
  }

  // ------------------------------ feedback ----------------------------------
  function openFeedback() { $("fb-text").value = ""; $("fb-modal").hidden = false; }
  function closeFeedback() { $("fb-modal").hidden = true; }
  async function sendFeedback() {
    const text = ($("fb-text").value || "").trim();
    if (!text) { showToast("写点什么再提交吧"); return; }
    const url = feedbackUrl();
    const payload = {
      kind: "feedback",
      text: text,
      email: (function () { try { return localStorage.getItem(REGISTERED_KEY) || ""; } catch (e) { return ""; } })(),
      level: levelInfo(state.total_exp).level,
    };
    if (url) {
      try {
        await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("感谢反馈！");
      } catch (e) {
        console.warn(e);
        showToast("提交失败，稍后再试");
        return;
      }
    } else {
      showToast("感谢反馈！（未配置收集端点）");
    }
    closeFeedback();
  }

  // --------------------------------- init -----------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    state = loadState();
    $("shop-btn").addEventListener("click", openShop);
    $("shop-close").addEventListener("click", closeShop);
    $("shop-modal").addEventListener("click", (e) => { if (e.target.id === "shop-modal") closeShop(); });
    $("quest-gen-btn").addEventListener("click", () => { proposedTitles = []; generateQuest(); });
    $("fb-btn").addEventListener("click", openFeedback);
    $("fb-close").addEventListener("click", closeFeedback);
    $("fb-send").addEventListener("click", sendFeedback);
    $("fb-modal").addEventListener("click", (e) => { if (e.target.id === "fb-modal") closeFeedback(); });
    $("gate-start").addEventListener("click", submitGate);
    $("gate-email").addEventListener("keydown", (e) => { if (e.key === "Enter") submitGate(); });
    renderAll();
    if (!isRegistered()) $("gate-overlay").hidden = false;
  });
})();
