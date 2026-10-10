# Browser Fleet: decision record

Status: **verified draft, 2026-10-10; revised the same day after the scenario stress tests; Justin's answers recorded the same day (next section)**
(`research/scenarios/S01.md` to `S14.md`; every change is listed with its gap id in "Revisions" at the end).
Every decision links its evidence. All eleven dossiers were
adversarially re-checked (`research/verification/<topic>.md`), cross-checked for contradictions
(`research/verification/CONSISTENCY.md`, items C-xx / O-xx / Q-xx), and the original Gemini
conversation was audited claim by claim (`research/verification/GEMINI-AUDIT.md`: 124 claims, 33
confirmed, 48 partly right, 26 wrong, 17 unverifiable). Items marked **[Justin]** need his call; they
are collected at the end. Nothing in the fleet is built; every decision below describes a target.

Most hands-on evidence comes from arm64 Docker on the maintainer's Mac or local Chrome, with
small samples. DigitalOcean droplets are amd64. **Every measured number here is re-measured on a
droplet in M1** before it is relied on (O-17).

## Justin's answers, 2026-10-10 (these override anything below that disagrees)

| Q | His answer | What it means now |
|---|---|---|
| Q-12 | "Yes you can use a cap droplet to test it." | One test droplet, `s-8vcpu-32gb-amd` (~$0.25/hour), tagged `fleet-test`, total ceiling $25, destroyed after testing unless he says keep it. Created with the same deploy script a Hermes agent will use. The live box and every other droplet in the account are not touched. |
| Q-01 | "I would say API. I don't know, to be honest." | **API-first, tentative.** The box does logins, open-web research and no-API gaps. Posting to Facebook, Instagram or TikTok goes through their APIs, which need the developer-app approvals of Q-06 (still open). |
| Q-15 | "No ... why would you have a default small driver versus Stagehand?" | **D18 is reversed.** Stagehand v4 is the main engine on every identity, Browser-Use the backup. No third executor is built. The extension-detection concern becomes one measured test on the droplet; if it bites on a logged-in site, browser-box's existing pure-CDP `act` (Jev) is the fallback. |
| Q-09 | "You can put it on the public repo right now." | `fleet/` may be public through box-kit's export (PR to browser-box `main`, then export). The scraped vendor docs (`research/corpus/` raw pages, spike screenshots) are **not** published: they are not ours to redistribute. Their MANIFEST/INDEX files (URLs) stay. browser-box itself stays private. |
| Q-08 | "I don't know about running Chrome as root ... it needs to all be on one box." | Decided for him: one Steel container per identity, so a Chrome exploit reaches one login, not all. Non-root with the sandbox on is tried on the droplet; if Steel's image cannot do it cheaply, the per-container isolation is the control, recorded with the measurement. |
| Scope | "It needs to all be on one box ... 10, 20, 50 browsers ... open source so I'm only paying for the droplet ... enterprise is not our use case right now." | **v0 is one box.** browser-box grows from one browser to one browser per identity (10-50), each with its own Steel container, profile volume, guard and lane. Hermes profiles (10-20) each get a token mapped to their identity. Browserbase, multi-node scheduling, the fleet control plane of ARCHITECTURE.md and the 1,000-identity costs are **out of scope**; those files stay as the long-range reference. Charter invariant 3 ("one browser, one lane") becomes "one browser and one lane per identity". |

**Second round, same day (supersedes the Q-01 row above):**

| Topic | His answer | What it means now |
|


---

Vocabulary used everywhere in `fleet/`:

| Word | Meaning |
|---|---|
| **fleet** | This subsystem: one shared service plus browser hosts, serving many Hermes profiles. |
| **fleetd** | The one shared fleet service (control plane): API doors, registry, leases, scheduler, ledgers. |
| **profile** | A Hermes agent profile (the caller). Holds only a scoped token. |
| **account** | The durable, client-facing thing an agent works on: one platform account (or one `research` lane), with its alias, API connection, bindings, manifests, effect ledger, caps and schedules. It survives a change of IP or infra home. Agents name it by alias; the tool argument is still called `identity`. |
| **identity** | One account's persistent browser self, also called a **device generation**: state + IP + persona + infra home. **An identity serves exactly one account**, so a client needing a browser on two platforms gets two identities and two IPs (how Meta treats linked Facebook and Instagram logins from two IPs is unresearched). An account has zero or one active identity (an API-only account has none). A new IP or infra home creates the next generation under the same account. A profile may be bound to several accounts. |
| **wake / sleep** | Start a browser for an identity from its stored state / flush and store state, stop the browser. |
| **channel** | How an action reaches a platform: `api` (official API) or `browser`. |
| **procedure** | A named, versioned, digest-pinned sequence of steps (e.g. `x.reply_to_mention`), with an authority and a verifier. |
| **System 1** | Decision models (Jev, Clef, Perplexity Decider, OpenAI Decisions): choose / yes-no / score. Never write text. |
| **System 2** | Hermes' own reasoning, plus the tool's reasoning model (GLM 5.3 Flash) for grounding, extraction and repair. |

---

## D1. One shared service, not 1,000 copies

**Decision.** One shared service (`fleetd`) with two doors that run the same handlers: remote MCP
(streamable HTTP) and HTTP/JSON with an OpenAPI spec. Each Hermes profile gets the same MCP config
entry, `Authorization: Bearer ${BROWSER_FLEET_TOKEN}`, with the token in that profile's own `.env`.
Skills ship as one read-only shared directory per host, attached with `skills.external_dirs`. An
optional thin Hermes plugin writes evidence into the profile's Obsidian vault.

**Why.** Hermes resolves `${VAR}` per profile and, at pins `09681e7` and current main, fails closed
when it is missing (tested: p1 sent token A, p2 token B, p3 refused). Shared external skill dirs show
up for every profile. It is the only no-code-change route into the Jev Workforce trial.
Evidence: `research/dossiers/hermes-packaging.md` §1; `research/verification/hermes-packaging.md`.

**Rules from verification.**
- **Pin skew.** The hands-on ran at Hermes `09681e7`, 4,595 commits behind main; verifiers re-read
  the relevant paths at main (unchanged except a shadow warning). At some older Hermes pins an
  unset `${VAR}` is sent **literally** as the bearer, so fleetd rejects any token that looks like
  `${...}` (HP-1).
- `BROWSER_FLEET_TOKEN` is never exported host-wide: when a secret scope is bound, a missing variable
  can fall through to the process environment (HP-1, X-3).
- A same-named local skill silently shadows the shared one: skills are named `fleet-*` and a drift
  scan runs on every host (HP-3).
- **Skill releases are versioned paths, not a flipped symlink.** Hermes resolves `current` and caches
  the resolved path; long-lived gateways keep the old release until restart or until the profile's
  `config.yaml` changes. Each release writes `.../skills/releases/<semver>` into each profile config
  **and** rolls gateways (both, because a long-lived gateway does not pick up the new path on its own; `hermes/README.md` section 3.3); old release dirs stay until every process has recycled. fleetd enforces a
  minimum skill version per token (X-1).
- **Design to a 90 s tool timeout.** The trial writes 90 s (connect 20 s) for added MCP servers; the
  Hermes default is 300 s. Everything longer than a few seconds, including `wake`, is
  submit-then-poll (C-15, HP-5).
- Every write tool is idempotent and not marked `readOnlyHint` (Hermes replays only read-only tools
  after a session expiry and returns `outcome_uncertain` for others) (HP-8).
- New profiles connect MCP servers eagerly at boot; `lazy: true` helps only from the second boot (X-2).
- **Hosts that cannot load plugins (for example the Jev Workforce host):** the owner connects the fleet
  as an MCP server through the host's own integration route (HTTPS) and approves short prose guides.
  Guides carry no executable authority. A host may allow every tool on a connected server, so fleetd
  enforces scopes itself (HP-5). **[Justin] Q-11.**

## D2. Channels: official API first, browser for the gaps **[Justin]**

**Decision (recommended).** For client social accounts, publishing, comment moderation, inbound-DM
replies and analytics go through official APIs (Meta Graph for Pages / Instagram professional /
Messenger, TikTok API for Business, LinkedIn Community Management, X API v2). The browser fleet is
for: (1) human login, re-auth and checkpoints; (2) open-web lead generation; (3) the narrow no-API set
in the table below (Facebook Groups and a few UI-only features), each action human-approved, low
volume, with the client's written risk acceptance; (4) sites with no API, and visual QA of clients'
own public pages. **The table below is the whole list.** The earlier wording ("personal profiles" in
the no-API set) is withdrawn (see the table and Revisions).

**Why.** X's developer rules say non-API automation leads to permanent suspension. LinkedIn bans bots
that post, comment or message. Meta's Terms §3.2 bar automated access and collection "without our
prior permission" (a scraping clause with a permission carve-out; the firmer basis is Meta's
Community Guidelines, which require an authorized route for scripted account use). TikTok bans
automated extraction and bypass tools and sanctions its Accounts API for posting. The API path is
sanctioned, cheaper and deterministic. The API-first conclusion survives the verifier's narrowing
of the Meta wording (SP-2).
Evidence: `research/dossiers/social-platforms.md` §1 + decision table Q6;
`research/verification/social-platforms.md`; `antidetect-proxies.md` §1.9.

**Allowed browser uses: platform × use × who clicks × risk acceptance.** One table. `identity create`
(ARCHITECTURE §4.15) refuses any row that is not in it, and the policy gate (ARCHITECTURE §2.1 C18) refuses
agent browsing on hosts the table does not allow. Adding a row is a change to this file, not a setting.
Sources: `docs/channels/social-channels.md` §5-§6, `CHARTER.md` red lines, `research/verification/social-platforms.md` SP-1, SP-8.

