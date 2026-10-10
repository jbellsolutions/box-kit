// (b2) Two CDP clients on the one browser: does closing/disconnecting one affect the other?
const { chromium } = require("playwright-core");
const { api, WS, sleep, log } = require("./lib.cjs");
(async () => {
  const mode = process.argv[2] || "close"; // close | disconnect-ws
  const A = await api("POST", "/v1/sessions", {});
  log("create", A.status, A.json.id);
  const c1 = await chromium.connectOverCDP(WS);
  c1.on("disconnected", () => log("c1 disconnected"));
  const p1 = await c1.contexts()[0].newPage(); await p1.goto("https://example.com/");
  const c2 = await chromium.connectOverCDP(WS);
  log("c2 sees", c2.contexts()[0].pages().length, "pages");
  if (mode === "close") await c2.close(); else c2._connection?.close?.();
  await sleep(3000);
  log(`after c2 ${mode}: c1.isConnected`, c1.isConnected());
  try { log("c1 page url", await p1.evaluate(() => location.href)); } catch (e) { log("c1 page dead:", e.message.split("\n")[0]); }
  const s = await api("GET", "/v1/sessions");
  log("sessions", JSON.stringify(s.json.sessions.slice(0, 2).map((x) => ({ id: x.id, status: x.status }))));
  await api("POST", "/v1/sessions/release", {});
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
