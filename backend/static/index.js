/* Hello / activation screen (figure 01). Reads the same localStorage state as
 * the dashboard and fills the host stats with REAL data; the 系统功能 menu
 * links into system.html (the dashboard) or toasts "未开启" for not-yet features. */
(function () {
  "use strict";

  var STORAGE_KEY = "personal_agent_system_v1";
  var ATTR_EXP_PER_LEVEL = 300;
  var ATTRS = [
    ["intellect", "智识"], ["constitution", "体魄"], ["willpower", "自律"],
    ["creativity", "创造"], ["spirit", "心境"],
  ];
  var RAINBOW = ["#ff5a5a", "#ff9f43", "#ffd93d", "#4ade80", "#34c8ff", "#5b8cff", "#c264ff"];

  function $(id) { return document.getElementById(id); }
  function loadState() {
    try { var raw = localStorage.getItem(STORAGE_KEY); if (raw) return JSON.parse(raw); } catch (e) {}
    return {};
  }
  var state = {};
  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
  }
  function levelInfo(totalExp) {
    function th(l) { return 100 + (Math.max(1, l) - 1) * 50; }
    var level = 1, remaining = Math.max(0, totalExp || 0);
    while (remaining >= th(level)) { remaining -= th(level); level += 1; }
    return { level: level, into: remaining, forNext: th(level) };
  }
  function attrLevel(exp) { return Math.min(7, Math.floor(Math.max(0, exp || 0) / ATTR_EXP_PER_LEVEL) + 1); }
  function hostTitle(level) {
    if (level >= 13) return "超凡者";
    if (level >= 9) return "卓越者";
    if (level >= 6) return "笃行者";
    if (level >= 4) return "精进者";
    if (level >= 2) return "修行者";
    return "初心者";
  }
  function showToast(text) {
    var el = $("toast");
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { el.hidden = true; }, 2200);
  }

  // Dynamic 系统 activation boot sequence: detection -> 激活中 progress -> 成功 flash
  // -> 欢迎 -> stats/menu/tip slide in. (Static fallback honours reduced-motion.)
  function finishBoot(win, ps) {
    setTimeout(function () { if (ps[2]) ps[2].classList.add("show", "flash"); }, 280);
    setTimeout(function () { if (ps[3]) ps[3].classList.add("show"); }, 820);
    setTimeout(function () { win.classList.add("activated"); }, 1200);
  }
  function runBoot() {
    var win = document.querySelector(".hello-window");
    if (!win) return;
    var ps = document.querySelectorAll("#hello-log p");
    var bar = document.querySelector(".act-bar");
    var fill = $("act-fill");
    var pct = $("act-pct");
    function show(el) { if (el) el.classList.add("show"); }
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      for (var k = 0; k < ps.length; k++) show(ps[k]);
      show(bar);
      if (fill) fill.style.width = "100%";
      if (pct) pct.textContent = "100";
      win.classList.add("activated");
      return;
    }
    win.classList.add("booting");
    setTimeout(function () { win.classList.add("activated"); }, 3600); // safety reveal if anything stalls
    setTimeout(function () { show(ps[0]); }, 250);
    setTimeout(function () {
      show(ps[1]); show(bar);
      var n = 0;
      var t = setInterval(function () {
        n += Math.max(1, Math.round((100 - n) / 9));
        if (n >= 100) { n = 100; clearInterval(t); finishBoot(win, ps); }
        if (pct) pct.textContent = n;
        if (fill) fill.style.width = n + "%";
      }, 55);
    }, 850);
  }

  // 系统设置: rename host / set GLM proxy / reset data (shares storage with the dashboard).
  function openSettings() {
    if ($("set-host")) $("set-host").value = (state.character && state.character.host) || "";
    var proxy = "";
    try { proxy = localStorage.getItem("proxy_url") || ""; } catch (e) {}
    if ($("set-proxy")) $("set-proxy").value = proxy;
    if ($("settings-modal")) $("settings-modal").hidden = false;
  }
  function closeSettings() { if ($("settings-modal")) $("settings-modal").hidden = true; }
  function saveSettings() {
    state.character = state.character || {};
    var host = (($("set-host").value) || "").trim().slice(0, 16);
    if (host) state.character.host = host;
    saveState();
    var proxy = (($("set-proxy").value) || "").trim();
    try { if (proxy) localStorage.setItem("proxy_url", proxy); else localStorage.removeItem("proxy_url"); } catch (e) {}
    if ($("hs-host")) $("hs-host").textContent = state.character.host || "无名宿主";
    closeSettings();
    showToast("已保存");
  }
  function resetData() {
    if (!window.confirm("确定要重置全部数据吗？此操作不可撤销，将清空你的成长进度。")) return;
    try { localStorage.clear(); } catch (e) {}
    location.reload();
  }

  // TEMPORARY PROMO: LLM Village cross-link — fades in after boot, ✕ dismiss remembered.
  function initGamePromo() {
    var el = $("game-promo");
    if (!el) return;
    var KEY = "game_promo_dismissed";
    try { if (localStorage.getItem(KEY)) return; } catch (e) {}
    setTimeout(function () {
      el.hidden = false;
      requestAnimationFrame(function () { el.classList.add("show"); });
    }, 3400);
    var x = $("game-promo-x");
    if (x) x.addEventListener("click", function (e) {
      e.preventDefault();
      el.classList.remove("show");
      setTimeout(function () { el.hidden = true; }, 350);
      try { localStorage.setItem(KEY, "1"); } catch (e) {}
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    state = loadState() || {};
    state.character = state.character || {};
    var s = state;
    var ch = s.character || {};
    var lvl = levelInfo(s.total_exp || 0);

    $("hs-host").textContent = ch.host || "无名宿主";
    $("hs-title").textContent = hostTitle(lvl.level);
    $("hs-level").textContent = lvl.level + "（" + lvl.into + "/" + lvl.forNext + "）";

    var attrs = s.attributes || {};
    $("hs-attrs").innerHTML = ATTRS.map(function (a) {
      var lv = attrLevel((attrs[a[0]] || {}).exp);
      var c = RAINBOW[lv - 1];
      return '<div class="hs-attr"><span class="hs-dot" style="background:' + c + ";box-shadow:0 0 6px " + c + '"></span>' +
        a[1] + ' <b style="color:' + c + '">Lv.' + lv + "</b></div>";
    }).join("");

    var items = document.querySelectorAll(".hm-item");
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener("click", function () {
        var go = this.getAttribute("data-go");
        var open = this.getAttribute("data-open");
        var soon = this.getAttribute("data-soon");
        if (go) { location.href = go; }
        else if (open === "settings") { openSettings(); }
        else if (soon) { showToast(soon + "：敬请期待"); }
      });
    }

    if ($("settings-close")) $("settings-close").addEventListener("click", closeSettings);
    if ($("settings-modal")) $("settings-modal").addEventListener("click", function (e) { if (e.target.id === "settings-modal") closeSettings(); });
    if ($("set-save")) $("set-save").addEventListener("click", saveSettings);
    if ($("set-reset")) $("set-reset").addEventListener("click", resetData);

    runBoot();
    initGamePromo();
  });
})();