| # | Platform | Use | Who acts | Written risk acceptance | Browser identity? |
|---|---|---|---|---|---|
| 1 | Facebook Page, Instagram professional, TikTok business, LinkedIn Page | Publish, comment, reply, moderate, analytics | The API (OAuth done by the client in their own browser) | n/a | **No.** `identity create` refuses a browser identity whose only purpose is this row |
| 2 | Facebook Groups | Post or moderate (no API since 2024-04-22, SP-7) | **A person** (`human_clicks`). `agent_clicks` only when the owner sets it on that identity, and then a per-action approval every time | Required | Yes. Which account type may act in a group is **not researched**: a Group session may be a personal-profile session (inference). Until Justin answers (ARCHITECTURE AQ-10) the acting `account_kind` must be `page` or `business`; `profile` is refused |
| 3 | Facebook personal profile | Anything | **A person, on their own device.** The fleet may draft (`draft_for_human`) | n/a | **No.** Terms §3.1 bars giving others access to the account (SC §6). This withdraws the old D2 wording |
| 4 | Instagram personal account | Anything | Convert to a professional account (free), then row 1. Until converted: `draft_for_human` | n/a | **No** |
| 5 | Page, professional or TikTok business account | UI-only creative features with no API (story stickers, licensed music, TikTok stories and LIVE) | **A person** (`human_clicks`), low volume | Required | Yes |
| 6 | LinkedIn | Any action by browser (connection requests, DMs, InMail, groups) | **A person, in their own session.** Posts and comments go through the API; the fleet drafts the rest (`draft_for_human`) | n/a | **No.** Charter red line |
| 7 | X (x.com) | Any agent browser | Nobody. A person who must use x.com uses their own device | n/a | **No.** Charter red line; SP-1. No exception row exists |
| 8 | Open web (not a platform host) | Lead generation, sites with no API, visual QA of a client's own public pages | An agent, read-only, no login, no form submit | n/a (live runs on company sites wait for MILESTONES N-4) | Yes, kind `research` |
| 9 | Any row above that has a browser identity | Login, re-auth, checkpoint | **A person in the viewer** | n/a (no effect) | Not a reason to create one |
| 10 | Facebook Page, Instagram professional, TikTok business **[pending Q-01 = browser-first]** | Post, comment, reply by browser | Per client with a signed acceptance. A person by default; per-action approval. Whether a manifest may authorize browser effects is a Q-01 sub-question (ARCHITECTURE §8.4) | Required | Yes, only for clients who signed |

`draft_for_human` is a result, not an action: the fleet writes a draft into `approvals` and a person sends it
from their own session. It never creates a browser identity.

**Inbound and recipients are refused in code, not by prompt.** A reply or DM goes only to a conversation
that the fleet's own inbound store shows the other party started, inside the platform's window, not opted out
(ARCHITECTURE §2.1 C19, §4.12). Red-line effect kinds (like, follow, unfollow, repost, cold DM) return the
non-retryable code `refused` (D17) and never create an approval. A policy gate ahead of every tool call enforces
host rules (x.com, LinkedIn, people-listing pages, social hosts for `research` identities)
(ARCHITECTURE §2.1 C18).

**Never built (any channel):** cold/outbound DMs, automated likes/follows/engagement, identical posts
across client accounts, AI auto-replies on X without X's approval, fake accounts, ban evasion,
scraping platforms for lead data, competitive benchmarking on X (prohibited).

**Constraints the connector layer and governor must carry** (dated; re-check at build time):
- **X:** build the rate governor from live `x-rate-limit-*` response headers, not constants. The
  "10,000 posts / 1,440 DMs per app per day, shared by all clients" figures are legacy Pro-plan
  columns and unproven for pay-per-use (SP-3). Per-account limits bind first for unverified client
  accounts: 50 original posts + 200 replies/day, 500 DMs/day, 400 follows/day, API use included
  (V-2). Pay-per-use fees: $0.015/post, $0.20/post with a URL, $0.015/DM, $0.010 summoned post,
  webhook events billed. API-driven automated accounts must carry X's "Automated" label, name the
  operator in the bio and link a human-managed account; whether human-approved scheduled brand
  posting counts is unresolved (V-8). **[Justin] Q-05.**
- **LinkedIn:** CM API version 202510 sunsets 2026-10-15; Development tier 500 calls/app/day,
  100/member/day (V-3).
- **Meta:** Messenger 24 h window, 7-day human-agent window, 30 s bot-response rule; Instagram 100 API
  posts/24 h; Facebook Reels 30 per Page per 24 h (V-5, SP-5). System-user tokens (assets in a
  Business Manager) and per-client OAuth are different onboarding models; pick per client.
- **TikTok:** Accounts API access form (mandatory since 2026-03-20); the Content Posting API audit
  rejects internal "upload for accounts you manage" tools and wants wide-audience clients, so an
  agency fleet may face the same test (SP-11); Business Messaging is open beta, unavailable in
  EEA/CH/UK, with privacy reviews (V-4).
- **Facebook Groups:** the API removal is cited from forward-looking changelog text and vendor
  corroboration (SP-7).

**Consent-based lead channels** are added as first-class options: Meta Lead Ads, opt-in DM capture,
LinkedIn Lead Gen Forms, TikTok instant forms (SP-11). **[Justin] Q-14.**

**Consequences.** One developer app per platform (Justin's business), authorized by each client; app
approvals are milestone dependencies (**[Justin] Q-06**). Most identities need **no** browser for
social work, which shrinks browser hours (D12).

## D3. Identity is pinned at creation and never drifts

**Decision.** An **identity** (the browser self, one device generation) fixes, at creation: infra home
(`steel-oss` default, `browserbase` opt-in), one dedicated static ISP IP (never shared, never rotated),
a persona, and where its state bundle lives. Every wake applies and checks the same values; the
forwarder keeps checking during the session (D10). A mismatch refuses the wake or stops the session.
**A new IP or a new infra home means a new device generation: a new identity record with a fresh human
login and no restored browser state, under the same account record** (see the vocabulary table).
What must be fresh: login, cookies and bundle, persona re-derivation, the canary. What stays with the
account: the platform account itself (tenant, platform, handle), API connection, alias, bindings,
manifests and approvals (re-pointed, see ARCHITECTURE §3.10), effect ledger, governor caps and
consents. The effect key and the governor key on the account, not on the identity (D13, D12).
**Region rule for the replacement:** the new IP is in the same country and, where the vendor offers it,
the same city or metro as the client's region and the old IP, so the platform sees a device change and
not also a change of place (inference from `docs/identity/identity-and-proxies.md` §2.6; no vendor
measurement). Revisions: S07-5, S07-6, G10-3.

**What "persona" can pin today, and what it cannot** (STE-10, C-02):
- **Pinned now (no fork):** user agent (matching the real Chromium version), timezone, locale,
  viewport — through Steel's session fields with fingerprint injection off, plus process env.
  The persona record also pins `executor_id` and `extension_mode` (D18): changing either is a persona
  change and goes through the canary rule, never per wake (S14-7).
- **On a Browserbase home the persona is per-home.** Browserbase chooses UA, OS, locale and hardware, and
  whether the fingerprint is stable per Context is unknown (`dossiers/browserbase.md` §3.6, §12 items 7
  and 20). The persona hash for that home covers timezone, viewport, region and exit IP only; the observed
  UA and languages are logged as telemetry. Continuity of the fingerprint is traded away on that home (D11;
  G10-5).
- **Not yet pinned, host-real and identical across identities on one node:** CPU core count, GPU /
  WebGL renderer, canvas hash, screen size (Steel reports 800x600), UA-CH brands; the injected mode
  even showed a UA/platform arch mismatch. Pinning these per identity needs a CDP-injection layer in
  the node agent or a patched browser, measured in M1 (O-01).
- **Until per-identity hardware values exist, identities of different clients do not share a node**
  (cross-client linkability), at a cost of ~7 identities per node (D12). **[Justin] decides whether
  cross-client unlinkability is required (O-01).** The unit that must not share is the **tenant**,
  at the same time and in sequence: between two tenants a node is destroyed, or its volumes, tmpfs and
  Docker image layers that held client data are deleted (S09-12).
- **This premise is a fork, not a fact (S09-1).** It assumes the host-real values (canvas hash, core
  count, GPU string) differ between nodes of the same size. Nobody has measured that
  (`research/verification/CONSISTENCY.md` C-02 says the values are host-real; `docs/engines/steel.md`
  §8.5 leaves open whether they differ across droplets). Two outcomes, decided by one M1 measurement
  (ARCHITECTURE §7.7): (a) **equal across droplets:** every node looks the same, linkability exists on
  every node, and one client per node buys nothing. Q-13 and this rule are reopened, and the options are
  per-identity hardware values (Q-04) or a written, accepted linkability risk. (b) **different across
  droplets:** an identity that wakes on another node changes hardware, which is the drift this decision
  forbids. Identities are pinned to a **node class** (size, image, CPU model), failover stays inside the
  class, and the autoscaler respects it. Until measured, the one-client-per-node default stands and
  nothing in ARCHITECTURE depends on which branch is true except the placer filter (§7.2).

**Why.** OSS Steel re-randomizes its fingerprint on every launch and its stealth output is internally
inconsistent; Browserbase cannot pin a fingerprint below Scale and has no sticky IP of its own.
Evidence: `research/dossiers/steel.md` §1.6; `scale-infra.md` §1.4; `antidetect-proxies.md`
§1.1-1.2; `browserbase.md` BB-1..BB-3; `verification/steel.md` STE-10; `CONSISTENCY.md` C-01, C-02.

## D4. Browser host: OSS Steel, one container per awake identity, wrapped

**Decision.** Self-hosted `steel-browser` (pinned digest) inside a wrapper image (`steel-profile`) run
by a node agent. Steel REST/CDP/viewer have no authentication, so only the node agent reaches a
container, on a per-identity Docker network; the raw CDP port 9223 is never published (Steel's own
quick starts publish it). browser-box's in-browser `Guard` runs once per awake browser.

**Wrapper rules (measured; `research/dossiers/steel.md` §1, `spikes/steel/RESULTS.md`):**
- **One session per container**, enforced by the node agent: a second `POST /v1/sessions` silently
  took over the live browser; `GET /v1/sessions/{id}` then returns a fabricated `released` stub and
  the list drops it. Ownership truth lives in fleetd's lease, plus a live-argv/CDP probe.
- **Health is never Steel's HTTP status.** `/v1/health` is structurally always `ok`, and a failed
  launch can answer 200 on the old browser. Health = the live Chromium's `--user-data-dir` is this
  identity's, plus the per-site login probe passes, after every launch.
- **Profile volume** at `/app/api/user-data-dir` (Steel ignores any per-session `userDataDir`).
  Delete `Singleton*` under the identity's lease before start (preferred over a fixed hostname, which
  can still SIGKILL a colliding live PID). Run with `--init` (8 cycles left 151 zombies without it).
  Never `docker stop` a live identity (it is a SIGKILL that leaves the lock).
