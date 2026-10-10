> **Read with its verification report.** [verification/stagehand.md](../verification/stagehand.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Stagehand dossier (deep dive, rerun)

Date: 2026-10-10. Pins: `browserbase/stagehand` monorepo @ `1fc884992b68a0196ea5c6e96cc29924b0922ef4`
(2026-10-09, clone `<scratch>/sources/stagehand`), npm `@browserbasehq/stagehand@4.2.0` and `@3.7.3`
(`v3` branch head `3554b02b2a`, 2026-08-28), PyPI `stagehand==4.2.0`. Steel `steel-browser` @ `1131a02`.
Spikes and raw numbers: [`spikes/stagehand/RESULTS.md`](../spikes/stagehand/RESULTS.md). Spend: **$0.0067** for this rerun (26 calls). The interrupted first attempt's spend is unknown.

Provenance tags: `hands-on` (run today against a `fleet-spike-stagehand` Steel container), `source-code`
(pinned commit or the installed package), `official-docs`, `vendor-claim`, `third-party`, `unverified`.

---

## 1. Verdict

1. **Stagehand v4 is not "Playwright plus an LLM". Its whole runtime runs inside a Chrome extension in the
   browser.** That includes the CDP driver, snapshots, act/observe/extract, prompts, and the LLM and cache HTTP
   calls when you use provider keys. The TS and Python SDKs are thin JSON-RPC clients over CDP. `source-code`
   (`packages/extension/**`, `sdk-ts/src/cdpClient.ts:337-412`).
2. **v4 can drive self-hosted Steel, but only with three undocumented steps.** Stock Steel fails with
   `File path cannot be resolved.` `hands-on`. The steps:
   - (a) The extension must be inside the Steel container. We bind-mounted it at `/app/api/extensions/stagehand`.
   - (b) Each Steel session must be created with `{"extensions":["stagehand"]}`. Steel launches Chromium with
     `--disable-extensions-except`, which neutralises `Extensions.loadUnpacked`.
   - (c) The CDP URL the SDK uses must also be reachable **from inside the browser**. The extension opens its own
     WebSocket to that URL (`extension/runtime.ts:396-399`). On a proxied profile, that host must be on Steel's
     `PROXY_INTERNAL_BYPASS` list (`source-code`, not tested with a proxy).

   No Browserbase, Stagehand server, or SEA binary is needed. Steel's own docs and cookbook still show **v3**
   (`official-docs`).
3. **v4 has no `agent()` and no local cache.** Caching is Browserbase-server-only. It is silently `DISABLED` without
   a Browserbase apiKey **and** a Browserbase sessionId, so on Steel every string `act` runs inference. Measured: two
   identical `act(...,{cache:true})` calls made 2 LLM calls, both `cache.status:"DISABLED"`. `hands-on` +
   `source-code` (`extension/services/cacheService.ts:62-73`). Sibling claim **confirmed**.
4. **The decider path works, with zero model calls, in both v3 and v4.** The path is `page.snapshot()`, then a
   decider picks a `[frame-backendId]` line, then `act({selector:"xpath="+xpathMap[id], method, arguments})`.
   Measured 0.28 s and 0 calls (v4), 0.58 s and 0 calls (v3). `act(observeResult)` was also 0 calls. `hands-on` +
   `source-code` (`extension/services/actService.ts:104-113`).
   - Caveat: self-heal is **off by default in v4** and **on by default in v3**. With `selfHeal:true`, a failing
     Action silently calls the model (measured: 1 call, then healed).
5. **v3.7.3 works on stock Steel with no changes.** It uses `env:"LOCAL"` with `localBrowserLaunchOptions.cdpUrl`.
   - Its `cacheDir` replay makes **zero model calls**: act run 2 took 0.50 s and 0 calls; `agent()` run 2 took
     1.2 s and 0 calls.
   - The same cache **clicked the wrong link with `success:true`** once the cached xpath pointed at a different
     element. The cache key is instruction + URL only, with no DOM check. `hands-on`.
   - The fleet needs its own replay cache, keyed and verified on element identity, whichever version it pins.
6. **Recommendation: pin v4 (4.2.0) as a deterministic executor plus an LLM grounding tool.** Build the agent loop,
   the replay cache and the decider tier in the fleet.
   - Don't pin v3 as a product dependency. It is in maintenance limbo: last release 2026-08-28, and an open v3 crash
     patch (#2910) is not released.
   - On a fresh v3.7.3 lockfile, `npm audit` reports 5 advisories in the non-optional tree (2 high: `undici` ≤6.28.0
     and `@fastify/busboy` via `ai@5.0.273` → `@ai-sdk/provider-utils@3.0.41`), and 19 with optional providers.
     `npm audit fix` left them in place. v4.2.0 reports 0. `hands-on`.
   - v3's agent and cache are a cheap reference design, not a foundation. Details are in Q-extra.
7. **Use the client callback (`model: { generate }`) for every model call.**
   - A provider-key `ModelConfig` makes the **browser** call the LLM, so the key sits inside the profile and the
     traffic leaves through the profile's sticky proxy IP (`extension/services/llmService.ts:21-35`).
   - The `ModelConfig` schema has no `baseURL`, so OpenRouter/GLM is only reachable through the callback anyway
     (`protocol/schemas.ts:688-694`).
8. **GLM 5.3 Flash @low handled every strict `json_schema` call (26/26).** On fully loaded pages, act returned a false
   `null` for an existing element in 3 of 12 inferences (2 of them served by Together, 1 by OpenInference).
   - The sample is too small to call this provider-dependent; that is a hypothesis for the fleet benchmark.
   - The fleet shim needs retry-on-null on another provider either way. `hands-on`.
9. **`variables` keep secrets out of the act prompt only.** The typed value then shows up in the accessibility tree,
   and our follow-up `observe()` sent it to the model. Password inputs are masked. `hands-on`. Humans must do
   logins, as the brief says.
10. **Concurrency: one Stagehand instance per browser.** v4 enforces it ("A Stagehand instance is already
    initialized"); v3 does not.
    - Process cost is small: Node SDK about 98 MB RSS (v4) or about 120-134 MB (v3); the v4 extension service worker
      uses about 25-34 MB heap per browser.
    - The browser dominates the footprint. `hands-on`.

---

## 2. Answers

### Q1. Versions, license, cadence; is Python 4.2.0 fully local?

- **TS**: `@browserbasehq/stagehand` latest **4.2.0** (2026-10-08). dist-tags: `latest 4.2.0`, `v3-latest 3.7.3`,
  `alpha 4.2.1-alpha-1fc8849…`. Stable cadence in 2026: 3.0.8 (Jan 22), 3.1.0 (Feb 24), 3.2.0 (Mar 18),
  3.3.0 (Apr 27), 3.4.0 (May 11), 3.5.0 (Jun 3), 3.6.0 (Jun 19), 3.7.0 (Jul 13), **4.0.0 (Aug 10)**, 4.0.1 (Aug 14),
  4.0.2 + 3.7.2 (Aug 20), **3.7.3 (Aug 28, last v3)**, 4.0.3 + 4.1.0 (Sep 9), 4.2.0 (Oct 8). That is a stable
  release every 2-4 weeks, plus an alpha publish on almost every commit to main. `source-code` (`npm view … time`,
  fetched 2026-10-10).
- **Python**: PyPI `stagehand` **4.2.0** (2026-10-08). Earlier stable releases: 4.0.0 (Aug 10), 4.0.1, 4.0.2,
  4.0.3, 4.1.0, plus **3.23.0 (2026-08-20)**, the last of the legacy 3.x line. Dev builds land almost daily.
  `source-code` (PyPI JSON).
- **License**: MIT for the SDKs, the extension and the monorepo (`LICENSE`, PyPI `License-Expression: MIT`).
  GitHub: 25.6k stars, 395 open issues, pushed 2026-10-10. `source-code`.
- **Python 4.2.0 is fully local** (`hands-on` + `source-code`). It needs no Stagehand server, no Browserbase API for
  the core, and no binary.
  - Ran `local_browser.connect` + `Stagehand.create(model=<raising callback>)` + `snapshot` + `act(Action)` against
    Steel: 0 LLM calls, 480 ms act, 55 MB max RSS (`spikes/stagehand/spike_v4_python.py`).
  - It accepted the extension mounted from the TS package (both Runtime 1.1.0).
  - The wheel bundles the built extension (`site-packages/stagehand/_extension/manifest.json`, `service-worker.js`,
    `content-script.js`; `extension_assets.py`).
  - `local_browser.connect(cdp_url=...)` passes `local_extension_dir=extension_directory()` with
    `api_key=None, browser=None` (`browser.py:531-557`). It then sends the same JSON-RPC (`stagehand.init/act/...`)
    over CDP (`stagehand.py:254-288`).
  - Dependencies: `browserbase`, `httpx`, `opentelemetry-api`, `pydantic`, `websockets`. The `browserbase` package
    is only used by the `browserbase.*` factory.
  - "Thin client" applies only in the sense that the engine runs in the browser extension. `source-code`.
- **The legacy Python 3.x line (≤3.23.0, repo `stagehand-python`, archived) is different.** It is a
  Stainless-generated REST client.
  - `server="remote"` targets the Browserbase-hosted Stagehand API; `server="local"` runs an embedded
    `stagehand-server-v3` binary. Steel's cookbook uses `AsyncStagehand(server="local", …)` with
    `stagehand>=3.19,<4`.
  - Sources: `official-docs` (`https://github.com/browserbase/stagehand-python/blob/a2af713/README.md` lines 138;
    `https://github.com/steel-dev/steel-cookbook/blob/40f1326/examples/stagehand-py/main.py` lines 96-111) and `third-party` (issue #2910: "the
    python SDK bundles and runs the v3 server").

### Q2. Architecture; attaching to an existing browser; the Gemini call shape

- **CDP-native, no Playwright.**
  - v4 drives Chromium through its own CDP layer ("understudy", `extension/understudy/*`), running in the extension
    service worker. That worker opens a WebSocket back to the browser's CDP endpoint
    (`understudy/browserWebSocketTransport.ts:64`).
  - The SDK talks to the worker with `Runtime.addBinding` / `Runtime.evaluate` on the service-worker target
    (`sdk-ts/src/cdpClient.ts:368-405`). Runtime deps are only `@browserbasehq/sdk`, OpenTelemetry and zod.
  - v3 is also CDP-native ("understudy" in-process, `ws` dependency). Playwright, Puppeteer and Patchright are only
    optional peer dependencies for interop.
  - `source-code`.
- **TS v4 attach.** `source-code` + `hands-on`.
  - Call shape:
    ```ts
    import { Stagehand, localBrowser } from "@browserbasehq/stagehand";
    const browser = await localBrowser.connect({ cdpUrl: "ws://127.0.0.1:3301/" }); // or http://host:9222
    const stagehand = await Stagehand.create({ browser, model: { generate: myLLM }, selfHeal: false });
    const page = (await browser.context.activePage()) ?? (await browser.context.newPage());
    ```
  - Option schema: `LocalBrowserConnectOptionsSchema = { cdpUrl, extensionId? }`, where `extensionId` is
    deprecated and ignored (`sdk-ts/src/clientSchemas.ts:58-63,313-318`).
  - Connect flow (`browser/factories.ts:122-138`, `cdpClient.ts:337-412`, `638-668`, `725-789`, `791-821`):
    1. `Extensions.getExtensions` finds an enabled extension named "Stagehand Runtime".
    2. Otherwise it calls `Extensions.loadUnpacked(path)`. The path comes from `STAGEHAND_EXTENSION_DIRECTORY_PATH`
       or `dist/extension/` (`extensionAssets.ts:14-20`).
    3. It waits for the service worker, attaches, and checks runtime compatibility.
  - **Gotcha**: `browser.close()` on a connected local browser sends `Browser.close` and kills the remote Chromium
    (`factories.ts:296-298`). Use `stagehand.close()` only.
- **Python v4 attach**:
  ```python
  from stagehand import Stagehand, local_browser
  browser = await local_browser.connect(cdp_url="ws://127.0.0.1:3301/")
  stagehand = await Stagehand.create(browser=browser, model=my_async_generate, self_heal=False)
  ```
  (`browser.py:531`, `stagehand.py:116-131`). `source-code` + `hands-on`: attach 43 ms, `act(Action)` 0 calls.
- **The Gemini shape `Stagehand(env="BROWSERBASE", cdp_url=...)` is not real.**
  - v4 Python has no `env` argument and no `cdp_url` on the `Stagehand` constructor. The constructor is private;
    use `Stagehand.create(...)` (`stagehand.py:96-104`).
  - The nearest real shapes are v3 TS `new Stagehand({ env: "LOCAL", localBrowserLaunchOptions: { cdpUrl } })` and
    legacy Python 3.x `sessions.start(browser={"type":"local","launchOptions":{"cdpUrl":…}})`.
  - `env:"BROWSERBASE"` plus a foreign `cdpUrl` was never the pattern; Browserbase sessions are addressed by
    session id (`browserbase.connect({apiKey, sessionId})`). `source-code`.
- **v3 TS attach (3.7.3)**:
  `new Stagehand({ env:"LOCAL", localBrowserLaunchOptions:{ cdpUrl, cdpHeaders?, connectTimeoutMs? }, llmClient?, model?, cacheDir?, selfHeal? })`
  then `await stagehand.init()`; pages via `stagehand.context.pages()` (`dist/esm/lib/v3/types/public/options.d.ts`,
  `v3.js:744-771`). Worked on stock Steel in 0.2 s. `hands-on`.

### Q3. Primitives: signatures, return shapes, what goes to the model; agent modes

v4 (TS `sdk-ts/src/stagehand.ts`, protocol `packages/protocol/schemas.ts`; Python mirrors it with snake_case keyword
arguments). `source-code`, shapes confirmed `hands-on`:

| Call | Signature | Returns | LLM calls / prompt |
|---|---|---|---|
| `act` | `act(instruction: string \| Action, { model?, variables?, timeout?, locator?, ignoreLocators?, cache?, page? })` (`stagehand.ts:232-246`) | `ActResult = { data: { success, message, actionDescription, actions: Action[] }, metadata: { usage:{inputTokens,outputTokens,reasoningTokens,cachedInputTokens,inferenceTimeMs}, cache:{status:"HIT"\|"MISS"\|"DISABLED",…}, actionId? } }` (`schemas.ts:1001-1030`) | string: **1** (or 2 when the model sets `twoStep:true` for non-`<select>` dropdowns). System `buildActSystemPrompt`, user `instruction: <buildActPrompt(...)>\nAccessibility Tree: <tree>` (`extension/prompt.ts:192-260`, `inference.ts:215-247`). Schema `{action:{elementId:"^\d+-\d+$",description,method∈SupportedUnderstudyAction,arguments[]}\|null, twoStep}` (`inference.ts:60-85`). `Action` object: **0** (`actService.ts:104-113`) |
| `observe` | `observe(instruction?, { model?, variables?, timeout?, locator?, ignoreLocators?, cache?, page? })` (`stagehand.ts:248-268`) | `ObserveResult = { data: Action[], metadata }` (`schemas.ts:1121-1126`). **v4 wraps the array in `.data`** (v3 returned the bare array) | **1**. `buildObserveSystemPrompt` (lists supported methods and the variable names/descriptions) + same user message. Schema `{elements:[{elementId,description,method,arguments}]}` (`inference.ts:34-58,174-213`). Default instruction when omitted: "Find elements that can be used for any future actions…" (`observeService.ts:21-22`) |
| `extract` | `extract(instruction, zodSchema?, { model?, timeout?, locator?, ignoreLocators?, screenshot?, cache?, page? })` (`stagehand.ts:270-310`) | `{ data: z.output<schema>, metadata }`; default schema `{extraction:string}` | **2**: "Extraction" (system `buildExtractSystemPrompt`, user `Instruction: …\nDOM: <tree>` plus an optional viewport screenshot), then "Metadata" `{progress, completed}` (`inference.ts:127-172`). Measured 2 calls |
| `Action` | `{ selector: string, description: string, method?: string, arguments?: string[] }` (`schemas.ts:851-874`) | n/a | methods: `click, fill, type, press, scrollTo, nextChunk, prevChunk, selectOptionFromDropdown, hover, doubleClick, dragAndDrop` (`types/private/handlers.ts`). The executor also accepts `scrollIntoView, scrollByPixelOffset, scroll, mouse.wheel, selectOption` (`handlers/handlerUtils/actHandlerUtils.ts:121-138`) |
| `page.snapshot` | `snapshot({ timeout?, includeIframes? })` | `{ formattedTree, xpathMap: {"0-1888":"/html[1]/…/a[1]"}, urlMap }` (`schemas.ts:1164-1170`) | 0 |

- **Every inference needs a configured model** even when it will not be used: act/observe/extract throw "An LLM was
  not configured" otherwise (`controllers/stagehandController.ts:72-75`). A throwing `generate` is enough for pure
  Action use (`hands-on`, `spike-v4-followup.mjs`).
- **Agent modes do not exist in v4** (`https://docs.stagehand.dev/v4/migrations/v3.md`: "agent() is gone"; no agent method in either
  SDK). The leftover `buildOperatorSystemPrompt` / `buildCuaDefaultSystemPrompt` in `extension/prompt.ts` are unused.
  `source-code`. Sibling claim **confirmed**.
- **v3 agent** (`agent(config).execute({instruction, maxSteps})`), from `dist/esm/lib/v3/types/public/agent.d.ts`,
  `handlers/v3AgentHandler.js:109-112`, `agent/AgentProvider.js`:
  - `mode:"dom"` (default): tools act, fillForm, ariaTree, extract, goto, scroll, keys, navback, screenshot, think,
    wait, done, search. Search needs a Browserbase key. It needs **any AI SDK LanguageModel**: the `llmClient` must
    implement `getLanguageModel()`, a known gap in issue #1669 for custom clients.
    - **Ran with GLM 5.3 Flash via `@ai-sdk/openai-compatible`**: 4 calls, $0.0017, correct answer; run 2 replayed
      from `cacheDir` with 0 calls. `hands-on`.
  - `mode:"hybrid"`: coordinate tools (click/type/dragAndDrop/clickAndHold/fillFormVision). Auto-selected for model
    ids containing `gemini-3`, `claude`, `gpt-5.4`, `gpt-5.5`, `gpt-5.6` (`types/private/agent.js:5-11`).
  - `mode:"cua"`: only models in `modelToAgentProviderMap`: OpenAI `computer-use-preview`/`gpt-5.4+`, Anthropic
    Claude 4.x/`claude-fable-5`, Google `gemini-2.5-computer-use`/`gemini-3*`. **GLM cannot run CUA mode.**
    `source-code`.

### Q4. Model layer, OpenRouter, custom LLM interface, and whether a decision model can drive act

- **Providers (v4)**: `openai, anthropic, google, groq, cerebras` (`protocol/schemas.ts:15-46`), plus Vertex and Azure
  provider options and the Browserbase Model Gateway (no key, Browserbase session required:
  `extension/llm/gatewayClient.ts`, `llmService.ts:25-33`).
  - `ModelConfig = {modelName, apiKey?, headers?}` is strict and has **no baseURL** (`schemas.ts:676-694`).
  - **OpenAI-compatible endpoints such as OpenRouter are only reachable through the client callback.** `source-code`
    + `hands-on`.
- **v3** additionally accepts `model: { modelName, apiKey, baseURL }` (OpenAI-compatible) and a custom `llmClient`
  subclass (`LLMClient.d.ts`, `types/public/model.d.ts:84-124`). `source-code`.
- **Custom LLM interface (v4)**: TS `model: { generate(params: LLMGenerateParams): Promise<LLMGenerateResult> }`;
  Python `model=<async callable>` (`LLMGenerateCallback`, `client_types.py`).
  - `params` = `{ messages[{role, content:{type:"text",text}|{type:"image",mimeType,data}}], systemPrompt?, temperature?, stopSequences?, responseFormat?: {type:"json_schema", name, schema} | text, tools?, toolChoice? }`.
  - The result must be
    `{ role:"assistant", content, outputFormat:"json_schema", structuredContent, usage?:{inputTokens,outputTokens,totalTokens,reasoningTokens?,cachedInputTokens?} }`.
    It is validated against the request's JSON Schema (`protocol/schemas.ts:340-411`,
    `extension/llm/clientLlmClient.ts:11-19`).
  - The SDK registers the callback as the JSON-RPC request handler `llm.generate`, so LLM traffic leaves the SDK
    process, not the browser (`stagehand.ts:200-205`).
  - Working adapter: `spikes/stagehand/openrouter-llm.mjs`.
- **Structured-output requirement**: every act/observe/extract call is a `json_schema` request, and a text answer is a
  hard error (`inference.ts:94-125`). GLM 5.3 Flash with `strict:true` + `provider.require_parameters:true`: 26/26 valid.
  `hands-on`.
- **Can a non-generative decision model drive act? Yes, two ways.**
  1. **Recommended: skip act's inference entirely.**
     - Call `page.snapshot()` (0 LLM calls; 0.2-1.3 s; quotes page 6,981 chars, books page about 5.4k tokens).
     - Parse its lines (`[0-1888] link: Next`) into candidates.
     - Let the decider pick an index.
     - Call `act({ selector: "xpath=" + xpathMap[id], description, method, arguments })`.
     - This takes the deterministic path (`actService.ts:104-113` → `takeDeterministicAction` →
       `performUnderstudyMethod`, `actService.ts:330-397`). Measured **0 calls, 0.28 s** (v4) and 0 calls, 0.58 s
       (v3). `hands-on` + `source-code`.
     - The decider supplies only the *which*. **`method` and any text `arguments` must come from code or the
       reasoning model.** For example: click for links and buttons, `fill` for textboxes with code-supplied text.
     - Raw `xpathMap` values work as-is for element nodes. For a `StaticText` node, trim a trailing `/text()[n]` as
       `trimTrailingTextNode` does (`utils.ts`), or pick its parent.
     - Cross-frame xpaths (`…/iframe[1]/html[1]/body[1]/div[1]`) work unchanged. `hands-on`.
  2. **Possible: put the decider behind the `generate` callback.**
     - The callback receives the full tree text and the instruction. It could pick an `elementId` and return
       `{action:{elementId, description, method, arguments}, twoStep:false}` as `structuredContent`.
     - This keeps Stagehand's prompt-free contract but wastes the snapshot-to-text round trip. `source-code`
       (inference) / `unverified`.
  - **`act(observeResult.data[i])` skips the LLM**: measured 0 calls, 0.46 s. `hands-on`.
  - **Exception: `selfHeal:true` makes a *failing* Action call the model** (`actService.ts:375-397`; measured 1 call).
    v4 default is `false` (`actService.ts:77`; `stagehandController.ts:85` passes the optional init value). v3
    default is **true** (`v3.js:729`, `this.opts.selfHeal ?? true`).
  - Sibling `system1-models` proposal **confirmed**, with the method/arguments caveat above.

### Q5. Caching and self-healing

- **v4: Browserbase server cache only.** `source-code` + `hands-on`.
  - `withCache` (`cacheService.ts:206-333`) ships the **raw `Accessibility.getFullAXTree` of every frame**, plus the
    instruction, URL and options, to `POST {apiUrl}/v1/cache/get|set` with `x-bb-api-key`
    (`clients/cacheClient.ts:127-160`). The server computes the key (DOM hash + normalized URL); the model is
    excluded.
  - On a hit, act replays the cached Actions with self-heal off. A failed replay falls back to full inference
    (`actService.ts:249-284`).
  - `buildCacheContext` returns `undefined` unless `apiKey` and `browser.sessionId` are both set (`:62-73`). Only the
    `browserbase.launch/connect` factories set a sessionId (`factories.ts:117,136,174-180,205-211`), so on Steel
    every call is `DISABLED`.
  - Measured on Steel: `cache:true`, same act twice, **2 LLM calls**, `status:"DISABLED"` both times.
  - Docs agree (`https://docs.stagehand.dev/v4/best-practices/caching.md`: local browser "the `cache` option has no effect and every call
    runs inference"; `v4/migrations/v3.mdx:509,601`). `official-docs`. Sibling claim **confirmed**.
- **Privacy notes for Browserbase caching (v4).**
  - The cache request carries the full AX tree of the page, which on social sites includes DMs and feeds.
  - The act cache `data` includes `options.variables` with **values** (`cacheService.ts:84-94`), so secrets passed as
    variables go to Browserbase when caching is on. `source-code`.
- **Can a self-hosted cache sit behind Stagehand's seam?** Not supported.
  - `apiUrl` is configurable, but `browser.sessionId` cannot be set for local browsers:
    `StagehandClientCreateConfigSchema` omits `browser` (`clientSchemas.ts:276-282`).
  - You would have to fork the SDK or speak raw JSON-RPC, and then implement Browserbase's private
    `/v1/cache/get|set` contract including its key computation.
  - **Build the cache outside Stagehand.** `source-code`.
- **v3 `cacheDir`.** `source-code` + `hands-on`.
  - Key: `sha256(JSON.stringify({instruction, normalizedUrl, sortedVariableKeys}))`
    (`dist/esm/lib/v3/cache/ActCache.js:21-38,129-136`).
  - Storage: `<cacheDir>/<sha256>.json` = `{version:1, instruction, url, variableKeys, actions[], actionDescription, message}`.
    Variable **values are not persisted**. `agent()` entries are `agent-<sha256>.json`.
  - Replay: waits up to **15 s** for each cached selector (`cache/utils.js:1,35-56`), then calls
    `takeDeterministicAction` with the LLM client for self-heal. When the healed actions differ, it **rewrites the
    entry** (`ActCache.js:137-245`).
  - A replay that fails is **returned as failed, with no fallback to fresh inference** (`v3.js:1059-1070`).
  - **Zero calls on a hit: proven** (act 0.50 s; agent 1.2 s).
  - **Hazards proven**:
    - (a) stale xpath: 16-23 s and 1 call. One run failed because the model returned null. One run healed and
      rewrote the entry.
    - (b) the xpath now resolves to a *different* element: **`success:true`, 0 calls, wrong page** (`/tag/love/`
      instead of `/page/2/`).
  - Works with any model, because the key excludes the model.

### Q6. Variables and secrets

- **v4 act.** `source-code` + `hands-on`.
  - Only `%name%` placeholders reach the model (`prompt.ts:211-223`).
  - Values are substituted in the extension right before execution (`actService.ts:506-521`), and the returned
    `actions[].arguments` keep `%secret%`. Measured: the canary was absent from the act prompt and was typed
    correctly.
- **v4 observe** sends variable **names and descriptions** (`prompt.ts:152-161`).
- **Leak path**: after typing, the value is part of the accessibility tree (`textbox` value). The next
  `observe/act/extract` on that page sends it to the model. Measured: canary present in the follow-up observe prompt.
  `<input type=password>` values are not in the tree (`hands-on`).
- **Implications**:
  - "Agents never type credentials" must stay a process rule: a human logs in via the live viewer.
  - For other sensitive text (DM drafts, client data), run inference before typing, or `ignoreLocators` the field,
    or use the decider path, which sends nothing to an LLM.
  - With Browserbase caching on, variable values go to Browserbase (Q5).

### Q7. Tabs, iframes, shadow DOM, rich-text composers, uploads, infinite scroll

All `hands-on` on public test pages, 0 LLM calls (decider/Action path):

- **Tabs**: clicking a `target=_blank` link: `context.pages()` went 1 → 2 and `activePage()` followed the new tab.
  `page` can be passed per call. `context.newPage()` and `setActivePage()` exist (`sdk-ts/src/browserContext.ts`).
- **Iframes**:
  - `snapshot({includeIframes:true})` shows child-frame nodes with frame ordinals (`[1-313] paragraph`).
  - The xpathMap gives cross-frame paths that `act(Action)` resolves (`resolveLocatorWithHops`,
    `actHandlerUtils.ts:62`). Contenteditable inside an iframe filled correctly.
  - The-internet's TinyMCE is read-only (no API key), so that page cannot test editing.
  - Open issues: #870 nested iframes with observe, and #2324 (closed) cross-origin iframe still loading.
- **Shadow DOM**: shadow-root and slotted text appear in the snapshot. Caveat issue #2693 (open): once *any* shadow
  root exists on the page, xpath resolution switches to a composed-tree parser that silently ignores unsupported
  predicates. Stagehand's own positional xpaths are fine; hand-written predicate xpaths are risky.
- **Rich-text composers**:
  - `fill` on a contenteditable returns `needsinput`, then focuses or selects, then issues **`Input.insertText`**
    (trusted input) (`dom/locatorScripts/scripts.ts:339`, `understudy/locator.ts:588-660`).
  - Measured on a synthetic composer: `beforeinput:insertText:true` and `input:insertText:true`, and emoji/hashtag
    text was set. This is the event shape Lexical (Facebook) and Draft.js (X) editors expect, but **not tested on real
    social sites** (forbidden here). `unverified` for X/Facebook.
  - `type` dispatches per-key events.
- **File uploads**:
  - `page.locator(sel).setInputFiles(path | {name, mimeType, buffer} | [...])` reads the file **in the SDK process**,
    sends base64 over CDP, and assigns it in-page. No shared filesystem is needed.
  - **Hard cap 50 MiB per file** (`sdk-ts/src/fileUpload.ts:3`, `extension/understudy/locator.ts:126`). Measured:
    attached over remote Steel.
  - Larger videos need Steel's files API (`POST /v1/sessions/:id/files`, `steel-browser api/src/modules/files/files.routes.ts:19`)
    plus raw CDP `DOM.setFileInputFiles` on the container path. Fleet-built, `unverified`.
  - Issue #972 (open): observe can't see `input[type=file]`; target it by selector.
  - Large `fullPage` screenshots or bodies over about 4-8 MiB overflow the base64 regex: issue #3060 (open, 4.1.0).
- **Infinite scroll**: `act({selector:"xpath=/html", method:"nextChunk"})` loaded 3 → 6 items in three calls, and
  `mouse.wheel` worked too. Stagehand does not loop for you; the fleet writes the scroll-until-N loop.

### Q8. Observability

- **v4**:
  - `logging: {level: off|error|warn|info|debug, format: pretty|json, onLog}` (`clientSchemas.ts:250-256`). Issue
    #3035 (open): `onLog` cannot be used without also writing to stderr.
  - Per-result `metadata.usage` (tokens, `inferenceTimeMs`) and `metadata.cache`. `stagehand.metrics()` gives
    per-primitive counters; measured equal to our counter.
  - OpenTelemetry traces via `telemetry: {traces: {endpoint: ".../v1/traces", headers}}` (`schemas.ts:1437-1448`).
    The exporter runs in the extension, i.e. from the browser's network.
  - `page.screenshot()`, `page.pdf()`. No `history`, no inference-to-file log, no session recording in OSS.
  - Cost in dollars is not computed; our OpenRouter shim records `usage.cost`.
- **v3**: `stagehand.history` (9 entries in our run), `stagehand.metrics` (adds agent token counters),
  `logInferenceToFile`, a `logger` hook, pino, and a flow logger.
- **Recordings/live view are Browserbase features.** Steel has its own recorder extension and DuckDB logs.
  `source-code`.

### Q9. Steel and Browserbase integration; what needs Browserbase

- **Steel's official guide is v3 only** (`official-docs`):
  - `steel-gh-docs/content/docs/integrations/stagehand.mdx` @322ad57 (2026-10-07) says `env:"LOCAL"` +
    `localBrowserLaunchOptions.cdpUrl` = session `websocketUrl` + `&apiKey=`.
  - The cookbook pins `@browserbasehq/stagehand ^3.2.1` (TS) and `stagehand>=3.19,<4` (Python, `server="local"`)
    (`steel-gh-steel-cookbook` @40f1326, 2026-09-02).
  - **No v4 Steel guide exists.**
- **v4 on self-hosted Steel works with the recipe in Verdict 2** (`hands-on`). Stagehand's docs say "Loading requires
  a shared filesystem" and nothing about the WebSocket-back requirement (`https://docs.stagehand.dev/v4/configuration/browser.md` lines 567-573).
  - This is what "the extension requirement for remote CDP targets is undocumented" means in practice.
  - Steel Cloud may differ; it was not tested (no key).
- **Browserbase native**: `browserbase.launch({apiKey, …session params})` / `browserbase.connect({apiKey, sessionId})`.
  Browserbase sessions are expected to have the extension preloaded (`preloadedExtension: true`,
  `factories.ts:142-214`).
- **What requires Browserbase**:
  - server-side caching;
  - Model Gateway (inference without your own key);
  - `browserbase.search/fetch` add-ons;
  - v3 agent `useSearch`;
  - v3 `model:"auto"` (Stagehand API only);
  - Browserbase stealth, proxies, captcha and recordings, which are session features.
  - `source-code` + `official-docs`.
- **What does not require Browserbase**: act/observe/extract/snapshot/Action/locators/uploads with your own model
  (`hands-on`).

### Q10. Concurrency and overhead

- **One Stagehand instance per browser.**
  - v4 enforces it in the extension: a second `Stagehand.create` on a live browser fails "A Stagehand instance is
    already initialized". After `close()`, a new one attaches. `hands-on` (`extension/runtime.ts:392`).
  - v3 has no guard: a second instance attached concurrently. The fleet's lane lock must enforce exclusivity.
    `hands-on`.
  - One instance can work several tabs through `page`.
  - Steel itself is one browser per container or instance, so the unit is profile = Steel instance = one Stagehand.
- **Overhead** (`hands-on`):
  - v4 Node SDK process about 98 MB RSS, flat across attach and snapshot. Mostly Node itself; one process can hold
    many instances, but per-extra-instance RSS was not measured.
  - v4 adds the extension service worker inside each browser: about 25 MB used / 34 MB total heap.
  - v3 Node process about 117-134 MB.
  - The Python 4.2.0 SDK peaked at 55 MB RSS.
  - Snapshots take 0.2-1.3 s of browser CPU.
  - The browser (about 700 MB for this Steel container) dominates.

### Q11. Known issues and limitations relevant to social SPAs (GitHub, 2026-10-10)

- #2945 (open, serious): `setDomainPolicy` is bypassed by service-worker fetches and WebSockets. Don't rely on
  Stagehand's domain policy as a security boundary.
- #2693 (open): xpath predicate semantics change once any shadow root exists.
- #870 (open): nested iframes with observe.
- #972 (open): observe ignores file inputs.
- #908, #1249 (open): `date`/`time`/`datetime-local` inputs.
- #3060 (open): base64 stack overflow on payloads over about 4-8 MiB.
- #3035 (open): logging.
- #1669 (open): v3 agent can't use a custom LLM client without `getLanguageModel`.
- #2910 (open): v3-lineage crash when CDP drops mid-request. The patch was posted 2026-09-09 as a "cherry-pick target
  for v3 release" and is unreleased, which is evidence that v3 fixes are not shipping.
- No issues mention X, Facebook, Instagram, TikTok, Lexical or Draft.js (searches returned nothing). That is absence
  of evidence, not support. `third-party` (GitHub issues).

### Q12. Hands-on summary

See [`RESULTS.md`](../spikes/stagehand/RESULTS.md).

| Primitive | v4 on Steel (GLM 5.3 Flash @low) | v3.7.3 on Steel |
|---|---|---|
| observe | 2.3 s, 1 call, $0.00013 | 1.8 s, 1 call, $0.00034 |
| extract | 2.0 s, 2 calls, $0.00026 | 2.1 s, 2 calls, $0.00043 |
| act string | 2.8 s, 1 call, $0.00016 | 7.8 s (cache miss), 1 call |
| cache replay | `DISABLED`, 2 calls | 0.5 s, **0 calls** |
| act(observe) | 0.46 s, 0 | 0.65 s, 0 |
| decider | 0.28 s, 0 | 0.58 s, 0 |

GLM structured output never failed, so no fallback model was needed. False-null rate is in Verdict 8. Total spend was
$0.0067. The container `fleet-spike-stagehand` was removed.

### Q-extra. v3 (3.7.3) vs v4 (4.2.0) for a self-hosted fleet

| | v3.7.3 | v4.2.0 |
|---|---|---|
| License | MIT | MIT |
| Maintenance | `v3-latest` tag. Last release 2026-08-28; `v3` branch idle since. Open v3 crash fix #2910 unreleased. Docs call v4 the path forward | Active: 4.0.0 → 4.2.0 in 2 months, near-daily alphas |
| Security (fresh lockfile, `npm audit --omit=dev`, 2026-10-10) | **5 advisories in the non-optional tree (3 moderate, 2 high: `undici` ≤6.28.0, `@fastify/busboy`)** via `ai@5.0.273` → `@ai-sdk/provider-utils@3.0.41`. 19 with optional providers. `npm audit fix` (no force) changed nothing; the newest `ai` 5.x and `provider-utils` 3.x are both in range. An `overrides` downgrade or AI SDK 6+ was not tested. `hands-on` | **0** |
| Install | 106 MB node_modules (AI SDK providers, OpenAI/Anthropic/Google SDKs, MCP, pino) | 3.4 MB package + small deps |
| Attach to Steel | **Plain `cdpUrl`, works on stock Steel** (Steel-documented) | Needs extension in container + session `extensions:["stagehand"]` + CDP URL reachable from inside the browser (+ proxy bypass) |
| Browser footprint | none | extension (content script on `<all_urls>`, all frames, `document_start`; `debugger`, `scripting`, `tabs` permissions; no `web_accessible_resources`). Anti-detection impact **unknown** |
| Where the LLM call happens | SDK process | callback: SDK process; provider-key: **inside the browser** |
| agent() | yes (dom works with GLM via AI SDK; hybrid/cua need specific vendors) | **no** |
| Local cache | `cacheDir`, zero-call replay, but URL + instruction key, no element check (**wrong-click proven**), 15 s stale waits, no fallback on failed replay | none (Browserbase-only) |
| Decider path (snapshot → act(Action)) | works, 0 calls | works, 0 calls |
| selfHeal default | **true** (failing Actions can call the model) | **false** |
| Exclusivity | none | one instance per browser enforced |
| Python | legacy 3.23.0: REST client + embedded server binary, repo archived | 4.2.0: same extension runtime, fully local |

**Recommendation**: build on **v4** and treat Stagehand as the deterministic executor plus grounding tool.

- Use `snapshot`, `act(Action)`, the `observe`/`act`/`extract` inference through our callback, locators, uploads and
  tabs.
- The fleet builds the agent loop (Hermes + reasoning model), the decider tier, and its own replay cache. The cache
  key should combine site, task step, URL pattern and an element fingerprint (role + accessible name + nearby text +
  frame path), verify the fingerprint before replay, and fall back to decider then LLM.
- The extension prerequisites become part of the fleet's Steel image (a 2 MB directory) and the session-create call.
  Pin SDK and extension together; the runtime compatibility check rejects mismatches.
- Use v3 only as a reference design, or as a short-lived bridge if `agent()` must exist before the fleet's loop does.
  In that case pin `3.7.3` exactly, keep `selfHeal` explicit, and wrap its cache with the element check.
- **The fleet must build its own replay cache in either case.** v4 has none off Browserbase, and v3's cache is unsafe
  without verification.
- Before committing to v4, the open risk is whether the extension changes the bot-detection profile. Hand that to
  the anti-detect agent.

---

## 3. What the open-source project gives us vs what the fleet must build

| Need | Stagehand gives (OSS, self-hosted) | Fleet must build |
|---|---|---|
| Attach to a profile's browser on Steel | v4 `localBrowser.connect`, v3 `cdpUrl` | Steel image with the extension baked in; session create with `extensions:["stagehand"]`; CDP URL reachable from the browser; `PROXY_INTERNAL_BYPASS` for proxied profiles; lane lock (v3 has no guard) |
| Element grounding by LLM | `act`/`observe`/`extract` prompts and schemas | OpenRouter `generate` adapter with `max_tokens`, `require_parameters`, reasoning effort, retry-on-null on another provider, cost accounting (`openrouter-llm.mjs` is a start) |
| Zero-LLM execution | `page.snapshot()` + `act(Action)` + locators | Candidate extraction from `formattedTree`, the System 1 decider call, the method/argument policy, verification after the action |
| Replay cache | v4: none off Browserbase. v3: unsafe URL + instruction cache | Fleet replay cache keyed on element fingerprint, verified before replay, with decider/LLM self-heal, stored per client/site (Obsidian holds memory, not this cache) |
| Agent loop | v4: none. v3: dom-mode agent | Hermes-driven loop or tool calling, step budgets, stop conditions; Browser-Use for open-ended tasks |
| Secrets | `variables` keep values out of the act prompt | Human login via live viewer; no typed credentials; avoid inference after typing sensitive text; never enable Browserbase caching with secret variables |
| Uploads | `setInputFiles` ≤50 MiB | Large-video path via Steel files API + raw CDP `DOM.setFileInputFiles` |
| Infinite scroll, feeds | `nextChunk`, `mouse.wheel` primitives | Scroll-until-N loops, dedupe, rate limits |
| Observability | per-call usage, `metrics()`, OTel from the browser, logs | Fleet traces per profile/task, cost in dollars, screenshots on failure, run history |
| Multi-tenancy, scheduling | nothing | Profile ↔ Steel instance mapping, wake on schedule, persistent state (Steel/Browserbase contexts) |
| Anti-detection | nothing (Browserbase stealth is cloud-only) | Separate workstream; also measure whether the v4 extension is detectable |

---

## 4. Operating notes for a Hermes agent (feeds the skills)

1. **Attach (v4, Steel)**: `POST /v1/sessions {"extensions":["stagehand"], …profile params}`, then
   `localBrowser.connect({cdpUrl})` with a URL the browser can reach too, then
   `Stagehand.create({browser, model:{generate}, selfHeal:false, logging:{level:"warn"}})`. Never call
   `browser.close()`, which kills the Steel browser. Call `stagehand.close()` when done. Only one instance per
   browser.
2. **Prefer zero-LLM steps.**
   - Use `page.goto`, `page.locator(css).click/fill`, and `page.waitForSelector` when the selector is known.
   - For a semantic target, take a `page.snapshot()` and let the decider choose. Then call
     `act({selector:"xpath="+xpathMap[id], method, arguments, description})`.
   - Use `observe()` (1 call) to plan several actions once, then `act(each)` at 0 calls.
3. **String `act()` costs about 1 call and 2-5 s** (3k input tokens on a small page). Write atomic instructions
   ("click the Next link"), one action each. Two-step dropdowns cost 2 calls.
4. **`extract()` costs 2 calls.** Pass a zod (TS) or pydantic (Python) schema. Scope it with `locator` to cut tokens.
   Use `screenshot:true` only when the tree lacks the data.
5. **Check `result.data.success`; it never throws on a miss.** A `null` from the model gives
   `"Failed to perform act: No action found"`; retry once, ideally on a different provider.
6. **Rich text**: target the contenteditable node (role `textbox`) with `method:"fill"`. It uses trusted
   `Input.insertText`. Verify by reading `innerText` back.
7. **Uploads**: `page.locator('input[type=file]').setInputFiles({name, mimeType, buffer})` up to 50 MiB. Larger files
   need the fleet's Steel-files path.
8. **Secrets**: never put a secret in an instruction. `variables` hide values from the act prompt only, and later
   inference on that page sees typed text.
9. **Tabs**: after a click that opens a tab, call `browser.context.activePage()` or `pages()` and pass `page` to
   later calls.
10. **Feeds**: loop `act({selector:"xpath=/html", method:"nextChunk"})` with a wait. Count items through
    `page.evaluate` and stop at N.
11. **Model**: GLM 5.3 Flash via the callback with `reasoning:{effort:"low"}`, `max_tokens` about 2048,
    `json_schema strict`, and `provider.require_parameters:true`. Never put provider keys in `ModelConfig` on fleet
    browsers.

---

## 5. Risks and unknowns

- **Anti-detection impact of the v4 extension is unknown.** It injects a content script into every frame at
  `document_start` and holds `debugger` permission. It exposes no `web_accessible_resources`, so it can't be probed by
  URL. Not measured. Hand to the anti-detect workstream. `unverified`.
- **Undocumented integration surface.** The extension path, `extensions:["stagehand"]`, and the WebSocket-back from
  the browser are not in either vendor's docs. A Steel or Stagehand change (Chrome flags, extension discovery,
  `--disable-extensions-except`) could break attach. Pin both images and versions, and run a smoke test on upgrade.
- **Proxy interaction is untested.** On a proxied profile, the extension's CDP WebSocket must bypass the residential
  proxy (`PROXY_INTERNAL_BYPASS` or loopback). Provider-key LLM calls and OTel traces would also leave through the
  proxy. `source-code` only.
- **v4 is fast-moving.** 4.0 → 4.2 shipped in 2 months. SDK and extension must match (runtime compatibility check).
- **GLM false nulls.** 3 of 12 act inferences on loaded pages. The provider dependence is unproven (small sample).
  Needs a larger eval in the fleet benchmark.
- **Real social-media composers (Lexical, Draft.js), X/Facebook iframes and shadow-DOM widgets were not tested**
  (forbidden in spikes). Only synthetic and public test pages were.
- **v3 security debt.** 2 high-severity advisories (`undici`, `@fastify/busboy`) in the required AI SDK v5 tree;
  `npm audit fix` didn't clear them. Runtime reachability was not analysed.
- **Browserbase caching sends full AX trees and variable values to Browserbase.** This matters if Browserbase is used
  as backup infra for client accounts.
- Steel Cloud was not tested (no key). Its preloaded-extension behaviour is unknown.

---

## 6. Sources

Source code (pinned):
- browserbase/stagehand @ `1fc884992b68a0196ea5c6e96cc29924b0922ef4` (2026-10-09):
  `packages/sdk-ts/src/{stagehand.ts,cdpClient.ts,clientSchemas.ts,extensionAssets.ts,fileUpload.ts,browserContext.ts,page.ts,browser/factories.ts,browser/localBrowser.ts}`,
  `packages/extension/{runtime.ts,inference.ts,prompt.ts,manifest.json,services/{actService,observeService,extractService,cacheService,llmService}.ts,controllers/stagehandController.ts,clients/{cacheClient,stagehandApi}.ts,llm/{clientLlmClient,aiSdkClient,gatewayClient,LLMProvider}.ts,understudy/{browserWebSocketTransport,locator}.ts,handlers/handlerUtils/actHandlerUtils.ts,dom/locatorScripts/scripts.ts,types/private/handlers.ts}`,
  `packages/protocol/schemas.ts`, `packages/docs/v4/migrations/v3.mdx`
- npm `@browserbasehq/stagehand@4.2.0` (`<scratch>/npm`) incl. `dist/extension/manifest.json` (Stagehand Runtime 1.1.0)
- npm `@browserbasehq/stagehand@3.7.3` (`<scratch>/npm-v3`): `dist/esm/lib/v3/{v3.js,cache/ActCache.js,cache/utils.js,handlers/actHandler.js,handlers/v3AgentHandler.js,agent/AgentProvider.js,types/private/agent.js,types/public/{options,model,agent}.d.ts,llm/LLMClient.d.ts}`; GitHub `v3` branch head `3554b02b2a` (2026-08-28)
- PyPI `stagehand==4.2.0` (`<scratch>/py/.venv/lib/python3.12/site-packages/stagehand/{browser.py,stagehand.py,extension_assets.py,_extension/}`)
- steel-dev/steel-browser @ `1131a0222a27f391bf8f27cca6f278ddf7ace8dd` (2026-10-06): `api/src/services/cdp/cdp.service.ts:806-948`, `api/src/utils/{extensions,proxy}.ts`, `api/src/env.ts`, `api/src/modules/files/files.routes.ts`
- Steel docs `steel-gh-docs` @ `322ad57` (2026-10-07) `content/docs/integrations/stagehand.mdx`; cookbook `steel-gh-steel-cookbook` @ `40f1326` (2026-09-02) `examples/stagehand-{ts,py}`

Docs / registries (fetched 2026-10-09/10):
- docs.stagehand.dev corpus: `https://docs.stagehand.dev/v4/{configuration/browser.md,best-practices/caching.md,migrations/v3.md}`, legacy `https://github.com/browserbase/stagehand-python/blob/a2af713/README.md`
- `npm view @browserbasehq/stagehand time dist-tags` (2026-10-10); `https://pypi.org/pypi/stagehand/json` (2026-10-10)
- GitHub issues (browserbase/stagehand, read 2026-10-10): #2945, #2693, #870, #972, #908, #1249, #3060, #3035, #1669, #2910, #2324, #1463

Hands-on artifacts: `fleet/research/spikes/stagehand/` (scripts, `RESULTS.md`, `results/*.json|jsonl`).
