# GLM 代理（Cloudflare Worker）

一段藏 GLM key 的瘦代理：浏览器把 `{messages,...}` 发给它，它注入 key + 模型转发给 GLM，返回 `{ok, answer, usage}`。**key 永远不进浏览器。** 免费、无主机、零运维。

代理脚本：[`glm-proxy.js`](glm-proxy.js)。

---

## 一、部署 Worker（网页控制台，免装 Node）

1. 登录 https://dash.cloudflare.com 。
2. 左侧 **Build → Compute**（新版导航里 Workers 在这；旧名「Workers & Pages」）。
3. **Create → Workers → Start with Hello World!** → 起名（如 `glm-proxy`）→ **Deploy**。
4. 进入该 Worker → **Edit code** → 清空编辑器 → 粘贴 [`glm-proxy.js`](glm-proxy.js) 全部内容 → **Deploy**。
5. 记下分配的地址，例如：`https://glm-proxy.<你的子域>.workers.dev/`。

> 不需要买域名；`*.workers.dev` 免费自带。其它创建方式（Connect GitHub / Upload static files / template）都用不上，Hello World 最省事。

## 二、配置密钥与模型

进入该 Worker → **Settings → Variables and Secrets**：

| 类型 | 名称 | 值 | 必填 |
|---|---|---|---|
| **Secret** | `GLM_API_KEY` | 你的智谱 GLM key（就是本地那把） | ✅ 必填 |
| **Variable** | `GLM_MODEL` | `glm-4.5-air` | 可选（默认即 glm-4.5-air）|

加完保存（会自动重新部署）。`GLM_API_KEY` 是 Secret，存于服务端，浏览器/网络都看不到。

## 三、测试 Worker

```powershell
curl.exe -X POST "https://glm-proxy.<你的子域>.workers.dev/" -H "content-type: application/json" -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Reply with: hello host\"}],\"max_tokens\":256,\"thinking\":{\"type\":\"disabled\"}}'
```

返回 `{"ok":true,"answer":"hello host",...}` 即成功。
- 用**英文**测试最稳；命令行传**中文**可能因终端编码而乱码（这是命令行的问题，不是 Worker 的——浏览器前端发的是规范 UTF-8，不受影响）。
- glm-4.5-air / glm-4.6 是**推理模型**：若不传 `thinking:{type:"disabled"}` 且 `max_tokens` 太小，推理会吃光预算导致 `answer` 为空。前端已默认带 `thinking:disabled`。

## 四、让前端连到这个 Worker

前端 [`backend/static/system.js`](../backend/static/system.js) 里有：
```js
const DEFAULT_PROXY_URL = "https://glm-proxy.1421608856.workers.dev/";
```
两种指向方式：
- **改默认值**：把 `DEFAULT_PROXY_URL` 改成你的 Worker 地址（部署前端时用这个）。
- **不改代码、临时覆盖**：在浏览器开发者控制台执行
  ```js
  localStorage.setItem("proxy_url", "https://你的-worker.workers.dev/");
  ```
  刷新页面即生效（`proxy_url` 优先于默认值）。把它清空（`localStorage.removeItem("proxy_url")`）则回到默认。

前端调用：点「✦ 系统生成任务」→ system.js 用系统人设 prompt + 计划上下文 POST 到 Worker（`thinking:disabled`、glm-4.5-air）→ 解析返回的 JSON 任务。

## 五、容错与成本

- **GLM 失败自动降级**：Worker 在 GLM 报错（含 key「最多 3 并发」被拒、限流、key 失效）时返回 `ok:false`（HTTP 200），前端据此**降级为规则任务 / 模板旁白**，不会硬报错或卡死。
- **CORS**：脚本里 `ALLOW_ORIGIN = "*"`（任何来源可调，方便起步）。正式上线建议改成你前端的域名，例如 `https://your-site.pages.dev`。
- **成本**：Cloudflare Workers 免费档（约 10 万次/天）足够 closed beta；真正花钱的是 GLM 调用本身（走你的 key），公开版用 glm-4.5-air 已是快而省的选择。
