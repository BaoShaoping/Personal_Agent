// All pixel art: Minecraft-style 4-direction characters, biome tiles, oak/birch/spruce
// trees, interactive objects, and the dragon. Everything is baked into textures at boot.
window.Art = (function () {
  const S = 2; // character scale: 14x18 grid -> 28x36 sprite

  // ---------- helpers ----------
  const b = (c, x, y, w, h, col) => { c.fillStyle = col; c.fillRect(x, y, w, h); };
  const clr = (c, x, y, w, h) => c.clearRect(x, y, w, h);
  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    const cl = (v) => Math.max(0, Math.min(255, v));
    const r = cl((n >> 16) + amt), g = cl(((n >> 8) & 255) + amt), bl = cl((n & 255) + amt);
    return "#" + ((r << 16) | (g << 8) | bl).toString(16).padStart(6, "0");
  }

  // ---------- characters (Minecraft-blocky, big cube head) ----------
  // K outline · H hair · F skin · E eye · N nose(side) · S shirt · P pants · B boots
  const DOWN0 = [
    "..............", "...KKKKKKKK...", "...KHHHHHHK...", "...KHHHHHHK...",
    "...KFFFFFFK...", "...KFEFFEFK...", "...KFFFFFFK...", "...KFFKKFFK...",
    "....KFFFFK....", "..KSSSSSSSSK..", "..KSSSSSSSSK..", ".KFSSSSSSSSFK.",
    "..KSSSSSSSSK..", "..KPPPPPPPPK..", "..KPPPPPPPPK..", "..KPPP..PPPK..",
    "..KBBB..BBBK..", "..............",
  ];
  const DOWN1 = DOWN0.slice(0, 15).concat(["..KPPPPPPPPK..", "..K.BBBBBB.K..", ".............."]);
  const UP0 = [
    "..............", "...KKKKKKKK...", "...KHHHHHHK...", "...KHHHHHHK...",
    "...KHHHHHHK...", "...KHHHHHHK...", "...KHHHHHHK...", "...KHHHHHHK...",
    "....KHHHHK....", "..KSSSSSSSSK..", "..KSSSSSSSSK..", ".KFSSSSSSSSFK.",
    "..KSSSSSSSSK..", "..KPPPPPPPPK..", "..KPPPPPPPPK..", "..KPPP..PPPK..",
    "..KBBB..BBBK..", "..............",
  ];
  const UP1 = UP0.slice(0, 15).concat(["..KPPPPPPPPK..", "..K.BBBBBB.K..", ".............."]);
  const SIDE0 = [
    "..............", "...KKKKKK.....", "..KHHHHHHK....", "..KHHHHFFK....",
    "..KHHHFEFK....", "..KHHFFFFK....", "..KHFFFFNK....", "..KFFFFKK.....",
    "...KFFFK......", "..KSSSSSK.....", "..KSSSSSK.....", "..KSSSSFK.....",
    "..KSSSSSK.....", "..KPPPPPK.....", "..KPPPPPK.....", "..KPP.PPK.....",
    "..KBB.BBK.....", "..............",
  ];
  const SIDE1 = SIDE0.slice(0, 15).concat(["..KPPPPPK.....", "...KBBBK......", ".............."]);
  const BODY = { down: [DOWN0, DOWN1], up: [UP0, UP1], side: [SIDE0, SIDE1] };

  function charResolve(pal, flags) {
    const nose = pal.nose || shade(pal.skin, -28);
    return function (ch, x, y) {
      switch (ch) {
        case "K": return pal.outline || "#241c14";
        case "H": return pal.hair;
        case "F":
          if (flags.bigNose && (y === 5 || y === 6) && (x === 6 || x === 7)) return nose;
          return pal.skin;
        case "E": return pal.eye || "#23252b";
        case "N": return nose;
        case "S": return pal.shirt;
        case "P": return flags.robe ? pal.shirt : pal.pants;
        case "B": return pal.boots;
        default: return null;
      }
    };
  }
  function buildChar(scene, id, pal, flags) {
    flags = flags || {};
    const res = charResolve(pal, flags);
    ["down", "up", "side"].forEach((dir) =>
      BODY[dir].forEach((g, i) => PIXELS.bake(scene, `char_${id}_${dir}_${i}`, g, res, S)));
  }
  function setCharFrame(sprite, id, facing, frame) {
    const dir = (facing === "left" || facing === "right") ? "side" : facing;
    sprite.setTexture(`char_${id}_${dir}_${frame}`);
    sprite.setFlipX(facing === "left");
  }

  // ---------- biome tiles (32x32) ----------
  function speckle(c, base, cols, seed, n) {
    b(c, 0, 0, 32, 32, base);
    const r = PIXELS.rng(seed);
    for (let i = 0; i < n; i++) {
      const x = (r() * 16 | 0) * 2, y = (r() * 16 | 0) * 2;
      b(c, x, y, 2, 2, cols[(r() * cols.length) | 0]);
    }
  }
  const grass = (seed) => (c) => speckle(c, "#5e9e44", ["#4f8a3a", "#69ad4d", "#79bd5a"], seed, 80);
  const path = (c) => speckle(c, "#c8b386", ["#b39c6a", "#d8c79a", "#a98f5f"], 7, 60);
  const sand = (c) => speckle(c, "#e3d29b", ["#d4c084", "#efe1b4", "#c9b478"], 9, 55);
  const dirt = (c) => { speckle(c, "#8a6a43", ["#75592f", "#9c7a4f", "#6e5230"], 13, 40);
    for (let y = 4; y < 32; y += 8) b(c, 0, y, 32, 2, "#6e5230"); };           // furrows
  const crop = (c) => { dirt(c); for (let x = 4; x < 32; x += 8) { b(c, x, 6, 3, 22, "#5fae3a"); b(c, x, 6, 3, 5, "#d8c537"); } };
  const stone = (c) => { speckle(c, "#8b8b85", ["#79796f", "#a2a298", "#6e6e64"], 5, 60);
    b(c, 0, 0, 32, 1, "#9c9c92"); b(c, 0, 15, 32, 1, "#6e6e64"); };
  const cave = (c) => speckle(c, "#3b3a40", ["#2e2d33", "#48474e", "#535259"], 17, 60);
  function water(c) {
    b(c, 0, 0, 32, 32, "#3f86d6");
    for (let y = 2; y < 32; y += 8) { b(c, 0, y, 32, 2, "#5b9ee6"); b(c, 0, y + 4, 32, 1, "#2f6fbd"); }
    const r = PIXELS.rng(3); for (let i = 0; i < 6; i++) b(c, (r() * 28 | 0), (r() * 28 | 0), 4, 1, "#bfe0ff");
  }
  const deep = (c) => { b(c, 0, 0, 32, 32, "#2b62a8"); for (let y = 3; y < 32; y += 9) b(c, 0, y, 32, 2, "#3a78c4"); };
  function bridge(c) { b(c, 0, 0, 32, 32, "#9a6b3f"); for (let x = 0; x < 32; x += 8) b(c, x, 0, 1, 32, "#7a5230");
    b(c, 0, 2, 32, 2, "#b88a55"); b(c, 0, 28, 32, 2, "#b88a55"); }
  function wall(c) {
    b(c, 0, 0, 32, 32, "#a9763f");
    for (let y = 0; y < 32; y += 8) b(c, 0, y + 7, 32, 1, "#7a5230");
    for (let x = 0; x < 32; x += 6) b(c, x, 0, 1, 32, "#b88a55");
    b(c, 0, 0, 32, 1, "#7a5230");
  }
  function roof(c) {
    b(c, 0, 0, 32, 32, "#9a4636");
    for (let y = 0; y < 32; y += 6)
      for (let x = ((y / 6) % 2) * 6 - 6; x < 32; x += 12) { b(c, x, y, 11, 5, "#a8513f"); b(c, x, y + 4, 11, 1, "#7a3328"); }
    b(c, 0, 0, 32, 2, "#c46a52");
  }
  function door(c) { wall(c); b(c, 8, 6, 16, 26, "#5a3a22"); b(c, 10, 8, 12, 24, "#6e4a2c"); b(c, 15, 18, 3, 3, "#e8d28a"); }

  // ---------- trees (tall, drawn above their trunk; origin = bottom-center) ----------
  function leaves(c, x0, y0, w, h, seed, pal) {
    b(c, x0, y0, w, h, pal[0]);
    const r = PIXELS.rng(seed);
    for (let y = y0; y < y0 + h; y += 4)
      for (let x = x0; x < x0 + w; x += 4) { const t = r(); if (t < 0.34) b(c, x, y, 4, 4, pal[1]); else if (t > 0.74) b(c, x, y, 4, 4, pal[2]); }
    // notch the corners so it reads round-ish
    [[x0, y0], [x0 + w - 6, y0], [x0, y0 + h - 6], [x0 + w - 6, y0 + h - 6]].forEach((p) => clr(c, p[0], p[1], 6, 6));
  }
  function oak(c, w, h) {
    clr(c, 0, 0, w, h); const cx = w / 2;
    b(c, cx - 5, h - 42, 10, 42, "#5e4226"); b(c, cx - 5, h - 42, 3, 42, "#70522f");
    leaves(c, cx - 30, h - 96, 60, 60, 21, ["#2f6b30", "#256026", "#57a44c"]);
  }
  function birch(c, w, h) {
    clr(c, 0, 0, w, h); const cx = w / 2;
    b(c, cx - 4, h - 50, 8, 50, "#e6e6dc"); for (let y = h - 46; y < h - 4; y += 9) b(c, cx - 4, y, 4, 3, "#2b2b2b");
    leaves(c, cx - 24, h - 92, 48, 52, 31, ["#6aa83f", "#5a9433", "#85c25a"]);
  }
  function spruce(c, w, h) {
    clr(c, 0, 0, w, h); const cx = w / 2;
    b(c, cx - 4, h - 34, 8, 34, "#4a3320");
    const g = ["#1f5a2a", "#184a22", "#2f7038"];
    let ty = h - 30;
    for (let i = 0; i < 4; i++) { const half = 28 - i * 5; b(c, cx - half, ty - 22, half * 2, 26, g[i % 3]);
      clr(c, cx - half, ty - 22, 5, 6); clr(c, cx + half - 5, ty - 22, 5, 6); ty -= 18; }
  }

  // ---------- interactive objects + props ----------
  const O = {
    chest_closed: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 5, 10, 22, 18, "#7a4a22"); b(c, 5, 10, 22, 6, "#8a5a2c");
      b(c, 5, 16, 22, 2, "#3a2412"); for (const x of [9, 22]) b(c, x, 8, 2, 22, "#caa44a"); b(c, 14, 17, 4, 4, "#e8d28a"); }],
    chest_open: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 5, 14, 22, 14, "#7a4a22"); b(c, 5, 6, 22, 6, "#8a5a2c");
      b(c, 7, 16, 18, 9, "#ffd34d"); b(c, 9, 18, 5, 5, "#fff0a0"); for (const x of [9, 22]) b(c, x, 14, 2, 14, "#caa44a"); }],
    lever_off: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 10, 22, 12, 6, "#777"); b(c, 14, 22, 4, 4, "#555");
      b(c, 14, 10, 3, 14, "#9a6b3f"); b(c, 12, 8, 7, 5, "#d64a4a"); }],
    lever_on: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 10, 22, 12, 6, "#777"); b(c, 14, 22, 4, 4, "#555");
      b(c, 16, 12, 3, 12, "#9a6b3f"); b(c, 17, 8, 7, 5, "#5fae54"); }],
    door_closed: [32, 48, (c) => { clr(c, 0, 0, 32, 48); b(c, 2, 6, 28, 42, "#6e6e64"); b(c, 6, 12, 20, 30, "#3a3a40");
      b(c, 2, 6, 28, 3, "#8b8b85"); b(c, 14, 20, 4, 12, "#7a5fd0"); b(c, 12, 24, 8, 4, "#7a5fd0"); }],
    door_open: [32, 48, (c) => { clr(c, 0, 0, 32, 48); b(c, 2, 6, 28, 42, "#6e6e64"); b(c, 6, 12, 20, 36, "#15141a");
      b(c, 2, 6, 28, 3, "#8b8b85"); }],
    boat: [48, 32, (c) => { clr(c, 0, 0, 48, 32); b(c, 4, 14, 40, 12, "#8a5a2c"); b(c, 2, 18, 44, 6, "#6e4422");
      b(c, 8, 10, 32, 5, "#a9763f"); b(c, 22, 4, 3, 12, "#7a5230"); }],
    campfire_unlit: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 6, 18, 20, 5, "#7a5230"); b(c, 9, 14, 14, 5, "#9a6b3f");
      b(c, 6, 22, 20, 3, "#5a3a22"); }],
    campfire_lit: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 6, 20, 20, 5, "#7a5230"); b(c, 11, 8, 10, 14, "#ff7a1a");
      b(c, 13, 11, 6, 9, "#ffd34d"); b(c, 14, 4, 4, 6, "#ffae42"); }],
    altar: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 6, 14, 20, 14, "#9a9a93"); b(c, 4, 12, 24, 4, "#b0b0a8");
      b(c, 4, 24, 24, 4, "#79796f"); b(c, 13, 6, 6, 6, "#7a5fd0"); }],
    sign: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 14, 14, 4, 16, "#7a5230"); b(c, 5, 5, 22, 11, "#c9a86a");
      b(c, 5, 5, 22, 2, "#9a7a48"); b(c, 8, 9, 16, 1, "#6e4a2c"); b(c, 8, 12, 11, 1, "#6e4a2c"); }],
    scarecrow: [32, 48, (c) => { clr(c, 0, 0, 32, 48); b(c, 14, 10, 4, 34, "#7a5230"); b(c, 4, 18, 24, 4, "#7a5230");
      b(c, 11, 6, 10, 10, "#d8c537"); b(c, 13, 9, 2, 2, "#000"); b(c, 17, 9, 2, 2, "#000"); b(c, 8, 2, 16, 5, "#9a6b3f"); }],
    fence: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 4, 10, 4, 18, "#9a6b3f"); b(c, 24, 10, 4, 18, "#9a6b3f");
      b(c, 2, 14, 28, 3, "#b88a55"); b(c, 2, 22, 28, 3, "#b88a55"); }],
    lantern: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 14, 8, 4, 22, "#5a3a22"); b(c, 10, 4, 12, 8, "#3a2a18");
      b(c, 12, 5, 8, 6, "#ffd966"); }],
    barrel: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 8, 8, 16, 22, "#9a6b3f"); b(c, 8, 12, 16, 2, "#5a3a22");
      b(c, 8, 24, 16, 2, "#5a3a22"); b(c, 10, 8, 2, 22, "#b88a55"); }],
    rock: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 6, 14, 20, 14, "#8b8b85"); b(c, 9, 11, 12, 6, "#a2a298"); b(c, 8, 24, 16, 3, "#6e6e64"); }],
    flowerR: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 15, 18, 2, 10, "#3a7a2e"); b(c, 12, 10, 8, 8, "#e0574a"); b(c, 14, 12, 4, 4, "#ffe08a"); }],
    flowerY: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 15, 18, 2, 10, "#3a7a2e"); b(c, 12, 10, 8, 8, "#f0c020"); b(c, 14, 12, 4, 4, "#fff3b0"); }],
    bush: [32, 32, (c) => { clr(c, 0, 0, 32, 32); b(c, 6, 14, 20, 14, "#2f6b30"); b(c, 9, 11, 14, 8, "#3d8038"); b(c, 11, 13, 5, 3, "#57a44c"); }],
    well: [32, 40, (c) => { clr(c, 0, 0, 32, 40); b(c, 5, 18, 22, 18, "#9a9a93"); b(c, 5, 18, 22, 2, "#b0b0a8");
      b(c, 8, 22, 16, 12, "#274a6b"); b(c, 10, 24, 12, 8, "#1c3650"); b(c, 4, 6, 3, 24, "#6e4a2c"); b(c, 25, 6, 3, 24, "#6e4a2c");
      b(c, 2, 2, 28, 7, "#9a4636"); b(c, 2, 2, 28, 2, "#c46a52"); b(c, 13, 20, 6, 6, "#7a5230"); }],
  };

  // ---------- the dragon 赤鳞 (big, 2 frames) ----------
  function dragon(c, w, h, frame) {
    clr(c, 0, 0, w, h);
    const cx = w / 2, base = "#b83227", dk = "#7e1f18", belly = "#e8a23c", out = "#3a0e0a";
    // tail
    b(c, cx + 30, h - 34, 46, 12, base); b(c, cx + 60, h - 28, 18, 8, dk);
    // body
    b(c, cx - 40, h - 60, 88, 44, base); b(c, cx - 40, h - 34, 88, 12, dk);
    b(c, cx - 30, h - 30, 60, 12, belly);
    // wings (flap differs per frame)
    const wy = frame ? h - 96 : h - 74;
    b(c, cx - 36, wy, 40, 30, dk); b(c, cx - 30, wy + 4, 28, 20, "#9a261d");
    b(c, cx + 4, wy, 40, 30, dk); b(c, cx + 10, wy + 4, 28, 20, "#9a261d");
    // legs
    b(c, cx - 30, h - 22, 14, 18, dk); b(c, cx + 16, h - 22, 14, 18, dk);
    b(c, cx - 32, h - 8, 18, 5, out); b(c, cx + 14, h - 8, 18, 5, out);
    // neck + head
    b(c, cx - 66, h - 70, 22, 40, base); b(c, cx - 84, h - 80, 30, 24, base);
    b(c, cx - 84, h - 80, 30, 4, dk);
    b(c, cx - 60, h - 84, 8, 14, dk); b(c, cx - 50, h - 86, 6, 12, dk); // horns
    b(c, cx - 80, h - 74, 6, 6, "#ffd34d"); b(c, cx - 79, h - 73, 3, 3, out); // eye
    b(c, cx - 92, h - 70, 10, 5, out); // snout
    if (frame) b(c, cx - 104, h - 69, 14, 3, "#ff7a1a"); // breath wisp
  }

  // ---------- build everything ----------
  const TILES = {
    grass0: grass(11), grass1: grass(37), path, sand, dirt, crop, stone, cave,
    water, deep, bridge, wall, roof, door,
  };
  const TREES = { tree_oak: [72, 112, oak], tree_birch: [64, 110, birch], tree_spruce: [64, 122, spruce] };

  const PAL = { hero: { skin: "#e0ac69", hair: "#4a3322", shirt: "#1fa89a", pants: "#39407a", boots: "#4a3320" } };

  function build(scene) {
    Object.keys(TILES).forEach((k) => PIXELS.canvas(scene, "tile_" + k, 32, TILES[k]));
    Object.keys(TREES).forEach((k) => { const [w, h, fn] = TREES[k]; PIXELS.canvasWH(scene, k, w, h, fn); });
    Object.keys(O).forEach((k) => { const [w, h, fn] = O[k]; PIXELS.canvasWH(scene, "obj_" + k, w, h, fn); });
    PIXELS.canvasWH(scene, "dragon_0", 200, 150, (c, w, h) => dragon(c, w, h, 0));
    PIXELS.canvasWH(scene, "dragon_1", 200, 150, (c, w, h) => dragon(c, w, h, 1));
    buildChar(scene, "hero", PAL.hero, {});
  }

  return { build, buildChar, setCharFrame, PAL };
})();