- **Safe release, empirical order (worked once, n=1):** export the session context (instant cookie
  journal, incl. httpOnly) → wait ≥ 31 s since the last cookie change (Chromium commits cookies on a
  30 s timer, re-armed by every cookie write; no CDP flush) → CDP `Browser.close` (Steel's own release
  left `Singleton*` 6/6 in persist mode; `Browser.close` left none 3/3) → Steel release → snapshot the
  bundle. Social pages rotate cookies constantly, so the **context export is the source of truth for
  cookies** and the tarball for everything else; M1 tests a graceful flush (C-03, BRO-6).
- **Persistence unit = the user-data-dir tarball**, encrypted at the bundle layer (Chromium's cookie
  store uses a fixed `v10` key under `--password-store=basic`). Context export/import round-trips
  cookies; localStorage needs key rewriting; IndexedDB results disagree (steel vs scale-infra) — M1.
- **Persona application:** Steel fingerprint injection off; UA, timezone, viewport via session fields;
  locale via `LANG`/`LANGUAGE` plus `--accept-lang` (Chromium's `--lang` does not work on Linux,
  antidetect V-1). WebGL: headful and headless both lacked WebGL until explicit SwiftShader flags were
  set; headful also needs Xvfb and dbus (C-11). Always pass `timezone` (with the proxy down it fell
  back to UTC).
- **Proxy credentials never reach Steel** (it echoes the credentialed upstream URL over its
  unauthenticated API): Steel gets only `http://127.0.0.1:<port>` of the node forwarder (D10). With a
  loopback forwarder `PROXY_INTERNAL_BYPASS` stays empty (C-08, unverified until a droplet run).
- **Security posture to fix or accept:** Steel's Chromium runs as root with `--no-sandbox
  --disable-setuid-sandbox --no-zygote` and site isolation disabled. **[Justin] Q-08:** run non-root
  with the sandbox back on (work, may need capabilities), or accept the risk in writing. Block the
  DigitalOcean metadata endpoint from the container (O-11).
- **Viewer for human login:** typed printable text and popups work through
  `/v1/sessions/debug?interactive=true`; modifiers are not forwarded, paste needs
  `clipboardBridge=true`; Enter/Backspace/Tab/arrows, IME, passkeys, native dialogs, HTTP auth and
  file pickers are **untested** (M1 gate). fleetd proxies it: a ticket is exchanged once for a viewer
  session, which survives a page reload and is gated by operator sign-in (D14). The viewer is open to the
  identity's platform hosts and their login providers only; anything else is blocked and logged (G12-14).
  The URL is never given to the agent (D14).
- **Who owns the network namespace.** A small holder container owns the identity's namespace and
  hostname. Steel, the forwarder and the runtime join it (`docs/infra/steel-profile.md` §2.2, §6.1,
  topology T-L; ARCHITECTURE §2.2). So the forwarder can be up and checked before Steel exists, which
  is what the research `http_only` mode needs (S04-4, S13-6).
- **Two image flavors, set by identity kind** (`docs/infra/steel-profile.md` §2): `account` images carry
  no Stagehand extension, none of its launch flags and a filtered `--remote-allow-origins`; `research`
  images keep the extension (mode A). `extension_mode` is part of the persona and is never chosen per
  wake (S14-4, S14-7; D18).
- **Upstream is not a plan.** #348 (userDataDir), #375 (singleton guard) and #235 (API auth) are
  outsider PRs/requests with no maintainer owner. The fleet carries its own takeover guard,
  auth-by-isolation, profile handling and persona work (C-24).

**Escape hatch, taken seriously.** Because the fleet already carries most of the hard parts itself,
plain Chromium + a small session API is a real alternative. M1 measures both on a droplet and writes
the winner into this decision (C-24).

**Steel Cloud** would add a Profiles API (300 MB cap, deleted after 30 days unused), concurrency and
CAPTCHA solving, but its ToS forbids using it to "violate any website's terms of service"; its
stealth browser is Enterprise-only. Self-hosted Apache-2.0 has no AUP.

## D5. The action ladder (System 1 first)

Every browser step climbs this ladder and stops at the first rung that succeeds:

| Rung | What runs | Model calls |
|---|---|---|
| L0 | Deterministic code or an official API call | 0 |
| L1 | Fleet replay cache: a stored Action, re-verified on element identity before acting | 0 |
| L2 | System 1 decider picks among candidates built from a fresh page snapshot; executor acts | 1 decision |
| L3 | A generative choice among structured candidates, run by the identity's executor (D18). Stagehand v4 `act` / `observe` / `extract` for `research` identities; the fleet's L3-lite for `account` identities | 1 generative |
| L4 | Browser-Use agent loop for an open-ended goal (read-mostly by default) | many generative |
| L5 | Human (live viewer) for login/checkpoint/approval; Hermes for planning and writing | n/a |

Rules:
- Irreversible actions (post, send, reply, DM, delete, pay, follow, submit) are gated by deterministic
  policy and approved manifests (D13), never by a model probability — on every rung, including
  free-form `act` and `task`.
- Below a decider's per-template threshold: abstain and climb, never guess.
- **The replay cache stores Actions, not instructions.** An L3 `observe` result becomes a stored
  `Action` (method, arguments, selector) keyed by procedure step + URL pattern + a DOM fingerprint,
  replayed through `act(Action)`. Snapshot and observe xpaths are **positional**: before every
  replayed or decided act, re-snapshot and verify the target's role and accessible name. A mismatch is
  a miss, never a click.
- On the decider path `selfHeal` stays **false** (with it on, a failed `act(Action)` silently calls
  the model). Browser-Use `rerun_history` is **not** a zero-call tier (it always ends with a summary
  LLM call) (C-07).
- A rung that succeeds on a new page becomes a candidate L1 step, released by D13's rules.
- **Effect steps stop at L1 (S06-1).** For any step with `effect != none` the ladder may not climb past
  L1 into a free-form click. Every such step carries a mandatory `target_rule` (role, name pattern,
  region or frame) in its released procedure (ARCHITECTURE §3.7). L2 candidates are pre-filtered by it
  and an L3 `observe` is constrained to it. No match: abstain and stop (`needs_human`, and the step is
  suspect), never climb to a free-form click. A repair of an effect step is a **rehearsal** (observe
  without act, in `mode: draft`) on an owner-owned canary account of the same UI variant. It yields a
  candidate with an annotated screenshot, and a person confirms it before the first live click. The
  pre-submit check also reads the approved audience, visibility and attachments from the DOM
  (ARCHITECTURE §4.7). This narrows "stops at the first rung that succeeds" for effect steps only and
  keeps D5 consistent with the Charter's "never by a model probability".
- **Assent is not dismissal (S06-8).** A blocker is either *dismissable* (a pure UI notice) or *assent*
  (terms, age gate, permission request, identity confirmation, payment or boost upsell). Assent goes to
  `needs_human` and is never an L3 target. L3 clicks on controls named accept, agree, allow, confirm or
  continue are denied unless the released step names them.
- **Login affordances are denied on every rung (S05-2).** A deterministic deny-list covers any control
  whose accessible name or role matches log in, sign in, continue as, or use another account, and any
  credential or OTP field. It applies to L2, L3 (`act`, `observe`, `extract`) and L4 (`task`). A blocker
  check runs after every navigation and before every executor command, ahead of the ladder. A positive
  result goes to the pause, never to L2 or L3 (ARCHITECTURE §4.3).
- **Which rungs exist depends on `data_class` (S06-7).** Under the Q-07 default L2 is closed on
  logged-in pages (`docs/models/system1.md` §3.6 rule 5), and every model is closed on DM surfaces
  (`docs/engines/stagehand.md` §6.2). So on a logged-in page a UI change goes L1, then L3-lite (D18)
  where a (provider, host) pair is cleared, else to a person; on a DM surface it goes to a person. The
  System-1 share for logged-in procedures is **L0 plus L1 only** until a (provider, host) pair is cleared.
  The per-class table is ARCHITECTURE §4.3. Repairs run on owner-owned canary accounts so that client
  pages are not sent to a model.
- **L3 is a model choice, not an engine (D18).** Stagehand is the L3 engine for `research` identities.
  For `account` identities L3 is the fleet's own L3-lite, run by the identity's executor.

**Why.** Stagehand v4 has no local cache and no `agent()` (its cache is Browserbase-server-only); v3's
cache replayed a wrong click with `success:true`. Both frameworks execute a chosen element with zero
model calls (Stagehand `page.snapshot()` → `act(Action)` with `selfHeal:false`; Browser-Use
`selector_map` → `Tools.act`). The Stagehand spike chose elements with a hardcoded rule, so decider
latency/accuracy there is unmeasured; the Browser-Use spike used real Jev (Poetry out of 71, 0.94-0.96,
315-388 ms) on one easy page.

**Unmeasured gates (M1/M3):** `act(Action)` replay across iframes and shadow DOM on Steel;
`Tools.act` against a live Steel session; element-choice accuracy on dense social pages.
Evidence: `research/dossiers/stagehand.md` §1.3-1.6; `browser-use.md` §1.2, §1.5; `system1-models.md`
§1; `verification/stagehand.md` SH-2/SH-3; `verification/system1-models.md` V-12.

## D6. Engines: Stagehand v4 for scoped steps and extraction, Browser-Use as the explorer

**Decision.**
- **Stagehand 4.2.0** (pinned) is the main engine for scoped steps and extraction (L3, and the L2
  executor where measurement allows). Its runtime is an MV3 extension inside the browser; on Steel
  each session needs the extension mounted in the container, `{"extensions":["stagehand"]}` on create
  (shown necessary for headless Steel), and a CDP URL reachable from inside the browser. It relies on
  Steel's launch flags (`--remote-allow-origins`, the `DisableLoadExtensionCommandLineSwitch` feature
  override) — both in the upgrade smoke test. Every model call goes through the client callback
  (`model: {generate}`): keys stay in fleet workers, prompts do not leave through the identity's IP,
  and OpenRouter is reachable (`ModelConfig` has no `baseURL`; with no model set on Browserbase it
  would use Browserbase's `auto` gateway).
- **Detectability is measured, not open** (AP-2, n=1 per condition): Stagehand v4's extension trips a
  public `isAutomatedWithCDP` check and stays resident after `close()` until `Extensions.uninstall` or
  a browser restart. Browser-Use attach/navigate did not trip it; its actor API and coordinate click
  do. Whether platforms weight this signal is unknown. So the **L1/L2 executor for logged-in
  identities is decided in M1**: Stagehand v4 (with uninstall-after-session), Browser-Use `Tools.act`,
  or a minimal CDP executor; the winner per site class goes into the router (O-02). **Amended by
  D18 (S14-8):** the rule is per identity kind. `account` identities use the minimal executor unless
  gate G1.4 shows otherwise (no extension on those images); `research` identities may use Stagehand with
  the extension. The per-site-class override stays an M1 result.
- **Stagehand operations:** one instance per browser; the instance lock is released only by an
  explicit `close` RPC, so a crashed worker can wedge the browser (recover by recreating the session).
  On Browserbase, `browser.close()` releases the session even with `keep_alive`: the login broker
  never calls it between steps. Large uploads use Steel's files API.
- **Browser-Use 0.13.x** (pinned, version self-check) is the backup engine for open-ended goals (L4):
  attach by `cdp_url`, `flash_mode`, capped `max_steps`, `exclude_actions` for uploads/PDF,
  `highlight_elements=False` (default injects an overlay into the page), proxy only on the Steel
  session (proxy credentials in Browser-Use turn on request interception), cleanup of its per-session
  temp dir, one agent per OS process with a hard kill timer. `allowed_domains` is not a boundary.
- **Stagehand v3 is not a dependency** (maintenance limbo; 5 npm advisories, 2 high; its agent cache
  replays stale extract answers).
Evidence: `stagehand.md` §1; `browser-use.md` §1; `antidetect-proxies.md` §1.3-1.4;
`verification/{stagehand,browser-use,antidetect-proxies}.md`; `CONSISTENCY.md` C-13.

## D7. System 1 models

**Decision.** A central `/decide` service inside fleetd fronts all decision models: one request shape
(the TypeSafe `systemone` family: `state` + named `noul` / `choice` / `score` questions; real endpoint
`POST https://api.typesafe.ai/v1/systemone`), provider adapters, a client-side token- and request-rate
limiter, question packing, per-template thresholds, escalation and calibration logs.
- **Jev** (TypeSafe): default for text-state questions. Text only. 139-329 ms direct; production-path
  medians in earlier projects were 443-487 ms.
