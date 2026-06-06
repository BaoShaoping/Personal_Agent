# 部署指南 · 托管 Beta（Phase 3）

把「系统」面板放到一个公开链接，给内测用户用、收集反馈。架构（见 `HOSTED_BETA_DESIGN.md`）：
- **静态前端**（`backend/static/` 的 system.* + system_avatars.js）→ 部署到 **Cloudflare Pages**（免费）。数据全在用户浏览器。
- **GLM 代理** → 已部署的 **Cloudflare Worker**（藏 key，见 `cloudflare-worker/README.md`）。
- **邮箱 + 反馈** → 外部收集器（**Formspree** 等），服务端零存储。

---

## 一、建收集器（Formspree，免费）

1. 注册 https://formspree.io 。
2. 建**两个 form**（或一个也行）：一个收**内测邮箱**、一个收**反馈**。各拿到一个端点，形如 `https://formspree.io/f/abcdwxyz`。
3. 前端配置（`backend/static/system.js` 顶部）：
   ```js
   const DEFAULT_SIGNUP_URL = "https://formspree.io/f/<邮箱form>";
   const DEFAULT_FEEDBACK_URL = "https://formspree.io/f/<反馈form>";
   ```
   （也可不改代码、在浏览器控制台临时设：`localStorage.setItem("signup_url","…")` / `localStorage.setItem("feedback_url","…")`。）
   - 留空也能跑：门槛只在本地记邮箱、反馈只弹 toast，不报错——但收不到名单/反馈。

> Formspree 免费档每月有提交次数上限，closed beta 足够。它替你存名单/反馈，**我们自己零存储**。

## 二、确认 GLM 代理已就绪

`system.js` 的 `DEFAULT_PROXY_URL` 已指向你的 Worker（`https://glm-proxy.1421608856.workers.dev/`）。换了 Worker 就改这里，或控制台 `localStorage.setItem("proxy_url","…")`。详见 `cloudflare-worker/README.md`。

## 三、部署静态前端到 Cloudflare Pages

仓库目前是**本地 git、未连 GitHub**，所以用 **Direct Upload**（免 GitHub）：

1. Cloudflare 控制台 → **Workers & Pages / Compute → Create → Pages → Upload assets**。
2. 项目起名（如 `system-panel`）。
3. 把 **`backend/static/` 整个文件夹**拖进去上传（里面含 system.*、system_avatars.js、`_redirects`；另有 app.*/debug_* 是旧文件，无害）。
4. 部署完成 → 拿到 `https://system-panel.pages.dev`。
   - 根路径 `/` 会通过 `_redirects` 跳到 `/system.html`（面板）。
5. 之后改了前端，重新 Upload 一次即可（或接 GitHub 自动部署）。

> CORS：`cloudflare-worker/glm-proxy.js` 里 `ALLOW_ORIGIN = "*"` 现在能直接用。上线想收紧，改成你的 Pages 域名（如 `https://system-panel.pages.dev`）再重部署 Worker。

## 四、closed beta 检查清单

- [ ] Formspree 两个端点已建，`DEFAULT_SIGNUP_URL` / `DEFAULT_FEEDBACK_URL` 填好
- [ ] Worker 正常（`cloudflare-worker/README.md` 的 curl 测试返回 `ok:true`）
- [ ] Pages 部署成功，打开链接出现**邮箱门槛** → 输入邮箱进入 → 面板正常
- [ ] 点「✦ 系统生成任务」来源显示「系统（GLM）生成」；断网/超限时自动降级规则任务
- [ ] 完成任务、换装、刷新后进度仍在（localStorage）
- [ ] 点「反馈」能提交（Formspree 收到）
- [ ] 把链接发给一小撮内测用户，观察反馈

## 备注
- 本地开发仍可跑 Flask：`/system` 会重定向到 `/static/system.html`（资源走相对路径）。
- 每个用户数据在各自浏览器、匿名、与邮箱不绑定；清缓存/换设备会丢进度（beta 可接受）。
