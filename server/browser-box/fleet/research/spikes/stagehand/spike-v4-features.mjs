// Stagehand 4.2.0 feature probes on public test pages (Q6, Q7, self-heal). Mostly zero-LLM:
// snapshot + act(Action) + Locator APIs. Inference only for the variables test and the self-heal test.
// Usage: or_env.sh node spike-v4-features.mjs [steelBase]
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";
import { makeOpenRouterLLM } from "./openrouter-llm.mjs";

const steelBase = process.argv[2] ?? "http://127.0.0.1:3301";
const cdpUrl = steelBase.replace(/^http/, "ws") + "/";
const MODEL = process.env.SPIKE_MODEL ?? "z-ai/glm-5.3-flash";
const PROMPTS = "prompts-v4-features.jsonl";
const LOG = "llm-calls-v4-features.jsonl";
for (const f of [LOG, PROMPTS]) rmSync(f, { force: true });
const CANARY = "CanaryS3cret-7781";
const llm = makeOpenRouterLLM({ model: MODEL, logFile: LOG, promptDumpFile: PROMPTS });
const out = { date: new Date().toISOString(), model: MODEL, probes: {} };
const T = () => performance.now();

async function probe(name, fn) {
  const c0 = llm.stats.calls;
  const t0 = T();
  try {
    out.probes[name] = { ...(await fn()), ms: Math.round(T() - t0), llmCalls: llm.stats.calls - c0 };
  } catch (e) {
    out.probes[name] = { error: String(e?.message ?? e).slice(0, 500), ms: Math.round(T() - t0), llmCalls: llm.stats.calls - c0 };
  }
  console.error(name, JSON.stringify(out.probes[name]).slice(0, 400));
}
async function gotoRetry(page, url) {
  for (let i = 0; i < 3; i++) {
    try {
      await page.goto(url, { waitUntil: "load", timeout: 30000 });
      return;
    } catch (e) {
      if (i === 2) throw e;
    }
  }
}
const findId = (tree, re) => tree.split("\n").find((l) => re.test(l))?.match(/\[(\d+-\d+)\]/)?.[1];

