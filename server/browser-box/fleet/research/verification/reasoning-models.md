# Verification: reasoning-models dossier

Adversarial verification of `fleet/research/dossiers/reasoning-models.md` (research date 2026-10-09).
Verifier run 2026-10-10. Rules followed: BRIEF.md. No containers, no Docker, no browser launched, no hermes CLI,
no HOME override. Key loaded from `browser-box/.env` into a subprocess env only and never printed.

**Method, in short.** I did not reuse the author's `score`/`valid` fields. Instead:

- I re-scored the raw JSONL with my own parser, jsonschema validator and ground-truth rules
  (`<scratch>/spikes/verify-reasoning-models/rescore.py`, output `rescore_out.txt`).
- I re-read the Stagehand source at the pinned commit `1fc8849`, the installed npm `@browserbasehq/stagehand@4.2.0`
  bundle, and the installed `browser_use 0.13.11` package.
- I re-fetched the OpenRouter models, endpoints and ZDR-endpoints APIs, the OpenRouter docs (`.md`) and the
  HF model API and README, all on 2026-10-10.
- I ran 41 small live OpenRouter calls: reasoning switches, provider pinning, ZDR routing, effort values, and a
  22-provider schema-enforcement sweep.

**Spend:** $0.0034 (sum of `usage.cost`; cap $0.10). The key's usage counter is shared with other agents and
lagged, so it is not a clean measure.

**Raw outputs** are in `<scratch>/spikes/verify-reasoning-models/`:

- `probes_2026-10-10.jsonl`, `provider_sweep_2026-10-10.jsonl`, `spend.jsonl`;
- `fetched/` (models, endpoints, ZDR list, docs, HF; all dated 2026-10-10).

## Verdict table

