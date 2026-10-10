# Browser-Use spike results (rerun, 2026-10-10 UTC)

Agent: browser-use deep-dive (rerun after the first attempt hit a usage limit).
Library: browser-use **0.13.11** in `<scratch>/py/.venv` (identical to the clone @ c75e8476 apart from
READMEs/tests: `diff -rq`), cdp-use 1.4.5, bubus 1.5.6, openai 2.26.0.
Browser: self-hosted Steel, `ghcr.io/steel-dev/steel-browser-api:latest` (image 7a161b95e8a9, pulled 2026-09-16),
own containers `fleet-spike-browseruse` (127.0.0.1:3302) and `fleet-spike-browseruse2` (127.0.0.1:3303),
`--memory 1536m --cpus 1.2`, removed by an EXIT trap in `with_steel.sh` after every batch.
Model: `z-ai/glm-5.3-flash` on OpenRouter via `ChatOpenAI(..., reasoning_models=[model], reasoning_effort="low")`
(the browser-box runner shape). Decision model: `typesafe/jev-1.13` via `POST https://openrouter.ai/api/v1/systemone`.
Pages: books.toscrape.com, quotes.toscrape.com, example.com only.

## Files

- `spike_bu.py` subcommands: `keyusage`, `task`, `replay`, `decider`, `direct`, `persist`, `conc` (docstring at top).
- `run.sh` loads `OPENROUTER_API_KEY` from `browser-box/.env` into the child process env only.
- `with_steel.sh` starts the spike Steel container(s), waits for `/v1/health` **and** a real CDP round trip
  (`Browser.getVersion` over `ws://127.0.0.1:<port>/`), runs the command, and always `docker rm -f`s them.
- Raw JSON outputs: `<scratch>/spikes/browser-use/run2/*.json` (not committed; numbers copied below).

## 1. End-to-end agent runs (task: "On https://books.toscrape.com find the price of the first book in the Poetry category", truth £51.77)

Modes: **baseline** = browser-box `AGENT_OPTIONS` (`use_vision=False, use_judge=False, max_failures=3,
llm_timeout=90, step_timeout=120, calculate_cost=False, directly_open_url=True`); **flash** = baseline +
`flash_mode=True`; **defaults** = Browser-Use defaults (`use_vision=True`, `use_judge=True`,
`enable_planning=True`). `max_steps=8` everywhere. Cost = OpenRouter `/generation` `total_cost` per call (billed).

| run | mode | steps (history) | LLM step calls | all LLM calls | wall s | LLM s | prompt tok | completion tok | billed USD | correct | providers | prompt tok / step |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| task_base1 | baseline | 3 | 2 | 2 | 14.6 | 6.64 | 16820 | 329 | 0.001342 | True | InferenceNet | 8410 |
| task_base2 | baseline | 3 | 2 | 2 | 8.6 | 3.91 | 16552 | 334 | 0.00265 | True | Together | 8276 |
| task_base3 | baseline | 3 | 2 | 2 | 8.0 | 3.2 | 16234 | 239 | 0.002555 | True | Friendli,Parasail | 8117 |
| task_flash1 | flash | 3 | 2 | 2 | 5.5 | 2.01 | 7008 | 145 | 0.001124 | True | Together | 3504 |
| task_flash2 | flash | 3 | 2 | 2 | 7.7 | 2.54 | 7001 | 148 | 0.000839 | True | InferenceNet,Venice | 3500 |
| task_defaults1 | defaults | 3 | 2 | 3 | 12.5 | 8.11 | 28285 | 394 | 0.003601 | True | BaseTen,Fireworks,Reka | 10760 |

- 6/6 correct. Every run: step 1 = `navigate` with **no LLM call** (`directly_open_url` pulls the URL out of
  the task text), step 2 = LLM picks `click(index)` on "Poetry", step 3 = LLM answers `done` from the page state.
- Reasoning tokens 0-8 per call: `reasoning_effort=low` was sent on every call (`reasoning_effort_sent: "low"`).
  `max_completion_tokens` 4096 sent on every call. `finish_reason` always `stop`.
- **Flash mode cut prompt tokens per step 58%** (8.1-8.4k -> 3.5k), because Browser-Use swaps the 24 KB
  `system_prompt.md` for the 2.4 KB `system_prompt_flash.md` and drops thinking/evaluation/next_goal fields.
- **Defaults cost 2.7x baseline** on this task: screenshots add ~2.5k prompt tokens per step (request body
  346-416 KB vs 33 KB) and the judge adds a 3rd call (6.8k tokens, images included).
