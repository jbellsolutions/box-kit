> **Read with its verification report.** [verification/scale-infra.md](../verification/scale-infra.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: running 30 → 100 → 1,000 persistent browser identities on DigitalOcean

Agent: scale-infra research agent. Date: 2026-10-09 (UTC 2026-10-10). Spend: **$0.00**.

What I did:
- one read-only DigitalOcean `GET /v2/sizes` call;
- one public OpenRouter `GET /api/v1/models` call (no key);
- local `fleet-spike-scale-*` containers, all of them removed afterwards;
- no model calls.

Spike: [`fleet/research/spikes/scale-infra/RESULTS.md`](../spikes/scale-infra/RESULTS.md).
Cost arithmetic: [`cost_model.py`](../spikes/scale-infra/cost_model.py), with its output in
[`raw/cost_model.out`](../spikes/scale-infra/raw/cost_model.out).

Pinned sources:

| repo | commit |
|---|---|
| `steel-browser` | `1131a02` |
| `browser-box` | `4c837a3` |
| `temporalio/docker-builds` | `8ea563e` (2026-01-06) |

The local Steel image is `sha256:7a161b95…` (2026-09-16, `@steel-browser/api` 0.5.3, Chromium 152).
Its compiled code matches `1131a02` on every line I checked.

Tags:
- `[hands-on]` means run today; the spike numbers are **arm64 Docker, not a droplet**.
- `[source-code]` means read at the commit above.
- `[official-docs]`, `[vendor-claim]`, `[third-party]` and `[unverified]` are as in the brief.
- `[estimate]` means my labeled planning assumption.

---

## 1. Verdict

1. **Self-hosted Steel runs one browser per container.** `SessionService` holds a single
   `activeSession` (`api/src/services/session.service.ts:67`) `[source-code]`. So the unit of scale is
   "one Steel container per *active* profile", and the plan is about how many of those fit on a droplet.
   - Planning slot: **1.5 GiB for the browser plus 0.35 GiB for its agent runtime, and 0.6 vCPU**
     `[estimate]`.
   - On an `s-8vcpu-16gb` ($96/mo) that is **7 active slots**.
   - Measured on light test pages: 0.70–0.85 GiB peak per container, and 344–407 MiB idle `[hands-on]`.
   - Social sites were not and cannot be measured under the brief's rules.
2. **Wake on demand, never always-on.** 1,000 always-on browsers is ~1.85 TB RAM, about 143 nodes and
   ~$13.7k/mo in droplets alone.
   - Waking on schedule needs 125 concurrent browsers (1 h/day) to 375 (3 h/day) at 1,000 profiles,
     which is 19–57 nodes.
   - Cold wake measured **~15–20 s** end to end: container start, restore, Chromium launch, first page
     `[hands-on, arm64]`.
   - Because most work is scheduled, pre-wake each profile just before its job. That beats a generic
     warm pool.
3. **Profile state at rest = a slim, encrypted tarball of the user-data-dir in DO Spaces.** It is
   portable across containers and nodes, but only if you **strip Chromium's `SingletonLock` /
   `SingletonSocket` / `SingletonCookie`**.
   - With those files left in, the restore *silently* came back logged out, even though the session
     create returned HTTP 200. With them removed, it restored `[hands-on]`.
   - Cookies use `--password-store=basic` (a fixed `v10` key), so no per-host key is involved
     (`cdp.service.ts:898`) `[source-code]` `[hands-on]`.
   - Slim bundle after 8 test pages: **57 KB** zstd. Social profiles will be much larger: the planning
     figure is 50 MB, and Steel Cloud caps a profile at 300 MB.
4. **OSS Steel does not give "same fingerprint every time".** It generates a new random fingerprint on
   **every Chromium launch, including relaunches of the same profile** `[hands-on]`:
   - the UA's Chrome version moved through 144 → 142 → 145;
   - `hardwareConcurrency` moved through 16 → 8 → 32 → 18;
   - the WebGL renderer moved through Intel → SwiftShader → AMD → a phone's Adreno GPU;
   - the timezone flipped between UTC and New York.

   Two more gaps:
   - The REST schema has no `fingerprint` field, and the plugin launch hooks run *after* `userDataDir`
     and `fingerprint` are read (`cdp.service.ts:704-722`) `[source-code]`.
   - The fleet must ship a **small patched Steel image**: honor a per-session `userDataDir`, accept and
     pin a stored fingerprint, and always pin timezone, UA and dimensions.
5. **Two silent traps in today's code.**
   - **(a)** `userDataDir` in the session body is ignored, because of operator precedence at
     `session.service.ts:180-183` `[source-code]` `[hands-on]`.
   - **(b)** browser-box's `session` tool sends Steel *Cloud* fields (`persistProfile`, `profileId`;
     `gateway/gateway/steel.py:103-105`). Self-hosted Steel accepts them with HTTP 200 and ignores them.
     The "persistent" profile actually lives in `/tmp/steel-chrome` inside the container and is lost
     whenever the container is recreated `[hands-on]`.
   - The fleet must not copy browser-box's session code.
6. **Scheduler: Docker on droplets + a small node agent + a placer inside the fleet service, with
   Postgres as the source of truth.** Postgres holds profiles, leases with **fencing tokens**,
   placements, effects and the audit log.
   - Use Temporal, deployed properly on Postgres, for durable per-profile workflows.
   - **Temporal on Postgres carries durability; NATS is for best-effort telemetry only.**
   - Nomad (BUSL) and DOKS are reasonable later. Neither is needed for ≤ ~60 nodes.
7. **Posting twice is prevented by an effect ledger, not by the job engine.**
   - Every side effect gets an idempotency key and an **intent row committed before the click**.
   - It then needs an independent **read-back receipt** from the destination.
   - Uncertain results go to reconciliation and are never retried blind. This is the
     pattern of an earlier internal trial `[source-code]`.
   - Temporal and JetStream are both at-least-once, so neither removes the need for this.
