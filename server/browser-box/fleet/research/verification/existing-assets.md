# Verification: existing-assets dossier (adversarial)

Verifier: independent adversarial pass, 2026-10-10 (external fetches dated 14:52Z onward). I did not write the dossier I checked:
[`../dossiers/existing-assets.md`](../dossiers/existing-assets.md). Claims file:
[`claims/existing-assets.json`](claims/existing-assets.json).

**Rules followed.** No Docker command of any kind, no browser, no Hermes CLI, no `HOME` override, no
`sudo`/`security`/`keyring`/`osascript`, no `git push`, nothing committed. Public HTTP only. One live
TypeSafe call. The key was loaded into a subprocess by name and never printed. One process note, for
honesty: I ran a read-only `git fetch --dry-run` in a local checkout (it contacts a private
origin). It printed no error and I saw no prompt, but I should not have used a git network
command that can reach a credential helper. I did not repeat it.

**Method, and how it differs from the author's.** The author's evidence was a Docker spike plus source
reading. I re-derived each claim by a different route:

1. **Source at the pinned commit.** Steel `steel-browser` @1131a02 (`session.service.ts`, `cdp.service.ts`,
   `retry.ts`, `validation.ts`, `sessions.schema.ts`), browser-box @4c837a3, private repos at pinned commits (names withheld),
   `jev-automation` `feat/steel-cdp` @edcbbae.
2. **Documents the author did not use.**
   - The two self-hosted OpenAPI specs in the Steel corpus (running image 2026-09-16 and source 1131a02), and the
     Steel Cloud spec.
   - Steel's "Steel Local vs Steel Cloud" page, re-fetched 2026-10-10T14:58Z.
   - TypeSafe `docs.typesafe.ai/models.md`, re-fetched 2026-10-10T14:52Z.
   - Chromium `main` source for the cookie store and the process singleton (`googlesource`).
   - Steel upstream PRs #348 and #375 (GitHub API).
   - The GHCR registry API for the Steel image.