- Same tokens, different price: OpenRouter routed GLM to InferenceNet ($0.00066/step) or Together ($0.0013/step).
- This task is easy (2 LLM steps). It proves wiring, cost per step and the no-LLM navigate; it is not an
  accuracy benchmark. The reasoning-models dossier already measured GLM step accuracy; not repeated here.

## 2. Decider behind the `BaseChatModel` protocol (rerun of the first attempt's spike)

`decider1.json`: a scripted, non-generative stand-in for a decision model passed as `Agent(llm=...)`, plus a
guardrail in `register_new_step_callback` that rewrites the proposed action before it executes.
4 steps, 3 "model" calls, **0 HTTP calls to any LLM**, correct (£51.77), 11.9 s wall. The stand-in picked
"Travel" on purpose; the callback swapped it to "Poetry" (`click 221 -> click 368`) and the swapped action is
the one that ran. Same result as the interrupted attempt (`decider.json`: 4 steps, 0 calls, correct).
This proves the hook points exist; it is a different pattern from the "selector_map -> decider -> Tools.act"
claim, which is tested next.

(sections 3+ appended below as runs finish)

## 3. The System 1 claim, tested directly: selector_map -> decision model -> `Tools.act`, no Agent, no chat model

`spike_bu.py direct` (runs `direct3`, `direct4`; earlier `direct1/2/dbg` made the same decision but hung at exit,
see section 7). Sequence, all in one process, no `Agent` object, no `BaseChatModel` object:

1. `tools.act(navigate https://books.toscrape.com/)` (code-chosen URL).
2. `get_browser_state_summary(include_screenshot=False)`: **104-132 ms**, `selector_map` = **201** interactive nodes.
3. Candidates = selector_map entries with a visible label, de-duplicated: **70** (+ `none`) = 71 options (under
   Jev's ~180 and Decider's 255 caps on this page; a social feed will not be, see dossier).
4. One `POST https://openrouter.ai/api/v1/systemone`, model `typesafe/jev-1.13` (served `typesafe/jev-1.13-20260917`,
   provider TypeSafe), question "Which element ... should be clicked next", command "Open the Poetry category".
   **315-388 ms**, choice `e365`/`e366` = `link "Poetry"`, confidence 0.94 / 0.96 (runner-up `none` 0.05 / 0.04).
   Usage 2,732 input tokens, **$0.000115** per decision.
5. `tools.act(ActionModel(click={"index": 365}), browser_session=b, page_extraction_llm=None)` -> "Clicked a "Poetry"",
   URL now `.../poetry_23/index.html` (949-1219 ms incl. page load).
6. `tools.act(find_elements{selector: "article.product_pod p.price_color"})`: 65-431 ms, first price **£51.77** (correct).

Whole flow 6.5-8.8 s wall, **0 chat/completions calls**, $0.000115 total. `ActionModel` came from
`tools.registry.create_action_model()` (`tools/registry/service.py:519`); `Tools.act` is at `tools/service.py:2178`.
**Verdict: the claim holds** for actions whose arguments are an index (click) or code-supplied values
(navigate URL, CSS selector, text to type).

Stale-index test (same run): after the click to Poetry, `tools.act(click{index: 219})` where 219 was "Travel" in the
**home page** map and no state refresh happened. Result: **no error**; it returned `Clicked a "Travel"` and the
browser went to `travel_2`. `DOM.describeNode(backendNodeId=219)` still resolved to an `<a href=".../travel_2/...">`,
and the Travel link sits at the same viewport position (410, 277) on both pages. Index 219 is **not** in the
refreshed selector map. So Browser-Use does not refuse a stale index; here the identical sidebar made it land on
the "same" link. On a page whose layout changed, the same call would act on whatever is there. An executor
must re-capture state right before each act and check the node's label/href against what the decider chose.

## 4. Replay (`Agent.load_and_rerun`) - does it avoid LLM calls?

History = `hist_base2.json` (3 steps: navigate, click Poetry, done). Before each replay the browser was parked on
`https://example.com/` so the end URL proves re-execution.

