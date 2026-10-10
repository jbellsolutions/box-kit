> **Read with its verification report.** [verification/browserbase.md](../verification/browserbase.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: Browserbase, the paid backup browser infra

Agent: browserbase deep-dive. Research date: 2026-10-09. Spend: $0. No Browserbase account or key exists, so nothing was run against the live API.
Hands-on work was limited to **offline** spikes: the HTTP transport was mocked, with no network calls and a dummy credential (`fleet/research/spikes/browserbase/RESULTS.md`).

Provenance tags follow `fleet/research/BRIEF.md`: `hands-on`, `source-code` (pinned commit), `official-docs`, `vendor-claim`, `third-party`, `unverified`.
`inference` marks my own reasoning from the cited evidence.

Corpus pages below are cited by their original vendor URL (the scraped copy under `fleet/research/corpus/browserbase/` is not published).
Source clones live under `<scratch>/sources/` and are written as `<repo>@<sha>`.

---

## 1. Verdict

- **Browserbase has no documented or self-serve sticky, static or dedicated IP.** The proxies page overview does promise "consistent IP addresses across sessions", but no parameter, field or SDK type implements it. The built-in residential proxy rotates per session; only geolocation can be pinned (country, US state, city), and that is best effort. Scale/contract terms are unknown.
  - The only way to get "same IP every time" is a **bring-your-own external proxy** per profile, on Developer plan or higher.
  - External proxies must be HTTP or HTTPS (no SOCKS5) and are validated when the session is created.
  - Using a BYO proxy loses Browserbase's automatic timezone alignment: the fleet must call CDP `Emulation.setTimezoneOverride` on every page.
  - Steel Cloud sells dedicated IPs at $5 per IP per month. Browserbase has no equivalent.
  - Sources: `official-docs` + `source-code` (proxies page, timezones page, Node SDK `SessionCreateParams`).
- **There is no "same fingerprint every time" contract.**
  - Without Verified, a session is **always Linux**, and passing `os` returns an error. Verified (Windows/Mac/mobile/tablet, real pre-made fingerprints, fixed viewport) is **Scale plan only** (custom pricing).
  - No API pins a fingerprint to a Context.
  - The plan table's "Basic" tier is never defined.
  - A `fingerprint` field still exists in Stagehand 4.2.0's types, and the Browserbase Python SDK passes it through unvalidated (`hands-on`). It is absent from the Browserbase SDK source and the docs spec, so server behaviour is unknown. Do not design on it.
- **Contexts give persistent logins and lock them in.**
  - What a Context stores: the Chromium user-data dir (cookies, localStorage, IndexedDB, sessionStorage, service workers, autofill, preferences/HSTS). Not stored: the HTTP cache.
  - Contexts are encrypted at rest, live indefinitely, and save when the session ends with `persist: true`.
  - There is **no API list endpoint and no export**. The dashboard can list Contexts (changelog 2026-08-19). Context upload via the API is deprecated: the `uploadUrl` field is a "non-functional sentinel".
  - Consequences:
    - The fleet registry is the only *programmatic* index of profile → `contextId`. Set each Context `name` to the `profile_id` so the dashboard can serve as a manual recovery index.
    - A profile cannot be cleanly moved between Browserbase and Steel. A partial move of cookies and localStorage over CDP from a live session is possible but untested, and the IP and fingerprint change may force re-auth anyway.
    - Account suspension "will invalidate all Contexts".
  - So **infra must be chosen per profile at creation**, as the brief already suspects. Sources: `source-code` + `official-docs`.
- **The one capability the fleet can neither build nor buy elsewhere is the Stagehand v4 action cache.** The other reasons in Q5 are measured-decision reasons.
  - In Stagehand v4, `act/observe/extract` caching is **server-side on Browserbase only**. The local `cacheDir`/`enableCaching` were removed in v4.
  - On self-hosted Steel, every Stagehand call runs inference. The brief's "Stagehand = deterministic, cached" premise holds only on Browserbase, unless the fleet builds its own replay cache or pins Stagehand v3.
  - The cache is best effort, gated per project on the server, keyed on URL + page accessibility tree + instruction + variables, and ships the page tree to Browserbase.
  - Hit rate on social feeds is unmeasured. Sources: `source-code` (stagehand@1fc8849 `packages/extension/services/cacheService.ts`) + `official-docs`.
- **Browserbase's direction is "identity, not evasion".**
  - Verified, Web Bot Auth and the bot-protection partnerships (Cloudflare, Fingerprint) make traffic *recognisable as an agent* to participating sites.
  - Meta, TikTok and X are not documented partners. For maintaining client social accounts this is not a stealth upgrade, and it may be the opposite of what the fleet wants (`vendor-claim` + `inference`).
- **The AUP risk is real but not explicit.**
  - No public acceptable-use policy was found. The ToS (last updated 2025-08-01) has **no social-media or multi-account clause about target sites**.
  - It does ban using the platform "to transmit, or procure the sending of, any advertising or promotional material ... 'spam,' or any other similar solicitation", and impersonating "any other person or entity".
  - It also keeps the right to suspend "for any or no reason".
  - Automated DMs and lead-gen outreach for clients sit close to the solicitation clause. A suspension wipes every Context, which means every client login (`official-docs` ToS).
- **Cost: proxy bandwidth dominates.**
  - At 50 MB per browser-hour, Browserbase proxy ($10-12/GB) costs about **5x the browser time** ($0.10-0.12/h).
  - List-price estimates on Startup: **$539/mo for 30 profiles × 1 h/day**, about $18 per profile-month at 1 h/day and about $54 at 3 h/day. 1,000 profiles × 3 h/day is about $54k/mo at list, and needs the custom Scale plan for concurrency.
  - With BYO proxies the Browserbase browser bill drops to about $3-5 per profile-month per daily hour ($0.10/h × 30 h, plus a share of the $99 base), if Browserbase does not bill BYO-proxy bytes (unknown). The BYO proxy cost is extra and not modelled here.
- **Hermes' built-in Browserbase mode is not usable for persistent profiles.**
  - `hermes-agent@5ba559c` `plugins/browser/browserbase/provider.py` never sends a Context.
  - It defaults `keepAlive` and `proxies` to true, uses the deprecated `advancedStealth`, and needs `BROWSERBASE_PROJECT_ID`.
  - It passes `BROWSERBASE_SESSION_TIMEOUT` straight through as seconds, while Browserbase's own Hermes page says milliseconds (600000), which would exceed the 21,600 s cap.
  - The fleet must ship its own session factory (`source-code`).
- **Recommendation in one line:** keep Steel as the default home for social-media profiles. Offer Browserbase as an **opt-in tier chosen at profile creation** for these cases:
  - a site where a measured Steel + pinned proxy run fails;
  - burst or pilot capacity before the Steel pool exists;
  - workflows where a measured Stagehand cache hit rate pays for the premium.

  In every case use BYO sticky proxies, `recordSession:false`, a per-context lock, and a fleet-held API key.

---

## 2. Answers

### Q1. Product surface (as of 2026-10-09)

**Sessions.**
- Create: `POST /v1/sessions` returns a `connectUrl` (CDP websocket), `seleniumRemoteUrl` and `signingKey`. The status lifecycle is `PENDING|RUNNING|ERROR|TIMED_OUT|COMPLETED`.
- End: `POST /v1/sessions/{id}` with `{"status":"REQUEST_RELEASE"}`.
- Create parameters (source wins): `browserSettings{advancedStealth(deprecated), allowedDomains, blockAds, captchaImageSelector, captchaInputSelector, context{id,persist}, extensionId, ignoreCertificateErrors, logSession, os, recordSession, solveCaptchas, verified, viewport}`, plus `extensionId`, `keepAlive`, `projectId`, `proxies`, `proxySettings{caCertificates}`, `region`, `timeout` (seconds, 60-21600), and `userMetadata` (<512 chars, string values for querying).
- Billing is per minute with a **1-minute minimum per session**.
- Sources: `source-code` `bb-sdk-node@adef824 src/resources/sessions/sessions.ts`; `official-docs` `https://docs.browserbase.com/reference/api/openapi.v1.yaml` (`Sessions_create`), `https://docs.browserbase.com/optimizations/concurrency/overview.md`.

**Contexts (persistence).**
- What is stored: see the Verdict above (`official-docs` `https://docs.browserbase.com/platform/browser/core-features/contexts.md`).
- `persist:true` means changes are saved **when the session closes**. Docs: "wait a few seconds before reusing the Context". `persist:false` gives read-only use of the stored state. The Node SDK defaults `persist` to `false`.
- Rules from the docs:
  - avoid simultaneous sessions on the same Context, because sites may force a logout;
  - use one Context per site per login.
- Contexts "live indefinitely". They become invalid on explicit delete, project delete, or account suspension or deletion.
- Names are optional, unique per project and case-insensitive (since 2026-08-19, `vendor-claim` changelog).
- Encrypted at rest. The create response still returns `publicKey`, `cipherAlgorithm` (AES-256-CBC) and `initializationVectorSize`, which are leftovers of a removed upload feature.
- API: create, get, delete. `PUT /v1/contexts/{id}` exists in both SDKs but is marked `@deprecated`. **No API list and no export.** The dashboard lists and names Contexts (`vendor-claim` changelog 2026-08-19).
- **No documented size or count limit.** The docs only warn that large contexts slow sessions. Steel Cloud profiles, by contrast, have a 300 MB cap and are auto-deleted after 30 idle days (`official-docs` Steel corpus).
- BYOS (Enterprise) can write Context artifacts to your own S3. Their format and encryption are undocumented (`official-docs` `https://docs.browserbase.com/account/enterprise/byos-setup-guide.md`).
- Sources: `source-code` `bb-sdk-node@adef824 src/resources/contexts.ts`; `official-docs` `https://docs.browserbase.com/reference/api/openapi.v1.yaml` lines 927-998.

**Keep-alive and max duration.**
- `keepAlive:true` keeps a session alive across CDP disconnects; reconnect with the same `connectUrl`. Paid plans only.
- Without keepAlive, **a session ends when its CDP client disconnects**.
- `timeout` is 60-21,600 s. The **hard maximum session is 6 hours**, including on Scale ("6+ hrs" in the plan table is not explained).
- keepAlive sessions bill until released or timed out. Overage has "No caps. No cut-offs."
- Sources: `official-docs` `https://docs.browserbase.com/platform/browser/long-sessions/{overview,keep-alive,timeouts}.md`, `https://docs.browserbase.com/account/billing/plans.md`.
- Docs bug: the raw-HTTP Python examples send `"api_timeout"` in the JSON body. The wire field is `timeout`: the SDK maps `api_timeout` → `timeout` (`hands-on`, spike 1).

**Proxies.**
- `proxies:true` gives a managed residential proxy, "best-effort" US, possibly falling back to a nearby country.
- `proxies:[{type:"browserbase", geolocation:{country, state?, city?}, domainPattern?}]` covers 200+ countries; the geolocation is best effort.
- BYO proxy: `{type:"external", server, username?, password?, domainPattern?}`, HTTP or HTTPS only.
- `{type:"none", domainPattern}` excludes domains. Rules are evaluated in order, first match wins.
- `proxySettings.caCertificates` lets the browser trust a TLS-intercepting proxy. It is **not** a sticky-IP knob.
- **Sticky IP: no documented or self-serve feature.** There are zero hits for sticky/static/dedicated IP in the corpus and the SDK source. The overview sentence "consistent IP addresses across sessions" has no parameter behind it. Its only concrete consistency mechanism is the geolocation pin, which is best effort. Scale/contract terms are unknown.
- Built-in proxies come from third-party providers with their own blocklists. The documented, "not exhaustive" list includes banking, .gov, streaming, ticketing, **webmail (Outlook, Yahoo)** and gambling. This matters for email-verification steps.
- Proxy billing has a 1 MB minimum and rounds to the MB.
- **Unknown:** whether bytes through a `type:"external"` proxy count toward Browserbase's per-GB proxy billing. The docs never say. The session's `proxyBytes` field cannot settle it.
- Sources: `official-docs` `https://docs.browserbase.com/platform/identity/proxies.md`, `https://docs.browserbase.com/platform/browser/security/ip-allowlisting.md` ("Socks5 proxies are not supported"); `source-code` Node SDK proxy config types.

**Stealth: basic vs advanced vs Verified.**
- `advancedStealth` is deprecated in source: "use `verified` instead". Hermes still sends it.
- Verified is described as:
  - a "purpose-built Chromium browser with real browser fingerprints that Browserbase's bot protection partners recognize";
  - `os` choices: windows (default), mac, linux, mobile (384x696), tablet (800x1200); `android` is rejected;
  - viewport not customisable;
  - "currently in beta";
  - **Scale plan** only.
- The docs warn: "When using contexts, changing the OS could reduce the success rate".
- Non-Verified sessions are "always `linux`". Their only documented stealth is "Automatic fingerprinting (devices, locales, operating systems)", with no detail.
- Plan table: "Verified: No / Basic / Basic / Verified". The marketing table says "Stealth Mode: No / Basic / Basic / Advanced". **"Basic" is never defined.**
- Sources: `official-docs` `https://docs.browserbase.com/platform/identity/{overview,verified-customization}.md`, `https://docs.browserbase.com/account/billing/plans.md`, `https://docs.browserbase.com/platform/browser/getting-started/create-browser-session.md`; `vendor-claim` `https://www.browserbase.com/pricing`; `source-code` sessions.ts.

**Fingerprint control and pinning per context.**
- None. The fleet controls only `verified` + `os` (Scale) and `viewport` (non-Verified).
- There is no fingerprint ID, seed or persistence flag.
- The identity blog (2026-04-06, `vendor-claim`) claims Verified keeps "the browser environment ... coherent across sessions", but no API or doc guarantees the same fingerprint per Context.
- Stagehand's generated `BrowserbaseFingerprint` (`browsers/devices/locales/operatingSystems/screen/httpVersion`) is a *selection filter*, not a pinned fingerprint. Its server-side support is unknown (`source-code` stagehand@1fc8849 `packages/protocol/schemas.ts`; `hands-on` spike 1 shows it is passed through).

**CAPTCHA solving.**
- On by default on Developer and above; the Free plan has none. Disable with `browserSettings.solveCaptchas:false`.
- Takes 5-30 s and emits the console events `browserbase-solving-started` / `browserbase-solving-finished`.
- Non-standard image CAPTCHAs are handled through `captchaImageSelector` / `captchaInputSelector`.
- No per-solve fee is listed (Steel Cloud charges $1-3 per 1,000).
- Which challenge vendors it solves (for example Arkose, or TikTok's slider) is **not documented**.
- The docs add: "Use CAPTCHA solving only for workflows that users and website owners authorize."
- Sources: `official-docs` `https://docs.browserbase.com/platform/identity/captcha-solving.md`, `plans.md`.

**Live View for a human login.**
- `GET /v1/sessions/{id}/debug?expiresIn=60..21600` returns `debuggerFullscreenUrl`, `debuggerUrl`, `wsUrl` and a `pages[]` list with one live URL per tab.
- It is **interactive** ("watch, click, type, and scroll") and **iframe-embeddable**:
  - read/write: `sandbox="allow-same-origin allow-scripts"`;
  - read-only: add `style="pointer-events:none"`;
  - `&navbar=false` hides the navbar.
- When the session ends, the iframe posts `browserbase-disconnected`.
- Mobile keyboards are "not officially supported".
- The docs list "delegate credentials - give control to the end user" and recommend logging in once through Live View and then persisting with a Context.
- `inference`: the URL appears to be a bearer capability, since no API key is involved in viewing it. Treat it like a password, mint it with a short `expiresIn`, and never put it in an agent's context.
- Sources: `official-docs` `https://docs.browserbase.com/platform/browser/observability/session-live-view.md`, `https://docs.browserbase.com/platform/identity/authentication.md`; `source-code` `SessionDebugParams.expiresIn`.

**Recordings.**
- On by default (`recordSession`).
- Delivered as an HLS replay per tab (up to 10 tabs). Playlist segment URLs are signed and valid for 6 h. The playlist endpoint is limited to 120 requests per minute per project.
- MP4 downloads: `POST`/`GET /v1/sessions/{id}/recording/downloads`, 5 POSTs per minute, only after the session ends.
- Retained up to 30 days (24 h on BYOS).
- The ToS says that by using recording "you authorize us to store the recordings for 30 days" and that you must "clearly and conspicuously display a persistent label identifying to the user that a recording is in process".
- Sources: `official-docs` `https://docs.browserbase.com/platform/browser/observability/{session-replay,recording-downloads}.md`; `official-docs` ToS.

**Uploads and downloads.**
- Downloads are synced to Browserbase storage with a timestamp suffix and listed via `GET /v1/sessions/{id}/downloads`, which the SDK exposes but the docs-site spec omits.
- Uploads: Playwright `setInputFiles`, or `POST /v1/sessions/{id}/uploads` for large files (lands in `/tmp/.uploads/`).
- Uploads through Live View are supported.
- Sources: `official-docs` `https://docs.browserbase.com/platform/browser/files/{downloads,uploads}.md`; `source-code` api.md.

**Extensions.**
- Upload a `.zip` (≤100 MB, `manifest.json` at the root), then pass `extensionId` on create. **One extension ID per session.**
- An extension restarts the browser and adds creation time.
- Stagehand v4 uploads its own 441,819-byte extension on every `browserbase.launch()` unless you pass `extension_id` (`hands-on`, spike 2).
- Sources: `official-docs` `https://docs.browserbase.com/platform/browser/core-features/browser-extensions.md`.

**Regions.**
- `us-west-2` (default), `us-east-1`, `eu-central-1`, `ap-southeast-1` (`source-code` region enum).
- The marketing FAQ also claims a "UK" region and APAC "upon request". These are not in source or the docs: source wins, so there are 4 regions.
- Functions run only in `us-west-2`.
- Sources: `official-docs` `https://docs.browserbase.com/optimizations/latency/multi-region.md`, `https://docs.browserbase.com/platform/functions/limits.md`; `vendor-claim` `https://www.browserbase.com/pricing`.

**Web Bot Auth and verified agents.**
- **Beta, request access.** Uses RFC 9421 HTTP message signatures (`Signature-Agent`, `Signature-Input`, `Signature` headers) that participating sites can verify.
- In the docs' words: "A valid signature doesn't grant access or sign your agent into a user account."
- Cloudflare lists Browserbase in its first "signed agents" cohort.
- `inference`: it identifies your traffic as an agent, which helps only on sites that welcome identified agents.
- Sources: `official-docs` `https://docs.browserbase.com/platform/identity/web-bot-auth.md`; `third-party` blog.cloudflare.com/signed-agents; `vendor-claim` browserbase.com/blog/identity (2026-04-06).

**The hosted Stagehand API.**
- In v4 the per-step act/observe/extract loop runs **inside the browser** as a Chrome extension.
- The hosted "Stagehand API" (`api.stagehand.browserbase.com`, plus `use1`, `euc1` and `apse1` regional hosts) serves only:
  1. the server-side cache (`POST /cache/get`, `/cache/set`), and
  2. Model Gateway inference.
- Both require a Browserbase session and key: "Model Gateway requires Browserbase-hosted browsers", and "With a local browser ... the cache option has no effect".
- Sources: `source-code` stagehand@1fc8849 `packages/extension/clients/{stagehandApi,cacheClient}.ts`, `services/cacheService.ts`; `official-docs` stagehand `packages/docs/v4/{best-practices/caching,configuration/models}.mdx`, `https://docs.browserbase.com/platform/model-gateway/overview.md`.

**Agent products.**
- **Agents**: `POST /v1/agents/runs` with `task`, optional `agentId`, `systemPrompt`, `resultSchema` and `%variables%`.
  - The agent is autonomous, built on Stagehand, and has browser, search, file system and shell tools. You cannot add custom tools.
  - `browserSettings` supports context, proxies and verified.
  - Pause/resume (`pauseWhen`) since 2026-09-24.
  - Included runs: 3, 15 or 50 per month by plan; overage not published.
  - The model is chosen by Browserbase. Agents are "outside the scope" of ZDR/BYOS, and a BYO model key needs a sales contact.
- **Functions**: serverless TypeScript in `us-west-2`, 60-900 s per invocation, no keepAlive, no persistent storage, free on every plan; Secrets since 2026-09-30.
- **Search** ($7 per 1,000) and **Fetch** ($0.5-1 per 1,000, no JS execution, 5 MB / 60 s).
- `inference`: Agents and Functions do not fit Hermes + System 1 routing. They replace the fleet's own agent loop and model choice.
- Sources: `official-docs` `https://docs.browserbase.com/platform/agents/{overview,how-it-works}.md`, `https://docs.browserbase.com/platform/functions/limits.md`, `plans.md`; `vendor-claim` `https://www.browserbase.com/changelog`.

### Q2. Pricing and limits (October 2026)

Source: `official-docs` `https://docs.browserbase.com/account/billing/plans.md` (fetched 2026-10-09). It matches `vendor-claim` `https://www.browserbase.com/pricing` except where marked.

| | Free | Developer | Startup | Scale |
| - | - | - | - | - |
| Price per month | $0 | $20 | $99 | Custom ("contact sales") |
| Included browser hours | 1 | 100 | 500 | "Flexible" / usage-based |
| Browser-hour overage | n/a | $0.12 | $0.10 | Custom |
| Included proxy | 0 GB | 1 GB | 5 GB | usage-based |
| Proxy overage | n/a (no proxies) | $12/GB | $10/GB | Custom |
| Concurrency | 3 | 25 | 100 | 250+ |
| Session creation rate | 5/min | 25/min | 50/min | 150+/min |
| Max session | 15 min | 6 h | 6 h | "6+ h" (the timeouts page says 6 h maximum) |
| keepAlive | no | yes | yes | yes |
| CAPTCHA | no | auto | auto | auto |
| Verified / stealth | no | "Basic" | "Basic" | Verified (marketing: "Advanced") |
| Data retention | 7 d | **7 d (docs) vs 30 d (pricing page)** | 30 d | 30+ d |
| Projects | 1 | ≤2 | ≤5 | 5+ |
| Agent runs included | 3 | 15 | 50 | custom |
| Search / Fetch | 1k / 1k | 1k ($7/1k after) / 1k ($1/1k; $4/1k with proxies) | 1k / 10k ($0.5/1k after) | custom |
| SSO, HIPAA BAA, DPA | no | no | no | available |

- Billing granularity: per minute and per MB, with a 1-minute and 1 MB minimum per session.
- Concurrency is per organization and split across projects.
- A 429 response comes with `retry-after` and `x-ratelimit-*` headers.
- Contexts: no documented price, count limit or size limit.
- Model Gateway is billed at "market price ... no markup" (`vendor-claim`).
- Retention disagreement, all four figures (none is clearly authoritative):
  - plans page: Developer 7 d;
  - pricing page: Developer 30 d;
  - replay page: 30 d for non-BYOS projects;
  - ToS: recordings stored 30 d.

  Re-check at purchase.

### Q3. Acceptable use

- **No standalone public AUP was found.**
  - `www.browserbase.com/legal/*`, `/aup` and `/acceptable-use-policy` all redirect to sign-in. That does not prove no AUP exists, and enterprise/MSA terms are unknown.
  - Web searches found none.
- The governing public document is the **Terms of Use, "Last Updated: August 1, 2025"** (https://www.browserbase.com/terms-of-service, fetched 2026-10-09; local copy at `<scratch>/spikes/browserbase/fetched/tos.md`). Tag: `official-docs`.
- **There is no clause about social media, multi-account management or account creation on third-party sites.**
  - The "multiple accounts" sentence concerns **Browserbase accounts**: "Abuse our account or plan system, including but not limited to circumventing usage limits, creating multiple accounts to avoid restrictions, manipulating service tiers ... may result in immediate termination of your account without refund."
- Clauses that bite on the fleet's use case (quoted):
  - "You agree not to use the Platform: ... To transmit, or procure the sending of, any advertising or promotional material, including any 'junk mail,' 'chain letter,' 'spam,' or any other similar solicitation."
    - `inference`: automated DMs, outreach and lead-gen messaging are closest to this clause.
  - "To impersonate or attempt to impersonate Browserbase, a Browserbase employee, another user, or any other person or entity."
    - `inference`: operating a client's own account with their authorization is not obviously impersonation. Personas or fake accounts would be.
  - "To engage in any other conduct ... which, as determined by us, may harm Browserbase or users of the Platform, or expose them to liability."
  - "Terminate or suspend your access to all or part of the Platform for any or no reason, including without limitation, any violation of these Terms of Use."
  - On recording: "you will clearly and conspicuously display a persistent label identifying to the user that a recording is in process"; "you authorize us to store the recordings for 30 days".
  - The docs (`https://docs.browserbase.com/platform/identity/captcha-solving.md`) say: "Use CAPTCHA solving only for workflows that users and website owners authorize. Follow the site's terms."
  - `https://docs.browserbase.com/platform/identity/overview.md` says: "Review the site's terms of service to ensure compliance."
- Posture (`vendor-claim`, blog 2026-04-06): "framing this as stealth implies something adversarial ... It feels shady"; "What we've built is better understood as identity."
- Net: nothing in the ToS forbids operating clients' social accounts with their authorization. However:
  - the target platforms' own terms forbid unofficial automation;
  - Browserbase's stated product direction is declared agent identity;
  - the ToS reserves suspension at will.

  So treat Browserbase as an infra choice that can be withdrawn. Never make it the only home for a client's login state.

### Q4. Compatibility (exact code)

**Stagehand (native environment), Python 4.2.0.** Parameter names were verified by `hands-on` spike 2/2b. The docs' `BrowserbaseBrowserSettings.model_validate(...)` fails on 4.2.0 (TypedDict), so use plain dicts.

```python
from stagehand import Stagehand, browserbase

browser = await browserbase.launch(
    api_key=BB_KEY,                       # fleet-held; never in a Hermes profile
    region="us-east-1",
    timeout=3600,                         # seconds; sent as 3600.0 (spec says integer: verify)
    keep_alive=False,
    proxies=[{"type": "external", "server": "http://<sticky-proxy>:<port>",
              "username": PROXY_USER, "password": PROXY_PASS}],
    browser_settings={"context": {"id": CONTEXT_ID, "persist": True},
                      "record_session": False, "solve_captchas": True},
    user_metadata={"fleet_profile": "p-0001"},   # short strings only; Stagehand adds ~90 chars
    # extension_id=PREUPLOADED_STAGEHAND_EXT_ID  # avoid a 442 KB upload per launch
)
stagehand = await Stagehand.create(browser=browser, model=..., model_api_key=..., cache=True)
page = await browser.context.active_page()
# ... act / observe / extract ...
await stagehand.close()     # ends Stagehand RPC only
await browser.close()       # REQUEST_RELEASE -> session ends -> Context persists
```

- To attach to a session the fleet created itself: `await browserbase.connect(api_key=BB_KEY, session_id=sid)`. The Stagehand extension must already be installed on that session through its `extensionId`.
  - `browser.close()` on a connected Browserbase browser **also sends `REQUEST_RELEASE`** (`source-code` stagehand 4.2.0 `browser.py`).
  - Cross-cutting: on a `local_browser.connect()` browser (for example Steel), `browser.close()` sends CDP `Browser.close` and kills the remote Chromium, which contradicts the v4 docs (`RESULTS.md`).
- Open issue: stagehand#2782 (2026-08-20, open), "Stagehand.create times out on Browserbase with official extension preloaded" on 4.0.1. Whether 4.2.0 fixes it is unknown (`third-party`).

**Browser-Use over CDP, browser-use 0.13.11.**
- The integration shape matches the Browserbase docs (`official-docs` `https://docs.browserbase.com/integrations/browseruse/python.md`) and was `hands-on`-checked offline.
- `Browser is BrowserSession` and `is_local=False` for `cdp_url`.
- browser-use opens tabs in the default context via `Target.createTarget` without a `browserContextId` (`source-code` browser-use@c75e847). That matters because Browserbase says to "always use the default context".

```python
from browserbase import Browserbase
from browser_use import Agent, Browser

bb = Browserbase(api_key=BB_KEY)
s = bb.sessions.create(
    region="us-east-1",
    api_timeout=3600,          # NOT timeout= (that is the HTTP client timeout)
    proxies=[{"type": "external", "server": "http://<sticky-proxy>:<port>",
              "username": PROXY_USER, "password": PROXY_PASS}],
    browser_settings={"context": {"id": CONTEXT_ID, "persist": True},
                      "record_session": False},
    user_metadata={"fleet_profile": "p-0001"},
)
browser = Browser(cdp_url=s.connect_url, keep_alive=False)   # or BrowserProfile(cdp_url=..., keep_alive=False)
agent = Agent(task=TASK, llm=LLM, browser=browser)
result = await agent.run()
await browser.stop()       # drops CDP -> session ends (no keepAlive) -> Context persists
try:
    bb.sessions.update(s.id, status="REQUEST_RELEASE")   # belt and braces
except Exception:
    pass   # may error if the session already COMPLETED on disconnect
```

**Playwright connect.**

```python
browser = await pw.chromium.connect_over_cdp(session.connect_url)
context = browser.contexts[0]          # use the DEFAULT context (Verified + recording rely on it)
page = context.pages[0]
```

The Node equivalent is `chromium.connectOverCDP(session.connectUrl)`. Puppeteer and Selenium (`seleniumRemoteUrl` + `signingKey`) are also documented.
Sources: `official-docs` `https://docs.browserbase.com/platform/browser/getting-started/using-browser-session.md`, `https://docs.browserbase.com/optimizations/concurrency/overview.md`.

### Q5. When the fleet needs Browserbase instead of self-hosted Steel

**Case for Browserbase.** Each reason is concrete and has a test that decides it.

1. **Stagehand v4 caching is Browserbase-only.**
   - If the fleet's "Stagehand = cached, cheap, near-deterministic" economics depend on Stagehand's own cache, they exist only on Browserbase browsers.
   - Decide by measuring hit rate and token savings per profile workflow on Browserbase.
   - Compare those savings with the browser-hour premium and with the alternatives: a fleet-built replay cache on Steel, or pinning Stagehand v3 with `cacheDir`.
   - Sources: `source-code` + `official-docs` above.
2. **Stagehand v4 is plug-and-play there.**
   - `browserbase.launch()` uploads and attaches the extension for you.
   - Over remote CDP (Steel), the extension must already be installed, or loaded from a shared filesystem (`official-docs` stagehand v4 `configuration/browser.mdx`, "Connecting over CDP").
   - Flag for the Steel and Stagehand dossiers.
3. **CAPTCHA auto-solve with no per-solve fee.** Self-hosted Steel has "None" (Steel corpus `https://docs.steel.dev/overview/self-hosting/steel-local-vs-steel-cloud.md`). Coverage of the challenges that Meta, TikTok and X use is unknown.
4. **Burst and no-ops capacity.**
   - 100 concurrent sessions on a $99 self-serve plan, and 250+ on Scale.
   - Chromium updates, crash recovery, 4 regions, HLS/MP4 recordings, and an embeddable interactive Live View.
   - Self-hosted Steel needs about 900 MB RAM per live browser (brief, measured) and one container per concurrent browser (Steel corpus INDEX).
5. **Human login UX.** The interactive iframe Live View with per-tab URLs and TTLs is documented end-to-end. Self-hosted Steel's human-login viewer is "not documented; needs a spike" (Steel corpus INDEX).
6. **Verified, if the fleet buys Scale.** Real Windows or Mac fingerprints instead of a Linux-only browser.
   - Value against Meta, TikTok and X is unproven, because their detection is in-house.
   - Decide by A/B on public bot-test pages first, then on a sacrificial account. Never on client accounts.
7. **Pilots before the Steel pool is built.**

**Case against Browserbase.**

1. **No sticky IP.** You pay for and manage BYO static proxies anyway, and lose the automatic timezone alignment.
2. **Linux-only fingerprint below Scale, and no per-context fingerprint pinning.**
3. **Lock-in.**
   - No Context export and no API list (dashboard only).
   - Moving a profile means a human re-login, or an untested partial cookie/localStorage copy over CDP.
   - Suspension invalidates every Context.
4. **Cost at scale.** With Browserbase proxies, the proxy line is about 5x the browser line. 1,000 profiles × 3 h/day is about $54k/mo at Startup list, and 250 peak concurrency forces the custom Scale plan.
5. **AUP and positioning.** Solicitation and impersonation clauses, "any or no reason" termination, and the declared-agent-identity strategy.
6. **Shared-key blast radius.**
   - `GET /v1/sessions` is account-wide; the Node `SessionListParams` has only `q` and `status`.
   - A naive "release all RUNNING" cleanup kills every other agent's sessions. The incident is documented in skills#153 (`third-party`, 2026-08-22) and confirmed by `source-code` `SessionListParams`.
   - There are no scoped per-agent keys. Hermes profiles must never hold the key.
7. **Privacy.**
   - Recordings are on by default and kept up to 30 days.
   - The Stagehand cache ships page accessibility trees, and possibly `%variables%`, to Browserbase.
   - Client inboxes and DMs would land in Browserbase storage unless disabled. ZDR and BYOS are Enterprise-only.
8. **Maturity signals** (`third-party`, open issues):
   - stagehand#2782: v4 init timeout on Browserbase.
   - sdk-node#183: keepAlive sessions going `COMPLETED` in seconds; possibly the same cross-agent release as skills#153 (unverified).
   - mcp-server-browserbase#187: orphaned sessions.

**Decision rule** (`inference`):
- Home a profile on Browserbase only when one of reasons 1, 3, 4 or 6 is *measured* to matter for that profile's sites and workflows. Otherwise use Steel.
- Choose at profile creation and record it in the registry.
- Fail over only between profiles, never by moving a live Context.

### Q6. Cost model (estimate)

Assumptions:
- 30-day month; 1 GB = 1,000 MB; 50 MB of proxy traffic per browser-hour (given).
- Hours spread across the day: average concurrency = profiles × h ÷ 24. "Peak" assumes a 12 h active window.
- List prices fetched 2026-10-09: `official-docs` `plans.md` and `vendor-claim` `https://www.browserbase.com/pricing`.
- Computed by `fleet/research/spikes/browserbase/cost_model.py`, output in `out_cost_model.txt`.

The table header uses short labels. In plain words:
- **Browserbase on Developer** and **Browserbase on Startup**: Browserbase also supplies (and bills) the proxy.
- **Browserbase browser time only**: Startup plan with your own (BYO) proxy. The BYO proxy cost is not included.
- **Steel Cloud Scale**: Steel's proxy, with or without a $5 dedicated IP for each profile.

| Profiles × h/day | Browser-h/mo | Proxy GB/mo | Avg / peak concurrency | Browserbase on Developer | Browserbase on Startup | Browserbase browser time only | Steel Cloud Scale + $5 IP per profile | Steel Cloud Scale, no dedicated IPs |
| - | - | - | - | - | - | - | - | - |
| 30 × 1 | 900 | 45 | 1.2 / 2.5 | $644 | **$539** | $139 | $642 | $492 |
| 30 × 3 | 2,700 | 135 | 3.8 / 7.5 | $1,940 | **$1,619** | $319 | $1,326 | $1,176 |
| 100 × 1 | 3,000 | 150 | 4.2 / 8.3 | $2,156 | **$1,799** | $349 | $1,790 | $1,290 |
| 100 × 3 | 9,000 | 450 | 12.5 / 25 | $6,476 | **$5,399** | $949 | $4,070 | $3,570 |
| 1,000 × 1 | 30,000 | 1,500 | 41.7 / 83 | $21,596 | **$17,999** | $3,049 | $16,550 † | $11,550 † |
| 1,000 × 3 | 90,000 | 4,500 | 125 / 250 | $64,796 ‡ | **$53,999** ‡ | $9,049 ‡ | $39,350 † | $34,350 † |

How the columns are calculated:
- Browserbase on Startup: $99 + (h − 500) × $0.10 + (GB − 5) × $10. Example for 30 × 1: $99 + 400 × $0.10 + 40 × $10 = **$539**.
- Browserbase on Developer: $20 + (h − 100) × $0.12 + (GB − 1) × $12.

Footnotes:
- ‡ 250 peak concurrency exceeds Startup's 100, so the custom **Scale** plan is required. The figure is a list-rate reference, not a quote. At a 24 h spread (125 average) it still exceeds 100.
- † Steel Cloud Scale caps at 100 concurrent sessions and a 1 h maximum session, with 25 self-serve dedicated IPs. 1,000 profiles needs Steel Enterprise (custom).
  - Steel Scale = $250 + max(0, usage − $100 credit) + $5 × dedicated IPs.
  - Dedicated-IP traffic is still metered at $6/GB.
  - Sources: `vendor-claim` Steel corpus `https://steel.dev/pricing.md`, `official-docs` `https://docs.steel.dev/overview/pricinglimits.md`, `https://docs.steel.dev/overview/sessions-api/dedicated-ips.md`.

Reading the table:
- Per profile-month on Browserbase with its proxy: about **$18 at 1 h/day** and about **$54 at 3 h/day**, roughly flat across scale at list price.
- About 74-83% of that is proxy. If BYO proxy traffic is not billed by Browserbase (**unknown**), the Browserbase share falls to about $3-5 per profile-month per daily hour (for example $3,049 / 1,000 profiles at 1 h/day, or $139 / 30), plus the BYO proxy bill.
- Not modelled:
  - BYO sticky-proxy cost (see the antidetect-proxies dossier);
  - self-hosted Steel droplet cost (see the scale-infra dossier);
  - LLM tokens;
  - Scale-plan discounts;
  - Steel Cloud CAPTCHA fees;
  - keepAlive idle minutes. Orphans bill until timeout: 1,000 orphaned 6 h keepAlive sessions ≈ 6,000 h ≈ $600 at the Startup overage rate.

### Q7. Steel Cloud on the same rows

See the last two columns of the Q6 table. Rates come from the Steel corpus (`https://steel.dev/pricing.md`, `vendor-claim`; `https://docs.steel.dev/overview/pricinglimits.md`, `official-docs`, both fetched 2026-10-09):
- Launch: $0 + usage; $0.10/h; $10/GB; 10 concurrent; 15-minute sessions; no dedicated IPs.
- Scale: $250 + usage with $100 monthly credit; $0.08/h; $6/GB; 100 concurrent; 1 h sessions; dedicated IPs $5 each.
- Enterprise: custom; 1,000+ concurrent; 24 h sessions; stealth browser.

Qualitative differences that matter more than price:
- **Sticky IP is a product on Steel Cloud and does not exist on Browserbase.** Dedicated IPs are pinnable per session or profile, and the docs name the "impossible traveler problem".
- **Steel Cloud Profiles** have a 300 MB cap and are auto-deleted after 30 idle days. **Browserbase Contexts** have no documented cap and live indefinitely.
- **Max session:** Steel Scale allows 1 h, Browserbase 6 h.
- **Stealth tier:** Steel's "Stealth browser" is Enterprise-only; Browserbase's Verified is Scale-only.
- **CAPTCHA:** Steel charges per solve; Browserbase includes it.
- **Stagehand v4 cache:** none on Steel (Cloud or self-hosted).

### Staleness in an older local tool's Browserbase provider pages (private; paths withheld)

Those files were last touched 2026-06-12.

- The changelog URL `https://docs.browserbase.com/changelog` now returns 404; the changelog is at `https://www.browserbase.com/changelog` (`hands-on` curl 2026-10-09).
- "Stealth browsers: Basic and advanced stealth tiers" is stale. `advancedStealth` is deprecated, and the tiers are now "Basic" (undefined) and **Verified** (Scale, beta).
- "Model Gateway / BYOK: Bring your own LLM keys" mixes up two opposite things. Model Gateway means *no* provider key, billed through Browserbase. BYO key means passing `model_api_key`, which **bypasses** the gateway.
- The audit cites Stagehand **v3** and `env: "BROWSERBASE"`. v4 (current: 4.2.0) replaced that with `browserbase.launch()` / `connect()`.
  - It also removed the local `cacheDir`, so "managed action caching" is now the *only* Stagehand cache, and it is Browserbase-only.
  - The audit does not mention this, though it changes the Steel-vs-Browserbase calculus for Stagehand-first designs.
- Missing from both files:
  - the Agents API (runs, pause/resume 2026-09-24);
  - Search and Fetch APIs; Functions Secrets and Webhooks;
  - named Contexts (2026-08-19);
  - Web Bot Auth;
  - the four regions;
  - **no self-serve sticky IP**, Linux-only non-Verified sessions, no context export;
  - pricing and limits;
  - the ToS clauses.
- The "Browser Use wins anti-bot routing today" and "escalation rank 2" lines are unsourced opinions about a different product (Super Browser routing), not facts about Browserbase.
- The audit's HARD FAIL verdict was about wiring a Super Browser adapter. It does not transfer to the fleet question, which turns on persistence, sticky IP and the cache.

---

## 3. What Browserbase gives us vs what the fleet must build

| Need (from BRIEF) | Browserbase provides | Fleet must build |
| - | - | - |
| Spin up a browser per profile | `sessions.create` with region, timeout, keepAlive; 25/100/250+ concurrency | Session factory and pool, 429 / `retry-after` backoff, creation-rate pacing (50/min on Startup: 1,000 profiles take about 20 min to wake) |
| Human logs in once | Interactive embeddable Live View (`debuggerFullscreenUrl`, `expiresIn`) | Login broker: mint a short-TTL URL, hand it to the human (never to the agent), detect "logged in", then release so the Context persists. Hold a CDP connection or use keepAlive during the login, because sessions end on disconnect (verify on a paid account) |
| Keeps auth and state across closes | Contexts (`persist:true`), encrypted, indefinite | profile_id → context_id registry (there is **no API list**; name each Context after its profile_id so the dashboard can be used for recovery); one-writer lock per Context; post-close settle wait; logged-out detectors and re-login flow; backups are impossible (no export) |
| Same browser every time | Same Context; nothing more | Pin `os` (Verified only) and viewport per profile in the registry; never change them; record and alert on drift |
| Same IP every time | **Nothing** (rotating residential, geo-pinned) | One BYO static or ISP proxy per profile (HTTP/HTTPS, not SOCKS5); proxy health checks; CDP `Emulation.setTimezoneOverride` on every page (and locale, if a later check shows it's needed) |
| Agent does the work | Stagehand v4 native; Browser-Use via CDP; hosted Agents (not a fit) | Hermes skill + System 1 routing; engine choice; per-profile task queue; posting and messaging safety gates |
| Cheap repeat actions | Stagehand server cache (Browserbase only, best effort) | Hit-rate telemetry from `metadata.cache.status`; `cache=False` on credential-bearing calls; a fallback replay cache for Steel-homed profiles |
| Isolation between agents | userMetadata + `q` filter | Fleet-held key; tag every session `{fleet_profile, owner}`; release only sessions you own; never bulk-release |
| Observability | Recordings (HLS/MP4), logs, live view | Turn recordings off by default for client accounts; store our own action log in Obsidian/Hermes memory; opt-in recording for debugging only |
| Cost control | Usage API (`projects.usage`), per-minute billing | Budget guard; orphan reaper keyed on userMetadata; keepAlive TTLs; proxy-byte accounting |

## 4. Operating notes for a Hermes agent (feeds the skills)

1. **Never give a Hermes profile the Browserbase key.**
   - The fleet service holds it and exposes `open_session(profile_id)` / `close_session(profile_id)`.
   - Keys are project/org-wide and `GET /v1/sessions` is account-wide.
2. **Every session gets `userMetadata={"fleet_profile": "<id>", "owner": "<service-instance>"}`.** Values must be strings, and the JSON must stay under 512 characters including Stagehand's own tags.
   - Find your orphans with `q=user_metadata['fleet_profile']:'<id>'` plus `status=RUNNING`.
   - **Never** release sessions you did not tag.
3. **Create call for a profile homed on Browserbase:**
   - `browserSettings.context = {id, persist: true}`;
   - `recordSession: false`, `logSession: false` unless debugging;
   - `proxies = [{type: "external", server, username, password}]` (that profile's sticky proxy);
   - `region` nearest the proxy;
   - `timeout` = task budget in seconds (≤21600);
   - `keepAlive: false` unless a human login or multi-step reconnect needs it.
   - **In the Python SDK use `api_timeout=`; `timeout=` is the HTTP timeout.**
4. **Name every Context after its `profile_id`** (`contexts.create(name=profile_id)`; names are unique per project). The registry is the only API index, and the dashboard is the manual fallback.
5. **One live session per Context.** Take a fleet lock on `context_id` before create and release it only after the session reports `COMPLETED`, plus a few seconds.
   - Unknown: whether a `TIMED_OUT` session persists its Context. Treat it as possibly not, and verify on a paid account.
6. **Use the default browser context and page** (`browser.contexts[0]`). Do not call `newContext()`: cookies and Verified features live in the default one.
7. **With a BYO proxy, set the timezone before navigating:** `Emulation.setTimezoneOverride` on every new page or tab. Browserbase aligns it automatically only for its own proxies.
8. **Stagehand on Browserbase:**
   - Upload the Stagehand extension once per Stagehand version and pass `extension_id`. Otherwise every launch uploads 442 KB, and the extension forces a browser restart.
   - Pass `cache=False` on any call that carries `%variables%` with secrets.
   - Log `result.metadata.cache.status` to measure hit rate.
   - `stagehand.close()` then `browser.close()`. The latter releases the session and triggers the Context save.
9. **Browser-Use on Browserbase:** `Browser(cdp_url=session.connect_url, keep_alive=False)`.
   - `keep_alive` defaults to `None`, so `Agent.run()` stops the browser at the end (`source-code` browser-use@c75e847 `agent/service.py`).
   - Stopping drops CDP, which ends a non-keepAlive Browserbase session and persists the Context.
   - With `keep_alive=True`, `browser.stop()` returns early and the session keeps billing.
10. **CAPTCHAs:** listen for the console events `browserbase-solving-started` / `browserbase-solving-finished` and pause agent actions in between (up to 30 s).
11. **Human login:**
    - Create the session with `keepAlive:true` and a short `timeout`.
    - Mint the live URL with `expiresIn` of a few minutes and show it to the human only.
    - Poll for a logged-in marker, then `REQUEST_RELEASE`, wait, and mark the profile ready.
    - The Live View does not support mobile keyboards; use desktop.
12. **429s:** honour `retry-after` and pace creation under 50/min on Startup.
13. **Proxy-blocked categories:** Browserbase's residential proxies may not reach webmail (Outlook, Yahoo), banking, .gov and some others. Email-verification steps may need a BYO proxy or no proxy.
14. **Do not use Hermes' built-in Browserbase provider for fleet profiles.** It has no Context support, defaults keepAlive to on, and uses the deprecated `advancedStealth`.
15. **Do not rely on `browserSettings.fingerprint`, `advancedStealth`, `contexts.update`, or the Python SDK repo's stale `https://docs.browserbase.com/reference/api/openapi.v1.yaml`.**

## 5. Risks and unknowns

- **Unknown (needs a paid key):**
  - whether BYO-proxy bytes are billed;
  - whether `fingerprint` is honoured or rejected;
  - whether `timeout: 1800.0` (float) is accepted;
  - whether `TIMED_OUT` sessions persist Contexts;
  - whether a never-attached session stays alive without keepAlive;
  - whether the fingerprint stays stable per Context, with and without Verified;
  - the real Context size ceiling;
  - which CAPTCHA vendors are solved;
  - Stagehand cache hit rate on social feeds and whether our project has the server-side cache flag.
- **Policy risk:**
  - the ToS solicitation and impersonation clauses plus at-will suspension;
  - Browserbase's "identity, not evasion" direction;
  - no public AUP, so terms may tighten.
  - Mitigation: Browserbase is never the only home for a client's login, and every Browserbase profile has a documented re-login path.
- **Lock-in risk:** no Context export and no API list (dashboard only). Losing the account means every Browserbase-homed client must log in again. Losing the registry means a manual dashboard recovery, which works only if Contexts were named after their profile_id.
- **Detection risk:**
  - Linux-only UA below Scale;
  - rotating IPs unless BYO;
  - a timezone mismatch if the CDP override is forgotten;
  - Verified/Web Bot Auth may *announce* automation.
  - None of this is measured. Spikes should use public fingerprint and bot test pages only.
- **Operational risk:**
  - shared-key cross-agent releases (skills#153);
  - orphaned keepAlive sessions billing until timeout;
  - open Stagehand v4-on-Browserbase init bug (stagehand#2782);
  - the 6 h hard session cap.
- **Privacy risk:** recordings (30 d), the cache payload (accessibility tree + variables) and logs leave our control unless disabled. ZDR/BYOS are Enterprise-only.
- **Docs drift:** plan retention numbers disagree; the marketing FAQ claims a UK region that the source does not have; Hermes docs and Hermes code disagree on timeout units; Stagehand docs show `.model_validate` on a TypedDict.

## 6. Sources

Docs corpus (captured 2026-10-09; Mintlify-hosted, so no commit), by vendor URL:
- `https://docs.browserbase.com/account/billing/plans.md`
- `https://docs.browserbase.com/platform/browser/core-features/{contexts,session-metadata,browser-extensions}.md`
- `https://docs.browserbase.com/platform/identity/{proxies,overview,verified-customization,web-bot-auth,captcha-solving,authentication}.md`
- `https://docs.browserbase.com/platform/browser/long-sessions/{overview,keep-alive,timeouts}.md`
- `https://docs.browserbase.com/platform/browser/observability/{session-live-view,session-replay,recording-downloads}.md`
- `https://docs.browserbase.com/platform/browser/files/{downloads,uploads}.md`
- `https://docs.browserbase.com/platform/browser/security/ip-allowlisting.md`
- `https://docs.browserbase.com/platform/browser/techniques/timezones.md`
- `https://docs.browserbase.com/platform/browser/getting-started/{create-browser-session,using-browser-session,remote-browser-versus-local-browser}.md`
- `https://docs.browserbase.com/optimizations/{concurrency/overview,latency/multi-region,cost/cost-optimization}.md`
- `https://docs.browserbase.com/platform/agents/{overview,how-it-works}.md`
- `https://docs.browserbase.com/platform/model-gateway/overview.md`
- `https://docs.browserbase.com/platform/functions/limits.md`
- `https://docs.browserbase.com/account/enterprise/{zero-data-retention,byos-setup-guide}.md`
- `https://docs.browserbase.com/integrations/{browseruse/python,hermes-agent/setup,hermes-agent/introduction}.md`
- `https://docs.browserbase.com/welcome/what-is-browserbase.md`
- `https://docs.browserbase.com/reference/api/openapi.v1.yaml`
- `https://www.browserbase.com/pricing`, `https://www.browserbase.com/changelog` (vendor-claim)

Source code:
- `bb-sdk-node@adef824c9bc9adaf7217aab980b4a9ca51ce73db` (2026-09-24): `src/resources/sessions/sessions.ts`, `src/resources/contexts.ts`, `src/resources/extensions.ts`, `api.md`
- `bb-sdk-python@b3d67ac84d8c5f9d79b4b8dfac3140bd4736eada` (installed as `browserbase==1.20.0`)
- `stagehand@1fc884992b68a0196ea5c6e96cc29924b0922ef4` (2026-10-09):
  - `packages/docs/v4/{configuration/browser.mdx, configuration/models.mdx, best-practices/caching.mdx, best-practices/user-data.mdx, migrations/v3.mdx}`
  - `packages/extension/{services/cacheService.ts, clients/stagehandApi.ts, clients/cacheClient.ts}`
  - `packages/protocol/schemas.ts`
- stagehand Python `4.2.0` installed package (`<scratch>/py/.venv/.../stagehand/{browser.py,browserbase_session.py,_generated/input_types.py}`)
- `browser-use@c75e8476e26d18b7617643bc2ae082fae8eae431` (`browser_use/browser/session.py`); installed 0.13.11
- `NousResearch/hermes-agent@5ba559c9e4b1c8397df7788e319ab634144ca728` (2026-10-10T02:58Z): `plugins/browser/browserbase/provider.py` (copy at `<scratch>/spikes/browserbase/hermes-bb-provider.py`)

Web (fetched 2026-10-09):
- https://www.browserbase.com/terms-of-service (Terms of Use, last updated 2025-08-01)
- https://www.browserbase.com/blog/identity (2026-04-06, vendor-claim)
- https://blog.cloudflare.com/signed-agents/ (third-party)
- https://www.browserbase.com/changelog (vendor-claim)

GitHub issues (third-party):
- https://github.com/browserbase/skills/issues/153 (2026-08-22)
- https://github.com/browserbase/stagehand/issues/2782 (2026-08-20)
- https://github.com/browserbase/sdk-node/issues/183 (2026-05-06)
- https://github.com/browserbase/mcp-server-browserbase/issues/187 (2026-06-04)
- https://github.com/browserbase/sdk-node/issues/214 (2026-08-24)

Steel comparison (`fleet/research/corpus/steel/`):
- `https://steel.dev/pricing.md`
- `https://docs.steel.dev/overview/pricinglimits.md`
- `https://docs.steel.dev/overview/sessions-api/dedicated-ips.md`
- `INDEX.md` (profiles: 300 MB cap and 30-day idle delete; self-hosted capabilities)

Prior internal docs reviewed:
- An older local tool's Browserbase provider page and capability audit (private; paths and commits withheld; 2026-06-12)

Spikes: `fleet/research/spikes/browserbase/{offline_request_shapes.py, offline_stagehand_launch.py, cost_model.py, RESULTS.md, out_*.txt}`.