| id | claim (from dossier) | verdict | method (vs author) | evidence | correction | impact |
|---|---|---|---|---|---|---|
| REA-1 | **Correctness.** GLM 5.3 Flash @low:<br>• act/observe 48/53<br>• extracts 100%<br>• replayed Browser-Use (BU) steps 8/8<br>• tool call 3/3 | **confirmed** | Independent re-score of `raw/main.jsonl` + `glm_effort.jsonl` + `glm_temp.jsonl`: own parser, jsonschema Draft 2020-12 against captured schemas, own ground-truth rules. Author used `summarize.py` post-hoc rules | **My numbers:**<br>• GLM@low n=72: 70 valid, 2 runaways, 67/72<br>• act+obs 48/53, extract 11/11, BU 8/8<br>• `tools.jsonl`: GLM 3/3 `click(index=347)`, p50 0.91 s<br><br>**Caveats:**<br>• The 72 calls are 3-8 identical replays of 9 frozen requests from 4 pages.<br>• Every GLM task was served by exactly one provider: book_link Together 26/26, sharp_basket Friendli 26/26, observe Parasail 26/26, negative Venice 6/6.<br>• So the effective sample is "9 prompts × 5 providers", not 72 independent trials | Restate as: "48/53 act/observe on 6 frozen prompts from 2 sites, each served by a single provider (Friendli, Together, Parasail, Modal or Venice)". Per-provider quality is unknown. A 22-provider sweep today found 5 of 20 served providers wrong or invalid on a trivial act (see REA-7) | detail |
| REA-2 | **Speed and cost.** Stagehand calls (n=64) p50 1.2 s, p90 3.4 s. BU step p50 1.8 s. About $0.001 per uncached act on a 6k-token page | **partially-confirmed** | Recomputed percentiles from raw. Split by `cached_tokens`. Recomputed uncached cost at the $0.15/$0.50 list price | • n=64: p50 1.21 s, p90 3.44 s, max 50.1 s (exact).<br>• Only 12 of the 64 had no prompt-cache hit. Those 12 have **p50 1.68 s, p90 3.54 s**. The 52 cached calls have p50 1.10 s.<br>• Uncached act on the 6k-token books page, runaways excluded: **$0.00095** (book_link and sharp_basket 6.15k prompt tokens).<br>• The Q1 upper bound of $0.0013 is inflated by the runaway calls (mean with runaways $0.00125).<br>• Metadata call: $0.00012 (730+25 tokens, `captures/capture_calls.jsonl`) | The headline p50 is cache-flattered. Use **p50 ≈1.7 s / p90 ≈3.5 s per uncached Stagehand call** (n=12), consistent with the dossier's own warning that production acts are uncached. The cost of ~$0.001/act stands | detail |
| REA-3 | **The defect.** GLM's one defect is a runaway in the act schema's `arguments` array in ~3% of structured calls (4/144; 95% CI 1-7%), at both efforts, at t=0, on Together and Friendli. It is mitigable by the shim | **partially-confirmed** | Re-derived from raw: counted runaways, junk args and false nulls per task and per provider. Wilson CI. Today: 22-provider sweep plus repeat probes | • 4/144 and Wilson CI 1.1-6.9% are reproduced.<br>• **But all 4 runaways and both junk-argument cases fall on just 2 tasks:** book_link (Together only, 2 runaways) and sharp_basket (Friendli only, 2 runaways + 2 junk).<br>• Runaway rate on the 6k-page click acts: **4/52 = 7.7% (Wilson 3-18%)**. Act defect rate including junk arguments: **6/80 = 7.5%**.<br>• Provider and task are perfectly confounded. The data cannot separate "GLM degenerates" from "Together/Friendli constrained decoding degenerates".<br>• Today Friendli emitted `"elementId":"[0-218]"`, which violates the schema's `^\d+-\d+$` pattern under strict mode, so its grammar enforcement is incomplete.<br>• "Mitigable": the shim's cap plus retry was **not measured**, and "a 1k cap → a few seconds" is unmeasured (the dossier says so) | Say: "~7-8% of click acts on a 6k-token page produced a runaway or junk argument. Both occurred on 2 providers that each served one task. Unknown whether the cause is the model or the provider." Budget retries and latency for ~1 in 13 acts, not 1 in 33. Bench per provider (`provider.only`) before trusting the rate | detail |
| REA-4 | **Stagehand cannot reach OpenRouter through built-in config:**<br>• direct providers are only openai, anthropic, google, groq and cerebras;<br>• `ModelConfig` = `{modelName, apiKey, headers}`, no baseURL;<br>• the only open-model route is the client callback;<br>• the callback keeps the key client-side, while a direct config ships the key into the extension in the browser | **partially-confirmed** | Author read source. I re-read source at `1fc8849` **and** the installed npm 4.2.0 bundle (different route), including env-var escape hatches | **Confirmed:**<br>• `packages/protocol/schemas.ts:15` enum has the 5 providers.<br>• `ModelConfigSchema` (l.688) is a strictObject with apiKey, headers and modelName only.<br>• `ClientOptionsSchema` has `baseURL`, but is only used by `LLMProvider.ts` (evals).<br>• `aiSdkClient.ts:132` calls `createOpenAI({apiKey, headers, fetch})` with no baseURL.<br>• In the npm bundle, `loadOptionalSetting` reads `{}[environmentVariableName]`, so `OPENAI_BASE_URL` is dead.<br>• Same enum in `dist/extension/service-worker.js`.<br>• `sdk-ts/src/stagehand.ts` `stagehandCreateParamsForWorker` sends the model (with apiKey) to the worker unless `"generate" in model`.<br>• `cdpClient.ts:791` loads the extension into the target browser via CDP `Extensions.loadUnpacked`.<br><br>**Too strong:**<br>• "Only open-model route": Groq and Cerebras are built-in providers, and both are listed OpenRouter providers of open-weight `gpt-oss-120b` (`raw/endpoints/openai_gpt-oss-120b.json`).<br>• Not GLM 5.3 Flash: neither serves it.<br>• Native Groq/Cerebras model IDs were not checked.<br><br>**Unmentioned:** a third route, Browserbase Model Gateway (`gatewayClient.ts`). With no model and a Browserbase key and session, the model is `"auto"`, selected by Browserbase | "The only route to **GLM** (and to any OpenRouter-only model) is the client callback. Groq/Cerebras built-ins can reach some open-weight models (gpt-oss-120b), with a provider key shipped into the browser." Whether the callback works against Steel's remote CDP, where `Extensions.loadUnpacked` takes a path on the browser host, is **unverifiable (needs hands-on on a droplet)**. The e2e proof ran on local Chrome | detail |
| REA-5 | **Reasoning is mandatory:**<br>• `enabled:false` and `effort:"none"` → 400;<br>• default effort = max;<br>• low ≈1 reasoning token per call;<br>• high is no more accurate and ~25% costlier | **partially-confirmed** | Re-ran the probes live today. Re-fetched the models API `reasoning` block and HF README. Recomputed reasoning tokens and cost from raw | • Today `enabled:false` and `effort:"none"` → HTTP 400 "Reasoning is mandatory for this endpoint and cannot be disabled."<br>• Default (no param) on the 864-token act: 85 reasoning tokens. Explicit `max`: 87. `low`: 0.<br>• Models API 2026-10-10: `{"mandatory":true,"supported_efforts":["max","high","low"],"default_effort":"max"}`.<br>• HF README l.45: "defaults to `max` if not passed".<br>• `effort:"medium"` was accepted and gave 0 reasoning tokens (n=1, Together), so it does not silently become max via OpenRouter.<br>• Raw Stagehand calls: **low mean 0.1 reasoning tokens (median 0); high mean 12.0** (the dossier says ~1 and ~15).<br>• Cost: high is +23% (main) and +31% (rerun) on non-runaway calls. But in `main` high was **cheaper and faster** overall (measured $0.00060 vs $0.00076; p50 1.58 vs 1.88 s) and scored 27/27 vs 24/27.<br>• Pooled 51/52 vs 67/72: Fisher p=0.40. Junk args and the false null appeared only at low | The cost case for low is real but small. The accuracy case is a tie, with the point estimate favouring high. Keep low, but treat effort as a tunable. Re-bench high per provider if the act defect rate matters more than about $0.0001/act | detail |
| REA-6 | **Browser-Use 0.13.11:**<br>• sends one strict json_schema `agent_output` per step, no tools;<br>• `ChatOpenAI` sends `max_completion_tokens` 4096 and `reasoning_effort` only for `reasoning_models`, drops temperature and frequency_penalty, raises on `length`;<br>• `ChatOpenRouter` has `extra_body` and no cap;<br>• `ChatOpenAI` cannot send provider prefs | **confirmed** | Author used source plus a capture. I read the installed package source and the captured HTTP body independently | • `llm/openai/chat.py` l.64: `max_completion_tokens=4096`. l.189-192: reasoning_effort only if `is_reasoning_model`, pops temperature and frequency_penalty. l.224-229: `{'name':'agent_output','strict':True,...}`. l.277-283: `ModelOutputTruncatedError` on `length`. No `extra_body`, no `tools=`.<br>• `llm/openrouter/chat.py` l.52: `extra_body`. No `max_tokens`.<br>• `raw/bu_capture1/bu_request_01.json` keys: `messages, model, max_completion_tokens(4096), reasoning_effort(low), response_format`. No `tools`.<br>• browser-box `4c837a3:agents/browseruse/runner.py` l.48-49 and commit `f696b13` ("~40 s and up to 6k completion tokens a step") match | — | none |
| REA-7 | **Structured outputs on OpenRouter:**<br>• 26/33 GLM endpoints support SO;<br>• OpenRouter drops non-SO endpoints from json_schema requests even without `require_parameters`;<br>• "JSON validity is solved by strict json_schema plus the shim" | **partially-confirmed** (refuted part: "JSON validity is solved by strict json_schema") | Author made one probe with `order`. I repeated it, then varied the request shape (`only`, `ignore`, `zdr`) and ran a 22-provider pinned sweep with `require_parameters:true`, validating each output | • 33 endpoints / 26 SO reproduced today. Only **22 distinct providers** serve SO, not 29.<br>• With `order:["z-ai"],allow_fallbacks:false`: 404 with or without `require_parameters` (reproduced).<br>• **With `only:["z-ai"]` and no `require_parameters`: HTTP 200 from Z.AI with YAML-like, non-JSON content.** The schema was silently ignored.<br>• Docs (provider-selection l.1112, fetched 2026-10-10): `response_format` is only a "soft preference … If none of a model's providers support the parameter, the request is still routed … and the parameter is ignored". It does not protect a narrowed candidate set.<br>• **Even with `require_parameters:true`**, Phala (lists `structured_outputs`, is ZDR) returned non-JSON or fenced, wrong-shape output **4/4** (2 `zdr:true` probes, 1 `data_collection:"deny"`-only probe, and the sweep).<br>• Sweep: 15/20 served providers valid and correct.<br>• **Schema-invalid** under strict + `require_parameters`: 2/20 (Phala not-JSON; Friendli `"[0-218]"`, which breaks the pattern). This is the real refutation.<br>• **Schema-valid but wrong**: 3/20 (Sail Research empty `arguments`; Morph and Venice false `null`). These are n=1 each and GLM@low also returned a false `null` on Together today, so they are not attributable to the provider (see missed issue 5).<br>• DeepInfra and BaseTen returned 429 | Always send `require_parameters:true`, which the `ChatOpenAI` BU path cannot send. Correction (refuted part first): JSON validity is **not** solved by strict json_schema, because enforcement is provider-dependent. Validate every response against the schema (including `pattern`) and retry on failure. Pin an **allowlist** of providers that pass a per-provider bench (`provider.only` + `require_parameters`), and exclude Phala. "Strict json_schema" is a provider-dependent hint, not a guarantee (structured-outputs doc l.133 says so) | **design-changing** |
| REA-8 | **Vision.** GLM is best of the open models: the only one with true pixel coordinates 3/3, and ratings 3/3 | **partially-confirmed** | Re-checked every `raw/vision.jsonl` coordinate against `vision_truth.json` bbox myself | • GLM clicks (1137,789), (1135,790), (1136,790), all inside x 1040-1235, y 773-807. Ratings 3/3.<br>• MiMo 2/3 (one 0-1000-normalised miss). Qwen 0/3. DeepSeek (1138,770): 3 px above the box. Gemma wrong.<br>• **Sample:** one 1280x1024 screenshot and one target, repeated 3x. All 3 GLM click calls served by Modal, all 3 rating calls by Friendli | True as measured, but n=1 distinct image per subtask, one provider each. "Best vision" is an n=1 observation, not a ranking | detail |
| REA-9 | **Live Browser-Use, multi-step:**<br>• GLM: 6/6, median 4 steps, 5.7 s LLM, $0.0024/task;<br>• DeepSeek: 6/6, 8.8 s, $0.0035 | **confirmed** | Re-tallied every `raw/bu_live/*/bu_calls.jsonl` and `bu_summary.json` | • GLM: 18 LLM calls, all `stop`, $0.01443 total → $0.0024/task. Median LLM 5.65 s. 4 "steps" per run, but only 3 LLM calls (step 1 is `directly_open_url`). Live step p50 2.1 s.<br>• Providers: Friendli, Parasail, Together, Fireworks, BaseTen, InferenceNet, Inceptron.<br>• Ran on **local headless Chrome on the Mac**, a method BRIEF.md now bans | Thin evidence: 2 trivial tasks. Re-run on a droplet against Steel before relying on it | detail |
| REA-10 | **Runner-up: DeepSeek V4.1 Flash @off:**<br>• fastest p50 (1.09 s Stagehand, 0.49 s tool step);<br>• 26/27;<br>• MIT;<br>• 23 SO endpoints;<br>• ~1.1x GLM's uncached cost | **partially-confirmed** | Re-scored raw. Compared all configs' latencies. HF API license re-fetched | • **Nemotron was faster** (0.95 s bench, 0.38 s tool), so "fastest" holds only among models fit to act.<br>• 1.09 s is the p50 over all 27 calls incl. extract and BU. The Stagehand-only p50 is 0.99 s.<br>• 26/27 depends on lenient extract scoring: run 2 returned truncated link titles ("A Light in the ..."). Under a strict full-title rule it is 25/27. GLM is unaffected.<br>• HF license MIT (2026-10-10). SO endpoints 23/31 (recorded) and 23/32 (today).<br>• Uncached 0.00098/0.00091 = 1.08x | Drop "fastest". Note the extract scoring. The role (cross-family retry) still stands | detail |
| REA-11 | **Qwen 3.8 Flash is fragile:** Alibaba only, no `tool_choice:required`, 0-1000 coords, p90 8.9 s, custom license.<br>**Nemotron** fabricates clicks (2/3).<br>**Mistral Small** is unmeasurable (20/27 calls hit 429) | **confirmed** | Endpoints re-fetched. Raw rows re-read | • Qwen: today 2 endpoints, 1 provider (Alibaba). Endpoint `supports_tool_choice.required=false`. `tools.jsonl` 3x 404, then 3/3 with auto. Vision 0-1000 coords. p90 8.88 s. HF license tag `other`.<br>• Nemotron `sh_act_negative` 1/3 correct (2 returned an element for "Log out").<br>• Mistral 20/27 status 429 "temporarily rate-limited upstream".<br>• Note: Qwen's 27/27 also relies on lenient extract scoring (2 truncated-title runs → 25/27 strict) | — | none |
| REA-12 | **Cheap repair model: gpt-oss-120b @low.** $0.037/$0.17 per M, Apache-2.0, act/observe 18/18; extract lists truncated in 2/6 | **confirmed** | Live models API price. HF license. Raw re-score | • Price $0.037/$0.17 unchanged on 2026-10-10. HF `license:apache-2.0`.<br>• Re-score: act+obs 18/18. Extract 4/6 (books r2: 2 items returned; quotes: 1 run short) | — | none |
| REA-13 | **Action cache.** "Stagehand's own action cache, which skips the LLM on a repeated act, is where cost savings come from" | **refuted** | Not checked by the author. I read the cache implementation at `1fc8849` and the npm 4.2.0 bundle | • `packages/extension/services/cacheService.ts` header: "Server-side caching … via the Stagehand API's stateless cache routes".<br>• `buildCacheContext` (l.62) returns `undefined` unless `initParams.apiKey && browser.sessionId`: "the stateless routes authenticate with the Browserbase API key and resolve the project from the session id".<br>• npm `dist/index.mjs`: "Server-side caching of act/observe/extract results … **Requires a Browserbase apiKey and browser sessionId**."<br>• `sdk-python/examples/caching.py:28`: "Server-side caching requires a Browserbase browser session." | On Steel (the main infra) Stagehand 4.2.0 has **no** act/observe/extract cache, so every act pays the LLM. The fleet must build its own cache. Store observe results and replay them deterministically: `StagehandActParamsSchema.instruction` accepts an `Action`. Key the cache by URL plus a DOM hash, and invalidate it on failure. Cost projections must not assume Stagehand cache hits off Browserbase | **design-changing** |
| REA-14 | **Price weighting.** "OpenRouter's default routing weights providers by inverse price squared, so effective cost is often below list" | **partially-confirmed** (refuted part: "effective cost often below list") | Docs re-fetched. Tallied the serving providers in raw | • Docs (provider-selection l.83, 2026-10-10): "select one weighted by inverse square of the price". Confirmed official-docs.<br>• **But** 150/150 GLM bench calls were served by $0.15/M endpoints (Friendli 55, Together 33, Parasail 28, Modal 27, Venice 7).<br>• Only 3/18 live BU calls went to cheaper endpoints (InferenceNet $0.07, Inceptron $0.096).<br>• 13 SO-capable endpoints list below $0.15 today ($0.044-0.12), yet were rarely used | Correction (refuted part first): effective cost is **not** below list in practice. Project costs at **list** ($0.15/$0.50). Any saving must come from an explicit `provider.sort:"price"` or an allowlist, which REA-7 shows must be quality-gated | detail |

