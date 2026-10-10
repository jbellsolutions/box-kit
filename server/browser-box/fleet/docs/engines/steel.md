# Steel (open-source `steel-browser`): the fleet's browser host

**Status: design target. Nothing in this file is built.** The facts below come from the research corpus.
Almost all hands-on numbers were taken on arm64 Docker on the maintainer's Mac, with small samples.
DigitalOcean droplets are amd64. Every number is re-measured on a droplet in M1 before the fleet relies on
it ([DEC] header, [CONS] O-17). That needs Justin's yes for a throwaway droplet ([DEC] Q-12).

The build spec for the wrapper image and the node-agent contract is the sibling file
[`../infra/steel-profile.md`](../infra/steel-profile.md). This file explains how Steel works and what the
fleet does about it. That file says exactly how the wrapper is built.

**Revision note.** This revision applies twelve gaps found by the stress tests in
[`../../research/scenarios/`](../../research/scenarios/) (S01, S05, S07, S08, S12, S13, S14). They are listed
in section 15. They change the topology (one namespace, loopback), the sleep spec (one spec, in the sibling
file), saved-state tags, the viewer rules, and the extension policy. Nothing was run.

## How to read this file

- **Precedence.** Where a dossier and its verification report disagree, the verification report and
  [DEC] win. Corrections are applied here. I do not cite a dossier claim a verifier refuted.
- **Tags.** `measured` = hands-on in [RES] (arm64, small n). `source` = read in the pinned Steel source and
  checked by a verifier (its ID is given, for example STE-3). `source (new)` = read by the author of this
  file in the scratch clone of `steel-browser@1131a02` while writing, and not covered by any verifier. M1
  re-checks every `source (new)` item first. `docs` = a vendor docs page from the capture. `to measure` and `estimate` mean what
  they say. `pending Q-xx` = waits for Justin's answer in the [DEC] table.
- **Corpus pages** are cited by their original vendor URL (the scraped copy is not published).
  [`../../research/corpus/steel/`](../../research/corpus/steel/INDEX.md) keeps the topic map and capture method.
- **Citation key.**

| Key | File |
|---|---|
| [DEC] | [`../../DECISIONS.md`](../../DECISIONS.md) |
| [CONS] | [`../../research/verification/CONSISTENCY.md`](../../research/verification/CONSISTENCY.md) |
| [GEM] | [`../../research/verification/GEMINI-AUDIT.md`](../../research/verification/GEMINI-AUDIT.md) |
| [S-dos], [S-ver] | [`steel` dossier](../../research/dossiers/steel.md), [`steel` verification](../../research/verification/steel.md) |
| [AP-dos], [AP-ver] | antidetect-proxies: [dossier](../../research/dossiers/antidetect-proxies.md), [verification](../../research/verification/antidetect-proxies.md) |
| [SC-dos], [SC-ver] | scale-infra: [dossier](../../research/dossiers/scale-infra.md), [verification](../../research/verification/scale-infra.md) |
| [EA-dos], [EA-ver] | existing-assets: [dossier](../../research/dossiers/existing-assets.md), [verification](../../research/verification/existing-assets.md) |
| [SH-dos], [SH-ver] | stagehand: [dossier](../../research/dossiers/stagehand.md), [verification](../../research/verification/stagehand.md) |
| [RES] | [`../../research/spikes/steel/RESULTS.md`](../../research/spikes/steel/RESULTS.md); blocks are written `[t1 #42]` |
| [BOX-SEC], [BOX-OPS], [BOX-COMPOSE] | the box's [`docs/security.md`](../../../docs/security.md), [`docs/operations.md`](../../../docs/operations.md), [`compose.yml`](../../../compose.yml) |
| [SP] | the build spec, [`../infra/steel-profile.md`](../infra/steel-profile.md) |
| [ARCH] | [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) |
| [SCN] | the stress-test walkthroughs in [`../../research/scenarios/`](../../research/scenarios/); design reviews, not measurements |

---

## 0. The short version

1. **OSS Steel is a one-browser runtime, not a multi-tenant service.** The fleet runs one container per
   awake identity, wrapped by `steel-profile`, and only the node agent talks to it ([DEC] D4; [S-ver] STE-1).
2. **Steel's own answers cannot be trusted about ownership or health.** `GET /v1/sessions/{id}` invents a
   `released` record for any id that is not the active one. `GET /v1/sessions` drops a session that was
   taken over. `/v1/health` is `ok` with no browser running ([S-ver] STE-1, STE-3). Ownership lives in
   fleetd's lease. Health is a live probe.
3. **A login survives a restart only if the fleet does three things.** Delete `Singleton*` before start.
   Let Chromium commit its cookies (a 30 s timer) before the browser closes. Close with a CDP
   `Browser.close`, not with Steel's release alone ([S-ver] STE-2, STE-3, STE-5). The order and every number
   are in one place, [SP] section 8.2.
4. **The cookie journal (context export) is the source of truth for cookies.** The profile tarball is the
   source of truth for everything else ([DEC] D4; [CONS] C-03).
5. **Proxy credentials never enter Steel.** Steel echoes them over an unauthenticated API. Steel gets only
   a credential-less local forwarder address ([S-ver] STE-7; [DEC] D10).
6. **Persona = continuity, not evasion.** Steel's fingerprint injection is off. UA, timezone, locale and
   viewport are pinned. CPU cores, GPU, canvas hash and UA-CH brands stay host-real, so identities of
   different clients do not share a node until that is fixed (pending Q-13) ([DEC] D3; [S-ver] STE-10).
7. **Steel's live viewer has no authentication.** fleetd hands a human a short-lived signed link and the
   node agent proxies only the viewer routes ([DEC] D14).
8. **Steel's Chromium runs as root, with no sandbox and site isolation off.** Fix it or accept it in
   writing (pending Q-08) ([S-ver] "Missed issues" 3).
9. **Upstream is not a plan.** The fixes we need are outsider PRs with no review. The fleet carries its own
   takeover guard, auth-by-isolation, profile handling and persona work ([CONS] C-24).
10. **Pin the image by digest and gate every upgrade** (section 14).
11. **Saved state is tagged, and only a clean generation is restored.** Each bundle and journal records the
    login result, whether the IP was wrong during its wake, and whether the Guard was lost. The pointer moves
    only to a clean one. Parked generations are kept, not used ([SP] 8.2, section 5 below).
12. **Everything that touches the browser lives in one network namespace and uses loopback.** The Guard fails
    open, so a lost Guard is an incident: the node agent blanks every page at once (section 9.3, [SP] 10.1).

---

## 1. Which Steel is this, and what the fleet takes from it

There are two products with one name. The docs at docs.steel.dev describe **Steel Cloud**. The fleet runs the
**open-source `steel-browser`**, self-hosted. No Steel Cloud key exists, and Steel Cloud was never tested
([BRIEF](../../research/BRIEF.md); [C-IDX](../../research/corpus/steel/INDEX.md) "Read this first").
The Gemini conversation that started this work credited Cloud features (profiles, `useProxy`, CAPTCHA,
stealth, 1,000-way concurrency) to the self-hosted Steel. They do not exist there ([GEM] top error 3, rows
4.01-4.16). Anything from that conversation is a hypothesis until a primary source confirms it.

### 1.1 OSS versus Cloud

| Feature | OSS `steel-browser` (what we run) | Steel Cloud (not used) | Evidence |
|---|---|---|---|
| Concurrency | **1 browser per container.** A second create takes the live browser over. | 10 / 100 / 1,000+ by plan | corpus: `https://docs.steel.dev/overview/self-hosting/steel-local-vs-steel-cloud.md`; [S-ver] STE-1, STE-13 |
| API surface | 29 operations. Core sessions, scrape/screenshot/pdf, files, logs, health. | 75 operations. Adds profiles, credentials, secrets, extensions, captchas, computers, agent traces, HLS, events, cost. | [C-IDX](../../research/corpus/steel/INDEX.md); corpus: `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published), `https://docs.steel.dev/openapi.json` |
| Persistence | `persist:true` selects one fixed directory, `/app/api/user-data-dir`. The `userDataDir` value is ignored. `persistProfile` and `profileId` are stripped with HTTP 200. | Profiles API: a user-data-dir snapshot saved on release. 300 MB cap. Deleted after 30 days unused. | [S-ver] STE-3; [EA-ver] EA-1, EA-2; corpus: `https://docs.steel.dev/overview/profiles-api/overview.md` |
| Session context (cookies, storage) | `GET /v1/sessions/{id}/context` and `sessionContext` on create | Same endpoints | corpus: `https://docs.steel.dev/overview/sessions-api/reusing-auth-context.md`; [S-ver] STE-6 |
| Proxy | Bring your own `proxyUrl`, run through a local proxy-chain forwarder. Credentials echoed in API responses. | BYO plus Steel-managed ($10 / $6 per GB, vendor-claim) plus dedicated IPs ($5/IP/month) | [S-ver] STE-7; corpus: `https://docs.steel.dev/overview/stealth/proxies.md`, `https://docs.steel.dev/overview/pricinglimits.md` |
| Stealth | A random fingerprint injected on every launch. No HTTP field pins one. Inconsistent output. | "Stealth Browser" is Enterprise-only in the pricing grid | [S-ver] STE-10, STE-13 |
| CAPTCHA | None | Solver API, $3 / $1 per 1k (vendor-claim) | corpus: `https://docs.steel.dev/overview/stealth/captcha-solving.md` |
| Live viewer | `GET /v1/sessions/debug`: a JPEG screencast plus a mouse and key relay. **Unauthenticated.** `interactive=false` is enforced by the viewer page only; the websocket takes input from any client (`source (new)`, section 7.1). | `debugUrl` iframe. New sessions are headful and stream WebRTC H.264. **The docs say the debug URL is also unauthenticated.** | [S-ver] STE-9; corpus: `https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md` |
| Timeouts | **None.** `KILL_TIMEOUT` is parsed and never used. | `timeout` default 300,000 ms. Max 15 min / 1 h / 24 h by plan. | [S-ver] STE-8; corpus: `https://docs.steel.dev/overview/pricinglimits.md` |
| Auth on REST, CDP, viewer | **None.** CORS `origin: true`. Raw CDP also on port 9223 (nginx to 9222). | API key (`steel-api-key`) on REST. The viewer URL stays open. | [S-ver] STE-8 |
| Health | `/v1/health` is `ok` whether or not a browser runs | n/a | [S-ver] STE-3 |
| Recordings | A recorder extension in headless sessions posts to `/v1/events`, then into `/v1/logs/*` (in memory unless `LOG_STORAGE_ENABLED`). No video. | Session replay, HLS, traces | [S-dos] Q1 (source: `cdp.service.ts`, `sessions.routes.ts`); corpus: `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published) |
| Files | `/v1/sessions/{id}/files*` routes are served (the docs wrongly say "Not supported"). Function untested. | Files API | [C-IDX](../../research/corpus/steel/INDEX.md) "docs and source disagree" #1 |
| Extensions | `extensions:["<name>"]` loads `/app/api/extensions/<name>`. The docs say `api/src/extensions/`; the code reads `api/extensions/`. | Extensions API | [S-dos] Q1 table (source); corpus: `https://docs.steel.dev/overview/self-hosting/steel-local-vs-steel-cloud.md` |
| Credentials store | None | `/v1/credentials`, `/v1/secrets` | [C-IDX](../../research/corpus/steel/INDEX.md) |
| Licence and use policy | Apache-2.0. No use policy. | ToS bans using it "to violate any website's terms of service" (line 187 of the captured ToS) | [S-ver] STE-13; corpus: `https://docs.steel.dev/overview/legal.md` |
| Cost | Free. You pay for droplets. | Launch $0 + usage. Scale $250/mo + usage. Enterprise custom. (vendor-claim) | corpus: `https://docs.steel.dev/overview/pricinglimits.md`; [S-ver] STE-13 |