- **Perplexity Decider:** screenshot questions (verified through OpenRouter: 271 ms). Open weights.
- **Clef:** screenshot questions **once tested** — Clef image calls through OpenRouter are untested and
  OpenRouter's alpha decisions request has no `images[]` field (S1-02). Open weights; silently
  truncates long text state.
- **OpenAI Decisions:** optional; closed weights, public beta; option cap unstated.
- OpenRouter exposes them behind one key (`/api/v1/systemone`, `/api/alpha/decisions`); provider
  pinning works on both. **Pin and log the serving provider.**

**Verified constraints:**
- **Token caps bind first.** Jev: 80 rps but 100K tokens/s (requests up 4x, tokens down 60% between
  2026-09-17 and 2026-10-10; "dynamic"). A 180-candidate step is ~4.9-6.2K tokens → ~16-20 steps/s.
  Perplexity: 10 rps per org plus a token limit. Clef ~300 rpm is an **assumption** (inferred from a
  page that predates Clef). OpenAI publishes Build 2M TPM (~5 steps/s), Launch 10M (~27), Grow 180M;
  whether those apply to Decisions is unconfirmed. Plan spillover across providers even at a 10% duty
  cycle; prune candidates well below the cap.
- **Option cap:** 255 is the hard limit for Jev/Clef/Perplexity (256 → HTTP 400); 180 is a working
  step size, not a provider limit (C-06).
- **No rate-limit headers** from Jev or OpenRouter on decision calls: limiting is client-side.
- **Option-order bias:** Jev leans to the first option; shuffle candidates or ask in both orders on
  low-margin steps.
- **Confidence is not portable.** It means different things per provider (Clef-flash top probability
  0.69 vs confidence 0.43; Jev 0.92/0.91; OpenAI 0.79/0.76) and per serving host (same weights 0.43 vs
  0.74). Thresholds are set per template × model × provider.
- **Modality enforced by the router** (Jev silently accepts images and bills them as text). Missing,
  unknown or refusal answers escalate. Jev context: 32K (guide prose) vs 64K (catalog) — use 32K.

**The 90% target is a hypothesis we measure (O-15).** Metric: *System-1 share* = actions completed
without a generative call (L0 + L1 + L2) / all browser actions, per procedure, on a held-out set.
Research estimate (unverified): ≥ 90% plausible for repetitive posting-style procedures, ~30-60%
decider-only overall, well below 90% for lead-gen research. Nothing measured supports 90% yet.
Evidence: `research/dossiers/system1-models.md` §1; `verification/system1-models.md` S1-02, S1-03,
S1-08, V-04; `existing-assets.md` §1.5.

## D8. Reasoning model

**Decision.** `z-ai/glm-5.3-flash` at `reasoning.effort = "low"` (reasoning is mandatory; unset means
max — the "~40 s per step" figure is from browser-box and was not re-measured) is the default for
Stagehand L3 and Browser-Use L4, behind a client shim every model call goes through:
- always `require_parameters`; validate every response against the full schema including patterns
  (strict `json_schema` enforcement is provider-dependent: one provider returned wrong shapes 4/4,
  another YAML with HTTP 200);
- a mandatory per-call `max_tokens` cap (runaways ran to 8K tokens, 34-52 s each);
- retry once on another provider on invalid output, `finish_reason=length`, or a `null` element;
- a **bench-gated provider allowlist** with price and quantization caps (OpenRouter listed 33-38 GLM
  5.3 Flash endpoints on 2026-10-09/10, $0.032-$0.225/M input, several fp4; 22-26 with structured
  outputs);
- lowercase only a click's mouse-button argument, never typed text or key names;
- Browser-Use's `ChatOpenAI` path cannot send `require_parameters`: use `ChatOpenRouter` (0.13.11+)
  or an httpx hook.

Repair ladder: retry GLM on another provider → DeepSeek V4.1 Flash (reasoning off; different failure
mode) → screenshot path with GLM vision. Optional cheap act tier: gpt-oss-120b @low (not extraction).
Do not use for acting: Nemotron 3.5 Lightning (fabricated clicks), Mistral Small 2603 (rate-limited).
Hermes' own model does planning and writing.

**Measured (small samples, local Chrome on a Mac, provider-confounded):** Stagehand act/observe 48/53,
extract 100%, Browser-Use live 6/6 and 9/9 on easy pages, ~$0.001 per uncached act, uncached
Stagehand p50 ≈ 1.7 s. Act defects cluster: 7.5% defects / 7.7% runaways on click acts on a 6K-token
page (Wilson 3-18%), all on two provider/task pairs. A **per-provider benchmark** (`provider.only`,
with and without ZDR) is an M3 gate (O-06). GLM throughput for 100-1,000 agents is unmeasured.

**Data handling [Justin] Q-07:** logged-in client pages (including DMs) go as text or screenshots to
OpenRouter-routed providers and System 1 vendors. 29 GLM endpoints are zero-data-retention listed;
the bench's main provider is not, and one ZDR provider failed schema enforcement every time. Requiring
ZDR changes the allowlist and invalidates the current numbers.
Evidence: `research/dossiers/reasoning-models.md` §1; `verification/reasoning-models.md` REA-3, REA-5,
REA-7, REA-13; `stagehand.md` §1.8.

## D9. Anti-detect: continuity, not evasion **[Justin]**

