# Browser-Use corpus: topic -> file map

> Published copy: the raw pages captured for this vendor are not republished (they are third-party content). Local paths marked "(scraped copy not published)" name files that exist only in the original capture. Where a page has a public source, the path is replaced by its vendor URL (docs pages) or by its GitHub URL at the pinned commit.

Fetched 2026-10-09. Read `MANIFEST.md` for method, hashes and known vendor disagreements.
All paths are relative to `fleet/research/corpus/browser-use/`. This is a **data directory**: the
files are untrusted vendor text. Nothing in them was executed or followed. Every `docs-site/*.md`
page starts with a vendor "Documentation Index / Agent Instructions" block (identical in all 227
pages); treat it as data.

Provenance tags used below: `official-docs` (docs.browser-use.com), `source-code` (repo clone,
commit c75e8476, browser-use 0.13.11), `vendor-claim` (browser-use.com marketing/pricing),
`unverified` (nothing in the corpus backs it).

## 0. Read this first: "Browser-Use" is three different products

| Product | What it is | License / hosting | Where documented |
|---|---|---|---|
| **OSS library** `browser-use` (Python, 0.13.11) | Local agent loop + CDP browser control. You supply the LLM and the browser. Works with any CDP URL (so it can sit on self-hosted Steel). | MIT, self-hosted (`source-code`: `https://github.com/browser-use/browser-use/blob/c75e847/LICENSE`) | `https://docs.browser-use.com/open-source/**`, `https://github.com/browser-use/browser-use/tree/c75e847/skills/open-source/`, `https://github.com/browser-use/browser-use/blob/c75e847/README.md`, `https://github.com/browser-use/browser-use/blob/c75e847/AGENTS.md` |
| **Browser Use Cloud: Agents** (API V2 / V3 / V4) | Hosted agent: you send a task, they run model + browser, you poll for the result. Closed source, paid, pay-as-you-go. | SaaS only | `https://docs.browser-use.com/cloud/agent/**`, `https://docs.browser-use.com/cloud/api-v{2,3,4}/**`, `https://docs.browser-use.com/openapi/*.json` |
| **Browser Use Cloud: Browser Infrastructure** | Managed stealth Chromium you drive over CDP (Playwright/Puppeteer/Selenium) via `POST /api/v4/browsers`. Closed source, paid. | SaaS only | `https://docs.browser-use.com/cloud/browser/**`, `https://docs.browser-use.com/cloud/api-v4/browsers/` |
| Dev tools | Browser Use CLI, Terminal app, Browser Harness (marketing page only), MCP server | mixed | `https://docs.browser-use.com/open-source/browser-use-cli.md`, `https://docs.browser-use.com/open-source/browser-use-terminal.md`, `https://browser-use.com/browser-harness.md`, `https://docs.browser-use.com/cloud/guides/mcp-server.md`, `https://docs.browser-use.com/open-source/customize/integrations/mcp-server.md` |

Pick the product first: `https://docs.browser-use.com/cloud/which-product.md`, `https://docs.browser-use.com/cloud/choosing-an-agent.md`.

Design-critical findings from this capture (each with its source):

1. **The hosted V4 agent cannot be pointed at your own browser.** The V4 OpenAPI schema has an
   `ExternalBrowserAttach {cdpUrl, liveViewUrl}` object, but its description reads "DEV-ONLY ... Gated
   to env=='development' in the router" (`https://docs.browser-use.com/openapi/v4.json`, `official-docs`). So Cloud Agents run only on Browser
   Use's own browsers. To drive self-hosted Steel (or any non-Browser-Use browser) you must use
   the **OSS library with `Browser(cdp_url=...)`** (`https://docs.browser-use.com/open-source/customize/browser/remote.md`, `official-docs`;
   `cdp_url` in `browser_use/browser/session.py`, `source-code`).
