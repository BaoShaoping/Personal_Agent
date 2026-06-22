// Texture factory: bake pixel-maps / canvas drawings into Phaser textures at boot.
// Keeps the whole game self-contained (no external image files, works offline).
window.PIXELS = (function () {

  // Bake a string-grid (array of equal-length strings) into a texture.
  // `resolve(ch,x,y)` returns a css color string, or null for transparent.
  function bake(scene, key, grid, resolve, scale) {
    scale = scale || 1;
    const h = grid.length, w = grid[0].length;
    if (scene.textures.exists(key)) scene.textures.remove(key);
    const tex = scene.textures.createCanvas(key, w * scale, h * scale);
    const ctx = tex.getContext();
    ctx.imageSmoothingEnabled = false;
    for (let y = 0; y < h; y++) {
      const row = grid[y];
      for (let x = 0; x < w; x++) {
        const c = resolve(row[x], x, y);
        if (c == null) continue;
        ctx.fillStyle = c;
        ctx.fillRect(x * scale, y * scale, scale, scale);
      }
    }
    tex.refresh();
    return key;
  }

  // Bake a free-form canvas drawing of arbitrary size (trees, dragon, banners…).
  function canvasWH(scene, key, w, h, draw) {
    if (scene.textures.exists(key)) scene.textures.remove(key);
    const tex = scene.textures.createCanvas(key, w, h);
    const ctx = tex.getContext();
    ctx.imageSmoothingEnabled = false;
    draw(ctx, w, h);
    tex.refresh();
    return key;
  }

  // Square convenience wrapper (good for tiles).
  function canvas(scene, key, size, draw) {
    return canvasWH(scene, key, size, size, (ctx) => draw(ctx, size));
  }

  // tiny deterministic RNG so textures look the same every run
  function rng(seed) {
    return function () {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 4294967296;
    };
  }

  return { bake, canvas, canvasWH, rng };
})();
