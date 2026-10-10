// Can Stagehand v4 attach (no LLM call) to a browser it did not launch? Optionally read the bot-test verdict.
// Usage: node sh_connect.mjs <cdpUrl> [--dabi]
import { createRequire } from 'node:module';
const SCRATCH = process.env.FLEET_SCRATCH || (console.error('set FLEET_SCRATCH to the scratch dir that holds npm/'), process.exit(1));
const require = createRequire(`${SCRATCH}/npm/package.json`);
const sh = await import(`${SCRATCH}/npm/node_modules/@browserbasehq/stagehand/dist/index.mjs`);
const [cdpUrl, flag] = process.argv.slice(2);
const t0 = Date.now(); const out = { cdpUrl };
try {
  const browser = await sh.localBrowser.connect({ cdpUrl });
  out.connectMs = Date.now() - t0;
  const stagehand = await sh.Stagehand.create({ browser });
  out.createMs = Date.now() - t0;
  const pages = await browser.context.pages();
  const page = pages[0] || await browser.context.newPage();
  await page.goto('https://example.com/');
  out.title = await page.evaluate(() => document.title);
  if (flag === '--dabi') {
    await page.goto('https://deviceandbrowserinfo.com/are_you_a_bot');
    await new Promise(r => setTimeout(r, 30000));
    const txt = await page.evaluate(() => document.body.innerText);
    const m = txt.match(/\{\s*"isBot"[\s\S]*?\n\}/);
    const p = m ? JSON.parse(m[0]) : null;
    out.dabi = p ? { isBot: p.isBot, flagged: Object.entries(p.details).filter(([k, v]) => v).map(([k]) => k) } : txt.slice(0, 300);
  }
  await stagehand.close?.();
} catch (e) { out.error = String(e && e.message || e).slice(0, 600); out.ms = Date.now() - t0; }
console.log(JSON.stringify(out));
process.exit(0);
