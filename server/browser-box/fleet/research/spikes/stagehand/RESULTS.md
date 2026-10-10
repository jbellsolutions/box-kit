# Stagehand spike results (v4.2.0 and v3.7.3 against self-hosted Steel)

Date: 2026-10-10 (UTC 07:00-07:45). Agent: stagehand deep-dive (rerun). Public test pages only
(example.com, quotes.toscrape.com, books.toscrape.com, the-internet.herokuapp.com). Nothing logged in, posted
or submitted.

## Setup

- Steel: `ghcr.io/steel-dev/steel-browser-api:latest` (local image 7a161b95e8a9, pulled 2026-09-16), Chromium
  152.0.7977.82 headless. Container `fleet-spike-stagehand`, `--memory 1536m --cpus 1.2`,
  `NODE_OPTIONS=--unhandled-rejections=warn`. **Removed at the end** (`docker rm -f`).
- Final working container command (v4 needs the in-container port to equal the host port, see finding 2):

  ```sh
  docker run -d --name fleet-spike-stagehand -p 127.0.0.1:3301:3301 --memory 1536m --cpus 1.2 \
    -e PORT=3301 -e DOMAIN=127.0.0.1:3301 -e CDP_DOMAIN=127.0.0.1:3301 \
    -e NODE_OPTIONS=--unhandled-rejections=warn \
    -v <npm>/node_modules/@browserbasehq/stagehand/dist/extension:/app/api/extensions/stagehand:ro \
    ghcr.io/steel-dev/steel-browser-api:latest
  curl -X POST http://127.0.0.1:3301/v1/sessions -H 'content-type: application/json' -d '{"extensions":["stagehand"]}'
  ```
- SDKs: `@browserbasehq/stagehand@4.2.0` (<scratch>/npm), `@browserbasehq/stagehand@3.7.3` +
  `@ai-sdk/openai-compatible@1.0.58` (<scratch>/npm-v3, `--legacy-peer-deps`). Node v24.14.0.
- Model: `z-ai/glm-5.3-flash` via OpenRouter chat completions, `reasoning.effort=low`, `max_tokens=2048`,
  `response_format=json_schema strict`, `provider.require_parameters=true`, temperature 0. Key loaded into the
  subprocess env only by `or_env.sh` (never printed or written).
- Ground truth for "zero model calls" = the call counter in `openrouter-llm.mjs` (every LLM request passes through it;
  v3 agent traffic passes through a counting `fetch`). Not `metrics()`.

## Commands

```sh
cd <scratch>/spikes/stagehand
node rawcdp.mjs ws://127.0.0.1:3301/ '[["Browser.getVersion"],["Extensions.getExtensions"],["Extensions.loadUnpacked",{"path":"/tmp/nonexistent"}],["Target.getTargets"]]'
node attach.mjs http://127.0.0.1:3301                  # stock Steel        -> fails (finding 1)
node attach.mjs http://127.0.0.1:3301 --session-ext    # recipe            -> works
SPEND_CAP=0.25 ./or_env.sh node spike-v4.mjs http://127.0.0.1:3301
./or_env.sh node spike-v4-features.mjs http://127.0.0.1:3301
node spike-v4-followup.mjs http://127.0.0.1:3301       # zero-LLM by construction (throwing model)
node spike-v4-overhead.mjs http://127.0.0.1:3301
cd v3 && ../or_env.sh node spike-v3.mjs ws://127.0.0.1:3301/
../or_env.sh node spike-v3-stale.mjs ws://127.0.0.1:3301/       # + ONLY_B / SKIP_RESET variants
node spike-v3-overhead.mjs ws://127.0.0.1:3301/
```

## Finding 1-3: can v4 attach to Steel? (raw: `results/probe-default.txt`, `results/attach-*.txt`)

| Attempt | Result |
|---|---|
| CDP `Extensions.getExtensions` on stock Steel (no `--enable-unsafe-extension-debugging`) | **works** on Chromium 152; lists only "Steel Recording Extension" |
| CDP `Extensions.loadUnpacked` on stock Steel | command available; returns `File path cannot be resolved.` for a path that is not inside the container |
| v4 `localBrowser.connect` on stock Steel | **fails in 36 ms: `File path cannot be resolved.`** (it sends the host path of the bundled extension) |
| Extension copied into container, `STAGEHAND_EXTENSION_DIRECTORY_PATH=/app/api/extensions/stagehand` | `loadUnpacked` returns an id but the extension never runs (Steel launches Chromium with `--disable-extensions-except=<recorder>`); connect **times out after 60 s** |
| Steel session created with `{"extensions":["stagehand"]}` (Steel adds it to `--load-extension`) | `getExtensions` now lists "Stagehand Runtime 1.1.0"; `connect` OK, but `Stagehand.create` **fails: `CDP websocket failed to open`** because the extension opens its own WebSocket to the SDK's `cdpUrl` (`ws://127.0.0.1:3301/`) from inside the container, where nothing listens on 3301 |
| Same, with Steel listening on 3301 inside the container too (`PORT=3301`, `-p 3301:3301`) | **works**: session 7.2 s (Chromium relaunch), connect 1.3 s, create 0.8 s, `goto` 0.9 s, `snapshot` 0.2 s |