**Why the fleet does not use Steel Cloud** ([DEC] D4, last paragraph): its ToS conflicts with the use case,
its stealth browser is Enterprise-only, its profiles are capped and expire, its viewer URL is also open, and
nothing on it was tested. The paid backup is Browserbase ([DEC] D11), not Steel Cloud.

**Docs versus source** (source wins): the Local-versus-Cloud page says Files are "Not supported" (the routes
exist), the Docker page's health path `/api/health` is stale (it is `/v1/health`), and its Chrome version is
stale (Debian `chromium`, unpinned in the Dockerfile, was 152.0.7977.82 in the tested image)
([C-IDX](../../research/corpus/steel/INDEX.md); corpus: `https://github.com/steel-dev/steel-browser/blob/1131a02/api/Dockerfile`).

**Not used from the OSS image:** the Hermes Steel plugin (`https://github.com/steel-dev/hermes-steel/tree/d8a1e39/`) would hand
Hermes a Steel URL, which the fleet forbids. Also not used: `/v1/scrape`, `/v1/screenshot`, `/v1/pdf`,
`/v1/search` and their session-bound twins (they navigate the shared browser outside the lease), Selenium
mode, `fullscreen`, `credentials`, `logSinkUrl` (deprecated; it would send logs elsewhere), `extra`.

---

## 2. Sessions API: the calls the node agent makes

Only the node agent calls Steel. No Hermes profile, worker or human ever holds a Steel URL
([DEC] D1, D4; [SC-dos] Q6).

### 2.1 The calls

