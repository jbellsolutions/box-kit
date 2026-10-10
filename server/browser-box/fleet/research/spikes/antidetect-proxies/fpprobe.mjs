// Fingerprint probe for any CDP endpoint (vanilla / CloakBrowser): example.com + optional CreepJS.
// Usage: node fpprobe.mjs <cdpHttpUrl> <label> [--creep]
import { createRequire } from 'node:module';
const SCRATCH = process.env.FLEET_SCRATCH || (console.error('set FLEET_SCRATCH to the scratch dir that holds npm/'), process.exit(1));
const require = createRequire(`${SCRATCH}/npm/package.json`);
const { chromium } = require('playwright-core');
const [url, label, flag] = process.argv.slice(2);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const FP_JS = async () => {
  const gl = (() => { try { const c = document.createElement('canvas').getContext('webgl'); const d = c.getExtension('WEBGL_debug_renderer_info'); return { vendor: c.getParameter(d.UNMASKED_VENDOR_WEBGL), renderer: c.getParameter(d.UNMASKED_RENDERER_WEBGL), maxDrawBuffers: c.getParameter(0x8824) }; } catch (e) { return { err: String(e) }; } })();
  const workerFp = await new Promise((res) => {
    try {
      const src = `let r={};try{const c=new OffscreenCanvas(1,1).getContext('webgl');const d=c.getExtension('WEBGL_debug_renderer_info');r.renderer=c.getParameter(d.UNMASKED_RENDERER_WEBGL);r.vendor=c.getParameter(d.UNMASKED_VENDOR_WEBGL);}catch(e){r.err=String(e)}r.ua=navigator.userAgent;r.hc=navigator.hardwareConcurrency;r.platform=navigator.platform;postMessage(r);`;
      const w = new Worker(URL.createObjectURL(new Blob([src], { type: 'application/javascript' })));
      w.onmessage = (e) => res(e.data); w.onerror = (e) => res({ err: 'worker error ' + (e.message || '') });
      setTimeout(() => res({ err: 'timeout' }), 4000);
    } catch (e) { res({ err: String(e) }); }
  });
  const uad = navigator.userAgentData ? await navigator.userAgentData.getHighEntropyValues(['platform', 'platformVersion', 'fullVersionList', 'architecture']).catch(e => String(e)) : null;
  const native = (f) => { try { return Function.prototype.toString.call(f).includes('[native code]'); } catch { return 'err'; } };
  const canvasHash = (() => { const c = document.createElement('canvas'); c.width = 200; c.height = 40; const x = c.getContext('2d'); x.font = '16px Arial'; x.fillStyle = '#f60'; x.fillRect(10, 5, 100, 20); x.fillStyle = '#069'; x.fillText('fleet-spike \u{1F600}', 2, 25); const s = c.toDataURL(); let h = 0; for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; } return h; })();
  return {
    ua: navigator.userAgent, platform: navigator.platform, languages: navigator.languages, webdriver: navigator.webdriver,
    hc: navigator.hardwareConcurrency, mem: navigator.deviceMemory, screen: [screen.width, screen.height, screen.colorDepth, devicePixelRatio], inner: [innerWidth, innerHeight, outerWidth, outerHeight],
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone, tzOffset: new Date().getTimezoneOffset(), plugins: navigator.plugins.length, chromeObj: typeof window.chrome, chromeRuntime: typeof window.chrome?.runtime,
    uad, gl, workerFp, canvasHash,
    nativeChecks: { getContext: native(HTMLCanvasElement.prototype.getContext), objectKeys: native(Object.keys), getOwnPropertyNames: native(Object.getOwnPropertyNames), consoleDebug: native(console.debug), consoleLog: native(console.log), Worker: native(window.Worker) },
    hcDescriptorOnNavigator: !!Object.getOwnPropertyDescriptor(navigator, 'hardwareConcurrency'),
  };
};


const b = await chromium.connectOverCDP(url);
const ctx = b.contexts()[0]; const page = await ctx.newPage();
await page.goto('https://example.com/');
const out = { label, browserVersion: b.version(), fp: await page.evaluate(FP_JS) };
if (flag === '--creep') {
  await page.goto('https://abrahamjuliot.github.io/creepjs/', { waitUntil: 'load', timeout: 60000 });
  await sleep(25000);
  const txt = await page.evaluate(() => document.body.innerText);
  const grab = (re) => { const m = txt.match(re); return m ? m[0] : null; };
  out.creepjs = { fpId: grab(/FP ID: [0-9a-f]{16}/), headless: grab(/[0-9]+% headless[^\n]*/i), like: grab(/[0-9]+% like headless[^\n]*/i), stealth: grab(/[0-9]+% stealth[^\n]*/i) };
}
await page.close(); await b.close();
console.log(JSON.stringify(out));
