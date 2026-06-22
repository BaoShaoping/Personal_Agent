// The expanded world of 井村: a 50x38 biome map (village / farmland / forest / lake /
// mountain-cave). Built in code. Exposes terrain + collision + buildings + trees + props
// + interactable positions + the cave gate.
(function () {
  const W = CONFIG.MAP_W, H = CONFIG.MAP_H;
  // tile codes
  const G = 0, P = 1, WT = 2, DP = 3, SD = 4, DR = 5, CR = 6, ST = 7, CV = 8, BR = 9, BLD = 10, TR = 11;

  const t = Array.from({ length: H }, () => Array(W).fill(G));
  const inb = (x, y) => x >= 0 && x < W && y >= 0 && y < H;
  function rect(x0, y0, x1, y1, v) {
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (inb(x, y)) t[y][x] = v;
  }

  // 1) northern cliff + dragon lair (carved into the stone, sealed by a gate)
  rect(0, 0, W - 1, 1, ST);
  rect(19, 1, 31, 6, ST);          // stone block around the lair
  rect(20, 1, 30, 5, CV);          // lair interior (cave floor)
  const GATE = { x: 25, y: 6 };
  t[GATE.y][GATE.x] = ST;          // sealed gate (solid until opened)

  // 2) lake (east) + deep water + island + sandy shore
  rect(37, 14, 38, 32, SD);        // west shore
  rect(39, 15, 48, 31, WT);
  rect(42, 19, 46, 27, DP);
  rect(39, 14, 48, 14, SD); rect(39, 32, 48, 32, SD);
  rect(43, 21, 46, 24, G);         // island
  rect(37, 22, 38, 22, BR);        // dock planks

  // 3) farmland (south-west)
  rect(2, 31, 14, 35, DR);
  for (let y = 31; y <= 35; y += 2) for (let x = 2; x <= 14; x++) t[y][x] = CR;

  // 4) buildings (footprints solid; drawn as roof/wall/door in main)
  const BUILDINGS = [
    { x0: 8, y0: 14, x1: 11, y1: 16, door: { x: 9, y: 16 }, sign: "铁匠铺" },
    { x0: 30, y0: 14, x1: 34, y1: 17, door: { x: 32, y: 17 }, sign: "客栈" },
    { x0: 8, y0: 26, x1: 11, y1: 28, door: { x: 9, y: 28 }, sign: "磨坊" },
    { x0: 30, y0: 25, x1: 33, y1: 28, door: { x: 31, y: 28 }, sign: "村公所" },
    { x0: 15, y0: 12, x1: 18, y1: 14, door: { x: 16, y: 14 }, sign: "学士居" },
    { x0: 3, y0: 28, x1: 6, y1: 30, door: { x: 5, y: 30 }, sign: "药庐" },
    { x0: 34, y0: 23, x1: 36, y1: 25, door: { x: 35, y: 25 }, sign: "哨楼" },
  ];
  BUILDINGS.forEach((bd) => rect(bd.x0, bd.y0, bd.x1, bd.y1, BLD));

  // 5) roads
  for (let y = 6; y <= 34; y++) if (t[y][25] === G) t[y][25] = P; // vertical
  for (let x = 8; x <= 37; x++) if (t[22][x] === G) t[22][x] = P;                // horizontal
  for (let y = 15; y <= 22; y++) if (t[y][16] === G) t[y][16] = P;              // to scholar
  for (let y = 22; y <= 30; y++) if (t[y][10] === G) t[y][10] = P;             // to mill
  for (let y = 22; y <= 29; y++) if (t[y][31] === G) t[y][31] = P;            // to hall
  for (let x = 26; x <= 30; x++) if (t[8][x] === G) t[8][x] = P;             // forest spur to the 斗篷客

  // hardcoded NPC tiles (must match npcs.js) — reserved so trees/props avoid them
  const NPC_TILES = [[9, 17], [32, 18], [9, 29], [31, 29], [16, 15], [5, 31], [35, 26], [24, 21], [30, 8], [25, 3]];

  // interactable objects (behaviour lives in interactables.js, keyed by type)
  const INTERACTABLES = [
    { type: "well", x: 24, y: 18 },
    { type: "sign", x: 26, y: 23, text: "井村 · 中央广场\n往北是山道，往东是湖。" },
    { type: "sign", x: 24, y: 10, text: "↑ 山道：通往被封印的洞窟\n（传说赤鳞巨龙沉睡其中）" },
    { type: "chest", x: 14, y: 9, gives: "torch", label: "林中木箱" },
    { type: "campfire", x: 21, y: 15 },
    { type: "cave_door", x: GATE.x, y: GATE.y },
    { type: "boat", x: 38, y: 22, to: { x: 43, y: 23 } },
    { type: "chest", x: 44, y: 22, gives: "gem", label: "湖心宝箱" },
    { type: "altar", x: 25, y: 5 },
  ];

  // ---- reservation set (no trees/props here) ----
  const reserved = new Set();
  const rk = (x, y) => x + "," + y;
  const reserve = (x, y, pad) => { pad = pad || 0; for (let dy = -pad; dy <= pad; dy++) for (let dx = -pad; dx <= pad; dx++) reserved.add(rk(x + dx, y + dy)); };
  BUILDINGS.forEach((b) => { for (let y = b.y0 - 1; y <= b.y1 + 1; y++) for (let x = b.x0 - 1; x <= b.x1 + 1; x++) reserved.add(rk(x, y)); });
  NPC_TILES.forEach(([x, y]) => reserve(x, y, 1));
  INTERACTABLES.forEach((o) => reserve(o.x, o.y, 1));
  reserve(25, 33, 2); // spawn
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if ([P, WT, DP, SD, BR, CV, DR, CR, BLD, ST].includes(t[y][x])) reserved.add(rk(x, y));
  for (let y = 6; y <= 14; y++) for (let x = 23; x <= 27; x++) reserved.add(rk(x, y)); // keep the mountain road clear

  // 6) scatter trees (forest band + edges) on free grass
  const rnd = PIXELS.rng(98765);
  const types = ["tree_oak", "tree_birch", "tree_spruce"];
  const TREES = [];
  function tryTree(x, y, prob) {
    if (!inb(x, y) || t[y][x] !== G || reserved.has(rk(x, y))) return;
    if (rnd() > prob) return;
    t[y][x] = TR; reserved.add(rk(x, y));
    TREES.push({ x, y, key: types[(rnd() * types.length) | 0] });
  }
  for (let y = 6; y <= 13; y++) for (let x = 1; x < W - 1; x++) tryTree(x, y, 0.4); // forest (kept passable)
  for (let x = 1; x < W - 1; x++) { tryTree(x, H - 2, 0.5); tryTree(x, H - 3, 0.3); } // south tree line
  for (let y = 14; y < H - 1; y++) { tryTree(1, y, 0.5); tryTree(2, y, 0.25); }       // west edge
  for (let y = 26; y < 32; y++) tryTree(48, y, 0.4);                                  // a few east of lake

  // 7) decorative props (no collision) on free grass
  const PROPS = [];
  function prop(x, y, key) { if (inb(x, y) && t[y][x] === G && !reserved.has(rk(x, y))) { PROPS.push({ x, y, key }); reserved.add(rk(x, y)); } }
  prop(8, 33, "obj_scarecrow"); prop(12, 33, "obj_scarecrow");
  [[22, 20], [27, 20], [23, 24], [28, 24]].forEach(([x, y]) => prop(x, y, "obj_barrel"));
  [[9, 18], [33, 18], [31, 16], [30, 27]].forEach(([x, y]) => prop(x, y, "obj_lantern"));
  for (let i = 0; i < 26; i++) { const x = 3 + (rnd() * 44 | 0), y = 16 + (rnd() * 18 | 0); prop(x, y, rnd() < 0.5 ? "obj_flowerR" : (rnd() < 0.7 ? "obj_flowerY" : "obj_bush")); }
  [[20, 24], [29, 17], [13, 20], [40, 26]].forEach(([x, y]) => prop(x, y, "obj_rock"));

  const MINI = { [G]: "#5e9e44", [P]: "#c8b386", [WT]: "#3f86d6", [DP]: "#2b62a8", [SD]: "#e3d29b", [DR]: "#8a6a43", [CR]: "#6fae3a", [ST]: "#8b8b85", [CV]: "#2e2d33", [BR]: "#9a6b3f", [BLD]: "#9a4636", [TR]: "#2f6b30" };

  window.WORLD = {
    tiles: t, W, H,
    codes: { G, P, WT, DP, SD, DR, CR, ST, CV, BR, BLD, TR },
    SOLID: new Set([WT, DP, ST, BLD, TR]),
    BUILDINGS, TREES, PROPS, INTERACTABLES, GATE,
    spawn: { x: 25, y: 33 },
    isSolid(tx, ty) { return !this.tiles[ty] || this.SOLID.has(this.tiles[ty][tx]); },
    miniColor(code) { return MINI[code] || "#000"; },
    cx(tx) { return tx * CONFIG.TILE + CONFIG.TILE / 2; },
    cy(ty) { return ty * CONFIG.TILE + CONFIG.TILE / 2; },
    // ground texture key for a tile
    groundKey(code, x, y) {
      switch (code) {
        case P: return "tile_path"; case WT: return "tile_water"; case DP: return "tile_deep";
        case SD: return "tile_sand"; case DR: return "tile_dirt"; case CR: return "tile_crop";
        case ST: return "tile_stone"; case CV: return "tile_cave"; case BR: return "tile_bridge";
        default: return ((x + y) % 2 === 0) ? "tile_grass0" : "tile_grass1"; // grass under G/BLD/TR
      }
    },
  };
})();
