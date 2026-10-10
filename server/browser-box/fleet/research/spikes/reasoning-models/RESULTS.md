# Spike: reasoning models for Stagehand / Browser-Use (OpenRouter)

Date: 2026-10-09. Agent: reasoning-models research agent. Spend: **$0.246** of the $0.80 cap
(sum of OpenRouter `usage.cost` over every call; the key's `usage` counter moved by the same
amount between the start and end snapshots in `raw/spend.jsonl`, so no other caller shared the key
during the run). Public test pages only: books.toscrape.com, quotes.toscrape.com,
the-internet.herokuapp.com. No containers were started. Local Chrome for Testing
(playwright `chromium-1243`) ran headless and was closed by each script.

## What was measured, and how

1. **Capture real requests.** `capture_stagehand.py` runs the Stagehand 4.2.0 **Python** SDK
   (`stagehand==4.2.0`, local headless Chrome) with `model=<async callback>`. The callback writes
   each request verbatim (system prompt, messages with the real accessibility tree, JSON schema) to
   `raw/captures/`, forwards it to `z-ai/glm-5.3-flash` on OpenRouter and returns the result. All 7
   Stagehand steps (observe, 2 extracts = 4 LLM calls, 4 acts) succeeded end to end
   (`raw/captures/capture_steps.jsonl`). `capture_browseruse.py` does the same for Browser-Use
   0.13.11, configured as browser-box's `agents/browseruse/runner.py` does it. An httpx hook records
   the exact HTTP bodies (`raw/bu_capture1/`). The live run answered correctly in 2 LLM calls and
   20.6 s wall, browser start included.
2. **Replay.** `bench.py` replays the frozen requests byte for byte against each model through
   OpenRouter chat completions. Every call sends `response_format: json_schema` (strict),
   `provider.require_parameters: true`, `usage.include: true` and `max_tokens` 8000 (4096 for the
   Browser-Use step, its own default). Each config ran 3 times per task, with up to 2 retries on
   429/5xx. Latency is client wall time for the final attempt (non-streaming).
3. **Scoring.**
   - *Valid* means all of these: the content parses with `json.loads` directly, it passes
     `jsonschema` Draft 2020-12 against the exact captured schema (strict `additionalProperties`,
     the `^\d+-\d+$` id pattern, the method enum, nullable `action`), and `finish_reason != length`.
     Invalid output scores 0, because Stagehand's `generateStructured` and Browser-Use's
     `model_validate_json` would throw.
   - *Correct* compares against ground truth written down before the runs, from the captured tree
     and from curl'd HTML (`raw/ground_truth.json`, `raw/vision_truth.json`).
   - **Disclosure: scoring was tightened and relaxed after the first pass to match how Stagehand
     executes an action.** Stagehand uses only `arguments[0]`
     (`packages/extension/handlers/handlerUtils/actHandlerUtils.ts` @1fc8849: `selectOption`,
     `fillOrType` and `typeText` read `args[0]`; `clickElement` passes `args[0]` straight to CDP as
     the mouse button). So:
     - a dropdown, fill or type with extra trailing arguments now counts as correct;
     - a click whose `arguments[0]` is anything but `""` or `"left"` (for example `"LEFT"`, `"],"` or
       `"Poetry"`) now counts as wrong.

     The raw `score` field in the JSONL is the bench's first-pass score. The tables below are from
     `summarize.py`, which applies the rule above.
4. **Tasks** (all real Stagehand / Browser-Use prompts):
   - Stagehand trees: books.toscrape.com is about 6k tokens; the herokuapp pages are about 0.9k.

   | task | page | correct answer |
   |---|---|---|
   | `sh_observe_categories` | books | exactly elements `0-91` (Travel) and `0-175` (Poetry) |
   | `sh_act_book_link` | books | a link to "Tipping the Velvet" (`0-348`, `0-362`, or image `0-349`), click |
   | `sh_act_sharp_basket` | books | the "Add to basket" button of "Sharp Objects", `0-433`. One of 20 identical buttons, so a disambiguation test. Same captured tree, with only the action string swapped in the `buildActPrompt` template |
   | `sh_act_negative` | books | "click the 'Log out' button": `action` must be `null` |
   | `sh_act_dropdown` | herokuapp `/dropdown` | `0-77`, `selectOptionFromDropdown`, `["Option 2"]` |
   | `sh_act_type` | herokuapp `/inputs` | `0-218`, fill/type, `["42"]` |
   | `sh_extract_books` | books | all 20 titles and prices |
   | `sh_extract_quotes` | quotes | all 10 quotes and authors |
   | `bu_step_poetry` | books | Browser-Use's real step-1 request (24.6 KB system prompt, 14 KB `agent_output` schema, about 8.5k prompt tokens). Correct is `click` index 347 (Poetry) |
   | `v_extract_ratings` | books | Stagehand's extract-with-screenshot prompt shape (`buildExtractSystemPrompt(includeScreenshot=true)`) plus a 1280x1024 PNG. Asks for star ratings, which exist only as pixels and a CSS class, not in the accessibility tree. Answer 3, 1, 1, 4 |
   | `v_click_coords` | books | Coordinate grounding: return pixel x,y for "Add to basket" of Sharp Objects. Bounding box x 1040-1235, y 773-807. Also checked whether the answer is right when read as 0-1000 normalised |