8. **Cost at 1,000 profiles (labeled estimates, System-1-first model mix):**
   - **3 h/day:** self-hosted **~$8.4k/mo autoscaled** (≈$11.2k static), against Steel Cloud **~$14k**
     and Browserbase **~$15.7k** (both custom-priced at this concurrency).
   - **1 h/day:** self-hosted **~$4.7k/mo**.
   - **Proxies ($2,500) and models ($1k–$9.6k) are at least as big as the compute**, so the
     System-1/cache share matters as much as the infrastructure choice.
   - **At 30 profiles, Browserbase (~$359) costs about the same as self-hosting (~$294–364).**
     Self-hosting wins from ~100 profiles upward, and its engineering cost is not in these numbers.
9. **Security posture changes from browser-box.**
   - Steel's REST, CDP and viewer have **zero authentication** (no auth code in `api/src`)
     `[source-code]`. Each profile container is therefore reachable only by its node agent, over a
     per-profile network.
   - The only external door is the fleet gateway, with per-profile scoped tokens.
   - Egress can be tightened to "proxy endpoint only". That is stronger than browser-box.
   - **Keep browser-box's in-browser guard anyway:** Chromium bypasses the proxy for loopback, so the
     2026-09-22 "page reads Steel's own API on 127.0.0.1:3000" exploit still applies.
   - `flock` lanes are replaced by Postgres leases with fencing tokens, which human takeover also takes.

---

## 2. Answers

### Q1. Resource math

**Per-session footprint**

| source | number | tag |
|---|---|---|
| browser-box README (2026-09-23): Steel container on the box | 686 MB after a few pages, 895 MB after a dozen, peak 1.08–1.36 GiB during HN/agent tasks; cap raised to 1.5 GiB | `[hands-on by browser-box]` README.md L418-436, L96-107 |
| browser-box `compose.yml` caps | steel 1536m / 1.2 CPU, agent-jev 384m / 0.5, agent-browseruse 640m / 0.6, gateway 256m / 0.5 | `[source-code]` compose.yml |
| this spike, idle container (Node API + boot Chromium) | 344–407 MiB | `[hands-on]` |
| this spike, 8 public test pages | 699 MiB settled, 851 MiB peak; 3 at once: 826 / 796 / 814 MiB peak, sum 2.4 GiB | `[hands-on]` |
| this spike, CPU while loading pages back to back | mean 0.3–0.55 core, p90 at the 1.2-CPU cap | `[hands-on]` |
| agent runtimes beside the browser | agent-browseruse 327 MiB peak; agent-jev 134 MiB | `[hands-on by browser-box]` README L428-429 |

Planning slot `[estimate]`:
- 1.5 GiB browser plus 0.35 GiB agent runtime, so **1.85 GiB**;
- **0.6 vCPU** average;
- 2 GiB reserved per node for OS, Docker, node agent and guard.

Social-network pages (Facebook, Instagram, TikTok, X) are heavy SPAs with video. The
`steel-browser` maintainers cap a Cloud profile at 300 MB on disk. Expect the RAM figure to be the
first thing the first live canary corrects.

**Headful vs headless**
- The stock self-hosted image **cannot launch headful**: `{"headless":false}` returned 500
  `launch_failed … Failed to connect to the bus` `[hands-on]`.
- The entrypoint starts dbus only when `DEBUG=true` and never starts Xvfb, although Xvfb is installed
  (`api/entrypoint.sh`, `api/Dockerfile:35,75`) `[source-code]`.
- Headful needs a custom entrypoint that starts Xvfb and dbus. Steel's headful flags render with
  SwiftShader in-process (`cdp.service.ts` `headfulArgs`).
- The cost delta is **unmeasured**. Budget +0.2 vCPU and +150 MB per headful slot until measured
  `[estimate]`.
- Whether headful is needed for stealth is for the antidetect dossier to decide.

**Concurrent active sessions per droplet** (prices from DO `GET /v2/sizes`, 2026-10-10, raw in
`spikes/scale-infra/raw/do-sizes-subset-2026-10-10.json`) `[official-docs API]`.

Slots = min((RAM − 2 GiB) / 1.85, vCPU / 0.6).

| size | vCPU / RAM | $/mo ($/hr) | active slots | $/slot-mo | note |
|---|---|---|---:|---:|---|
| s-2vcpu-4gb | 2 shared / 4 GB | 24 (0.0357) | 1 | 24 | browser-box's live box: one browser |
| s-4vcpu-8gb | 4 shared / 8 GB | 48 (0.0714) | 3 | 16 | |
| **s-8vcpu-16gb** | 8 shared / 16 GB | **96 (0.1429)** | **7** | **13.7** | default browser node; 12 regions |
| s-8vcpu-32gb-amd | 8 shared / 32 GB | 168 (0.25) | 13 (CPU-bound) | 12.9 | |
| g-8vcpu-32gb | 8 dedicated / 32 GB | 252 (0.375) | 13 | 19.4 | 4 regions on this account |
| c-16 | 16 dedicated / 32 GB | 336 (0.50) | 16 | 21.0 | predictable CPU |
| m-4vcpu-32gb | 4 dedicated / 32 GB | 168 (0.25) | 6 | 28.0 | memory-optimized is a bad fit (CPU-bound) |

At the measured light-page footprint (0.85 + 0.35 GiB), an s-8vcpu-16gb fits ~11 slots. On shared
("Basic") CPUs, noisy neighbors will show up as slower page loads. Benchmark Basic against c-/g-
sizes on the first droplets before committing the fleet to one size.

**Billing.** Droplets are billed **per second**, with a 60 s / $0.01 minimum and a monthly cap of 672 h.
Powered-off droplets still bill; only destroyed droplets stop
(docs.digitalocean.com/products/droplets/details/pricing, "last verified 25 Aug 2026")
`[official-docs]`. That makes scaling browser nodes with the work schedule worth it from ~100 profiles.

