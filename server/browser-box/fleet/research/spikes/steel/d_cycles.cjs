// (d) N create/use/release cycles: count non-200s, timing, zombie count after.
// Usage: CREATE_BODY='{"persist":true}' node d_cycles.cjs <N>
const { chromium } = require("playwright-core");
const { execSync } = require("child_process");
const { api, WS, log } = require("./lib.cjs");
(async () => {
  const N = Number(process.argv[2] || 8);
  const body = JSON.parse(process.env.CREATE_BODY || '{"persist":true}');
  const res = { create: {}, release: {}, createMs: [], releaseMs: [] };
  for (let i = 0; i < N; i++) {
    const c = await api("POST", "/v1/sessions", body);
    res.create[c.status] = (res.create[c.status] || 0) + 1; res.createMs.push(c.ms);
    try {
      const b = await chromium.connectOverCDP(WS, { timeout: 20000 });
      const p = await b.contexts()[0].newPage(); await p.goto("https://example.com/", { timeout: 20000 });
      await b.close();
    } catch (e) { log("cycle", i, "client error", e.message.split("\n")[0]); }
    const r = await api("POST", "/v1/sessions/release", {});
    res.release[r.status] = (res.release[r.status] || 0) + 1; res.releaseMs.push(r.ms);
    if (r.status !== 200) log("cycle", i, "release", r.status, JSON.stringify(r.json).slice(0, 200));
  }
  const z = execSync(`docker exec fleet-spike-steel sh -c "ps -eo stat | grep -c '^Z' || true"`).toString().trim();
  log("RESULT", JSON.stringify(res), "zombies:", z);
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
