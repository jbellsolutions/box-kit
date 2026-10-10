// Shared helpers for the Steel spike. No secrets. Hard-wired to the spike port (never 3000).
// Run with: NODE_PATH=<scratch>/npm/node_modules node <script>.cjs
const PORT = Number(process.env.STEEL_SPIKE_PORT || 3300);
if (PORT === 3000) throw new Error("refusing to touch the live Steel on :3000");
const BASE = `http://127.0.0.1:${PORT}`;
const WS = `ws://127.0.0.1:${PORT}/`;

async function api(method, path, body, timeoutMs = 120000) {
  const t0 = Date.now();
  const r = await fetch(BASE + path, {
    method,
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await r.text();
  let json;
  try { json = JSON.parse(text); } catch { json = text; }
  return { status: r.status, ms: Date.now() - t0, json };
}

// Minimal raw CDP client over Node's global WebSocket (browser-level target).
async function rawCdp(url = WS) {
  const ws = new WebSocket(url);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pending = new Map(); const events = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else events.push(msg);
  };
  const send = (method, params = {}, sessionId) => new Promise((res) => {
    const mid = ++id; pending.set(mid, res);
    const msg = { id: mid, method, params }; if (sessionId) msg.sessionId = sessionId;
    ws.send(JSON.stringify(msg));
  });
  return { ws, send, events, close: () => ws.close() };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString(), ...a);
module.exports = { PORT, BASE, WS, api, rawCdp, sleep, log };