**Account droplet limit: unknown.** I was only cleared to read `/v2/sizes`. 1,000 profiles at 3 h/day
needs ~57 browser nodes, so check the limit and request an increase early `[unverified]`.

### Q2. Waking on demand vs always-on, and the scheduler

**Peak concurrency** `[estimate]` = profiles × active h/day ÷ 16 h active window × 2 peak factor.

| profiles | 1 h/day | 3 h/day |
|---|---:|---:|
| 30 | 4 | 12 |
| 100 | 13 | 38 |
| 1,000 | 125 | 375 |

**Profile state at rest: two layers.**
1. **The user-data-dir bundle (primary).**
   - Release the session (Chromium flushes) and stop the container.
   - `tar` with the caches excluded (`Cache`, `Code Cache`, `GPUCache`, `Dawn*Cache`, `GrShaderCache`,
     `ShaderCache`, `Service Worker/CacheStorage`) **and** `Singleton*`, then compress with zstd.
   - Encrypt client-side with a per-profile data key, wrapped by a master key. DO has no managed KMS
     `[unverified]`, so hold the master key in the control plane's secret store.
   - Upload as `profiles/<id>/gen-<fencing_token>.tar.zst.enc` in Spaces, then move the pointer in
     Postgres with a check on the fencing token.
   - Measured: 5.2 MB raw → 57 KB slim in 0.6 s; restore verified in a different container and after a
     `docker restart` `[hands-on]`.
2. **A context checkpoint (crash insurance).**
   - Every few minutes during a long session, and before release, call
     `GET /v1/sessions/{id}/context`. It returned cookies and localStorage, 1,829 bytes `[hands-on]`.
     Store the result next to the bundle.
   - A fresh container restored perfectly from it via `sessionContext` `[hands-on]`.
   - This layer is also the **only cross-vendor migration path** (cookies + localStorage). IndexedDB and
     service-worker auth state do not travel this way.
   - Overlaying `sessionContext` on a restored dir is `[unverified]`.

**Spaces pricing** `[official-docs]`:
- $5/mo includes 250 GiB stored and 1 TiB outbound;
- then $0.02/GiB stored and $0.01/GiB transferred;
- cold storage $0.007/GiB.

**Node pools.**
- One pool of browser nodes (s-8vcpu-16gb), autoscaled on the schedule.
- One small always-on control pool.
- Bake the 2.66 GB Steel image into a droplet snapshot (snapshots cost $0.06/GB-mo `[official-docs]`).
  A new node then does not pull the image at wake time.

**Placement and stickiness.**
- Correctness does not depend on sticky placement: the bundle is portable, and the profile's IP is its
  proxy's IP, not the node's.
- Prefer the last node anyway: its local LRU bundle cache skips the Spaces download, and its OS page
  cache is warm. Fall back to the least-loaded node.
- Never place two holders of one profile at once (the lease below).

**Per-profile lock.** A Postgres row
`lease(profile_id PK, holder, holder_kind agent|human, fencing_token BIGINT, expires_at)`.
- **Acquire** with `UPDATE … SET fencing_token = fencing_token + 1, holder = $me, expires_at = now() + ttl
  WHERE profile_id = $p AND (expires_at < now() OR holder = $me) RETURNING fencing_token`.
- Every call to the node agent carries the token, and the node agent refuses stale tokens.
- Bundle upload and pointer update are conditional on the token.
- **Human takeover** acquires the same lease as `human`. That bumps the token, so the agent's in-flight
  calls fail closed. The human gets the authenticated viewer.
- The lease must cover the whole container, not only the session. In Steel, creating a session with a
  different config **relaunches Chromium**: hands-on, 1–11 s; the same config reuses it in 0.3 s.
- browser-box's `flock` lane (`gateway/gateway/lock.py`) works only on one host.

**Warm pools.**
- A pre-started generic container saves only the 3–7 s container boot.
- The dominant cost was Chromium launching on a restored profile: 6.5–11 s `[hands-on]`.
- With stock Steel the profile directory is fixed at container start (`/app/api/user-data-dir` mount),
  so a warm container cannot adopt a profile until the per-session `userDataDir` patch exists.
- Recommendation: **schedule-driven pre-wake** (start the profile ~30–60 s before its job). Keep a
  warm pool only after the patch, and only if p95 wake latency matters to a human-facing flow.

**Orchestration options**

| option | gives | costs / gaps | fit |
|---|---|---|---|
| **Docker on droplets + node agent + placer in the fleet service** (recommended) | Full control. Mirrors browser-box ops: per-container memory/CPU caps, per-profile Docker networks, loopback/VPC binding. No new platform. | We build placement, health, drain and reschedule. That is small at ≤ 60 nodes. | Every milestone up to ~60 nodes |
| **Nomad** | Bin-packing, Docker driver, parameterized/dispatch jobs (a natural "wake profile X"), health checks, native service discovery | **BUSL 1.1** (internal use is fine); IBM-era support model: 1.10.x is the last LTS, to 2027-04-30 (developer.hashicorp.com/nomad/docs/ce-license-support) `[official-docs]`. One more system to run. | Revisit if the custom placer grows past ~60 nodes or multi-region |
| **DOKS** | Free control plane; HA $40/mo; nodes priced as droplets; cluster autoscaler; NetworkPolicy for isolation; LB $12/mo `[official-docs]` (digitalocean.com/pricing/kubernetes) | Kubernetes ops weight and pod start overhead. Per-profile block volumes do not scale (bundles still come from Spaces). Overkill at 30. | Plausible at 1,000 if a team already runs Kubernetes |
| **Temporal + NATS** | Durable workflows, timers, schedules, signals (human-in-loop), visibility | **Not a placement system**: it complements the three rows above. NATS use is best-effort telemetry. | Use the pattern; deploy Temporal properly |

### Q3. Durable execution, idempotency, crash recovery, evidence

