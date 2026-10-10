// Stagehand 3.7.3 (last v3) against self-hosted Steel over CDP. Public test pages only.
// observe / act / extract / act(Action) / cacheDir replay (zero-call check) / stale-cache self-heal /
// a short agent() run and its cache replay. All LLM traffic is counted:
//   - act/observe/extract go through a custom LLMClient backed by the shared OpenRouter shim
//   - agent() needs an AI SDK LanguageModel; it uses @ai-sdk/openai-compatible with a counting fetch
// Usage: ../or_env.sh node spike-v3.mjs [cdpUrl]
import { rmSync, writeFileSync, readdirSync, readFileSync } from "node:fs";
import { Stagehand, LLMClient } from "@browserbasehq/stagehand";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { z } from "zod";
import { makeOpenRouterLLM } from "../openrouter-llm.mjs";

const cdpUrl = process.argv[2] ?? "ws://127.0.0.1:3301/";
const steelBase = cdpUrl.replace(/^ws/, "http").replace(/\/$/, "");
const MODEL = process.env.SPIKE_MODEL ?? "z-ai/glm-5.3-flash";
const CACHE_DIR = new URL("./v3-cache/", import.meta.url).pathname;
rmSync(CACHE_DIR, { recursive: true, force: true });
for (const f of ["llm-calls-v3.jsonl", "prompts-v3.jsonl"]) rmSync(f, { force: true });
const shim = makeOpenRouterLLM({ model: MODEL, logFile: "llm-calls-v3.jsonl", promptDumpFile: "prompts-v3.jsonl" });

// ---- agent-side counting fetch (AI SDK path) ----
const agentStats = { calls: 0, costUsd: 0, inputTokens: 0, outputTokens: 0 };
const countingFetch = async (url, init) => {
  agentStats.calls += 1;
  let body = init?.body;
  try {
    const j = JSON.parse(body);
    j.reasoning = { effort: "low" };
    j.usage = { include: true };
    j.max_tokens = Math.min(j.max_tokens ?? 4096, 4096);
    delete j.max_completion_tokens;
    body = JSON.stringify(j);
  } catch {}
  const res = await fetch(url, { ...init, body });
  const text = await res.text();
  try {
    const j = JSON.parse(text);
    agentStats.costUsd += Number(j.usage?.cost ?? 0);
    agentStats.inputTokens += j.usage?.prompt_tokens ?? 0;
    agentStats.outputTokens += j.usage?.completion_tokens ?? 0;
  } catch {}
  return new Response(text, { status: res.status, statusText: res.statusText, headers: res.headers });
};
const openrouter = createOpenAICompatible({
  name: "openrouter",
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: process.env.OPENROUTER_API_KEY,
  fetch: countingFetch,
});

// ---- custom v3 LLMClient ----
function textOf(content) {
  if (typeof content === "string") return content;
  return content.map((c) => c.text ?? "").join("\n");
}
class OpenRouterV3Client extends LLMClient {
  constructor(modelName) {
    super(modelName);
    this.type = "openrouter";
    this.hasVision = false;
    this.clientOptions = {};
  }
  getLanguageModel() {
    return openrouter.chatModel(MODEL);
  }
  async createChatCompletion({ options }) {
    const systemPrompt = options.messages.filter((m) => m.role === "system").map((m) => textOf(m.content)).join("\n\n");
    const messages = options.messages
      .filter((m) => m.role !== "system")
      .map((m) => ({ role: m.role, content: { type: "text", text: textOf(m.content) } }));
    const toUsage = (u) => ({
      prompt_tokens: u?.inputTokens ?? 0,
      completion_tokens: u?.outputTokens ?? 0,
      total_tokens: u?.totalTokens ?? 0,
      reasoning_tokens: u?.reasoningTokens ?? 0,
    });
    if (options.response_model) {
      const schema = z.toJSONSchema(options.response_model.schema);
      delete schema.$schema;
      const r = await shim.generate({
        systemPrompt,
        messages,
        temperature: options.temperature,
        responseFormat: { type: "json_schema", name: options.response_model.name, schema },
      });
      return { data: r.structuredContent, usage: toUsage(r.usage) };
    }
    const r = await shim.generate({ systemPrompt, messages, temperature: options.temperature });
    return {
      id: "or",
      object: "chat.completion",
      created: Date.now(),
      model: MODEL,
      choices: [{ index: 0, message: { role: "assistant", content: r.content.text, tool_calls: [] }, finish_reason: "stop" }],
      usage: toUsage(r.usage),
    };
  }
}

const results = [];
const totalCalls = () => shim.stats.calls + agentStats.calls;
const totalCost = () => shim.stats.costUsd + agentStats.costUsd;
async function timed(name, fn) {
  if (totalCost() > Number(process.env.SPEND_CAP ?? 0.3)) throw new Error("spend cap reached");
  const c0 = totalCalls();
  const k0 = totalCost();
  const t0 = performance.now();
  let value;
  let error;
  try {
    value = await fn();
  } catch (e) {
    error = String(e?.message ?? e).slice(0, 500);
  }
  const rec = { name, ms: Math.round(performance.now() - t0), llmCalls: totalCalls() - c0, costUsd: +(totalCost() - k0).toFixed(6), ...(error ? { error } : {}) };
  results.push(rec);
  console.error(JSON.stringify(rec));
  return value;
}

