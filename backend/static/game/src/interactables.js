// Interactive objects you press E on (not NPCs). Each reads/writes Quest state and
// shows a simple (non-LLM) message via Dialogue.message().
window.Interact = (function () {
  const TILE = CONFIG.TILE;
  const DEFAULT_TEX = {
    well: "obj_well", sign: "obj_sign", chest: "obj_chest_closed",
    campfire: "obj_campfire_lit", cave_door: "obj_door_closed", boat: "obj_boat", altar: "obj_altar",
  };
  let items = [];

  function chestKey(d) { return `chest_${d.x}_${d.y}`; }

  function build(scene) {
    items = WORLD.INTERACTABLES.map((def) => {
      let tex = DEFAULT_TEX[def.type] || "obj_sign";
      if (def.type === "chest" && Quest.getFlag(chestKey(def))) tex = "obj_chest_open";
      if (def.type === "cave_door" && Quest.getFlag("cave_open")) tex = "obj_door_open";
      const px = WORLD.cx(def.x), py = WORLD.cy(def.y) + TILE / 2; // sit on the tile's bottom edge
      const spr = scene.add.image(px, py, tex).setOrigin(0.5, 1).setDepth(py);
      const o = { def, px: WORLD.cx(def.x), py: WORLD.cy(def.y), spr, type: def.type, isNpc: false };
      o.interact = () => handle(scene, o);
      return o;
    });
    return items;
  }

  function handle(scene, o) {
    const d = o.def;
    switch (o.type) {
      case "sign":
        return Dialogue.message(d.label || "木牌", d.text || "（字迹模糊）");

      case "well":
        return Dialogue.message("古井", Quest.getFlag("key_returned")
          ? "井盖重新锁好了，清水汩汩。井村又有水喝了。"
          : "古老的水井。井盖上着锁——没有那把钥匙，谁也打不开。");

      case "altar":
        return Dialogue.message("石祭坛", "一座苔痕斑驳的石祭坛，似是先人用来安抚山神的。坛上刻着盘龙的纹样。");

      case "chest": {
        if (Quest.getFlag(chestKey(d))) return Dialogue.message(d.label || "木箱", "箱子已经空了。");
        Quest.setFlag(chestKey(d), true);
        o.spr.setTexture("obj_chest_open");
        Quest.addItem(d.gives);
        return Dialogue.message(d.label || "木箱", `你打开箱子，得到了「${Quest.itemName(d.gives)}」。`);
      }

      case "campfire": {
        if (Quest.hasItem("lit_torch")) return Dialogue.message("篝火", "篝火噼啪燃烧。你的火把已经点亮了。");
        if (!Quest.hasItem("torch")) return Dialogue.message("篝火", "一堆篝火在噼啪燃烧。你需要一支火把，才能从这里取火。");
        Quest.removeItem("torch"); Quest.addItem("lit_torch");
        return Dialogue.message("篝火", "你把火把凑近篝火——呼地一下点燃了！（火把已点燃）");
      }

      case "cave_door": {
        if (Quest.getFlag("cave_open")) return Dialogue.message("封印石门", "石门洞开，门后漆黑幽深，隐隐传来龙息。");
        if (!Quest.hasItem("old_key")) return Dialogue.message("封印石门", "巨大的石门上缠着古老的封印，需要一把特别的钥匙才能开启。");
        if (!Quest.hasItem("lit_torch")) return Dialogue.message("封印石门", "钥匙似乎合得上锁孔……但门后一片漆黑，你需要光亮才敢踏入。");
        Quest.setFlag("cave_open", true);
        o.spr.setTexture("obj_door_open");
        if (scene.openGate) scene.openGate();
        return Dialogue.message("封印石门", "钥匙转动，封印崩解，石门轰然开启！一股灼热的龙息自洞中涌出……（北山封印已开）");
      }

      case "boat": {
        const a = d, bdst = d.to;
        const p = scene.player;
        const dA = Phaser.Math.Distance.Between(p.x, p.y, WORLD.cx(a.x), WORLD.cy(a.y));
        const dB = Phaser.Math.Distance.Between(p.x, p.y, WORLD.cx(bdst.x), WORLD.cy(bdst.y));
        const target = dA <= dB ? bdst : a;             // hop to the far landing
        p.setPosition(WORLD.cx(target.x), WORLD.cy(target.y));
        o.spr.setPosition(WORLD.cx(target.x), WORLD.cy(target.y) + TILE / 2);
        o.px = WORLD.cx(target.x); o.py = WORLD.cy(target.y); // move the boat's E-point too
        return Dialogue.message("小船", "你撑起小船，悠悠渡过湖面。");
      }
    }
  }

  return { build, get items() { return items; } };
})();
