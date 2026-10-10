> **Read with its verification report.** [verification/existing-assets.md](../verification/existing-assets.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: existing assets the fleet should reuse

Agent: existing-assets research agent. Date: 2026-10-09 (spike ran 2026-10-10 03:03-03:08 UTC). Spend: $0.
Scope: this repo and several related repositories (some private; details withheld),
all read-only.

Provenance tags: `hands-on` (ran today), `source-code` (read at a pinned commit), `official-docs`,
`vendor-claim`, `third-party`, `unverified`.

---

## 1. Verdict

1. **Self-hosted Steel keeps exactly one profile per Steel process, at a fixed path, and fails silently.**
   - OSS Steel accepts `persist` and `userDataDir`, but any `userDataDir` value is treated as a flag only. Every persisted session writes to `/app/api/user-data-dir`.
   - `persistProfile` and `profileId`, which browser-box sends, are silently stripped.
   - One `activeSession` per process means one browser per container.
   - Re-creating a container on an existing profile volume gave a **logged-out browser while Steel still answered HTTP 200**. Steel's log shows Chromium's `process_singleton` launch error, caused by a stale `SingletonLock` naming the old container. The fallback to a blank browser is inferred from that log line plus the empty cookie read.
   - A cookie set about 5 s before release never reached disk. One set 40 s before release did.
     - This happened even though release calls puppeteer `browser.close()` and then `process().kill()` (`cdp.service.js:382-383` in the image).
     - n = 1. The mechanism is not proven.
   - Consequence: the persistence boundary is **one Steel container per awake profile, with that profile's volume mounted at `/app/api/user-data-dir`**, plus a wrapper that clears stale `Singleton*` files and verifies "still logged in" after every wake.
   - `hands-on` + `source-code` (spike `spikes/existing-assets/RESULTS.md`; `session.service.ts:180-183` @1131a02; image `sha256:7a161b95…`).
2. **browser-box's security core carries straight over: `security.py` and `guard.py`.**
   - `security.py` is stdlib only.
   - `guard.Guard(cdp_url)` can be built once per browser, with the cdp_url as its only argument.
   - Both come with 18 attack checks and 33 shared scope vectors that the TypeScript port (`jev-automation/core/scope.ts`) also passes.
   - The fleet should import these modules, not copy them. AGENTS.md says "port it, never rewrite it". `source-code`
3. **Everything else in the gateway assumes one browser.**
   - `steel.BASE` and `steel.CDP` are module globals.
   - `guard.GUARD` is a module singleton.
   - `jev.SESSION = "playwright"` is a constant.
   - `tools._CALLS` is an in-memory list.
   - `lock.py` lanes are host-local `flock` files, so they cannot coordinate two hosts.
   - The pattern to reuse is the dispatch layer: one `TOOLS` list feeding MCP, HTTP/JSON and OpenAPI, with refusals returned as answers. The modules themselves are not reusable. `source-code`
4. **Useful fleet-scale patterns exist in earlier internal projects (details withheld).** A cross-host per-profile lease idea (one earlier design is safe only serially, so the fleet lease is designed fresh); a digest-pinned procedure registry whose effectful adapters declare an authority and an independent verifier; an intent journal written before the effect, with receipts and no replay of an uncertain effect; a metered System 1 loop with ABSTAIN and a confidence threshold; and release rules (quarantine, three owner-accepted outcomes, rollback per skill).
5. **Nothing in the existing assets supports "System 1 powers 90%+ of actions".** No earlier evaluation measured live model quality on real sites, and the published benchmark has a grounding miss on search. So 90% is a hypothesis to measure, not a fact.
6. **An older local tool checkout is mostly stale for this fleet.** Its Steel and Browser-Use pages describe the cloud products and its anti-detection matrix was never run on Steel. Still useful: a publishing-safety action taxonomy, the reasoning that profiles, workers and computers are different quantities, a micro-dollar reserve/settle ledger pattern and a verifier evidence-integrity checklist.
7. **The browser-box charter cannot govern the fleet as written.**
   - Three of its five invariants conflict at 100-1,000 profiles: "one browser, one lane", "no brain in the box", and per-action confirmation for "post"/"send".
   - Its security invariants carry over unchanged: "never type credentials" and "only the public web".
   - Section 2, Q1(b) proposes the fleet-charter equivalent for each.
8. **Reuse map in one line:**
   - **Import as-is:** `security.py`, `guard.Guard`, `tests/scope_vectors.json`, the shield-check attack suite.
   - **Adapt:** `lock.py` (rebuild as a DB lease), `steel.py` (rewrite for one container per profile), the `agents/browseruse` confinement (re-pin, multi-CDP), the public action-selection library, and patterns from earlier internal projects (details withheld).
   - **Reference only:** the older local tool checkout's references, the public handoff kit (TypeSafe docs snapshot, the outreach reconciliation spec) and the drift-watch pipeline (details withheld).
   - **Do not use:** the older tool's toy fleet module (capped at 10), super-saiyan-browser (the 29-tool system browser-box replaced), and a retired runtime snapshot.
9. **Two policy tensions to put to Justin, not resolve here:**
   - (a) An earlier internal outbound-email project states a no-spoofing, no-proxy-rotation policy for its own product. The fleet brief points the other way: anti-detect, proxies, stealth.
   - (b) `box-kit/scripts/export.sh` publishes **the whole browser-box repo** (minus plugins and bench) to the **public** box-kit repo. A `fleet/` subtree merged to `main` would be exported unless it is excluded first.

---

## 2. Answers

### Q1. This repo (@4c837a3)

Baseline check, `hands-on`: `PYTHONPATH=gateway .venv/bin/python -m unittest discover -s tests -t .` → `Ran 178 tests … OK (skipped=1)`.
`docs/operations.md` still says "167 tests". The doc number is stale, and that drift is minor.

#### Q1(a). Reusable modules and how each carries into a multi-profile fleet

| Module | What it is (evidence) | Single-browser assumptions | How it carries into the fleet | Verdict |
|---|---|---|---|---|
| `gateway/gateway/security.py` (147 lines) | URL scope classifier. Handles obfuscated IPv4, IPv4-mapped IPv6, CGNAT 100.64/10, `.local/.internal`, bare hostnames. Also `require_public_addresses`, which refuses a hostname if any of its addresses is private. Stdlib only. `source-code` | none | Import it unchanged into the fleet service and every worker. The TypeScript port `jev-automation/core/scope.ts` passes the same `tests/scope_vectors.json` (33 vectors), so a Node Stagehand worker can import that port. `source-code` | **reuse as-is (import)** |
| `gateway/gateway/guard.py` (318 lines) | A CDP client attached to the **browser target**, with `Fetch.enable` on every tab, frame and dedicated worker. It also auto-attaches and holds service and shared workers. It fails open, so the tools fail closed. `make guard-check` and `make shield-check` run 18 attacks. `source-code` | `GUARD = Guard()` module singleton (`guard.py:318`). The default `cdp_url` comes from `steel.CDP`. | `Guard(cdp_url=...)` already takes the URL. Construct one per awake browser inside the per-profile supervisor and gate every navigation on `wait_ready()`. Cost: one websocket and one asyncio task per browser. Its DNS check resolves locally, while proxied Chromium resolves at the proxy. Keep the host egress rule as the backstop. | **reuse as-is (instantiate per profile)** |
| `gateway/gateway/lock.py` (88 lines) | Cross-process `flock` "lane". Named lanes already exist via `name=`. `source-code` | Host-local files (`LOCK_PATH`, `lock.py:23`, `fcntl.flock` at `:56`). They cannot coordinate across hosts or a pool of DO droplets. | Keep the *semantics*: one writer per profile, a busy reply that names the holder, a bounded wait. Re-implement as a DB lease; an earlier internal job-claim design has the same shape (hashed token, expiry, one lease per profile) but is safe only serially. A `flock` is still fine as a second guard inside one host. | **adapt** |
| `gateway/gateway/steel.py` (114 lines) | Thin REST client for scrape, screenshot, session create, release and list. It probes the `/v1` prefix and maps a blocked request inside the browser to `UnsafeUrl`. `source-code` | `BASE` and `CDP` are module globals (`steel.py:16-17`). `create_session` sends `persistProfile` and `profileId` (`:100-105`), which OSS Steel ignores (`hands-on`). | Make it a per-profile client object holding `base_url` and `cdp_url`. Send `persist: true`. Never send `userDataDir` as a path, because it is ignored. Add `proxyUrl`, `userAgent`, `timezone`, `dimensions`, and `skipFingerprintInjection` or the fingerprint inputs. All of these are in the OSS schema: `sessions.schema.ts` @1131a02, `source-code`. Keep the `ERR_BLOCKED_BY_CLIENT` → refusal mapping. | **adapt** |
| `compose.yml` Steel service | Steel hardening: loopback-only port, `NODE_OPTIONS=--unhandled-rejections=warn` (a tab close crashed the whole server 4/5 times), memory and CPU caps, healthcheck. `source-code` | One `steel` service. No volume at `/app/api/user-data-dir`, so profiles die when the container is recreated. | Becomes the template for `fleet/infra/steel-profile`: one container per awake profile, named volume `profile-<id>` at `/app/api/user-data-dir`, an entrypoint that removes `Singleton*`, its own network, and egress allowed only to that profile's proxy. | **adapt** |
| `gateway/gateway/jev.py` (138 lines) | Client for the agent-jev container: `/command`, `/reply`, `/cancel`, `/read`. `summarize()` maps Jev results to `needs_clarification` or `needs_confirmation`. `source-code` | `SESSION="playwright"` (`jev.py:19`); one `BB_JEV_URL`. | The `summarize()` result vocabulary (done, failed, needs_clarification, needs_confirmation, `decided_by`, `decision_ms`) is a good worker-result contract. The transport is not: one agent-jev container per profile at roughly 134 MiB each is wasteful. Call Jev in-process from the worker instead (see jev-automation below). | **reference only** (contract), **do not use** (transport) |
| `gateway/gateway/browseruse.py` + `agents/browseruse/{server,runner}.py` | Browser-Use runs in a killable child process confined to its own tab, with foreign tabs hidden. It has no downloads watchdog, `permissions=[]`, `upload_file` excluded, `reasoning_effort=low` for GLM 5.3 Flash, a step ledger and cost. `source-code` | `runner.py:32` pins `PINNED = "0.13.10"` and `confine()` refuses any other version (`:58`). `hands-on`: under the shared scratch venv, `runner.py --self-check` fails with "browser-use 0.13.11 is installed; the confinement here is written against 0.13.10". One CDP URL per container. | In the fleet each profile has its own browser, so tab confinement matters less. The child-process kill, the excluded actions, the self-check, per-step progress lines and cost reporting all carry over. Re-pin to the version the browser-use dossier chooses and re-run `--self-check`. Make `CDP_URL` a per-task argument. | **adapt** |
| `server.py` + `rest.py` + `tools.py` (the `TOOLS` card list, `run_tool`, OpenAPI generation, `offered_tools`) | One `TOOLS` list drives MCP `list_tools`, `/api/v1/<tool>`, `/openapi.json`, and a drift test against `docs/openapi.json`. `run_tool` turns expected exceptions into `{"error"}` answers (HTTP 422). `source-code` | Bearer token is a single `BB_TOKEN`. `_CALLS` lives in memory (`tools.py:197`). `status` reports one browser. | Copy the *pattern* into `fleet/fleetd/api/`. Use a separate `FLEET_TOOLS` list with its own `fleet/docs/openapi.json` and a drift test. Add per-profile scoped tokens (the System One trial and the TypeSafe rollout both specify scoped per-profile credentials). Add per-profile and fleet-wide `status`. Do **not** add fleet tools to the box's `TOOLS` list. | **adapt (pattern)** |
| `pp-cli/` (Go, Printing Press) | Generated from `docs/openapi.json`. Adds a local ledger, cache, find, `queue read` (lane-aware retry), aliases and drift. `source-code` (skimmed) | Built for one box, and its ledger sees only its own calls. | Once the fleet's OpenAPI exists, regenerate a `fleet-pp-cli` with the same toolchain (the `printing-press` skill). The `queue` lane-aware retry concept maps to "profile busy". | **reference only** (regenerate, don't fork) |
| `cli/` (`bb`) | Small Python CLI and an optional local chat loop. `source-code` | single box | Not needed; Hermes is the client. | **do not use** |
| `orgo.py` | Orgo desktops; computers are billed until stopped. `source-code` | | Out of scope unless a profile needs a full desktop. Its "validate the model id before any request" pattern is a good habit. | **reference only** |
| `tests/scope_vectors.json`, `scripts/guard_probe.py`, the `steel-shield-check.ts` 18-attack suite (in jev-automation) | Shared vectors, plus attacks run from inside the browser. `source-code` | | Make them fleet deploy gates: run against each new Steel image digest and each `steel-profile` wrapper version. | **reuse as-is** |
| `bench/` + `scripts/bench.py` (B5) | `act` vs `task` with ground truth fetched separately. `source-code` | | Methodology template for measuring "System 1 share" and accuracy per procedure. | **reference only** |
| `skills/browser-box/SKILL.md`, `box-kit/hermes/skills/browser-box/SKILL.md` | Teaches "fetch before read" and that refusals are answers. `source-code` | | Style template for `fleet/hermes/skills/fleet-browser/SKILL.md`. | **reference only** |

