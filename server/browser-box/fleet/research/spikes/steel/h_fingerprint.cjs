// (h) Fingerprint stability: collect fingerprint surface in N consecutive sessions with the same create body.
// Usage: CREATE_BODY='{"persist":true}' node h_fingerprint.cjs <N>
const { chromium } = require("playwright-core");
const { api, WS, log } = require("./lib.cjs");
const collect = async () => {
  const gl = (() => { try { const c = document.createElement("canvas").getContext("webgl"); const d = c.getExtension("WEBGL_debug_renderer_info"); return [c.getParameter(d.UNMASKED_VENDOR_WEBGL), c.getParameter(d.UNMASKED_RENDERER_WEBGL)]; } catch (e) { return ["err", e.message]; } })();
  let uad = null; try { uad = navigator.userAgentData ? await navigator.userAgentData.getHighEntropyValues(["platform", "platformVersion", "fullVersionList", "architecture"]) : null; } catch (e) {}
  const cv = (() => { const c = document.createElement("canvas"); c.width = 200; c.height = 50; const x = c.getContext("2d"); x.textBaseline = "top"; x.font = "14px Arial"; x.fillStyle = "#f60"; x.fillRect(0, 0, 100, 30); x.fillStyle = "#069"; x.fillText("fleet-fp \u{1F600}", 2, 15); const s = c.toDataURL(); let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h; })();
  return {
    ua: navigator.userAgent, uaBrands: uad && uad.fullVersionList && uad.fullVersionList.map((b) => b.brand + "/" + b.version).join(","), uaPlatform: uad && uad.platform + " " + uad.platformVersion,
    platform: navigator.platform, hc: navigator.hardwareConcurrency, mem: navigator.deviceMemory, lang: navigator.languages.join(","),
    screen: `${screen.width}x${screen.height} avail ${screen.availWidth}x${screen.availHeight} dpr ${devicePixelRatio}`, inner: `${innerWidth}x${innerHeight}`,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone, webdriver: navigator.webdriver, webgl: gl.join(" | "), canvasHash: cv,
    plugins: navigator.plugins.length, cursorDiv: !!document.getElementById("__cursor__"),
  };
};
(async () => {
  const N = Number(process.argv[2] || 2);
  const body = JSON.parse(process.env.CREATE_BODY || '{"persist":true}');
  const rows = [];
  for (let i = 0; i < N; i++) {
    const s = await api("POST", "/v1/sessions", body);
    const b = await chromium.connectOverCDP(WS);
    const p = process.env.NEWPAGE ? await b.contexts()[0].newPage() : b.contexts()[0].pages()[0];
    await p.goto("https://example.com/");
    const fp = await p.evaluate(collect);
    fp.sessionUA = s.json.userAgent;
    rows.push(fp);
    log(`session ${i + 1}`, s.status, JSON.stringify(fp));
    await api("POST", "/v1/sessions/release", {});
    await b.close().catch(() => {});
  }
  const keys = Object.keys(rows[0]);
  const changed = keys.filter((k) => rows.some((r) => JSON.stringify(r[k]) !== JSON.stringify(rows[0][k])));
  log("RESULT fields that changed across sessions:", JSON.stringify(changed));
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
