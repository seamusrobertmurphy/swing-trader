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
//
// Deploy, round two task 7 of 26 September 2026. POST /order stores a paper
// order shaped like Alpaca's order request (symbol, side, notional, type,
// time_in_force, client_order_id) against an anonymous device id, in the same
// key-value store, with the order in the key's metadata so a listing needs no
// second read. GET /orders?device=<id> lists one device's orders and GET
// /orders lists them all for the hourly settlement job, which fills and
// settles them on public prices. Nothing here reaches a broker: the book is
// long only and paper only, so side must be buy.

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
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
    };
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/order") return order(req, env, cors);
    if (req.method === "GET" && url.pathname === "/orders") return orders(url, env, cors);
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

const DEVICE = /^[a-z0-9]{16,40}$/;
const PRESETS = ["best", "threeway", "quick"];
const FRAMES = ["15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"];

async function order(req, env, cors) {
  const text = await req.text();
  if (text.length > 4000) return json({ error: "That order is too large to send." }, 413, cors);
  let d;
  try { d = JSON.parse(text); } catch { return json({ error: "The order could not be read." }, 400, cors); }
  const o = (d && d.order) || {}, s = (d && d.signal) || {};
  const device = String((d && d.device) || "");
  const symbol = String(o.symbol || "").toUpperCase();
  const notional = Number(o.notional);
  if (!DEVICE.test(device)) return json({ error: "This browser has no device id." }, 400, cors);
  if (!/^[A-Z0-9]{1,12}(\/USDT)?$/.test(symbol)) return json({ error: "That symbol is not offered." }, 400, cors);
  if (o.side !== "buy") return json({ error: "Only buy orders; the book never sells short." }, 400, cors);
  if (!(notional >= 10 && notional <= 100000)) return json({ error: "Choose an amount from 10 to 100,000 dollars." }, 400, cors);
  if (!PRESETS.includes(s.preset) || !FRAMES.includes(s.frame) || !["crypto", "equity"].includes(s.market)) {
    return json({ error: "That signal could not be read." }, 400, cors);
  }
  const expires = new Date(s.expires);
  if (isNaN(expires) || expires <= new Date()) return json({ error: "That signal has expired." }, 400, cors);

  const iso = new Date().toISOString();
  const kDev = `odev:${device}:${iso.slice(0, 13)}`;
  const kDay = `oday:${iso.slice(0, 10)}`;
  const nDev = Number((await env.LIMITS.get(kDev)) || 0);
  const nDay = Number((await env.LIMITS.get(kDay)) || 0);
  if (nDev >= 20) return json({ error: "That is 20 orders from this browser this hour. Try again next hour." }, 429, cors);
  if (nDay >= 1000) return json({ error: "Today's orders are all used. Try again tomorrow." }, 429, cors);

  const id = `${iso.slice(0, 10).replace(/-/g, "")}-${iso.slice(11, 19).replace(/:/g, "")}-` +
    crypto.randomUUID().replace(/-/g, "").slice(0, 6);
  const rec = {
    id, device, submitted_at: iso, status: "accepted",
    symbol, side: "buy", type: "market", time_in_force: "gtc", notional: Math.round(notional * 100) / 100,
    client_order_id: String(o.client_order_id || id).slice(0, 48),
    market: s.market, preset: s.preset, frame: s.frame, horizon: Number(s.horizon) || 0,
    signal_generated: String(s.generated || "").slice(0, 32), expires: expires.toISOString(),
    expected: Number.isFinite(Number(s.expected)) ? Number(s.expected) : null,
    confidence: Number(s.confidence) || null,
  };
  await env.LIMITS.put(`order:${device}:${id}`, "", { metadata: rec, expirationTtl: 7776000 });
  await env.LIMITS.put(kDev, String(nDev + 1), { expirationTtl: 7200 });
  await env.LIMITS.put(kDay, String(nDay + 1), { expirationTtl: 172800 });
  return json({ order: rec }, 200, cors);
}

async function orders(url, env, cors) {
  const device = url.searchParams.get("device") || "";
  if (device && !DEVICE.test(device)) return json({ error: "That device id could not be read." }, 400, cors);
  const out = [];
  let cursor;
  do {
    const page = await env.LIMITS.list({ prefix: device ? `order:${device}:` : "order:", cursor });
    for (const k of page.keys) if (k.metadata) out.push(k.metadata);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return json({ orders: out }, 200, cors);
}