## Unsourced or unsupported numbers in the dossier

- **Per-call-type `max_tokens` caps** (act/observe 1024, extract "about 30 tokens per expected item + 512", Metadata 256).
  - Called "from observed completion sizes". The observed sizes support them loosely: GLM act/observe 12-110 completion tokens (non-runaway), 20-item books extract 380-584.
  - The formula itself is a heuristic and was never run.
- **"a 1k cap should bring that to a few seconds".** Not measured; the dossier admits it.
- **"Stagehand trees are 1-10k tokens".** Only 0.73k-6.35k was measured. The 10k upper bound is unsourced.
- **"Expect about $0.001-0.0014 and 1.5-3 s per step"** (Browser-Use).
  - $0.0014 uncached and a 1.8 s replay p50 are measured.
  - The 1.5-3 s band and $0.001 lower bound are not stated anywhere in the raw data. The live step p50 was 2.1 s.
- **"High … adds about 0.1-0.4 s at p50"** (RESULTS). In `main`, high was 0.3 s **faster** (1.58 vs 1.88). Only the rerun shows +0.41 s.
- **"low ≈1 reasoning token per Stagehand call; high ≈15".** Raw gives a mean of 0.1 and 12.0.
- **Max completion "128k-944k" (Q1) vs "131k-944k" (§4 and RESULTS).** The endpoint data minimum is 128,000 (streamlake), so the two sections disagree.
- **DeepSeek "endpoint prices vary 20x ($0.016-0.45/M)".** The quoted range is 28x. Today it is $0.0001-0.6.
- **"`openai/gpt-6-luna` @none, at the same list price as GLM".** The list price is $0.10/$0.50, not $0.15/$0.50 (both the 2026-10-09 snapshot and today).
- **"Highest agentic index among sub-$0.50 open models listed"** (AA 50.9).
  - `z-ai/glm-5.3` (open weights, HF `zai-org/GLM-5.3`) shows agentic 53.1 at a listed $0.039 input.
  - That price is one wafer/us endpoint. Most endpoints are $1.40/$4.40 and output is $4.80, so the claim holds only if the cap covers output price.
