// The relay between the public demo page and the demo-run workflow.
//
// The page cannot start a GitHub workflow itself, because that takes a token
// and anything in a public page is public. This Cloudflare Worker holds the
// token as a secret, accepts one POST /run from the demo page, gives the run
// an id, and starts .github/workflows/demo-run.yml with the visitor's saved
// settings. The token needs one permission, Actions read and write, on the
// swing-trader repository alone.
//
// Limits, counted in the LIMITS key-value store: PER_IP_HOUR runs an hour from
// one address and PER_DAY runs a day in all, so nobody can queue the runner
// solid. Both are set in wrangler.toml.

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "content-type": "application/json" },
  });
}

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOW_ORIGIN,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
    };
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    const url = new URL(req.url);
    if (req.method !== "POST" || url.pathname !== "/run") return json({ error: "not found" }, 404, cors);

    const text = await req.text();
    if (text.length > 60000) return json({ error: "Those settings are too large to send." }, 413, cors);
    let data;
    try { data = JSON.parse(text); } catch { return json({ error: "The settings could not be read." }, 400, cors); }
    if (typeof data !== "object" || data === null || typeof data.config !== "object") {
      return json({ error: "No settings were sent." }, 400, cors);
    }

    const ip = req.headers.get("cf-connecting-ip") || "unknown";
    const iso = new Date().toISOString();
    const kIp = `ip:${ip}:${iso.slice(0, 13)}`;
    const kDay = `day:${iso.slice(0, 10)}`;
    const nIp = Number((await env.LIMITS.get(kIp)) || 0);
    const nDay = Number((await env.LIMITS.get(kDay)) || 0);
    if (nIp >= Number(env.PER_IP_HOUR)) {
      return json({ error: `That is ${env.PER_IP_HOUR} runs from you this hour, the most allowed. Try again next hour.` }, 429, cors);
    }
    if (nDay >= Number(env.PER_DAY)) {
      return json({ error: "Today's runs are all used. Try again tomorrow." }, 429, cors);
    }

    // 20260924-153000-abc123, the shape demo_run.py checks for.
    const runId = `${iso.slice(0, 10).replace(/-/g, "")}-${iso.slice(11, 19).replace(/:/g, "")}-` +
      crypto.randomUUID().replace(/-/g, "").slice(0, 6);
    const name = String(data.name || "").replace(/[^\w .'-]/g, "").slice(0, 40);

    const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/demo-run.yml/dispatches`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.GITHUB_TOKEN}`,
        accept: "application/vnd.github+json",
        "x-github-api-version": "2022-11-28",
        "user-agent": "swing-trader-relay",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: { run_id: runId, name, config: JSON.stringify(data.config) },
      }),
    });
    if (r.status !== 204) {
      return json({ error: "The runner did not accept the run. Try again in a few minutes." }, 502, cors);
    }
    await env.LIMITS.put(kIp, String(nIp + 1), { expirationTtl: 7200 });
    await env.LIMITS.put(kDay, String(nDay + 1), { expirationTtl: 172800 });
    return json({ run_id: runId }, 200, cors);
  },
};