## Finding 4: v4 primitives on quotes.toscrape.com (raw: `results/result-v4-z_ai_glm_5_3_flash.json`)

| Call | ms | LLM calls | in / out tokens | USD | Notes |
|---|---:|---:|---|---:|---|
| `observe("find the 'Next' pagination link")` | 2314 | 1 | 2495 / 26 | 0.000128 | `data[0] = {selector:"xpath=/html[1]/body[1]/div[1]/div[2]/div[1]/nav[1]/ul[1]/li[1]/a[1]", method:"click", arguments:[]}` |
| `extract(..., z.object({quotes:[{text,author}]}))` | 1981 | **2** | 2403 / 178 | 0.000257 | Extraction + Metadata calls; 3 correct quotes |
| `act(observe.data[0])` | 460 | **0** | 0 | 0 | navigated to /page/2/ |
| `act("click the Next link")` | 2823 | 1 | 3067 / 33 | 0.000158 | |
| `act("click the Next link", {cache:true})` run 1 | 5027 | 1 | 2756 / 42 | 0.000434 | `metadata.cache.status = "DISABLED"` |
| same, run 2 | 2479 | **1** | 3075 / 33 | 0.000158 | `DISABLED` again: **no cache on a non-Browserbase browser** |
| `page.snapshot()` | 386 | 0 | - | - | 6,981 chars, 167 lines, 256 xpathMap entries, 56 urlMap entries |
| decider: `act({selector:"xpath="+xpathMap["0-1888"], method:"click", arguments:[]})` | 282 | **0** | 0 | 0 | picked line `[0-1888] link: Next`; raw xpathMap value used as-is |
| `act(<broken xpath>)`, selfHeal default | 16 | **0** | 0 | 0 | `success:false`, "Could not find an element" |

`stagehand.metrics()` agreed with the counter. All structured outputs parsed (no code fences, no schema errors).

## Finding 5: v4 feature probes (raw: `results/result-v4-features.json`, `result-v4-followup.json`)