#### Q1(b). Charter invariants that conflict with per-profile browsers at scale, and the fleet-charter equivalent

The box charter is not edited. `fleet/CHARTER.md` gets its own invariants.

| Box charter rule (CHARTER.md @4c837a3) | Conflict at 100-1,000 profiles | Proposed fleet-charter equivalent |
|---|---|---|
| **Inv. 1** "If a tool is listed, it works … never report ok for something you did not check" | No conflict, but it scales differently. The spike showed Steel returning **200 with a logged-out browser**, so "ok" from the infra layer is not proof. | **"A profile is ready only when checked."** Each wake runs a per-profile auth probe (a site-specific "logged-in" marker) before any work. Profile state is one of `asleep / waking / ready / needs_reauth / quarantined / locked`. `status` reports per profile and per fleet with a one-line reason. |
| **Inv. 2** "No brain in the box by default" | The fleet *is* the agent: Stagehand, Browser-Use, System 1 and GLM run inside the service by design. | **"Every brain is declared, bounded and logged."** System 1 picks only among options that code produced (elements, procedures, supplied values) and may ABSTAIN. The reasoning model is called only on escalation. Text that will be published comes only from approved content, never from page text. Every decision records `decided_by`, confidence and cost, as `jev.summarize` and the trial's route events already do. The Hermes profile still owns the *goal*. |
| **Inv. 3** "One browser, one lane" | Directly contradicts 1,000 concurrent profiles. | **"One profile, one identity, one writer."** Each profile has exactly one pinned browser identity (infra, volume, proxy, fingerprint) and at most one active lease. Many profiles run concurrently up to per-host capacity. A tab is never an isolation boundary (`researched-outreach-plan.md`). The lease is a DB lease, not a flock. |
| **Inv. 4** "The browser reaches only the public web … host egress rules are the backstop" | Kept, but proxies change the network path. Chromium talks only to its upstream proxy. Steel runs its own local proxy chain (`proxyServer.listen()` in `session.service.ts`). | **Kept, with these additions:** `guard.Guard` on every awake browser. Per-container egress allows **only that profile's proxy endpoint** (plus nothing private). Never fall back to direct egress when a proxy fails: that would change the IP the profile is known by. |
| **Inv. 5** "Few tools, each proven … cards, OpenAPI and plugin generated from one TOOLS list" | No conflict. | **Kept:** one `FLEET_TOOLS` list feeds MCP, HTTP and OpenAPI, plus the Hermes plugin and skill. A *procedure* (e.g. "post to X") is released only after proof. Release rules come from the trial: three distinct owner-accepted outcomes, digest-pinned, rollback per procedure. |
| "Must not … confirm a `needs_confirmation` step (buy, delete, send, **post**). Ask the person." | Agents whose job is posting and replying cannot ask a human per action at this volume. | **Campaign-level authorization instead of per-click.** Build an immutable, hashed authorization manifest per client and profile: audience, content or content rules, schedule, caps, kill switch. An earlier internal approval-manifest design is the template. Then journal intent before the effect, record a content hash and idempotency key, run an independent receipt check, and **hold uncertain effects without retrying them** (the procedure-registry pattern). Anything outside the manifest falls back to per-action human confirmation. |
| "Never type credentials into a page through act, task or computer" | No conflict. It is the brief's own rule. | **Kept verbatim.** A human logs in once through a live viewer, and agents never see credentials or 2FA codes. |
| Escalation: "stop and ask when … a page asks for credentials" | At scale, sessions expire continuously. | **Human re-auth queue:** the profile moves to `needs_reauth` and work for that profile stops. A time-limited, authenticated live-viewer lease goes to the human; the trial uses a one-hour takeover lease. Every other profile keeps working. |
| "Must not … start an Orgo computer (it bills until stopped)" | Paid infra (Browserbase sessions, proxy GB, model tokens) is routine in the fleet. | **Every paid unit is reserved before use and settled after**, against per-profile, per-client and fleet caps (a micro-dollar ledger pattern, trial model gateway). An unknown outcome keeps its reservation. |
| "Steel holds nothing worth stealing" (`docs/security.md` limit 3) | False in the fleet. Every profile volume holds a client's logged-in social accounts. | **Profile volumes are secrets:** encrypt at rest, never leave the infra host except as encrypted backups, give no agent filesystem access, and keep CDP on loopback or the internal network only. |
| Security limit 7: "after a session login, a task can act as that login" (Browser-Use follows page instructions) | In the fleet every Browser-Use task runs logged in, and DMs and comments are attacker-written text. | Browser-Use runs only for open-ended *read* goals, or behind a procedure allowlist. Effects go through System-1/Stagehand procedures with code-built options. `upload_file` stays excluded unless a procedure needs it. |
| "Definition of done: deployed and `make smoke` passes on the live box" | The fleet has no single box. | **A profile-level smoke and a fleet canary:** wake → guard attached → auth marker → one read-only procedure → sleep. Fleet changes roll out to a canary profile set first, mirroring the staged rollout in `typesafe-fleet-rollout.md`. |

