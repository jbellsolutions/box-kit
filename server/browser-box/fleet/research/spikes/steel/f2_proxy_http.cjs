// (f2) With a dead upstream proxy, what does an http:// navigation actually return?
const { chromium } = require("playwright-core");
const { api, WS, log } = require("./lib.cjs");
(async () => {
  const s = await api("POST", "/v1/sessions", { proxyUrl: "http://fleetuser:fleetpass@127.0.0.1:9" });
  log("create", s.status);
  const b = await chromium.connectOverCDP(WS);
  const p = await b.contexts()[0].newPage();
  const resp = await p.goto("http://example.com/", { timeout: 20000 });
  log("http status", resp.status(), "headers.server", resp.headers()["server"], "body:", (await p.evaluate(() => document.body.innerText)).slice(0, 160).replace(/\n/g, " "));
  await api("POST", "/v1/sessions/release", {});
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
