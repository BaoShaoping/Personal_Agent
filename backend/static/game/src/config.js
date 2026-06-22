// Global config + world flavor text. No build step: plain global `CONFIG`.
window.CONFIG = {
  // Cloudflare Worker (key-hiding proxy; holds the GLM key as a Worker secret — never in the game).
  // Swap to "http://localhost:8787/" to use the local Python proxy. "" = canned fallback only.
  PROXY_URL: "https://glm-proxy.1421608856.workers.dev/",

  MODEL: "glm-4.5-air",
  TILE: 32,

  // The world is now much bigger than the screen — the camera follows the player.
  MAP_W: 50,
  MAP_H: 38,
  VIEW_W: 832, // visible canvas (26 x 19 tiles)
  VIEW_H: 608,

  PLAYER_SPEED: 185,
  INTERACT_DIST: 52,     // px: how close you must stand to press E
  MEMORY_TURNS: 6,       // rolling per-NPC conversation memory
  LANG: "中文",

  WORLD_SETTING:
    "「井村」坐落在群山脚下：村中有老水井和木屋，往西是农田，往北是密林，往东是一片湖水，" +
    "再往北的山里藏着一个被古老封印锁住的洞窟。传说洞中沉睡着赤鳞巨龙。" +
    "昨夜水井的钥匙失窃，而那把钥匙，据说也能开启山中洞窟的封印……",

  SITUATION: "村里为失窃的钥匙人心惶惶，山中又隐隐传来龙吟，气氛不太平静。",
};
