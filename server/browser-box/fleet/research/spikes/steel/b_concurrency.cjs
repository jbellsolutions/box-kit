// (b) What happens when a second session is created while session A is live and a client is attached?
// Usage: node b_concurrency.cjs '<bodyA json>' '<bodyB json>'
const { chromium } = require("playwright-core");
const { api, WS, sleep, log } = require("./lib.cjs");
(async () => {
  const bodyA = JSON.parse(process.argv[2] || "{}");
  const bodyB = JSON.parse(process.argv[3] || "{}");
  const A = await api("POST", "/v1/sessions", bodyA);
  log("A create", A.status, A.ms + "ms", A.json.id);
  const browser = await chromium.connectOverCDP(WS);
  let disconnected = false;
  browser.on("disconnected", () => { disconnected = true; log("A client: browser 'disconnected' event"); });
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  await page.goto("https://example.com/");
  await page.evaluate(() => { window.__marker = "A-was-here"; localStorage.setItem("k", "A"); });
  log("A page url", page.url(), "pages in ctx", ctx.pages().length);

  const B = await api("POST", "/v1/sessions", bodyB);
  log("B create", B.status, B.ms + "ms", B.json.id || JSON.stringify(B.json).slice(0, 200));
  await sleep(1500);
  log("A client disconnected?", disconnected, "browser.isConnected()", browser.isConnected());
  try {
    const m = await page.evaluate(() => [window.__marker, location.href]);
    log("A page still alive; marker/url:", JSON.stringify(m));
  } catch (e) { log("A page evaluate failed:", e.message.split("\n")[0]); }
  const gA = await api("GET", `/v1/sessions/${A.json.id}`);
  log("GET /v1/sessions/{A}", gA.status, JSON.stringify({ id: gA.json.id, status: gA.json.status }));
  const list = await api("GET", "/v1/sessions");
  log("list", JSON.stringify(list.json.sessions.map((x) => ({ id: x.id, status: x.status }))));
  // Can a client still reach the browser via the same ws URL? (no session id in URL)
  const b2 = await chromium.connectOverCDP(WS);
  const urls = b2.contexts().flatMap((c) => c.pages().map((p) => p.url()));
  log("fresh CDP attach sees pages:", JSON.stringify(urls));
  await b2.close().catch(() => {});
  await browser.close().catch(() => {});
  const rel = await api("POST", "/v1/sessions/release", {});
  log("release", rel.status, rel.ms + "ms");
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
