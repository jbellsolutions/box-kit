# Browserbase: the fleet's opt-in paid home

Status: design target. **Nothing here is built.** No Browserbase account or key exists, so nothing below was run against the live API. What exists is docs, SDK source and offline request-shape spikes (`fleet/research/spikes/browserbase/RESULTS.md`).

How to read this guide:

- It follows [DECISIONS.md](../../DECISIONS.md) (D3, D6, D10, D11, D12, D14). Where a dossier and its verification report disagree, the verification report wins. Corrections that matter are listed in section 1.
- Tags: `official-docs`, `source-code`, `vendor-claim`, `third-party`, `hands-on` (offline request shapes only), `inference` (my reasoning from cited evidence), `estimate`, `to measure`, `unbuilt`.
- Browserbase docs pages are cited by their vendor URL (captured 2026-10-09; the scraped copy is not published). "Corpus" below means that capture. Index: section 14.
- Items waiting on Justin are marked **[pending Q-nn]** with the number from the end of DECISIONS.md. Until he answers, the recommended default applies.
- Vocabulary (identity, wake, sleep, fleetd, lease) is DECISIONS.md's.
- Stress-test findings applied in this revision: `fleet/research/scenarios/S10.md` (G10-1 triage, G10-8 Live View link, G10-9 evidence rule, G10-14 checklist) and `S12.md` (G12-12 human sessions and watching). They are in sections 3.7, 3.9, 8.1 and 8.2.

---

## 1. What this is, and what changed from the dossier

Browserbase rents out cloud browsers. You call its REST API, you get a CDP websocket, and Chromium runs on Browserbase's machines (`https://docs.browserbase.com/platform/browser/getting-started/create-browser-session.md`).

In the fleet it is one of two homes an identity can be created on:

| Home | Role | Chosen |
|---|---|---|
| `steel-oss` | Default. Self-hosted Steel on our droplets (D4). | Every identity unless a reason below applies. |
| `browserbase` | Paid, opt-in. | At identity creation, for a measured reason that passed triage: a functional failure on Steel, never a block or a restriction (section 8.1). Never changed afterwards. |

Moving an identity between homes is not a move. It is a new identity and a fresh human login (D3; `fleet/research/verification/browserbase.md` BB-3).

Four facts shape everything below:

1. **No sticky IP of its own.** Built-in proxies rotate, and Browserbase's own blog recommends static IPs for logged-in sessions. Every fleet identity brings its own static ISP proxy (BB-1).
2. **No fingerprint pin.** Without Verified (Scale plan, beta) a session is always Linux. No API ties a fingerprint to a Context (BB-2).
3. **Contexts hold the login, and the API cannot export them.** Suspension voids all of them (BB-3).
4. **Stagehand v4's cache exists only here, and it is a weak reason to choose it.** The key includes page content, and a hit-count threshold applies (BB-4, V-1).

### Corrections applied (verification wins over the dossier)

| Dossier said | Verified position used here | Source |
|---|---|---|
| $18 / $54 per profile-month, $539 / $53,999 | Dropped. Rests on an unsourced 50 MB per browser-hour and on rotating proxies identities cannot use. Use D12's Browserbase column. | BB-10 |
| Built-in proxies rotate "per session" | The vendor says they rotate, and may rotate within a session. Unfit for logged-in identities either way. | BB-1, missed issue 1 |
| "No scoped keys" | Keys are per project (Developer up to 2 projects, Startup up to 5). Per-agent keys do not exist. "Account-wide listing" is unverifiable without a key. | BB-7, missed issue 5 |
| "No export, backups impossible" | Self-serve API: no list, export or upload. The dashboard lists Contexts. Enterprise BYOS writes Context files to your own S3. A CDP snapshot of cookies and localStorage is a partial backup. | BB-3, missed issue 9 |
| keepAlive: no / yes / yes / yes by plan | The plan gate is contradictory across three sources. Not tabled as a fact. | V-3 |
| Example sets `solve_captchas: True` | Fleet sets `solveCaptchas: false`. D14: agents never solve CAPTCHAs on client accounts. | D14 |
| Example uses `model=..., model_api_key=..., cache=True` | Model call goes through the fleet's own callback. Server cache off by default. | D6, D11 |
| `browser.close()` ends the Stagehand session only | It releases the Browserbase session, even with `keep_alive=True`. | BB-9 |
| "Identity, not evasion" positioning | Mixed. The same-day pricing page still sells "Stealth Mode: Advanced". | V-2 |
| Hermes sends `advancedStealth` by default | It is an opt-in env knob that sends a deprecated flag. | BB-5 |
| Marketing FAQ lists a UK region | Source lists four regions. | `fleet/research/dossiers/browserbase.md` Q1 |

---

## 2. Product surface the fleet uses

### 2.1 Stance on every feature

| Feature | Fleet stance |
|---|---|
| Sessions (REST create / release) | Use. Only fleetd calls it. |
| Contexts | Use. Exactly one per identity. |
| `keepAlive` | Not the default. fleetd holds its own "anchor" CDP connection on every working and login session instead (3.8). keepAlive only after it is verified on the real plan (2.3). |
| BYO proxy (`type: "external"`) | Required on every identity. |
| Built-in proxies (`proxies: true`, `type: "browserbase"`) | Never for an identity. |
| Verified, `os` | Off. Scale only. Closed while Q-04 is at its default, and never an answer to a block (section 8.1, R4). |
| `advancedStealth`, `fingerprint` | Never. Deprecated and undocumented. |
| CAPTCHA solving | Off. A CAPTCHA pauses the identity (`checkpoint`). |
| Live View | Use, for human login and takeover only. Minted after operator authentication, short `expiresIn`, never shown to an agent (3.7). Never a watch mode (3.9). |
| Recording, session logs | Off. |
| Regions | Use. Pinned per identity. |
| Extensions | One: Stagehand's own. |
| Web Bot Auth | Not used. |
| `allowedDomains` | Optional extra layer. `to measure`. |
| Model Gateway, hosted Stagehand cache | Gateway: never. Cache: off by default. |
| Agents, Functions, Search, Fetch | Never. They replace Hermes and System 1 routing. |
| `userMetadata` tags | Required on every session. |

### 2.2 Sessions

- `POST /v1/sessions` returns `id`, `connectUrl` (CDP websocket), `seleniumRemoteUrl` and `signingKey`. Statuses: `PENDING`, `RUNNING`, `ERROR`, `TIMED_OUT`, `COMPLETED`. End a session with `POST /v1/sessions/{id}` and `{"status":"REQUEST_RELEASE"}` (`official-docs` `https://docs.browserbase.com/platform/browser/long-sessions/keep-alive.md`; `source-code` `bb-sdk-node@adef824 src/resources/sessions/sessions.ts`).
- Create parameters the fleet cares about: `projectId`, `region`, `timeout`, `keepAlive`, `proxies`, `extensionId`, `userMetadata`, and `browserSettings{context, recordSession, logSession, solveCaptchas, viewport, verified, os, allowedDomains, blockAds, ...}` (`source-code`).
- Billing is per minute, with a one-minute minimum per session (`https://docs.browserbase.com/account/billing/plans.md`).
- Without keepAlive, **a session ends when its CDP client disconnects**.
- Hard maximum session length is 6 hours (`https://docs.browserbase.com/platform/browser/long-sessions/timeouts.md`). A longer job is split across sessions. The Context carries the login between them.
- `GET /v1/sessions` filters only by `q` and `status`. Tags are queried as `user_metadata['fleet_profile']:'<id>'` (`https://docs.browserbase.com/platform/browser/core-features/session-metadata.md`).
- `userMetadata` must stay under 512 characters, with string values for querying. Stagehand adds about 90 characters of its own tags when it creates a session (`hands-on` offline, `fleet/research/spikes/browserbase/RESULTS.md` spike 2).

### 2.3 Contexts, keepAlive and timeouts

**Contexts.**
- A Context stores the Chromium user-data dir: cookies, localStorage, IndexedDB, sessionStorage, service workers, autofill data and preferences. It does not store the HTTP cache. It is encrypted at rest and "live[s] indefinitely" (`https://docs.browserbase.com/platform/browser/core-features/contexts.md`).
- `persist: true` saves changes **when the session closes**. The docs say to "wait a few seconds before reusing the Context". `persist: false` is read-only.
- The docs warn against two sessions on one Context at once ("sites may force a log out"), and advise one Context per site per login. An identity is one client account, so one Context per identity fits.
- Contexts become invalid on explicit delete, project delete, or account suspension or deletion.
- Names are unique per project, case-insensitive. The dashboard lists Contexts by name (`vendor-claim` `https://www.browserbase.com/changelog`, 2026-08-19).
- API: create, get, delete. **No list, no export, no upload** (`PUT /v1/contexts/{id}` is `@deprecated`; `uploadUrl` is a "non-functional sentinel"). Section 5 covers what that means.
- No size or count limit is documented. The docs only say large Contexts slow sessions.
- The Context does not exclude a second writer. Exclusion is fleetd's lease (D12).

**keepAlive.**
- Docs: "Session keep alive is only available on paid plans." Node SDK comment: "Hobby Plan and above" (a legacy plan name). Stagehand docs: "Available on Startup plan" (`https://docs.browserbase.com/platform/browser/long-sessions/keep-alive.md`; `https://docs.stagehand.dev/v4/configuration/browser.md` line 380). `plans.md` has no keepAlive row.
- So the gate is unknown. **Verify on the real plan before relying on it** (V-3). The $20 Developer plan may not allow it.
- keepAlive sessions bill until released or timed out.

**Timeouts.**
- `timeout` is an integer in seconds, 60 to 21,600.
- Whether a `TIMED_OUT` session still saves its Context is unknown. The fleet never relies on a timeout to end a session. It releases first.
- After any session that did not end with a clean `COMPLETED`, the next wake runs the login probe before anything else. A failed probe is `needs_reauth`, not a fleet fault.

### 2.4 Proxies

- Built-in: `proxies: true` is a managed residential proxy, "best-effort" US. Geolocation (country, US state, city) is best effort. Browserbase's own docs describe it as "Rotate residential proxies" (`https://docs.browserbase.com/platform/identity/authentication.md`), and its 2026-09-01 blog says it "assign[s] and rotate[s] the IP" and recommends static proxies for logged-in sessions (`vendor-claim`, BB-1).
- **No documented sticky, static or dedicated IP.** The proxies overview says "consistent IP addresses across sessions", but no parameter implements it. The corpus and SDK source have zero hits for sticky, static or dedicated (`corpus/INDEX.md`, Proxies).
- BYO: `{type:"external", server, username?, password?, domainPattern?}`. HTTP or HTTPS only; "Socks5 proxies are not supported" (`https://docs.browserbase.com/platform/browser/security/ip-allowlisting.md`). Allowed on Developer and above (`proxies.md` line 779).
- Rules apply in order, first match wins. `{type:"none", domainPattern}` bypasses the proxy for matching domains.
- `proxySettings.caCertificates` is for TLS-intercepting proxies. It is not a sticky-IP setting.
- Unknown: whether bytes through an `external` proxy are counted in Browserbase's per-GB proxy billing. The docs never say. (section 9, section 12)
- **Fleet rule:** one rule, `type: "external"`, no `domainPattern`, so all traffic uses the identity's IP. Never add a `type: "none"` rule: it would expose a Browserbase datacenter IP to those domains.

### 2.5 Stealth tiers and Verified

