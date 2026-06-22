// Quest engine v2 — acts, flags, multi-item inventory, objectives, endings.
// The engine owns truth: only whitelisted clue/item/flag ids change state.
window.Quest = (function () {
  const SAVE_KEY = "llmvillage_save_v2";

  const CLUES = {
    clue_blacksmith: { short: "斗篷人影朝北山道去了", from: "老铁" },
    clue_inn:        { short: "陌生旅人用古怪旧币付账", from: "阿珍" },
    clue_mill:       { short: "磨坊旁捡到一把旧钥匙",   from: "小石头" },
  };
  const ITEMS = {
    old_key: "水井旧钥匙", torch: "火把", lit_torch: "点燃的火把",
    map_fragment: "封印残图", herb_charm: "安神草香", sword: "祖传旧剑",
    gem: "湖心宝石", dragon_scale: "赤鳞之鳞",
  };
  const CLUE_IDS = Object.keys(CLUES);

  const ACTS = {
    1: "第一章 · 失窃的钥匙：查清是谁拿走了水井钥匙（集齐 3 条线索并取回钥匙）。",
    2: "第二章 · 山雨欲来：探明赤鳞的来历，去找学士墨白、药婆云娘、哨楼铁柱，并打开北山封印。",
    3: "终章 · 面对赤鳞：进入洞窟——是战，是和，还是智取，由你决定。",
  };
  const ENDINGS = {
    peace: "🕊️ 和解结局：你以诚意打动了赤鳞。巨龙敛去怒火，归还了水井的钥匙，振翅飞向远山。井村重归安宁。",
    trick: "🧠 智取结局：你借残图与古老的封印之力，将赤鳞重新引入沉眠。危机暂解，心结却仍待了结……",
    fight: "⚔️ 决战结局：你举剑直面赤鳞。惊天搏杀之后，村庄保住了，你的名字也被人们传颂多年。",
  };

  let state = { act: 1, clues: {}, inventory: [], flags: {}, ending: null };

  function load() { try { const r = localStorage.getItem(SAVE_KEY); if (r) state = Object.assign(state, JSON.parse(r)); } catch (_) {} }
  function save() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(state)); } catch (_) {} }

  function foundCount() { return CLUE_IDS.filter((id) => state.clues[id]).length; }
  function hasItem(id) { return state.inventory.includes(id); }
  function itemName(id) { return ITEMS[id] || id; }
  function getFlag(n) { return !!state.flags[n]; }

  function init() {
    load(); renderHUD(); renderObjective();
    if (state.ending) showEnding(state.ending, false);
  }

  // ---- mutations (called by NPC dispatch + interactables) ----
  function revealClue(id) {
    if (!CLUES[id] || state.clues[id]) return;
    state.clues[id] = true; save(); toast(`🔍 获得线索：${CLUES[id].short}`); after();
  }
  function addItem(id) {
    if (!ITEMS[id] || hasItem(id)) return false;
    state.inventory.push(id); save(); toast(`🎒 获得物品：${ITEMS[id]}`); after(); return true;
  }
  function removeItem(id) { const i = state.inventory.indexOf(id); if (i >= 0) { state.inventory.splice(i, 1); save(); after(); } }
  function setFlag(n, v) { state.flags[n] = !!v; save(); after(); }
  function met(id) { if (!state.flags["met_" + id]) setFlag("met_" + id, true); }

  function setEnding(kind) {
    if (state.ending || !ENDINGS[kind]) return;
    state.ending = kind;
    if (kind === "peace") { addItem("dragon_scale"); setFlag("key_returned", true); }
    save(); renderHUD(); showEnding(kind, true);
  }

  // ---- action dispatcher: called after every NPC reply ----
  function dispatch(npc, parsed) {
    const action = parsed && parsed.action, arg = (parsed && parsed.arg || "").trim();
    if (action === "reveal_clue") revealClue(arg);
    else if (action === "give_item") addItem(arg);
    else if (action === "move") toast(`${npc.name} 动身了…`);
    else if (action === "trade") toast(`${npc.name} 想做个交换…`);
    else if (action === "end") {
      if (npc.isDragon && ENDINGS[arg]) setEnding(arg);
      return "end";
    }
    return null;
  }

  // advance acts whenever state changes
  function after() {
    if (state.act === 1 && foundCount() >= 3 && hasItem("old_key")) advance(2);
    else if (state.act === 2 && getFlag("cave_open")) advance(3);
    renderHUD(); renderObjective();
  }
  function advance(n) {
    if (state.act >= n) return;
    state.act = n; save();
    banner(`【${ACTS[n].split("：")[0]}】`, ACTS[n].split("：")[1] || "");
  }

  // ---- HUD / objective / banners ----
  function renderObjective() {
    const el = document.getElementById("objective"); if (!el) return;
    el.textContent = state.ending ? "✦ 结局已揭晓" : "目标 · " + ACTS[state.act];
  }
  function renderHUD() {
    const el = document.getElementById("hud"); if (!el) return;
    const clueLines = CLUE_IDS.map((id) => state.clues[id] ? `✔ ${CLUES[id].short}` : `✘ ？？？（问问${CLUES[id].from}）`).join("<br>");
    const items = state.inventory.map((id) => ITEMS[id]);
    el.innerHTML =
      `<b>线索 ${foundCount()}/${CLUE_IDS.length}</b><br>${clueLines}` +
      `<br><b>行囊</b>：${items.length ? items.join("、") : "（空）"}` +
      (getFlag("cave_open") ? "<br><span style='color:#7a5fd0'>封印已开启</span>" : "");
  }

  let toastTimer = null;
  function toast(msg) {
    const el = document.getElementById("toast"); if (!el) return;
    el.textContent = msg; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
  }
  function banner(title, sub) {
    const el = document.getElementById("banner"); if (!el) return;
    el.innerHTML = `<div style="font-size:26px;margin-bottom:8px">${title}</div><div style="font-size:16px;opacity:.9">${sub}</div><div style="font-size:12px;margin-top:18px;opacity:.6">（点击关闭）</div>`;
    el.classList.remove("hidden"); el.onclick = () => el.classList.add("hidden");
  }
  function showEnding(kind, dismissable) {
    const el = document.getElementById("banner"); if (!el) return;
    el.innerHTML = `<div style="font-size:22px;line-height:1.8;max-width:620px">${ENDINGS[kind]}</div>` +
      (dismissable ? `<div style="font-size:12px;margin-top:20px;opacity:.6">（点击关闭 · 谜题完结）</div>` : "");
    el.classList.remove("hidden"); el.onclick = () => el.classList.add("hidden");
  }

  function reset() { state = { act: 1, clues: {}, inventory: [], flags: {}, ending: null }; save(); renderHUD(); renderObjective(); const b = document.getElementById("banner"); if (b) b.classList.add("hidden"); }

  // world-state summary injected into NPC prompts (so dialogue reflects progress)
  function worldStateText() {
    const lines = [`当前章节：${ACTS[state.act].split("：")[0]}`];
    lines.push(`已知线索：${foundCount()}/3`);
    if (getFlag("cave_open")) lines.push("北山封印已被开启。");
    if (getFlag("met_stranger")) lines.push("玩家已见过林中的斗篷客。");
    return lines.join(" ");
  }
  function inventoryText() {
    return state.inventory.length ? state.inventory.map((id) => ITEMS[id]).join("、") : "（看不出他带着什么特别之物）";
  }

  return {
    init, dispatch, reset, renderHUD,
    addItem, removeItem, hasItem, itemName, setFlag, getFlag, met, toast, banner,
    get state() { return state; }, get act() { return state.act; },
    CLUES, ITEMS, worldStateText, inventoryText,
  };
})();
