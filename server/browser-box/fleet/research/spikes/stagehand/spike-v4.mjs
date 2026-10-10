// Stagehand 4.2.0 (TS) against self-hosted Steel. Public test pages only.
// Measures: observe, act (string), extract (zod), act(observeResult), decider path
// (page.snapshot -> pick -> act(Action)), cache:true replay, broken selector, variables leak check.
// Every LLM call goes through the counting OpenRouter shim; its counter is the ground truth.
// Usage: or_env.sh node spike-v4.mjs [steelBase]   (SPIKE_MODEL overrides the model id)
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";
import { z } from "zod";
import { makeOpenRouterLLM } from "./openrouter-llm.mjs";

const steelBase = process.argv[2] ?? "http://127.0.0.1:3301";
const cdpUrl = steelBase.replace(/^http/, "ws") + "/";
const MODEL = process.env.SPIKE_MODEL ?? "z-ai/glm-5.3-flash";
const tag = MODEL.replace(/[^a-z0-9]+/gi, "_");
const LOG = `llm-calls-v4-${tag}.jsonl`;
const PROMPTS = `prompts-v4-${tag}.jsonl`;
for (const f of [LOG, PROMPTS]) rmSync(f, { force: true });
const SPEND_CAP = Number(process.env.SPEND_CAP ?? 0.3);
const CANARY = "CanaryS3cret-7781";

const llm = makeOpenRouterLLM({ model: MODEL, logFile: LOG, promptDumpFile: PROMPTS });
const results = [];
async function timed(name, fn) {
  if (llm.stats.costUsd > SPEND_CAP) throw new Error(`spend cap ${SPEND_CAP} reached`);
  const c0 = llm.stats.calls;
  const cost0 = llm.stats.costUsd;
  const in0 = llm.stats.inputTokens;
  const out0 = llm.stats.outputTokens;
  const t0 = performance.now();
  let value;
  let error;
  try {
    value = await fn();
  } catch (e) {
    error = String(e?.message ?? e).slice(0, 500);
  }
  const rec = {
    name,
    ms: Math.round(performance.now() - t0),
    llmCalls: llm.stats.calls - c0,
    inputTokens: llm.stats.inputTokens - in0,
    outputTokens: llm.stats.outputTokens - out0,
    costUsd: +(llm.stats.costUsd - cost0).toFixed(6),
    ...(error ? { error } : {}),
  };
  results.push(rec);
  console.error(JSON.stringify(rec));
  return value;
}

