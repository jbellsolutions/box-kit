// (h2) Is the missing fingerprint on Playwright-created tabs a race? newPage -> goto immediately vs after a delay vs 2nd nav.
const { chromium } = require("playwright-core");
const { api, WS, sleep, log } = require("./lib.cjs");
const probe = () => ({ ua: navigator.userAgent.match(/(Headless)?Chrome\/[\d.]+/)[0], hc: navigator.hardwareConcurrency, cursor: !!document.getElementById("__cursor__"), screen: screen.width + "x" + screen.height });
(async () => {
  const s = await api("POST", "/v1/sessions", {});
  log("create", s.status, "session UA", s.json.userAgent.match(/Chrome\/[\d.]+/)[0]);
  const b = await chromium.connectOverCDP(WS);
  const ctx = b.contexts()[0];
  const p1 = await ctx.newPage(); await p1.goto("https://example.com/");
  log("newPage+immediate goto:", JSON.stringify(await p1.evaluate(probe)));
  await p1.goto("https://example.com/?2");
  log("same tab, 2nd navigation:", JSON.stringify(await p1.evaluate(probe)));
  const p2 = await ctx.newPage(); await sleep(3000); await p2.goto("https://example.com/");
  log("newPage+3s wait+goto:", JSON.stringify(await p2.evaluate(probe)));
  const p0 = ctx.pages()[0]; await p0.goto("https://example.com/");
  log("primary page:", JSON.stringify(await p0.evaluate(probe)));
  await api("POST", "/v1/sessions/release", {});
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