| run | summary_llm | wall s | LLM calls | billed USD | URL after replay | element match |
|---|---|---:|---|---:|---|---|
| replay1 | default (agent's GLM) | 10.0 | 1 x `rerun_summary` (3,049 prompt tokens, **with screenshot**) | 0.000176 | poetry_23 | `index 364 -> 360 (EXACT)` |
| replay2_stub | local stub object | 6.2 | **0** | 0 | poetry_23 | `index 364 -> 366 (EXACT)` |

- Clicks were re-executed (example.com -> books -> poetry_23), with the index remapped by element hash.
- The replayed `done` action **re-emits the original run's answer text** (results[2] is the stored string).
  Replay does not re-read the page unless the history contains an `extract` action (that one re-runs as an LLM
  "AI step"). A data task replayed this way returns stale data.
- `rerun_history` calls `self.close()` in its `finally` (`agent/service.py:3282`).
- Passing any object with `ainvoke` as `summary_llm` removes the last LLM call.

## 5. Persistence

### 5a. Browser-Use `storage_state` across a real browser reset (`persist1.json`)

Steel `POST /v1/sessions/release` tears Chromium down and relaunches an idle one with a cleaned
`/tmp/steel-chrome` (`session.service.ts` `endSession`, `cdp.service.ts:1397`; Steel log "Cleaning up files before
browser launch").

| check | result |
|---|---|
| run 1 sets cookie + localStorage on quotes.toscrape.com, then on books.toscrape.com, `stop()` | file written on stop (not before): cookies **both** origins; localStorage **books only** |
| negative control after release, no storage_state | cookies none, localStorage none (reset is real) |
| run 2 after another release, `Browser(cdp_url=..., storage_state=FILE)` | cookies restored for **both** origins; localStorage restored for **books only**; quotes localStorage **lost** |
| set `fleet_ls_books=v2` then reload | cookie keeps v2, **localStorage reverts to v1** (the restore init-script re-runs on every new document) |
| `BrowserSession.export_storage_state()` | cookies only, `origins: []` |

Mechanism (source): `_cdp_get_origins` collects storage only for origins in the **focused tab's frame tree** at
save time (`session.py:3576-3649`); restore is `Page.addScriptToEvaluateOnNewDocument` per origin on the focused
target (`storage_state_watchdog.py:269-307`), which overwrites live values on every load. IndexedDB is never
captured. Auto-save runs every 60 s only when cookies changed (`session.py:1733-1747`).

### 5b. `user_data_dir`

- Remote CDP (Steel/Browserbase): Browser-Use never launches Chrome, so `user_data_dir` does nothing for
  persistence. It still gets a temp dir: `Browser(cdp_url=...)` yields `user_data_dir=/var/folders/.../browser-use-user-data-dir-XXXX`
  (hands-on, `pure_checks`), which switches on the StorageStateWatchdog (60 s cookie polling) for every session.
- Local launch trap (hands-on, no browser needed): `BrowserProfile(user_data_dir=".../chrome-profile-1")` and
  `.../Chrome` come back as a **temp copy** (`browser-use-user-data-dir-*`); so does any dir with `channel="chrome"`.
  `.../profile-1` is used in place. Cause: `_copy_profile()` copies when the path contains "chrome"
  (`profile.py:849-904`). Logins made in such a run are written to the temp copy and lost.

### 5c. Persistence held by the browser host: Steel `userDataDir` (`steelprofile1.json`, `steelprofile2.json`)

Browser-Use only drives; Steel holds the profile. Each step = `POST /v1/sessions {...}` then
`Browser(cdp_url="ws://127.0.0.1:3302/")`, set cookie + localStorage on quotes and books, then `POST /v1/sessions/release`.

| step | wait before release | cookies read back | localStorage read back |
|---|---:|---|---|
| A write (`userDataDir: /tmp/fleet-profile-A`) -> release -> control session `{}` | 2 s | none | none (control is clean) |
| ... -> new session `userDataDir: /tmp/fleet-profile-A` | 2 s | **none (lost)** | both origins |
| ... -> new session `userDataDir: /tmp/fleet-profile-B` (different path) | 2 s | none | **A's values** |
| repeat, A write | **40 s** | **both origins** | both origins |
| ... -> `userDataDir: /tmp/fleet-profile-B` | 40 s | **A's cookies** | **A's values** |

- Steel-held profile keeps localStorage for every origin (unlike Browser-Use storage_state), and cookies too,
  **but only cookies Chromium had flushed to disk**: released 2 s after the write, the cookies were gone; after
  40 s they survived (Chromium commits its cookie store on a timer; n=1 each). Rule for the fleet: do not release
  a profile's browser within ~30 s of a login or cookie change, or snapshot cookies over CDP as a backup.
- **Any** `userDataDir` (or `persist: true`) maps to one fixed directory in self-hosted Steel: profile B read
  profile A's data. Source: `session.service.ts:180-183`
  (`options.userDataDir || options.persist === true ? path.join(..., "user-data-dir") : env.CHROME_USER_DATA_DIR || tmp/steel-chrome`).
  So one Steel container (or one mounted volume per wake-up) per profile. Details belong to the Steel dossier.

### 5d. Harder task + its replay (`task2_*`, `replay_t2`)

Task: "open the Poetry category, open the first book listed there, and report its UPC and how many copies are in
stock" (truth: UPC a897fe39b1053632, 22 in stock).

| run | mode | steps | LLM calls | wall s | prompt tok (cached) | billed USD | correct |
|---|---|---:|---:|---:|---:|---:|---|
| task2_base1 | baseline | 4 | 3 | 20.7 | 26,038 (4,480) | 0.002423 | yes |
| task2_base2 | baseline | 4 | 3 | 14.9 | 23,389 (4,096) | 0.003269 | yes |
| task2_flash1 | flash | 4 | 3 | 11.1 | 8,167 (0) | 0.001344 | yes |
| replay_t2 (of task2_base1) | replay | 4 replayed | 1 (summary) | 13.7 | 2,869 | 0.000475 | ended on the product page; clicks remapped `363->366`, `2227->2223` (EXACT) |

GLM read UPC and stock from the DOM state, so no `extract` action (and no replay "AI step") occurred in any run.

## 6. Concurrency (`conc1.json`, two Steel containers, scripted LLM so no spend)

| configuration | result |
|---|---|
| 2 BrowserSessions, 2 browsers, each in its own thread + event loop, 4 nav/state rounds | both OK (6.6 s) |
| 2 BrowserSessions, 2 browsers, one event loop | both OK (8.7 s) |
| 2 Agents, 2 browsers, own threads/loops | both correct (6.5 s) |
| 2 Agents, 2 browsers, one loop | both correct (7.4 s) |
| 2 Agents, **same** browser, one loop | both correct (8.1 s) |

At process exit: 16 x "Task was destroyed but it is pending" (bubus `EventBus._run_loop`,
`StorageStateWatchdog._monitor_storage_changes`) and 4 x cdp_use "Event loop is closed". Not reproduced in
these short runs: the bubus cross-loop capacity bug (#5509, open; fix PR browser-use/bubus#34 unmerged; bubus
pinned 1.5.6) and browser-box's "attached to a different loop". A pass at 2 agents x 6 steps is "not
reproduced", not "safe".

## 7. Hangs and exits

- `direct1`, `direct2`, `direct_dbg` finished every step (decision call recorded, all steps "ok" in the trace)
  and then **hung in `asyncio.run()` teardown** until the hard timeout, because a `keep_alive=True` session's
  background tasks (bubus run loop, CDP reader) never finish. Fixed in the spike the same way browser-box's runner
  does it: write the result and `os._exit()` from **inside** the loop. After that change, 0 hangs.
- First connect right after container start failed once with "did not receive a valid HTTP response" followed
  by "Root CDP client not initialized" (Steel log: "WebSocket endpoint not available. Ensure the browser is launched
  first"). `/v1/health` answers before Chromium is reachable; `with_steel.sh` now also probes a CDP round trip.
  So browser-box's "Root CDP client not initialized" is the follow-on message of a failed or dropped CDP
  connection (also open upstream as #6005 for the stop path).

## 8. browser-box runner self-check against 0.13.11 (scratch copies, `python -I`)

- `runner.py --self-check` as committed: `self-check failed: RuntimeError: browser-use 0.13.11 is installed;
  the confinement here is written against 0.13.10`, exit 1.
- Copy with only `PINNED = "0.13.11"` changed (`diff` confirms one line): `self-check ok`, exit 0: every patched
  method still exists, every Agent option is still accepted, `upload_file`/`save_as_pdf` still exist.
- GitHub compare 0.13.10...0.13.11 (138 commits): `session_manager.py`, `downloads_watchdog.py`,
  `permissions_watchdog.py`, `aboutblank_watchdog.py` unchanged; `session.py` +2 lines (cloud start guard).
- Pure checks: `BrowserSession(browser_profile=BrowserProfile(cdp_url=X, is_local=False)).is_local` is **True**
  (the browser-box form); `Browser(cdp_url=X).is_local` is False.

## 9. Spend (OpenRouter, one shared key)

- Sum of billed per-call costs for this rerun: **$0.0204** (24 GLM chat calls $0.0198 + 5 Jev decisions $0.00057).
- Key usage delta over this rerun: $0.0259. The key is shared with sibling research
  agents running at the same time, so the delta is an upper bound; the per-call sum is this agent's spend.
- The interrupted first attempt's spend is not recoverable from its outputs (its saved runs made 0 LLM calls).
- Cap $0.60: used about 3.4-4.3%.

## 10. Deviations

- One read-only `docker exec browser-box-agent-browseruse-1 python -c "<print versions>"` was run by mistake to read the
  live container's openai/browser-use versions (2.26.0 / 0.13.10). Nothing was changed; the brief puts those
  containers off-limits, so it is reported here. No other live container, port or the live box was touched.
- Spike containers: `fleet-spike-browseruse` and `fleet-spike-browseruse2`, created and removed per batch by the
  `with_steel.sh` trap. `docker ps -a` shows neither after the last batch.
