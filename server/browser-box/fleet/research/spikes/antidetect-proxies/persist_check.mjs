// Does OSS Steel's persist:true carry cookies/localStorage across release+relaunch? (example.com only)
import { createRequire } from 'node:module';
const SCRATCH = process.env.FLEET_SCRATCH || (console.error('set FLEET_SCRATCH to the scratch dir that holds npm/'), process.exit(1));
const require = createRequire(`${SCRATCH}/npm/package.json`);
const { chromium } = require('playwright-core');
const base = process.argv[2], mode = process.argv[3], waitMs = Number(process.argv[4] || 12000);
const post = (p, b) => fetch(base + '/v1' + p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b || {}) }).then(r => r.json());
const s = await post('/sessions', { persist: true });
const b = await chromium.connectOverCDP(base.replace('http', 'ws') + '/');
const ctx = b.contexts()[0]; const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://example.com/');
const before = await page.evaluate(() => ({ ls: localStorage.getItem('fleetspike3'), cookie: document.cookie }));
if (mode === 'write') {
  await page.evaluate(() => { localStorage.setItem('fleetspike3', 'v' + Date.now()); document.cookie = 'fleetspike3=1; max-age=86400; path=/'; });
  await new Promise(r => setTimeout(r, waitMs));
}
console.log(JSON.stringify({ session: s.id, mode, before }));
await b.close().catch(() => {});
await post('/sessions/release');
