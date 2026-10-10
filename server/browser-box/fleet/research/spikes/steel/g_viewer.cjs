// (g) Live viewer: what does a human see at /v1/sessions/debug, and can they type into a form through it?
// The "human" is a headless Chrome for Testing on the host with a throwaway profile. No form is submitted.
const path = require("path");
const { chromium } = require("playwright-core");
const { api, WS, BASE, sleep, log } = require("./lib.cjs");
const OUT = process.env.OUT_DIR || __dirname;
const CFT = process.env.CFT || (console.error('set CFT to a Chrome for Testing binary'), process.exit(1));
(async () => {
  const s = await api("POST", "/v1/sessions", { dimensions: { width: 1280, height: 800 } });
  log("create", s.status, "debugUrl", s.json.debugUrl, "debuggerUrl", s.json.debuggerUrl);
  const agent = await chromium.connectOverCDP(WS);
  const actx = agent.contexts()[0];
  const primary = actx.pages()[0];
  await primary.goto("https://the-internet.herokuapp.com/login", { waitUntil: "domcontentloaded", timeout: 45000 });
  const box = await primary.locator("#username").boundingBox();
  log("remote #username box", JSON.stringify(box));

  const human = await chromium.launch({ executablePath: CFT, headless: true });
  const hp = await human.newPage({ viewport: { width: 1400, height: 950 } });
  await hp.goto(`${BASE}/v1/sessions/debug?interactive=true&showControls=true`);
  await sleep(5000);
  await hp.screenshot({ path: path.join(OUT, "viewer-1-login-form.png") });
  const canvas = await hp.locator("canvas").first().boundingBox();
  log("viewer canvas box", JSON.stringify(canvas));
  // map remote CSS px -> canvas px (remote viewport 1280x800)
  const sx = canvas.width / 1280, sy = canvas.height / 800;
  await hp.mouse.click(canvas.x + (box.x + box.width / 2) * sx, canvas.y + (box.y + box.height / 2) * sy);
  await sleep(500);
  await hp.keyboard.type("viewer-typed", { delay: 60 });
  await sleep(1500);
  const val = await primary.locator("#username").inputValue();
  log("RESULT value typed through viewer, read by agent:", JSON.stringify(val));
  await hp.screenshot({ path: path.join(OUT, "viewer-2-typed.png") });
  // popup / second tab: does the viewer get a tab for it?
  await primary.evaluate(() => window.open("https://example.com/", "_blank"));
  await sleep(4000);
  const tabs = await hp.locator(".tab").count();
  log("viewer tab count after window.open:", tabs);
  await hp.screenshot({ path: path.join(OUT, "viewer-3-popup.png") });
  const ld = await api("GET", `/v1/sessions/${s.json.id}/live-details`);
  log("live-details", ld.status, JSON.stringify((ld.json.pages || []).map((p) => p.url)), "browserVersion field:", JSON.stringify(ld.json.browserState?.browserVersion).slice(0, 120));
  const insp = await fetch(`${BASE}/v1/devtools/inspector.html`);
  log("devtools inspector.html", insp.status, (await insp.text()).length, "bytes");
  await human.close();
  await api("POST", "/v1/sessions/release", {});
  await agent.close().catch(() => {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
