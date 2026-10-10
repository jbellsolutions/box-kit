// Attach Stagehand 4.2.0 (TS) to a self-hosted Steel container over CDP. No LLM calls.
// Usage: node attach.mjs <steelBase http://127.0.0.1:PORT> [--session-ext]
//   --session-ext : first POST /v1/sessions {extensions:["stagehand"]} so Steel relaunches Chromium
//                   with the pre-installed Stagehand extension (--load-extension).
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";

const steelBase = process.argv[2] ?? "http://127.0.0.1:3301";
const withSessionExt = process.argv.includes("--session-ext");
const cdpUrl = steelBase.replace(/^http/, "ws") + "/";
const t = () => performance.now();
const out = { steelBase, cdpUrl, withSessionExt, steps: [] };
const step = async (name, fn) => {
  const t0 = t();
  try {
    const v = await fn();
    out.steps.push({ name, ok: true, ms: Math.round(t() - t0) });
    return v;
  } catch (e) {
    out.steps.push({ name, ok: false, ms: Math.round(t() - t0), error: String(e?.message ?? e).slice(0, 500), cause: e?.cause ? String(e.cause?.message ?? JSON.stringify(e.cause)).slice(0, 300) : undefined });
    throw e;
  }
};

let browser, stagehand;
try {
  if (withSessionExt) {
    await step("steel.createSession(extensions=[stagehand])", async () => {
      const r = await fetch(`${steelBase}/v1/sessions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ extensions: ["stagehand"] }),
      });
      const j = await r.json();
      out.steelSession = { status: r.status, id: j.id, websocketUrl: j.websocketUrl };
      if (!r.ok) throw new Error(`steel session HTTP ${r.status}`);
    });
  }
  browser = await step("localBrowser.connect", () => localBrowser.connect({ cdpUrl }));
  stagehand = await step("Stagehand.create", () =>
    Stagehand.create({
      browser,
      model: { generate: async () => { throw new Error("no LLM in attach test"); } },
      logging: { level: "warn" },
    }),
  );
  const page = await step("activePage", async () => (await browser.context.activePage()) ?? (await browser.context.newPage()));
  await step("goto example.com", () => page.goto("https://example.com/"));
  const snap = await step("page.snapshot", () => page.snapshot());
  out.snapshot = { treeChars: snap.formattedTree.length, xpathEntries: Object.keys(snap.xpathMap).length, head: snap.formattedTree.slice(0, 400) };
  out.title = await page.title();
  out.metrics = await stagehand.metrics();
} catch (e) {
  out.fatal = String(e?.message ?? e).slice(0, 500);
} finally {
  // stagehand.close() releases the claim only. browser.close() on a connected local browser sends
  // Browser.close (kills the remote Chromium), so the attach test deliberately does NOT call it.
  try { if (stagehand) await stagehand.close(); } catch (e) { out.closeError = String(e); }
}
console.log(JSON.stringify(out, null, 2));
process.exit(0);
