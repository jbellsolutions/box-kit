// (f) Per-session proxy plumbing with a deliberately dead proxy (no real proxy, no credentials of value).
const { chromium } = require("playwright-core");
const { api, WS, log } = require("./lib.cjs");
(async () => {
  const proxyUrl = process.argv[2] || "http://fleetuser:fleetpass@127.0.0.1:9";
  const s = await api("POST", "/v1/sessions", { proxyUrl });
  log("create", s.status, s.ms + "ms", "response.proxy =", JSON.stringify(s.json.proxy), "keys:", Object.keys(s.json).join(","));
  const l = await api("GET", "/v1/sessions");
  log("GET /v1/sessions active.proxy =", JSON.stringify(l.json.sessions[0].proxy));
  const g = await api("GET", `/v1/sessions/${s.json.id}`);
  log("GET /v1/sessions/{id}.proxy =", JSON.stringify(g.json.proxy));
  const b = await chromium.connectOverCDP(WS);
  const p = await b.contexts()[0].newPage();
  try { await p.goto("http://example.com/", { timeout: 20000 }); log("navigation unexpectedly OK", p.url()); }
  catch (e) { log("navigation error:", e.message.split("\n")[0]); }
  try { await p.goto("https://example.com/", { timeout: 20000 }); log("https navigation unexpectedly OK"); }
  catch (e) { log("https navigation error:", e.message.split("\n")[0]); }
  const r = await api("POST", "/v1/sessions/release", {});
  log("release", r.status, r.ms + "ms");
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
