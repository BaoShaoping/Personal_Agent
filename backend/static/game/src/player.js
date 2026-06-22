// Player sprite (animated pixel character) + movement.
window.Player = (function () {
  function create(scene, px, py) {
    const p = scene.physics.add.sprite(px, py, "char_hero_down_0");
    p.charId = "hero"; p.facing = "down"; p.frame2 = 0; p.animT = 0;
    p.body.setSize(14, 12);
    p.body.setOffset((p.width - 14) / 2, p.height - 14); // collide box near the feet
    p.body.setCollideWorldBounds(true);
    p.setDepth(py);
    return p;
  }

  function move(scene, p) {
    const c = scene.cursors, k = scene.keys;
    const left = c.left.isDown || k.A.isDown;
    const right = c.right.isDown || k.D.isDown;
    const up = c.up.isDown || k.W.isDown;
    const down = c.down.isDown || k.S.isDown;

    let vx = (right ? 1 : 0) - (left ? 1 : 0);
    let vy = (down ? 1 : 0) - (up ? 1 : 0);
    if (vx && vy) { const inv = 1 / Math.sqrt(2); vx *= inv; vy *= inv; }
    p.body.setVelocity(vx * CONFIG.PLAYER_SPEED, vy * CONFIG.PLAYER_SPEED);

    if (vx || vy) {
      p.facing = Math.abs(vx) >= Math.abs(vy) ? (vx < 0 ? "left" : "right") : (vy < 0 ? "up" : "down");
      p.animT += scene.game.loop.delta;
      if (p.animT > 130) { p.animT = 0; p.frame2 ^= 1; }
    } else {
      p.frame2 = 0;
    }
    Art.setCharFrame(p, "hero", p.facing, p.frame2);
    p.setDepth(p.y);
  }

  return { create, move };
})();