5. **Extras:**
   - `tools_step.py`: one OpenAI tools call (`tool_choice: required`), using the Browser-Use
     browser_state message as context.
   - `routing_probe.py`: GLM reasoning switch-off and provider pinning.
   - `glm_temp.jsonl` and `glm_effort.jsonl`: extra GLM runs, low vs high effort and temperature 0.
   - Live multi-step Browser-Use runs (`run_bu_live.sh`, `raw/bu_live/`).

Model configs: the fastest sensible reasoning setting for each model. Reasoning is off where the
model allows it and low where it is mandatory. GLM was also run at `high`.

## Results: Stagehand + Browser-Use text tasks (3 runs each, `raw/main.jsonl`)

| config | open weights (license) | schema-valid | correct (27) | act+observe (18) | extract mean | BU step (3) | p50 s | p90 s | measured $/call | uncached list $/call |
|---|---|---|---|---|---|---|---|---|---|---|
| **glm-5.3-flash @low** | yes (MIT) | 25/27 | 24 | 15 | 1.00 | 3/3 | 1.88 | 6.62 | 0.00076 | 0.00091 |
| glm-5.3-flash @high | yes (MIT) | 27/27 | 27 | 18 | 1.00 | 3/3 | 1.58 | 3.42 | 0.00060 | 0.00091 |
| qwen3.8-flash @off | yes (qwen-community-1.0) | 27/27 | 27 | 18 | 1.00 | 3/3 | 2.43 | 8.88 | 0.00041 | 0.00085 |
| deepseek-v4.1-flash @off | yes (MIT) | 27/27 | 26 | 17 | 1.00 | 3/3 | **1.09** | 2.11 | 0.00063 | 0.00098 |
| deepseek-v4.1-flash @low | yes (MIT) | 27/27 | 25 | 16 | 1.00 | 3/3 | 2.11 | 5.62 | 0.00081 | 0.00128 |
| gpt-oss-120b @low | yes (Apache-2.0) | 27/27 | 25 | 18 | 0.67 | 3/3 | 3.02 | 9.84 | 0.00028 | 0.00028 |
| gemma-4-31b (default, no reasoning) | yes (Apache-2.0) | 25/27 | 25 | 16 | 1.00 | 3/3 | 4.34 | 20.40 | 0.00067 | 0.00067 |
| nemotron-3.5-lightning @off | yes (openmdw-1.1) | 27/27 | 24 | 15 | 1.00 | 3/3 | 0.95 | 2.46 | 0.00031 | 0.00033 |
| mimo-v2.6-flash @off | yes (MIT) | 27/27 | 23 | 14 | 1.00 | 3/3 | 4.69 | 14.84 | 0.00034 | 0.00076 |
| mistral-small-2603 @none | yes (Apache-2.0) | 7/27 | **unmeasured**: 20/27 calls got 429 "temporarily rate-limited upstream" (single provider: Mistral) | | | | | | | |
| REF (closed) gpt-6-luna @none | no | 20/27 | 20 | 18 | 0.00* | 2/3 | 1.23 | 2.25 | 0.00028 | 0.00027 |

\* gpt-6-luna is the closed-model reference. OpenAI's strict mode **rejects the Stagehand Python
SDK's extract schema** (`"additionalProperties": {}` on pydantic objects: "schema must have a 'type'
key"), so both extracts were 400s. Open-model providers accepted the schema as-is.

"Uncached list $/call" is the measured token counts times the serving endpoint's list price,
computed by `costs.py` (`raw/summary_costs.md`). The bench replays identical prompts, so 35-78% of
prompt tokens were served from provider prompt caches. **In production, Stagehand puts the
instruction before the tree, so most act/observe/extract calls are uncached. Use the uncached
column for projections.**

Uncached cost per call for GLM 5.3 Flash @low:

| call | GLM uncached $ |
|---|---|
| act or observe, 6k-token page | 0.0009-0.0013 |
| act, 0.9k-token page | 0.00015 |
| 20-item extract, plus its metadata call | 0.0011 + 0.00012 |
| Browser-Use step (prefix-cacheable, 24 KB system prompt) | 0.0014 |