- Non-Verified: always Linux. Passing `os` without Verified is an error. The only documented stealth is "automatic fingerprinting (devices, locales, operating systems)", with no detail. The plans page calls the paid tiers "Basic" and never defines it (`https://docs.browserbase.com/platform/identity/verified-customization.md`, `plans.md`).
- `advancedStealth` is deprecated in source ("use `verified` instead").
- **Verified**: purpose-built Chromium with real pre-made fingerprints. `os` can be windows (default), mac, linux, mobile or tablet. Viewport is fixed. "Currently in beta." **Scale plan only**, custom pricing. Docs warn: "When using contexts, changing the OS could reduce the success rate."
- No fingerprint ID, seed or per-Context pin exists. The `browserSettings.fingerprint` field appears in Stagehand's types and the stale Python repo spec, not in either SDK's source or the docs spec. The Python SDK passes it through unvalidated. The server's reaction is unknown. Do not use it (BB-2).
- Non-Verified sessions get Browserbase's own "automatic fingerprinting". Whether a plain session already presents altered device, locale or OS values is unknown (`to measure`). That matters for D9 and Q-04.
- What the fleet can pin on this home: **viewport** (non-Verified only), **region**, **timezone** (a CDP override), and the **proxy IP**. It cannot pin the UA, the OS, the locale, or the fingerprint. D3's persona is narrower here than on Steel (section 3.6).
- Web Bot Auth (beta, request access) signs requests so participating sites can verify an agent. "A valid signature doesn't grant access or sign your agent into a user account." Meta, TikTok and X are not documented partners. It announces automation, so the fleet does not use it (`https://docs.browserbase.com/platform/identity/web-bot-auth.md`; `inference`).

### 2.6 CAPTCHA

- "Browserbase enables CAPTCHA solving by default for all sessions." Turn it off with `browserSettings.solveCaptchas: false` (`https://docs.browserbase.com/platform/identity/captcha-solving.md`).
- Solving takes up to about 30 s and emits console events `browserbase-solving-started` and `browserbase-solving-finished`.
- The docs: "Use CAPTCHA solving only for workflows that users and website owners authorize."
- **Fleet:** `solveCaptchas: false` on every session. A CAPTCHA, login wall, 2FA prompt or checkpoint pauses the identity and notifies the owner with a fresh Live View link (D14). Which challenge vendors Browserbase solves is undocumented, so it is not a reason to choose this home.

### 2.7 Live View (human login)

- `GET /v1/sessions/{id}/debug?expiresIn=<60..21600>` returns `debuggerFullscreenUrl`, `debuggerUrl`, `wsUrl` and a `pages[]` list with one URL per tab. If `expiresIn` is omitted the URLs last as long as the session (`https://docs.browserbase.com/reference/api/session-live-urls.md`).
- It is interactive ("watch, click, type, and scroll") and can be embedded in an iframe: read/write with `sandbox="allow-same-origin allow-scripts"`, read-only by adding `pointer-events: none`. `&navbar=false` hides the navbar. When the session ends the iframe posts `browserbase-disconnected` (`https://docs.browserbase.com/platform/browser/observability/session-live-view.md`).
- Mobile keyboards are "not officially supported". Use desktop.
- The docs name "delegate credentials - give control to the end user" and recommend logging in once through Live View, then persisting with a Context (`https://docs.browserbase.com/platform/identity/authentication.md`).
- `inference`: the URL looks like a bearer capability, since no API key is involved in viewing it. Treat it like a password. The same goes for `debuggerUrl`, `wsUrl` and every per-tab URL in `pages[]`.
- `expiresIn` is an integer from 60 to 21,600 seconds. "If omitted, the URLs expire with the session" (`https://docs.browserbase.com/reference/api/session-live-urls.md`). The fleet always sends it (3.7).
- **Read-only is the embedder's job, not the product's.** The docs' read-only snippet is the same iframe with `pointer-events: none`. The URL itself is read/write. The fleet therefore has no watch-only mode on this home (3.9).
- A human session and an agent session are never the same session here (3.9).
- Untested, as on Steel (D4): Enter, Backspace, Tab, arrows, IME, passkeys, native dialogs, HTTP auth and file pickers through the viewer. Section 12 lists it.

### 2.8 Recordings and logs

- Recording is **on by default** (`recordSession`). HLS replay per tab (up to 10 tabs), MP4 downloads after the session, retained up to 30 days (24 h on BYOS projects). Sessions created with `recordSession: false` "produce no replay"; Live View still works (`https://docs.browserbase.com/platform/browser/observability/session-replay.md`).
- Browserbase's terms say that by using recording "you authorize us to store the recordings for 30 days" and that you must display a persistent recording label to the user (section 6).
- **Fleet:** `recordSession: false` and `logSession: false` on every client-account session. Recording is a debugging opt-in on a throwaway identity only. **[pending Q-07]**

### 2.9 Regions

- `us-west-2` (default), `us-east-1`, `eu-central-1`, `ap-southeast-1` (`source-code` region enum; `https://docs.browserbase.com/optimizations/latency/multi-region.md`). The marketing page also mentions a UK region and "APAC upon request". They are not in source or docs. Source wins: four regions.
- With a BYO proxy, the region does not set the exit IP. The proxy does. The region affects latency to the proxy and to the platform.
- **Fleet:** choose the region nearest the proxy exit at creation and pin it. A region change is a persona change, so it is a new identity (D3, `inference`).

### 2.10 Uploads, downloads, extensions

- Uploads: Playwright `setInputFiles`, or `POST /v1/sessions/{id}/uploads` for large files. Downloads sync to Browserbase storage and list at `GET /v1/sessions/{id}/downloads` (`https://docs.browserbase.com/platform/browser/files/`).
- Extensions: upload a `.zip` (at most 100 MB, `manifest.json` at the root), then pass **one** `extensionId` at create. An extension restarts the browser and adds creation time (`https://docs.browserbase.com/platform/browser/core-features/browser-extensions.md`).
- Downloaded and uploaded files are client content sitting in Browserbase storage. Treat them like Context data. **[pending Q-07]**

### 2.11 `allowedDomains` (optional)

- `browserSettings.allowedDomains` blocks top-level navigations to domains not on the list. It is "experimental" (`https://docs.browserbase.com/platform/browser/security/allowed-domains.md`).
- Possible use: restrict an identity to its platform's domains. It covers top-level navigation only, so it is not a security boundary. `to measure`. Not in the v0 create shape.

---

## 3. Session shapes for a fleet identity

All of these are `unbuilt`. The request shapes were checked offline against the Browserbase Python SDK 1.20.0 and Stagehand 4.2.0 with a mocked HTTP layer (`hands-on`, RESULTS.md spike 1 and 2). The server's replies were never observed.

### 3.1 The lifecycle

| Step | Who | What happens on Browserbase |
|---|---|---|
| Create identity | Owner | `POST /v1/contexts` with `name` = identity id. fleetd stores `contextId`, `projectId`, region, viewport, timezone, proxy reference and the reason for this home. |
| First login | Human, through fleetd | Create a session with `persist: true`. fleetd holds its **anchor** CDP connection so the session survives (3.8). The operator opens a fleetd ticket and authenticates (AQ-1). Only then fleetd mints a Live View URL (3.7). Human logs in. Login probe passes. Release. Wait. Mark ready. |
| Wake | fleetd | Take the identity lease (D12). Check no tagged session is still `RUNNING` for this identity. Create the session (3.2). Open the anchor (3.8). Attach the engine (section 4). Run the IP and timezone checks (3.5, 3.6). Run the login probe. |
| Work | Engine | Stagehand or Browser-Use over CDP, on top of the anchor. The D13 effect rules apply unchanged. |
| Sleep | fleetd | The engine detaches. With the anchor still connected: any D13 read-back, then the optional cookie and localStorage snapshot (section 5). Then `REQUEST_RELEASE`, wrapped (it can error if the session is already `COMPLETED`). Wait for `COMPLETED`, then a settle hold. Release the lease. |
| Reap | fleetd | Release only sessions whose `fleet` tag is this fleet's stable id (3.2) and that outlive their lease. The tag is stable on purpose: a restarted fleetd instance must still match the orphans it needs to reap. Never release an untagged session. Never bulk-release. |

The settle hold after release: the docs say "a few seconds". Start with 10 s (`estimate`) and measure.

Never call a bulk "release all RUNNING". `GET /v1/sessions` is not filterable by project, and a bulk release killed other agents' sessions in a documented incident (`third-party` browserbase/skills#153; `source-code` `SessionListParams`; BB-7).

### 3.2 Raw HTTP: a working session for one identity

```http
POST https://api.browserbase.com/v1/sessions
X-BB-API-Key: <fleet-held key; never in a Hermes profile>
Content-Type: application/json

{
  "projectId": "<project for this client group>",
  "region": "us-east-1",
  "timeout": 1800,
  "keepAlive": false,
  "proxies": [
    {
      "type": "external",
      "server": "http://<this identity's static ISP proxy host>:<port>",
      "username": "<credential scoped to this one IP>",
      "password": "<...>"
    }
  ],
  "browserSettings": {
    "context": { "id": "<contextId>", "persist": true },
    "recordSession": false,
    "logSession": false,
    "solveCaptchas": false,
    "viewport": { "width": 1280, "height": 720 }
  },
  "userMetadata": {
    "fleet": "<stable id of this fleet deployment>",
    "fleet_profile": "<identity_id>",
    "instance": "<fleetd instance id>"
  }
}
```

Field notes:

| Field | Value | Why |
|---|---|---|
| `projectId` | The project for this client group | Optional (the key resolves its project). Sent so the project is explicit. Projects give coarse isolation: up to 2 on Developer, 5 on Startup (BB-7). |
| `region` | Nearest the proxy | Section 2.9. Pinned. |
| `timeout` | Task budget in seconds, 60 to 21,600, **an integer** | The spec says integer. The Stagehand launch path sends `1800.0` (a float). Whether the server accepts a float is unknown. Send an integer from the fleet's own factory. |
| `keepAlive` | `false` | Section 2.3. |
| `proxies` | One `external` rule, no `domainPattern` | Section 2.4. Use a credential scoped to this single IP, not the proxy account's master login: Browserbase's browser needs it to connect. |
| `context.persist` | `true` | Saves login changes when the session closes. |
| `recordSession`, `logSession` | `false` | Section 2.8. |
| `solveCaptchas` | `false` | Section 2.6. On by default, so it must be sent. |
| `viewport` | The identity's pinned value | Allowed only without Verified. |
| `userMetadata` | Opaque ids only: `fleet` (stable id of this deployment), `fleet_profile` (identity id), `instance` (this fleetd process) | At most 512 characters, including Stagehand's own tags. No client names, no PII. The reaper matches on `fleet`, never on `instance`, so a restart does not hide orphans. |

Never sent: `proxies: true`, `type: "browserbase"`, `advancedStealth`, `fingerprint`, `os`, `verified`, any `extensionId` except Stagehand's own, and `keepAlive: true` except the login case.

### 3.3 Python (`browserbase==1.20.0`)

