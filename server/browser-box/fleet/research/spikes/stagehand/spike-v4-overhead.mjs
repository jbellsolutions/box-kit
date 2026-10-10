// v4 overhead + concurrency probe, zero LLM calls.
// - Node RSS of the SDK process before/after attach and after a snapshot
// - Chromium-side memory of the Stagehand extension service worker (Performance.getMetrics on the SW target)
// - Can a second Stagehand attach to the same browser while the first is live?
import { writeFileSync } from "node:fs";
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";

const steelBase = process.argv[2] ?? "http://127.0.0.1:3301";
const cdpUrl = steelBase.replace(/^http/, "ws") + "/";
const mb = (n) => Math.round(n / 1048576);
const out = { date: new Date().toISOString() };
const noLlm = { generate: async () => { throw new Error("no LLM"); } };
out.rssBaselineMB = mb(process.memoryUsage().rss);

await fetch(`${steelBase}/v1/sessions`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ extensions: ["stagehand"] }) });
const b1 = await localBrowser.connect({ cdpUrl });
const s1 = await Stagehand.create({ browser: b1, model: noLlm, logging: { level: "off" } });
const page = (await b1.context.activePage()) ?? (await b1.context.newPage());
await page.goto("https://books.toscrape.com/");
out.rssAfterAttachMB = mb(process.memoryUsage().rss);
const t0 = performance.now();
const snap = await page.snapshot();
out.snapshotMs = Math.round(performance.now() - t0);
out.snapshotChars = snap.formattedTree.length;
out.snapshotApproxTokens = Math.round(snap.formattedTree.length / 4);
out.rssAfterSnapshotMB = mb(process.memoryUsage().rss);

// Service-worker heap via raw CDP
const ws = new WebSocket(cdpUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}, sessionId) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params, ...(sessionId ? { sessionId } : {}) })); });
const targets = (await send("Target.getTargets")).result.targetInfos;
const sw = targets.find((t) => t.type === "service_worker" && t.title.includes("service-worker.js"));
if (sw) {
  const { result } = await send("Target.attachToTarget", { targetId: sw.targetId, flatten: true });
  const heap = await send("Runtime.getHeapUsage", {}, result.sessionId);
  out.extensionServiceWorkerHeapMB = heap.result ? { used: mb(heap.result.usedSize), total: mb(heap.result.totalSize) } : heap.error;
}
ws.close();

// Second Stagehand on the same browser while the first is live
try {
  const b2 = await localBrowser.connect({ cdpUrl });
  const s2 = await Stagehand.create({ browser: b2, model: noLlm, logging: { level: "off" } });
  out.secondInstance = "attached (unexpected)";
  await s2.close();
} catch (e) {
  out.secondInstance = `rejected: ${String(e?.message ?? e).slice(0, 200)}`;
}
await s1.close();
// After close, a new instance can attach
try {
  const b3 = await localBrowser.connect({ cdpUrl });
  const s3 = await Stagehand.create({ browser: b3, model: noLlm, logging: { level: "off" } });
  out.afterCloseNewInstance = "attached";
  await s3.close();
} catch (e) {
  out.afterCloseNewInstance = `failed: ${String(e?.message ?? e).slice(0, 200)}`;
}
writeFileSync("result-v4-overhead.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