Per task (correct/3, p50 s): see `raw/summary_main.md`. Notable failures:

- **GLM 5.3 Flash (all GLM runs together, `raw/summary_glm_all.md`; n=72 at low, 52 at high, 20 at
  low with temperature 0):**
  - **4 runaways**: `finish_reason=length` after 8,000 tokens, 34-52 s and about $0.004 each. They
    hit 2 of 72 calls at low, 1 of 20 at low with temperature 0, and 1 of 52 at high, on providers
    Together and Friendli.
  - **Every runaway is the same failure.** Constrained decoding degenerates inside the free-string
    `arguments` array of the act schema (`"arguments": ["left", "", "", "" , ...`).
  - Related junk in `arguments` that still validated: `["],", "twoStep}} 2:false} jedoch", ...]` and
    `["LEFT"]`.
  - One false `null` on the dropdown act.
  - Temperature 0 did not prevent runaways.
  - Low vs high effort is within noise. On the 5x hard-task rerun (`glm_effort.jsonl`) both scored
    24/25. High costs about 25% more and adds about 0.1-0.4 s at p50.
  - The browser-box README's "cut its own JSON off at the 4,096-token limit" is very likely this same
    failure.
- **Nemotron 3.5 Lightning** returned an element instead of `null` on the impossible
  "click 'Log out'" act in 2 of 3 runs. It fabricates clicks.
- **gpt-oss-120b** returned truncated lists on extract (1 or 2 items instead of 10 or 20) in 2 of 6
  runs.
- **Gemma 4 31B** had 2 whitespace runaways on the tiny inputs page, each about 350 s (DeepInfra), and
  a p90 of 20 s.
- **MiMo V2.6 Flash** picked the `<option>` instead of the `<select>`, returned `null` on a valid
  act, and put category names into the click arguments.
- **DeepSeek V4.1 Flash** returned 2 false `null`s, on the 20-identical-buttons act and the book link.

## Results: vision (3 runs each, `raw/vision.jsonl`)

| config | star ratings from screenshot (4 books) | pixel click on the right button | notes |
|---|---|---|---|
| **glm-5.3-flash @low** | **3/3** | **3/3** (1135-1137, 789-790) | real pixel coordinates; p50 1.1-2.1 s |
| mimo-v2.6-flash @off | 3/3 | 2/3 | the miss was 0-1000-normalised (887,774) |
| qwen3.8-flash @off | 3/3 | 0/3 | 2/3 answered 0-1000-normalised (887,769, which would be right if rescaled); 1/3 echoed the schema instead of an object |
| deepseek-v4.1-flash @off | 1.75/3 (partial ratings) | 0/3 | 1 normalised; 2 missed by 3 px (y=770 vs box top 773) |
| gemma-4-31b | 1/3 (partial) | 0/3 | wrong place (882,748) |
| REF gpt-6-luna @none | 3/3 | 0/3 valid | coordinates right, but it wrote prose before the JSON in strict mode (not enforced) |

## Results: one OpenAI tools step (`raw/tools.jsonl`, `tool_choice: required`)

Every model called `click(index=347)` 3/3, with these exceptions and notes:

- **qwen3.8-flash**: 404 "No endpoints found that support the provided 'tool_choice' value" for
  `tool_choice: required` (Alibaba is its only provider). It went 3/3 with `tool_choice: auto` at
  p50 7.2 s.
- p50: DeepSeek 0.49 s, Nemotron 0.38 s, GLM 0.91 s, gpt-oss 1.03 s, luna 1.05 s, MiMo 2.06 s,
  Gemma 2.18 s.
- Browser-Use 0.13.11 itself does **not** use tools. It sends one strict `json_schema`
  `response_format` (`agent_output`) per step. So what gates a Browser-Use model is json_schema
  support, not tool support.

## Results: OpenRouter behaviour for GLM 5.3 Flash (`raw/routing_probe.jsonl`)

- **Reasoning cannot be turned off.**
  - `reasoning: {enabled:false}` and `reasoning: {effort:"none"}` both return HTTP 400 "Reasoning is
    mandatory for this endpoint and cannot be disabled."
  - With no reasoning parameter, it runs at `max`. A 0.9k-token act used 91 reasoning tokens.
  - At `low` the mean was about 1 reasoning token per Stagehand call; at `high`, about 15.
- **Endpoints without structured-output support are filtered out of json_schema requests.** Pinning
  the request to `z-ai` (first party), `relace` or `novita` with `allow_fallbacks:false` returned 404.
  OpenRouter's message named the filter: "Filter by Parameters removed relace, streamlake/fp8,
  novita/fp8, gmicloud/fp8, atlas-cloud/fp8, siliconflow/fp8, z-ai/fp8". This happened **with and
  without** `require_parameters` (one observation on 2026-10-09). Keep `require_parameters: true`
  anyway: the official docs recommend it.