### Q2. An older local tool checkout (now the data-box repo; details withheld)

**What it gives the fleet.** Ecosystem notes (cheapest capable first, escalate on evidence; proxy-tier economics); a publishing-safety skill and approval policy (a complete taxonomy of external writes and the approval payload: target, account, exact content, audience, irreversible effects, action fingerprint; no automatic retry once an approved write has started); a verifier evidence-integrity checklist; and a micro-dollar reserve/settle ledger (interrupted jobs charged in full, request-id idempotency). **Stale or wrong for this fleet:** its Steel and Browser-Use pages and anti-detection results describe other products and were never run on self-hosted Steel; do not carry their conclusions.

### Q3. GitHub repos (read-only via `gh`)

Visibility check (`gh repo view`, `hands-on`):
- **Public:** `jev-automation` (a **fork of `yatharth1706/jev-automation`**), `jev-agent-kit`, `super-saiyan-browser`, `hermes-workforce-router`, `box-kit`.
- **Private:** several other repos (names withheld), plus `browser-box` itself.

The brief calls them all private, and several are not.

#### jev-automation, branch `feat/steel-cdp` @edcbbae (the exact `JEV_REF` of the B5 benchmark)

- **What it does.** "Jev Voice Browser" became a text-first Mac panel. TypeSafe Jev turns a plain-words step plus a page snapshot into an action. It has Playwright, a Chrome bridge extension, and Mac (cua-driver) executors, and runs as the `agent-jev` container beside Steel. `source-code`
- **Reusable for the fleet:**
  - `core/decide.ts` is the System-1 action-selection pattern. One `systemone` request fans out `choice`/`noul` questions: route, intent, target element (≤180 elements + `none`, under Jev's 255-option limit), `risky`, `submit_after_typing`, `url_pick`. Code applies `THRESHOLDS` (intent 0.25, target 0.35, risk 0.6, submit 0.6). These thresholds are *their* tuning, not validated for social sites.
  - `core/verify.ts` is a post-action check: code diffs the before and after snapshots, and Jev answers `done`/`stuck`/`blocker`. The blocker taxonomy (consent_dialog, login_wall, captcha, error_page, popup, permission_prompt, no_change) maps directly to fleet health signals. A `login_wall` means `needs_reauth`.
  - `core/elements.ts` and `core/page-script.ts` do element extraction, with `data-jev-id` re-location and a text signature.
  - `core/scope.ts` is the TypeScript URL guard, with byte-identical vectors.
  - `server/executors/playwright.ts` attaches over CDP to an existing browser. It owns only its own tabs, reattaches when Steel relaunches, and runs a per-page CDP Fetch guard.
  - `scripts/steel-shield-check.ts` is the 18-attack suite.
  - SDK: `@typesafe-ai/sdk ^0.6.0` (`package.json`).
  - All `source-code`.
- **How it fits.** Stagehand is the planned primary agent. The `core/` modules are the natural "System 1 inside Stagehand's loop" layer: Stagehand's `observe` produces candidates, Jev chooses, code acts, Jev verifies. Lift `core/` as a library into `fleet/workers/stagehand-worker`. Do not run one agent-jev container per profile.
- **Conflicts:**
  - It is a public fork, so client-specific procedures must never be committed there.
  - Its `/ask` brain path (OpenRouter) and Mac surfaces are irrelevant.
  - `server/index.ts` binds one `CDP_URL` at startup, so it is single-browser.
  - Measured weakness: the search grounding miss (B5 0/3).

#### jev-agent-kit @faeae16 (public)

- **What it does.** A handoff kit: the complete `typesafe-ai` skill, an **offline snapshot of TypeSafe docs** (HTTP API, JS/Python SDKs, primitives, confidence, cookbooks, Jev 1.13 "jaggedness" notes), the email-outreach build brief, and evidence. `source-code`
- **Reusable:**
  - The TypeSafe docs snapshot, for the System-1 agent to cross-check (`skill/typesafe-ai/references/docs/`).
  - `source/typesafe-fleet-rollout.md`. Proposed 2026-09-17: one versioned Hermes plugin; a central service holds the TypeSafe key; **scoped per-profile credentials**; the `pre_llm_call` hook (via hermes-workforce-router); a central ledger; offline acceptance of ≥20 routing tasks and ≥90% labeled agreement before routine use; a staged canary → wave rollout; rollback per profile. This is the closest existing blueprint for "one shared service, a skill and scoped token per profile".
  - `source/researched-outreach-plan.md`:
    - profiles, workers and computers are different quantities;
    - one active writer per profile;
    - a tab is not an account boundary;
    - record a unique key and content hash before Send;
    - verify Sent independently;
    - crash after click → `uncertain`, reconcile, never resend.
    - Its distinct outcome states (drafted, authorized, attempted, confirmed, bounced, replied, opted out, uncertain) carry directly to "posted/replied/DM'd".
  - All `source-code`.
- **Conflicts.** `SUPER-BROWSER-LLM-BOOTSTRAP.txt` points at the retired hosted service, and the README says so.

#### A retired handoff snapshot (private; details withheld)

- **What it does.** A retired portable snapshot of an older runtime, skills and docs (details withheld).
- **Reusable.** Nothing that is not better taken from the sources above.
- **Verdict.** **Do not use.**

#### super-saiyan-browser @87531e9 (public, 2026-09-13)

- **What it does.** The public plugin version of Super Browser: provider ladder, 3-5 deliberation loops, approvals, verifier, and a Chrome side-panel table scraper. Its v0.7.1 adds "anti-bot pacing" (jittered inter-page delays) and captcha/challenge detection that pauses (`extension/ids-engine.js:240-248`). `source-code`
- **Reusable.** The challenge-detection selector list (`iframe[src*="turnstile"]`, `#challenge-form`, `cf-challenge` …) as a seed for the fleet's blocker detector. **Reference only.**
- **Conflicts.** It is the "29 MCP tools, 22 could not reach a browser" lineage that browser-box's charter was written against. Do not resurrect its architecture.

#### An earlier outbound-email control plane (private; details withheld)

- **Adapt:** immutable approval manifests (any change to audience, persona, cap or attachment invalidates the approval); a versioned workflow registry and decision-policy registry; outbound modes (disabled, seed-only, approved campaign) with per-sender caps; one-time enrollment tokens exchanged for revocable node credentials; budget reservations and an audit log.
- **Conflicts.** Its job-claim lease is safe only serially, so the fleet lease is designed fresh (D12). It states a no-spoofing, no-proxy-rotation policy for its own email product, which is the spoofing question in Q-04. Serialized authenticated writes on one machine do not scale to a fleet.

#### An upstream-drift watch pipeline (private; details withheld)

A read-only daily pipeline that ranks upstream releases. Extend its queries to cover Stagehand, Steel, Browserbase and anti-detect tooling so upstream changes trigger re-validation of the pinned self-checks.

#### The Jev Workforce Phase 1 trial (private; details withheld)

A local trial with one isolated container per employee. **Adapt (patterns only):** a digest-pinned procedure registry whose effectful adapters declare an authority and an independent verifier; an intent journal written before the effect, with receipts and no replay; a bounded System 1 browser loop (candidates from the accessibility snapshot plus ABSTAIN, supplied values only, stop on repeated actions or the step budget); a metered model gateway (effective confidence is the minimum of the reported confidence and the chosen option's probability; reserve before each call, settle after); and release rules (quarantine, three owner-accepted outcomes, rollback per skill). Its evidence is offline only: no live model quality has been measured. **Conflicts:** a full desktop container per employee does not fit state-at-rest browsers at fleet scale, and its accessibility-tree driver must be re-bound to CDP. Nothing in this work modifies that repo.

#### Also relevant, not in the task list

- **`box-kit` @5271017 (public).** A self-host bundle of browser-box and data-box with Claude plugins and Hermes skills (`hermes/skills/browser-box/SKILL.md`, `hermes/config-snippet.yaml`).
  - Its `scripts/export.sh` runs `git archive "$BB_REF"` on **the whole browser-box repo**, excluding only `.claude-plugin`, `.mcp.json`, `skills`, `commands`, `bench` and `tests/test_plugin.py`. `source-code`
  - So `fleet/` must be added to that exclude list (or live outside the exported ref) before any merge to `main`.
- **`hermes-workforce-router` (public):** a Hermes plugin with the `pre_llm_call` hook. It is covered by the hermes-packaging dossier.

### Q4. Reuse map and proposed layout

#### Reuse map

| Asset | Decision | Reason |
|---|---|---|
| `browser-box/gateway/gateway/security.py` | **reuse as-is (import)** | Proven classifier with 33 shared vectors, stdlib only. AGENTS.md: "port it, never rewrite it". |
| `browser-box/gateway/gateway/guard.py` (`Guard` class) | **reuse as-is (one instance per awake browser)** | Browser-target `Fetch` interception closed the leaks found in the redirect tests, and it is 18/18 on guard-check. Already parameterized by `cdp_url`. |
| `browser-box/tests/scope_vectors.json`, `jev-automation/scripts/steel-shield-check.ts`, `browser-box/scripts/guard_probe.py` | **reuse as-is (deploy gates)** | Run against every Steel image digest and `steel-profile` wrapper version. |
| `browser-box/gateway/gateway/lock.py` | **adapt** | The semantics are right. The `flock` is host-local, so the cross-host primary becomes a DB lease (an earlier internal job-claim design, safe only serially). |
| `browser-box/gateway/gateway/steel.py` | **adapt** | Becomes a per-profile client. Use `persist` (not `persistProfile`/`profileId`), add proxy, UA, timezone and dimensions. |
| `browser-box/compose.yml` (steel service hardening) | **adapt** | Template for a one-container-per-profile wrapper with a volume at `/app/api/user-data-dir`, `Singleton*` cleanup, and proxy-only egress. |
| `browser-box/agents/browseruse/{runner,server}.py` | **adapt** | Child-process kill, excluded actions, version self-check and cost lines carry over. Re-pin it (now 0.13.10, scratch has 0.13.11) and take a per-task CDP URL. |
| `browser-box` `TOOLS` → MCP/REST/OpenAPI pattern, `run_tool` refusals-as-answers | **adapt (pattern)** | A separate `FLEET_TOOLS` with its own OpenAPI and drift test. Never extend the box's `TOOLS`. |
| `browser-box/gateway/gateway/jev.py` (`summarize` result vocabulary) | **reference only** | A good result contract. The transport (one agent-jev container per browser) does not scale. |
| `browser-box/pp-cli` | **reference only** | Regenerate for the fleet OpenAPI with Printing Press. |
| `browser-box/bench` (B5 method) | **reference only** | Template for measuring System-1 share and accuracy per procedure. |
| `browser-box/cli` (`bb`), `orgo.py` | **do not use** / reference | Hermes is the client. Orgo is out of scope. |
| `jev-automation/core/{decide,verify,elements,page-script,scope}.ts` | **adapt (lift as a library)** | The System-1 decide and verify pattern with confidence gates and a blocker taxonomy. It was tuned on generic pages, not social platforms. |
| `jev-automation/server/executors/playwright.ts` | **adapt** | CDP attach, own-tabs-only, reattach on relaunch. |
| `jev-automation` agent-jev container, `/ask` brain, Mac/bridge surfaces | **do not use** | Single `CDP_URL` per process. Brain and Mac paths are irrelevant. |
| Earlier internal procedure registry, model gateway, System 1 loop and release rules (details withheld) | **adapt (patterns only)** | Digest-pinned procedures, authority and verifier adapters, intent journal, receipts, no replay, reserve/settle metering, min-confidence rule, quarantine and rollback. |
| Earlier internal job-claim, approval, workflow and enrollment designs (details withheld) | **adapt (rebuild the lease)** | The job-claim lease is safe only serially and is designed fresh (D12). Approval manifests, registries and node enrollment carry over as patterns. |
| Handoff-kit notes, the older local tool checkout and the drift-watch pipeline (details withheld) | **reference only** | Blueprints and taxonomies; provider facts are stale. |
| `super-saiyan-browser` | **reference only** (challenge selectors) | The 29-tool lineage browser-box replaced. |
| `box-kit` | **reference only** + **must change before merge** | Its Hermes skill and config snippet are templates. Its export would publish `fleet/`. |

#### Proposed directory layout (branch `feat/system1-browser-fleet`; box untouched)

```
browser-box/                         # existing box: gateway/, agents/, tests/, compose.yml, TOOLS, docs/openapi.json UNCHANGED
└── fleet/
    ├── CHARTER.md                   # fleet invariants (section 2, Q1(b)); points to ../CHARTER.md for the box
    ├── README.md
    ├── research/                    # (exists) BRIEF, corpus, dossiers, spikes, verification
    ├── fleetd/                      # the one shared fleet service (Python package `fleetd`)
    │   ├── pyproject.toml           # depends on the box by import path, not by copy (PYTHONPATH=gateway:fleet/fleetd)
    │   ├── fleetd/
    │   │   ├── api/                 # MCP + HTTP/JSON + OpenAPI from one FLEET_TOOLS list; per-profile scoped tokens
    │   │   ├── registry/            # profile record: client, infra (steel|browserbase), volume, proxy, fingerprint, state machine
    │   │   ├── leases/              # DB lease per profile (rebuilt, not copied) + host-local flock as a second guard
    │   │   ├── scheduler/           # wake/sleep, routines, queue; capacity per host
    │   │   ├── infra/               # steel_oss.py (container-per-awake-profile), browserbase.py (paid backup), health/auth probe
    │   │   ├── guard.py             # thin: `from gateway.guard import Guard`; one instance per awake browser
    │   │   ├── engines/             # router: system1-first -> stagehand -> browser-use -> reasoning; decision log
    │   │   ├── procedures/          # digest-pinned registry, adapters {authority, verifier}, release rules, quarantine
    │   │   ├── receipts/            # intent journal, receipts, reconciliation, uncertain-hold
    │   │   ├── approvals/           # campaign authorization manifests (immutable, hashed)
    │   │   ├── ledger/              # reserve/settle (data_box/ledger.py pattern), per profile/client/fleet caps
    │   │   ├── reauth/              # human re-auth queue + time-limited live-viewer leases
    │   │   └── memory/              # Obsidian vault writer (per-profile notes; mem0-style search layered on top)
    │   └── tests/                   # includes a test that runs ../../tests/scope_vectors.json through fleetd's guard
    ├── workers/
    │   ├── stagehand-worker/        # Node: Stagehand + lifted jev-automation core/{decide,verify,elements,scope}.ts
    │   └── browseruse-worker/       # adapted agents/browseruse (re-pinned; per-task CDP URL; confinement self-check)
    ├── infra/
    │   ├── steel-profile/           # wrapper image/entrypoint: clear Singleton*, volume at /app/api/user-data-dir, caps
    │   ├── compose.fleet.yml        # own compose project name + networks; never references box services or ports 3000/8080
    │   └── egress/                  # per-container proxy-only egress rules (iptables templates from docs/operations.md)
    ├── hermes/
    │   ├── plugin/                  # Hermes plugin (per hermes-packaging dossier)
    │   └── skills/fleet-browser/SKILL.md
    ├── docs/openapi.json            # fleet's own; drift-tested; box's docs/openapi.json untouched
    └── fleet.mk                     # fleet targets; NOT included from the root Makefile (root `make test` stays the box's)
```

Rules that keep the box intact:
- No edits under `gateway/`, `agents/`, `tests/`, `compose.yml`, `Makefile`, `docs/openapi.json`, `skills/`, `.claude-plugin/`.
- Root `make test` must still report the same suite (178 tests, 1 skipped) after `fleet/` lands.
- Different compose project, networks, ports and container names (`fleet-*`). Never `browser-box-*`.
- **Before** merging to `main`, add `--exclude='fleet'` to `box-kit/scripts/export.sh`, or decide explicitly what of `fleet/` may become public.

---

## 3. What existing assets give vs what the fleet must build (gap table)

| Need | Existing asset gives | Fleet must build |
|---|---|---|
| Persistent per-profile browser state | Steel OSS `persist` → fixed `/app/api/user-data-dir` (`hands-on`). Trial: Chromium `--user-data-dir` per profile. | A one-container-per-awake-profile wrapper and volume lifecycle. `Singleton*` cleanup. A cookie-flush-safe release (wait or graceful close). An auth-marker probe after every wake. Encrypted volume backup. |
| Same fingerprint / IP every time | Steel schema has `proxyUrl`, `userAgent`, `timezone`, `dimensions`, `skipFingerprintInjection`, `deviceConfig` (`source-code`). No existing asset pins these per profile. | A per-profile pin record (proxy endpoint, UA, timezone, viewport, fingerprint seed) applied identically on every wake. Detection of drift (exit IP check against the pin). |
| Many profiles concurrently | `lock.py` named lanes (one host). An earlier DB lease design with a one-lease-per-profile rule (safe only serially). | Fleet lease service, per-host capacity accounting, wake/sleep scheduler, multi-droplet worker enrollment. |
| URL safety in the browser | `security.py`, `guard.Guard`, `scope.ts`, the 18-attack suite. | A per-browser Guard supervisor and per-container proxy-only egress. Re-run the shield check per image. |
| System-1 action choice | `jev-automation/core/decide.ts`/`verify.ts`, the trial's model and desktop modules, vendored jev-ultrafast. | Integration with Stagehand's observe/act loop. Per-procedure confidence thresholds measured on target sites. Measurement of the actual System-1 share (no existing number). |
| Engine selection (Stagehand vs Browser-Use) | B5 method (act vs task). Trial route reasons (`system_one_first` vs `reasoning`). | A router with logged reasons. Per-procedure engine choice from measured results ("measure, then write the winner"). |
| Posting and messaging safety | Publishing-safety taxonomy. Earlier internal approval manifests. Intent journal and receipts. Uncertain-hold. | Campaign manifests for social posting. Platform-specific receipt checks (the post exists on the profile page, the DM appears in the thread). Per-profile and per-platform rate caps. |
| Human login / re-auth | Box: devtools URL through an SSH tunnel (dev only). Trial: one-hour takeover lease. | Authenticated live-viewer brokering per profile and a re-auth queue with notifications. Agents never see credentials. |
| Spend control | `data_box/ledger.py`, trial reserve/settle, the TypeSafe $5/month cap pattern. | Fleet-wide ledger with per-profile, per-client and per-provider caps (TypeSafe, OpenRouter, Browserbase, proxies). |
| Procedure memory and learning | Trial procedure registry and release rules. An earlier internal workflow registry. | Social-platform procedures, held-out evaluation sets, a quarantine and release pipeline, and Obsidian-backed notes per profile. |
| Hermes distribution | box-kit Hermes skill and config snippet. TypeSafe rollout blueprint. hermes-workforce-router hook. | The fleet Hermes plugin and skill and per-profile token issuance (hermes-packaging dossier). |
| Upstream drift | An internal drift-watch pipeline. browser-use `confine()` version self-check. | Pins and self-checks for Stagehand, Browser-Use and the Steel image digest. Watch queries for them. |

---

## 4. Operating notes for a Hermes agent (feeds the skills later)

These come from the existing code and the spike. Each is a rule a fleet-browser skill should teach or enforce.

- **Treat infra "200 OK" as unproven.** Self-hosted Steel answered `POST /v1/sessions` with 200 while serving a fresh, logged-out browser, because the profile lock was stale (`hands-on`). After every wake, check a per-site logged-in marker. If it is absent, report `needs_reauth`. Do not try to log in.
- **Do not release a profile right after a login or an auth refresh.**
  - Released about 5 s after the cookie was set, it was lost. After 40 s it was kept (`hands-on`, n=1).
  - This happened even though Steel's release calls `browser.close()` and then `kill()`.
  - Until a better mechanism is proven, wait at least 30-40 s after the last auth change.
  - Untested alternative: export Steel's session context before release and inject `sessionContext.cookies` on create.
- **Call shape for self-hosted Steel (pinned image `sha256:7a161b95…`):**
  - `POST /v1/sessions {"persist": true, "proxyUrl": ..., "userAgent": ..., "timezone": ..., "dimensions": {...}}`.
  - `userDataDir` values, `persistProfile` and `profileId` are ignored.
  - CDP at `ws://<steel>:3000/`, dialled by IP or `localhost` (Chromium rejects other Host headers; see `guard.dialable`).
  - `POST /v1/sessions/release` may return 500 and leave no browser. Health-check, and recreate the container if needed.
- **One profile, one writer.** Never run two agents in one profile, and never treat a tab as an account boundary. A "profile busy" answer is an answer: wait or move on, as with the box's `LaneBusy`.
- **Refusals are answers.** A refused private address or a `needs_confirmation` must be reported, not worked around (the box's `run_tool` contract).
- **System 1 picks, code acts, the reasoning model writes.** Jev answers `choice`, `noul` or `score` over options code built: elements (≤255, the box uses ≤180 plus `none`), procedures, supplied values. Use effective confidence = `min(confidence, probability of the chosen option)` (trial model gateway). Below the threshold, abstain and escalate. Text comes from the approved manifest or the reasoning model, never from page content.
- **TypeSafe call shape seen in source:**
  - `POST https://api.typesafe.ai/v1/systemone`, bearer key, body `{model:"jev-1.13.0", state:{...}, questions:{name:{type:"choice", criteria:{id:label}, instructions}}}`, from an earlier internal model client.
  - SDKs `@typesafe-ai/sdk ^0.6.0` and `typesafe-sdk==0.6.0`.
  - Handle the price as a dated vendor figure: $0.042 per million input tokens, output free.
  - The System-1 dossier should confirm all of this against live docs.
- **Thresholds that exist, unvalidated for social sites:** intent 0.25, target 0.35, risk 0.6, submit 0.6 (`jev-automation/core/decide.ts:80-95`). Tune them per procedure on held-out cases.
- **Use `verify` blockers as health signals:** `login_wall` means `needs_reauth`; `captcha` means pause the profile and alert (do not solve blindly); `consent_dialog` and `popup` have known dismiss procedures; `no_change` means stop and do not repeat. Stop after three identical actions (trial desktop loop).
- **Never auto-retry an uncertain effect** (post, reply, DM, follow). Journal intent first, check the receipt, and hold anything uncertain for reconciliation (the procedure-registry and job-claim patterns).
- **Browser-Use only for open-ended read goals by default.** In a logged-in profile, page text can steer it (`docs/security.md` limit 7). Keep `upload_file` and `save_as_pdf` excluded. Before reusing `runner.py`, check the browser-use version: `confine()` refuses anything but its pin (0.13.10 now; scratch venv has 0.13.11).
- **Memory:** per-profile notes go to Justin's Obsidian vault, not to the browser profile or a database-only store.

---

## 5. Risks and unknowns

1. **Silent auth loss in Steel OSS** (`hands-on`).
   - A stale `SingletonLock` produced a fallback to a blank browser behind HTTP 200.
   - A fast release lost the cookie.
   - A release can 500 and leave no browser.
   - Each was observed once or twice. Repeat at scale on amd64 droplets before trusting any timing.
   - Steel already calls `browser.close()` before `kill()` on release, so it is unknown why the flush was missed.
   - Fixes not yet tested:
     - export and inject Steel's session context;
     - a fixed `--hostname` per profile container, as an alternative to deleting `Singleton*`.
   - Another agent's container `fleet-spike-antidetect` was running at about 03:03 UTC on the same Docker host. This agent did not touch it.
2. **Steel OSS is single-session per process** (`source-code`, `hands-on`). Fleet density depends on one container per awake profile. At about 550 MiB right after one example.com session (`hands-on`), and about 900 MiB-1.36 GiB under real load (box README / B5), RAM per awake profile caps concurrency per droplet. Waking, not count, is the scaling variable.
3. **browser-box `session` overclaims slightly** (`hands-on` + `source-code`).
   - Its card says "keeps cookies and a profile across calls". That holds only within one Steel lifetime.
   - `persistProfile` is ignored by OSS Steel, and compose mounts no profile volume.
   - Under charter invariant 1 this should be corrected in the box by its owner. **Reported here, not changed.**
4. **No measured System-1 share or accuracy on any social platform.** The trial ran 0 live cases and B5 has a Jev search grounding miss. "90%" is unproven.
5. **Prompt injection through social content.** DMs and comments are attacker-written and agents act logged in. Browser-Use is the most exposed. Procedures with code-built options are the mitigation, and that is unmeasured.
6. **Anti-detection on Steel is untested by any existing asset.** The older local tool's matrix is about other products and partly vendor claims.
7. **Policy tension.** An earlier internal outbound-email project disclaims fingerprint spoofing and proxy rotation, while the fleet brief seeks anti-detect, proxies and stealth. This needs Justin's explicit position, plus platform-ToS and client-consent framing.
8. **Public export leak.** `box-kit/scripts/export.sh` archives the whole browser-box repo into a **public** repo. If `fleet/` merges to `main` before the export is updated, research, procedures or client details could be published.
9. **Repo visibility mismatch.** `jev-automation` is a **public fork**, along with `jev-agent-kit`, `super-saiyan-browser`, `hermes-workforce-router` and `box-kit`. Do not put fleet procedures, client names or account handles there.
10. **Version drift.**
    - Browser-Use: pin 0.13.10 vs scratch 0.13.11.
    - Steel: the image is 2026-09-16, the source clone 2026-10-06.
    - TypeSafe: `jev-1.13.0` is pinned in two places.
    - Any upgrade can silently change confinement or persistence. The drift watch does not yet track Stagehand or Steel.
11. **Guard DNS vs proxy DNS.** `guard.verdict` resolves hostnames locally, but a proxied Chromium resolves at the proxy. That is fine for the private-address check. Whether the guard's local lookups create a detectable signal, or mismatch geo-DNS, is unknown.
12. **Profile volumes are high-value secrets.** Their encryption at rest, backups and access control are not designed anywhere yet. The trial's portability deliberately excludes cookies, so there is no existing backup pattern for logged-in profiles.
13. **Stale docs inside sources.** The older local tool's provider pages are "last verified 2026-06-11". `docs/operations.md` says 167 tests (actual 178). The local checkout of that tool is behind its origin. Treat dated numbers as dated.

---

## 6. Sources

Related repositories were read read-only on 2026-10-09. Pinned commits, file lists and local paths for private repos are withheld from this public copy. Steel: `steel-browser` @1131a02 and image `sha256:7a161b95…` (created 2026-09-16).

Spike (this agent, 2026-10-10 03:03-03:08 UTC, $0):
`fleet/research/spikes/existing-assets/{steel_persist_probe.py,steel_persist_probe2.py,RESULTS.md}`.