```python
from browserbase import Browserbase

bb = Browserbase(api_key=BB_KEY)            # fleetd process only

session = bb.sessions.create(
    project_id=PROJECT_ID,
    region=ident.region,
    api_timeout=ident.budget_seconds,       # session lifetime, seconds.
                                            # NOT timeout=: that is the HTTP client timeout.
    keep_alive=False,
    proxies=[{
        "type": "external",
        "server": ident.proxy_server,       # "http://host:port"
        "username": ident.proxy_user,
        "password": ident.proxy_password,
    }],
    browser_settings={
        "context": {"id": ident.context_id, "persist": True},
        "record_session": False,
        "log_session": False,
        "solve_captchas": False,
        "viewport": {"width": ident.viewport_w, "height": ident.viewport_h},
    },
    user_metadata={"fleet": FLEET_ID, "fleet_profile": ident.id, "instance": FLEETD_ID},
    # extension_id=STAGEHAND_EXT_ID,        # only when a Stagehand run needs it (section 4)
)
# session.id, session.connect_url

# sleep (wrapped: the call can error if the session already reached COMPLETED):
try:
    bb.sessions.update(session.id, status="REQUEST_RELEASE")
except Exception:
    if bb.sessions.retrieve(session.id).status not in ("COMPLETED", "TIMED_OUT", "ERROR"):
        raise
```

The SDK converts snake_case to camelCase on the wire (`hands-on`, RESULTS.md spike 1).

### 3.4 Node (`@browserbasehq/sdk` 2.21.0)

```ts
import { Browserbase } from "@browserbasehq/sdk";

const bb = new Browserbase({ apiKey: process.env.BROWSERBASE_API_KEY! }); // fleetd only

const session = await bb.sessions.create({
  projectId: PROJECT_ID,
  region: ident.region,
  timeout: ident.budgetSeconds,
  keepAlive: false,
  proxies: [{
    type: "external",
    server: ident.proxyServer,
    username: ident.proxyUser,
    password: ident.proxyPassword,
  }],
  browserSettings: {
    context: { id: ident.contextId, persist: true },
    recordSession: false,
    logSession: false,
    solveCaptchas: false,
    viewport: { width: ident.viewportW, height: ident.viewportH },
  },
  userMetadata: { fleet: FLEET_ID, fleet_profile: ident.id, instance: FLEETD_ID },
});

// sleep (wrapped like the Python version: it can error if already COMPLETED):
try {
  await bb.sessions.update(session.id, { status: "REQUEST_RELEASE" });
} catch (err) {
  const { status } = await bb.sessions.retrieve(session.id);
  if (!["COMPLETED", "TIMED_OUT", "ERROR"].includes(status)) throw err;
}
```

### 3.5 Timezone: override over CDP, then check

With a BYO proxy, Browserbase does not align the timezone. The docs only promise that for its own proxies. Otherwise: "override the existing page through CDP before navigating", and "The override applies per page. Set it before navigation for each new page or tab" (`https://docs.browserbase.com/platform/browser/techniques/timezones.md`). The docs never mention `type: "external"`, so "BYO loses the alignment" is an inference from silence (BB-8).

```python
# Playwright over CDP. Use the DEFAULT context, never new_context().
# The docs say Verified features and the recording rely on it.
browser = await pw.chromium.connect_over_cdp(session.connect_url)
context = browser.contexts[0]
keep = []                       # CDP sessions held for the life of their pages

async def pin_tz(page):
    cdp = await context.new_cdp_session(page)
    await cdp.send("Emulation.setTimezoneOverride", {"timezoneId": ident.timezone})
    keep.append(cdp)            # hold the CDP session for the page's life (see below)

for page in context.pages:
    await pin_tz(page)
context.on("page", lambda p: asyncio.create_task(pin_tz(p)))
```

Call is not enough. **The fleet needs a check:**

- Before each step, and after every new tab, popup, CDP reconnect and Live View handoff, run `Intl.DateTimeFormat().resolvedOptions().timeZone` in the page and compare with `ident.timezone`.
- A mismatch stops the session. D3: "A mismatch refuses the wake or stops the session."
- Why: CDP emulation lasts only as long as the DevTools session that set it, so reconnects, tabs opened by the engine, workers and the Live View handoff may show the datacenter timezone (`inference`, BB-8 and verification missed issue 10). None of this is measured. It is in the smoke test (section 15).
- Stagehand and Browser-Use open their own CDP sessions. The adapter that attaches them is the one that installs the override and runs the check. `to measure`.

The timezone value comes from the identity record, matched at creation to the proxy IP's location (D10).

### 3.6 Keeping the IP and persona pinned: what Browserbase cannot do

Two gaps in DECISIONS.md show up here. I found them while writing this guide.

**Gap 1: the credential-less forwarder (D10) cannot sit in the path.** On Steel the browser's only egress is a node-local forwarder that holds no credentials and "fails closed on any exit-IP change, mid-session included". On Browserbase the browser runs in their cloud. The proxy host, username and password go to Browserbase in the create body, and Browserbase's browser connects to the proxy directly. There is no node of ours to kill.

What replaces it, in order of strength:

| Control | What it does | Status |
|---|---|---|
| Wake-time exit-IP check | Load a fleet-run IP-echo URL (not a third party) in a page. The seen address must equal the pinned IP. Repeat before every irreversible effect (D13) and on a timer. | `unbuilt`; leaves a window between checks. |
| Provider kill switch | Use a proxy product whose session drops instead of swapping the IP (D10: IPRoyal sticky sessions swap silently unless `_killswitch-1` is set). Whether Browserbase surfaces a drop as a failed navigation and not a leak is `to measure`. | `unbuilt`. |
| Scoped proxy credential | One credential per IP. A leak at Browserbase exposes one IP, not the account. | Rule. |
| WebRTC / DNS leak check | Load a public leak-test page once per wake. Steel pins WebRTC to `disable_non_proxied_udp`. Browserbase documents nothing on it. | `to measure`. |
| **Option F: fleet-run edge forwarder** | The session's `external` proxy points at a forwarder we run on a public host. It holds the ISP credentials, accepts a short-lived per-session credential, and kills the connection if the upstream exit IP changes. Restores fail-closed. Costs an extra hop and a public service to defend. | Design option. `unbuilt`. |

Default for v0: the first three controls. Option F is the upgrade if the first wake-time and mid-session checks show swaps or leaks. **Open item BB-O1: Justin decides whether the extra hop is worth it.** It is not among his questions in DECISIONS.md.

**Gap 2: the persona pin (D3) is partly unachievable here.**

| Persona value | Steel (D3, D4) | Browserbase |
|---|---|---|
| User agent | Pinned through session fields | Not pinnable. Linux, chosen by Browserbase's "automatic fingerprinting". Windows or Mac only with Verified (Scale). |
| Timezone | Session field plus `TZ` | CDP override. Fragile. Needs the check in 3.5. |
| Locale | `LANG`, `--accept-lang` | No documented knob. `to measure`. |
| Viewport | Session field | `browserSettings.viewport`, non-Verified only. |
| Hardware values (cores, GPU, canvas) | Host-real, identical on a node | Unknown. Browserbase's choice. |

Consequence for Q-13 (cross-client unlinkability): **it cannot be assessed on this home** without hands-on. Do not tell a client that Browserbase-homed identities are unlinkable. **[pending Q-13]**

D4's Guard (browser-box's in-browser CDP guard) on a remote Browserbase CDP connection is unmeasured. Its main purpose (stopping a page from reading Steel's own API on loopback) does not seem to apply to Browserbase, which exposes no such local service to a page (`inference`). Whether it is still wanted for other reasons is open. Q-08 (Steel's root/no-sandbox Chromium) does not apply to this home. Browserbase runs the browser, and its sandboxing is theirs.

### 3.7 Human login on Browserbase

**Who gets which link.**

