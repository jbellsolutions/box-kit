// (c1) Cookie flush: set a cookie (+localStorage) on example.com in a persist:true session, wait W s,
// then end the browser by MODE, then let the caller inspect the on-disk Cookies DB.
// Usage: node c1_flush.cjs <waitSeconds> <mode: steel-release | cdp-browser-close | none> <cookieName>
const { chromium } = require("playwright-core");
const { api, WS, rawCdp, sleep, log } = require("./lib.cjs");
(async () => {
  const W = Number(process.argv[2] || 5), MODE = process.argv[3] || "steel-release", NAME = process.argv[4] || "flushprobe";
  const body = JSON.parse(process.env.CREATE_BODY || '{"persist":true}');
  const s = await api("POST", "/v1/sessions", body);
  log("create", s.status, s.ms + "ms", s.json.id, JSON.stringify(body));
  const b = await chromium.connectOverCDP(WS);
  const ctx = b.contexts()[0];
  const p = await ctx.newPage();
  await p.goto("https://example.com/");
  await p.evaluate((n) => { document.cookie = `${n}=v1; max-age=2592000; path=/`; localStorage.setItem(n, "ls-v1"); }, NAME);
  const ck = (await ctx.cookies("https://example.com")).map((c) => c.name);
  log("cookie readback before end:", JSON.stringify(ck));
  log(`waiting ${W}s`);
  await sleep(W * 1000);
  const t0 = Date.now();
  if (MODE === "steel-release") {
    const r = await api("POST", "/v1/sessions/release", {});
    log("steel release", r.status, r.ms + "ms");
  } else if (MODE === "cdp-browser-close") {
    const c = await rawCdp();
    const r = await Promise.race([c.send("Browser.close"), sleep(15000).then(() => "timeout")]);
    log("raw CDP Browser.close ->", JSON.stringify(r).slice(0, 120), Date.now() - t0 + "ms");
    c.close();
    await sleep(8000); // let Steel notice the disconnect and relaunch its idle browser
  } else { log("mode none: leaving session live"); }
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