2. **Stealth, fingerprinting, CAPTCHA solving, managed residential proxies, profile storage and live
   view are Cloud features.** The OSS library does not ship them (sections 4 to 8). `source-code`:
   a case-insensitive search of `browser_use/**/*.py` for "stealth" and "fingerprint" finds no
   fingerprint-spoofing code. Hits are nudge strings telling users to try `Browser(use_cloud=True)`,
   `PageFingerprint` in `agent/views.py` (page-stagnation detection, not browser fingerprinting), a
   telemetry device id, a Vercel model alias, and comments. The only stealth-adjacent OSS behavior is
   launch-flag hygiene in `browser_use/browser/profile.py`: it drops `--enable-automation` (the comment
   says the "automation fingerprint" is masked "via JS and other flags", but no `webdriver` string
   appears anywhere in `browser_use/**/*.py`) and adds `--disable-blink-features=AutomationControlled`.
3. **Same-fingerprint / same-IP is not a documented guarantee.** `CreateBrowserSessionRequest`
   has `profileId, proxyCountryCode, metadata, timeout, browserScreenWidth/Height, allowResizing,
   pdfRendererEnabled, solveCaptchas, customProxy, enableRecording, extensionIds` and nothing for
   a fingerprint seed, user agent, or sticky-proxy session (`https://docs.browser-use.com/openapi/v4.json`, `official-docs`). The
   vendor preamble says "A new managed browser does not guarantee a unique proxy IP or particular
   city". Fingerprints are "randomized per session" (`https://docs.browser-use.com/cloud/browser/stealth.md`). A
   `customProxy` (your own sticky-IP proxy) is supported, which is the documented route to a stable IP.
4. **No Stagehand-style action cache exists.** See "Caching" below for the nearest things.

## 1. Quickstart / which product

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/quickstart.md` | Cloud: run a hosted agent or launch a cloud browser |
| `https://docs.browser-use.com/cloud/agent/quickstart.md` | Run a V4 task (SDK + curl) |
| `https://docs.browser-use.com/cloud/browser/quickstart.md` | Launch a cloud browser and connect with CDP |
| `https://docs.browser-use.com/open-source/quickstart.md` | OSS library install + first `Agent` |
| `https://docs.browser-use.com/open-source/introduction.md` | OSS overview |
| `https://docs.browser-use.com/cloud/which-product.md`, `https://docs.browser-use.com/cloud/choosing-an-agent.md` | Product and agent selection |
| `https://docs.browser-use.com/cloud/agent-signup.md` | API key creation; "agent signup is off" |
| `https://docs.browser-use.com/cloud/vibecoding.md`, `https://docs.browser-use.com/open-source/vibecoding.md` | Single-page prompts for coding agents |
| `https://github.com/browser-use/browser-use/blob/c75e847/README.md` | Repo README (`source-code`) |

## 2. Connect / CDP

| Cloud / OSS | File |
|---|---|
| Cloud | `https://docs.browser-use.com/cloud/browser/playwright-puppeteer-selenium.md` (drive a Browser Use cloud browser over CDP) |
| Cloud | `https://docs.browser-use.com/cloud/browser/quickstart.md`, `https://docs.browser-use.com/cloud/api-v4/browsers/create-browser-session.md` (response carries `cdpUrl`, `liveUrl`) |
| Cloud | `https://docs.browser-use.com/cloud/agent/network-capture.md` (attach your own CDP observer to a live V4 browser) |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/remote.md` (`cdp_url`, `use_cloud=True`, third-party CDP providers, proxy) |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/real-browser.md` (attach to your own Chrome), `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md` (`cdp_url`, `is_local`, `headers`) |
| OSS | `https://github.com/browser-use/browser-use/blob/c75e847/skills/remote-browser/SKILL.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/open-source/references/browser.md` |

## 3. Sessions