3. **Other agents' raw records.** The steel agent's recovered transcripts in `spikes/steel/RESULTS.md`
   (t1 #45-#74), which ran the stale-lock, `--hostname` and `CHROME_USER_DATA_DIR` variants the author
   left untested. I label these `hands-on (steel agent)`; they are corroboration, not mine.
4. **Own hands-on.** One live TypeSafe call, the box test suite, GitHub visibility by unauthenticated API.

**Spend: about $0.00002.** One `POST /v1/systemone` call, 449 input tokens at $0.042/M. Cap was $0.10.
No OpenRouter call. **Containers left running: none** (I created none).

**Not verified (needs hands-on on a droplet or Docker, banned this round).**
- Line numbers inside the compiled image (`session.service.js:89-91`, `cdp.service.js:382-383, :984`).
  I checked the same logic in source @1131a02 and in the image's committed OpenAPI. The image build is 2026-09-16
  and the source is 2026-10-06; `latest` has since moved (see M-4).
- That `jev-automation`'s TypeScript scope test passes (needs npm install).
- The 18/18 guard-check result and the real behaviour on amd64.

## Verdict table

Provenance tags: `source-code`, `official-docs`, `vendor-claim`, `hands-on` (mine), `hands-on (steel agent)`.

| id | claim (short) | verdict | method | evidence | correction | impact |
|---|---|---|---|---|---|---|
| EA-1 | OSS Steel ignores the value of `userDataDir`; any truthy `userDataDir` or `persist:true` uses the one fixed `<build>/../../user-data-dir` (`/app/api/user-data-dir`) | **confirmed** | Read `session.service.ts` @1131a02 myself. Different route from the author: the open upstream PR that describes the same bug, the image's committed OpenAPI, and the steel agent's variant runs. | `session.service.ts:180-183`: `options.userDataDir \|\| options.persist === true ? path.join(..., "user-data-dir") : env.CHROME_USER_DATA_DIR \|\| path.join(os.tmpdir(), "steel-chrome")`. The `\|\|` binds tighter than `?:`, so the caller's path is only a truthiness test. Upstream PR #348 "fix(sessions): respect the caller-supplied userDataDir" (opened 2026-08-24, **still open** at 14:53Z; upstream HEAD is still 1131a02) describes exactly this precedence bug. The steel agent's R4 (t1 #65-#66) ran `CHROME_USER_DATA_DIR=/data/profile` with a non-persist session: the cookie reached disk after 35 s and was read back after a same-hostname recreate (n=1). | The fixed path is not the only no-patch route. `env.CHROME_USER_DATA_DIR` (`session.service.ts:183`, `cdp.service.ts:161`) lets the volume mount anywhere with no `persist` flag. The claim flips if #348 merges, which is a reason to pin the image by digest. | detail |
| EA-2 | OSS `CreateSession` has no `persistProfile`/`profileId`; the box sends them; they are stripped; the request still returns 200 | **confirmed** | Three routes: the zod schema, both self-hosted OpenAPI specs in the corpus, and the Cloud spec for contrast. Read box `steel.py` and `tools.py` for the caller. | `sessions.schema.ts` `CreateSession = z.object({...})`; zod strips unknown keys. Neither `steel-browser-selfhosted-openapi-running-image-2026-09-16.json` nor `...committed-1131a02.json` contains the strings `persistProfile` or `profileId`. Their `CreateSession.properties` are exactly: blockAds, credentials, deviceConfig, dimensions, extensions, extra, fullscreen, headless, isSelenium, logSinkUrl, optimizeBandwidth, persist, proxyUrl, sessionContext, sessionId, skipFingerprintInjection, timezone, userAgent, userDataDir, userPreferences. `steel-cloud-openapi.json` has `persistProfile` (3 hits) and `profileId`. Steel's profiles cookbook (`persistProfile`, `profileId`, `client.profiles.delete`) is a Cloud workspace feature. `steel.py:103,105` set both. | Two additions. (1) `steel.py:101` also sends `timeout`, which is not in `CreateSession` either, so it is also dropped. (2) `tools.py:341` calls `create_session(timeout_seconds=...)` with the default `persist_profile=True`, so the body is `{timeout, persistProfile}` and **never contains `persist`**. Box sessions therefore use the non-persist dir `/tmp/steel-chrome`, the same dir as the idle browser. The dossier's "one Steel lifetime" understates it: by source this is one *container* lifetime, shared by every tool. That reading is inferred from source, not run. | detail |
| EA-3 | One OSS Steel process runs one session at a time through a single `activeSession` | **confirmed** | Source + the vendor's own docs page + upstream PR + the steel agent's run. | `session.service.ts:67` `public activeSession: Session`. `startSession` calls `resetSessionInfo` then `cdpService.startNewSession`, so a second create replaces the live session. Steel docs "Steel Local vs Steel Cloud" (`official-docs`, fetched 2026-10-10T14:58Z): "Concurrency \| 1 \| 100+". PR #375 (opened 2026-10-10): "The self-hosted singleton can currently replace a live session on a second create ... this does not add multiple isolated browsers". Steel agent: "A second POST /v1/sessions silently took over the live browser; nothing returns 409" (DECISIONS D4). | Stronger than the dossier says: a second create does not queue or fail, it destroys the first. The lease alone is not enough; the wrapper must serialize creates. | detail |
| EA-4 | Recreating a container on a profile volume with a stale `SingletonLock` makes Steel log `process_singleton`, return HTTP 200, and serve a browser without the cookies; removing `Singleton*` restores them | **confirmed**, with a mechanism the author only inferred | Read `launchInternal`, `RetryManager`, `isSimilarConfig`; fetched Chromium `process_singleton_posix.cc`; read the steel agent's raw logs. | Author's evidence: RESULTS.md rows 6-7, n=1, log lines quoted but no raw log preserved. Steel agent t1 #56-#57 (raw): `Launching new browser instance ... Setting up user preferences in /app/api/user-data-dir` -> `LAUNCH ERROR (BROWSER_PROCESS) ... process_singleton_posix.cc:365 The profile appears to be in use by another Chromium process (4225) on another computer` -> `Browser Launch failed on attempt 1/3` -> attempt 2 `Reusing existing browser instance with default configuration` -> `succeeded on attempt 2/3`; cookies `[]`; live Chromium `user-data-dir=/tmp/steel-chrome`. Source explains it: attempt 1 overwrites `this.launchConfig` with the new config (`cdp.service.ts` launchInternal), so attempt 2's `isSimilarConfig(launchConfig, config)` compares the config with itself, returns true, and returns the **old idle browser**. Chromium: `hostname != GetHostName() && !IsChromeProcess(pid)` returns `PROFILE_IN_USE`. | The 200 holds **only for the first create after the container starts**. The steel agent's next persist create (t1 #62) returned **500 after 3 attempts**. "Fallback to a blank browser" is now observed, not inferred. Fixed `--hostname` worked once (R3, n=1) but see M-5. | detail |
| EA-5 | A cookie set ~5 s before release was lost; one set 40 s before survived; n=1; release does `browser.close()` then `process().kill()` | **confirmed** (the author's n=1 stands; the mechanism is now grounded) | Re-read the raw rows and both probe scripts. Fetched Chromium cookie-store source. Read the steel agent's repeats. | Source: `cdp.service.ts:520-521` `await this.browserInstance?.close(); await this.browserInstance?.process()?.kill();`. Chromium `main`, `sqlite_persistent_cookie_store.cc:1237-1239` (fetched 2026-10-10): `kCommitInterval = base::Seconds(30)` "Commit every 30 seconds"; the first pending op arms the timer; also commit at 512 ops. `sqlite_persistent_store_backend_base.cc:235-238`: `DoCloseInBackground()` does "Commit any pending operations", so a graceful store close would have flushed. Steel agent (steel.md §1.a): losses at 2 s and 5 s (Steel release and `Browser.close`), kept at 31, 35, 40 s, boundary 28-32 s. | Two cautions. (a) Probe 1 (5 s) and probe 2 (40 s) differ in more than the wait: probe 2 also set a page cookie, read back first, and ran in a reused container. The single pair could not isolate the variable; the 30 s constant and the steel agent's repeats do. (b) The 30 s timer is re-armed by any later cookie change. Social sites churn cookies, so "wait 30-40 s" must hold at every release, not just after login. The context export is a required journal (see M-6). | detail |
| EA-6 | `lock.py` is a host-local `fcntl.flock` on a file path and cannot coordinate across hosts | **confirmed** | Read `lock.py` @4c837a3. | `lock.py:23` `LOCK_PATH = Path(os.getenv("BB_LANE_LOCK", "/tmp/browser-box/lane.lock"))`; `:56` `fcntl.flock(handle, fcntl.LOCK_EX \| fcntl.LOCK_NB)`. The docstring's "different containers" means a shared bind-mounted path on one host. | none | none |
| EA-7 | An earlier internal job-claim design was described as never leasing a job whose browser profile is already leased, with a hashed lease token and uncertain jobs held, not retried | **partially-confirmed** | Read the code at a pinned commit and looked for what makes the invariant hold under concurrency. | True serially only. Two concurrent claimers can lease different jobs for the same profile, the lease has a fixed length with no renewal, and a held (uncertain) job does not block the next job on that profile. | "A ready-made pattern for one profile, one writer" is true of the idea and false of that code under concurrency. The fleet lease needs DB-enforced uniqueness on the active lease per profile, renewal tied to worker liveness, and a rule that a profile with an uncertain or held effect is itself blocked. | **design-changing** |
| EA-8 | Box Browser-Use runner pins 0.13.10 and refuses anything else; the shared venv has 0.13.11, so `--self-check` fails | **confirmed** | Read `runner.py`, `requirements.txt`, the venv's `dist-info`, PyPI. Did not run `--self-check` (importing `browser_use` is not needed to confirm). | `runner.py:32` `PINNED = "0.13.10"`; `:58` `if version != PINNED: raise RuntimeError(...)` runs before any patching; `requirements.txt` `browser-use==0.13.10`. Shared venv `site-packages/browser_use-0.13.11.dist-info`. PyPI (2026-10-10): latest `browser-use` is **0.13.11**. | The pin is already one release behind PyPI latest, not only behind the scratch venv. | detail |
| EA-9 | Existing code calls TypeSafe by `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, typed questions `{type:"choice", criteria, instructions}` | **confirmed** | Read the trial source, then made my own live call and re-fetched the docs. | The trial's model client (file references withheld) uses the same URL, model and question shape. **Hands-on:** `POST /v1/systemone`, `model: "jev-1.13.0"`, one `choice` question with `criteria` and `instructions` -> HTTP 200 in 348 ms, `answers.target = {type:"choice", choice:"e1", confidence:1.0, probabilities:{e1:1.0,e2:0.0,e3:0.0,none:0.0}}`, `usage {input_tokens:449, output_tokens:49}`. `docs.typesafe.ai/models.md` (fetched 2026-10-10T14:52Z): "Jev 1.13 / `jev-1.13.0` / Price \$42 / \$0.042 per Btok / Mtok", "Output tokens are free", "Rate limits: 100K tokens per second / 80 requests per second". | Version drift to note. (1) The Python SDK pin `typesafe-sdk==0.6.0` appears only in older retired kits; PyPI latest is **0.7.4** (2026-10-09); npm `@typesafe-ai/sdk` latest is 0.6.0. (2) The `jev-agent-kit` docs snapshot (2026-09-17) is stale on limits: 250,000 tok/s and 1,200 rpm then, 100K tok/s and 80 rps now. (3) The `$0.042` in the trial is a hard-coded constant; the docs page confirms it today. | detail |
| EA-10 | An earlier evaluation measured no live System-One/GLM cases; its offline results were scripted choices | **confirmed** | Read the evaluation's reports and evidence files. | The reports state zero live provider calls and no committed model usage. | Offline results are not live accuracy: the live target was **not measured**, not measured-and-failed. | none |
| EA-11 | `box-kit/scripts/export.sh` archives the whole browser-box repo at a ref into the public box-kit repo, excluding only `.claude-plugin`, `.mcp.json`, `skills`, `commands`, `bench`, `tests/test_plugin.py` | **confirmed** | Fetched `export.sh` at `52710179a7...` from `raw.githubusercontent.com`; repo visibility by unauthenticated `api.github.com`. | `export.sh` line: `git -C "$BB" archive "$BB_REF" \| tar -x -C ... --exclude='.claude-plugin' --exclude='.mcp.json' --exclude='skills' --exclude='commands' --exclude='bench' --exclude='tests/test_plugin.py'`. `GET /repos/jbellsolutions/box-kit` -> 200, `private:false`. | Three nuances. (1) The export is **manual**: the operator passes `<bb ref>`, so the leak happens when a ref that contains `fleet/` is exported, not on merge as such. The feature branch already tracks 1,736 `fleet/` files, so exporting that ref leaks too. (2) The excludes are unanchored `tar` patterns, so `--exclude='skills'` and `'bench'` would also drop any `fleet/**/skills` and `fleet/**/bench` while still publishing the rest. (3) `scan.sh` looks for secrets and owner hosts, not for research content. The recommended `--exclude='fleet'` is right. | detail |
| EA-12 | `Guard` takes `cdp_url` as a constructor parameter; only the module-level `GUARD` is bound to the single Steel; one `Guard` can be built per awake browser | **partially-confirmed** | Read all 318 lines of `guard.py` and every use of `GUARD` outside it. | `guard.py` `Guard.__init__(self, cdp_url: str \| None = None)`; `self.cdp_url = cdp_url or steel.CDP`; `:318 GUARD = Guard()`. The class holds all state per instance. But the safety behaviour around it lives in `tools.py` and is bound to the singleton: `:312, :340-343, :376-378, :390, :506, :539-541` use `GUARD.up`, `GUARD.generation`, `reattached_after(generation)`, `wait_ready()` and a `_guard_lost` watcher. Other facts: `_steel_events` hard-codes port 3000 and `/v1/events`; `from . import steel` reads `BB_STEEL_URL` at import; `except TimeoutError` needs Python >= 3.11 (the images are 3.12). | The class is reusable by import. The gating contract (wait before any self-navigating action, re-gate after every Steel relaunch, cancel work when the guard drops) is **not**, and must be rebuilt per profile. The dossier's "cost: one websocket and one asyncio task per browser" is wrong: `Fetch.enable` with `urlPattern "*"` pauses **every request in every tab and worker**, each round-tripping through the guard and spawning a task (`_on_paused`), plus a DNS lookup in a thread. The guard must run next to its browser, and its CPU cost per awake profile is unmeasured. | detail |
| V-1 | (Verdict 2) `security.py` + `guard.py` "come with 18 attack checks and 33 shared scope vectors that the TS port also passes" | **partially-confirmed** | Counted vectors in both files; counted cases in the shield-check script at the pinned JEV ref; box docs. | 33 vectors in `tests/scope_vectors.json` and in `jev-automation/test/scope-vectors.json`, and `vectors` are byte-equal when loaded. `scripts/steel-shield-check.ts` @edcbbae yields **18** `results.push` rows: 2 in the worker/WebSocket block, 5 blocked + 2 allowed, click, page fetch, 1.5 MB request, popup, reattach, blocked-after-reattach, allowed-after-reattach, tab-adoption, close. That is **11 attack cases and 7 positive or behavioural controls**. | "18 attacks" (copied from `docs/security.md:52`) is 18 checks, 11 of them attacks. The script drives jev-automation's `PlaywrightExecutor`, uses the compose name `gateway:8080`, and relaunches the browser, so "reuse as-is" needs a port to a Stagehand/CDP client. The TS test result was not run here. | detail |
| V-2 | (Verdict 5) B5: Jev `act` 0/3 on search, 3/3 on forms, pagination, state, SPA | **confirmed** | Read `docs/benchmark.md` and `bench/results-2026-09-23.json` (30 rows, `jev_ref` edcbbae). | Table matches. | The 0/3 is one deterministic miss (the red "create this page" link) repeated three times, so it is effectively n=1 evidence of a grounding failure, not a rate. | none |
| V-3 | (Verdict 4) An earlier procedure registry "requires every effectful adapter to declare its authority and an independent verifier" | **partially-confirmed** | Read the registry code and spec at a pinned commit. | The only adapter shaped like the fleet's work has a human verifier; the machine receipt exists only for a synthetic CRM. Owner acceptance of a few outcomes is not independent business-result verification. | The gap table names platform receipts as a build item; Verdict 4 should not imply it exists. Owner-accepted outcomes do not scale to unattended posting. | detail |
| V-4 | (Verdict 6, Q2) An older local tool checkout is stale for this fleet; its Steel specialist skill targets Steel Cloud; the anti-detection matrix never ran on Steel; its toy fleet module is capped at 10 | **confirmed** | `git remote -v`, grep of the skill and reference pages, jev-agent-kit READMEs. | The Steel skill and provider page point at `api.steel.dev`, `STEEL_API_KEY`, `wss://connect.steel.dev`. Its anti-detection results doc says Hyperbrowser and Steel have not yet been through its matrix. Its fleet module refuses more than 10. READMEs: "Retired (2026-09-28)". Provider pages: "Last verified 2026-06-11". | A claim that the private origin is ahead of the local checkout is unverified. | none |
| V-5 | (Q3) Repo visibility: public = jev-automation (a fork), jev-agent-kit, super-saiyan-browser, hermes-workforce-router, box-kit; the other six private | **confirmed** | Unauthenticated `api.github.com/repos/jbellsolutions/<name>` on 2026-10-10T14:52Z (no `gh`, no keychain). | 200 and `private:false` for the five public ones; `jev-automation` has `fork:true`, `parent: yatharth1706/jev-automation`. 404 for the six private repos (names withheld; consistent with private). | none | none |
| V-6 | (Q1a) Steel RAM "~550 MiB to 1.36 GiB measured" per awake profile | **partially-confirmed** | Re-read the spike row and the B5 JSON. | 552 MiB is one `docker stats` sample right after an `example.com` session (n=1). B5 rows: `steel_peak_mib` ranges **984 to 1355** over 30 runs. README:133 and `docs/benchmark.md` say "1.36 GiB", but 1355 MiB is **1.32 GiB**. | The upper bound is a MiB/GiB slip of about 3%. The RAM-per-awake-profile argument stands; plan on about 1.0-1.4 GiB under task load. | detail |
| V-7 | (Q3 trial) A per-employee desktop container is expensive and always-on, so contradicts state-at-rest | **partially-confirmed** | Read the trial's architecture notes and config. | The memory figure is a cap, not a measurement. | The number is a cap, not a measurement, and the shape does support stop/start with the volume retained. The reason to reject it (Cua/X11 desktop vs a CDP stack) is sound; the "expensive, always-on" justification is not. | detail |
| V-8 | (Q3 jev-automation) THRESHOLDS: intent 0.25, target 0.35, risk 0.6, submit 0.6 (`decide.ts:80-95`) | **confirmed** | Read `core/decide.ts`. | `THRESHOLDS` block lines 80-95 matches. | `risk` is "Noul probability above which an action needs confirmation": the gate fires only when Jev is >60% sure the action is hard to undo. A 0.35 target floor is low for logged-in account work; keep these as unvalidated defaults. | none |
| V-9 | (Q2) A TypeSafe integration note and a micro-dollar ledger from the older checkout (details withheld) | **confirmed** | Read both files. | The note and the ledger agree: a calendar-month budget cap, integer-unit accounting, and reservations charged in full for interrupted jobs. | none | none |
| V-10 | (Q1 baseline) `make test` -> "Ran 178 tests ... OK (skipped=1)"; operations.md says 167 | **confirmed** | Ran the suite in the worktree (no Docker, no browser, no keys). | `Ran 178 tests in 8.671s` / `OK (skipped=1)`. `docs/operations.md:107` says "167 tests". | none | none |
| V-11 | (Verdict 9a) An earlier private SDR harness's README disclaims fingerprint spoofing, CAPTCHA bypass, proxy rotation, filter evasion | **confirmed** | Read the README at a pinned commit. | `README.md:10` and `:171` (the first version of an email product excludes fingerprint spoofing, proxy rotation, CAPTCHA bypass and per-sender browser profiles). | Line 171 scopes it to "V1" of an email product. It is still a stated stance to put to Justin. | none |
| V-12 | (Gap) The upstream-drift watch queries do not track Stagehand, Steel, Browserbase, DICloak, anti-detect | **confirmed** | Read its config. | Its queries cover other agent tooling. | none | none |
| V-13 | (Q1a) "Cost: one websocket and one asyncio task per browser" for the guard | **refuted** (see EA-12) | Read `guard.py` `_on_paused`, `_spawn`, `verdict`. | Every paused request spawns a task, may do a threaded DNS lookup (60 s cache), and sends a CDP reply; a heartbeat runs every 15 s. | Unmeasured; plan to measure guard CPU per awake profile. | detail |

**Totals.** 12 numbered claims: 10 confirmed, 2 partially-confirmed (EA-7, EA-12), 0 refuted, 0 unverifiable.
Extra Verdict items: 6 confirmed, 5 partially-confirmed, 1 refuted (an unmeasured cost figure). One
design-changing finding (EA-7).

## What the author's raw spike supports

Only `RESULTS.md` and two probe scripts exist; no raw logs were saved, so every row is the author's transcription.

| Row | n | Really measured | Inferred |
|---|---|---|---|
| 1 custom `userDataDir` ignored | 1 | HTTP 200; Steel log `userDataDir /app/api/user-data-dir`; `/tmp/custom-profile-x` absent | none; source and OpenAPI agree |
| 2 vs 3 cookie vs wait | 1 each | on-disk `Cookies` empty at ~5 s; two rows present after a 40 s wait | the 30 s window; the two probes also differ in cookie route, readback and container reuse |
| 6 recreate on same volume | 1 | cookies absent, HTTP 200, `process_singleton` line in the log, cookies present in the volume | "silent fallback to a non-persisted browser". **Now observed** in the steel agent's raw log and explained by `launchInternal` |
| 7 delete `Singleton*` | 1 | cookies present | none |
| Release status | 7 (5 x 200, 2 x 500) | status codes | that the 500s come from the relaunch hitting `process_singleton`. The steel agent also saw zombie accumulation without `--init` (151 after 8 cycles), a likelier cause of a "live" PID |
| RAM | 1 | 552 MiB | n/a |

Platform caveat: all of it ran on arm64 Docker against the 2026-09-16 image; droplets are amd64.

## Unsourced or weakly sourced numbers in the dossier

1. "one websocket and one asyncio task per browser" (Q1a, guard cost). Unmeasured and wrong in kind (V-13).
2. "wait at least 30-40 s". The author measured 5 s and 40 s only. 30 s comes from the Chromium constant
   (which I checked); the 28-32 s boundary is the steel agent's. Neither is in the dossier's sources.
3. "~0.55-1.36 GiB". 552 MiB is a single sample. 1.36 GiB is a MiB/GiB slip (1355 MiB = 1.32 GiB). The
   README's "sits near 900 MB" (line 231) has no raw backing; the bench minimum is 984 MiB.
4. "about 2.3 GiB per employee". A cap, not a measurement (V-7).
5. "18 attack checks". 18 checks, 11 attacks (V-1).
6. "roughly 134 MiB each" for `agent-jev`. From the README (one measurement); not re-measured.
7. "release returned 500 twice". 2 of 7 releases, one container, arm64.
8. "$0.042 per million input tokens". Sourced to the trial's hard-coded constant; I confirmed it against the
   TypeSafe docs on 2026-10-10 (above).
9. "a tab close crashed the whole server 4/5 times". From the `compose.yml` comment ("Reproduced 4/5 on
   2026-09-23"); not re-run.
10. "Computer and profile counts" in a rollout doc: not re-counted.

## Missed issues

Ordered by how much they could change the design.

- **M-1. The lease pattern is not race-safe (EA-7).** Add DB-enforced uniqueness, lease renewal and a rule
  that a held/uncertain effect blocks its profile. This is the one finding that changes what "reuse" means.
- **M-2. Steel echoes the proxy URL, credentials included.** `session.service.ts:173` stores
  `proxy: proxyUrl` and `SessionDetails.proxy` returns it in create, list and get responses over an
  unauthenticated API. The dossier recommends adding `proxyUrl` to the `steel.py` rewrite without this
  caveat. The steel agent reached the same conclusion (D4: Steel gets only a credential-less local
  forwarder). Do not put a credentialed `proxyUrl` into any Steel request.
- **M-3. `CHROME_USER_DATA_DIR` is a no-patch alternative to the fixed persist path** (EA-1). Persist mode
  also always fails `isSimilarConfig` against the idle browser (`userDataDir` differs), so every wake is a
  double launch plus a Guard reattach. The env route avoids that but keeps the profile open (locked) whenever
  the container is up, which matters for volume snapshots.
- **M-4. Steel `latest` has moved.** GHCR `latest` is now index `sha256:459919842a...`; amd64 and arm64
  configs were built 2026-10-06 (16:02 and 16:11 UTC), the same day as source 1131a02. The dossier's
  `sha256:7a161b95...` is still pullable (HTTP 200 on its manifest). All hands-on evidence is from the older
  image on arm64. PRs #348 (userDataDir precedence) and #375 (singleton guard, 409) are both open. A merge
  of either changes behaviour the dossier's recommendations rest on.
- **M-5. A fixed `--hostname` is not strictly safer than deleting `Singleton*`.** Chromium's
  `process_singleton_posix.cc` (fetched 2026-10-10): with the same hostname, a lock whose PID is a live
  *Chromium* process that is not the current instance leads to retries and then `KillProcessByLockPath` ->
  `kill(pid, SIGKILL)`. In a fresh container a stale PID can coincide with a live Chromium (the idle browser or a
  helper). With a different hostname the same check applies first (`!IsChromeProcess(pid)` -> `PROFILE_IN_USE`,
  which is the observed failure). The steel agent's R3 passed once because PID 165 was absent. Prefer
  deleting `Singleton*` under the lease; treat `--hostname` as a supplement.
- **M-6. Cookie churn defeats a one-time wait.** The 30 s timer is re-armed by every later cookie operation, and
  logged-in social pages rotate cookies constantly. "Wait 30-40 s after login" is necessary but not
  sufficient; at every release the last cookie change must be at least 30 s old, or the cookie journal
  (`GET /v1/sessions/{id}/context`) must be the source of truth. The dossier lists context export only as an
  "untested" option.
- **M-7. Failed-launch poisoning is a Steel bug the wrapper must not trust around.** Attempt 1 overwrites
  `launchConfig`, so the retry "reuses" the old idle browser and the API answers 200. The health signal must
  be "the live Chromium's `--user-data-dir` is the identity's and the login probe passes", not an HTTP status
  (the steel agent made the same point for `/v1/health`).
- **M-8. The dossier presents a public companion kit as the "closest existing blueprint" without an
  exposure note.** The exposure question is tracked privately and is not reproduced here.
- **M-9. `jev-automation` has no `LICENSE` file** and no `license` in `package.json`; the upstream
  `yatharth1706/jev-automation` reports no license either. In the clone, all 29 commits touching `core/` are
  by `jbellsolutions`, so the risk is low, but "lift `core/` as a library" should carry a license note.
- **M-10. box-kit's unanchored `tar --exclude` patterns** (EA-11) would also strip `fleet/**/skills` and
  `fleet/**/bench` from an export while publishing everything else.
- **M-11. Silent no-ops in the box itself** (EA-2): `timeout` is dropped, and `session` never sends
  `persist`. This is the box owner's fix; the dossier correctly does not touch it.
- **M-12. `shield-check` cannot be a fleet deploy gate as is** (V-1): it relaunches the browser, is welded to
  jev-automation's Playwright executor, and is pinned by `JEV_REF` in the Makefile.
- **M-13. Python SDK drift and a stale rate-limit snapshot** (EA-9): the dossier's `typesafe-sdk==0.6.0` is
  from retired kits.

## Bottom line

The dossier is accurate where it matters most. Every Steel persistence claim survives, and the two weakest
(EA-4's silent fallback and EA-5's flush window) are now stronger than the author's own n=1 evidence. The
corrections that matter are EA-7 (the lease reference implementation is not concurrency-safe), the Steel
proxy-credential echo (M-2), the guard-cost and gating understatement (EA-12), and the fact that Steel's
`latest` and two open upstream PRs may have changed the behaviour all the hands-on numbers came from (M-4).
