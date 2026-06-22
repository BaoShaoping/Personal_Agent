// Phaser boot + scene: bake art, paint the big world, spawn everyone, follow-camera,
// minimap, and unified E-interaction (NPCs talk via LLM; objects via Interact).
(function () {
  const T = CONFIG.TILE;
  const baseDepth = (ty) => WORLD.cy(ty) + T / 2;

  function drawBuilding(scene, bd) {
    const d = baseDepth(bd.y1);
    const roofRows = Math.ceil((bd.y1 - bd.y0 + 1) / 2);
    for (let y = bd.y0; y <= bd.y1; y++)
      for (let x = bd.x0; x <= bd.x1; x++) {
        let key = "tile_wall";
        if (y < bd.y0 + roofRows) key = "tile_roof";
        else if (bd.door && x === bd.door.x && y === bd.door.y) key = "tile_door";
        scene.add.image(WORLD.cx(x), WORLD.cy(y), key).setDepth(d);
      }
  }

  function create() {
    const scene = this;
    const WW = WORLD.W * T, WH = WORLD.H * T;
    scene.cameras.main.setBackgroundColor("#0d1410");

    Art.build(scene);
    NPCS.forEach((n) => { if (!n.isDragon) Art.buildChar(scene, n.id, n.sprite.palette, n.sprite.flags || {}); });
    scene.physics.world.setBounds(0, 0, WW, WH);

    // --- ground baked into one RenderTexture (1 object instead of ~1900) ---
    const rt = scene.add.renderTexture(0, 0, WW, WH).setOrigin(0, 0).setDepth(0);
    for (let y = 0; y < WORLD.H; y++)
      for (let x = 0; x < WORLD.W; x++)
        rt.draw(WORLD.groundKey(WORLD.tiles[y][x], x, y), x * T, y * T);

    // --- collision: one static zone per solid tile (gate kept separate so it can open) ---
    scene.solidBodies = []; scene.gateBody = null;
    for (let y = 0; y < WORLD.H; y++)
      for (let x = 0; x < WORLD.W; x++) {
        if (!WORLD.SOLID.has(WORLD.tiles[y][x])) continue;
        const z = scene.add.zone(WORLD.cx(x), WORLD.cy(y), T, T);
        scene.physics.add.existing(z, true);
        scene.solidBodies.push(z);
        if (x === WORLD.GATE.x && y === WORLD.GATE.y) scene.gateBody = z;
      }
    scene.openGate = () => {
      if (!scene.gateBody) return;
      const i = scene.solidBodies.indexOf(scene.gateBody);
      if (i >= 0) scene.solidBodies.splice(i, 1);
      scene.gateBody.destroy(); scene.gateBody = null;
    };

    // --- trees + decorative props (depth-sorted, anchored at base) ---
    WORLD.TREES.forEach((tr) => scene.add.image(WORLD.cx(tr.x), WORLD.cy(tr.y) + T / 2, tr.key).setOrigin(0.5, 1).setDepth(baseDepth(tr.y)));
    WORLD.PROPS.forEach((p) => scene.add.image(WORLD.cx(p.x), WORLD.cy(p.y) + T / 2, p.key).setOrigin(0.5, 1).setDepth(baseDepth(p.y)));
    WORLD.BUILDINGS.forEach((bd) => {
      drawBuilding(scene, bd);
      if (bd.sign) {
        const lx = (WORLD.cx(bd.x0) + WORLD.cx(bd.x1)) / 2;
        scene.add.text(lx, WORLD.cy(bd.y0) - 8, bd.sign, {
          fontSize: "11px", color: "#ffe9a8", backgroundColor: "rgba(0,0,0,0.5)", padding: { x: 4, y: 1 },
        }).setOrigin(0.5, 1).setDepth(99998);
      }
    });

    // --- interactive objects ---
    Interact.build(scene);

    // --- player ---
    scene.player = Player.create(scene, WORLD.cx(WORLD.spawn.x), WORLD.cy(WORLD.spawn.y));
    scene.physics.add.collider(scene.player, scene.solidBodies);

    // --- NPCs + dragon ---
    NPCS.forEach((n) => {
      const px = WORLD.cx(n.location.x), py = WORLD.cy(n.location.y);
      n._px = px; n._py = py; n._facing = "down"; n._frame = 0; n._bob = 0; n.isNpc = true;
      let s;
      if (n.isDragon) { s = scene.physics.add.sprite(px, py, "dragon_0").setOrigin(0.5, 0.72); n._dragonT = 0; }
      else { s = scene.physics.add.sprite(px, py, `char_${n.id}_down_0`); if (n.sprite.scale) s.setScale(n.sprite.scale); }
      const bw = n.isDragon ? 44 : 14, bh = n.isDragon ? 22 : 12;
      s.body.setImmovable(true); s.body.moves = false;
      s.body.setSize(bw, bh); s.body.setOffset((s.width - bw) / 2, s.height - bh - (n.isDragon ? 8 : 0));
      s.setDepth(py); n._sprite = s;
      scene.physics.add.collider(scene.player, s);
      scene.add.text(px, py - (n.isDragon ? 64 : 30), n.name, {
        fontSize: "12px", color: "#fff", backgroundColor: "rgba(0,0,0,0.55)", padding: { x: 4, y: 2 },
      }).setOrigin(0.5).setDepth(99999);
    });

    // --- camera follow + minimap ---
    scene.cameras.main.setBounds(0, 0, WW, WH).setRoundPixels(true).startFollow(scene.player, true, 0.12, 0.12);
    const mmW = 162, mmH = Math.round(mmW * WH / WW);
    const mm = scene.cameras.add(scene.scale.width - mmW - 10, 56, mmW, mmH);
    mm.setBackgroundColor(0x0a0f08).setZoom(mmW / WW).centerOn(WW / 2, WH / 2);
    scene.scale.on("resize", (sz) => mm.setPosition(sz.width - mmW - 10, 56)); // keep minimap top-right

    // --- input ---
    scene.cursors = scene.input.keyboard.createCursorKeys();
    scene.keys = scene.input.keyboard.addKeys("W,A,S,D,E");
    scene.prompt = scene.add.text(0, 0, "按 E", {
      fontSize: "13px", color: "#fff", backgroundColor: "rgba(0,0,0,0.72)", padding: { x: 6, y: 3 },
    }).setOrigin(0.5).setDepth(100000).setVisible(false);

    Quest.init(); Dialogue.init(scene); LLM.checkHealth();
  }

  function animateNpcs(scene) {
    const p = scene.player, dt = scene.game.loop.delta;
    for (const n of NPCS) {
      if (n.isDragon) { n._dragonT += dt; if (n._dragonT > 420) { n._dragonT = 0; n._frame ^= 1; n._sprite.setTexture("dragon_" + n._frame); } continue; }
      const dx = p.x - n._px, dy = p.y - n._py, near = Math.abs(dx) < 170 && Math.abs(dy) < 170;
      n._facing = near ? (Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? "left" : "right") : (dy < 0 ? "up" : "down")) : "down";
      n._bob += dt; if (n._bob > 520) { n._bob = 0; n._frame ^= 1; }
      Art.setCharFrame(n._sprite, n.id, n._facing, n._frame);
    }
  }

  function update() {
    const scene = this, p = scene.player;
    animateNpcs(scene);

    // nearest E-target among NPCs and interactable objects
    let near = null, nd = Infinity;
    for (const n of NPCS) { const d = Phaser.Math.Distance.Between(p.x, p.y, n._px, n._py); if (d < nd) { nd = d; near = n; } }
    for (const o of Interact.items) { const d = Phaser.Math.Distance.Between(p.x, p.y, o.px, o.py); if (d < nd) { nd = d; near = o; } }
    const reach = near && near.isDragon ? 84 : CONFIG.INTERACT_DIST;
    const inRange = near && nd <= reach;

    if (window.DIALOGUE_OPEN) { p.body.setVelocity(0, 0); scene.prompt.setVisible(false); return; }

    scene.prompt.setVisible(!!inRange);
    if (inRange) {
      const tx = near.isNpc ? near._px : near.px, ty = near.isNpc ? near._py : near.py;
      scene.prompt.setText(near.isNpc ? "按 E 交谈" : "按 E").setPosition(tx, ty - 44);
    }
    Player.move(scene, p);
    if (inRange && Phaser.Input.Keyboard.JustDown(scene.keys.E)) {
      if (near.isNpc) Dialogue.open(near); else near.interact();
    }
  }

  window.addEventListener("load", () => {
    new Phaser.Game({
      type: Phaser.AUTO,
      pixelArt: true,
      scale: { parent: "game", mode: Phaser.Scale.RESIZE, width: window.innerWidth, height: window.innerHeight },
      physics: { default: "arcade", arcade: { gravity: { y: 0 }, debug: false } },
      scene: { create, update },
    });
  });
})();
