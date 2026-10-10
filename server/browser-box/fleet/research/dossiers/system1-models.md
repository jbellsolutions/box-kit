> **Read with its verification report.** [verification/system1-models.md](../verification/system1-models.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: System 1 decision models (Jev, Clef, OpenAI Decisions, Perplexity Decider)

Research agent: system1-models. Date: 2026-10-09. Spike: [`../spikes/system1-models/`](../spikes/system1-models/RESULTS.md).
Provenance tags: `hands-on` (run today), `source-code` (pinned commit), `official-docs`,
`vendor-claim`, `third-party`, `unverified`. Spend: **≈ $0.000135** (TypeSafe $0.000115 + OpenRouter $0.00002).

---

## 1. Verdict

- **All four exist and are live**, and all share one API family. Jev's `POST /v1/systemone` contract (`state` plus named `noul`/`choice`/`score` questions, returning probabilities) is now an industry pattern.
  - **Clef** (Cloudflare, 2026-10-01): open weights. `official-docs`.
  - **Perplexity Decider** v1 (2026-10-01) and v1.1 (2026-10-06/07): open weights. `official-docs`.
  - **OpenAI Decisions**: public beta since 2026-10-06, closed weights. Same idea, different JSON shape. `official-docs`.
  - **None of them generates text.** Every vendor says so plainly.
- **OpenRouter lists all four behind one key; only one of the four was called through it today.**
  - `GET /api/v1/models?output_modalities=decisions` returns 19 entries. They include Jev, Clef, Clef-flash, Clef-omni, Decider v1.1 and `openai/gpt-6-luna-decisions`. `hands-on`.
  - Two endpoints: `POST /api/v1/systemone` (Jev/TypeSafe-SDK shape) and `POST /api/alpha/decisions` (same shape, plus `provider` routing preferences). `official-docs`.
  - **Verified:** a Jev-shaped body, unchanged, got a correct answer from Perplexity Decider through OpenRouter in 271 ms. `hands-on`.
  - **Not tested through OpenRouter:** Jev (called directly at TypeSafe), Clef, and OpenAI. In particular, whether OpenRouter translates the System One shape for OpenAI's Decisions API.
  - OpenRouter serves `cloudflare/clef` and `clef-flash` from both Cloudflare (65,536 context) and PrimeIntellect (16,384 context). A call may not reach Cloudflare unless `provider` is pinned.
- **Jev works and is fast. My 3 calls today took 139–329 ms; the README's n=20 median is ~300 ms. But nobody has measured element-grounding accuracy at scale.**
  - Every published benchmark (the Decision Index, Clef's table, the Perplexity panel) covers NLU, classification and tool calling. None of them asks "which element on a web page".
  - The only browser evidence is ours: README act bench 3/3 on 4 jobs, **0/3 on "first search result"** (a real Jev miss), plus today's easy n=3 test. `hands-on` + `source-code`.
- **Inputs differ in ways that matter for a browser.** Jev is **text-only**: you must serialize the DOM or a11y tree. Clef (≤4 images), Decider (OpenAI-style `image_url` parts inside `state`) and OpenAI Decisions (`input_image`) **accept screenshots**. Perplexity publishes a full screenshot-plus-numbered-badges browser-agent recipe. `official-docs`.
- **Rate limits are per account or org (Jev's page does not say which) and small next to 1,000 agents. The fleet needs a central limiter, request packing (fan-out) and multi-provider spillover:**

  | Provider | Limit | Provenance |
  |---|---|---|
  | Jev | 80 rps and 100K tok/s, "dynamic". The 2026-09-17 snapshot said 1,200 rpm. | `official-docs` |
  | Perplexity | **10 rps** per org on every plan | `official-docs` |
  | Clef on Workers AI | Default for its task type is 300 rpm per model. Inferred, not stated on the Clef page. | `official-docs` (inferred) |
  | OpenAI Decisions | unconfirmed | |

- **The 90%+ System 1 target is a hypothesis.** It is plausible only if "System 1" means *no generative call*: deterministic code, replay and decider together. Of that, the decision model itself plausibly owns **~30–60% of browser actions**, depending on workflow. My estimates: repetitive posting is the best case and can plausibly reach ≥90% non-generative actions; lead-gen research cannot. Generated text (posts, replies, DMs) always needs the reasoning model. The figures in §2 Q4 are estimates, and the measurement plan is there too.
- **Stagehand v4's act/observe cache only works on Browserbase.** It lives on Browserbase's servers; `enableCaching`/`cacheDir` were removed in v4. So on self-hosted Steel, the "Stagehand = cached, deterministic" premise does not hold out of the box. The fleet must build its own replay cache, and the decider is the natural self-heal tier for it. `source-code` + `official-docs` (stagehand @1fc8849).
- **Where a decider plugs in:**
  - **Stagehand:** `page.snapshot()` returns `formattedTree` and `xpathMap`. A decider choice over those can be passed to `act(Action)`, which runs `takeDeterministicAction` with no LLM.
  - **Browser-Use:** `get_browser_state_summary().dom_state.selector_map`. A decider choice can be executed with `Tools.act` / `registry.execute_action('click', {'index': n})`, with no LLM.
  - **Both frameworks have a model hook, but it expects generative structured output.**
    - Stagehand's act service takes `clientLLMGenerate` and must return `{elementId, method, arguments, twoStep}`.
    - Browser-Use accepts any `BaseChatModel` and must return a full `AgentOutput`.
    - A decider behind either hook would have to fake that contract. That is fragile and not recommended.
    - The clean path is your own loop, with the framework as the executor. `source-code`.
- **A decider is not a safety control.** Page text is untrusted: commenters on a social page can write anything. TypeSafe's jaggedness page says adversarial content moves answers. Perplexity's cookbook says its risk score "is not a safeguard". Irreversible actions (post, send, DM, delete, pay) must be gated by deterministic policy, not by a probability. `official-docs`.

---

## 2. Answers

### Q1. Does each model exist? API, question types, inputs, outputs, latency, price, limits, weights, context, accuracy

#### Side-by-side (details and sources below)

| | **Jev** (TypeSafe) | **Clef / Clef-flash / Clef-omni** (Cloudflare) | **OpenAI Decisions** | **Perplexity Decider** |
|---|---|---|---|---|
| Exists | Yes. `jev-1.13.0`; aliases `jev-latest` and `jev-preview` both point to it. `official-docs`, `hands-on` | Yes. `@cf/cloudflare/clef` (27B), `clef-flash` (9B), `clef-omni` (30B MoE, 3B active, appeared 2026-10-09). `official-docs` | Yes. **Public beta**; `gpt-6-luna` is the only model. `official-docs` | Yes. `pplx-decider-v1-27b`, `pplx-decider-v1.1-27b`. `official-docs`, `hands-on` (v1.1 via OpenRouter) |
| Native endpoint | `POST https://api.typesafe.ai/v1/systemone` | `POST https://api.cloudflare.com/client/v4/accounts/{id}/ai/run/@cf/cloudflare/clef` or `env.AI.run()`; also AI Gateway | `POST https://api.openai.com/v1/decisions` | `POST https://api.perplexity.ai/v1/decisions` |
| Via OpenRouter | `typesafe/jev-1.13`, `~typesafe/jev-latest` | `cloudflare/clef`, `/clef-flash`, `/clef-omni` | `openai/gpt-6-luna-decisions` | `perplexity/pplx-decider-v1.1-27b` |
| Request shape | `{model, state, questions:{id:{type,instructions,criteria}}}` | Same as Jev, plus `model:"clef"\|"clef-flash"`, plus an `images[]` extension. Omni adds audio and video. | **Different:** `{model, input, questions:[{type, name, instructions, choices[]/levels[]}]}`; `predicate` instead of `noul` | Same as Jev; images go as `image_url` parts inside a `state` array |
| Question types | noul, choice, score | noul, choice, score | predicate, choice, score | noul, choice, score |
| Response | `{model, answers:{id:{type, choice, confidence, probabilities}}, usage}` | Same as Jev | `answers:[{type, name, choice, probabilities:[{value, probability}], confidence}]`, plus a **`refusal`** answer type | Same as Jev, full-precision floats |
| Inputs | **Text only**: string, JSON object, or array of text | Text/JSON plus ≤4 images (PNG/JPEG/WebP, base64 only, ≤1,024 tokens each). Omni also takes audio and video. | Text plus images (base64 data URLs only) | Text/JSON plus images (base64 only, ≤2,048 32×32 tiles per image) |
| Output | Choice: chosen option plus a per-option probability map plus confidence. Noul: a probability. Score: expected level plus distribution. | same | same (as arrays) | same |
| Limits per request | Context: 64k for state plus all questions; 32k for state plus the longest question. ≤255 choice options. | ≤64 questions; choice 2–255 options; score 2–10 levels; 13 MiB body | unconfirmed | 1–128 questions; ≤255 options; ≤10 levels; <262,144 input tokens; 32 MiB body |
| Price (input; output free for all) | $0.042/M | Clef $0.24/M; flash $0.038/M; omni $0.15/M | $0.10/M, plus regional and long-context multipliers | $0.02/M (Perplexity docs and OpenRouter) |
| Rate limits | 100K tok/s and 80 rps, "dynamic" | Unconfirmed for Clef. The Workers AI default for its task type is 300 rpm per model per account (inferred). | unconfirmed | 10 rps per org on every plan, plus a token limit |
| Latency | Measured: 139–329 ms (n=3, today); README ~300 ms median (n=20). Cloudflare's measurement: 524 ms. | Vendor: Clef 209 ms median; flash 38.8 ms median, 122 ms p95 | Vendor: "up to 10x faster than Responses"; no absolute number | Measured: 271 ms (n=1 via OpenRouter). Docs: <2 s for small inputs, 23 s near the limit. |
| Open weights / self-host | **No.** API only. Enterprise ZDR. | **Yes**, Apache-2.0 on HF. SGLang image serves `/v1/systemone`; tested on an H200. | **No.** ZDR/HIPAA for eligible customers. | **Yes**, Apache-2.0 on HF. Custom noncausal inference code; ~49 GiB of GPU memory. |
| Accuracy evidence | Vendor evals; Decision Index 57.9 (from Perplexity's table) | Vendor table: "leads 7 of 10" benchmarks; Typesafe workflow evals 3/4 vs Jev | **None published** | Vendor: Decision Index 61.56 (v1.1) vs Jev 57.9 |

#### Jev (TypeSafe)

- **Endpoint and shape:**
  - Endpoint: `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer`. `GET /v1/models` lists aliases. `official-docs` (docs.typesafe.ai/api, fetched 2026-10-09), `hands-on`.
  - **The Gemini doc's `api.typesafe.com/v1/jev/decide` does not exist.**
  - `instructions` and `criteria` may be a string, an object or an array. Using an object for `instructions` is new since the 2026-09-17 snapshot. `official-docs`.
- **Measured response shape** (`hands-on`, raw in `spikes/system1-models/raw/ts1.json`):
  `{"model":"jev-1.13.0","answers":{"target":{"type":"choice","choice":"e7","confidence":1.0,"probabilities":{"e1":0.0,...,"e7":1.0,...,"none":0.0}},"login_wall":{"type":"noul","noul":0.04},...},"usage":{"input_tokens":1032,"output_tokens":208}}`.
  - Probabilities are **rounded to 2 decimals**.
  - TypeSafe returns an `x-typesafe-request-id` header. It was seen on a full-header capture of `GET /v1/models`; the allowlist filter in the first spike run had dropped it.
  - Whether `POST /v1/systemone` sends rate-limit headers is unconfirmed. `GET /v1/models` sends none.
  - `hands-on`.
- **Choice options:** "up to 255 options" (`official-docs`, primitives/choice). jev-automation caps elements at 180 (`MAX_ELEMENTS`, `core/elements.ts` @edcbbae, `source-code`).
- **Price:** $0.042/M input tokens; output tokens are free.
- **Rate limits:**
  - Today: 100K tokens per second and 80 requests per second, marked "adjusting dynamically" and able to change without notice.
  - The 2026-09-17 snapshot said 250,000 tok/s and 1,200 rpm.
  - `official-docs`, both versions.
- **Context:** 64k tokens for `state` plus all questions; 32k for `state` plus the longest question. OpenRouter's Jev hub says "32,000 tokens". The two sources disagree; TypeSafe's own page wins. `official-docs`.
- **Inputs:** "Text only. String, JSON object, or array of text values." `official-docs` (models page, 2026-10-09).
- **Weights:** "Jev is not fine-tuned or LoRA-adapted with customer data… the same weights serve every account." API-only; ZDR for enterprise. `official-docs`.
- **Accuracy:** TypeSafe publishes failure modes ("jaggedness"):
  - Literal reading.
  - Numbers and counting.
  - Dates.
  - Indirection.
  - **Large state with irrelevant detail ("context rot")**.
  - **Adversarial content**.
  - Generation.

  There is no browser-grounding benchmark. `official-docs`.
- **Latency:**
  - Vendor: "Most queries complete in about 100 ms." `vendor-claim`.
  - Measured today: 329, 264 and 139 ms. `hands-on`.
  - README: 209–424 ms, median ~300, n=20, one 8.8 s outlier. `source-code`/measured.
  - Cloudflare: 524 ms median. `vendor-claim` from a competitor.
- **SDKs:**
  - PyPI `typesafe-sdk` 0.7.4. 0.7.0 switched msgspec to pydantic (breaking). an older local tool pins 0.6.0.
  - npm `@typesafe-ai/sdk` 0.6.0.
  - Both SDKs accept `TYPESAFE_BASE_URL`, so they can be pointed at OpenRouter.
  - `official-docs`.

#### Clef (Cloudflare)

- **Exists.**
  - Launched 2026-10-01 as `@cf/cloudflare/clef` (27B, fine-tuned from Qwen3.8-27B) and `@cf/cloudflare/clef-flash` (9B, fine-tuned from Qwen3.5-9B).
  - `clef-omni` (Qwen3-Omni-30B-A3B) appeared on Hugging Face and OpenRouter on 2026-10-09.
  - Sources: Cloudflare changelog 2026-10-01; model pages; Hugging Face API. `official-docs`.
- **API:**
  - Workers AI binding `env.AI.run("@cf/cloudflare/clef", {model:"clef", state, questions})`, or REST `POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef` with a Bearer token.
  - Also available through AI Gateway.
  - "Clef follows the System One API… switch an existing Jev integration to Clef by changing the endpoint and model." `official-docs`.
- **Limits:**
  - 1–64 questions; ids ≤100 characters; choice 2–255 options; score 2–10 levels.
  - `images[]` holds ≤4 PNG/JPEG/WebP base64 images (no remote URLs), each ≤4 MiB and 16 MP, 8 MiB total; request body ≤13 MiB.
  - Each image costs ≤1,024 tokens: 32×32 patches, resized to 65k px–1 MP.
  - "Long text state is truncated to fit." That is silent truncation, not an error.
  - `official-docs` (schema-input.json).
- **Context:** the Clef page says 65,536.
  - **Clef-flash: three different figures.** The model page says 24,576, the changelog says "64K", and OpenRouter's top provider says 16,384.
  - The Hugging Face `encode_record` default is 16,384 tokens.
  - Sources conflict; treat the smallest as safe.
- **Price:** Clef $0.24/M, flash $0.038/M, omni $0.15/M input. Output is free. `official-docs`.
- **Rate limits:** not stated on the model page.
  - The Workers AI limits page gives "Text Generation: 300 requests per minute, unless the model requires the Workers Paid plan".
  - The Clef page is categorized as "Text Generation" and does not say Paid is required, so 300 rpm per account per model is **inferred**, not confirmed.
- **Latency (vendor):** "43 benchmark runs". Clef median 209.3 ms (p95 238.6); flash median 38.8 ms (p95 122.4); Jev median 524.1 ms (p95 536). `vendor-claim`.
- **Weights:** Apache-2.0, ungated, on Hugging Face.
  - Repos: `Cloudflare/clef` @0b331204, `clef-flash` @8b2e5fd1, `clef-omni` @0db1cd26.
  - Custom `joint_schema_model.py` with a joint schema head over Qwen hidden states.
  - "Tested with torch 2.11 and transformers 5.10.2 on a single H200."
  - SGLang image `lmsysorg/sglang:dev-clef` serves `/v1/systemone`.
  - `official-docs`. Not run here.
- **Accuracy:** the model card has a Decision Index 0.2.1 table (internal run).
  - Clef or Clef-flash wins most rows, e.g. BFCL 98.5 / 98.8 vs Jev 95.8 and BANKING77 94.2 vs 79.7.
  - Jev wins GPQA, MMLU-Pro, BBH, When2Call and ANLI.
  - Typesafe workflow evals: Clef beats Jev on 3 of 4.
  - `vendor-claim`. No web-grounding benchmark.
- **This box:** no Cloudflare access has been exercised. Docs only.

#### OpenAI Decisions

- **Exists.** "The Decisions API is in public beta, and we expect to GA in the coming weeks. `gpt-6-luna` is the only model currently available." Announced on the community forum 2026-10-06. `official-docs` (developers.openai.com/api/docs/guides/decisions.md, fetched 2026-10-09).
- **Endpoint:** `POST https://api.openai.com/v1/decisions`. SDKs: Python ≥3.26.0, JS ≥7.30.0, Go ≥3.73.0, and others.
- **Shape (different from System One):**
  - `{"model":"gpt-6-luna","input": "<text>" | [{"role":"user","content":[{"type":"input_text",...},{"type":"input_image","image_url":"data:..."}]}], "questions":[{"type":"predicate"|"choice"|"score","name":"...","instructions":"...","choices":[{"value","description"}] | "levels":[{"label","description"}]}]}`.
  - Response: `answers` is an **array** of `{type, name, probability}` (predicate), `{type, name, choice, probabilities:[{value, probability}], confidence}` (choice), or `{type, name, score, probabilities:[{value, label, probability}], confidence}` (score).
  - There is also a **`refusal`** answer type.
  - Images must be inline base64; URLs and `file_id` are not supported.
  - `official-docs`.
- **Price:** $0.10 per 1M input tokens. No output, cache-read or cache-write charges. "Regional processing premiums and long-context input pricing multipliers apply." `official-docs`.
- **Latency:** "about 10x faster than the Responses API". **No absolute number.** `vendor-claim`.
- **Rate limits, per-request limits, context:** **unconfirmed.** The guide does not state them.
  - OpenRouter lists `openai/gpt-6-luna-decisions` with 1,050,000 context, i.e. the base model's. `third-party` (aggregator).
- **Weights:** closed. ZDR/HIPAA for eligible customers; US/EU data residency. `official-docs`.
- **Accuracy:** none published. `unconfirmed`.
- **This box:** no OpenAI Decisions access has been exercised. Docs only.

#### Perplexity Decider

- **Exists.**
  - `pplx-decider-v1-27b`: 2026-10-01. HF @b01a5cba.
  - `pplx-decider-v1.1-27b`: HF @6195aa55; on OpenRouter as `perplexity/pplx-decider-v1.1-27b-20261006`.
  - Both are Apache-2.0, fine-tuned from Qwen3.8-27B.
  - `official-docs` + `hands-on`.
- **Endpoint:** `POST https://api.perplexity.ai/v1/decisions` with Bearer auth.
  - Watch the edge cases: an `x-api-key` header gets 401, and a trailing slash gets 404.
  - Responses carry an `x-request-id` header.
  - Same `state`/`questions` shape as Jev.
  - `official-docs`.
- **Limits:**
  - 1–128 questions; 1–255 options; ≤10 levels.
  - <262,144 input tokens; 32 MiB body.
  - Images: ≤2,048 tiles of 32×32 per image. **An oversized image does not return 400: the request hangs ~1 min and then returns 504.**
  - 10 rps per org; 429 responses carry `Retry-After`.
  - `official-docs`.
- **Price:** $0.02/M input; output free; no per-request fee. `official-docs`, `hands-on` (`usage.cost` 2e-05 for 1,000 tokens).
- **Latency:**
  - Docs: <2 s for a few hundred tokens; 5 s at ~90k tokens; 23 s near the limit.
  - Browser cookbook: ~1 s on the first request, then 0.25–0.5 s for ~7,300-token screenshot steps.
  - Today: 271 ms via OpenRouter (n=1).
- **Self-host:**
  - "~49 GiB of weights plus working memory" on a CUDA GPU.
  - It **must use the bundled noncausal-attention inference code** ("default causal inference does not reproduce this checkpoint's evaluated setup").
  - The readout head is `[255, 5120]`, so the 255-option cap is structural.
  - The self-host `prepare` limit is **8,192 tokens**, against 262k for the API.
  - The card says "private repository", but the Hugging Face API shows `gated:false` and anonymous file listing works. The card text is stale.
  - `official-docs` (HF card), not run.
- **Accuracy (vendor):** Decision Index overall 61.56 (v1.1) vs 56.4 (v1) vs Jev 57.9. Jev still leads the "Knowledge" category. `vendor-claim`.

#### Bonus finding: the broader "decision model" catalog

OpenRouter's `GET /api/v1/models?output_modalities=all` lists more decision models (`output_modalities:["decisions"]`):
- `microsoft/microsoft-decision-1`
- `liquid/d1`
- `upstage/solar-decide`, `upstage/solar-decide-flash`
- `inception/mercury-decide` (it has a `:free` variant)
- `nace-ai/drex-v1.5`
- `togethercomputer/tev1-4b-experimental`
- `jaredpalmer/kev-4b` (open, a LoRA on a 4B base)
- `respan/span-01`

Most descriptions say "served over the same /v1/systemone contract". `third-party` (catalog listing), unverified. These are candidates for the provider pool later, not part of this scope.

### Q2. Jev specifically

- **What the box's code actually does.**
  - `gateway/gateway/jev.py` (browser-box @4c837a3) does **not** call TypeSafe. It calls the `agent-jev` container (jev-automation `server/http.ts`): `/api/command`, `/reply`, `/cancel`, `/read`.
  - The model call happens inside jev-automation's `core/decide.ts` @edcbbae: `TypeSafeClient.systemOne({state, questions}, {timeout: 8000})`. `source-code`.
- **The real question set** (decide.ts `buildQuestions`) is one speculative fan-out request:
  - `route` (choice: hermes / browser_now / computer / ...).
  - `intent` (choice over 11 browser intents).
  - `risky` (noul: hard to undo?).
  - `scroll_direction` (choice).
  - `submit_after_typing` (noul).
  - `target`: a choice over up to 180 elements plus `none`. Instructions are `{question, command}`; criteria are `describeElement` strings like `link "Pricing" → /pricing [off-screen]`.
  - `url_pick`.
- **Code-side thresholds:** intent 0.25, target 0.35 (below that → `needs_clarification` with the top 3 alternatives), risk 0.6 (→ `needs_confirmation`), submit 0.6.
- **Verification is a second request** (`core/verify.ts`):
  - Code decides the obvious cases first: URL change and similar.
  - The rest goes to Jev as `step_done` / stuck / `blocker`, a choice over `none, consent_dialog, login_wall, captcha, error_page, no_results, popup, permission_prompt, no_change`.
  - Its state carries diffs: `new_elements` ≤8 and `gone_elements` ≤5.
  - `source-code`.
- **Lessons already learned** (README, `source-code`/measured 2026-09-23):
  - Explicit-URL steps bypass Jev. Jev had picked a prominent link instead of the URL.
  - Typed text is copied verbatim by code. Jev once lowercased quoted text.
  - Unlabelled checkboxes needed de-duplication.
  - Opacity-0 custom checkboxes needed listing.
  - **Search "first result" 0/3**: Jev picked Wikipedia's red "create this page" link.
- **The README's measured act numbers**, from browser-box README "act vs task" and "Jev, and why it is inside":

  | Job | act success | median s |
  |---|---|---|
  | search | **0/3** | 3.8 |
  | form | 3/3 | 4.7 |
  | paginate | 3/3 | 2.2 |
  | cookie state | 3/3 | 0.5 |
  | SPA | 3/3 | 3.0 |

  - For comparison, `task` (Browser-Use + GLM 5.3 Flash) took 31–300 s.
  - Jev's decision alone took 209–424 ms; a whole click step took 1.2–2.5 s ("page load and settling dominate").
  - These numbers exclude the caller's own planning turns.
- **An older local tool** (its TypeSafe integration and pilot docs):
  - Production wiring is `typesafe-sdk==0.6.0` with `jev-1.13.0`.
  - It keeps a $5/month ledger that reserves $0.042 (1M tokens) per attempt.
  - Staging: 5 real calls, median 443 ms (378–701).
  - Shadow pilot: 16 calls, median 487 ms (max 775); option order never flipped a choice, but confidence moved up to 0.09.
  - Explicit stance: "agreement is not accuracy… no automatic promotion". `source-code`.
- **jev-agent-kit** @faeae16:
  - It is the TypeSafe skill plus a 111-page docs snapshot (retrieved 2026-09-17) plus the pilot reference implementation.
  - **The live docs have since changed:** rate limits, structured instructions, and a context/input table.
  - **Both `jev-automation` and `jev-agent-kit` are public on GitHub (`isPrivate:false`).** The brief calls them private; Justin should know.
- **Hands-on today** (see `spikes/system1-models/RESULTS.md`): 3 direct calls, all 200, all matched the expectations written before the calls.
  - **ts1**, home page, 3 questions fanned out: target `e7` at 1.00 over the near-distractor "GoodReads.com → /quotes" at 0.00; login_wall 0.04; blocker `none` at 0.91. 329 ms, which includes the TLS handshake.
  - **ts2**, `/login` page: login_wall **0.95**; blocker `login_wall` at 0.98. 264 ms.
  - **ts3**, ts1 with option order reversed: same picks; blocker confidence 0.87. 139 ms on a warm connection.
  - TypeSafe spend: 2,732 tokens = **$0.000115**.
  - These cases were easy; they show the wiring works, not accuracy.

### Q3. Perplexity Decider on OpenRouter; Clef / OpenAI keys

- **Is it on OpenRouter?** Yes, as `perplexity/pplx-decider-v1.1-27b`. `hands-on`.
  - It only appears with `?output_modalities=all` or `=decisions`; both were run, and `=decisions` returns 19 models. The default `/api/v1/models` list hides decision models.
  - v1 (`pplx-decider-v1-27b`) is not in the current catalog.
  - Endpoint metadata: provider `Perplexity`, context 262,144, $0.00000002 per prompt token.
- **One call** (`hands-on`): `POST https://openrouter.ai/api/v1/systemone` with the **exact ts1 body**, only `model` changed. 200 in **270.8 ms**.
  - Response: `{"model":"perplexity/pplx-decider-v1.1-27b-20261006","provider":"Perplexity","id":"gen-dec-…","answers":{…same keys, full-precision floats…},"usage":{"input_tokens":1000,"output_tokens":3,"cost":2e-05}}`.
  - Target `e7` at 0.9985; login_wall 0.0009; blocker `none` at 0.978. Spend **$0.00002**.
- **Clef and OpenAI access:** no Clef or OpenAI Decisions access has been exercised, so both are **docs only**.
  - OpenRouter lists both, so a ~$0.001 follow-up with the existing key would test them.

### Q4. Integration design: where a decider replaces a generative call

**Stagehand v4** (sdk-ts / extension @1fc8849, `source-code`):
- **`act("click the login button")`:**
  - Step 1: `page.captureSnapshot()`, an a11y tree with lines like `[frameIdx-nodeId] role: name` (`understudy/a11y/snapshot/treeFormatUtils.ts:12`).
  - Step 2: `getActionFromLLM` → `{elementId, method, arguments, twoStep}`. A **generative** structured-output call, possibly two (two-step).
  - Step 3: `takeDeterministicAction` (`extension/services/actService.ts:62-245`).
  - The model is pluggable (`ActServiceOptions.model` / `clientLLMGenerate`), but the hook expects a generative structured answer.
  - A decision model cannot natively return `method`, `arguments` or `twoStep`. Wrapping one to fake that contract is fragile, so it is not recommended.
- **What can be reused:**
  - `page.snapshot()` is public and returns `{formattedTree, xpathMap, urlMap}` (`protocol/schemas.ts:1164`).
  - `act(action: Action)` with `{selector, description, method?, arguments?}` skips inference entirely (`stagehand.ts:233`; actService "deterministic" path).
- **So the decider path is:** `snapshot()` → filter interactive nodes into ≤180 candidates → decider `choice` → `act({selector: <from xpathMap>, method: "click"|"fill"|..., arguments:[<code-supplied text>]})`. The exact selector string format for xpath is to be confirmed in the Stagehand spike.
- **`observe()` is an LLM call that returns `Action[]`.** It is the generative equivalent of what the decider does. Use it as an escalation step, not a primary step.
- **Cache:** v4 "caches `act()`, `observe()`, and `extract()` results on Browserbase's servers… `enableCaching`/`cacheDir` → no equivalent". `buildCacheContext` returns undefined without a Browserbase `apiKey` and `sessionId` (`services/cacheService.ts`; `docs/v4/migrations/v3.mdx:509,601`). **No cache on self-hosted Steel.**

**Browser-Use 0.13.11** (@c75e847, `source-code`):
- **The agent's generative call** is `Agent.get_model_output` → `self.llm.ainvoke` (`agent/service.py:1945-1955`). It returns `AgentOutput{thinking, evaluation_previous_goal, memory, next_goal, action:[...]}`.
  - Any `BaseChatModel` can be plugged in.
  - A decider cannot produce that whole object, including typed text and multi-action lists, without a fragile wrapper.
- **What can be reused:**
  - `browser_session.get_browser_state_summary()` gives `dom_state.selector_map` (index → element) and `llm_representation()`.
  - Execution with no agent LLM: `Tools.act(ActionModel)` or `tools.registry.execute_action('click', {'index': n}, browser_session=...)`. Actions: `click{index}`, `input{index,text,clear}`, `navigate`, `scroll`, `send_keys`, `go_back`, `upload_file`. **`extract` calls an LLM.** (`tools/service.py:2132-2178`, `tools/views.py:69-86`)
- **So there are two patterns:**
  - (i) Browser-Use as the executor under our own decide loop.
  - (ii) Browser-Use as the open-ended fallback: run `Agent.step` only when the decider escalates.
- **`rerun_history`** replays a recorded run with no LLM, except `extract`/AI steps. It is a replay tier for flows first solved open-endedly.

#### Step-type classification (social media and lead-gen agent)

| Step type | Class | How |
|---|---|---|
| Navigate to a known URL (profile, compose, inbox, search URL with params) | **deterministic** | URL from config or template. Jev is deliberately bypassed for explicit URLs (decide.ts `explicitNavigation`). |
| Pick the element to click (compose, reply, next, tab, menu item, dismiss) | **decider-capable** | Choice over snapshot candidates plus `none`. Escalate on low confidence or margin. Replay a cached selector first when one exists. |
| Type **known** text (a pre-approved post body, a search term from the plan, a template with filled slots) | **decider (which field) + deterministic (the text)** | Code copies the text verbatim. Never let a model retype it. |
| Type **generated** text (reply, DM, comment, post copy, personalized intro) | **needs generator** | The reasoning model writes. A decider can *gate* the result: on-brand score, policy noul, "does it answer the message" noul. |
| Extract fields (name, title, company, follower count, post stats) | **deterministic** for known sites (selectors/parsers); **generator** for unstructured pages; **decider** only to *pick among* code-found candidates or to classify | TypeSafe pattern: "pre-parsed value extraction". Jev cannot generate or count. |
| Verify outcome (posted? sent? page advanced?) | **deterministic first** (URL change, element present, toast text), then **decider** noul | jev-automation `verify.ts` pattern |
| Detect checkpoint, CAPTCHA, login wall, consent, rate-limit page | **deterministic signals** (URL patterns, known challenge iframes, HTTP status) + **decider** choice over BLOCKERS. The response to a detection is **deterministic**: pause, alert a human, never solve. | Hands-on today: login_wall 0.95 vs 0.04 |
| Choose the next page in exploration | **decider-capable** when candidates can be enumerated (rank links or results with a score per candidate); **generator** for open research planning ("what should I look for next") | |
| Stop or continue | **deterministic** budgets (steps, time, quotas, rate caps) + **decider** noul `goal_reached` | Perplexity cookbook: stop at ≥0.8 |
| Plan or decompose a task | **generator** once, then **deterministic replay** of the stored plan | |
| Classify inbound messages (intent, priority, spam, needs reply) | **decider-capable** | Fan-out: several questions per message in one request |
| Choose a reply template or route | **decider-capable**; filling slots is deterministic | |
| Approve an irreversible action (post, send, DM, delete) | **deterministic policy** (schedule-approved content, quotas, allowlist) + optional decider as a *second* opinion, **never the only gate** | |

#### Estimated share System 1 could own

**`unverified`: these are estimates, not measurements.** The denominator is *browser actions plus judgment calls per completed task*. There are three buckets: **D** = deterministic code or replay, **S1** = decided by a decision model, **G** = generative call.

| Workflow | D | S1 (decider) | G | "No generative call" (D+S1) | Comment |
|---|---|---|---|---|---|
| (a) Repetitive posting (content pre-approved or generated upstream) | 40–60% | 35–55% | 0–10% (≈1 copy-writing call per post, if generated in-loop) | **~90–100%** | Best case. The 90% target is plausible here once replay exists. |
| (b) Inbox triage + reply | 25–40% | 35–55% | 15–35% (scales with the share of messages needing bespoke replies) | ~65–85% | Template replies push it up; personalized DMs push it down. |
| (c) Lead-gen research (open web) | 15–30% | 30–45% | 30–50% (queries, unstructured extraction, summaries, planning) | ~50–70% | The 90% target is implausible unless research is narrowed to known sites with selector extractors. |

The 90%+ claim is a **hypothesis**. It is only plausible when "System 1" means "no generative call", and then only for (a).

The share decided *by the decision model itself* is likely 30–55% in every workflow. The rest of the non-generative work is ordinary code and replay. That is a good outcome, because code is cheaper and more deterministic than a model.

**Measurement plan.** This reuses an older local tool's comparison-pilot discipline.

- **Instrument every step:**
  - `step_type`, `bucket` (D/S1/G), `provider`, `model` (versioned), `template_id@version`.
  - Option order, probabilities at full precision, confidence, margin, latency, cost.
  - Escalation reason, executor result.
  - Ground-truth outcome from an independent check, never the agent's own claim.
- **Phase 0: offline set.**
  - Record snapshots (a11y text plus screenshot) of public test pages, and later of client pages with consent.
  - Hand-label the correct element or answer.
  - Score each provider in **both option orders**.
  - Produce reliability curves (accuracy vs confidence) per `template_id × provider × model version`.
- **Phase 1: shadow.** The existing path (LLM or human) is authoritative; deciders run in shadow. Agreement is *not* accuracy. Label disagreements plus a sample of confident agreements.
- **Phase 2: canary.**
  - Enable decider actions above per-template thresholds that hit a target wrong-action rate. For example, ≤1% on reversible steps.
  - Irreversible steps always keep their deterministic gate.
- **Report per workflow:**
  - D / S1 / G shares on **successful** tasks.
  - Escalations and human interventions per 100 tasks.
  - Wrong-action rate, cost and latency per task.
- **Done means** the 90% figure is reported per workflow with its denominator, n and confidence interval.

### Q5. Multi-provider strategy

**Yes, the fleet should put all deciders behind one interface.** It becomes necessary rather than nice-to-have for four reasons:

1. **Rate limits are per org or account, and low:** Perplexity 10 rps per org; Jev 80 rps "dynamic", with scope unstated; Clef likely 300 rpm per model, which is inferred. 1,000 profiles need pooled limits and spillover.
2. **Shapes differ:** OpenAI uses arrays, `predicate` and `refusal`; Clef and Perplexity carry images differently; Jev is text-only.
3. **Thresholds are not portable.** They must be calibrated per provider, model version and question template. Aliases (`jev-latest`) move.
4. **OpenRouter already normalizes most of it.** `/api/v1/systemone` and `/api/alpha/decisions` give one shape, one key, `usage.cost`, `id` and `provider`, and `provider` preferences on the alpha endpoint. Use it as one backend. Keep direct backends for the main providers so OpenRouter is not a single point of failure.

**Proposed interface** (a fleet service endpoint, e.g. `POST /decide`):

```jsonc
// request
{
  "request_id": "uuid",                 // idempotency key
  "profile_id": "...", "task_id": "...", "step_id": "...",
  "template": "pick_target@3",          // versioned question template; thresholds attach here
  "risk_class": "read|reversible_write|irreversible_write",
  "state": { ... },                     // text/JSON, already filtered (context rot)
  "images": ["data:image/png;base64,..."],   // optional; routes only to vision providers
  "questions": { "target": {"type":"choice","instructions":{...},"criteria":{"e1":"...","none":"..."}},
                 "blocker": {...}, "done": {"type":"noul",...} },
  "routing": { "providers": ["jev","clef-flash","decider"], "max_latency_ms": 2000,
               "max_cost_usd": 0.001, "shuffle_options": true }
}
// response
{
  "outcome": "decided|escalate|refused|error",
  "answers": { "target": {"type":"choice","choice":"e7","probabilities":{...},
               "confidence":0.98,"margin":0.97,"passed_threshold":true} },
  "escalate_reason": null,              // "low_confidence" | "low_margin" | "disagreement" | "refusal" | "rate_limited" | "timeout"
  "provider": "typesafe", "model": "jev-1.13.0", "latency_ms": 312,
  "input_tokens": 1032, "cost_usd": 0.0000433, "log_ref": "decisions/2026-10-09/....jsonl#L123"
}
```

- **Thresholds:**
  - Each `(template, provider, model_version, risk_class)` gets a minimum `confidence`, a minimum `margin` (top1 − top2), and for nouls a two-sided band. For example, act when ≥0.8, treat as "no" when ≤0.2, escalate in between.
  - Start conservative. Do **not** carry over Gemini's ">0.85" or the cookbook's 0.6; set them from Phase 0 and 1 data.
- **Escalation ladder:**
  1. Deterministic replay or rule.
  2. Primary decider.
  3. On mid confidence, a second decider from a *different family*, accepted only if both agree.
  4. Reasoning model (GLM 5.3 Flash) given the *same candidates*.
  5. A human, through the live viewer.

  Irreversible steps never auto-pass on a decider alone.
- **Calibration logging (append-only, per call):**
  - Full request after redaction, option order, and raw probabilities. Jev rounds to 2 decimals; note that in the log.
  - Versioned model id, latency, tokens, cost, escalation, executor result, independent outcome label.
  - Store these as structured records, plus an Obsidian daily-note rollup so Justin can browse decisions per profile.
  - Weekly reliability diagrams per template; drift alarm on any model-version change.
  - **Pin versions** (`jev-1.13.0`, `perplexity/pplx-decider-v1.1-27b-20261006`) and move on purpose.
- **Rate governance:**
  - One central token bucket per provider and org, plus per-profile fairness.
  - Pack the questions for a step into one request (target + blocker + done + risk): one call per step, not four.
  - Budget the request rate: 1,000 profiles × duty cycle × (1 call per ~2–3 s while active). At 10% concurrently active that is ~35–50 rps, which fits Jev alone at today's 80 rps. At 100% active it is ~330–500 rps and needs several providers or a self-hosted Clef/Decider on a GPU.

---

## 3. What the OSS projects give us vs what the fleet must build

| Need | Stagehand v4 (OSS) | Browser-Use 0.13 (OSS) | Decision providers | Fleet must build |
|---|---|---|---|---|
| Candidate list of interactive elements | `page.snapshot()` (a11y tree plus xpathMap) | `selector_map` / `llm_representation()` | n/a (Jev needs text; others also take screenshots) | Filter and rank into ≤180 candidates; per-site noise filters; iframe and shadow-DOM coverage checks |
| Execute a chosen element without an LLM | `act(Action)` | `Tools.act` / `execute_action` | n/a | Adapter from decider choice to executor call |
| Element choice by a decision model | Model hook exists (`clientLLMGenerate`) but expects generative `{elementId, method, arguments, twoStep}` | Any `BaseChatModel`, but it must emit a full `AgentOutput` | Choice API | **The decide loop** (snapshot → decide → act → verify), using the framework only as the executor |
| Action cache / replay | **Browserbase-only** server cache; none on Steel | `rerun_history` (file-based replay) | n/a | **Replay cache** keyed by site + template + DOM signature; decider as the self-heal tier |
| Verify, blockers, login wall | none built in | judge (LLM) | Noul / choice | Verify step (code-first, then decider); blocker taxonomy; human-handoff hook |
| Multi-provider routing, limits, spillover | none | none | OpenRouter partly (one shape, `provider` prefs on alpha) | `/decide` service: limiter, shape adapters (OpenAI), failover, budgets |
| Thresholds and calibration | none | none | `confidence` only (uncalibrated for our tasks) | Labeled sets, shadow pilot, per-template thresholds, drift alarms |
| Risk gating of irreversible actions | none | none | Risk questions exist but are "not a safeguard" | Deterministic policy gate (schedule, quotas, approvals) |
| Prompt-injection resistance | none | none | Jev docs admit adversarial content can move answers | State sanitization; quoting untrusted text as data; second-family agreement on risky steps |
| Self-hosting | n/a | n/a | Clef and Decider weights (GPU, custom code) | Only if rate limits or cost force it: GPU host, SGLang `dev-clef` or Perplexity's inference code |

---

## 4. Operating notes for a Hermes agent (feeds the skills)

- **Call shape (System One family: Jev, Clef, Decider, and OpenRouter `/api/v1/systemone`):**
  `{"model": "...", "state": {...}, "questions": {"<id>": {"type": "choice", "instructions": {"question": "...", "goal": "..."}, "criteria": {"e1": "link \"Next\" -> /page/2/", "none": "No element listed here advances the goal"}}}}`.
  - Read `answers[id].choice`, `.confidence` and `.probabilities`, or `answers[id].noul`.
  - Always include a `none` / `other` option.
- **OpenAI shape is different:** `input` instead of `state`; a `questions` array with `name`; `predicate` instead of noul; `choices[{value,description}]`; `levels[{label,description}]`; `answers` as an array; handle `type:"refusal"`.
- **Ask everything for a step in one request** (speculative fan-out): target, blocker, done, risk. It costs the same latency (vendor claim, consistent with n=1 today) and one rate-limit slot.
- **Keep `state` small and relevant.** Accuracy drops as irrelevant text grows. Send url, title, a short excerpt, and the candidates in `criteria`, not the whole DOM.
- **Element descriptions:** use the `describeElement` style (`kind "text" (label) placeholder "…" → href [checked] [off-screen]`). Disambiguate repeated labels ("Quickstart") with their nearest heading. Perplexity measured 93% → 96% when labels were added.
- **Never ask a decider to:**
  - Write, retype or "extract" free text. Code copies verbatim text; a generator writes new text.
  - Count, do arithmetic, or compare dates.
  - Pick a URL that is already explicit in the instruction.
- **Text-only Jev:** if the decision depends on what the page *looks like* (a modal over the content, a visual-only button), use Clef, Decider or OpenAI with a screenshot.
  - Perplexity: keep each image ≤2,048 tiles (e.g. 1280×800 = 1,000 tiles ≈ 6,000 tokens). Oversize does not return 400; it hangs ~1 min and then returns 504.
  - Clef: ≤4 images.
- **Thresholds are per template, provider and model version.** Today's starting points from shipped code, to be re-measured:
  - jev-automation: target 0.35 (→ clarify), risk 0.6.
  - Perplexity cookbook: act ≥0.6, done ≥0.8, blocked ≥0.8, risk-stop ≥0.7.

  Prefer the margin (top1 − top2) together with confidence. Leave headroom: Jev confidence moved up to 0.09 with option order.
- **Pin model versions** (`jev-1.13.0`). An alias like `jev-latest` can move under you.
- **Timeouts and retries:**
  - jev-automation uses 8 s for decide and 6 s for verify. The Gemini doc's 1 s timeout is too tight.
  - Retry 429/529/5xx with backoff and honor `Retry-After`. Do not retry 400/401/422.
  - Perplexity: 429 carries `Retry-After`; responses carry `x-request-id`.
  - Jev direct: log `x-typesafe-request-id`, plus `cf-ray`.
  - OpenRouter returns `id` (`gen-dec-…`) and `usage.cost`.
- **Option-count caps:** 255 for every provider. Pre-filter dense feeds to ≤180.
- **Clef via OpenRouter** is also served by PrimeIntellect, with 16,384 context. If Cloudflare specifically is required, for its latency or its 64k context, pin `provider` order on `/api/alpha/decisions` or call Workers AI directly. OpenRouter responses report the `provider` that served each call.
- **Untrusted page content:** treat post or comment text as data. Never let a decider be the only gate for post, send, DM, delete or pay. Pair it with a deterministic policy, and use a second-family agreement for medium confidence.
- **Cost reference** (1,000-token step, output free):

  | Model | Cost per step |
  |---|---|
  | Jev | $0.000042 |
  | Decider | $0.00002 |
  | Clef-flash | $0.000038 |
  | Clef | $0.00024 |
  | OpenAI | $0.0001 |
  | Perplexity screenshot step (~7,300 tokens) | ~$0.00015 |

---

## 5. Risks and unknowns

- **Grounding accuracy on real social and lead-gen pages is unmeasured for every provider.** Today's test was easy. The only hard evidence is a Jev miss (search, 0/3). No benchmark covers web-element choice.
- **Rate limits:**
  - Jev's limit changed within three weeks and is "dynamic".
  - Perplexity is 10 rps per org.
  - Clef's limit is inferred, not stated.
  - OpenAI's limits and OpenRouter's limits for decisions are unconfirmed.
- **OpenAI Decisions is a beta.** Shape and pricing may change before GA.
- **OpenRouter:**
  - `/api/alpha/decisions` is labeled alpha.
  - Its translation of the System One shape to OpenAI's API is untested.
  - Its context figures disagree with vendors: Jev 32k vs 64k; Clef-flash 16k vs 24.5k vs 64k.
  - It is one point of failure for every provider.
- **Silent truncation:** Clef truncates long text `state` instead of erroring. A candidate list could be cut without notice. Count tokens client-side.
- **Calibration:** Jev returns 2-decimal probabilities, so 0.00 is not "impossible". `confidence` is the vendors' own statistic, not a measured success rate.
- **Prompt injection through page content** can steer any of these models (`official-docs`, Jev jaggedness).
- **Self-hosting is GPU work, not a droplet:**
  - Clef was tested on an H200.
  - Decider needs ~49 GiB in BF16 plus custom noncausal attention, and its self-host input limit is 8,192 tokens against 262k via the API.
  - Not run or costed here.
- **Vendor benchmark tables are self-reported, and each vendor's table favors its own model** (Cloudflare's shows Jev at 524 ms; ours measured ~300 ms).
- **Stagehand on Steel has no act cache.** That changes the cost and latency assumptions in the Gemini plan, which said cached replays cost $0 on runs 2–1,000.
- **Visibility:** `jev-automation` and `jev-agent-kit` are **public** repos (`isPrivate:false`); the brief calls them private.
  - A separate exposure question about a public companion repo is tracked privately (details withheld).

---

## 6. Sources

All fetched 2026-10-09 unless noted. Local raw copies are in `<scratch>/spikes/system1-models/live/` (not committed).

**TypeSafe / Jev**
- https://docs.typesafe.ai/api.md, /models.md, /concepts/state.md, /primitives/choice.md, /confidence.md, /model-jaggedness/jev-1.13.md, /introduction/coding-agents.md, /legal.md, /sdk/python/changelog.md, /llms.txt (official-docs)
- 2026-09-17 docs snapshot: `jev-agent-kit/skill/typesafe-ai/references/docs/` (manifest `upstream_revision` 65a39f39; retrieved 2026-09-17T22:21Z)
- PyPI `typesafe-sdk` 0.7.4; npm `@typesafe-ai/sdk` 0.6.0

**Cloudflare Clef**
- https://developers.cloudflare.com/changelog/post/2026-10-01-clef-workers-ai/ (2026-10-01)
- https://developers.cloudflare.com/workers-ai/models/clef/, /clef-flash/, /clef-omni/, /clef/schema-input.json
- https://developers.cloudflare.com/workers-ai/platform/limits/
- https://huggingface.co/Cloudflare/clef (sha 0b331204bb13), /clef-flash (8b2e5fd17c09), /clef-omni (0db1cd2607d7). README model card.
- Blog (not fetched, linked from changelog): https://blog.cloudflare.com/clef-decision-models/

**OpenAI Decisions**
- https://developers.openai.com/api/docs/guides/decisions.md
- https://developers.openai.com/api/docs/models/gpt-6-luna.md
- https://community.openai.com/t/decisions-api-is-now-available-in-public-beta/1403877 (2026-10-06)

**Perplexity Decider**
- https://docs.perplexity.ai/docs/decisions/quickstart.md
- https://docs.perplexity.ai/docs/cookbook/examples/decisions-api-browser-agent/README.md
- https://docs.perplexity.ai/llms.txt
- https://huggingface.co/perplexity-ai/pplx-decider-v1.1-27b (sha 6195aa55a72a), /pplx-decider-v1-27b (b01a5cbaca53)

**OpenRouter**
- https://openrouter.ai/api/v1/models?output_modalities=all (catalog with `decisions` modality)
- /api/v1/models/{slug}/endpoints
- https://openrouter.ai/docs/guides/community/typesafe-sdk.md, /docs/guides/community/jev.md
- /docs/api/api-reference/alphadecisions/submit-a-decisions-request.md (OpenAPI for `POST /api/alpha/decisions`)
- /docs/client-sdks/typescript/sdks/systemone/README.md

**Third-party** (used only to find primary sources): InfoQ, the-decoder, aiweekly, eesel, flaviocopes (search results only, not relied on)

**Local code (pinned)**
- browser-box @4c837a30cda707d1c8a4db0dc361f5063b1eb671: `gateway/gateway/jev.py`, `README.md` (act vs task, Jev sections)
- An older local tool checkout (private; pinned commit and file list withheld).
- the public jev-automation fork, `feat/steel-cdp` @edcbbae8e0f7d31359294c93d53cad159d00696a (public): `core/decide.ts`, `core/elements.ts`, `core/verify.ts`, `.env.example`, `package.json`
- jbellsolutions/jev-agent-kit @faeae1633240be142f5695c1ea7728f048bbf601 (public): `skill/typesafe-ai/`, `source/*.md`, `evidence/*.json`
- stagehand @1fc884992b68a0196ea5c6e96cc29924b0922ef4:
  - `packages/extension/services/actService.ts`, `services/cacheService.ts`, `understudy/a11y/snapshot/treeFormatUtils.ts`
  - `packages/sdk-ts/src/page.ts`, `stagehand.ts`
  - `packages/protocol/schemas.ts`
  - `packages/docs/v4/migrations/v3.mdx`, `v4/basics/observe.mdx`
- browser-use @c75e8476e26d18b7617643bc2ae082fae8eae431: `browser_use/agent/service.py`, `agent/views.py`, `tools/service.py`, `tools/views.py`, `tools/registry/service.py`

**Spike:** `fleet/research/spikes/system1-models/{spike_decide.py, RESULTS.md, raw/*.json}` (hands-on, 2026-10-10 02:53 UTC)
