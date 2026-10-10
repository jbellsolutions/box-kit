> **Read with its verification report.** [verification/browser-use.md](../verification/browser-use.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: Browser-Use (OSS 0.13.11) as the fleet's backup agent

- Agent: browser-use deep-dive. This is a rerun; the first attempt hit a usage limit.
- Research date: 2026-10-09/10 (spikes ran 2026-10-10 UTC).
- Source: browser-use @ `c75e8476` (0.13.11, 2026-10-07). It is identical to the shared venv's installed package
  (`diff -rq` differs only in READMEs/tests).
- Spike: `fleet/research/spikes/browser-use/` (`spike_bu.py`, `run.sh`, `with_steel.sh`, `RESULTS.md`).
- Spend: **$0.0204** of the $0.60 cap. Containers left running: none.
- Provenance tags follow BRIEF.md: `hands-on`, `source-code`, `official-docs`, `vendor-claim`, `third-party`, `unverified`.

## 1. Verdict

1. **Browser-Use OSS works as the open-ended backup agent on self-hosted Steel. Attach with `Browser(cdp_url="ws://<steel>:3000/")`.**
   - Hands-on: GLM 5.3 Flash @low over OpenRouter, driving Steel.
   - 9/9 runs correct on two public tasks.
   - 2-3 LLM steps each, 5.5-20.7 s wall, **$0.0008-0.0036 per task**.
   - `flash_mode=True` cut prompt tokens per step by 58% (8.2k to 3.5k).
   - It is MIT, pure CDP (`cdp-use` + `bubus`), and has no Playwright dependency. `source-code`
2. **The System 1 claim is proven.** The chain is: `get_browser_state_summary()` gives `selector_map`, a real decision call picks an index, and `Tools.act(click{index})` executes it. There is no Agent and no chat model in the loop. `hands-on`
   - Jev 1.13 via OpenRouter `/systemone` picked "Poetry" out of 71 candidates at 0.94-0.96 confidence, in 315-388 ms, for $0.000115.
   - The click and a CSS `find_elements` read gave the correct price. **0 chat/completions calls.**
   - Two caveats the fleet must engineer around:
     - **Option caps vs page size:** 201 raw nodes became 70 labelled ones here; a social feed will exceed Jev's ~180.
     - **Index freshness:** a stale index from the previous page was **executed, not refused**.
3. **Persistence must live in the browser host, not in Browser-Use.**
   - Browser-Use `storage_state` restored cookies across a real browser reset. It lost localStorage for every origin except the focused tab's, and its restore script **reverted a newer localStorage value on reload**. It never captures IndexedDB. `hands-on` + `source-code`
   - Steel's own `userDataDir` kept cookies and localStorage for all origins. Two catches:
     - Cookies written <30 s before release were lost.
     - Self-hosted Steel maps **every** `userDataDir` to one directory, so one profile per container/volume.
4. **The browser-box confinement patches are not needed for a one-browser-per-profile fleet.** What is still needed:
   - **Code that still applies:** the version-pin self-check, the `reasoning_models=[model]` trick, exiting from inside the event loop, and `exclude_actions`.
   - **New fleet controls:** a per-profile engine mutex (Stagehand, Browser-Use and the human viewer can all reach the same browser), plus permissions and downloads settings.

   Evidence for the patch status:
   - The patched code did not change between 0.13.10 and 0.13.11.
   - The runner's self-check refuses 0.13.11 only because of the version string. A copy with `PINNED` bumped passes every check. `hands-on` + GitHub compare.
5. **Replay exists in OSS (`save_history` / `load_and_rerun(variables=...)`) and re-executes clicks deterministically.**
   - It remaps element indexes by element hash.
   - It still makes 1 LLM call (an end summary with a screenshot) unless you pass a stub `summary_llm`; then it makes **0**. `hands-on`
   - It replays the **old `done` text**, so it is not a data refresh.
   - Browser-Use "skills" are a **retired Cloud** feature that sends the browser's cookies to Browser Use's API. Do not use them. `source-code` + `official-docs`
6. **Stealth, fingerprinting, CAPTCHA solving, residential proxies and profile sync are Browser Use Cloud only.** `official-docs` + `source-code`
   - OSS has launch-flag hygiene only. Its `ProxySettings.server` is ignored on a remote CDP browser, so the proxy must be set on the Steel session.
   - Cloud fingerprints are "randomized per session", which is the opposite of the fleet's same-identity requirement.
7. **`allowed_domains` is not a security boundary** (open issues #5815, #4763). Do not rely on it for client accounts; enforce egress policy at the proxy/Steel layer. `third-party` (upstream issues), consistent with `source-code`.
8. **Process model: one Browser-Use agent per OS process, with a hard kill timer.** `hands-on`
   - Leaving a `keep_alive` session open made `asyncio.run()` hang forever at exit, 3 times out of 3, until the spike exited from inside the loop.
   - Two agents in one process (one loop or two threads, two browsers or even one shared browser) worked in a short test.
   - The bubus cross-loop capacity bug (#5509, fix unmerged) is the known risk at scale.

## 2. Answers

### Q1. Version, license, architecture, core classes and exact parameters

- **Version:** 0.13.11, released 2026-10-07. It is the shared venv and clone @c75e847. `hands-on` (`importlib.metadata`).
- **Dependencies:** pins `cdp-use==1.4.5`, `bubus==1.5.6`, `openai==2.26.0`, `browser-harness==0.1.13`, `browser-use-sdk==3.4.2`, `mcp==2.1.1`.
- **License:** MIT (`LICENSE`, pyproject classifier). `source-code`
- **Architecture:**
  - Pure CDP through `cdp-use` (`TimeoutWrappedCDPClient`, `session.py:1898-1905`).
  - A `bubus` event bus plus "watchdogs": downloads, about:blank, permissions, storage_state, security, popups, crash, captcha, dom, screenshot, recording and HAR.
  - **No Playwright** in `dependencies`. Playwright appears only in comments and option names borrowed from its API. `source-code`
- **Classes:**
  - `Agent`.
  - `BrowserSession`; `Browser` is an alias of it.
  - `BrowserProfile`, a pydantic model of launch/context/connect options.
  - `Tools` (alias `Controller`).
  - Chat classes (Q2). `source-code` `browser_use/__init__.py`
- **Exact parameters** (`BrowserSession.__init__`, `session.py:262-330`; `BrowserProfile`, `profile.py:585-735`). `source-code`

| Need | Parameter | Notes |
|---|---|---|
| Attach to existing browser | `cdp_url: str` | `ws://...` or `http://host:9222` (it resolves `/json/version`). **Pass it directly**: `BrowserSession(browser_profile=BrowserProfile(cdp_url=X, is_local=False))` comes out `is_local=True`, which changes upload/download paths (`session.py:400-404`, hands-on `pure_checks.json`). browser-box's runner uses that form |
| Local launch | `executable_path`, `channel`, `args`, `headless: bool\|None` (env `BROWSER_USE_HEADLESS`, else display detection), `devtools`, `chromium_sandbox` | Irrelevant on Steel |
| Profile dir | `user_data_dir`, `profile_directory='Default'` | **Trap:** a path containing "chrome" or `channel=chrome` is copied to a temp dir and used from there, so logins are lost (`profile.py:849-904`, hands-on). Remote sessions still get a temp `user_data_dir`, which turns on the StorageStateWatchdog (hands-on) |
| Cookie/localStorage file | `storage_state: str\|Path\|dict` | Loaded on connect; saved on stop and every 60 s if cookies changed (Q4) |
| Proxy | `proxy=ProxySettings(server, bypass, username, password)` | `server`/`bypass` are **launch args only** (`profile.py:943`). Over remote CDP only `username/password` are used, by answering `Fetch.authRequired` (`session.py:2040-2152`). So on Steel, set the proxy at Steel session creation (`proxyUrl`) |
| Headless | `headless` | Remote: decided by the host (Steel launches `--headless=new`) |
| Stealth | **none** | No `stealth` option exists. Only `--disable-blink-features=AutomationControlled` and dropping `--enable-automation` on local launch (`profile.py:201,439`). Cloud: `use_cloud=True` / `cloud_profile_id` / `cloud_proxy_country_code` / `cloud_timeout` |
| Domain allow/deny | `allowed_domains`, `prohibited_domains` (globs, sets at 100+ entries), `block_ip_addresses` | Checked only on agent-initiated navigation (issue #5815) |
| Keep browser after run | `keep_alive: bool\|None` | With `True`, `stop()` returns without resetting (`session.py:1294`) |
| Others worth knowing | `permissions` (default `['clipboardReadWrite','notifications']` granted to **all origins**), `accept_downloads=True`, `downloads_path` (a **local** temp path even for remote browsers), `auto_download_pdfs=True`, `enable_default_extensions=True` (uBlock, cookie-banner, ClearURLs; local launch only), `captcha_solver=True` (only waits for Cloud's solver events), `highlight_elements=True`, `wait_between_actions=0.1`, `minimum_wait_page_load_time=0.25`, `cross_origin_iframes`, `max_iframes`, `headers` (CDP connect headers) | hands-on `pure_checks.json` |

### Q2. LLM layer

- **Chat classes** (`browser_use/__init__.py`, `llm/*`). `source-code`
  - The full list: `ChatOpenAI`, `ChatOpenAILike`, `ChatAzureOpenAI`, `ChatOpenRouter`, `ChatAnthropic`, `ChatAnthropicBedrock`, `ChatAWSBedrock`, `ChatGoogle`, `ChatGroq`, `ChatMistral`, `ChatCerebras`, `ChatDeepSeek`, `ChatOllama`, `ChatLiteLLM`, `ChatVercel`, `ChatOCIRaw`, `ChatOrcaRouter`, and `ChatBrowserUse` (Browser Use's hosted model, needs `BROWSER_USE_API_KEY`).
  - All of them implement the `BaseChatModel` protocol (`llm/base.py`): `model`, `provider`, `name`, and `async ainvoke(messages, output_format=None)` returning `ChatInvokeCompletion`.
  - **If `llm=None` and no `DEFAULT_LLM` is configured, Agent silently uses `ChatBrowserUse()`** (`agent/service.py:225-235`).
- **OpenAI-compatible endpoints:**
  - `ChatOpenAI(base_url=...)`, `ChatOpenAILike`, and `ChatOpenRouter` (default `https://openrouter.ai/api/v1`).
  - 0.13.11 changed `ChatOpenRouter.extra_body` to be passed as `extra_body=` (GitHub compare 0.13.10...0.13.11). On 0.13.10 it was spread as `**extra_body` into `chat.completions.create()`, which in openai 2.26.0 has no `**kwargs`. So `ChatOpenRouter(extra_body={"provider": ...})` **raises `TypeError` on browser-box's pinned 0.13.10** but works on 0.13.11.
  - The reasoning-models dossier's `ChatOpenRouter(extra_body=...)` recommendation therefore needs 0.13.11. `source-code` (0.13.10 file via `gh api`; SDK signature checked in the venv)
- **Structured output, not tool calling:**
  - `ChatOpenAI` sends one strict `response_format: json_schema` per step (`llm/openai/chat.py:225-256`). The schema is the `AgentOutput` with a union of all action models.
  - For models without json_schema there are fallbacks: `add_schema_to_system_prompt=True` or `dont_force_structured_output=True`.
  - `ChatAnthropic` uses forced tool use for structured output (`llm/anthropic/chat.py`).
  - Default `max_completion_tokens=4096`; raises on `finish_reason=length`. `source-code`, matches the reasoning-models dossier.
- **Vision:** `use_vision=True` (default; screenshot every step), `False`, or `'auto'` (only after a `screenshot` action; `message_manager/service.py:462-472`). Also `vision_detail_level` and `llm_screenshot_size`.
  - Hands-on cost: defaults (vision + judge) used 10.8k prompt tokens/step vs 8.2k, and 2.7x the cost per task.
- **Flash mode:** `flash_mode=True` swaps the 24 KB `system_prompt.md` for the 2.4 KB `system_prompt_flash.md` (`agent/prompts.py:60-82`). It drops thinking/evaluation/next_goal and disables planning.
  - It is forced on for `ChatBrowserUse`.
  - Hands-on: 3.5k vs 8.2k prompt tokens per step, 3/3 correct.
- **Thinking/reasoning:**
  - `use_thinking=True` adds the agent's own "thinking" field.
  - Provider reasoning is sent only when the model matches `reasoning_models` (default list: OpenAI o-series/gpt-5 only). So for GLM pass `reasoning_models=[model], reasoning_effort="low"`. That also drops `temperature`/`frequency_penalty` (`llm/openai/chat.py:189-192`). `source-code` + hands-on (`reasoning_effort_sent: "low"` on every call; 0-8 reasoning tokens).
- **Per-step token drivers:**
  - System prompt: 24 KB normal, 2.4 KB flash.
  - Action schema: about 14 KB, sent every step.
  - Serialized DOM: capped by `max_clickable_elements_length=40000` chars.
  - History items: `max_history_items`.
  - Screenshots.
  - Extra calls: judge (default **on**, one more call with screenshots), planning (default on), message compaction (every 25 steps or about 10k tokens), `extract` (LLM over page markdown), and `fallback_llm`.
  - Measured: 8.1-8.4k prompt tokens per baseline step on books.toscrape (`RESULTS.md` section 1).
- **Can a decision model drive or accelerate it? Yes, at these points** (`hands-on` where marked):

| Plug point | How | Status |
|---|---|---|
| **Own loop over Browser-Use primitives** (recommended) | `get_browser_state_summary()` gives `selector_map` and candidates; decider picks; `tools.act(ActionModel(click={"index": n}), browser_session=b, page_extraction_llm=None)` executes. ActionModel comes from `tools.registry.create_action_model()` | **hands-on**: 0 LLM calls, correct, $0.000115 per decision |
| Guardrail between model output and execution | `register_new_step_callback(state, output, n)` runs after the model answers and **before** actions execute. Mutating `output.action[i]` changes what runs | **hands-on**: swapped Travel to Poetry |
| Decider as `Agent(llm=...)` | Must return a full `AgentOutput` via `output_format.model_validate(...)` | **hands-on** with a scripted stand-in (0 network calls). Fragile for real deciders: they cannot generate typed text, URLs or multi-action lists |
| Done-check / stop | `register_should_stop_callback()` (polled each step), `register_done_callback`, or replace the judge (`judge_llm` must return `JudgementResult{verdict,...}`; a decider "noul" fits) | `source-code` |
| Self-heal for replay | When `rerun_history` cannot match an element (5 levels: EXACT hash, STABLE hash, XPATH, AX_NAME, ATTRIBUTE; `agent/service.py:3529-3690`), escalate to a decider over the fresh selector_map | `source-code` (fleet must build) |
| As a custom tool | `@tools.action("choose element ...")` that calls the decider, for an LLM agent to delegate choices | `source-code` |

### Q3. Tools registry, secrets, limits, failure handling, judge, memory, files

- **Registry:**
  - `@tools.action(description, param_model=..., allowed_domains=[...], terminates_sequence=False)` (`tools/registry/service.py:291`).
  - Handlers get injected special params by name: `browser_session`, `page_url`, `cdp_client`, `page_extraction_llm`, `available_file_paths`, `has_sensitive_data`, `file_system`.
  - `Tools(exclude_actions=[...])` removes built-ins.
  - Built-ins in 0.13.11: `done, search, navigate, go_back, wait, click, input, upload_file, switch, close, extract, search_page, find_elements, scroll, send_keys, find_text, screenshot, save_as_pdf, dropdown_options, select_dropdown, write_file, replace_file, read_file, evaluate`.
  - `search_page` and `find_elements` are zero-LLM. `extract` is an LLM call. `evaluate` runs arbitrary JS. `hands-on` (listed from `Tools()`)
- **sensitive_data:**
  - `Agent(sensitive_data={"x_pw": "...", "https://*.example.com": {...}})`, values optionally domain-scoped.
  - The model sees placeholder names and writes `<secret>name</secret>`. The registry substitutes the real value at execution if the current URL matches (`tools/registry/service.py:427-480`).
  - Outgoing text messages are scrubbed of secret values (`message_manager/service.py:577-600`), and saved history is filtered (0.13.11 fixed nested lists).
  - **Screenshots are not scrubbed.** The protection depends on `allowed_domains`, which pages can bypass (#5815, #4763).
  - For the fleet, humans log in and agents never type credentials, so `sensitive_data` should stay unused. `source-code`
- **max_steps:** `agent.run(max_steps=500)` is the default (`agent/service.py:2505`). Always pass a small number.
- **Failure handling:**
  - `max_failures=5` consecutive failures, then one forced final `done` if `final_response_after_failure=True`.
  - `fallback_llm` is used on rate-limit/provider errors.
  - Loop detection: `loop_detection_window=20`.
  - Planning replan nudge after 3 stalls.
  - `llm_timeout` defaults by model name (75 s default); `step_timeout=180`.
  - Per-action timeout: `BROWSER_USE_ACTION_TIMEOUT_S` (180 s).
  - `source-code`
- **Judge:** `use_judge=True` by default. It is one extra LLM call at the end over the trace plus screenshots, returning `JudgementResult{reasoning, verdict, failure_reason, impossible_task, ...}`; `ground_truth` is optional.
  - Hands-on: 6.8k tokens, $0.0011.
  - It is a model's opinion, not verification.
- **Memory:**
  - Within a run, the `memory` field in each AgentOutput, plus message compaction (an LLM summary every 25 steps).
  - Across runs, nothing: no long-term memory store. Follow-up tasks reuse an Agent (`add_new_task`).
  - The fleet's memory is Obsidian (BRIEF). `source-code`
- **Files:**
  - `FileSystem` (`write_file`/`read_file`/`replace_file` in an agent data dir). 0.13.11 can write tiny base64 images.
  - `available_file_paths` whitelist for `upload_file`.
  - **Remote-browser gotchas** (`tools/service.py:860-925`, `downloads_watchdog.py`):
    - Upload uses `DOM.setFileInputFiles` with a path that must exist **on the browser host** (the Steel container). With `is_local=False` the model may name **any** absolute remote path.
    - Downloads land on the browser host; the agent gets a path it cannot read.
    - Download behaviour is set browser-wide to a **local** temp path.
  - browser-box excludes `upload_file` for this reason. Social posting needs images in the Steel container first (Steel files API; see the Steel dossier).

### Q4. Persistence and attaching

- **storage_state:**
  - Loaded on `BrowserConnectedEvent`: cookies via `Storage.setCookies`, localStorage/sessionStorage via a per-origin `addScriptToEvaluateOnNewDocument` on the focused target.
  - Saved on `stop()`, and every 60 s if cookies changed (`session.py:1733-1747`).
  - Hands-on, against a real Steel reset with a negative control (`RESULTS.md` 5a):
    - Cookies for both origins came back.
    - **localStorage only for the origin in the focused tab at save time** (quotes lost).
    - **A newer localStorage value was reverted to the saved one on reload.**
    - `export_storage_state()` returns cookies only. IndexedDB is never captured.
  - Use it as a backup snapshot, not as the source of truth for a logged-in social profile.
- **user_data_dir:**
  - Remote CDP: not applicable to Browser-Use. Persistence is the host's job.
  - Local launch: watch the "chrome"-in-path copy trap (Q1).
- **Steel-held profile** (hands-on, `RESULTS.md` 5c):
  - `POST /v1/sessions {"userDataDir": "..."}` then attach Browser-Use. Cookies and localStorage for all origins survived a release.
  - Caveat 1: only cookies older than Chromium's flush (written 2 s before release: lost; 40 s: kept).
  - Caveat 2: any `userDataDir` maps to one directory per Steel container (`session.service.ts:180-183`). One profile per container/volume.
- **Profiles:** in OSS, a profile is whatever the browser host keeps. Cloud has managed profiles (`profileId`, Q6).
- **Attach code** (all `Browser(cdp_url=...)`):

```python
from browser_use import Agent, Browser, ChatOpenAI, Tools
import httpx

# Self-hosted Steel (hands-on, this spike): create/configure the session, then attach to the single CDP URL.
httpx.post("http://steel:3000/v1/sessions", json={"userDataDir": "/profiles/p1", "proxyUrl": "http://user:pw@proxy:port"})
browser = Browser(cdp_url="ws://steel:3000/", keep_alive=True)   # NOT BrowserSession(browser_profile=BrowserProfile(cdp_url=...))

# Browserbase (source-code: bb-sdk-python types SessionCreateResponse.connect_url, BrowserSettingsContext{id,persist}; not run, no key):
# from browserbase import Browserbase
# s = Browserbase(api_key=KEY).sessions.create(project_id=PID, browser_settings={"context": {"id": CTX, "persist": True}})
# browser = Browser(cdp_url=s.connect_url)

# Any CDP endpoint: Browser(cdp_url="http://host:9222")  # resolved via /json/version
llm = ChatOpenAI(model="z-ai/glm-5.3-flash", base_url="https://openrouter.ai/api/v1", api_key=KEY,
                 reasoning_models=["z-ai/glm-5.3-flash"], reasoning_effort="low")
agent = Agent(task=..., llm=llm, browser=browser, tools=Tools(exclude_actions=["upload_file", "save_as_pdf", "evaluate"]),
              use_vision=False, use_judge=False, flash_mode=True, max_failures=3, llm_timeout=90, step_timeout=120,
              directly_open_url=True, enable_signal_handler=False)
history = await agent.run(max_steps=8)
```

- Browserbase: `connect_url` and `browser_settings.context.{id,persist}` exist in the Python SDK types (`<scratch>/sources/bb-sdk-python/src/browserbase/types/session_create_params.py:74-79`, `session_create_response.py:11`). The attach itself was not run here (no key); the Browserbase dossier owns the details.

### Q5. Deterministic re-runs: recording, replay, caching, "skills"

- **OSS replay exists.** `source-code` + `hands-on`
  - The API: `agent.save_history(path)`, `Agent.load_and_rerun(path, variables={...}, max_retries, skip_failures, delay_between_actions, max_step_interval, summary_llm, ai_step_llm, wait_for_elements)`, `rerun_history(history)`, and `detect_variables()` for parameterising typed values.
  - Elements are re-found by hash/xpath/ax-name.
  - Hands-on (`RESULTS.md` section 4, 5d): 2 replays of a 3-step and a 4-step history re-executed every click from a parked example.com (indexes remapped at EXACT level).
  - LLM calls: **1 summary call with a screenshot** ($0.00018-0.00048), or **0** with a stub `summary_llm`. `extract` steps would re-run as LLM "AI steps".
  - The replayed `done` returns the **original** answer text.
  - No cache with hit/miss semantics, no per-site DOM-signature keys, no self-heal beyond the 5 match levels and `skip_failures`.
- **"Skills" in OSS** = `Agent(skills=[ids])` → `SkillService` → Browser Use **Cloud API** (`BROWSER_USE_API_KEY`).
  - The agent fills skill "cookie" parameters **from the live browser's cookies and sends them to Browser Use's API** (`agent/service.py:853-905`, `skills/service.py:165-230`).
  - Cloud docs: skills are **retired**; create/refine return 410 (`https://docs.browser-use.com/cloud/legacy/skills.md`).
  - Not usable for client accounts. `source-code` + `official-docs`
- **Cloud "rerunnable scripts"** (`https://docs.browser-use.com/cloud/agent/scripts.md`):
  - A V4 agent writes and saves a script in a workspace; later runs start an agent again that runs or repairs it.
  - Still LLM-driven per run, and Cloud-only. `official-docs`
- **Browser Harness** (`browser-harness` 0.1.13, a hard dependency; the `browser-use` CLI now delegates to it):
  - A CDP harness for coding agents. The agent writes reusable helpers (`agent_helpers.py`) and optional "domain skills" (`BH_DOMAIN_SKILLS=1`).
  - Its recorder saves screenshots and an event trace for **videos**, not for replay. `source-code` (installed package)
- **Actor API** (`browser_use/actor`): Playwright-like Page/Element/Mouse over CDP, deterministic.
  - `get_elements_by_css_selector` has no LLM; `get_element_by_prompt` and `extract_content` call an LLM.
  - It is a building block for a fleet replay cache. `source-code`
- **Beta Agent** (`browser_use.beta`): backed by a separately installed `browser-use-terminal` binary / `browser-use-core` wheel. Not investigated; license `unverified`.

### Q6. Browser Use Cloud vs OSS; pricing (October 2026)

- **Cloud only** (`official-docs` corpus: `https://docs.browser-use.com/cloud/browser/stealth.md`, `https://docs.browser-use.com/cloud/browser/captcha-handling.md`, `https://docs.browser-use.com/cloud/browser/proxies.md`, `https://docs.browser-use.com/cloud/guides/authentication.md`, `https://docs.browser-use.com/cloud/guides/profile-sync.md`):
  - Hardened Chromium fork with fingerprints **randomized per session**.
  - CAPTCHA solving (OSS only waits on Cloud's `BrowserUse.captchaSolverFinished` CDP event).
  - Residential proxies on by default (US), 195+ countries; `customProxy` accepted.
  - Managed **profiles** (cookies/localStorage/login) with `profileId`, and a profile-sync script that uploads a local login.
  - Live view, recording, V4 hosted agents, workspaces, rerunnable scripts, skills (retired).
  - The V4 hosted agent **cannot attach to your own browser** (`ExternalBrowserAttach` is dev-only in `https://docs.browser-use.com/openapi/v4.json`).
  - Same fingerprint and same IP are not documented guarantees.
- **OSS:** the agent loop, CDP control, replay, storage_state, local launch hygiene flags. You bring the browser, proxy and fingerprint layer.
- **Pricing**: `vendor-claim`, `browser-use.com/pricing.md`. Re-fetched 2026-10-10 and byte-identical to the 2026-10-09 capture; the page says "last verified September 3, 2026".
  - No subscriptions; credits are dollar-denominated.
  - Browser **$0.02/browser-hour** (per minute, 1-minute minimum).
  - Managed residential proxy **$5/GB**; direct or own-proxy egress **$0.20/GB**.
  - V4 models from $0.24/$1.44 per 1M tokens (gpt-5.6-luna) up to Claude Opus 5 at $6/$30. The default model disagrees between the docs (`gpt-6-luna`) and the pricing page; see corpus MANIFEST.
  - BU 2.0 model API $0.60/$0.06/$3.50 per 1M.
  - BYOK: provider cost plus a 0.2x fee.
  - V2: from $0.006/step plus $0.01/task.
  - Concurrency by lifetime spend: 10 / 50 ($200) / 250 ($1k) / 500 ($5k) / 1,000 ($25k) / Enterprise 1,000+. The docs say $100 for tier 1; the pricing page says $200.
  - Profile count limit: exists ("Profile limit reached") but no number is published.
  - GLM 5.3 Flash is a hosted V4 model (`glm-5.3-flash`, no BYOK). The vendor's own BU_Bench_v2 gives it 28.0/100 at $0.114/task (`vendor-claim`).

### Q7. Concurrency and stability; browser-box confinement on 0.13.11

- **Upstream stance:** one Agent per BrowserSession. No documented multi-agent sharing of one browser. The official parallel template (`official-docs` `https://docs.browser-use.com/open-source/examples/templates/parallel-browser.md`) runs 3 Agents on 3 separate `Browser(user_data_dir=...)` instances with `asyncio.gather` in one event loop.
- **Hands-on (`RESULTS.md` 6-7):**
  - Two sessions or two scripted Agents, on two Steel browsers, in one loop or in two threads each with its own loop: all correct.
  - Two Agents on the **same** browser in one loop: both correct in this short run.
  - At exit: "Task was destroyed but it is pending" (bubus run loops, storage monitor) and "Event loop is closed".
  - **`asyncio.run()` teardown hung forever with a live `keep_alive` session (3/3)** until the spike exited from inside the loop, as browser-box does.
- **browser-box's errors explained:**
  - "Root CDP client not initialized" is the follow-on message after a failed or dropped CDP connect. Reproduced when attaching right after Steel's `/v1/health` turned green but before Chromium accepted CDP; also open upstream as #6005 on the stop path.
  - "attached to a different loop" matches the bubus cross-loop bug #5509 (open, 0.13.8+; fix PR browser-use/bubus#34 unmerged; bubus pinned 1.5.6). Not reproduced in 2-agent runs.
- **The confinement patches** (`agents/browseruse/runner.py` @4c837a3) and whether they are still needed:

| Patch | What it stops | Still needed on 0.13.11 for a **shared** browser? | Needed for a fleet with **one browser per profile**? |
|---|---|---|---|
| `SessionManager.get_all_page_targets`, `BrowserSession._cdp_get_all_pages` filter FOREIGN tabs | Agent adopting another client's tab | Yes: `session_manager.py` unchanged in 0.13.10 to 0.13.11 | No. Replace with a **per-profile engine mutex** so Stagehand, Browser-Use and the human viewer never drive at once |
| `get_or_create_cdp_session`, `get_target_id_from_tab_id`, `on_CloseTabEvent`, `_cdp_close_page` refuse FOREIGN | Navigating, switching or closing others' tabs | Yes (session.py target code unchanged) | No (same mutex) |
| `DownloadsWatchdog.attach_to_target` no-op | Browser-wide `Browser.setDownloadBehavior` to a temp dir | Yes (unchanged) | Partly. The setting is per browser and the path is a local temp dir that does not exist in Steel. Keep `accept_downloads=False`, `auto_download_pdfs=False` unless downloads are designed |
| `permissions=[]` | Clipboard and notifications granted to every origin | Yes | **Yes**: a consistent identity should not suddenly grant notifications everywhere |
| Version pin + `--self-check` | Silent breakage on upgrade | Yes. It refuses 0.13.11 only on the version string; a bumped copy passes all checks (hands-on) | **Yes**, keep the pattern |
| `reasoning_models=[model]` | GLM at max effort (~40 s/step) | Yes | Yes |
| `os._exit` from inside the loop | Shutdown hangs | Yes (hands-on, 3/3 hangs without it) | Yes |
| `exclude_actions=["upload_file","save_as_pdf"]` | Remote file exfiltration, files nobody collects | Yes | Yes; also consider `evaluate` (arbitrary JS) |

### Q8. Known limitations on social-media-style SPAs (GitHub issues, `third-party` unless noted)

- **React contenteditable editors** (X reply box, Slack): first character doubled (#4461) or missed (#3889, x.com, Draft.js). Closed by a stale bot or with a Draft.js workaround; not verified fixed in 0.13.11.
- **`input(clear=True)`** dispatches `change` before typing; formatter fields mangle values (#5721, open, 0.13.8+).
- **Typing cadence:** 1-10 ms between key events (`default_action_watchdog.py:1892-1998`, `source-code`); #3825 asked for human cadence. There is no human-like mouse path. Both are bot signals on social sites.
- **Shadow DOM:** user-agent shadow roots are mis-reported as open (#5817, open). Past issues with clicking inside shadow DOM (#3810), and an agent "giving up" on SPA/shadow-DOM pages (#4306, called LLM judgement).
- **Domain lock bypass:** page-initiated navigation, redirects, popups (#5815, open, severity high) and `data:`/`blob:` URLs (#4763, open).
- **Storage/state:**
  - The StorageStateWatchdog logs errors every interval once the CDP client is gone (#5912, open).
  - `SaveStorageStateEvent` asserts "Root CDP client not initialized" on stop (#6005, open).
  - localStorage persistence is focused-origin only, and the restore clobbers newer values (`hands-on`, this dossier).
- **Iframes:** cross-origin iframe handling needs `cross_origin_iframes`/`max_iframes` and has a history of issues (#3382, #4089).
- **Project hygiene:** 168 open issues on 2026-10-10. At least 23 closed by the 14-day stale bot. A closed issue is not proof of a fix.
- **Not exercised:** infinite/virtualised feeds. The DOM serializer only sends what is rendered plus `max_clickable_elements_length`, so long feeds need scroll-and-re-snapshot loops. `source-code`, inference.

### Q9. Hands-on (details and raw numbers in `spikes/browser-use/RESULTS.md`)

- Setup: Steel `ghcr.io/steel-dev/steel-browser-api:latest` (7a161b95e8a9) as `fleet-spike-browseruse` on 127.0.0.1:3302, plus `...2` on 3303 for concurrency. `--memory 1536m --cpus 1.2`, `NODE_OPTIONS=--unhandled-rejections=warn`, `DOMAIN/CDP_DOMAIN=localhost:<port>`. Removed by a trap after every batch.
- Model: GLM 5.3 Flash @low via OpenRouter, browser-box options, `max_steps=8`.
- Task 1 ("first Poetry book price"): 6/6 correct (3 baseline, 2 flash, 1 defaults).
  - Steps per run: 3, of which the 1st is a no-LLM navigate.
  - Baseline: 8.0-14.6 s, 16.2-16.8k tokens, $0.0013-0.0027.
  - Flash: 5.5-7.7 s, 7.0k tokens, $0.0008-0.0011.
  - Defaults: 12.5 s, 28.7k tokens, $0.0036 (vision + judge).
- Task 2 ("first Poetry book's UPC and stock"): 3/3 correct, 4 steps.
  - Baseline: 14.9-20.7 s, $0.0024-0.0033.
  - Flash: 11.1 s, $0.0013.
- Decider path (no Agent): 2/2 correct, 6.5-8.8 s, 0 chat calls, $0.000115.
- Replay: 3/3 re-executed. 1 LLM call (summary), or 0 with a stub.
- Persistence: covered in Q4 (Browser-Use storage_state vs Steel userDataDir, both with negative controls).
- Spend: $0.0204 per-call billed (key delta $0.0259 on a shared key).

## 3. What OSS Browser-Use gives vs what the fleet must build

| Need | Browser-Use 0.13.11 OSS gives | Fleet must build |
|---|---|---|
| Open-ended agent loop on any CDP browser | `Agent` + `Browser(cdp_url)`; GLM works at @low with flash mode | Engine router (Stagehand first, Browser-Use for open-ended); a task contract with step, time and spend caps |
| Persistent identity (cookies, storage, fingerprint, IP) | Nothing durable. `storage_state` is partial (focused-origin localStorage, no IndexedDB, clobbers on reload) | Profile store on the browser host (Steel userDataDir per container/volume) plus a periodic CDP cookie snapshot as a backup; respect the cookie flush window before release |
| Stealth / fingerprint / proxy | Local-launch flag hygiene only; `ProxySettings.server` ignored on remote | Pinned fingerprint per profile and a sticky proxy per profile, set on the Steel/anti-detect side (other dossiers) |
| System 1 decisions | `selector_map`, `Tools.act`, `register_new_step_callback`, `register_should_stop_callback`, replaceable judge | Candidate builder (filter/rank to ≤180, per-site noise rules, viewport/scroll), decider client with thresholds and escalation, **fresh-snapshot-before-act and node-identity check**, deterministic verify step |
| Deterministic re-runs | `save_history` / `load_and_rerun(variables)` with 5-level element matching | Replay cache keyed by site + workflow + DOM signature; stub `summary_llm`; re-extract instead of replaying `done`; decider self-heal on match failure; versioned workflows |
| Safety | `allowed_domains` (bypassable), `sensitive_data` (text-only scrubbing), `exclude_actions` | Egress allowlist at proxy/Steel; deterministic gates for post/send/DM/delete; no credentials to agents; exclude `upload_file`/`evaluate` unless designed |
| Files for social posting | `upload_file` needs a path on the browser host | Media staging into the Steel container (Steel files API) and an upload action with a whitelist |
| Concurrency & lifecycle | One agent per session; hangs on teardown; reconnect noise | One agent per OS process, hard kill timer, exit from inside the loop, CDP-readiness probe before attach, per-profile mutex |
| Observability & cost | `history` (steps, URLs, usage), `register_new_step_callback` | Per-call model/provider/cost logging (OpenRouter `/generation`), per-profile spend ledger, step traces into the fleet's store |
| Memory | Per-run `memory` field and compaction | Obsidian-based memory per profile (BRIEF), injected via `extend_system_message` / task text |
| Human login | none | Live viewer on Steel, "human logs in once" flow, then lock the profile |

## 4. Operating notes for a Hermes agent (feeds the skills)

**Call shape (the backup engine):**
- Run Browser-Use in **its own process per task**: a child process with a spec on stdin and a result file out, as `agents/browseruse/runner.py` does.
  - Write the result and `os._exit(0)` **from inside the event loop**.
  - Arm a hard kill timer of max_steps × step_timeout + margin.
- Attach with `Browser(cdp_url=<profile's Steel ws url>, keep_alive=True)`. Never use `BrowserSession(browser_profile=BrowserProfile(cdp_url=...))`.
- Before attaching right after a wake-up, probe a CDP round trip (`Browser.getVersion`); `/v1/health` turns green before Chromium accepts CDP.
- LLM: `ChatOpenAI(model="z-ai/glm-5.3-flash", base_url="https://openrouter.ai/api/v1", reasoning_models=[model], reasoning_effort="low")`.
  - Use `ChatOpenRouter(extra_body=...)` only on ≥0.13.11.
- Agent defaults for the fleet:
  - Flags: `flash_mode=True`, `use_vision=False` (or `'auto'`), `use_judge=False` (verify deterministically instead), `max_failures=3`, `llm_timeout=90`, `step_timeout=120`, `directly_open_url=True`, `enable_signal_handler=False`.
  - Actions: `Tools(exclude_actions=["upload_file","save_as_pdf","evaluate"])`.
  - Always `run(max_steps=N)` with a small N; the default is 500.
- Put the target URL in the task text; `directly_open_url` opens it without an LLM call.
- Env: `ANONYMIZED_TELEMETRY=false` (this also disables `BROWSER_USE_CLOUD_SYNC`) and `BROWSER_USE_SETUP_LOGGING=false`.
- Never leave `llm=None`: it silently switches to Browser Use's hosted model.

**System 1 executor (the main path when Stagehand is not used):**
- State: `st = await b.get_browser_state_summary(include_screenshot=False)` (about 0.1 s on a simple page).
- Candidates: build from `st.dom_state.selector_map` (key = backendNodeId-based index; node has `tag_name`, `attributes`, `get_all_children_text()`, `absolute_position`, `is_visible`).
  - Label as `link "Text" -> href` and add a `none` option.
  - Cap at about 180; filter per site.
- Act: `tools.act(AM.model_validate({"click": {"index": n}}), browser_session=b, page_extraction_llm=None)`, where `AM = tools.registry.create_action_model()`.
- Text the agent types is **code-supplied**: `{"input": {"index": n, "text": approved_text}}`.
- **Always re-snapshot immediately before act** and check that the node at that index still has the chosen label/href. A stale index executes silently.
- Reads: `find_elements` (CSS) and `search_page` (regex) cost zero LLM. `extract` costs an LLM call.

**Replay:**
- Save every successful open-ended run (`agent.save_history`).
- Replay with `load_and_rerun(path, variables=..., summary_llm=<stub>, skip_failures=False)`.
- Treat a replayed `done` text as stale; re-read values with `find_elements`/`search_page`.

**Persistence:**
- Persist on the browser host. After a login or any cookie change, wait ≥30 s before releasing or stopping the Steel session.
- Optionally keep a CDP cookie snapshot (`Storage.getCookies`) as a backup.
- Do not rely on Browser-Use `storage_state` for social logins.

**Limits to tell the agent:**
- Typing is superhuman-fast and clicks have no mouse path. React contenteditable editors can drop or double the first character, so verify posted text after typing.
- Domain allowlists are advisory.
- No CAPTCHA solving: detect it and hand off to a human.

## 5. Risks and unknowns

- **Small samples.** 9 agent runs on two easy static pages, and 2 decider runs on one page. No social-media SPA was tested (the brief forbids it). GLM accuracy on long feeds, modals and contenteditable editors is unmeasured here.
- **Stale-index behaviour** was explained only empirically. The old backendNodeId still resolved to a same-looking link, so the exact mechanism is not traced. On changed layouts, the result of a stale act is undefined.
- **bubus cross-loop bug (#5509)** at fleet scale is untested; the fix is unmerged.
- **Steel cookie flush window** is measured on n=1 per setting (2 s lost, 40 s kept). The real threshold and the effect of a graceful Chrome shutdown are unknown. Steel's own `sessionContext` capture on release was not tested.
- **Steel's single persistent dir** means per-profile isolation needs one container or a volume swap per wake. Cost and latency of that are in the scale-infra and Steel dossiers, not here.
- **Version churn.** 138 commits between 0.13.10 and 0.13.11 in five weeks. Pin the version, self-check on start, and re-run the spike on upgrade.
- **The upstream stale-bot** closes issues without fixes; treat "closed" as unknown.
- **Cloud claims are vendor-only:** stealth 81%/84.8%, 195+ countries, the profile limit. The default-model disagreement in Cloud docs is unresolved.
- **Browserbase attach** is unverified here (no key).
- **Beta Agent** (Rust terminal binary) and `browser-use-core` were not examined.
- **Deviation:** one read-only `docker exec` version query on the live `browser-box-agent-browseruse-1` container (no changes). Recorded in `RESULTS.md` section 10.

## 6. Sources

Source code (pinned):
- browser-use @ `c75e8476e26d18b7617643bc2ae082fae8eae431` (`<scratch>/sources/browser-use`), equal to venv 0.13.11:
  - `browser_use/browser/session.py`: `__init__` 262-410; connect 1880-1905; storage 1437-1480, 3484-3660; watchdog setup 1733-1747; proxy auth 2040-2152.
  - `browser_use/browser/profile.py`: fields 585-735; `_copy_profile` 849-904; proxy args 943.
  - `browser_use/browser/watchdogs/storage_state_watchdog.py`, `downloads_watchdog.py` 307-520, `permissions_watchdog.py`, `aboutblank_watchdog.py`, `default_action_watchdog.py` 705-880 and 1880-2000.
  - `browser_use/agent/service.py`: `__init__` 136-430; run 2503; replay 2907-3910; skills 836-922.
  - `browser_use/tools/service.py` (`act` 2178, `upload_file` 860-925); `tools/registry/service.py` (`action` 291, `execute_action` 331, `create_action_model` 519).
  - `browser_use/llm/openai/chat.py`, `llm/openrouter/chat.py`, `llm/base.py`; `browser_use/skills/service.py`; `browser_use/sync/service.py`; `browser_use/config.py`; `browser_use/agent/prompts.py`; `browser_use/agent/system_prompts/*.md`.
- GitHub compare `browser-use/browser-use` 0.13.10...0.13.11 (138 commits; fetched 2026-10-10 via `gh api`). Also `browser_use/llm/openrouter/chat.py?ref=0.13.10`.
- browser-harness 0.1.13 (installed package `site-packages/browser_harness/`: README in METADATA, `recorder.py`, `SKILL.md`).
- steel-browser @ `1131a02` (`<scratch>/sources/steel-browser`): `api/src/services/session.service.ts:180-183, 278-320`, `api/src/services/cdp/cdp.service.ts:1397-1427`, `api/src/modules/sessions/sessions.routes.ts:111-131`, `sessions.schema.ts:29-90`.
- browser-box @ `4c837a3`: `agents/browseruse/runner.py`, `compose.yml`.

Docs and vendor material (corpus fetched 2026-10-09, `fleet/research/corpus/browser-use/`, see MANIFEST/INDEX):
- `https://docs.browser-use.com/open-source/customize/browser/remote.md`, `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md`, `https://docs.browser-use.com/open-source/customize/browser/authentication.md`.
- `https://docs.browser-use.com/cloud/browser/stealth.md`, `https://docs.browser-use.com/cloud/browser/captcha-handling.md`, `https://docs.browser-use.com/cloud/browser/proxies.md`.
- `https://docs.browser-use.com/cloud/guides/authentication.md` (Profiles), `https://docs.browser-use.com/cloud/guides/profile-sync.md`, `https://docs.browser-use.com/cloud/guides/concurrency.md`.
- `https://docs.browser-use.com/cloud/agent/scripts.md`, `https://docs.browser-use.com/cloud/legacy/skills.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/hermes-agent.md`, `https://docs.browser-use.com/openapi/v4.json`.
- `https://browser-use.com/pricing.md`: re-fetched https://browser-use.com/pricing.md on 2026-10-10, identical; the page states "last verified September 3, 2026".

GitHub issues (browser-use/browser-use, read 2026-10-10):
- Open: #5509 (bubus cross-loop, 2026-08-21), #6005 (Root CDP client on stop, 2026-10-06), #5912 (storage watchdog error loop, 2026-09-25), #5815 (allowed_domains bypass, 2026-09-15), #4763 (data:/blob: bypass, 2026-04-29), #5721 (input clear/change, 2026-09-08), #5817 (shadow root type, 2026-09-15).
- Closed: #4461 (contenteditable doubled char), #3889 (x.com first letter), #3825 (typing speed), #4306 (SPA give-up), #3718 (Root CDP client).
- browser-use/bubus PR #34 (open, created 2026-08-27).

Hands-on (2026-10-10 UTC):
- `fleet/research/spikes/browser-use/RESULTS.md` and its scripts.
- Raw JSON in `<scratch>/spikes/browser-use/run2/` (`task_*.json`, `task2_*.json`, `direct3/4.json`, `decider1.json`, `replay*.json`, `persist1.json`, `steelprofile1/2.json`, `conc1.json`, `pure_checks.json`, `key_before/after*.json`).

Sibling dossiers used (not re-measured):
- `dossiers/reasoning-models.md`: GLM per-step accuracy and latency.
- `dossiers/system1-models.md`: decider API shapes and `/systemone` contract.
