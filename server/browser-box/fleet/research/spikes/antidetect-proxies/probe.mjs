// Fleet spike (antidetect-proxies): measure what OSS Steel's stealth does, on public/test pages only.
// Usage: node probe.mjs <steelBase> <label> '<sessionBodyJSON>' [--sites]
// No secrets. No logins. Pages: data: URLs, example.com, public bot-test pages.
import { createRequire } from 'node:module';
const SCRATCH = process.env.FLEET_SCRATCH || (console.error('set FLEET_SCRATCH to the scratch dir that holds npm/'), process.exit(1));
const require = createRequire(`${SCRATCH}/npm/package.json`);
const { chromium } = require('playwright-core');

const [base, label, bodyJson, flag] = process.argv.slice(2);
const wsBase = base.replace(/^http/, 'ws') + '/';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function api(path, body) {
  const r = await fetch(base + '/v1' + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) });
  const t = await r.text(); try { return JSON.parse(t); } catch { return { raw: t, status: r.status }; }
}

// Minimal raw CDP client: Target domain only (never Runtime.enable), to isolate Steel's own leak.
async function rawLeakTest() {
  const html = `<html><head><title>pending</title></head><body><script>
  let dbg=false, lg=false;
  const e1=new Error(); Object.defineProperty(e1,'stack',{configurable:false,get(){dbg=true;return ''}}); console.debug(e1);
  const e2=new Error(); Object.defineProperty(e2,'stack',{configurable:false,get(){lg=true;return ''}}); console.log(e2);
  setTimeout(()=>{ document.title = 'dbg='+(dbg?1:0)+';log='+(lg?1:0)+';wd='+navigator.webdriver+';debugNative='+(Function.prototype.toString.call(console.debug).includes('[native code]')?1:0)+';keysNative='+(Function.prototype.toString.call(Object.keys).includes('[native code]')?1:0); }, 800);
  </script></body></html>`;
  const url = 'data:text/html;base64,' + Buffer.from(html).toString('base64');
  const ws = new WebSocket(wsBase);
  let id = 0; const pending = new Map();
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const created = await send('Target.createTarget', { url });
  const targetId = created.result?.targetId;
  await sleep(3000);
  const targets = await send('Target.getTargets');
  const t = targets.result?.targetInfos?.find(x => x.targetId === targetId);
  await send('Target.closeTarget', { targetId });
  ws.close();
  return t?.title ?? JSON.stringify(created);
}

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

const out = { label, at: new Date().toISOString(), body: JSON.parse(bodyJson || '{}') };
const sess = await api('/sessions', out.body);
out.session = { id: sess.id, userAgent: sess.userAgent, dimensions: sess.dimensions, status: sess.status, err: sess.message || sess.raw };
await sleep(1500);
try { out.rawLeak = await rawLeakTest(); } catch (e) { out.rawLeak = 'ERR ' + e; }
const browser = await chromium.connectOverCDP(wsBase);
out.browserVersion = browser.version();
const ctx = browser.contexts()[0];
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://example.com/', { waitUntil: 'load', timeout: 30000 });
out.marker_before = await page.evaluate(() => localStorage.getItem('fleetspike'));
await page.evaluate(() => localStorage.setItem('fleetspike', String(Date.now())));
out.fp = await page.evaluate(FP_JS);
// Leak test again, now with Playwright attached (Playwright enables Runtime on its sessions)
await page.setContent(`<script>window.__r={};const e1=new Error();Object.defineProperty(e1,'stack',{get(){window.__r.dbg=1;return ''}});console.debug(e1);const e2=new Error();Object.defineProperty(e2,'stack',{get(){window.__r.log=1;return ''}});console.log(e2);</script>`);
await sleep(500);
out.leakWithPlaywright = await page.evaluate(() => window.__r);
if (flag === '--sites') {
  out.sites = {};
  try {
    await page.goto('https://bot.sannysoft.com/', { waitUntil: 'networkidle', timeout: 45000 });
    await sleep(3000);
    out.sites.sannysoft = await page.evaluate(() => Array.from(document.querySelectorAll('table tr')).map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim().slice(0, 60)).join(' | ')).filter(r => /failed|warn/i.test(r) || /WebDriver|Chrome|Permissions|Plugins|Languages|WebGL/i.test(r)).slice(0, 40));
  } catch (e) { out.sites.sannysoft = 'ERR ' + e.message; }
  try {
    await page.goto('https://deviceandbrowserinfo.com/are_you_a_bot', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(12000);
    out.sites.dabi = (await page.evaluate(() => document.body.innerText)).slice(0, 2500);
  } catch (e) { out.sites.dabi = 'ERR ' + e.message; }
  try {
    await page.goto('https://abrahamjuliot.github.io/creepjs/', { waitUntil: 'load', timeout: 60000 });
    await sleep(25000);
    const txt = await page.evaluate(() => document.body.innerText);
    const grab = (re) => { const m = txt.match(re); return m ? m[0] : null; };
    out.sites.creepjs = { headless: grab(/[0-9]+% headless[^\n]*/i), like: grab(/[0-9]+% like headless[^\n]*/i), stealth: grab(/[0-9]+% stealth[^\n]*/i), lies: grab(/lies[^\n]{0,40}/i), trust: grab(/trust score[^\n]{0,40}/i), head: txt.slice(0, 1200) };
  } catch (e) { out.sites.creepjs = 'ERR ' + e.message; }
}
await browser.close().catch(() => {});
await api('/sessions/release', {});
console.log(JSON.stringify(out, null, 2));