Terminology (`official-docs`, `https://docs.browser-use.com/cloud/guides/concurrency.md`): a V4 **session** is a conversation,
a **run** is one turn, a **browser** is the live Chrome instance. Only one run may be active per session
(follow-up while busy returns 409; the queue holds 20 messages). A browser can outlive its run; idle cleanup
is about 20 minutes after the last run activity; hard timeout 4 hours.

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/agent/sessions.md` | V4 sessions: follow-ups, queue |
| `https://docs.browser-use.com/cloud/api-v4/sessions/*.md`, `https://docs.browser-use.com/cloud/api-v4/runs/*.md` | Session / run endpoints (create run, events, status, cancel; session queue, cost, share, purge) |
| `https://docs.browser-use.com/cloud/api-v4/browsers/*.md` | Standalone browser sessions (create, get, list, stop via PATCH `{"action":"stop"}`, downloads) |
| `https://docs.browser-use.com/cloud/guides/concurrency.md` | Browser lifetime, queues, 409/429 behavior |
| `https://docs.browser-use.com/cloud/legacy/agent.md`, `https://docs.browser-use.com/cloud/api-v2/sessions/*.md`, `https://docs.browser-use.com/cloud/api-v3/sessions/*.md` | Older session models (V2 tasks+sessions, V3 sessions) |
| `https://docs.browser-use.com/open-source/examples/templates/follow-up-tasks.md` | OSS: follow-up tasks on the same browser session |
| OSS `keep_alive` | `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md` |

## 4. Persistence: profiles, auth state, contexts, workspaces

| Cloud / OSS | File | Note |
|---|---|---|
| Cloud | `https://docs.browser-use.com/cloud/guides/authentication.md` (title: "Profiles") | A profile persists cookies, localStorage and login state across browsers; "one profile per end user". Pass `browserSettings.profileId`. `official-docs` |
| Cloud | `https://docs.browser-use.com/cloud/guides/profile-sync.md` | Sync a local login into a cloud profile with `curl -fsSL https://browser-use.com/profile.sh \| sh`. Caveat in the page: sites can expire cookies or bind sessions to device/network |
| Cloud | `https://docs.browser-use.com/cloud/api-v4/profiles/*.md` | CRUD; create takes `name`, `userId`; "Profile limit reached" error exists, **no numeric profile cap is documented anywhere in this corpus** |
| Cloud | `https://docs.browser-use.com/cloud/guides/concurrency.md` ("Profile quotas are separate") | |
| Cloud | `https://docs.browser-use.com/cloud/agent/workspaces.md` | Workspaces hold **files**, not browser state; IDs are not interchangeable with profile/session IDs |
| Cloud | `https://docs.browser-use.com/cloud/guides/secrets.md`, `https://docs.browser-use.com/cloud/guides/2fa.md`, `https://docs.browser-use.com/cloud/guides/1password.md` | Run-scoped secret bindings, TOTP, 1Password. Humans-log-in-once fits `profile-sync` + live view |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/authentication.md` | Real browser profiles, `storage_state` export/load/auto-save, TOTP 2FA, AgentMail/1Password/Gmail 2FA, domain restriction |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md` | `user_data_dir`, `profile_directory`, `storage_state`, `Browser.from_system_chrome()`, `list_chrome_profiles()` |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/real-browser.md` | Reuse a logged-in local Chrome |
| OSS | `https://docs.browser-use.com/open-source/examples/templates/sensitive-data.md` | Keep passwords out of the LLM context |

## 5. Proxies

