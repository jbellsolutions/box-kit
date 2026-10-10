// (c2) After a container restart: create a session (CREATE_BODY), report example.com cookies,
// localStorage and which --user-data-dir the running Chromium actually uses.
// Usage: CREATE_BODY='{"persist":true}' node c2_check.cjs [release:yes|no]
const { chromium } = require("playwright-core");
const { execSync } = require("child_process");
const { api, WS, log } = require("./lib.cjs");
(async () => {
  const body = JSON.parse(process.env.CREATE_BODY || '{"persist":true}');
  const s = await api("POST", "/v1/sessions", body);
  log("create", s.status, s.ms + "ms", s.json.id || JSON.stringify(s.json).slice(0, 300));
  const dirs = execSync(`docker exec ${process.env.CONTAINER || "fleet-spike-steel"} sh -c "ps -eo stat,args | grep -v '^Z' | grep -o 'user-data-dir=[^ ]*' | sort | uniq -c"`).toString().trim();
  log("live chromium user-data-dir(s):", dirs.replace(/\n/g, " | "));
  const b = await chromium.connectOverCDP(WS);
  const ctx = b.contexts()[0];
  const ck = (await ctx.cookies("https://example.com")).map((c) => c.name).sort();
  const p = await ctx.newPage();
  await p.goto("https://example.com/");
  const ls = await p.evaluate(() => Object.fromEntries(Object.keys(localStorage).map((k) => [k, localStorage.getItem(k)])));
  const idb = await p.evaluate(async () => (indexedDB.databases ? (await indexedDB.databases()).map((d) => d.name) : "n/a"));
  log("RESULT cookies:", JSON.stringify(ck), "localStorage:", JSON.stringify(ls), "indexedDB:", JSON.stringify(idb));
  await p.close();
  if ((process.argv[2] || "yes") === "yes") {
    const r = await api("POST", "/v1/sessions/release", {});
    log("release", r.status, r.ms + "ms");
  }
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