- **"35-78% of prompt tokens served from caches".** `summary_costs.md` gives 2-78% (gpt-oss 2%, nemotron 11%). 35-78% is GLM, DeepSeek and Qwen only.
- **"Spend … verified two ways: the sum of `usage.cost` equals the key's usage delta".**
  - The sum of all raw `usage.cost` is $0.24513; the key delta is $0.24624. That is near-equal ($0.0011 gap), not equal.
  - The key is shared: usage is $445 lifetime and other callers spent today. So "no other caller shared the key" is not provable from the counter.
- **Prices that drifted overnight** (quoted correctly for 2026-10-09; quote both dates):
  - GLM minimum endpoint input $0.032 → $0.04;
  - `~z-ai/glm-flash-latest` $0.032/$0.72 → $0.04/$0.50;
  - Nemotron $0.047/$0.134 → $0.07/$0.20;
  - Kimi K2.6 input $0.465 → $0.441.

Sourced and verified, for the record:

- $0.00012 Metadata call;
- 24.6 KB system prompt and 14 KB schema (24,622 and 14,369 chars in `bu_request_01.json`);
- ~$0.15 per full bench run (`main.jsonl` sums to $0.140);
- Wilson CI 1-7%;
- 33 endpoints, 29 providers, quantizations 11/9/3/10.

