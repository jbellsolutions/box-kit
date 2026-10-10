> **Read with its verification report.** [verification/reasoning-models.md](../verification/reasoning-models.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: the reasoning model inside the browser tool (Stagehand, Browser-Use, vision, repair)

Research date 2026-10-09. Scope: the generative model that Stagehand (act/observe/extract) and
Browser-Use (step loop) call, plus a vision fallback and a repair path. Hermes' own brain is out
of scope. Spike: `fleet/research/spikes/reasoning-models/` (RESULTS.md, scripts, raw JSONL).
Spend: $0.246 of the $0.80 cap. Verified two ways: the sum of OpenRouter `usage.cost` equals the key's usage delta. Provenance tags follow BRIEF.md.

## 1. Verdict

- **GLM 5.3 Flash (`z-ai/glm-5.3-flash`) stays the default reasoning model for both Stagehand and
  Browser-Use, at `reasoning.effort = "low"`, behind a thin client shim** (hands-on).
  - **Correctness, at `low`:**
    - Stagehand act/observe: 48 of 53 correct.
    - Extracts: 100%.
    - Replayed Browser-Use steps: 8 of 8.
    - Live multi-step Browser-Use runs: 6 of 6, median 4 steps, about 5.7 s of LLM time and $0.0024 per task (easy pages only).
    - Tool call: 3 of 3.
    - Vision: best of every open model tested. It is the only one that returned true pixel
      coordinates 3 of 3.
  - **Speed:** p50 1.2 s and p90 3.4 s per Stagehand call (n=64); Browser-Use step p50 1.8 s.
  - **Cost:** about $0.001 per uncached act on a 6k-token page.
  - **Openness:** MIT open weights, served by 29 providers on OpenRouter.
- **GLM has one real defect, and it is mitigable.** In about 3% of structured calls (4 of 144)
  constrained decoding degenerates inside the act schema's free-string `arguments` array. It emits
  `"", "", ...` until `max_tokens` (34-52 s, about $0.004 each) or leaves junk such as `"],"` or
  `"LEFT"` in `arguments[0]`, which Stagehand passes to CDP as the mouse button (hands-on +
  source-code).
  - It happens at both `low` and `high` effort and at temperature 0, on the Together and Friendli
    endpoints.
  - **The fleet must ship a client shim with every model, not only GLM.** It caps `max_tokens` per
    call type, retries on `finish_reason=length` or invalid output, and keeps only a valid
    `arguments[0]`. Gemma also ran away, for about 6 minutes, so this is not a GLM-only need.
- **Stagehand 4.2.0 cannot reach OpenRouter through its built-in model config** (source-code).
  - Its direct providers are only openai, anthropic, google, groq and cerebras.
  - `ModelConfig` is just `{modelName, apiKey, headers}`: there is no `baseURL`.
  - The only open-model route is the **client LLM callback**: Python `Stagehand.create(model=<async fn>)`
    or TS `model: {generate}`. Proven end to end against GLM via OpenRouter (hands-on, 7 of 7 steps).
  - The callback also keeps the API key in the client process. A direct `ModelConfig` ships the key
    into the Stagehand extension running inside the browser, which would be the Steel or Browserbase
    browser (source-code).
- **Reasoning on GLM 5.3 Flash is mandatory** (hands-on).
  - `reasoning: {enabled:false}` and `effort:"none"` both return 400 "Reasoning is mandatory for this
    endpoint and cannot be disabled".
  - With no parameter it runs at `max`, which is the browser-box "~40 s a step" trap.
  - `low` costs about 1 reasoning token per Stagehand call. `high` measured no more accurate here and
    costs about 25% more.
- **Browser-Use 0.13.11 does not use tool calling. It sends one strict json_schema
  `response_format` (`agent_output`) per step** (source-code + hands-on).
  - What matters for a Browser-Use model is json_schema support plus a token cap.
  - browser-box's `ChatOpenAI(base_url=OpenRouter, reasoning_models=[m], reasoning_effort="low")`
    pattern is correct and should be reused. It sends `max_completion_tokens` 4096 by default.
- **Runner-up / cross-family retry: DeepSeek V4.1 Flash with reasoning off** (hands-on).
  - Fastest p50: 1.09 s Stagehand, 0.49 s tool step. Accuracy 26 of 27.
  - MIT license, 23 endpoints with structured-output support.
  - Its failure mode is different from GLM's: false `null`s, not runaways. That makes it the right
    second opinion.
  - It is weak at vision grounding. Uncached cost is about 1.1x GLM's.
- **Qwen 3.8 Flash scored 27 of 27, but it is a fragile dependency** (hands-on + vendor listing):
  - one provider (Alibaba);
  - `tool_choice: "required"` is unsupported (404);
  - 0-1000-normalised coordinates;
  - p90 8.9 s;
  - a custom `qwen-community-1.0` license (terms not reviewed).

  Good as a third option, not the default.
- **Do not use these for anything that acts:**
  - **Nemotron 3.5 Lightning**: fabricated a click on an impossible instruction in 2 of 3 runs.
  - **Mistral Small 2603**: unmeasurable; 20 of 27 calls were rate-limited upstream, single provider.

  For agents that post and message on clients' accounts, a fabricated click is the worst failure.
- **"Repair" is mostly code, not a model.** JSON validity is solved by strict json_schema plus the
  shim. The model-side repair ladder for a failed act or step is:
  1. retry GLM on a different provider;
  2. escalate to DeepSeek V4.1 Flash, reasoning off;
  3. escalate to the screenshot path, with GLM vision.

  The only cheap text model worth keeping is **gpt-oss-120b @low**: $0.037/$0.17 per M, Apache-2.0,
  18 of 18 on act/observe. It is not for extraction, where it truncated lists in 2 of 6 runs.

## 2. Answers to the numbered questions

### Q1. GLM 5.3 Flash on OpenRouter: pricing, context, tools, json_schema, vision, reasoning controls, providers

| property | value | provenance / source |
|---|---|---|
| Slug | `z-ai/glm-5.3-flash` (canonical `z-ai/glm-5.3-flash-20260826`). Do **not** use the `~z-ai/glm-flash-latest` alias: it silently redirects to the newest GLM Flash and carries a different listed price ($0.032 in) | vendor-claim: `https://openrouter.ai/api/v1/models`, fetched 2026-10-09 (`raw/openrouter_models_subset_2026-10-09.json`) |
| Weights | MIT, ungated, 321.3B total params (safetensors: about 314B FP8 + 6.9B BF16). README says "320B total parameters and just 18B active", hybrid sparse+linear attention, natively multimodal. HF repo created 2026-08-25 | official-docs: `https://huggingface.co/zai-org/GLM-5.3-Flash` (API + README fetched 2026-10-09) |
| List price | $0.15/M input, $0.50/M output, $0.03/M cache read. `:batch` variant $0.06/$0.20. Endpoint prices range $0.032-$0.225/M input. OpenRouter's default routing weights providers by inverse price squared, so effective cost is often below list | vendor-claim: models API + `/api/v1/models/z-ai/glm-5.3-flash/endpoints` (`raw/endpoints/z-ai_glm-5.3-flash.json`); routing rule: official-docs `https://openrouter.ai/docs/guides/routing/provider-selection` |
| Measured cost | Stagehand act/observe on a 6k-token page: about $0.0009-0.0013 uncached (about $0.0002 when the provider prompt cache hits). Act on a 0.9k-token page: $0.00015. 20-item extract: $0.0011 plus about $0.00012 for its mandatory Metadata call. Browser-Use step (about 8.5k prompt tokens): $0.0014 uncached | hands-on: `raw/summary_costs.md` |
| Context | 1,048,576 tokens. Max completion 943,717 at top endpoint; 128k-944k depending on provider. Reka caps context at 262k | vendor-claim: models + endpoints API |
| Tool calling | `tools`, `tool_choice`, `parallel_tool_calls` listed. Measured: 3 of 3 correct `click(index=347)` with `tool_choice: required`, p50 0.91 s | vendor-claim + hands-on (`raw/tools.jsonl`) |
| json_schema / structured outputs | `response_format` + `structured_outputs` listed at model level. **26 of 33 endpoints** support structured outputs. These lack it: relace, streamlake, novita, gmicloud, atlas-cloud, siliconflow and **z-ai's own first-party endpoint**. On 2026-10-09 OpenRouter dropped those endpoints from json_schema requests even without `require_parameters` (pinning to z-ai returned 404 "Filter by Parameters removed ... z-ai/fp8"). Strict validity in the bench: 70 of 72 at low; both failures were runaways | vendor-claim + hands-on (`raw/routing_probe.jsonl`, `raw/summary_glm_all.md`) |
| Vision | Input modalities text, image, video. Measured: star ratings read from a screenshot 3 of 3; pixel-accurate click coordinates 3 of 3 (1135-1137, 789-790 inside box x 1040-1235, y 773-807); p50 1.1-2.1 s | vendor-claim + hands-on (`raw/vision.jsonl`) |
| Reasoning controls | Mandatory. Efforts `max`, `high`, `low`; default `max`. `reasoning:{enabled:false}` and `effort:"none"` both return HTTP 400 "Reasoning is mandatory for this endpoint and cannot be disabled." Default (max) spent 91 reasoning tokens on a 0.9k-token act. Low spent about 1 token per Stagehand call on average, high about 15. The model card says the same: `reasoning_effort` low/high/max, default max | hands-on (`raw/routing_probe.jsonl`) + official-docs (HF README line 45) + vendor-claim (`reasoning` block in models API) |
| Latency at low | Stagehand calls (n=64): p50 1.21 s, p90 3.44 s, max 50 s (runaway). All 72 text calls including Browser-Use: p50 1.36 s, p90 3.46 s. Browser-Use step: p50 1.8 s. Matches the box note "low effort is a few seconds" | hands-on |
| Providers | 33 endpoints from 29 providers: OpenInference, Relace, Sail Research, Morph, Reka, InferenceNet, Wafer, DeepInfra, StreamLake, Novita, GMICloud, Decart, Inceptron, DekaLLM, Near AI, Phala, Modal, BaseTen, Crusoe, CoreWeave, AtlasCloud, Fireworks, Friendli, SiliconFlow, DigitalOcean, Together, Parasail, Venice, Z.AI. Quantization: 11 fp8, 9 fp4, 3 nvfp4, 10 unknown. Measured traffic landed on Friendli, Together, Parasail, Modal, Venice (plus InferenceNet for Browser-Use). `data_collection:"deny"` and `zdr:true` still served (Together) | vendor-claim (endpoints API) + hands-on |
| Third-party scores | Artificial Analysis via the OpenRouter models API: intelligence 41.8, coding 71.5, agentic 50.9. That is the highest agentic index among sub-$0.50 open models listed | third-party (embedded in the OpenRouter models API) |
| Siblings | `glm-5.3-flashx`: $0.37/$1.25, "up to 200 tokens/s", **no HF id** (not open weights), no `structured_outputs` at model level. `glm-5.3`: text only, $0.039/$4.80 listed. `glm-5v-turbo`: closed. None is a better fit | vendor-claim |

### Q2. Open-weight alternatives on OpenRouter (Oct 2026) with tools + structured outputs

The survey is filtered from the full models list (458 models). It keeps models with an HF id, tools
plus `response_format`/`structured_outputs`, and 2026 releases, plus the older gpt-oss, Llama 4 and
Mistral. Prices are list $/M (input/output). "SO eps" counts endpoints that support structured
outputs. The measured column is from this spike.

| model | license (HF) | $/M in/out | ctx | vision | SO eps | reasoning control | AA intel/agentic | measured (this spike) |
|---|---|---|---|---|---|---|---|---|
| **z-ai/glm-5.3-flash** | MIT | 0.15/0.50 | 1M | yes | 26/33 | mandatory: low/high/max | 41.8/50.9 | default; see Q1 |
| deepseek/deepseek-v4.1-flash | MIT | 0.30/1.20 (eps 0.02-0.45) | 1M | yes | 23/31 | optional: max/high/low, can be off | 39.5/- | 26/27 off, p50 1.09 s; vision weak |
| qwen/qwen3.8-flash | qwen-community-1.0 | 0.15/0.47 | 1M | yes | 2/2 (Alibaba only) | optional | -/- | 27/27, p50 2.43 s, p90 8.9 s; no `tool_choice:required`; 0-1000 coordinates |
| xiaomi/mimo-v2.6-flash | MIT | 0.14/0.28 | 1M | yes (+audio) | 7/8 (mostly Xiaomi) | optional | 37.9/- | 23/27, p50 4.7 s; vision 5/6 |
| google/gemma-4-31b-it | Apache-2.0 | 0.09/0.34 | 262k | yes | 11/13 | off by default | 14.7/4.2 | 25/27 but p90 20 s with 6-minute runaways; vision poor |
| openai/gpt-oss-120b | Apache-2.0 | 0.037/0.17 | 131k | no | 18/23 | mandatory: low/med/high | 11.6/3.7 | act/observe 18/18; extract lists truncated 2/6; p50 3.0 s |
| nvidia/nemotron-3.5-lightning | openmdw-1.1 | 0.047/0.134 | 262k | no | 6/6 | optional | 12.9/3.5 | p50 0.95 s but **fabricated clicks** on the negative task (2/3) |
| mistralai/mistral-small-2603 | Apache-2.0 | 0.15/0.60 | 262k | yes | 4/4 (Mistral only) | high/none | 11.3/0.8 | unmeasurable: upstream 429 on 20 of 27 calls |
| moonshotai/kimi-k2.6 | HF id listed | 0.465/2.45 | 262k | yes | 17/17 | optional | 27/20.5 | not run (3-5x GLM output price) |
| minimax/minimax-m3 | HF id listed | 0.30/1.20 | 1M | yes | 3/13 | optional | 29.2/29.5 | not run (few SO endpoints) |
| qwen/qwen3.6-35b-a3b | HF id listed | 0.15/1.00 | 262k | yes | 8/10 | optional | 18.2/13.1 | not run |
| tencent/hy3 | HF id listed | 0.132/0.528 | 262k | no | 3/5 (none with both RF+SO) | high/low/none | -/- | not run |
| stepfun/step-3.7-flash | HF id listed | 0.20/1.15 | 262k | yes | 2/2 | mandatory | 19.5/- | not run |
| meta-llama/llama-4-maverick | HF id listed | 0.188/0.652 | 1M | yes | yes | none | 10/0.6 | not run: 2025 generation, far behind |

Sources: `https://openrouter.ai/api/v1/models` and `/api/v1/models/<id>/endpoints`, fetched
2026-10-09 (vendor-claim; `raw/openrouter_models_subset_2026-10-09.json`, `raw/endpoints/`).
Licenses come from the HF API (`https://huggingface.co/api/models/<id>`, official-docs).
AA indices are third-party. Kimi, MiniMax, Qwen 3.6, Hy3 and Step licenses were not checked.

Closed reference measured for calibration: `openai/gpt-6-luna` @none, at the same list price as GLM.
It was accurate on act/observe (18/18) and fast (p50 1.2 s). But OpenAI strict mode **rejects the
Stagehand Python SDK's extract schema** (`additionalProperties: {}`), and it leaked prose before the
JSON on the vision task. It is not open, and it is not better here.

### Q3. Hands-on benchmark

All in `fleet/research/spikes/reasoning-models/RESULTS.md` (commands, raw numbers, date, spend).
Headline rows (3 runs × 9 real Stagehand/Browser-Use tasks; correct counts use Stagehand's
execution semantics):

| config | valid | correct /27 | act+observe /18 | extract | BU step | p50 s | uncached $/call |
|---|---|---|---|---|---|---|---|
| glm-5.3-flash @low | 25/27 | 24 | 15 | 1.00 | 3/3 | 1.88 | 0.00091 |
| glm-5.3-flash @high | 27/27 | 27 | 18 | 1.00 | 3/3 | 1.58 | 0.00091 |
| GLM, all extra runs pooled: low n=72, high n=52 | 70/72, 51/52 | 67/72, 51/52 | 48/53, 37/38 | 1.00 | 8/8, 8/8 | 1.36, 1.48 | - |
| deepseek-v4.1-flash @off | 27/27 | 26 | 17 | 1.00 | 3/3 | 1.09 | 0.00098 |
| qwen3.8-flash @off | 27/27 | 27 | 18 | 1.00 | 3/3 | 2.43 | 0.00085 |
| gpt-oss-120b @low | 27/27 | 25 | 18 | 0.67 | 3/3 | 3.02 | 0.00028 |
| gemma-4-31b | 25/27 | 25 | 16 | 1.00 | 3/3 | 4.34 | 0.00067 |
| nemotron-3.5-lightning @off | 27/27 | 24 | 15 | 1.00 | 3/3 | 0.95 | 0.00033 |
| mimo-v2.6-flash @off | 27/27 | 23 | 14 | 1.00 | 3/3 | 4.69 | 0.00076 |

Low vs high on GLM is within noise. On the dedicated 5-run rerun of the hard tasks both scored
24/25 (`raw/glm_effort.jsonl`). Low is cheaper and faster, so keep low.

Live multi-step Browser-Use runs: 3 runs each of quotes pagination to page 3, and of the-internet
`dynamic_loading/2`, max 8 steps, local headless Chrome (`raw/bu_live/summary.md`).

| model | correct | median steps | median LLM s / task | $ / task | finish=length |
|---|---|---|---|---|---|
| GLM 5.3 Flash @low (browser-box config) | 6/6 | 4 | 5.7 | 0.0024 | 0 |
| DeepSeek V4.1 Flash @off (`ChatOpenRouter`) | 6/6 | 4.5 | 8.8 | 0.0035 | 0 |

These are easy pages. The README's harder GLM failures (URL typing, SPA shadow roots) were not
re-tested.

### Q4. Recommendations

| role | pick | evidence | config |
|---|---|---|---|
| **Stagehand default** (act/observe/extract) | **GLM 5.3 Flash @low** | 48/53 act/observe correct, 100% extract, p50 1.4 s. All 5 misses were runaways or junk arguments the shim fixes, except 1 false `null` | Python SDK callback → OpenRouter chat completions, json_schema strict, `require_parameters`, `max_tokens` capped, retry once on another provider |
| **Browser-Use default** | **GLM 5.3 Flash @low** (keep browser-box's runner config) | 8/8 replayed steps. Live multi-step (quotes pagination, dynamic loading): 6/6, median 4 steps, 5.7 s of LLM time and $0.0024 per task. DeepSeek @off was also 6/6, but slower (8.8 s) and costlier ($0.0035 per task). Easy pages only | `ChatOpenAI(model, base_url=OpenRouter, reasoning_models=[model], reasoning_effort="low")`, `max_completion_tokens` 4096, `use_vision=False` |
| **Cross-family retry / second opinion** | **DeepSeek V4.1 Flash, reasoning off** | 26/27, fastest p50, different failure mode (false nulls), MIT, 23 SO endpoints | same shim. For Browser-Use use `ChatOpenRouter(extra_body={"reasoning":{"enabled":False},"max_tokens":4096,"provider":{"require_parameters":True}})` |
| **Vision fallback** (screenshot extract, coordinate click) | **GLM 5.3 Flash @low** itself | ratings 3/3, pixel click 3/3; no other open model got pixel coordinates right 3/3 | send the screenshot at its real size; tell it the pixel size; validate x,y inside the viewport. Second choice MiMo V2.6 Flash (5/6) |
| **Cheap repair model** | Mostly **code**, not a model. If a cheap text model is wanted for re-asking a small act or classifying a failure: **gpt-oss-120b @low** | act/observe 18/18 at $0.00028/call; not for extract | never Nemotron for anything that clicks |
| **Should GLM 5.3 Flash stay default?** | **Yes** | best mix of accuracy, vision, openness (MIT, 29 providers), speed and price; its one defect is mitigable in the shim | re-run `bench.py` when GLM 5.4 Flash or DeepSeek V4.2 lands |

## 3. What the open-source projects give us vs what the fleet must build

| need | Stagehand 4.2.0 / Browser-Use 0.13.11 give | fleet must build |
|---|---|---|
| Reaching GLM on OpenRouter from Stagehand | Client LLM callback hook (`model=<async fn>` in Python, `model:{generate}` in TS) and an example for OpenAI Responses (`packages/sdk-python/examples/custom_llm.py`). No OpenRouter or baseURL support in `ModelConfig` | **`openrouter_generate()` shim**: maps `LLMStructuredGenerateParams` to OpenRouter chat completions and back, including usage mapping and images (`image_url` data URL) |
| Token cap / runaway protection | Nothing on the callback path (no `max_tokens` in the params). Browser-Use `ChatOpenAI` sends `max_completion_tokens` 4096 and raises `ModelOutputTruncatedError` on `length`. Browser-Use `ChatOpenRouter` sends **no** cap | Per-call-type caps in the shim, from observed completion sizes: act/observe 1024, extract about 30 tokens per expected item + 512, Metadata 256. Retry on `length` with `provider.ignore=[failed provider]` |
| `arguments` sanitizing | Stagehand executes `arguments[0]` only; a click passes it to CDP as the button | Keep `arguments[:1]`. Lowercase. For click, keep only `""`/`left`/`right`/`middle`, else drop it |
| Schema portability | Python SDK emits `additionalProperties: {}` for pydantic extract schemas. Open-model providers accept it; OpenAI strict rejects it | Schema sanitizer: `{}` → `false`, so any provider works |
| Provider hygiene | — | Always `provider.require_parameters: true`. Set `data_collection: "deny"` (or `zdr: true`; both measured still routable for GLM). Pin the exact slug, never `~...-latest` |
| Reasoning effort | Stagehand passes none. Browser-Use passes `reasoning_effort` only if the model is in `reasoning_models` | Shim sends `reasoning: {effort: "low"}` for GLM and `{enabled: false}` for DeepSeek |
| Model escalation / repair ladder | Stagehand self-heal and Browser-Use `max_failures` retry with the same model | Ladder: GLM retry on a new provider → DeepSeek V4.1 Flash @off → screenshot/vision path → hand back to Hermes |
| Cost accounting | Stagehand returns token counts; Browser-Use `calculate_cost` uses its own price table | Record OpenRouter `usage.cost` and `provider` per call and per profile; aggregate in the fleet service |
| Per-call observability | — | Log model, provider, finish_reason, latency, cost and a validation verdict, so a regression on one provider shows up |
| Regression test | — | Keep `bench.py` + `raw/captures/` as the model-swap acceptance test (about $0.15 per full run) |

## 4. Operating notes for a Hermes agent (feeds the skills)

**Stagehand (Python) with GLM:**

```python
async def generate(params):                     # stagehand.LLMStructuredGenerateParams
    rf = params.response_format
    schema = sanitize(rf.schema_.model_dump(mode="json", by_alias=True))   # {} -> false
    body = {
      "model": "z-ai/glm-5.3-flash",                       # exact slug, never ~z-ai/glm-flash-latest
      "messages": to_openai(params.system_prompt, params.messages),   # images -> image_url data URLs
      "response_format": {"type": "json_schema",
                          "json_schema": {"name": rf.name, "strict": True, "schema": schema}},
      "reasoning": {"effort": "low"},                      # 'none'/enabled:false -> HTTP 400
      "max_tokens": cap_for(rf.name),                      # Act/Observation 1024, Metadata 256, Extraction sized
      "provider": {"require_parameters": True, "data_collection": "deny"},
      "usage": {"include": True},
    }
    # POST https://openrouter.ai/api/v1/chat/completions ; on finish_reason=="length" or invalid JSON:
    # retry once with provider.ignore=[resp["provider"]], then fall back to deepseek/deepseek-v4.1-flash
    # with reasoning {"enabled": False}. Then fix arguments: keep [:1], lowercase, drop bad click buttons.
stagehand = await Stagehand.create(browser=browser, model=generate)
```

- Each `extract()` makes **2** LLM calls: Extraction, then a Metadata "is it complete" check.
  Budget both (source-code: `packages/extension/inference.ts`).
- Stagehand's act prompt puts the instruction before the accessibility tree. Provider prompt caching
  therefore rarely applies across different actions on the same page. Plan on uncached cost: about
  $0.001 per act on a 6k-token page.
- Stagehand's own action cache, which skips the LLM on a repeated act, is where cost savings come from.
  So does routing simple picks to the System 1 model (Jev), so it, not GLM, takes most acts.
- `act()` returning "No action found" is often correct. GLM returned `null` correctly 3/3 on an
  impossible instruction. Don't retry a `null` blindly on a stronger model; check the page first.
- Repeated widgets ("Add to basket for X" among 20 identical buttons) are where both runaways and
  false `null`s clustered. Phrase acts with the anchoring text.
  - GLM picked the right button in 24 of 24 non-runaway attempts. 2 of those carried junk click
    arguments, which the shim fixes.
  - DeepSeek returned `null` there 2 times.

**Browser-Use with GLM** (keep browser-box's runner pattern):

```python
llm = ChatOpenAI(model="z-ai/glm-5.3-flash", base_url="https://openrouter.ai/api/v1", api_key=KEY,
                 reasoning_models=["z-ai/glm-5.3-flash"], reasoning_effort="low")   # max_completion_tokens=4096 default
Agent(task=..., llm=llm, use_vision=False, use_judge=False, max_failures=3, llm_timeout=90, step_timeout=120,
      calculate_cost=False, directly_open_url=True)
```

- Without `reasoning_models=[model]`, Browser-Use sends no `reasoning_effort`, and GLM reasons at
  `max` (about 40 s and up to 6k tokens per step; browser-box commit f696b13).
- For reasoning models it also drops `temperature` and `frequency_penalty`.
- A step is about 8.5k prompt tokens: a 24.6 KB system prompt plus a 14 KB schema, both stable and
  cacheable. Expect about $0.001-0.0014 and 1.5-3 s per step.
- `ChatOpenAI` cannot send `provider` prefs (no `extra_body`). To add `require_parameters` or
  `data_collection`, either use `ChatOpenRouter(extra_body=...)` and add `max_tokens` to `extra_body`
  yourself, or inject them with an httpx request hook. On 2026-10-09 OpenRouter already filtered out
  non-json_schema endpoints without being asked.

**Vision fallback:**

- Use GLM itself. State the image's pixel size in the prompt, and validate the output's x,y bounds.
- If you swap in Qwen or MiMo, expect 0-1000-normalised coordinates sometimes. Detect that case
  (both values ≤ 1000, viewport larger) and rescale, or re-ask.

**Model swaps and limits:**

- **GLM 5.3 Flash:** no `none` effort. Default effort is `max`. Max completion 131k-944k by provider,
  so always cap. 1M context, but Stagehand trees are 1-10k tokens, so context is never the limit.
- **DeepSeek V4.1 Flash:** reasoning can be off (`{"enabled": false}`). Endpoint prices vary 20x
  ($0.016-0.45/M input), so OpenRouter's price weighting matters.
- **Qwen 3.8 Flash:** use `tool_choice: "auto"`, not `"required"`. Single provider.
- **gpt-oss-120b:** text only, 131k context; fine for acts, not for long extractions.

## 5. Risks and unknowns

- **GLM runaway rate.** About 3% (4/144; 95% CI roughly 1-7%), on only two pages' worth of trees.
  - Harder pages (social feeds, long DOMs) may change the rate.
  - The shim bounds the cost to one capped call plus a retry. It does not bound latency to zero.
  - Each runaway at an 8k cap cost 34-52 s; a 1k cap should bring that to a few seconds (not measured).
- **Provider variance.** GLM is served at fp4, fp8 and nvfp4 by 29 providers, and quality per
  provider was not separated.
  - Both runaways seen were on Together and Friendli, which also served most calls.
  - `provider.quantizations` / `only` can pin a set if a provider regresses.
- **Single-provider alternatives.** Qwen 3.8 Flash (Alibaba) and Mistral Small (Mistral, rate-limited
  during this spike) are availability risks at fleet scale.
- **Small samples.** n=27 per non-GLM model. Rankings among the models that scored 24-27 are not
  significant.
- **Live Browser-Use evidence is thin.** It covers 2 multi-step tasks × 3 runs per model on easy
  public pages. The browser-box README saw GLM fail on an SPA and on URL typing in multi-step tasks;
  those were not re-tested here.
- **Vision.** One viewport size (1280x1024, DPR 1). Provider-side image preprocessing is undocumented.
  Coordinate accuracy at DPR 2, or with cropped screenshots, is untested.
- **OpenRouter behaviour can change.** Parameter filtering without `require_parameters`, mandatory
  reasoning, and endpoint lists are observations dated 2026-10-09.
- **Data handling.** Page trees from clients' social accounts will include private messages.
  - `data_collection: "deny"` and `zdr: true` still route GLM (Together served both probes).
  - How many of the 29 providers remain under ZDR was not enumerated.
- **Stagehand version drift.** The callback protocol (`LLMStructuredGenerateParams`) is v4-specific.
  The bench captures are tied to 4.2.0 prompts (`packages/extension/prompt.ts` @1fc8849).
- **Not investigated (out of scope):** `typesafe/jev-router` is listed on OpenRouter (variable
  pricing, created 2026-09-25). It is a pointer for the System 1 agent only.

## 6. Sources

Primary (hands-on, 2026-10-09):

- Spike, `fleet/research/spikes/reasoning-models/`:
  - `RESULTS.md`
  - `raw/main.jsonl`, `raw/vision.jsonl`, `raw/tools.jsonl`, `raw/glm_effort.jsonl`,
    `raw/glm_temp.jsonl`, `raw/routing_probe.jsonl`
  - `raw/captures/` (real Stagehand 4.2.0 requests), `raw/bu_capture1/` (real Browser-Use 0.13.11
    HTTP bodies), `raw/bu_live/`
  - `raw/spend.jsonl` (key usage before and after)

Source code (pinned):

- Stagehand @1fc884992b68a0196ea5c6e96cc29924b0922ef4 (scratch clone `sources/stagehand`):
  - `packages/extension/prompt.ts`: act/observe/extract prompts.
  - `packages/extension/inference.ts`: schemas; 2-call extract.
  - `packages/extension/llm/aiSdkClient.ts`: direct providers; no baseURL; `.responses()` for OpenAI;
    the "server runs inside the browser extension" comment.
  - `packages/extension/llm/aisdk.ts`: `PROMPT_JSON_FALLBACK_PATTERNS ["deepseek","kimi","glm"]`.
    Only reachable through `LLMProvider.ts`, which only evals reference, so **not live**.
  - `packages/protocol/schemas.ts`: `ModelProviderSchema`, `ModelConfigSchema` with no baseURL.
  - `packages/sdk-ts/src/stagehand.ts:356`: the model config, including `apiKey`, is sent to the
    extension worker unless it is a callback.
  - `packages/sdk-python/src/stagehand/stagehand.py:141-149,497`.
  - `packages/sdk-python/examples/custom_llm.py`.
  - `packages/extension/handlers/handlerUtils/actHandlerUtils.ts`: `arguments[0]` semantics.
- Stagehand npm `@browserbasehq/stagehand@4.2.0`: `dist/extension/service-worker.js` bundles the
  same prompts. Python `stagehand==4.2.0` in `<scratch>/py/.venv`.
- Browser-Use 0.13.11 (`<scratch>/py/.venv/lib/python3.12/site-packages/browser_use`):
  - `llm/openai/chat.py`: json_schema `agent_output` strict; `reasoning_effort` only for
    `reasoning_models`; `max_completion_tokens` 4096; raises on `length`.
  - `llm/openrouter/chat.py`: `extra_body`, no token cap.
  - `llm/__init__.py`: "switched all of our code from langchain"; LiteLLM is an optional `ChatLiteLLM`
    class. The Gemini hypothesis "browser-use uses LiteLLM / LangChain under the hood" is false for
    0.13.
- browser-box @4c837a3:
  - `agents/browseruse/runner.py` (`llm_options`).
  - Commit f696b13: mandatory reasoning, about 40 s per step at full effort.
  - `README.md`: GLM `task` failure notes.

Vendor and official docs (fetched 2026-10-09; the pages carry no dates):

- `https://openrouter.ai/api/v1/models`, `https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints`
  and the other endpoint lists (vendor-claim).
- `https://openrouter.ai/z-ai/glm-5.3-flash` and `/llms.txt` (vendor-claim; parameter list only).
- `https://openrouter.ai/docs/guides/features/structured-outputs` (official-docs: `require_parameters`
  recommendation; strictness varies by endpoint).
- `https://openrouter.ai/docs/guides/best-practices/reasoning-tokens` (official-docs: `mandatory` flag;
  reasoning tokens billed as output and counted against `max_tokens`).
- `https://openrouter.ai/docs/guides/routing/provider-selection` (official-docs: `order`, `only`,
  `ignore`, `quantizations`, `sort`, `data_collection`, `zdr`; inverse-square price load balancing).
- `https://huggingface.co/zai-org/GLM-5.3-Flash` (API + README: MIT, 320B/18B active, reasoning_effort
  low/high/max, default max).
- HF API for `deepseek-ai/DeepSeek-V4.1-Flash` (MIT), `Qwen/Qwen3.8-Flash-Next` (qwen-community-1.0),
  `XiaomiMiMo/MiMo-V2.6-Flash-RL` (MIT), `google/gemma-4-31B-it` (Apache-2.0), `openai/gpt-oss-120b`
  (Apache-2.0), `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` (openmdw-1.1),
  `mistralai/Mistral-Small-4-119B-2603` (Apache-2.0).

Third-party:

- Artificial Analysis indices as embedded in the OpenRouter models API.
- Web search summaries for GLM 5.3 Flash (powerdrill.ai, cloudprice.net, llmreference.com).
  Superseded by the HF model card, so nothing is carried from them.
