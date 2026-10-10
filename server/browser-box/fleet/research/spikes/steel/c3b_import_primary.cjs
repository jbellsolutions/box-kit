// (c3b) Import variant: navigate Steel's PRIMARY page (pages()[0]) instead of a new tab, and reload once.
const fs = require("fs");
const { chromium } = require("playwright-core");
const { api, WS, log, sleep } = require("./lib.cjs");
(async () => {
  const ctxData = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const s = await api("POST", "/v1/sessions", { sessionContext: ctxData });
  log("create with sessionContext", s.status, s.json.id);
  const b = await chromium.connectOverCDP(WS);
  const ctx = b.contexts()[0];
  const pages = ctx.pages();
  log("existing pages:", JSON.stringify(pages.map((p) => p.url())));
  const p = pages[0];
  await p.goto("https://example.com/");
  await sleep(1000);
  const read = () => p.evaluate(() => ({ ls: localStorage.getItem("ctx_ls"), ss: sessionStorage.getItem("ctx_ss") }));
  log("primary page after goto:", JSON.stringify(await read()));
  await p.reload(); await sleep(1000);
  log("primary page after reload:", JSON.stringify(await read()));
  const p2 = await ctx.newPage(); await p2.goto("https://example.com/"); await sleep(1000);
  log("new tab:", JSON.stringify(await p2.evaluate(() => ({ ls: localStorage.getItem("ctx_ls") }))));
  await api("POST", "/v1/sessions/release", {});
  await b.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
