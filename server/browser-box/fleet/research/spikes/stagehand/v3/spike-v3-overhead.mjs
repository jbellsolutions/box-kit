// v3.7.3 overhead + concurrency probe, zero LLM calls.
import { writeFileSync } from "node:fs";
import { Stagehand } from "@browserbasehq/stagehand";
const cdpUrl = process.argv[2] ?? "ws://127.0.0.1:3301/";
const mb = (n) => Math.round(n / 1048576);
const out = { date: new Date().toISOString(), rssBaselineMB: mb(process.memoryUsage().rss) };
const mk = () => new Stagehand({ env: "LOCAL", localBrowserLaunchOptions: { cdpUrl }, model: { modelName: "openai/none", apiKey: "unused" }, verbose: 0, disablePino: true, logger: () => {} });
const s1 = mk();
await s1.init();
const page = s1.context.pages()[0];
await page.goto("https://books.toscrape.com/");
out.rssAfterAttachMB = mb(process.memoryUsage().rss);
const t0 = performance.now();
const snap = await page.snapshot();
out.snapshotMs = Math.round(performance.now() - t0);
out.snapshotChars = snap.formattedTree.length;
out.rssAfterSnapshotMB = mb(process.memoryUsage().rss);
try { const s2 = mk(); await s2.init(); out.secondInstance = `attached; pages seen=${s2.context.pages().length}`; await s2.close(); } catch (e) { out.secondInstance = `rejected: ${String(e).slice(0, 200)}`; }
await s1.close();
const r = await fetch(cdpUrl.replace(/^ws/, "http").replace(/\/$/, "") + "/v1/sessions").then((x) => x.status).catch((e) => String(e));
out.steelAliveAfterCloseHttp = r;
writeFileSync("result-v3-overhead.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