**Decision (recommended).** No commercial anti-detect browser by default. Each identity gets a
persistent profile, one dedicated static ISP IP, timezone/locale/geo matched to that IP, the same
pinned values at every wake (D3), human-like cadence, and headful (Xvfb) or headless with explicit
SwiftShader. The goal is **device and network continuity for the client's own account**, not evasion
(Meta's terms forbid circumventing technological measures).

Options per identity, chosen at creation after M1 measurement:
- **Honest persona** (default): stock Chromium, no spoofing; hardware values host-real (D3).
- **Per-identity hardware values injected over CDP by the node agent** (no fork; to measure).
- **Seed-pinned patched kernel, e.g. CloakBrowser:** same seed → same fingerprint, clean `toString`
  checks. **It is proprietary** (binary licence; latest major build needs a paid subscription; an
  OEM/SaaS licence may apply if third parties such as client staff reach it through the live viewer;
  it reports licence and concurrent-session telemetry) and it **is spoofing** (V-9). Stagehand v4
  works on a patched kernel only from Chromium ≥ 149 (147-148 gated), with the extension on the host
  filesystem, an in-browser-resolvable CDP URL and an admitting `--remote-allow-origins` (AP-1).
  **[Justin] Q-03, Q-04.**
- **Commercial anti-detect** (Linux + CDP capable: Kameleo, Multilogin X, AdsPower, Octo, DICloak
  agent, Nstbrowser, GoLogin, Dolphin, MoreLogin; Windows/macOS-only Undetectable and Incogniton are
  out): only after a measured failure. Licence cost is 4-30% of the base bill for most vendors, but
  Kameleo is 35-51% at 100-1,000 identities (V-2); integration, lock-in and the vendor holding client
  cookies are the larger costs. Firefox kernels (Stealthfox, Junglefox, Camoufox) cannot be driven by
  Stagehand or Browser-Use. **[Justin] Q-02.**

An earlier private SDR harness states it implements no fingerprint spoofing or proxy rotation. The fleet pins
proxies and personas (continuity); the patched-kernel option would be spoofing. **[Justin] Q-04.**
Evidence: `research/dossiers/antidetect-proxies.md` §1; `verification/antidetect-proxies.md` AP-1,
AP-2, AP-7, V-1, V-2, V-9; `social-platforms.md` §1.9.

## D10. Proxies

**Decision.** Yes. One **dedicated static ISP IP per identity**, bought on a term (about $2.5-3.3 per
IP-month at list, vendor-claim), never shared (e.g. not "shared with up to 3 users"), never rotating
residential for logged-in identities. Mobile dedicated ports (~$117-130/mo) only as a targeted
exception. Bind through a **node-local, credential-less forwarder** that is the container's only
egress (Stagehand's local launch rejects proxy credentials; Steel echoes credentials; Browser-Use's
proxy auth intercepts requests). Pin timezone with the process `TZ`, locale per D4.

**The forwarder fails closed on any exit-IP change, mid-session included.** IPRoyal "sticky" sessions
silently swap the IP unless `_killswitch-1` is set; Bright Data IPs carry a 100 GB/IP fair-use
allowance (antidetect missed issue 8, V-3).

**Proxy vetting rule (O-10):** provenance cannot be read from a vendor name (the seized NetNut pool
was widely resold, AP-7). A new IP is accepted only after: exit-IP match, ASN class (ISP, not
datacenter), reputation checks, geo/timezone match, and a provider statement of sourcing. Fail closed.
Evidence: `antidetect-proxies.md` §1.7-1.8; `scale-infra.md` Q4 inputs; `verification/antidetect-proxies.md`.

## D11. Browserbase: opt-in home per identity, chosen at creation

**Decision.** Browserbase is a paid home an identity can be created on, for a measured reason: **a
functional failure on Steel**, or burst/pilot capacity. Never a block, a restriction or a bot-defence
page. Every Browserbase identity gets a BYO sticky proxy
(`type: "external"`, HTTP/HTTPS only), a CDP timezone override (fragile across reconnects and Live
View; to measure), `recordSession: false`, **`solveCaptchas: false`**, a per-Context lock, a fleet-held
key, and the fleet's own model callback. Hermes' built-in Browserbase provider is not used (it sends no
Context). `identity create` refuses a Browserbase home without a triage record (class B-F) and refuses
`solveCaptchas` other than `false` (Browserbase solves CAPTCHAs on every session by default;
`docs/engines/browserbase.md` §2.6; a solver on a client account is what D14 and the Charter forbid).
- **Functional versus defence (G10-1, G10-13).** "A site where Steel fails" is read as a **functional**
  failure only: Steel cannot render a page or finish a login because a browser capability is missing, or an
  input never reaches the page (`docs/engines/browserbase.md` §8.1, triage classes B-F and B-D). A site
  that is refusing this browser, IP or traffic (challenge page, 403 or 429, "unusual traffic") is class
  B-D and is **not** a reason to move; the fix there is a site cool-down (ARCHITECTURE §4.2 `site_blocked`),
  not a new home. This follows D9 and the Charter red line on circumventing access measures.
- **Continuity is traded away on this home.** Browserbase picks UA, OS, locale and hardware, and no
  document shows the fingerprint is stable per Context (`docs/engines/browserbase.md` §3.6, §12 items 7
  and 20). The persona check on this home covers timezone, viewport, region and exit IP only (D3). The
  owner is told this at creation.
- **BB-O1 (pending Justin):** how the exit-IP pin is enforced on this home. Default: accept the wake-time
  and mid-session checks plus a kill switch; build the edge forwarder (Option F) only if those show swaps
  or leaks (`docs/engines/browserbase.md` §3.6). Not among Justin's questions.
- **BB-O2 (pending Justin, with Q-01):** whether Browserbase's ToS solicitation clause covers a client's own
  authorized posting. Default: on Browserbase-homed identities, DM, comment and reply procedures do not run,
  and `publish` needs the owner's recorded acknowledgement for that identity (`docs/engines/browserbase.md`
  §6).
- **Lock-in:** Contexts cannot be listed, exported or uploaded via API on self-serve plans; suspension
  voids all of them. The fleet snapshots cookies and storage over CDP at session end as a backup.
- Built-in proxies rotate (its own blog recommends static proxies for logged-in sessions): never for
  identities. Non-Verified sessions are always Linux; Verified is Scale-only beta.
- Its ToS forbids "creating multiple accounts to avoid restrictions": no sharding across accounts.
  Per-project keys and concurrency allotments give coarse isolation (e.g. per client group).
- The Stagehand server cache is a weak reason to choose it (hit-count threshold; key includes page
  content and URL; social-feed hit rates likely low).
- The keepAlive plan gate is inconsistent across Browserbase's own docs; verify on the real plan.
  The absence of a public AUP is weak evidence (unknown paths redirect to sign-in).
Evidence: `research/dossiers/browserbase.md`; `verification/browserbase.md` BB-6, BB-10, V-3.

## D12. Control plane, scheduling, scale

**Decision.** Postgres is the source of truth: identities, bindings, leases, placements, the effect
ledger, the spend ledger, audit. A node agent on each droplet starts/stops `steel-profile`
containers; a placer in fleetd assigns wakes to nodes by capacity (and by client, per D3).

