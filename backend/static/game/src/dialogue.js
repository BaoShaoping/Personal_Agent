// Dialogue overlay: NPC conversations (LLM, with input) + simple object messages (no input).
window.Dialogue = (function () {
  const EMOJI = { neutral: "🙂", happy: "😄", angry: "😠", sad: "😢", afraid: "😨", curious: "🤔" };
  let scene = null, npc = null, busy = false, mode = null, msgKey = null;
  let elRoot, elEmoji, elName, elText, elInput, elSend, elRow;

  const byId = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function init(phaserScene) {
    scene = phaserScene;
    elRoot = byId("dialogue"); elEmoji = byId("dlg-emoji"); elName = byId("dlg-name");
    elText = byId("dlg-text"); elInput = byId("dlg-input"); elSend = byId("dlg-send"); elRow = byId("dlg-input-row");
    elSend.addEventListener("click", submit);
    elInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); submit(); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    });
  }

  function lockKb() { const kb = scene.input.keyboard; kb.enabled = false; if (kb.manager) kb.manager.enabled = false; }
  function unlockKb() { const kb = scene.input.keyboard; if (kb.manager) kb.manager.enabled = true; kb.enabled = true; kb.resetKeys(); }

  // --- NPC conversation (LLM) ---
  function open(target) {
    if (window.DIALOGUE_OPEN) return;
    npc = target; mode = "npc"; window.DIALOGUE_OPEN = true; busy = false;
    if (Quest.met) Quest.met(npc.id);
    lockKb();
    elRow.style.display = "";
    elEmoji.textContent = (npc.sprite && npc.sprite.emoji) || "🙂";
    elName.textContent = npc.name;
    elText.innerHTML = `<div class="npc-line">${esc(npc.greeting)}</div>`;
    elInput.value = ""; elInput.disabled = false;
    elRoot.classList.remove("hidden");
    setTimeout(() => elInput.focus(), 0);
  }

  // --- simple object message (no LLM, no input) ---
  function message(title, body) {
    if (window.DIALOGUE_OPEN && mode === "npc") return; // don't interrupt a conversation
    mode = "message"; window.DIALOGUE_OPEN = true;
    lockKb();
    elRow.style.display = "none";
    elEmoji.textContent = "📜"; elName.textContent = title || "";
    elText.innerHTML = `<div class="npc-line">${esc(body)}</div>` +
      `<div style="margin-top:8px;color:#9bbf9b;font-size:12px">（点击 / 按 Esc / E 关闭）</div>`;
    elRoot.classList.remove("hidden");
    elRoot.addEventListener("click", close);
    msgKey = (e) => { if (["Escape", "e", "E", "Enter", " "].includes(e.key)) { e.preventDefault(); close(); } };
    window.addEventListener("keydown", msgKey);
  }

  function close() {
    if (!window.DIALOGUE_OPEN) return;
    window.DIALOGUE_OPEN = false;
    elRoot.classList.add("hidden");
    elRow.style.display = "";
    if (msgKey) { window.removeEventListener("keydown", msgKey); msgKey = null; }
    elRoot.removeEventListener("click", close);
    npc = null; mode = null;
    unlockKb();
  }

  async function submit() {
    if (busy || !npc || mode !== "npc") return;
    const text = elInput.value.trim(); if (!text) return;
    busy = true; elInput.disabled = true;
    elText.innerHTML = `<div class="player-line">你：${esc(text)}</div>` +
      `<div class="npc-line thinking">（${esc(npc.name)}正在思考…）</div>`;

    const reply = await LLM.getNpcReply(npc, text);
    npc.memory.push({ player: text, npc: reply.say });
    if (npc.memory.length > CONFIG.MEMORY_TURNS) npc.memory.shift();
    npc.emotion = reply.emotion;

    elEmoji.textContent = EMOJI[reply.emotion] || "🙂";
    elText.innerHTML = `<div class="player-line">你：${esc(text)}</div>` +
      `<div class="npc-line">${esc(reply.say)}</div>`;

    const r = Quest.dispatch(npc, reply);
    busy = false; elInput.value = ""; elInput.disabled = false;
    if (reply.action === "end" || r === "end") setTimeout(close, 1500);
    else elInput.focus();
  }

  return { init, open, message, close };
})();
