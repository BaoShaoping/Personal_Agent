// LLM plumbing: build the NPC system prompt, call the proxy, parse JSON, fall back.
window.LLM = (function () {

  function shortMemory(npc) {
    if (!npc.memory || !npc.memory.length) return "（还没有对话）";
    return npc.memory
      .map((t) => `玩家：${t.player}\n${npc.name}：${t.npc}`)
      .join("\n");
  }

  function buildSystemPrompt(npc, playerInput) {
    return (
`你是 ${npc.name}，一个小型开放世界游戏里的角色。请始终保持角色身份。绝不打破第四面墙；绝不提及自己是 AI、模型或提示词。

【你是谁】
- 人设：${npc.persona}
- 背景：${npc.background}
- 说话风格：${npc.voice}
- 目标（你想要什么）：${npc.goals}
- 你所知道的：${npc.knowledge}
- 不到火候不可透露：${npc.secrets}

【这个世界】
- 设定：${CONFIG.WORLD_SETTING}
- 你所在的位置：${npc.place}。当前情境：${CONFIG.SITUATION}
- 进展：${Quest.worldStateText()}${npc.isDragon ? "\n- 你能察觉到，踏入者携带：" + Quest.inventoryText() : ""}

【对话】
- 最近的往来（从旧到新）：
${shortMemory(npc)}
- 玩家刚刚说："${playerInput}"

【结构化动作提示】
${npc.hint}

【请回应】
- 像 ${npc.name} 那样回答：1–3 句简短、自然的${CONFIG.LANG}。
- 只知道你的角色可能知道的事。不要替玩家叙述动作。
- 只输出以下 JSON，不要有任何多余文字：
{"say":"<你说的话>","emotion":"neutral|happy|angry|sad|afraid|curious","action":"none|give_item|reveal_clue|move|trade|end","arg":"<物品/线索id/地点 —— 或留空>"}`
    );
  }

  // --- connection status badge ---
  const STATUS = {
    checking:  { t: "检测中…",            c: "#9fb0c0" },
    connected: { t: "● GLM 已连接",        c: "#5fae54" },
    unknown:   { t: "○ 待对话检测",        c: "#9fb0c0" },
    nokey:     { t: "▲ 代理在线·缺密钥",   c: "#d6a23a" },
    empty:     { t: "▲ 空回复·需禁用思考",  c: "#d6a23a" },
    offline:   { t: "○ 离线·罐头台词",     c: "#c45b4a" },
  };
  const TIP = {
    checking: "正在检测本地代理…",
    connected: "已通过本地代理连到 GLM，NPC 由大模型驱动。",
    unknown: "代理似乎在线但没有 /health；开口说话后再判定。",
    nokey: "本地代理在线，但没读到 GLM_API_KEY。在代理终端设置后重启 glm_local_proxy.py。",
    empty: "GLM 返回空内容——通常是没禁用思考或 max_tokens 太小。",
    offline: "连不上本地代理，NPC 使用罐头台词。先启动 glm_local_proxy.py。",
  };
  function setStatus(state) {
    const el = document.getElementById("llm-badge");
    if (!el) return;
    const s = STATUS[state] || STATUS.unknown;
    el.textContent = "LLM " + s.t;
    el.style.color = s.c;
    el.style.borderColor = s.c;
    el.title = TIP[state] || "";
  }

  // cheap boot check: GET /health (no GLM call, no tokens)
  async function checkHealth() {
    if (!CONFIG.PROXY_URL) { setStatus("offline"); return; }
    setStatus("checking");
    const url = CONFIG.PROXY_URL.replace(/\/?$/, "/") + "health";
    try {
      const r = await fetch(url);
      let d = null;
      try { d = await r.json(); } catch (_) {}
      // ok:true -> a proper /health route (Python/Node proxy, or an updated Worker).
      // ok:false / non-JSON -> reachable but no /health (the deployed Worker says "POST only")
      // -> don't cry offline; the first real turn will confirm connected.
      if (d && d.ok) setStatus(d.key === false ? "nokey" : "connected");
      else setStatus("unknown");
    } catch (e) {
      // GET threw (network/DNS) — probe with OPTIONS to tell "down" from "reachable".
      try { await fetch(CONFIG.PROXY_URL, { method: "OPTIONS" }); setStatus("unknown"); }
      catch (_) { setStatus("offline"); }
    }
  }

  // POST to the proxy. Returns assistant text, or null on any failure. Updates the badge.
  async function rawCall(messages) {
    if (!CONFIG.PROXY_URL) { setStatus("offline"); return null; }
    let d;
    try {
      const r = await fetch(CONFIG.PROXY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages,
          model: CONFIG.MODEL,
          thinking: { type: "disabled" }, // REQUIRED for glm-4.x
          max_tokens: 400,
          temperature: 0.9,
        }),
      });
      d = await r.json();
    } catch (e) {
      setStatus("offline"); // unreachable / CORS
      return null;
    }
    if (d && d.ok && d.answer) { setStatus("connected"); return d.answer; }
    if (d && d.ok && !d.answer) setStatus("empty");
    else if (d && d.error && /GLM_API_KEY/i.test(d.error)) setStatus("nokey");
    else setStatus("offline");
    return null;
  }

  // Pull the first {...} block out of the text and parse it.
  function extractJson(text) {
    if (!text) return null;
    const s = text.indexOf("{");
    const e = text.lastIndexOf("}");
    if (s < 0 || e < 0 || e <= s) return null;
    try { return JSON.parse(text.slice(s, e + 1)); } catch (_) { return null; }
  }

  const EMOTIONS = ["neutral", "happy", "angry", "sad", "afraid", "curious"];
  const ACTIONS = ["none", "give_item", "reveal_clue", "move", "trade", "end"];

  function pickFallback(npc) {
    const f = npc.fallback || ["……"];
    return f[Math.floor(Math.random() * f.length)];
  }

  // Orchestrator: always returns a clean {say, emotion, action, arg} object.
  async function getNpcReply(npc, playerInput) {
    const messages = [
      { role: "system", content: buildSystemPrompt(npc, playerInput) },
      { role: "user", content: playerInput },
    ];
    const answer = await rawCall(messages);
    let p = extractJson(answer);

    if (!p || typeof p.say !== "string" || !p.say.trim()) {
      return { say: pickFallback(npc), emotion: "neutral", action: "none", arg: "", _fallback: true };
    }
    return {
      say: String(p.say).trim(),
      emotion: EMOTIONS.includes(p.emotion) ? p.emotion : "neutral",
      action: ACTIONS.includes(p.action) ? p.action : "none",
      arg: typeof p.arg === "string" ? p.arg.trim() : "",
    };
  }

  return { getNpcReply, buildSystemPrompt, extractJson, checkHealth, setStatus };
})();