let sh;
try {
  const r = await fetch(`${steelBase}/v1/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ extensions: ["stagehand"] }),
  });
  if (!r.ok) throw new Error(`steel HTTP ${r.status}`);
  const browser = await localBrowser.connect({ cdpUrl });
  // selfHeal ON for this instance so the self-heal probe can show when it calls the model.
  sh = await Stagehand.create({ browser, model: { generate: llm.generate }, selfHeal: true, logging: { level: "error" } });
  const ctx = browser.context;
  const page = (await ctx.activePage()) ?? (await ctx.newPage());

  await probe("variables (secret never sent to model)", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/key_presses");
    const res = await sh.act("type %secret% into the text input box", { variables: { secret: CANARY } });
    const typed = await page.evaluate(() => document.querySelector("#target")?.value ?? null);
    const afterTyping = await page.snapshot();
    const leakedBefore = readFileSync(PROMPTS, "utf8").includes(CANARY);
    await sh.observe("find the text input box");
    return {
      success: res.data.success,
      actions: res.data.actions,
      typedValueIsCanary: typed === CANARY,
      canaryInPromptsDuringAct: leakedBefore,
      canaryInSnapshotAfterTyping: afterTyping.formattedTree.includes(CANARY),
      canaryInPromptsAfterFollowupObserve: readFileSync(PROMPTS, "utf8").includes(CANARY),
    };
  });

  await probe("selfHeal:true + broken selector (does it call the model?)", async () => {
    await gotoRetry(page, "https://quotes.toscrape.com/");
    const res = await sh.act({
      selector: "xpath=/html/body/div[99]/a[7]",
      description: "Next pagination link",
      method: "click",
      arguments: [],
    });
    return { success: res.data.success, message: res.data.message.slice(0, 200), actions: res.data.actions, usage: res.metadata.usage, url: await page.url() };
  });

  await probe("iframe + contenteditable (TinyMCE) via snapshot -> act(fill)", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/iframe");
    await page.waitForTimeout(2500);
    const snap = await page.snapshot({ includeIframes: true });
    const lines = snap.formattedTree.split("\n");
    const iframeLines = lines.filter((l) => /\[[1-9]\d*-\d+\]/.test(l));
    const id = iframeLines.map((l) => l.match(/\[(\d+-\d+)\]/)?.[1]).find((i) => i && /paragraph|RootWebArea|body/.test(lines.find((l) => l.includes(`[${i}]`)) ?? ""));
    const target = findId(snap.formattedTree, /^\s*\[[1-9]\d*-\d+\]\s+paragraph/) ?? id;
    const xpath = target ? snap.xpathMap[target] : undefined;
    let fill;
    if (xpath) {
      const res = await sh.act({ selector: `xpath=${xpath}`, description: "editor body", method: "fill", arguments: ["Hello from Stagehand"] });
      fill = { success: res.data.success, message: res.data.message.slice(0, 300) };
    }
    const editorText = await page.evaluate(() => {
      const f = document.querySelector("iframe");
      return f?.contentDocument?.body?.innerText ?? null;
    });
    return {
      iframeNodeLines: iframeLines.length,
      sampleIframeLines: iframeLines.slice(0, 6).map((s) => s.trim()),
      target,
      xpath,
      fill,
      editorText,
      readOnlyBanner: /read-only|readonly/i.test(snap.formattedTree),
    };
  });

  await probe("synthetic contenteditable (fill -> Input.insertText path)", async () => {
    await gotoRetry(page, "https://example.com/");
    await page.evaluate(() => {
      const d = document.createElement("div");
      d.id = "composer";
      d.setAttribute("contenteditable", "true");
      d.setAttribute("role", "textbox");
      d.setAttribute("aria-label", "Post composer");
      d.style.cssText = "min-height:40px;border:1px solid #000";
      document.body.appendChild(d);
      window.__inputEvents = [];
      d.addEventListener("beforeinput", (e) => window.__inputEvents.push(`${e.type}:${e.inputType}:${e.isTrusted}`));
      d.addEventListener("input", (e) => window.__inputEvents.push(`${e.type}:${e.inputType}:${e.isTrusted}`));
    });
    const snap = await page.snapshot();
    const id = findId(snap.formattedTree, /textbox: Post composer/);
    const res = await sh.act({ selector: `xpath=${snap.xpathMap[id]}`, description: "post composer", method: "fill", arguments: ["Hello 👋 world #test"] });
    const state = await page.evaluate(() => ({ text: document.querySelector("#composer").innerText, events: window.__inputEvents.slice(0, 6) }));
    return { id, success: res.data.success, ...state };
  });

  await probe("shadow DOM content in snapshot", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/shadowdom");
    const snap = await page.snapshot();
    return {
      hasShadowText: snap.formattedTree.includes("Let's have some different text!"),
      hasSlotText: snap.formattedTree.includes("In a list!"),
      treeChars: snap.formattedTree.length,
    };
  });

  await probe("file upload via Locator.setInputFiles (no submit)", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/upload");
    await page.locator("#file-upload").setInputFiles({ name: "hello.txt", mimeType: "text/plain", buffer: new TextEncoder().encode("hello from the fleet spike") });
    const files = await page.evaluate(() => Array.from(document.querySelector("#file-upload").files).map((f) => ({ name: f.name, size: f.size, type: f.type })));
    return { files };
  });

  await probe("infinite scroll via act(nextChunk) x3", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/infinite_scroll");
    await page.waitForTimeout(1500);
    const count = () => page.evaluate(() => document.querySelectorAll(".jscroll-added").length);
    const before = await count();
    const steps = [];
    for (let i = 0; i < 3; i++) {
      const res = await sh.act({ selector: "xpath=/html", description: "page", method: "nextChunk", arguments: [] });
      await page.waitForTimeout(1200);
      steps.push({ success: res.data.success, count: await count() });
    }
    const wheel = await sh.act({ selector: "xpath=/html", description: "page", method: "mouse.wheel", arguments: ["2000"] }).catch((e) => ({ data: { success: false, message: String(e) } }));
    await page.waitForTimeout(1200);
    return { before, steps, wheel: { success: wheel.data.success, message: wheel.data.message?.slice(0, 150) }, afterWheel: await count() };
  });

  await probe("new tab (target=_blank) handling", async () => {
    await gotoRetry(page, "https://the-internet.herokuapp.com/windows");
    const before = (await ctx.pages()).length;
    const snap = await page.snapshot();
    const id = findId(snap.formattedTree, /link: Click Here/);
    await sh.act({ selector: `xpath=${snap.xpathMap[id]}`, description: "Click Here", method: "click", arguments: [] });
    await page.waitForTimeout(2000);
    const pages = await ctx.pages();
    const active = await ctx.activePage();
    return {
      pagesBefore: before,
      pagesAfter: pages.length,
      activeUrl: active ? await active.url() : null,
      urls: await Promise.all(pages.map((p) => p.url())),
    };
  });

  await probe("screenshot", async () => {
    const png = await page.screenshot();
    return { bytes: png.byteLength };
  });

  out.metrics = await sh.metrics();
} catch (e) {
  out.fatal = String(e?.message ?? e).slice(0, 800);
} finally {
  try {
    if (sh) await sh.close();
  } catch {}
}
out.llm = { calls: llm.stats.calls, costUsd: llm.stats.costUsd, inputTokens: llm.stats.inputTokens, outputTokens: llm.stats.outputTokens };
out.llmRecords = llm.stats.records.map(({ output, ...r }) => r);
writeFileSync("result-v4-features.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