## Missed issues

1. **No Stagehand cache off Browserbase** (REA-13, design-changing).
   - Stagehand 4.2.0's act/observe/extract cache is server-side and needs a Browserbase API key and session id.
   - The fleet's main infra (self-hosted Steel) gets none. The fleet must build its own observe→`Action` cache and replay it via `act(Action)`.
   - Cost models that lean on the Stagehand cache are wrong for Steel profiles.
2. **Structured-output enforcement varies by provider, even with `require_parameters`** (REA-7, design-changing).
   - Hands-on today:
     - Phala returned non-JSON or a wrong shape 4/4;
     - Friendli broke the `elementId` pattern;
     - with `only` and no `require_parameters`, Z.AI returned YAML with HTTP 200.
   - The wrong-but-valid answers (Sail Research, Morph, Venice) are a different failure and are filed under item 5.
   - The shim must:
     - validate every response with the exact schema (including `pattern`);
     - retry on another provider;
     - run on a **bench-gated provider allowlist**.
   - Phala is ZDR-listed, so a privacy filter (`zdr:true`) can route into it.
3. **Provider and task are confounded throughout the bench.**
   - Sticky routing sent each frozen prompt to one provider, so every "GLM" number is really "GLM on provider X for task Y".
   - The dossier's "quality per provider was not separated" understates this. Low-vs-high also compares the same provider each time.
   - Needed: a per-provider bench (`provider.only`) on the 6k-page acts before choosing the allowlist.
