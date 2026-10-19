# Browser Fleet: architecture

> **Superseded in part (Justin, 2026-10-19; DECISIONS "guardrails, not rules").** Red-line refusals, the
> host table, `people_list`, N-4 and "agents never type credentials" below are design history. They are
> now guardrails per client; the policy gate warns and asks, it does not refuse them.

Status: **design, written 2026-10-10. Nothing here is built.** Every component, table, tool and flow below is a
target. Where a number comes from a measurement it cites the evidence; everything else is labelled.

This file follows [DECISIONS.md](DECISIONS.md) (D1-D18). Where it adds to or disagrees with that record,
section 9 says so. It was revised on the same day after the 14 scenario stress tests
(`research/scenarios/S01.md` to `S14.md`); section 9.5 is the ledger of every gap and where it is handled. Vocabulary (fleet, fleetd, profile, identity, wake, sleep, channel, procedure, System 1,
System 2) is defined at the top of DECISIONS.md and is not repeated.

## 0. How to read this file

Markers used throughout:

| Marker | Meaning |
|---|---|
| **[unbuilt]** | Designed here, no code exists. (Everything is unbuilt; the marker is used where a reader might assume otherwise, for example next to a reused box module.) |
| **[pending Q-nn]** | Depends on a question only Justin can answer (list at the end of DECISIONS.md; map in section 10). The text proceeds on the recommended default. |
| **[extension]** | A design element this file adds that DECISIONS.md does not contain. Each is listed in section 9. |
| **[to measure]** | A number or behaviour no one has measured. M1 is the droplet milestone; M3 is the model-provider milestone (DECISIONS.md D5, D8). |
| **estimate** | An arithmetic or planning figure with a stated basis. Not a measurement. |

Citations point at files under `research/`. Precedence rule from the task: where a dossier and its
verification report disagree, the verification report and DECISIONS.md win. This file cites dossiers only for
claims the verifiers confirmed, or states the correction.

Milestones and dependencies only. There are no dates or durations for future work in this file.

## 1. The system at a glance

### 1.1 One picture

```
 HERMES SIDE  (any number of hosts; one profile holds one scoped token and nothing else)
 +------------------+  +------------------+        +-----------------------------+
 | Hermes profile   |  | Hermes profile   |  ...   | Jev Workforce trial employee |
 | fleet-* skills   |  | fleet-* skills   |        | MCP entry + prose guides     |
 | Obsidian writer  |  | Obsidian writer  |        | skills only (no plugins)     |
 +--------+---------+  +--------+---------+        +--------------+--------------+
          |  HTTPS, Authorization: Bearer <profile token>         |
          v                                                       v
 +--------------------------- CONTROL PLANE: fleetd ----------------------------------+
 | doors:  MCP | HTTP+OpenAPI | internal (mTLS) | operator console                      |
 | auth+admission | policy gate R | registry | leases | jobs+scheduler+placer+capacity   |
 | run engine | procedures+manifests+approvals | /decide (System 1) | model shim        |
 | connectors+governor | inbound (webhooks, conversations) | media store | research     |
 | effect ledger+reconciler | spend ledger | viewer broker | evidence+audit | notifier   |
 | metrics                                                                                 |
 +---+---------------+------------------------+--------------------+-------------------+
     | SQL           | objects                | mTLS (commands)    | HTTPS
     v               v                        v                    v
 Postgres        Spaces                 +--- NODE PLANE (droplets) ---+     Platform APIs
 (source of      (state bundles,        | node agent                  |     (Meta, TikTok,
  truth)          evidence)             |  per awake identity:        |      X, LinkedIn)
                                        |   holder = one namespace +  |
                                        |   egress rule; forwarder,   |     Model APIs
                                        |   steel-profile, runtime    |     (OpenRouter,
                                        |   (guard, exporter), actors |      TypeSafe, ...)
                                        |   (executor, Stagehand,     |     called ONLY
                                        |   Browser-Use)              |     from fleetd
                                        +--------------+--------------+
                                                       |
                                                       v  the identity's only egress
                                              dedicated static ISP IP (one per identity)
```

Three planes and one side:

| Plane | What lives there | Scales with |
|---|---|---|
| Hermes side | Profiles, `fleet-*` skills, the optional plugin, the Obsidian writer. Outside the fleet's control except through the token. | Number of profiles |
| Control plane (fleetd) | Everything that decides, records or is secret: policy, ledgers, leases, model keys, platform tokens. | Number of identities and calls |
| Node plane | Everything that touches a browser: containers, forwarder, guard, workers. | Peak number of awake browsers |
| Stores | Postgres (truth), Spaces (bundles, evidence). | Identities, evidence retention |

### 1.2 Ten rules that shape every later section

1. **One shared service.** A profile holds a token. Skills are read-only and shared. (D1)
2. **An identity is pinned at creation** (infra home, one dedicated IP, persona, state-bundle home) and
   never drifts. A mismatch refuses the wake or stops the session. A new IP or home is a new device generation
   under the **same account**, whose ledger, caps and manifests carry over. (D3)
3. **One writer per identity.** The lease carries a fencing token. The thing that acts (node agent,
   executor) checks the token on every command. A counter that is only stored is not fencing. A human lease
   follows the open viewer, and no agent can start beside it. (D12)