const out = { date: new Date().toISOString(), version: "3.7.3", model: MODEL, cdpUrl, results, notes: {} };
let sh;
try {
  // Fresh Steel session (no Stagehand extension needed for v3).
  await timed("steel.createSession()", async () => {
    const r = await fetch(`${steelBase}/v1/sessions`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
    if (!r.ok) throw new Error(`steel HTTP ${r.status}`);
  });
  sh = new Stagehand({
    env: "LOCAL",
    localBrowserLaunchOptions: { cdpUrl },
    llmClient: new OpenRouterV3Client(MODEL),
    cacheDir: CACHE_DIR,
    verbose: 0,
    disablePino: true,
    logger: () => {},
  });
  await timed("stagehand.init() (attach over CDP)", () => sh.init());
  const page = sh.context.pages()[0];

  await timed("goto quotes", () => page.goto("https://quotes.toscrape.com/"));
  const obs = await timed("observe('Next pagination link')", () => sh.observe("find the 'Next' pagination link"));
  out.notes.observe = obs;
  const ex = await timed("extract(first 3 quotes, zod)", () =>
    sh.extract("extract the first 3 quotes on the page with their author", z.object({ quotes: z.array(z.object({ text: z.string(), author: z.string() })) })),
  );
  out.notes.extract = ex;
  if (obs?.[0]) {
    const r = await timed("act(observe[0]) [expect 0 calls]", () => sh.act(obs[0]));
    out.notes.actFromObserve = { r, url: page.url() };
  }

  // cacheDir replay: run 1 = miss (inference + write), run 2 = hit (expect 0 calls)
  for (const i of [1, 2]) {
    await timed(`goto reset (cache run ${i})`, () => page.goto("https://quotes.toscrape.com/"));
    const r = await timed(`act('click the Next link') cache run ${i}`, () => sh.act("click the Next link"));
    out.notes[`cacheRun${i}`] = { success: r?.success, actions: r?.actions, url: page.url() };
  }
  out.notes.cacheFiles = readdirSync(CACHE_DIR);
  const entryFile = out.notes.cacheFiles.find((f) => f.endsWith(".json"));
  if (entryFile) out.notes.cacheEntrySample = JSON.parse(readFileSync(CACHE_DIR + entryFile, "utf8"));

  // stale cache: shift the DOM so the cached xpath no longer resolves -> self-heal (selfHeal defaults true in v3)
  await timed("goto reset (stale cache)", () => page.goto("https://quotes.toscrape.com/"));
  await page.evaluate(() => document.body.prepend(document.createElement("div")));
  const stale = await timed("act('click the Next link') with stale cached xpath", () => sh.act("click the Next link"));
  out.notes.staleCache = { success: stale?.success, actions: stale?.actions, url: page.url() };
  await timed("goto reset (after self-heal)", () => page.goto("https://quotes.toscrape.com/"));
  const healed = await timed("act('click the Next link') after self-heal refresh", () => sh.act("click the Next link"));
  out.notes.afterHeal = { success: healed?.success, actions: healed?.actions, url: page.url() };

  // decider path in v3: page.snapshot -> pick -> act(Action)
  await timed("goto reset (decider)", () => page.goto("https://quotes.toscrape.com/"));
  const snap = await timed("page.snapshot()", () => page.snapshot());
  const line = snap?.formattedTree?.split("\n").find((l) => /\]\s+link: Next/.test(l));
  const id = line?.match(/\[(\d+-\d+)\]/)?.[1];
  out.notes.decider = { line: line?.trim(), id, xpath: id ? snap.xpathMap[id] : undefined };
  if (id) {
    const r = await timed("act({xpath from snapshot}) [expect 0 calls]", () =>
      sh.act({ selector: `xpath=${snap.xpathMap[id]}`, description: "Next", method: "click", arguments: [] }),
    );
    out.notes.decider.result = { success: r?.success, url: page.url() };
  }

  // agent(): DOM mode with GLM 5.3 Flash through OpenRouter; run twice to test agent cache replay
  for (const i of [1, 2]) {
    await timed(`goto reset (agent run ${i})`, () => page.goto("https://quotes.toscrape.com/"));
    const agent = sh.agent({ mode: "dom" });
    const res = await timed(`agent.execute run ${i}`, () =>
      agent.execute({ instruction: "Go to the second page of quotes and tell me the author of the first quote there.", maxSteps: 8 }),
    );
    out.notes[`agentRun${i}`] = {
      success: res?.success,
      completed: res?.completed,
      message: res?.message?.slice(0, 300),
      actions: res?.actions?.map((a) => a.type ?? a.action ?? Object.keys(a)[0]).slice(0, 20),
      usage: res?.usage,
      url: page.url(),
    };
  }
  out.notes.cacheFilesAfterAgent = readdirSync(CACHE_DIR);
  out.metrics = await sh.metrics;
  out.historyLength = (await sh.history)?.length;
} catch (e) {
  out.fatal = String(e?.stack ?? e).slice(0, 1200);
} finally {
  // v3 close() on a cdpUrl-attached browser: record whether it kills the remote browser.
  try {
    if (sh) await sh.close();
  } catch (e) {
    out.closeError = String(e);
  }
}
out.llmActObserveExtract = { calls: shim.stats.calls, costUsd: shim.stats.costUsd, inputTokens: shim.stats.inputTokens, outputTokens: shim.stats.outputTokens };
out.llmAgent = agentStats;
out.llmRecords = shim.stats.records.map(({ output, ...r }) => r);
writeFileSync("result-v3.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
