# Cross-dossier consistency review

Role: consistency critic for the System 1 browser fleet research. Date: 2026-10-10. Branch `feat/system1-browser-fleet`.
Scope: the 11 dossiers in `fleet/research/dossiers/`, the 11 adversarial reports in `fleet/research/verification/`, and the draft `fleet/DECISIONS.md` (D1-D17).

This file does not re-verify anything the verifiers already checked. It cross-reads them, decides which side of each disagreement the evidence supports, and lists what is still unsettled. Nothing here was run on a droplet, in a container, or in a browser.

## 0. How to read this

Method.
- Read BRIEF.md, all 11 dossiers, all 11 verification reports and DECISIONS.md in full.
- Spot-checked the load-bearing disagreements against the verifier tables and the dossier line they target (cited as file:line). Where a source clone was already on disk I grepped it (for example Steel's launch flags in `cdp.service.ts`). No web fetches were needed to break a tie.
- Re-read `spikes/scale-infra/cost_model.py` to confirm which assumptions sit behind the D12 cost table.

Not done, and why.
- `verification/claims/*.json` (7 files) and the raw spike outputs under `research/spikes/` were not re-read. The verifier reports quote them; I relied on those quotes. Any number below that I did not see in a verifier row or a dossier line is marked `inference`.
- Nothing needing Docker, a browser, the Hermes CLI, or a droplet was attempted. Those items are listed in section 6 as "unverifiable (needs hands-on on a droplet)".

Provenance tags follow BRIEF.md: `hands-on`, `source-code`, `official-docs`, `vendor-claim`, `third-party`, `unverified`, plus `inference` for my own reasoning from those.

Severity.
- DESIGN: changes a rule, number or component the design depends on.
- DETAIL: wording or count; the design survives.

Systemic finding that explains most of section 3: **the dossiers were not updated after verification; only DECISIONS.md carries corrections, and only some of them.** Anyone who reads a dossier alone, or builds from `existing-assets.md` or `scale-infra.md`, inherits claims the verifiers refuted. The dossiers need an "as verified" pass or a banner pointing at the verifier file.

---

## 1. Bottom line

1. **"Pinned persona" means two different things, and the weaker one is what is actually available.** With Steel's injection off, the pinned values are UA, timezone, locale and viewport. Core count, GPU string, canvas hash and (until fixed) screen stay host-real, and are identical for every identity on a node. D3, D4 and D9 each promise more than that; the three dossiers that discuss it (steel, antidetect-proxies, scale-infra) propose three different mechanisms (C-01, C-02).
2. **Two of the three lease/claim designs the fleet would copy are unsafe as written** (scale-infra's lease SQL cannot implement takeover; an earlier internal job-claim design is only safe serially). D12 still points at that design as the pattern (C-14).
3. **D8's "~3% runaway" understates the act defect rate by more than 2x** (7-8% on click acts on a 6k-token page, all concentrated on two provider/task pairs) (C-22).
4. **D4 carries a wrong count (7/7 vs 6/6), a refuted flag (`--lang` on Linux), an unproven cause (headful WebGL) and omits the root/no-sandbox/site-isolation finding and the fabricated session stubs** (section 3b).
5. **D2 states X's per-app ceilings as fact.** They are legacy Pro-plan columns carried onto a pay-per-use page; "shared by all clients" is an inference. The binding limits for client accounts are per-account (C-28).
6. **The D12 cost table is sized as if every identity needs a browser for the stated hours**, while D2 says most social work needs none, and it contains no X API usage fees. It also credits a 40% "cached" action share to a cache that does not exist on Steel (C-05, C-17).
7. **The tool surface in D17 conflicts with the one in hermes-packaging** and mixes read and write operations inside `identity`, which breaks the `readOnlyHint` replay rule D1 depends on. D17 references an `ARCHITECTURE.md` and a fleet charter that do not exist (C-16).
8. **Stagehand v4's resident extension trips `isAutomatedWithCDP`; the stagehand dossier still says "unknown".** D6 handles this as an open question, correctly, but omits the measured mitigation and that Browser-Use's own actor/coordinate-click paths also trip it (C-13).
9. **The weekly "keep-warm" login probe is justified by a Meta dormancy trigger that applies only to empty accounts**, and the probe itself adds ToS-exposed scripted access (section 4, O-12).
10. **Data handling is unaddressed.** Logged-in client page text and screenshots go to OpenRouter providers (GLM) and to four System 1 vendors. 29 GLM endpoints are zero-data-retention (ZDR) listed, but the bench's main provider is not, and the bench numbers do not transfer. This is a Justin decision, not an engineering one (Q-07).
11. **D16's export-leak guard is still a to-do, and separate exposure questions about public companion repos are tracked privately.** Nothing in `fleet/` should merge before that is closed (Q-09, Q-10).
12. **Process breach.** Two spikes ran a browser on the maintainer's workstation instead of a container (section 7).

---

## 2. Contradictions between dossiers

Format per item: the two (or more) positions with their sources, what the evidence supports, and the effect on DECISIONS.md.

### C-01 How to pin a fingerprint on Steel: fork, wrapper, or injection (DESIGN)
- steel.md (lines ~337-350): "a small fork, carried until upstream accepts it" that accepts a `fingerprint`/`personaId` on `POST /v1/sessions`, drops the cursor `div`, filters `--disable-gpu`.
- scale-infra.md (~514, ~577): "Patch Steel" and calls the fingerprint patch a fork liability.
- antidetect-proxies.md (~346-358): two routes, a fork/plugin calling `sessionService.startSession({fingerprint})`, or bypass with `skipFingerprintInjection` + `userAgent`; and says `launchMutators` cannot pin it.
- Verifier SCA-3: "must ship a patched image" is a design choice, not a proven necessity; the no-fork route (REST `userAgent`/`dimensions`/`timezone`/`skipFingerprintInjection`, or CDP injection from the node agent) is `unverified` because nobody tested it.
- Evidence supports: no-fork is viable for UA/TZ/viewport (`hands-on`, one launch, E3; stability across launches of that config was not re-measured). Fork is only needed for hardware-level values, and only if the fleet decides to spoof them (C-02).
- DECISIONS: D4 already adopts the no-fork route in practice ("turns Steel's fingerprint injection off and applies the pinned persona natively") but the same dossiers that justify it (and the cost/risk text in D4's escape hatch) still assume a fork. Pick one in the architecture doc (O-01).

### C-02 What a pinned persona actually delivers (DESIGN)
- steel.md headline: UA-pinned scored "Normal" on browserscan and 0% headless on creepjs.
- Verifier STE-10: stable but host-derived: `hardwareConcurrency` equals host cores, SwiftShader, screen still 800x600 even with `dimensions` pinned (E3), empty UA-CH brands, canvas hash identical across all sessions on a host. Also (missed issue 4) UA says `Linux aarch64` while `navigator.platform` says `Linux x86_64` in the injected case.
- D3 says every wake "applies the same values and checks them"; D4 itself notes the cross-identity linkability.
- Evidence supports: UA-pinned is consistent over time for one identity, and linkable across identities on one node. Those are two different properties. The pin gives continuity (what Justin asked for), not unlinkability between clients.
- Effect: D3's "persona" list should split into values the fleet can pin (UA, TZ, locale, viewport) and values it cannot yet (cores, GPU, canvas, screen, UA-CH). D4's "different clients on different nodes until it does" is a real cost lever: a node holds about 7 identities, so a one-client-per-node rule changes the D12 table. The table does not model it.

### C-03 Release flush: 1-3 s versus a 30 s timer (DESIGN)
- scale-infra.md:547-548: "`POST /v1/sessions/release` closes Chromium so it flushes cookies (1-3 s). Then stop the container, then tar."
- steel.md:48-49: no CDP flush command; Steel's release leaves `Singleton*`; cookies written 2 s before release were lost, 40 s kept (also browser-use.md:180, 376).
- Verifier BRO-6/EA-5: the 30 s Chromium cookie commit interval is `source-code` (Chromium main, not Steel's pinned Chrome build); only 2 s (lost) and 40 s (kept) were measured; the exact threshold is not.
- Evidence supports the steel/browser-use side. scale-infra's 1-3 s is unsupported and would corrupt every snapshot taken that way.
- DECISIONS: D4 has it right (wait >= 31 s since the last auth change, journal, `Browser.close`, then release). Two gaps remain. (a) Social sites write cookies continuously, so "since the last auth change" cannot be observed; the wait is a floor, not a guarantee (BRO-6). (b) The >= 31 s hold per sleep is container time that the D12 slot-hour accounting does not include.

### C-04 Per-profile `userDataDir` on self-hosted Steel (DETAIL, resolved)
- browser-use.md Q4 sample and box `steel.py` send per-profile `userDataDir` / `persistProfile` / `profileId`.
- steel.md, scale-infra SCA-2, BRO-6: the value is ignored (`session.service.ts:180-183`, precedence bug); `persistProfile`/`profileId` are ignored with HTTP 200; everything maps to one fixed directory.
- Evidence (`source-code`, `hands-on`): ignored. D4 is right (one container per volume). Note the box's own `steel.py` sends the ignored fields, so the fleet must not copy that code path.

### C-05 Stagehand action cache: where it exists and what the cost model assumes (DESIGN)
- browserbase.md:36-40: the v4 cache is "the one capability the fleet can neither build nor buy elsewhere"; it is server-side, Browserbase-only. The same dossier lists a fleet-built replay cache or pinning v3 as alternatives (verifier browserbase V-1: "neither build nor buy" is overstated).
- reasoning-models.md:221: "Stagehand's own action cache, which skips the LLM on a repeated act, is where cost savings come from."
- stagehand.md: v4 has no local cache; v3's `cacheDir` cache replays wrong clicks and stale agent answers with `success:true`.
- scale-infra `cost_model.py`: mix A assigns 40% of actions to `cached`, commented "Stagehand cache hit / deterministic replay".
- Evidence (`source-code`, npm 4.2.0 dist, BB-4, S1-05): no local cache on Steel. Savings can only come from a fleet-built L1 replay (D5), which is unbuilt and unmeasured.
- Effect: the 40% in mix A is the fleet's own L1 replay hit rate assumed, not a Stagehand feature. D12's table should say so, and the "System-1-first" mix labels should read as hypotheses, as D7 already says for the 90% target. Browserbase's server cache is a weak reason to choose Browserbase (D11 says this correctly).

### C-06 Option cap: 180 versus 255 (DETAIL, resolved)
- browser-use.md and system1-models.md use "Jev's ~180"; RESULTS calls 255 "Decider's" cap.
- Verifier BRO-4 (`hands-on`): 256 options returned HTTP 400, 255 returned 200. 180 is jev-automation's client constant `MAX_ELEMENTS` (`core/elements.ts:34`). S1-08: Jev, Clef and Perplexity cap at 255; OpenAI's cap is unstated.
- D7 treats 180 as the working step size, which is fine, but should not call it a provider limit.

### C-07 `rerun_history` and "replay with no LLM" (DESIGN)
- system1-models.md:309 and browser-use.md:122 treat `rerun_history` as a no-LLM replay tier with self-heal.
- Verifier system1-models V-12 (`source-code` @c75e847): `rerun_history` always ends with `_generate_rerun_summary(...)`, which uses the agent's LLM if no summary LLM is given. One generative call per rerun.
- Evidence supports the verifier. Effect on D5: Browser-Use replay cannot count toward the "zero generative calls" System-1 share unless a no-op `summary_llm` is supplied. The share metric in D7 (L0 + L1 + L2) does not use `rerun_history` today, so D5/D7 are unaffected as long as L1 stays the fleet's own cache.

### C-08 `PROXY_INTERNAL_BYPASS`: add to it, or keep it empty (DETAIL)
- stagehand.md:26, 463, 520: use `PROXY_INTERNAL_BYPASS` (or loopback) so the CDP URL and extension traffic skip the identity proxy.
- antidetect-proxies.md:271: "Keep that list empty."
- scale-infra SCA-14 / steel verifier: it defaults to `0.0.0.0` and `HOST`; Chromium bypasses loopback implicitly.
- Evidence: both statements rest on `source-code` reading and neither was tested with a proxy in the loop (steel verifier item 10). Resolve by design: because the fleet's proxy is a node-local forwarder on loopback, no bypass entry is needed and the antidetect rule (keep it empty) should win. Mark `unverified` until a droplet run.

### C-09 Browser-Use proxy settings "ignored on remote CDP" (DETAIL)
- browser-use.md:43, 318: `ProxySettings.server` is ignored on a remote CDP browser.
- Verifier BRO-11: source confirms `--proxy-server` exists only in launch args, but the author's own later probe recorded `proxy_ignored: false` (unexplained, not reported in the dossier). Also, giving Browser-Use proxy credentials on a remote session turns on Fetch interception of every request on the focused tab.
- D10/D6 already say: proxy only on the Steel session, via the credential-less forwarder. Consistent. The "ignored" wording is unproven, not wrong in effect.

### C-10 Locale pinning with `--lang` (DESIGN)
- antidetect-proxies.md:79, 223, 277, 359, 378, 409 and D4/D10: pin locale natively with `--lang`; Stagehand's `locale` maps to `--lang`.
- Verifier antidetect-proxies V-1 (`source-code`, Chromium `ui_base_switches.h`): "On Linux, this flag does not work; use the LC_*/LANG environment variables instead."
- Evidence: refuted on Linux. DigitalOcean droplets are Linux. Use `LANG`/`LANGUAGE` for UI locale and `--accept-lang=<list>` or the `intl.accept_languages` pref for Accept-Language and `navigator.languages`. Stagehand's `locale` option does nothing useful here. No spike measured locale (every run was en-US).

### C-11 Why headful Steel has no WebGL (DETAIL)
- steel.md patch item 6 and antidetect: `--disable-gpu` is the cause; filter it with `FILTER_CHROME_ARGS`.
- Verifier STE-11 / AP-8: the effect is real, the cause is not proven. A vanilla headful run without `--disable-gpu` on a GPU-less host also had no WebGL; WebGL appeared only with explicit SwiftShader flags. Steel also cannot launch headful at all without Xvfb and dbus (SCA-2c).
- D4 says "SwiftShader WebGL instead of Steel's blanket `--disable-gpu`". Correct to: headful needs Xvfb + dbus in the wrapper, and WebGL needs explicit SwiftShader opt-in flags; whether filtering `--disable-gpu` is needed is untested.

### C-12 Stagehand v4 on a vendor/foreign kernel (DESIGN)
- antidetect-proxies.md:206 and D9: Stagehand 4.2.0 cannot run on CloakBrowser (146: "Method not available"); D9 generalises to "not usable with Stagehand v4".
- Verifier AP-1: the real rule is a version threshold. `Extensions.getExtensions`/`loadUnpacked` are absent at <= 146, present but gated at 147-148, and ungated from Chromium 149 (`source-code`, upstream commit `dddf05b0e6`). Stagehand also needs the extension on the browser host's filesystem, a CDP URL that resolves inside the browser, and a `--remote-allow-origins` that admits the extension's origin. It worked on Debian Chromium 152.
- Effect on D9: "not usable with Stagehand v4" is true for the free 146 build only. State the rule as "needs Chromium >= 149 and the origin flag". A newer licensed kernel, if one exists, would lift the restriction. Steel's source does set `--remote-allow-origins=*` and `--load-extension`/`--disable-extensions-except` (`cdp.service.ts:860-870`), so Steel itself satisfies the flag side (`source-code`).

### C-13 Is Stagehand v4 detectable? (DESIGN)
- stagehand.md:432, 454, 473, 513-515: "Anti-detection impact unknown", `unverified`, handed to the anti-detect workstream.
- antidetect-proxies.md:49, 162, 440 and AP-2/AP-3 (`hands-on`, n=1 per condition): on stock Chromium 152 Stagehand v4 trips `isAutomatedWithCDP`; the extension stays resident after `close()` and keeps tripping new tabs until `Extensions.uninstall` or a browser restart (a CDP-loaded extension is not persisted). Browser-Use 0.13.11 attach + navigate + state summaries did not trip it, because default Agent clicks use `force=True`; the MCP coordinate click and the actor API do trip it.
- Evidence supports antidetect over stagehand. Whether Meta/TikTok/X weigh this signal is `unverified`.
- Effect: update the stagehand dossier. D6 should add the measured mitigations (uninstall the extension after the session or restart the browser), the Browser-Use caveat (do not use actor API or coordinate clicks on sensitive sites), and list "minimal CDP executor" as a first-class candidate for L1/L2 on logged-in identities (O-02).

### C-14 Lease and job-claim safety (DESIGN)
- scale-infra: per-profile Postgres lease statement `UPDATE ... SET fencing_token = fencing_token + 1 ... WHERE profile_id = $p AND (expires_at < now() OR holder = $me)` with human takeover acquiring the same lease.
- existing-assets: an earlier internal job-claim design, described as never leasing a job whose profile is already leased.
- Verifier SCA-10 (`hands-on`, SQL run verbatim in local SQLite): every renewal bumps the token (1 -> 2 -> 3), and a human acquiring while the agent lease is unexpired gets 0 rows, so takeover is impossible as written and a heartbeat would invalidate its own holder's fencing token. EA-7: true serially only.
- Evidence supports the verifiers. Both are unsafe under concurrency as written.
- DECISIONS: D12 says "leases with fencing tokens (one writer per identity: an agent or a human, never both)" and points to an earlier internal job-claim design. Needed: a DB-enforced uniqueness constraint on the active lease per identity; separate statements for acquire, renew (does not bump the token) and takeover (bumps it and requires explicit preemption); and the token must be checked by whatever executes the side effect (node agent / executor), otherwise it is a counter, not fencing (O-03). The last point is `inference`.

### C-15 MCP timeout: 300 s, 120 s, 90 s, 960 s (DETAIL)
- hermes-packaging.md:59, 161: default 300 s; its sample config uses 120 s; a plugin-less host writes 90 s with `connect_timeout: 20` (HP-5).
- scale-infra.md:533: "Hermes MCP's default tool timeout is 300 s".
- All are true of different contexts. Design to the minimum, 90 s. D1 says submit-then-poll but does not state 90 s as the budget. Wake is 11.7-21.6 s in the one measured composite (C-27), so it fits, but a first-time `wake` on a loaded node is close enough to warrant making `wake` itself asynchronous.

### C-16 Tool surface: four proposals (DESIGN)
- hermes-packaging.md:326: `status`, `run`, `job`, `cancel`, `read`, `login_link`, `procedures`, `feedback` (8), with `readOnlyHint` on `status`, `job`, `read`, `procedures`.
- scale-infra.md:529-533: `profile.status`, `profile.run`, `task.status` ("names are proposals").
- existing-assets.md:91, 109, 273, 317: one `FLEET_TOOLS` list, "few tools, each proven", never extend the box's `TOOLS`.
- D17: `fleet_status`, `identity`, `run`, `act`, `extract`, `task`, `publish`, `run_status`, `approvals` (9).
- Problems.
  - D17 drops `cancel`, `read`, `procedures`, `feedback`, and `login_link` (folded into `identity.reauth`).
  - `identity` bundles reads (`list`, `get`, `health`) and writes (`wake`, `sleep`, `reauth`) in one tool. After session expiry Hermes replays only `readOnlyHint: true` tools and returns `outcome_uncertain` for unannotated ones (HP-8, `source-code`). A mixed tool cannot be annotated truthfully, so either reads lose replay or writes get replayed. `inference` from HP-8; split the tool.
  - `act` and `task` are free-form browser control. Some hosts allow every tool of a connected MCP server and guard only their own browser tools (HP-5). D1 correctly says the fleet must enforce everything server-side, but D17 never says that `act`/`task` are write-capable and need the D13 approval/manifest gate. `act` on "Post" is a publish bypass unless scoped.
  - D17 and D1 refer to `ARCHITECTURE.md` and a "fleet charter" that do not exist (`fleet/` contains only DECISIONS.md and `research/`).
- Decision of record is D17 once reconciled (O-05).

### C-17 Browser-hour sizing versus API-first (DESIGN)
- scale-infra cost model and D12: 30x1, 100x3 and 1,000x3 identities x active browser-hours.
- D2 and social-platforms.md: most routine social work (publish, comment moderation, inbound-DM reply, analytics) goes through official APIs with no browser. The browser is for login/re-auth, open-web lead gen, a narrow no-API set, and QA.
- Effect: the D12 table is an all-browser upper bound. It also omits the API-first costs the same research priced: X pay-per-use is $0.015 per post, $0.20 per post containing a URL, $0.015 per DM (SP-4, `official-docs`, "prices subject to change"), plus connector build and app-review work. The real driver is the share of identities that need a browser at all, which no one has estimated. Neither side is "wrong"; the table needs a second axis.

### C-18 Browserbase cost basis (DETAIL, resolved in D12)
- browserbase.md: $18 and $54 per profile-month on Startup with Browserbase proxies.
- scale-infra: $359 for 30x1 and ~$1.7k for 100x3 on Browserbase.
- Verifier BB-10: the 50 MB/h figure behind the first is unsourced, 6-18x below scale-infra's, and it priced rotating proxies that identities cannot use. D12 already uses scale-infra and says so. Both rest on estimated bandwidth; real per-hour bandwidth on social SPAs is unmeasured (steel verifier item 10).

### C-19 Can skills reach plugin-less hosts? (DETAIL, resolved in D1)
- hermes-packaging.md still says plugins and skills cannot reach employees on plugin-less hosts.
- HP-5: refuted for skills. Owner-approved prose guides of limited length are a no-code skill channel. The host appends its own restriction on outreach to them, which collides with fleet posting and DM guidance. Plugins still do not load.
- D1 has the correction. The dossier text does not, and the guide size cap is not in D1.

### C-20 Skills release by flipping a `current` symlink (DETAIL, resolved in D1)
- hermes-packaging.md 2.4: flip the symlink atomically; new sessions see the new release.
- X-1 (`source-code`): refuted; `get_external_skills_dirs` resolves and caches the resolved path; the cache is cleared at gateway start and in CLI update/profile/hub paths only. D1 uses versioned paths and rolls gateways. Correct.

### C-21 Does strict `json_schema` give valid output? (DESIGN, resolved in D8)
- reasoning-models.md: JSON validity solved by strict `json_schema` plus the shim.
- REA-7: refuted; enforcement is provider-dependent (one provider returned wrong shapes 4/4, another YAML with HTTP 200); 26 of 33 GLM endpoints advertise structured outputs and OpenRouter drops non-SO endpoints from schema requests; provider and task are confounded throughout the bench. D8 reflects this. Open item: the per-provider benchmark is an M3 gate and nothing yet shows which providers to allow (O-06).

### C-22 Act defect rate: ~3% versus ~7-8% (DESIGN)
- reasoning-models.md and D8: "~3% runaway/garbage" in the act schema's free-string `arguments` (4/144 structured calls).
- REA-3: all 4 runaways and both junk-argument cases fall on two tasks and two providers (book_link on Together; sharp_basket on Friendli). Click acts on the 6k-token page: 4/52 = 7.7% runaway (Wilson 3-18%); including junk arguments 6/80 = 7.5%. Each runaway at an 8k cap cost 34-52 s (reasoning-models.md:270).
- Evidence supports the verifier. Plan on roughly one defective act in 13 on dense pages until the provider-pinned bench says otherwise; the `max_tokens` cap in the shim is mandatory, not optional.

### C-23 How large is the anti-detect licence cost? (DETAIL)
- antidetect-proxies.md Verdict 6 and D9: licence is small, "under a third of the bill in every row except Kameleo at 30".
- antidetect-proxies V-2: Kameleo is 51.5% of base at 100 profiles and 34.9% at 1,000. The other vendors stay under a third. D9's "licence cost is small" holds for Multilogin/Octo/GoLogin/CloakBrowser; not for Kameleo.

### C-24 Steel upstream posture (DETAIL)
- steel.md: `:latest` lags the releases; a maintainer comment plans optional `STEEL_API_KEY`; track #348, #375, #235.
- STE-14: `:latest` tracks `main`, not releases; the "plan" comment on #235 is by an outside volunteer (`author_association: NONE`); #348 and #375 are outside-contributor PRs with zero reviews; "75 open issues" counts 36 PRs. Digest pinning is still right.
- Effect on D4: "Track upstream fixes" should read "carry our own: takeover guard, auth by network isolation, userDataDir, fingerprint". The escape hatch (plain Chromium + small session API) is a more serious option than D4 suggests.

### C-25 Guard reuse: "18 attacks", "one websocket per browser", "import, don't copy" (DESIGN)
- existing-assets.md:27, 85 and D4/D16: 18 attack checks; `Guard` costs one websocket and one asyncio task per browser; the fleet imports `security.py` and `guard.Guard`.
- existing-assets V-1: 18 checks, of which 11 are attacks and 7 are positive/behavioural controls; the shield-check script drives jev-automation's `PlaywrightExecutor`, uses the compose host `gateway:8080`, and relaunches the browser, so it needs a port to run against a CDP client. existing-assets EA-12 / V-13: `Guard(cdp_url=...)` is reusable, but the gating contract (`wait_ready`, re-gate after relaunch, cancel work when the guard drops) lives in `tools.py` bound to the module singleton. `Fetch.enable` with `urlPattern "*"` pauses every request in every tab and worker, each spawning a task and possibly a threaded DNS lookup; per-profile CPU cost is unmeasured.
- Also `_steel_events` hard-codes port 3000 and `/v1/events`, and `from . import steel` reads `BB_STEEL_URL` at import, so "import" couples `fleet/` to box internals.
- Effect: D16's "imports ... instead of copying" is only partly true; the gating contract must be rebuilt per profile, and the guard must run next to its browser.

### C-26 Singleton count (DETAIL)
- steel.md:49 and D4: stale `Singleton*` left 7/7 times.
- STE-3: 6/6 in persist mode; the 7th (`#65`) was a live lock in `CHROME_USER_DATA_DIR` mode. Correct to 6/6. Also: the cause of Steel's non-graceful release is unexplained (Steel's code sends `Browser.close` and waits, yet leaves `Singleton*`), so the safe-release order is empirical.

### C-27 Cold wake time (DETAIL)
- scale-infra and D12: cold wake measured ~15-20 s.
- SCA-6: composite of parts (container to health 3.1-6.6 s, create-persist 6.5-11.0 s, first navigation 2.2-3.6 s; sum 11.7-21.6 s), one chain visible in timestamps, on arm64 Docker. Not a p50 or p95, and not measured on amd64 droplets. Treat as a floor. It also leaves out bundle download/decrypt/extract, proxy connect, the IP-echo and fingerprint checks, and node creation (DigitalOcean: 60 s billing minimum, at most 10 droplets created at once). A failed restore (stale `Singleton*`) costs an additional 27 s before returning 500.

### C-28 Platform ceilings (DESIGN)
- D2/social-platforms.md: X allows 10,000 posts and 1,440 DMs per 24 h per app, shared by all clients; 100 posts/15 min per account.
- SP-3: those are the "Per App" columns of a rate-limit page whose Wayback snapshot shows them as legacy plan columns (Pro: 10,000/24 h per app; Basic: 1,667/24 h), carried onto a pay-per-use page that does not say which plan they apply to; `openapi.json` lists only user-context auth for those endpoints. "Shared by all clients" is an inference and the page's own legend contradicts it. social-platforms V-2: for unverified client accounts the binding account limits are 50 original posts and 200 replies per day, 500 DMs per day and 400 follows per day, and they apply to API use too.
- Build the governor from response headers on live user-context calls (`x-rate-limit-*`), not from constants. Unverifiable without a live pay-per-use app (needs Justin's developer app).

### C-29 Where the Obsidian writer lives (DESIGN)
- existing-assets.md:329 places `memory/` ("Obsidian vault writer") inside `fleetd`.
- scale-infra.md:449 has a per-profile daily rollup "written into the Obsidian vault" as part of the fleet audit trail.
- hermes-packaging.md (item 9) and D15: written on the Hermes side; `fleetd` returns structured evidence; plugin hook where plugins load, skill instructions where they do not.
- Evidence: D15 is right for the trial (no plugins load) and for the shared-service shape (the service runs on droplets; the vault is on Justin's machine). What it leaves open: who generates the daily rollup (a Hermes-side cron/skill reading `run_status`?), how the vault reaches machines that need it, and whether a trial employee's runtime can reach a vault path at all (`unverified`). Also, X-5 found community Obsidian entries (`obsidian-memory`, `vault-view`, `icarus` with a `fabric_init_obsidian` tool) that D15 does not mention; all are community tier and unvetted.

### C-30 Item counts that disagree inside a single dossier (DETAIL)
- system1-models.md says the decider owns "~30-60%" in one place and "30-55%" in another (system1-models V-05); the whole table is `unverified`. D7 uses "~30-60%". Fine, but both are guesses.
- Perplexity's own docs disagree 6x on image token cost (quickstart ~1,000 tokens per megapixel vs cookbook ~6,000 for a screenshot, system1-models V-14); the dossier's "$0.00015 per Perplexity screenshot step" rests on the cookbook (item 11).

---

## 3. Refuted claims that other documents still rely on

### 3a. Where refuted claims still stand in the dossiers

"Relied on by" lists documents other than the one that first made the claim. Rows where nothing else depends on the claim are marked self-contained.

| Refuted or corrected claim | Verifier row | Stated in | Relied on by |
|---|---|---|---|
| Release flushes cookies in 1-3 s | BRO-6, EA-5, STE-3 | `dossiers/scale-infra.md:547-548` | Scale-infra's wake/sleep sequence and slot-hour accounting behind D12 (D4 itself is correct) |
| Steel left `Singleton*` 7/7 | STE-3 | `dossiers/steel.md:49` | D4 (states 7/7) |
| `--lang` pins locale on Linux; Stagehand `locale` maps to it | antidetect V-1 | `dossiers/antidetect-proxies.md:79, 223, 277, 359, 378, 409` | D4 (persona list), D10 (pin locale with `--lang`) |
| `rerun_history` replays with no LLM | system1-models V-12 | `dossiers/system1-models.md:309` | `dossiers/browser-use.md:122` (self-heal tier); not D5/D7 as written |
| Guard costs one websocket and one task per browser | existing-assets EA-12, V-13 | `dossiers/existing-assets.md:85` | D4 (Guard once per awake browser), D16 (import `guard.Guard`), D12 (no Guard CPU line) |
| "18 attack checks" and reuse as-is | existing-assets V-1 | `dossiers/existing-assets.md:27, 85` (copied from box `docs/security.md:52`) | D4 and D16 reuse decision |
| Stagehand cache is where savings come from | browserbase BB-4, system1-models S1-05 | `dossiers/reasoning-models.md:221` | `spikes/scale-infra/cost_model.py` mix A (40% `cached`), hence the D12 table |
| The v4 cache is irreplaceable | browserbase V-1 | `dossiers/browserbase.md:36` | self-contained (D11 already calls it a weak reason) |
| A 1,000-token System 1 step, tagged `hands-on` | system1-models V-04, missed issue 10 (measured 4,911-6,217 tokens for 180 candidates) | `spikes/scale-infra/cost_model.py` (`COST["system1"] = 1000 * JEV_IN`); system1-models cost reference | D12 table (tiny dollar effect, but wrong provenance tag and 5-6x error in any token-rate sizing); D7 states 5-6K but never ties it to the model |
| "~$0.001 per call on GLM 5.3 Flash" for social DOMs | social-platforms V-11 | `dossiers/social-platforms.md` tier-1 cost | scale-infra `[estimate]` (8k prompt assumed, not measured); D12 mixes |
| Skills cannot reach trial employees | HP-5 | `dossiers/hermes-packaging.md` (trial section) | D15 (skill instructions where plugins do not load) depends on the corrected version; D1 corrected |
| Flip `current` symlink to release skills | X-1 | `dossiers/hermes-packaging.md` 2.4 | the dossier's `/opt/jev-fleet/skills/current` layout; D1 corrected |
| Per-profile `userDataDir` works on self-hosted Steel | SCA-2, BRO-6 | `dossiers/browser-use.md` Q4 sample | box `steel.py` (sends ignored `persistProfile`/`profileId`); anyone copying the sample; D4 corrected |
| Anti-detection impact of the v4 extension is unknown | antidetect AP-2 | `dossiers/stagehand.md:432, 454, 473, 513-515` | D6 (frames as open question; mitigation missing) |
| `:latest` lags; a maintainer plans `STEEL_API_KEY` | STE-14 | `dossiers/steel.md:534` and risks | D4 ("track #235") |
| Per-app X ceilings shared by all clients | social-platforms SP-3 | `dossiers/social-platforms.md` governor list | D2 (verbatim as fact), D13 (per-app governor) |
| Dormancy trigger covers any dormant account | social-platforms SP-9 | `dossiers/social-platforms.md` verdict 8 / keep-warm item 3 | self-contained so far (no DECISIONS item; O-12) |
| Lease SQL implements takeover | scale-infra SCA-10 | `dossiers/scale-infra.md` lease section | D12 (leases with fencing tokens), D13 (one writer per identity) |
| An earlier internal job-claim design never double-leases a profile | existing-assets EA-7 | `dossiers/existing-assets.md` Q1/Q4 | D12 (cites that design) |
| Cold wake ~15-20 s | scale-infra SCA-6 | `dossiers/scale-infra.md:50, 533` | D12 |
| Browserbase per-profile cost $18 / $54 | browserbase BB-10 | `dossiers/browserbase.md` cost section | D12 already discards it |
| Jev's cap is ~180 options | browser-use BRO-4, system1-models S1-08 | `dossiers/system1-models.md`, `dossiers/browser-use.md` | D7 ("a 180-candidate step") |
| Act defect rate ~3% | reasoning-models REA-3 | `dossiers/reasoning-models.md` | D8 |
| Kameleo licence under a third of the bill | antidetect V-2 | `dossiers/antidetect-proxies.md` verdict 6 | D9 ("licence cost is small") |
| 38 GLM endpoints from $0.04 | reasoning-models REA-7 says 33 endpoints / 29 providers, $0.032 | not in the dossier | D8 only |

### 3b. Errors and gaps in DECISIONS.md, by decision

D1 (shared service, packaging)
- "fails closed without it (tested ...)" holds at pins `09681e7` and main only. At some older pins unset vars keep the literal `${VAR}` and are sent as the token (HP-1). When a secret scope is bound, a miss falls through to `os.environ` unless the process serves a routed profile. So: never export `BROWSER_FLEET_TOKEN` in a host-wide environment; `fleetd` should reject a literal `${...}` bearer. The hands-on test used separate per-profile `hermes -p pX mcp test` processes; the multiplexed-gateway path was reasoned from source (X-3), not run.
- Pin skew: the hands-on ran at `09681e7`, 4,595 commits behind the targeted main and 8,011 after an older pin. Verifiers re-checked the relevant paths at main (unchanged except a shadow warning).
- A same-named local skill silently shadows the shared external skill at the tested and older pins (HP-3). Not in D1; a drift scan is required.
- First boot of a new profile connects MCP eagerly, one profile after another; `lazy` helps from the second boot (X-2). Not in D1.
- Missing upside (HP item 13): a root-owned `/etc/hermes/config.yaml` can pin the `browser_fleet` URL so an agent cannot redirect its own fleet entry. The docstring and code disagree on `${VAR}` expansion there, so do not rely on either.

D2 (channels)
- "Per-app ceilings (e.g. X: 10,000 posts and 1,440 DMs per 24 h across all clients)" is stated as fact. See C-28. Replace with a rule: ceilings come from headers; per-account caps bind first.
- "Meta ... terms explicitly forbid bot-driving the logged-in web UI": SP-2 shows §3.2 is a scraping clause ("access or collect data ... automated means (without our prior permission)"), not a posting ban. The firmer basis is Community Guidelines: using an account "through automated means, such as scripting (unless the scripting activity occurs through authorized routes ...)". Restate as: reading/collecting by script is banned; scripted account use needs an authorized route. The API-first conclusion survives.
- Missing from the "never built" and constraints text: X's rule that automated accounts using the API must carry the "Automated" profile label, disclose the operator in the bio, link a human-managed account, and honour opt-out (social-platforms V-8). Whether human-approved, API-scheduled brand posting counts is unresolved (Q-05).
- Missing: consent-based lead capture (Lead Ads forms, DM opt-in capture, LinkedIn Lead Gen Forms, TikTok instant forms) is an official lead source; D2 says only what is never built (SP-11).
- Missing: LinkedIn CM API version 202510 sunsets on 2026-10-15 (social-platforms V-3, `official-docs`); Development tier is 500 requests/app/day and 100/member/day. TikTok Business Messaging is open beta, not available in the EEA, Switzerland or the UK, and needs privacy reviews (V-4). Messenger: 24 h window, 7-day human-agent window, 30 s bot reply; Instagram 100 API posts per 24 h per account, Reels 30 per Page per 24 h (V-5, SP-5).
- Facebook Groups API removal: the cited Graph v19.0 changelog is forward-looking ("will be removed", effective for all versions 2024-04-22). That it happened rests on vendor corroboration and a dead docs URL (SP-7). Browser-only group posting stays ToS-exposed.

D3 (identity pinning)
- Persona scope: see C-02. The cited drift "UA Chrome 144 -> 142 -> 145, WebGL Intel -> SwiftShader -> AMD -> Adreno" splices two separate relaunch pairs and skips the first session's 139 (SCA-3, STE-10). The conclusion (random per launch) stands.
- "Exit IP equals the pinned IP" is the right check, but IPRoyal sticky sessions silently swap the IP by default unless `_killswitch-1` is set (AP verifier missed issue 8). The wake check catches it only at wake; mid-session swaps need the forwarder to fail closed.

D4 (Steel host)
- "Steel's own release left `Singleton*` behind 7/7" -> 6/6 persist-mode (C-26).
- "(`TZ`, `--lang`, UA, window size, SwiftShader WebGL ...)" -> `--lang` does nothing on Linux (C-10); WebGL cause unproven and headful needs Xvfb + dbus (C-11).
- Missing finding (STE missed issue 3): Steel's Chromium runs as root with no sandbox (`--no-sandbox --disable-setuid-sandbox --no-zygote`) and with site isolation off (`IsolateOrigins,site-per-process` disabled in the static args), inside logged-in client sessions on arbitrary pages. The wrapper should run as a non-root user and drop capabilities, or the risk must be accepted in writing (Q-08).
- Missing (missed issues 1-2, 9): `GET /v1/sessions/{id}` returns a fabricated `released` stub for any non-active id and `GET /v1/sessions` drops a taken-over session; `/v1/health` is structurally always `ok` (`isRunning()` is `this.browserInstance?.process() !== null`, true when there is no browser); the Docker quick starts publish unauthenticated raw CDP on 9223. D4 says "never trust `/v1/health`" but attributes it to observation; it is a source-level bug.
- "Track upstream fixes: #348, #375, #235" -> none has a maintainer owner or a review (C-24).
- Viewer: "typed text and popups work" was exercised with synthetic input only. Special keys are sent as `keyDown` without `text`; Enter, Backspace and Tab were never tried (missed issue 8). IME, native dialogs, HTTP auth, passkeys and file pickers are untested.
- "Cross-identity linkability" paragraph is right and should be linked from D3 (C-02).
- All measurements were on arm64 Docker; the source pin `1131a02` is not the tested image (built 2026-09-16, before #366, #327, #374). Restoring a profile tarball cross-host and on x86 is unverified (steel verifier item 10), which matters for "wake on any node".
- Guard: see C-25. The sentence "browser-box's in-browser `Guard` runs once per awake browser" understates the porting and CPU cost.

D5 (action ladder)
- "Both frameworks can execute a chosen element with zero model calls" is correct for Stagehand `act(Action)` with `selfHeal:false` and Browser-Use `Tools.act`, but not for `rerun_history` (C-07).
- Unmeasured: `act(Action)` replay of real `xpathMap` selectors across iframes and shadow DOM on Steel; Browser-Use `Tools.act` index execution against a live Steel CDP session; element-choice accuracy on dense social pages (system1-models verifier). D5 should list these as M1 gates.

D6 (engines)
- "Open question to measure on a droplet: Stagehand v4's resident extension trips ..." -> the trip is measured (n=1 per condition); the open part is whether platforms weight it. Add the mitigations and the Browser-Use caveat (C-13).
- D9's statement about patched Chromium and Stagehand needs the version rule (C-12).
- 50 MiB uploads are unproven above 26 bytes (SH verifier); D6 already says "unproven above a few bytes". Keep.

D7 (System 1 models)
- "Clef ~300 rpm per model" is inferred from a Workers AI limits page dated 2026-09-17, before Clef launched on 2026-10-01, on a platform that says beta models may be lower (S1-03). Mark as an assumption.
- OpenAI Decisions is not a blank: the gpt-6-luna page publishes tiers (Build 5,000 RPM / 2M TPM; Launch 10,000 / 10M; Grow 30,000 / 180M). Token caps matter more than RPM: at a ~6K-token step Build gives ~5 steps/s (below Jev's ~16), Launch ~27, only Grow covers full concurrency. Whether the tiers apply to `/v1/decisions` is unconfirmed (S1-03). D7 omits them and OpenAI's option cap (unstated, S1-08).
- "Clef / Perplexity Decider: screenshot questions": Decider and OpenAI image calls through OpenRouter were tested; **Clef images through OpenRouter are untested**, and OpenRouter's alpha `DecisionsRequest` has no `images[]` field (S1-02, system1-models V-02).
- `confidence` is not portable across providers (Clef-flash 0.69 top probability gave 0.43 confidence; Jev 0.92/0.91; OpenAI 0.79/0.76). D7 says thresholds are not portable, which is the same point; add that "confidence" itself means different things.
- Perplexity has a token limit as well as 10 rps (S1-03).
- The "180-candidate step is ~5-6K tokens" is measured (4,911-6,217); the cost reference elsewhere assumes a 1,000-token step, 5-6x too low.
- Jev's context length is 32k in the OpenRouter guide prose but 64k in its catalog and endpoint metadata (system1-models V-15); Clef truncates long text silently (V-11).
- A decider is not a safety control (system1-models V-07). D5/D13 already gate irreversible actions deterministically; keep that explicit in D7.

D8 (reasoning model)
- "~3% runaway/garbage" -> 7-8% on click acts (C-22).
- "uncached Stagehand p50 ~1.7 s": REA-2 gives 1.68 s for the 12 uncached calls (p90 3.54 s) out of 64; the 1.2 s headline was cache-flattered. D8 is right. Note n=12.
- "Reasoning cannot be turned off; unset means max and ~40 s steps": REA-5 confirmed the mandatory reasoning and `default_effort: max`; on the 864-token act the unset default produced 85 reasoning tokens vs 0 at `low`. The "~40 s" figure was not re-measured in the rows I read (`inference`: treat as unverified).
- D8 says "OpenRouter lists 38 GLM 5.3 Flash endpoints from $0.04 to $0.225/M input". The reasoning-models dossier (lines 88, 92, 96) and its verifier (REA-7 and the fetched-data summary) both say 33 endpoints from 29 providers, 26 with structured outputs, priced $0.032-$0.225/M input. I found no source in the research for 38 or for the $0.04 floor. Either D8 used a later fetch (cite it with a date) or the number is a transcription error (`unverified`).
- No data-handling statement (ZDR): 29 endpoints are ZDR-listed, 25 with structured outputs; the bench's main provider (Friendli) is not ZDR-listed; Phala is, but its schema enforcement failed every time. A ZDR requirement changes which providers serve and invalidates the bench numbers (Q-07).
- The caveat that benches ran on local Chrome on a Mac (not Steel) is in D8; the process breach it implies is in section 7.

D9 (anti-detect)
- "Two OSS persona options": the seed-pinned patched Chromium option is **not OSS**. CloakBrowser is a proprietary binary under `BINARY-LICENSE.md` v1.3 with an MIT wrapper; internal use of the unmodified binary is allowed, the latest major build requires a paid subscription, an OEM/SaaS licence is also required "if third-party customers are given technical access to, or control over, the browser capability itself", and the binary reports for licence validation and concurrent-session monitoring (antidetect-proxies V-9). If client staff log in through the fleet's live viewer, the OEM clause is arguably in play (AP verifier's inference). The free build is 146 (C-12).
- "Licence cost is small" fails for Kameleo (C-23).
- Note an earlier private SDR harness says it implements no fingerprint spoofing or proxy rotation; the seed-pinned option would be spoofing and conflicts with that stance (Q-04).

D10 (proxies)
- "Avoid NetNut-sourced pools": AP-7 confirms the domain seizure (FBI, 2026-07-02, Popa botnet; netnut.io banner) but the pool was "widely resold or white-labelled". Provenance cannot be established from the vendor name; D10 needs a vetting rule, not just a name (O-10).
- IPRoyal silent IP swap on sticky sessions (D3). Bright Data's IPs carry a 100 GB per-IP fair-usage allowance (antidetect-proxies V-3).
- Pin `TZ` and `--lang`: see C-10.

D11 (Browserbase)
- Accurate. One reading to guard against: the "multiple accounts" ToS sentence concerns Browserbase accounts (circumventing limits), not target-site accounts; the dossier says so correctly and D11 states it correctly. AUP probes all redirect to sign-in, which every unknown path does, so "no AUP" is weak evidence (BB-6).
- The keepAlive plan gate is inconsistent across sources (browserbase V-3): `plans.md` has no keepAlive row, the Node SDK says "Hobby and above" (a legacy plan name), and `keep-alive.md` says "paid plans". D11 doesn't state it; verify against the real plan before buying.
- `browser.close()` releasing even a keepAlive session is confirmed on both npm and Python 4.2.0 (BB-9); D6 states it.

D12 (control plane and cost)
- "SKIP LOCKED lease pattern from an earlier internal job-claim design" -> not race-safe (C-14).
- "on-demand wakes cost ~15-20 s cold" -> 11.7-21.6 s, effectively n=1, arm64, composite (C-27).
- Table rows: the 40% "cached" share in mix A is an assumption about a cache that does not exist (C-05); the planner cost per task (`TASKS_PER_HOUR = 6`, 8k+500 tokens twice) is an `ESTIMATE`; the 16 h active window and 2x peak factor have no source (SCA-7); the browser slot size (1.5 GiB) is an estimate against 0.65-0.85 GiB measured on light pages and 1.08-1.36 GiB on heavier ones.
- Steel Cloud rows: self-serve dedicated IPs cap at 25 (D12 says so); also Steel Cloud caps a profile at 300 MB and deletes after 30 days unused (SCA-13).
- "1,000 always-on browsers = ~1.85 TB RAM": 1,850 GiB is 1.81 TiB; fine as an approximation (SCA-7).
- `COST["system1"] = 1000 * JEV_IN` in `cost_model.py` is tagged `hands-on` but is an assumed 1,000-token step. Measured 180-candidate steps are 4,911-6,217 tokens (system1-models V-04 and missed issue 10), so any token-rate or Jev-capacity sizing built on it is 5-6x too small. The dollar effect is small (Jev is $0.042/M input, output free). Likewise the "~$0.001 per GLM call" in social-platforms rests on scale-infra's assumed 8k-token prompt, not a measurement (social-platforms V-11).
- Missing line items: the >= 31 s flush hold per sleep (C-03); X API fees (C-17); Guard CPU per awake profile (C-25); evidence/screenshot storage is modelled but its retention is `ESTIMATE`.
- DigitalOcean specifics (scale-infra verifier, SCA-12 and missed issues 4-5): per-second billing with a 60 s / $0.01 minimum is confirmed; the $96/month price and 672 h cap apply to bundled plans only, and v5 droplets (and Autoscale Pools) are $0.1953/h for the same shape with no cap where available; at most 10 droplets can be created at once; the account's own droplet limit was never checked (scale-infra.md:178, 565, 602). The wake-latency figure leaves out the network-bound steps (bundle download/decrypt/extract, proxy connect, IP-echo and fingerprint checks) and node creation. D12 states none of these.

D13 (effect journaling)
- The intent/receipt/uncertain-hold pattern comes from the Jev Workforce trial (private) and was confirmed in code (SCA-9). The "read-back receipt" rests on API reads for API channels; for browser-driven social actions on Meta/X/TikTok the receipt design is unproven. Mark the browser path as a hypothesis for social.
- "Temporal workflow ID = task ID rejects duplicates" was only partly confirmed against Temporal's reuse-policy docs (SCA-9).
- "Three distinct owner-accepted outcomes" to release a procedure is the trial's rule for procedures. Prose guides on plugin-less hosts are admitted on owner approval alone (HP-5). So fleet guidance delivered there is gated by a human click, not by the release rule; say so.

D14 (human login)
- Depends on the viewer working for real logins, which is untested for special keys, IME, passkeys, native dialogs and HTTP auth (D4). Until tested, D14 is a plan, not an established path.
- "Stagehand `variables` keep values out of the act prompt only; the typed value then appears in the accessibility tree (measured)": consistent with SH rows; no change.

D15 (Obsidian)
- See C-29. Missing: community Obsidian entries (X-5); the trial runtime's reach to a vault is unverified. "mem0-style semantic layer over the vault later" matches Justin's directive.

D16 (repo and release)
- "Before any merge to `main`, `box-kit`'s export must exclude `fleet/`" is correct and still open. Related findings that make it more urgent: `jev-automation` and `jev-agent-kit` are public (`isPrivate:false`), and a separate exposure question is tracked privately; existing-assets verifier M-items on the export leak.
- "the fleet imports the box's `security.py` and `guard.Guard`": see C-25.

D17 (tool surface)
- See C-16: split `identity` by read/write, state that `act`/`task` are write-capable and scope-gated, reconcile with the 8-tool proposal, and create the referenced `ARCHITECTURE.md` and fleet charter or remove the references.

---

## 4. Open decisions

Each entry: what has to be decided, where the documents disagree or are silent, options, and what blocks it. "M1" and "M3" are the milestones DECISIONS.md already names.

**O-01 Fingerprint strategy (blocks D3, D4, D9).** Three mechanisms are proposed (C-01). Options: (a) honest persona, stock Chromium, no spoofing, UA/TZ/locale/viewport pinned; (b) fork Steel to accept a stored fingerprint object; (c) CDP-side injection from the node agent; (d) seed-pinned patched kernel (licensed binary, Chromium >= 149 needed for Stagehand). Linkability between clients on a node is real under (a) (C-02). Decide whether cross-client unlinkability is a requirement; if yes, either one client per node or (b)-(d). Blocked by an M1 measurement of per-identity canvas/GPU/cores.

**O-02 L1/L2 executor.** Stagehand v4 (extension trips `isAutomatedWithCDP`; mitigations exist), Browser-Use `Tools.act` (attach did not trip; actor/coordinate paths do), or a minimal CDP executor. D6 already says to measure per site class; the router must record the winner. Blocked by droplet measurements (section 6).

**O-03 Lease and fencing design (blocks D12).** One mechanism for agent and human ownership; DB uniqueness on the active lease; acquire/renew/takeover as separate operations; fencing token checked by the node agent and executor, not just stored. Blocked by nothing but design; test in SQL before any code.

**O-04 Job engine and claim.** Postgres queue now with a rewritten claim that locks the profile row; Temporal later. D12 states the plan; the rewrite is not scheduled as a dependency. Temporal workflow-ID dedup semantics need confirming against the reuse policy actually used.

**O-05 Final tool surface (blocks D17).** Reconcile C-16: names, read/write split for `readOnlyHint`, whether `act` and `task` are exposed at all to profiles, how `cancel`/`read`/`login_link`/`procedures`/`feedback` are covered, and the 90 s budget. Create the missing ARCHITECTURE.md and charter first.

**O-06 Provider allowlist for GLM (M3 gate) and its data policy.** The bench confounds model and provider. Needed: a per-provider bench with `provider.only`, with and without `zdr:true`, with price and quantization caps, plus a shim that validates schemas and retries once on a different provider (D8 already specifies the shim). Blocked by Q-07.

**O-07 Which System 1 providers are in the first release.** D7 lists four; OpenAI's limits and cap are unconfirmed; Clef image path through OpenRouter is untested; Jev's limits moved between the 2026-09-17 snapshot and 2026-10-10 (requests up 4x, tokens down 60%) and the page says they can change without notice. Decide the minimum viable set and a fallback ordering. Per-provider calibration needs a procedure (D7 says log and pin).

**O-08 Credentials and keys procurement.** Which keys exist today, which have to be bought or applied for (X developer app with prepaid credits; Meta App Review and Business Verification; TikTok Accounts API form; LinkedIn CM API tier; Orgo; Browserbase if used; proxy accounts; OpenRouter spend limits; Spaces). The research never lists which are already in `.env`; I did not check (secrets stay out of this file). Blocks every API-first milestone.

**O-09 Secret and state-bundle custody (D3, D4, D14).** State bundles contain logged-in client cookies. D4 says "encrypted state bundle in Spaces". Not decided: who holds the key (KMS vs a per-identity key in Postgres vs an operator key), who can decrypt, rotation, what happens on client offboarding. Chrome's cookie encryption in the profile uses `--password-store=basic` (fixed `v10` key, `cdp.service.ts:898`), so the profile's cookie store is protected by a fixed key rather than a per-host secret, and the bundle layer has to do the real encryption (SCA-4; the second half is `inference`). Cross-vendor restore of a Browserbase Context is not possible (no export), so custody differs per home.

**O-10 Proxy vetting rule.** NetNut-sourced pools are widely resold; a vendor name does not tell provenance (AP-7). Also IPRoyal's silent swap. Decide the acceptance test for a new IP (exit-IP check, ASN class, reputation lookup, provenance statement) and the fail-closed behaviour on a mid-session change.

**O-11 Networks and isolation per identity.** One Docker network per identity, node-local forwarder, egress only via the forwarder, metadata-endpoint blocking on DigitalOcean, non-root Chromium (Q-08). The "metadata endpoint reachability around the proxy" test is unverifiable here (steel verifier item 10).

**O-12 Keep-warm and dormancy policy.** The weekly read-only login probe per account rests on a Meta dormancy trigger that applies only to empty accounts (SP-9, social-platforms V-12); it also adds scripted access on Meta. Options: drop it; replace with API-token health checks; probe only identities that actually use a browser. Cadence is "policy, not a sourced figure" and is `unverified`; measure with checkpoint telemetry.

**O-13 Soak and canary policy.** New identities, new procedures and new releases need a rule for when they may touch a client account. D13 has procedure quarantine (three distinct owner-accepted outcomes); nothing covers a new identity or a new Steel/Stagehand pin. The upgrade smoke test in D6 is the only gate and it does not include the extension-flag recipe's behaviour against a real site.

**O-14 Vault location and sync (D15, C-29).** Where the Obsidian vault lives relative to droplets and the Jev trial; who writes the per-profile daily rollup; whether a trial employee can reach it.

**O-15 Measurement plan that closes the 90% hypothesis.** D7 says the 90% System-1 share is a hypothesis. Nothing yet measures the numerator or denominator on a real social procedure. Define the procedures, the held-out set and the metric before any target is quoted to a client.

**O-16 Which dossiers get an "as verified" pass.** Section 3a lists the rows. Without it, builders will keep rediscovering refuted claims.

**O-17 amd64 re-run of every Steel measurement.** All hands-on Steel/Stagehand/Browser-Use numbers were taken on arm64 Docker (or locally on a Mac). DigitalOcean droplets are amd64. Cross-arch tarball restore is explicitly unverified. This is a dependency for M1, not a nicety.

---

## 5. Questions only Justin can answer

**Q-01 API-first or browser-first for client social (D2).** DECISIONS recommends API-first. If any client wants browser-driven posting, which clients accept in writing that Meta, X, LinkedIn and TikTok terms can result in suspension? The dossiers give the clause text; the risk acceptance is yours.

**Q-02 Anti-detect: continuity-only or buy now (D9).** Spend decision. Recommended default is continuity-only with a measured per-identity upgrade. Kameleo is not "small" at 100-1,000 profiles (35-51% of the base bill); the others are 4-30%.

**Q-03 Proprietary kernels and licences.** May the fleet depend on a proprietary binary (CloakBrowser) that reports licence and concurrency telemetry and has an OEM/SaaS clause relevant to the live viewer? If a vendor sees client session counts, is that acceptable?

**Q-04 Spoofing stance.** An earlier private SDR harness states it implements no fingerprint spoofing or proxy rotation. The fleet pins a persona (continuity) and may add seed-pinned spoofing. Which side of that line do you want, publicly and for clients?

**Q-05 X "Automated" label.** X requires API-driven automated accounts to carry the label, name the operator and link a human account. Does human-approved, scheduled client brand posting need the label, and are clients willing to display it? The verifier could not settle this from the text (social-platforms V-8).

**Q-06 Developer-app applications and spend caps.** Will you apply for Meta App Review and Business Verification, the TikTok Accounts API form, LinkedIn Community Management API access and an X pay-per-use app? What is the per-client and fleet-wide monthly cap for X API fees ($0.015 per post, $0.20 per post with a URL, $0.015 per DM, `official-docs`, subject to change), model spend, proxy spend and droplets?

**Q-07 Data handling for client page content.** Logged-in client pages (including DMs) are sent as text or screenshots to OpenRouter-routed providers for GLM and to up to four System 1 vendors. Do you require zero-data-retention routing, per-client consent, or both? ZDR changes which GLM providers can serve and invalidates the current bench numbers (REA item 12).

**Q-08 Root, no-sandbox, site isolation off.** Steel's Chromium runs as root without a sandbox and without site isolation. Do you want the wrapper to run non-root and re-enable the sandbox (extra work, may need capabilities), or accept the risk for now?

**Q-09 Private repo or exclude-from-export (D16).** Either `box-kit`'s export excludes `fleet/`, or `fleet/` moves to its own private repo. The box publishes publicly, and this research names providers, internal projects, UUID-bearing files and client-handling assumptions.

**Q-10 Public companion repo exposure.** A separate exposure question about a public companion repo is tracked privately (details withheld).

**Q-11 Jev Workforce host.** The fleet's only no-code path in is the owner adding the MCP server through the host's own integration route (HTTPS only) plus owner-approved prose guides of limited length. Only the host's owner can do this. Is that acceptable, and who holds that role? The host's own appended instructions constrain fleet wording.

**Q-12 Droplet hands-on.** Every item in section 6 needs a droplet, containers and (for some) a browser. Do you approve a small, capped, throwaway droplet and which spend ceiling? Without it, those claims stay `unverified`.

**Q-13 Workstation housekeeping (DECISIONS.md Q-19).** A question about the maintainer's local Hermes install, kept out of the public copy.

**Q-14 Written client risk and lead-gen position.** Open-web lead generation by the agent's own browser is allowed by D2 and the no-paid-enrichment rule. Platform terms bar building lead databases without consent. Do you want consent-based channels (Lead Ads, opt-in DMs) added as first-class so the browser stays away from platform lead scraping?

---

## 6. Unverifiable here (needs hands-on on a droplet)

Marked as "unverifiable (needs hands-on on a droplet)". Each also needs your yes (Q-12) because it requires Docker, a browser, or a paid account.

- Steel: metadata-endpoint reachability around the proxy; `<-loopback>` through `CHROME_ARGS`; `PROXY_INTERNAL_BYPASS` effect; in-container argv free of proxy credentials; `FILTER_CHROME_ARGS` effect on WebGL; special-key and IME input through the viewer; native dialogs, HTTP auth, passkeys and file pickers; cross-host and x86 restore of the tarball; resource use on social SPAs; whether a clean-exit `Browser.close` skips the cookie store's `Close()`.
- Stagehand: `act(Action)` replay of real `xpathMap` selectors across iframes and shadow DOM on Steel; the extension-recipe's behaviour against real sites; a large (media-size) upload through Steel's files API; behaviour of the instance lock after a worker crash.
- Browser-Use: `Tools.act` index execution against live Steel CDP; whether `ProxySettings` is truly ignored (BRO-11's contrary probe).
- System 1: element-choice accuracy on dense social or lead-gen pages; Clef image calls through OpenRouter; OpenAI Decisions limits on the tier Justin would use.
- Reasoning: act/observe/extract on Steel (every bench ran on local Chrome for Testing on a Mac); per-provider bench with `provider.only` and with ZDR; GLM throughput for 100-1,000 agents (429s seen).
- Social platforms: X per-app/per-account limits on a live pay-per-use app; keep-warm cadence versus checkpoint rate; Messenger 30 s window; TikTok review timing.
- Scale: wake latency p50/p95 on amd64; Guard CPU per awake profile; Postgres lease semantics under concurrency (SQL test can be done locally, no network).
- Hermes: multiplexed-gateway token isolation (the hands-on used separate processes); whether `hermes mcp test` fills the lazy schema cache; behaviour at main's pin versus the tested pin.

---

## 7. Process notes

- **Native browser on the maintainer's workstation.** `spikes/reasoning-models/RESULTS.md:7` says "Local Chrome for Testing ... ran headless" and the verifier (REA item 9) flags it as a method BRIEF.md bans. The social-platforms spike's `render.cjs` calls `chromium.launch({executablePath: ... 'Google Chrome for Testing' ...})` (social-platforms verifier item 1). The data is usable, but the Stagehand end-to-end proof, live Browser-Use runs and all latencies are from macOS and local Chrome, not Steel.
- **Hermes fresh-root bootstrap.** A fresh `HERMES_HOME` root is a heavyweight, side-effecting install (HP-10). Fleet hosts use baked images and never create ad-hoc roots. Not touched by this review.
- This review itself ran only file reads, `grep`, `sed`, and a read-only `cat` of one Python file; no Docker, no browser, no network, no Hermes CLI.

---

## 8. Coverage and limits

- Contradictions C-01 to C-30 are those I could tie to a dossier line or a verifier row. Statements marked `inference` are mine.
- DECISIONS.md was read as of its last modification on 2026-10-10 10:47. Re-diff section 3b after the next edit.
- Not reviewed: `verification/claims/*.json`; raw spike outputs; the BRIEF's cross-links to the corpus under `fleet/research/corpus` (not opened).
- The verifier reports were treated as evidence of the claims they quote; they were not independently re-derived except for the spot checks listed in section 0 (the 7/7 vs 6/6 count, 255 vs 180, 1.65x vs 2.7x, `--lang`, the ≥149 threshold, Steel's extension flags, the lease SQL result, the guard and 18-checks rows, the X ceiling rows, the NetNut/IPRoyal rows, the ZDR pool).