**What a prior internal fan-out project did, as a counterexample** `[source-code]`: a single fan-out workflow with no entity per profile; a catch-all fallback that silently drops durability and can re-run failed work; retries that never fire because exceptions are returned as values; a Temporal deployment that cannot start as configured; and fire-and-forget NATS publishes. The lesson: deploy Temporal on Postgres, give side-effect activities one attempt, and never fall back silently.

**Fleet design** (pattern taken from an earlier internal trial) `[source-code]`.

Durable execution comes in four layers:
- the job layer,
- the effect ledger, which is the part that prevents double posts,
- crash recovery,
- evidence.

1. **Job layer.**
   - The Hermes task becomes a Temporal workflow with **workflow ID = task ID**, so a duplicate
     submission is rejected.
   - Each profile gets one long-lived *entity workflow* (`profile-<id>`). It receives work as signals,
     runs it serially, owns wake/sleep, and calls continue-as-new periodically.
   - Read-only steps get normal retries. **Side-effect activities get `maximum_attempts=1`** and do their
     own idempotency check.
   - If Temporal is not adopted at milestone 1, a Postgres queue (`SELECT … FOR UPDATE SKIP LOCKED`)
     with the same tables works for 30 profiles.
   - Either way, no silent fallback: if the durable layer is down, the work waits.