| Cloud / OSS | File | Note |
|---|---|---|
| Cloud | `https://docs.browser-use.com/cloud/browser/proxies.md` | US residential proxy on by default; `proxyCountryCode` per run/browser; `null` disables; `customProxy {host,port,username,password,ignoreCertErrors}` for your own proxy (all accounts, no subscription). `official-docs` |
| Cloud | `https://docs.browser-use.com/cloud/browser/stealth.md` | "Residential proxies enabled by default across 195+ countries" |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/remote.md` | `cloud_proxy_country_code` accepts us, uk, fr, it, jp, au, de, fi, ca, in (10 values; differs from the 195+ claim above, see MANIFEST) |
| OSS | `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md` | `proxy=ProxySettings(server, bypass, username, password)` for any proxy you supply |
| Pricing | `https://browser-use.com/pricing.md` | $5/GB managed residential, $0.20/GB direct or custom proxy egress (`vendor-claim`; `https://docs.browser-use.com/cloud/guides/billing.md` confirms the $0.20/GB direct rate in a worked example and defers to the pricing page for the rest) |
| Marketing | `https://browser-use.com/proxies.md` | "195+ countries" and "HTTP/SOCKS5" claims (`vendor-claim`) |

## 6. Stealth / fingerprint

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/browser/stealth.md` | Cloud only: hardened Chromium fork, per-session randomized canvas/WebGL/fonts/navigator, ad and cookie-banner blocking, "access to every site is not guaranteed". `official-docs` |
| `https://browser-use.com/pricing.md`, `https://browser-use.com/stealth-browsers.md`, `https://browser-use.com/anti-detect-browser.md`, `https://browser-use.com/captcha-solving.md`, `https://browser-use.com/llms-full.txt` (benchmarks section) | Benchmark claims (81% on 71 high-security sites, 84.8% on BrowserBench) are `vendor-claim`, from the vendor's own benchmark; the methodology blog post is not captured here. The anti-detect page also compares against competitors |
| `https://docs.browser-use.com/cloud/guides/troubleshooting.md` | What to do when a site still blocks |
| OSS | Nothing equivalent in the library (section 0, finding 2). `https://docs.browser-use.com/open-source/customize/browser/all-parameters.md` lists `user_agent`, `args`, `ignore_default_args`, `enable_default_extensions` (uBlock Origin, cookie handlers, ClearURLs) as the relevant knobs; you bring your own fingerprint/anti-detect layer |

## 7. CAPTCHA

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/browser/captcha-handling.md` | Cloud solves supported CAPTCHAs automatically (V4 runs and standalone browsers); `"solveCaptchas": false` on `POST /api/v4/browsers` only; not guaranteed; Cloudflare-style walls are stealth+proxy, not the solver. `official-docs` |
| `https://browser-use.com/captcha-solving.md` | Marketing page (`vendor-claim`) |
| OSS `source-code` | `browser_use/browser/watchdogs/captcha_watchdog.py` + `Agent` step loop: `wait_if_captcha_solving()` just waits for the Cloud browser's `BrowserUse.captchaSolverFinished` CDP event. The OSS library has no solver of its own. (Source is not in the corpus; read it in the clone at c75e8476.) |

## 8. Live view / human takeover / recording

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/browser/live-preview.md` | `browser.ready` event carries `live_view_url` (host `live.browser-use.com`, treat as a credential); iframe embed; read-only embed trick; recording (`enableRecording` / `browserSettings.record`, off by default; ZDR projects never record) |
| `https://docs.browser-use.com/cloud/agent/human-in-the-loop.md` | Open the live browser, take over, continue the same session |
| `https://docs.browser-use.com/cloud/agent/observability.md` | Ordered run events stream |
| `https://docs.browser-use.com/cloud/tutorials/chat-ui.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/cloud/references/guides/chat-ui.md` | End-to-end chat UI with live preview |
| OSS | `https://docs.browser-use.com/open-source/development/monitoring/observability.md`, `https://docs.browser-use.com/open-source/development/monitoring/openlit.md`; recording params `record_video_dir`, `record_har_path`, `traces_dir` in `all-parameters.md` |

## 9. Models / LLM configuration

