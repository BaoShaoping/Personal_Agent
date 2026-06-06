/* Cloudflare Worker — thin GLM proxy that hides the API key.
 *
 * The browser POSTs OpenAI-style { messages, temperature?, max_tokens?, thinking? };
 * this Worker injects the secret key + model and forwards to GLM's v4 endpoint,
 * returning { ok, answer, usage }. The key never reaches the browser.
 *
 * Setup (Cloudflare dashboard → your Worker → Settings → Variables and Secrets):
 *   - Secret  GLM_API_KEY = <your Zhipu GLM key>      (required)
 *   - Variable GLM_MODEL  = glm-4.5-air               (optional; default below)
 *
 * On any GLM failure (including the key's "max 3 concurrent" rejection) it returns
 * { ok: false, ... } with HTTP 200 so the frontend can gracefully fall back to a
 * rule-based quest / template narration instead of hard-failing.
 */

const GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions";

// For a quick start this allows any origin. Tighten to your site's origin for production,
// e.g. "https://your-site.pages.dev".
const ALLOW_ORIGIN = "*";

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": ALLOW_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json", ...corsHeaders() },
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders() });
    if (request.method !== "POST") return json({ ok: false, error: "POST only" }, 405);
    if (!env.GLM_API_KEY) return json({ ok: false, error: "server missing GLM_API_KEY" }, 200);

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return json({ ok: false, error: "invalid JSON body" }, 400);
    }

    const payload = {
      model: body.model || env.GLM_MODEL || "glm-4.5-air",
      messages: Array.isArray(body.messages) ? body.messages : [],
      temperature: typeof body.temperature === "number" ? body.temperature : 0.7,
      max_tokens: body.max_tokens || 1024,
    };
    if (body.thinking) payload.thinking = body.thinking;

    let res;
    try {
      res = await fetch(GLM_URL, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer " + env.GLM_API_KEY,
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      return json({ ok: false, error: "upstream fetch failed: " + e }, 200);
    }

    const text = await res.text();
    if (!res.ok) {
      // GLM rejected (e.g. >3 concurrent, rate limit, bad key) — let the client degrade.
      return json({ ok: false, status: res.status, error: text.slice(0, 300) }, 200);
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return json({ ok: false, error: "invalid upstream JSON" }, 200);
    }

    const choice = (data.choices || [])[0] || {};
    const answer = (choice.message || {}).content || "";
    return json({ ok: true, answer: answer, usage: data.usage || null });
  },
};