2. **Effect ledger** (the part that prevents double posts).
   - **Key:** `effect_key = H(profile_id, task_id, effect_kind, target, content_hash)`, with
     `UNIQUE(effect_key)`.
   - **States:** `intent → committed | uncertain → reconciled`.
   - **Intent:** write the intent row and commit it **before** the click. The trial journals
     `procedure_intent` before the click and never replays it.
   - **Before acting**, check for a prior receipt. A committed or uncertain
     effect is never repeated.
   - **Receipt:** after the click, read the effect back from the destination: the post is on the
     profile's feed with the content hash, or the DM is in the thread. Only then mark it `committed`,
     with evidence.
   - **Crash or timeout between intent and receipt:** mark it `uncertain` and **block replay** until
     reconciliation ("Uncertain submission; owner reconciliation required before
     any replay").
   - **Reconciliation** is itself a read-only job. Found → `committed`. Not found after a grace period →
     either a human decides, or an automatic retry if that platform+effect pair is marked "safe after
     negative read-back".
   - A prior internal trial's own caveat applies: visible confirmation text is an observation, not proof
     ("The framework does not guarantee exactly-once effects in arbitrary websites").
3. **Crash recovery.**
   - Node or container death → the lease expires → the run is marked `interrupted`.
   - The profile restores from the last bundle plus the newest context checkpoint.
   - Any open intents become `uncertain`.
   - JetStream, if used for jobs, delivers at least once: set `Nats-Msg-Id` on publish and keep
     consumers idempotent.
4. **Evidence.**
   - Per effect: screenshot before and after (~200 KB JPEG; browser-box measured a 371 KB full page),
     a gzipped DOM/a11y snapshot, the action log, and the decision record (model, options,
     probabilities).
   - Continuous video or rrweb recording **only on failure or for a sample**. Recording every
     active hour costs orders of magnitude more storage.
   - Retention `[estimate]`: evidence 30 days hot in Spaces, then deleted or moved to cold
     ($0.007/GiB); effect receipts and the audit log for 1 year.
   - At 1,000 × 3 h, evidence ≈ 540 GiB retained, about $6/mo over the Spaces base. Storage is not
     the cost driver.

### Q4. Cost model (labeled estimates; arithmetic in `cost_model.py`)

**Inputs**

| input | value | source |
|---|---|---|
| browser node | s-8vcpu-16gb, $96/mo, $0.14286/hr, 7 slots | DO `/v2/sizes` `[official-docs API]` + slot estimate |
| autoscale utilization | 70 %, plus one always-on node | `[estimate]` |
| control plane | 30: one s-4vcpu-8gb ($48) running API, placer, Temporal and Postgres, plus Spaces $5. 100: + Managed Postgres 2 GiB $30.45. 1,000: 2× control, a Temporal droplet, Managed PG 4 GiB $60.90 ×2 (standby price unlisted), Spaces, LB $12 | DO pricing pages `[official-docs]` |
| static ISP proxy, 1 dedicated IP per profile | $3.00 / $2.75 / $2.50 per IP-month at 30 / 100 / 1,000 | Bright Data ISP: dedicated $3.5@10, $2.75@100, $2.6@500, $2.5@1,000 IPs, 100 GB/IP fair use (tab mapping inferred) `[vendor-claim]`. IPRoyal ISP: $2.70 per 30-day term, $2.40 per 90-day `[vendor-claim]` |
| GLM 5.3 Flash | $0.15 / M in, $0.50 / M out, cache read $0.03 | OpenRouter `/api/v1/models`, 2026-10-10 `[official-docs API]` |
| Jev (jev-1.13.0) | $0.042 / M input, output free; ~1,000 input tokens per multi-question decision | `spikes/system1-models/RESULTS.md` `[hands-on by system1 agent]` |
| Stagehand act/observe/extract on GLM 5.3 Flash | 0.86k–6.4k prompt + 40–480 completion tokens on test pages, so 8k prompt + 80 out assumed for social DOMs → **$0.00124/call** | `<scratch>/spikes/reasoning-models/main.jsonl` `[hands-on by reasoning agent]` + `[estimate]` |
| Browser-Use step on GLM 5.3 Flash | 8.5k prompt + 195–307 completion → **$0.0014/step**. browser-box measured whole tasks at $0.0011–$0.0064 | same file; README L206-211 |
| actions per active browser-hour | 100 (one per ~36 s), plus 6 Hermes plan+verify calls per hour at $0.0029 per task | `[estimate]` |
| mix A, System-1-first (the target) | 50 % Jev, 40 % cached, 8 % LLM act, 2 % BU step → **$0.000148/action** | `[estimate]` |
| mix B, LLM-heavy (cold start, nothing cached) | 30 % Jev, 60 % LLM act, 10 % BU step → **$0.000897/action** | `[estimate]` |
| Steel Cloud | Scale $250/mo incl. $100 credit, $0.08/browser-h, 100 concurrent, 1 h max session; dedicated IP $5; Launch $0 + $0.10/h, 10 concurrent, 15 min sessions; Enterprise custom, 1,000+ concurrent | corpus `https://steel.dev/pricing.md` `[vendor-claim]` |
| Browserbase | Startup $99/mo incl. 500 h, then $0.10/h, 100 concurrent; Developer $20 incl. 100 h, then $0.12/h, 25 concurrent; Scale custom, 250+ concurrent; built-in proxies $10–12/GB | corpus `https://www.browserbase.com/pricing` `[vendor-claim]` |
| Above 100 concurrent (1,000 profiles) | list rates used as a stand-in for custom pricing | `[estimate]` |
| Egress | ≈ $0: inbound is free, outbound is pooled per team (s-8vcpu-16gb includes 6 TB each), overage $0.01/GiB | docs.digitalocean.com/platform/billing/bandwidth `[official-docs]` |

**Line items, $/month** (proxies, models and control plane are the same whichever browser host is used)

| profiles × h/day | browser-h/mo | peak conc. | self-host nodes static (N+spare) | autoscaled | control | proxies | models mix A | models mix B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 × 1 | 900 | 4 | $192 (2) | $122 | $53 | $90 | $29 | $96 |
| 30 × 3 | 2,700 | 12 | $288 (3) | $175 | $53 | $90 | $87 | $289 |
| 100 × 1 | 3,000 | 13 | $288 (3) | $183 | $83 | $275 | $97 | $321 |
| 100 × 3 | 9,000 | 38 | $672 (7) | $358 | $83 | $275 | $290 | $964 |
| 1,000 × 1 | 30,000 | 125 | $1,824 (19) | $971 | $283 | $2,500 | $967 | $3,212 |
| 1,000 × 3 | 90,000 | 375 | $5,472 (57) | $2,720 | $283 | $2,500 | $2,900 | $9,635 |

**Totals, $/month, model mix A.** Each total includes proxies, control and models. The cloud
columns add our agent-runtime workers, because Stagehand and Browser-Use still run on our side.

| profiles × h/day | self-hosted static | self-hosted autoscaled | Steel Cloud | Browserbase | always-on self-hosted (contrast) |
|---|---:|---:|---:|---:|---:|
| 30 × 1 | $364 | $294 | $470 | $359 | $652 |
| 30 × 3 | $518 | $405 | $644 | $597 | $710 |
| 100 × 1 | $743 | $639 | $893 | $852 | $1,895 |
| 100 × 3 | $1,320 | $1,007 | $1,662 | $1,741 | $2,088 |
| 1,000 × 1 | $5,577 | $4,724 | $6,537 (Enterprise, custom) | $7,137 (Scale, custom) | $17,481 |
| 1,000 × 3 | $11,165 | $8,413 | $13,949 (Enterprise, custom) | $15,749 (Scale, custom) | $19,421 |

With mix B, add $67–$6,735/mo to every column; at 1,000 × 3, models become the largest line.

**Reading the tables**
- Infrastructure is not the whole bill. At 1,000 profiles, proxies and models are ~60–75 % of the
  total.
- The share of actions handled by System 1 and the cache is a cost lever as large as the choice of
  hosting.
- Vendor-cloud caveats that change the arithmetic:
  - **Steel Cloud Scale caps a session at 1 h.** 3 h/day therefore means ≥ 3 sessions per profile per
    day, each restoring the profile.
  - **Steel Cloud deletes a profile unused for 30 days** and caps it at 300 MB `[official-docs,
    docs.steel.dev/overview/profiles-api/overview]`.
  - **Steel Cloud dedicated IPs** are $5/IP, 25 self-serve, of unstated type (datacenter or ISP
    `[unverified]`). Bring-your-own proxy costs nothing at Steel `[official-docs]`.
  - **Browserbase sessions max out at 6 h**, and Contexts **never expire** `[official-docs]`.
  - **Browserbase supports `type: "external"` BYO proxies**, so the same static ISP IP can follow a
    Browserbase-homed profile `[official-docs]`. Its built-in residential proxies, at $10–12/GB and
    best-effort geography, are the wrong tool for a sticky identity.

### Q5. Observability and operations

**Health, per layer**
- **Node agent:** a heartbeat with free slots, disk, image digest and running containers.
- **Container:** `/v1/health`, as in browser-box `compose.yml`.
- **Browser:** a CDP `Browser.getVersion` ping, the guard attached (browser-box makes the guard its own
  `status` component), and the session status.
- **Proxy:** before every wake, fetch a public IP-echo URL **through the profile's proxy** and require
  it to equal the pinned IP. "Same IP every time" is otherwise unchecked.
- **Fingerprint:** hash the navigator/screen/WebGL surface at session start and compare it with the
  pinned hash. Drift means a stealth regression or an unpatched Steel image. The spike showed the
  stock image drifts on every launch.
- **Login state:** a deterministic per-platform probe, for example the System 1 `login_wall`
  question. The system1 spike got `login_wall` 0.95 / blocker 0.98 on a login page `[hands-on by
  system1 agent]`.

**Keep-warm**
- **Steel Cloud:** needed. Touch dormant profiles inside 30 days `[official-docs]`.
- **Browserbase:** not needed at the infrastructure level `[official-docs]`.
- **Self-hosted:** not needed; retention is our own policy.
- **Site-side session expiry** is real everywhere: Browserbase's own docs cite ~30-day cookie expiry.
  So the scheduler runs a per-platform "visit the home feed" job at a cadence that the
  social-platforms dossier should set.

**Alerts that page a human** (via NATS or webhook into Hermes/Slack)
- Any checkpoint: CAPTCHA, login wall, 2FA prompt, "suspicious activity" interstitial. The profile is
  paused, and the alert carries an authenticated viewer link.
- An `uncertain` effect older than its grace period.
- Proxy IP drift, or fingerprint drift.
- A failed bundle upload. The profile is held, not slept.
- Wake p95 above its SLO.
- Spend per profile per day above its cap.
- A node out of slots, or disk above 80 %.

**Dashboards**
- Profiles by state (sleeping / waking / active / paused-needs-human / quarantined).
- Node slots and utilization.
- Wake latency p50/p95.
- **Action share by engine** (System 1 / cache / LLM act / Browser-Use). This is the "90 %" KPI.
- Cost per profile per day.
- Checkpoint rate per platform.
- Effects committed / uncertain / reconciled.

**Audit trail per profile**
- Append-only rows in Postgres: lease holder and token, wake/sleep, every effect (intent, receipt,
  evidence keys), and every decision record.
- Evidence objects go in Spaces.
- A human-readable daily rollup per profile is written into the Obsidian vault (Justin's memory rule).
  Postgres stays the system of record.

### Q6. Security

**What carries over from browser-box** `[source-code @4c837a3]`
- The URL classifier `security.py`, and the browser-wide CDP `Fetch` guard `guard.py`. Run **one guard
  per browser, inside the node agent**, rather than one central guard: local CDP keeps latency low, and
  375 remote CDP sockets is fragile.
- The guard is still needed with a proxy. Chromium sends loopback directly, outside the proxy, and
  Steel's unauthenticated API listens on the container's own loopback. The 2026-09-22 redirect exploit
  (a page reads `127.0.0.1:3000/v1/sessions`) is exactly that path.
- Steel's own launch flags include `--remote-allow-origins=*` (`cdp.service.ts` staticDefaultArgs)
  `[source-code]`.
- The deny list must add the fleet's own public hostnames and droplet IPs. Through the proxy, a page
  could otherwise reach our own public endpoints.
- "Tools fail closed when the guard is down" carries over unchanged.

**What changes**
1. **Isolation between clients.**
   - **Network.** One container per active profile, on its own Docker network (no shared bridge, no
     inter-container traffic). The Steel port is bound to the node's VPC address or a unix socket
     reachable only by the node agent. A DO Cloud Firewall allows node-agent traffic only from the
     control-plane tag.
   - **No raw access for Hermes.** Hermes profiles never get raw CDP or Steel URLs. They get the fleet
     gateway's high-level tools (act, extract, task, status). The live viewer is proxied by the gateway
     behind a short-lived human lease.
   - **Why this matters.** Steel has no authentication of its own (`api/src`: 0 matches for
     authorization, bearer or apikey) `[source-code]`. Anyone who reaches the port drives a logged-in
     client account.
2. **Tokens.**
   - **One opaque token per Hermes profile** (see the hermes-packaging dossier). The gateway maps it to
     a tenant, a set of identities and their scopes (read / draft / publish / dm / takeover), each with
     an expiry.
   - Tokens are stored hashed and rotated.
   - Model and proxy credentials stay in the control plane and the node agent, never in a Hermes
     profile. This mirrors an earlier internal trial, where "the owner token and model provider keys stay in the
     controller".
3. **Egress.** browser-box allows the public internet. The fleet should allow **only the profile's proxy
   endpoint (IP:port)** from that container's network, enforced in DOCKER-USER/nftables per network.
   - **Leaks closed.** The droplet IP cannot leak through a direct connection. WebRTC is already pinned
     to `disable_non_proxied_udp` (`cdp.service.ts:880-881`) `[source-code]`.
   - **DNS caveat.** With an HTTP proxy, name resolution happens at the proxy. The guard's local DNS
     check (`require_public_addresses`) can disagree with what the proxy resolves, so it is advisory.
     The network rule is the real control.
   - **Bypass list.** `PROXY_INTERNAL_BYPASS` adds hosts that skip the upstream proxy; it defaults to
     `0.0.0.0` and `HOST` (`api/src/utils/proxy.ts:28-40`). Keep it empty otherwise.
4. **Profile data at rest.** Bundles and context checkpoints are client-side encrypted (they contain
   session cookies), with per-profile keys. Browserbase also encrypts Contexts at rest per context
   `[official-docs]`.
5. **Prompt-injection blast radius.**
   - Browser-Use and Stagehand read hostile pages while logged in as a client.
   - The browser-box warning applies per profile: "after a session login, a task can act as that
     login" (docs/security.md).
   - Side effects are therefore gated by the effect ledger, per-platform rate limits and scope checks in
     the gateway, not by the model.

---

## 3. What the open-source projects give us vs what the fleet must build

| need | self-hosted Steel @1131a02 / image 0.5.3 gives | Browserbase gives | fleet must build |
|---|---|---|---|
| A browser per profile | One Chromium per container, REST + CDP on one port | Managed sessions; 6 h max; concurrency by plan | Node agent: run/stop per-profile containers with caps and networks |
| Persistent state | `persist:true` → fixed `/app/api/user-data-dir`. `userDataDir` param ignored (precedence bug). No profiles API (that is Cloud-only). `GET /sessions/{id}/context` + `sessionContext` restore works | Contexts (`persist:true`), never expire, encrypted at rest | Bundle pipeline: slim tar, strip `Singleton*`, encrypt, versioned upload, conditional pointer, LRU cache. Plus context checkpoints |
| Same fingerprint every time | **No.** Random per launch; no REST `fingerprint` field; hooks run too late | Managed stealth by plan (not my scope) | **Patch Steel**: accept and persist a pinned fingerprint, honor per-session `userDataDir`. Store the fingerprint in the profile record. Check drift every wake |
| Same IP every time | `proxyUrl` per session; WebRTC non-proxied UDP disabled | `type:"external"` BYO proxy per session | Proxy inventory (one static ISP IP per profile), credentials vault, IP-echo check before each wake |
| Timezone/locale consistent with the IP | `timezone` param; otherwise a network lookup that flipped UTC/NY across launches | geolocation by proxy | Pin timezone/locale/UA/dimensions per profile at creation |
| Headful / human login | Live viewer, but headful launch fails in the stock image (no dbus/Xvfb) | Live view | Custom entrypoint (Xvfb + dbus) if headful is required; authenticated viewer proxy; human lease |
| Auth / multi-tenant | **None** on REST, CDP or viewer | API key per project | Gateway with per-profile scoped tokens; network isolation per container |
| Session lifetime | `timeout: 0` (no idle reaping) | Timeouts and keep-alive | Idle reaper; sleep after the job; max wall time per wake |
| Scheduling / placement | — | — | Placer with capacity slots, sticky preference, drain, reschedule |
| One holder per profile | — (browser-box has a single-host `flock`) | Docs only *advise* against concurrent use of one Context | Postgres lease with fencing token, shared by agents and humans |
| Durable jobs, no double posts | — | — | Temporal (or a Postgres queue) + effect ledger + read-back receipts + reconciliation |
| Evidence and audit | Steel log storage (duckdb), screenshots via CDP | Session replay/recordings | Evidence writer to Spaces, retention rules, per-profile audit log, Obsidian daily rollups |
| Ops | `/v1/health` | Dashboard | Metrics, alerts (checkpoints, drift, uncertain effects), dashboards incl. the System-1 share KPI |

---

## 4. Operating notes for a Hermes agent (feeds the skills)

**Call shapes.** The Hermes skill sees only the fleet gateway; the names below are proposals.
- `profile.status(id)` returns `{state: sleeping|waking|active|paused_needs_human|quarantined, lease, last_wake, login_ok}`.
- `profile.run(id, task)` is **submit-then-poll**. It returns a `task_id` at once; poll
  `task.status(task_id)`. Waking takes ~15–20 s cold, so never block a tool call on it (Hermes MCP's
  default tool timeout is 300 s, per the hermes-packaging dossier).
- Every side-effecting step carries an `effect_key`, or the gateway derives one. A repeat returns the
  existing receipt instead of acting again. `uncertain` means **stop and report**; do not retry.
- `needs_human` (checkpoint, login wall, 2FA) means the profile is paused. Report the viewer link to a
  person, and never type credentials.

**Steel gotchas for whoever builds and runs the node agent**
1. **Never send `persistProfile` or `profileId` to self-hosted Steel.** HTTP 200 does not mean they were
   honored. Use `persist:true` with a per-profile directory mounted at `/app/api/user-data-dir` until the
   patch lands.
2. **`userDataDir` in the body does nothing** on stock 0.5.3 / 1131a02.
3. **Strip `SingletonLock`, `SingletonSocket` and `SingletonCookie` before restoring** a directory into
   another container. Otherwise the session is created "successfully" but logged out.
4. **Release before snapshotting.** `POST /v1/sessions/release` closes Chromium so it flushes cookies
   (1–3 s). Then stop the container, then tar.
5. **Always pin `timezone`, `dimensions` and the fingerprint** (once patched). Pinning `userAgent` alone
   turns fingerprint injection off and exposes the host's real core count and SwiftShader WebGL.
6. **A session create with a different config relaunches Chromium** and resets every tab. The same
   config reuses the browser (0.3 s). One lease covers the whole container.
7. **Do not create two sessions on one container concurrently.** There is one `activeSession`.
8. **Headful needs a custom image.** Stock `headless:false` returns 500.
9. Set `NODE_OPTIONS=--unhandled-rejections=warn`. browser-box reproduced a whole-server crash on an
   unhandled rejection (compose.yml comment, 2026-09-23).
10. **Export context (`GET /v1/sessions/{id}/context`) every few minutes on long wakes.** It is the
    crash checkpoint and the cross-vendor migration format.

**Limits to plan around**
- **Steel Cloud** caps sessions at 1 h on Scale and 15 min on Launch, deletes profiles after 30 days
  unused, caps a profile at 300 MB, and allows 25 self-serve dedicated IPs.
- **Browserbase** caps sessions at 6 h and returns 429 above plan concurrency or the per-minute
  session-creation limit.
- **DO** account droplet limit: unknown (check it).

---

## 5. Risks and unknowns

1. **Unmeasured items.**
   - **Social-site RAM and CPU.** All spike pages were light. If Facebook/Instagram/TikTok/X need
     2.5–3 GiB, slots per node drop by about a third. The first live canary must measure it.
   - **amd64 droplet numbers.** Everything here is arm64 Docker. Wake latency and memory on a real
     droplet are unmeasured.
   - **The headful cost delta.** Unmeasured; the stock image cannot launch headful at all.
2. **The fingerprint patch is a fork liability.** Steel ships often (`api` 0.5.3). We maintain a patch
   to `sessions.schema.ts`, `sessions.controller.ts` and `session.service.ts`, or upstream it.
   - Until then, every launch is a new device to the sites.
   - The generated fingerprints are also internally inconsistent: a phone GPU on "Linux x86_64", an
     `800x600` screen beside a 1920x1080 window, a UA version behind the engine's Chromium 152. The
     antidetect dossier must judge whether Steel's generator is usable at all, or whether real-hardware
     values should be pinned instead.
3. **Shared-CPU noise.** Basic droplets are shared vCPU; page-load bursts hit the cap in the spike (p90
   at 1.2 CPUs). Dedicated c-/g- sizes cost 1.5× per slot.
4. **Proxy pricing and provenance.**
   - Per-IP prices are vendor claims, and Bright Data's shared/dedicated tab mapping was inferred.
   - ISP pools have known provenance problems; one 2026 comparison ties a provider's pool to a botnet
     `[third-party]`.
   - The 100 GB per-IP fair-use cap is fine at the estimated ~27 GB/profile-month `[estimate]`.
5. **Vendor custom pricing at 1,000 profiles.** Steel Enterprise and Browserbase Scale are "contact
   sales". The tables use list rates as stand-ins.
6. **The Temporal adoption cost is real.** A dev-grade Temporal deployment is not enough for this fleet.
   Running Temporal on Postgres (or paying for Temporal Cloud, whose price was
   not researched) is new ops work. A Postgres queue is the fallback for the first milestone.
7. **Cross-vendor migration loses state.** Moving a profile between Steel and Browserbase carries cookies
   and localStorage only. IndexedDB and service-worker state, and the fingerprint, change, and some
   platforms bind login to them. Browserbase's create-context response includes `publicKey` /
   `cipherAlgorithm` (AES-256-CBC) for an encrypted user-data-dir, but no current doc page describes
   uploading one `[unverified]`. **So pick a profile's home infrastructure at creation, and treat
   migration as a re-login event.**
8. **The DO account droplet limit, and Spaces lifecycle rules** for retention, were not checked
   `[unverified]`.
9. **Bundle growth.** Steel Cloud's 300 MB cap hints at how large a heavy social profile can get. Large
   bundles slow every wake (download + decrypt + extract). The LRU cache on the last node, from sticky
   preference, mitigates this.
10. **browser-box itself.** Its `session` tool's "persistent logged-in session" is not persisted beyond
    the container's lifetime (finding 5b). It is out of scope to change here, but the box's owner
    should know.

---

## 6. Sources

**Local code and data (pinned)**
- `steel-browser@1131a02`:
  - `api/src/services/session.service.ts` L67, L104-105, L180-183
  - `api/src/modules/sessions/sessions.schema.ts` L28-89 (no `fingerprint`, `persistProfile` or `profileId`)
  - `api/src/modules/sessions/sessions.controller.ts` L8-60
  - `api/src/services/cdp/cdp.service.ts` L600-640 (browser reuse), L704-790 (fingerprint generation; hooks after destructure), L860-960 (launch flags: `--password-store=basic` L898, WebRTC L880-881, `--remote-allow-origins=*`)
  - `api/src/utils/proxy.ts` L20-50
  - `api/src/env.ts`
  - `api/entrypoint.sh`
  - `api/src/steel-browser-plugin.ts` L37
- Local image `ghcr.io/steel-dev/steel-browser-api:latest`, `sha256:7a161b95e8a9…`, created 2026-09-16. Compiled `build/services/session.service.js:90`, `build/services/cdp/cdp.service.js:616-634`.
- `browser-box@4c837a3`: `README.md` (L19, L96-107, L144, L206-211, L418-436, L573-575), `compose.yml`, `CHARTER.md`, `docs/architecture.md`, `docs/security.md`, `gateway/gateway/{lock.py, steel.py L98-106, guard.py, security.py}`.
- A prior internal fan-out project (private; file and line references withheld).
- The Jev Workforce trial (private; file and line references withheld).
- `temporalio/docker-builds@8ea563e` (2026-01-06), `docker/auto-setup.sh` L7, L76-95, read via `gh api`.
- Corpus, fetched 2026-10-09:
  - `https://steel.dev/pricing.md`
  - `https://docs.steel.dev/llms-full.txt` (profiles-api overview ~L13340-13370; dedicated-ips L14239+; BYOP L16044-16056)
  - `https://www.browserbase.com/pricing`
  - `https://docs.browserbase.com/platform/browser/core-features/contexts.md`
  - `https://docs.browserbase.com/platform/identity/proxies.md`
  - `https://docs.browserbase.com/reference/api/create-a-context.md`
  - `https://docs.browserbase.com/platform/browser/long-sessions/timeouts.md`
  - `https://docs.browserbase.com/optimizations/concurrency/overview.md`
- Other agents' data:
  - `fleet/research/spikes/system1-models/RESULTS.md` (Jev price and token counts)
  - `<scratch>/spikes/reasoning-models/main.jsonl` (GLM 5.3 Flash Stagehand/Browser-Use token counts)
  - `fleet/research/dossiers/hermes-packaging.md`
- This spike: `fleet/research/spikes/scale-infra/{RESULTS.md, run_spike.sh, run_spike2.sh, probe.mjs, cost_model.py, raw/}`.

**Web (fetched 2026-10-09 / 10)**
- DigitalOcean API `GET https://api.digitalocean.com/v2/sizes` (read-only; subset saved in `raw/`).
- https://www.digitalocean.com/pricing/spaces-object-storage ($5, 250 GiB, 1 TiB; $0.02/GiB; $0.01/GiB; cold $0.007).
- https://www.digitalocean.com/pricing/kubernetes (free control plane; HA $40; LB $12).
- https://www.digitalocean.com/pricing/droplets (transfer allowances; snapshots $0.06/GB-mo; backups 20/30 %).
- https://docs.digitalocean.com/platform/billing/bandwidth/ (pooled per team; $0.01/GiB overage; inbound free).
- https://docs.digitalocean.com/products/droplets/details/pricing/ (per-second billing, 60 s minimum, 672 h cap; "last verified 25 Aug 2026").
- https://www.digitalocean.com/pricing/managed-databases (PG 1 GiB $15.15, 2 GiB $30.45, 4 GiB $60.90).
- https://openrouter.ai/api/v1/models (z-ai/glm-5.3-flash $0.15/$0.50 per M; fetched 2026-10-10 02:57 UTC).
- https://iproyal.com/pricing/isp-proxies/ (ISP $2.70 / 30 d, $2.55 / 60 d, $2.40 / 90 d; dedicated) `[vendor-claim]`.
- https://brightdata.com/pricing/proxy-network/isp-proxies (per-IP tiers; 100 GB/IP fair use) `[vendor-claim]`.
- https://developer.hashicorp.com/nomad/docs/ce-license-support (Nomad CE BUSL; 1.10.x LTS to 2027-04-30) `[official-docs]`.
- https://community.temporal.io/t/feedback-request-retiring-temporalio-auto-setup-docker-image/165 and https://community.temporal.io/t/future-sqlite3-support/5915 `[third-party: vendor forum]`.
- Proxy price comparisons, used only as a cross-check: https://research.aimultiple.com/isp-proxies, https://use-apify.com/blog/iproyal-pricing-plans-2026 `[third-party]`.