**The lease is designed fresh, not copied** (O-03, C-14; an earlier internal job-claim design and
scale-infra's lease SQL are race-unsafe and cannot express takeover):
- DB-enforced uniqueness: at most one active lease per identity (partial unique index or a
  per-identity row lock taken before any read);
- separate `acquire`, `renew` (tied to worker liveness; does not change the fencing token) and
  `takeover` (human preemption, new fencing token) operations;
- the fencing token is checked by the node agent and the executor on every command, not just stored;
- **purposes:** `work`, `reconcile`, `canary`, `reauth`, `human_session`, `observe`, `maintenance`, `system`
  (a pause lease nobody else can claim). `acquire` for `work` also requires: the identity's state is not `needs_reauth`,
  `checkpoint`, `restricted`, `quarantined`, `migrating` or `retired` (S05-1); no hold whose scope covers
  the work (below); and no effect row in `intent` or `uncertain` for the identity (S08-2). Expiry,
  conversion of open intents and the hold happen inside one transaction with `acquire`, so there is no
  window between a lease expiring and the hold existing. Scheduler claims skip such identities and mark
  the job `queued` with reason `identity_state`.
- **Timing (all estimates, to measure in G2.1/G5.x):** lease TTL `L`, renewal every `L/3`, liveness =
  the node agent's heartbeat carrying the fencing token plus a probe of the live worker. The node
  self-fences at `L - max clock skew - margin`. fleetd re-places an identity only after `L + margin` **and**
  a fence confirmation (the node's ack, or the droplet powered off through the provider API). A reconcile
  wake never starts before that. The one effect in flight at the partition stays `uncertain` (S08-3).
  The fencing token fences the next command; the platform sees no token, so an already-authorised click
  can still land. That is why the effect, not the lease, is the unit of doubt.
- **A human lease follows viewer liveness, not worker liveness:** the broker renews it on a heartbeat
  (input-frame counts only, no payload logged) while the viewer socket is open, up to a hard ceiling;
  there is an idle timeout, a visible countdown and an extend button. The scheduler and the idle reaper
  skip an identity with a human lease. fleetd calls `viewer_close` on every token change, so the route
  never outlives the lease (S01-4, G12-1).
- **Holds are rows, not a field (S07-2):** `holds(account, identity, reason, scope, effect_id, since,
  cleared_by)`. Scope is `browser`, `api` or `all`. `proxy_*`, `persona_mismatch` and `upload_failed` are
  browser scope. An `uncertain` effect on the **browser** channel holds scope `all` (a shared session; one
  doubt blocks both channels on that platform). An `uncertain` effect on the **API** channel holds only
  `api` on (account, platform, conversation), because the browser reason does not apply to API effects
  (S03-10, S07-4). Each reason has its own clear rule; clearing one never clears another.
  `proxy_mismatch` is an incident hold that only the owner clears, with preconditions (S07-3);
  `proxy_unavailable` is **not a hold**: it is a retryable wake failure with backoff, a per-vendor circuit
  breaker and one aggregated alert (S07-1).
- **Admission control (S09-4, S09-7):** per-token and per-tenant limits on requests per second, in-flight
  jobs and in-flight wakes (reason `rate_limited`); a weighted fair claim across tenants (the queue is not
  "oldest first" globally); priority classes for operator queues: security (checkpoint, reauth), then
  approvals, then reconcile; a per-tenant share of every platform app window (weight, floor, burst) with
  per-tenant and per-platform kill switches. Numbers are estimates to set from G2.1 and M6.
- an identity with a held/uncertain effect is itself blocked until reconciled (scoped as above).
These can be specified and SQL-tested without a droplet.

**Scheduling.** Most work is scheduled, so fleetd **pre-wakes** an identity before its job. Cold wake
measured 11.7-21.6 s as one composite chain on arm64, excluding bundle download/decrypt, proxy
connect, IP and persona checks and node creation — treat it as a floor. Never always-on at scale
(1,000 always-on browsers ≈ 1,850 GiB RAM). Start with a Postgres job queue whose claim locks the
identity row; add Temporal (on Postgres, `REJECT_DUPLICATE` + retention for post-completion dedupe)
at the multi-node milestone if durable workflows earn their keep. Deploy it properly on Postgres, with
no silent fallback that re-runs failed workflows.
The node agent restarts containers on a memory threshold (no soak test exists for 1-3 h sessions).
A **capacity planner** computes the number of awake identities over time from manifest windows (known in
advance) and reserves nodes ahead in batches of at most 10 creations; the pre-wake lead grows with queue
depth and new-node count; each node has a concurrent-wake cap (value from M1); creation is shared out by a
weighted fair share per tenant (ARCHITECTURE §7.8, S09-3). Spreading inside an approved window is for
capacity only, and its value against platform detection is unverified.

**Sizing and cost (all estimates, scale-infra Q4).** Planning slot 1.5 GiB + 0.35 GiB, 0.6 vCPU →
~7 awake identities per `s-8vcpu-16gb` ($96/mo bundled; 672 h cap; v5 droplets bill hourly with no
cap; at most 10 droplets created at once; account droplet limit unchecked).

| Identities × browser h/day | Self-hosted (autoscaled) | Steel Cloud | Browserbase |
|---|---:|---:|---:|
| 30 × 1 | ~$294 | ~$470 | ~$359 |
| 100 × 3 | ~$1,007 | ~$1,662 | ~$1,741 |
| 1,000 × 3 | ~$8,413 | ~$13,949 (custom) | ~$15,749 (custom) |

How to read it (C-05, C-17, D12 errors in `CONSISTENCY.md`):
- It is an **all-browser upper bound**. Under API-first (D2) most identities need few or no browser
  hours; the real driver — the share of identities that need a browser — is not yet estimated.
- Its "System-1-first" model mix assumes 40% of actions hit the fleet's own L1 cache (unbuilt) and
  1,000 tokens per decision (measured: 4.9-6.2K for 180 candidates), so model and decider-capacity
  lines are understated.
- It omits X API fees, the ≥ 31 s flush hold per sleep, Guard CPU, and the one-client-per-node rule.
- Steel Cloud self-serve dedicated IPs cap at 25; its stealth browser is Enterprise-only.
- Proxies and models are 60-75% of the bill at 1,000 identities. Replace every row with M1/M6
  measurements.
- **A second axis is missing (S09-8): `f`, the share of accounts that need a browser at all.** Under
  API-first (D2) an API-only account owns no IP (vocabulary: an account has zero or one identity), so
  proxy and node cost scale with `f`, not with 1,000. One identity serves one account, so a client with a
  browser on two platforms needs two IPs. **A third: X volume.** The table omits X API fees
  ($0.015 per post, $0.20 per post with a URL, $0.005 read-back, and billed webhook events; D2). A
  fourth: operator time, and the >= 31 s hold per sleep. Both are labelled **estimate**.
  The scenario walk-through (`research/scenarios/S09.md`) shows how wide the spread is: IPs only for
  browser identities at `f` = 10% versus a mandatory IP for all 1,000 differ by roughly a factor of
  three (its own estimate, inference). **Do not quote a single total.** M6 (G6.5) replaces every figure
  with a measurement.
- **Two things in the table are wrong or unproven.** Its 1,000 x 3 self-hosted cell says ~$8,413 but its
  own line items add to $8,403 (S09-8); and it credits a 40% replay share to a cache that does not exist
  yet (above). Neither number is a plan.

## D13. Effects are journaled, verified and never blindly retried

**Decision.** Every side effect (post, reply, DM, comment, delete, follow, form submit) has an
idempotency key; an intent row committed before the click or API call; an independent read-back
receipt (API read of the post, the message in the thread); and, when uncertain, a hold for
reconciliation, never a blind retry. Content to publish comes from an **approved campaign manifest**
(immutable, hashed, human-approved) or a per-action human approval. Tokens
carry scopes per identity: `read`, `draft`, `publish`, `dm`. A per-account and per-app governor
enforces platform ceilings as ceilings, built from live limit headers where they exist.

**What code enforces about content, and what only a person catches (S13-18).** Code enforces: `publish`
has no raw-text argument for page-derived content; the text that is sent hashes to the approved text;
the person approving sees the exact text, the conversation being answered, and warnings computed in
code (off-allow-list link, shortener, a string that was returned as untrusted to this token, a first link
to this destination). Code cannot enforce that a draft contains no copied page text: Hermes writes the
draft, and fleetd cannot tell whether it copied an attacker's sentence. That last check is the human
approver's, which is why the approval card shows provenance and requires a second acknowledgement for a
warning. The earlier phrase "never from page text" overstated what code does.

**The effect key names the authority, not the job (S08-1, S07-5, G10-3).**
`effect_key = H(tenant, platform, handle, kind, target, manifest_item_id + occurrence | approval_id)`.
A new job, a new idempotency key, or a replacement identity record for the same account yields the same
key, so `ON CONFLICT` fires. Scheduler jobs get the deterministic key `(manifest_item_id, occurrence)`.
A **second, authority-independent check** refuses any new effect for the same
`(platform, handle, content_hash)` while a row in `intent`, `uncertain` or `committed` exists inside an
open window. The approval page shows that prior attempt (S05-7). The approval is **consumed, and the
per-item cap bumped, in the same transaction as the intent insert**; a `failed_clean` outcome releases
both, while `committed` and `uncertain` keep them consumed (S08-1, S03-8). A person who acts by hand in
a takeover leaves a `channel=human` effect row, written at the mandatory closure step (D14); the
governor counts human effects (S05-7, G12-5).

**Read-back is tri-state: found, absent, unobservable (S05-6, S06-2, S08-5, S08-6).**
- A negative counts only when the auth probe is `ok` and a known-positive item (a previously committed
  post) is visible in the same page. Otherwise the result is `unobservable`. The grace clock pauses
  while auth is not `ok`.
- The matcher requires the target (group or thread id), `created >= intent_at - skew`, and normalised
  text. It captures the permalink or post id from the page right after the click when present, prefers
  an API read when the account has a healthy connection, and treats an ambiguous match as `uncertain`,
  not `found`. Its miss rate is logged (gate G4B.1).
- **No retry after a negative browser-channel read-back.** No browser-channel effect pair is marked safe to
  retry until G4B.1 reports a false-negative rate. A miss leads to `human_resolved` only. If a person says
  retry, it is the same effect row with `attempt + 1`, a new per-action approval and a new pre-submit
  check. A retry under a new key is the path the protocol forbids. (This reconciles the Charter's
  "nobody retries an uncertain effect" with the earlier "may be retried" wording in ARCHITECTURE §3.6.)
- The owner is alerted at the first `uncertain` and again when grace ends, with account, target, content
  hash, evidence refs, what the fleet does next and what the person checks by hand. Grace is defined per
  platform before any use.
- Evidence is uploaded and `evidence_refs` written into the intent row **before** the click, so a node
  that dies after the click still leaves the reconciler more than a hash (S08-13).

**First post per account, content type and destination always needs a person** (MILESTONES 4.6.1; S02-4).
The gate checks a recorded "first" (ARCHITECTURE `account_firsts`). A manifest approval satisfies it only
through an explicit per-account tick; otherwise one extra approval is needed.

**Procedures, revisions and L1 entries are two different things (S06-4).**
Procedures are digest-pinned. A UI change is repaired as a **new revision**, reviewed by an operator and
canaried on an owner-owned account of the same UI variant, then released fleet-wide as a unit. The
operator roles are named in ARCHITECTURE §6.13 (this resolves N-5). The "three distinct owner-accepted
outcomes" rule applies to a new **procedure revision** that contains an effect step. L1 entries for
non-effect steps are promoted by machine criteria (k verified successes with code `expects` passing, zero
mismatches, at least two identities; k is an estimate to measure) and carry no human outcome. Entries for
effect steps exist only inside a released revision. **Rollback** reverts to the previous revision and
retires L1 entries built under the failed one; if the platform changed, rollback means "pause and repair",
not "previous digest". The same canary rule applies to a new identity, a new Steel/Stagehand pin, a new
persona, a new `executor_id` or `extension_mode` before they touch a client account (O-13).

Verified caveats: the intent/receipt/hold pattern is proven in the trial's code against a synthetic
CRM; **read-back receipts for browser-driven social actions are a hypothesis** (their false-negative
rate sets the human reconciliation load). Prose guides on a plugin-less host
carry no executable authority.
Evidence: `scale-infra.md` §1.7; `existing-assets.md` §1.4; `verification/scale-infra.md` SCA-9;
`verification/hermes-packaging.md` HP-5.

## D14. Authentication is human, through a brokered live viewer

**Decision.** A human logs in once per identity through a viewer brokered by fleetd; the human holds
the identity's lease (takeover) while connected. Agents never type credentials and never solve CAPTCHAs
on client accounts. Stagehand `variables` keep values out of the act prompt only; the typed value then
appears in the accessibility tree (measured). **This is a plan, not an established path:** the viewer
is untested for special keys, IME, passkeys, native dialogs and HTTP auth (D4) — an M1 gate.
- **Who may open it (S01-3, S13-10; AQ-1, pending Justin).** Design default: operator accounts with
  passkeys, plus a `tenant_viewer` role limited to its own tenant, because the person logging in is
  often the client's own staff. A ticket alone never opens a session: the person must also be signed in.
  Steel's debug URLs have no authentication (`research/corpus/steel/`, live sessions), so this second
  factor is the only control. Until AQ-1 is closed the viewer broker is a blocked component.
- **The URL never goes to the agent (S01-3, S05-8, S13-10).** The notifier delivers the ticket straight to
  the named human. The tool result returns `{ticket_id, notified, expires_at}`, never the URL. The plugin
  hook and the vault note redact tickets and URLs. A ticket is exchanged once for a **viewer session**
  that survives a page reload. The human sees starting, ready, checking, done or failed in the same
  session, with a retry; the notification is sent when the browser is ready (S01-14).
- **Two kinds of pause (S05-4).** `login_wall` (the session expired): resume after the login probe passes.
  `checkpoint`, `captcha` or `restricted` (the platform challenged or limited the account): the identity
  enters `cooldown_until`; governor caps drop; effectful jobs do not resume on their own and need a fresh
  owner approval. A platform warning means stop all activity, as the Charter says. Precedence of answers:
  `checkpoint` over `outcome_uncertain`, with the `effect_id` in the details.
- **Takeover modes (G12-3).** Default: request takeover, honoured at the next step boundary within a
  bounded wait, with the live step shown to the person. Break-glass: immediate, flags the open effect and
  shows the in-doubt text. Takeover has a purpose: `reauth`, `human_session` (a healthy account used by
  hand) or `observe`. Handback for `human_session` does not touch `auth_epoch`.
- **Closure is mandatory (S05-7, G12-5).** Every takeover ends with the person stating "no effect" or
  "effect done: kind/target", written as a `channel=human` effect row, and, for each in-doubt effect, what
  happened to it (`human_resolved`). Where a connector exists the fleet also lists the account's recent
  posts and diffs them against the ledger.
- **After a human session (G12-6).** Open a fresh tab at a known URL, close the other tabs, verify the
  account header and persona, and re-run the step from its start. Never resume mid-page.
- **Pause cost (S05-11).** After the pause plus the ticket lifetime the identity sleeps (journal, flush,
  bundle) and `wake(purpose=reauth)` starts when the person opens a fresh link.
- **Next-day verify (S01-15).** If the fleet re-checks a browser effect or a fresh login the next day, it
  is a `system` job of kind `verify` (ARCHITECTURE §4.8 step 7). It is the only probe outside real work
  and is not a keep-warm probe.

**Keep-warm (O-12):** Meta's dormancy trigger covers "empty accounts with prolonged dormancy", so a
weekly scripted login probe on Meta adds terms exposure for little benefit. Probe only identities that
actually use the browser; use API-token health checks for API-channel identities.
Evidence: `stagehand.md` §1.9; `existing-assets.md` §4; `verification/social-platforms.md`.

## D15. Memory is Obsidian, written on the Hermes side

**Decision.** fleetd returns structured evidence (what ran, rung per step, receipts, evidence refs);
the profile writes run notes into its own Obsidian vault folder (plugin hook where plugins load; skill
instructions where they do not, e.g. the trial). The per-profile daily note is written by the profile
itself on a scheduled Hermes job from fleetd's `run_status`/history reads. Built-in Hermes memory
(2,200 chars) holds pointers only. A mem0-style semantic layer over the vault is a later milestone.
Community Obsidian plugins for Hermes (obsidian-memory, vault-view, icarus) are unvetted.
**Open (O-14):** where the vault lives relative to droplets and the trial, and whether a trial employee
can reach it (unverified).
Evidence: `hermes-packaging.md` §1.9; `verification/hermes-packaging.md` X-5; `CONSISTENCY.md` C-29.

## D16. Repository and release **[Justin]**

**Decision.** The fleet lives in `fleet/` on branch `feat/system1-browser-fleet`. The box is not
edited. `security.py` is reused verbatim (copied at a pinned box commit with a test that fails if it
drifts from the box's file); the `Guard` class is reused, but its gating contract (bound to the box's
module singleton in `tools.py`) is rebuilt per identity in fleetd, and its shield-check is ported off
the Playwright executor (11 attacks + 7 controls). Direct import would couple the fleet to box
internals (hard-coded port 3000, env read at import) (C-25).
**Before any merge to `main`:** `box-kit`'s export publishes the repo publicly (and its unanchored
excludes would strip `fleet/**/skills` while publishing the rest), so either exclude `fleet/`
precisely or move it to its own private repo. **[Justin] Q-09.** Separately, an exposure question about a public
companion repo is tracked privately. **[Justin] Q-10.**

## D17. Tool surface (v0, designed, not built)

What a Hermes profile sees. A tool is listed only after it passes a live end-to-end check (fleet
charter). Reads and writes are separate tools so `readOnlyHint` is truthful (HP-8). Everything that
can take longer than a few seconds is submit-then-poll within a 90 s budget (D1). This reconciles
hermes-packaging's eight tools (status, run, job, cancel, read, login_link, procedures, feedback).

| Tool | R/W | Purpose |
|---|---|---|
| `fleet_status` | R | What works now for this token: identities and health, providers, budget left, minimum skill version. |
| `identity_status` | R | List/get the accounts and identities bound to this token: state (canary, asleep, waking, awake, sleeping, needs_reauth, checkpoint, restricted, migrating, quarantined, retired), holds with their scope, cool-down, next scheduled items, and what is needed (an ordered list). |
| `identity_control` | W | `wake`, `sleep`, `reauth` (asks the notifier to send a ticket to the named person; returns `{ticket_id, notified, expires_at}`, never the URL). Creation is owner-only, not here (an `identity create` operator flow, ARCHITECTURE §4.15). |
| `procedures` | R | Released procedures this token may run, with required fields. |
| `run` | W | Run a released procedure on an identity with supplied fields. Returns a run id. |
| `act` | W | One scoped browser step (ladder L1-L3). Steps that would submit, post, send or delete return `needs_approval` unless tied to an approved manifest item and allowed by scope. |
| `extract` | R* | Structured extraction (schema) from the current page or a URL (*navigation only, no effects). |
| `task` | W | Open-ended browser goal (L4). Read-mostly: effect-like steps are blocked or return `needs_approval`. |
| `publish` | W | A channel-routed effect from an approved manifest item or a per-action approval; API first. Kinds: `post`, `comment`, `reply`, `dm`, `private_reply`. For `reply`, `dm` and `private_reply` the target is a fleet-issued `conversation_id` (or `comment_id`) from `inbox`, never a free string. |
| `job` | R | Poll a run/task/wake: steps, rung per step, receipts, evidence refs, cost. |
| `cancel` | W | Cancel a run/task and free the identity. |
| `approvals` | R | List approvals this token may see, with subject, diff and status. |
| `approve` | W | Answer an approval. Scope `approve`; **never held together with `publish` or `dm` on the same account**; held by operator-console users and not listed for Hermes profile tokens by default (ARCHITECTURE §5.3 tool 13, §9.1 row 2; AQ-5). |
| `feedback` | W | Report a wrong result, a site change, `blocked` or `injection_suspected` against a run. It raises a repair's priority and is rate-limited per token; it never quarantines a shared procedure by itself (S06-3, G10-12). |
| `manifest` | W | Scope `draft`. Propose or revise a campaign manifest (campaign, items, media refs, triggers). Returns a revision id and a diff. Approval and revocation stay with operators. |
| `manifest_status` | R | List and get manifests, items (including `missed` and `expired_unrun`), revision diffs and campaign status per platform. |
| `inbox` | R | Inbound messages and comments for conversations this token may answer, with a cursor. Text is flagged `untrusted: true`, length-capped and defanged. |

Errors are answers: `identity_busy`, `needs_reauth`, `checkpoint`, `needs_approval`,
`outcome_uncertain`, `budget_exhausted`, `scope_denied`, `infra_unavailable`, `not_released`,
`rate_limited`, `proxy_unavailable` and `proxy_mismatch` (wake-job reasons, S07-1), `identity_state` (the identity is `canary`, `migrating`, `restricted` or otherwise not in a
workable state) and **`refused`**.
- **`refused` (G11-2, S03-2).** Non-retryable. No scope, approval or manifest can unlock it. No approval
  request is created. `error.next` names the allowed route (API, draft for a person, consent channel).
  `details.reason` is one of `red_line_kind` (like, follow, unfollow, repost), `no_prior_contact` (a cold
  DM), `window_closed`, `opted_out`, `host_not_allowed` (x.com or LinkedIn browsing, social hosts for a
  research identity), `people_list` (a people-listing surface reached inside a session: a clicked link, a history change or an opened dialog; ARCHITECTURE §4.5 item 5), `no_consent_ref`. Approvals for red-line effect kinds cannot be created. This is the
  pass rule for gate G4.6 and a new row in fleet-router's "Read the answers" table.
- **`scope_denied`** keeps its meaning (the token lacks the scope or the target is not allowed to this
  token). Its `details.reason` includes `target_not_public` (a URL that is not public, S13-5),
  `host_not_allowed` (a `task` host outside `allowed_hosts`) and `conversation_not_yours`.
- **`rate_limited`** (S09-7): per-token or per-tenant request, in-flight job or in-flight wake limit.
- **`checkpoint`** carries `cooldown_until` and, when an effect was open, its `effect_id`.
- **`task` requires `allowed_hosts` and `output_schema`** (G11-12); a goal with no measurable end is
  rejected before any spend. Page-derived strings in any result are `{text, untrusted: true, source_ref}`
  (S13-3).
- **No tool lets an agent clear a hold, close a takeover, approve, or read a viewer URL.**

## D18. Executor and L3 by identity kind (added by the revision of 2026-10-10)

**Decision.** The executor and the meaning of L3 depend on the identity's kind, not on one global
engine. This amends D5 and D6 (S14-2, S14-3, S14-4, S14-7, S14-8).
- **The Executor is a fleet-owned interface.** It takes a fleet-owned `Action` (method, arguments,
  element identity: role and accessible name, frame path) and a snapshot builder, and returns what
  happened. L1 and L2 formats are not Stagehand's `Action`, snapshot or `xpathMap`. Every `l1_entries`
  key carries `executor_id` and `schema_version`. Stored entries are versioned and never converted
  across versions; a new version starts empty.
- **`account` identities** (a logged-in client account) use the **minimal CDP executor**, with no
  Stagehand extension, unless gate G1.4 shows another executor is better for that site class. Their
  image carries no extension directory, no extension flags and a filtered `--remote-allow-origins`
  (via `FILTER_CHROME_ARGS`, to measure) (`docs/infra/steel-profile.md` §2).
- **`research` identities** may use Stagehand with the extension (mode A, the measured recipe).
- **L3 is a model choice among structured candidates, run by the identity's executor.** For `account`
  identities the fleet's own **L3-lite** does it: its own snapshot builder, a shim call using the same
  `{elementId, method, arguments}` schema as L2, gate G, and the minimal executor. Where no
  (provider, host) pair is cleared for page text (Q-07), L3-lite is closed and the step climbs to L4 or
  L5 per the Q-01 branch. The System-1 share and the human load for logged-in procedures are re-estimated
  on that basis: **estimate, to measure** (G1.4, M3).
- **`extension_mode` is derived, never chosen per wake.** The node agent derives it from identity kind and
  wake purpose: a human-login or canary wake never loads the extension. It is `none`, `A` or `B`, and the
  persona pins it together with `executor_id` (D3). A change goes through the canary rule (O-13).
- **O-02 is updated:** the executor winner is per identity kind first, per site class second.

---

## Questions only Justin can answer

| # | Question | Blocks |
|---|---|---|
| Q-01 | API-first for client social (recommended) or browser-first; which clients accept the terms risk in writing? | D2, M4 |
| Q-02 | Anti-detect: continuity-only with measured per-identity upgrades (recommended) or buy a product from the start? | D9 |
| Q-03 | May the fleet depend on a proprietary patched kernel (CloakBrowser: telemetry, paid latest build, possible OEM clause)? | D9 |
| Q-04 | Spoofing stance: continuity only, or allow seed-pinned spoofing? (an earlier private SDR harness says no spoofing.) | D9 |
| Q-05 | X "Automated" label: will client brand accounts carry it if X requires it? | D2 |
| Q-06 | Apply for Meta App Review + Business Verification, TikTok Accounts API, LinkedIn CM API, X pay-per-use; monthly caps for X fees, models, proxies, droplets? | D2, M4 |
| Q-07 | Data handling: require zero-data-retention model routing, per-client consent, or both? | D8, M3 |
| Q-08 | Run Steel's Chromium non-root with the sandbox on, or accept the risk in writing? | D4, M1 |
| Q-09 | Exclude `fleet/` from box-kit's public export, or move the fleet to its own private repo? | D16 |
| Q-10 | A separate exposure question about a public companion repo (tracked privately). | D16 |
| Q-11 | Jev trial: OK to add the fleet via the integrations route + owner-approved guides? Who holds the owner role? | D1 |
| Q-12 | Approve a small, capped, throwaway DigitalOcean droplet for M1 hands-on; spend ceiling? | M1 |
| Q-13 | Cross-client unlinkability required (one client per node until per-identity hardware values exist)? | D3, D12 |
| Q-14 | Add consent-based lead channels (Lead Ads, opt-in DMs, LinkedIn Lead Gen Forms, TikTok instant forms) as first-class? | D2 |
| Q-15 | Confirm D18: logged-in client accounts default to the fleet's own minimal CDP executor (no Stagehand extension), with Stagehand v4 kept for research identities, unless gate G1.4 shows otherwise. This changes your "Stagehand is the main agent". Who builds the executor, and in which language (N-12)? | D6, D18, M1, M3 |
| Q-16 | Add a `moderate` publish kind (hide, unhide, delete) with an intent row and a read-back? Is delete a red line (`refused`)? D2 row 1 offers moderation by API; D17 has no kind for it. | D2, D13, D17 |
| Q-17 | A near-duplicate post across client accounts: refuse it (`duplicate_content`, proposed in ARCHITECTURE §5.5 and CHARTER) or hold it for approval? | D2, D17 |
| Q-18 | Hermes side: may profiles of different clients share a gateway host, or does each client get its own host (raises host count at 1,000)? `hermes/README.md` assumes they do not share. | D1, D3, D12 |
| Q-19 | A housekeeping question about the maintainer's local Hermes install (kept out of the public copy). Nothing was touched. Called Q-13 in `research/verification/CONSISTENCY.md`. | none |

---

## Revisions

**2026-10-10: revised after the 14 scenario stress tests** (`research/scenarios/S01.md` to `S14.md`). The
Questions table was unchanged by this pass (Q-15 to Q-19 were added by the second pass below). Gap ids are the scenario files' own; the full list, with where each
gap is handled, is `ARCHITECTURE.md` §9.5. Nothing in the fleet is built; every change below is to the
target.

| Decision | What changed | Gaps |
|---|---|---|
| Vocabulary | Added `account`; `identity` redefined as the browser self (one device generation) serving exactly one account (1:1). An account has zero or one active identity. Agents name it by alias; the tool argument stays `identity`. | S02-6, S07-5, G10-3 |
| D2 | One table of allowed browser uses (platform x use x who clicks x risk acceptance); `identity create` refuses any row not in it. The "personal profiles" wording is **withdrawn**: a Facebook personal profile and LinkedIn get no browser identity (`draft_for_human`), Instagram personal means convert to professional, X has no row. Red-line effects return the new `refused` code. A policy gate (R) and recipient eligibility are enforced in code. | S01-10, G11-1, G11-2, G11-3, G11-11, S03-2 |
| D3 | New IP or new infra home = a new device generation under the same account, fresh login, no restored state. The account, ledger, caps, API connection, alias, bindings and manifests carry over. Region rule for the replacement. Persona is per-home (Browserbase). The one-client-per-node rule is stated as a **fork** to be settled by one measurement, with the isolation unit defined as the tenant. `executor_id` and `extension_mode` join the persona. | S07-5, S07-6, S09-1, S09-12, G10-5, S14-7 |
| D4 | Viewer sentence: ticket exchanged once for a session, gated by operator sign-in, domain-limited. Holder owns the namespace. Two image flavors by identity kind. | S01-3, G12-14, S04-4, S13-6, S14-4 |
| D5 | Effect steps may not climb past L1 into a free-form click (mandatory `target_rule`, rehearsal repair, pre-submit check reads audience/visibility/attachments). Assent versus dismissal. Login affordances denied on every rung. Per-`data_class` rung availability. L3 is a model choice run by the identity's executor. | S06-1, S06-7, S06-8, S05-2, S14-8 |
| D6 | Pointer: executor is decided per identity kind (D18). | S14-8 |
| D11 | Trigger is a **functional** failure only. `solveCaptchas: false` on every session and an `identity create` check. BB-O1, BB-O2 recorded as pending. Continuity trade-off stated. | S05-14, G10-13 |
| D12 | Lease: purposes, acquire predicates (state, hold scope, open effects), timing and fence rules, human-lease liveness. Holds become rows with scopes. Admission control and fair share. Cost axes `f`, X volume and operator time added, labelled estimate; no single total; two table errors named. Capacity planner. | S01-4, S05-1, S08-2, S08-3, S07-1, S07-2, S07-3, S07-4, S03-10, S09-3, S09-4, S09-7, S09-8, G12-1 |
| D13 | Effect key on the account authority; second uniqueness check; approval consumed at intent and released on `failed_clean`; tri-state read-back; no retry after a negative browser read-back; matcher rules; evidence before the click; first-post gate; procedure revision versus L1 entry (release, promotion, rollback); the "never from page text" wording replaced by what code enforces and what only a person catches. | S08-1, S08-5, S08-6, S08-7, S08-13, S03-8, S05-6, S05-7, S06-2, S06-4, S02-4, S13-18 |
| D14 | Passkey sign-in plus `tenant_viewer`; URL never to the agent; ticket exchanged once; `login_wall` versus `checkpoint`/`restricted` with cool-down; two takeover modes; mandatory closure; clean tab after a human session; sleep during a long pause. | S01-3, S01-14, S05-4, S05-8, S05-11, S05-7, S13-10, G12-2, G12-3, G12-5, G12-6 |
| D17 | Added `manifest`, `manifest_status`, `inbox`. `publish` takes a fleet-issued `conversation_id`. New codes `refused` and `rate_limited`; reasons under `scope_denied`. `reauth` returns a ticket id, not a URL. `task` requires `allowed_hosts` and `output_schema`. | S02-1, S03-1, S03-2, G11-2, G11-3, G11-7, G11-12, S13-1, S13-3, S13-5, S13-13, S09-7, S09-10 |
| D18 (new) | Executor interface, fleet-owned Action schema, versioned L1 key, executor and L3 by identity kind, L3-lite, derived `extension_mode`. | S14-2, S14-3, S14-4, S14-7, S14-8 |

**2026-10-10, second pass (completeness review, `research/verification/COMPLETENESS.md` section 5).** Mechanical fixes:
D1 "and/or" made "and"; D5 path corrected to `docs/models/system1.md`; D17 `approvals` split into `approvals` (R)
and `approve` (W) to match ARCHITECTURE §9.1; D14 gained the next-day `verify` job sentence. Items that need a
judgment went to the Questions table instead: Q-15 (D18 executor default), Q-16 (`moderate` kind), Q-17
(`duplicate_content`), Q-18 (Hermes host sharing across clients), Q-19 (a workstation housekeeping item, which
CONSISTENCY.md calls Q-13; DECISIONS Q-13 is cross-client unlinkability).

**Defaults taken in this revision without Justin.** They are design defaults, marked "pending" wherever
they appear in ARCHITECTURE:
- AQ-1: operator sign-in by passkeys plus a `tenant_viewer` role. AQ-3: notifier destination left open
  (the ticket goes to the named person by the channel the owner records at identity creation).
- `human_clicks` is the default for every browser-channel effect; `agent_clicks` only by an explicit owner
  setting per identity (G12-15, S08-9).
- Facebook Groups: until Justin settles whether a Groups session is a personal-profile session, the acting
  account must be a Page or business account (ARCHITECTURE AQ-10).
- Scheduling is fleet-side only; never platform-side scheduled posts (S02-11).
- BB-O1 and BB-O2 defaults above. The one-client-per-node default stands until the S09-1 measurement.
- An identity serves exactly one account (1:1). A client needing a browser on two platforms gets two identities
  and two IPs; the effect on Meta of linked logins from two IPs is unresearched.
- The D17 `identity_status` row lists the new states and holds; wake-job reasons `proxy_unavailable` and
  `proxy_mismatch` are in the D17 error list (S07-1).
- Every number added (TTLs, k, caps, windows) is an estimate to measure.
