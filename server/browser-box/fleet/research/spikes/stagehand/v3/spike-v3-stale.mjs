// v3.7.3 cacheDir hazards, reusing the cache written by spike-v3.mjs (key = instruction + URL).
// A: DOM shifted so the cached xpath resolves to nothing -> what does replay do (self-heal? fallback?)
// B: DOM changed so the cached xpath resolves to a DIFFERENT element -> silent wrong click?
// Usage: ../or_env.sh node spike-v3-stale.mjs [cdpUrl]
import { writeFileSync } from "node:fs";
import { Stagehand, LLMClient } from "@browserbasehq/stagehand";
import { z } from "zod";
import { makeOpenRouterLLM } from "../openrouter-llm.mjs";

const cdpUrl = process.argv[2] ?? "ws://127.0.0.1:3301/";
const MODEL = "z-ai/glm-5.3-flash";
const CACHE_DIR = new URL("./v3-cache/", import.meta.url).pathname;
const shim = makeOpenRouterLLM({ model: MODEL, logFile: "llm-calls-v3-stale.jsonl" });
const textOf = (c) => (typeof c === "string" ? c : c.map((x) => x.text ?? "").join("\n"));
class OR extends LLMClient {
  constructor() { super(MODEL); this.type = "openrouter"; this.hasVision = false; this.clientOptions = {}; }
  async createChatCompletion({ options }) {
    const systemPrompt = options.messages.filter((m) => m.role === "system").map((m) => textOf(m.content)).join("\n\n");
    const messages = options.messages.filter((m) => m.role !== "system").map((m) => ({ role: m.role, content: { type: "text", text: textOf(m.content) } }));
    const schema = z.toJSONSchema(options.response_model.schema);
    delete schema.$schema;
    const r = await shim.generate({ systemPrompt, messages, responseFormat: { type: "json_schema", name: options.response_model.name, schema } });
    return { data: r.structuredContent, usage: { prompt_tokens: r.usage.inputTokens, completion_tokens: r.usage.outputTokens, total_tokens: r.usage.totalTokens } };
  }
}
const out = { date: new Date().toISOString(), probes: {} };
const sh = new Stagehand({ env: "LOCAL", localBrowserLaunchOptions: { cdpUrl }, llmClient: new OR(), cacheDir: CACHE_DIR, verbose: 0, disablePino: true, logger: () => {} });
await sh.init();
const page = sh.context.pages()[0];
async function probe(name, mutate) {
  await page.goto("https://quotes.toscrape.com/");
  await page.evaluate(mutate);
  const c0 = shim.stats.calls;
  const t0 = performance.now();
  const r = await sh.act("click the Next link").catch((e) => ({ success: false, message: String(e) }));
  out.probes[name] = { ms: Math.round(performance.now() - t0), llmCalls: shim.stats.calls - c0, success: r.success, message: r.message?.slice(0, 300), actions: r.actions, urlAfter: page.url() };
  console.error(name, JSON.stringify(out.probes[name]));
}
if (!process.env.ONLY_B) await probe("A: cached xpath resolves to nothing", () => document.body.prepend(document.createElement("div")));
else if (!process.env.SKIP_RESET) await probe("reset: normal page (re-heals entry back to li[1] if needed)", () => {});
await probe("B: cached xpath resolves to a different link", () => {
  const ul = document.querySelector("nav ul.pager");
  const li = document.createElement("li");
  li.innerHTML = '<a href="/tag/love/">Love</a>';
  ul.prepend(li);
});
await sh.close();
out.llm = { calls: shim.stats.calls, costUsd: shim.stats.costUsd };
writeFileSync(process.env.ONLY_B ? (process.env.OUT ?? "result-v3-stale-B.json") : "result-v3-stale.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
