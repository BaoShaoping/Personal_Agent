# GLM 代理（Cloudflare Worker）

一段藏 GLM key 的瘦代理：浏览器把 `{messages,...}` 发给它，它注入 key + 模型转发给 GLM，返回 `{ok, answer, usage}`。**key 永远不进浏览器。** 免费、无主机、零运维。

## 部署（网页控制台，免安装 Node）

1. 注册/登录 https://dash.cloudflare.com （免费）。
2. 左侧 **Workers & Pages → Create → Create Worker**，起个名（如 `glm-proxy`）→ **Deploy**（先建一个 hello world）。
3. **Edit code**，把本目录 `glm-proxy.js` 全部内容粘进去 → **Deploy**。
4. 进该 Worker 的 **Settings → Variables and Secrets**：
   - 加一个 **Secret**：`GLM_API_KEY` = 你的智谱 GLM key（就是本地那把）。
   - （可选）加一个 **Variable**：`GLM_MODEL` = `glm-4.5-air`。
   - 保存 / 重新部署。
5. 拿到地址：`https://glm-proxy.<你的子域>.workers.dev`。

## 测一下（PowerShell）

```powershell
curl.exe -X POST "https://glm-proxy.<你的子域>.workers.dev" `
  -H "content-type: application/json" `
  -d '{\"messages\":[{\"role\":\"user\",\"content\":\"用一句话问候宿主\"}]}'
```

返回 `{"ok":true,"answer":"..."}` 就成功了。把这个 URL 给我，我来把前端（system.js）的任务生成/旁白指向它（Phase 2）。

## 备注
- `ALLOW_ORIGIN` 现在是 `*`（任何来源可调）。上线时改成你前端的域名更安全。
- GLM 失败（含 key「最多 3 并发」被拒）时返回 `ok:false`，前端会**优雅降级**为规则任务/模板旁白，不会硬报错。
- 想用 wrangler CLI 部署需要 Node；网页控制台不需要，推荐先用控制台。
