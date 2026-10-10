// Scale-infra spike probe. Drives a self-hosted Steel container over CDP.
// Public test pages only. No logins, no secrets.
// Usage: PW_CORE=/abs/path/to/playwright-core node probe.mjs <port> <mode>
//   mode = fp        print the fingerprint surface of the current browser
//          setstate  set a persistent cookie + localStorage key on example.com
//          getstate  read them back
//          browse    visit a fixed list of public test pages (sequential)
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW_CORE || "playwright-core");

const [port, mode] = process.argv.slice(2);
const MARK = "fleetspike";

const browser = await chromium.connectOverCDP(`ws://127.0.0.1:${port}/`, { timeout: 30000 });
const ctx = browser.contexts()[0];
const page = ctx.pages()[0] || (await ctx.newPage());
const t0 = Date.now();
let out = { mode, port };

if (mode === "fp") {
  await page.goto("https://example.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
  out.fp = await page.evaluate(() => {
    let gl = null;
    try {
      const c = document.createElement("canvas").getContext("webgl");
      const ext = c && c.getExtension("WEBGL_debug_renderer_info");
      gl = ext ? [c.getParameter(ext.UNMASKED_VENDOR_WEBGL), c.getParameter(ext.UNMASKED_RENDERER_WEBGL)] : null;
    } catch (e) { gl = String(e); }
    return {
      ua: navigator.userAgent,
      platform: navigator.platform,
      hc: navigator.hardwareConcurrency,
      dm: navigator.deviceMemory,
      lang: navigator.languages,
      screen: [screen.width, screen.height, screen.colorDepth],
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      webdriver: navigator.webdriver,
      gl,
    };
  });
} else if (mode === "setstate") {
  await page.goto("https://example.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.evaluate((m) => {
    document.cookie = `${m}=persist-${Date.now()}; max-age=31536000; path=/; secure; samesite=lax`;
    localStorage.setItem(m, "ls-ok");
  }, MARK);
  out.cookie = await page.evaluate(() => document.cookie);
} else if (mode === "getstate") {
  await page.goto("https://example.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
  out.cookie = await page.evaluate(() => document.cookie);
  out.localStorage = await page.evaluate((m) => localStorage.getItem(m), MARK);
  out.restored = out.cookie.includes(MARK) && out.localStorage === "ls-ok";
} else if (mode === "browse") {
  const urls = [
    "https://quotes.toscrape.com/",
    "https://quotes.toscrape.com/page/2/",
    "https://books.toscrape.com/",
    "https://books.toscrape.com/catalogue/category/books/poetry_23/index.html",
    "https://the-internet.herokuapp.com/",
    "https://the-internet.herokuapp.com/dynamic_loading/2",
    "https://example.com/",
    "https://quotes.toscrape.com/js/",
  ];
  out.pages = [];
  for (const u of urls) {
    const s = Date.now();
    try {
      await page.goto(u, { waitUntil: "load", timeout: 45000 });
      out.pages.push({ u, ms: Date.now() - s });
    } catch (e) {
      out.pages.push({ u, err: String(e).slice(0, 120) });
    }
  }
}
out.ms = Date.now() - t0;
console.log(JSON.stringify(out));
// Exit without browser.close(): over CDP that could close the remote Chromium.
process.exit(0);
