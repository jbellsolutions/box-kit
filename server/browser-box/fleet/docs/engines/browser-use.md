# Engine guide: Browser-Use (L4, the explorer)

Status: **target design. Nothing in `fleet/` is built.** Every "the fleet does X" below describes the
target. A statement is only a fact if it carries a `hands-on`, `source-code` or `official-docs` tag and
says what was run or read.

Precedence: where a dossier and its verification report disagree, the verification report and
[DECISIONS.md](../../DECISIONS.md) win. This guide follows that rule. The list of dossier claims it
corrects is in section 20.

Tags used here:

- Provenance (from [BRIEF.md](../../research/BRIEF.md)): `hands-on`, `source-code`, `official-docs`,
  `vendor-claim`, `third-party`, `unverified`.
- Status: **unbuilt** (designed, no code), **estimate** (arithmetic or judgement, not measured),
  **to measure** (a named gate with no data yet), **pending Q-nn** (waits on one of Justin's questions
  at the end of DECISIONS.md; the guide proceeds on the recommended default).

Row ids such as BRO-4, REA-7, S1-08 and AP-3 are rows in the matching verification report
(`verification/browser-use.md`, `reasoning-models.md`, `system1-models.md`, `antidetect-proxies.md`).
Almost all hands-on evidence is small-sample and ran on arm64 Docker; DigitalOcean droplets are
amd64, so every measured number is re-measured in M1 before it is relied on (DECISIONS.md, O-17).