- `response_format: json_object` instead of json_schema produced a wrongly shaped object (no
  `action` wrapper, `arguments` as a string). Strict json_schema matters.

## Results: live multi-step Browser-Use (`raw/bu_live/`, `run_bu_live.sh`)

3 runs per model per task, max 8 steps, local headless Chrome.

Tasks:

- **q**: "Go to https://quotes.toscrape.com/, use the Next button to go to page 3, and report the
  author of the first quote on page 3." Correct answer: Pablo Neruda.
- **d**: "Go to https://the-internet.herokuapp.com/dynamic_loading/2, click Start, wait, and report
  the exact text." Correct answer: Hello World!

Model settings:

- GLM uses browser-box's exact config: `ChatOpenAI(base_url=OpenRouter)` +
  `reasoning_models=[model]`, `reasoning_effort=low`.
- DeepSeek V4.1 Flash uses `ChatOpenRouter` with `extra_body` set to
  `{reasoning:{enabled:false}, max_tokens:4096, provider:{require_parameters:true}}`.

Wall time includes launching Chrome and the page's own 5 s loading wait. "LLM s" is the sum of the
model calls' latency.

| model | correct | median steps | median LLM s / task | median wall s / task | $ total (6 runs) | finish=length |
|---|---|---|---|---|---|---|
| z-ai/glm-5.3-flash @low (box config) | **6/6** | 4 | 5.7 | 36.6 | 0.0144 | 0 |
| deepseek/deepseek-v4.1-flash @off | **6/6** | 4.5 | 8.8 | 48.7 | 0.0211 | 0 |

Per run: `raw/bu_live/summary.md`. GLM traffic was served by Friendli, Parasail, Together,
Fireworks, BaseTen, Inceptron and InferenceNet, all with valid output.

Both are easy public tasks. They do **not** re-test the multi-step failures the browser-box README
reported for GLM (URL typing, SPA shadow roots). Treat the Browser-Use evidence as "fine on simple
multi-step", not as proven on hard SPAs.

## Reproduce

```bash
PY=<scratch>/py/.venv/bin/python   # stagehand 4.2.0, browser-use 0.13.11
D=<scratch dir with data/: captures/, bu_request_01.json, ground_truth.json, vision_truth.json, books_viewport.png>
$PY capture_stagehand.py <out>                      # needs OPENROUTER_API_KEY in env or browser-box/.env
$PY capture_browseruse.py <out> [model] [steps] [box|or-off] [task]
OUT_DIR=<dir> node screenshot.mjs                   # playwright-core from <scratch>/npm
$PY bench.py $D main.jsonl 3 all text 0.55
$PY bench.py $D vision.jsonl 3 "glm-5.3-flash@low,mimo-v2.6-flash@off,qwen3.8-flash@off,deepseek-v4.1-flash@off,gemma-4-31b@default,REF-closed:gpt-6-luna@none" vision 0.15
$PY bench.py $D glm_effort.jsonl 5 "glm-5.3-flash@low,glm-5.3-flash@high" "sh_act_book_link,sh_act_sharp_basket,sh_act_dropdown,sh_observe_categories,bu_step_poetry" 0.1
$PY tools_step.py $D tools.jsonl 3 "z-ai/glm-5.3-flash@low,..."
$PY routing_probe.py $D routing_probe.jsonl
python3 summarize.py main.jsonl ; python3 costs.py <endpoints dir> <glm endpoints json> main.jsonl ...
$PY orkey.py <tag> spend.jsonl                      # spend snapshot, never prints the key
```

## Caveats

- n=27 per model (3 runs x 9 tasks). A gap like 27/27 vs 24/27 is not statistically significant.
  GLM has the most samples (144 structured calls), so its rare failures are the most visible.
  Do not read the others' clean runs as "never runs away": Gemma did, for about 6 minutes.
- The bench used `max_tokens` 8000. **Stagehand's client-callback path sends no token cap unless your
  callback sets one.** Unbounded, a runaway could run to the endpoint's limit (131k-944k tokens for GLM).
- Latency includes OpenRouter routing and the network from macOS. Runs 2 and 3 of each task partly
  benefit from provider prefill caching.
- Vision used one viewport (1280x1024, DPR 1). Pixel coordinates at other sizes or DPRs are untested.
  - GLM's model card says its own visual benchmarks resized images so the shorter side is at least
    1.5K px.
  - What each OpenRouter provider does to images before inference is not documented.
