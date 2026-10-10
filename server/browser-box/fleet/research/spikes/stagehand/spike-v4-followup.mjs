// Follow-up probes, zero LLM calls expected: contenteditable inside an iframe via cross-frame xpath,
// TinyMCE body target, and whether a typed password value appears in the snapshot sent to models.
import { writeFileSync } from "node:fs";
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";

const steelBase = process.argv[2] ?? "http://127.0.0.1:3301";
const cdpUrl = steelBase.replace(/^http/, "ws") + "/";
let calls = 0;
const out = { date: new Date().toISOString(), probes: {} };
const findId = (tree, re) => tree.split("\n").find((l) => re.test(l))?.match(/\[(\d+-\d+)\]/)?.[1];
async function probe(name, fn) {
  const c0 = calls;
  try {
    out.probes[name] = { ...(await fn()), llmCalls: calls - c0 };
  } catch (e) {
    out.probes[name] = { error: String(e?.message ?? e).slice(0, 400), llmCalls: calls - c0 };
  }
  console.error(name, JSON.stringify(out.probes[name]).slice(0, 500));
}
let sh;
try {
  await fetch(`${steelBase}/v1/sessions`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ extensions: ["stagehand"] }) });
  const browser = await localBrowser.connect({ cdpUrl });
  sh = await Stagehand.create({
    browser,
    model: { generate: async () => { calls++; throw new Error("no LLM allowed in follow-up"); } },
    logging: { level: "error" },
  });
  const page = (await browser.context.activePage()) ?? (await browser.context.newPage());

  await probe("contenteditable inside same-origin iframe (srcdoc)", async () => {
    await page.goto("https://example.com/");
    await page.evaluate(() => {
      const f = document.createElement("iframe");
      f.id = "ed";
      f.srcdoc = '<div id="c" contenteditable="true" role="textbox" aria-label="Inner composer" style="min-height:30px"></div>';
      document.body.appendChild(f);
      return new Promise((r) => f.addEventListener("load", r));
    });
    const snap = await page.snapshot({ includeIframes: true });
    const id = findId(snap.formattedTree, /textbox: Inner composer/);
    const xpath = snap.xpathMap[id];
    const res = await sh.act({ selector: `xpath=${xpath}`, description: "inner composer", method: "fill", arguments: ["iframe text ok"] });
    const text = await page.evaluate(() => document.querySelector("#ed").contentDocument.querySelector("#c").innerText);
    return { id, xpath, success: res.data.success, message: res.data.message.slice(0, 200), text };
  });

  await probe("TinyMCE body target (the-internet /iframe)", async () => {
    await page.goto("https://the-internet.herokuapp.com/iframe", { waitUntil: "load", timeout: 30000 });
    await page.waitForTimeout(2500);
    const snap = await page.snapshot({ includeIframes: true });
    const pId = findId(snap.formattedTree, /^\s*\[[1-9]\d*-\d+\]\s+paragraph/);
    const bodyXpath = snap.xpathMap[pId]?.replace(/\/p\[1\]$/, "");
    const res = await sh.act({ selector: `xpath=${bodyXpath}`, description: "editor body", method: "fill", arguments: ["Hello TinyMCE"] });
    const info = await page.evaluate(() => {
      const b = document.querySelector("iframe")?.contentDocument?.body;
      return { text: b?.innerText ?? null, contentEditable: b?.getAttribute("contenteditable") ?? null };
    });
    return { bodyXpath, success: res.data.success, message: res.data.message.slice(0, 200), ...info };
  });

  await probe("password field value in snapshot after typing", async () => {
    await page.goto("https://example.com/");
    await page.evaluate(() => {
      const i = document.createElement("input");
      i.type = "password";
      i.setAttribute("aria-label", "Password");
      document.body.appendChild(i);
      const t = document.createElement("input");
      t.type = "text";
      t.setAttribute("aria-label", "Plain");
      document.body.appendChild(t);
    });
    let snap = await page.snapshot();
    const pw = findId(snap.formattedTree, /textbox: Password/);
    const tx = findId(snap.formattedTree, /textbox: Plain/);
    await sh.act({ selector: `xpath=${snap.xpathMap[pw]}`, description: "pw", method: "fill", arguments: ["PwCanary-4242"] });
    await sh.act({ selector: `xpath=${snap.xpathMap[tx]}`, description: "plain", method: "fill", arguments: ["TxtCanary-4242"] });
    snap = await page.snapshot();
    return {
      passwordValueInSnapshot: snap.formattedTree.includes("PwCanary-4242"),
      textValueInSnapshot: snap.formattedTree.includes("TxtCanary-4242"),
      lines: snap.formattedTree.split("\n").filter((l) => /textbox/.test(l)).map((l) => l.trim()),
    };
  });
} catch (e) {
  out.fatal = String(e?.message ?? e).slice(0, 500);
} finally {
  try { if (sh) await sh.close(); } catch {}
}
out.totalLlmCalls = calls;
writeFileSync("result-v4-followup.json", JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
process.exit(0);