- A tool result carries only a **fleetd ticket URL** (`fleet/ARCHITECTURE.md` §4.8 step 2: 256-bit, hashed, single use, bound to `(identity, purpose, lease token)`). That URL grants nothing by itself.
- The **Browserbase Live View URL is never in a tool result.** fleetd mints it server-side, only after the operator has opened the ticket and authenticated, and puts it on a fleetd page for that operator. It is never shown to an agent, never put in an agent's context, and never written to a log.
- ARCHITECTURE §4.8 step 2 and §5.3 (`identity_control reauth`) say the agent receives the viewer URL "so it can pass it on". On this home that URL is the fleetd ticket, never the Browserbase URL. ARCHITECTURE should say "fleetd ticket URL" (stress test G10-8, `fleet/research/scenarios/S10.md`).
- **How the operator authenticates is open: AQ-1** (`fleet/ARCHITECTURE.md` §9.4; not among Justin's 14). **It blocks the Browserbase onboarding flow** (8.2 item 10), because the first login needs this link.

**Flow.**

1. fleetd creates a session as in 3.2, with `persist: true`. It holds its anchor connection (3.8) to keep the session alive. If keepAlive is verified on the plan, it may use `keepAlive: true` with a short `timeout` instead.
2. fleetd issues a **ticket**. The operator opens it and authenticates (AQ-1).
3. Only then, fleetd calls `GET /v1/sessions/{id}/debug?expiresIn=<N>` (Node `bb.sessions.debug(id, { expiresIn })`, Python `expires_in=`; `source-code` `bb-sdk-node@adef824`, `bb-sdk-python@b3d67ac`), embeds the result in the operator's page, and discards the rest.
4. The human holds the identity lease. The engine adapter sends no commands while the human drives. Browserbase does not enforce this. fleetd does (3.9).
5. fleetd polls a logged-in marker (the per-site login probe, D14). If the human needs longer, fleetd repeats steps 2-3 with the lease and authentication re-checked. It does not extend an old URL.
6. fleetd takes the optional snapshot, calls `REQUEST_RELEASE`, waits for `COMPLETED`, holds for the settle time, and marks the identity ready.
7. On the next wake, the login probe confirms the Context really carried the login.

Mid-login, the engines never call `browser.close()`: for Stagehand it releases the session (section 4.2).

**Live View URL rules.** The URL is a bearer capability: no API key is involved in viewing it (`inference`, 2.7).

| Rule | Detail |
|---|---|
| Mint late | After the operator authenticates, while that operator holds the lease, never earlier. Not at ticket creation, not at wake. |
| Always send `expiresIn` | If it is omitted, "the URLs expire with the session, up to a maximum of 21600 seconds (6 hours)" (`https://docs.browserbase.com/reference/api/session-live-urls.md`). That is long enough to outlive a lease. |
| `expiresIn` value | The shorter of the **remaining human lease** and a policy cap (the cap is `to measure`; the ticket TTL of 15 minutes in ARCHITECTURE §4.8 is an estimate). The API floor is **60 s**. If the remaining lease is under 60 s, the operator renews the lease first or fleetd refuses to mint. |
| One URL per handoff, never reused | A re-mint, a new handoff and a new operator each get a fresh call that re-checks authentication and the lease. The API returns a URL per tab (`pages[]`), plus `debuggerUrl` and `wsUrl`. They are all capabilities. Use the one needed, keep it in memory, discard the rest. |
| Never logged, never stored | Not in a log, a trace, a job record, an evidence file, a note or an error message. The audit trail records operator, start, end and ticket id (ARCHITECTURE §4.8 step 9), not the URL. |
| Revocation is the session | The corpus documents no call that revokes a Live View URL. The only way to kill one before `expiresIn` is to end the session with `REQUEST_RELEASE`. So when the lease ends early (operator done, lease lost, ticket revoked), release the session at once. |
| The operator's browser sees it | It is the iframe `src`. That is accepted. The controls are authentication first, short life, one URL per handoff and release at lease end. Whether fleetd can reverse-proxy Live View so the URL never reaches the operator's browser is `to measure` (section 12). |

### 3.8 Session lifetime: the anchor connection

Without keepAlive, "a session ends when its CDP client disconnects" (`https://docs.browserbase.com/platform/browser/long-sessions/keep-alive.md`). Engines disconnect when they finish or crash. The fleet still needs the session after that, for the cookie snapshot (section 5), for D13 read-back receipts after an effect, and for Live View handoffs.

**Design rule: fleetd opens its own CDP connection (the "anchor") to every working session and holds it until fleetd itself decides to end the session.**

- The anchor sends no commands. It only holds the websocket.
- Engines attach and detach on top of it. Browser-Use runs with its own `keep_alive=True`, so it does not stop the browser (4.4). Stagehand's `stagehand.close()` ends only its own RPC (4.2).
- fleetd then does read-back, the snapshot and the wrapped `REQUEST_RELEASE`.
- If fleetd crashes, the anchor drops. The reaper (3.1) releases what is left.

**Unknown, `to measure`:** whether Browserbase keeps a non-keepAlive session alive while one CDP client drops and another stays connected. The keep-alive page lists "multiple connections" only as a benefit of keepAlive. If the anchor is not enough, there are two fallbacks:

1. Use keepAlive, on a plan where it is verified, with a short `timeout`.
2. Run read-back and the snapshot inside the engine adapter, over the engine's own single connection, before it disconnects. Accept that the disconnect ends the session. The Context saves at close.

### 3.9 Human sessions, fencing and watching on this home

What follows is `design`, `unbuilt`, and none of it has run. It states what this home cannot do. On Steel, the node agent kills agent workers on a takeover (`fleet/ARCHITECTURE.md` §3.5), and a watch-only ticket has been proposed, using Steel's documented `interactive=false` (`fleet/research/scenarios/S12.md` section 6, G12-8). Neither is possible here. Lease and fencing in general are ARCHITECTURE §3.5. This file's §3.5 is the timezone section, so the Browserbase-side statements are in 3.7 and here (stress test G12-12).

**A human session ends the agent's session.**

- There is no node of ours and no way to cut one CDP client of a remote session. The one cut fleetd has is `REQUEST_RELEASE`, and it ends the whole session (ARCHITECTURE §3.5: "weaker fencing").
- So a takeover runs in this order:
  1. fleetd takes the lease (`takeover`, fencing token T+1). The executor checks the token on every command and stops.
  2. fleetd detaches the engine and ends the agent's session as in Sleep (3.1): D13 read-back only if it is safe, the optional snapshot, then the wrapped `REQUEST_RELEASE`.
  3. fleetd waits for `COMPLETED` and the settle hold. **It does not create the human's session before that**, because two sessions on one Context at once may force a logout (2.3).
  4. fleetd creates the human's session on the same Context (3.7) and mints Live View after the operator authenticates.
  5. When the human is done: release, settle hold, login probe. Agent work then resumes as a **fresh wake** with a fresh lease. It never resumes inside the old session.
- A step cut off mid-click may have had an effect. An effect with no receipt is `uncertain` and held for reconciliation (D13), never retried. Reconciliation takes its own lease (`purpose=reconcile`, ARCHITECTURE §3.5).
- Until the release lands, anyone holding the `connectUrl` can keep driving. That is why `connectUrl` stays inside fleetd workers (15.2). The gap between the takeover decision and the release landing is `to measure`.

**There is no watch mode.**

- Read-only Live View is only the embedding page adding `pointer-events: none` to the iframe (`https://docs.browserbase.com/platform/browser/observability/session-live-view.md`). Only that page enforces it. The URL itself is read/write, and the docs show the same URL in both snippets.
- fleetd cannot cut a Live View holder without ending the session, which also ends the agent's work.
- So the fleet never labels a Browserbase view "watch only", and never hands out a Live View URL to look. Steel's watch tickets (forced `interactive=false`, input frames dropped by the broker) have no equivalent here.
- What is offered instead is **screenshots**, taken by the engine adapter on its own connection (a read-only CDP call, so the anchor keeps sending no commands, 3.8) and shown on a fleetd page. They can show DMs and personal data, so they get the same operator authentication and tenant scope as a viewer ticket. How long they are kept is Q-07's call (`inference`).

**Lease and URL lifetime.**

- A Live View URL is minted only for a lease that is currently held, and `expiresIn` is never longer than what is left of it (3.7).
- When the lease ends for any reason, fleetd releases the session. The URL then dies with the session ("When the browser session ends, the live view will show a disconnect message", `session-live-view.md`).
- Whether an already-open Live View connection survives past `expiresIn` is unknown (section 12). Until it is measured, the release at lease end is the control, and `expiresIn` is a second layer.

---

## 4. Engines on Browserbase: Stagehand and Browser-Use

D6 sets the engines: Stagehand 4.2.0 for scoped steps and extraction, Browser-Use 0.13.x as the open-ended explorer. This section covers only what is different on Browserbase.

### 4.1 Stagehand: three ways to connect

There is no `env="BROWSERBASE"` and no `Stagehand(cdp_url=...)` in v4. Those calls raise `TypeError` on 4.2.0 (`fleet/research/verification/GEMINI-AUDIT.md` rows 2.10, 10.01). The real entry points are `browserbase.launch()`, `browserbase.connect()` and `local_browser.connect()`.

| | N1: `browserbase.launch(...)` | N2: fleetd creates, then `browserbase.connect(session_id=...)` | C: `local_browser.connect(cdp_url=...)` |
|---|---|---|---|
| Who creates the session | Stagehand | fleetd, with the Browserbase SDK (3.3) | fleetd |
| Fleet sees the session id first | No | Yes: tags, lease, Live View, reaper all work | Yes |
| Extension | Stagehand uploads its own on every launch (a 441,819-byte request body) unless `extension_id` is passed, and deletes it at close | Pre-uploaded once per Stagehand version. Passed as `extensionId` **at session create** | Must already be discoverable in the browser. No shared filesystem with Browserbase. |
| `extension_id` on `connect` | n/a | **Ignored.** Docstring marks it deprecated. Set it at create. | n/a |
| Server-side cache | Available | Expected available. `to measure` | **Always off**: no session id is passed |
| `browser.close()` | Releases the session (even with `keep_alive=True`) and deletes the auto-upload | Releases the session | Sends CDP `Browser.close`, which kills the remote Chromium |
| Known problems | stagehand#2782: init timeout with a preloaded official extension, reported on 4.0.1, still open, unknown on 4.2.0 | Same open issue applies to a preloaded extension | Used for Steel (D6), not here |

Sources: `hands-on` offline (RESULTS.md spike 2); `source-code` Stagehand 4.2.0 Python `browser.py` and npm `dist/index.mjs` (BB-9, BB-4); docs `https://docs.stagehand.dev/v4/configuration/browser.md` lines 470-476, 617, 1013.

**Decision for the design: N2 is the target, N1 is the fallback.** fleetd must own the session id from the first call, because the lease, the tags, the Live View link and the orphan reaper all hang on it. N2 has not been run. If it fails the smoke test (extension preload, `connect` behaviour), use N1 with `extension_id` set and wrap it so fleetd still tags and tracks the session. **Path C is not used on Browserbase.**

### 4.2 Stagehand: the fleet's call (N2)

```python
from stagehand import Stagehand, browserbase

# session = bb.sessions.create(..., extension_id=STAGEHAND_EXT_ID)  # section 3.3
browser = await browserbase.connect(api_key=BB_KEY, session_id=session.id)

stagehand = await Stagehand.create(
    browser=browser,
    model=fleet_generate,       # the fleet's async callback (D6, D8). Not a provider/model string.
    self_heal=False,            # D5: on the decider path, a failed act must not call the model
    cache=False,                # section 4.3
)
# act / observe / extract ...
await stagehand.close()         # ends Stagehand's own RPC. Does NOT end the Browserbase session.
# Do not call browser.close() between steps. It releases the session.
# fleetd's anchor connection (3.8) keeps the session alive after Stagehand detaches.
# fleetd, not the engine, snapshots and releases.
```

Rules:

- **Always pass the model callback.** With no model set on Browserbase, Stagehand would use Browserbase's Model Gateway, billed through Browserbase and carrying page content to Browserbase's model providers (D6). Gateway "requires Browserbase-hosted browsers" (`https://docs.browserbase.com/platform/model-gateway/overview.md`). Not used.
- **Use plain dicts for settings.** The docs call `BrowserbaseBrowserSettings.model_validate(...)`. On 4.2.0 it is a TypedDict and that call raises `AttributeError` (`hands-on`, RESULTS.md spike 1, item 6).
- **Do not call `browser.close()` between steps.** It sends `REQUEST_RELEASE`, even with `keep_alive=True`. The Stagehand docs say the session "continues running after close()". Source says otherwise, in both Python and npm 4.2.0, and source wins (BB-9).
- **Pre-upload the Stagehand extension once per Stagehand version** and reuse its id. Otherwise every launch uploads about 442 KB, and the extension restarts the browser. But stagehand#2782 reports an init timeout with a preloaded extension on 4.0.1. The smoke test settles it for 4.2.0.
- The Stagehand extension tripped a public `isAutomatedWithCDP` check on stock Chromium 152 and stayed resident after `close()` (AP-2, n=1, measured on stock Chromium 152, not on Browserbase). On Browserbase it is unmeasured. The L1/L2 executor choice (D6, O-02) applies to this home too.

### 4.3 The server-side cache

- In v4 the act/observe/extract cache is server-side and Browserbase-only. With a local or attached browser "the `cache` option has no effect and every call runs inference" (`https://docs.stagehand.dev/v4/best-practices/caching.md`; BB-4).
- It is best effort and gated per project on the server. The key covers URL, page accessibility tree, instruction and variables. A hit needs a threshold of identical results. Locator-scoped calls are not cached.
- It sends the page's accessibility tree, and possibly `%variables%`, to Browserbase.
- On dynamic social feeds the hit rate is probably low (`inference`; verification missed issue 7).
- **Fleet:** `cache=False` by default. Opt-in per measured procedure, never on a call that carries credentials or private message text. Log `result.metadata.cache.status` to measure hit rate. **[pending Q-07]** (the tree leaves our control).
- It is a weak reason to choose Browserbase (D11, section 8, R3).

### 4.4 Browser-Use over CDP

Browser-Use 0.13.11 attaches by `cdp_url`. `Browser is BrowserSession`, and `cdp_url` gives `is_local=False` (`hands-on` offline). The shape matches the Browserbase docs (`https://docs.browserbase.com/integrations/browseruse/python.md`).

```python
from browser_use import Agent, Browser

# session = bb.sessions.create(...)           # section 3.3, no extension needed
browser = Browser(cdp_url=session.connect_url, keep_alive=True)  # Browser-Use's own flag
agent = Agent(task=TASK, llm=fleet_llm, browser=browser)   # fleet LLM shim, D8
result = await agent.run()                    # max_steps capped, flash_mode, exclude_actions: D6
# The agent process exits here and drops its CDP connection.
# fleetd's anchor (3.8) is still connected. fleetd then does read-back,
# the snapshot and the wrapped REQUEST_RELEASE. The engine never releases.
```

Rules:

- **Proxy only on the Browserbase session.** Do not set a Browser-Use proxy: with credentials it turns on request interception (D6).
- **`keep_alive=True` on the Browser-Use `Browser`.** This is Browser-Use's flag, not Browserbase's `keepAlive`. With the default (`None`), `Agent.run()` stops the browser at the end. That drops CDP and, without the anchor, ends the Browserbase session before fleetd can snapshot or read back. With `True`, `browser.stop()` returns early and the session keeps billing until fleetd releases it (`source-code` browser-use@c75e847 `agent/service.py`). The anchor (3.8) is what keeps it alive, so that is the thing the smoke test must prove.
- **Never `timeout=` for the session lifetime in the Python SDK.** Use `api_timeout=`.
- It opens tabs in the default context (`Target.createTarget` without a `browserContextId`), which is what Browserbase asks for.
- D6's other Browser-Use rules apply unchanged: `highlight_elements=False`, one agent per OS process with a hard kill timer, `allowed_domains` is not a boundary.
- A Stagehand extension is not needed for a Browser-Use session. `extensionId` is one per session, so a session is created with it or without it.
- Browser-Use attach did not trip `isAutomatedWithCDP` on stock Chromium 152; its actor API and coordinate clicks did (AP-2, C-13). Browserbase is unmeasured.

### 4.5 CAPTCHA events

Even with solving off, listen for `browserbase-solving-started` on the console. If it appears, solving was on by mistake. Stop and raise a `checkpoint`.

---

## 5. Lock-in and recovery

What the fleet gets and does not get, plainly:

| Event | What happens | What the fleet has | What it lacks |
|---|---|---|---|
| Browserbase suspends or deletes the account | "Account suspension or deletion will invalidate all Contexts" (`https://docs.browserbase.com/platform/browser/core-features/contexts.md`). The terms allow suspension "for any or no reason". | The registry knows every identity on this home. Optional CDP snapshots. | Every Browserbase-homed identity needs a human login again, on a new home, as a new identity (D3). |
| fleetd loses a Context id | The API has no list. | Contexts are named after the identity id. The dashboard lists them by name, so recovery is manual. | Any automated recovery. |
| A Context grows large | Sessions slow down (docs). | One Context per identity. | No API to read Context size. |
| Move to Steel | No export, no upload. | A CDP snapshot of cookies and localStorage, taken at session end. Untested. The IP and fingerprint change, so re-auth is likely anyway. | IndexedDB, service workers. |
| Enterprise plan | BYOS can write `contexts` artifacts ("Session context files (cookies, storage)", read/write) to your own S3 (`https://docs.browserbase.com/account/enterprise/byos-setup-guide.md`; BB-3). | Format and encryption are undocumented. | Not self-serve. |

The "Move to Steel" row and the suspension row are stated again as checklist lines in 8.2 (items 11-13). The owner and the client are told before the first Browserbase identity exists.

Fleet measures:

1. **The registry is the only programmatic index** of identity to `contextId`. fleetd's Postgres holds it (D12).
2. **Name every Context after its identity id** (`contexts.create(name=identity_id)`). Names are unique per project.
3. **Snapshot at session end.** Before `REQUEST_RELEASE`, read cookies and localStorage over CDP (for example Playwright `storage_state()`) and store them in the same encrypted bundle layer as Steel identities (D4; key custody is O-09). `unbuilt`, untested on Browserbase. It does not cover IndexedDB or service workers. It is a partial backup, not a migration.
4. **Every Browserbase-homed identity has a written re-login path**: who the human is, how the owner is notified, what the login probe checks.
5. **Browserbase is never the only thing that holds a client's access.** The client can always log in again, and the platform's own API tokens (D2) do not depend on this home.

---

## 6. Terms of use

Governing text: Browserbase Terms of Use, "Last Updated: August 1, 2025", https://www.browserbase.com/terms-of-service (`official-docs`, fetched 2026-10-09, byte-identical on 2026-10-10: `fleet/research/verification/browserbase.md`). The local copy sits in uncommitted scratch (`<scratch>/spikes/browserbase/fetched/tos.md`). It is not in the corpus.

**No standalone acceptable-use policy was found.** `/aup`, `/acceptable-use-policy`, `/legal` and `/legal/*` all redirect (307) to sign-in, as does every unknown path. So absence is weak evidence (BB-6). Enterprise or MSA terms are unknown.

Clauses that bite on the fleet's use, quoted:

| Topic | Quote |
|---|---|
| Spam / solicitation | "You agree not to use the Platform: ... To transmit, or procure the sending of, any advertising or promotional material, including any 'junk mail,' 'chain letter,' 'spam,' or any other similar solicitation." |
| Impersonation | "To impersonate or attempt to impersonate Browserbase, a Browserbase employee, another user, or any other person or entity ..." |
| Suspension | "Terminate or suspend your access to all or part of the Platform for any or no reason, including without limitation, any violation of these Terms of Use." |
| Multiple accounts | "Abuse our account or plan system, including but not limited to circumventing usage limits, creating multiple accounts to avoid restrictions, manipulating service tiers ... may result in immediate termination of your account without refund." |
| Intended use | "all use shall comply with applicable laws and the Platform's intended use cases. Use of the Platform in violation of any applicable law or outside its intended purpose is prohibited and shall void your rights hereunder." |
| Account transfer | "You may not transfer your account to anyone else without our prior written permission." |
| Recording | "By using the Session Recording Feature, you authorize us to store the recordings for 30 days." and "you will clearly and conspicuously display a persistent label identifying to the user that a recording is in process". |
| Recording conduct | Do not "Engage in activity that is illegal, false or misleading." |
| CAPTCHA (docs) | "Use CAPTCHA solving only for workflows that users and website owners authorize. Follow the site's terms ..." (`https://docs.browserbase.com/platform/identity/captcha-solving.md`) |
| Site terms (docs) | "Review the site's terms of service to ensure compliance." (`https://docs.browserbase.com/platform/identity/overview.md`) |

What they mean for the fleet:

- **The "multiple accounts" sentence is about Browserbase accounts, not accounts on target sites.** There is no clause about social media or multi-account management on third-party sites. So: **one Browserbase organization.** No sharding across Browserbase accounts to escape a concurrency cap or limit suspension blast radius. Use projects for coarse isolation (BB-6, missed issue 4).
- **The solicitation clause is ambiguous for client brand posts.** Read literally, "transmit ... advertising or promotional material" could cover a client's own promotional post. Read in context ("junk mail ... spam ... similar solicitation"), it targets unsolicited sending. Automated DMs and lead-gen outreach sit closest to it, and D2 already forbids building them. **Recommended default (pending Justin): on Browserbase-homed identities, outbound-message procedures (DM, comment, reply) do not run, and `publish` needs the owner's recorded acknowledgement for that identity.** **Open item BB-O2: ask Browserbase support in writing whether a client's own authorized posting through its own account is within the intended use.** **[pending Q-01]**
- **No impersonation:** only a client's own account, with the client's authorization. No personas or fake accounts (D2).
- **Recording off** removes the labelling duty and the 30-day store. If recording is ever turned on for debugging, the label rule applies.
- **The account belongs to Justin's business.** Do not hand it to a client.
- **Withdrawable infra.** The posture in the terms is "we can end this at will". Section 5 and the soul line follow from it.

---

## 7. Pricing and limits

Source: `official-docs` `https://docs.browserbase.com/account/billing/plans.md`, fetched 2026-10-09 and byte-identical when re-fetched 2026-10-10. The marketing page (`vendor-claim`, `https://www.browserbase.com/pricing`) matches except where marked. **Prices change. Re-check at purchase.**

| | Free | Developer | Startup | Scale |
|---|---|---|---|---|
| Price per month | $0 | $20 | $99 | Custom |
| Browser hours included | 1 | 100 | 500 | Flexible |
| Browser-hour overage | n/a | $0.12 | $0.10 | Custom |
| Proxy GB included | 0 | 1 | 5 | Usage-based |
| Proxy overage per GB | n/a | $12 | $10 | Custom |
| Concurrency | 3 | 25 | 100 | 250+ |
| Session creation rate | 5 per min | 25 per min | 50 per min | 150+ per min |
| Max session | 15 min | 6 h | 6 h | "6+ h" (timeouts page says 6 h) |
| CAPTCHA | none | auto | auto | auto |
| Verified | no | "Basic" | "Basic" | Verified (marketing: "Advanced") |
| Data retention | 7 d | 7 d (docs) vs 30 d (pricing page) | 30 d | 30+ d |
| Projects | 1 | up to 2 | up to 5 | 5+ |
| Agent runs included | 3 | 15 | 50 | custom |
| SSO, HIPAA, DPA | no | no | no | available |

Notes:

- **keepAlive is not in this table on purpose.** `plans.md` has no keepAlive row, and three sources disagree (section 2.3).
- BYO proxy needs Developer or above.
- Billing: per minute and per MB, with a one-minute and one-MB minimum per session. Overage has "No caps. No cut-offs." keepAlive orphans bill until timeout. 1,000 orphaned 6 h sessions would be about 6,000 browser hours, about $600 at $0.10 (`estimate`).
- Concurrency is per organization, split across projects (BB-7).
- At 50 sessions per minute (Startup), creating 100 sessions takes about 2 minutes (`plans.md`). Pre-wake spreads this (D12).
- A 429 comes with `retry-after` and `x-ratelimit-*` headers. The factory honours `retry-after`.
- Contexts: no documented price, count limit or size limit.
- Data retention figures disagree four ways (plans page, pricing page, replay page, terms). None is clearly authoritative.
- Verified and Web Bot Auth are Scale / request-access features with custom pricing.
- ZDR and BYOS are Enterprise-only (`https://docs.browserbase.com/account/enterprise/`).
- Spend caps for this home are **[pending Q-06]**.

---

## 8. When the fleet chooses Browserbase, and when not

Default is `steel-oss`. An identity gets `home: browserbase` only if **triage allows it (8.1), one reason applies, and all preconditions hold (8.2)**. Identity creation is owner-only (D17).

### 8.1 Triage first, then a reason

D11 lets an identity be created on Browserbase "for a measured reason: a site where Steel fails, burst/pilot capacity". **This guide reads "a site where Steel fails" as a functional failure only.** That is narrower than D11's words. It follows from D9 (continuity, not evasion), the charter red line on ban evasion and on "circumventing a platform's technical access measures", `fleet/docs/identity/identity-and-proxies.md` §3.7 and `fleet/docs/playbooks/lead-gen.md` §1.2 and §3.8. D11 itself has not been edited to say so yet. It should carry the same sentence (stress test G10-1 and G10-13: `fleet/research/scenarios/S10.md`).

#### Step 1. Triage (mandatory, before any Browserbase run)

A failure on Steel can mean three different things. Only the first one is a reason to look at Browserbase.

| Class | What it is | Typical signs |
|---|---|---|
| **B-F** functional | Steel cannot render a page or finish a login because a browser capability is missing, or an input never reaches the page. | A passkey, IME or native-dialog login the Steel viewer cannot complete (D4: untested). A page feature the headless build lacks. A script error in the console. No refusal text anywhere. |
| **B-D** defence | The site is refusing this browser, this IP or this traffic. | A "checking your browser" interstitial, a challenge page, a CAPTCHA, 403 or 429, "unusual traffic" or "automated" wording, a block that follows the IP or the fingerprint. |
| **B-P** platform restriction | A platform restricts, challenges or suspends the client's account. | A checkpoint, a restriction, a warning, a suspension or a ban on the client account. |

Rules:

1. **Classify from Steel-side evidence only, before any Browserbase run.** A Browserbase result never reclassifies a failure. If Browserbase gets through a page that refused Steel, that is the B-D signature, not evidence of B-F.
2. **B-F needs all of these:**
   - the failure is in the page's own function (a console error, a missing feature, input that is not delivered), not in a refusal;
   - there is no refusal signal in the table above, on the target site or in the logs;
   - the same failure reproduces on a **public** page that exercises the same feature, with no account of any client;
   - the Steel-side fix path is written down and has failed or is ruled out (flags, GPU and WebGL setup, viewer input; D4).
3. **Ambiguous is B-D.** A blank page, a timeout or an unexplained 403 is not B-F until the evidence says so. Fail closed.
4. **Do not probe the target site with other IPs, personas or stacks to find out which class it is.** Trying another stack against a site that refuses you is the work-around (`lead-gen.md` §3.8: "No IP rotation, no proxy change, no User-Agent change to get through").
5. **Record it.** Class, evidence references, who decided. The note goes into the owner's Obsidian vault (D15). Its path is `home_evidence` on the identity record (8.4).

What happens next:

| Class | Next step |
|---|---|
| B-F | Continue to the reasons (step 2). R1 applies. |
| B-D | **Stop. Owner decision. No new home, IP, persona or stealth setting.** The allowed routes are: ask the site for permission, an API or an allow-list entry for the identity's static IP; have the client's person use the site by hand, on their own device or in the viewer on the existing identity (the viewer is still the fleet's browser driven by a human, so it may meet the same wall; their own device is cleaner, see `fleet/research/scenarios/S12.md` G12-10); or drop the procedure. |
| B-P | **Stop all activity on the identity** (charter, Escalation). A platform restriction is never answered with a new home, a new IP or a new identity: that is ban evasion, a red line (`identity-and-proxies.md` §3.7). The client resolves it with the platform through their own channels. |

Why Browserbase is no answer to B-D or B-P: it sells "automatic fingerprinting (devices, locales, operating systems)" and the fleet does not know what that changes (section 2.5). If that is what passes, the fleet would adopt spoofing by renting it, without Q-04 being answered (`https://docs.browserbase.com/platform/identity/verified-customization.md`). The old wording of R1 ("Steel failed, Browserbase passed with the same proxy") could be satisfied by exactly that. The triage closes it.

An open B-D or B-P record for the same site and client account also blocks R2 and R3 below. A reason that does not involve a failure cannot be used to route around one.

#### Step 2. Reasons (at least one, written into the identity record with its evidence)

| # | Reason | What counts as evidence |
|---|---|---|
| R1 | A **functional** failure on Steel (triage class B-F) that Browserbase does not have. | The triage record, plus the R1 evidence rule below. Includes a login that Steel's viewer cannot complete (special keys, IME, passkeys: untested, D4), but only if the same input class is shown to complete in Browserbase Live View. That is untested too (section 12, item 12). |
| R2 | Burst or pilot capacity before the Steel pool exists. | The M1 node pool is not ready. Pilot identities stay where they were created. New identities go to Steel once it exists. No triage is needed, because no failure is involved. |
| R3 | A measured Stagehand cache hit rate pays for the premium. | Hit rate and token savings per procedure on Browserbase, compared with a fleet-built L1 replay cache on Steel (D5). **Weak** (D11). Needs the Q-07 answer. |
| R4 | Verified, if the owner buys Scale. **[pending Q-04]** | **Closed while Q-04 is at its default (no spoofing).** Verified selects a vendor-supplied OS fingerprint ("changes the user agent and browser environment", `verified-customization.md`), which is what Q-04 asks about. If Justin ever allows it, R4 still never answers a B-D or B-P failure. It needs its own case, measured on public bot-test pages only. No sacrificial account. Its value against Meta, TikTok and X is unproven, because their detection is in-house, and Verified may announce automation (`inference`). |

**R1 evidence rule.** A plain A/B ("a sacrificial account, the same proxy and persona") cannot be followed here, for five reasons:

- A sacrificial account on a social platform is a fake account, a charter red line.
- "Same proxy" is unreachable: each identity's exit IP is unique, and a test that borrows a live client IP from a second browser puts two fingerprints on one IP.
- "Same persona" is unreachable: Browserbase cannot pin the UA or locale (3.6).
- The A/B could run with Browserbase's default CAPTCHA auto-solve on, while production sets `solveCaptchas: false` (`https://docs.browserbase.com/platform/identity/captcha-solving.md`).
- Public pages cannot reproduce a logged-in defence.

The rule now has two parts.

*Part A. Public-page A/B, before the identity exists.*

1. Use a **spare vetted IP**: one that passed D10's vetting rule, belongs to no identity, and is never assigned to one afterwards (`inference`: a test IP that has been through a datacenter browser carries that reputation). Never a client's live IP. Run the two arms one after the other from it, never at the same time.
2. Use a **public page that reproduces the B-F failure** (for a viewer input class, a public demo page built for that input, such as a passkey or input-method demo). No account of any client and no social platform.
3. The Browserbase arm runs the **production settings**: BYO `type: "external"` proxy on the spare IP, `solveCaptchas: false`, `recordSession: false`, `logSession: false`, no Verified, no `os`, no `advancedStealth`, no `fingerprint`. Void any run where `browserbase-solving-started` appears on the console (4.5).
4. Record what each arm actually presented (UA, language, timezone, platform, WebGL renderer) as telemetry. "Same persona" is not claimed, because Browserbase cannot pin it.
5. The owner fixes the number of runs before the test, not after (`to measure`).
6. Needs a paid key and a spare IP, so Q-12 and Q-06 (section 8.2). Nothing here has run.

*Part B. Canary in the new home, after the identity exists.*

1. The new identity starts **read-only** (D13, O-13).
2. The client's person does a **logged-in, read-only check** by hand through Live View on the new identity: open the page, look, change nothing. This is the only way to see a logged-in defence, and public pages cannot show it.
3. Then the first fleet run is a read-only procedure, and its verifier decides.
4. If the canary meets a wall, a challenge or a checkpoint, it is **B-D or B-P. Stop.** Do not tune settings, change the IP or try another home.

*What a pass proves, and what it does not.*

**A pass proves:** on those public pages, from that IP, with those settings, Browserbase's browser did what Steel's did not. For a B-F failure that is the point: the missing capability is on the Steel side.

**A pass does not prove:**

- that a logged-in client account will pass, now or later;
- that a platform's or site's defences will stay quiet (detection is theirs, and the A/B cannot see it);
- that the fingerprint is stable per Context (section 12, items 7 and 20);
- that Browserbase's undeclared "automatic fingerprinting" was not what passed (Q-04);
- that identities on this home are unlinkable from other clients' identities (Q-13, 3.6).

**Not reasons:**

- CAPTCHA auto-solve (D14: agents never solve CAPTCHAs on client accounts).
- Getting past a bot wall, an IP or fingerprint block, or a platform restriction (B-D, B-P).
- A Browserbase pass against a page that refused Steel.
- "Less ops work" alone. It is real, but not a decision on its own.
- Anything the dossier says the fleet "cannot build elsewhere". The cache can be built (V-1).

### 8.2 Preconditions (all of them)

This is the decision checklist. Items 1-8 are the original list and keep their numbers. Items 9-13 were added after the stress tests (`fleet/research/scenarios/S10.md` G10-1, G10-8, G10-14).

1. Owner approval. **[pending Q-12]** for any hands-on or paid key.
2. A vetted static ISP IP assigned (D10's vetting rule), on a provider that offers an **HTTP or HTTPS** endpoint with a credential scoped to that single IP. SOCKS5-only is out.
3. A Q-07 answer that allows this client's page content, files and Context to live in a third-party hosted browser. **[pending Q-07]**
4. The client's written risk acceptance (Q-01), plus the Browserbase-specific note in section 6. **[pending Q-01]**
5. A plan with the concurrency the identity needs, and keepAlive verified if the login flow needs it.
6. A written re-login path (section 5).
7. A spend cap for the home. **[pending Q-06]**
8. The canary rule (D13, O-13) passes before any client work. For R1 that includes Part B of the evidence rule in 8.1.
9. **Triage record.** For R1: class **B-F**, with its evidence, recorded before any Browserbase run (8.1). No B-D or B-P record is open for the same site and client account.
10. **Operator authentication for the viewer is decided.** **[pending AQ-1]** Browserbase Live View is a bearer capability, so it is minted only after the operator has authenticated (3.7). Until AQ-1 is answered, no Browserbase identity can be onboarded, because the first login needs that link. AQ-1 is not among Justin's 14 (`fleet/ARCHITECTURE.md` section 9.4).

The owner records these three acknowledgements on the identity, and the client is told before creation:

11. **Unlinkability is not claimed on this home.** **[pending Q-13]** Browserbase picks the hardware and fingerprint values, and what they are is unknown (3.6, section 12 items 7 and 20). Cross-client unlinkability cannot be assessed without hands-on. Do not tell a client that a Browserbase-homed identity is unlinkable from other clients' identities.
12. **No way back.** Any later move is a new identity and a fresh human login. Contexts cannot be exported or uploaded through the self-serve API, and the CDP snapshot misses IndexedDB and service workers (section 5). **A Browserbase suspension voids every Context at once**, so every Browserbase-homed identity needs a fresh login together.
13. **Continuity is partly traded away.** "Same browser every time" is not fully met here: Browserbase chooses the UA, OS, locale and hardware values, and the fleet can pin only the viewport, region, timezone and proxy IP (3.6).

### 8.3 Do not choose it when

- **The Steel failure is B-D or B-P (8.1), or cannot be shown to be B-F.** This guide has no route for it.
- A Browserbase run got through a page that refused Steel. That is the B-D signature (8.1), not a reason.
- It is the first choice for convenience. The default stands.
- The client's login must be portable or exportable.
- The Q-07 answer forbids third-party hosted browsers, or requires ZDR. ZDR is Enterprise-only.
- The identity needs a pinned UA, locale or hardware profile (section 3.6), or cross-client unlinkability must be promised. **[pending Q-13]**
- The workflow is outbound messaging or anything near the solicitation clause (section 6).
- The proxy provider cannot give an HTTP or HTTPS static IP.
- A session would need to run longer than 6 hours without a clean split.
- The work needs no browser at all. API-first (D2) covers most social work.
- The workflow needs a watch-only view of the live browser. This home cannot offer one (3.9).
- Volume is at the 1,000-identity scale, where Scale custom pricing, concurrency and the ToS single-account cap all apply.

### 8.4 What the identity record carries

Target shape, `unbuilt`:

```json
{
  "identity_id": "<opaque>",
  "home": "browserbase",
  "home_reason": "R1",
  "home_failure_class": "B-F",
  "home_evidence": "<path to the triage and measurement note>",
  "owner_acknowledged": ["no_unlinkability_claim (Q-13)", "no_way_back", "continuity_traded"],
  "browserbase": {
    "project_id": "<...>",
    "context_id": "<...>",
    "region": "us-east-1",
    "viewport": [1280, 720],
    "timezone": "America/New_York",
    "proxy_ref": "<vault reference; never the secret itself>",
    "pinned_exit_ip": "<...>",
    "plan_snapshot": "2026-10-09"
  }
}
```

`home_failure_class` is `B-F` for R1 and empty for R2 and R3 (no failure is involved). `B-D` and `B-P` never appear on a created identity: they stop before creation (8.1).

Changing `home`, `region`, `viewport`, `timezone` or the exit IP means a new identity (D3). Rotating the credential of the same proxy IP is the only in-place change.

---

## 9. Cost comparison

**Use D12's table** ([DECISIONS.md](../../DECISIONS.md) D12, from `fleet/research/dossiers/scale-infra.md` Q4). Its Browserbase column is the like-for-like number: Browserbase browser hours at list price, plus the same static-ISP proxy, model, control-plane and agent-worker lines as the other columns.

| Identities x browser h/day | Self-hosted (autoscaled) | Steel Cloud | Browserbase |
|---|---:|---:|---:|
| 30 x 1 | ~$294 | ~$470 | ~$359 |
| 100 x 3 | ~$1,007 | ~$1,662 | ~$1,741 |
| 1,000 x 3 | ~$8,413 | ~$13,949 (custom) | ~$15,749 (custom) |

All are estimates. How to read the Browserbase column:

- It implicitly assumes **BYO-proxy bytes are not billed by Browserbase.** That is unknown. If they are, the size of the extra bill is unmeasured (BB-10, section 12).
- **Parity with self-hosting holds only at 30 x 1.** At 30 x 3 Browserbase is $597 against $405 to $518 (SCA-11).
- **At 30 x 1 the Developer plan is cheaper**: browser time is $20 + 800 h x $0.12 = $116 against $139 on Startup. It has 25 concurrent sessions and keepAlive is unverified there (SCA-11).
- The 1,000-identity rows need the **Scale** plan, which is custom-priced. The table uses list rates as a stand-in.
- Under API-first (D2) most identities need few or no browser hours. The real driver is the share of identities that need a browser, and that share is not yet estimated (C-17). The table is an all-browser upper bound.
- Its model mix assumes a fleet-built L1 cache hit rate that does not exist yet (C-05).
- It omits X API fees, the settle hold per sleep, and the cost of the Option F forwarder if built.
- Proxies and models are 60-75% of the bill at 1,000 identities. Replace every row with M1 and M6 measurements.

Browser-time-only at list on Startup (arithmetic: $99 + (hours - 500) x $0.10; excludes proxy, models and workers; `estimate`): 30 x 1 = 900 h = $139; 100 x 3 = 9,000 h = $949; 1,000 x 3 = 90,000 h = $9,049. Peak concurrency in the D12 model (scale-infra Q2) is 4, 38 and 375 for those three rows, so 1,000 x 3 exceeds Startup's 100. The peak figures rest on a 16-hour active window and a 2x factor that have no source (SCA-7).

The dossier's per-profile figures ($18 and $54 per month) are dropped. They rest on an unsourced 50 MB per browser-hour and on Browserbase's rotating proxy. Measured bytes per hour is a smoke-test item.

---

## 10. Why Hermes' built-in Browserbase provider is not used

Hermes ships a Browserbase browser provider: `NousResearch/hermes-agent@5ba559c` `plugins/browser/browserbase/provider.py` (copy at `<scratch>/spikes/browserbase/hermes-bb-provider.py`; identical on re-fetch). Browserbase documents it on `https://docs.browserbase.com/integrations/hermes-agent/setup.md`. Checked by BB-5. The fleet does not use it:

| Problem | Detail |
|---|---|
| **No Context** | The session config has only `projectId`, `keepAlive`, `timeout`, `proxies` and `browserSettings.advancedStealth`. No `context`. A profile on it would lose its login every session. |
| Wrong proxy default | `BROWSERBASE_PROXIES` defaults to true: Browserbase's rotating proxy. |
| keepAlive default on | `BROWSERBASE_KEEP_ALIVE` defaults to true. Sessions bill until released. |
| **Automatic downgrade** | On HTTP 402 it drops `keepAlive`, then `proxies`, and retries, logging only a warning. For a fleet identity the IP would change and nothing would stop the session. |
| Deprecated flag | `BROWSERBASE_ADVANCED_STEALTH` (default off) sends `advancedStealth`, which the SDK marks deprecated. |
| Timeout unit | The code sends `BROWSERBASE_SESSION_TIMEOUT` straight through as seconds. Browserbase's own Hermes page says "in milliseconds" (600000), which would exceed the 21,600 s cap. |
| **Key in the profile** | It reads `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` from the profile. The key is project-wide. No per-agent keys exist. A profile must never hold it. |

So the fleet ships its own session factory (section 3) behind the fleetd tool surface (D17). Fleet profiles do not get `BROWSERBASE_API_KEY` or `BROWSERBASE_PROJECT_ID` in their `.env`, and Hermes' browser provider stays unconfigured for them.

---

## 11. Privacy

What leaves our control on this home:

- **Everything the page shows, types or stores passes through Browserbase's machines**, because the browser runs there (`inference`).
- **The Context** (cookies, tokens, IndexedDB) is stored by Browserbase. The docs say it is "uniquely encrypted at rest". They do not say the key is ours, so assume Browserbase can read it (`inference`).
- **Proxy credentials** go to Browserbase in the create body. Use a credential scoped to one IP.
- **Recordings** are on by default and kept 30 days. Off in the fleet.
- **The Stagehand cache** ships the accessibility tree. Off by default.
- **Files** uploaded or downloaded sit in Browserbase storage.
- **Retention figures** disagree (section 7). ZDR and BYOS are Enterprise-only.
- **Tags** hold opaque ids only.
- **The Live View URL** is a bearer capability. It is minted only after operator authentication, with `expiresIn` no longer than the remaining lease. It is never reused, never logged and never in an agent's context or a tool result (3.7). Agents get a fleetd ticket URL only.

Model calls do not go through Browserbase: they use the fleet's callback from a fleet worker (D6). Data handling for client pages and model providers is **[pending Q-07]**.

---

## 12. Unknowns the first paid key must settle

None of these can be settled without a paid key and Justin's yes (**Q-12**). Sources: `fleet/research/dossiers/browserbase.md` section 5; `fleet/research/verification/browserbase.md` "Unverifiable".

1. Whether bytes through an `external` proxy are billed as Browserbase proxy GB.
2. Real bytes per browser-hour on social pages.
3. Whether keepAlive works on Developer, and which plan gate is true.
4. Whether `timeout` as a float is accepted.
5. Whether a `TIMED_OUT` session saves its Context.
6. Whether a never-attached session stays alive without keepAlive.
7. Whether the fingerprint stays stable per Context, with and without Verified.
8. Whether `browserSettings.fingerprint` is honoured or rejected.
9. Whether the timezone override survives a new tab, a worker, a reconnect and a Live View handoff.
10. Whether the exit IP stays pinned for a full session through an `external` proxy, and whether a provider kill switch shows up as a failed navigation.
11. Whether WebRTC or DNS leaks a Browserbase datacenter IP.
12. Whether Live View handles Enter, Backspace, Tab, arrows, IME, passkeys, native dialogs, HTTP auth and file pickers. For an R1 case the class that Steel could not complete is the one that must be shown to work (8.1).
13. Whether `GET /v1/sessions` crosses projects, and whether the `q` tag filter works as the docs show.
14. The real Context size ceiling.
15. Whether Stagehand 4.2.0 initializes with a preloaded extension (stagehand#2782), and whether `browserbase.connect` works as N2 assumes.
16. Stagehand cache hit rate on social feeds, and whether our project has the server-side cache flag.
17. Whether `isAutomatedWithCDP`-style signals appear with Stagehand's extension on Browserbase.
18. Whether the Guard (D4) is wanted or workable over remote CDP here.
19. Whether a non-keepAlive session survives one CDP client dropping while fleetd's anchor stays connected (3.8), and whether it ends when the anchor drops last.
20. What Browserbase's default "automatic fingerprinting" actually presents, and whether it is stable per Context.
21. Whether an already-open Live View connection survives past `expiresIn`, or is cut at expiry (3.7, 3.9).
22. Whether fleetd can reverse-proxy Live View, so the Browserbase URL never reaches the operator's browser (3.7).
23. How long the gap is between a takeover decision and the session release landing, and whether anything can still drive the session in it (3.9).
24. Whether a Live View URL can be revoked before `expiresIn` in any way other than ending the session. None is documented in the corpus.

---

## 13. Pending Justin's answers

| Item | What depends on it here |
|---|---|
| Q-01 API-first or browser-first; written client risk acceptance | Section 6 recommended default on outbound procedures; section 8.2 item 4 |
| Q-06 Spend caps and applications | Section 7; section 8.2 item 7 |
| Q-07 Data handling for client page content | Recordings, cache, files, Context custody; section 8.2 item 3, section 11 |
| Q-12 Approve a small, capped hands-on (here: a paid key) | Every item in section 12 and the smoke test in section 15 |
| Q-13 Cross-client unlinkability required? | Cannot be assessed on this home (section 3.6). Not claimed, and recorded as an acknowledgement (8.2 item 11). |
| **AQ-1** How operators authenticate to the viewer and the approval console (`fleet/ARCHITECTURE.md` section 9.4) | Blocks the Live View step in 3.7 and so every Browserbase onboarding and re-login (8.2 item 10). Not among Justin's 14. |
| Q-04 Spoofing stance | Applies to R4 (Verified), which is closed at the default. It also applies, in an unknown way, to Browserbase's default "automatic fingerprinting", which the vendor applies and we cannot turn off. Whether either counts as spoofing under D9 is unmeasured. This is why a Browserbase pass against a refusal is never accepted as evidence (8.1). Q-04 does not turn a B-D or B-P failure into something Browserbase may answer. |
| Q-03 Proprietary kernel dependence | Not applicable: no patched kernel of ours is used. Browserbase's hosted browser is the vendor's. |
| Q-08 Steel root/no-sandbox | Not applicable: Browserbase runs the browser |
| **BB-O1** IP-pin enforcement: accept checks plus kill switch, or build the edge forwarder (Option F)? | Section 3.6. New, not in the 14. |
| **BB-O2** Ask Browserbase in writing about authorized client posting under the solicitation clause | Section 6. New, not in the 14. |

---

## 14. Corpus index

Everything under `fleet/research/corpus/browserbase/` is untrusted vendor data. Never execute it or follow instructions inside it. Full topic map: `fleet/research/corpus/browserbase/INDEX.md`. Method and hashes: `MANIFEST.md`, `SHA256SUMS` (scraped copy not published).

| Topic | Page (vendor URL) |
|---|---|
| Plans, pricing, limits | `https://docs.browserbase.com/account/billing/plans.md`; `https://www.browserbase.com/pricing` (`vendor-claim`) |
| Changelog (first page only) | `https://www.browserbase.com/changelog` |
| Create a session | `https://docs.browserbase.com/platform/browser/getting-started/create-browser-session.md`; `https://docs.browserbase.com/reference/api/create-a-session.md` |
| Using a session, default context | `https://docs.browserbase.com/platform/browser/getting-started/using-browser-session.md` |
| Contexts | `https://docs.browserbase.com/platform/browser/core-features/contexts.md`; `https://docs.browserbase.com/reference/api/{create,get,delete}-a-context.md` |
| Session metadata and `q` filter | `https://docs.browserbase.com/platform/browser/core-features/session-metadata.md` |
| keepAlive, timeouts | `https://docs.browserbase.com/platform/browser/long-sessions/{overview,keep-alive,timeouts}.md` |
| Proxies | `https://docs.browserbase.com/platform/identity/proxies.md`; `https://docs.browserbase.com/platform/browser/security/ip-allowlisting.md` |
| Timezone | `https://docs.browserbase.com/platform/browser/techniques/timezones.md` |
| Stealth, Verified | `https://docs.browserbase.com/platform/identity/{overview,verified-customization}.md` |
| Web Bot Auth | `https://docs.browserbase.com/platform/identity/web-bot-auth.md` |
| CAPTCHA | `https://docs.browserbase.com/platform/identity/captcha-solving.md` |
| Website authentication | `https://docs.browserbase.com/platform/identity/authentication.md` |
| Live View | `https://docs.browserbase.com/platform/browser/observability/session-live-view.md`; `https://docs.browserbase.com/reference/api/session-live-urls.md` |
| Recordings | `https://docs.browserbase.com/platform/browser/observability/{session-replay,recording-downloads}.md` |
| Files | `https://docs.browserbase.com/platform/browser/files/{downloads,uploads}.md` |
| Extensions | `https://docs.browserbase.com/platform/browser/core-features/browser-extensions.md` |
| Allowed domains | `https://docs.browserbase.com/platform/browser/security/allowed-domains.md` |
| Regions | `https://docs.browserbase.com/optimizations/latency/multi-region.md` |
| Concurrency | `https://docs.browserbase.com/optimizations/concurrency/overview.md` |
| Model Gateway | `https://docs.browserbase.com/platform/model-gateway/overview.md` |
| Enterprise: ZDR, BYOS | `https://docs.browserbase.com/account/enterprise/{zero-data-retention,byos-setup-guide}.md` |
| Browser-Use on Browserbase | `https://docs.browserbase.com/integrations/browseruse/python.md` |
| Hermes integration | `https://docs.browserbase.com/integrations/hermes-agent/{introduction,setup}.md` |
| API schema | `https://docs.browserbase.com/reference/api/openapi.v1.yaml` (incomplete; see INDEX.md) |
| SDK methods | `https://github.com/browserbase/sdk-node/blob/adef824/api.md`, `https://github.com/browserbase/sdk-python/blob/b3d67ac/api.md` |

Other corpora used:

- Stagehand v4 docs: `https://docs.stagehand.dev/v4/configuration/browser.md`, `https://docs.stagehand.dev/v4/best-practices/caching.md`.
- Steel, for comparison: `https://steel.dev/pricing.md`, `https://docs.steel.dev/overview/pricinglimits.md`, `https://docs.steel.dev/overview/sessions-api/dedicated-ips.md`.

Research behind this guide:

- Dossier: `fleet/research/dossiers/browserbase.md`. Verification: `fleet/research/verification/browserbase.md` (BB-1 to BB-10, V-1 to V-6, missed issues 1-12).
- Scale and cost: `fleet/research/dossiers/scale-infra.md` Q4 and `fleet/research/verification/scale-infra.md` SCA-5, SCA-11, SCA-13.
- Cross-dossier: `fleet/research/verification/CONSISTENCY.md` (C-05, C-17, C-18, C-24); `fleet/research/verification/GEMINI-AUDIT.md` (rows 1.04, 2.04, 2.10, 5.01-5.05, 9.03, 10.01).
- Offline spikes: `fleet/research/spikes/browserbase/RESULTS.md`.
- Stress tests: `fleet/research/scenarios/S10.md` (a new identity homed on Browserbase) and `S12.md` (a human takes over an identity). Charter and policy sources for triage: `fleet/CHARTER.md` (Red lines, Escalation), `fleet/docs/identity/identity-and-proxies.md` §3.7, `fleet/docs/playbooks/lead-gen.md` §1.2 and §3.8.
- Source pins: `bb-sdk-node@adef824c9bc9adaf7217aab980b4a9ca51ce73db`, `bb-sdk-python@b3d67ac84d8c5f9d79b4b8dfac3140bd4736eada` (`browserbase==1.20.0`), `stagehand@1fc884992b68a0196ea5c6e96cc29924b0922ef4` (Python and npm 4.2.0), `browser-use@c75e8476e26d18b7617643bc2ae082fae8eae431` (0.13.11), `NousResearch/hermes-agent@5ba559c9e4b1c8397df7788e319ab634144ca728`.

---

## 15. Governance

### 15.1 Version pin and the upgrade gate

Browserbase is a hosted service. There is no Browserbase version to pin, and **its Chromium is not pinnable**. They can change the browser, the fingerprint set, the proxy pool or the API under us. The smoke test exists to catch that. What the fleet does pin:

| Pinned | Value |
|---|---|
| Stagehand | 4.2.0 (PyPI `stagehand==4.2.0`, npm `@browserbasehq/stagehand@4.2.0`) |
| Browser-Use | 0.13.11 |
| Browserbase Python SDK | `browserbase==1.20.0` (`bb-sdk-python@b3d67ac`) |
| Browserbase Node SDK | `@browserbasehq/sdk` 2.21.0 (`bb-sdk-node@adef824`) |
| REST API | `/v1` as captured in `https://docs.browserbase.com/reference/api/openapi.v1.yaml` and `sdk/*/api.md` (scraped copy not published) |
| Docs and plans snapshot | The corpus capture of 2026-10-09, hashes in `corpus/SHA256SUMS` (scraped copy not published) |
| Stagehand extension id | One uploaded id per Stagehand version, stored with the pin |

**Upgrade gate.** None of the following may change in use until the smoke test passes:

- a pin above (Stagehand, Browser-Use, either SDK);
- a drift check that finds a changed page. Re-fetch `plans.md`, `proxies.md`, `contexts.md`, `verified-customization.md`, `timezones.md`, `keep-alive.md`, `captcha-solving.md` and the terms of use, and diff against the corpus. A changed page blocks the pin until it is re-read, and the corpus is refreshed. Needs no key;
- a changed Chromium version or user agent, recorded at every smoke-test run and at every wake.

A new pin or a changed browser also passes the canary rule (D13, O-13) on a throwaway identity before it touches a client account.

**Smoke test.** `unbuilt`. It needs a paid key and Justin's yes (Q-12). It runs on public test pages only (no logins, no social sites, no real accounts, nothing that posts or sends) with a throwaway Context and a throwaway static proxy. Pass means all of these, on two runs in a row:

1. The create shape in 3.2 is accepted: `timeout` as an integer, the `userMetadata` cap (with Stagehand's added tags), `solveCaptchas: false` honoured (no `browserbase-solving-started` event on a public CAPTCHA demo page).
2. The exit IP seen by the fleet's echo endpoint equals the pinned IP, at wake, mid-session and in a second session.
3. The timezone equals the pinned value after a new tab, a popup, a CDP reconnect, a Live View handoff and inside a dedicated worker.
4. A marker cookie and a localStorage key set in session 1 with `persist: true` are present in session 2 after release and the settle hold. A deliberate `TIMED_OUT` ending is probed to settle unknown 5.
5. A Live View URL mints with `expiresIn: 60`, works, and stops working after expiry. A connection that is already open at expiry is observed: cut, or still alive (section 12, item 21). Typed text plus Enter, Backspace and Tab work through it. The URL is minted only after a (test) operator authentication step, and a URL requested for a lease with less than 60 s left is refused by the fleet. It appears in no log line, trace or tool result of the test run (grep the run's output for it).
6. Release semantics: Stagehand 4.2.0 `browser.close()` releases the session even with `keep_alive=True`; `stagehand.close()` does not; `browserbase.connect` works with the extension set at create (N2), or N1 works.
7. `recordSession: false` yields a 404 for the replay.
8. A public WebRTC / DNS leak page shows no Browserbase datacenter IP.
9. The project usage API shows whether `external` proxy bytes were billed, and the measured bytes per browser-hour.
10. keepAlive is accepted (or refused) on the purchased plan.
11. The anchor works: the session survives when an engine's CDP client drops while fleetd's anchor stays connected, and the Context still saves after the wrapped release (3.8).
12. The takeover drill (3.9): an agent session is running, a takeover releases it, the human's session is created only after `COMPLETED` and the settle hold, then released, then a fresh agent wake follows. At no moment does `GET /v1/sessions` (queried by the `fleet_profile` tag) show two `RUNNING` sessions for the identity, and the marker cookie and localStorage key survive all three sessions. The gap between the takeover decision and the release landing is recorded (section 12, item 23).

A failure blocks new identities on this home and the upgrade. Existing identities keep running only if the failure is not in their own path. The owner decides. The result goes into fleetd's release record, and a copy goes into the owner's Obsidian vault as a run note (D15).

### 15.2 What agents may and may not do through this property

Agents never touch Browserbase. They reach it, if at all, through fleetd's tools (D17), with the same scopes and gates as on Steel.

| Agents may | Agents may not |
|---|---|
| Ask for `wake`, `sleep` and `reauth` on an identity bound to their token. They receive state, and for `reauth` a **fleetd ticket URL**, never the Browserbase session id, `connectUrl`, Context id or a Live View URL. | Hold or see the Browserbase API key, project id, proxy credentials, `connectUrl` or Context id. |
| Run released procedures, `act`, `extract` and `task` within their scopes. D13 gates (manifest, approval, idempotency, read-back) apply unchanged. | Mint, see or forward a Live View URL (a fleetd ticket URL is the only link an agent may pass on). |
| Report a `checkpoint` or `needs_reauth` and wait for a human. | Create, delete or rename Contexts, change the identity's home, proxy, region, viewport or timezone. |
| | Turn on recording, CAPTCHA solving, keepAlive, Verified, the server cache or any extension. |
| | Call the Browserbase REST API or SDK directly, or Hermes' built-in Browserbase provider. |
| | List, release or touch sessions, tagged or not. Bulk release is never allowed. |
| | Use Browserbase Agents, Functions, Search, Fetch, Model Gateway or Web Bot Auth. |
| | Type credentials, solve CAPTCHAs, or bypass a login wall on a client account. |
| | Keep a session open past its lease, or run a second session on a Context. |
| | Move a client's login to another home or copy a Context's contents anywhere. |

fleetd enforces all of it server-side. The trial allows every tool on a connected server (D1, HP-5), so the fleet cannot rely on the trial's own gate.

### 15.3 Who may change its configuration

Only the **owner** (Justin, or a role he names; the trial's owner role is **Q-11**). Specifically:

| Change | Rule |
|---|---|
| Browserbase account, plan, projects, API keys, key rotation | Owner only. Keys live in fleetd's secret store, never exported host-wide, never in a profile's `.env`. |
| Choosing `home: browserbase` for an identity, and recording the reason | Owner only, at creation (section 8). |
| Creating or deleting a Context | Owner only. |
| Proxy assignment, region, viewport, timezone | Owner only, at creation. Changing one means a new identity (D3). Rotating the credential of the same IP is the one in-place change. |
| Enabling recording, CAPTCHA solving, keepAlive, Verified, `allowedDomains`, the server cache | Owner only, per identity, with the reason written down. Recording needs Q-07. |
| A pin change or the smoke test | Owner approves; the gate in 15.1 applies. |
| Spend caps | Owner only. **[pending Q-06]** |
| Corpus refresh | Anyone may refresh it. Changing what the fleet does because of a page diff is the owner's call. |

fleetd operators apply what the identity record says and nothing else.

### 15.4 Soul

**Browserbase is a rented room that can lock us out for any or no reason: we enter it only for a measured, functional reason and never to get past a block, bring our own IP, keep every key and record on our side, and never depend on it for anything a human could not log in to again.**