Main sources: [dossier](../../research/dossiers/browser-use.md),
[verification](../../research/verification/browser-use.md),
[reasoning-models](../../research/dossiers/reasoning-models.md) +
[verification](../../research/verification/reasoning-models.md),
[system1-models](../../research/dossiers/system1-models.md) +
[verification](../../research/verification/system1-models.md),
[spike results](../../research/spikes/browser-use/RESULTS.md), and the box runner
(`agents/browseruse/runner.py` in the repo root). Question numbers (Q-nn) and decision numbers (D-nn) are
DECISIONS.md's. Open items (O-nn) and contradictions (C-nn) are from
[CONSISTENCY.md](../../research/verification/CONSISTENCY.md). (That file's Q-13 differs from
DECISIONS.md's; this guide cites only Q-01 to Q-12, which match.)

---

## 1. Role in the fleet

Browser-Use is the **backup agent for open-ended goals** (rung L4 of the action ladder, D5/D6). It is an
open-source Python library (MIT) that runs an LLM loop over a browser it reaches by CDP.

What it does here:

- **L4 `task`:** one open-ended goal, many generative calls, read-mostly (D5, D17).
- **Possible L1/L2 executor:** its `selector_map` + `Tools.act` can click an element a System 1 decider
  chose, with zero chat-model calls. Whether it, Stagehand v4 or a minimal CDP executor is the executor
  for logged-in identities is decided in M1, per site class (D6, O-02). **to measure**

What it is not:

- Not the browser host. Steel or Browserbase own the browser, the profile, the IP and the persona (D3, D4, D11).
- Not the persistence layer (section 12), the stealth layer (section 17), the policy gate (section 8)
  or the memory (Obsidian, D15).
- Not something a Hermes profile runs. Browser-Use runs in **fleet workers** next to fleetd. A profile
  holds only a scoped token and calls the `task` tool (D1, D17). It does not run in the Jev Workforce
  trial either.

Where it sits among the engines:

| Engine | Used for | Why not Browser-Use |
|---|---|---|
| Deterministic code / API | Everything with a known path (L0) | Zero model calls beats any agent |
| Fleet replay cache (L1) | Stored, re-verified Actions | Browser-Use replay is not that (section 11) |
| System 1 decider + executor (L2) | Pick one element from a fresh snapshot | Browser-Use can be the executor (section 6) |
| Stagehand v4 `act`/`observe`/`extract` (L3) | Scoped single steps, extraction | Main engine for scoped work (D6) |
| **Browser-Use agent loop (L4)** | **Open-ended goals, unknown number of steps** | **This guide** |
| Human via live viewer (L5) | Login, 2FA, CAPTCHA, checkpoints, approvals | Agents never type credentials (D14) |

---

## 2. Version pin and self-check

### The pin

| Package | Pin | Note |
|---|---|---|
| `browser-use` | **`0.13.11`** (git `c75e8476e26d18b7617643bc2ae082fae8eae431`, released 2026-10-07) | MIT. `hands-on` (`importlib.metadata`), `source-code` |
| `cdp-use` | `1.4.5` | Pinned by browser-use itself. `source-code` |
| `bubus` | `1.5.6` | Pinned by browser-use itself. Carries the open cross-loop bug #5509 (section 13) |
| `openai` | `2.26.0` | Pinned by browser-use itself. Its `create()` has no `**kwargs`; see below |

Browser-Use also hard-depends on `browser-harness==0.1.13`, `browser-use-sdk==3.4.2` and `mcp==2.1.1`
(`source-code`, [dossier Q1](../../research/dossiers/browser-use.md)). So the install contains Cloud SDK and
MCP code the fleet never calls. Section 17 covers keeping it that way.

The box is **not** on this pin. `agents/browseruse/runner.py` pins `0.13.10`. On 0.13.10,
`ChatOpenRouter(extra_body=...)` raises `TypeError`, because 0.13.10 spread `extra_body` into
`chat.completions.create()` and openai 2.26.0 has no `**kwargs`. 0.13.11 passes `extra_body=` properly
(`source-code`, GitHub compare 0.13.10...0.13.11; verification BRO-7). Do not copy the box's pin.

Version churn is high: 138 commits between 0.13.10 (2026-09-04) and 0.13.11 (2026-10-07) (verification
BRO-7). Every upgrade goes through the gate in section 21.

### The self-check (written fresh, **unbuilt**)

The box runner has a `--self-check`. Keep the pattern, not the code. The runner's check would pass or
fail for the wrong reasons here:

- It builds the session as `BrowserProfile(cdp_url=..., is_local=False)`, which comes out
  `is_local=True` (`hands-on`, `pure_checks.json`; verification spot check). The fleet uses
  `Browser(cdp_url=...)`.
- It asserts `user_data_dir is None`. The correct `Browser(cdp_url=...)` form is given an empty temp
  `user_data_dir` (`browser-use-user-data-dir-*`) even on a remote session (`hands-on`, `persist1.err`;
  verification missed issue 7). The assertion that matters is `storage_state is None`.
- It refuses 0.13.11 only on the version string. A copy with `PINNED` bumped passes every check
  (`hands-on`, spike section 8).

The fleet worker's self-check runs offline (no browser, no network), at image build and at the start of
every worker process. It must verify:

1. The exact versions of the four packages above.
2. The session the fleet builds: `Browser(cdp_url="ws://127.0.0.1:1/", ...)` has `is_local` false,
   `storage_state` None, `highlight_elements` false, `permissions == []`, `accept_downloads` false,
   `auto_download_pdfs` false, `keep_alive` true, `proxy` None.
3. `Agent.__init__` accepts every option in section 7, including `register_new_step_callback`,
   `register_should_stop_callback`, `extend_system_message`, `fallback_llm`, `flash_mode`.
4. Every action in the exclusion list exists in `Tools().registry.registry.actions`. Excluding a name that
   no longer exists silently does nothing.
5. `Tools.act`, `tools.registry.create_action_model`, `BrowserSession.get_browser_state_summary` exist.
6. `inspect.signature(AsyncCompletions.create)` has `extra_body` (the route in section 5 that needs it).
7. The worker environment has no `BROWSER_USE_API_KEY`, has `ANONYMIZED_TELEMETRY=false`, and the
   `Agent` is never built with `llm=None` (section 5).
8. If the fleet keeps the one-line downloads patch (section 10), `DownloadsWatchdog.attach_to_target`
   exists.
9. Coordinate clicking is off. Build an `Agent` offline with the configured `llm` slug (a stub object with
   that `.model` is enough) and assert that the registered `click` action's `param_model` is
   `ClickElementActionIndexOnly`. `agent/service.py:326-333` switches the coordinate variant on by
   model-name pattern, and `set_coordinate_clicking` has no other caller, so only the primary `llm` counts.
   This keeps the G3.8 coordinate-click rule true if someone changes the model (section 6). Attribute names
   are to be confirmed at build.

Exit with `os._exit(code)` after printing `self-check ok` or the failure. That avoids the shutdown hang
(section 13).

---

## 3. Architecture

- **Pure CDP.** Browser control goes through `cdp-use` (`TimeoutWrappedCDPClient`,
  `session.py:1898-1905`). **No Playwright** is installed or required; the word appears in the
  pyproject only in a comment (`source-code`; the shared venv has no playwright or patchright package;
  verification BRO-1).
- **Event bus plus watchdogs.** `bubus` carries events. Watchdogs react to them: downloads, about:blank,
  permissions, storage state, security, popups, crash, captcha, DOM, screenshot, recording, HAR
  (`source-code`).
- **Classes.** `Agent`; `BrowserSession` (`Browser` is an alias); `BrowserProfile` (a pydantic model of
  options); `Tools` (alias `Controller`); chat classes (`ChatOpenAI`, `ChatOpenRouter`, ...).
- **One step of the agent loop:** capture browser state (serialized DOM with an index-keyed
  `selector_map`, optional screenshot) -> one LLM call -> run the chosen actions -> record history.

Defaults that bite on a remote, shared-identity browser. The fleet turns each one off:

| Default | What it does | Fleet setting |
|---|---|---|
| `llm=None` | Silently uses `ChatBrowserUse()`, Browser Use's hosted model (`agent/service.py:225-235`) | Always pass an explicit `llm` |
| `highlight_elements=True` | Injects `<div data-browser-use-interaction-highlight>` at z-index 2147483647 into the live page on every click, input and upload, **including on the `Tools.act` path** (`session.py:2940-2995`, `tools/service.py:728,793,936`). A page with a MutationObserver can see it | `highlight_elements=False`; leave `dom_highlight_elements` at its default `False` |
| `permissions=['clipboardReadWrite','notifications']` | Granted to **all origins** through `Browser.grantPermissions` (`permissions_watchdog.py:34-39`) | `permissions=[]` |
| `accept_downloads=True`, `auto_download_pdfs=True` | Sets browser-wide download behaviour to a **local temp path** on the worker, which does not exist in Steel | Both `False` |
| `use_judge=True`, `enable_planning=True`, `use_vision=True` | Extra LLM calls and screenshots | Off / off under flash mode / off (section 7) |
| `max_steps=500` in `run()` | Runs very long | Always pass a small number |
| Telemetry | The library sends PostHog telemetry that "may include ... task instructions, URLs" unless disabled ([corpus](https://docs.browser-use.com/open-source/development/monitoring/telemetry.md), `official-docs`) | `ANONYMIZED_TELEMETRY=false` (this also turns off cloud sync), `BROWSER_USE_SETUP_LOGGING=false` |
| Remote session gets a temp `user_data_dir` | Switches on the storage-state watchdog (60 s cookie polling, writes nothing when `storage_state` is None, leaves an empty temp dir per session) | Never set `storage_state`; delete the temp dir at process end (section 12) |

---

## 4. Attaching to the browser host

### Rules

1. The **node agent** owns the browser: it creates the Steel session, applies the persona, binds the
   proxy forwarder, and keeps raw CDP unpublished (D4, D10). Browser-Use never calls Steel's REST API.
   It only attaches.
2. Attach with **`Browser(cdp_url=...)`**. Never
   `BrowserSession(browser_profile=BrowserProfile(cdp_url=..., is_local=False))`: that form comes out
   `is_local=True`, which changes upload and download paths (`session.py:400-411`). The box runner uses
   the wrong form (`runner.py:127-130`).
3. **Probe CDP before attaching.** Steel's `/v1/health` turns green before Chromium accepts CDP. The
   first attach after container start failed once with "Root CDP client not initialized"
   (`hands-on`, spike section 7). D4 already says health is never Steel's HTTP status. The worker does one
   more check: a `Browser.getVersion` round trip over the CDP socket, with a short retry.
4. **No `ProxySettings` on a remote session.** `server` and `bypass` are launch args only
   (`profile.py:943-949`). If `username`/`password` are given, Browser-Use turns on `Fetch.enable` with
   `urlPattern: '*'` on the focused tab and answers every request from Python
   (`session.py:2030-2158`; verification BRO-11 and missed issue 2). The author's own later probe
   recorded `proxy_ignored: false` and an unexplained page title (`hands-on`, `proxy_check.json`), so
   "ignored" is a source-code finding only. Rule: the proxy is the node's loopback forwarder, set on the
   Steel session by the node agent, and Browser-Use sees none of it (D10).
5. **One CDP client at a time.** The fleet lease (D12) is the mutex. Details in section 13.
6. **The clean attach result applies only when the wake's effective `extension_mode` is `none`:** no Stagehand
   extension loaded, and none left resident by an earlier session. Identities of kind `account` are `none`
   by default. A persona that M1 gave Stagehand mode A or B (a `research` identity by default) carries the
   extension, and a Browser-Use run on it inherits the Stagehand signal (section 14). The node agent derives
   the effective mode from the persona, and the caller cannot pass it ([steel-profile](../infra/steel-profile.md)
   section 2 flavor table; persona fields in section 5). The router checks it before it treats Browser-Use as
   the lower-exposure engine for a step. Consequence: section 8 recommends running L4 with no client login,
   which means a `research` identity, and that persona defaults to mode A. So the recommended L4 home runs
   beside a resident Stagehand extension. No account is at risk there, but open-web bot walls may react to
   it. G1.4's research arm (the share of runs that raise no flag with the extension on and off) is the
   measurement. **unbuilt.**

### Steel (the main host)

Steel serves one CDP URL at the container root, `ws://<host>:3000/` (`hands-on`). In the fleet that URL
comes from the node agent for the leased identity. Raw port 9223 is never published (D4).

```python
# Worker environment (set by the worker image, not by the model or the caller):
#   ANONYMIZED_TELEMETRY=false      # also disables BROWSER_USE_CLOUD_SYNC
#   BROWSER_USE_SETUP_LOGGING=false
#   BROWSER_USE_API_KEY             # must NOT be set
from browser_use import Browser

async def attach(cdp_url: str) -> Browser:
    await cdp_round_trip(cdp_url)            # fleet helper (unbuilt): Browser.getVersion, short retry
    browser = Browser(
        cdp_url=cdp_url,                     # ws://host:port/ or http://host:port (resolved via /json/version)
        keep_alive=True,                     # Browser-Use must never tear down the host's browser
        permissions=[],
        accept_downloads=False,
        auto_download_pdfs=False,
        highlight_elements=False,
        # deliberately absent: proxy=, storage_state=, user_data_dir=, headless=
        # allowed_domains= is advisory only (section 9)
    )
    await browser.start()                    # Agent(browser=...) starts it too; the System 1 path needs it explicit
    return browser
```

`Browser(cdp_url=...)` was measured against self-hosted Steel: 9 of 9 agent runs correct, 5.5-20.7 s wall
(`hands-on`, arm64 Docker, public static pages; section 16).

### Browserbase (opt-in home, D11)

`source-code` only. The Python SDK types show `sessions.create(project_id=..., browser_settings={"context":
{"id": ..., "persist": True}})` returning `connect_url`
(`<scratch>/sources/bb-sdk-python/.../session_create_params.py:74-79`, `session_create_response.py:11`).
**Never run: no Browserbase key exists.** The Browserbase guide owns session creation (BYO sticky proxy,
`recordSession: false`, per-Context lock, keepAlive plan check). This guide covers only the attach:

```python
# source-code only, never run
session = Browserbase(api_key=KEY).sessions.create(
    project_id=PROJECT_ID,
    browser_settings={"context": {"id": CONTEXT_ID, "persist": True}},
)
browser = Browser(cdp_url=session.connect_url, keep_alive=True, permissions=[],
                  accept_downloads=False, auto_download_pdfs=False, highlight_elements=False)
```

Rules that follow from D11: the fleet's lease layer, not Browser-Use, decides when the Browserbase
session ends. Browser-Use never sends `Browser.close`. `keep_alive=True` plus `os._exit` (section 13)
only drops the socket. Treat `connect_url` as a secret (inference: it grants control of the session).
**Browserbase attach: to measure** once a key exists.

### Any other CDP endpoint

`Browser(cdp_url="http://host:9222")` resolves `/json/version`. The same profile settings apply.

### Open dependencies (**unbuilt**, not decided in DECISIONS.md)

- **How the worker reaches a CDP URL that D4 says is never published.** Options: the worker runs on the
  identity's per-identity network next to the browser, or the node agent brokers a CDP socket. Brokering
  also solves fencing (section 13). **to decide in M1.**
- **Tab state at hand-off.** Browser-Use focuses the first tab it finds and can see, switch to and close
  any tab. The box patched that away because its Chromium was shared (section 10). With one driver at a
  time the filter is not needed, but the previous driver (Stagehand, the human viewer) may leave tabs
  behind (verification BRO-7 nuance). Define it at lease release: the releasing party closes its tabs, or
  fleetd normalises the browser to one blank tab before the next driver attaches.

---

## 5. The LLM layer

### What Browser-Use sends

- **One strict `response_format: json_schema` per step**, named `agent_output`. The schema is
  `AgentOutput` with a union of all action models. **No tool calling** (`llm/openai/chat.py:225-256`;
  captured HTTP body in the reasoning-models spike has no `tools`; reasoning-models verification REA-6).
- The action schema is large: a static build gives 17.3 KB (normal), 16.7 KB (flash) and 13.4 KB (flash
  with three actions excluded) (verification, unsourced-numbers item 4). The raw flash runs billed about
  3.5k prompt tokens per step although the messages alone are 10.6k characters. GLM's providers do not
  appear to bill the schema as prompt tokens. Budget by **billed tokens**, not by schema size.
- `ChatOpenAI` default `max_completion_tokens=4096`. On `finish_reason=length` it raises
  `ModelOutputTruncatedError` (400), even when content is `None` (`llm/openai/chat.py:277-283`,
  `llm/exceptions.py`).
- Page state (serialized DOM, capped at `max_clickable_elements_length=40000` characters, plus optional
  screenshots) leaves the **worker** for the model provider. It does not leave through the identity's IP,
  and the key stays in the worker. That is a plus compared with Stagehand's direct model config, which
  ships the key into the browser (reasoning-models verification REA-4). The data-handling question is
  still open: **pending Q-07** (zero-data-retention routing, per-client consent, or both).

### The measured baseline

`ChatOpenAI` against OpenRouter, GLM 5.3 Flash at `low`. This is what every Browser-Use number in this
guide was measured with.

```python
from browser_use import ChatOpenAI

MODEL = "z-ai/glm-5.3-flash"      # exact slug; never the ~z-ai/glm-flash-latest alias
llm = ChatOpenAI(
    model=MODEL,
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    reasoning_models=[MODEL],     # see below
    reasoning_effort="low",
    max_completion_tokens=CAP,    # Browser-Use default is 4096; the fleet value is to measure
)
```

Why `reasoning_models=[MODEL]`: Browser-Use sends `reasoning_effort` only for models on that list, and
the default list has only OpenAI o-series and gpt-5 models (`llm/openai/chat.py:65-80,189-192`). GLM 5.3
Flash has mandatory reasoning that defaults to `max`: `enabled:false` and `effort:"none"` both return HTTP
400, and with no parameter the model reasons at max (reasoning-models verification REA-5, `hands-on`).
Naming the model also drops `temperature` and `frequency_penalty`. Measured: `reasoning_effort: "low"`
was sent on every call, with 0-8 reasoning tokens (spike section 1). The box commit message says
unset effort costs "about 40 s and up to 6k completion tokens a step". **That figure was not re-measured**
(CONSISTENCY section 3b, D8).

### What D8 requires that this baseline cannot do

D8 says every model call goes through a client shim that: always sends `require_parameters`; validates
each response against the full schema including `pattern`; enforces a mandatory per-call `max_tokens`
cap; retries once on another provider on invalid output, `finish_reason=length` or a `null` element; and
sends only to a **bench-gated provider allowlist** with price and quantization caps. Strict `json_schema`
alone is not enough: enforcement is provider-dependent (one ZDR-listed provider returned wrong shapes
4/4; another returned YAML with HTTP 200 when pinned without `require_parameters`; reasoning-models
verification REA-7).

`ChatOpenAI` pointed straight at OpenRouter can send none of the provider preferences. D8 names two
routes. The fleet target is one of them; the choice waits on the per-provider bench (O-06, an M3 gate)
and on **pending Q-07**.

| Route | How | What the source shows | Status |
|---|---|---|---|
| **A. Baseline** | `ChatOpenAI` direct to OpenRouter | Measured with GLM (9/9 spike runs). No provider block, 4096 cap | `hands-on`. Not enough for production |
| **B. `ChatOpenRouter`** (needs 0.13.11) | `extra_body` carries the reasoning block, the cap and the provider block | No `reasoning_effort` or cap field: both go in `extra_body`. Never checks `finish_reason` (`ChatOpenAI` raises `ModelOutputTruncatedError` on `length`; this class does not, so a cut-off reply is caught only as a parse failure, below). OpenAI-client `max_retries` defaults to **10** (`ChatOpenAI`: 5), so set it low (`llm/openrouter/chat.py`, read for this guide, not run) | Measured with DeepSeek only (6/6 live, reasoning-models dossier). With GLM: **to measure** |
| **C. `ChatOpenAI` + `http_client`** | A custom `httpx.AsyncClient` rewrites the request body to add the provider block and cap | `ChatOpenAI` accepts `http_client` (`llm/openai/chat.py:62`). A request hook cannot see responses, so "validate and retry on another provider" needs a wrapping transport or a loopback endpoint instead | **to verify**, **unbuilt** |

```python
# Route B sketch (unbuilt; GLM through ChatOpenRouter in Browser-Use is not measured)
from browser_use import ChatOpenRouter
llm = ChatOpenRouter(
    model=MODEL, api_key=KEY, max_retries=2,
    extra_body={
        "reasoning": {"effort": "low"},
        "max_tokens": CAP,
        "provider": {"require_parameters": True, "only": ALLOWLIST},   # ALLOWLIST: from the O-06 bench; ZDR per Q-07
    },
)
```

What Browser-Use can do by itself, so the shim knows what it must add:

- A reply that is not valid for the schema fails to parse in **both** classes (`ChatOpenAI`
  `llm/openai/chat.py:300-318`; `ChatOpenRouter` `llm/openrouter/chat.py`) and surfaces as
  `ModelProviderError` with the default status 502, which is in the fallback-retryable set
  (`llm/exceptions.py`, `agent/service.py:1975-2010`; read for this guide, not run). With `fallback_llm`
  set, one bad reply triggers the one-way switch below. Without it, the step fails and counts toward
  `max_failures`. Either way there is no retry on another provider for the same model.
- `fallback_llm` is a **one-way switch for the rest of the run**: one malformed reply from the primary
  model moves the whole run to the fallback model. It triggers on `ModelRateLimitError`,
  `ModelOutputTruncatedError` and status codes 401, 402, 429, 500, 502, 503, 504
  (`agent/service.py:1983-2025`). Set it to the next rung of the D8 repair ladder: DeepSeek V4.1 Flash,
  reasoning off (different failure mode). It switches once; a second failure ends the run.
- The "lowercase" rule in the reasoning-models dossier is for Stagehand's click button argument only.
  Browser-Use's typed text must never be lowercased (reasoning-models verification missed issue 4). Typed
  text in this engine is code-supplied (section 6).

**Gap for DECISIONS.md:** "use `ChatOpenRouter` or an httpx hook" (D8) understates the work. The retry,
validation and logging parts are a build item, not a configuration.

### Token and cost levers

| Lever | Setting | Effect |
|---|---|---|
| `flash_mode=True` | Swaps the 24,145-byte `system_prompt.md` for the 2,417-byte flash prompt (`agent/prompts.py:60-82`). Drops thinking/evaluation/next_goal, turns planning off | Prompt tokens per step 8.1-8.4k -> 3.5k (-58%), 3/3 correct (`hands-on`). Model-dependent: for Anthropic 4.5 models it picks a 21 KB flash prompt, so "2.4 KB" holds for non-Anthropic models like GLM (verification missed issue 8) |
| `use_vision=False` | No screenshot per step | Screenshots add about 2.5k prompt tokens per step in the one defaults run |
| `use_judge=False` | No end-of-run judge call | The judge is one more call with screenshots (6.8k tokens, $0.0011). It is a model's opinion, not verification. Verify deterministically instead |
| `max_clickable_elements_length` | Default 40,000 characters of DOM | The main driver on real pages. Social pages are bigger than the test pages. **to measure** |
| `max_history_items` | Limits history sent each step | Not tuned |
| Message compaction | An LLM summary when **both** at least 25 steps since the last one **and** at least 40,000 characters of history (`message_manager/service.py:235-242`) | The dossier said "or"; the source says both |
| `extract` action | One LLM call over page markdown | Prefer `find_elements` (CSS) and `search_page` (regex): zero LLM calls |
| Token cap | `max_completion_tokens` / `max_tokens` | Mandatory (D8). Observed completions were about 120-170 tokens per call on easy pages. The spike's task runs and the 18 live GLM calls all ended with `finish_reason=stop` (`hands-on`, spike section 1; reasoning-models verification REA-9). A `done` with a long answer needs headroom. The fleet value is **to measure** in the M3 bench |
| Per-run step cap | `run(max_steps=N)` | Section 7 |

---

## 6. The System 1 path

This is the fast path: a decision model chooses, Browser-Use only executes. There is **no `Agent` and no
chat model** in the loop. `hands-on`: 2 recorded end-to-end runs, 0 chat calls, correct answer, 6.5-8.8 s
wall, mostly page loads.

### The loop (target, **unbuilt**; the pieces were each run in the spike)

```python
tools = Tools(exclude_actions=EXCLUDED)
AM = tools.registry.create_action_model()        # tools/registry/service.py:519

# 1. state
st = await browser.get_browser_state_summary(include_screenshot=False)    # ~0.1 s on a simple page
smap = st.dom_state.selector_map     # index -> node: tag_name, attributes, get_all_children_text(),
                                     #   absolute_position, is_visible

# 2. candidates (fleet code): label as  link "Text" -> href , dedupe, filter, rank, cap, add a "none" option
cands = build_candidates(smap)

# 3. decide (fleet /decide service, D7): one request packs target + blocker + done + risk
choice = await decide(cands, template="pick_target@N")

# 4. freshness guard: re-snapshot, look the element up again by identity, never trust the old index
fresh = (await browser.get_browser_state_summary(include_screenshot=False)).dom_state.selector_map
hit = find_by_identity(fresh, role=choice.role, name=choice.name, href=choice.href)   # exactly one match
if hit is None:
    return MISS                                  # climb the ladder; never click

# 5. act
await tools.act(AM.model_validate({"click": {"index": hit.index}}),
                browser_session=browser, page_extraction_llm=None)
# typed text is code-supplied, from an approved manifest item:
#   {"input": {"index": n, "text": approved_text}}
# 6. verify: code first (URL change, element present), then a decider noul. Reads: find_elements / search_page.
```

### Why the freshness guard is mandatory

`hands-on` (3 of 3 runs): after navigating from the home page to the Poetry category, a click on index
219, which was "Travel" on the *home* page, returned `Clicked a "Travel"` and went to `travel_2`. Browser-Use
**executed the stale index, it did not refuse it**. Cause (`source-code`, verification BRO-4):
`get_dom_element_by_index` reads `_cached_selector_map` (`session.py:2459-2474`), which is cleared only on
reset or a state timeout (`664`, `1643`), not on navigation. The index is the backendNodeId unless IDs
collide (`serializer.py:649-658`). The stale click only landed on a "same-looking" link because the sidebar
was identical on both pages. On a changed layout the call acts on whatever sits there.

So, per D5: re-snapshot immediately before every act. Match the target by **role, accessible name and
href**, then click the index found in the *fresh* map. Zero or two matches is a **miss**, not a click.
The same rule applies to a model-chosen index inside an `Agent` run (section 8).

### Option caps and page size

- **Hard cap: 255 options** for Jev, Clef and Perplexity. 256 returns HTTP 400 "Too many choices. Must
  have at most 255 choices" (`hands-on`, verifier, 2026-10-10). OpenAI Decisions' cap is **unstated**.
  Minimums differ (Clef 2, Perplexity 1) (system1-models verification S1-08).
- **180 is a working step size**, jev-automation's client constant `MAX_ELEMENTS`
  (`core/elements.ts:34`), not a provider limit (C-06). The dossier called it "Jev's ~180"; do not.
- **Token cap binds first.** A 180-candidate step is 4,911-6,217 input tokens (`hands-on`, verifier).
  Jev's limit on 2026-10-10 is 100K tokens/s, about 16-20 steps/s; it was 250K tok/s and 1,200 rpm on
  2026-09-17 and can change without notice. Prune candidates well below 180 and plan spillover across
  providers (D7, system1-models verification V-04).
- **Cost grows with options:** $0.000115 at 71 options, $0.000363 at 255 (`hands-on`, verifier). A
  realistic 180-candidate Jev step is about $0.0002-0.00026.
- **A social feed will exceed the cap.** The spike page gave 201 raw nodes, 70 labelled (+ `none`).
  Virtualised infinite feeds were not exercised; the serializer sends only what is rendered, so long feeds
  need scroll-and-re-snapshot loops (inference). Use `is_visible` and `absolute_position` to build the
  candidate list from the viewport.

### Decider rules that apply here (D7, system1-models)

- **Always include `none`.** Below the per-template threshold: abstain and climb the ladder.
- **Option-order bias.** Jev leans to the first option. DOM order puts headers and navigation first.
  Shuffle candidates or ask in both orders on low-margin steps.
- **Confidence is not portable** across providers or serving hosts (the same Clef-flash weights gave 0.43
  on Cloudflare and 0.74 on PrimeIntellect). Thresholds are per template x model x provider. Pin and log
  the serving provider. Do not carry over the ">0.85" from the Gemini conversation.
- **Modality is enforced by the router.** Jev is text-only and silently accepts images (it bills them as
  text and returns a plausible number). A screenshot question must go to Perplexity Decider, Clef (once
  tested) or OpenAI.
- **A decider is not a safety control.** Page text is untrusted and can steer answers. Effects are gated by
  code (section 8), never by a probability (D5).
- **Never ask a decider to write, retype or extract free text.** Code copies text verbatim.

### What was and was not measured

- Measured: Jev picked "Poetry" out of 71 options at 0.94-0.96 confidence in 315-388 ms; the verifier's
  independent call on 75 options chose Poetry at 0.98 in 359.5 ms. One easy static page.
- Not measured: accuracy on dense social or lead-gen pages (O-15). The only hard evidence is a Jev miss in
  the box README (search "first result", 0/3).
- `Tools.act` index execution ran in the spike (`direct3`, `direct4`) against Steel containers on arm64
  (arm64 Docker), on one public static page.
  D5 lists it as a gate to repeat against a real session on an amd64 droplet (O-17). **to measure in M1**
  (see section 18). Cross-origin iframes and shadow DOM: user-agent shadow roots are mis-reported as open
  upstream (#5817). **to measure.**
- **Detectability: what was run, what was only read, what is untested.** The engine comparison is in
  section 14; the click-level facts are here.
  - **Run (`hands-on`, n=1 per condition, antidetect verification AP-3;
    [spike results](../../research/spikes/antidetect-proxies/RESULTS.md) section 1):** attach by `cdp_url`,
    navigate, and two `get_browser_state_summary` calls did not trip the public `isAutomatedWithCDP` check on
    Chromium 152 or CloakBrowser 146. That run attached to the **bare browser**: no Guard, no proxy forwarder,
    no persona probe. It used `BrowserSession(cdp_url=..., keep_alive=True)` with library defaults, not the
    fleet's attach settings from section 4 (defaults leave highlight on, grant clipboard and notifications to
    all origins, and the first state call took a screenshot). It included **no click, no typing and no
    scroll**. So this engine has no measured action-level result at all, and none for the fleet's own
    configuration.
  - **Read in source, never run against a detector (`source-code`, c75e847):** `Runtime.enable` is sent from
    only two places, the actor API (`actor/page.py:69`) and the Anthropic computer-use integration
    (`integrations/anthropic/browser_use.py:251`). The MCP server's coordinate click dispatches
    `ClickCoordinateEvent` without `force` (`mcp/server.py:793`), and a non-forced event calls
    `get_dom_element_at_coordinates` (`default_action_watchdog.py:407`), which reaches the actor path
    (`session.py:2523-2528`). The Agent's **own** coordinate click passes `force=True`
    (`tools/service.py:679`) and skips that call. (AP-3 says the "default Agent click uses `force=True`";
    line 679 is the *coordinate* click, not the index click.) That coordinate variant is registered only when
    the model name contains `claude-sonnet-4`, `claude-opus-4`, `claude-fable-5`, `gemini-3-pro` or
    `browser-use/` (`agent/service.py:326-333`). GLM 5.3 Flash and DeepSeek V4.1 Flash match none, so the
    fleet's `click` takes an index only today. A change of primary model to a matching name would turn the
    coordinate variant on with no other setting, which is why the self-check in section 2 asserts it.
  - **The click this guide uses, and the part that is untested.** The index click (`_click_by_index` ->
    `ClickElementEvent`, `tools/service.py:704-731`; handler `default_action_watchdog.py:338-388`, body
    `703-1040`) reaches none of the `Runtime.enable` sites. By the same reading it sends
    `Page.getLayoutMetrics`, `DOM.scrollIntoViewIfNeeded`, element geometry (`DOM.getContentQuads`, then
    `DOM.getBoxModel`; `session.py:2827-2860`) and an occlusion check (`DOM.resolveNode` plus
    `Runtime.callFunctionOn`; `default_action_watchdog.py:574-601`), then `Input.dispatchMouseEvent`
    `mouseMoved` at the centre of the element's largest visible quad, a fixed 50 ms sleep, `mousePressed`, a
    fixed 80 ms sleep, `mouseReleased`, and `Runtime.runIfWaitingForDebugger` in a `finally`. There is no
    mouse path. If the element is occluded or has no geometry it runs a script `this.click()` instead; a
    script-made click event is untrusted to the page (inference from DOM behaviour, **to measure**).
    **A click through `Tools.act` against the detection page was not run, and neither was typing** (1-10 ms
    between key events, `default_action_watchdog.py:1892-1998`, issue #3825). The test to run is DABI's
    separate behavioural check, which "detects CDP mouse leak" (text in `raw/runD.json`; antidetect
    verification, missed issue 9). That verification infers that both Stagehand and Browser-Use click with
    `Input.dispatchMouseEvent`, so, by the same inference, this index click is exposed to the same behavioural
    signal as any CDP click. **to measure in M1**, first on the bare browser and then with the Guard attached
    (section 18).
  - **Rule kept (G3.8, `MILESTONES.md`):** on a logged-in identity the worker never uses `browser_use.actor`,
    `get_dom_element_at_coordinates`, any coordinate click (the MCP server's or the Agent's own), the MCP
    server, or the Anthropic integration. The rule does not wait for the click result above: none of the
    banned paths was shown safe by a run, and the fleet needs none of them. G3.8 names the actor API and the
    coordinate click; this guide's list is wider (it adds the MCP server and the Anthropic integration, AP-3
    missed issue 10). The fleet's worker code never imports or calls any of them, and a lint test over the
    worker package checks that (**unbuilt**). The coordinate-click ban is also checked structurally by the
    self-check (section 2, item 9).

### Other plug points

| Hook | Use | Evidence |
|---|---|---|
| `register_new_step_callback(state, output, n)` | Runs after the model answers and **before** actions execute. Mutating `output.action[i]` changes what runs. This is where the gate in section 8 sits | `hands-on`: swapped "Travel" to "Poetry" |
| `register_should_stop_callback()` | Polled each step. Lease lost, cancel, spend cap reached, blocker detected | `source-code` |
| `register_done_callback` | Collect the result | `source-code` |
| Replace the judge | `judge_llm` must return `JudgementResult{verdict,...}`; a decider noul fits | `source-code` |
| `Agent(llm=<decider>)` | Not recommended: it must return a full `AgentOutput`. Deciders cannot produce typed text or multi-action lists | `hands-on` with a scripted stand-in (0 network calls); fragile |
| Custom tool via `@tools.action(...)` | Let the model delegate a choice to the decider | `source-code` |

---

## 7. Agent settings, tools and secrets

### Fleet defaults for the `Agent`

| Option | Value | Reason |
|---|---|---|
| `llm` | explicit, never `None` | `None` silently becomes the hosted `ChatBrowserUse` |
| `browser` | the `Browser` from section 4 | |
| `flash_mode` | `True` | 58% fewer prompt tokens per step; turns planning off |
| `use_vision` | `False` (or `'auto'`, only after a `screenshot` action) | Cost; screenshots are not scrubbed by `sensitive_data` either |
| `use_judge` | `False` | Verify deterministically |
| `max_failures` | `3` | Then one forced final `done` (`final_response_after_failure=True`): treat that answer as untrusted |
| `llm_timeout` / `step_timeout` | `90` / `120` seconds | Defaults are 75 s (by model name) and 180 s |
| `directly_open_url` | `True` | The URL in the task text is opened with no LLM call (step 1 was a no-LLM navigate in every spike run) |
| `enable_signal_handler` | `False` | The worker owns signals |
| `calculate_cost` | `False` | The fleet logs OpenRouter's billed `usage.cost` and serving provider per call instead |
| `max_actions_per_step` | default `5` | The gate evaluates each action in order and drops everything after the first blocked one. Lowering it costs more LLM calls. **to measure** |
| `fallback_llm` | next rung of the D8 ladder | Section 5 |
| `extend_system_message` | a short note: public pages only; say so in the final answer if blocked, do not retry | Advisory. The model can ignore it. It is never a control |
| `sensitive_data` | **unset** | See below |
| `register_new_step_callback` / `register_should_stop_callback` | the gate and the stop checks | Section 8 |
| `run(max_steps=N)` | small `N` from the task contract | The default is 500. The spike used 8. No fleet value is chosen: **to measure** per procedure class |

### Tools and excluded actions

Built-in actions in 0.13.11 (24, `hands-on` from `Tools()`): `done, search, navigate, go_back, wait, click,
input, upload_file, switch, close, extract, search_page, find_elements, scroll, send_keys, find_text,
screenshot, save_as_pdf, dropdown_options, select_dropdown, write_file, replace_file, read_file, evaluate`.

`Tools(exclude_actions=[...])` removes built-ins. **Always excluded:**

| Action | Why |
|---|---|
| `upload_file` | `DOM.setFileInputFiles` takes a path that must exist on the **browser host**. With `is_local=False` the model may name **any** absolute path in the Steel container. Social posting uploads go through a separate fleet action with a media whitelist (staged by Steel's files API), never through the model. The box excludes it for the same reason |
| `save_as_pdf` | Writes files nobody collects |
| `evaluate` | Runs arbitrary JavaScript in a page that may be a logged-in client session. The dossier said "consider"; the fleet default is to exclude. **D6 lists only uploads and PDF; it should add `evaluate`** |

`write_file`, `replace_file` and `read_file` work in the agent's own data directory on the worker
([dossier Q3](../../research/dossiers/browser-use.md)). The dossier did not assess them further. Decide in the M1 smoke test whether to exclude them (each excluded action also shrinks the
schema). **to decide.**

Typing and key presses are **not** excluded, because search boxes need them. The gate (section 8) decides
per target.

Reads that cost no LLM call: `find_elements` (CSS), `search_page` (regex). `extract` is an LLM call.

### `sensitive_data`: stays unset

Humans log in; agents never type credentials (D14). `sensitive_data` only protects text: the model sees
`<secret>name</secret>` placeholders and the registry substitutes at execution if the URL matches
(`tools/registry/service.py:427-480`), outgoing text is scrubbed, saved history is filtered (nested lists
fixed in 0.13.11). **Screenshots are not scrubbed**, and the protection leans on `allowed_domains`, which
pages can bypass (#5815, #4763). The worker refuses to start a task whose spec carries `sensitive_data`,
credentials, cookies or tokens (**unbuilt**).

---

## 8. Policy gate for open-ended tasks (**unbuilt**, the core of the L4 safety story)

D5 and D17 say an L4 `task` is **read-mostly**, and that irreversible actions are gated by deterministic
policy "on every rung, including free-form `act` and `task`". DECISIONS.md does not say how. Browser-Use
has no notion of "read-only": its model can click any element. This section is the mechanism. It is a
design, not a measurement. **Gap to flag in DECISIONS.md.**

### Where it sits

In the worker, outside the model: `register_new_step_callback`. It fires after the model has answered and
before the actions execute, and changing `output.action` changes what runs (`hands-on`). A second hook,
`register_should_stop_callback`, ends the run.

### What it does at each step

1. **Fresh snapshot** (about 0.1 s on a simple page). For every proposed action that carries an index,
   find the node in the fresh map and require the same role, name and href as in the `state` the model
   saw. Mismatch: block as stale. This is the section 6 guard applied inside `Agent` runs. The model
   sees a snapshot, thinks for 1-3 s, then acts; the page can change in between.
2. **Classify each action** from the live node and the task's allowance, with no model:
   - Read, always allowed: `navigate`, `go_back`, `wait`, `scroll`, `search_page`, `find_elements`,
     `find_text`, `extract`, `screenshot`, `switch`, `dropdown_options`, `done`.
   - `click`: allowed only for a navigational target. A link whose href stays on a host in the run's host
     set and does not match the site's effect patterns (logout, follow, compose, share, delete,
     unsubscribe, intent URLs and similar), an expand/collapse or pagination control, or a short allow
     set of benign controls (Next, More, Close, consent accept). Any other button, any
     `input[type=submit|button]`, any control inside a `<form>` that is not a search form, and any
     accessible name matching an effect verb (post, send, reply, comment, publish, share, follow, like,
     repost, delete, remove, report, block, buy, pay, order, subscribe, sign up, submit, confirm,
     connect, invite, message) is **effect-like**.
   - `input`: allowed only into a search-type field (`type=search`, `role=searchbox`, or a name/label that
     says search or query). Never `type=password`. Never a contenteditable or textarea that is a composer.
   - `send_keys`: Enter only straight after an allowed search `input` in the same step. Other keys are
     effect-like, and any chord (such as Ctrl+Enter) is blocked.
   - `upload_file`, `save_as_pdf`, `evaluate`: not available (excluded).
3. **Effect-like or stale -> stop.** Replace the action with a harmless one, set the stop flag, return
   `needs_approval` with the proposed action and the node description to fleetd (D13, D17 `approvals`).
   Nothing auto-resumes. An approved effect is a new request through the `act`/`publish` path with an
   approved manifest item, never a continuation of the model's own step. **to verify** which replacement
   action is safe (a no-op `wait`), and that the loop ends cleanly.
4. **Stop conditions** (in `register_should_stop_callback`, all deterministic): lease lost or human takeover;
   cancel; spend or wall-time cap reached; login wall, checkpoint or CAPTCHA detected from deterministic
   signals (URL patterns, known challenge frames, optionally a decider noul); budget of steps. A blocker
   sets `needs_reauth` or `checkpoint` and hands off to a human (D14). Browser-Use has no CAPTCHA solver and
   `captcha_solver=True` only waits for Cloud's solver event, so it is never set.

### What it cannot do

A structural classifier cannot prove a control is harmless. Icon-only buttons, labels in other languages,
and links that change state on GET all get through a verb list. So:

- Default-deny for every non-link control. Effect patterns are per-site data kept with the site class.
- **Proposed:** the `task` tool runs under a token that has neither `publish` nor `dm` scope. D13 defines
  the scopes (`read`, `draft`, `publish`, `dm`) and D17 marks `task` as a write tool, but neither maps
  `task` to a scope. This mapping is this guide's proposal, pending the owner. The gate is a second layer,
  not the only one.
- D13's journal and read-back catch an effect after the fact. They do not prevent one. An effect that
  slips past the gate is detected, not stopped.
- The false-block and false-allow rates are **to measure** in M3 with planted effect controls (a test
  page with "Post", "Send", an icon-only submit button, a GET-based "follow" link).

### Recommendation for the owner (**pending Q-01**)

Run open-ended exploration in a browser with **no client login** wherever the goal does not need one
(open-web lead generation, public pages, QA of clients' public pages: D2 items 2 and 4). Running L4 inside
a client's logged-in identity should be the exception, allowed per procedure. DECISIONS.md has no identity
type for logged-out research browsing; adding one is the owner's call.

---

## 9. Boundaries: `allowed_domains` is not one

### The facts

- `allowed_domains` is checked only on `NavigateToUrlEvent`, `NavigationCompleteEvent` and
  `TabCreatedEvent`, and `data:`/`blob:` URLs are explicitly allowed (`security_watchdog.py:199`).
  `NavigationCompleteEvent` is dispatched only inside `on_NavigateToUrlEvent` and the downloads watchdog.
  `_is_url_allowed` has three callers, all in `security_watchdog.py`. So navigation the model's own
  **clicks** cause in the same tab never reaches the check (verification BRO-12, stronger than the
  dossier's claim).
- Open upstream: #5815 (page-initiated navigation, redirects, popups; self-labelled severity high) and
  #4763 (`data:`/`blob:`). `third-party`, consistent with `source-code`.

### What the fleet does

- It may set `allowed_domains` as an advisory speed bump to reduce wandering and wasted steps. It is never
  cited as protection.
- The boundaries are elsewhere:
  1. **The container's only egress is the node-local forwarder** (D4, D10). Browser-Use cannot widen it.
  2. **A destination allowlist at the forwarder** (HTTP CONNECT host) would be the real per-run boundary.
     **DECISIONS.md does not specify it.** D10 says the forwarder fails closed on an exit-IP change, not
     that it filters destinations. Proposed, **unbuilt**, owner decision.
  3. **The in-browser Guard** (browser-wide `Fetch.enable`) refuses private, loopback and metadata
     addresses. It is ported per D16/C-25 and its CPU cost per awake profile is unmeasured.
  4. **The step gate** (section 8) for effects.
- Instructions in the prompt ("stay on example.com") are never a control.
- Browser-Use's own warning ties `sensitive_data` to a locked-down `allowed_domains`
  (`agent/service.py:533-580`). The fleet leaves `sensitive_data` unset (section 7), so it never depends on
  that pairing.

---

## 10. Browser-box confinement patches: what still matters

`agents/browseruse/runner.py` confines Browser-Use to one tab of a **shared** Chromium. The fleet has one
browser per identity and one driver at a time, so most of the patches go away. The box's mutex idea
becomes the fleet lease (D12): acquire, renew and takeover are separate operations with a fencing token.
It is not a new component.

| Box patch (written against 0.13.10) | What it stops | Fleet decision |
|---|---|---|
| Filter FOREIGN tabs (`SessionManager.get_all_page_targets`, `BrowserSession._cdp_get_all_pages`); refuse CDP sessions on them (`get_or_create_cdp_session`, `get_target_id_from_tab_id`); refuse closing them (`on_CloseTabEvent`, `_cdp_close_page`) | Browser-Use adopting, driving or closing another client's tab. Verified in the box: it took Jev's first tab | **Drop**, with the tab hand-off rule from section 4. They come back if any browser is ever shared between two drivers. The patched files are unchanged between 0.13.10 and 0.13.11 (verification BRO-7), but no run has exercised them on 0.13.11 |
| `DownloadsWatchdog.attach_to_target` made a no-op | The watchdog switching the **whole browser** to download into a temp dir (a local path that does not exist in Steel) | **Keep as one-line insurance** until the smoke test shows `accept_downloads=False` is enough. It is unverified whether that flag stops the browser-wide call |
| `permissions=[]` | Clipboard and notifications granted to every origin | **Keep.** A consistent identity should not suddenly grant notifications everywhere |
| Version pin + `--self-check` | Silent breakage on upgrade | **Keep the pattern, write it fresh** (section 2) |
| `reasoning_models=[model]` | GLM at max effort | **Keep** (section 5) |
| `os._exit` from inside the event loop | The shutdown hang | **Keep** (section 13) |
| `exclude_actions=["upload_file","save_as_pdf"]` | Remote file exfiltration, files nobody collects | **Keep and add `evaluate`** (section 7) |
| Box `AGENT_OPTIONS` | `use_vision=False, use_judge=False, max_failures=3, llm_timeout=90, step_timeout=120, calculate_cost=False, directly_open_url=True` | **Keep and add** `flash_mode=True`, `enable_signal_handler=False`, `highlight_elements=False` |
| Box progress file and result file, `finish()` | Kill-safe reporting | **Keep** (section 13) |

Do not import the box runner. It refuses 0.13.11, builds the session the wrong way (section 4) and ships
patches the fleet drops. The box's SSRF code (`security.py`) and `Guard` are reused by the fleet under D16
and C-25; they live outside Browser-Use.

---

## 11. Replay

### What exists (OSS, `source-code` + `hands-on`)

- `agent.save_history(path)`, `Agent.load_and_rerun(path, variables={...}, max_retries, skip_failures,
  delay_between_actions, max_step_interval, summary_llm, ai_step_llm, wait_for_elements)`,
  `rerun_history(history)`, and `detect_variables()` to parameterise typed values.
- Elements are re-found by five match levels: EXACT hash, STABLE hash, XPATH, AX_NAME, ATTRIBUTE
  (`agent/service.py:3584-3685`). Indexes are remapped ("index 364 -> 360, matched at EXACT level").
- It is not documented in the vendor docs; it exists in source only
  ([corpus INDEX section 10](../../research/corpus/browser-use/INDEX.md)).

### What was measured

Three replays of a 3-step and a 4-step history on one static site re-executed every click from a parked
page (`hands-on`, spike sections 4 and 5d; verification BRO-8):

| Replay | LLM calls | Cost |
|---|---|---|
| Default `summary_llm` (the agent's own model) | 1: `rerun_summary`, 2.9-3.0k prompt tokens **with a screenshot** | $0.00018-0.00048 |
| Stub `summary_llm` (any object with `ainvoke`) | **0** | $0 |

### Rules

1. **Browser-Use replay is not the L1 tier** (C-07, D5). L1 is the fleet's own cache of Stagehand `Action`
   objects, each re-verified on element identity before acting. Browser-Use `rerun_history` always ends
   with `_generate_rerun_summary`, which uses the agent's LLM unless a summary model is supplied. It counts
   as zero-call only with a stub. Even then it is not part of the System-1-share numerator until an
   independent identity check wraps it.
2. **It replays the old `done` text.** The stored answer is re-emitted; the page is not re-read. A data
   task replayed this way returns stale data. Re-read values with `find_elements` or `search_page`.
3. **`extract` steps re-run as LLM "AI steps"** (`ai_step_llm`).
4. **The weaker match levels are fuzzy.** XPATH, AX_NAME and ATTRIBUTE can land on a different element.
   False matches are unmeasured. So an effect-like step is never replayed through Browser-Use: effects go
   through D13's approved-manifest path.
5. **Use it for** (a) recording what an L4 run did, so the owner can review it as a candidate procedure
   step (D5: "a rung that succeeds on a new page becomes a candidate L1 step", released by D13's rules);
   and (b) cheap re-runs of read-only navigation sequences with a stub `summary_llm`,
   `skip_failures=False`, and the values re-read separately.
6. **Saved histories are client data.** They hold URLs, titles, tab info, the clicked elements and
   screenshot paths (`AgentHistory`, `BrowserStateHistory`; `source-code`, content not inspected). Store
   them under the fleet's retention rules, not in a temp dir. Retention policy: **pending Q-07**.
7. Self-heal on a match failure (escalate to a decider over a fresh `selector_map`) is something the fleet
   would build (**unbuilt**).
8. `rerun_history` calls `self.close()` in its `finally` (`agent/service.py:3282`): do not reuse the agent.

### Not replay

- Browser-Use "skills" (`Agent(skills=[...])`) are a **Cloud** feature (section 17).
- Cloud "rerunnable scripts" are Cloud-only and still LLM-driven per run.
- The Browser Harness recorder saves screenshots and an event trace for videos, not for replay.

---

## 12. Persistence

**Persistence lives in the browser host, not in Browser-Use.** The unit is the Steel user-data-dir
tarball (D4), encrypted at the bundle layer, with the session-context export as the cookie source of
truth. Browser-Use drives the browser; it stores nothing the fleet should keep.

### Do not rely on `storage_state`

`hands-on` (spike section 5a; verification BRO-5, `source-code` explains it deterministically):

| Check | Result |
|---|---|
| Cookies, two origins | Restored for both |
| localStorage, two origins | Saved and restored for **the focused tab's origin only**; the other origin was lost (`_cdp_get_origins` reads one frame tree, `session.py:3576-3590`) |
| A newer localStorage value, then reload | **Reverted to the saved value.** The restore script runs on every new document (`storage_state_watchdog.py:269-305`) |
| `export_storage_state()` | Cookies only; `origins` is hard-coded to `[]` (`session.py:1469`) |
| IndexedDB | Never captured |
| Auto-save | On stop, and every 60 s if cookies changed |

Setting it on a live identity would overwrite the identity's real localStorage on every page load. The
self-check asserts `storage_state is None` (section 2).

### What Browser-Use does on a remote session

- `user_data_dir` does nothing for persistence on remote CDP: Browser-Use never launches Chrome. It still
  allocates an **empty** temp dir (`browser-use-user-data-dir-*`) per session, one per process. `os._exit`
  skips `finally` and `atexit`, so delete the dir explicitly before exiting, and sweep stale ones when a
  worker starts (covers killed processes; verification missed issue 7).
- The local-launch trap (a path containing "chrome", or `channel=chrome`, is copied to a temp dir, so
  logins are lost) does not apply to remote sessions.

### What the browser host must do (D4; restated for operators of this engine)

- Self-hosted Steel maps **any** `userDataDir` to one fixed directory (`session.service.ts:180-183`).
  Profile B read profile A's data (`hands-on`, n=1). One profile per container or volume. **Do not copy the
  dossier's Q4 sample**, which sends a per-profile `userDataDir` and a credentialed `proxyUrl`: Steel
  ignores the first and echoes the second over its unauthenticated API.
- Cookies written 2 s before release were lost; 40 s kept (`hands-on`, n=1 each). Chromium commits its
  cookie store on a 30 s timer (`source-code`, Chromium main, `kCommitInterval = 30 s`; Steel's pinned
  Chrome build was not checked). Social sites rewrite cookies constantly, so the D4 hold of at least 31 s
  is a **floor, not a guarantee**. The session-context export is the cookie source of truth; a
  graceful-flush release is an M1 test (C-03).
- Browser-Use **never** releases the session or closes Chromium. A Browser-Use run can change cookies, so
  the lease is marked dirty at the end of every run and the node agent applies the D4 safe-release order.

---

## 13. Process model

**One Browser-Use agent per OS process, one process per task, with a hard kill timer.** Same shape as the
box runner.

- **Spec in, result out.** The supervisor passes a JSON spec on **stdin** (never argv; the CDP URL is a
  capability). The worker appends one JSON line per step to a progress file from
  `register_new_step_callback`, so a task killed at its timeout still reports what it did, and writes the
  finished run to a result file. Result fields to borrow from the runner: `status`
  (`done | failed | incomplete | error`), `success`, `answer`, `steps`, `urls`, `final_url`, `tokens`,
  `errors`, `agent_seconds`. The fleet adds the gate verdicts, cost, serving providers and evidence refs.
- **Leave from inside the loop.** Write the result file, flush, then `os._exit(0)` **from inside the
  running event loop**. `asyncio.run()` teardown hung until the hard timeout in 3 of 3 runs that left a
  session un-stopped (`direct1`, `direct2`, `direct_dbg`); after switching to `os._exit` inside the loop
  there were 0 hangs (`hands-on`, spike section 7). Only `direct2` has a full step trace; the other two
  show a CDP reconnect loop. The cause is **inferred, not isolated**: an un-stopped session's CDP
  auto-reconnect firing during teardown (`_intentional_stop` stays False, `session.py:589-640,2249`).
  No run used `keep_alive=False` as a control. The prescription does not depend on the cause.
- **Hard kill timer** in the supervisor: `max_steps x step_timeout + margin` (formula from the dossier).
  The margin is **to measure**. Kill the process, not just the task.
- **Readiness probe before attach** (section 4).
- **Concurrency inside one process** worked in a short test: two agents on two browsers, in one loop or two
  threads; two agents on the same browser in one loop; scripted LLM, about 6 steps each (`hands-on`).
  "Not reproduced" is not "safe": the bubus cross-loop bug #5509 (open since 0.13.8; fix PR bubus#34
  unmerged; bubus pinned 1.5.6) is the known risk at scale. At exit there were 16 "Task was destroyed but
  it is pending" and 4 "Event loop is closed" messages. So the fleet runs **one agent per process**
  regardless of what a test showed. Worker memory per Browser-Use process is **to measure**; it is outside
  the D12 browser slot.
- **Single driver per identity.** The lease (D12) is the only mutex: Stagehand, Browser-Use and the human
  viewer never drive at once. Browser-Use gives fleetd no per-command hook, so fencing happens at two
  places: the worker polls lease state in `register_should_stop_callback`, and the node agent closes the
  worker's CDP socket on takeover or expiry. That requires the node agent to sit in the CDP path
  (section 4, open dependency). **unbuilt.**
- **Cancel** (`cancel`, D17): fleetd kills the worker process; the node agent normalises tabs.
- **Version and environment:** the worker runs the pinned image with the environment in section 3.

---

## 14. When the router picks Browser-Use

The router is fleetd's and is **unbuilt** (D5, D17). This is the rule it follows.

**Pick Browser-Use (L4) only when all of these hold:**

1. No released procedure covers the goal (not L0, not L1), and it cannot be cut into scoped steps for
   Stagehand (L3) because the number of steps or pages is unknown. Examples: "find where this company
   lists a pricing contact", "check these public pages for X".
2. The goal produces **information, not effects.** Effects go through `act`/`publish` with an approved
   manifest item (D13).
3. The task contract carries a step cap, a wall-time cap and a spend cap.
4. Preferably a browser with **no client login** (section 8 recommendation, **pending Q-01**).

**Do not pick it for:**

| Case | Use instead |
|---|---|
| A known path | L0 code or API; L1 replay of Actions |
| One scoped step or a typed extraction | Stagehand L3 (`extract` with a schema) |
| Publishing, replying, DMs, deleting, following | The API channel first (D2); otherwise a human-approved manifest item |
| Typing into a React editor (X reply box, Draft.js) | Not L4. Doubled or dropped first characters (#4461, #3889, #5721); verify read-back on the effect path |
| Login, 2FA, CAPTCHA, checkpoint | A human through the live viewer (D14). Browser-Use has no solver |
| Visual-only decisions, screenshot grounding | A screenshot-capable decider or the GLM vision path (D8) |
| Infinite or virtualised feeds | Unmeasured. Scroll-and-re-snapshot with a decider, or a human |

**Detectability: where Browser-Use stands against the other L1/L2 candidates (D6, O-02).** Short version:
Browser-Use has **less measured exposure** than Stagehand v4. It does **not** have a measured clean click. The
router must not read it as "the cleaner engine for accounts" until the M1 executor test (G1.4) includes the
click. The click-level facts are in section 6. All data below is `hands-on`, n=1 per condition, arm64 Docker,
Chromium 152 and CloakBrowser 146, against public detection pages only (no platform).

| Candidate | Measured against `isAutomatedWithCDP` | Not measured |
|---|---|---|
| Stagehand v4 (4.2.0) | Trips on attach. Its extension stays resident after `close()` and keeps tripping new tabs until `Extensions.uninstall` or a browser restart. After uninstall a raw client was clean (AP-2) | The fleet loads the extension with a launch flag (`steel-profile` "mode A"), not over CDP as measured, and whether uninstall works for a flag-loaded extension is untested ([steel-profile section 10.3](../infra/steel-profile.md)). Clicks and typing |
| Browser-Use `Tools.act` | Attach, navigate and two state reads were clean (AP-3) | **Element click, typing, scroll** (section 6). The Guard, the proxy forwarder, the persona probe. DABI's behavioural check |
| Minimal CDP executor (**unbuilt**) | Only a raw control exists: `createTarget`, `attachToTarget`, `Runtime.evaluate`, no `Runtime.enable`. Clean on both browsers (`v_rawctrl`, `n_rawctrl`, `c_rawctrl` in the [spike results](../../research/spikes/antidetect-proxies/RESULTS.md) section 1) | Everything an executor adds: snapshot, clicks, typing |

How to read the table:

- **No candidate has been measured clicking or typing against a detector.** Browser-Use and the raw control
  were both clean with no actions, so there is no measured action-level advantage for Browser-Use. The
  difference that was measured is at attach: Stagehand's extension queues `Runtime.enable` and
  `Target.setAutoAttach{waitForDebuggerOnStart:true}` for every new target (AP-2, `service-worker.js`
  L59845), and AP-2 did not isolate which call raises the flag. Browser-Use sends no `Runtime.enable`
  (section 6), and its own `Target.setAutoAttach` calls use `waitForDebuggerOnStart: false`
  (`session.py:1924,2214`, `session_manager.py:428`; `source-code`, read for this guide).
- **Browser-Use's clean result holds only on a browser that never loaded the Stagehand extension.** A
  Browser-Use run on a browser where the extension was still resident flagged `isAutomatedWithCDP`
  (`v_bu_state.json`, a confounded run that is itself the evidence). The router therefore counts Browser-Use
  as the lower-exposure engine only when the wake's effective `extension_mode` is `none` (section 4 rule 6;
  [steel-profile](../infra/steel-profile.md) section 2 and section 5).
- **No engine result transfers to the fleet stack.** The spike attached to the bare browser. Every fleet wake
  adds the Guard, which sends `Fetch.enable` and `Target.setAutoAttach` with `waitForDebuggerOnStart: true`
  (`gateway/gateway/guard.py:58-61,186-187`), the same auto-attach shape AP-2 reads in the extension code and
  unlike Browser-Use's own `false`. Whether the Guard trips the check is unmeasured. The persona probe through
  `Runtime.evaluate`, the proxy forwarder, headless against headful, and the viewer are also absent from the
  data. G1.4 in [`MILESTONES.md`](../../MILESTONES.md) tests each executor alone, inside the real stack with
  the Guard attached, and for behavioural input, and logs the CDP methods each one sends (section 18).

What this means for the router:

- "Browser-Use `Tools.act` as the L2 executor on a logged-in identity" is an **unproven candidate, not a
  preference.** The router row is filled per site class from M1 data that includes the click (D6, O-02).
  **to measure.** Until then the only measured difference is at attach, against Stagehand left loaded. There
  is no measured basis to prefer Browser-Use over Stagehand with uninstall, or over a minimal CDP executor.
- **L4 is not shown to stand in for a missing L3 on an account.** If M1 removes Stagehand from logged-in
  identities, AP-3 does not show that a Browser-Use `task` can take over. It covers no click, the loop is
  read-mostly by design, and the step gate (section 8) stops every effect-like step, where an L3 `act` can run
  one under an approved manifest item (D17). Whether L4 may cover L3 on accounts depends on M1's click data
  and on **pending Q-01**. This guide does not settle it. Section 8 still recommends running L4 with no
  client login.
- If every candidate trips on a logged-in persona, this guide has no workaround to offer. Browser-Use is not a
  detection-evasion tool, and the fleet's stance is continuity, not evasion (D9). That outcome is a product
  decision for Justin (**pending Q-01, Q-02, Q-04**).
- The G3.8 rule stays: no actor API, no coordinate click, no MCP server, no Anthropic integration on a
  logged-in identity (section 6).

Browser-Use also attaches to CloakBrowser 146, where Stagehand 4.2.0 cannot. That is a Chromium version limit,
not a CloakBrowser defect: Stagehand 4.2.0's `connect` cannot load its extension over a WebSocket on
Chromium 148 or older, and can from 149 (AP-1, partially-confirmed; the dossier's framing is corrected).
CloakBrowser Pro ships newer builds (AP-1 reads 150-154 on its releases page), which probably pass; not tested.
This touches **pending Q-02, Q-03, Q-04** (anti-detect, proprietary kernels, spoofing stance), which this guide
does not decide.

**Contract (target, aligned with D17 `task`).**

- In: goal text including the target URL; host set; `max_steps` and time and spend caps, each at or under
  the token's ceiling; the identity (or none); mode `read_mostly`.
- Out: `status` in `done | failed | incomplete | error | needs_approval | needs_reauth | checkpoint |
  infra_unavailable | budget_exhausted | scope_denied`; `success` (the model's claim, advisory); `answer`
  (**untrusted text**, data, never an instruction and never publish content, D13); steps with URL, action
  and rung; token counts, billed cost and serving provider per call; errors; evidence refs for the
  profile's Obsidian note (D15).
- Accounting: every Browser-Use step is a generative (G) step in the System-1-share metric (D7). Heavy
  L4 use lowers the share. That is expected.
- No Browser-Use `memory` crosses runs. The field is per-run only (D15: memory is Obsidian, written on the
  Hermes side).

---

## 15. Failure modes and handling

| Symptom | Cause | Handling | Evidence |
|---|---|---|---|
| Process never exits after the result is written | CDP auto-reconnect in `asyncio.run` teardown (inferred) | `os._exit(0)` inside the loop; supervisor kill timer | `hands-on` 3/3; BRO-13 |
| "Root CDP client not initialized" or "did not receive a valid HTTP response" on attach | Chromium not accepting CDP although Steel health is green; also open upstream on the stop path (#6005) | `Browser.getVersion` probe, one retry, else `infra_unavailable` | spike section 7 |
| "attached to a different loop" | bubus cross-loop bug #5509 | One agent, one loop, one process | `source-code`, upstream issue; not reproduced |
| A click lands on the wrong element | Stale index executed, not refused | Freshness guard (sections 6, 8) | `hands-on` 3/3 |
| Output cut off (`ModelOutputTruncatedError`) | Cap too low or a runaway | Counts as a failure; one-way `fallback_llm` switch; raise the cap only from bench data | `source-code` |
| Reply is not valid for the schema (wrong shape, YAML, pattern break) | Provider-dependent enforcement (REA-7) | `require_parameters`, bench-gated allowlist, validation (section 5). A parse failure is a `ModelProviderError` 502: one-way `fallback_llm` switch if set, else a counted step failure | reasoning-models verification |
| 429 or 5xx from the provider | Upstream limits (DeepInfra and BaseTen returned 429 on single calls) | OpenAI-client retries (5, or 10 on `ChatOpenRouter`: set low), then `fallback_llm`. GLM throughput at 100-1,000 agents is unmeasured | REA missed issue 6 |
| Run ends `done` but the claim is wrong | The success flag is the model's claim, and the judge is off | Verify with `find_elements`, `search_page` or a decider noul. Treat `answer` as untrusted | design |
| Loops or stalls | `loop_detection_window=20`; replan nudge after 3 stalls (planning is off in flash mode) | `max_steps`, `max_failures=3`; status `incomplete`; no blind retry on a stronger model | `source-code` |
| First character doubled or dropped in a React editor | Fast synthetic key events (1-10 ms) | The gate keeps L4 out of composers. The effect path reads back posted text (D13) | upstream #4461, #3889 (closed, not verified fixed), #5721 (open) |
| Shadow DOM, cross-origin iframes, virtualised feeds | `cross_origin_iframes`/`max_iframes` needed; #5817, #3382, #4089 | M1 coverage test; scroll-and-re-snapshot; fall back to L3 or a human | `third-party`; **to measure** |
| Page text steers the model (prompt injection) | Untrusted post, comment and bio text | Gate, exclusions, no secrets in scope, `answer` is data (D13). A decider is not a safety control | system1-models V-07 |
| Login wall, checkpoint, 2FA, CAPTCHA | | Stop; `needs_reauth` or `checkpoint`; human through the viewer (D14) | D14 |
| Injected overlay visible to page scripts | `highlight_elements=True` default | Off; the smoke test checks for `data-browser-use-*` nodes after clicks | verification missed issue 1 |
| Cookies lost on release | 30 s Chromium commit timer | D4 safe-release order; context export | BRO-6 |
| localStorage reverted or partial | `storage_state` | Never set it | BRO-5 |
| Temp dirs pile up | One `browser-use-user-data-dir-*` per session | Delete at exit; sweep at worker start | missed issue 7 |
| Cost jumps | Same GLM tokens cost $0.00066 or $0.0013 per step by routed provider; vision plus judge defaults cost about 1.65x | Fixed config, allowlist, per-task spend cap in `register_should_stop_callback` from OpenRouter `usage.cost` | BRO-2; missed issue 4 |
| Lease lost or a human takes over mid-run | | Stop callback; node agent cuts the CDP socket; an in-flight effect-class action is `outcome_uncertain` (D13) | design |
| A call to Browser Use Cloud | `llm=None`, `use_cloud`, skills, telemetry | No `BROWSER_USE_API_KEY` in the worker env; egress allowlist for the worker; self-check | section 17 |
| Regression after an upgrade | 138 commits in about 4.7 weeks | The gate in section 21. A closed upstream issue is not a fix: a stale bot marks issues stale after 60 days and closes them 14 days later (31 closed issues carry the label on 2026-10-10) | verification unsourced item 6 |

---

## 16. Cost per task (measured)

All Browser-Use numbers: GLM 5.3 Flash @low through OpenRouter, `ChatOpenAI` (route A), self-hosted Steel
in Docker on arm64, public static pages, `max_steps=8` (`hands-on`, spike results; billed cost from
OpenRouter `/generation`). Easy tasks: they prove wiring and cost per step, not accuracy.

| Run | Mode | LLM calls | Wall | Prompt tokens | Billed | Correct |
|---|---|---:|---|---:|---:|---|
| Task 1 "first Poetry price", 3 runs | baseline (box options) | 2 | 8.0-14.6 s | 16.2-16.8k | $0.00134-0.00265 | 3/3 |
| Task 1, 2 runs | `flash_mode` | 2 | 5.5-7.7 s | 7.0k | $0.00084-0.00112 | 2/2 |
| Task 1, 1 run | Browser-Use defaults (vision + judge) | 3 | 12.5 s | 28.3k | $0.0036 | 1/1 |
| Task 2 "UPC and stock", 2 runs | baseline | 3 | 14.9-20.7 s | 23.4-26.0k | $0.0024-0.0033 | 2/2 |
| Task 2, 1 run | `flash_mode` | 3 | 11.1 s | 8.2k | $0.0013 | 1/1 |
| System 1 path, 2 runs | decider + `Tools.act` | 0 chat | 6.5-8.8 s | 2,732 decider tokens | $0.000115 (71 options) | 2/2 |

What to take from it:

- **Per step:** baseline 8.1-8.4k prompt tokens; flash 3.5k; defaults 10.8k. Step 1 is a no-LLM navigate.
- **Defaults cost about 1.65x the baseline mean in dollars and 1.71x in tokens**, not the dossier's 2.7x.
  The 2.7x divided by the single cheapest baseline run, which was routed to InferenceNet (verification
  BRO-2).
- **Every dollar figure is confounded by provider routing.** The same tokens cost $0.00066 per step on
  InferenceNet and $0.0013 on Together. For a budget, project at **list price** ($0.15 per million input,
  $0.50 per million output): in the GLM bench 150 of 150 calls were served by $0.15 endpoints, not the
  cheaper ones (reasoning-models verification REA-14). Pin the provider or budget on tokens.
- **At list price (arithmetic, estimate):** a baseline step is about 8.3k x $0.15/M + about 150 completion
  tokens x $0.50/M, roughly $0.0013. A flash step is about 3.5k tokens, roughly $0.0006.
- **Decider step:** about $0.0002-0.00026 for a realistic 180-candidate Jev step; $0.000363 at 255 options.
- **Live multi-step runs** (reasoning-models spike, quotes pagination and dynamic loading): GLM @low 6/6,
  median 4 steps, 5.7 s of LLM time, **$0.0024 per task**; DeepSeek V4.1 Flash off 6/6, 8.8 s,
  $0.0035. These ran on **local Chrome on the Mac**, a method BRIEF.md now bans (reasoning-models
  verification missed issue 9). The data is usable, but it is not Steel data, and it is two trivial tasks.
- **Dense pages (estimate, to measure).** The serialized DOM is capped at 40,000 characters. At roughly 4
  characters per token that is up to about 10k tokens, so a flash step on a dense social page could be
  3-4x the measured 3.5k, about $0.002 at list. A 20-step run could then reach about $0.04. The Gemini
  conversation's "$0.01-$0.08 per task" is 10-20x above the easy-page measurements and within reach of
  this dense-page estimate. No dense page was measured.
- **Browser side:** no Browser-Use charge. Browser Use Cloud's $0.02 per browser-hour is not used
  (section 17). Worker CPU and memory per process: **to measure.**
- **Not measured:** social SPAs, long feeds, long runs, GLM throughput for 100-1,000 agents (429s seen),
  the effect of a provider allowlist or ZDR on price (**pending Q-07, O-06**).

---

## 17. Cloud-only features not to depend on

Browser Use is three products: the OSS library, Cloud agents, and Cloud browser infrastructure
([corpus INDEX section 0](../../research/corpus/browser-use/INDEX.md)). The fleet uses only the library.

| Cloud feature | Why the fleet does not use it | Source |
|---|---|---|
| Stealth Chromium fork, fingerprints "randomized per session" | The opposite of the fleet's same-identity requirement (D3). OSS has no stealth: only `--disable-blink-features=AutomationControlled` and dropping `--enable-automation` on **local** launch | `official-docs` `https://docs.browser-use.com/cloud/browser/stealth.md`; `source-code` `profile.py:201,439`; BRO-10 |
| CAPTCHA solving | OSS only waits for Cloud's `BrowserUse.captchaSolverFinished` event. Agents never solve CAPTCHAs on client accounts (D14) | `captcha_watchdog.py:152-153` |
| Managed residential proxies | The fleet uses one dedicated static ISP IP per identity (D10) | `official-docs` `https://docs.browser-use.com/cloud/browser/proxies.md` |
| Managed profiles and profile sync | The fleet keeps profiles in its own bundle. Cloud would hold client cookies | `official-docs` `https://docs.browser-use.com/cloud/guides/authentication.md`, `https://docs.browser-use.com/cloud/guides/profile-sync.md` |
| Hosted V4 agent on your browser | Not possible: `ExternalBrowserAttach` is "DEV-ONLY ... gated to env=='development'" | `https://docs.browser-use.com/openapi/v4.json` |
| `ChatBrowserUse`, `use_cloud=True`, `cloud_profile_id`, `captcha_solver=True` | Hosted model and browser; `captcha_solver` only waits. `llm=None` silently picks `ChatBrowserUse` | `source-code` |
| Skills (`Agent(skills=[...])`) | Retired for new skills (create and refine return 410), but **existing skills still run**. The agent fills a skill's declared cookie parameters from the live browser's cookies, matched by name across domains, and sends them to Browser Use's API | `official-docs` `https://docs.browser-use.com/cloud/legacy/skills.md`; `source-code` `agent/service.py:872-877`, `skills/service.py:194-221`; BRO-9 |
| Rerunnable scripts, workspaces | Cloud-only and still LLM-driven per run | `official-docs` `https://docs.browser-use.com/cloud/agent/scripts.md` |
| Live view, recording | The fleet's own viewer is brokered by fleetd (D14) | `official-docs` |
| Pricing and benchmark numbers | `vendor-claim`, "last verified September 3, 2026". GLM 5.3 Flash's 28.0/100 at $0.114 per task is a quality score on the vendor's own benchmark, not a success rate. The V4 price range tops out at GPT-6 Astra $12/$60 per million, not Claude Opus 5 at $6/$30 (BRO-14) | `vendor-claim` |
| Beta agent (`browser_use.beta`), Browser Harness, Browser Use Terminal | Not investigated; licence of `browser-use-core` unverified. Harness is a hard dependency but unused | `source-code` |

Keeping the Cloud pieces dormant is a worker rule: no `BROWSER_USE_API_KEY`; telemetry and cloud sync off;
an egress allowlist for the worker (the model provider, the System 1 providers, fleetd, nothing at
browser-use.com); the self-check (section 2).

---

## 18. Gates not yet measured

Milestone dependencies, not dates. M1 is the droplet hands-on (**pending Q-12**); M3 is the provider
bench.

| Gate | Needs | Closes |
|---|---|---|
| `Tools.act` index click against a real Steel session on an amd64 droplet, then against a real site class | M1, Q-12 | D5 gate, O-17 |
| Candidate coverage across iframes and shadow DOM on Steel | M1 | D5 gate |
| Decider element-choice accuracy on dense social and lead-gen pages | M1/M3 data, O-15 | The 90% hypothesis |
| Element click, typing and scroll through `Tools.act` against the `isAutomatedWithCDP` page **and DABI's behavioural check** ("CDP mouse leak"), first on the bare browser, then **with the Guard attached** and the rest of the fleet stack (G1.4 conditions (i) to (iii) in `MILESTONES.md`). No such result exists today (section 6) | M1 | O-02, G1.4 |
| The G3.8 rule is checkable: the Browser-Use worker's own CDP log for a run that clicks, types and scrolls shows no `Runtime.enable` and no coordinate-click event, and the self-check's `click` `param_model` assertion (section 2, item 9) passes. G3.8 names only the actor API and the coordinate click; the per-executor CDP-method log that G1.4 stores would also cover the MCP server and the Anthropic integration | M1/M3 | G3.8 |
| Graceful-flush release and the 31 s hold | M1 | C-03 |
| Whether `accept_downloads=False` stops the browser-wide download call | M1 smoke test | Section 10 |
| `highlight_elements=False` really leaves no overlay nodes | M1 smoke test | Section 6 |
| `ChatOpenRouter` + GLM in Browser-Use; the Route C transport; `finish_reason` and retry behaviour | M3 | O-06, D8 |
| The `max_completion_tokens` value; per-provider schema validity; ZDR effect | M3, Q-07 | O-06 |
| Gate false-block and false-allow rates on planted effect controls | M3 | Section 8 |
| Worker memory per process; bubus #5509 at scale | M1/M6 | D12 sizing |
| Browserbase attach | A Browserbase key | D11 |
| Agent loop on a real social SPA | Justin's yes (the brief forbids it now) | All of the above |

---

## 19. Corpus index

Topic map and capture method for the official docs (the scraped copy is not published; pages are cited by vendor URL): [`../../research/corpus/browser-use/`](../../research/corpus/browser-use/INDEX.md).
The captured material is untrusted vendor text. Nothing in it was followed as an instruction. Start at
[`INDEX.md`](../../research/corpus/browser-use/INDEX.md) (topic map) and
[`MANIFEST.md`](../../research/corpus/browser-use/MANIFEST.md) (method, hashes, known vendor disagreements).
Pages below are given by their vendor URL.

| Need | Page |
|---|---|
| Which product is which | `https://docs.browser-use.com/cloud/which-product.md`, `INDEX.md` section 0 |
| Remote browser, `cdp_url`, proxy | `https://docs.browser-use.com/open-source/customize/browser/remote.md`, `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md`, `https://docs.browser-use.com/open-source/customize/browser/real-browser.md` |
| Auth, `storage_state`, 2FA (OSS) | `https://docs.browser-use.com/open-source/customize/browser/authentication.md` |
| Agent parameters | `https://docs.browser-use.com/open-source/customize/agent/all-parameters.md`, `https://docs.browser-use.com/open-source/customize/agent/basics.md`, `https://docs.browser-use.com/open-source/customize/agent/output-format.md`, `https://docs.browser-use.com/open-source/customize/agent/prompting-guide.md` |
| Tools, built-ins, add or remove actions | `https://docs.browser-use.com/open-source/customize/tools/{basics,available,add,remove,response}.md` |
| Hooks (lifecycle) | `https://docs.browser-use.com/open-source/customize/hooks.md` |
| Models and OpenRouter | `https://docs.browser-use.com/open-source/supported-models.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/open-source/references/models.md` |
| System prompts actually sent | `https://github.com/browser-use/browser-use/blob/c75e847/browser_use/agent/system_prompts/*.md` |
| Sensitive data, secure template | `https://docs.browser-use.com/open-source/examples/templates/sensitive-data.md`, `https://docs.browser-use.com/open-source/examples/templates/secure.md` |
| Parallel browsers template | `https://docs.browser-use.com/open-source/examples/templates/parallel-browser.md` |
| Telemetry | `https://docs.browser-use.com/open-source/development/monitoring/telemetry.md` |
| Replay (undocumented; read source) | `INDEX.md` section 10; clone at `c75e8476`: `browser_use/agent/service.py` |
| Cloud features (to know, not use) | `https://docs.browser-use.com/cloud/browser/{stealth,captcha-handling,proxies}.md`, `https://docs.browser-use.com/cloud/guides/{authentication,profile-sync,concurrency}.md`, `https://docs.browser-use.com/cloud/legacy/skills.md`, `https://docs.browser-use.com/cloud/agent/scripts.md` |
| Hermes integration (Cloud provider route; not used) | `https://docs.browser-use.com/cloud/tutorials/integrations/hermes-agent.md` |
| Pricing (`vendor-claim`) | `https://browser-use.com/pricing.md`, `https://browser-use.com/benchmarks/pricing-models.json` |
| API specs | `https://docs.browser-use.com/openapi/v4.json` (`ExternalBrowserAttach` dev-only note) |
| Repo docs at the pinned commit | `https://github.com/browser-use/browser-use/blob/c75e847/README.md`, `https://github.com/browser-use/browser-use/blob/c75e847/AGENTS.md`, `https://github.com/browser-use/browser-use/blob/c75e847/CLAUDE.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/remote-browser/SKILL.md` |
| Whole-site search | `https://docs.browser-use.com/llms-full.txt`, `https://docs.browser-use.com/llms.txt` |

Source code is not in the corpus. Read it in the clone at `c75e8476`
(`<scratch>/sources/browser-use`), which equals the shared venv's 0.13.11.

---

## 20. Sources and corrections applied

**Read for this guide:**
[BRIEF](../../research/BRIEF.md), [DECISIONS](../../DECISIONS.md),
[CONSISTENCY](../../research/verification/CONSISTENCY.md),
[GEMINI-AUDIT](../../research/verification/GEMINI-AUDIT.md) (rows 2.10, 3.02-3.06, 10.07, 11.04 touch this
engine), [browser-use dossier](../../research/dossiers/browser-use.md) and
[verification](../../research/verification/browser-use.md),
[reasoning-models dossier](../../research/dossiers/reasoning-models.md) and
[verification](../../research/verification/reasoning-models.md),
[system1-models dossier](../../research/dossiers/system1-models.md) and
[verification](../../research/verification/system1-models.md),
[antidetect-proxies verification](../../research/verification/antidetect-proxies.md) (AP-1, AP-2, AP-3 and
missed issues 9 and 10 only), the
[antidetect spike results](../../research/spikes/antidetect-proxies/RESULTS.md) (sections 1 and 2c),
[spike results](../../research/spikes/browser-use/RESULTS.md), the box `agents/browseruse/runner.py`,
`docs/security.md` and `gateway/gateway/guard.py`, scenario
[S14](../../research/scenarios/S14.md) (the stress test that prompted the section 14 rewrite), and, in the
pinned clone, the files cited inline (read-only).

**Dossier claims this guide corrects** (the verification report or DECISIONS.md wins):

| Dossier says | This guide says | Source |
|---|---|---|
| Defaults cost 2.7x per task | About 1.65x cost, 1.71x tokens | BRO-2 |
| Jev's cap is about 180 options | Hard cap 255 (256 -> HTTP 400); 180 is a client constant; OpenAI's cap is unstated | BRO-4, S1-08 |
| $0.000115 per decision | At 71 options; $0.000363 at 255 | BRO-4, missed issue 9 |
| A 1,000-token decider step | 4.9-6.2k tokens for 180 candidates | system1-models V-04 |
| Action schema about 14 KB, a token driver | 13.4-17.3 KB static; GLM providers do not appear to bill it as prompt tokens | verification unsourced item 4 |
| Cookies written under 30 s before release are lost | Only 2 s (lost) and 40 s (kept) measured, n=1 each; Chromium's 30 s commit timer supports it; the hold is a floor | BRO-6 |
| Q4 attach sample (per-profile `userDataDir`, credentialed `proxyUrl`) | Steel ignores the first; the second breaks D10. Fresh code in section 4 | C-04, missed issue 3 |
| `ProxySettings.server` is ignored on remote CDP | `source-code` finding only; the author's own probe points the other way; never pass `ProxySettings` | BRO-11 |
| `keep_alive` caused the hang | Cause inferred: an un-stopped session's CDP auto-reconnect; no control run | BRO-13 |
| `rerun_history` is a no-LLM replay and self-heal tier | Always ends with a summary LLM call unless stubbed; replays old `done` text | C-07, V-12 |
| Skills are retired | New skills are; existing skills still run and send cookies named by their parameters | BRO-9 |
| Compaction every 25 steps or about 10k tokens | Both at least 25 steps and at least 40,000 characters | verification unsourced item 7 |
| 168 open issues, at least 23 closed by a 14-day stale bot | 169 open; 31 closed issues carry the label; the bot stales at 60 days, closes 14 days later | verification unsourced item 6 |
| Remote sessions get a temp `user_data_dir` (`pure_checks.json`) | Evidence is in `persist1.err`/`conc1.err`; effect is an empty dir per session | missed issue 7 |
| `highlight_elements=True` listed as a plain default | Turn it off: it injects a page-visible node on every click and type | missed issue 1 |
| Default agent click uses `force=True`, so it avoids detection (AP-3 wording) | `force=True` is the coordinate-click path. The index-click path was not tested against the detection page | `tools/service.py:679,704-731` |
| Stagehand cannot attach to CloakBrowser 146 (dossier CloakBrowser row) | A Chromium version limit (148 or older), not a CloakBrowser defect | AP-1 |
| GLM "~3% runaway", "max effort ~40 s/step" | The runaway rate is for Stagehand's act schema (7-8% of click acts on a 6k-token page). No `finish_reason=length` was seen in Browser-Use runs. "~40 s" was not re-measured | REA-3, REA-5 |
| Cloud V4 prices top out at Claude Opus 5 | GPT-6 Astra $12/$60 per million. GLM's 28.0 is a quality score. Cloud only; not used | BRO-14 |
| "Works as the open-ended backup" | Shown for scripted 2-3-click flows on one static site. Open-ended accuracy is unmeasured | BRO-1 |

**Wording in DECISIONS.md and CONSISTENCY.md that this guide reads more narrowly.** No design change; this
guide does not edit DECISIONS.md, and the point is also reported to the owner. D6 says Browser-Use's "actor
API and coordinate click do" trip the check, and C-13 says its attach was clean "because default Agent clicks
use `force=True`". Both are source readings that were never run against a detector. By source, the actor API,
the MCP server's coordinate click and the Anthropic integration reach `Runtime.enable`
(`actor/page.py:69`, `default_action_watchdog.py:390-407`, `mcp/server.py:793`,
`integrations/anthropic/browser_use.py:251`).
The Agent's own coordinate click (`force=True`) does not, and it is not registered for the fleet's models
(`agent/service.py:326-333`). The clean attach result does not depend on clicks at all, because none were
made. The G3.8 ban stays, for the reasons in section 6.

---

## 21. Governance

### The version pin and its upgrade gate

**Pin:** `browser-use==0.13.11` with `cdp-use==1.4.5`, `bubus==1.5.6`, `openai==2.26.0`, in the worker
image's lock. The pin is a decision of record, not a drift.

**Upgrade gate (the smoke test is a spec; it is unbuilt).** A new pin may replace the old one only when
every step passes, on a throwaway Steel container, public test pages only, no client identity. It runs on
a droplet or cloud sandbox, **never on the maintainer's workstation** (BRIEF: no Docker container lifecycle there). **pending Q-12.**

1. **Read the upstream compare** for the files this guide depends on: `browser/session.py`,
   `session_manager.py`, the downloads, permissions, about:blank, storage-state and security watchdogs,
   `browser/profile.py` defaults, `agent/service.py` (callbacks, fallback, rerun, `sensitive_data`),
   `tools/service.py` (`act`, click paths), `tools/registry`, `llm/openai/chat.py`, `llm/openrouter/chat.py`,
   `llm/exceptions.py`. Note any changed default (for example a new default that talks to the network).
2. **The offline self-check passes** (section 2).
3. **Attach and agent run:** attach by `cdp_url` after the readiness probe; a scripted task with the
   pinned LLM config returns the right answer inside the step and token caps; `reasoning_effort: "low"`
   is on the wire; no `finish_reason=length`; the cost is within the band of section 16, at list price.
4. **System 1 path:** `selector_map` -> candidate -> `Tools.act` click works; the **stale-index negative
   control** (click an index from the previous page) is refused by the freshness guard, not executed.
5. **Gate:** a planted effect-like click (a test form with a "Post" button, an icon-only submit, a GET
   "follow" link) is stopped with `needs_approval`; a navigational click passes; typing into a search box
   passes; typing into a composer is stopped.
6. **Replay:** with a stub `summary_llm`, zero LLM calls; the old `done` text is flagged as stale.
7. **Hygiene:** no overlay node in the DOM after clicks; no `storage_state` writes; no files outside the
   scratch dir; temp dirs removed; no download-behaviour change; no connection to browser-use.com or any
   host outside the egress allowlist; telemetry off.
8. **Exit:** the process exits inside the kill timer on 10 of 10 runs (the hang regression).
9. **Detectability:** on a wake whose effective `extension_mode` is `none`, the public `isAutomatedWithCDP` check
   stays clean after attach, navigate and a `Tools.act` index click, type and scroll, and DABI's behavioural
   check ("CDP mouse leak") is run and recorded. Run it on the bare browser and again **with the Guard
   attached** (the Guard's `Target.setAutoAttach{waitForDebuggerOnStart:true}` is absent from the earlier
   data). The index click, typing and the behavioural check have no result today (section 6), so this step
   records a first baseline on the first pin, then guards against change. The worker's CDP log shows no
   `Runtime.enable` (section 18).
10. **Canary:** the new pin first runs on a non-client identity, then on client identities only after
    owner-accepted outcomes (the same canary rule D13 applies to a new Steel or Stagehand pin).

Rollback is the previous lock and image tag, kept until every worker process has recycled. One process per
task makes that quick. Only Justin merges a pin change.

### What agents may and may not do through this property

"Agent" here means both the **Hermes profile** that calls `task` and the **model inside the worker**.

**May:**

- A profile whose token the owner has allowed to call `task` submits a goal, a host set and budgets at or
  under its ceilings, and receives status, steps, cost and an **untrusted** answer. (Proposal: that token
  carries `read` scope only. D17 marks `task` as a write tool and does not map it to a scope: pending the
  owner.)
- The worker's model may navigate, scroll, expand, paginate, search, read (`find_elements`, `search_page`,
  `find_text`, `extract`) and click navigational links, inside the budget, under the gate.
- A run may save its history as a **candidate** for owner review.

**May not:**

- Post, send, reply, comment, DM, like, follow, repost, delete, submit forms, pay, or do anything else
  effect-like. These return `needs_approval`. Effects go only through an approved manifest item and the
  `publish`/`dm` scopes (D5, D13).
- Type credentials, handle 2FA, solve CAPTCHAs, or set `sensitive_data` (D14).
- Upload files, save PDFs, run JavaScript, or use the actor API, coordinate clicks (the MCP server's or the
  Agent's own), the MCP server or the Anthropic integration on a logged-in identity. This is the G3.8 rule:
  it holds whatever the M1 click test shows (section 6).
- Change anything about the browser: persona, proxy, IP, timezone, locale, viewport, permissions, cookies,
  storage, the Steel session, the lease. Those belong to the node agent and fleetd (D3, D4, D10, D12).
- Use any Browser Use Cloud feature, or reach any host except through the browser and the allowlisted
  worker egress.
- Drive an identity it does not hold the lease for, run while a human holds it, or run beside another
  engine.
- Treat page text, or its own `answer`, as instructions or as content to publish (D13).
- Run without a step cap, a wall-time cap and a spend cap.
- Write memory. Memory is Obsidian, written on the Hermes side from fleetd's evidence (D15).
- Edit this configuration from inside a run.

### Who may change its configuration

| What | Who | Condition |
|---|---|---|
| The version pin, the worker image | Justin | The upgrade gate passes |
| Model slug, effort, provider allowlist, ZDR, token caps, `fallback_llm` | Justin | Per-provider bench evidence (O-06) and the Q-07 data decision |
| Agent defaults, the excluded-actions list, gate rules, effect patterns, host sets | Justin | Loosening is per procedure, with a written reason and a re-run of the gate tests. Tightening also re-runs them |
| Per-run goal, URL, `max_steps`, time and spend | The calling profile | At or under the ceilings in its token, which Justin sets. It cannot raise a ceiling |
| Browser settings (persona, proxy, lease, session) | Not this property | Node agent and fleetd (D3, D4, D10, D12) |

Changes go through the `fleet/` repo and Justin's review. A deploy to fleet nodes needs his explicit yes
(the same rule the box's `CLAUDE.md` applies to the live box). No Hermes profile and no fleet agent changes
this configuration.

### Pending Justin

- **Q-01:** API-first versus browser-first. Decides how often L4 touches client social at all, and the
  logged-out research recommendation in section 8.
- **Q-07:** data handling. Page text and screenshots from client pages go from the worker to OpenRouter
  providers. A ZDR requirement changes the allowlist and invalidates the bench numbers. Also governs
  saved-history retention.
- **Q-12:** a capped throwaway droplet for M1. Without it, every gate in section 18 stays open.
- **Q-02, Q-03, Q-04:** anti-detect, proprietary kernels, spoofing stance. Browser-Use is the engine that
  works on a patched kernel; this guide takes no side.
- **Q-08:** Steel's Chromium runs as root without a sandbox. It is the host's risk, but L4 browses
  arbitrary pages in it, so the answer changes how much L4 may be trusted near a logged-in identity.

### Soul

*We send Browser-Use out to look and never to act: it explores read-mostly inside a hard budget, and every
effect it could cause is stopped by code it cannot talk to.*