4. **State at rest, browsers on demand.** Never always-on at scale. (D12)
5. **The ladder stops at the first rung that works** (L0 code/API, L1 replay, L2 System 1, L3 a model choice run
   by the identity's executor, L4 Browser-Use, L5 human). Irreversible actions are gated by deterministic policy
   on every rung, free-form `act` and `task` included, never by a model probability, and an effect step never
   climbs past L1 into a free-form click. (D5, D18)
6. **Effects are journaled before they happen,** read back after, and never blindly retried. (D13)
7. **Humans authenticate. Agents never type credentials** and never solve CAPTCHAs on client accounts. (D14)
8. **Every call returns inside the 90 s budget.** Longer work is submit-then-poll. The Hermes default is
   300 s, a plugin-less host writes 90 s with a 20 s connect timeout. (D1, C-15, HP-5)
9. **Memory is Obsidian, written on the Hermes side.** fleetd returns structured evidence; it does not write
   the vault. (D15)
10. **Red lines are refused in code, not by prompt.** A policy gate (R) runs on every tool call; a like, a
    follow, a cold DM, or agent browsing of x.com or LinkedIn gets `refused`, and no approval can unlock it.
    (D2, D17; Charter)

### 1.3 What the fleet reuses from the box, and what it does not

The box (the enclosing repository, charter and modules unchanged) supplies patterns and a few modules.
The fleet has its own charter **[unbuilt]**; the box's invariants are not edited. Reuse map
(`research/dossiers/existing-assets.md` Q4, as corrected by `research/verification/existing-assets.md`):

| Box / sibling asset | Fleet use | Condition |
|---|---|---|
| `gateway/security.py` (URL classifier) | Copied at a pinned box commit, with a test that fails if it drifts from the box file | D16, C-25 |
| `guard.Guard` (CDP `Fetch` interception) | Class reused; one instance per awake browser; the gating contract (`wait_ready`, re-gate after relaunch, cancel work when the guard drops) is rebuilt per identity because the box binds it to a module singleton in `tools.py` | C-25 |
| Shield-check attack suite | Ported off jev-automation's Playwright executor to a CDP client; it is 11 attacks plus 7 positive/behavioural controls (not "18 attacks"); runs as a deploy gate per Steel digest and per `steel-profile` version | C-25, existing-assets V-1 |
| `lock.py` (`flock` lane) | Semantics only (one writer, a busy answer that names the holder). Rebuilt as a DB lease | O-03 |
| `steel.py` | Not copied. It sends Steel Cloud fields (`persistProfile`, `profileId`) that self-hosted Steel strips with HTTP 200 | C-04 |
| `TOOLS` list -> MCP + REST + OpenAPI pattern, `run_tool` refusals-as-answers | Pattern only: a separate `FLEET_TOOLS` list, its own `docs/openapi.json`, a drift test | existing-assets Q1(a) |
| An earlier internal job-claim design | Not copied. It is safe only serially | EA-7, C-14 |
| The Jev Workforce trial's procedures, models, receipts (private; details withheld) | Pattern: digest-pinned procedures, intent-before-click, receipts, uncertain-hold, release rules. Its receipts are verified against a synthetic backend; browser receipts on real social sites are a hypothesis | SCA-9 |
| `data_box/ledger.py` | Pattern for the spend ledger: reserve, settle, interrupted = charged in full, request-id idempotency | existing-assets Q2 |

## 2. Components

All components are **[unbuilt]**. fleetd is one Python deployable (the box is Python; existing-assets Q4
proposes a `fleetd` package). It runs as several processes from one codebase:
`api` (doors), `scheduler` (jobs, placer, schedules), `reconciler` (effects, lease expiry, drift),
`decide` and `model` (the two provider-facing services, separate so a slow provider cannot stall the doors)
**[extension]**.

### 2.1 Control plane: fleetd

| # | Component | Job | Owns (state) | Notes and sources |
|---|---|---|---|---|
| C1 | **Doors** | MCP over streamable HTTP; HTTP/JSON with OpenAPI; an internal mTLS API for node agents and workers; an operator console for humans (its functions: `identity create`, bind, quarantine, retire, approve, take over, mark an uncertain effect found or absent, `hold_clear`, cutover, set the click mode; 4.15, 6.13). Public tools come from **one** `FLEET_TOOLS` list, so MCP, REST and `docs/openapi.json` cannot drift (drift test). | none | D1; box pattern in existing-assets Q1(a). The fleet owns the MCP server, so it also owns how often sessions expire: keep idle streamable-HTTP sessions long or run stateless, because Hermes returns `outcome_uncertain` for non-read-only tools after an expiry (HP-8, hermes-packaging missed issue 7). |
| C2 | **Auth, admission and policy** | Token to binding to scopes. Per-token and per-tenant admission limits. A pure, deterministic gate: scope, identity state, channel policy, manifest or approval resolution, governor, effect classification. No model is in the gate. The red-line gate R is C18. | tokens (hashed), bindings, policy decisions | Rejects a bearer that looks like `${...}` (HP-1). Never trusts `X-Hermes-Profile`: Hermes sends it on session traffic but not on the HEAD/GET preflight (HP-9). Enforces a minimum skill version per token (X-1). |
| C3 | **Registry** | Tenants (clients), **platform accounts**, identities (device generations), personas, proxy inventory, infra homes, platform connections, operators. Unique `(platform, handle)` over non-retired accounts so one live account can never be bound twice. | Postgres tables, section 3 | Identity creation is an owner-only flow, not an agent tool (D17; 4.15). |
| C4 | **Leases** | One writer per identity: acquire (with state, hold and open-effect predicates), renew, takeover, release, each a separate statement. DB-enforced; fencing token bumps only on a new holder; eight purposes; a human lease follows viewer liveness. | `identities` lease columns, `lease_history` | Designed fresh. The scale-infra SQL cannot express takeover and bumps the token on every renewal (SCA-10, C-14). Section 3.5. |
| C5 | **Jobs, scheduler, placer** | A Postgres job queue whose claim locks the identity row and applies the acquire predicates, with a weighted fair claim across tenants. Pre-wakes identities before scheduled jobs. The placer picks a node by tenant, node class, region, capacity and last-node cache; the capacity planner (7.8) reserves nodes ahead. | `jobs`, `schedules`, node inventory | D12. Temporal (on Postgres, `REJECT_DUPLICATE` plus retention) is a later option at the multi-node milestone. A fallback that re-runs failed workflows must not be used (SCA-8). |
| C6 | **Procedures, manifests, approvals** | Digest-pinned procedure registry with authority, verifier and mandatory `target_rule` on effect steps; campaigns and immutable approved manifests with triggers; per-action approvals with `in_reply_to` and warnings; first-post gate. | `procedures`, `campaigns`, `manifests`, `approvals`, `account_firsts` | D13; trial pattern (`research/dossiers/existing-assets.md` Q3). A new procedure version that contains an effect step is released after three distinct accepted outcomes; non-effect L1 entries are machine-promoted; rollback is per version (3.7). |
| C7 | **Run engine** | Executes a procedure as a state machine. Sends one step at a time to the node executor under the fencing token; applies the gates; pauses for humans; resumes. Owns no browser I/O. | `runs`, `run_steps` | Section 4.2. |
| C8 | **/decide (System 1)** | One request shape for all decision models, provider adapters, rate limits, question packing, thresholds, escalation, calibration logs. Section 2.4. | `decision_log`, `thresholds` | D7. |
| C9 | **Model shim (System 2)** | Every generative call from Stagehand and Browser-Use goes through it. Section 2.5. | `model_calls` (in the spend ledger) | D8. Provider keys live here and only here. |
| C10 | **Platform connectors** | The API channel: Meta Graph (Pages, Instagram professional, Messenger), TikTok API for Business, LinkedIn Community Management, X API v2. One interface, four implementations. Section 2.6. | `connections` (encrypted tokens) | D2. |
| C11 | **Governor** | Rate and budget windows per account (keyed on tenant, platform, handle), per app **with a per-tenant share**, per grantor or member, per provider, per identity-day, with read classes (effect, read-back, health, analytics) and human effects counted. Ceilings are ceilings, never targets. | `governor_windows` | Built from live `x-rate-limit-*` response headers where they exist, not constants (D2, SP-3). Each platform names its live source or is marked static and "to verify" (3.13). Tenant shares and kill switches: 4.17. |
| C12 | **Effect ledger and reconciler** | Idempotency key on the account and authority, intent row before the effect (with approval consumption), tri-state read-back receipt, scoped hold when uncertain. The reconciler runs read-only jobs to settle `uncertain` rows. | `effects`, `holds` | D13. Sections 3.6, 3.11. |
| C13 | **Spend ledger** | Reserve before every paid unit, settle after; an unknown outcome keeps its reservation. Caps per identity, client, provider and fleet. Workers take leased budget slices and settle in batches, so one hot row does not serialize the fleet (4.17). | `spend` | Pattern from `data_box/ledger.py` (micro-dollar integers). Covers models, System 1, proxies, X API fees, Browserbase, droplet-hours. |
| C14 | **Viewer broker** | Mints tickets, exchanges one for a viewer session, renews the human lease from the open socket, reverse-proxies only the viewer routes of one container, shows starting/ready/checking/done/failed, hosts the clipboard bridge, applies the domain policy. | `viewer_tickets`, `viewer_sessions` | D14. Sections 4.8, 4.14, 6.5. Operator authentication is AQ-1, a blocking item of M2. |
| C15 | **Evidence store and audit log** | Screenshots, gzipped a11y snapshots, action logs, decision records in Spaces; an append-only audit table in Postgres. | `evidence`, `audit` | Evidence on failure and on every effect; video only on failure or a sample. Retention is an estimate (30 days hot, audit 1 year; scale-infra Q3). **Class `lead_source`** holds the exact model-shim request body (the text the model saw) for lead work and is retained as long as the lead is (N-10); the quote, URL, fetch time and `content_sha256` are also kept inside the lead record and note, so provenance survives blob expiry (S04-9). |
| C16 | **Notifier** | Delivers viewer tickets to the named person (and only there). Tells owners about `needs_reauth`, `checkpoint`, `needs_approval`, **the first `uncertain` effect and again at the end of grace**, IP or persona drift, a failed bundle upload, budget caps, **window closing**, **item missed or expired_unrun**, **procedure or step quarantined**, **L1 mismatch storm**, **item skipped: not_released**, **repeated step failure on one host**, **suspected injection**, **inbound budget spent**, **an incident**. Alerts group by cause. | `notifications` | Destinations (Slack, email, webhook into Hermes) are AQ-3, a blocking item of M2. The body names account, platform and reason; it never carries page content. |
| C17 | **Metrics** | Identities by state, node slots, wake latency p50/p95, **System-1 share per procedure** (L0+L1 only on logged-in procedures until a provider/host pair is cleared, 4.3), cost per identity-day, checkpoint rate per platform, effects by state, L1 mismatch rate, L3 spend, `uncertain` surges. | time series | D7 metric: actions completed with no generative call (L0 + L1 + L2) over all browser actions. |
| C18 | **Policy gate R** **[extension]** | Deterministic, table-driven, ahead of gate G on every tool call: host policy (D2's table), effect-kind deny list, recipient eligibility, duplicate content, URL classification. Answers `refused` or `scope_denied`. | none (reads D2's table, `channel_policy`, 3.12) | Section 4.3. The Charter's "refused in code, not by prompt". |
| C19 | **Inbound pipeline** **[extension]** | Webhook receiver with signature check and event-id dedupe; conversation and window tracker; opt-out ledger; per-account inbound metering; the `inbox` read. | `inbound_events`, `conversations`, `opt_outs` | Sections 3.12, 4.12. Push into Hermes is unresearched. |
| C20 | **Media store** **[extension]** | Ingest, convert, hash and validate media before approval; serve from the verified domain on short-lived unguessable URLs. | `media_assets` (Spaces) | Section 3.13. |
| C21 | **Capacity planner and admission** **[extension]** | Awake-count forecast from manifest windows; node reservations; per-node wake cap; per-token and per-tenant limits; weighted fair share. | `nodes`, planner state | Sections 4.17, 7.8. |
| C22 | **Connector support** **[extension]** | OAuth start and callback, scope selection, consent ledger, token-refresh scheduler, revocation handling, platform-app state. | `consents`, `connection_health`, `platform_apps` | Section 3.13. |
| C23 | **Research services** **[extension]** | Source registry, robots and politeness check (fail-closed), per-host pace, lead records, `http_only` fetch worker. | `source_registry`, `leads` | Sections 3.14, 4.13. Exists before the lead-gen skill is released. |

### 2.2 Node plane

A **node** is one droplet running the node agent and, per awake identity, a small group of containers that share
one network namespace owned by a **holder**.

```
 node (droplet)
 +------------------------------------------------------------------------------------+
 | node agent (systemd, Python)     <--- mTLS commands from fleetd only               |
 |   bundle cache (LRU, encrypted)   highest-fencing-token-seen per identity (on disk)|
 |   docker + nftables control       heartbeat: slots, disk, image digests            |
 |   fence file per identity         viewer route allow-list; watchdog                |
 |                                                                                    |
 |   per awake identity  -------------------------------------------------------      |
 |   | holder  fleet-net-<id>   owns the network namespace and the hostname;     |    |
 |   |                          runs nothing                                      |    |
 |   | egress rule: this namespace -> its vendor proxy IP:port ONLY (host nftables)|   |
 |   |                                                                            |    |
 |   |  forwarder   127.0.0.1:<f>  holds proxy credentials, checks exit IP        |    |
 |   |  steel-profile (pinned Steel digest + wrapper, flavor account|research)     |    |
 |   |    Steel API+CDP on 127.0.0.1:3000 (unauthenticated; never published)      |    |
 |   |    Chromium, volume at /app/api/user-data-dir  (extension: research only)  |    |
 |   |  runtime     guard (CDP Fetch interception), exporter, login prober        |    |
 |   |  actors      executor | Stagehand worker | Browser-Use worker (one          |    |
 |   |              container each; the only containers that send input)          |    |
 |   --------------------------------------------------------------------------   |    |
 +------------------------------------------------------------------------------------+
```

This is the layout of `docs/infra/steel-profile.md` section 2.2 and 3.1, which this file follows.
Earlier drafts had Steel own the namespace and one `identity-runtime` container hold the forwarder, guard,
executor and workers. That changed for these reasons (S04-4, S13-6; **design choice to confirm in M1; C-08 is
unverified**):
- DECISIONS D4/D10 say Steel is given `http://127.0.0.1:<port>` of a node-local forwarder. A container's
  loopback is not the node's loopback, so the forwarder must live in the browser's namespace. A **holder** that
  owns the namespace lets the forwarder be up and checked **before Steel exists**, which is what the research
  `http_only` mode and `probe_ip` need (no Steel, no bundle; 4.13).
- Stagehand v4's extension opens its own WebSocket to the same `cdpUrl` the SDK uses
  (`research/dossiers/stagehand.md` Verdict 2c). With both on `ws://127.0.0.1:3000/` inside one namespace, one URL
  is valid inside and outside the browser, and Chromium sends loopback direct, so `PROXY_INTERNAL_BYPASS` stays
  empty (the antidetect rule wins over the stagehand rule in C-08). No exception for the bridge IP is needed.
- Steel echoes `proxyUrl` in create/list/get responses over an unauthenticated API
  (`research/dossiers/steel.md` Verdict 4). The echoed value is `http://127.0.0.1:<f>`: no credentials.
- The credentials live in the forwarder container (tmpfs file, mode 0400), which no actor can read.
- Cost of the choice: everything in the namespace can reach everything else on loopback. The executor
  therefore authenticates every command with a per-wake key, and the guard blocks page access to
  loopback and private ranges (the 2026-09-22 redirect exploit class, SCA-14). Killing the actor containers on a
  higher fencing token is one `docker kill` per actor, while the Guard stays up.
- Open interactions **[to measure, M1]**: the guard's `Fetch` interception against the extension's loopback
  WebSocket (research flavor); containers sharing one namespace against Docker's `--init` and restart behaviour;
  whether one `identity-runtime` or per-actor containers is the better packaging (`docs/infra/steel-profile.md`
  section 10.3).

| # | Component | Job | Notes and sources |
|---|---|---|---|
| N1 | **Node agent** | The only thing that talks to containers. Starts and stops identities; downloads, decrypts, tars and uploads bundles and periodic journals; creates and removes the holder, its egress rule and the group of containers; **derives `extension_mode` from identity kind, image flavor, persona and wake purpose** (never per wake from fleetd); enforces the fencing token (refuses a command whose token is lower than the highest seen, writes the fence file, and kills the actors when the highest token increments); idle reaper (skips identities with a human lease); restart on a memory threshold; heartbeat. Never calls `POST /v1/sessions` twice on one container. | Steel keeps one `activeSession` per process; a second create silently takes over the live browser and `GET /v1/sessions/{id}` then returns a fabricated `released` stub (`research/dossiers/steel.md` Verdict 1, STE-1). Ownership truth is fleetd's lease plus a live-argv probe. Docker allows only about 30 bridge networks by default, so networks are created per wake and removed on sleep (SCA-14 note). Never `docker stop` a live identity (it is a SIGKILL that leaves the lock, STE-4). |
| N2 | **`steel-profile` container** | Pinned Steel digest plus a wrapper, in two flavors. Common: `--init` (8 cycles left 151 zombies without it), volume at `/app/api/user-data-dir`, `NODE_OPTIONS=--unhandled-rejections=warn`, Xvfb and dbus if headful, SwiftShader flags for WebGL, `TZ`, `LANG`/`LANGUAGE` and `--accept-lang`, memory and CPU caps, no published ports, never the raw CDP port 9223. **`account` flavor: no Stagehand extension directory, no extension launch overrides, `--remote-allow-origins=*` filtered out through `FILTER_CHROME_ARGS` (to measure).** **`research` flavor: the extension at `/app/api/extensions/stagehand` and `extensions:["stagehand"]` on session create (mode A).** | D4, C-10, C-11, S14-4. `docs/infra/steel-profile.md` section 2. Image `sha256:7a161b95…` (2026-09-16, `@steel-browser/api` 0.5.3, Chromium 152) is the tested image; the source pin `1131a02` is not (D4 caveat). Run non-root with the sandbox on, or accept the risk in writing **[pending Q-08]**. Block the DigitalOcean metadata endpoint (O-11). |
| N3 | **Runtime, forwarder and holder** | The holder owns the namespace. The forwarder holds the proxy credentials and checks the exit IP. The runtime holds the Guard, the journal exporter and the login prober. Section 2.3. | Section 2.2 rationale above. |
| N4 | **Stagehand worker** (`research` identities, and `account` identities only where G1.4 selects it) | Stagehand 4.2.0 attached to the one browser: `localBrowser.connect({cdpUrl:"ws://127.0.0.1:3000/"})`, `Stagehand.create({browser, model:{generate}, selfHeal:false})`. One instance per browser. Never `browser.close()` (kills the Steel browser); use `stagehand.close()`. `generate` calls fleetd's model shim. | D6, D18; `research/dossiers/stagehand.md` Q2, Q3. Python SDK 4.2.0 is fully local and bundles the same extension (attach 43 ms and `act(Action)` with 0 model calls, hands-on; its memory figure has no raw artifact, V-10), so the worker is Python by default and TypeScript is the fallback **[extension]**. A crashed worker can wedge the browser, because the instance lock is released only by the `close` RPC; recovery is to recreate the session (SH-6). |
| N5 | **Browser-Use worker** | Browser-Use 0.13.11, one agent per container with a hard kill timer, attached by `Browser(cdp_url=...)` (not `BrowserSession(browser_profile=BrowserProfile(cdp_url=...))`, which comes out `is_local=True`). `flash_mode`, capped `max_steps`, `Tools(exclude_actions=[upload_file, save_as_pdf, evaluate])`, `highlight_elements=False`, proxy only on the Steel session, temp-dir cleanup. | D6; `research/dossiers/browser-use.md` Q1, Q4. A leaked `keep_alive` session hangs `asyncio.run()` at exit 3 of 3; exit from inside the loop. `allowed_domains` is not a boundary (#5815, #4763). |
| N6 | **Minimal CDP executor** | The `account` identity's default executor (D18): a small fleet-owned CDP client implementing the `Executor` interface (4.3): snapshot, run a fleet `Action` with a trusted-input path, observe a region. No page-injected code. | D18; S14-2. Its composer behaviour on Lexical and Draft.js is a G6a.5 item. |

### 2.3 Inside the namespace: runtime, forwarder and actors

| Part | Job | Fail-closed rule |
|---|---|---|
| **Forwarder** | Credential-holding HTTP forwarder on `127.0.0.1:<f>` to the vendor's dedicated ISP proxy. Checks the exit IP through itself at start, on a timer, and after any upstream error. | Any exit-IP change, mid-session included, drops all connections, writes a `proxy_mismatch` hold and stops the session. An upstream that is merely down, 407 or timing out is `proxy_unavailable`: no hold, a retryable failure (3.11). IPRoyal "sticky" sessions swap the IP silently unless `_killswitch-1` is set; set it (D10, antidetect missed issue 8). It never falls back to direct egress: that would change the IP the identity is known by. |
| **Guard** | `Guard(cdp_url=ws://127.0.0.1:3000/)`: `Fetch.enable` on every tab, frame and worker, classifier from `security.py`, deny list extended with the fleet's own hostnames, droplet IPs, VPC ranges and `169.254.169.254`. **Per-task navigation policy (S04-6, S13-8):** top-level navigations limited to the identity's `allowed_hosts` (and, for a research task, its registrable domain, sub-resources free); `robots.txt` on every top-level navigation of a research identity, click-triggered ones included; a refusal counter (6.7). | If the guard drops, tools fail closed (`infra_unavailable`) and work is cancelled. Its DNS check resolves locally while the proxy resolves remotely, so it is advisory; the network rule is the real control. CPU cost per awake identity is **[to measure]** (C-25). |
| **Executor** (an actor) | Accepts one step command at a time from fleetd (through the node agent). Every command carries `identity_id`, `fencing_token`, `command_key`, `job_id`, `step_id`. It refuses stale tokens and unknown keys. It owns the ladder L1-L3 for the step (section 4.3) through the `Executor` interface, the snapshot, candidate building, the **blocker check before and after each command** (4.2) and the post-action check. | Refuses typing into credential or 2FA fields (section 4.3) and every login affordance (S05-2). |
| **Exporter and prober** | Context export (`GET /v1/sessions/{id}/context`, cookies incl. httpOnly) on a timer and before sleep; per-platform deterministic login probe (skipped for `research` identities). | A probe failure never triggers a login attempt. It sets `needs_reauth`. |

### 2.4 /decide (System 1)

One request shape for all providers: the TypeSafe System One family (`state` plus named `noul`, `choice`
and `score` questions), `POST https://api.typesafe.ai/v1/systemone` natively
(`research/dossiers/system1-models.md` Q1). Adapters translate to the others.

| Provider | Role in the router | Constraints carried (verified) |
|---|---|---|
| **Jev** `jev-1.13.0` | Default for text-state questions | Text only; modality enforced by the router because Jev silently accepts images and bills them as text (S1). 80 rps but 100K tokens/s, "dynamic": requests up 4x, tokens down 60% between 2026-09-17 and 2026-10-10. Context: use 32K. No rate-limit headers: limiting is client-side. Leans to the first option: shuffle candidates. |
| **Perplexity Decider** `perplexity/pplx-decider-v1.1-27b-20261006` | Screenshot questions | Verified through OpenRouter at 271 ms (n=1). 10 rps per org plus a token limit. An oversized image hangs ~1 min then returns 504: cap tiles. |
| **Clef** (flash) | Screenshot questions **once tested** | Clef images through OpenRouter are untested and OpenRouter's alpha decisions request has no `images[]`. Cloudflare serves 65K context; PrimeIntellect serves 16K, so pin the provider. ~300 rpm is an assumption. Silently truncates long text. |
| **OpenAI Decisions** `gpt-6-luna` | Optional spillover | Different shape (`input`, `predicate`, answers as an array, a `refusal` type). Public beta; limits and option cap unconfirmed. Build 2M TPM is about 5 steps/s at 6K tokens. |

Rules (D7, as verified):
- **Option cap is 255** for Jev, Clef and Perplexity (256 returns HTTP 400). Working step size is 180 plus
  `none`: that is jev-automation's client constant, not a provider limit (C-06).
- **Token caps bind first.** A 180-candidate step is 4.9-6.2K input tokens, not 1,000 (BRO-4, S1 V-04), so the
  limiter works in tokens per second per provider and spills over to another provider. Prune candidates
  well below the cap.
- **Confidence is not portable.** Thresholds are keyed by `(template, model version, serving provider,
  risk_class)`, each with a minimum confidence and a minimum margin (top1 minus top2). Starting values come
  from offline and shadow data, not from jev-automation's 0.25/0.35/0.6 or Gemini's 0.85 [to measure, M3].
- **Pin and log the serving provider** (OpenRouter reports it per call). Pin model versions, not aliases.
- **A decider is not a safety control.** Page text can steer it (TypeSafe's own "jaggedness" notes; the
  Perplexity cookbook says its risk score "is not a safeguard"). Irreversible actions are gated by policy
  (section 4.3 gate G).
- **L2 is closed on logged-in pages and on DM surfaces by default** (`docs/models/system1.md` section 3.6 rule 5;
  the table in 4.3) until a (provider, host) pair is cleared **[pending Q-07]**. The decider never sees a DM.
- Escalation ladder: replay or rule, then primary decider, then (on mid confidence) a second decider from a
  different family that must agree, then the reasoning model over the *same candidates*, then a human.

Request and response (internal; the public tools never expose it):

```jsonc
// POST /internal/decide   (job-scoped credential)
{ "request_id": "uuid", "identity_id": "...", "job_id": "...", "step_id": "...",
  "template": "pick_target@3",              // versioned; thresholds attach here
  "risk_class": "read | reversible_write | irreversible_write",
  "state": { "url": "...", "title": "...", "excerpt": "..." },     // filtered, small
  "images": [ "data:image/png;base64,..." ],                        // only vision providers
  "questions": { "target":  {"type":"choice","instructions":{...},"criteria":{"e1":"link \"Next\" -> /page/2/","none":"..."}},
                 "blocker": {"type":"choice", ...}, "done": {"type":"noul", ...} },
  "routing": { "providers": ["jev","decider"], "max_latency_ms": 2000, "max_cost_usd": 0.001, "shuffle": true } }
// response
{ "outcome": "decided | escalate | refused | error",
  "answers": { "target": {"choice":"e7","confidence":0.98,"margin":0.97,"passed_threshold":true} },
  "escalate_reason": null,   // low_confidence | low_margin | disagreement | refusal | rate_limited | timeout
  "provider": "typesafe", "model": "jev-1.13.0", "latency_ms": 312,
  "input_tokens": 5100, "cost_usd": 0.00021, "log_ref": "decision_log:..." }
```

Everything for a step goes in one request (target, blocker, done, risk): one call and one rate-limit slot
(`research/dossiers/system1-models.md` Q5). Every call is logged with full-precision probabilities, option
order, provider and an independent outcome label for calibration.

### 2.5 Model shim (System 2)

`z-ai/glm-5.3-flash` at `reasoning.effort="low"` is the default for L3 (Stagehand on `research` identities, the fleet's L3-lite on `account` identities, D18) and Browser-Use L4 (D8).
The shim is mandatory for every model, not just GLM. It:
- always sends `provider.require_parameters`; validates every response against the full schema, including
  patterns (strict `json_schema` enforcement is provider-dependent: one provider returned wrong shapes 4/4,
  another YAML with HTTP 200; REA-7);
- sets a mandatory `max_tokens` per call type (runaways ran to 8K tokens, 34-52 s each, 7-8% of click acts
  on a 6K-token page, Wilson 3-18%; C-22, REA-3);
- retries once on another provider on invalid output, `finish_reason=length`, or a `null` element; repair
  ladder: another GLM provider, then DeepSeek V4.1 Flash (reasoning off), then the screenshot path with GLM
  vision;
- keeps a **bench-gated provider allowlist** with price and quantization caps; the per-provider benchmark
  is an M3 gate and the ZDR requirement changes the list **[pending Q-07]**;
- lowercases only a click's mouse-button argument, never typed text or key names;
- serves three faces: a Stagehand `generate` endpoint; an **L3-lite candidate-choice endpoint** (a generative choice among structured candidates with the same `{elementId, method, arguments}` schema as L2, D18); and an OpenAI-compatible endpoint (with
  `require_parameters` honoured, which Browser-Use's plain `ChatOpenAI` cannot send) for Browser-Use via
  `ChatOpenRouter` (0.13.11 or later) or an httpx hook.

Workers hold a short-lived, job-scoped credential for the shim and never see a provider key. Prompts leave
fleetd's IP, not the identity's (D6).

### 2.6 Platform connectors (API channel)

One interface **[extension]**, four implementations:

```
 PlatformConnector
   capabilities(account)        -> {publish, comment, reply_dm, private_reply, analytics, ...}
   publish(item, idem)          -> {platform_id, url?}          # an EFFECT: goes through the ledger
   reply(conversation, text)    -> {...}                         # an EFFECT; conversation from the inbound store
   private_reply(comment_id, text) -> {...}                      # an EFFECT; own route, own 7-day limit, 750/h/Page
   inbound(since)               -> events[]                      # webhook receiver (C19) plus a catch-up read
   thread(conversation)         -> messages[]                    # read before every send (a person may have replied)
   readback(effect)             -> {result: found|absent|unobservable, observed_hash, ref}   # the receipt source
   limits(account)              -> {windows from live headers, or static caps flagged "to verify"}
   health(account)              -> {token_ok, scopes, expires_at}    # writes connection_health; never identity state
```

Receipt rule: the id returned by the write, then a fetch by id, then a normalised-text compare. List-and-match is
a fallback after a timeout only. Normalisation is defined per platform at build time and its false-negative rate
is logged (G4A.1). The fleet never adds a visible marker to a client's post (S02-10). OAuth, consent, token
refresh and platform-app state are C22 (3.13).

Constraints the connector and governor carry (dated; re-check at build time; D2, `research/verification/social-platforms.md`):

| Platform | Carry |
|---|---|
| X | Governor from live `x-rate-limit-*` headers. Every `dm.received` and `post.create` webhook event is billed ($0.010; SP-4), so inbound is metered per account (3.12). The "10,000 posts / 1,440 DMs per app per day, shared by all clients" figures are legacy Pro-plan columns and unproven for pay-per-use (SP-3); per-account limits bind first for unverified accounts: 50 posts + 200 replies/day, 500 DMs/day, 400 follows/day, API included (V-2). Fees: $0.015/post, $0.20/post with a URL, $0.015/DM (official-docs, subject to change). Automated accounts carry X's "Automated" label **[pending Q-05]**. |
| LinkedIn | Community Management API version 202510 sunsets 2026-10-15; Development tier 500 calls/app/day and 100/member/day (V-3). |
| Meta | Messenger 24 h window, 7-day human-agent window, 30 s bot-response rule; Instagram 100 API posts/24 h; Facebook Reels 30 per Page per 24 h (V-5, SP-5). System-user tokens versus per-client OAuth is a per-client onboarding choice **[pending Q-06]**. |
| TikTok | Accounts API access form (mandatory since 2026-03-20); the Content Posting API audit rejects internal "upload for accounts you manage" tools, so an agency may face the same test (SP-11); Business Messaging is open beta, unavailable in EEA/CH/UK (V-4). |
| Facebook Groups | No API (removal rests on forward-looking changelog text and vendor corroboration, SP-7): browser channel only, `human_clicks` by default, with the client's written risk acceptance (D2 table row 2). |

Connector credentials (OAuth tokens, system-user tokens) never leave fleetd. One developer app per
platform is owned by Justin's business and authorized by each client; approvals are milestone dependencies
**[pending Q-06]**. Consent-based lead channels (Lead Ads, opt-in DM capture, LinkedIn Lead Gen Forms, TikTok
instant forms) are connector capabilities, not browser work **[pending Q-14]**.

### 2.7 Hermes side

| # | Component | Job | Notes and sources |
|---|---|---|---|
| H1 | **Profile config** | `mcp_servers.browser_fleet` with `Authorization: "Bearer ${BROWSER_FLEET_TOKEN}"`; the token lives only in that profile's `.env`. `agent.disabled_toolsets: [browser]` so there is no unmanaged second browser and no `browser_vault_*` credential typing. **The provisioner also applies the tool policy of `hermes/README.md` 2.4 (G11-8) [extension]:** `mcp_servers` holds `browser_fleet` plus only owner-allowlisted servers, never one that can post, DM, like, follow or read people on a social platform, a people-data or enrichment server, or a desktop-control server; every other built-in toolset that can drive a browser or a desktop is disabled too (only `browser` is confirmed, X-7). The red lines are only as strong as the profile's other tools. `skills.external_dirs` points at a versioned release path. | D1, HP-1, X-7. `BROWSER_FLEET_TOKEN` is never exported host-wide, and the launch/default profile of a multiplexed host gets no fleet token (its `.env` lands in `os.environ`). `lazy: true` helps only from the second boot (X-2). |
| H2 | **Shared skills `fleet-*`** | Eight skills in `hermes/skills/`: `fleet-router`, `fleet-identity`, `fleet-steps`, `fleet-browser-use`, `fleet-social`, `fleet-inbox`, `fleet-leadgen`, `fleet-evidence` (the dossier's eight, with `fleet-checkpoint-escalation` folded into `fleet-identity` and `fleet-router`, `fleet-stagehand-operator` renamed `fleet-steps` (S14-16), and `fleet-inbox` added for the `inbox` tool; `research/dossiers/hermes-packaging.md` 2.5, `hermes/README.md` section 1). Released as versioned, read-only directories (`.../skills/releases/<semver>`). A release writes the new path into each profile's `config.yaml` or rolls the gateways, and old release directories stay until every process has recycled; a `current` symlink is not flipped, because Hermes caches the resolved path. | D1, X-1. A same-named local skill silently shadows the shared one: a drift scan runs on every host (HP-3). Skills are written around "default to draft, never retry an uncertain write, never type credentials". |
| H3 | **Optional plugin `browser-fleet`** | No dependencies, pinned by `--ref <sha>`. A `post_tool_call` hook writes Obsidian evidence for `mcp__browser_fleet__*` results, **redacting tickets and URLs** (S05-8); a `/fleet` command. Does not load in the Jev trial. | D1, D15. The experimental `BrowserProvider` idea (leasing the CDP URL to Hermes' native `browser_*` tools) is **not** in v0: it would hand clicks to the Hermes LLM and bypass the ladder and the gates. |
| H4 | **Provisioner** (admin CLI, not agent-facing) | Per profile: mint a token, write `.env`, merge and **validate** the config YAML (one bad `config.yaml` breaks plugin dependency prep for every profile), run `hermes -p <p> mcp test browser_fleet`, record the binding. For hosts that cannot load plugins it registers the fleet as an MCP server through that host's own integration route instead. | `research/dossiers/hermes-packaging.md` 2.4. Runs on Hermes hosts, never on the maintainer's workstation. |
| H5 | **Obsidian writer** | The memory substrate is an Obsidian vault written **by the profile, not by fleetd**. Where plugins load: the H3 hook writes `Runs/<job_id>.md`. Where they do not (the trial): the `job` result carries a ready-made `obsidian_note` block (page-derived lines marked untrusted, tickets and URLs never present) and the skill tells the agent to save it. The profile polls `inbox` on a cron job and writes conversation notes; whether a trial employee can poll on a schedule is unverified. The daily note is written by the profile itself on a scheduled Hermes job that reads `job` (list mode) and `identity_status`. Vault folder per profile (one profile serves one client, `hermes/README.md` section 5): `Agents/<profile>/{Daily,Runs,Identities,Leads}/`; `Leads/<domain>.md` holds lead notes (`docs/playbooks/lead-gen.md` 4.6) **[extension]**. Built-in Hermes memory holds one pointer line only. | D15, C-29. Evidence links in notes are opaque refs (`fleet-evidence:ev_...`), resolved on demand through `job include=evidence` into short-lived URLs, so notes never hold a link that expires **[extension]**. Where the vault lives relative to droplets and the trial, and whether a trial employee can reach it, is open (O-14). A mem0-style layer on top of the vault is a later milestone, never a replacement. |

### 2.8 External dependencies (pins)

| Dependency | Pin | Source |
|---|---|---|
| Steel | image digest `sha256:7a161b95…` (2026-09-16, API 0.5.3, Chromium 152.0.7977.82); `:latest` tracks `main`, not releases, so pin by digest | `research/dossiers/steel.md` header, STE-14 |
| Stagehand | 4.2.0 TypeScript and Python, extension runtime 1.1.0; v3 is not a dependency (5 npm advisories, 2 high; wrong-click cache) | `research/dossiers/stagehand.md` Verdict 6, SH-8, SH-9 |
| Browser-Use | 0.13.11 with a version self-check (the box runner pins 0.13.10 and refuses 0.13.11 by string) | `research/dossiers/browser-use.md` Q1 |
| Hermes | one commit pinned per host; hands-on ran at `09681e7`, an older pin was read at `8a92051f`, targeted main was read at `46d7718a` | `research/dossiers/hermes-packaging.md` header, HP-1 |
| Reasoning model | `z-ai/glm-5.3-flash`, `reasoning.effort="low"` | D8 |
| System 1 | `jev-1.13.0`; `perplexity/pplx-decider-v1.1-27b-20261006` | D7 |
| Browserbase | opt-in home; Stagehand reaches it only with `browserbase.connect`; no key exists yet | D11 |
| Proxy vendors | dedicated static ISP, one IP per identity; Bright Data and IPRoyal verified, vetting rule O-10 | D10 |

Upstream drift is watched with an existing private drift-watch pipeline (details withheld), extended to Stagehand, Steel and
Browserbase queries (`research/dossiers/existing-assets.md` Q3).

## 3. Data model

Postgres is the source of truth (D12). Names are proposals; types are Postgres. Everything is **[unbuilt]**.
Secrets are never columns in clear: they are `*_enc` (envelope encryption, section 6.8) or `*_ref` (a secret
store reference). Items marked **[extension]** are not in DECISIONS.md; section 9 lists them. Gap ids
(`S01-3`, `G12-1`, ...) point at `research/scenarios/` and the ledger in section 9.5.

### 3.1 Entities at a glance

```
 tenants 1---* platform_accounts 1---0..1 connections (API-channel tokens) + connection_health, consents
    |               |   \---* manifests (by campaign) ---* items;  conversations, inbound_events, opt_outs
    |               |   \---* effects (keyed on the account), holds, account_firsts, governor_windows
    |               1---0..1 serving identity  (+ at most one candidate during a move; section 3.10)
    |                          |  \_ personas (1:1, immutable)   \_ proxies (1:1, unique IP)
    |                          |  \_ state_bundles, journals     \_ auth_markers + blocker_spec (per platform)
    |                          |  \_ [lease columns, fencing_token]
    |                          \---* jobs 1---* run_steps ---0..1 effects
    \---* tokens 1---* bindings (token x account: scopes, caps)
 campaigns, media_assets, platform_apps, source_registry, leads, site_incidents, incidents,
 spend, evidence, decision_log, audit, l1_entries, viewer_tickets, viewer_sessions, operators, nodes,
 risk_acceptances, approvals
```

An **account** is the durable thing a client owns on a platform (or one `research` lane). An **identity** is
that account's browser self for one device generation. **An identity serves exactly one account (1:1, not 1:many).**
This is narrower than the older sketch, where one browser and one IP could carry logins for several platforms. The
consequence: a client that needs a browser on two platforms (say a Facebook Page and Instagram) gets two
identities, two IPs and two logins. How Meta treats linked Facebook and Instagram logins seen from two IPs is
unresearched, and the extra IPs raise cost (the `f` axis of D12). It is chosen because the lease, the holds and the
open-effect check of 3.5 are then exact: one shared session is never behind two accounts. An API-only account has no
identity and no IP (S02-6). The ledger, caps, manifests and bindings hang off the account, so they survive a new IP
(S07-5).

### 3.2 Account and identity records **[extension]**

**`platform_accounts`** (set at creation by an owner; `identity create`, section 4.15):

| Field | Type | Meaning and rules |
|---|---|---|
| `account_id` | uuid pk | |
| `tenant_id` | fk | The client. Drives node affinity **[pending Q-13]**, spend caps, data policy **[pending Q-07]**. |
| `platform`, `handle` | text | Unique together **over accounts whose `status <> 'retired'`** (a partial unique index), so one live account can never be bound twice, and a retired handle can be re-created. |
| `alias` | text, unique per tenant | What agents say (`acme-instagram`). The tool argument is still named `identity`. Agents never see ids, proxies, CDP URLs or cookies. |
| `account_kind` | enum | `page`, `professional`, `business`, `group_member`, `profile`, `research_lane`. `profile` is refused for browser use by D2's table. |
| `connection_id` | fk null | The API-channel token, if any (3.13). |
| `channel_policy` | jsonb | **The single place channel choice is stored; read only by the router; defaults in section 8.** Includes `click_mode` (`human_clicks` default, `agent_clicks` only by explicit owner setting, G12-15), `bot_disclosure` per market (S03-5), and `browser_allowed` (a list taken from D2's table, never wider). |
| `risk_acceptance_id` | fk null | Required before any browser-channel effect (3.7). |
| `allowed_hosts` | text[] | Owner-managed: the platform's hosts plus the client's own domains. Enforced by gate R and the Guard (4.5, S13-8). |
| `status` | enum | `active`, `retired` |

**`identities`** (one row per device generation; zero rows for an API-only account):

| Field | Type | Meaning and rules |
|---|---|---|
| `identity_id` | uuid pk | |
| `account_id` | fk | The one account this identity serves. Exactly one: no identity spans accounts (3.1). |
| `generation` | int | 1, 2, ... A new IP or a new infra home creates the next generation (D3). |
| `serves_account` | bool | True for the one identity whose browser is used for the account's work. A partial unique index allows at most one `true` per account. A candidate has it `false` until cutover (3.10). |
| `successor_of`, `superseded_by` | fk null | Links across generations (3.10). |
| `kind` | `account` \| `research` | `account` is a client's logged-in brand account. `research` is an open-web identity with no social login. Only `research` identities may run plain-HTTP reads through their proxy (4.4), because HTTP-client traffic from a logged-in identity's static IP would break continuity (D9). |
| `research_mode` | `http_only` \| `ephemeral_browser` \| null | `research` only (S04-4, 4.13). |
| `infra_home` | `steel-oss` \| `browserbase` | Default `steel-oss`. Immutable. |
| `infra_ref` | jsonb | Browserbase: `{context_id, project}`; the Context `name` is set to `identity_id` so the dashboard doubles as a manual recovery index (browserbase BB-3). Steel: empty. |
| `proxy_id` | fk; partial unique index `UNIQUE (proxy_id) WHERE state NOT IN ('quarantined','retired')` | One **dedicated static ISP IP**, never shared, never rotated. Mandatory on every identity; absent on an API-only account because it has no identity. The partial index lets a successor of the **same account** take its predecessor's IP once the predecessor is `quarantined` (3.10, same-IP path; G10-3). A trigger refuses a second row on one `proxy_id` unless both rows share `account_id` and one is `successor_of` the other; a different account, tenant or client never receives the IP. |
| `persona_id` | fk | See 3.3. |
| `image_cohort`, `image_flavor` | text | Steel digest and Chromium major; flavor `account` or `research` (`docs/infra/steel-profile.md` section 2). Changing either is a persona update through the canary rule (O-13). |
| `state` | enum | `asleep, waking, canary, awake, sleeping, needs_reauth, checkpoint, restricted, migrating, quarantined, retired`. Transitions in 3.8. |
| `cooldown_until` | timestamptz null | Set by `checkpoint`, `captcha`, `restricted` (S05-4). While set, no effects and lower governor caps. |
| `node_id`, `container_ids`, `awake_since`, `last_active_at`, `last_node_id` | | `last_node_id` feeds the placer's cache preference. |
| `current_bundle_gen`, `current_journal_gen` | int | `0` = no bundle (a brand-new identity). Moved only by compare-and-set on the fencing token (3.3). |
| `fencing_token` | bigint | Monotonic, never reset, never reused. Bumped by acquire and takeover only. |
| `lease_holder_kind`, `lease_holder_ref`, `lease_purpose`, `lease_job_id`, `lease_expires_at`, `lease_heartbeat_at` | | The lease, as columns of this one row (3.5). |
| `created_by`, `created_at`, `retired_at` | | Creation is owner-only (4.15). |

Holds are not a column. They are rows in `holds` (3.11) so that two causes can stand at once and each clears
by its own rule (S07-2).

### 3.3 Persona, proxy, state bundle, auth markers

**Persona** (`personas`, 1:1 with the identity, immutable). What can be pinned today and what cannot
(D3, STE-10, C-02):

| Pinned now (no fork) | Mechanism |
|---|---|
| User agent matching the real Chromium version; timezone; locale; viewport | Steel session fields (`userAgent`, `timezone`, `dimensions`) with fingerprint injection off, plus process `TZ`, `LANG`/`LANGUAGE`, and `--accept-lang=<list>`. `--lang` does nothing on Linux (V-1) and Stagehand's `locale` option is no substitute (C-10). Always pass `timezone`: with the proxy down it fell back to UTC (STE-7). |

| Not pinned: host-real, identical across identities on a node | Consequence |
|---|---|
| CPU core count, GPU / WebGL renderer, canvas hash, screen size (Steel reports 800x600), UA-CH brands | Identities of **different clients do not share a node** until per-identity hardware values exist (about 7 identities per node; D12) **[pending Q-13, O-01]**. This premise is a fork, settled by one measurement (D3, section 7.7). Per-identity hardware values need a CDP-injection layer in the executor or a patched kernel, measured in M1. |

Fields: `persona_id`, `mode` (`honest` default \| `cdp_injected` \| `patched_kernel` **[pending O-01, Q-03, Q-04]**),
`user_agent`, `chromium_major`, `timezone`, `locale`, `accept_languages`, `viewport {w,h,dpr}`,
`hw jsonb` (null in `honest` mode), **`executor_id`, `extension_mode` (`none \| A \| B`), `image_flavor`**
(S14-7: pinned here, changed only through the canary rule O-13, never per wake), `persona_hash`,
`history` (forward-only steps on image-cohort changes).

- **Steel homes:** every wake observes `navigator.userAgent`, `Intl` timezone, `navigator.languages` and the
  viewport in the live page and compares them to `persona_hash`; a mismatch refuses the wake or stops the
  session (`persona_mismatch` hold).
- **Browserbase homes (G10-5):** Browserbase chooses UA, OS, locale and hardware (`docs/engines/browserbase.md`
  section 3.6; stability per Context unknown, section 12 items 7 and 20). The persona hash covers timezone,
  viewport, region and exit IP only. Observed UA and languages are recorded as telemetry. Continuity of the
  fingerprint is traded away on this home (D11), and the owner is told at creation.

**Proxy** (`proxies`): `proxy_id`, `vendor`, `kind='isp_static'`, `exit_ip` (unique), `asn`, `asn_class`
(`isp`, never `datacenter`), `geo`, `tz`, `term_expires_at`, `vetting` (jsonb: exit-IP match, ASN class,
reputation checks, geo/timezone match, provider sourcing statement; O-10), `creds_ref`, `vendor_opts`
(for example IPRoyal `_killswitch-1`). A new IP is accepted only after vetting; the check fails closed. Static
ISP list price is about $2.5-3.3 per IP-month (vendor claim; scale-infra Q4 inputs). Mobile ports (~$117-130/mo)
are a targeted exception, never the default. A replacement IP must match the client's region and the old IP's
(D3).

**State bundle** (`state_bundles`, one row per generation): `identity_id`, `generation`, `spaces_key`
(`profiles/<id>/gen-<token>.tar.zst.enc`), `sha256`, `bytes`, `dek_id`, `fencing_token_at_write`, `node_id`,
`cookies_unflushed bool`, `journal_key` (the context export taken at sleep, encrypted), `created_at`. The
tarball excludes `Cache`, `Code Cache`, `GPUCache`, `Dawn*Cache`, `GrShaderCache`, `ShaderCache`,
`Service Worker/CacheStorage` and `Singleton*`. **Unit of persistence = the user-data-dir tarball; the
context export is the source of truth for cookies** (Chromium commits cookies on a 30 s timer and there is no
CDP flush; D4, STE-2). Last 5 generations retained (estimate). Slim size: 57 KB after 8 light pages
(hands-on); a social profile is planned at 50 MB (estimate); Steel Cloud's profile cap of 300 MB hints at the
heavy end.
- **Generation 0 means "no bundle" (S01-13).** A new identity wakes with an empty user-data-dir and a fresh
  `.fleet-identity` marker (`docs/infra/steel-profile.md` section 8.1 steps 3-4). Its first sleep writes
  generation 1 by compare-and-set from 0.
- **Cross-host restore is the expected path, not an edge case (S01-7).** Nodes are created on schedule and
  destroyed after (section 7.4), and a new client gets its own node (Q-13), so the next-day wake usually has
  no bundle cache on the node: download, decrypt and extract happen on most wakes. Cross-host and x86
  restore of a tarball is **unverified** (O-17). The G1.1 two-node run and G5.2 are **hard prerequisites for
  onboarding any client**, and bundle size plus download time are terms in the wake budget (4.1, 4.11).
- **Periodic journals outlive the node (S08-4).** The journal timer started at wake (4.1 W13) uploads each
  context export, encrypted, to Spaces under the fencing token, as `journal_generation` with its own
  compare-and-set pointer (`current_journal_gen`). Interval `J` and retention are **estimates to set in
  G5.3**. G5.3 must end with a reconcile wake that needs no human login. A journal that stays on the node
  would restore only the last sleep's bundle, and social cookies rotate, so that reconcile wake would land in
  `needs_reauth`.
- **Cookie precedence at wake (S01-5).** When the newest bundle is `cookies_unflushed`, or when the journal
  is newer than the bundle, the journal is applied **before the first navigation to the platform**, with
  these rules: for a cookie in both, the journal wins if its `expires` or last-update is later; a cookie
  only in the tarball stays; a cookie only in the journal is added. Whether to apply the journal at every
  wake is decided by G1.1: the test app must see **no logged-out request** before the journal is applied
  (a new G1.1 case). Journal re-inject on `persist:true` is untested (O-17).
- Browserbase-homed identities have no bundle: the Context is the state, it cannot be listed or exported
  on self-serve plans, and suspension voids all of them (BB-3); the fleet snapshots cookies and storage over
  CDP at session end as a backup (D11).

**Auth markers** (`auth_markers`, per identity; an identity serves one account, so one platform): `marker_spec` (jsonb: the deterministic probe,
for example a URL pattern, a selector, a cookie name), `blocker_spec` (jsonb: the mid-run signals, below),
`spec_version`, `last_probe_at`, `last_result` (`ok | login_wall | checkpoint | captcha | restricted | error`),
`last_ok_at`, `auth_epoch` (increments on each successful human **login**; not on a `human_session` handback),
`last_login_by`, `last_login_at`. A `POST /v1/sessions` returning 200 proves nothing: Steel answered 200 while
serving a logged-out browser after a stale-lock restore, and `/v1/health` is structurally always `ok` (STE-3;
`isRunning()` is true when no browser exists, steel verification missed issue 2). A profile is ready only when
a probe has passed after the launch.
- **Marker specs are per platform, written by the owner, versioned,** and released by the same three-outcome
  rule as a procedure (3.7). The first probe after a human login counts as the first outcome (S01-8). A spec
  must work with zero model calls. A bad marker makes `ok` meaningless (Charter invariant 1), so a new
  platform has no marker until its first identity is logged in by a person and the spec is tested on that
  logged-in page.
- **`blocker_spec` (S05-3).** Per platform, next to `marker_spec`. The executor evaluates it before and after
  every command from signals the Guard already sees: top-frame URL patterns, status codes of top-frame
  navigations and of key XHRs (401/403, redirect to a login page), challenge-frame hosts, DOM landmarks, and
  the session cookies named in `marker_spec` read from the context export on the journal timer. A decider is
  optional and only after the deterministic check has cleared. The same list feeds Browser-Use's stop callback.
- **Research identities have no marker** (S04-8): their wake skips the login probe, and a login wall on a
  research identity is a per-domain `blocked` result (4.13), never an identity state.

### 3.4 Tokens, bindings, scopes

`tokens(token_id, token_hmac, installation_id, hermes_profile, tenant_id, min_skill_version, created_at,
rotated_at, revoked_at)`. The token is opaque and stored only as an HMAC. A bearer that looks like `${...}` is
rejected before lookup.

`bindings(token_id, account_id, alias, scopes, daily_caps, pending_approval_cap, valid_until)`. Scopes:

| Scope | Allows |
|---|---|
| `read` | status, wake, sleep, reauth request, `extract`, `task` in `read_only` mode, `act` steps that are not effect-like, `inbox`, `manifest_status` |
| `draft` | everything in `read`, plus filling composers without submitting, creating approval requests, and the `manifest` tool (propose and revise only) |
| `publish` | post, comment, story effects, each still needing a manifest item or an approval |
| `dm` | DM, `private_reply` and inbound-reply effects, each still needing a manifest item or an approval, and a conversation from `inbox` (3.12) |
| `approve` **[extension]** | Answering approvals. **Never held together with `publish` or `dm` on the same account** (separation of duties). Held by operator-console users, not by Hermes profile tokens by default. |

Human takeover is not a token scope: it goes through the operator console under an authenticated operator
(section 6.13). Tokens never carry model, proxy or platform credentials. **Flood limits (G11-5, S13-12):** a
binding caps pending approvals per token and per account; a second draft with the same normalised text to a
new target inside a window is rejected; if more than `K` same-shape approval requests arrive in a window
(`K` and the window are estimates), the token's `publish`/`dm` scope is suspended pending the owner; the
owner is alerted once per burst, not once per approval.

### 3.5 Lease with fencing token

The lease is columns on the single `identities` row, so "at most one active lease per identity" is enforced
by the primary key and by row locking, not by convention. Four separate statements. This replaces the
scale-infra statement that bumped the token on every renewal and could not express takeover (SCA-10) and the
claim in an earlier internal job-claim design that is safe only serially (EA-7). These statements can be
SQL-tested locally with no droplet (O-03).

```sql
-- acquire: only a free or expired lease. Work needs the identity's state, holds and open effects to allow it.
UPDATE identities i
   SET lease_holder_kind = $kind, lease_holder_ref = $ref, lease_purpose = $purpose,
       lease_job_id = $job, fencing_token = fencing_token + 1,
       lease_expires_at = now() + $ttl, lease_heartbeat_at = now()
 WHERE i.identity_id = $id
   AND (i.lease_holder_ref IS NULL OR i.lease_expires_at < now())
   AND ( $purpose <> 'work' OR (
            i.serves_account
        AND i.state IN ('asleep','waking','awake')            -- S05-1: not needs_reauth, checkpoint, restricted,
                                                              --   canary, migrating, quarantined, retired
        AND (i.cooldown_until IS NULL OR i.cooldown_until < now())
        AND NOT EXISTS (SELECT 1 FROM holds h                  -- S07-2: a hold whose scope covers browser work
                         WHERE h.account_id = i.account_id AND h.cleared_at IS NULL
                           AND (h.identity_id IS NULL OR h.identity_id = i.identity_id)
                           AND h.scope IN ('browser','all'))
        AND NOT EXISTS (SELECT 1 FROM effects e                -- S08-2: closes the gap between lease expiry
                         WHERE e.account_id = i.account_id     --   and the hold being written
                           AND e.channel <> 'api' AND e.state IN ('intent','uncertain')) ) )
RETURNING fencing_token;                -- 0 rows = identity_busy, identity_held or identity_state (queue it)

-- renew (heartbeat, tied to worker liveness for agent leases): the token does NOT change
UPDATE identities SET lease_expires_at = now() + $ttl, lease_heartbeat_at = now()
 WHERE identity_id = $id AND lease_holder_ref = $ref AND fencing_token = $t
RETURNING 1;                                    -- 0 rows = the lease was lost

-- takeover (explicit human preemption): bumps the token, so the agent's in-flight commands go stale.
-- $purpose is reauth | human_session | observe. Refused while the identity is waking or sleeping: queue it.
UPDATE identities
   SET lease_holder_kind = 'human', lease_holder_ref = $operator, lease_purpose = $purpose,
       fencing_token = fencing_token + 1, lease_expires_at = now() + $human_ttl,
       lease_heartbeat_at = now()
 WHERE identity_id = $id AND fencing_token = $t_seen AND state NOT IN ('waking','sleeping','retired')
RETURNING fencing_token;

-- release: the token stays; the holder is cleared
UPDATE identities
   SET lease_holder_kind = NULL, lease_holder_ref = NULL, lease_purpose = NULL, lease_job_id = NULL
 WHERE identity_id = $id AND lease_holder_ref = $ref AND fencing_token = $t
RETURNING 1;
```

In the same transaction as `acquire`, the expiry of an old lease turns that lease's open `intent` rows into
`uncertain` and writes the hold. There is no moment where a lease has expired, the hold does not exist yet and
a queued job can slip in (S08-2). Add both cases to G2.1 and G4.1 as SQL tests, with the state cases of S05-1
in G0b.2.

- **`purpose`** is `work | reconcile | canary | reauth | human_session | observe | maintenance | system`
  **[extension]**. Only `work` may run effects, and only on a serving identity in `asleep`, `waking` or `awake`
  with no covering hold and no open browser effect. `reconcile` is read-only and allowed while held (without it,
  reconciliation, which needs the lease to read the page, would deadlock). `canary` runs the login probe and
  read-only procedures on an identity in `canary` state; `reconcile` is also allowed there. `reauth` and `human_session` are the human leases
  below. `observe` is a human watching without input. `maintenance` is node work (bundle repair, image
  update). `system` is a pause lease that fleetd holds while a job is `needs_human`, so nothing else can claim
  the identity in the gap (S05-5).
- **A human lease follows viewer liveness, not worker liveness** (S01-4, G12-1). `$human_ttl` is short. The
  viewer broker renews it on a heartbeat while the viewer socket is open, until a hard ceiling. The heartbeat
  is derived from input-frame counts only; no payload is logged (steel.md section 7.3). There is an idle
  timeout, a visible countdown and an extend button. The scheduler's pre-wake and the idle reaper (N1) skip an
  identity that holds or is waiting on a human lease. On every token change fleetd calls the node agent's
  `viewer_close` (`docs/infra/steel-profile.md` section 9.2), so the viewer route never outlives the lease:
  there is no moment with a human and an agent both able to write. Values for the TTL, heartbeat, idle timeout
  and ceiling are **estimates to measure** (M1).
- **Timing (S08-3), all estimates to measure in G2.1 and G5.x.** The agent lease TTL is `L`; the node renews
  every `L/3`; the liveness signal is the node agent's heartbeat carrying the fencing token plus a probe of the
  live worker. The node self-fences at `L - max clock skew - margin`. fleetd re-places an identity only after
  `L + margin` **and** a fence confirmation: the node's ack, or the droplet powered off through the provider
  API. The reconcile wake never starts before that. The one effect in flight at the moment of a partition stays
  `uncertain`: the token fences the next command, but the platform sees no token, so a click that was already
  authorised may still land.
- **The token is checked by whoever acts**, not just stored. The node agent keeps the highest token seen per
  identity on its disk (so it survives an agent restart) and refuses lower ones. The executor re-checks on
  every command. On a higher token the node agent kills that identity's actor containers at once
  (`docs/infra/steel-profile.md` section 10.3). The gap between the takeover decision and the kill is one RPC
  **[to measure, M1]**.
- **Bundle commits and effect rows carry the token.** The pointer move is
  `UPDATE identities SET current_bundle_gen = $g WHERE identity_id = $id AND fencing_token = $t`; the journal
  pointer moves the same way.
- **Browserbase-homed identities have weaker fencing [extension].** The node agent cannot cut a remote CDP
  session it does not host. fleetd keeps the `connectUrl` secret, allows one connection per Context, and on
  takeover ends the session through the Browserbase API (`REQUEST_RELEASE`). Anyone who already holds the
  `connectUrl` can keep driving until the release lands. Browserbase's own docs only *advise* against
  concurrent use of one Context.
- `lease_history` (append-only) records every acquire, takeover and release with token, holder, purpose.

### 3.6 Effect ledger row

An **effect** is anything irreversible or externally visible: post, comment, reply, DM, story, delete, follow,
form submit, edit. The ledger is keyed on the **account and the authority**, not on the job and not on the
identity row, so re-creating the work or replacing the identity cannot produce a second effect (S08-1).

| Field | Meaning |
|---|---|
| `effect_id`, `effect_key` (**UNIQUE**) | `effect_key = H(tenant_id, platform, handle, kind, target, authority_ref)`. `authority_ref` is `manifest_item_id#occurrence` for scheduled and triggered items, or the `approval_id` for a per-action approval. A new job, a new idempotency key or a replacement identity for the same account yields the same key. Scheduler jobs carry the deterministic key `(manifest_item_id, occurrence)` (they have no token, so the per-token idempotency rule does not apply). |
| `account_id`, `identity_id`, `tenant_id`, `platform`, `handle`, `job_id`, `step_no` | `identity_id` records which device acted; it is not part of the key. |
| `kind` | `post \| comment \| reply \| dm \| private_reply \| story \| delete \| follow \| form_submit \| edit` (red-line kinds are refused before this table, 4.3 gate R) |
| `channel` | `api \| browser \| human` (`human` = a person acted in the viewer or on their own device and said so at closure, 4.14) |
| `target`, `conversation_id`, `content_hash`, `content_ref` | What and to where. For `reply`, `dm`, `private_reply` the target is a fleet-issued conversation (3.12). The content is never page text (section 6.7). |
| `manifest_id`, `manifest_item_id`, `occurrence`, `approval_id` | The authority. At least one of item or approval is required. |
| `fencing_token` | The lease token under which the action ran. |
| `attempt` | 1 at first. A human-ordered retry of the same effect increments it (below). |
| `state` | `intent -> committed \| uncertain \| failed_clean`; `uncertain -> reconciled_found (= committed) \| human_resolved` |
| `intent_at`, `acted_at`, `receipt_at`, `uncertain_since`, `grace_until`, `grace_paused_ms` | `grace_until` is per platform and set before any use; the grace clock pauses while auth is not `ok`. |
| `evidence_refs` | Written into the intent row **before the click** (pre-submit screenshot, snapshot): a node that dies after the click still leaves the reconciler more than a hash (S08-13). |
| `receipt` | jsonb: `{source: api_readback \| dom_readback \| thread_readback \| human, result: found \| absent \| unobservable, observed_hash, platform_ref, permalink, created_at_platform, preconditions: {auth_ok, known_positive_visible}, matcher_version}` |
| `retry_allowed` | Default `false`. Never `true` for a browser-channel effect until G4B.1 reports a false-negative rate. For an API-channel pair it may be set per platform and kind after G4A.1 reports its rate. |
| `cost_usd_micro` | for example an X API fee |

```
 (none) --INSERT intent (committed to the DB BEFORE the click or API call)--> intent
 intent --receipt read back, content matches------------------------------> committed
 intent --refused before any side effect (validated, e.g. API 4xx)---------> failed_clean   (approval and cap released)
 intent --timeout / crash / lease lost / no receipt after grace------------> uncertain  (+ hold, 3.11)
 uncertain --reconcile job finds it, tri-state result 'found'--------------> committed (reconciled_found)
 uncertain --anything else (absent, unobservable, ambiguous)---------------> human_resolved (owner decides, with evidence)
 human_resolved --person says "retry"--------------------------------------> intent again, SAME row, attempt + 1,
                                                                             new per-action approval, new pre-submit check
```

Protocol: `INSERT ... ON CONFLICT (effect_key) DO NOTHING RETURNING`. If the row exists and is `committed`, the
call returns the stored receipt (idempotent replay, no action). If it is `intent` or `uncertain`, the call
returns `outcome_uncertain` and does nothing. **Nothing is blindly retried.**

- **One transaction (S08-1, S03-8).** The intent insert, the approval consumption (`approved` to `consumed`) and
  the manifest item's cap increment happen in one transaction. A crash cannot leave a usable approval or an
  uncounted cap. `failed_clean` reverses both (approval back to `approved`, cap decremented, `released_at`
  stamped). `committed` and `uncertain` keep them consumed.
- **Second uniqueness check, independent of authority (S08-1, S05-7).** In the same transaction, under a row
  lock on the account, refuse a new effect if a row exists for the same `(platform, handle, content_hash)` in
  `intent`, `uncertain` or `committed` inside an open window. For `intent` and `uncertain` the window never
  closes until the row is terminal. For `committed` it is `W` (an estimate, per platform and kind; a recurring
  manifest item may set `allow_repeat_after`). The approval page shows any such prior attempt. The pre-publish
  duplicate check also includes the account's **recent posts, comments and messages as listed by the connector**,
  not only the fleet ledger, so what a person did by hand is seen (G12-5).
- **Read-back is tri-state: found, absent, unobservable (S05-6, S06-2).** A negative counts only when the auth
  probe is `ok` **and** a known-positive item (a previously committed post) is visible in the same page or API
  view. Otherwise the result is `unobservable`. Each verifier adapter has this self-test (S06-2). The grace
  clock pauses while auth is not `ok`.
- **Matcher (S08-6, S02-10).** A match needs the target (group or thread id), `created >= intent_at - skew`,
  and normalised text. Prefer the receipt `id returned by the write + fetch by id + normalised-text compare`.
  List-and-match is a fallback only after a timeout. Capture the permalink or post id from the page right after
  the click when present. Prefer an API read when the account has a healthy connection. An ambiguous match is
  `uncertain`, not `found`. Normalisation (link shortening, previews, mention rewrites, caption handling) is
  defined per platform at build time (inference: platforms rewrite text, not researched) and its false-negative
  rate is logged (G4A.1, G4B.1). **The fleet never adds a visible marker to a client's post.**
- **No retry after a negative browser read-back (S08-5, S06-2).** A miss on the browser channel is weak
  evidence: feeds index late, DM requests land elsewhere, a Facebook Group with admin approval may queue the
  post (inference). So a miss leads to `human_resolved` and nothing else. If a person says retry, it is the
  same effect row with `attempt + 1`, a new per-action approval and a new pre-submit check. A retry under a new
  key is the path section 5.5 forbids. This is the Charter's "nobody retries an uncertain effect" made
  precise, and it replaces the earlier "reconciled_absent, may be retried".
- **Human effects (S05-7, G12-5).** Every takeover ends with a closure form (4.14) that writes a
  `channel=human` row for each thing the person did, or "no effect". The governor counts human effects. A
  person who posts by hand in a free takeover therefore appears in the ledger and in the duplicate check.
- **Receipt sources for the API channel (S03-14).** For a DM the receipt is the message in the thread read
  through the Conversations API, after reading the whole thread. Instagram Requests-folder threads idle for
  30 days are not returned by that API, so the reconcile job names this blind spot and sends it to
  `human_resolved` with evidence instead of calling it absent.

Verified caveat: the intent/receipt/hold pattern is proven in the trial's code against a synthetic CRM the
controller owns; **read-back receipts for browser-driven social actions are a hypothesis**, and their
false-negative rate sets the human reconciliation load (SCA-9, D13) **[to measure]**.

### 3.7 Procedure record, manifest, approval, risk acceptance

**Procedure** (`procedures`): a named, versioned, digest-pinned sequence, for example `x.reply_to_mention`.

| Field | Meaning |
|---|---|
| `name`, `version`, `digest` | `digest = sha256(canonical JSON of kind, platforms, input_schema, steps, authority, verifier)`. The registry refuses a procedure whose stored digest does not match. A UI repair is a **new version** (D13). |
| `kind` | `api \| browser \| hybrid \| read` |
| `input_schema` | JSON Schema for the `fields` a caller supplies. Supplied values are copied verbatim; no model retypes them. |
| `steps[]` | `{key, op, rung_hint, effect: none \| reversible \| irreversible, effect_kind?, l1_cacheable, expects, readback?, restart_from: bool, target_rule?}` |
| `target_rule` | **Mandatory when `effect != none`** (S06-1): `{role, name_regex, region_or_frame}`. L2 candidates are pre-filtered by it; an L3 `observe` is constrained to it; with no match the step abstains and stops (`needs_human`), it never climbs to a free-form click (D5). |
| `restart_from` | Marks a step boundary at which the run may be restarted after a pause (S05-5). Resume restarts at the last boundary before the first non-committed effect, never mid-page (4.2 step 8). |
| `authority` | `{hosts[], effect_kinds[], max_effects_per_run, content_source: manifest_item \| approval, scopes_required[]}` |
| `verifier` | The name of a verifier adapter. Effectful adapters are registered in reviewed code ("adding an effectful adapter is a software release") and declare the independent check: `api_readback`, `dom_readback`, `thread_readback` or `owner_review`, and its known-positive self-test (3.6). |
| `release_state` | `draft -> quarantined -> released -> rolled_back \| retired` |
| `accepted_outcomes` | count of distinct owner-accepted outcomes. Released at 3 for a **version that contains an effect step** (the trial's rule). Non-effect steps are promoted by machine criteria (3.9 `l1_entries`) and carry no human outcome (S06-4). Outcomes are accepted by the `reviewer` role (6.13, which resolves N-5). |
| `previous_digest` | rollback pointer. Rollback means "revert to the previous version and retire the L1 entries built under the failed one"; if the platform itself changed, it means "pause and repair", not "previous digest" (D13). |
| `guide` | prose guide for hosts that cannot load plugins, of limited length. Prose guides on such hosts are admitted on owner approval alone, so a guide carries **no executable authority** (D13, HP-5). |

A new Steel/Stagehand pin, a new persona, a new `executor_id` or `extension_mode`, and a new identity follow the
same quarantine and canary rule before they touch a client account (O-13, MILESTONES S2).

**Campaign and manifest [extension].** A **campaign** (`campaigns`: `campaign_id`, `tenant_id`, `name`, `status`)
groups manifests across accounts and platforms (S02-3). A **manifest** (`manifests`) is an **immutable, hashed,
human-approved authorization** for one account: `manifest_id`, `campaign_id`, `account_id`, `platform`,
`revision`, `supersedes`, `status` (`draft | approved | revoked | expired`), `items[]`, `caps` (per hour, per
day), `kill_switch`, `manifest_hash`, `created_by`, `approved_by`, `approved_at`, `valid_from/until`. It is keyed
on the **account**, not the identity, so a new IP does not strand it (3.10). Any change to audience, persona,
cap or attachment creates a new revision and revokes the old one (the approvals pattern of an earlier private SDR harness).
- **Item:** `{item_id, kind: post | comment_template | reply_template | dm_template | private_reply_template,
  content: {text, media[{asset_id, sha256_published}]} or content_rules, trigger, window{not_before, not_after,
  tz}, per_item_cap, target_rule, state}`, with its own `content_hash`.
- **Trigger (S03-5).** `schedule` (a clock, as before) or `inbound_event` (a deterministic match from the closed
  set below, one reply per conversation, class-gated, with the kill switch). A time window and an `inbound_event`
  trigger can be combined (reply only inside business hours).
- **Closed rule sets (S13-14).** `content_rules` kinds: `fixed_text`, `template_slots` (slots take values only
  from fleet-held structured fields, never from stranger-controlled text; display names are stripped of URLs and
  markup or left out), `max_length`, `link_allow_list`. `target_rule` kinds: `inbound_thread`, `opted_in_list`,
  `own_post`, `own_page`, `group_id`. **A manifest item whose target rule is anything else is rejected at
  approval** (G11-3): "people who liked post 123" is not a kind.
- **Item states:** `pending -> ready -> running -> done`, plus `blocked_until_ready` (the platform app is not
  approved, 3.13), `missed` (the window closed undelivered, with a reason such as `human_session`,
  `not_released`, `channel_unavailable`), `expired_unrun` (the identity was held or unwakeable; terminal, with a
  reason; the owner gets the list; an item is **never shifted outside its approved window**, the owner approves a
  new revision) (S07-16), `skipped(not_released)` and `cancelled`. API items continue under an identity-scoped
  hold (3.11).
- **Approval of a campaign** is one event covering a named set of manifests, with a per-manifest diff (S02-3).
  A `client_approver` (6.13) may give client sign-off on content; an operator still approves the technical set.
- **Media (S02-2).** An item refers to a `media_asset` whose hash is of the **published artifact** (3.13).
- **Scheduling is on the fleet side only** (S02-11). Facebook can hold a scheduled post platform-side
  (SPV V-10), and the kill switch cannot recall it, so the fleet never uses platform-side scheduling. Each item
  runs at a per-account offset inside its window; the offset spreads load and the benefit of spreading against
  platform detection is **unverified** (GEMINI-AUDIT 9.07, SPV V-13).

Publishable content comes from a manifest item or an approved draft. Code enforces the no-raw-text-argument
rule and the hash match; only the human catches page text copied into a draft (D13).

**Approval** (`approvals`): a per-action authorization consumed at the intent insert (3.6). `approval_id`, `kind`
(`manifest | campaign | action`), `subject` (the exact payload: target, account, exact content, audience,
irreversible effects, **`in_reply_to {message_ids, snapshot}`**, **`prior_attempts[]`**, **`warnings[]`**) and
`subject_hash`, `requested_by_token`, `status` (`pending | approved | rejected | expired | withdrawn | invalidated
| consumed`), `decided_by` (an operator), `decided_at`, `acknowledged_warnings[]`, `edit_history[{text_before,
text_after, by, at}]`, `expires_at`, `consumed_by_effect_id`, `released_at`.
- **`expires_at = min(conversation window close, TTL)`** (S03-8). The queue sorts by time left; the notifier alerts
  at a threshold (4.12). The expiry outcome is written once: the approval is `withdrawn`, the conversation is
  marked closed, the owner is told, and a person may still answer natively in the platform's own inbox. After an
  API `publish` is approved, the **same job continues**; no one has to re-ask.
- **Stale drafts (S03-9).** The approval shows the message being answered. A newer inbound message in the same
  conversation sets the approval `invalidated`. An approver may edit: the edit re-hashes and records both texts.
- **Warnings are computed in code (S13-2)** and require a second acknowledgement: a link off the tenant's
  allow-list, a URL shortener, overlap with any string that was returned as untrusted to this token, a first
  link to this destination. The card also shows which untrusted item the profile read before drafting.
- **Consumption and release** are stated in 3.6. **First post** per account, content type and destination
  always needs a person: gate G checks `account_firsts` (3.13). Manifest approval satisfies it only through an
  explicit per-account tick on the approval; without the tick an extra approval is required. Launch day, when
  many accounts have a "first", therefore costs a tick each, not a silent pass.

**Risk acceptance** (`risk_acceptances`) **[extension]**: `tenant_id`, `platform`, `scope` (which browser-channel
effect kinds), `document_ref` (the client's written acceptance), `accepted_by`, `valid_until`. Required before
any browser-channel effect and before an identity leaves `canary` for a browser-write row of D2's table; the
fleet stores the reference, the document lives with Justin.

### 3.8 Identity state machine

```
        identity create (4.15)
              |
              v     login probe ok, canary passed     wake                  probe ok            idle / schedule end / sleep
          canary ---------------------------> asleep ------> waking ------------------> awake -------------------------> sleeping --> asleep
           (read-only; wake purpose           ^                |  proxy/persona mismatch   |   |                               | upload fails
            canary or reauth)                 |                +--> hold(mismatch)         |   | login_wall                    +--> hold(upload_failed)
                                              |                                            |   +-----> needs_reauth --+
                                              |                                            | checkpoint / captcha         | human login + probe ok
                                              |                                            +-----> checkpoint ------------+--> awake (or sleep)
                                              |                                            | platform restriction
                                              |                                            +-----> restricted (cooldown_until; owner decides)
   any state --owner--> quarantined (no work, no wake)     serving identity --cutover--> migrating --> quarantined --> retired (3.10)
   quarantined --owner lift--> asleep  (only if no other live row holds its proxy_id; rollback of 3.10)
   any state --owner--> retired (terminal)
   holds (3.11) are rows, set by the ledger, the forwarder and the node; they are orthogonal to state
```

- **`canary` (S01-1)** is the state of a new identity, and of a candidate during a move. Allowed: wake with
  purpose `reauth`, `canary` or `reconcile`, the login probe, read-only procedures. Refused: every effect and `work`. The
  identity leaves `canary` for `asleep` only when the canary rule is met (MILESTONES S2: read-only first, then
  low-volume own-account effects; for a replacement, operator at the login, a set number of read-only probes,
  a per-action approval for its first browser effect, a reset first-post gate) and, for a browser-write row, a
  risk acceptance is on file (G4B.2). `quarantined` is **not** for "not yet canaried": it means the owner
  stopped the identity (no work, no wake).
- **Leaving `quarantined` (G10-3).** Only by an owner **lift** to `asleep` (audited), and only when no other
  identity outside `quarantined`/`retired` holds the same `proxy_id` (3.2 partial index), and, for a predecessor
  in a move, only as part of the 3.10 rollback transaction. `migrating` has two exits: `quarantined` when the
  cutover commits, and `retired`. Nothing leaves `retired`.
- **`checkpoint`, `captcha`, `restricted` versus `login_wall` (S05-4).** A `login_wall` is an expired
  session: resume after a probe passes. The others mean the platform challenged or limited the account. The
  identity enters `cooldown_until`, governor caps drop, effectful jobs do not resume on their own and need a
  fresh owner approval, and a telemetry row is written. `restricted` is a state because it is not cleared by a
  login; the owner decides (retire, wait or appeal). Error precedence for Hermes: `checkpoint` over
  `outcome_uncertain`, with the `effect_id` in the details.
- **A waiting identity does not hold a slot (S05-11).** After the pause plus the ticket lifetime, the identity
  sleeps (journal, flush, bundle). `wake(purpose=reauth)` starts when the person opens a fresh link. Seven
  slots per node and one client per node (Q-13) mean a few stuck identities would otherwise pin capacity.
- **A `research` identity** never enters `needs_reauth` (S04-8): no marker, no login.
- **Browserbase-homed identities** skip the node and bundle steps (D11).

### 3.9 Jobs, runs, steps

`jobs`: `job_id`, `kind` (`wake | sleep | run | batch | act | extract | task | publish | reconcile | reauth |
maintenance`), `account_id`, `identity_id`, `token_id`, `tenant_id`, `state` (`queued | claimed | running |
needs_human | needs_approval | done | failed | cancelled | uncertain | missed`), `queued_reason`
(`identity_state | human_session | rate_limited | capacity`), `missed_reason`, `idempotency_key` (unique per token
and tool; scheduler jobs use `(manifest_item_id, occurrence)`), `args`, `result`, `error`, `not_before`,
`claimed_by`, `claim_expires_at`, `parent_job_id`, `budget` (`max_usd`, `max_steps`), `cost_usd_micro`,
`needs[]` (an **ordered** list, for example `[reauth, reconcile, approval]`, S05-5).
- **Claim.** `SELECT ... FROM identities WHERE identity_id = $id FOR UPDATE` first. The claim then **applies the
  acquire predicates of 3.5** (state, cool-down, holds, open effects) and, if any fails, leaves the job
  `queued` with `queued_reason = identity_state` (S05-1). It takes the next job by **weighted fair share across
  tenants**, not the globally oldest (S09-7). So there is at most one running job per identity. A scheduler job
  runs the same state check as 4.0; the scheduler also stops pre-waking such identities.
- **Batch (S04-5).** A `batch` job has a parent and one child job per seed (4.13): `parent_job_id` means "child
  of this batch". A batch has one campaign budget, partial results, cancel-all and per-seed verdicts.
- **A job with `needs` having more than one item** resolves them in order: reauth, then reconcile, then
  approval. A job with any effect in `intent` or `uncertain` cannot resume until the effect is terminal.
- **Missed jobs.** A due scheduled job that meets a human lease, a hold or a non-serving state is deferred. If
  its window closes it becomes `missed(reason)`, the owner and the profile are told (C16) and the manifest
  runner writes a visible `skipped` row to `job list` and the daily note (S06-10, G12-4).

`run_steps`: `job_id`, `step_no`, `step_key`, `rung` (`L0..L5`), `outcome`, `target` (`{role, name, frame_path}`),
`decided_by` (`{provider, model, template, confidence, margin}`), `cost_usd_micro`, `latency_ms`,
`evidence_refs`, `effect_id`, `blocker_checks[]`. The rung per step is what makes the System-1 share computable.

`l1_entries` (the fleet's own replay cache; **the cache stores Actions, not instructions**, D5):
- **Key:** `(platform, procedure_digest or null, step_key, url_pattern, dom_fingerprint, locale, variant_id,
  executor_id, schema_version)` (S06-5, S14-2). Locale is in the key because accessible names are localized and
  the persona locale is pinned per identity. `variant_id` names a staged rollout or A/B variant seen by the
  detector (3.15). A changed executor or schema starts empty: entries are versioned and **never converted**.
- **`dom_fingerprint`** is a hash of the `(role, name-class)` skeleton of the step's region. The region is the
  subtree rooted at the landmark or dialog holding the target. A name-class is the accessible name lowercased,
  with digits, dates and handles replaced by placeholders, cut at 40 characters. Whether this tolerance is right
  is **to measure** (M3 corpus).
- **Value:** `{selector (xpath), method, arguments_template}` plus `target_fingerprint {role, accessible-name
  pattern, frame path, nearby-text hash}`.
- **State machine (S06-6):** `candidate -> released -> quarantined -> retired`, with counters `replays`,
  `verified`, `mismatches`, `outcome_failures`. The feedback answer `step_quarantined` and `docs/engines/stagehand.md`
  section 9.3 use the same words (update together).
- **Promotion.** A step with `effect = none` is promoted `candidate -> released` by machine criteria: `k` verified
  successes with the code `expects` passing, zero mismatches, at least two identities (`k` is an estimate to
  measure). Entries for effect steps exist only inside a released procedure version (D13, D5).
- **A lookup miss counts against the procedure step**, not only against an entry (S06-5), so a UI change that
  makes every lookup miss is still visible to the detector (3.15).
- Scoped per tenant by default; a content-scrubbed shared tier across tenants is a later review **[extension]**.
  A rung that succeeds on a new page becomes a *candidate*; D13's release rules promote it.

Other tables, briefly: `spend` (`entry_id`, `tenant_id`, `identity_id`, `job_id`, `provider`, `kind`,
`state: reserved | settled | released | unknown`, micro-dollar amounts, unique `request_id`; worker-side
**budget slices** settle in batches, 4.0 and 2.1 C13); `evidence` (`evidence_id`, `job_id`, `step_no`, `kind`,
`class`, `spaces_key`, `sha256`, `bytes`, `expires_at`); `decision_log` (every /decide call); `viewer_tickets`
(hash, identity, operator, purpose, expiry, used) and `viewer_sessions` (ticket exchanged once; heartbeat;
closed_at); `operators` (`operator_id`, roles, `tenant_id` for a `tenant_viewer` or `client_approver`, passkey
credentials; 6.13); `nodes` (`node_id`, region, size, `node_class`, state `active | draining | retired`, slots,
image digests, heartbeat, `tenant_affinity`); `audit` (append-only).

### 3.10 An account across a move: replacement and cutover **[extension]**

D3 says a new IP or a new infra home is a new device generation under the same account. This subsection says
what that means in the tables (S07-5, S07-6, G10-3).

**What carries over, and what is fresh.**

| Carries over (keyed on the account) | Fresh (keyed on the identity) |
|---|---|
| The account record, alias, bindings, API connection and its health | The login, cookies and state bundle (generation 0 again) |
| The effect ledger, including `committed` and `uncertain` rows, and their holds with scope `all` | Node affinity; the IP and its vetting, **unless the owner chooses the same-IP path** below |
| Governor windows and caps (keyed on `(tenant, platform, handle)`), consents, opt-outs | The persona hash, `auth_epoch` (reset to 0), image cohort |
| Manifests and campaigns (as new revisions, below), schedules, queued jobs | The canary result and the first-post gate (`account_firsts` is per generation for browser effects, MILESTONES S2 d) |
| Conversations and their windows | Browser-scope holds that name the old identity |
| L1 entries (per tenant, locale and executor are unchanged) | Viewer tickets and sessions |

**Cutover operation (owner-only, audited).**
0. **Same IP or new IP (G10-3; `docs/identity/identity-and-proxies.md` section 2.7).** The owner chooses and
   records the reason code. **Same IP, or the old IP is already dead:** the predecessor goes to `quarantined`
   (class `fleet_side`) first, keeping its bundle and keys as the rollback, and skips `migrating`. The account has
   no serving identity until cutover, so its browser jobs wait as `identity_state`. Two fingerprints never wake on
   one IP: the partial index of 3.2 and the lift rule of 3.8 enforce it. **New IP and the old IP still works:**
   the predecessor keeps serving through steps 1 and 2.
1. Create the successor beside the predecessor: a new `identities` row with `generation + 1`, `successor_of`,
   `serves_account = false`, state `canary`, the new home, and either the predecessor's `proxy_id` (same-IP) or a
   newly vetted IP. A new IP follows the region rule of D3. A
   replacement is refused if the predecessor had a checkpoint, restriction or quarantine inside a window the
   owner sets (ban evasion is a red line; MILESTONES G5.11).
2. Run the replacement canary (MILESTONES S2): login with an operator present, read-only wakes, a per-action
   approval for the first browser effect, a reset first-post gate. A failed canary leaves the predecessor
   serving and intact (MILESTONES GB.8).
3. **Cutover transaction.** Flip `serves_account` from the predecessor to the successor; set the predecessor
   `migrating`; re-point queued jobs and schedules to the successor; write a **new revision of every active
   manifest** (the persona and device lines changed, so the revision diff shows exactly that) and send them for
   re-approval; invalidate pending per-action approvals whose subject names the old device. Committed and
   uncertain effects need no copying: they are already on the account.
4. **Retire precondition.** The successor passed the canary rule **and one full scheduled cycle**. Until then the
   predecessor stays in `quarantined` (its bundle and keys intact; `migrating` moves to `quarantined` once the
   cutover transaction commits). Only then is the predecessor `retired`.
   **Rollback (owner-only, one transaction, before retire).** Successor to `quarantined`; predecessor lifted from
   `quarantined` to `asleep` (3.8 lift rule: refused while another live row holds its `proxy_id`, which the
   successor no longer is once quarantined); `serves_account` flipped back; queued jobs and schedules re-pointed;
   a new revision of every active manifest sent for re-approval. To the platform this is one more device change,
   not an undo (`docs/identity/identity-and-proxies.md` section 2.7 step 8).
5. **Retiring an identity never revokes the OAuth connection.** That belongs to the account. Retiring the
   account revokes it and destroys its identities' bundles (`docs/identity/identity-and-proxies.md` section 2.6).
   Together with the partial unique index of 3.2, this removes the old collision: the successor and predecessor
   share one account row.

If the old IP is gone for good and an effect is `uncertain`, reconcile cannot run through the dead egress. The
successor logs in, and the reconcile job runs on it (purpose `reconcile` is allowed in `canary`). If the read
cannot settle it, the owner records `human_resolved` from the client's own device, then retires the old identity
(S07-3).

### 3.11 Holds **[extension]**

`holds(hold_id, account_id, identity_id null, reason, scope, platform null, conversation_id null, effect_id null,
since, cleared_at, cleared_by, clear_note)`. A hold with `scope = browser` and an `identity_id` applies to that
identity only; a hold with a null `identity_id` follows the account. `acquire` for work needs **no open hold
whose scope covers the work** (3.5). An API `publish` checks only holds of scope `api` or `all` that match its
platform and conversation (4.6).

| Reason | Scope | Set by | Cleared by |
|---|---|---|---|
| `uncertain_effect`, browser or human channel | `all`, on the account | The ledger, when a lease is lost or a receipt does not arrive | The reconciler (`found`), or an operator's `human_resolved` |
| `uncertain_effect`, API channel | `api`, on `(account, platform, conversation)` | The ledger | The reconciler through the Conversations API read, or `human_resolved` (S03-10). One timed-out Messenger send must not block Instagram, TikTok or other conversations |
| `proxy_mismatch` | `browser`, on the identity | The forwarder or `probe_ip` | **Owner-only `hold_clear`**, with preconditions: the pinned exit IP is back, vetting re-ran, and the stability echo passed over an idle period (length: estimate, to measure). Or the replacement flow (3.10). `identity_status.needs` shows `owner` with a reason text |
| `persona_mismatch` | `browser`, on the identity | The wake check | An operator, after persona review and the canary rule |
| `upload_failed` | `browser`, on the identity | The node agent | A successful re-upload, or the owner accepts the loss and the identity restarts at generation 0 |
| `owner_hold` | `all` | The owner | The owner |

- **Why a table (S07-2).** A mid-session IP swap with an effect in flight gives `proxy_mismatch` and
  `uncertain_effect` together, and `upload_failed` can join. Clearing one must not reopen work while another
  stands.
- **`proxy_unavailable` is not a hold (S07-1).** A transient vendor outage at wake (upstream down, 407, timeout)
  is a retryable wake failure with backoff, a per-vendor circuit breaker, and one aggregated alert (4.10).
  `proxy_mismatch` (the exit IP changed) is the incident-grade hold. The forwarder reports them as different
  classes (`docs/infra/steel-profile.md` section 9.6).
- **An IP hold blocks the browser only.** API calls leave fleetd, not the identity's proxy, so scheduled Page
  posts that never needed the IP keep going (S07-4).
- **No agent tool clears a hold** (D17).

### 3.12 Inbound, conversations, consent and opt-out **[extension]**

Without this, the fleet cannot tell Hermes that a message exists, and the Charter's "reply only to people who
wrote first" has no data behind it (S03-1, G11-7, S13-1).

| Table | Key fields |
|---|---|
| `inbound_events` | `event_id`, `platform`, `account_id`, `external_event_id` (**unique per platform**: dedupe), `kind` (`dm`, `comment`, `mention`, `story_reply`), `conversation_id`, `author_ref` (opaque), `body_enc` (untrusted), `received_at`, `signature_ok`, `billed_cost_usd_micro`, `state` (`new`, `delivered`, `dropped:<reason>`), `retention_until` |
| `conversations` | `conversation_id` (fleet-issued, opaque), `account_id`, `platform`, `external_thread_ref`, `author_ref`, `kind`, `first_inbound_at`, `last_inbound_at`, `last_outbound_at`, `window_kind`, `window_expires_at`, `opted_out`, `closed` |
| `opt_outs` | `account_id`, `platform`, `author_ref`, `since`, `source` |
| `consents` | see 3.13 |

- **Window rules are data, in `channel_policy`,** from `docs/channels/social-channels.md` section 3: Messenger 24 h,
  with a 7-day `human_agent` tag; Instagram 24 h and a 7-day private reply; TikTok Business Messaging 10 messages
  in the first 48 h then unlimited within 48 h of the user's last reply and then at most 3 (so the TikTok window
  counts messages as well as hours). They are re-read at build time.
- **Eligibility is checked in code at three places:** at draft time, at approval time and at send time (4.12).
  A reply or DM goes only to a conversation with an inbound message inside its window, not opted out, belonging
  to the caller's account. Otherwise the answer is `refused` (D17).
- **Spend and abuse (S03-12, S13-12).** Every inbound event is metered per account. An X `dm.received` webhook
  event is billed ($0.010; `research/verification/social-platforms.md` SP-4), so an attacker can run up fees by
  messaging. Each account has an inbound budget and per-author and per-thread ingestion limits with dedupe. When
  the budget is spent, fleetd stops the X webhook subscription (or filters), drops events with a policy that keeps
  existing legitimate threads, and notifies the owner. A spent spend cap can stop replies but cannot refuse a
  webhook, which is why the subscription itself must be stopped. An answered X DM costs about $0.035 in platform
  fees before any context read (webhook, send and read-back; estimate from the listed fees).
- **Retention of message bodies** follows the data-handling answer (Q-07) and the tenant's policy; the default
  is short and the body is never copied into a vault note by fleetd.

### 3.13 Campaign support tables **[extension]**

| Table | Purpose |
|---|---|
| `media_assets` | `asset_id`, `tenant_id`, `sha256_source`, `sha256_published`, `mime`, `width`, `height`, `bytes`, `derived_from`, `platform_checks` (per platform: spec ok or the reason), `public_url_state`. Ingest, convert (for example PNG to JPEG for Instagram) and hash **before approval**, so the approved hash is the hash of the published artifact (S02-2). Platform specs are validated at approval. Files are served from the verified domain on unguessable, short-lived URLs that outlive the publish by a set margin. Early public URLs can leak unreleased assets, so a URL exists only from just before the publish. |
| `platform_apps` | `platform`, `app`, `state` (`not_applied`, `applied`, `in_review`, `approved`, `restricted`, `suspended`), `access_level`, `source` (dated), `checked_at`. Preflight at manifest approval: refuse, or mark the item `blocked_until_ready` (S02-7). |
| `connection_health` | `account_id`, `platform`, `token_ok`, `scopes`, `expires_at`, `refresh_due_at`, `last_checked_at`, `state` (`ok`, `degraded`, `reauth_required`). **Per account and platform, and it never sets `identities.state`.** A 401 from TikTok marks only that connection (S02-9). A scheduler refreshes tokens ahead of expiry (Instagram long-lived about 60 days; TikTok access 1 day, refresh 365 days; `docs/channels/social-channels.md` section 3). |
| `consents` | `consent_id`, `account_id`, `platform`, `scope` (for X: express consent per action type), `granted_by`, `document_ref`, `granted_at`, `revoked_at`. Revocation handling cancels the connection's queued items. |
| `account_firsts` | `account_id`, `channel_generation` (0 for the API channel, the identity's generation for browser effects), `content_type`, `destination`, `first_effect_id`, `approved_by`, `at`. Gate G checks it (4.3). |

**Connector support (C22).** OAuth start and callback (the client authorizes in their own browser), scope
selection, a consent ledger, the token-refresh scheduler, revocation handling and the opt-out ledger live in one
component next to the connectors. Per platform, the connector names its **live limit source**, or the cap is
marked static and "to verify" (S02-8). `research/corpus/` has no Meta, TikTok, LinkedIn or X pages, so every non-header source below is
unconfirmed until build time:

| Platform | Live source | If none |
|---|---|---|
| X | `x-rate-limit-*` response headers | n/a |
| Instagram | the `content_publishing_limit` endpoint (the pages disagree on 50 versus 100, SPV SP-5) | static cap, to verify |
| Facebook Page | none confirmed in the research (the corpus holds no Meta documentation); usage headers may exist, **to verify** | static caps from `docs/channels/social-channels.md` section 4.2 (private replies 750/h, Send API 300/s, Conversations API 2/s), to verify |
| TikTok | none confirmed; per-account 6/min, 15/day and 40 QPM are static caps | static cap, to verify |
| LinkedIn | none confirmed; Development tier 500/app/day and 100/member/day are static | static cap, to verify |

Re-read every cap at build time (D2: dated).

### 3.14 Research tables **[extension]**

| Table | Purpose |
|---|---|
| `source_registry` | `source_id`, `host` (registrable domain), `purpose`, `allowed`, `robots_fetched_at`, `robots_allows_bot`, `crawl_delay`, `bot_user_agent`, `min_interval_ms`, `blocked_until`, `listed_by`. The robots and politeness component (C23) reads it. **A robots fetch that fails on the network fails closed.** |
| `leads` | `lead_id`, `tenant_id`, `batch_job_id`, `company_domain`, `fields` (name, role, public contact values), each value `{quote, url, fetched_at, content_sha256, domain_match}`; `unverified_contact[]` for values whose `domain_match` is false; `evidence_ref` (class `lead_source`); `consent_basis`; `state`; `retention_until`. |

The lead record keeps `quote`, URL, fetch time and `content_sha256` **inside the record and the Obsidian note**, so
provenance survives the expiry of the stored blob (S04-9). Values with `domain_match = false` go to
`unverified_contact`, are excluded from any "contactable" export, and tier-1 extraction is restricted to the page
regions named by the goal (footer, contact block) (S04-13). The playbook is `docs/playbooks/lead-gen.md`.

### 3.15 Detection and incident tables **[extension]**

| Table | Purpose |
|---|---|
| `site_incidents` | `incident_id`, `host`, `home`, `failure_class` (`functional`, `defence`), `evidence_refs[]`, `identities[]`, `first_seen`, `last_seen`. `feedback kind=blocked` can write it; a `home_evidence` field on the identity can reference it (the Browserbase R1 note, `docs/engines/browserbase.md` section 8.1) (G10-12). |
| `host_cooldowns` | `identity_id`, `host`, `class`, `until`, `reason`. Written by the `site_blocked` blocker class (4.2 step 6). |
| `step_health` | Windowed counters per `(procedure, step, url_pattern, variant)`: L1 mismatches, lookup misses, L2 abstains, distinct identities affected. Feeds the change detector (4.16). |
| `incidents` | `incident_id`, `cause` (`vendor`, `region`, `image`, `provider`), `opened_at`, `closed_at`, `alert_group`, `affected_identities`. Groups alerts and throttles reconcile and wake storms (4.10, S09-16). |

## 4. Call flows

### 4.0 Conventions for every public call

1. **Authenticate:** token lookup by HMAC; reject a literal `${...}` bearer; check the minimum skill version.
2. **Admit:** per-token and per-tenant limits on requests per second, in-flight jobs and in-flight wakes. Over a
   limit: `rate_limited` (a distinct reason, S09-7). `job` long-polls have their own rate rule so 1,000 profiles
   polling do not starve the doors.
3. **Resolve:** `alias` -> binding -> account and its serving identity; check scope (3.4); check identity state
   (the acquire predicates of 3.5) and any hold whose scope covers the call (3.11).
4. **Policy gate R** (4.3): the deterministic, table-driven red-line check that runs on every tool call, before
   anything else is spent. It can answer `refused` or `scope_denied` here.
5. **Idempotency:** a repeated `idempotency_key` from the same token and tool returns the first call's job and
   result. `publish` and effectful `run` require a key. Other write tools get a server-derived key, returned
   in the result. Scheduler jobs use the deterministic key `(manifest_item_id, occurrence)` (3.6).
6. **Return inside the 90 s budget.** Work that can exceed a few seconds is a job. Write tools take `wait_s`
   (default 20, maximum 60, **estimates chosen to stay under a plugin-less host's 90 s timeout**): if the job finishes in
   time the result is inline; otherwise `{status:"running", job_id}`. `job` long-polls up to 60 s, so a
   employee on a turn-capped host spends few iterations polling.
7. **Errors are answers** (section 5.5): normal results with `ok:false`, never an MCP protocol error, so a
   refusal reaches the model as data.
8. **Every effectful step ends in the effect ledger** (3.6) or is not effectful.

### 4.1 Wake (`identity_control wake`, or the first stage of any job on a sleeping identity)

Cold wake was measured at 11.7-21.6 s as one composite chain on arm64 Docker (container to health
3.1-6.6 s, create-with-persist 6.5-11.0 s, first navigation 2.2-3.6 s). That is a **floor**: it excludes
bundle download, decrypt and extract, proxy connect, the IP and persona checks, and node creation (DigitalOcean
bills a 60 s minimum and creates at most 10 droplets at once). A failed restore from a stale lock cost another
27 s and then returned 500 (C-27, SCA-6). All numbers are re-measured on a droplet in M1 (O-17). So wake is
always submit-then-poll. **Because nodes are created and destroyed on schedule (7.4), the usual wake also pays
for download, decrypt and extract of the bundle, so bundle size and download time are terms in the wake budget
and in the pre-wake lead (4.11), not a rare case** (S01-7).

```
 Hermes        fleetd                      node agent                runtime / Steel
   | wake        |                              |                          |
   |------------>| W1 auth,scope,state          |                          |
   |<-- job_id --| W2 job row                   |                          |
   |             | W3 claim+acquire lease  (T)  |                          |
   |             | W4 place on node             |                          |
   |             |--- W5 wake(T,key,persona)--->| W6 bundle -> volume      |
   |             |                              | W7 holder + egress rule  |
   |             |                              | W8 forwarder, Steel,     |
   |             |                              |    runtime ------------->| forwarder up
   |             |                              |                          | W9 exit-IP check
   |             |                              |                          | W10 POST /v1/sessions
   |             |                              |                          | W11 health, guard, persona
   |             |<------ W12 login probe ------|<-------------------------|
   |             | W13 state=awake, job done    |                          |
   |-- job ----->|                              |                          |
```

- **W1 Validate.** `awake` -> return success (idempotent). `waking` -> return the existing job.
  `needs_reauth`, `checkpoint` or `restricted` -> answer with that code (a wake would reload the same bad
  session), except a wake with `purpose=reauth`. `quarantined`, `migrating` or `retired` -> answer with that
  code. `canary` -> allowed only with `purpose` `reauth`, `canary` or `reconcile`.
- **W2 Job.** Insert the `wake` job; answer with `job_id` in well under a second.
- **W3 Claim and lease.** Lock the identity row, then `acquire` (3.5). `identity_busy` names the holder kind and
  expiry only; `identity_held` names the hold reason; a refused state leaves the job `queued` with reason
  `identity_state`.
- **W4 Place.** Filter nodes by infra home, tenant (the isolation unit is the tenant, simultaneous and
  sequential; 7.2), node class (7.7), region and proxy reachability, free slots, and the per-node concurrent-wake
  cap (3 browsers already saturate CPU, SCV SCA-5; the cap value comes from M1). Slots: planning slot 1.5 GiB
  browser + 0.35 GiB runtime, 0.6 vCPU, so 7 per `s-8vcpu-16gb` (estimate). Prefer `last_node_id` (its bundle
  cache is warm), then least loaded. Record node-to-proxy latency in wake telemetry (S09-15). No node: ask for
  scale-out and keep the job `queued` with reason `capacity`; if scale-out is impossible, `infra_unavailable`.
- **W5 Command.** fleetd sends `wake{identity_id, token T, command_key, purpose, persona, proxy_ref, bundle_ref,
  image_cohort}` over mTLS. The node agent refuses `T` lower than the highest seen, then persists `T`. **The
  node agent derives `extension_mode` itself** from the identity's kind, image flavor, persona and the wake
  purpose (S14-4): `account` identities get `none`; a `research` identity gets the persona's mode; a human-login,
  `reauth` or `canary` wake always gets `none`. fleetd does not pass it per wake.
- **W6 State.** Generation 0 (no bundle): create an empty user-data-dir and write the `.fleet-identity` marker
  (`docs/infra/steel-profile.md` section 8.1 steps 3-4). Otherwise use the node's cached generation if its sha256
  matches `current_bundle_gen`; else download from Spaces, verify sha256, decrypt with the identity's data key,
  extract into a node-local volume. Delete `Singleton*` under the lease (preferred over a fixed hostname, which
  can still SIGKILL a colliding PID; D4). Verify the marker file `fleet-identity.json` (identity id and
  generation) **[extension]**: a restore into the wrong directory otherwise looks like a logged-out browser.
  **Then apply the cookie journal before the first navigation to the platform** whenever the bundle is
  `cookies_unflushed` or an uploaded journal is newer (3.3, S01-5).
- **W7 Network.** Create the holder container, which owns the identity's network namespace, and install the host
  rule: this namespace may reach its vendor proxy `IP:port` and nothing else (no metadata endpoint, no VPC, no
  host) (`docs/infra/steel-profile.md` section 6).
- **W8 Containers.** Start the forwarder sidecar, then Steel (`--init`, caps, volume at
  `/app/api/user-data-dir`, env `TZ`, `LANG`, `LANGUAGE`, Chromium args incl. `--accept-lang` and the explicit
  SwiftShader flags), then the runtime (Guard, exporter, prober). Actor containers (executor, Stagehand worker,
  Browser-Use worker) start only when work needs them. The Stagehand extension is mounted only in the `research`
  flavor and never on a human-login or canary wake. Steel's idle default Chromium has no route out until the
  forwarder exists.
- **W9 Proxy check, before any session.** The forwarder fetches an IP-echo URL through itself. It must equal
  `proxies.exit_ip`, with the ASN class and geo/timezone consistent with the persona. **Two outcomes (S07-1):**
  *`proxy_unavailable`* (upstream down, 407, timeout): no hold; the wake fails with a retryable
  `infra_unavailable`, backoff, a per-vendor circuit breaker and one aggregated alert. *`proxy_mismatch`* (a
  different exit IP): everything stops, `holds` gets a `proxy_mismatch` row (3.11), notify, job fails
  `proxy_mismatch`. No browser ever runs on a wrong IP.
- **W10 Session.** `POST /v1/sessions {persist:true, proxyUrl:"http://127.0.0.1:<f>", userAgent, timezone,
  dimensions, extensions:[...]}` where `extensions` is `["stagehand"]` only when the derived `extension_mode` is
  `A` or `B`, otherwise empty. Never send `userDataDir`, `persistProfile` or `profileId` (stripped with HTTP
  200; C-04). A pinned `userAgent` turns fingerprint injection off. Drive Steel's primary page for the first
  navigation, never a fresh `newPage()`.
- **W11 Health is never Steel's HTTP status.** (a) The live Chromium argv has
  `--user-data-dir=/app/api/user-data-dir` **and** the mounted directory's marker matches; (b) the observed
  persona equals `persona_hash` (on a Browserbase home: the reduced hash of 3.3); (c) the guard is attached and
  `wait_ready` returns. Any failure: stop, hold, `persona_mismatch` or `infra_unavailable`.
- **W12 Login probe.** Skipped for `research` identities (S04-8). Otherwise per platform, deterministic first
  (`marker_spec`), then the `login_wall` decider question if ambiguous. On failure, the journal was already
  applied in W6; try once more to re-inject it (`sessionContext` on a fresh create; the combination with
  `persist:true` is **untested**, M1) and probe again. Still failing: `needs_reauth`, lease released, a viewer
  ticket sent **by the notifier to the named person** (4.8). The probe never tries to log in.
- **W13 Commit.** `state=awake`, `node_id`, `awake_since`; start the lease heartbeat and a context-journal
  timer (every `J`, an estimate). **Each periodic journal is encrypted and uploaded to Spaces under the fencing
  token** (3.3), so a node loss does not lose cookie rotation. The job completes with
  `{state:"awake", auth:"ok", wake_ms}`.

**Browserbase-homed identity (opt-in; D11).** No node and no bundle. A worker host creates the session with
the identity's `context.id` and `persist:true`, `proxies:[{type:"external",...}]` (HTTP or HTTPS only; the
credentials necessarily go to Browserbase), `recordSession:false`, **`solveCaptchas:false`**, and applies a CDP
timezone override on every page (fragile across reconnects and Live View; **to measure**). The guard attaches to
the remote `connectUrl`. The lease is the per-Context lock. `browser.close()` is never called between steps: it
releases the session even with `keepAlive` (BB-9). Fencing is weaker here (3.5).

### 4.2 Run a procedure (`run`)

1. **Validate.** Gate R has passed. Scope covers every `scopes_required` of the procedure; procedure is
   `released` and the registry digest matches (`not_released`); `fields` validate against `input_schema`
   (`invalid_arguments`); budget reserve succeeds (`budget_exhausted`).
2. **Preflight authority, before waking anything.** For every effect step, resolve the content source: an
   approved manifest item that is in its window with caps left, or an `approval_id` that is approved,
   unconsumed and hash-matching. If missing, create the approval request and answer `needs_approval` at once.
   `mode:"draft"` (the default) runs everything up to the first effect step and returns a preview plus an
   approval request. Also check the account-level state now: no covering hold, no effect in `intent` or
   `uncertain`, the platform app is ready (3.13), and the first-post gate (3.13).
3. **Governor.** Reserve a slot in each window the effects will touch (`rate_limited` or `platform_limit`).
4. **Job and lease.** Create the `run` job. Acquire the lease (`purpose=work`; refused states leave the job
   `queued` with reason `identity_state`). If the identity is asleep, stage 0 is the wake flow (4.1).
5. **Steps.** For each step fleetd sends one command to the executor:
   `{job_id, step_no, op, params, rung_hint, fencing_token, command_key}`. The executor runs the **blocker check**
   (below), then the ladder (4.3), and answers `{ok, rung, target, evidence_refs, observation, blocker?}`. fleetd
   writes `run_steps`. Effect steps go through gate G (4.3).
   **Blocker check first (S05-2, S05-3).** After every navigation and before every executor command the
   executor evaluates the platform's `blocker_spec` (3.3) from signals the Guard already sees. A positive result
   short-circuits to the pause in step 6. It never goes to L2 or L3.
6. **Blockers have deterministic responses, in a taxonomy of five classes:**
   - `login_wall`: the session expired. Pause the identity (`needs_reauth`), job `needs_human`, the notifier
     sends a ticket. Resume after the login probe passes. **Never solved by an agent.**
   - `checkpoint`, `captcha`, `restricted`: the platform challenged or limited the account. The identity
     enters `cooldown_until` (3.8); effectful jobs do not auto-resume and need a fresh owner approval; a
     telemetry row is written; **never solved**. A `restricted` identity is a state of its own.
   - `site_blocked` **[extension]** (G10-11): the site refuses this browser or IP (a bot-defence interstitial,
     a 403 or 429) and the page is not a platform challenge. Write a per-`(identity, host)` cool-down
     (`host_cooldowns`, 3.15), **no automatic retry**, notify the owner, and add repeated step failure on one
     host to the notifier list (C16). Scheduled pre-wakes do not keep waking the identity against that host.
     This is not a reason to move to Browserbase (D11). A `checkpoint` answer remains for platform challenges and
     pauses the whole identity; `site_blocked` pauses one host.
   - `dismissable`: a pure UI notice (a cookie banner, a "what's new" card). A released dismiss procedure, else
     one L3 attempt on a non-effect step, else `needs_human`.
   - `assent` (S06-8): terms or policy updates, age or identity confirmation, permission prompts, payment or
     boost upsells. Always `needs_human`, **never an L3 target**. L3 clicks on controls named accept, agree,
     allow, confirm or continue are denied unless the released step names them.
   `no_change`, or the same action three times: stop.
7. **Verify and finish.** The procedure's verifier adapter runs an independent check (not the agent's own
   claim). Settle spend. Write evidence. Build the `obsidian_note` block. Release the lease, or keep the
   identity awake for the next queued job inside the idle window (4.11).
8. **Resume after a pause.** A job paused in `needs_human` or `needs_approval` holds a `system` lease so nothing
   else can claim the identity (3.5). The `needs` list is ordered (3.9): re-auth, then reconcile, then
   approval. **Resume restarts at the last `restart_from` boundary before the first effect that is not
   committed**, never "from the last completed step" mid-page, because after a takeover the page is gone or
   changed (S05-5, G12-6). A job with any effect in `intent` or `uncertain` cannot resume until that effect is
   terminal. After a successful re-auth, fleetd queues a reconcile job on its own. On release of a reauth or
   human lease the node agent resets tabs to a neutral page and, before the run restarts, opens a fresh tab at a
   known URL, closes the others and verifies the account header and persona (4.14). Pauses expire (TTL,
   estimate); an expired pause fails with the cause's code.

### 4.3 The act ladder, L0 to L5, and the two gates

One browser step climbs the ladder and stops at the first rung that succeeds (D5), **with two limits:** an
effect step never climbs past L1 into a free-form click (below), and a login affordance is denied on every
rung. The executor owns L1-L3; L0 can also be API calls made by fleetd; L4 is `task`; L5 is a human.

| Rung | Entry condition | What runs | Model calls | Exit |
|---|---|---|---|---|
| **L0** | The step has a deterministic path: a known URL, a procedure locator whose role and name match the stored target fingerprint, an official API call | Plain navigation, CSS/aria locator, connector call | 0 | Success, or fall through |
| **L1** | An `l1_entries` row matches `(platform, step, URL pattern, DOM fingerprint, locale, variant, executor_id, schema_version)` | **Re-snapshot first** and verify the target's role, accessible name and frame path against the stored fingerprint. Match: the executor runs the stored `Action` with no self-heal. Mismatch: a miss, never a click | 0 | Success, or a miss counts against the entry **and the procedure step** (3.9) |
| **L2** | Candidates can be enumerated from the executor's snapshot, and L2 is open for this `data_class` (table below) | Build up to 180 candidates plus `none` (pruned, option order shuffled; ask both orders on low-margin steps). Candidates for an effect step are **pre-filtered by the step's `target_rule`**. One /decide request: `target`, `blocker`, `risk`, `done`. If confidence and margin pass the threshold for `(template, model, provider, risk_class)`, code supplies `method` and `arguments` (click for links and buttons; `fill` with *supplied* text), re-verifies the target, runs the `Action`, then checks the post-condition (code first, then the decider's `step_done`) | 1 decision, 0 generative | Success, **abstain and climb** below threshold (non-effect steps only) |
| **L3** | L2 abstained, or no candidates, or L2 is closed for this `data_class`; and L3 is open for it | A generative choice among structured candidates, run by the identity's executor (D18). For `account` identities this is the fleet's **L3-lite**: its own snapshot builder, one model-shim call with the same `{elementId, method, arguments}` schema as L2, gate G and the minimal executor. For `research` identities it may be Stagehand `observe`/`act`. Success writes a *candidate* L1 entry. Constrained by `target_rule` where the step has one | 1-2 generative | Success, or retry once on another provider, else climb (non-effect steps only) |
| **L4** | Only via `task`, or a procedure step marked `explore_allowed` after two L3 failures; never for an effect step | Browser-Use agent loop, read-mostly (4.5) | many generative | Result, or `needs_human` |
| **L5** | Login, checkpoint, approval, an assent blocker, an effect step with no `target_rule` match, or planning and writing | A human through the viewer or the operator console; Hermes plans and writes | n/a | `needs_*` answers |

**Which rungs exist, per `data_class` (S06-7).** Under the Q-07 default, L2 is closed on logged-in pages
(`docs/models/system1.md` section 3.6 rule 5) and every model is closed on DM surfaces
(`docs/engines/stagehand.md` section 6.2 item 13). The table is the default until a (provider, host) pair is
cleared **[pending Q-07]**:

| `data_class` | L0 | L1 | L2 decider | L3 / L3-lite | L4 | Consequence of a UI change |
|---|---|---|---|---|---|---|
| Public / open web (`research`) | yes | yes | yes | yes | yes (read-only) | Climbs normally |
| Logged-in page of an `account` identity | yes | yes | **closed** by default | yes **once a (provider, host) pair is cleared**, else closed | `task` read-only, same clearance | L1, then L3-lite if cleared, else a person |
| DM / inbox surface | yes | yes | **closed** | **closed** (no model sees DM content) | closed | L1, then a person |
| Effect step (any surface) | yes | yes, only inside a released procedure version | candidates pre-filtered by `target_rule` | `observe` only, as a **rehearsal** on a canary account | never | Abstain and stop (`needs_human`) |

So the **System-1 share for logged-in procedures is L0 plus L1 only** until a (provider, host) pair is cleared,
and a UI change collapses it (S06-7). Repairs are done on **owner-owned canary accounts** of the same UI variant,
so client pages need not be sent to a model (4.16). `docs/models/system1.md` section 6 should state this
share rule. The human-load and System-1 estimates elsewhere in this file assume L3-lite only where the clearance
exists **(estimate, to measure in G1.4 and M3)**.

Rules (all from D5, with the verified corrections):
- **Snapshot and observe xpaths are positional.** They resolve to whatever now sits there. Before every
  replayed or decided act, re-snapshot and verify role and accessible name. A stale index in Browser-Use is
  *executed, not refused* (BRO-3), so the same check applies there.
- **No self-heal on the decider path:** with Stagehand's `selfHeal` on, a failed `act(Action)` silently calls the
  model (measured: 1 call). Stagehand v3's cache replayed a click onto the wrong element with `success:true`
  (SH-8); v3 is not used.
- **Browser-Use `rerun_history` is not a zero-call tier:** it always ends with a summary LLM call unless a
  stub `summary_llm` is passed (C-07). L1 is the fleet's own cache.
- **The Stagehand v4 cache is Browserbase-server-only** and shows `DISABLED` on Steel (SH-1), so there is no
  vendor cache to count on, and the 40% "cached" share in the cost model is the fleet's own unbuilt L1.
- A decider only picks *which* element. `method` and typed text come from code, the manifest or the
  reasoning model, never from the decider. Deciders cannot extract text, count or compare dates.
- **Effect steps stop at L1 (S06-1).** For a step with `effect != none` the ladder may not climb past L1 into a
  free-form click. Its `target_rule` (3.7) is mandatory. No match: abstain and stop (`needs_human`; the step is
  marked suspect for the detector, 4.16). A repair of an effect step is a **rehearsal**: `observe` without `act`,
  in `mode: draft`, on an owner-owned canary account. It produces a candidate with an annotated screenshot, and a
  **person confirms it before the first live click**. This sits with the Charter's "never by a model probability"
  and amends D5 (Revisions).
- **Login affordances are denied on every rung (S05-2).** A deterministic deny-list applies to L2, L3
  (`act`, `observe`, `extract`) and L4 (`task`): any control whose accessible name or role matches *log in*,
  *sign in*, *continue as*, *use another account*, *sign in with ...*, and any credential or OTP field. A blocker
  check runs first (4.2 step 5), so an `expects` failure on a login page goes to the pause, not up the ladder.
- **Unmeasured gates (M1/M3):** `act(Action)` replay across iframes and shadow DOM on Steel; Browser-Use
  `Tools.act` against a live Steel session; element-choice accuracy on dense social pages (the Stagehand spike
  chose elements with a hard-coded rule; the Browser-Use spike used real Jev on one easy page: Poetry out of 71,
  0.94-0.96, 315-388 ms).
- **The executor is chosen per identity kind, then per site class (D18, O-02).** `account` identities use the
  fleet's minimal CDP executor with no Stagehand extension unless gate G1.4 shows otherwise. The reason: the
  Stagehand v4 extension trips a public `isAutomatedWithCDP` check and stays resident after `close()` until
  `Extensions.uninstall` or a browser restart (n=1 per condition), while Browser-Use attach and navigate did not
  trip it (its actor API and coordinate clicks do). Whether platforms weigh the signal is unknown.
  `research` identities may use Stagehand with the extension (mode A, the measured recipe).
- **The `Executor` interface (S14-2) [extension].** L1 and L2 are written against a fleet-owned interface, not
  against Stagehand's types:

```
 Executor
   snapshot(scope?)           -> {nodes[{id, role, name, frame_path, region, state}], url, title}
   run(action, fence)         -> {ok, post_condition?}     # action = {method, arguments, target_fingerprint}
   observe_region(target_rule)-> candidates[]              # read-only
   capabilities()             -> {executor_id, schema_version, frames, shadow_dom, trusted_input}
```

  The fleet-owned `Action` is `{method, arguments, target_fingerprint {role, name pattern, frame path}}`, not a
  Stagehand `Action` or `xpathMap`. `executor_id` and `schema_version` are part of the `l1_entries` key and of
  the persona (3.3, 3.9). Entries are versioned and **never converted** across versions; a new version starts
  empty. Adapters wrap the minimal CDP executor, Stagehand and Browser-Use `Tools.act`.

**Gate R: policy, on every tool call, ahead of gate G (G11-1).** Deterministic and table-driven, owned by C18
(2.1). No model is in it. It is where the Charter's red lines become code. It runs before any job, wake or spend.
1. **Host policy.** For `account` identities, allow the identity's own handle and page URLs plus its login
   flow, the owner-managed `allowed_hosts`, and (for visual QA of a client's own public pages) the client's
   domains; everything else on a platform host is denied by default (CHARTER host table). **People lists
   (followers, following, likers, members) are allowed: Justin removed that red line on 2026-10-19 (DECISIONS,
   "people lists, removed"); the people-list text below is superseded and is not built.** ~~Deny~~
   people-listing surfaces (search, hashtag and explore results, followers, following, likers, members, other
   people's profiles) by the people-list path rules of 4.5 item 5, which gate G, the Guard and the post-action
   check also apply inside the session. **Deny
   everything on `x.com` and `linkedin.com` for agent browsing.** Deny social hosts outright for `research`
   identities. `extract` and `task` are not procedures, so a procedure's `authority.hosts` does not apply to
   them; gate R holds their host rules, and `task` requires `allowed_hosts` (4.5). D2's table is the source.
2. **Effect-kind deny list.** Like, follow, unfollow, repost (and any kind not in D2's table for the platform).
   Answer `refused` (`red_line_kind`); no approval request is created, and approvals for these kinds cannot be
   created.
3. **Recipient eligibility** for `dm`, `reply` and `private_reply`: the target is a fleet-issued
   `conversation_id` or comment id from the inbound store (3.12, 4.12). `refused` with `no_prior_contact`,
   `window_closed` or `opted_out`; `scope_denied` if the conversation belongs to another account. Checked again
   at approval and at send.
4. **Duplicate-content check** (3.6 second uniqueness).
5. **URL classification (S13-5).** Every URL-bearing argument (`extract.url`, `task.start_url`,
   `act navigate`, `allowed_hosts`) is validated at the door: `http`/`https` only, `security.py`
   `target_scope`, `require_public_addresses`. A failure is `scope_denied` with `reason: target_not_public`,
   before any job, wake or spend.

**Gate G: every rung, every call that may have a side effect.** Cannot be skipped by climbing.

0. **Blocker and login deny-list** (4.2 step 5).
1. **Classify.** The procedure step's declared `effect` wins. For free-form `act` and `task` there is no
   declaration, so two modes apply:
   - `read_only` (default for `task`, and for `act` when the token lacks `publish`/`dm`): a **positive
     allow-list** of actions. Navigate (inside the identity's `allowed_hosts`), scroll, find, extract; click on
     links with an `href`, tabs, disclosure widgets, dismiss/close. Text into search boxes is allowed **only for
     `research` identities on non-platform hosts** (and never under `lead_gen`, below); on platform hosts
     search is a people-listing surface and is denied (G11-1). Anything else on a platform host is refused as
     `needs_approval`. Every allowed navigation and link click is also checked against the **people-list path
     rules** (4.5 item 5).
   - `guarded` (token has `publish`/`dm`, no authority yet): same, and effect-like actions need an approval.
   - **`lead_gen` (S04-6):** for `research` identities on a non-platform host: **no `fill` or `press` in any
     input, and no form submit of any kind.** Navigation is limited to the task's registrable domain.
   An element-label classifier over role, accessible name, form action, `type=submit` and Enter in a composer
   is only a **deny-list backstop**: it **fails open on unlabeled icon buttons**. That is why the default is
   an allow-list and why the hard gate is scope plus authority, not the classifier. Its miss rate on real
   pages is **[to measure]**. Method-based network blocking is rejected: social SPAs send reads as POST
   GraphQL.
2. **Scope** (3.4). 3. **Authority:** an approved manifest item (window, caps, kill switch) or an approval
   whose `subject_hash` equals the action. 3b. **First-post gate:** if `account_firsts` (3.13) has no row for
   this account, content type and destination (and channel generation), a person must approve it: the manifest
   approval counts only if it carries the explicit per-account tick, else one extra approval.
4. **Governor** reserve. 5. **Content check:** for composers, the DOM text equals the approved `content_hash`;
   the account header equals the identity's handle; **and the approved audience, visibility and attachments,
   read from the DOM, match the approved subject** (S06-1).
6. **Intent row, approval consumption and cap bump** in one transaction (3.6), with evidence refs written first.
7. **Act.** 8. **Read-back** by the verifier (tri-state). 9. **Commit** or **uncertain** plus hold.

**Credentials are never typed.** The executor refuses `fill`/`type` into `type=password`, `autocomplete`
`current-password`/`username`/`one-time-code`, and fields whose names match login or OTP patterns, and answers
`needs_reauth`. `sensitive_data` (Browser-Use) and `variables` (Stagehand) are unused for credentials:
`variables` hide a value only from the act prompt, and once typed it appears in the accessibility tree and goes
to the model on the next inference (measured; SH-5).

### 4.4 Extract (`extract`)

`extract` is read-only for the effect ledger but is not quick: it may need a wake, a navigation and two
model calls. It is submit-then-poll, and `readOnlyHint` is true because replay is harmless (it consumes budget
and a lease, and fleetd dedupes by idempotency key).

1. Validate token, scope `read`, schema size, `via`: `auto` (default) | `http` | `browser`, and classify the URL
   at the door (gate R item 5).
2. **L0 plain HTTP, `research` identities only.** The fetch runs **inside the identity's namespace through the
   forwarder only** (a fetch worker in the runtime container), not on the host. Before every hop it validates the
   URL (`http`/`https`, `target_scope`, `require_public_addresses`), it walks redirects by hand (a port of the
   box's `follow_public_chain`), it caps size, time and content type, and it sends no cookies. A `file:` URL is
   impossible by construction. It also obeys the source registry and robots rules (4.13). A stdlib fetch took
   70-344 ms per static page in the spike. Parse with deterministic parsers (JSON-LD, selectors, a stored
   per-site extractor). `account` identities never do this: HTTP-client traffic from a client's logged-in static
   IP breaks continuity.
3. **Escalate on the goal being unmet,** not on page shape: both shape heuristics misfired in the spike (SP-12).
4. **Browser.** Wake stage if needed; navigate through the guard; L0 per-site extractor if one exists; else L3
   `extract` (two model calls: Extraction, then Metadata), scoped with a locator to cut tokens (and, for lead
   records, to the page regions named by the goal: footer, contact block, S04-13), `screenshot:true` only when
   the tree lacks the data. The shim validates against the caller's schema.
5. **A decider never extracts text.** It may choose among code-found candidates or classify.
6. Return `{data, source:{via, rung, url}}` with **every page-derived string as `{text, untrusted:true,
   source_ref}`**, length-capped and with URLs defanged (5.2 taint map). Extracted strings are untrusted page
   text: they are never used as publishable content (6.7). Values with `domain_match:false` go to
   `unverified_contact`. Logged-in pages, DMs included, go as text or screenshots to OpenRouter-routed
   providers **[pending Q-07]**. The text the model actually received is stored as evidence class `lead_source`
   for lead work (3.14).

### 4.5 Task (`task`, L4)

1. **Validate.** `mode` is `read_only` (default) or `guarded`. **`allowed_hosts` and `output_schema` are
   required** (G11-12); a goal with no measurable end is rejected before any spend. Social-platform hosts are
   denied by default through gate R. Hard caps: `max_steps` default 8, maximum 25 (Browser-Use's own default is
   500); `max_usd`; the budget reserve.
2. **Lease and wake** as in 4.1. The executor takes the **engine mutex** for this identity: Stagehand,
   Browser-Use and the human viewer can all reach the same browser, so one engine runs at a time. Switching
   engines closes the other client first.
3. **Spawn a Browser-Use worker as its own container** (an actor, `docs/infra/steel-profile.md` section 3.1),
   with a hard kill timer.
   `Browser(cdp_url="ws://127.0.0.1:3000/", keep_alive=...)`; proxy is set only on the Steel session
   (credentials in Browser-Use turn on request interception); `flash_mode=True`; `use_vision` off unless the
   task needs it (the vision-plus-judge defaults cost 2.7x per task, hands-on); `use_judge=False`; `Tools(exclude_actions=["upload_file",
   "save_as_pdf", "evaluate"])`; `highlight_elements=False` (the default injects an overlay into the page);
   `directly_open_url`; `max_failures=3`; the per-session temp directory is removed afterwards. The LLM is the
   model shim's OpenAI-compatible face with a job-scoped key (`ChatOpenRouter`, 0.13.11 or later, with
   `reasoning_models=[model]` and `reasoning_effort="low"`).
4. **Gate G on every action, before it runs.** `register_new_step_callback` fires after the model answers
   and before actions execute; mutating `output.action[i]` changes what runs (measured: swapped an action).
   The callback runs gate G and replaces a refused action with a `done`/`wait` carrying
   `needs_approval`. The same `blocker_spec` feeds Browser-Use's stop callback (3.3).
5. **Who enforces which host rule (written once; S13-8, S04-6).** `allowed_hosts` is not a Browser-Use feature we
   can lean on (`allowed_domains` is not a boundary: #5815, #4763), so:

   | Layer | What it enforces |
   |---|---|
   | Gate R (fleetd, per tool call) | Host policy of 4.3; classification of `task.allowed_hosts`, `start_url` and other URL arguments |
   | Gate G (executor, per action) | `navigate`, new tabs and link clicks against the identity's `allowed_hosts` **and the people-list path rules**; a click whose target `href` or accessible name matches a people-list surface is refused before it runs |
   | Post-action check (executor, per action, on platform hosts) | After every action on an `account` identity: if the URL (including same-document history changes) matches a people-list path, or a dialog opened whose accessible name or role matches a people-list surface (likers, reactions, followers, following, members, search results), close it, end the job with `refused` (`people_list`) and write the event. This is the layer for modals that list people without a navigation |
   | The Guard (in the browser, CDP `Fetch`) | Top-level and frame navigations against `allowed_hosts`, `task.allowed_hosts` **and the people-list path rules on platform hosts**; for `research` identities, top-level navigations limited to the task's registrable domain (sub-resources free) and `robots.txt` checked on **every top-level navigation, including click-triggered ones**; private ranges and fleet hosts |
   | The network rule (host nftables) | The proxy IP and port only. It is not a host filter |
   | Browser-Use `allowed_domains` | Belt only, never relied on |

   **Removed by Justin, 2026-10-19 (DECISIONS, "people lists, removed"): the people-list path rules, the
   post-action `people_list` check and the `people_list` refusal reason are not built. The rows above that
   mention them are superseded.** The original design, kept for history:
   **People-list path rules (G11-1).** One table per platform host, owned by C18 next to D2's table, listing the
   path and dialog patterns of people-listing surfaces (search, hashtag and explore results, followers,
   following, likers and reactions, group members, other people's profiles). Default-deny on platform hosts for
   `account` identities: only the identity's own handle and page URLs, its login flow and the paths a released
   procedure names are allowed, matching the CHARTER host table. Gate R applies it to URL arguments, gate G and
   the Guard to every in-session navigation and click, the post-action check to same-document changes and
   dialogs. Because the default is deny, a new UI path missing from the table is refused, not allowed.
   MILESTONES G3.10 tests all four layers (URL argument, clicked link, history change, opened modal).

   `docs/playbooks/lead-gen.md` section 3.7 and `docs/engines/browser-use.md` section 9 cite this table.
6. **Circuit breaker (S13-13).** After N Guard refusals in one job (N is an estimate), cancel the job, hold the
   identity read-only, write `feedback kind=injection_suspected` and send a notifier event. Otherwise a run burns
   steps to its cap.
7. **Stream** each step to fleetd (`run_steps`, rung `L4`, cost).
8. **Finish.** Result shaped by `output_schema`, every page string marked untrusted; cost; the trace; a
   *candidate procedure* if the run looks repeatable (quarantined, never auto-released). Always: kill the
   process, remove its temp dir, close the client.
9. Browser-Use is for open-ended *read* goals. Effects go through procedures and `publish`.

### 4.6 Publish via the API channel (`publish`, `channel=api`)

No browser is woken and no lease is needed. The call checks only holds whose scope is `api` or `all` for its
platform and conversation (3.11); a browser-scope hold such as `proxy_mismatch` does not stop it, because API
calls leave fleetd, not the identity's proxy (S07-4). Calls are serialized per `(account, platform)`.

1. **Validate.** Gate R has passed. While a human lease is held on the account's identity, **effects pause and
   reads continue** (4.14), so the job defers. Scope `publish` or `dm`; `channel_policy` allows `api` for this effect kind
   (else `channel_unavailable`); the platform app is ready (3.13); the connection is healthy
   (`connection_health`: token, scopes, expiry). **A 401 sets `connection_health.state = reauth_required` for
   that account and platform only; it never changes `identities.state`** (S02-9). The fix is an OAuth link
   to the client, not a viewer, and the answer is `needs_reauth` with `kind:"api_connection"`. One expired
   TikTok token must not stop Facebook posting.
2. **Target and content.** From `manifest_item_id` or `approval_id`; compute `content_hash`. Never from page
   text. For `reply`, `dm` and `private_reply` the target is a `conversation_id` (or `comment_id`), and fleetd
   re-checks eligibility now (3.12): an inbound message inside the window, not opted out, belonging to this
   account. **Read the thread first and refuse if a newer outbound message exists** (a person may already have
   answered in the platform's own inbox, S03-14). `private_reply` is a separate route with its own 7-day limit
   and a 750-per-hour-per-Page cap (`docs/channels/social-channels.md` section 3.1).
3. **Approval lifecycle.** The approval's `expires_at` is the earlier of the window close and the TTL (3.7). The
   same job continues when an approval arrives. If the window closes first, write the outcome once: approval
   `withdrawn`, conversation closed, owner told, a person may answer natively.
4. **Governor.** Reserve in every window the effect touches: the per-account window (from live headers where
   they exist), the **app window with the tenant's share** (4.17), the **grantor/member window** where the
   platform limits per authorising member (LinkedIn's 100 per member per day follows whoever authorised;
   inference), and any fee (X: $0.015/post, $0.20/post with a URL). Reads spend the same budget, so reads have
   classes with a priority: effect, read-back, health, analytics. Over a ceiling: `rate_limited` with
   `retry.after_s`, or `platform_limit` if the daily cap is spent. Caps without a live source are static and
   "to verify" (3.13).
5. **Intent.** One transaction: `INSERT` the effect (`channel=api`), consume the approval, bump the cap (3.6).
6. **Call the connector.** For example Instagram is two steps, `POST /{ig_id}/media` (a container; not an
   effect) then `media_publish` (the effect); media must be a public URL, JPEG only
   (`research/dossiers/social-platforms.md` Q1b), served from the media store (3.13).
7. **Classify the outcome.** 2xx with an id -> read back by **fetching the object by that id and comparing
   normalised text** -> `committed`; list-and-match only as a fallback after a timeout. A 4xx that the platform
   guarantees had no effect -> `failed_clean` (approval and cap released). A timeout, 5xx or network error ->
   `uncertain` plus an **API-scope** hold on `(account, platform, conversation)`. A 429 -> release the
   reservation, `failed_clean`. For a DM the receipt is the message in the thread via the Conversations API;
   Requests-folder threads idle for 30 days are not returned, so a reconcile miss there goes to `human_resolved`
   with evidence, not to "absent".
8. **Settle and record.** Update windows from response headers, settle spend, store redacted request and
   response as evidence, return `{effect_id, effect_state, platform_ref, url}`.

### 4.7 Publish via the browser channel under human-in-the-loop (`publish`, `channel=browser`)

For the rows of D2's table that allow a browser identity to act (Facebook Groups, and UI-only features of a
Page, professional or business account) and, where the owner allows it, anything else **[pending Q-01, see
section 8]**. **Not** LinkedIn and **not** Facebook personal profiles: those get `draft_for_human` (below).
Each action is human-approved, low volume, with the client's written risk acceptance on file.

1. **Validate.** `channel_policy.browser_allowed` (a subset of D2's table) covers this kind and platform; a
   valid `risk_acceptance_id`; scope; the governor's owner-set low-volume cap. There are no official numbers for
   safe action cadence on any platform; published ceilings are ceilings, never targets (social-platforms
   verdict 8). For Facebook Groups the acting `account_kind` must be `page` or `business` until Justin settles
   whether a Groups session is a personal-profile session (AQ-10).
2. **Authorization.** `channel_policy.browser_hitl` decides (section 8; the default is `per_action`). Under
   `per_action` a manifest does not authorize browser-channel effects: create an approval (exact content hash,
   target, account, audience, irreversible effects, action fingerprint) and answer `needs_approval` with its
   id. The job parks in `needs_approval`; it resumes by itself when an operator approves. Under `manifest`
   an approved manifest item authorizes the effect inside its window and caps, and steps 3 onward are
   unchanged. **The first post per account, content type and destination always needs a person** (gate G 3b).
3. **On approval:** lease, wake if needed, login probe.
4. **Non-effect steps:** navigate to the composer; `fill` the content verbatim (trusted `Input.insertText`,
   the event shape Lexical and Draft.js composers expect; **untested on real social sites**, M1). Take a
   preview screenshot as evidence, and upload it before step 7 (the evidence refs go into the intent row).
5. **Pre-submit check:** read the composer text back; its hash must equal the approved `content_hash`, the
   page's account header must equal the identity's handle, **and the approved audience, visibility and
   attachments, read from the DOM, must match** (S06-1). A mismatch aborts as `failed_clean`; nothing was posted.
6. **Who clicks (G12-15, S08-9).** The default is **`human_clicks`** for every browser-channel effect: the operator
   takes over in the viewer, sees the filled composer, presses Post, and the effect is recorded with
   `channel=human`. This is the strongest option and costs only an operator's minute. **`agent_clicks` only by an
   explicit owner setting on that identity** (`channel_policy.click_mode`), and then with a per-action approval
   every time. This is the same default as `docs/channels/social-channels.md` section 6.1. Takeover mid-click is
   still handled (4.14), because other effects can be in flight.
7. **Intent row, then click,** then a **separate read-back step**: navigate to the profile or thread list and
   match, with the target, a time floor and normalised text (3.6), inside a grace window (feeds index late; DM
   requests land in other folders; a Group with admin approval may queue the post, inference). The read-back is
   tri-state. Found -> `committed`. Absent or unobservable, or an ambiguous match -> `uncertain` plus hold.
8. **Uncertain** alerts the owner at the first `uncertain` and again when grace ends, with: account, target,
   content hash, evidence refs, what the fleet does next, and what the person checks by hand (the feed and the
   pending queue). The reconciler's read-only job tries to find the post; otherwise the console offers
   *mark found* or *mark absent*, each with a note and evidence. **No automatic resend, ever,** and no browser
   retry after a negative read-back (3.6).
9. Evidence: before and after screenshots, the a11y snapshot, the decision records.

**`draft_for_human`.** For LinkedIn messages, connection requests and Facebook personal profiles, and for an
Instagram personal account before conversion, `publish` returns the result `draft_for_human`: the draft is
stored in `approvals` and a person sends it from their own session. It creates no browser identity and no
effect row (D2's table).

No scheduled keep-warm login probes for Meta identities: the dormancy trigger covers empty accounts, and a
scripted probe adds terms exposure for little benefit (O-12). Probe only identities that really use the
browser; API-channel accounts get token-health checks.

### 4.8 Reauth via the viewer

Triggers: a failed probe at wake; a `login_wall` blocker mid-run (a `checkpoint`, `captcha` or `restricted`
blocker follows the same viewer path but sets a cool-down first, 3.8); `identity_control reauth` from an agent or
an operator. **Blocked until AQ-1 is closed** (operator authentication, below).

1. **Pause.** Job -> `needs_human`; identity state -> `needs_reauth` or `checkpoint`; effects held; fleetd takes
   a `system` lease; the notifier alerts the owner.
2. **Ticket, delivered by the notifier only (S01-3, S05-8, S13-10).** The viewer broker mints a ticket: 256-bit
   random, stored hashed, bound to `(identity, purpose, lease token)`, short TTL (15 minutes; estimate). The
   notifier delivers it **straight to the named human** (the person recorded for the identity). The agent gets
   `{ticket_id, notified:[...], expires_at}` and **never the URL**; the plugin hook and `obsidian_note` redact
   URLs and tickets. Steel's debug URLs have no authentication
   (`research/corpus/steel/`, live sessions), so the broker's sign-in is the only control. **A ticket alone never
   opens a session.** The person must also be signed in as an operator, or as a `tenant_viewer` for their own
   tenant only (6.13). Design default **[pending AQ-1]**: operator accounts with passkeys plus the
   `tenant_viewer` role, because the person logging in is often the client's own staff
   (`docs/identity/identity-and-proxies.md` section 2.2 option 2). The notification body names the account, the
   platform and why (login wall or challenge), and never contains page content. The destination is AQ-3.
3. **Wake for reauth** if asleep: `purpose=reauth`, extension `none`, no workers started, no login probe.
   **Notify only when the browser is ready** (S01-14). While the node is being created and the wake runs, the
   person sees a waiting page.
4. **Takeover.** The person opens the link, signs in, and the broker **exchanges the ticket once for a viewer
   session** that survives a page reload. fleetd runs `takeover` with `purpose=reauth` (token T+1). The node
   agent kills the actor containers. The guard and the forwarder stay up.
5. **Relay.** The viewer broker reverse-proxies **only** `GET /v1/sessions/debug` and the
   `/v1/sessions/*/cast` WebSocket for that session; every other Steel route is blocked. The page embeds the
   viewer with `clipboardBridge=true` so paste works (otherwise Ctrl/Cmd+V types "v"), shows the identity alias and
   platform, and shows one of **starting, ready, checking, done, failed**, with a **retry in the same viewer
   session** after a failed probe (a spent ticket does not strand the person). The URL bar is limited to the
   identity's platform hosts and their login providers; everything else is blocked and logged (G12-14), so no
   other account's cookies enter the bundle.
6. **The human logs in.** Verified: typed printable text and `window.open` popups work. **Untested,
   M1 gate:** Enter, Backspace, Tab, arrows, IME, passkeys, native JS dialogs, HTTP auth, file pickers.
   Modifiers are not forwarded. Until M1 passes, D14 is a plan, not an established path. If a login class
   cannot be completed here, that platform cannot be onboarded on this stack.
7. **Done and closure.** The person presses *login done* and completes the **closure** (4.14: "no effect" or
   "effect done"). Wait for the cookie-quiet period (4.9 step 3), run the login probe. On `ok`: `auth_epoch + 1`
   (for `purpose=reauth` only), store a new journal, release the lease, and fleetd queues a reconcile job if any
   effect is open. If the fleet queues a next-day verification wake after a login, it is a `system` job of kind `verify`: the only probe outside real work, and not a keep-warm probe (S01-15; D14 should say so, pending). For a `login_wall` pause the job resumes at its last `restart_from` boundary (4.2 step 8); for
   a `checkpoint` it does not resume without a fresh owner approval (3.8).
8. **Failure.** Ticket expiry leaves the state unchanged and sends a fresh link (the identity may sleep first,
   3.8). A failed probe keeps `needs_reauth`.
9. **Audit.** Operator, start, end, ticket id, viewer session id, viewer access log.

Agents never type credentials and never solve CAPTCHAs on client accounts (D14). Hermes' `browser` toolset,
including `browser_vault_*`, is disabled on fleet profiles.

### 4.9 Sleep, flush, snapshot (`identity_control sleep`, idle, schedule end, drain)

Chromium commits cookies on a 30 s timer re-armed by every cookie write, with no CDP flush. Every release
under 30 s lost the cookie; 31, 35 and 40 s kept it. Steel's own release left `Singleton*` in 6 of 6 persist-mode
runs; a raw CDP `Browser.close` left none in 3 of 3 (C-26, C-03). This order is empirical (worked once, n=1),
and social pages rotate cookies constantly, so the **journal is the source of truth for cookies** and the
tarball covers everything else. M1 tests a graceful flush. **This path is for identities that have a bundle.** A
`research` identity in `http_only` or `ephemeral_browser` mode has no bundle and runs none of steps 3 to 7 (4.13).
A login page keeps rewriting cookies, so the first sleep after a login is the likeliest to hit the 90 s cap; the
next wake therefore applies the journal first (4.1 W6).

1. **Hold the lease.** Stop issuing commands; let the executor finish or cancel the step.
2. **Quiesce.** Stop actors (Stagehand `close`, not `browser.close()`; kill Browser-Use). Optionally
   `Extensions.uninstall` for the Stagehand extension (research flavor only).
3. **Journal and quiet period.** Export the context (`GET /v1/sessions/{id}/context`; includes httpOnly
   cookies; instant). Re-export every 5 s. The quiet period starts at the last export that differed from its
   predecessor; wait for **31 s of quiet**, capped at 90 s. If the cap hits, the bundle is marked
   `cookies_unflushed` and the journal is authoritative. This hold is container time that the D12
   slot-hour accounting omits.
4. **Encrypt and store the final journal** next to the bundle.
5. **Close in order:** raw CDP `Browser.close`, then `POST /v1/sessions/release`. Verify no `Singleton*`
   remains. Only now stop the container; **never `docker stop` a live identity** (a SIGKILL that leaves the lock).
6. **Snapshot.** Slim tar with the exclusions of 3.3 and `Singleton*`, zstd, write the marker file, encrypt
   with the identity's data key.
7. **Upload** `profiles/<id>/gen-<token>.tar.zst.enc` to Spaces, verify the remote size and sha256, then move
   the pointer with compare-and-set on the fencing token (3.5); generation 1 is written by compare-and-set from
   0. **Fail closed:** if the upload or the CAS fails, the identity gets an `upload_failed` hold, **not**
   slept; the local volume is kept and retried.
8. **Release the lease,** tear down the actors, runtime, Steel, forwarder, holder and network, remove the egress
   rule, delete the local decrypted directory (the encrypted copy stays in the LRU cache). State `asleep`.
   Between tenants a node is destroyed, or the volumes, tmpfs and image layers that held client data are deleted
   (7.2).
9. **Account.** Settle spend and write the cost per identity-day.

### 4.10 Failure and recovery

| Failure | Detected by | Effect | Recovery |
|---|---|---|---|
| Stagehand worker crash or wedge | Executor heartbeat; instance lock not released (SH-6) | Step fails | Recreate the Steel session, not the container; rerun the step if non-effect; effect steps follow the ledger |
| Node or container death | Lost heartbeat; lease expires | Run `interrupted`; open `intent` rows become `uncertain` in the same transaction as the next `acquire`; hold | Placer re-wakes on another node from the last bundle plus the **newest uploaded journal** (3.3) under a new, higher token; reconcile before more effects |
| Partitioned node still running | Node agent cannot renew within the lease TTL | The old node could keep acting | **Self-fencing:** the node kills the identity's containers at `L - skew - margin`; fleetd re-places only after `L + margin` **and** a fence confirmation (the node's ack, or the droplet powered off through the provider API); the token check fences it at the next command; the one effect in flight stays `uncertain` (3.5) |
| Proxy upstream down, 407 or timeout | Forwarder or `probe_ip` class `unreachable`/`timeout`/`auth_failed` | The wake cannot start | **`proxy_unavailable`: no hold.** Retryable wake failure with backoff; a per-vendor circuit breaker; one aggregated alert (S07-1) |
| Proxy exit IP changes mid-session | Forwarder check | Browser egress stops | Stop the session; `proxy_mismatch` hold on the identity (browser scope); notify; only the owner clears it (3.11) |
| Guard drops | Guard task | Tools fail closed | `infra_unavailable`; cancel work; restart guard or session |
| Bundle upload fails | Step 7 of 4.9 | Not slept | `upload_failed` hold; retry with backoff; alert |
| Human lease expires or the viewer socket dies | Broker heartbeat | A person is cut off or an agent could start | The broker extends while input is seen; at the ceiling it warns, then closes the route; the scheduler never acquires for work while the human lease exists (3.5) |
| **Shared-fate event:** a region outage, a bad image digest, a vendor seizure, a provider outage | Many leases expire or probes fail at once | N alerts and N reconcile jobs | **Open an `incident`** (3.15) that groups alerts by cause (vendor, region, image, provider). Throttle reconcile and wake storms. Reconcile in client-priority order. Tied to the vendor breaker (S09-16) |
| Postgres unavailable | Health | No new work | Wait; **no silent fallback to degraded durability** (an asyncio-style fallback that re-runs failed work is the counterexample) |
| Chromium memory climbs (box README: "climbs with use") | Node agent threshold | Slower pages | Restart at a safe point (sleep then wake). No soak test exists for 1-3 h sessions (SCA missed issue 3) **[to measure]** |
| Disk above 80% on a node | Heartbeat | | Drain; evict cache |

### 4.11 Scheduled work and pre-wake

Most work is scheduled (D12). The scheduler turns `schedules` and manifest items into jobs at `not_before`, each
with the deterministic key `(manifest_item_id, occurrence)`. The **capacity planner** (7.8) computes the number
of awake identities over time from manifest windows and reserves nodes ahead.
- **Pre-wake lead** is a function of the measured wake p95, **bundle size and download time** (S01-7), **queue
  depth** and the number of **new nodes** to create (ten at a time, so the last wake waits
  `ceil(new nodes / 10)` creation times; the creation time is unmeasured). The dossier's "30-60 s" is an
  estimate and the 11.7-21.6 s floor leaves little margin (**to measure**). The scheduler **does not pre-wake**
  an identity that is not in a serving, workable state, or that has or awaits a human lease.
- **After a job** the identity stays awake only if another job is due inside the idle window; otherwise it
  sleeps (4.9). The idle reaper skips identities with a human lease.
- **Items from an approved manifest run without a Hermes call:** campaign-level authorization covers them inside
  their window, caps and kill switch. Gate G still runs, including the **first-post gate**: an item whose account
  has no `account_firsts` row needs the explicit per-account tick or an extra approval (3.7). Outcomes appear
  through `job` list mode and `manifest_status`. Anything outside the manifest falls back to a per-action
  approval. Items with an `inbound_event` trigger run when a matching event arrives (4.12).
- **Preflight at approval:** a manifest approved for a platform whose app is not ready is refused, or its items
  are marked `blocked_until_ready` (3.13).
- **When the work cannot run.** A due item on a held, non-serving or human-leased identity is deferred. If its
  window closes undelivered it becomes `missed(reason)` or `expired_unrun` (3.7), the owner and the profile are
  told, and the item is **never shifted outside its approved window**. The owner approves a new revision.
  API-channel items continue unless an `api`-scope hold covers them (S07-4).
- **Spreading.** Each item runs at a per-account offset inside its window, and creation of nodes is shared out
  with a weighted fair share per tenant. The offset is for capacity only; its value against detection is
  unverified (3.7).

### 4.12 Inbound events and replying **[extension]**

Before this subsection the fleet could publish a reply but could not tell Hermes that a message existed
(S03-1, G11-7, S13-1, S09-10). v0 now has an inbound path. **Push into Hermes is unresearched;** the default is
that the profile **polls `inbox` on a cron job**.

```
 platform webhook --> receiver (C19): signature check, event-id dedupe, per-account metering
        --> inbound_events + conversations (window, opt-out) --> inbox tool (cursor, untrusted text)
 Hermes (cron) polls inbox --> drafts --> publish kind=reply|dm|private_reply, conversation_id
        --> gate R eligibility --> approval (with in_reply_to) --> connector --> receipt
```

1. **Receive.** The receiver (C19) verifies the platform signature, drops a repeated `external_event_id`, meters
   the event against the account's inbound budget (3.12), and writes `inbound_events` and the `conversations`
   row (`window_expires_at` from the platform's rule; an opt-out phrase sets `opted_out`). When the budget is
   spent it stops the X webhook subscription (or filters) and notifies the owner.
2. **Read.** `inbox` (D17, scope `read`) returns, per conversation this token may answer, typed, length-capped
   items with `untrusted:true`, defanged URLs, `conversation_id`, `window_expires_at`, `kind` and a cursor.
   Retention follows Q-07. It exposes **only** conversations of accounts the token is bound to.
3. **Draft and publish.** The profile calls `publish kind:reply|dm|private_reply` with `conversation_id` (or the
   comment id for a private reply). It cannot name a free target.
4. **Eligibility is rechecked at three points:** draft time, approval time and send time (gate R item 3). The
   answer is `refused` (`no_prior_contact`, `window_closed`, `opted_out`) or `scope_denied`
   (`conversation_not_yours`). A cold DM is `refused`: that is the pass rule of G4.6.
5. **Approval.** The subject includes `in_reply_to` (message ids and a snapshot) and the card shows the
   conversation. A newer inbound message `invalidated` the approval; an approver may edit, which re-hashes and
   records both texts. Time left in the window orders the queue; the notifier alerts at a threshold; on expiry the
   outcome is written once (3.7, 4.6 step 3).
6. **Triggered replies (S03-5).** A manifest item with `trigger: inbound_event` matches a deterministic rule (the
   closed set of 3.7), sends an approved template once per conversation, is class-gated and obeys the kill
   switch. This is the only route that can answer inside Messenger's 30-second bot-response rule; a slower,
   human-approved AI draft may or may not count as an "automated bot" (unestablished: SPV missed issue 8,
   `hermes/README.md` gap 8). **Default:** a human-approved draft is treated as automated for
   disclosure purposes, `channel_policy.bot_disclosure` is set per market, and a message written or edited by a
   person may use the `human_agent` tag **[pending AQ-8]**.
7. **Flood control (G11-5, S13-12).** Per-author and per-thread ingestion limits and dedupe; a cap on pending
   approvals per token and account; a second draft with the same normalised text to a new target inside a window
   is rejected; more than `K` same-shape approval requests in a window suspends the token's `publish`/`dm` scope
   pending the owner (3.4). The owner is alerted once per burst.

### 4.13 Research identities: two modes and batch runs **[extension]**

A `research` identity has no login, so it needs no bundle, no 31 s cookie hold and no auth marker (S04-4, S04-8).
It has one of two modes, set at creation:

| Mode | What starts | Bundle | Lease |
|---|---|---|---|
| `http_only` | The holder, the forwarder and a fetch worker in the runtime container, with the egress rule. **No Steel and no browser.** | None | None needed (S04-5): fetch-only, rate-limited per host, so domains run in parallel |
| `ephemeral_browser` | As above plus Steel with `persist:false` | None; no sleep hold, no tar, no upload | A normal work lease, because it drives a browser |

Namespace owner: the holder (3.2, `docs/infra/steel-profile.md` section 2.2), which is what lets `http_only`
start without Steel. Whether this is cheaper than the cold-wake floor is **to measure in M1**.
(`docs/infra/steel-profile.md` should add the `http_only` start sequence; today it describes `probe_ip`, which is
the same shape.)

**Politeness, in code (S04-3).** The source registry (3.14) decides whether a host may be fetched, with the bot
user agent, `robots.txt` and a per-host pace. A **robots fetch that fails on the network fails closed.** The
check runs in the HTTP path and for browser navigations (4.5 table). The Charter's promises on robots and pacing
exist in code before the lead-gen skill is released (C23).

**Batch shape (S04-5).** `run` (and `task`) accept an array of seeds. One **parent job** holds the campaign
budget and the cancel-all; one **child job per domain** runs under it with a per-domain verdict
(`done | blocked | robots_disallowed | login_wall_blocked | goal_unmet`). Partial results come back from the
parent, together with the lead records (3.14). A login wall on a research identity is a per-domain `blocked`
result, never an identity state. The trial employee submits one batch and polls once, instead of 200 submit and
poll pairs.

**Navigation policy** for research tasks is in 4.3 (`lead_gen` mode) and the table in 4.5.

### 4.14 Human session: takeover, handback and closure **[extension]**

A person uses the browser by hand in three ways, each a lease purpose (3.5): `reauth` (4.8), `human_session`
(a healthy account used by hand, which is not a lost login) and `observe`. Common rules (G12-1 to G12-6):

- **Two takeover modes (G12-3).** *Default:* **request** takeover; it is honoured at the next step boundary within
  a bounded wait, and the person sees the live step. *Break-glass:* immediate; it flags the open effect and shows
  the in-doubt text. An effect in doubt at takeover **never auto-retries**.
- **State guard (G12-2).** Takeover is refused or queued while the identity is `waking` or `sleeping`.
- **Liveness (G12-1).** The broker heartbeats the human lease from the open viewer connection (3.5); there is an
  idle timeout, a hard ceiling, a visible countdown and an extend button. `viewer_close` runs on every token
  change.
- **Domain policy (G12-14).** The URL bar allows the identity's platform hosts and their login providers; the rest
  is blocked and logged.
- **Closure is mandatory (S05-7, G12-5).** When the person ends the session, a form asks: *no effect*, or *effect
  done* (kind and target), and for each effect that was in doubt, what happened. Answers are written as
  `channel=human` effect rows and `human_resolved` outcomes. Where a connector exists the fleet also lists the
  account's recent posts, comments and messages and **diffs them against the ledger**. The governor counts the
  human effects. A person's unlogged delete or post therefore cannot make a later read-back lie.
- **Handback.** For `human_session` the handback does **not** touch `auth_epoch`; it runs the probe and checks
  which account and which tabs are open. For `reauth` it follows 4.8 step 7.
- **After any human session (G12-6).** Open a fresh tab at a known URL, close the other tabs, verify the account
  header and persona, and re-run the interrupted step **from its start** (`restart_from`). Never resume mid-page.
- **Scheduled work that meets a human lease (G12-4).** A due job **defers** while the lease is held. If its window
  closes it becomes `missed(human_session)`, the owner and the profile are told (C16 event `item_missed`), and
  the job shows a stage `waiting_human`. **Default:** *effects on that account pause during a human session,
  reads continue*, and this includes API effects (the Charter's "never both" is thereby extended past the
  browser lease). `CHARTER.md` invariant 2 should be reworded to match **[pending: CHARTER owner]**.
- **Reauth versus `human_session` in the profile's view.** A `human_session` is shown to the profile and the
  notifier as "a person is using the account", not as a lost login.

### 4.15 Creating an identity (owner-only) **[extension]**

Creation is **not an agent tool** (D17). It is an owner-only flow in the operator console (or CLI), one
transaction, audited (S01-2):

1. **Inputs:** the tenant; the platform and handle; the account kind; the **use** (a row of D2's table);
   `kind` (`account` or `research`); infra home; the vetted proxy; the persona; the named human for viewer
   tickets; the bindings (token, scopes, caps).
2. **Refuses** unless: the use is a row of D2's table (otherwise `refused`, and no identity is created); a
   passed **IP vetting record** exists for the proxy (O-10); for a browser-write use, a `risk_acceptance` is on
   file; for a Browserbase home, a triage record of class B-F is attached and `solveCaptchas:false` is set;
   `extension_mode` and `executor_id` come from the image flavor (D18).
3. **Writes** in one transaction: tenant link, `platform_accounts`, `identities` (generation 1, state `canary`,
   bundle generation 0), `proxies` link, `personas`, `auth_markers` (marker and blocker specs for the platform),
   `risk_acceptances`, bindings and node affinity. An **API-only** account writes no identity and no proxy
   (S02-6).
4. **Console functions (C1):** create, bind, quarantine, retire, approve (manifests, campaigns, actions, warnings),
   take over, mark an uncertain effect found or absent (with note and evidence), `hold_clear`, cutover (3.10),
   set the click mode, and see the notification queue.
5. The identity leaves `canary` by the rule in 3.8.

### 4.16 Detecting a changed site, and repairing it **[extension]**

Before this subsection the only trigger was agent feedback and "repeats", which let one confused or prompt-injected
profile quarantine a procedure shared by every tenant, and let every identity repeat the risky climb on its own
(S06-3).

- **Detector.** Over `(procedure, step, url_pattern, variant)` it watches a windowed rate of L1 mismatches, lookup
  misses and L2 abstains across **distinct identities** (`step_health`, 3.15). At `k` distinct identities (an
  estimate to measure) the step is **suspect**. Effect steps on that variant **auto-pause** (a circuit breaker),
  the owner is alerted (C16 and C17), and a **fleet-wide repair job** is queued.
- **Agent feedback raises priority only.** It never quarantines a shared procedure on its own, and it is
  rate-limited per token. `hermes/skills/fleet-steps` section 4 (the fleet-stagehand skill of the scenario): "twice" is a hint, not the trigger.
- **Repair.** A repair is a **new procedure version**, built as a rehearsal on an owner-owned canary account of the
  same UI variant (4.3), confirmed by a person for effect steps, reviewed by the `reviewer` role, and released
  fleet-wide as a unit with its L1 entries (D13). If the platform change is staged, the canary account may not see
  the new variant; the repair record says so.
- **Alerts** (C16/C17, MILESTONES G5.9): L1 mismatch rate, System-1 share drop, L3 spend spike, `uncertain` surges,
  `item skipped: not_released`, procedure or step quarantined.

### 4.17 Admission, fairness and shared app windows **[extension]**

Spend caps limit money, not load (S09-7, S09-4).

- **Per-token and per-tenant limits** on request rate, in-flight jobs and in-flight wakes; reason `rate_limited`.
- **Weighted fair claim** across tenants in the job queue (3.9); a large batch from one client cannot delay the
  rest.
- **Operator queues** have priority classes: security (checkpoint, re-auth), then approvals, then reconcile; with
  fairness inside a class.
- **Shared app windows.** One developer app per platform is a rule (D2, `docs/channels/social-channels.md`
  section 2.1), so a burst by one client spends quota for all (LinkedIn Development tier: 500 calls per app per
  day; about 250 posts fleet-wide). The governor gives each tenant a **share of every app window** (weight,
  floor, burst), keeps global headroom for work where a person is waiting, has per-tenant and per-platform kill
  switches, an app-health monitor, and a runbook for app-level enforcement. **Apps are not split.**
- **Spend ledger on a hot row (S09-14).** Reserve-and-settle comes from a single-process ledger. Tens of calls a
  second would each update identity, client, provider and fleet rows. Decide and model workers therefore take a
  **leased budget slice**, spend it locally and settle in batches; reconcile against provider billing (MILESTONES
  G3.9).

## 5. Tool surface and errors-as-answers

This expands D17 and reconciles the four proposals in C-16. The public surface is a Hermes profile's whole
view of the fleet. Wire names are `mcp__browser_fleet__<tool>` (the server is named `browser_fleet` so it does
not merge with Hermes' built-in `browser` toolset); skills refer to the short names.

### 5.1 Principles

- **Few tools, each proven.** A tool is listed only after it passes a live end-to-end check (fleet charter
  **[unbuilt]**). If a tool cannot work right now, `fleet_status` says why (the box's rule).
- **Reads and writes are separate tools** so `readOnlyHint` is truthful. After a streamable-HTTP session
  expires, Hermes replays only `readOnlyHint:true` tools and returns `outcome_uncertain` for the rest (HP-8).
  Every write tool is idempotent.
- **Eight tools are read-only:** `fleet_status`, `identity_status`, `procedures`, `extract`, `job`, `approvals`,
  `manifest_status`, `inbox`. `manifest` is write-only, so the reads stay truthful (HP-8).
- **`act` and `task` are write-capable.** They are free-form browser control, and some hosts allow every tool of
  a connected MCP server (HP-5). fleetd enforces scopes itself, through gate G (4.3).
- **The tool list is per token.** A token without the `approve` scope does not see `approve` at all.
- **Guidance lives in tool descriptions and skills.** No Hermes code path injects an MCP server's
  `instructions` into the prompt, and Hermes ignores `prompts/list_changed` (X-6), while tool-description
  changes propagate on `tools/list_changed`. Descriptions follow the box's form: what it does, "Do NOT use
  when", "Returns".
- **Screenshots come back as evidence refs, not inline images** (MCP `ImageContent` is re-sent on every later
  turn; HP 2.1).
- **Identity is an alias** of the **account** (the argument is still called `identity`). Agents never see or handle
  proxies, CDP URLs, cookies, node ids, persona fields, viewer URLs or viewer tickets.
- **No tool lets an agent clear a hold, close a takeover, approve, or open a viewer** (D17).

### 5.2 Envelope and the taint map

Every result has this shape. Expected refusals are normal results (`ok:false`), not MCP protocol errors; only a
genuine server fault is `isError:true` with `internal_error`.

```jsonc
{ "ok": true,
  "status": "done",          // done | running | needs_human | needs_approval | failed | cancelled | uncertain
  "job_id": "job_01H...",    // present whenever a job exists
  "data": { },               // tool-specific
  "error": null,             // or { code, message, retry:{retryable, after_s, same_idempotency_key},
                             //      next:[{tool, args}], details:{} }
  "cost": { "usd": 0.0012, "generative_calls": 1, "decider_calls": 1 },
  "fleet": { "request_id": "...", "idempotency_key": "...", "skill_min": "1.2.0" } }
```

**The taint map (S13-3).** Page text and stranger-written text are untrusted. Before this revision only `extract`
carried the marker. Now **every page-derived field path is listed in one taint map in the envelope code, and
returned as `{ "text": "...", "untrusted": true, "source_ref": "..." }`**, length-capped, with URLs defanged. When
an `output_schema` is given, no free-text `answer` is returned.

| Tool | Tainted paths |
|---|---|
| `extract` | `data.*` (every string leaf) |
| `act` | `observation`, `step.target.name` |
| `task` | `answer`, `structured.*` (string leaves), `steps[].observation` |
| `job` | `result.*`, `steps[].observation`, `obsidian_note` (page-derived lines only; the rest is fleet-written) |
| `inbox` | `items[].text`, `items[].author_display` |
| `approvals` | `subject.in_reply_to[].text`; the draft text is **not** tainted but is shown with `warnings[]` |

The marker is for the model and the reviewer. It is not a safety control by itself: it is why the approval card
shows which untrusted item the profile read before drafting (3.7).

### 5.3 The v0 tools

Shapes are JSON-Schema-like shorthand; `?` means optional. Every write tool takes optional `wait_s` (0-60,
default 20) and `idempotency_key`.

**1. `fleet_status`** (read-only; any valid token). What works now for this token.
```jsonc
args:   { "include"?: ["tools","providers","budget"],
          "skill_version"?: "0.2.0" }     // [extension, from hermes/README.md 3.5] the skill's own version, so fleetd can see a profile that has not rolled
result: { "fleet": {"version","status":"ok|degraded","notices":[...]},
          "skill": {"your_version","min_version","ok":true},
          "tools": [ {"name","available":true,"reason"?} ],
          "providers": {"system1":[{"id","ok"}], "reasoning":{"id","ok"}},
          "budget": {"day_usd_left","month_usd_left"},
          "identities": {"count","by_state":{"asleep":..,"awake":..}} }
```
Answers even when the skill is outdated (it is how an agent learns that).

**2. `identity_status`** (read-only). List or get identities bound to this token.
```jsonc
args:   { "identity"?: "acme-instagram", "include"?: ["lease","auth","caps","next"] }
result: { "identities": [ {
          "identity":"acme-instagram", "kind":"account",
          "state":"canary|asleep|waking|awake|sleeping|needs_reauth|checkpoint|restricted|migrating|quarantined|retired",
          "cooldown_until": null | "ts",
          "holds": [ {"reason","scope":"browser|api|all","since","effect_id"?,"conversation"?} ],
          "platforms":[ {"platform":"instagram","handle":"@acme",
                         "auth":{"state":"ok|login_wall|checkpoint|unknown","last_probe_at","auth_epoch"},
                         "channels":{"api":"ok|unavailable","browser":"allowed|not_allowed"} } ],
          "lease": null | {"holder_kind":"agent|human|system","purpose","expires_at"},
          "caps_remaining": {"publish_today","dm_today","spend_usd_today"},
          "next_scheduled": [ {"at","procedure"|"manifest_item_id","state"} ],
          "needs": [ "reauth" | "owner" | "reconcile" | "approval" ]    // ordered; "owner" carries reason text
        } ] }
```

**3. `identity_control`** (write). Creation is owner-only and is not here.
```jsonc
args:   { "identity", "action": "wake|sleep|reauth", "reason"?: string, "wait_s"?, "idempotency_key"? }
result: wake/sleep -> { "status":"running|done", "job_id" }
        reauth     -> { "ticket_id", "notified": ["<named person>"], "expires_at" }
                      // never a URL; the notifier delivers it to the named human (4.8)
errors: identity_busy, identity_held, needs_reauth, checkpoint, quarantined, infra_unavailable, scope_denied
```
`wake` on an awake identity succeeds idempotently. `takeover` is not an action here; it is an operator console
function (4.14). `sleep` waits for a running job's step boundary; use `cancel`
to stop a job.

**4. `procedures`** (read-only). Released procedures this token may run on an identity.
```jsonc
args:   { "identity"?, "platform"?, "kind"? }
result: { "procedures": [ {"name":"x.reply_to_mention","version":3,"digest8":"a1b2c3d4",
          "summary","kind":"api|browser|hybrid|read","effects":["reply"],
          "scopes_required":["dm"],"content_source":"manifest_item|approval",
          "fields_schema": { ...JSON Schema... } } ] }
```

**5. `run`** (write). Run a released procedure.
```jsonc
args:   { "identity", "procedure", "version"?: int|"digest8", "fields": {...},   // or "seeds": [ {...}, ... ] for a batch (4.13)
          "mode"?: "draft|execute"   // default draft
          "manifest_item_id"?, "approval_id"?,
          "budget"?: {"max_usd","max_steps"},
          "idempotency_key"            // required when the procedure has effects
        }
result: { "outcome":"ok|partial|failed",
          "steps":[ {"n","key","rung":"L0..L5","ok"} ],
          "effects":[ {"effect_id","kind","channel","state","receipt_summary"} ],
          "preview"?: {...}, "approval_request"?: {"approval_id"},
          "system1_share"?: 0.82,
          "batch"?: {"parent_job_id", "children": [ {"seed","verdict","job_id"} ], "leads"?: [...] } }
errors: not_released, scope_denied, refused, needs_approval, identity_busy, identity_held, needs_reauth,
        checkpoint, budget_exhausted, rate_limited, platform_limit, outcome_uncertain, step_failed,
        infra_unavailable, invalid_arguments
```

**6. `act`** (write). One scoped browser step on the ladder (L1-L3).
```jsonc
args:   { "identity",
          "instruction"?: "click the Next link"       // one atomic step; uses the ladder
          "action"?: {"op":"navigate|click|fill|press|select|scroll","target"?,"value"?,"url"?},  // skips models
          "mode"?: "read_only|guarded",               // default: read_only unless the token has publish/dm
          "max_rung"?: "L1|L2|L3" }
result: { "step": {"rung","method","target":{"role","name"},"decided_by":{...},"confidence"?,"latency_ms"},
          "page": {"url","title"}, "observation"?: string, "evidence": ["ev_..."] }
errors: needs_approval (the action is effect-like or not on the allow-list; details name the element role and
        name), refused (red-line kind or host, e.g. a Like button, x.com), needs_reauth, checkpoint, identity_busy,
        identity_held, step_failed, budget_exhausted, infra_unavailable, scope_denied
```
Text in `value` is copied verbatim. A step that would submit, post, send or delete returns
`needs_approval` unless it is tied to an approved manifest item or approval **and** the token has the scope. A
step that would like, follow, unfollow or repost returns `refused`: it is a red line, not a missing approval.
"Click Post" through `act` is not a publish bypass.

**7. `extract`** (read-only; long-running, so submit-then-poll).
```jsonc
args:   { "identity", "instruction", "schema": {...JSON Schema, <= 20 KB...}, "url"?,
          "via"?: "auto|http|browser",              // http only on kind=research identities
          "locator"?: string, "screenshot"?: false }
result: { "data": {...}, "source": {"via","rung","url"}, "truncated"?: false,
          "unverified_contact"?: [...] }               // every string leaf is {text, untrusted, source_ref} (5.2)
errors: goal_unmet, identity_busy, needs_reauth, checkpoint, infra_unavailable, budget_exhausted, invalid_arguments,
        scope_denied (reason target_not_public | host_not_allowed), refused (host_not_allowed)
```
**[extension, from `hermes/README.md` section 7 gap 16.]** `extract` also returns the goal verdict, evaluated in code and
never by a model, and per-field evidence, which lead route 2 needs (`docs/playbooks/lead-gen.md` 4.2 and 5 hold the
shape; it is not fixed here). On an `account` identity where L3-lite is closed (D18, Q-07) it may answer
`unsupported_on_identity` instead of climbing.

**8. `task`** (write). An open-ended goal on Browser-Use (L4). Read-mostly.
```jsonc
args:   { "identity", "goal", "start_url"?, "mode"?: "read_only|guarded",
          "max_steps"?: 8,   // cap 25
          "max_usd"?, "output_schema": {...}, "allowed_hosts": [...] }   // both REQUIRED (G11-12); enforced by gate R,
                                                                       // gate G and the Guard (4.5), not by Browser-Use
result: { "answer": string, "structured"?: {...}, "steps": n, "proposed_procedure_id"?: "..." }
errors: goal_unmet, needs_approval, refused, needs_reauth, checkpoint, identity_busy, budget_exhausted,
        step_failed, infra_unavailable, scope_denied
```

**9. `publish`** (write). A channel-routed effect. **There is no `text` argument for ready-to-send content:**
publishable content is a manifest item or an approved draft, never page text and never a bare model string.
```jsonc
args:   { "identity", "platform", "kind": "post|comment|reply|dm|private_reply|story|edit|delete",
          "conversation_id"?: string,   // REQUIRED for reply|dm|private_reply: issued by fleetd from `inbox`; comment_id for private_reply
          "target"?: string,            // for post|comment|edit|delete on the account's own objects only
          "manifest_item_id"?  |  "approval_id"?  |  "draft"?: {"text","media":["asset_id",...]},   // media ids come from the media store (3.13)
          "channel"?: "auto|api|browser",          // routing: section 8
          "hitl"?: "agent_clicks|human_clicks",    // browser channel only; default human_clicks; agent_clicks only if the owner set it (4.7)
          "idempotency_key" }                       // required
result: { "effect": {"effect_id","kind","channel","state","platform_ref"?,"url"?,"receipt"?} }
        or  needs_approval -> { "approval_id", "subject_summary", "expires_at" }
        or  draft_for_human -> { "approval_id" }      // LinkedIn, personal profiles: a person sends it (D2 table)
errors: refused (no_prior_contact | window_closed | opted_out | red_line_kind | no_consent_ref),
        needs_approval, content_not_approved, scope_denied, channel_unavailable, rate_limited, platform_limit,
        outcome_uncertain, identity_held, needs_reauth, checkpoint, budget_exhausted, infra_unavailable
```
A `draft` with no item or approval **creates an approval request** holding the exact content hash and answers
`needs_approval`, unless the kind is red-line (then `refused`: **approval requests cannot be created for red-line
kinds**). AI-drafted replies on X always need a per-action approval (the D2 rule on AI auto-replies). A pending
approval cap per token and per account applies (3.4).

**10. `job`** (read-only). Poll one job, or list history.
```jsonc
args:   { "job_id", "wait_s"?: 0-60,                     // long-poll
          "include"?: ["steps","effects","evidence","cost","obsidian_note","obsidian_notes","artifacts"] }   // the last two: [extension], batch parents only
   or   { "list": {"identity"?, "since"?, "status"?, "kind"?, "limit"?: <=100} }     // [extension]
result: { "job": {"job_id","kind","identity","status","stage":
             "queued|waking|running|waiting_human|waiting_approval|reconciling|sleeping|missed|done","created_at","finished_at"?},
          "steps"?, "effects"?, "evidence"?: [ {"ref","kind","url":"short-lived"} ],
          "cost"?, "obsidian_note"?: "markdown block for Runs/<job_id>.md", "result"?, "error"? }
```
List mode is what the profile's scheduled daily-note job reads (D15); it also shows manifest items that were
`skipped`, `missed` or `expired_unrun`, with the reason. Evidence refs resolve to short-lived URLs
only here.

**[extension, from `hermes/README.md` section 7 gaps 13 to 15; not yet reflected in the shapes above.]** Each list row
says who started the job (`started_by`: `agent`, `scheduler`, `system` or `human`), so a profile writes a run note
only for jobs it started (S02-12). For a batch parent, `include: ["obsidian_notes","artifacts"]` returns one block
per child with its vault-relative path (for example `Leads/<domain>.md`), an index block, and `leads.jsonl` and
`leads.csv` as evidence refs. fleetd renders them from its own records, in code; a spreadsheet cell that starts
with `=`, `+`, `-` or `@` is neutralized (S04-10). **The generator never inlines stranger text:** a quote goes to
an evidence file by opaque ref, or into a fence longer than any backtick run inside it with `[[`, `![[`, `%%`,
`<%`, `{{`, `$=` and HTML neutralized and a length cap, and a block that holds stranger text is tagged
`untrusted` so no later recall treats it as an instruction (S13-4; `hermes/README.md` 4.1).

**11. `cancel`** (write). `{ "job_id", "reason"? }`. A queued job is cancelled; a running job stops at its next
step boundary and frees the identity; an effect past its intent row **cannot** be cancelled: the ledger decides
and the result is `cancelled` or `uncertain`. Idempotent.

**12. `approvals`** (read-only). `{ "action": "list|get", "approval_id"?, "status"? }` -> pending approvals this
token may see, with the exact subject (target, account, content, audience, effects, `in_reply_to`, `prior_attempts`,
`warnings[]`, time left in the window).

**13. `approve`** (write; **[extension]** split out of D17's `approvals` so `readOnlyHint` stays truthful).
`{ "approval_id", "decision": "approve|reject", "note"?, "acknowledged_warnings"?: [...], "edit"?: {"text"} }`. An
edit re-hashes the subject and records both texts; a warning needs its own acknowledgement. Listed only for tokens with the `approve` scope,
which Hermes profile tokens do not hold by default. **No token holds `approve` together with `publish` or `dm`
on the same identity**: an agent that can answer its own approvals is no gate. Approvals are normally answered
by operators in the operator console.

**14. `feedback`** (write). `{ "job_id"?, "procedure"?, "kind": "wrong_result|site_changed|blocked|injection_suspected|red_line_request|proposal|other",
"note", "evidence_ref"?, "proposed_steps"? }` -> `{ "feedback_id", "effect": "recorded|priority_raised|step_quarantined" }`.
**Feedback raises the priority of a repair; it never quarantines a shared procedure by itself** (S06-3). The
change detector does that (4.16). Reports are rate-limited per token. A `site_changed` or `wrong_result` report
quarantines at most the reporting identity's own L1 entry. `blocked` can write a `site_incidents` row (3.15).
`injection_suspected` and `red_line_request` (a person asked for something on the red-line list; **[extension]**, G11-6) raise a notifier event. A repeatable success from `task` arrives as a `proposal`; a human
releases it. Proposals reach the reviewer as **untrusted diffs**.

**15. `manifest`** (write; scope `draft`). `{ "identity", "action": "propose|revise|withdraw", "campaign"?,
"items": [ {"kind","content"|"content_rules","media"?,"trigger","window","per_item_cap"?,"target_rule"} ],
"note"? }` -> `{ "manifest_id", "revision", "diff", "status":"draft" }`. The agent that writes the words can hand
them to the thing that publishes. Approval and revocation stay with operators (and a tenant's `client_approver`).
Rule kinds are the closed sets of 3.7; a free-form rule is `invalid_arguments`.

**16. `manifest_status`** (read-only). `{ "identity"?, "campaign"?, "manifest_id"?, "include"?: ["diff","items"] }`
-> manifests, revision diffs, items with their state (`pending|ready|running|done|blocked_until_ready|missed|
expired_unrun|skipped|cancelled`) and campaign status per platform.

**17. `inbox`** (read-only; scope `read`). `{ "identity", "since"?: cursor, "limit"?: <=50, "kind"?: [...] }` ->
`{ "items": [ {"conversation_id","kind","received_at","window_expires_at","text":{"text","untrusted":true,
"source_ref"},"author_display"?} ], "cursor" }`. Only conversations of accounts the token is bound to. Delivery
default: the profile polls this on a cron job (4.12).

That is **17** tools (D17's list with `approvals` split and the three added by the scenario revision), 8 of them
read-only. A Hermes profile token sees 16: `approve` is not listed for it.

### 5.4 Scope per tool

| Tool | `read` | `draft` | `publish` / `dm` | `approve` |
|---|---|---|---|---|
| `fleet_status`, `identity_status`, `procedures`, `job`, `approvals`, `manifest_status`, `inbox`, `feedback`, `cancel` (own jobs) | yes | yes | yes | yes |
| `manifest` | no | propose and revise | propose and revise | no |
| `identity_control` (wake, sleep, reauth) | yes | yes | yes | no |
| `extract` | yes | yes | yes | no |
| `act`, `task` | `read_only` only | `read_only`, plus fill without submit | `guarded`; effect-like needs authority | no |
| `run` | read-kind procedures | draft mode | execute mode with authority | no |
| `publish` | no | creates an approval request (never for a red-line kind) | yes, with item or approval; `reply`, `dm` and `private_reply` need `dm` and an eligible `conversation_id` | no |
| `approve` | no | no | **never together** | yes |

### 5.5 Errors are answers

Codes, the caller's move, and whether a retry is allowed. **No code ever tells a caller to retry an effect
under a new idempotency key.**

| Code | Meaning | Caller should | Retry |
|---|---|---|---|
| `identity_busy` | Another job or a human holds the lease (the box's "lane busy"). `details`: holder kind, purpose, expires_at | Wait with `job`, or do other work | yes, same key, after `after_s` |
| `identity_held` | A hold whose scope covers this call blocks it: an `uncertain` effect (browser or human channel: all scopes; API channel: only that conversation), failed upload, proxy mismatch, persona mismatch or owner hold. `details.reason`, `details.scope` | Stop. Read `identity_status` (`needs` says who clears it). Only `uncertain_effect` waits for reconciliation; `proxy_mismatch`, `persona_mismatch`, `upload_failed` and `owner_hold` are cleared by the owner or an operator (3.11). Tell the owner | no, until the hold clears |
| `needs_reauth` | The login is gone (`kind:"browser_login"`) or the API connection expired (`kind:"api_connection"`). **The caller never receives a viewer URL** (D14, 4.8): the fleet has already sent a ticket to the named person, or sends an OAuth link to the owner for an API connection. `details` carries `ticket_id` when one is out | Tell the owner and end the run. Do not call `identity_control reauth` again while a ticket is out. Never log in | after the human finishes |
| `checkpoint` | The platform asked for a CAPTCHA, 2FA or a "suspicious activity" review, or restricted the account. `details`: `cooldown_until`, and `effect_id` if an effect was open. Takes precedence over `outcome_uncertain` | Same. Never solve it. Effectful jobs do not resume on their own; they need a fresh owner approval | after the human finishes and the cool-down ends |
| `needs_approval` | The action needs a manifest item or approval. `details`: `approval_id`, subject summary | Tell the human what is waiting; poll `job` | resumes on approval |
| `outcome_uncertain` | An effect may or may not have happened. `details`: `effect_id`, state | **Do not call again.** Read `job` or `identity_status`; wait for reconciliation | no |
| `budget_exhausted` | A spend cap is spent (job, identity, client, provider or fleet). `details`: scope, cap, used | Stop and ask the owner | no |
| `scope_denied` | The token lacks the scope, or the target is not allowed to this token. `details.needed` or `details.reason`: `target_not_public`, `host_not_allowed`, `conversation_not_yours` | Use a tool you are scoped for | no |
| `refused` | **A red line or an eligibility rule that no scope, approval or manifest can unlock.** No approval request is created. `details.reason`: `red_line_kind`, `no_prior_contact`, `window_closed`, `opted_out`, `host_not_allowed`, `people_list` (a people-listing surface reached inside a session, 4.5 item 5), `no_consent_ref`. `error.next` names the allowed route (the API, `draft_for_human`, a consent channel) | Do not retry. Use the route named in `next` | **never** |
| `duplicate_content` **[proposed; CHARTER "Duplicate content", AGENTS, SOUL and the skills already use it]** | Gate R found that the text or media matches this account's history (a person's posts count), another account of the same client, or another client's. Not a red-line kind, but no manifest waives it. No approval request is created, and no effect row exists | Write a different version for this account in substance (the angle, the example, the opening), not by changing a word; then submit it as a new request. Do not post the original elsewhere | yes, with different content only |
| `infra_unavailable` | No node, browser host failing, guard down, database down | Back off | yes |
| `proxy_unavailable` | A wake-job error (a reason of `infra_unavailable`): the vendor's upstream is down, answers 407 or times out. **Not a hold.** Backoff, a per-vendor circuit breaker and one aggregated alert (S07-1) | Wait; do not wake again at once | yes, with backoff |
| `proxy_mismatch` | A wake-job error: the exit IP is not the pinned one. An incident-grade hold on the identity (browser scope) stands until the owner clears it (3.11) | Stop. Tell the owner | no |
| `not_released` | The procedure is unknown, quarantined, or its digest does not match | Use `procedures`; report with `feedback` | no |
| `invalid_arguments` | Schema failure | Fix the arguments | yes, fixed |
| `token_invalid` | Unknown, revoked, or a literal `${...}` bearer (an unset `${VAR}` is sent literally at some older Hermes pins) | Tell the owner | no |
| `skill_outdated` | Below the token's minimum skill version | Update the skill release | after update |
| `identity_unknown` | Not bound to this token (never distinguishes "absent" from "not yours") | Use `identity_status` | no |
| `quarantined` | The owner stopped the identity, or a procedure is quarantined. (A new identity is in `canary`, not `quarantined`; a candidate or predecessor in a move is `canary` or `migrating`.) | Stop | no |
| `identity_state` | The identity is not in a workable state (`canary`, `migrating`, `restricted`, `needs_reauth`, `checkpoint`). `details.state` | Wait; the job stays `queued` | after the state changes |
| `rate_limited` | A governor window, platform limit, **or an admission limit** (per-token or per-tenant requests, in-flight jobs or wakes); `details.reason`; `retry.after_s` | Wait | yes |
| `platform_limit` | A daily or per-account ceiling is spent | Stop for the day | no |
| `channel_unavailable` | Policy, missing connection or missing risk acceptance forbids this channel | Ask the owner | no |
| `content_not_approved` | Manifest item missing, revoked, out of window, or hash mismatch | Request an approval | no |
| `goal_unmet` | `extract` or `task` finished without satisfying the goal | Rephrase, or use `feedback` | maybe |
| `step_failed` | A step failed after the whole ladder; `details` carries rung history | Report with `feedback` | maybe |
| `cancelled` | Cancelled | | |
| `not_found` | Unknown job | | no |
| `internal_error` | A fleet fault (the only `isError:true`) | Back off | yes |

### 5.6 Hosts that cannot load plugins

On a host that cannot load plugins, the owner connects the fleet as an MCP server through that host's own integration route, over HTTPS. Guidance arrives as short prose guides that carry no executable authority **[pending Q-11]**. Plugins do not load there, so
the `obsidian_note` block in `job` results is how evidence reaches the vault. Never let one social account be
logged in both from the employee's in-container Chromium and from a fleet identity: that is two fingerprints
and two IPs. Fleet-side model spend is capped by the fleet's own
spend ledger.

## 6. Security model

### 6.1 What is being protected, and from whom

| Asset | Why it matters |
|---|---|
| Logged-in client sessions (cookies and storage in bundles) | Whoever holds one can act as the client's account. |
| Authority to publish, reply, DM, delete | Irreversible and public. |
| Platform API tokens, proxy credentials, model and System 1 keys | Spend, and the ability to impersonate the fleet. |
| Client content, including DMs | Goes to model providers unless routed otherwise **[pending Q-07]**. |

| Adversary | Path |
|---|---|
| Hostile page content | Posts, comments and DMs are written by strangers, and the agent is logged in (the box's "after a session login, a task can act as that login" applies per identity). |
| A prompt-injected or leaked Hermes profile | It holds a token and can call the tools. Profiles are not sandboxes; on a local terminal backend all profiles share one Unix user and a prompt-injected agent can plausibly read a sibling profile's `BROWSER_FLEET_TOKEN` (untested; hermes-packaging missed issue 5). |
| A network attacker | Steel's REST, CDP and viewer have **no authentication at all** and CORS `origin:true` (STE-8). |
| One client against another | A shared node shares the host-real canvas hash, core count and GPU (C-02). |
| Vendors | Proxy vendor, model providers, System 1 vendors, Browserbase, and the proprietary patched-kernel option (licence telemetry). |

### 6.2 Steel has no auth: isolation is the auth

- **One container per awake identity, on its own network, with no published ports.** Only the node agent
  reaches it. Steel's quick starts publish raw CDP on 9223 (nginx to Chromium 9222, bypassing Steel); the fleet
  never does.
- **No inter-container path.** A fresh holder-owned network namespace per wake, removed on sleep. No shared bridge. The
  node's DO Cloud Firewall admits the node agent's port only from the control-plane tag.
- **No raw access for Hermes, ever.** Profiles get the tools of section 5 (16 of 17). They never get a CDP URL, a
  Steel URL, a viewer URL or a ticket: the notifier delivers the ticket to a named person (4.8).
- **Steel is not trusted with secrets.** It never receives proxy credentials (it echoes the upstream URL
  over its open API); it gets `http://127.0.0.1:<f>` only (2.2). Provider keys never enter the container.

### 6.3 Network egress: proxy only, fail closed

- The host rule for each container namespace allows exactly **its vendor proxy `IP:port`**. Not the open
  internet, not the DigitalOcean metadata service (`169.254.169.254`; Chromium sends link-local and loopback
  direct, bypassing any proxy, so a page could otherwise reach it, steel dossier Q3), not the VPC, not other
  containers, not the host. Proxy hostnames are resolved by the node agent and the rule uses IP literals.
- The rule is the real control. The guard's DNS check is advisory because a proxied Chromium resolves at the
  proxy.
- WebRTC is pinned to `disable_non_proxied_udp` by Steel's launch flags (`cdp.service.ts:880-881`; source).
- **No direct fallback.** A dead upstream makes Steel fail closed (HTTPS `ERR_TUNNEL_CONNECTION_FAILED`, HTTP a
  594 page; hands-on). A mid-session exit-IP change stops the session (2.3).
- A `PROXY_INTERNAL_BYPASS` entry is not needed because every internal URL is loopback (C-08; unverified
  until a droplet run). `CHROME_ARGS=--proxy-bypass-list=<-loopback>` is an untested extra.

### 6.4 The guard on every browser

`Guard` (CDP `Fetch` interception on every tab, frame and worker, with `security.py`'s classifier) runs once per
awake browser, next to it, over local CDP (375 remote sockets would be fragile; scale-infra Q6). It is still
needed with a proxy, because loopback bypasses the proxy and Steel's open API listens on the container's own
loopback: the 2026-09-22 redirect exploit (a page that 302s to `127.0.0.1:3000/v1/sessions`) is exactly that
path. The deny list adds the fleet's own hostnames and droplet IPs. "Tools fail closed when the guard is
down" carries over unchanged. **Per-task navigation policy (S04-6, S13-8):** the Guard also enforces, per identity
and per task, the top-level and frame navigation rules, the `robots.txt` check on every top-level navigation of a
`research` identity, and the host rules of 4.5; it counts refusals (6.7 item 7). Deploy gates run on every Steel digest and `steel-profile` version: the
33 shared scope vectors and the shield-check attacks, **11 attacks plus 7 positive/behavioural controls**,
ported off jev-automation's Playwright executor to a CDP client (C-25). Per-identity CPU of the guard is
**[to measure]**.

### 6.5 The viewer

- A **ticket** opens one identity, for one purpose, once, for minutes, and is exchanged **once** for a viewer
  session that survives a page reload (4.8). The broker proxies only the viewer routes. Everything else Steel
  exposes (`/v1/sessions`, `/v1/logs`, files, scrape) returns 404 from the broker.
- **Human authentication (AQ-1) is a blocking item of M2.** A ticket must never be enough on its own, and **the
  ticket and URL never pass through an agent's context**: the notifier delivers them to the named person and the
  tool result carries only `{ticket_id, notified, expires_at}` (S01-3, S13-10). Steel's debug URLs have no
  authentication (`research/corpus/steel/`), so the broker's sign-in is the only control. Design default
  **[pending AQ-1]**: operator accounts with passkeys plus a `tenant_viewer` role limited to its own tenant
  (6.13). Alternatives for Justin: operator accounts behind the company's identity provider, or a one-time code
  delivered out of band. The design requires the second factor; the default is a recommendation, not a decision.
- **Domain policy for a human session (G12-14).** The URL bar allows the identity's platform hosts and their login
  providers. The rest is blocked and logged, so no other account's cookies enter the bundle.
- The viewer is unauthenticated upstream and keystrokes pass through fleetd's infrastructure. Viewer access is
  logged (counts only, no payload; steel.md section 7.3). Untested input classes are an M1 gate (4.8).
  `viewer_close` runs on every fencing-token change (3.5).
- **The viewer is not offered for Browserbase-homed identities** (their Live View URL is a bearer capability;
  `docs/infra/steel-profile.md` section 9.5): screenshots are the substitute.

### 6.6 Tokens, scopes, and client isolation

- **Token handling.** Opaque, stored as an HMAC, rotated by the provisioner (rewrite `.env`, the next connect
  uses it), revocable at once. A bearer that looks like `${...}` is rejected (HP-1). `BROWSER_FLEET_TOKEN` is
  never exported host-wide; a multiplexed host's launch profile gets none; the `X-Hermes-Profile` header is a
  label, not authentication (HP-9).
- **Least privilege is the blast-radius limit.** A leaked token can only do what its bindings allow: scopes
  per identity, daily caps, spend caps. A leaked `read` token cannot publish.
- **Server-side enforcement is mandatory.** Some hosts allow every tool of a connected
  server; Hermes' `trust: untrusted` would prompt a human on every write and fail closed in cron. So fleetd
  enforces scope, approvals, rates and spend for every call. A root-owned `/etc/hermes/config.yaml` can pin the
  `browser_fleet` URL so an agent cannot redirect its own fleet entry; keep the token out of it (the
  `${VAR}` expansion there is undocumented behaviour; HP-7).
- **Fleet hosts** use a sandboxed terminal backend or per-profile Unix users.
- **Client isolation.**
  - Every table row carries `tenant_id`; every query is tenant-scoped, backed by Postgres row-level
    security **[extension]**.
  - Spaces prefixes, data keys and evidence are per tenant; operators have tenant-scoped roles.
  - **Nodes:** identities of different clients do not share a node until per-identity hardware values exist
    **[pending Q-13, O-01]**. The unit is the tenant, simultaneous and sequential: between two tenants a node is
    destroyed, or its volumes, tmpfs and Docker image layers that held client data are deleted (S09-12).
    Whether this isolation buys anything is a measured fork (7.7).
  - `/decide` and the model shim never batch across tenants; prompts and responses are logged per tenant.
  - The L1 cache is per tenant by default (3.9).
  - Spend caps are per tenant, per identity, per provider and fleet-wide.

### 6.7 Hostile content, the policy gate and the effect gate

1. **Untrusted text is data.** Every page-derived string in every result is `{text, untrusted:true, source_ref}`,
   length-capped, URLs defanged, from one taint map (5.2). Page text never becomes publishable content: content
   comes from a manifest item or an approved draft (D13). **What code enforces:** no raw-text argument, a hash
   match, the exact text shown to the approver. **What only the human catches:** a draft that copies an
   attacker's sentence, because fleetd cannot tell. To help the human, the approval carries code-computed
   `warnings[]` (a link off the tenant's allow-list, a URL shortener, overlap with strings returned as untrusted
   to this token, a first link to this destination), each needing its own acknowledgement, and it shows which
   untrusted item the profile read before drafting (3.7).
2. **Policy gate R runs on every call** (4.3): red-line effect kinds, host rules, recipient eligibility,
   duplicate content, URL classification. Red lines are refused in code, not by prompt (Charter).
3. **Options are built by code,** from the snapshot, with a `none` choice. A decider chooses among them. A
   decider is not a safety control: adversarial content moves answers.
4. **Browser-Use is read-mostly.** `upload_file`, `save_as_pdf` and `evaluate` are excluded; effect-like steps
   hit gate G through the step callback. `allowed_domains` (Browser-Use) and `setDomainPolicy` (Stagehand,
   bypassed by service-worker fetches and WebSockets, #2945) are not boundaries; the table in 4.5 says what is.
5. **Gate G** is deterministic: blocker and login deny-list, scope, authority, first-post gate, governor, a
   content-hash check before submit, the intent row, an independent read-back. Its allow-list default fails
   closed; its classifier backstop fails open on unlabeled icon buttons **[to measure]** (4.3).
6. **Credentials are never typed by agents** (4.3), and no tool returns a cookie, a credential, a viewer URL or a
   ticket.
7. **Guard refusals are counted.** After N refusals in one job the job is cancelled, the identity is held
   read-only, `feedback kind=injection_suspected` is written and the notifier fires (4.5). Feedback proposals
   reach the reviewer as untrusted diffs.
8. **Flood and cost amplification.** Per-author and per-thread ingestion limits, dedupe, a cap on pending
   approvals, a billed-inbound budget with a drop policy, and a suspension of the token's `publish`/`dm` scope
   when more than K same-shape approvals arrive (3.4, 3.12, 4.12).
9. **Uploads.** Browser-Use uploads need a path on the browser host and the model may name any absolute remote
   path, so `upload_file` is excluded. Stagehand `setInputFiles` reads files in the worker (50 MiB cap;
   proven only to 26 bytes). Media for posts goes through the Steel files API and a fleet-built
   `DOM.setFileInputFiles` path, **[unverified]**. The media store (3.13) serves API-channel media only from the
   verified domain on short-lived URLs.

### 6.8 Secrets custody

| Secret | Held by | Delivered to | Notes |
|---|---|---|---|
| Hermes profile token | The profile's `.env`; HMAC in `tokens` | n/a | Scoped; rotatable |
| Platform OAuth and system-user tokens | `connections` (`*_enc`) | Only the connector code in fleetd | Never reach nodes, browsers or Hermes |
| Proxy credentials | Secret store; `proxies.creds_ref` | The node agent, over mTLS at wake, onto a tmpfs file (mode 0400) read by the forwarder | Never in Steel's environment or API |
| Model and System 1 keys | fleetd's `decide` and `model` processes | nobody else | Workers use job-scoped credentials |
| State bundles and journals | Spaces, encrypted | The node, decrypted into a node-local directory for one wake | **Chromium's cookie store uses a fixed `v10` key under `--password-store=basic`** (`cdp.service.ts:898`), so the profile directory itself is not protected; the bundle layer is (O-09) |
| Data key (DEK) per identity; key-encryption key (KEK) | fleetd's secret store | The DEK, unwrapped, to one node for one wake | DigitalOcean has no managed KMS (unverified). **KEK custody is open [pending O-09]:** a key on the control droplet via systemd credentials, a separate vault, or an external KMS. |
| Viewer tickets and sessions | Hashed | The named human, by the notifier only | A ticket is exchanged once; the session is closed on a token change |

Offboarding a client: stop and retire the identity, delete bundle generations, journals, evidence and
connections by retention policy, rewrap or destroy the DEK, revoke tokens, release the proxy. Browserbase
Contexts cannot be exported and a suspension voids all of them (BB-3).

### 6.9 Chromium inside the container

Steel's Chromium runs as **root with `--no-sandbox --disable-setuid-sandbox --no-zygote`** and with site
isolation disabled, on arbitrary logged-in pages. **[pending Q-08]:** run non-root with the sandbox back on (work,
may need capabilities or a seccomp profile for user namespaces), or accept the risk in writing. Compensating
controls that hold either way: one identity per container and per network; no secret in the container other than
that identity's own cookies; capabilities dropped; read-only root filesystem where Steel allows; tmpfs for
scratch; memory, CPU and pids limits; no Docker socket; the egress rule; the guard.

### 6.10 Data handling

Logged-in client pages, DMs included, go as text or screenshots to OpenRouter-routed providers (GLM) and to up
to four System 1 vendors. 29 GLM endpoints are zero-data-retention listed; the bench's main provider is not,
and one ZDR provider failed schema enforcement every time. A tenant flag `zdr_required` selects the provider
allowlist for that tenant's calls, and requiring it invalidates the current bench numbers
**[pending Q-07]**. Browserbase-homed identities send their credentialed proxy to Browserbase. Secrets and
tokens are redacted from logs; keys are never printed or committed.

### 6.11 Supply chain and upgrades

Steel by digest (`:latest` tracks `main`); Stagehand SDK and extension pinned together (the runtime
compatibility check rejects mismatches); Browser-Use with a version self-check; Hermes one commit per host.
Upstream Steel fixes (#348, #375, #235) are outsider PRs and requests with no maintainer owner, so the fleet
carries its own takeover guard, isolation-as-auth, profile handling and persona work (C-24). Any new pin or
persona goes through the canary rule before touching a client (O-13). `security.py` is copied at a pinned box
commit with a test that fails if it drifts.

### 6.12 Repository exposure

`box-kit`'s export publishes the whole box repository publicly and its unanchored excludes would strip
`fleet/**/skills` while publishing the rest. Nothing under `fleet/` merges to `main` until `fleet/` is excluded
precisely or moved to a private repo **[pending Q-09]**. A separate exposure question about a public companion repo is tracked privately **[pending Q-10]**. Client names, handles and procedures never go in the public forks.

### 6.13 Operators and roles **[extension]**

The operator console is a human surface (C1). Roles resolve N-5 ("owner" was undefined) and S01-3 (the human who
logs in is often the client's own staff).

| Role | May | May not |
|---|---|---|
| `owner` (Justin's business) | Everything an operator can, plus `identity create`, cutover, retire, `hold_clear` for `proxy_mismatch`, risk acceptances, kill switches | |
| `operator` | Approve manifests, campaigns and actions; take over (all three purposes); mark an uncertain effect found or absent; quarantine; see the notification queue | Create identities, clear `proxy_mismatch`, accept risk |
| `reviewer` | Review and accept outcomes for a procedure version (3.7); review feedback proposals as untrusted diffs | Approve effects |
| `tenant_viewer` | Open a viewer for identities of **its own tenant only**, under its sign-in | Anything else; see another tenant |
| `client_approver` | Give client sign-off on content for its own tenant's campaigns (S02-3) | Approve technical sets; take over |

- **Authentication** is passkeys by default **[pending AQ-1]**. Hermes profile tokens never hold operator roles.
  The `approve` scope is never held together with `publish` or `dm` on the same account (3.4).
- **Separation of duties.** The person who proposes a manifest (via a profile token) cannot approve it. A
  `client_approver` sign-off is recorded next to the operator's approval, not instead of it.
- **Every console action is audited** (operator, time, target, note).


## 7. DigitalOcean deployment topology

Everything here is a plan. Droplets are amd64; **all hands-on numbers so far are arm64 Docker or
local Chrome and are re-measured on a droplet in M1** (O-17). The Steel image, the cross-host and x86 tarball
restore, wake latency and social-site memory are all unmeasured on amd64.

### 7.1 Sizing as formulas over P

The driver is **P, the peak number of simultaneously awake browsers**, not the number of identities.

```
 B = identities that need a browser at all        (set in section 8 for each Q-01 answer)
 h = active browser hours per day per such identity
 P = B x h / 16 x 2          16 h active window and 2x peak factor are unsourced estimates
 slots per node = min( (RAM - 2 GiB) / 1.85 GiB , vCPU / 0.6 )      planning estimate
 N (nodes)      = ceil( P / slots ) + spare                          spare: +1 below 20 nodes, 5% above
 N with one client per node [pending Q-13] = sum over clients c of ceil( P_c / slots ) + spare
```

- Planning slot: 1.5 GiB for Chromium plus 0.35 GiB for the runtime, 0.6 vCPU, with 2 GiB per node reserved
  for the OS, Docker, node agent and guard (all estimates; the 2 GiB reserve was never measured). On
  `s-8vcpu-16gb` ($96/month bundled, 672 h cap) that is **7 slots**. Measured on light test pages:
  0.70-0.85 GiB peak per container, which would fit about 11; social SPAs are heavier and unmeasured, so the
  first live canary corrects this first (SCA-5).
- The all-browser upper bound (every identity awake 1 h or 3 h a day) is in `research/dossiers/scale-infra.md`
  Q4 and DECISIONS D12; its static node counts are **2, 3, 3, 7, 19, 57** for 30x1, 30x3, 100x1, 100x3, 1,000x1
  and 1,000x3. Costs are in D12 (all estimates). They omit X API fees, the 31 s flush hold per sleep, guard
  CPU and the one-client-per-node rule, and credit a 40% replay share to a cache that does not yet exist.
  **B is a second axis (D12):** only accounts with a browser identity need a node, and an API-only account owns
  neither an IP nor a slot. The share `f = B / accounts` is unmeasured; do not quote a single total (S09-8).
- **One client per node** (Q-13 = yes) can dominate at small clients: a client with five identities that
  would otherwise fit anywhere still occupies a node's worth of capacity. The formula's last line is the
  honest count.
- Cloud-vendor alternatives (Steel Cloud, Browserbase) and their rows are in D12; Steel Cloud's stealth browser
  is Enterprise-only and its terms bar using it to violate sites' terms.

### 7.2 Building blocks

| Block | Choice | Source |
|---|---|---|
| Control droplets | `s-4vcpu-8gb` ($48) | scale-infra Q4 control row |
| Browser nodes | `s-8vcpu-16gb` ($96, 7 slots, 12 regions). `s-8vcpu-32gb-amd` ($168, 13 slots, CPU-bound) is cheaper per slot ($12.9 vs $13.7); benchmark shared "Basic" CPUs against `c-` and `g-` sizes before committing | scale-infra Q1 table |
| Node image | A droplet snapshot ($0.06/GB-month) with Docker, the pinned Steel image, the wrapper, the node agent and the host firewall rules, so a node does not pull the image at wake time | scale-infra Q2 |
| Database | Postgres: source of truth, backed up. Managed Postgres 2 GiB $30.45, 4 GiB $60.90 (standby price unlisted) | scale-infra SCA-12 |
| Object store | Spaces ($5 includes 250 GiB and 1 TiB out; $0.02/GiB stored; cold $0.007/GiB). Lifecycle rules for evidence retention are unchecked | SCA-12 |
| Load balancer | DO Load Balancer ($12) at the largest scale | SCA-12 |
| Billing facts | Per second, 60 s / $0.01 minimum; powered-off droplets still bill; the $96 price and 672 h cap are for bundled plans only (v5 droplets are $0.1953/h for the same shape with no cap, where available); **at most 10 droplets created at once**; the account droplet limit was never checked and must be raised early | SCA-12 |
| Node enrollment | A one-time enrollment token is exchanged for a revocable node credential (the edge-enrollment pattern of an earlier private SDR harness) and an mTLS certificate **[extension]** | existing-assets Q3 |
| Placer filter (W4) | infra home; **tenant** (the unit of isolation, below); node class (7.7); **region and proxy reachability** (node-to-proxy-to-platform latency is unmodelled until measured; each wake records node-to-proxy latency; region choice for a multi-country client is open, `docs/identity/identity-and-proxies.md` section 9 item 8); free slots; the per-node concurrent-wake cap (7.8); then `last_node_id` and least loaded **[extension]** | S09-15, S09-3 |
| Unit of isolation | **The tenant**, both at the same time and in sequence. Two tenants never share a node at once. Reusing a long-lived node for a second tenant counts as sharing unless it is scrubbed: destroy the node, or delete the volumes, tmpfs and Docker image layers that held the first tenant's data. Scrubbing runs between tenants and is logged **[extension]** | S09-12 |

### 7.3 Network and firewall (all scales)

```
  Hermes hosts / Jev trial ----HTTPS 443----> [ LB or Caddy ] --> fleetd api  (agent door: MCP + REST)
  Operators (humans) -------HTTPS 443----> [ same edge, other hostname ] --> operator console + viewer broker
                                                    |
        VPC (private)  ---------------------------- | -----------------------------------
        control tag:  fleetd api | scheduler | reconciler | decide | model | Postgres (managed or local)
                          |  mTLS, VPC only (node agent port; internal API)
        node tag:     node agent -> per-identity netns -> vendor proxy IP:port ONLY   (host nftables)
                          |
        outbound:     control -> platform APIs, OpenRouter, System 1 vendors, Spaces
                      node host -> Spaces (bundles), control (VPC)
```

- DO Cloud Firewalls are tag-based: the node agent port accepts only from the control tag; nodes accept no
  inbound from the internet; the control edge accepts 443 only. SSH goes through a bastion tag, not the
  internet.
- **Container egress is not a Cloud Firewall matter.** It is enforced on the node by host nftables in the
  `DOCKER-USER` chain, per namespace (6.3).
- The Jev trial requires an HTTPS fleet URL.
- Droplet-to-droplet traffic uses the VPC; outbound transfer is pooled per team and the quoted allowance makes
  egress about $0 (scale-infra Q4), but the proxy vendors' GB charges are separate.

### 7.4 The three topologies

**30 identities (the first live canary).**

| Piece | Setting |
|---|---|
| Control | One `s-4vcpu-8gb` running Caddy, fleetd (api, scheduler, reconciler, decide, model) and Postgres, with nightly dumps and WAL archive to Spaces. The alternative is Managed Postgres 1 GiB at $15.15 (scale-infra SCA-12). Postgres holds the lease table and the effect history, so the backup is not optional. |
| Nodes | A **static** pool sized by the formula, 2-3 `s-8vcpu-16gb` for the all-browser upper bound; one region. Autoscaling saves little at this size. |
| Jobs | Postgres queue; no Temporal. |
| Notes | A single point of failure at the control droplet is accepted; recovery is rebuild from the snapshot and the Postgres backup. Operator console on the same host. |

**100 identities.**

| Piece | Setting |
|---|---|
| Control | One or two `s-4vcpu-8gb` for fleetd; **Managed Postgres 2 GiB** ($30.45) with point-in-time backups; Spaces. A second fleetd instance is optional (the scheduler and reconciler elect a leader with a Postgres advisory lock). |
| Nodes | 3-7 `s-8vcpu-16gb` for the all-browser upper bound, **created from the snapshot on the schedule and destroyed after** (per-second billing). Pre-wake lead includes node creation (60 s minimum, snapshot boot). |
| Isolation | If Q-13 = yes, node pools are **per tenant** (the isolation unit; 7.2), not per client group. |
| Jobs | Postgres queue. Temporal only if durable workflows have earned their keep. |
| Notes | Raise the droplet limit now. Add a metrics and dashboard droplet. |

**1,000 identities.**

| Piece | Setting |
|---|---|
| Control | At least two fleetd `api` instances behind the DO Load Balancer; `scheduler` and `reconciler` as leader-elected singletons; `decide` and `model` on their own droplets so provider rate limits and slow providers cannot starve the doors. A **shared limiter store** is needed once `decide` has more than one instance: a small managed key-value store or Postgres-backed counters (choice deferred). Managed Postgres 4 GiB with a standby. |
| Nodes | 19 to 57 `s-8vcpu-16gb` as the all-browser upper bound; the real count follows P. Pools per tenant (Q-13), node class (7.7) and region. Created in batches of at most 10, sized ahead by the capacity planner (7.8). Revisit Nomad (BUSL; internal use is fine) or DOKS only if the custom placer outgrows about 60 nodes. |
| Jobs | Postgres queue; Temporal on Postgres with `REJECT_DUPLICATE` and namespace retention if per-identity durable workflows pay off. |
| Hermes side | 1,000 profiles on one multiplexing gateway is unmeasured (about 1,000 MCP connections, startup time, memory). Shard profiles across Hermes hosts; `lazy: true` helps only from the second boot. |
| Notes | KEK custody must be decided (O-09). Evidence retention lifecycle rules checked. Proxy and model lines are 60-75% of the all-browser bill at this size (D12). |

### 7.5 Browserbase-homed identities in the topology

They need no node slot and no bundle. A small pool of **worker hosts** runs the executor and guard against the
remote `connectUrl`. Capacity is the vendor's concurrency (Developer 25, Startup 100, Scale 250+; vendor
claim) and per-project keys give coarse isolation, for example per client group. No sharding across
Browserbase accounts: the ToS bars "creating multiple accounts to avoid restrictions" (D11).

### 7.6 What this section leaves open

The amd64 re-run; the account droplet limit; shared-CPU noise (3 concurrent browsers saturated their CPU
caps in the spike, so seven simultaneous wakes on 8 shared vCPUs will contend); Spaces lifecycle rules; the
Postgres standby price; the Guard's CPU; the real B per Q-01 answer (section 8); the node-creation time (never
measured); the host-real values across same-size droplets (7.7); and the `http_only` research start-up time
(4.13).

### 7.7 Node classes, and the one-client-per-node fork **[extension]**

D3 and Q-13 assume that canvas hash, core count and GPU string are host-real and differ between nodes. Nobody has
measured whether they differ across **droplets of the same size built from one snapshot**
(`docs/engines/steel.md` section 8.5). On the same image with software rendering (SwiftShader) they plausibly
match (inference, not a measurement). Two outcomes (S09-1):

| Outcome | What it means | What changes |
|---|---|---|
| **Equal across droplets** | Every node looks identical. Linkability exists on every node, so one client per node is cost with no benefit. | Reopen Q-13 and D3. Options: per-identity hardware values (Q-04), or an accepted, written linkability risk. The placer drops the per-tenant partition for fingerprint reasons (the data-isolation unit of 7.2 stays) |
| **Different across droplets** | An identity that wakes on another node changes hardware wake to wake, which is the drift D3 forbids, and "wake on any node" with autoscale-and-destroy cannot hold. | Pin each identity to a **node class** (size, image, CPU model). Failover stays inside the class (S08-8). The autoscaler creates nodes by class. `nodes.node_class` and `identities.node_class` are placer inputs |

**Measure first (S09-2), in M1:** read the host-real values on at least two same-size droplets from one snapshot
and on two sizes. Until then the default (one tenant per node, no pinning to a class) stands, and **nothing
else in this file depends on the branch** except the placer filter and the autoscaler.

### 7.8 Capacity planner, wake smoothing and fair share of node creation **[extension]**

Schedules are known in advance, so capacity is planned, not reacted to (S09-3).

- **Planner.** From manifest windows and schedules it computes the **awake count over time** and reserves nodes
  ahead in batches of at most 10 creations (`ceil(new nodes / 10)` creation times before the first wake that
  needs them; the creation time is unmeasured). The 2x peak factor and the 16 h window of 7.1 are unsourced, and a
  clustered morning breaks both, so the planner works from the actual windows.
- **Per-node concurrent-wake cap.** 3 browsers already saturate a node's CPU (SCV SCA-5). The cap value comes from
  M1; the placer never starts more wakes than the cap on one node.
- **Pre-wake lead** is a function of wake p95, bundle size and download time, queue depth and the number of new
  nodes (4.11).
- **Window-aware smoothing, for capacity only.** Inside each approved window an item runs at a per-account offset.
  The benefit of spreading against detection is unverified. An item never moves outside its approved window.
- **Weighted fair share of node creation per tenant,** so one client's morning does not delay the rest.
- **Gate.** MILESTONES G5.7 is a scale-tier gate with no number today; the planner's headroom and the wake cap are
  the numbers it needs.

## 8. BRANCH POINT: Q-01, API-first or browser-first for client social

**Q-01 [Justin]:** for client social accounts, should the default channel be the official API, with the browser
fleet used for login, open-web lead generation and the narrow no-API set (DECISIONS D2, the recommended
answer), or should the browser carry routine posting, replying and messaging? And which clients accept, in
writing, that Meta, X, LinkedIn and TikTok terms can then lead to suspension?

This section is written so that **the answer changes this section and nothing else**. Sections 1-7 and 9-10
describe both channels as available mechanisms; this section is the only place that says which one is the
default, which one is the exception, and what that does to sizing and milestones. Until Justin answers, build
and plan on the recommended default (A below).

### 8.1 What does not change under either answer

All seventeen tools, all components, the data model, the lease and fencing design, the ladder and gate G, the
effect ledger, the extract, task, reauth and sleep flows, the security model and the topology shape. Both
publish flows (4.6 API, 4.7 browser) exist either way: the browser flow is needed for the no-API set even when
the API is the default. The never-built list (cold or outbound DMs, automated likes and follows, identical
posts across client accounts, AI auto-replies on X without X's approval, fake accounts, ban evasion, scraping
platforms for lead data, competitive benchmarking on X) holds under **both** answers: browser-first does not
unlock any of it.

### 8.2 The single switch

Channel choice is stored in exactly one place, `platform_accounts.channel_policy` (3.2), and read by exactly one
piece of code, the channel router inside `publish` and `run`:

```jsonc
channel_policy = {
  "default":        "api" | "browser",          // used when publish.channel = "auto"
  "by_kind":        { "post":"api", "comment":"api", "reply":"api", "dm":"api", "story":"browser" },
  "browser_allowed":["story","edit"],           // effect kinds the owner permits on the browser channel;
                                                //   always a subset of the rows of D2's allowed-uses table
  "browser_hitl":   "per_action" | "manifest",  // how browser-channel effects are authorized
  "click_mode":     "human_clicks" | "agent_clicks",   // default human_clicks (G12-15); agent_clicks only by explicit owner setting
  "bot_disclosure": { "<market>": "required" | "not_required" },   // S03-5, pending AQ-8
  "risk_acceptance_id": "ra_..."                // required when any browser kind is allowed
}
```

Router rule: `channel = request.channel`, or for `auto`, `by_kind[kind]`, else `default`. `browser` is refused
(`channel_unavailable`) unless the kind is in `browser_allowed`, the risk acceptance is valid and the
authorization rule is satisfied. `api` is refused unless the connection is healthy and the connector
supports the kind. A per-client or mixed answer is rows in this table, not code.

### 8.3 Answer A: API-first (recommended; D2)

| Aspect | Setting under A |
|---|---|
| Default policy | `default:"api"`. Publishing, comment moderation, inbound-DM replies and analytics use the connectors. `browser_allowed` holds only the rows of D2's table that allow a browser identity: **Facebook Groups** (acting account a Page or business account until AQ-10 is answered) and **UI-only features** of a Page, professional or business account. It does **not** hold LinkedIn (connection requests, DMs and InMail get `draft_for_human`), Facebook personal profiles (`draft_for_human`; terms bar giving others access) or Instagram personal accounts (convert to professional, free; until then `draft_for_human`) (S01-10, G11-11). `browser_hitl:"per_action"`, `click_mode:"human_clicks"`. |
| Who needs a browser (B in 7.1) | Human login and re-auth sessions (short), `research` identities for open-web lead generation, visual QA of clients' own public pages, and the no-API set. Most identities need few or no browser hours. **The share has not been estimated by anyone** (C-17), so P is unmeasured; it is bounded above by the all-browser numbers in 7.1. *Illustration, an assumption and not a forecast:* if 10 of 100 identities needed 1 h a day, `P = 10 x 1 / 16 x 2` is about 1.25, so 2 nodes. |
| Critical path | **Developer-app approvals, which are milestone dependencies with external timelines the fleet cannot control** [pending Q-06]: Meta App Review, Advanced Access and Business Verification; the TikTok Accounts API form (mandatory since 2026-03-20), with the audit risk that rejects internal "upload for accounts you manage" tools; LinkedIn Community Management (vetted; version 202510 sunsets 2026-10-15); an X pay-per-use app with prepaid credits. Until a platform's approval lands, its API channel is `unavailable`, and under A its browser channel stays off, so that platform waits. |
| Governor | Limits read from live headers; per-account caps bind first; X fees reserved per effect. |
| Receipts | API read-back: the strongest receipt (it is the one that has a verified pattern). |
| Health | API-token health checks; no scripted keep-warm login probes on Meta (the dormancy trigger covers empty accounts; O-12). |
| Human load | Low: approvals only for the no-API set; login events; the `draft_for_human` sends. |
| Anti-detect pressure | Low. D9 continuity is enough; Q-02 is not blocking. |
| M1 gates that block social work | Viewer login classes; for the no-API set also the composer and read-back items below. |

### 8.4 Answer B: browser-first

| Aspect | Setting under B |
|---|---|
| Default policy | For clients with a valid written risk acceptance: `default:"browser"` and `browser_allowed` covering post, comment, reply and dm. The API stays the channel wherever a connection exists and the client has not accepted the risk. Per client and platform, not global. |
| Authorization | D2 says browser-channel actions are each human-approved, at low volume (D2 table row 10, **[pending Q-01]**). Per-action approval of every routine post does not scale to 100-1,000 accounts. Whether a manifest may authorize browser effects at all is a Q-01 sub-question. If Justin says yes, under B the owner chooses `browser_hitl:"manifest"` for accepted clients, `click_mode` stays `human_clicks` unless the owner sets otherwise, the first-post gate still needs a person, and X and LinkedIn stay refused: an approved campaign manifest authorizes scheduled items inside its window and caps, and **step 2 of 4.7 is relaxed accordingly**. Everything else in 4.7 holds: pre-submit content-hash check, intent row, separate read-back, uncertain-hold. Per-action approval remains the fallback for anything outside the manifest. |
| Who needs a browser (B in 7.1) | Every identity on a browser-default platform. The all-browser upper bound in 7.1 becomes the planning number: static node counts **2, 3, 3, 7, 19, 57** for 30x1, 30x3, 100x1, 100x3, 1,000x1, 1,000x3. Proxies and models are 60-75% of the bill at 1,000 (D12). |
| Terms exposure | X: non-API automation leads to permanent suspension. Meta: its Community Guidelines require an authorized route for scripted account use, and its terms bar circumventing technological measures. LinkedIn bans bots that post, comment or message. TikTok bans automation tools and sanctions its Accounts API for posting. The suspension lands on the **client's** account. This is Justin's and the client's risk to accept in writing, not an engineering item. |
| Governor | There are no official numbers for safe action cadence on any platform; published ceilings are ceilings. The owner sets pacing; checkpoint telemetry is the feedback loop. Expect a higher checkpoint rate and more reauth work (operator load). |
| Receipts | **DOM or thread read-back is a hypothesis** for Meta, X and TikTok. Its false-negative rate sets the reconciliation load. It must be measured before volume. |
| Health | Login probes at wake (already part of wake). Still no scripted keep-warm probe on Meta. |
| Anti-detect pressure | High. D9 and Q-02 become decisive. Before any client: measure the `isAutomatedWithCDP` trip, choose the executor per site class (O-02), decide the persona mode (O-01, Q-03, Q-04), and apply the measured mitigation. |
| M1 gates that now block | Viewer login classes (special keys, IME, passkeys, native dialogs, HTTP auth, file pickers); composer `fill` on real Lexical and Draft.js editors; the effect-classifier miss rate; read-back receipt rates on real feeds; guard plus extension interaction; amd64 memory on social SPAs. |
| System-1 share | Computed over social procedures; the 90% figure is a hypothesis (O-15). Research estimate, unverified: at least 90% plausible for repetitive posting, lower for inbox and replies, well below for lead generation. |
| API approvals | Off the critical path for accepted clients, still pursued for the rest. |

### 8.5 The edit list when Q-01 is answered

1. The default `channel_policy` rows (8.2) per client and platform, and the `risk_acceptances` they point at.
2. Step 2 of 4.7 (`browser_hitl`) and step 6 (`click_mode`), and rows 2 and 10 of D2's table.
3. B and P in 7.1, and therefore node counts in 7.4.
4. Milestone order of connectors (Q-06) versus browser-channel hardening (the M1 gates in 8.4).
5. The content of the `fleet-social-ops` and `fleet-router` skills (pacing, caps, approval states, proof of
   posting).
6. Which M1 gates block the first client.

Nothing else in the document changes.

## 9. Deviations from, and extensions to, DECISIONS.md

The design follows DECISIONS.md. Where building from it exposed a gap or an unimplementable sentence, this
section says so instead of silently diverging.

### 9.1 Places where DECISIONS.md is underspecified, unimplementable, or arguably wrong

| # | Where | Finding | What this file does |
|---|---|---|---|
| 1 | D4 and D10: "Steel gets only `http://127.0.0.1:<port>` of the node forwarder" | A container's loopback is not the node's loopback, so the sentence cannot be implemented as written unless the forwarder shares the container's network namespace. It must also satisfy three facts at once: Stagehand v4's extension opens its own WebSocket to the same `cdpUrl` the SDK uses; Chromium bypasses a proxy only for loopback and link-local; Steel echoes `proxyUrl` over an unauthenticated API. | A small **holder** container owns the identity's namespace; the forwarder, Steel, the runtime and the actors all join it (2.2) and use loopback. The earlier draft had Steel own it; `docs/infra/steel-profile.md` now agrees with the holder form (its topology T-L), and the packaging of the actors is settled in M1. **Design choice to confirm in M1; C-08 is unverified.** |
| 2 | D17 `approvals`: "list and answer approvals this token may see" | A token that can answer its own approvals is no gate, and a mixed read/write tool breaks truthful `readOnlyHint` (HP-8). | Split into `approvals` (read) and `approve` (write, scope `approve`, never held with `publish` or `dm` on the same account; not listed for Hermes profile tokens). With `manifest`, `manifest_status` and `inbox` added, 17 tools. |
| 3 | D14: "time-limited, authenticated viewer link" | Nothing defines how the human authenticates. A bare signed URL that passes through an agent's context gives control of a logged-in client account to anyone who sees it. | The ticket alone never suffices; an authenticated operator is required (6.5), the URL never goes to the agent, and a ticket is exchanged once for a session (4.8). **The mechanism is an open question for Justin** (AQ-1); the design default is passkeys plus a `tenant_viewer` role (6.13). |
| 4 | D15 (daily note on a scheduled Hermes job from `run_status`/history reads) against D17 (`job` polls by id) | There is no history read. | `job` gets a list mode (5.3 tool 10). |
| 5 | D12: "an identity with a held/uncertain effect is itself blocked until reconciled" | Reconciliation needs the lease, so the rule deadlocks without a notion of why the lease is taken. | Lease `purpose` (`work`, `reconcile`, `canary`, `reauth`, `human_session`, `observe`, `maintenance`, `system`). A covering hold refuses `work` only (3.5, 3.11). |
| 6 | D12: fencing token checked by the node agent and executor | A node agent cannot cut a remote CDP session it does not host, so Browserbase-homed identities have weaker fencing. In-container workers talk to Steel on loopback, so the cut is killing them. | Stated in 3.5: the `connectUrl` is secret, one connection per Context, takeover ends the session through the API; for node-hosted identities the node agent kills workers on a higher token; the gap is one RPC **[to measure]**. |
| 7 | D5: irreversible actions gated "on every rung, including free-form `act` and `task`" | The mechanism is unspecified. An element-label classifier is a deny-list and fails open on unlabeled icon buttons; method-based network blocking fails because social SPAs send reads as POST GraphQL. | Default-deny allow-list for `read_only`; the hard gate is scope plus a manifest item or approval; Browser-Use's `register_new_step_callback` is the pre-execution hook; the classifier miss rate is **[to measure]** (4.3). |
| 8 | D3 on persona | UA must match the real Chromium version, but an image upgrade then changes the UA. D3 is silent on upgrades. | `image_cohort`, forward-only persona steps, canary rule (O-13) (3.2, 3.3). |
| 9 | D2 ("each action human-approved, low volume") against any volume at 100-1,000 accounts | Under a browser-first answer to Q-01, per-action approval of routine posts does not scale. | `browser_hitl` in `channel_policy`, confined to section 8. |
| 10 | D17 `identity_status` lists states asleep, awake, needs_reauth, checkpoint, held | `waking`, `sleeping`, `quarantined`, `retired`, and (after the scenarios) `canary`, `restricted` and `migrating` are needed; holds coexist with any state. | Holds are rows in `holds`, orthogonal to state (3.8, 3.11). |
| 11 | D17 and D1 refer to `ARCHITECTURE.md` and a fleet charter | The charter does not exist. | This file is the architecture. The charter is **[unbuilt]** and its first rule is "a tool is listed only after it passes a live end-to-end check". |
| 12 | D17 `extract` marked "R*" | It is long-running (wake, navigation, two model calls). | `readOnlyHint:true` because replay is harmless, but it is submit-then-poll (4.4). |
| 13 | D3: "changing infra or IP means a new identity and a fresh human login" (and the old vocabulary, one identity per platform account with the ledger keyed on it) | It conflates what must be fresh (login, state, persona) with what must stay (account, ledger, caps, API connection, manifests). With the ledger keyed on `identity_id`, a new IP resets caps and loses duplicate protection, and `unique (platform, handle)` blocks the successor (S07-5, S07-6, G10-3, S02-6). | **Account and identity are split** (3.1, 3.2, 3.10). DECISIONS D3 and the vocabulary are revised (Revisions). |
| 14 | D5: the ladder "stops at the first rung that succeeds" | For an irreversible step a repaired target is first used as a live click chosen by a model, ahead of any review (S06-1). | Effect steps stop at L1; a mandatory `target_rule`; repair by rehearsal and a person's confirmation (3.7, 4.3). D5 is amended. |
| 15 | D12 / old ARCH 3.2: any `uncertain` effect holds the whole identity | An API timeout would stop the browser and every other platform and conversation (S03-10, S07-4). | Hold scopes: browser-channel doubt is `all`; API-channel doubt is `api` on `(account, platform, conversation)` (3.11). D12 is revised. |
| 16 | D2: "personal profiles" in the narrow no-API set | `docs/channels/social-channels.md` section 6 says a Facebook personal profile is not offered (terms bar giving others access), and LinkedIn is a Charter red line (S01-10, G11-11). | One allowed-uses table in D2; no browser identity for personal profiles or LinkedIn; `draft_for_human` (4.7). D2 is revised. |
| 17 | D13: effect key, "may be retried", "never from page text" | The key included the job, so a new job could double-post; a negative browser read-back is weak evidence; "never from page text" overstated what code enforces (S08-1, S08-5, S13-18). | Key on the account and the authority; second uniqueness check; approval consumed at intent; no retry after a negative browser read-back; wording corrected (3.6). D13 is revised. |
| 18 | D11: Browserbase "for a site where Steel fails" | Too loose to build a gate from; omits `solveCaptchas:false`, BB-O1, BB-O2 and the continuity trade-off (G10-13, S05-14). | Functional-only rule, `identity create` checks, persona per home (3.3, 4.15). D11 is revised. |
| 19 | D17: error list | No code means "no scope, approval or manifest can unlock this" (G11-2). | New `refused`, plus `rate_limited` and `identity_state` (5.5). |
| 20 | D5 / D6: L3 is Stagehand; the executor is decided per site class | Account images carry no extension (S14-4), so L3 would have no engine (S14-3). | D18: executor and L3 by identity kind; the L3-lite design (4.3). |
| 21 | D3 / Q-13: one client per node, because host-real values differ across nodes | Never measured; if they are equal across droplets the rule buys nothing (S09-1). | A measured fork (7.7). |
| 22 | D12 cost table | One axis (all-browser). No `f`, no X volume; $8,403 summed against ~$8,413 stated; a 40% replay share from a cache that does not exist (S09-8). | `f` and X volume added as axes, no single total (D12; 7.1). |
| 23 | Vocabulary: "identity" (old ARCH 3.1: one identity with several `identity_platforms`) | An identity could span several platform accounts, but the acquire predicates, holds and open-effect check need to know which accounts share a session (S08-2, S05-1). | **1:1: an identity serves exactly one account** (3.1). Two platforms needing a browser mean two identities and two IPs. |

### 9.2 Elements this file adds that DECISIONS.md does not contain **[extension]**

1. `identities.kind` (`account` or `research`), two research modes (`http_only`, `ephemeral_browser`) and plain-HTTP reads through a `research` identity's forwarder (4.13).
2. `identities.image_cohort` and forward-only persona history.
3. The network holder, the forwarder sidecar, the runtime and per-actor containers in one namespace, and kill-on-takeover fencing for the actors.
4. Lease `purpose` (eight values) and human-lease liveness.
5. The `approve` scope and tool, and the rule that no token holds `approve` with `publish` or `dm`.
6. `job` list mode.
7. The `risk_acceptances` table.
8. `channel_policy` and a single channel router; `browser_hitl`; the `human_clicks` option for browser-channel effects.
9. The `PlatformConnector` interface.
10. Postgres row-level security for tenant isolation.
11. The marker file inside a state bundle (detects a restore into the wrong directory).
12. Self-fencing node agents.
13. Operator accounts, roles and a second factor on viewer tickets (mechanism open; 6.13).
14. Opaque evidence refs in Obsidian notes, resolved through `job`.
15. `wait_s` semantics (default 20, maximum 60; `job` long-poll up to 60).
16. Separate `decide` and `model` processes; a Python Stagehand worker by default (TypeScript as the
    fallback); an `Executor` interface so the L1/L2 executor choice (O-02) is local.
17. Node enrollment tokens and mTLS between fleetd and nodes.
18. A per-identity engine mutex (Stagehand, Browser-Use and the viewer never act at once).
19. A per-token tool list and `fleet_status.tools[].available`.
20. A tenant-scoped L1 cache, with a content-scrubbed shared tier left as a later review.
21. A shared limiter store at the 1,000 scale.
22. Per-wake network creation and removal (Docker's bridge limit).
23. **Added by the scenario revision (2026-10-10):** the account/identity split and `platform_accounts` (3.2);
    the `canary`, `restricted` and `migrating` states (3.8); the `holds` table (3.11); the cutover operation (3.10);
    policy gate R (4.3, C18); the inbound pipeline, `inbound_events`, `conversations`, `opt_outs` and the `inbox`
    tool (3.12, 4.12, C19); the `manifest` and `manifest_status` tools, campaigns, triggers and closed rule sets
    (3.7); the media store (3.13, C20); `platform_apps`, `connection_health`, `consents`, `account_firsts` (3.13,
    C22); the source registry, politeness component and lead records (3.14, C23); `site_incidents`,
    `host_cooldowns`, `step_health`, `incidents` (3.15); the change detector (4.16); the human-session flow with
    two takeover modes and mandatory closure (4.14); owner-only `identity create` (4.15); admission control,
    fair share and tenant shares of app windows (4.17); the capacity planner (7.8); node classes (7.7); operator
    roles (6.13); the taint map (5.2); the `Executor` interface, L3-lite and `executor_id`/`extension_mode` in the
    persona (3.3, 4.3, D18); `refused` and `rate_limited` (5.5); the `site_blocked` and `assent` blocker classes
    (4.2); `draft_for_human` (4.7); leased budget slices (4.17).

### 9.3 Refuted or corrected claims, and how this file treats them

Per the precedence rule the verification reports win. Checked against this file:

| Claim | Treatment here |
|---|---|
| Steel left `Singleton*` 7/7 | 6/6 in persist mode (C-26) |
| `--lang` pins locale on Linux | `LANG`, `LANGUAGE` and `--accept-lang` (C-10) |
| "~3% runaway" | 7-8% on click acts on a 6K-token page, Wilson 3-18%; `max_tokens` cap mandatory (C-22) |
| Cold wake "15-20 s" | 11.7-21.6 s as a floor, excluding download, decrypt, proxy connect, checks, node creation (C-27) |
| Release flushes cookies in "1-3 s" | At least 31 s of cookie quiet plus the journal as source of truth (C-03) |
| A System 1 step is "1,000 tokens" | 4.9-6.2K for 180 candidates (BRO-4) |
| Jev's cap is "180" | 255 for Jev, Clef, Perplexity; 180 is a working size (C-06) |
| `rerun_history` replays with no LLM | One summary call unless stubbed; not a zero-call tier (C-07) |
| "18 attack checks" | 11 attacks plus 7 controls, ported off Playwright (C-25) |
| Release skills by flipping `current` | Versioned paths in each profile config, or roll gateways; keep old releases until recycled (X-1) |
| scale-infra lease SQL; an earlier internal job-claim design | Replaced by four separate statements on the identity row (SCA-10, EA-7) |
| X per-app ceilings shared by all clients | Governor from live headers; per-account caps bind first (SP-3, V-2) |
| "Patch Steel" is required | No-fork route (session fields plus env, with CDP injection as an option) is viable; a fork only if hardware values must be spoofed (SCA-3, C-01) |
| Stagehand v4 cache works on Steel; 40% "cached" share | `DISABLED` on Steel; the share is the fleet's own unbuilt L1 (SH-1, C-05) |
| Per-profile `userDataDir` works on self-hosted Steel | Ignored; one container per volume (C-04) |
| Skills cannot reach hosts that cannot load plugins | Owner-approved prose guides can; plugins cannot (HP-5) |
| Meta ToS 3.2 bans bot-driving the UI | A scraping clause with a permission carve-out; the firmer basis is the Community Guidelines (SP-2) |
| Weekly keep-warm login probe | Dropped for Meta (O-12, SP-9) |
| Headful WebGL absence is caused by `--disable-gpu` | Cause unproven; explicit SwiftShader flags plus Xvfb and dbus (C-11) |
| Stagehand v4's detectability is unknown | Measured trip of `isAutomatedWithCDP` (n=1); weighting by platforms unknown (C-13) |
| Guard costs one websocket and one task | CPU unmeasured; gating contract rebuilt (C-25) |
| Kameleo licence is small | 35-51% of the base bill at 100-1,000 identities (V-2, C-23); not relied on |
| NetNut-sourced pools can be avoided by name | Vetting rule per IP (O-10) |
| Steel upstream will fix auth, singleton, userDataDir | Outsider PRs with no maintainer owner; the fleet carries its own (C-24) |

### 9.4 Questions this design raises that are not in Justin's 14

- **AQ-1** How do operators authenticate to the viewer and the approval console (passkeys, the company IdP, an
  out-of-band one-time code)? **Blocks the reauth flow (4.8) and is a blocking item of M2.** *Design default,
  pending Justin:* passkeys plus a `tenant_viewer` role (6.13).
- **AQ-2** KEK custody (O-09): a key on the control droplet, a separate vault, or an external KMS.
- **AQ-3** Where do owner alerts go (Slack, email, a webhook into Hermes)? **A blocking item of M2** because the
  viewer ticket travels by the notifier only. *Default, pending Justin:* the channel the owner records per
  identity at creation.
- **AQ-4** Are open-web lead-generation identities separate from client social identities, each with its own IP?
  (Assumed yes: `kind:"research"`.)
- **AQ-5** Who holds `approve`: operator-console users only, or also an owner-facing Hermes profile?
- **AQ-6** Where does the Obsidian vault live relative to the droplets and the trial (O-14)?
- **AQ-7** The host-real fingerprint values across same-size droplets (7.7): the measurement decides whether
  Q-13 is reopened. Not a question for Justin until it is measured.
- **AQ-8** Does a human-approved AI draft count as an "automated bot" under Messenger's 30-second rule and the
  disclosure rules? Unestablished (SPV missed issue 8). *Default, pending:* treat it as automated and set
  `channel_policy.bot_disclosure` per market (4.12).
- **AQ-9** BB-O1: how the Browserbase exit-IP pin is enforced (accept checks plus a kill switch, or build the edge
  forwarder). Default: the checks and a kill switch (D11).
- **AQ-10** Is a Facebook Groups session a personal-profile session? Not researched. Until answered the acting
  account must be a Page or business account (D2 table row 2).
- **AQ-11** BB-O2: ask Browserbase in writing whether a client's own authorized posting is within its terms
  (D11).
- **AQ-12** May a manifest authorize **browser** effects (a Q-01 sub-question, D2 table row 10, 8.4)?
- **AQ-13** Delivery of inbound events into Hermes by push: unresearched. v0 polls `inbox` on a cron job (4.12).
- **AQ-14** Who is the named person for viewer tickets on each identity (the client's staff, an agency
  operator)? Recorded at creation (4.15).

### 9.5 Gap ledger: scenario stress tests S01-S14

Every gap the stress tests raised against this file or DECISIONS.md, and where it is now handled. "Target" is the
file the scenario aimed the gap at: `arch` rows are fixed in this file; `decisions` rows are fixed in DECISIONS.md
and, where this file depends on them, here as well (the DECISIONS change is listed in its "Revisions"). Section
numbers are of this file; "D2", "D3" and so on are of DECISIONS.md. Gap ids are the scenario files' own ids
(`research/scenarios/S01.md` ... `S14.md`; S07 and S08 carry printed ids in their own tables). **No gap is declined outright.** Where a fix is a default pending
Justin, or part of it belongs in a file this reviser does not own, the Note column says so; the follow-ups for other
files are in the revision result.

| Gap | Target | Where handled | Note |
|---|---|---|---|
| S01-1 | arch | 3.2 state enum, 3.8 canary |  |
| S01-2 | arch | 4.15 identity create; 2.1 C1 console functions; 6.13 |  |
| S01-3 | arch | 4.8 (ticket via notifier only, AQ-1 default), 6.13 | Mechanism stays open: AQ-1 default (passkeys + tenant_viewer) is a design default pending Justin; viewer broker is a blocked component until AQ-1 and AQ-3 close |
| S01-4 | arch | 3.5 human lease liveness |  |
| S01-5 | arch | 3.3 cookie precedence (journal first) | Journal-first when the bundle is cookies_unflushed or the journal is newer; "apply at every wake" is left to the new G1.1 case |
| S01-7 | arch | 3.3 cross-host restore expected path |  |
| S01-8 | arch | 3.3 marker specs |  |
| S01-10 | decisions | D2 allowed-uses table; 8.3 (LinkedIn and personal profiles removed from browser_allowed); 4.7 draft_for_human | Which account type may act in a Group is unresearched (AQ-10); default Page or business only |
| S01-13 | arch | 3.3 generation 0 |  |
| S01-14 | arch | 4.8 steps 3 and 5 (waiting/ready/checking/done page) |  |
| S02-1 | arch | 3.7 manifest items; 5.3 tools manifest and manifest_status |  |
| S02-2 | arch | 3.13 media_assets; 2.1 C20; 4.6 step 6 |  |
| S02-3 | arch | 3.7 campaigns and campaign approval; 5.3 tool 15 (`manifest`); 6.13 `client_approver` |  |
| S02-4 | arch | 3.7, 3.13 account_firsts, 4.3 gate G 3b, 4.11 |  |
| S02-6 | arch | 3.1, 3.2 accounts split from identities |  |
| S02-7 | arch | 3.13 `platform_apps`; 4.11 preflight and `blocked_until_ready` |  |
| S02-8 | arch | 3.13 live limit sources; 2.1 C11 | Corpus holds no Meta/TikTok/LinkedIn pages; only X and Instagram have a named live source. Others are static caps "to verify" |
| S02-9 | arch | 3.13 connection_health, consents; 2.1 C22 |  |
| S02-10 | arch | 3.6 matcher |  |
| S02-11 | arch | 3.7 fleet-side scheduling |  |
| S03-1 | arch | 3.12, 4.12 inbound pipeline, 5.3 inbox tool |  |
| S03-2 | arch | 4.3 gate R item 3, 4.12, 5.5 refused/reasons |  |
| S03-5 | arch | 3.7 triggers, 4.12 step 6 | Default for human-approved drafts is a design default pending AQ-8 (unestablished in the research) |
| S03-8 | arch | 3.6, 3.7 approval lifecycle |  |
| S03-9 | arch | 3.7 approval in_reply_to |  |
| S03-10 | decisions | D12; 3.11 API-scope holds |  |
| S03-12 | arch | 3.12 inbound budget |  |
| S03-14 | arch | 4.6 steps 2 and 7 (read-before-send, private_reply, Requests blind spot) |  |
| S04-3 | arch | 3.14 source_registry, 4.13 politeness, 2.1 C23 |  |
| S04-4 | arch | 4.13 two research modes, 2.2 holder-owned namespace | http_only start sequence is not yet in steel-profile.md; listed in open questions |
| S04-5 | arch | 4.13 batch shape, no lease for http_only |  |
| S04-6 | arch | 4.3 lead_gen mode, 4.5 enforcement table |  |
| S04-8 | arch | 3.3, 3.8 research identity |  |
| S04-9 | arch | 3.14 lead record; 2.1 C15 |  |
| S04-13 | arch | 3.14 unverified_contact | docs/playbooks/lead-gen.md 4.3 is outside this file; listed in open questions |
| S05-1 | arch | 3.5 acquire predicates, 3.9 claim |  |
| S05-2 | arch | 4.2 step 5, 4.3 login deny-list |  |
| S05-3 | arch | 3.3 blocker_spec, 4.2 step 5 |  |
| S05-4 | arch | 3.8 cooldown, restricted |  |
| S05-5 | arch | 3.5 system lease, 3.7 restart_from, 3.9 needs |  |
| S05-6 | arch | 3.6 tri-state read-back |  |
| S05-7 | arch | 3.6 second uniqueness, human effects |  |
| S05-8 | arch | 4.8 step 2 (notifier only, redaction) | hermes/README.md plugin and fleet-identity steps 3-4 are outside this file; listed in open questions |
| S05-11 | arch | 3.8 sleep during pause |  |
| S05-14 | decisions | D11 solveCaptchas:false; 4.1 Browserbase paragraph; 4.15 check |  |
| S06-1 | decisions | 3.7 target_rule, 4.3 effect steps stop at L1, pre-submit check |  |
| S06-2 | arch | 3.6 known-positive self-test, 4.16 |  |
| S06-3 | arch | 3.15 step_health; 4.16 detector | MILESTONES G5.9 and the fleet-steps skill section 4 are outside this file; listed in open questions |
| S06-4 | decisions | D13 (revision versus L1 entry, promotion, rollback); 3.7 procedure fields; 3.9 promotion; 6.13 reviewer |  |
| S06-5 | arch | 3.9 l1 key and fingerprint |  |
| S06-6 | arch | 3.9 l1 state machine |  |
| S06-7 | arch | 4.3 data_class rung table | Edit to docs/models/system1.md section 6 is outside this file; listed in open questions |
| S06-8 | arch | 4.2 step 6 assent versus dismissable |  |
| S06-10 | arch | 3.9 missed jobs, 4.16 alerts, 2.1 C16 |  |
| S07-1 | arch | 3.11 proxy_unavailable not a hold; 4.1 W9, 3.11, 4.10 | steel-profile 9.6 already classes probe results; ARCH adds the two outcomes |
| S07-2 | arch | 3.11 holds table |  |
| S07-3 | arch | 3.10, 3.11 hold_clear |  |
| S07-4 | arch | 3.11 hold scope |  |
| S07-5 | arch | 3.10 account across a move |  |
| S07-6 | decisions | D3 reworded; 3.10 |  |
| S07-16 | arch | 3.7 expired_unrun |  |
| S08-1 | arch | 3.6 effect key, one transaction |  |
| S08-2 | arch | 3.5 acquire |  |
| S08-3 | arch | 3.5 timing and fence | TTL, renewal interval, skew and margin are symbols with "estimate, to measure" because no source gives numbers |
| S08-4 | arch | 3.3 periodic journals |  |
| S08-5 | arch | 3.6 no retry after negative read-back |  |
| S08-6 | arch | 3.6 matcher |  |
| S08-7 | arch | 4.7 step 8 (first and second alert, console actions); 2.1 C16; 4.15 console functions |  |
| S08-13 | arch | 3.6 evidence before click |  |
| S09-1 | decisions | D3 fork paragraph; 7.7 | A fork, not a decision: D3 keeps one client per node until the S09-2 measurement |
| S09-3 | arch | 7.8 capacity planner, 4.1 W4, 4.11 |  |
| S09-4 | arch | 4.17 shared app windows |  |
| S09-7 | arch | 4.0 step 2, 4.17 admission |  |
| S09-8 | decisions | D12 cost axes; 7.1 note |  |
| S09-10 | arch | 3.12, 4.12, 5.3 inbox |  |
| S09-12 | arch | 7.2 isolation unit, 4.9 step 8 |  |
| S09-14 | arch | 4.17 leased budget slices |  |
| S09-15 | arch | 4.1 W4, 7.2 placer |  |
| S09-16 | arch | 4.10 incident row, 3.15 incidents |  |
| G10-3 | arch | 3.10 steps 0, 1, 4 and rollback; 3.2 partial unique `proxy_id`; 3.8 lift rule | Second pass after the blocker re-check: same-IP successor and rollback states added |
| G10-5 | arch | 3.3 persona per home |  |
| G10-11 | arch | 4.2 step 6 site_blocked, 3.15 host_cooldowns |  |
| G10-12 | arch | 3.15 site_incidents |  |
| G10-13 | decisions | D11 (functional-only rule, solveCaptchas, BB-O1, BB-O2, continuity) |  |
| G11-1 | arch | 4.3 gate R, gate G read_only; 4.5 item 5 people-list path rules and post-action check; 2.1 C18 | Second pass after the blocker re-check: in-session enforcement added, platform search removed from read_only |
| G11-2 | decisions | D17 and 5.5 `refused`; 5.3 publish/act errors | fleet-router "Read the answers" row is outside this file; listed in open questions |
| G11-3 | arch | 3.7 closed target_rule, 4.3 gate R item 3, 4.12 |  |
| G11-5 | arch | 3.4 flood limits |  |
| G11-7 | arch | 3.12 |  |
| G11-11 | arch | 4.7 draft_for_human, 8.3 |  |
| G11-12 | arch | 4.5 step 1 |  |
| G12-1 | arch | 3.5 human lease | steel-profile.md section 9.2 edit is outside this file; listed in open questions |
| G12-2 | arch | 3.5 purposes |  |
| G12-3 | arch | 4.14 takeover modes |  |
| G12-4 | arch | 4.14 scheduled work meets a human lease | Default (pause effects, allow reads, API included) is pending the CHARTER invariant 2 reword, which is outside this file |
| G12-5 | arch | 3.6 |  |
| G12-6 | arch | 4.2 step 8, 4.14 |  |
| G12-14 | arch | 4.8 step 5, 4.14 |  |
| G12-15 | arch | 4.7 step 6 human_clicks default | human_clicks default; agent_clicks only by explicit owner setting |
| S13-1 | arch | 3.12 |  |
| S13-2 | arch | 3.7 warnings |  |
| S13-3 | arch | 5.2 taint map; 6.7 item 1 |  |
| S13-5 | arch | 4.3 gate R item 5, 4.4 step 2 |  |
| S13-8 | arch | 4.5 enforcement table, 3.2 allowed_hosts |  |
| S13-10 | arch | 4.8 step 2 |  |
| S13-12 | arch | 3.4 flood limits; 3.12 inbound budget; 4.12 step 7; 6.7 item 8 |  |
| S13-13 | arch | 4.5 step 6, 5.5, 5.3 feedback |  |
| S13-14 | arch | 3.7 closed rule sets |  |
| S13-18 | decisions | D13 reworded; 6.7 item 1 |  |
| S14-2 | arch | 4.3 Executor interface, 3.9 l1 key |  |
| S14-3 | arch | 4.3 L3-lite and the per-data_class table; D18; 2.5 third shim face |  |
| S14-4 | arch | 4.1 W5 and W10, 2.2 |  |
| S14-7 | arch | 3.3 persona pins executor_id |  |
| S14-8 | decisions | D18; D5 and D6 amended (Revisions) |  |

## 10. Map of pending questions and measurement gates

### 10.1 Justin's questions Q-01 to Q-14: what each one changes here

Q-15 to Q-19 were added to DECISIONS.md after the completeness review: Q-15 confirms D18 (executor on
logged-in accounts), Q-16 the `moderate` kind, Q-17 `duplicate_content`, Q-18 Hermes host sharing across
clients, Q-19 a workstation housekeeping item. Their defaults are in DECISIONS.md and ANSWERS.md section 1.

The design proceeds on the recommended default for every one. The last column is where to edit when he answers.

| Q | Question (short) | Default assumed | Where it bites |
|---|---|---|---|
| Q-01 | API-first or browser-first for client social; which clients accept the terms risk in writing | API-first | **Section 8 only**; 4.7 steps 2 and 6 read it through `browser_hitl` and `click_mode`; D2's table row 10; AQ-12 |
| Q-02 | Anti-detect: continuity only with measured upgrades, or buy a product | Continuity only | 3.3 persona `mode`; 4.3 executor choice; 8.4 |
| Q-03 | May the fleet depend on a proprietary patched kernel (CloakBrowser) | No | 3.3 persona `mode:"patched_kernel"` stays disabled |
| Q-04 | Spoofing stance: continuity only, or seed-pinned spoofing | Continuity only | 3.3; `cdp_injected` and `patched_kernel` stay off |
| Q-05 | X "Automated" label on client brand accounts | Treated as required; **no X publishing for client brand accounts until he answers** (CHARTER, MILESTONES 5.1); the connector carries the label | 2.6 X row; 4.6 |
| Q-06 | Apply for Meta App Review and Business Verification, TikTok Accounts API, LinkedIn CM API, X pay-per-use; monthly caps | The design treats the approvals as milestone dependencies; **nothing is applied for, and no paid call is made, until he says yes** (CHARTER "Spots that wait on Justin") | 2.6; 8.3 critical path; spend caps in 3.9 |
| Q-07 | Data handling: require zero-data-retention routing, per-client consent, or both | Both required until he answers (CHARTER invariant 8, MILESTONES 5.1); `tenant.zdr_required` flag exists | 2.5 provider allowlist; the per-`data_class` rung table in 4.3; 4.4; 3.12 retention; 6.10 |
| Q-08 | Steel's Chromium non-root with sandbox on, or accept the risk in writing | Try non-root; otherwise written acceptance | 2.2 N2; 6.9 |
| Q-09 | Exclude `fleet/` from box-kit's public export, or move to a private repo | Nothing merges until decided | 6.12 |
| Q-10 | A separate exposure question about a public companion repo (tracked privately) | n/a to design | 6.12 |
| Q-11 | Jev trial: add the fleet through the integrations route and owner-approved guides; who holds owner | The design supports the route (5.6); **the fleet is not connected to the trial until he answers** (CHARTER, `hermes/README.md` section 6) | 2.7 H4; 5.6 |
| Q-12 | Approve a small, capped, throwaway DigitalOcean droplet for M1 | Required for every gate below | Section 7 numbers; 10.2 |
| Q-13 | Cross-client unlinkability required (one client per node) | Yes until per-identity hardware values exist; **a measured fork** (7.7) | 3.3; 7.1 formula; 7.4; 7.7; 6.6 |
| Q-14 | Add consent-based lead channels (Lead Ads, opt-in DMs, LinkedIn Lead Gen Forms, TikTok instant forms) as first-class | Yes, as connector capabilities | 2.6 |

**Blocking items of M2 (reauth and the first client login), not among the 14:** **AQ-1** (operator
authentication for the viewer) and **AQ-3** (where the notifier sends the ticket). The viewer broker is a blocked
component until both are closed, and the reauth flow (4.8) is not relied on before then. The other AQ defaults
(9.4) proceed without Justin and are marked "pending" where they appear.

### 10.2 Measurement gates this design depends on

None of these are done; each marks the places in the text tagged **[to measure]** or "untested".

**M1 (droplet hands-on; needs Q-12; also an amd64 re-run of every Steel measurement, O-17):**
- Plain Chromium plus a small session API versus the Steel wrapper; the winner is written into D4 (C-24).
- Cross-host and x86 restore of a profile tarball; bundle download, decrypt, extract time; wake p50/p95.
- A graceful cookie flush (4.9), and whether a clean-exit `Browser.close` commits the cookie store.
- The viewer: Enter, Backspace, Tab, arrows, IME, passkeys, native dialogs, HTTP auth, file pickers.
- The same-namespace runtime: loopback CDP for Stagehand's extension, the guard's `Fetch` interception against
  that WebSocket, empty `PROXY_INTERNAL_BYPASS`, in-container argv free of proxy credentials, metadata-endpoint
  reachability around the proxy, `<-loopback>` through `CHROME_ARGS`.
- `act(Action)` replay across iframes and shadow DOM; Browser-Use `Tools.act` against a live Steel session; the
  extension recipe on real sites; large uploads through Steel's files API; the Stagehand instance lock after
  a worker crash.
- Executor choice per site class (`isAutomatedWithCDP`; uninstall after session) (O-02).
- Per-identity hardware values: CDP injection versus a patched kernel (O-01).
- Cookie journal re-injection with `persist:true` (4.1 W12); Browserbase CDP timezone override across
  reconnects.
- Memory and CPU on social SPAs; soak behaviour over 1-3 h; guard CPU; a graceful kill-on-takeover gap.
- Composer `fill` on real Lexical and Draft.js editors; the effect classifier's miss rate; read-back receipt
  false-negative rates on real feeds.
- **Added by the scenario revision (2026-10-10), all estimates until measured:** the host-real fingerprint values
  across same-size droplets and across sizes (7.7, S09-2); node-creation time and the per-node concurrent-wake
  cap (7.8); the G1.1 two-node restore, including a test-app case that sees **no logged-out request before the
  journal is applied**, and G5.2 (both are hard prerequisites for onboarding any client, 3.3); G5.3 ending in a
  reconcile wake that needs no human; the periodic-journal interval `J`; lease TTL `L`, renewal interval, clock
  skew and margin (3.5); human-lease heartbeat, idle timeout and ceiling; `http_only` start-up and the holder
  starting without Steel (4.13); account-image extension flags and `FILTER_CHROME_ARGS` for
  `--remote-allow-origins` (N2); the `proxy_mismatch` stability-echo idle period (3.11); the `domain_match` and
  `dom_fingerprint` tolerances (3.9, 3.14).

**M3 (model providers, and the L3-lite and detector numbers):** a per-provider GLM benchmark with `provider.only`, with and without ZDR, price and
quantization caps, and the shim's schema validation (O-06); Clef images through OpenRouter; OpenAI Decisions
limits; element-choice accuracy on dense social and lead-gen pages; thresholds per
`(template, model, provider, risk_class)`; GLM throughput for 100-1,000 agents; the System-1 share per
procedure on a held-out set (O-15); L3-lite accuracy and the re-estimated System-1 share and human load for
logged-in procedures (G1.4, 4.3 table); the detector's `k` and window (4.16); the L1 promotion `k` (3.9).

**M4 (social channels, see section 8):** developer-app approvals; X limits on a live pay-per-use app (the
per-app ceilings are unproven, SP-3); the Messenger 30 s window and whether a human-approved draft counts as a
bot (AQ-8); TikTok review outcome; live limit sources per platform (3.13); the normalised-text matcher and its
false-negative rate (G4A.1) and the browser read-back rate (G4B.1); inbound webhook volume and the X inbound
budget (3.12).

**M6 (cost):** replace every row of D12's table with measurements, including `f` (the share of accounts with a
browser identity), X volume and operator time (G6.5); reconcile the leased budget slices against provider billing
(MILESTONES G3.9).

### 10.3 Order of dependencies (no dates)

1. Charter and the pure-SQL pieces that need no droplet: the lease statements and the effect-ledger state
   machine, tested against Postgres locally (O-03, O-04).
2. Q-12 answered, then M1. Nothing in sections 2.2-2.3, 4.1, 4.8 or 4.9 is relied on before M1 passes. AQ-1 and AQ-3
   close before the reauth flow is relied on.
3. Connector approvals (Q-06) can start in parallel with M1 because they are external.
4. M3 gates the model shim's provider allowlist and the /decide thresholds.
5. The first client account follows: a canary identity under the O-13 rule, with the executor and persona
   choices already measured.
6. Scale steps (30 -> 100 -> 1,000) follow the cost and wake measurements (M6), not a calendar.
