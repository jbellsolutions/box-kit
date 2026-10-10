// Playwright connectOverCDP to vanilla Chromium -> read bot-test verdict.
import { createRequire } from 'node:module';
const SCRATCH = process.env.FLEET_SCRATCH || (console.error('set FLEET_SCRATCH to the scratch dir that holds npm/'), process.exit(1));
const require = createRequire(`${SCRATCH}/npm/package.json`);
const { chromium } = require('playwright-core');
const b = await chromium.connectOverCDP(process.argv[2]);
const ctx = b.contexts()[0]; const page = await ctx.newPage();
await page.goto('https://deviceandbrowserinfo.com/are_you_a_bot', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(15000);
const txt = await page.evaluate(() => document.body.innerText);
const m = txt.match(/\{\s*"isBot"[\s\S]*?\n\}/); const p = m ? JSON.parse(m[0]) : null;
console.log(JSON.stringify({ driver: 'playwright-core connectOverCDP', isBot: p?.isBot, flagged: p ? Object.entries(p.details).filter(([k, v]) => v).map(([k]) => k) : txt.slice(0, 200) }));
await page.close(); await b.close();
