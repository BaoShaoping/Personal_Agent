/* System Edition — 二次元 avatars drawn purely in SVG (no image assets).
 * Four stylised chibi busts the host can equip as the System's appearance.
 * Exposes window.avatarSvg(id) and window.SYSTEM_AVATAR_IDS. */
(function () {
  "use strict";

  // Shared chibi face: skin + big anime eyes + blush + mouth (viewBox 0 0 100 100).
  function face(eye) {
    return (
      '<path d="M30,50 Q30,74 50,80 Q70,74 70,50 Q70,33 50,32 Q30,33 30,50 Z" fill="#ffe2d2"/>' +
      '<ellipse cx="36" cy="62" rx="5" ry="3" fill="#ffb0c2" opacity="0.7"/>' +
      '<ellipse cx="64" cy="62" rx="5" ry="3" fill="#ffb0c2" opacity="0.7"/>' +
      '<ellipse cx="41" cy="56" rx="6.4" ry="8.6" fill="#fff"/>' +
      '<ellipse cx="59" cy="56" rx="6.4" ry="8.6" fill="#fff"/>' +
      '<ellipse cx="41" cy="57.5" rx="4.8" ry="6.8" fill="' + eye + '"/>' +
      '<ellipse cx="59" cy="57.5" rx="4.8" ry="6.8" fill="' + eye + '"/>' +
      '<circle cx="41" cy="59" r="2.3" fill="#241f2b"/>' +
      '<circle cx="59" cy="59" r="2.3" fill="#241f2b"/>' +
      '<circle cx="39.2" cy="54.6" r="1.8" fill="#fff"/>' +
      '<circle cx="57.2" cy="54.6" r="1.8" fill="#fff"/>' +
      '<path d="M46,68 Q50,71 54,68" fill="none" stroke="#e08a8a" stroke-width="1.6" stroke-linecap="round"/>'
    );
  }

  function wrap(id, stops, inner) {
    return (
      '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;display:block">' +
      '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="1" y2="1">' + stops + "</linearGradient></defs>" +
      '<rect x="0" y="0" width="100" height="100" rx="18" fill="url(#' + id + ')"/>' +
      inner +
      "</svg>"
    );
  }

  // 1) 赛博少女 — cyan hair, neon visor + headphones (cyberpunk)
  var cyber = wrap(
    "avCyber",
    '<stop offset="0" stop-color="#16335a"/><stop offset="1" stop-color="#0a1830"/>',
    '<path d="M24,58 Q20,28 50,24 Q80,28 76,58 Q72,44 50,40 Q28,44 24,58 Z" fill="#33c2ee"/>' +
      face("#1f7fb8") +
      '<path d="M28,47 Q32,28 50,27 Q68,28 72,47 Q62,38 54,40 Q56,32 50,32 Q44,32 46,40 Q38,38 28,47 Z" fill="#5ce0ff"/>' +
      '<rect x="33" y="51" width="34" height="5" rx="2.5" fill="#7af0ff" opacity="0.28"/>' +
      '<path d="M26,52 Q50,30 74,52" fill="none" stroke="#2a3a55" stroke-width="3"/>' +
      '<rect x="22" y="50" width="8" height="13" rx="4" fill="#23314a"/>' +
      '<rect x="70" y="50" width="8" height="13" rx="4" fill="#23314a"/>' +
      '<rect x="23.5" y="53" width="5" height="7" rx="2.5" fill="#34c8ff"/>' +
      '<rect x="71.5" y="53" width="5" height="7" rx="2.5" fill="#34c8ff"/>'
  );

  // 2) 元气少女 — orange twin tails, hair clips, amber eyes
  var genki = wrap(
    "avGenki",
    '<stop offset="0" stop-color="#5a2f3f"/><stop offset="1" stop-color="#34202c"/>',
    '<ellipse cx="19" cy="58" rx="11" ry="19" fill="#ff9f43"/>' +
      '<ellipse cx="81" cy="58" rx="11" ry="19" fill="#ff9f43"/>' +
      '<circle cx="24" cy="46" r="3" fill="#ff5a8a"/>' +
      '<circle cx="76" cy="46" r="3" fill="#ff5a8a"/>' +
      '<path d="M27,54 Q25,27 50,24 Q75,27 73,54 Q68,42 50,39 Q32,42 27,54 Z" fill="#ffb15c"/>' +
      face("#e08a2a") +
      '<path d="M30,47 Q34,28 50,27 Q66,28 70,47 Q60,39 50,40 Q40,39 30,47 Z" fill="#ffc77f"/>' +
      '<rect x="60" y="40" width="8" height="3.2" rx="1.6" fill="#ff5a8a"/>' +
      '<rect x="60" y="44" width="8" height="3.2" rx="1.6" fill="#ffd166"/>'
  );

  // 3) 冷静系 — long straight violet hair, calm violet eyes
  var cool = wrap(
    "avCool",
    '<stop offset="0" stop-color="#2c2456"/><stop offset="1" stop-color="#191334"/>',
    '<path d="M27,52 Q25,26 50,23 Q75,26 73,52 L73,84 L65,84 L65,54 Q61,42 50,41 Q39,42 35,54 L35,84 L27,84 Z" fill="#7d63c9"/>' +
      face("#5b3fb0") +
      '<path d="M31,46 Q33,29 50,28 Q67,29 69,46 Q60,40 52,41 L50,30 L48,41 Q40,40 31,46 Z" fill="#9079db"/>'
  );

  // 4) 精灵系 — silver-green hair, pointed ears, circlet, green eyes
  var elf = wrap(
    "avElf",
    '<stop offset="0" stop-color="#214a32"/><stop offset="1" stop-color="#122a1d"/>',
    '<path d="M27,55 L18,49 L30,61 Z" fill="#ffe2d2"/>' +
      '<path d="M73,55 L82,49 L70,61 Z" fill="#ffe2d2"/>' +
      '<path d="M26,57 Q22,28 50,24 Q78,28 74,57 Q70,43 50,39 Q30,43 26,57 Z" fill="#bfe6c6"/>' +
      face("#3aa867") +
      '<path d="M30,47 Q34,28 50,27 Q66,28 70,47 Q60,39 50,40 Q40,39 30,47 Z" fill="#d9f0db"/>' +
      '<path d="M33,41 Q50,35 67,41" fill="none" stroke="#8fd49a" stroke-width="1.6"/>' +
      '<circle cx="50" cy="37" r="2.4" fill="#7fe6a0"/>'
  );

  var AVATARS = { cyber: cyber, genki: genki, cool: cool, elf: elf };

  window.SYSTEM_AVATAR_IDS = ["cyber", "genki", "cool", "elf"];
  window.avatarSvg = function (id) {
    return AVATARS[id] || AVATARS.cyber;
  };
})();