| Probe | Result |
|---|---|
| `act("type %secret% into the text input box", {variables:{secret:CANARY}})` on /key_presses | typed correctly; returned action `arguments:["%secret%"]`; **canary absent from the act prompt** |
| ...then `observe()` on the same page | **canary present in the snapshot and in the prompt sent to the model** (the a11y tree shows the input's value) |
| synthetic `<input type=password>` filled via `act(Action)` | password value **not** in the snapshot; plain text input value **is** |
| `selfHeal:true` + `act(<broken xpath>, description:"Next pagination link")` | **1 LLM call (2634 in / 40 out), healed, `success:true`** |
| same-origin iframe contenteditable via cross-frame xpath `/html[1]/body[1]/iframe[1]/html[1]/body[1]/div[1]` + `fill` | `success:true`, text set, 0 calls |
| the-internet /iframe TinyMCE | iframe tree visible (`[1-313] paragraph`), but the editor is `contenteditable="false"` (TinyMCE read-only without an API key) so `fill` correctly fails `unsupported-element`. Not a Stagehand result |
| synthetic contenteditable "Post composer" + `fill("Hello 👋 world #test")` | `success:true`; events `beforeinput:insertText:true`, `input:insertText:true` (trusted `Input.insertText`) |
| /shadowdom | shadow-root and slotted text both present in snapshot |
| /upload `page.locator("#file-upload").setInputFiles({name,mimeType,buffer})` | file attached (`hello.txt`, 26 B) over the remote CDP link, 0 calls; not submitted |
| /infinite_scroll `act({selector:"xpath=/html", method:"nextChunk"})` x3, then `mouse.wheel 2000` | paragraphs 3 -> 4 -> 5 -> 6 -> 7, 0 calls |
| /windows click `target=_blank` | `context.pages()` 1 -> 2, `activePage()` switched to the new tab |
| `page.screenshot()` | 28,946 bytes |

## Finding 6: overhead and concurrency (raw: `results/result-v4-overhead.json`, `result-v3-overhead.json`)

| | v4.2.0 | v3.7.3 |
|---|---|---|
| SDK process RSS (Node 24, idle after attach + snapshot) | ~98 MB | ~117-134 MB |
| In-browser cost | extension service worker heap 25 MB used / 34 MB total; Steel container 666 -> 708 MiB across the probe | none (no extension) |
| `page.snapshot()` books.toscrape.com | 1333 ms, 21,553 chars (~5.4k tokens) | 913 ms, 22,070 chars |
| Second instance on the same browser while the first is live | **rejected: "A Stagehand instance is already initialized"** | **attaches** (no guard; two controllers can fight) |
| After `close()` | new instance attaches; browser alive | browser alive (`close()` did not kill the Steel browser) |

## Finding 7: v3.7.3 against stock Steel (raw: `results/result-v3.json`, `result-v3-stale*.json`)

No extension, no port trick: `new Stagehand({env:"LOCAL", localBrowserLaunchOptions:{cdpUrl:"ws://127.0.0.1:3301/"}, llmClient, cacheDir})`.

| Call | ms | LLM calls | USD | Notes |
|---|---:|---:|---:|---|
| `init()` (CDP attach) | 201 | 0 | 0 | |
| `observe(...)` | 1847 | 1 | 0.000344 | returns `Action[]` directly |
| `extract(..., zod)` | 2085 | 2 | 0.000431 | |
| `act(observe[0])` | 652 | **0** | 0 | |
| `act("click the Next link")` cacheDir run 1 (miss) | 7823 | 1 | 0.000268 | wrote `v3-cache/<sha256>.json` |
| same, run 2 (hit) | 502 | **0** | 0 | **replayed from disk, zero model calls** |
| stale entry: cached xpath resolves to nothing | 22632 / 16272 | 1 / 1 | ~0.0004 | waits up to 15 s for the cached selector, then self-heals (selfHeal defaults **true** in v3). Run A failed (model returned null); rerun healed and **rewrote** the entry |
| stale entry: cached xpath now points at a **different** link | 392 | **0** | 0 | **`success:true` but landed on `/tag/love/` instead of `/page/2/`**: silent wrong click |
| decider: `page.snapshot()` + `act({xpath})` | 628 + 580 | 0 | 0 | same shape as v4 |
| `agent({mode:"dom"}).execute(...)` run 1 | 5712 | 4 | 0.001665 | tools: goto, ariaTree, done; correct answer (Marilyn Monroe) |
| same instruction, run 2 | 1198 | **0** | 0 | **agent cache replay from cacheDir** |

## Finding 8: Python SDK 4.2.0, zero-LLM (raw: `spike_v4_python.py`)

`local_browser.connect(cdp_url="ws://127.0.0.1:3301/")` then `Stagehand.create(browser=..., model=<raising callback>,
self_heal=False)`, `page.snapshot()`, decider pick `[0-207] link: Next`, `act({"selector": "xpath=...", "method": "click", ...})`.
Result: attach 43 ms (after the Steel session existed), act 480 ms, `success: true`, landed on `/page/2/`,
**0 LLM calls**, max RSS 55 MB. The Python wheel's runtime accepted the extension mounted from the **TS** package
(same Stagehand Runtime 1.1.0), so one baked extension serves both SDKs at 4.2.0.

## Finding 9: dependency audit (fresh lockfiles, 2026-10-10)

`npm i --package-lock-only --legacy-peer-deps @browserbasehq/stagehand@<v> zod@^4` then `npm audit --omit=dev`:

| | all deps (incl. optional providers) | `--omit=optional` |
|---|---|---|
| 3.7.3 | 19 (17 moderate, 2 high) | **5 (3 moderate, 2 high)**: `undici` ≤6.28.0 (request smuggling, CRLF, decompression DoS, ...) and `@fastify/busboy`, via `@ai-sdk/provider-utils@3.0.41` ← `ai@5.0.273` (direct dep, declared `^5.0.185`) and `@ai-sdk/gateway` |
| 4.2.0 | **0** | **0** |

`npm audit fix` (no `--force`) left the 3.7.3 tree unchanged. `ai@5.0.273` and `@ai-sdk/provider-utils@3.0.41` are the
newest 5.x / 3.x releases; `provider-utils` added `undici ^5.29.0` after 3.0.30. Untested options: an `overrides`
pin to `ai ≤5.0.222` / `provider-utils ≤3.0.30`, or AI SDK 6+, which is a major bump v3 does not declare. Whether
the vulnerable undici paths are reachable at runtime in Stagehand was not analysed.

## Model behaviour (GLM 5.3 Flash @low)

- 26 calls total, all valid JSON for the strict `json_schema`; no structured-output failures, so no fallback model
  was needed.
- **False `null` act results**: 3 of 12 act inferences on fully loaded pages returned `action:null` for an element
  that existed (a 4th null came from a page whose `domcontentloaded` timed out, so it is excluded). 2 of the 3 were
  served by the Together endpoint, 1 by OpenInference. The sample is far too small to call this provider-dependent;
  treat that as a hypothesis for the fleet benchmark. Either way, act needs a retry-on-null (ideally on another
  provider) in the fleet shim.
- Latency per inference call 0.3-2.9 s (median about 0.7 s on the OpenRouter side); the end-to-end act adds snapshot and
  DOM-settle time (2.5-5 s total).

## Spend

26 OpenRouter calls, **$0.0067 total for this rerun** (v4 $0.0022, v3 act/observe/extract $0.0029, v3 agent $0.0017). Cap was $0.60
for hands-on, $0.80 for the agent. The interrupted first attempt's spend (if any) is unknown: the OpenRouter key is
shared with other concurrent work, so it cannot be separated from account-level usage.
