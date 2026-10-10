> **Read with its verification report.** [verification/steel.md](../verification/steel.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: Steel (open-source steel-browser, self-hosted) vs Steel Cloud

Status: FINAL (third Steel agent; the first two were cut off by session limits). Date: 2026-10-10.
Source pin: `steel-dev/steel-browser@1131a02` (2026-10-06). Image measured: `ghcr.io/steel-dev/steel-browser-api:latest`
`sha256:7a161b95e8a9` (created 2026-09-16, `@steel-browser/api` 0.5.3, Chromium 152.0.7977.82, node 22.13.0,
puppeteer-core 23.6.0). Spike container `fleet-spike-steel` on `127.0.0.1:3300`, `--memory 1536m --cpus 1.2`, arm64 Linux VM on the maintainer's Mac.
Raw outputs: `fleet/research/spikes/steel/RESULTS.md` (rebuilt verbatim from the earlier agents' transcripts; block ids like `[t1 #45]`).
Spend: $0. Containers left running: none (read-only `docker ps -a` / `docker volume ls` filtered on `fleet-spike`, 14:20Z, both empty).

**Provenance tags**
- `hands-on†`: run on 2026-10-10 by the earlier Steel agent. The raw output was recovered from its transcript into RESULTS.md. Each claim cites the block, for example `[t1 #45]`. This session did no Docker lifecycle work and launched no browser; the brief now bans both on this Mac. The only Docker commands were the read-only `docker ps -a` / `docker volume ls` used for the cleanup check.
- `hands-on`: run by this agent today. This was read-only: curl, gh, and crops of the saved screenshots.
- `source-code`: read at `1131a02`, plus the compiled image where it says "image".
- `official-docs`, `vendor-claim`, `third-party` and `unverified` are as defined in BRIEF.md.

**What was checked in the compiled image vs only in source.** The image was checked for:
- `session.service.js` user-data-dir precedence;
- `endSession` / `shutdown`;
- fingerprint constraints;
- `proxy: proxyUrl` in session info;
- the `PROXY_INTERNAL_BYPASS` set;
- CORS `origin: true`;
- the puppeteer `closeBrowser` path (graceful `Browser.close`; process-group `SIGKILL` only on its error path);
- the devtools-protocol flush grep.

The source evidence (`[t1 #36-#38]`, `[t2 #29-#35]`) was used without re-checking against the image for:
- the viewer template;
- the context export/import code;
- the env schema;
- the launch flags.

Note that `:latest` (built 2026-09-16) reports **0.5.3**, although v0.5.4-beta was released on 2026-08-25. Pin images by digest.

---

## 1. Verdict

1. **OSS Steel is a single-browser runtime, not a multi-tenant browser service.** Use it as "one container = one awake profile = one Chromium", wrapped by a fleet node agent.
   - A "session" is bookkeeping on one shared Chromium.
   - A second `POST /v1/sessions` with the same config silently took over the live browser. A's tab and its JS state were still there, while `GET /v1/sessions/{A}` reported `released` `hands-on†` `[t1 #42]`.
   - With a different config, the browser was relaunched and A's client was dropped `[t1 #42]`.
   - Nothing returns 409 today. Upstream PR #375 (opened 2026-10-10) proposes exactly that guard `hands-on` (gh).

2. **The profile volume persists logins, but stock Steel loses them silently in three measured ways.** The fleet must own the release and wake procedure.
   - **(a) 30 s cookie window.** Chromium commits cookies to SQLite on a 30 s timer. Source: `kCommitInterval = base::Seconds(30)` at `sqlite_persistent_cookie_store.cc:1225` @152.0.7977.82 `source-code`. Measured: the cookie reached disk between t+28 s and t+32 s `[t1 #47]`.
     - Every release under 30 s lost the cookie: 5 s + Steel release, 5 s + CDP `Browser.close`, and 2 s with either `[t1 #45, #53, #54]`.
     - 31 s, 35 s and 40 s kept it `[t1 #65, #73]`, plus existing-assets.
     - There is no CDP flush command `[t2 #29-#32]`.
   - **(b) Stale `Singleton*` lock leads to a silent fallback.** Steel's release left `Singleton*` in the profile in every observed run (7/7: `[t1 #48, #53 ×2, #56, #63, #64, #65]`). A raw CDP `Browser.close` left none in 3 of 3 runs `[t1 #53, #73]`.
     - After a recreate under a new hostname, a `persist:true` create returned **200**, but Chromium ran on `/tmp/steel-chrome` with empty cookies `[t1 #56-#60]`.
     - The next create returned **500** after 27 s, and `/v1/health` still said `ok` with no Chromium running `[t1 #61, #62]`.
     - This upgrades existing-assets' "inference" to measured.
   - **(c) `docker stop` is a `SIGKILL`.** It took 10.4 s with exit 137, and left the lock in place both with and without `--init` `[t1 #74]`.
   - **The safe release worked end to end once (n=1)** `[t1 #73]`:
     1. export the context;
     2. wait 31 s;
     3. send CDP `Browser.close`;
     4. call Steel release.

     A recreate under a **new** hostname then came back logged in. See Q2.

3. **Session context export/import complements the user-data-dir; it does not replace it.**
   - Cookies, including httpOnly ones, export instantly from memory and re-inject before the first navigation `[t1 #67, #73]`. That makes the export a good auth-cookie journal, because it covers the 30 s window.
   - localStorage and sessionStorage do not round-trip as exported. Export keys them by hostname, import looks them up by origin (`utils/context.ts:82,103` vs `:255`) `source-code`. They came back only after rewriting the keys to `https://host`, and only on Steel's primary page `[t1 #67-#69]`.
   - IndexedDB came back empty (`{"example.com":[]}`) even though a record existed `[t1 #67]`.
   - Export never covers service workers, Cache Storage, saved passwords or preferences.
   - **Use the user-data-dir tarball as the persistence unit, and the context export as the journal.**

4. **The per-session proxy is accepted and plumbed through a local proxy-chain forwarder.**
   - It failed closed with a dead upstream. HTTPS returned `ERR_TUNNEL_CONNECTION_FAILED`. HTTP returned proxy-chain's own 594 page, with no direct egress `[t1 #75, #78]`.
   - **The credentialed upstream URL is echoed** in the create, list and get-by-id responses, over an unauthenticated API with CORS `origin:true` `[t1 #75]` `source-code`. Anything that can call the API can read it.
   - With the proxy down, the timezone **silently fell back to UTC** `[t1 #75]`.
   - Keep the credentials in the fleet's node-agent forwarder, give Steel only `http://127.0.0.1:<port>`, and always pass `timezone`.

5. **The live viewer is good enough for a human login. It is unauthenticated, and it must sit behind the fleet gateway.**
   - Text typed through `/v1/sessions/debug?interactive=true` landed in the remote form `[t1 #89]`.
   - A `window.open` popup appeared as a second tab and became active `[t1 #89]`, and the screenshot confirms it.
   - Not forwarded:
     - keyboard modifiers on key events;
     - paste, unless embedded with `clipboardBridge=true` `source-code`.
   - Not available on this image:
     - `/v1/devtools/inspector.html` returned 404 `[t1 #89]`;
     - `/ui` is not served by the API image ("UI dist not found") `[t1 #60]`.

6. **Turn off Steel's stealth. Neither it nor the stock alternatives pin a fingerprint across launches.**
   - **Default injection.** browserscan says "Robot" in 2/2 runs, and creepjs scores 33% headless and 20% stealth.
   - **UA-pinned headless.** browserscan says "Normal", and creepjs scores 0% headless.
   - **Headful under Xvfb.** It still says "Robot" unless the UA is pinned, and it has **no WebGL at all**.
   - **`skipFingerprintInjection`.** It leaks `HeadlessChrome` (`[t1 #97-#111]`, table in Q5).
   - **Across 3 sessions on one volume.** The UA, `hardwareConcurrency`, viewport and WebGL changed every time `[t1 #93]`.
   - **Host-wide constants.** The canvas hash was identical in all 7 h/h2 sessions, in every mode. Whenever injection was off (UA-pinned, `skipFingerprintInjection`, and tabs that missed injection), the real `hc=10` and SwiftShader showed too. In the injected default mode, hc varied 8/20/32 and once an NVIDIA renderer was reported.

     That is a cross-profile linkability risk on a shared node `[t1 #93-#96]`.
   - A pinned persona needs a patched Steel (Q5).

7. **Resources per awake profile container on light pages** (arm64 Mac VM).
   - Idle means Steel's own default Chromium is running. Idle: about 450-510 MiB cgroup anonymous memory and under 1% CPU.
   - One example.com tab: about 485-520 MiB.
   - creepjs: about 585-675 MiB.
   - `docker stats` MemUsage ranged from 450 to 970 MiB.
   - CPU peaked at 35% of a 1.2-CPU cap while a page loaded `[t1 #112, #113]` `[t2 #47]`.
   - Social sites are unmeasured.

8. **Steel Cloud fixes the multi-profile gaps for a price, and its terms forbid much of the use case.** The live pages re-fetched today are byte-identical to the 2026-10-09 corpus `hands-on`.
   - What it adds:
     - a Profiles API (300 MB cap, deleted after 30 days unused);
     - concurrency of 10, 100 or 1,000+;
     - sessions capped at 15 min, 1 h or 24 h;
     - a stealth browser, on Enterprise only;
     - CAPTCHA solving.
   - Its ToS bans using it to "violate any website's terms of service" and to "create fake accounts".
   - Self-hosted Apache-2.0 carries no AUP. Browserbase remains the brief's named paid backup.

9. **Required wrapper for stock OSS Steel:**
   - run with `--init` (without it, 8 cycles left 151 zombies; with it, 0 `[t1 #72]`);
   - use a fixed per-profile `--hostname`, or delete `Singleton*` under a lease before start;
   - never `docker stop` a live profile;
   - health-check by checking the live `--user-data-dir` and a login probe, not `/v1/health`;
   - drive Steel's primary page, never a fresh `newPage()` for the first navigation;
   - never send Cloud fields;
   - pin the image by digest.

   Track or carry these upstream fixes:
   - #348 (userDataDir precedence);
   - #375 (singleton guard);
   - #235 (API key auth);
   - #330 (800x600 screen).

---

## 2. Answers

### Q1. OSS vs Steel Cloud feature matrix

| Feature | OSS steel-browser (self-hosted, image 0.5.3) | Steel Cloud | Proof |
|---|---|---|---|
| **Sessions API** | Routes: `POST/GET /v1/sessions`, `GET /v1/sessions/{id}`, `POST /v1/sessions/release` and `/{id}/release`, `/{id}/context`, `/{id}/live-details`. SELF-only: `/v1/sessions/debug`, `/v1/health`, `/v1/logs/*`, and session-bound scrape/screenshot/pdf. **`release/{id}`, `/{id}/context`, `/{id}/live-details` and the cast websocket act on the one active session whatever `{id}` says** (cast: `sessionService.activeSession`; others per PR #375's description). `GET /v1/sessions/{id}` does return the named record, for example A's `released` `[t1 #42]`. | Same core, plus profiles, credentials, secrets, extensions, captchas, computers, agent traces, HLS, events and cost (75 ops vs 29). | `official-docs` corpus `https://docs.steel.dev/openapi.json` vs `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published). `source-code` `casting.handler.ts:26-40`. PR #375 text `[t1 #118]` |
| **Concurrency per container** | **1 browser.** A second create with the same config reuses the live Chromium. A's page and state persist while A is marked `released`. With a different config, Chromium is relaunched and A's client is disconnected. | 10 / 100 / 1,000+ by plan | `hands-on†` `[t1 #42]`. `source-code` `session.service.ts:67`. `official-docs` `steel-local-vs-steel-cloud.md` ("Concurrency 1", re-fetched today). `vendor-claim` `pricinglimits.md` |
| **Persistence / profiles** | `persist:true` (or any truthy `userDataDir`) selects one fixed dir, `/app/api/user-data-dir`. The `userDataDir` value is ignored. `persistProfile`/`profileId` are stripped. `CHROME_USER_DATA_DIR` makes the *idle* browser use that dir too. | Profiles API: a user-data-dir snapshot saved on release, 300 MB cap (`FAILED` on upload failure), deleted after 30 days unused. `persistProfile:true` must be repeated to keep accumulating state. | `source-code` `session.service.ts:180-183` (and image `session.service.js:89-91`). `hands-on†` `[t1 #46, #56, #65]`. Issue #347, PR #348 open. `official-docs` `https://docs.steel.dev/overview/profiles-api/overview.md` |
| **Session context export/import** | `GET /v1/sessions/{id}/context` returns: all cookies (`Network.getAllCookies`, in-memory); localStorage/sessionStorage from disk LevelDB plus open pages; IndexedDB from open pages only. `sessionContext` on create re-injects cookies via `Network.setCookies`. Storage is injected on navigation, looked up **by origin**, while export keys it **by hostname**. | Same endpoints (`reusing-auth-context.md`) | `source-code` `cdp.service.ts:1232-1300`, `chrome-context.service.ts:66-130`, `utils/context.ts:82,103,255,404-450`. `hands-on†` `[t1 #67-#69, #73]` |
| **Per-session proxy + auth** | `proxyUrl` is accepted and runs through a local proxy-chain forwarder on `127.0.0.1:<random>`; Chromium sees only the local URL. Fails closed. The credentialed URL is echoed in API responses. The timezone falls back to UTC when the proxy is dead. The env `PROXY_URL` is parsed but used only in validation and error enums. | BYO `proxyUrl` plus managed residential (`useProxy`) plus dedicated IPs ($5/IP/mo on Scale) | `hands-on†` `[t1 #75, #78]`. `source-code` `utils/proxy.ts:16-63`, `session.service.ts:173,212-221`, `cdp.service.ts:934`. `official-docs` `proxies.md`, `dedicated-ips.md` |
| **Stealth / fingerprint pinning** | A random fingerprint (`fingerprint-generator`, linux/chrome≥146, relaxed when unsatisfiable) on every launch. `userAgent` or `skipFingerprintInjection` disables it. There is **no HTTP field to pin one**: the controller drops `fingerprint`. | `stealthConfig` (`humanizeInteractions`, `skipFingerprintInjection`, `autoCaptchaSolving`). "Stealth Browser" is Enterprise-only. | `hands-on†` `[t1 #93-#111]`. `source-code` `sessions.controller.ts:14-59`, `cdp.service.ts:704-760`. Image `cdp.service.js:510-511` `[t1 #36]`. `vendor-claim` `pricing.md` |
| **CAPTCHA** | None | `/v1/sessions/{id}/captchas/*`, `solveCaptcha`; $3 / $1 per 1k | `official-docs` local-vs-cloud page; Cloud OpenAPI |
| **Live viewer for human login** | `/v1/sessions/debug?interactive=true&showControls=true`: JPEG screencast (quality 75) plus a mouse/key relay, tab bar, address bar, back/forward/reload. **No auth.** Inspector 404 on this image. `/ui` is a separate image. | Embeddable `debugUrl` iframe, `interactive=true`; WHEP live view; authenticated by Cloud | `hands-on†` `[t1 #89]`. `source-code` `sessions.routes.ts:144-161` (`onRequest: []`), `casting.handler.ts:280-400`. `official-docs` `https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md`. Cloud OpenAPI `recording` field |
| **Recordings** | Headless sessions load the `recorder` extension, which posts to `/v1/events` and on into the log store (`/v1/logs/*`; in-memory unless `LOG_STORAGE_ENABLED`, which uses DuckDB). No video. | Session replay (headful, `recording` default true), HLS, agent traces, 7-14 day retention | `source-code` `cdp.service.ts:809`, `sessions.routes.ts:163-182`. `hands-on†` "Using in-memory log storage" `[t1 #60]`. Cloud OpenAPI |
| **Files** | `/v1/sessions/{id}/files*` routes are served (docs wrongly say "Not supported"). Function untested. | Files API | `hands-on` by the corpus agent (running-image OpenAPI). `official-docs` page disagrees. Corpus INDEX "docs and source disagree" #1 |
| **Extensions** | `extensions:["<dir>"]` loads from `/app/api/extensions/<dir>`. The docs say `api/src/extensions/`, but the code reads `api/extensions/`. `--disable-extensions-except` blocks runtime `Extensions.loadUnpacked`. | Extensions API (`/v1/extensions*`, `extensionIds`) | `source-code` `utils/extensions.ts:5-9`, `cdp.service.ts:807-863`. `stagehand.md` Verdict 2 (`hands-on`). `official-docs` local-vs-cloud page |
| **Credentials API** | None (`credentials` is an options object, with no store) | `/v1/credentials`, `/v1/secrets*` | Cloud OpenAPI. `official-docs` ("Not supported" locally) |
| **Timeouts** | **None.** No `timeout`/`inactivityTimeout`. `KILL_TIMEOUT` is parsed (`env.ts:26`) and used nowhere. A session lives until release, `Browser.close`, a crash or the container dies. | `timeout` defaults to 300000 ms; `inactivityTimeout`; max 15 min / 1 h / 24 h by plan | `source-code` grep `[t2 #42-#43]`. Cloud OpenAPI. `vendor-claim` `pricinglimits.md` |
| **Auth on REST/CDP/viewer** | **None.** CORS `origin: true`. The image also exposes **9223 = nginx → raw Chromium CDP on 9222**, bypassing Steel entirely. | API key (`steel-api-key` header / `apiKey` query) | `source-code` `index.ts:22`, `api/nginx.conf`, `api/Dockerfile:101 EXPOSE 3000 9223`, `cdp.service.ts` `--remote-debugging-address=${HOST}`. Issue #235 (open, updated 2026-10-08), draft PR #43 |
| **Health** | `/v1/health` returned `{"status":"ok"}` while no Chromium was running | n/a | `hands-on†` `[t1 #61, #66]` |

### Q2. Persistence model and the safe release procedure

**Model** `source-code`, checked in the image `[t1 #36]`:
- **Which directory.** `persist:true` uses `/app/api/user-data-dir`. Otherwise Steel uses `CHROME_USER_DATA_DIR` or `/tmp/steel-chrome`.
  - One container persists exactly one profile: whichever volume is mounted at the fixed path.
  - With `CHROME_USER_DATA_DIR`, even the idle default browser holds that profile `[t1 #65]`.
- **What release does.** `POST /v1/sessions/release` → `endSession` → `getBrowserState()` → `shutdown()` → relaunch an idle default browser on `/tmp/steel-chrome` `[t1 #46]`. Inside `shutdown()`:
  - first the context is dumped and then discarded;
  - `browserInstance.close()` sends CDP `Browser.close` and waits for exit;
  - then `process().kill()`. `process()` is the Node `ChildProcess` (`CdpBrowser._create(..., browserProcess.nodeProcess, ...)`), so this is a default `SIGTERM` to the one pid, normally already exited. The process-group `SIGKILL` (`process.kill(-pid,'SIGKILL')` in `@puppeteer/browsers`) runs only on `closeBrowser`'s error path: `Browser.close` throws, then `browserProcess.close()`, then `kill()` `[t1 #37-#38]`.
- **Portability.** Cookies are encrypted with `--password-store=basic` (a fixed key), so a copied user-data-dir works in any container (`cdp.service.ts:898`) `source-code`. Measured: a recreate onto the same volume under a new hostname kept the cookies after the safe release `[t1 #73]`.
- **Cookie commit.** Chromium batches cookie writes:
  - the first pending operation arms a **30 s** timer;
  - 512 pending operations commit at once.

  Source: `sqlite_persistent_cookie_store.cc:1225-1278` @152.0.7977.82, fetched today `source-code`.
- **No flush in the protocol.** The image's devtools-protocol 0.0.1354347 has no `*flush*` method. The only matches are `CacheFlushed` and `CookieFlushed`, which are BFCache not-restored reasons `[t2 #29-#32]`.

**Measured flush matrix** `hands-on†`. Cookies and localStorage are listed separately because they are separate stores.

| Wait after write | End by | Cookie on disk | localStorage kept | Singleton* left | Block |
|---|---|---|---|---|---|
| 0 s, session left live | (polled every ~4 s; t ≈ seconds after the cookie write, ±2 s, given the script's 6 s sleep and +3 s offset) | absent through t+28 s, **present from t+32 s** | n/a | n/a | `[t1 #47]` |
| 2 s | Steel release (n=2) | lost | **lost** | **3 files** | `[t1 #53, #54, #56]` |
| 2 s | raw CDP `Browser.close` (n=2) | lost | kept | **0** | `[t1 #53, #54, #56]` |
| 5 s | Steel release | lost | kept | (not counted) | `[t1 #45, #56]` |
| 5 s | raw CDP `Browser.close` | lost | kept | (not counted) | `[t1 #45, #56]` |
| 31 s | client closed, then CDP `Browser.close`, then Steel release | **kept** | kept | **0** | `[t1 #73]` |
| 35 s | Steel release (`CHROME_USER_DATA_DIR` mode) | **kept** | kept | 3 files | `[t1 #65, #66]` |
| 40 s | Steel release | kept | — | stale lock | existing-assets RESULTS row 3 |

**Answers to the sub-questions:**
- **Waiting fixes the cookie loss.** It was measured at 31, 35 and 40 s, and Chromium's code gives a 30 s commit interval. Use **≥35 s after the last auth-relevant change**.
- **A CDP cookie flush is not possible.** The protocol has no such method.
- **CDP `Browser.close` does not save recent cookies**: 5 s followed by `Browser.close` lost the cookie. It only fixes the stale lock.
  - One possible mechanism, `unverified`. After a raw `Browser.close`, Steel's disconnect handler runs `endSession` and then `shutdown()` on a connection that is already closed. `cdpConnection.closeBrowser()` would then throw into the error path, which sends a process-group `SIGKILL`. That could kill the network-service child before its pending batch commits. Another possibility is that Chromium's own shutdown does not wait for the batch.
- **"Close pages first" has no recorded output.** e_safe_release confounds it with the 31 s wait.
- **A stale lock causes a silent fallback** (R1, `[t1 #56-#62]`):
  - recreate under a new hostname with the lock left in place;
  - the `persist` create returns 200 on `/tmp/steel-chrome`, with empty cookies;
  - the next create returns 500 after 3 attempts;
  - health stays `ok` throughout.
- **Three ways to clear or tolerate the lock:**
  - delete `Singleton*` before start (R2 `[t1 #63]`);
  - recreate with the **same fixed `--hostname`** (R3 `[t1 #64]`, n=1). Chromium treats a same-host lock with a dead PID as stale. Risk: a new process whose PID equals the one in the lock (`unverified`);
  - end with `Browser.close` so that no lock is left (`[t1 #53, #73]`).
- **In `CHROME_USER_DATA_DIR` mode with a new hostname and a stale lock**, even the idle browser failed to start, and health still said `ok` (R4b `[t1 #66]`).
- **Recommended safe release.** Every step is measured at least once, except where marked.
  1. Hold the profile lease.
  2. Stop agent actions. Wait until **≥35 s** have passed since the last login, 2FA or cookie-changing step.
  3. `GET /v1/sessions/{id}/context` and store the cookies, encrypted, as the profile's auth journal. This works instantly, includes httpOnly cookies and needs no flush `[t1 #73]`.
  4. Disconnect agent clients:
     - Playwright `browser.close()` on a `connectOverCDP` browser only disconnects (`[t1 #43]`: the other client survived);
     - Stagehand v4: `stagehand.close()`, not `browser.close()` (`stagehand.md`).
  5. Send raw CDP `Browser.close` on the browser websocket. This leaves 0 `Singleton*` files `[t1 #53, #73]`.
  6. `POST /v1/sessions/release`. Without it, Steel keeps the session `live` `[t1 #45, #73]`.
  7. Only now tar the volume or stop the container.
- **Recommended wake:**
  1. Take the lease.
  2. Delete `Singleton*` in the volume.
  3. Start with `--init --hostname <profile-id>`.
  4. `POST /v1/sessions {"persist":true, …pinned params}`.
  5. Verify that the live Chromium argv has `--user-data-dir=/app/api/user-data-dir`. Run a login probe.
  6. If the probe fails, re-inject the journal with `sessionContext`. This **combination with `persist:true` is untested**.

**Is the context export a better persistence unit than the raw user-data-dir? No, but it is a necessary second copy.**
- **For the user-data-dir:**
  - it is complete: cookies, localStorage, IndexedDB, service workers, Cache Storage, preferences, extension state, site permissions;
  - it is portable (`password-store=basic`);
  - Steel Cloud's Profiles API uses the same unit.
- **Against using the context export alone:**
  - the hostname/origin key mismatch;
  - storage injection only on Steel-tracked page navigations: an origin-keyed import read in a Playwright `newPage()` tab returned `null` `[t1 #68]`; on the primary page it restored `[t1 #69]`;
  - an empty IndexedDB export `[t1 #67]`.
- **For keeping the export as a journal:**
  - it captures cookies the disk does not have yet;
  - it is vendor-neutral, so it suits a Steel ↔ Browserbase migration;
  - it is small (577 bytes for the test page) `[t1 #67]`.

### Q3. Per-session proxy

- **Accepted.** `proxyUrl` is in the OSS create schema (`sessions.schema.ts:30`). Create returned 200 in 1.7 s `[t1 #75]` `source-code`.
- **Plumbed through proxy-chain.**
  - `new ProxyServer(proxyUrl)` listens on `127.0.0.1:<random>` with `requestAuthentication:false` (`utils/proxy.ts:16-63`).
  - Chromium gets `--proxy-server=<local url>` (`session.service.ts:212-221`, `cdp.service.ts:934`) `source-code`.
  - With a dead upstream (`127.0.0.1:9`), HTTPS failed `ERR_TUNNEL_CONNECTION_FAILED`, and HTTP got proxy-chain's status 594 "Connection Refused". The browser had no direct-egress fallback `[t1 #75, #78]`.
  - Note that any process in the container can use the forwarder without credentials.
- **Credentials kept out of Chromium.** Chromium's argv carries only the local URL by construction `source-code`. The in-container `ps` check was **never run** (no recorded output).
  - Credentials were **not** kept out of the API. `response.proxy`, `GET /v1/sessions[].proxy` and `GET /v1/sessions/{id}.proxy` all returned `http://fleetuser:fleetpass@127.0.0.1:9` `[t1 #75]`.
  - Combined with zero auth and CORS `origin:true`, anything on the network path that can call the API can read the credentials. The path demonstrated on browser-box (2026-09-22) was a navigation or redirect to `127.0.0.1:3000/v1/sessions`, with the agent reading the result. A cross-origin `fetch` from a public page to loopback may be blocked by Chromium's local-network checks. That was not tested here.
  - Docker logs held 0 occurrences of the credential `[t1 #78]`.
- **Timezone.** Without `timezone`, Steel resolves it through the proxy via ipinfo.io on every create. With the proxy down, it logged `Using fallback timezone: UTC` `[t1 #75]`. Always pass `timezone`.
- **`PROXY_INTERNAL_BYPASS`.** `source-code` only; **f3 never ran**.
  - It is a comma list of **exact hostnames**. proxy-chain sends those directly (`PassthroughServer`) instead of upstream, together with `0.0.0.0` and `process.env.HOST` (`utils/proxy.ts:27-46`; image `proxy.js:16-22` `[t2 #35]`).
  - It is not a Chromium `--proxy-bypass-list`. Steel passes no bypass list to Chromium.
  - **Chromium's implicit bypass rules send `localhost`, `*.localhost`, `127.0.0.1/8`, `[::1]`, `169.254/16` and `[FE80::]/10` directly, without the proxy** (`net/docs/proxy.md:493-530` @152.0.7977.82, fetched today `source-code`). Three consequences:
    1. Stagehand v4's in-browser CDP websocket needs `PROXY_INTERNAL_BYPASS` only if its URL uses a non-loopback hostname. Loopback never reaches the proxy.
    2. Navigations from pages reach Steel's own unauthenticated API on `127.0.0.1:3000` and raw CDP on `:9222` without the proxy (the 2026-09-22 browser-box exploit class). Reaching a port is not the same as reading its response: script reads are limited by CORS and local-network checks, so the risk is an agent that reads or acts on what it navigated to.
    3. On a DigitalOcean droplet, pages can reach the **metadata service at `169.254.169.254` directly**, around the proxy.
  - Possible fix, **untested**: `CHROME_ARGS=--proxy-bypass-list=<-loopback>` subtracts the implicit rules, so loopback and link-local go to the upstream proxy and are effectively unreachable. Keep the CDP `Fetch` guard regardless.

### Q4. Live viewer

**What a human sees** `hands-on†` `[t1 #89]` (screenshots `spikes/steel/viewer-{1,2,3}-*.png` (image not published)):
- the remote page as a JPEG screencast in a canvas;
- a dark tab bar, with titles and close buttons;
- back, forward and reload buttons;
- a URL bar showing the page URL with a lock icon.

`window.open` from the page created a second tab in the viewer and switched to it. The tab count went to 2, and `live-details` listed both URLs. `live-details.browserVersion` serialises as `"[object Object]"` (issue #332).

**What a human can do:**
- **Click and type.** Typing "viewer-typed" into the-internet login field arrived, and the agent read the same value back. The form was not submitted `[t1 #89]`.
- **Mouse events carry modifiers; key events do not** (`live-session-streamer.ejs:1013-1110` vs `:1127-1150`; `casting.handler.ts:314-326`) `source-code`.
  - Shift works through `e.key`.
  - Ctrl/Cmd shortcuts arrive as plain letters.
- **Paste only works when the viewer is embedded** by a parent page with `?clipboardBridge=true`. The pasted text is then typed one key event per character (`live-session-streamer.ejs:1522-1600`). Otherwise Ctrl/Cmd+V types "v".
- **2FA codes must be typed by hand** unless the gateway's embed page implements the bridge.
- **2FA popups and OAuth windows** appear as viewer tabs (the popup test). Never run:
  - native JS dialogs;
  - HTTP basic auth;
  - WebAuthn/passkey prompts;
  - file pickers.

  These are `unverified`, and are the likeliest login blockers.

**Auth.**
- None. `/v1/sessions/debug` has `onRequest: []`.
- The cast websocket (`/v1/sessions/<anything>/cast?pageId=…|tabInfo=true`) ignores the id and attaches to `activeSession` (`casting.handler.ts:26-40`) `source-code`.
- `debugUrl` is a fixed `http://<DOMAIN>/v1/sessions/debug` with no session id `[t1 #41]`.

**Exposing it safely per profile:**
1. Never publish the Steel port (3000) or 9223.
2. The fleet gateway issues a short-lived, single-use signed URL bound to a **human lease** on that profile. The lease bumps the fencing token, so the agent's calls fail closed.
3. Reverse-proxy only `GET /v1/sessions/debug` and the `/v1/sessions/*/cast` websocket upgrade to that profile's container. Block every other route.
4. Serve the viewer inside a gateway page that implements the clipboard bridge, so humans can paste.
5. After the human finishes, keep the browser up **≥35 s**, then run the safe release. Record who held the lease, and log the screencast URL access.

### Q5. Fingerprint / stealth

Sources:
- `hands-on†` `[t1 #97, #100-#104, #111]`;
- browserscan category colours for default r1 and headful-xvfb r1 were read from the saved screenshots by this agent `hands-on`;
- all modes ran on Steel's primary page;
- the headful modes needed a manual `Xvfb :10`, because without it create returned 500 with "Missing X server or $DISPLAY" `[t1 #100-#101]`.

| Mode (create body) | Page UA seen | sannysoft failed rows | browserscan | creepjs headless / like-headless / stealth |
|---|---|---|---|---|
| default `{}` r1 | Linux aarch64 Chrome/139 | Plugins Length, PluginArray | **Robot** (CDP, Navigator red) | 33% / 75% / 20% |
| default `{}` r2 | Linux x86_64 Chrome/142 | + WebGL Renderer | **Robot** (Navigator) | 33% / 75% / 20% |
| ua-pinned `{"userAgent":"…Chrome/152.0.0.0…"}` | Chrome/152 | Plugins ×2, WebGL Renderer | **Normal** | 0% / 69% / 0% |
| headful-xvfb `{"headless":false}` r1 | aarch64 Chrome/139 | Plugins ×2, **WebGL Vendor + Renderer** ("Canvas has no webgl context") | **Robot** (Navigator) | 0% / 69% / 0% |
| headful-xvfb r2 | x86_64 Chrome/138 | Plugins ×2, WebGL Vendor + Renderer | **Robot** (Navigator) | 0% / 69% / 0% |
| headful-xvfb + ua-pinned | Chrome/152 | Plugins ×2, WebGL Vendor + Renderer | **Normal** | 0% / 63% / 0% |
| skipFingerprintInjection (headless) | **HeadlessChrome/152**; the session API claimed "Chrome/128" | User Agent, Plugins ×2, WebGL Renderer, HEADCHR_UA, CHR_MEMORY | **Robot** (User-Agent) | 67% / 69% / 0% |

**Other measured facts** `hands-on†`:
- **Across 3 `persist:true` sessions on one volume, the fingerprint changes every time** `[t1 #93]`:
  - UA: Chrome/145, then 144, then 142, while the engine is 152;
  - `hardwareConcurrency`: 8, 20, 32;
  - viewport: changed;
  - WebGL renderer: SwiftShader, then "NVIDIA GeForce RTX 4060 Laptop GPU", then SwiftShader, always with vendor "0";
  - `screen`: always 800x600 inside a 1920x1080 window (#330);
  - `navigator.userAgentData` brands: empty.
- **UA-pinned is stable across 2 sessions (0 fields changed)** `[t1 #94]`, but:
  - it shows the container's real `hc=10` and real SwiftShader;
  - the UA-CH brands are empty;
  - the screen is still 800x600.
- **Constant on this host in every session and every mode:**
  - canvas hash `-1820136790`;
  - timezone follows the egress IP's region (from ipinfo, no proxy). Per-profile proxies would change this one.

  Host-wide, and so shared by every profile on a node: the canvas hash, plus the real `hc` and SwiftShader whenever injection is off. Whether they differ across droplets is `unverified`.
- **A CDP-created tab misses injection on its first navigation** `[t1 #94, #96]`:
  - `newPage()` followed by an immediate `goto` showed the real `hc=10` and no cursor overlay;
  - the next navigation on the same tab showed the injected `hc=16`;
  - in the h NEWPAGE run the UA leaked `HeadlessChrome/152`;
  - so one session showed two different `hardwareConcurrency` values.
- **Steel injects a visible cursor `div#__cursor__`** into every headless page (`utils/browser.ts:35-75`) `source-code` `[t1 #93]`. Page scripts can see it.

**Can a fingerprint be pinned per profile across restarts? Not on stock Steel.**
- The REST controller drops `fingerprint`, and `launchMutators` run after it is read (`cdp.service.ts:704-760`) `source-code`.
- Cross-*container* stability was **never measured** (no recorded output).

**The patch** (a small fork, carried until upstream accepts it):
1. Accept `fingerprint` (or `personaId`) on `POST /v1/sessions`. Store it in the profile record. Inject that object instead of generating one.
2. Apply `screen` / `availScreen` and DPR from the persona; this fixes #330.
3. Set the UA-CH brands consistent with the real engine major.
4. Inject on `targetcreated` before the first navigation, or attach with `waitForDebuggerOnStart`, to close the `newPage` race.
5. Drop the cursor `div`, or move it out of the page DOM.
6. Allow WebGL in headful by filtering `--disable-gpu`. `FILTER_CHROME_ARGS=--disable-gpu` exists in `env.ts` and is applied to the launch args. **Untested.**
7. Pin `timezone` from the persona and never call ipinfo.

The stock workaround is only partial: `skipFingerprintInjection:true` plus a `userAgent` pinned to `Chrome/152.0.0.0` (headless, or headful under Xvfb), plus `timezone` and `dimensions`.
- It scored "Normal" on browserscan and 0% headless on creepjs.
- It still has no plugins, SwiftShader or no WebGL, empty UA-CH brands, an 800x600 screen and host-wide constant values.
- These three pages are weak proxies for Meta/TikTok/X detection. See `antidetect-proxies.md`.

**Sibling claims:**
- **antidetect-proxies, "headful has no WebGL due to `--disable-gpu`": confirmed.** sannysoft shows "Canvas has no webgl context" in all three headful runs.
- **scale-infra, "fingerprint re-randomised per launch": confirmed** within one container.
- **scale-infra, headful 500 cause: refined.** scale-infra reported "Failed to connect to the bus". This run logged `Missing X server or $DISPLAY` 12× `[t1 #101]`. Both point to the stock entrypoint starting neither Xvfb nor (unless `DEBUG=true`) dbus.

### Q6. Resources

`hands-on†`, `docker stats` plus cgroup `anon`, on an arm64 Mac VM with a 1.5 GiB / 1.2 CPU cap. "Idle" always includes Steel's own default Chromium. `rss_sum` is not reported, because it double-counts shared pages.

| State | cgroup anon | docker MemUsage | CPU | PIDs | Block |
|---|---|---|---|---|---|
| fresh container, idle | 448-449 MiB (`--init`); 473-508 MiB (no init) | 453-705 MiB (`--init`, 2 runs); 486-973 MiB (no init) | 0-0.8% (`--init`); 0-23% (no init, first sample) | 133-134 | `[t1 #112, #113]` `[t2 #47]` |
| one example.com tab | 485-486 MiB; 486-517 MiB | 530-643 MiB; 586-619 MiB | 5-35% | 132-142 | same |
| one creepjs tab | 584-639 MiB; 639-676 MiB | 646-887 MiB; 755-929 MiB | 7-30% | 139-167 | same |

Other measurements and context:
- Create took 1.0-2.6 s and release 1.3-2.8 s over 8 warm cycles `[t1 #72]`. A restored-profile create took up to 7.4 s `[t1 #45]`.
- One release took 19 s `[t1 #64]`.
- browser-box's README measured 0.69-1.36 GiB on real browsing (`scale-infra.md`).
- Social SPAs and x86 droplets were **not measured**.

### Q7. Steel Cloud pricing, limits, Profiles API, AUP

**Freshness.** Re-fetched by this agent at 2026-10-10 14:20Z (`hands-on` curl). The content is `vendor-claim` / `official-docs`. These four pages are byte-identical to the 2026-10-09 corpus:
- `steel.dev/pricing.md` (sha256 `8ebbe74a…`);
- `docs.steel.dev/overview/pricinglimits.md` (`ef70f318…`, page "Last Edit: June 30th, 2026");
- `https://docs.steel.dev/overview/profiles-api/overview.md` (`6f6bd9f7…`);
- `https://docs.steel.dev/overview/self-hosting/steel-local-vs-steel-cloud.md` (`e7bcd5ec…`).

**Plans:**
- Launch: $0 + usage, with a $30 one-time credit valid 90 days.
- Scale: $250/mo + usage, with $100/mo credit.
- Enterprise: custom.

**Rates.** Browser hour: $0.10 / $0.08, billed per minute and rounded up. Proxy: $10 / $6 per GB. CAPTCHA: $3 / $1 per 1k. Browser tools: $5 per 1k.

**Limits:**
- concurrency: 10 / 100 / 1,000+;
- max session: 15 min / 1 h / up to 24 h;
- 60 / 600 requests per minute;
- retention: 7 / 14 days;
- Stealth Browser and reserved pools: Enterprise only;
- dedicated IPs: $5/IP/month on Scale;
- Launch needs a $10 paid deposit to unlock CAPTCHA solving and Steel proxies;
- Cloud sessions appear to be headful by default. This is an inference from the OpenAPI `headless` and `recording` descriptions, not a documented statement.

**Profiles API:**
- a snapshot of the user-data-dir, saved on release;
- `READY` / `FAILED` states, with a 300 MB cap;
- auto-deleted after 30 days unused;
- `persistProfile:true` plus `profileId` is needed to keep accumulating state;
- the profile's `userAgent`, proxy and userDataDir zip can be updated;
- the docs recommend one profile plus one dedicated IP per account.

**AUP (Terms of Service).** "Last updated February 05, 2025", Nen Labs, Inc. Captured 2026-10-10 to `<scratch>/spikes/steel/tos/steel-tos-2026-10-10.txt`; line numbers re-checked today.
- Prohibited:
  - "Use the Services to violate any website's terms of service, robots.txt, or similar access restrictions" (L187);
  - "circumvent paywalls" (L188);
  - "create fake accounts or engage in identity fraud" (L190).
- The general list also bans "automated use of the system, such as using scripts to send comments or messages" (L166). That clause is about Steel's own Services.
- Steel may terminate "FOR ANY REASON OR FOR NO REASON" (L238).
- **Implication.** Driving client accounts on platforms whose ToS forbid automation (`antidetect-proxies.md`) breaches Steel's ToS as well as the platform's. Self-hosted OSS (Apache-2.0) has no AUP.

### Q8. Running N OSS containers per droplet; clustering

**There is no official clustering.**
- `https://docs.steel.dev/overview/self-hosting/clustering.md` is a title-only stub (corpus INDEX) `official-docs`.
- The OSS OpenAPI describes "controlling a single instance of Steel Browser" `source-code`.
- `gh search code --owner steel-dev` found no Deployment or Helm manifests. The org's repos are SDKs, docs, CLI, MCP, `hermes-steel` and others `[t1 #117]`.
- Draft PR #240 "Session State Machine" and PR #375 are single-instance lifecycle work.

**The unit is one container per awake profile.** Each container has:
- its own volume at `/app/api/user-data-dir`;
- `--hostname <profile-id>`, `--init`, and memory/CPU caps;
- its own Docker network;
- no published 9223;
- a loopback- or VPC-bound 3000 port.

**Measured density.** scale-infra measured 3 concurrent containers on one host: 826 / 796 / 814 MiB peaks, 2.4 GiB total (`scale-infra.md` Q1). Not re-run here.

**Planning slot.** Keep scale-infra's 1.5 GiB + 0.35 GiB agent and 0.6 vCPU. The anon figures above, about 0.45-0.68 GiB, fit inside it with headroom for social SPAs.

**Wake on demand, not always on.** A cold create on a restored profile took 2-7 s for Steel alone `[t1 #45, #63]`; container boot comes on top of that.

### Q9. License, activity, relevant open issues

**License and activity** (`hands-on` gh, 2026-10-10 14:28Z):
- License: Apache-2.0.
- 7,779 stars, 992 forks, 75 open issues.
- Last push 2026-10-09T18:33Z; not archived.

**Releases and commits:**
- Releases: v0.5.4-beta (2026-08-25, latest), v0.5.3-beta (2026-04-24), v0.5.2-beta (2026-03-15).
- 38 commits since 2026-01-01.
- The ten most recent (2026-07-20 .. 2026-10-06) are fixes in cdp, context, files and sessions `[t1 #114]` `[t2 #37]`.

**Open issues and PRs that bite the fleet** (state re-read today `hands-on` gh; titles are `third-party`):

| # | State (updated) | Title / relevance |
|---|---|---|
| #347 / PR #348 | open (2026-08-24) | Caller-supplied `userDataDir` ignored. Fix PR open, not merged. |
| PR #375 | open (2026-10-10) | Guard singleton ownership: 409 on a competing create/release, scoped release/read, bounded launches. Matches `[t1 #42]`. |
| #235 / draft PR #43 | open (2026-10-08) | API key auth for the self-hosted container. A maintainer comment plans an optional `STEEL_API_KEY` header on REST and the WS upgrade. |
| #330 | open (2026-08-24) | Requested dimensions leave screen at 800x600. Reproduced `[t1 #93-#94]`. |
| #359 | open (2026-09-08) | WebGL renderer always SwiftShader. |
| #294 / #295 / #302 | open | fingerprint-generator 2.1.82 lacks Chrome 146 samples at 1920x1080. "Failed to generate a consistent fingerprint". Steel now logs "relaxed constraints" instead `[t1 #46, #60]`. |
| #322 | open (2026-09-17) | dbus launch failure in Docker. |
| #333 | open (2026-08-03) | Session viewer UI always shows `sessions[0]`. |
| #331 | open (2026-08-07) | Proxy byte counters stay zero. |
| #332 | open | `live-details.browserVersion` is `"[object Object]"`. Reproduced `[t1 #89]`. |
| #247 | open (2026-01-19) | Performance degradation with concurrent tabs. |
| PR #293 | closed, not merged (created 2026-05-03) | Inactivity-based session timeout. Hence there are no timeouts. |

---

## 3. OSS-vs-fleet gap table

| Need (fleet) | Stock OSS Steel gives | Fleet must build | Evidence |
|---|---|---|---|
| Many isolated profiles | 1 browser per container; `userDataDir` ignored; a 2nd create silently takes over | One container per awake profile (volume at the fixed path, `--hostname=<profile>`, `--init`, caps, own network). A lease with fencing tokens. Optionally carry PR #348. | `[t1 #42]`, `source-code` |
| Durable login across restarts | Volume persists, but: the 30 s cookie window; Steel release leaves `Singleton*` (silent fallback to a blank profile with a 200); `docker stop` = SIGKILL | Node-agent safe-release and wake (Q2). An auth-cookie journal from the context export. A volume tarball to Spaces after release. A post-wake login probe. | `[t1 #45-#74]` |
| Readiness / health | `/v1/health` says ok with no browser | Check the live `--user-data-dir` in `ps` plus a CDP `Browser.getVersion` plus the login probe. Restart on failure. | `[t1 #61, #66]` |
| Zombie-free long runs | Zombies accumulate (151 after 8 cycles) | Always run with `--init` (tini). | `[t1 #72]` |
| Timeouts / idle reaping | None | Fleet-enforced max session and inactivity timers, then the safe release. | `source-code` |
| Auth on control plane | None on 3000, 9223, CDP or viewer; CORS `*`; proxy credentials echoed | Private network only. The gateway holds per-profile scoped tokens. Never publish 3000 or 9223. Never give Steel URLs to Hermes. | `source-code`, `[t1 #75]` |
| Human login | Unauthenticated viewer; typing works; paste only via an embed bridge; key modifiers dropped | Gateway-proxied viewer behind a human lease. Signed one-time URL. Clipboard-bridge embed page. "Login done" button, then wait ≥35 s, then safe release. | `[t1 #89]`, `source-code` |
| Same fingerprint every wake | Random per launch; injection race on new tabs; 800x600 screen; constant host canvas/GPU/hc | Persona registry and a patched Steel (Q5). A drift check that re-hashes probe values every wake. | `[t1 #93-#111]` |
| Sticky IP per profile | `proxyUrl` works and fails closed; credentials echoed; TZ falls back to UTC | Per-profile forwarder owned by the node agent (credentials never sent to Steel). Pinned `timezone`. Egress firewall to the proxy only. `--proxy-bypass-list=<-loopback>` (untested). CDP `Fetch` guard blocking loopback and 169.254/16. | `[t1 #75, #78]`, Chromium `proxy.md` |
| CAPTCHA | None | Escalate to a human lease through the viewer. Prefer accounts and cadence that avoid challenges. | `official-docs` |
| Credentials | None | Not needed by design: humans log in and agents never type credentials. | brief |
| Audit / evidence | Recorder events to the log store (in-memory by default) | Evidence writer (screenshot plus DOM receipt per side effect) and an effect ledger. Obsidian daily rollups for agent memory. | `source-code` |
| Stagehand v4 | Works only with the extension mounted, `extensions:["stagehand"]`, and a CDP URL reachable from inside the browser | Bake the extension into the fleet image at `/app/api/extensions/stagehand`. Use a loopback CDP URL inside the container. | `stagehand.md` |
| Image drift | `:latest` = 0.5.3 even though 0.5.4-beta exists | Pin by digest. Canary-test each new tag against this spike's probes. | `[t1 #36]`, gh |
| Scheduling / placement | Nothing | Placer + node agent + Postgres leases (`scale-infra.md`). | `official-docs` stub |

---

## 4. Operating notes for a Hermes agent

These notes are for the fleet skill that a Hermes profile calls. Hermes agents never get Steel or CDP URLs; they call the fleet tool. The notes cover what the tool does underneath and what the agent must respect.

1. **One writer per profile.** Call `acquire(profile)` before any browsing, and treat a lost lease as "stop now".
   - Never start a second session on a profile that is awake. In Steel, that silently reuses or relaunches the same browser `[t1 #42]`.
2. **Wake, then verify.** After wake, the tool runs a login probe for each platform the profile maintains.
   - If the probe says "logged out", **do not** try to log in. Request a human login (rule 4).
   - A 200 from Steel's create does not prove the right profile is loaded `[t1 #56]`.
3. **Drive the existing primary tab.**
   - Steel's fingerprint and storage injection can miss a brand-new CDP tab on its first navigation `[t1 #96]` `[t1 #68]`.
   - Open new tabs only after the first navigation on the primary tab has completed.
   - Popups and OAuth windows will appear as extra tabs.
4. **Human login handoff.** The agent posts a "needs human login" request with the profile id and site. The fleet then:
   1. bumps the lease to the human;
   2. issues a one-time viewer link;
   3. on "done", **waits ≥35 s** before any release;
   4. exports the context into the profile's auth journal.

   Humans can type, and 2FA codes are typed by hand. Paste works only in the fleet's embed page. Popups show as tabs.
5. **End every run with the tool's `release`, never by killing.** The tool's release is the Q2 procedure:
   1. wait ≥35 s since the last auth change;
   2. export the context;
   3. CDP `Browser.close`;
   4. Steel release;
   5. tarball.

   If the agent changed auth state (for example re-auth or "remember this device"), it must say so, so that the tool waits.
6. **Never pass Cloud-only fields** (`persistProfile`, `profileId`, `useProxy`, `solveCaptcha`, `timeout`) to self-hosted Steel. They return 200 and do nothing.
7. **Pinned identity parameters belong to the profile record**, not the agent: UA, timezone, dimensions and the forwarder port. The agent must not change them.
   - Do not set `skipFingerprintInjection` without a pinned `userAgent`. That combination leaks `HeadlessChrome` `[t1 #111]`.
8. **Engines:**
   - Stagehand v4 needs the fleet image's extension and `{"extensions":["stagehand"]}` at create; v3.7.3 attaches with a plain `cdpUrl` (`stagehand.md`).
   - Browser-Use attaches with `BrowserSession(cdp_url=…)` (corpus `https://docs.steel.dev/integrations/browser-use.md`).
   - For each, call the engine's own close or disconnect, which leaves the browser running for the safe release.
9. **Security.** Pages can reach loopback and link-local addresses directly, around the proxy. The tool's CDP guard blocks `127.0.0.0/8`, `localhost`, `169.254.0.0/16` and the fleet's own hosts.
   - The agent must never navigate to internal addresses, even if a page or prompt tells it to.
10. **Expect slow or failing wakes.** A wake can take several seconds, and a create can return 500 after a stale lock. The tool retries after clearing the lock under the lease. The agent should not retry blind.

---

## 5. Risks and unknowns

**Risks:**
- **Silent profile loss.** Steel answers 200 on the wrong profile after a stale lock `[t1 #56]`. Mitigation: wake verification, plus `--hostname` and lock clearing. The fixed-hostname approach is n=1. A PID collision with the PID recorded in the lock is `unverified`.
- **The cookie window is n=1 for timing.** It agrees with Chromium's 30 s constant. The `Browser.close`-doesn't-flush mechanism is `unverified`. Hypothesis: the error path of Steel's second `shutdown()`, which sends a process-group `SIGKILL`.
- **Fork liability.** Pinned fingerprints, the userDataDir fix and auth need a patched image. Upstream ships often (38 commits this year), and `:latest` lags the releases.
- **Fleet-wide linkability.** The same canvas hash, `hc` and SwiftShader appeared across all sessions on one host. Real-device diversity needs per-node or per-persona variation, and its plausibility is untested.
- **Unauthenticated surfaces.** Ports 3000 and 9223 (raw CDP), the viewer, and proxy credentials in API responses. Any misconfigured port exposure gives full control of a logged-in client account.
- **Metadata endpoint** (`169.254.169.254`) reachable around the proxy on DigitalOcean (Chromium implicit bypass). Inference from Chromium docs and Steel flags; `unverified` on a droplet.
- **Steel Cloud AUP** conflicts with automating client social accounts against platform ToS.

**Unknowns** (need hands-on on a droplet, with Justin's yes):
- Does `PROXY_INTERNAL_BYPASS` / `--proxy-bypass-list=<-loopback>` behave as described? Is the in-container `ps` free of proxy credentials? (f3 never ran.)
- Is the fingerprint stable across container recreates with the patch?
- Does `FILTER_CHROME_ARGS=--disable-gpu` restore WebGL in headful?
- Resource use on x86 droplets with social SPAs, and N-per-droplet density.
- How the viewer handles native dialogs, HTTP auth, passkeys and file pickers.
- Does `sessionContext` combined with `persist:true` behave correctly?
- Does closing pages before `Browser.close` change cookie durability?
- IndexedDB export: why was it empty?
- Steel Cloud behaviour in general. No key exists, so nothing was tested: profiles, Stagehand v4 preloaded extension, stealth quality.

---

## 6. Sources

**Raw outputs**
- `fleet/research/spikes/steel/RESULTS.md`. Every `[tN #k]` block is verbatim from:
  - t1 = first attempt agent transcript (local, not published): `wf_bcf55518-978/agent-a0c8966259a2a5e93.jsonl`;
  - t2 = second attempt agent transcript (local, not published): `wf_f416b110-ea2/agent-a5c7e45052d066185.jsonl`.
- The Oct-10 03:17Z attempt (`wf_f147e0b3-6c9/agent-accfe553800e801d6.jsonl`) read source only and ran no probes.

**Spike scripts and artefacts**
- Scripts: `fleet/research/spikes/steel/*.cjs|*.sh`.
- Screenshots: `bot-*-{sannysoft,browserscan,creepjs}.jpg`, `viewer-{1,2,3}-*.png` (image not published).
- `<scratch>/spikes/steel/{ctx-export.json, ctx-export-origin.json, bs-crop.jpg, tos/steel-tos-2026-10-10.txt}`.

**Steel source** (`steel-dev/steel-browser@1131a0222a27f391bf8f27cca6f278ddf7ace8dd`):
- `api/src/services/session.service.ts` (67, 140-235);
- `api/src/services/cdp/cdp.service.ts` (310-340, 704-760, 800-960, 1228-1340, 1397-1427);
- `api/src/utils/{context.ts, proxy.ts, extensions.ts, browser.ts}`;
- `api/src/services/context/chrome-context.service.ts`;
- `api/src/modules/sessions/{sessions.routes.ts, sessions.controller.ts, sessions.schema.ts}`;
- `api/src/plugins/browser-socket/casting.handler.ts`;
- `api/src/templates/live-session-streamer.ejs`;
- `api/src/env.ts`, `api/src/index.ts`, `api/nginx.conf`, `api/Dockerfile`, `api/entrypoint.sh`.
- Compiled image `sha256:7a161b95e8a9` `/app/api/build/**` and `/app/node_modules/{puppeteer-core,@puppeteer/browsers,devtools-protocol}` (`[t1 #36-#38]`, `[t2 #26-#35]`).

**Chromium source** (fetched today):
- `net/extras/sqlite/sqlite_persistent_cookie_store.cc` @`152.0.7977.82` L1225-1278, and `main` L1237-1290;
- `net/docs/proxy.md` @`152.0.7977.82` L493-545.

**Steel docs and corpus** (`fleet/research/corpus/steel/`, `official-docs` / `vendor-claim`):
- `INDEX.md`;
- `https://docs.steel.dev/openapi.json`, `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published);
- `https://docs.steel.dev/overview/{pricinglimits.md,profiles-api/overview.md,self-hosting/steel-local-vs-steel-cloud.md,self-hosting/clustering.md,sessions-api/reusing-auth-context.md,sessions-api/embed-sessions/live-sessions.md,stealth/proxies.md,sessions-api/dedicated-ips.md,legal.md}`;
- `https://docs.steel.dev/integrations/{stagehand,browser-use,playwright,puppeteer}.md`;
- `https://steel.dev/pricing.md`.
- Live re-fetch 2026-10-10 14:20Z (hashes in RESULTS.md).

**GitHub** (`hands-on` gh, 2026-10-10):
- `steel-dev/steel-browser` repo metadata and releases;
- issues #347, #235, #330, #359, #294, #295, #302, #322, #333, #331, #332, #247;
- PRs #348, #375, #43, #240, #293;
- the `steel-dev` org repo list.

**Sibling dossiers and spikes** (confirmed or refined here):
- `spikes/existing-assets/RESULTS.md`:
  - persistence: confirmed;
  - lock fallback: now measured;
  - the 5 s / 40 s cookie result: confirmed, with the window narrowed to 28-32 s;
  - "fixed hostname, untested": now tested, n=1.
- `dossiers/scale-infra.md`:
  - re-randomised fingerprint: confirmed;
  - userDataDir ignored: confirmed;
  - zero auth: confirmed, and extended with port 9223 and credential echo;
  - headful 500 cause: refined.
- `dossiers/antidetect-proxies.md`:
  - headful has no WebGL: confirmed;
  - Steel stealth inconsistent: confirmed;
  - proxy credentials kept out of Chromium: true, but echoed by the API.
- `dossiers/stagehand.md`:
  - v4 extension recipe;
  - the `PROXY_INTERNAL_BYPASS` note narrowed: loopback URLs bypass the proxy anyway.
