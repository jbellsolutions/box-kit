// (e) Candidate safe release: export context -> wait >30 s since last auth change -> raw CDP Browser.close
// (clean Chromium exit, no stale Singleton*) -> POST /v1/sessions/release (reset Steel bookkeeping).
const fs = require("fs");
const { chromium } = require("playwright-core");
const { execSync } = require("child_process");
const { api, WS, rawCdp, sleep, log } = require("./lib.cjs");
const sh = (c) => execSync(`docker exec fleet-spike-steel sh -c "${c}"`).toString().trim();
(async () => {
  const W = Number(process.argv[2] || 31);
  const s = await api("POST", "/v1/sessions", { persist: true });
  log("create", s.status, s.json.id);
  const b = await chromium.connectOverCDP(WS);
  const p = await b.contexts()[0].newPage(); await p.goto("https://example.com/");
  await p.evaluate(() => { document.cookie = "safe_rel=1; max-age=2592000; path=/"; });
  const ctx = await api("GET", `/v1/sessions/${s.json.id}/context`);
  log("context export cookies:", JSON.stringify((ctx.json.cookies || []).map((c) => c.name)));
  await b.close();
  log(`wait ${W}s`); await sleep(W * 1000);
  const c = await rawCdp(); const r = await c.send("Browser.close"); c.close();
  log("Browser.close", JSON.stringify(r));
  await sleep(3000);
  log("session list after Browser.close:", JSON.stringify((await api("GET", "/v1/sessions")).json.sessions.slice(0, 1).map((x) => x.status)));
  const rel = await api("POST", "/v1/sessions/release", {});
  log("release", rel.status, rel.ms + "ms");
  log("Singleton files in profile:", sh("ls /app/api/user-data-dir | grep -c Singleton || true"));
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