| Purpose | Call | What it does | What to trust |
|---|---|---|---|
| Is Node up? | `GET /v1/health` | Returns `{"status":"ok"}` | **Nothing but "Node answers".** `isRunning()` is `this.browserInstance?.process() !== null`; with no browser that is `undefined !== null`, which is true ([S-ver] STE-3, source). |
| Start the identity's browser | `POST /v1/sessions` | Launches Chromium on the mounted profile. A persist create never matches the idle browser's config, so **Chromium launches again** ([EA-ver] M-3). | The 200. It also returns 200 when the wrong profile is loaded ([RES] `[t1 #56]`). |
| Cookie journal | `GET /v1/sessions/{id}/context` | Cookies (including httpOnly) from memory. localStorage and sessionStorage from disk and open pages. IndexedDB from open pages. | The cookies. It reads the **active** session whatever `{id}` says ([S-ver] STE-1). |
| End the session | `POST /v1/sessions/release` (or `/{id}/release`) | Dumps context, closes the browser, relaunches an idle default browser on `/tmp/steel-chrome` | Nothing about the profile. It left `Singleton*` in 6 of 6 persist-mode runs ([S-ver] STE-3). Also acts on the active session whatever the id. |
| Viewer | `GET /v1/sessions/debug?interactive=true&showControls=true`, plus the cast websocket `/v1/sessions/<id>/cast` | A JPEG screencast and an input relay | The page. The cast websocket **ignores the id** and attaches to the active session ([S-ver] STE-1, STE-9). |
| Tabs | `GET /v1/sessions/{id}/live-details` | Lists open pages | The page list. `browserVersion` serialises as `"[object Object]"` (issue #332). |
| Real readiness | Not a Steel call (see 2.4) | | |

CDP is also served on port 3000 at `ws://<host>:3000/`. Dial it by IP or `localhost`, because Chromium rejects
other Host headers ([EA-dos] section 4). **Who dials what:** the Guard and every actor run inside the identity's
network namespace and dial `ws://127.0.0.1:3000/`; the node agent, on the host, dials the holder's bridge IP on
port 3000 for the calls in the table above ([SP] 10.4). Steel also publishes raw CDP on 9223 (nginx to 9222).
The fleet never publishes 9223 and starts the container with `--no-nginx` (the entrypoint supports it;
`source (new)` `api/entrypoint.sh`; to verify nothing in the session path needs it).

### 2.2 The create body

```json
{
  "sessionId": "<wake uuid>",
  "persist": true,
  "headless": false,
  "userAgent": "<pinned; Chrome major equals the real engine major>",
  "skipFingerprintInjection": true,
  "timezone": "<pinned IANA zone>",
  "dimensions": { "width": 1366, "height": 768 },
  "proxyUrl": "http://127.0.0.1:<forwarder port>",
  "blockAds": false
}
```

`extensions: ["stagehand"]` is added to this body only when the identity's persona says mode A (section 9.1).
It is never in the body of an `account` flavor wake, a human-login wake or a canary wake.

| Field | Why |
|---|---|
| `persist: true` | Selects the fixed directory. A volume mounted there **is** the identity ([EA-ver] EA-1; [S-ver] STE-3). |
| `headless` | Always sent. Omitted means `CHROME_HEADLESS`, default true (`https://github.com/steel-dev/steel-browser/blob/1131a02/api/src/env.ts`). Default for logged-in identities is headful under Xvfb; headless is the fallback and the only mode the Stagehand recipe was measured in ([DEC] D9; [SH-ver] SH-3). Chosen per identity in M1. |
| `userAgent` + `skipFingerprintInjection: true` | Turns off the random fingerprint and pins the UA. The UA's Chrome major must equal the engine's real major, or `navigator.userAgentData` contradicts it ([AP-dos] section 3). Without a pinned UA, `skipFingerprintInjection` leaks `HeadlessChrome` in headless ([RES] `[t1 #111]`). |
| `timezone` | Always sent. With the proxy down and no value, Steel fell back to UTC ([RES] `[t1 #75]`). Steel passes the value to Chromium as `TZ` (`source (new)` `cdp.service.ts` launch `env`). |
| `dimensions` | Window size. It does not set `screen`; headless `screen` stays 800x600 ([AP-ver] AP-4). |
| `proxyUrl` | The credential-less forwarder only (section 6). Never an upstream URL with a password. |
| `blockAds: false` | Always sent. When omitted, `validation.ts:144` treats it as on and `cdp.service.ts:447` treats it as off (`source (new)`). Ad-blocking also changes how pages behave. |
| `extensions` | Only when the persona's `extension_mode` is `A`: the `research` flavor, or an `account` identity that M1 assigned to Stagehand. Absent otherwise, and always absent on a human-login or canary wake. The caller never chooses it (section 9.1). |
| `sessionId` | Our wake id, for log correlation only. Steel's id checks are meaningless (2.4). |

**Fields never sent** (they return 200 and do nothing, or do harm): `userDataDir` as a path, `persistProfile`,
`profileId`, `useProxy`, `solveCaptcha`, `timeout`, `stealthConfig` ([S-ver] STE-3; [EA-ver] EA-2; [SC-dos]
section 4 note 1); `credentials`, `logSinkUrl`, `extra`, `isSelenium`, `fullscreen`, `optimizeBandwidth`.
The box's own `steel.py` sends the ignored fields. The fleet must not copy that code ([CONS] C-04).

### 2.3 One create, one relaunch

A persist create relaunches Chromium. Failed-launch retries can also return the old idle browser with 200
([EA-ver] M-7). So: **the Guard and every engine attach only after the create returns and the probes in 2.4
pass, never at container start** ([EA-ver] EA-12, M-3).

### 2.4 Answers that cannot be trusted, and the fleet's substitute

| Steel says | What is true | Fleet substitute |
|---|---|---|
| `GET /v1/sessions/{id}` returns `released` | Any id that is not the active one gets a made-up `released` record, even a random UUID ([S-ver] STE-1). | fleetd's lease and the node agent's own record of the wake id. |
| `GET /v1/sessions` lists sessions | A taken-over session is missing from the list ([S-ver] STE-1). | Same. A takeover leaves no trace in the API. |
| `/v1/health` = `ok` | True with no browser ([S-ver] STE-3). | Browser probe: CDP `Browser.getVersion` answers, Chromium's argv (read from the host with `docker top`) has `--user-data-dir=/app/api/user-data-dir`, the persona probe passes, then the per-site login probe. |
| `POST /v1/sessions` 200 | Chromium may be running on `/tmp/steel-chrome` with an empty jar ([RES] `[t1 #56-#60]`). | Same live-argv check, then the login probe. |
| Session `userAgent` | Run C reported `Chrome/128` while the page saw `HeadlessChrome/152` ([AP-ver] missed issue 12). | Read the UA from the page, never from the session response. |
| `proxy` in create, list and get | The full credentialed upstream URL ([S-ver] STE-7). | Steel never receives one. |

---

## 3. One browser per container

**Measured:** a second `POST /v1/sessions` with the same config silently took over the live Chromium. The
first client's tab and JS state survived, while `GET /v1/sessions/{A}` said `released`. A different config
relaunched Chromium and dropped the first client. Nothing returned 409 ([RES] `[t1 #42]`; [S-ver] STE-1).
Source: `activeSession` is one object (`session.service.ts:67`) ([SC-ver] SCA-1). An independent third party
reproduced it in upstream PR #375 ([S-ver] STE-1).

Rules the fleet follows:

- **One container per awake identity.** It has its own volume, its own network, its own egress rules and a
  stable name. The unit of scale is the container ([DEC] D4, D12).
- **The node agent is the only caller and serialises.** It issues at most one create per container per wake
  and refuses a second create while a wake is live. fleetd's lease is the ownership truth ([DEC] D12).
- **A human takeover is a lease change, not a second session.** The node agent kills the agent's actor
  containers first and confirms none is running, then opens the viewer (section 7; [SP] 10.3).
- **Do not wait for Steel to add the guard.** PR #375 has no review and no maintainer owner
  ([S-ver] STE-14).

---

## 4. Persistence model, the Singleton trap, and the safe release

### 4.1 What persists where

- With `persist:true` Chromium's user data lives in `/app/api/user-data-dir`. Mount the identity's volume
  there. Otherwise Steel uses `CHROME_USER_DATA_DIR` or `/tmp/steel-chrome`, which dies with the container
  ([S-ver] STE-3; [SC-ver] SCA-2). Measured: a profile on a volume survives `docker restart` and a recreate
  under a new hostname ([RES] `[t1 #73]`; [SC-ver] SCA-4).
- **The alternative**, `CHROME_USER_DATA_DIR` with no `persist`, avoids the double launch but keeps the profile
  open and locked whenever the container is up ([EA-ver] M-3). The fleet uses `persist:true` ([DEC] D4).
- Cookies are encrypted with `--password-store=basic`, a fixed key, so the profile is portable between
  containers and is **not protected by the browser**. The bundle layer encrypts ([SC-ver] SCA-4; [CONS] O-09).
- Cross-host and x86 restore of a tarball was **never run**. The plan depends on it (**to measure**, [CONS]
  O-17).

### 4.2 The 30 second cookie window

Chromium commits cookies to SQLite on a **30 s timer** (`kCommitInterval`, `sqlite_persistent_cookie_store.cc`
at Chromium 152.0.7977.82). Every cookie write re-arms it. There is no CDP flush command ([S-ver] STE-2).

| Wait after the write | End by | Cookie kept? | `Singleton*` left | Source |
|---|---|---|---|---|
| 2 s | Steel release (n=2) | lost (localStorage also lost) | 3 files | [RES] `[t1 #53, #54, #56]` |
| 2 s | raw `Browser.close` (n=2) | lost | 0 | same |
| 5 s | Steel release / raw close | lost | not counted | [RES] `[t1 #45, #56]` |
| 31 s | client closed, `Browser.close`, then Steel release | **kept** (n=1) | **0** | [RES] `[t1 #73]` |
| 35 s | Steel release | kept (n=1) | stale lock | [RES] `[t1 #65]` |
| 40 s | Steel release | kept (n=1) | stale lock | [EA-dos] spike row 3 |

Reading it right ([S-ver] STE-2; [CONS] C-03):

- **31 s is the minimum** ([DEC] D4). It is the single measured keep, with about 1.5 s of margin over the
  30 s timer. The spec's default hold is **35 s, a chosen margin and not a measured threshold**. M1 measures
  the real threshold.
- Social pages rotate cookies constantly. "Since the last cookie change" cannot be read off a clock. So the
  hold is a floor, and **the cookie journal is the source of truth for cookies**, not the disk.
- A raw `Browser.close` fixed the stale lock but did **not** save a cookie written 5 s earlier. Why Steel's
  own release leaves `Singleton*` while a raw close does not is unexplained ([S-ver] "Missed issues" 5). The
  procedure below is empirical, not mechanistic.

### 4.3 The Singleton lock trap

**What happens** ([RES] `[t1 #56-#62]`; [EA-ver] EA-4):

1. Steel's release leaves `SingletonLock`, `SingletonSocket` and `SingletonCookie` in the profile. Count: **6
   of 6** persist-mode runs. (The earlier "7 of 7" included a live lock in `CHROME_USER_DATA_DIR` mode,
   [S-ver] STE-3.)
2. A new container starts on that volume. Chromium sees a lock owned by another computer and refuses
   (`process_singleton_posix.cc`: "in use by another Chromium process ... on another computer").
3. Steel's launch retry overwrites its config, then "reuses" the old idle browser. **The create answers 200,
   but Chromium runs on `/tmp/steel-chrome` with empty cookies** ([EA-ver] EA-4).
4. The next create returned **500 after 27 s**. `/v1/health` stayed `ok` ([RES] `[t1 #61, #62]`).

**What the fleet does:**

- **Delete `SingletonLock`, `SingletonSocket`, `SingletonCookie` from the volume, on the host, under the
  identity's lease, before the container starts.** This is the preferred fix ([DEC] D4; [EA-ver] M-5).
- Also set a fixed `--hostname` per identity. It is a supplement, not a fix: a same-host lock whose PID
  matches a live Chromium process can still be killed. That PID-collision risk is narrower than first
  thought (Chromium checks that the process is named `chrome`; Debian's binary is `chromium`) but it is
  unverified ([S-ver] STE-5).
- After every launch, assert the live argv has the right `--user-data-dir`. A 200 proves nothing.
- Never `docker stop` a live identity. With `--init` it took 10.4 s and left the lock (exit 137 seen
  without `--init`) ([RES] `[t1 #74]`; [S-ver] STE-4). Steel has no SIGTERM handler.
- Always run with `--init`. Without it, 8 create/release cycles left 151 zombie processes. With it, 0
  ([RES] `[t1 #72]`).

### 4.4 The safe release (the only way an identity sleeps)

**The numbers, the flag, the tags and the failure list are in [SP] section 8.2, which is the one spec of the
sleep** *(S01-6)*. This section gives the order and the reason for each step, and repeats no number. The order is
the single tested sequence (n=1, a synthetic cookie on example.com, same host, same arch) with two changes marked
*added*. Treat it as the best known order, not a proven one ([S-ver] STE-5). (Step numbers here are one higher
than [SP]'s, because this list starts with the lease.)

1. **Hold the lease** and stop agent actions.
2. **Quiesce.** Actors disconnect their own way and their containers stop. A CDP client's `browser.close()` only
   disconnects, but Stagehand must use `stagehand.close()` (its `browser.close()` sends `Browser.close` and
   kills the browser) ([SH-dos] Q2; [AP-ver] V-7).
3. **Record the login result** for each site (the newest probe of the wake, and any blocker an actor reported).
   *Added.* It becomes the generation's `auth_result` tag.
4. **Navigate open tabs to `about:blank`** to stop page timers (*added*, **to measure**).
5. **Export the context** (cookie journal #1, crash insurance). Instant, includes httpOnly. [DEC] D4 puts the
   export here.
6. **Hold** until the cookies have been quiet for the floor ([SP] 8.2: the 31 s keep is the floor, the default
   is a chosen margin above it, the poll interval and the maximum are estimates set in M1). If the cookies never
   go quiet, stop at the maximum and flag the generation `journal_authoritative`. That is the only name for the
   flag; [ARCH]'s `cookies_unflushed` is retired.
7. *Added, untested:* **export the context again** (journal #2, the one of record). Cookies can rotate during
   the hold, so this one is fresher. It is read-only, so the risk is low.
8. **CDP `Browser.close`** on the browser websocket. It left 0 `Singleton*` files in 3 of 3 runs.
9. **`POST /v1/sessions/release`.** Without it Steel keeps the session `live` ([RES] `[t1 #45, #73]`).
10. **Check the volume is quiet:** no `Singleton*`, and no Chromium holding the volume.
11. **Snapshot** the volume to an encrypted bundle, upload, verify, **tag** it, then move the pointer in
    Postgres with a check on the fencing token, **only if the generation is clean** ([SP] 8.2).
12. Stop the container, drop the network, delete the local volume.

If step 8, 9, 10 or 11 fails, the identity goes to `held`. Nothing is deleted. A person looks. A held volume
leaves the node only through `salvage` ([SP] 8.6).

**Why tag and park.** A generation written while the account was logged out, challenged or restricted, while the
exit IP was wrong, or while the Guard was down is real data. It is also not a state to wake from by default.
A cookie jar the platform saw over a second IP may be bound to a second place; a jar from a revoked session is
useless and may look like suspicious reuse. So such a generation is uploaded and kept, and the pointer stays on
the last clean one. The rules are in [SP] 8.2 and 8.4.

### 4.5 Crashes

A killed container loses up to 30 s of cookie writes and any in-memory state. The lease expires, the run is
marked interrupted, and the identity restores from the last clean bundle plus the newest **clean** journal. Any
open effect becomes `uncertain` and blocks replay ([DEC] D13; [SC-dos] Q3). Journals are taken on a timer during
long wakes (interval **to measure**; scale-infra suggests every few minutes, [SC-dos] section 4 note 10), and
each one is tagged when it is made, so a crash does not lose its tags.

---

## 5. Context export and import

The export is a necessary second copy. It is not a replacement for the profile ([S-ver] STE-6).

| Item | Round-trips? | Notes |
|---|---|---|
| Cookies, including httpOnly | Yes. Export is instant and import runs before the first navigation. | 1 export, 3 imports ([RES] `[t1 #67, #73]`) |
| localStorage, sessionStorage | **Only after rewriting keys** from hostname to origin, and only on Steel's primary page | Export keys by hostname, import looks up by origin (`utils/context.ts`). A fresh `newPage()` tab got `null` ([RES] `[t1 #68]`). |
| IndexedDB | Came back **empty** in the one test, though a record existed | Unexplained ([S-ver] STE-6). Steel's format has an IndexedDB path ([SC-ver] SCA-15). Treat as untested. |
| Service workers, Cache Storage, passwords, preferences | Never covered | Read from the code, not measured |

Rules: take the journal at every release and on a timer. Encrypt it with the bundle's key. Tag it like a
bundle. Use it to re-inject cookies if a wake's login probe fails, **but only a clean journal, and only when the
identity's last recorded result is not `checkpoint`, `captcha` or `restricted`** *(S05-12)*: replaying the
cookies of a session the platform has revoked or challenged can itself look like suspicious reuse. The exact
rule is [SP] 8.1 step 14. **Combining `sessionContext` with `persist:true` is untested.** An alternative is to
set the cookies over CDP into the running browser; also untested. If the probe still fails, the identity goes
to `needs_reauth` and a human logs in. The fleet never loops on login.

---

## 6. Per-session proxy and the credential-less forwarder

**What Steel does** ([S-ver] STE-7; [RES] `[t1 #75, #78]`): `proxyUrl` is accepted and run through a local
proxy-chain forwarder on `127.0.0.1:<random>`. Chromium sees only the local URL. With a dead upstream it
failed closed: HTTPS gave `ERR_TUNNEL_CONNECTION_FAILED`, HTTP got proxy-chain's own 594 page, and there was no
direct egress. That is one failure mode (connection refused). Auth failure (407), timeouts and DNS failure
were not tried.

**What is wrong with it:**

- Steel stores `proxy: proxyUrl` and **returns the credentialed URL** in create, list and get responses, over
  an API with no auth and CORS `origin: true`.
- With no `timezone`, Steel looks the zone up through ipinfo.io. With the proxy down it fell back to UTC.
- Chromium sends `localhost`, `127.0.0.0/8`, `[::1]`, `169.254.0.0/16` and `fe80::/10` **around** the proxy.
  On DigitalOcean that includes the metadata service (inference from Chromium's `net/docs/proxy.md`;
  unverifiable here).
- At boot, Steel's idle browser calls ipinfo.io **directly**, outside any proxy: the cold-start timezone fetch
  runs when the service is built (`source (new)` `cdp.service.ts` ~L150; `timezone-fetcher.service.ts`).

**What the fleet does** ([DEC] D10, D4):

1. A **forwarder** owned by the node agent holds the identity's dedicated static ISP IP credentials. Steel
   gets `http://127.0.0.1:<port>` and nothing else. The forwarder adds the upstream credentials itself.
2. **Where it lives.** Inside a container, `127.0.0.1` is that container's own loopback. So the forwarder runs
   as a sidecar that **shares the browser container's network namespace**, through a small network-holder
   container that every member joins: Steel, the forwarder, the runtime (Guard, exporter, login prober) and
   the actors (executor, Stagehand, Browser-Use), each in its own container ([SP] 1, 3.1). The credentials sit in
   the forwarder's own process space and a tmpfs secret file that **only the forwarder mounts**. They are not in
   the Steel container's environment, not in `docker inspect`, and not readable by an actor. The alternative
   (the forwarder on an internal per-identity network) was considered and not chosen. This is this spec's
   choice; [DEC] D4 only says "loopback" ([SP] section 6). It is topology **T-L**, and it matches [ARCH]
   section 2.2 except that the holder, not the Steel container, owns the namespace, and the actors are split
   into containers of their own so that "kill the workers" is one operation ([SP] 10.3).
3. **Fail closed, mid-session included.** No upstream, a failed auth, or an exit-IP change means no traffic
   and the node agent stops the session. IPRoyal "sticky" sessions swap IPs silently unless `_killswitch-1`
   is set ([AP-ver] missed issue 8). A static ISP IP should not swap, but the check runs anyway.
4. **Exit-IP check** before the browser starts and on a timer. It must equal the pinned IP. The echo endpoint
   is fleet-owned (a design choice; a third-party echo would see every identity). A **sleeping** identity is
   checked too: the node agent's `probe_ip` starts only the holder and the forwarder, with no browser, and
   reports a class (`mismatch`, `unreachable`, `auth_failed`, `timeout`) so a dead IP is found before a job needs
   the identity *(S07-13)*. The credential reaches the node for that call only ([SP] 9.6).
5. **Egress.** The identity's network allows traffic only to the upstream proxy's IP and port. Everything else
   is dropped, including DNS, the metadata address, the VPC and the host. That also covers Steel's direct
   boot-time ipinfo call.
6. **`PROXY_INTERNAL_BYPASS` stays empty** ([CONS] C-08; unverified until a droplet run). Do not use
   `--proxy-bypass-list=<-loopback>`: it would send loopback through the proxy, which breaks the forwarder at
   `127.0.0.1`. **Loopback inside the namespace is guarded by the Guard and by Chromium's Local Network Access,
   not by the egress rules.** The egress chain never sees a loopback connection. That is the weak spot: see
   section 9.3 and [SP] 10.1.
   **There is no exception for the bridge IP.** The earlier draft ran the workers outside the namespace and gave
   the forwarder a rule to serve a `CONNECT` to its own bridge IP on port 3000, so that Stagehand's extension
   could dial the CDP URL back. That rule is gone *(S13-6)*. It could not tell the extension's request from a
   page's own request to Steel's unauthenticated API at the same address. Under T-L the actors and the extension
   dial `127.0.0.1:3000`, which Chromium bypasses by itself ([SH-ver] SH-3, the measured attach used a loopback
   URL). The forwarder refuses every private destination, its own bridge IP included, and answers any
   non-proxy request on its listener with a fixed refusal ([SP] 6.2 rule 9). The old shape survives only as
   the fallback **T-O**, and only for the `research` flavor ([SP] 10.4).
7. Timezone, locale and geo are resolved once at identity creation from the IP, stored in the persona, and
   never looked up again ([AP-dos] Q5).
8. A new IP is accepted only after the vetting rule ([DEC] D10 / O-10: exit-IP match, ISP-class ASN,
   reputation, geo match, provenance statement). That rule belongs to identity creation, not to this file.

---

## 7. The live viewer, human login, and how fleetd brokers it

### 7.1 What the OSS viewer is

- A canvas with a JPEG screencast (quality 75), a tab bar, a URL bar and back, forward, reload. It also
  relays mouse and key events ([S-dos] Q4; [RES] `[t1 #89]`, screenshots `spikes/steel/viewer-{1,2,3}-*.png` (image not published)).
- **No authentication.** The route has `onRequest: []`. The cast websocket ignores the session id
  ([S-ver] STE-9). `debugUrl` is a fixed URL with no session id ([RES] `[t1 #41]`).
- The inspector (`/v1/devtools/inspector.html`) returned 404. `/ui` is not in the API image.
- The Steel Cloud viewer streams WebRTC H.264 for headful sessions. **The OSS viewer was only tested in
  headless**; headful under Xvfb is **to measure**.
- **`interactive=false` is a property of the page, not of the server** *(S12 G12-8; `source (new)`, read in
  `steel-browser@1131a02`, not covered by a verifier; M1 re-checks it on the tested image)*. The word
  `interactive` appears only in the viewer page template, the query schema and the controller that renders the
  page. The cast websocket handler (`casting.handler.ts`) never reads it, and it acts on `mouseEvent`,
  `keyEvent`, `navigation`, `closeTab` and `getSelectedText` messages from any client. The Cloud docs call `interactive=false` "a
  read-only view" (`https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md`); on the OSS server
  that is only true if the client behaves.
- **A viewer connection is not passive** (`source (new)`, to measure). For each cast connection the handler
  opens its own puppeteer connection to the browser, creates a CDP session on the page it shows, calls
  `bringToFront()` on that page (in per-page mode) and starts a screencast. Input from a person arrives as
  CDP `Input.dispatchMouseEvent` and `Input.dispatchKeyEvent` calls. So a person in the viewer is a human
  driving an automation-capable browser, and a watcher can change the foreground tab and add CDP activity.

### 7.2 What was measured, and what was not

| Works (n=1 each, synthetic) | Not forwarded | Untested, and the likeliest login blockers |
|---|---|---|
| Typed text reached the remote field. A `window.open` popup became the active tab. | Key **modifiers** (key events carry none). Paste, unless the page is embedded with `clipboardBridge=true`. | Enter, Backspace, Tab, arrows (sent as `keyDown` without text). Non-ASCII and IME input. Native JS dialogs. HTTP basic auth. Passkeys and WebAuthn. File pickers. Real latency. |

The "human" in the test was a headless Chrome driven by Playwright typing a 12-character string, with no
submit ([S-ver] STE-9). So "good enough for a human login" is an extrapolation. **The viewer is an M1 gate,**
and D14 is a plan, not an established path ([DEC] D14).

### 7.3 How fleetd brokers it

1. **Nothing is published.** The Steel port (3000) and 9223 are reachable only by the node agent
   ([SC-dos] Q6).
2. **A human lease.** When a login, checkpoint or 2FA is needed the identity moves to `needs_reauth` or
   `checkpoint` and fleetd takes a human lease. The lease bumps the fencing token, so the agent's calls fail
   closed ([DEC] D12, D14). The node agent writes the fence file, `docker kill`s the actor containers, confirms
   none is running, and only then opens the viewer route ([SP] 10.3). A click already handed to CDP cannot be
   recalled, so a step that was in flight is `uncertain`.
3. **A signed link.** fleetd issues a short-lived, single-use link bound to (identity, lease generation, the
   human it was issued to). TTL and how the human is authenticated at the gateway are **pending a design
   decision**: without a human identity system, the link is a bearer capability and must be treated that
   way. It is an open design item and not one of Justin's questions.
4. **Route allowlist.** The gateway proxies through the node agent to the identity's container and passes
   only: `GET /v1/sessions/debug` and the cast websocket upgrade. The proxy sets `interactive` and
   `showControls` itself (true for a control route, false for a watch route, whatever the client sent); `theme`
   and `pageIndex` pass through. It blocks everything else: the REST API (the list route leaks the proxy URL),
   the CDP websocket at `/`, `/documentation`, `/v1/logs/*`, `/v1/events`, files, scrape.
5. **A fleet embed page.** It frames the viewer with `clipboardBridge=true` so a human can paste a 2FA code.
   Otherwise codes are typed by hand ([S-dos] Q4).
6. **Typed secrets are in transit.** Agents never type credentials, but humans do, and the keystrokes cross
   fleet infrastructure. Policy: **no logging of viewer websocket payloads and no recording of the stream.**
   Steel's recorder extension (loaded in headless sessions) posts page events to Steel's own log store;
   what it captures is undocumented. The wrapper removes the recorder extension from the image, so it never
   loads (`source (new)`: `getExtensionPaths` skips a name whose directory is absent; **to verify** that a
   headless create works without it). The box's Guard already refuses the recorder's posts
   ([BOX-SEC] "The in-browser guard").
7. **The Guard stays on** during the human session. A person can type any address into the viewer's URL bar.
8. **End of login.** The human presses "login done". fleetd keeps the browser up for the cookie hold (section
   4.4), runs the login probe, then either returns the lease to the agent or sleeps the identity with the
   safe release. Who held the lease, and when, is recorded.
9. **Rules for a person in the viewer** *(S12 G12-7; the full rules are [SP] 9.4; all values are to set)*.
   - The agent's maximum-wake and inactivity timers do not run against a person. Two viewer timers do: an idle
     timeout, reset by input activity (a count of input frames, never their content) or by an explicit
     "extend", and a hard maximum that "extend" cannot move. A reader who is not typing is therefore cut off
     only by the idle timeout, not slept by an agent timer. The memory watch warns and does not restart a
     browser under a person.
   - A takeover is refused while the identity is waking, quiescing or sleeping.
   - A dropped connection can reopen within a short reconnect window for the same operator, with no new ticket
     and no new takeover, so a network blip does not cost the seat or move the token. After the window the
     person takes over again.
   - A new takeover closes any earlier viewer route. Two people never hold one browser. fleetd calls
     `viewer_close` on every token change, and the node agent also closes a route the moment it sees a higher
     token.
10. **Watch tickets** *(S12 G12-8; [SP] 9.5)*. A person can look without taking the lease. No lease, no token
    bump, no kill: it cannot preempt the agent. The same operator login and tenant scoping as a takeover. The
    node agent **forces `interactive=false` and drops every client-to-server frame itself**, because the
    server does not (7.1). Each watch is an audit row with no payload. It shows everything on screen, DMs
    included, so it is under the same Q-07 data-handling decision as the rest. Because a cast connection moves
    the foreground tab and starts a screencast, a watch is allowed only to the tab the executor reports as
    active, and the default is **off for `account` identities until M1 measures the side effects**, on for
    `research` identities. **Not offered for Browserbase-homed identities**: their Live View URL is a bearer
    capability and its read-only mode is a property of the embedding page only
    ([`https://docs.browserbase.com/platform/browser/observability/session-live-view.md`](https://docs.browserbase.com/platform/browser/observability/session-live-view.md)); screenshots are the
    substitute there.

---

## 8. Fingerprint and stealth: what the fleet does and why

### 8.1 What OSS Steel does ([S-ver] STE-10; [AP-ver] AP-4)

Steel generates a **new random fingerprint on every launch** with `fingerprint-generator` (Chrome 146+
requested, relaxed when impossible) and injects it over CDP. The REST controller drops any `fingerprint`
field. The `userAgent` field or `skipFingerprintInjection` turns generation off. The output is internally
inconsistent:

- The UA says Chrome 139 to 145 while the engine is 152.
- Headless `screen` is 800x600 inside a 1920x1080 window. (That is headless Chromium's default, not a
  generated value; headful gave 1920x1080.)
- `navigator.userAgentData.brands` is empty.
- On the arm64 test host the UA said `Linux aarch64` while `navigator.platform` said `Linux x86_64`.
- The main thread and workers report different GPUs. Patched functions fail the `toString` native check.
- Steel adds a visible cursor `div#__cursor__` to headless pages, and the first navigation on a fresh CDP tab
  can miss injection ([RES] `[t1 #93-#96]`).

Bot-page results, one or two runs each, public test pages only (weak proxies for Meta, TikTok or X)
([S-ver] STE-10; [RES] `[t1 #97, #100-#104, #111]`):

| Mode | browserscan | creepjs headless / stealth |
|---|---|---|
| Default injection | Robot (2 of 2) | 33% / 20% |
| UA pinned, headless | Normal | 0% / 0% |
| Headful under Xvfb, no UA pin | Robot | 0% / 0% (and no WebGL) |
| Headful + UA pinned | Normal | 0% / 0% |
| `skipFingerprintInjection` alone | Robot (leaks `HeadlessChrome/152`) | 67% / 0% |

"Changes every time" is overstated: across three sessions the viewport changed once and the GPU once, and a
UA-pinned config changed 0 fields across two sessions ([S-ver] STE-10). The honest reading: **injected = a new
device each launch; UA-pinned = stable but it is the host's real hardware.**

### 8.2 Why the fleet turns injection off and pins a persona ([DEC] D3, D9)

- A platform sees a new device when any of IP, cookies or fingerprint changes. Continuity is the goal. Steel's
  per-launch regeneration is exactly what to avoid ([AP-dos] section 1.1, Q4).
- The same persona at every wake is what Justin asked for ([BRIEF](../../research/BRIEF.md)).
- This is **continuity for the client's own account, not evasion** ([DEC] D9). The patched-kernel option would
  be spoofing and waits on Q-03 and Q-04.

### 8.3 What the persona pins today, and what it cannot

| Value | Applied by | Status |
|---|---|---|
| User agent | session `userAgent` + `skipFingerprintInjection`; the Chrome major equals the real engine major | Stable across 2 sessions, n=1 ([RES] `[t1 #94]`) |
| Timezone | session `timezone` (Steel sets `TZ` for Chromium), plus container `TZ` and `DEFAULT_TIMEZONE` | Pinned by value; stability across wakes **to measure** |
| Locale and languages | See 8.4. `--lang` **does nothing on Linux** ([AP-ver] V-1). | **To measure**; nobody tested locale |
| Viewport | session `dimensions` | Works; `screen` does not follow in headless |
| Screen | headful only: Xvfb `-screen` geometry | **To measure** (inference from [AP-ver] AP-4) |
| WebGL present | explicit `--use-angle=swiftshader --enable-unsafe-swiftshader` | Cause of "no WebGL" is **unproven**. Only these flags gave WebGL in a vanilla headful run. How they interact with Steel's own `--disable-gpu` and `--use-gl=swiftshader` is untested ([S-ver] STE-11; [AP-ver] V-5). |
| CPU core count, GPU string, canvas hash, UA-CH brands | **Not pinned.** Host-real. | Identical for every identity on a node ([S-ver] STE-10; [DEC] D3) |

### 8.4 Locale on stock Steel does not work the way D4 says (`source (new)`)

[DEC] D4 says locale is set with `LANG` and `LANGUAGE` plus `--accept-lang`. On stock Steel the first half
probably does nothing. Steel launches Chromium with an explicit `env` of only `HOME`, `TZ` and `DISPLAY`
(`cdp.service.ts`, `finalLaunchOptions.env`). Puppeteer hands that object to the child process, which
replaces the container environment. So `LANG`, `LANGUAGE` and `DBUS_SESSION_BUS_ADDRESS` set on the
container never reach Chromium. **To verify** by reading `/proc/<chromium pid>/environ` (read from the host
side) in M1. The fleet's route: point `CHROME_EXECUTABLE_PATH` at a tiny wrapper script that exports the
persona's `LANG`, `LANGUAGE` and bus address and then `exec`s `/usr/bin/chromium` (Steel honours the variable
when the file exists, `source (new)` `utils/browser.ts`). `--accept-lang=<list>` goes in `CHROME_ARGS`
(split on spaces; no spaces in the value). A `userPreferences` value for `intl.accept_languages` is the
backup. Details are in [`steel-profile.md`](../infra/steel-profile.md) section 4.

### 8.5 Linkability, one client per node, and node classes

Because the canvas hash, core count and GPU are host-real, two identities on one node look related to any site
that compares them ([S-ver] STE-10). Until per-identity hardware values exist, **identities of different
clients do not share a node**, at a cost of about 7 identities per node ([DEC] D3, D12). Whether
cross-client unlinkability is required is **pending Q-13**.

Whether the host-real values also differ **between droplets** is **unverified** ([S-dos] Q5), and the answer
cuts both ways *(S08-8, S09-1)*:

- **If they are equal across droplets** of one size and image, every node looks the same. Linkability then
  exists on all of them, one client per node buys little, and Q-13 and [DEC] D3 are reopened.
- **If they differ**, an identity that wakes on another node changes hardware between wakes. That is the drift
  D3 forbids, and "wake on any node" cannot hold.

So the spec does not assume either. Each identity has a **home node class** in its persona (droplet size slug,
base image, CPU model as `/proc/cpuinfo` reports it, vCPUs). A host-real baseline is recorded **per class**. P5
compares to the baseline of the class the node reports and refuses on a mismatch inside the class. **Failover
stays inside the class**, a `reconcile` wake included. When no node of the class exists, the job waits while a
droplet of the class is requested, then fails `no_node_in_class`; a different class is used only if the owner
admits it explicitly, which means the account will see new hardware. The full rules are [SP] section 5.
M1 measures the cross-droplet table (same size, same image, and a different size) and records which of the two
outcomes holds ([SP] T6; G1.3 in [`MILESTONES.md`](../../MILESTONES.md)).

### 8.6 Engine upgrades are persona migrations

The UA's Chrome major must follow the engine. A new Steel image with a new Chromium major means a new UA, and
to a site that is a browser update. Do it on purpose, with the canary rule ([DEC] D13; [AP-dos] risk 8).

---

## 9. Engines on Steel

### 9.1 Stagehand v4 (pinned 4.2.0) needs the extension in the browser

Measured recipe ([SH-ver] SH-3; [DEC] D6). All three are needed on headless Steel:

1. The extension directory is inside the container at `/app/api/extensions/stagehand`.
2. The session is created with `{"extensions":["stagehand"]}`. Steel then launches Chromium with
   `--load-extension` and `--disable-extensions-except`. Without (2), `Extensions.loadUnpacked` is neutralised.
3. The CDP URL the SDK uses is also reachable **from inside the browser**, because the extension dials it back.
   On the fleet that URL is `ws://127.0.0.1:3000/`. Chromium sends loopback direct, so the proxy setting is not
   involved and the forwarder needs no exception ([SP] 10.3). This is also the condition of the measured attach.

It also relies on launch flags Steel already sets: `--remote-allow-origins=*` and the
`DisableLoadExtensionCommandLineSwitch` / `DisableDisableExtensionsExceptCommandLineSwitch` feature overrides
([SH-ver] missed issue 5). Both go into the upgrade smoke test.

**Detectability.** On stock Chromium 152 Stagehand v4 trips `isAutomatedWithCDP`. The extension stays resident
after `close()` until `Extensions.uninstall` or a restart (n=1 per condition) ([AP-ver] AP-2). That was
measured with a **CDP-loaded** extension. Steel's `extensions:["stagehand"]` loads it with `--load-extension`,
so it is resident from browser start on every page, and **uninstalling a flag-loaded extension is untested**
(`source (new)`). So the spec offers two modes:

| Mode | How | Status |
|---|---|---|
| **A** | `extensions:["stagehand"]` on the create | The measured recipe (headless). Resident for the browser's life. |
| **B** | No session extension. The SDK loads it with `Extensions.loadUnpacked` (headful has no recorder, so Steel adds no `--disable-extensions-except`) and `Extensions.uninstall` removes it after the session. | **Untested on Steel.** Matches the condition AP-2 measured. M1 candidate. |

**The policy by kind** *(S14-12)*. The mode is part of the persona. The node agent derives the effective mode
from the persona and the wake mode. The caller cannot choose it, and it is never switched per wake
([SP] 5, 10.3).

| Kind | Default mode | When it may differ | Image |
|---|---|---|---|
| `research` (open web, no login) | `A` | `B` if M1 prefers it | `research` flavor (extension present) |
| `account` (a logged-in client account) | `none` | `A` or `B` only if M1 selects Stagehand for that site class **and** the owner records it at creation | `account` flavor: no extension directory, the two `DisableLoadExtension...` overrides dropped, `--remote-allow-origins=*` filtered (to measure). An `account` identity that M1 assigns to Stagehand runs the `research` image for good. |
| Any kind, human-login wake | `none` | Never | (unchanged) |
| Any kind, canary wake | `none` | Never | (unchanged) |

Why `none` for accounts by default: the extension is resident from launch and trips a public automation check,
and whether a platform weighs that signal is unknown. A burnt client account costs more than a slower
executor. The consequence is that an `account` identity needs another executor until M1 decides which one
([DEC] D6 / O-02; [SCN] S14 walks the effects on L1, L2 and L3). This file does not choose that executor. The
Stagehand smoke test (T11) runs only against an image that carries the extension; the `account` flavor has the
negative check T11n instead.

### 9.2 Browser-Use (pinned 0.13.x)

Attaches by `cdp_url` (loopback, inside the namespace). No extension. Rules from [DEC] D6: proxy only on the
Steel session, exclude uploads and PDF actions, disable its default extensions, one agent per OS process with a
hard kill timer. It is read-mostly by default; effect-like steps need approval ([DEC] D5, D17). A logged-in
session means a task can act as that login ([BOX-SEC] "What this does NOT cover" 7).

### 9.3 The Guard, and what happens when it is lost

The box's in-browser `Guard` (one CDP client with browser-wide request interception) runs once per **browser
launch**, in the identity's runtime container inside the namespace. After every Steel relaunch it must
re-attach before any actor starts. Its gating contract (wait until ready, re-gate after relaunch, cancel work
when it drops) is bound to the box's module singleton and is rebuilt per identity ([EA-ver] EA-12; [DEC] D16).
Its CPU cost per awake identity is **unmeasured** (**to measure**).

**The Guard fails open** *(S13-7)*. When its connection goes, Chrome drops its interception. "Tools fail closed"
stops new calls; it does not stop a hostile page that is already loaded, which can request `127.0.0.1:3000`
in the gap. Inside the namespace nothing but the Guard and Local Network Access covers loopback. So the node
agent treats a lost Guard as an **incident**: it detects the loss at once (Docker's `die` event, a missed
heartbeat, or the Guard reporting a closed socket), uses its own bare CDP connection (the watchdog, kept in the
node agent so it survives the runtime) to navigate every page to `about:blank` and close all but the primary
tab, kills the actors, logs `guard_dropped` with the page URLs, and tags the next generation `incident`
([SP] 10.1). A **second layer** for variant N is under evaluation: Chromium under its own uid, and a rule
dropping that uid's connections to `127.0.0.1:3000` and `:9222`. It fits the `account` flavor only, because the
same rule would block a Stagehand extension's dial-back. It depends on Q-08 and is measured, not decided
([SP] 10.1, T20).

**Open interaction (to measure in M1; only for an image that carries the extension):** Stagehand's extension
dials `127.0.0.1:3000` from inside the browser, and the Guard refuses loopback. Whether the Guard sees that
websocket at all is unknown. If it blocks it, a narrow allow for the one CDP endpoint is a loosening of a
guard, which needs Justin's explicit yes (the box charter's rule, [`CHARTER.md`](../../../CHARTER.md)).

---

## 10. Resources per container

Measured on an arm64 Mac VM with a 1.5 GiB / 1.2 CPU cap, light pages only ([S-dos] Q6; [S-ver] STE-12):

| State | cgroup anon | `docker stats` memory | CPU |
|---|---|---|---|
| Idle (Steel's default Chromium running) | 448-449 MiB with `--init`; 473-508 MiB without | 453-705 MiB | 0-0.8% with `--init` (23% and 17% seen without) |
| One example.com tab | 485-517 MiB | 530-643 MiB | 5-35% of one core |
| One creepjs tab | 584-676 MiB | 646-929 MiB | 7-30% of one core |

Other facts:

- `docker stats` CPU% is relative to **one** core. "35% of a 1.2-CPU cap" in the dossier is really 0.35 core,
  about 29% of the cap ([S-ver] STE-12).
- The box's README peak while doing real tasks was 1.32 GiB (1,355 MiB; a MiB/GiB slip made it "1.36"). The
  bench range over 30 runs was 984-1,355 MiB. Chromium memory climbs with use ([EA-ver] V-6;
  [BOX-OPS] troubleshooting).
- Create took 1.0-2.6 s and release 1.3-2.8 s over 8 warm cycles. A restored-profile create took up to
  7.4 s. One release took 19 s ([RES] `[t1 #45, #64, #72]`).
- **Planning slot:** 1.5 GiB browser + 0.35 GiB agent runtime, 0.6 vCPU (**estimate**, [SC-dos] Q1). That gives
  7 awake identities on an `s-8vcpu-16gb` ($96/mo) ([SC-ver] SCA-5). With the runtime, the forwarder and up to
  three actors now in separate containers, the 0.35 GiB has to cover all of them plus the holder (a sleeping
  container) and each container's own overhead (**to measure**; the slot is not re-derived here).
- **Headful** adds about +0.2 vCPU and +150 MB per slot (**estimate**, unmeasured).
- **Not measured at all:** Facebook, Instagram, TikTok and X pages; amd64; a 1-3 h soak; the Guard's CPU. The
  first live canary corrects the slot ([SC-dos] risks 1; [SC-ver] missed issue 3). The node agent restarts a
  container through the safe sleep and wake path when memory crosses a threshold set from M1 data.

---

## 11. Security posture

| Surface | Fact | Control |
|---|---|---|
| REST, CDP, viewer, logs have no auth | CORS `origin: true` ([S-ver] STE-8) | Only the node agent reaches the container, on a per-identity network. fleetd scopes tokens. Nothing is published. |
| Raw CDP on 9223 | The Docker quick starts publish it ([S-ver] missed issue 9) | Never published. `--no-nginx` (to verify). |
| Proxy credentials echoed | Create, list and get return them ([S-ver] STE-7) | Steel never gets credentials (section 6). |
| Root, no sandbox, site isolation off | The image has no `USER`, so Steel adds `--no-sandbox --disable-setuid-sandbox --no-zygote`, and `IsolateOrigins,site-per-process` are in the disabled features ([S-ver] missed issue 3; corpus: `https://github.com/steel-dev/steel-browser/blob/1131a02/api/Dockerfile`). Arbitrary pages run inside logged-in client sessions. | **Pending Q-08.** Variant 1: run non-root with the sandbox on (the container may need user namespaces or a seccomp profile; **to measure**). Variant 2: accept the risk in writing. Re-enabling site isolation is harder than it sounds: the disabled list is **one** `--disable-features=` string that also carries the two features Stagehand needs. `FILTER_CHROME_ARGS` matches whole arguments, so the fleet filters the whole string and supplies a replacement in `CHROME_ARGS`. Whether two such flags merge or the last wins is **to measure** (`source (new)`). |
| Pages reach loopback and link-local | Chromium's implicit proxy bypass ([S-ver] STE-7) | Egress drops everything but the upstream proxy, **for link-local and every non-loopback address**. Loopback inside the namespace is covered by the Guard and Local Network Access only. |
| Pages reach Steel's own API | The 2026-09-22 exploit: a redirect to `127.0.0.1:3000/v1/sessions` ([BOX-SEC]). Also the bridge IP on port 3000, through the proxy path, if the forwarder serves it. | The Guard, run for every awake browser. The forwarder refuses its own bridge IP with no exception (T-L). T18 injects both. |
| The Guard is lost while a page is loaded | The Guard fails open; "tools fail closed" covers only new calls *(S13-7)* | The node agent blanks every page at once, kills the actors, logs an incident, and tags the next generation `incident` (9.3). Variant N may add a uid rule (to measure). |
| DO metadata endpoint | Reachable around a proxy (inference; unverifiable here) | Egress drop. Tested on a droplet in M1. |
| Whole-server crash | An unhandled rejection from a tab closed mid-navigation killed Steel 4 of 5 times on the box ([BOX-COMPOSE]) | `NODE_OPTIONS=--unhandled-rejections=warn`. |
| No idle reaping | `KILL_TIMEOUT` unused ([S-ver] STE-8) | The node agent enforces maximum wake time and inactivity, then runs the safe release. **Not against a person:** while a control route is open, viewer timers replace these (7.3 item 9). |
| Volumes hold logged-in accounts | Not "nothing worth stealing" as in the box ([EA-dos] Q1(b)) | Bundles encrypted in Spaces. The local volume is deleted after upload and after any failed wake in which no session ran; a held volume leaves only through `salvage`. Only the Steel container mounts the volume. No actor has filesystem access. |
| The viewer ignores `interactive=false` on the server | `source (new)` (7.1) | The node agent forces the flag and drops client frames on a watch route. |
| A saved cookie jar from a bad window | Logged out, challenged, wrong IP, Guard down | Tagged and parked; the pointer moves only to a clean generation (section 4.4, [SP] 8.2). |
| Hostile page content | Browser agents read it while logged in | Effects are gated by approved manifests, not by the model ([DEC] D5, D13). |
| Extension inventory | Stagehand's extension runs in all frames at `document_start` ([SH-ver] V-1) | Fixed per kind in the persona; the `account` flavor has none (9.1). |

---

## 12. Known issues

Upstream state, re-read 2026-10-10 ([S-ver] STE-14): Apache-2.0, last push 2026-10-09. `:latest` tracks
`main`, not releases. The `0.5.3` string was never bumped, even at tag `v0.5.4-beta`, so do not read it as a
version. "75 open issues" counts 36 PRs.

| # | State | What it is | Fleet answer |
|---|---|---|---|
| #347 / PR #348 | open, outsider PR, no review | `userDataDir` is ignored (precedence bug) | Use the fixed path. Carry the fix only if it earns its keep. |
| PR #375 | open, outsider PR, no review | Guard singleton ownership (409 on a competing create) | The node agent is the guard. |
| #235 | open | API-key auth. The "plan" comment is by an outside volunteer, not a maintainer. | Auth by isolation. |
| #330 | open | `dimensions` leaves `screen` at 800x600 | Headful Xvfb geometry (to measure). |
| #359 | open | WebGL renderer is always SwiftShader | Accept; explicit flags. |
| #294 / #295 / #302 | open | Fingerprint generator lacks Chrome 146 samples | Injection is off anyway. |
| #322 | open | dbus launch failure in Docker | The wrapper starts dbus itself. |
| #332 | open | `live-details.browserVersion` is `"[object Object]"` | Read the version over CDP. |
| #333 | open | Viewer always shows `sessions[0]` | One session per container. |
| #331 | open | Proxy byte counters stay zero | Count bytes in the forwarder. |
| #247 | open | Slowdown with concurrent tabs | One agent, few tabs. |
| PR #293 | closed, not merged | Inactivity timeout | The node agent enforces it. |

**Fleet-level traps found in the research:** the persist double launch ([EA-ver] M-3); failed-launch
poisoning ([EA-ver] M-7); stub sessions and a lying health route (section 2.4); the Singleton trap (4.3); the
30 s window (4.2); locale env not reaching Chromium (8.4); the boot-time direct ipinfo call (6); the
`blockAds` ambiguity (2.2); the viewer's `interactive` flag that only the page honours (7.1); a Guard that
fails open (9.3).

Because the outsider fixes have no owner, "track upstream" is not the plan. The fleet carries its own
takeover guard, auth-by-isolation, profile handling and persona work ([CONS] C-24). The escape hatch is plain
Chromium plus a small session API. M1 measures both on a droplet and writes the winner into [DEC] D4
([DEC] D4 "Escape hatch").

### 12.1 Pending Justin, and open items

| Item | Needed from | Effect here |
|---|---|---|
| **Q-08** Run Steel's Chromium non-root with the sandbox on, or accept the risk? Also whether to build the uid rule that covers a lost Guard. | Justin | Section 11, 9.3, and the root versus non-root variants in `steel-profile.md` |
| **Q-12** A small, capped, throwaway droplet for M1 | Justin | Every test in `steel-profile.md` section 12 and every number above |
| **Q-13** Cross-client unlinkability required? (one client per node). Reopened by either outcome of the cross-droplet measurement. | Justin | Section 8.5, node packing |
| **Q-02, Q-03, Q-04** Anti-detect stance, patched kernels, spoofing | Justin | Whether anything beyond the honest persona is allowed |
| **Q-07** Data handling for client page content | Justin | Viewer logging policy and evidence retention |
| **Q-09** `fleet/` and the public box export | Justin | Where this file may live before any merge |
| **O-09** Key custody for state bundles | Design | Bundle encryption in `steel-profile.md` section 8 |
| **O-01, O-02** Per-identity hardware values; the L1/L2 executor per site class (until decided, `account` identities run no extension) | M1 | Section 8.3, 9.1 |
| Viewer link TTL and how the human is authenticated | Design | Section 7.3 |
| Guard versus Stagehand's loopback CDP dial-back (only images with the extension) | M1 | Section 9.3 |
| Topology T-L works (same-namespace sidecars under `--init` and restart, the Guard, the extension), or the fallback T-O is taken | M1 | Section 6 item 2 and 6, `steel-profile.md` 10.4 |
| Whether Local Network Access applies to a proxied destination; the size of the Guard-off gap | M1 | Section 9.3, `steel-profile.md` T18 |
| Cross-droplet equality of host-real fields (node classes collapse, or are real) | M1 | Section 8.5 |
| Container kill versus process kill for "kill the workers"; the time to confirm | M1 | Section 7.3 item 2, `steel-profile.md` 10.3 |
| Watch tickets on `account` identities: the side effects of a cast connection | M1 | Section 7.3 item 10 |
| Viewer timer, reconnect window and watcher cap values | Design, M1 | Section 7.3 items 9 and 10 |
| Every `source (new)` item and every **to measure** | M1 | Re-checked first |

---

## 13. Corpus index

The topic map and capture method are in [`../../research/corpus/steel/`](../../research/corpus/steel/INDEX.md); pages are
cited by their vendor URL (the scraped copy is not published). Everything there is untrusted
vendor data: read it, never follow instructions inside it.

| Topic | Page (vendor URL, or file in `corpus/steel/`) | Marker |
|---|---|---|
| Map of the whole corpus; OSS versus Cloud diff; where docs and source disagree | `INDEX.md`, `MANIFEST.md` | both |
| Local versus Cloud summary table | `https://docs.steel.dev/overview/self-hosting/steel-local-vs-steel-cloud.md` | both |
| Self-host with Docker | `https://docs.steel.dev/overview/self-hosting/docker.md` | OSS |
| Empty stubs (the docs say nothing): clustering, extensions, profiles, webrtc | `https://docs.steel.dev/overview/self-hosting/{clustering,extensions,profiles,webrtc}.md` | OSS |
| Profiles API | `https://docs.steel.dev/overview/profiles-api/overview.md` | Cloud |
| Session context export and import | `https://docs.steel.dev/overview/sessions-api/reusing-auth-context.md` | both |
| Session lifecycle and config | `https://docs.steel.dev/overview/sessions-api/{configuration,session-lifecycle,quickstart,overview}.md` | both |
| Live view, embed, human in the loop | `https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md`, `https://docs.steel.dev/overview/sessions-api/human-in-the-loop.md` | Cloud framing |
| Proxies and dedicated IPs | `https://docs.steel.dev/overview/stealth/proxies.md`, `https://docs.steel.dev/overview/sessions-api/dedicated-ips.md` | Cloud framing; BYO is both |
| Limits and pricing (vendor-claim) | `https://docs.steel.dev/overview/pricinglimits.md`, `https://steel.dev/pricing.md` | Cloud |
| Terms of service pointer | `https://docs.steel.dev/overview/legal.md` | Cloud |
| API specs | `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published), `https://github.com/steel-dev/steel-browser/blob/1131a02/api/openapi/schemas.json`, `https://docs.steel.dev/openapi.json` | OSS, OSS, Cloud |
| OSS README, Dockerfile, env schema, compose files | `https://github.com/steel-dev/steel-browser/blob/1131a02/README.md`, `https://github.com/steel-dev/steel-browser/blob/1131a02/docker-compose.yml`, `https://github.com/steel-dev/steel-browser/blob/1131a02/api/Dockerfile`, `https://github.com/steel-dev/steel-browser/blob/1131a02/api/src/env.ts`, `https://github.com/steel-dev/steel-browser/tree/1131a02/docs/` | OSS |
| Stagehand, Browser-Use, Playwright integration pages | `https://docs.steel.dev/integrations/{stagehand,browser-use,playwright,puppeteer}.md` | Cloud URL shapes; v3 only for Stagehand |
| Hermes plugin (not used) | `https://github.com/steel-dev/hermes-steel/tree/d8a1e39/` | both |
| Spike evidence | [`../../research/spikes/steel/RESULTS.md`](../../research/spikes/steel/RESULTS.md) and its scripts | measured |

---

## 14. Governance

### 14.1 Version pin and the upgrade gate

**The pin.** One image by **manifest-list digest**, not a tag and not one architecture's digest
([BOX-COMPOSE] comment on `STEEL_REF`). The evidence came from image `sha256:7a161b95e8a9...` (created
2026-09-16; Chromium 152.0.7977.82; the research recorded only a prefix). The full digest is resolved when
`steel-profile` is first built. That image is 3 commits behind the source pin `1131a02` and ahead of tag
`v0.5.4-beta` ([S-ver] STE-14). `latest` has since moved, and the two PRs that matter are still open
([EA-ver] M-4). The pin also fixes the Chromium major, and with it the persona UA. It lives in one file in the
wrapper repo (unbuilt). Stagehand is pinned beside it: SDK 4.2.0 and its bundled extension together, because
the runtime compatibility check rejects a mismatch ([SH-ver] missed issue 6).

**The gate.** A new digest, a new wrapper version, a new Stagehand pin or a new Chromium major runs this on a
throwaway droplet. It maps to the tests in [`steel-profile.md`](../infra/steel-profile.md) section 12:

1. Takeover behaviour: does a second create still replace the live browser (or does #375 now answer 409)?
2. `userDataDir` precedence: does #348 change what the fixed path means?
3. Health and stub behaviour unchanged, so the fleet's substitutes still hold.
4. Safe release leaves 0 `Singleton*`; a stale lock still produces the silent fallback (so the probes still
   catch it); no zombies with `--init`.
5. Cookie commit: a cookie written 31 s or more before close survives; one written 5 s before does not
   (so the hold is still needed).
6. No proxy credential in any Steel response, in the container argv, in `docker inspect`, or in logs.
7. The persona probe is stable across wakes and the UA major equals the engine major.
8. The Stagehand smoke test, **only for an image that carries the extension**: extension in place,
   `extensions:["stagehand"]`, `--remote-allow-origins`, the two feature overrides, attach on loopback, one
   `observe`, `close`. For the `account` flavor, the no-extension check instead (T11n).
9. The viewer test, the box shield-check port with the page-to-Steel vectors (T18), `guard_probe.py`, and the
   Guard-drop test (T19).
10. A resource baseline against the previous digest.
11. The viewer's server side still ignores `interactive=false` (the premise of the watch proxy, T23), and the
    takeover kill time and the in-flight rule still hold (T22).
12. The local rules suite: tags, pointer, retention floor, failed-wake deletion, node-class placement (T21).

Pass, then a **canary identity** takes it before any client account does ([DEC] D13, [CONS] O-13). A failed
gate keeps the old pin. Rollback is re-pinning the old digest. Applying a new pin to the live fleet needs
Justin's explicit yes ([`CLAUDE.md`](../../../CLAUDE.md): deploys and firewall changes on the live box).

### 14.2 What agents may and may not do through this property

Hermes profiles reach Steel only through fleet tools ([DEC] D17). They never hold a Steel, CDP or viewer URL.

| May | May not |
|---|---|
| Ask for `wake`, `sleep`, `reauth` on identities their token covers | Create, delete or reconfigure an identity |
| Run released procedures and bounded `act` / `extract` / `task` steps through the ladder | Call any Steel route, open raw CDP, or hold a browser outside a lease |
| Ask for `reauth` and get back a ticket id, a list of people notified and an expiry. **Never the viewer link**: the notifier sends it straight to the named person (D14, D17, ARCH 4.8) | Receive, forward or store a viewer URL or ticket; open a viewer or type into one themselves |
| Report a checkpoint or a wrong result | Type or store credentials, solve a CAPTCHA, or retry a login |
| Read their identity's state and evidence | Change persona, proxy, timezone, locale, viewport, extensions or engine mode |
| | Start a second session, restart or kill a container, or run a release |
| | Navigate to internal, loopback, link-local or fleet addresses |
| | Install or remove extensions; export a context or a bundle |
| | Use `skipFingerprintInjection` without a pinned UA, or send any Cloud-only field |
| | Post, send, reply, delete, follow or submit without an approved manifest or a human approval |

### 14.3 Who may change its configuration

| What | Who | How |
|---|---|---|
| The image digest, the wrapper, the Stagehand pin | The fleet owner (today Justin), after the gate | A reviewed change on a branch, then the canary, then a live apply with his yes |
| An identity's persona, proxy or infra home | The owner, **at creation only** | A change after creation is a new identity and a new human login ([DEC] D3) |
| An identity's kind, image flavor and extension mode | The owner, at creation, from the M1 result for the site class | Fixed in the persona. A change is a persona migration under the canary rule, never a per-wake switch. |
| Whether watch tickets are on for an `account` identity | The owner, per identity, after M1 reports the side effects | Off by default for `account`, on for `research` |
| Admitting a second node class for an identity | The owner, explicitly | `class_admit` records a new baseline and means the account sees new hardware ([SP] 5) |
| Promoting a parked generation | The owner, with a reason | An audit row; a `tainted_ip` generation cannot be promoted ([SP] 8.2) |
| Egress rules, the Guard, the route allowlist, the root and sandbox choice | The owner, with an explicit yes each time | Loosening any of them is never done to make a test pass |
| Engine mode and engine per site class | The owner, from M1 measurements | Written into the router |
| Anything at runtime | Nobody. The node agent applies recorded config and refuses drift. | |

### 14.4 Soul

> Steel is a borrowed browser with no locks, so we keep it in a box of our own, reach it only through the node
> agent, believe nothing it says about itself, and close it only the careful way.

---

## 15. Stress-test gaps applied in this revision

Each row is a finding from [SCN] and where this file answers it. The build detail is in [SP] section 15. Where
a row says another document should change, this file does not edit it.

| Gap | Answered here | Other documents should |
|---|---|---|
| S01-6 two specs of the sleep | 4.4 gives the order and the reasons and no numbers; [SP] 8.2 is the one spec; one flag name, `journal_authoritative` | [ARCH] 4.9 points to [SP] 8.2 and drops `cookies_unflushed`; M1 measures the hold |
| S05-12 auth result on saved state | 4.4 (tag and park), 5 (re-injection rule) | [ARCH] 3.3 adds the tag columns; `restricted` joins the result vocabulary |
| S07-12 state from a wrong-IP window | 4.4, 6 item 3 and 4 | [ARCH] 4.9 and 4.10 add `tainted_ip` and the canary wake |
| S07-13 idle IP death | 6 item 4 (`probe_ip`) | [ARCH] 6.8, 4.11 |
| S07-15 plaintext after a failed wake | 11 (volumes row); [SP] 8.1, 8.6 | [ARCH] 4.9 |
| S08-8 node class | 8.5 | [ARCH] 3.3, W4; [DEC] D3 and Q-13 are reopened by the M1 result |
| S08-12 where workers live | 6 item 2, 7.3 item 2, 9.3 | [ARCH] 2.2, 3.5 |
| S12 G12-7 human session rules | 7.3 item 9 | [ARCH] 3.5 (human lease liveness, G12-1) |
| S12 G12-8 watch mode | 7.1, 7.3 item 10 | [ARCH] 6.5; the Browserbase guide |
| S13-6 two topologies | 6 items 2 and 6; 9.1 item 3 | [ARCH] 2.2 (holder owns the namespace) |
| S13-7 Guard fails open | 9.3, 11 | [ARCH] 2.3, 4.10 |
| S14-12 extension policy by kind | 9.1 | [ARCH] N2, W8, W10 (S14-4); persona (S14-7); [DEC] D6 (S14-8) |