4. **The shim's "lowercase" step would corrupt typed content** (design-changing for posting and messaging).
   - §3 says "Keep `arguments[:1]`. Lowercase. For click, keep only `""`/`left`/`right`/`middle`". §4 says "keep [:1], lowercase, drop bad click buttons".
   - Applied literally to `fill`/`type` this lowercases every post, message and reply. Applied to `press` it breaks key names (`Enter`).
   - Lowercase only the `click` button argument.
5. **False nulls at low effort are not only DeepSeek's failure mode.**
   - GLM had a false `null` on the dropdown in the bench.
   - Today GLM@low returned `action:null` on the trivial "type 42" act on Together, Morph and Venice (3 of ~24 non-Phala low-effort calls).
   - The dossier advises "don't retry a `null` blindly". At about $0.00015 per small act, one retry on another provider before accepting a `null` is cheap insurance.
6. **Fleet-scale throughput and rate limits are not assessed.**
   - The sweep hit 429s from DeepInfra and BaseTen on single calls today, and Mistral was 429 on 20/27 calls.
   - Nothing measures GLM concurrency for 100-1,000 agents, or per-provider limits once an allowlist narrows the pool.
7. **Direct `ModelConfig` sends LLM traffic from inside the browser.** The Stagehand extension service worker makes the provider HTTP calls.
   - On a profile with a sticky residential proxy, that traffic would plausibly ride the proxy: billed bandwidth, extra latency, and prompts crossing the proxy path.
   - This is an inference from the architecture (extension fetch uses the browser network stack), not measured.
   - It is a second reason, besides key locality, to use the client callback.
