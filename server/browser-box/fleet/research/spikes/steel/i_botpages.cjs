// (i) Public bot-detection pages through Steel. Uses Steel's primary tab (best case for injection).
// Usage: CREATE_BODY='{}' LABEL=default node i_botpages.cjs
const path = require("path");
const { chromium } = require("playwright-core");
const { api, WS, sleep, log } = require("./lib.cjs");
const OUT = process.env.OUT_DIR || __dirname;
const LABEL = process.env.LABEL || "default";
(async () => {
  const body = JSON.parse(process.env.CREATE_BODY || "{}");
  const s = await api("POST", "/v1/sessions", body);
  log(LABEL, "create", s.status, s.ms + "ms", JSON.stringify(body), (s.json.userAgent || JSON.stringify(s.json)).slice(0, 160));
  if (s.status !== 200) return;
  const b = await chromium.connectOverCDP(WS);
  const p = b.contexts()[0].pages()[0];
  const shot = async (name) => p.screenshot({ path: path.join(OUT, `bot-${LABEL}-${name}.jpg`), type: "jpeg", quality: 55, fullPage: true }).catch((e) => log("shot err", e.message.split("\n")[0]));
  // 1. sannysoft
  try {
    await p.goto("https://bot.sannysoft.com/", { waitUntil: "domcontentloaded", timeout: 45000 }); await sleep(6000);
    const r = await p.evaluate(() => {
      const rows = [...document.querySelectorAll("table tr")].map((tr) => [...tr.querySelectorAll("td")].map((td) => [td.innerText.trim().slice(0, 60), td.className]));
      const failed = rows.filter((r) => r.some(([, c]) => /failed/.test(c))).map((r) => r[0][0]);
      const warn = rows.filter((r) => r.some(([, c]) => /warn/.test(c))).map((r) => r[0][0]);
      const ua = rows.find((r) => /User Agent/.test(r[0]?.[0] || ""));
      return { rows: rows.length, failed, warn, ua: ua && ua[1] && ua[1][0] };
    });
    log(LABEL, "sannysoft", JSON.stringify(r));
    await shot("sannysoft");
  } catch (e) { log(LABEL, "sannysoft error", e.message.split("\n")[0]); }
  // 2. browserscan bot detection
  try {
    await p.goto("https://www.browserscan.net/bot-detection", { waitUntil: "domcontentloaded", timeout: 45000 }); await sleep(12000);
    const t = await p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
    const m = t.match(/Test Results:?\s*(\w+)/i);
    const flagged = await p.evaluate(() => ["Webdriver", "User-Agent", "CDP", "Navigator"].map((k) => { const el = [...document.querySelectorAll("*")].find((e) => e.childElementCount === 0 && e.textContent.trim() === k); if (!el) return k + "=?"; const c = getComputedStyle(el).color; const rgb = c.match(/\d+/g).map(Number); return k + "=" + (rgb[0] > 180 && rgb[1] < 140 ? "RED" : "ok"); }));
    log(LABEL, "browserscan categories:", JSON.stringify(flagged));
    log(LABEL, "browserscan result:", m ? m[1] : "?", "| snippet:", t.slice(t.search(/Test Results/i), t.search(/Test Results/i) + 400));
    await shot("browserscan");
  } catch (e) { log(LABEL, "browserscan error", e.message.split("\n")[0]); }
  // 3. creepjs
  try {
    await p.goto("https://abrahamjuliot.github.io/creepjs/", { waitUntil: "domcontentloaded", timeout: 45000 }); await sleep(15000);
    const t = await p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
    const grab = (re) => { const m = t.match(re); return m ? m[0] : null; };
    log(LABEL, "creepjs:", JSON.stringify({ headless: grab(/\d+% headless/i), likeHeadless: grab(/\d+% like headless/i), stealth: grab(/\d+% stealth/i), lies: grab(/lies \(\d+\)/i), trash: grab(/trash \(\d+\)/i) }));
    await shot("creepjs");
  } catch (e) { log(LABEL, "creepjs error", e.message.split("\n")[0]); }
  await api("POST", "/v1/sessions/release", {});
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