const out = { date: new Date().toISOString(), model: MODEL, steelBase, results, notes: {} };
let stagehand;
try {
  await timed("steel.createSession(extensions=[stagehand])", async () => {
    const r = await fetch(`${steelBase}/v1/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ extensions: ["stagehand"] }),
    });
    if (!r.ok) throw new Error(`steel HTTP ${r.status}`);
  });
  const browser = await timed("localBrowser.connect", () => localBrowser.connect({ cdpUrl }));
  stagehand = await timed("Stagehand.create", () =>
    Stagehand.create({ browser, model: { generate: llm.generate }, logging: { level: "warn" } }),
  );
  const page = (await browser.context.activePage()) ?? (await browser.context.newPage());

  // 1. observe
  await timed("goto quotes.toscrape.com", () => page.goto("https://quotes.toscrape.com/"));
  const obs = await timed("observe('the Next pagination link')", () =>
    stagehand.observe("find the 'Next' pagination link"),
  );
  out.notes.observe = { data: obs?.data, usage: obs?.metadata?.usage, cache: obs?.metadata?.cache };

  // 2. extract with a zod schema (2 LLM calls expected: Extraction + Metadata)
  const QuoteSchema = z.object({
    quotes: z.array(z.object({ text: z.string(), author: z.string() })),
  });
  const ex = await timed("extract(first 3 quotes, zod)", () =>
    stagehand.extract("extract the first 3 quotes on the page with their author", QuoteSchema),
  );
  out.notes.extract = { data: ex?.data, usage: ex?.metadata?.usage };

  // 3. act(observeResult) -> deterministic, expect 0 LLM calls
  if (obs?.data?.[0]) {
    const r = await timed("act(observe.data[0]) [expect 0 calls]", () => stagehand.act(obs.data[0]));
    out.notes.actFromObserve = { data: r?.data, usage: r?.metadata?.usage, url: await page.url() };
  }

  // 4. act(string) -> inference
  await timed("goto quotes.toscrape.com (reset)", () => page.goto("https://quotes.toscrape.com/"));
  const a1 = await timed("act('click the Next link')", () => stagehand.act("click the Next link"));
  out.notes.actString = { data: a1?.data, usage: a1?.metadata?.usage, cache: a1?.metadata?.cache, url: await page.url() };

  // 5. cache:true twice on a local (non-Browserbase) browser
  for (const i of [1, 2]) {
    await timed(`goto reset (cache run ${i})`, () => page.goto("https://quotes.toscrape.com/"));
    const r = await timed(`act('click the Next link', {cache:true}) run ${i}`, () =>
      stagehand.act("click the Next link", { cache: true }),
    );
    out.notes[`cacheRun${i}`] = { cache: r?.metadata?.cache, usage: r?.metadata?.usage, url: await page.url() };
  }

  // 6. decider path: snapshot -> deterministic pick -> act(Action). Expect 0 LLM calls.
  await timed("goto reset (decider)", () => page.goto("https://quotes.toscrape.com/"));
  const snap = await timed("page.snapshot()", () => page.snapshot());
  const lines = snap.formattedTree.split("\n");
  const nextLine = lines.find((l) => /\]\s+link: Next/.test(l));
  const id = nextLine?.match(/\[(\d+-\d+)\]/)?.[1];
  const rawXpath = id ? snap.xpathMap[id] : undefined;
  out.notes.decider = {
    treeChars: snap.formattedTree.length,
    treeLines: lines.length,
    xpathEntries: Object.keys(snap.xpathMap).length,
    urlEntries: Object.keys(snap.urlMap ?? {}).length,
    pickedLine: nextLine?.trim(),
    id,
    rawXpath,
    sampleXpaths: Object.entries(snap.xpathMap).slice(0, 4),
  };
  if (rawXpath) {
    const r = await timed("act({selector:xpath from snapshot, method:click}) [expect 0 calls]", () =>
      stagehand.act({ selector: `xpath=${rawXpath}`, description: "Next pagination link", method: "click", arguments: [] }),
    );
    out.notes.decider.act = { data: r?.data, usage: r?.metadata?.usage, url: await page.url() };
  }

  // 7. broken selector, default selfHeal (false in v4) -> expect success:false and 0 calls
  const broken = await timed("act(broken selector, selfHeal default) [expect 0 calls]", () =>
    stagehand.act({ selector: "xpath=/html/body/div[99]/a[7]", description: "missing link", method: "click", arguments: [] }, { timeout: 8000 }),
  );
  out.notes.brokenDefault = { data: broken?.data, usage: broken?.metadata?.usage };

  // 8. variables: secret value must not reach the model
  await timed("goto the-internet /key_presses", () => page.goto("https://the-internet.herokuapp.com/key_presses"));
  const v = await timed("act('type %secret% into the text input', variables)", () =>
    stagehand.act("type %secret% into the text input box", { variables: { secret: CANARY } }),
  );
  const typed = await page.evaluate(() => document.querySelector("#target")?.value ?? null);
  const after = await timed("page.snapshot() after typing", () => page.snapshot());
  const promptsText = readFileSync(PROMPTS, "utf8");
  out.notes.variables = {
    data: v?.data,
    typedValueMatches: typed === CANARY,
    canaryInAnyPromptSoFar: promptsText.includes(CANARY),
    canaryInSnapshotAfterTyping: after.formattedTree.includes(CANARY),
  };
  // 9. a follow-up inference on the same page: does the typed secret leak through the a11y tree?
  await timed("observe('the text input') after typing", () => stagehand.observe("find the text input box"));
  out.notes.variables.canaryInPromptsAfterFollowupObserve = readFileSync(PROMPTS, "utf8").includes(CANARY);

  out.metrics = await stagehand.metrics();
} catch (e) {
  out.fatal = String(e?.message ?? e).slice(0, 800);
} finally {
  try {
    if (stagehand) await stagehand.close();
  } catch (e) {
    out.closeError = String(e);
  }
}
out.llm = { ...llm.stats, records: undefined };
out.llmRecords = llm.stats.records.map(({ output, ...r }) => r);
writeFileSync(`result-v4-${tag}.json`, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