8. **Browserbase Model Gateway is unmentioned** (`packages/extension/llm/gatewayClient.ts`, `sdk-python/examples/model_gateway.py`).
   - On the Browserbase backup path with no model set, Stagehand uses Browserbase's gateway with model `"auto"`.
   - The fleet must always pass its callback, or it silently loses model control and cost attribution.
9. **The spike used a method BRIEF.md bans.** RESULTS.md: "Local Chrome for Testing (playwright chromium-1243) ran headless".
   - Affected: `capture_stagehand.py`, `capture_browseruse.py`, `run_bu_live.sh` and `screenshot.mjs` all launched a browser on the Mac.
   - The data is usable, but the Stagehand e2e proof, the live BU runs and all latencies are from macOS and local Chrome.
   - Whether the callback works over Steel's remote CDP (extension loading via `Extensions.loadUnpacked` path on the browser host) is **unverifiable (needs hands-on on a droplet)**.
10. **Latency is cache-flattered** (REA-2): uncached Stagehand p50 is about 1.7 s, not 1.2 s.
11. **Act-level defect rate is understated** (REA-3): about 7-8% of click acts on the 6k-token page, not 3% of calls.
12. **ZDR pool.**
    - The dossier says how many of the 29 providers remain under ZDR "was not enumerated". `GET /api/v1/endpoints/zdr` (public, fetched 2026-10-10) answers it.
    - 29 GLM 5.3 Flash endpoints are ZDR-listed, 25 of them with SO.
    - **Friendli**, the bench's main provider, is **not** ZDR-listed.
    - Phala is ZDR-listed, but its schema enforcement failed every time.
    - So a ZDR configuration changes which providers serve. The bench numbers do not transfer to it without re-testing.