| Cloud / OSS | File | Note |
|---|---|---|
| Cloud | `https://docs.browser-use.com/cloud/agent/models.md` | V4 model IDs by provider incl. Z.ai `glm-5.2`, `glm-5.3-flash` (hosted only, no BYOK), default `gpt-6-luna` at High reasoning; token prices; BYOK |
| Cloud | `https://docs.browser-use.com/openapi/v4.json` (`RunCreateRequest.model` enum, `"default": "gpt-6-luna"`) | `glm-5.3-flash` is an accepted value (`official-docs`) |
| Cloud | `https://docs.browser-use.com/cloud/agent/thinking-levels.md` | Reasoning values per model; `modelParams` |
| Cloud | `https://browser-use.com/pricing.md`, `https://browser-use.com/benchmarks/pricing-models.json` | Benchmark table includes GLM 5.3 Flash: quality 28.0/100, $0.114/task, 28.8 min/task on BU_Bench_v2 (`vendor-claim`; vendor's own benchmark, 60 tasks/setting). The pricing page does not list a GLM price row |
| OSS | `https://docs.browser-use.com/open-source/supported-models.md` | `ChatBrowserUse`, `ChatOpenAI` (any OpenAI-compatible `base_url`), `ChatAnthropic`, `ChatGoogle`, Bedrock, Ollama, Qwen/DashScope, **OpenRouter** section |
| OSS | `https://docs.browser-use.com/open-source/customize/agent/all-parameters.md`, `https://docs.browser-use.com/open-source/customize/agent/basics.md` | `llm`, `page_extraction_llm`, `use_vision`, `flash_mode`, `extend_system_message`, etc. |
| OSS | `https://github.com/browser-use/browser-use/blob/c75e847/skills/open-source/references/models.md`, `https://github.com/browser-use/browser-use/blob/c75e847/browser_use/agent/system_prompts/*.md` | The actual system prompts the agent sends (`source-code`) |

## 10. Caching / replay (honest answer: there is no action cache)

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/agent/scripts.md` | **Closest thing in Cloud:** the agent saves a tested script into a workspace; later runs reuse and self-repair it. It is an LLM-authored script pattern, not a deterministic cache with hit/miss semantics |
| `https://docs.browser-use.com/cloud/tutorials/grow-therapy-compare.md` | Worked example of "cached reruns" |
| `https://docs.browser-use.com/cloud/agent/models.md`, `https://browser-use.com/pricing.md` | Token-level prompt-cache pricing ("cached input" rates) |
| OSS `source-code` | `Agent.save_history`, `Agent.load_and_rerun`, `Agent.rerun_history` exist in `browser_use/agent/service.py`; they are **not documented** in `docs-site/` (scraped copy not published) or the repo markdown copied here. Anthropic `cache_control` support is in `browser_use/llm/anthropic/` |
| OSS | `https://docs.browser-use.com/open-source/customize/agent/output-format.md` (history / action logs) |

## 11. Agents (behavior, tools, hooks, structured output)

| Cloud / OSS | File |
|---|---|
| Cloud | `https://docs.browser-use.com/cloud/agent/*.md` (extensions, human-in-the-loop, models, network-capture, observability, quickstart, scripts, sessions, structured-output, thinking-levels, workspaces) |
| Cloud | `https://docs.browser-use.com/cloud/guides/webhooks.md` (V2 task / V3 session webhooks), `https://docs.browser-use.com/cloud/guides/mcp-server.md`, `https://docs.browser-use.com/cloud/eu-deployment.md` |
| Cloud | `https://docs.browser-use.com/cloud/tutorials/integrations/hermes-agent.md` **(Hermes integration: `browser.cloud_provider: browser-use` in `~/.hermes/config.yaml`, or the Browser Use CLI skill)**, also `https://docs.browser-use.com/cloud/tutorials/integrations/openclaw.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/claude-code.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/claude-managed-agents.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/n8n.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/vercel.md`, `https://docs.browser-use.com/cloud/tutorials/integrations/agentcard.md` |
| OSS | `https://docs.browser-use.com/open-source/customize/agent/{basics,all-parameters,output-format,prompting-guide}.md` |
| OSS | `https://docs.browser-use.com/open-source/customize/tools/{basics,available,add,remove,response}.md` (built-in actions, custom tools) |
| OSS | `https://docs.browser-use.com/open-source/customize/hooks.md` (lifecycle hooks) |
| OSS | `https://docs.browser-use.com/open-source/examples/**` (templates: fast-agent, parallel-browser, secure, playwright-integration; apps; skills) |
| OSS | `https://github.com/browser-use/browser-use/blob/c75e847/AGENTS.md`, `https://github.com/browser-use/browser-use/blob/c75e847/CLAUDE.md` (repo conventions and architecture notes), `https://github.com/browser-use/browser-use/blob/c75e847/skills/open-source/references/{agent,tools,actor}.md`, `https://docs.browser-use.com/open-source/legacy/actor/*` (low-level Playwright-like CDP "Actor") |
| OSS (beta) | `https://github.com/browser-use/browser-use/blob/c75e847/BETA_AGENT_INTEGRATION_FEATURES.md` (`browser_use.beta.Agent` backed by the Rust terminal SDK server); `https://docs.browser-use.com/open-source/browser-use-terminal.md` |
| OSS | `https://docs.browser-use.com/open-source/customize/integrations/{mcp-server,toolsets-for-claude}.md`, `https://docs.browser-use.com/open-source/browser-use-cli.md` |

## 12. API reference

| File | What |
|---|---|
| `https://docs.browser-use.com/openapi/v4.json` (32 paths) | **Authoritative machine-readable V4 reference** (runs, sessions, workspaces, browsers, profiles, extensions, integrations, wallets) |
| `https://docs.browser-use.com/openapi/v3.json` (16 paths), `https://docs.browser-use.com/openapi/v2.json` (29 paths) | Older APIs (V3 sessions/workspaces/billing/x402; V2 tasks/sessions/skills/profiles/files/billing) |
| `https://docs.browser-use.com/cloud/api-reference.md`, `https://docs.browser-use.com/cloud/api-v4-overview.md`, `https://docs.browser-use.com/cloud/api-v2-overview.md` | Auth (`X-Browser-Use-API-Key`, no Bearer), base URLs |
| `https://docs.browser-use.com/cloud/api-v4/**` (49 pages), `https://docs.browser-use.com/cloud/api-v3/**` (27), `https://docs.browser-use.com/cloud/api-v2/**` (44) | One page per endpoint. Each embeds the endpoint's OpenAPI YAML, so they duplicate the JSON specs; kept for per-endpoint grep. `https://docs.browser-use.com/llms-full.txt` has only stubs for these |
| `https://github.com/browser-use/browser-use/blob/c75e847/skills/cloud/references/api-v{2,3,4}.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/cloud/references/browser-api.md`, `https://github.com/browser-use/browser-use/blob/c75e847/skills/cloud/references/features.md` | Condensed API notes shipped in the repo (`source-code`) |
| `https://browser-use.com/api.md`, `https://browser-use.com/auth.md`, `https://browser-use.com/web-agent-api.md` | Marketing summaries (`vendor-claim`) |

Base URL: `https://api.browser-use.com/api/v4` (`servers` in the spec). The docs say billing account info for
every version is read from `GET /api/v2/billing/account` (`https://docs.browser-use.com/cloud/guides/concurrency.md`).

## 13. Pricing

| File | What | Provenance |
|---|---|---|
| `https://docs.browser-use.com/cloud/guides/billing.md` | Credits, BYOK (provider tokens + 0.2x orchestration fee), auto-recharge, API-key spending caps (soft limits) | `official-docs` |
| `https://docs.browser-use.com/cloud/api-v4/browsers/create-browser-session.md` | "$0.02/hour for all users", billed upfront, unused time refunded, rounded up to the minute, max 4 hours per session | `official-docs` |
| `https://docs.browser-use.com/cloud/agent/models.md` | V4 model token prices | `official-docs` |
| `https://browser-use.com/pricing.md` (official markdown view), `https://browser-use.com/benchmarks/pricing-models.json`, `https://browser-use.com/pricing/legacy.md` | Browser $0.02/hr; managed residential proxy $5/GB; direct or own-proxy $0.20/GB; model price + 20%; BU 2.0 model $0.60/$0.06/$3.50 per 1M; V2 from $0.006/step + $0.01/task | `vendor-claim` |
| `https://docs.browser-use.com/cloud/guides/x402.md`, `https://docs.browser-use.com/cloud/guides/x402-agent-wallets.md` | Crypto pay-per-request | `official-docs` |

No subscription tiers exist now; legacy plans are retired (`https://browser-use.com/pricing.md`, `https://docs.browser-use.com/cloud/guides/billing.md`).

## 14. Limits

| File | What |
|---|---|
| `https://docs.browser-use.com/cloud/guides/concurrency.md` | Concurrency by lifetime spend (10 / 50 / 250 / 500 / 1000), project vs edge HTTP rate limits (`max(25, 2 x concurrency)` RPS capped at 100 for general traffic), 5-second windows, 20-message session queue, 4-hour browser hard timeout, profile quota is separate. **Tier-1 threshold disagrees with the pricing page; see MANIFEST** |
| `https://docs.browser-use.com/cloud/faq.md`, `https://docs.browser-use.com/cloud/guides/troubleshooting.md` | Common failures and error-code handling |
| `https://docs.browser-use.com/cloud/api-v4/browsers/create-browser-session.md` | 4-hour session cap, 402 on insufficient credits |
| `https://docs.browser-use.com/cloud/guides/billing.md` | Monthly spending caps are soft limits |
| `https://browser-use.com/pricing.md` | Enterprise: 1,000+ concurrency, ZDR, HIPAA, EU residency on request (`vendor-claim`) |

For Justin's 100 to 1,000 profile target: 1,000 concurrent browsers needs the $25,000 lifetime-spend tier
or Enterprise; the number of **stored** profiles is capped by an undocumented limit (error "Profile limit reached").

## 15. Everything else

- Extensions: `https://docs.browser-use.com/cloud/browser/extensions.md`, `https://docs.browser-use.com/cloud/agent/extensions.md`, `https://docs.browser-use.com/cloud/api-v4/extensions/*`
- Integrations (OAuth tools): `https://docs.browser-use.com/cloud/api-v4/integrations/*`
- EU: `https://docs.browser-use.com/cloud/eu-deployment.md`
- MCP: `https://docs.browser-use.com/cloud/guides/mcp-server.md`, `https://github.com/browser-use/browser-use/blob/c75e847/browser_use/mcp/manifest.json`, `https://github.com/browser-use/browser-use/blob/c75e847/server.json`
- Skills shipped in the repo: `https://github.com/browser-use/browser-use/tree/c75e847/skills/{browser-use,cloud,open-source,qa,remote-browser,x402}/`
- Telemetry: `https://docs.browser-use.com/open-source/development/monitoring/telemetry.md`. The OSS library sends PostHog telemetry that "may include ... task instructions, URLs" unless `ANONYMIZED_TELEMETRY=false` is set. Set it for any client work (`official-docs`)
- Security / contribution: `https://github.com/browser-use/browser-use/blob/c75e847/.github/SECURITY.md`, `https://docs.browser-use.com/open-source/development/setup/*`
- Retired: `https://docs.browser-use.com/cloud/legacy/*`, `https://docs.browser-use.com/open-source/legacy/sandbox/*` (hosted sandbox, "Box" and "Bux" retired per the vendor preamble)
- Whole-site search: `https://docs.browser-use.com/llms-full.txt` (prose only, 227 sections, `Source:` URL under each heading), `https://docs.browser-use.com/llms.txt` (index with one-line descriptions), `https://docs.browser-use.com/sitemap.xml`
