> **Read with its verification report.** [verification/antidetect-proxies.md](../verification/antidetect-proxies.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: anti-detect browsers, stealth and proxies for 30 → 1,000 persistent client social identities

Agent: antidetect-proxies (rerun after the first attempt hit a usage limit). Research date: 2026-10-09/10.
Provenance tags follow `fleet/research/BRIEF.md`: `hands-on`, `source-code` (pinned commit), `official-docs`, `vendor-claim`,
`third-party`, `unverified`. Spike scripts, raw JSON and `RESULTS.md` are in `fleet/research/spikes/antidetect-proxies/`.
Spend: **$0**. No container is left running.

Pinned sources: steel-browser `1131a0222a27f391bf8f27cca6f278ddf7ace8dd`, stagehand monorepo `1fc884992b68a0196ea5c6e96cc29924b0922ef4`,
installed `@browserbasehq/stagehand@4.2.0` (`<scratch>/npm`), browser-use `c75e8476e26d18b7617643bc2ae082fae8eae431` plus installed
`browser-use==0.13.11`, and an older local tool's results doc (private; commit withheld).

---

## 1. Verdict

1. **Do not use OSS Steel's built-in stealth for persistent identities. Turn it off, then pin values yourself.**
   - It generates a new random fingerprint on every launch, and there is no HTTP field to pin one (`source-code`).
   - The fingerprint it generates is internally inconsistent (`hands-on`):
     - the UA says Chrome/142-144 while the engine is Chromium 152;
     - the screen is 800x600 inside a 1920x1080 window;
     - the main thread reports one GPU while workers report a hardcoded Windows D3D11 NVIDIA string;
     - all patched functions fail the `toString` native check.
   - deviceandbrowserinfo flags it (`hasInconsistentWorkerValues`).
   - The same instability is what "same browser every time" forbids.
2. **The recipe in the question is the right one. What matters is who supplies the "pinned consistent fingerprint".** For legitimate,
   human-paced upkeep of 30-1,000 client accounts:
   - persistent profile directory;
   - one static ISP IP per profile, never shared or rotated;
   - timezone, locale and geo pinned to that IP;
   - a fingerprint that is the same at every wake;
   - human-like cadence;
   - headful or source-patched Chromium.

   A commercial anti-detect browser adds no capability that changes the dominant risks: behaviour, platform ToS, and IP history.
   It is optional, not required. Two OSS-compatible ways to get the pinned fingerprint:
   - **(a) An "honest" persona:** stock Chromium, headful under Xvfb, no spoofing, consistent by construction. It is visibly a Linux machine with
     software (SwiftShader) graphics.
   - **(b) A source-patched Chromium with a seed-pinned persona.** Measured on CloakBrowser: the same seed gave the same fingerprint across
     restarts, workers and main thread agreed, and `toString` checks were clean.
3. **The phrase "returns a CDP websocket, so Stagehand can drive it" is false for Stagehand v4** (`hands-on` + `source-code` + `official-docs`). Stagehand 4.2.0 runs inside the
   browser as an MV3 extension, "Stagehand Runtime". To attach to a browser it did not launch, all three of these must hold:
   - the extension must be loadable from the **browser's** filesystem ("Loading requires a shared filesystem");
   - the CDP URL must be reachable **from inside the browser at the same address**, because the extension dials it back;
   - the kernel must expose the `Extensions.*` CDP domain. Debian Chromium 152 worked. CloakBrowser's Chromium 146 failed with
     `Method not available.`, even with the extension preloaded.

   Browser-Use (`cdp_url`) attaches to any Chromium CDP endpoint without these constraints.
4. **Stagehand v4 is the more detectable engine on stock Chromium** (`hands-on`, public test page only).
   - It trips deviceandbrowserinfo's `isAutomatedWithCDP`.
   - Its extension **stays resident after `close()`** and keeps tripping the check on new tabs until it is uninstalled (`Extensions.uninstall`) or the browser restarts. A CDP-loaded extension is session-only and is not written into the profile (`hands-on`).
   - Browser-Use 0.13.11 attached by `cdp_url`, with per-step DOM and screenshot extraction, did not trip it. This is **measured for attach, navigate and state reads only**; clicks, typing and scrolling were not run against the test. From source, the default Agent tools avoid the one path that sends `Runtime.enable` (the actor `Page`). The MCP server's coordinate click and the actor API do take that path.
   - A source-patched build (CloakBrowser) hid Playwright's CDP signal.
   - Whether Meta, TikTok, X or LinkedIn use this signal is **unknown**.
5. **The Linux-server constraint filters the vendor list hard** (`official-docs` / `vendor-claim`).
   - Linux-capable with a documented CDP path: Kameleo (official Linux Docker image, Apr 2026), Multilogin X (Ubuntu agent under Xvfb),
     AdsPower (Ubuntu Desktop 22.04+ app, `headless`, `launch_args`), Octo (Linux build plus a Docker recipe), DICloak (Docker agent image),
     Nstbrowser (browserless Docker), GoLogin (SDK runs Orbita on Linux), Dolphin and MoreLogin (Linux downloads), CloakBrowser (Docker).
   - Windows/macOS only, so ruled out for DigitalOcean: **Undetectable** and **Incogniton**.
   - Firefox kernels (Multilogin Stealthfox, Kameleo Junglefox, Camoufox) cannot be driven by Stagehand or Browser-Use. Both are CDP-only.
6. **The anti-detect licence is a small line item. Integration risk is what decides.**
   - Licence for API-capable plans: about $29-€79/mo at 30 profiles, $36-€299 at 100, and $179-€1,499 at 1,000 (`vendor-claim`).
   - Against scale-infra's totals of $294 / $639 / $4,724 per month (1 h/day, self-hosted autoscaled), that is roughly 10-30%, 6-50% and 4-35%, converting EUR at about 1.1 USD.
   - The real costs are elsewhere:
     - vendor desktop agents on Linux;
     - Stagehand compatibility, which must be tested per vendor kernel;
     - vendor lock-in of profile data;
     - the vendor cloud holding client session cookies;
     - kernels lagging Chrome.
7. **Proxies:**
   - **Use** one **dedicated static ISP IP** per profile, bought for a whole term, about $2.5-3.3 per IP-month (`vendor-claim`).
   - **Do not use** shared ISP IPs (Oxylabs: "Shared with up to 3 users") or rotating residential for logged-in identities.
   - Mobile dedicated ports cost about $117-130/month (IPRoyal) and are a targeted exception, for example TikTok-heavy profiles.
   - Vet provenance: **NetNut's domains were seized by the FBI on 2026-07-02 over the Popa botnet**, and its pool was widely white-labelled
     (`third-party`, Krebs). netnut.io/pricing now shows the seizure banner (`hands-on` fetch).
8. **Keep credentials out of the browser.** Bind each profile's proxy through a **local, credential-less forwarder** on the node; Steel already
   does this with proxy-chain. Two engines need it:
   - Stagehand `localBrowser.launch` rejects proxy credentials;
   - Browser-Use answers proxy auth through `Fetch.authRequired`, which only works when Browser-Use owns the session.
   Pin timezone with the process `TZ` and locale with `--lang`, natively, not through CDP emulation.
9. **The biggest risk for client accounts is ToS, not fingerprinting.**
   - X: scripting the website "may result in the permanent suspension of your account".
   - LinkedIn bans bots and "copying cookies" to use another's account.
   - Meta bans automated access without permission and password sharing.

   Prefer sanctioned delegation (Meta Business roles, LinkedIn Page admins, X delegate access, TikTok Business Center) and official
   posting APIs. Keep browser agents for the gaps.

Corrections to sibling dossiers:
- `browserbase.md` stands.
- `scale-infra.md` asked whether Steel's generator is usable at all. Answer: **no, not for persistent identities**.
- `scale-infra.md` asked whether headful is needed. Answer: headful avoids the `HeadlessChrome` leak that
  `skipFingerprintInjection` exposes in headless mode. Under Steel, headful has **no WebGL at all**, because Steel's static `--disable-gpu`
  applies in both modes. A WebGL-less desktop is itself an anomaly, so the fleet's own launch config needs SwiftShader WebGL or a patched persona.

---

## 2. Answers to the numbered questions

### Q1. Anti-detect vendor matrix

Column legend:
- **Linux** = can run on a headless Linux server or in Docker (the DigitalOcean constraint).
- **CDP** = the start API returns a Chromium DevTools endpoint usable by Playwright `connect_over_cdp`, and therefore by Browser-Use `cdp_url`.
- **Stagehand prereqs** = can we pass custom Chromium flags or preload an extension, and how old is the kernel. See Q2 for why this matters.
- Prices are list prices, monthly billing unless stated, fetched 2026-10-10.

| Vendor | Engine(s) | Linux / Docker | Start API → CDP | Custom flags / extensions | Proxy per profile | ~100 profiles | ~1,000 profiles | Provenance |
|---|---|---|---|---|---|---|---|---|
| **DICloak** | Chromium kernels, downloaded on demand | **Docker agent image** `dicloakinc/dicloak-agent-image` (Agent API :52100, CDP ports 45000-45099, up to 100 concurrent). A "runtime image" is non-headless | Local API opens profile → `debug_port` → `/json/version` → `webSocketDebuggerUrl` | Not documented | Yes (UI/API) | Plus $28.8/mo or Share+ $138/mo; Open API from Plus. **Profile counts hidden** ("-+") | Unknown, contact | `vendor-claim` dicloak.com/develop/docker (build ~2026-08-28), dicloak.com/pricing |
| **Multilogin (X)** | Mimic (Chromium) and Stealthfox (Firefox) | **Ubuntu only**: `mlx` agent + `Xvfb :99` as systemd units (updated 2026-08-14). Headless via `headless_mode=true` | `GET https://launcher.mlx.yt:45001/api/v2/profile/f/{folder}/p/{profile}/start?automation_type=playwright&headless_mode=…` → port → `connectOverCDP("http://127.0.0.1:"+port)`. "Playwright for Stealthfox is not available" | Not documented for start | Yes | **$40/mo** (Business 100); $26.67 billed annually | **$185/mo** (1,000); $121.25 billed annually | `official-docs` multiloginx.helpjuice.com (headless 2026-08-27, linux-agent-autolaunch 2026-08-14, playwright example 2026-03-05); `vendor-claim` multilogin.com/pricing |
| **GoLogin** | Orbita (Chromium) | SDK (Node/Python, `gologin` 2026.6.24) downloads Orbita, `os:'lin'`; headless via `extra_params:["--headless"]`; no official Docker image found. **Cloud Browser**: `https://cloudbrowser.gologin.com/connect?token=…&profile=…` | `GL.launch()` / `gl.start()` returns a ws/debugger URL | **`extra_params`** (any flags, e.g. `--load-extension`) | `changeProfileProxy` | **$39/mo** (Professional 100; API starts here); $19.50 billed annually | **$179/mo** (Enterprise 1,000); $89.50 billed annually | `official-docs` npm/PyPI README; `vendor-claim` gologin.com/pricing; `third-party` search summary for Cloud Browser docs |
| **AdsPower** | SunBrowser (Chromium), FlowerBrowser (Firefox) | **Linux (64-bit), "Ubuntu Desktop 22.04 or later"** app; client must be running. Also has a CLI | `POST /api/v2/browser-profile/start` → `ws.puppeteer`, `debug_port`. Params include **`headless`**, **`launch_args`**, **`cdp_mask`** ("masks CDP detection", default 1) | **`launch_args`** | Yes | ~$36/mo (Professional 100) | Custom / unknown | `official-docs` localapi-doc-en.adspower.com; `vendor-claim` adspower.com/download; `third-party` pricing (afftank, affninja; official page renders no prices) |
| **Kameleo** | Chroma (Chromium), Junglefox (Firefox) | **Official Linux Docker image** `kameleo/kameleo-app:latest` (Ubuntu 22.04, **amd64**; launched 2026-04-24), `-e PAT=…`, `--shm-size=2g`, :5050, VNC optional. Headless mode listed on all plans | `ws://localhost:5050/playwright/{profileId}` → `connect_over_cdp`; Junglefox only through a bridge (`launch_persistent_context`) | "To use custom flags or preferences, call `startProfile` before connecting." Docs say not to add stealth patches | Yes | **Priced by concurrent browsers**: Startup €59 (10), **Business €299 (100)** | **Enterprise €1,499 (1,000 concurrent)**; local profiles unlimited | `official-docs` developer.kameleo.io/integrations/{docker,playwright}; `vendor-claim` kameleo.io/pricing, changelog 2026-04-24 |
| **Octo Browser** | Octium (Chromium) | Linux tarball; API guide has a Docker section (Ubuntu 22.04 container, headless, `seccomp:unconfined`) | `POST http://localhost:58888/api/profiles/start {uuid, headless, debug_port, flags, …}` → `ws_endpoint`, `debug_port` | **`flags`** | Yes | €79/mo (Base, 200 profiles; API 50 RPM) | €329/mo (Advanced, up to 100k profiles) | `official-docs` blog.octobrowser.net API guide; `vendor-claim` octobrowser.net/pricing |
| **Dolphin{anty}** | Chromium | "For Linux" download; headless via `headless=1` (`third-party`) | `GET http://localhost:3001/v1.0/browser_profiles/{id}/start?automation=1` → `port` + `wsEndpoint` (`third-party`; the app must be running, loopback only) | Unknown | Yes | $89/mo (Base 100) | $299/mo (Enterprise 1,000) | `vendor-claim` dolphin-anty.com/pricing; `third-party` API shape |
| **MoreLogin** | Chromium | "Linux (Desktop & Server)" download | Local API (Selenium/Puppeteer listed) | Unknown | Yes | Calculator, not shown | Calculator, not shown | `vendor-claim` morelogin.com/pricing |
| **Nstbrowser** | Chromium | **Docker** `nstbrowser/browserless` (blog 2024-09-18, tag `0.0.1-beta`), :8848, `TOKEN` | `ws://{host}:8848/ws/connect` (+ config) → `connectOverCDP` | Config JSON (not detailed) | Yes | Free plan: 500 profiles | Starter $29.9/mo (20,000 profiles) + **per-launch** fees ($0.008-0.015/launch) | `vendor-claim` nstbrowser.io pricing and blog |
| **Undetectable** | Chromium (lies applied inside Chromium); JS for Safari/Firefox personas | **Windows / macOS only** | Local API | n/a | Yes | $69/mo (100 cloud, unlimited local) | $139/mo + $100 per extra 1,000 cloud | `vendor-claim` undetectable.io/pricing; `third-party` Castle 2025-03-05 |
| **Incogniton** | Chromium | **Windows / macOS only** ("compatible with Windows and Mac") | Local API, Selenium/Puppeteer from Entrepreneur | n/a | Yes | $79.99/mo (Professional 150) | Custom, $149.99+ (500) | `vendor-claim` incogniton.com/pricing, /download-incogniton |
| **CloakBrowser** (2026 entrant) | Source-patched Chromium ("87 C++ patches"), seed-pinned personas | **Linux x64/arm64, Docker** `cloakhq/cloakbrowser`. Wrapper is MIT; **binary is proprietary** ("can't be redistributed… running the unmodified binary inside your own infrastructure is fine") | You launch it with `--remote-debugging-port`; any CDP client | **Any flags** (you launch it) | `--proxy-server`, and the wrapper handles credentials | By **concurrency**: Team $49-79 (20 concurrent), Business $199-249 (200) | Business (200 concurrent) or Scale $499-699 (2,000) | `source-code`/`official-docs` github.com/CloakHQ/CloakBrowser README (repo created 2026-02-22, pushed 2026-10-08); `vendor-claim` cloakbrowser.dev; **`hands-on`** free v146 |

ToS on automation:
- Every vendor above sells automation (API/Selenium/Puppeteer/Playwright are listed plan features). None forbids it (`vendor-claim`, pricing pages).
- Kameleo's docs ask you **not** to change browser or network settings from Playwright, and not to add third-party stealth patches (`official-docs`).
- The binding constraint is the **platform's** ToS. See Q4.

Two things the matrix does not show:
- **Vendor kernel version.** Stagehand needs a recent `Extensions.*` CDP surface (Q2). No vendor publishes its kernel's CDP surface, and anti-detect kernels routinely trail stable Chrome. **Every candidate must pass a Stagehand attach test before it is chosen** (`hands-on` shows Chromium 146 fails).
- **Profile custody.** Cloud-synced vendors (GoLogin `stop()` "uploads it to the storage", Multilogin cloud profiles, DICloak remote auth) hold client cookies on vendor servers.

### Q2. Can Stagehand and Browser-Use, called from a Hermes profile, drive one?

**Browser-Use: yes, for any Chromium-kernel vendor that returns a CDP endpoint.**
- Browser-Use 0.13 is CDP-only (`cdp_use`; `source-code` `browser_use/browser/session.py`) and takes `BrowserSession(cdp_url=…)`.
- `hands-on`: it attached to vanilla Chromium 152 and to CloakBrowser 146, and ran `get_browser_state_summary` twice (an agent step's DOM and screenshot extraction, no LLM).
- In those tests deviceandbrowserinfo reported `isBot:false`. Its page sessions enable Page and Network, but not Runtime (`source-code` `session_manager.py`).
- Scope of that result: hands-on covers attach, navigate and state reads only.
  - `Runtime.enable` is sent by `actor/page.py` `_ensure_session` (L55-72).
  - That path is reached by non-forced coordinate clicks (`default_action_watchdog.py` L390-407 → `session.py` L2506-2528), the MCP server's coordinate click (`mcp/server.py` L793), and the actor API.
  - The Agent's default click tool forces coordinate clicks (`tools/service.py` L679), so it avoids the path (`source-code`). Re-test with real actions before relying on it.

**Stagehand 4.2.0: only conditionally.** It is not "any CDP URL". Stagehand v4's runtime is an MV3 extension, "Stagehand Runtime"
(permissions `debugger`, `scripting`, `tabs`, `<all_urls>` content script; `source-code` `dist/extension/manifest.json`).
`localBrowser.connect({cdpUrl})` works in four stages:
1. It calls `Extensions.getExtensions` to find an installed copy.
2. Otherwise it calls `Extensions.loadUnpacked` with `STAGEHAND_EXTENSION_DIRECTORY_PATH`. That is a path on the **browser's** host
   (`source-code` `dist/index.mjs` `resolveExtension` / `loadUnpackedExtension`; `official-docs` "Loading requires a shared filesystem").
3. It attaches to the extension's service worker.
4. The service worker opens **its own WebSocket to the same CDP URL** (`source-code` `dist/extension/service-worker.js` `browserWebSocketFactory`).

Measured outcomes (`hands-on`, `RESULTS.md` §2):

| Condition | Result |
|---|---|
| Extension only on the client host | `File path cannot be resolved.` |
| Extension in the browser container, but the host-mapped CDP URL does not exist inside the container | `CDP websocket failed to open` (from the extension) |
| + an in-container forwarder so the same URL resolves inside | **Works**: connect 139 ms, `Stagehand.create` 345 ms |
| Chromium 152 **without** `--enable-unsafe-extension-debugging` | **Works.** This contradicts the Stagehand docs ("required") and the CDP docs (`getExtensions` needs `--remote-debugging-pipe`). Treat the requirement as build-dependent |
| CloakBrowser Chromium 146, with or without the flag, even with the extension preloaded via `--load-extension` | **Fails**: `Extensions.getExtensions` "wasn't found", `loadUnpacked` "Method not available." |

Gotchas for Stagehand on any foreign browser:
- **CDP detection.** It trips `isAutomatedWithCDP` (the extension sends `Runtime.enable` on page sessions; `source-code` service-worker). After `close()` the extension **stays loaded** and keeps tripping the check. `Extensions.uninstall` cleared it, and so did a browser restart on the same profile, because the CDP-loaded extension is not persisted (`hands-on`, `raw/r_ext_after_restart.json`).
- **Closing.** `browser.close()` on a *connected* local handle sends `Browser.close` (`source-code` `connectBrowser`). With vendor apps, stop the profile through the **vendor API** instead, so the vendor syncs the profile (GoLogin `stop()` uploads it).
- **Extension probing.** The Stagehand extension has no `web_accessible_resources`, so LinkedIn-style `chrome-extension://` probing cannot see it. This is an inference from the manifest; content-script side effects were not measured.
- **Firefox kernels.** Neither engine supports Firefox or Juggler. The only Firefox mention in Browser-Use is a stale MCP `manifest.json` enum. Stealthfox, Junglefox and Camoufox are out.
- **Older kernels.** One option to test is Stagehand **v3** (CDP-direct, no extension). It is documented under `v3/` in the corpus; its maintenance status is unverified.

**Connection paths for the best Linux-capable options** (`official-docs` + `source-code`; vendor attach is **not hands-on**, because there are no accounts and no spend):

1. **Kameleo in Docker on the droplet** (amd64):
   - Run the container:
     ```
     docker run --shm-size=2g -p 127.0.0.1:5050:5050 -e PAT=… -v kameleo-data:/data -v /opt/stagehand-ext:/opt/stagehand-ext:ro kameleo/kameleo-app
     ```
   - Start the profile with the SDK, then use `cdp = f"ws://127.0.0.1:5050/playwright/{profile_id}"`.
   - Browser-Use: `BrowserSession(cdp_url=cdp, keep_alive=True)`.
   - Stagehand: run the client on the droplet with `STAGEHAND_EXTENSION_DIRECTORY_PATH=/opt/stagehand-ext` and `localBrowser.connect({cdpUrl: cdp})`. The container must map 5050 so that `127.0.0.1:5050` means the same thing inside and outside.
   - Unknowns:
     - whether Chroma's kernel exposes `Extensions.*`;
     - whether Kameleo's `/playwright/{id}` proxy accepts the extension's second connection.
2. **Multilogin X agent on Ubuntu** (systemd `xvfb.service` + `mlx.service`):
   - Start: `GET https://launcher.mlx.yt:45001/api/v2/profile/f/{f}/p/{p}/start?automation_type=playwright&headless_mode=false` → `port`.
   - Browser-Use: `cdp_url=f"http://127.0.0.1:{port}"`. Stagehand: `localBrowser.connect({cdpUrl:`http://127.0.0.1:${port}`})`. Same host, so the filesystem is shared.
   - Stop with the launcher stop endpoint.
   - Unknown: Mimic's `Extensions.*` support.
3. **AdsPower on Ubuntu Desktop 22.04** (run Xvfb on a server) or **Octo** in its Docker recipe. These are the most flexible for Stagehand because the start call takes flags:
   - AdsPower: `POST /api/v2/browser-profile/start {"profile_id":…, "headless":"0", "launch_args":["--enable-unsafe-extension-debugging"], "cdp_mask":"1"}` → `debug_port`.
   - Octo: `POST :58888/api/profiles/start {"uuid":…, "debug_port":true, "flags":[…]}` → `ws_endpoint`.

**Profile locking.**
- One Chromium process per user-data-dir (`SingletonLock`).
- Vendor apps also refuse to start a profile that is already running, or that is open by another team member (`unverified`; check per vendor).
- A human in the live viewer and an agent on the same CDP browser **can** act at the same time and will fight over focus and input.
- The fleet needs a **lease**: one writer per profile; a human lease preempts and parks the agent; the agent re-reads state after the lease ends.

### Q3. Open-source stealth options: what each fixes and what it does not

| Option | What it is | Fixes | Does not fix / caveats | Fit for Stagehand v4 / Browser-Use |
|---|---|---|---|---|
| **Steel OSS built-in** (`fingerprint-generator`/`-injector` 2.1.82 + Steel's obfuscated `scripts/fingerprint.js`) | Per-launch random fingerprint injected over CDP (`Emulation.setUserAgentOverride`, `evaluateOnNewDocument`) | Strips `HeadlessChrome` from the UA; hides `navigator.webdriver` (`--disable-blink-features=AutomationControlled`, no `--enable-automation`); forces WebRTC `disable_non_proxied_udp`; aligns timezone to the proxy IP via ipinfo.io | **New fingerprint on every launch, no HTTP pin.** The controller drops `fingerprint`; only the internal `startSession` accepts it. `launchMutators` run after it is read. Measured inconsistencies (Q-verdict 1). Canvas untouched. `--disable-gpu` → no WebGL when headful. Locale fixed `en-US`. Steel's own Puppeteer attaches to every page | Engine-agnostic (it is the host). `source-code` `api/src/services/cdp/cdp.service.ts` L704-800, L860-960, L1493-1560; `api/src/modules/sessions/sessions.controller.ts`; `hands-on` runs A-E |
| **fingerprint-suite** (Apify `fingerprint-generator` + `fingerprint-injector`) | Bayesian-network fingerprint generation + JS injection | Plausible marginal distributions | JS-level lies are detectable (toString, worker and iframe consistency; Castle's general method). Random unless you persist and re-inject the same object | Usable only by persisting one generated fingerprint per profile and injecting it at every wake. Workers stay unpatched |
| **patchright** | Playwright fork that avoids `Runtime.enable` and other Playwright leaks | Playwright-driver CDP leaks | Only for code that drives **Playwright**. Stagehand v4 (own CDP client + extension) and Browser-Use (`cdp_use`) do not use Playwright | **No** effect on either engine (`source-code`) |
| **rebrowser-patches** | Patches for puppeteer/playwright to avoid `Runtime.enable` | Same | Same; 2026 maintenance status unverified | **No** effect on either engine |
| **nodriver / zendriver** | Python CDP drivers that avoid WebDriver/Runtime artifacts | Driver leaks for scripts written against them | They are drivers, not agent engines | Not pluggable into Stagehand or Browser-Use. Possible for hand-written deterministic flows |
| **Camoufox** | Firefox fork with C++-level fingerprint spoofing, driven through Playwright's **Juggler** protocol | Strong fingerprint spoofing; no CDP to leak | **No CDP endpoint** | **Rules out both engines.** Both are CDP-only (`source-code`). Same for Multilogin Stealthfox, Kameleo Junglefox, AdsPower FlowerBrowser |
| **CloakBrowser** (proprietary binary, MIT wrapper) | Chromium with source-level patches, seed-pinned personas, Windows persona on Linux | `hands-on`: same seed → same canvas, GPU and CreepJS FP ID across restarts; worker = main thread; `toString` clean; hid Playwright's `isAutomatedWithCDP`; Browser-Use clean | Free build is old (146) and **Stagehand 4.2.0 cannot attach to it**; latest needs a key (free = 1 concurrent session; Pro by concurrency). Closed binary from a publisher with no stated legal entity on its site: supply-chain risk for a browser holding client sessions. Default TZ `UTC` (must pin). A seed may map to a different identity after a major-version upgrade (`vendor-claim`) | Browser-Use: yes. Stagehand: blocked on the tested build |
| **Brave** | Chromium-based browser with "farbling" | Per-site randomised canvas/audio | Farbling keys reset per session: deliberately **not** stable across restarts, which is wrong for a persistent identity. Exposes `navigator.brave` (`unverified` for 2026 builds) | Driveable by CDP; not recommended |
| **ungoogled-chromium** | Chromium without Google services | Removes Google phone-home | No fingerprint work; equivalent to vanilla Chromium | Like vanilla |
| **Vanilla Chromium, headful under Xvfb, no injection** (the "honest persona") | Stock Debian Chromium 152 | `hands-on`: no `webdriver`, 5 plugins, `toString` clean, CreepJS 0% headless / 44% like-headless / 0% stealth, raw-CDP DABI clean, Browser-Use clean | **No WebGL** without a GPU, or **SwiftShader** renderer with `--use-angle=swiftshader --enable-unsafe-swiftshader`, which is a server/VM tell. Linux persona (a small share of desktop social users). Chromium (not "Google Chrome") UA-CH brands | Both engines, with the Stagehand caveats in Q2 |

### Q4. Detection science: what the platforms check

Primary sources from the platforms on detection are thin. They publish rules, not detectors. Each claim below carries its tag.

| Signal | Evidence | For **keeping** an existing account healthy | For **mass creation** (out of scope) |
|---|---|---|---|
| New device / new location at login | Meta: alerts for logins "from a new device or a web browser that Facebook doesn't recognize" with a location tag, plus extra verification for "an unusual device" (`third-party` mobigyaan, ITPro). Instagram: "Suspicious Login Attempt" with an emailed 6-digit code on new device/location (`third-party` Cerby help, an enterprise shared-account vendor) | **Dominant.** Every change of IP geo/ASN, cookie jar or fingerprint looks like a new device in a new place → checkpoint. Hence: one sticky IP, a persistent profile, a pinned fingerprint, human logs in once | Also dominant |
| Fingerprint consistency (canvas, WebGL, workers vs main thread, toString of patched functions, UA vs engine, UA-CH vs UA) | Castle: anti-detect browsers "still leave detectable patterns"; detection by correlating values "to detect lies" (`third-party`, 2025-03-05). TikTok's web VM checks `webdriver` and canvas `toDataURL` (`third-party` Castle 2025-06-04); TikTok's `msToken` is minted by webmssdk.js from canvas/WebGL/audio fingerprints (`third-party` go-tiktok docs). LinkedIn's script collects CPU cores, memory, screen, timezone, language, battery (`third-party` BleepingComputer 2026-04, BrowserGate) | **High.** Inconsistency over time on one account matters more than being "unique". Steel's per-launch regeneration is exactly what to avoid | High |
| Extension inventory | LinkedIn probes for **6,000+ Chrome extension IDs** (`third-party` BleepingComputer, Apr 2026). LinkedIn bans "browser plugins and add-ons" that scrape or automate (`official-docs` User Agreement §8.2 and help a1341387) | Medium. Keep profiles free of known automation and sales extensions. Browser-Use's **default** extensions (uBlock Origin Lite, "I still don't care about cookies", ClearURLs) load when Browser-Use **launches** the browser (`source-code` `profile.py` L648-650, L939); disable them for identity profiles | Medium |
| CDP / automation leaks | The classic `console.debug(Error)` check was killed by V8 commits of 7 and 9 May 2025 (`third-party` Castle, 2025-08-28; `hands-on`: no fire on Chromium 152). Detectors moved to other JS signals. DABI still flags Playwright and Stagehand on stock Chromium (`hands-on`) | Unknown weight at Meta/TikTok/X/LinkedIn. Cheap to reduce: prefer Browser-Use on unpatched Chromium for the most sensitive actions (measured clean for attach and state reads; actions not yet measured), uninstall Stagehand's extension after use, or use a patched kernel | High for scrapers |
| Headless signals | `HeadlessChrome` UA, SwiftShader, 800x600 default screen, no plugins | Medium. Run headful. Steel's headless with `skipFingerprintInjection` leaks `HeadlessChrome/152` (`hands-on` run C) | High |
| IP / ASN reputation | Datacenter ASNs are routinely scored; ISP proxies are datacenter-hosted IPs announced under ISP ASNs; residential pools have provenance problems (NetNut/Popa seizure, `third-party` Krebs 2026-07) | **High**, but what matters is **stability** more than "residential-ness". Never let a client account hop IPs | High |
| WebRTC / DNS / timezone / locale mismatch | Classic consistency checks. Steel forces WebRTC `disable_non_proxied_udp` (`source-code`) and fetches the timezone through the proxy | High and cheap to get right: pin `TZ`, `--lang`, accept-language, and geolocation permission off, all from the IP's geo at profile creation | High |
| Behavioural cadence | Castle's stack: behaviour (mouse, scroll, typing), "red pills" for VMs and fake hardware, proxy and network detection, time-series analysis (`third-party`, 2025-08-28). X: "non-API-based forms of automation, such as scripting the X website… may result in the permanent suspension of your account" (`official-docs` help.x.com/articles/20174732, via search; a direct fetch returned 403) | **Dominant over time.** Volume caps, jittered schedules, session lengths like a social-media manager's, no 24/7 activity, no burst replies | Dominant |
| Account-sharing rules | LinkedIn §8.2: may not "use or attempt to use another's account (such as sharing log-in credentials or copying cookies)" (`official-docs`, eff. 2025-11-03). Meta §3.1: "Not share your password, give access to your Facebook account to others"; §3.2: no automated access or collection "without our prior permission" (`official-docs`, eff. 2025-01-01) | **The real exposure for an agency.** Use delegated roles where they exist; browser agents on personal profiles are a ToS risk no fingerprint fixes | n/a |

### Q5. Proxies

**Which type for persistent social identities.** These are judgments built on the sources above.
- **Static ISP, dedicated: the default.** One IP for months, ISP ASN, unlimited or high bandwidth.
- **Rotating residential (sticky sessions): wrong for logged-in identities.**
  - IPRoyal's maximum sticky `lifetime` is 7 days, and exits can drop earlier (`official-docs` docs.iproyal.com rotation; `third-party` Proxidize).
  - Each re-roll is a "new location" event.
  - Fine for logged-out research or enrichment browsing.
- **Mobile 4G/5G dedicated port: the exception.**
  - Highest trust (CGNAT), but expensive, and the IP changes on rotation within one carrier and region.
  - Consider it for TikTok/Instagram-first profiles if ISP IPs measure badly.
- **Shared ISP** (Oxylabs: "Shared with up to 3 users"): avoid. Someone else's behaviour lands on your client's IP.

**Prices** (`vendor-claim`, fetched 2026-10-10 unless noted):

| Provider | Static ISP, dedicated, per IP-month | Mobile | Rotating residential per GB | Notes |
|---|---|---|---|---|
| Decodo (ex-Smartproxy) | $3.33 @3, $2.9 @10, $2.7 @50, **$2.6 @100**, **$2.5 @200** | n/a | shared ISP from $1.30/GB | "100% dedicated", "unlimited bandwidth" |
| Bright Data | dedicated $3.5 @10 → $2.75 @100 → **$2.5 @1,000**; 100 GB/IP fair use | n/a | n/a | from scale-infra (shared/dedicated tab mapping inferred there); `third-party` guides give $1.5-4 |
| IPRoyal | ISP $2.70/30 d, $2.40/90 d (scale-infra) | **$130 per 30 days**, $117/mo on 90 d, "reserved for you" | n/a | sticky residential `lifetime` up to 7 days |
| Proxy-Cheap | $2.71/mo ($2.44 promo) | static mobile from $3.50 or $11.61 "per proxy" (page inconsistent); rotating mobile $5.99/GB | $0.78/GB promo | page internally inconsistent |
| Oxylabs | **shared** ISP $1.1-1.5/IP | n/a | n/a | not dedicated: avoid for identities |
| SOAX | n/a (no ISP on the page) | same per-GB as residential | $5.00 → $0.85/GB by tier (Tier 1 geo) | sticky duration not stated |
| Webshare | static residential tab did not render | n/a | n/a | datacenter only visible ($0.03/proxy) |
| Rayobyte | page fetch failed (TLS error) | n/a | n/a | not verified |
| **NetNut** | **domain seized by the FBI on 2026-07-02** (Popa botnet); netnut.io/pricing shows the seizure banner | n/a | n/a | `third-party` Krebs, Neowin; `hands-on` fetch |

For the fleet's arithmetic, scale-infra's **$3.00 / $2.75 / $2.50 per IP-month at 30 / 100 / 1,000** stands. At 1,000 profiles that is about $2,500/mo.

**Sticky-session mechanics.**
- Static ISP has no sessions: the port or IP *is* the identity.
- Rotating providers encode a session ID and lifetime in the proxy username (e.g. IPRoyal `_session-XXXXXXXX_lifetime-7d`).
- Treat any exit-IP change as an incident: before every wake, check the exit IP through the proxy with an IP echo (scale-infra already prescribes this).

**Matching timezone, locale and geo to the IP.**
- Resolve the IP's geo once, at profile creation.
- Pin these in the registry: timezone, primary language, accept-language, and geolocation permission denied, or coordinates matching the city.
- Never re-resolve at wake. Steel's per-launch ipinfo lookup can flip if ipinfo's data changes; scale-infra saw UTC/NY flips. Pass `timezone` explicitly.

**Binding a proxy per profile:**
- **OSS Steel** (`source-code` `session.service.ts` L146-230, `utils/proxy.ts`):
  - Call `POST /v1/sessions {"proxyUrl":"http://user:pass@host:port","timezone":"America/Chicago", …}`.
  - Steel starts a local **proxy-chain** forwarder and launches Chromium with `--proxy-server=http://127.0.0.1:<port>`, so credentials never reach Chromium.
  - It forces WebRTC `disable_non_proxied_udp`.
  - The `PROXY_INTERNAL_BYPASS` hosts skip the upstream proxy. Keep that list empty.
- **Browserbase**: `proxies:[{type:"external", server, username, password}]`, HTTP/HTTPS only. Set the timezone yourself (see `browserbase.md`).
- **Raw Chromium**: `--proxy-server=http://host:port` (no credentials in the flag) plus either:
  - (a) CDP `Fetch.enable({handleAuthRequests:true})` with `Fetch.authRequired` → `Fetch.continueWithAuth`, armed on every target before its first request (Browser-Use does this, `source-code` `session.py` L2049-2160); or
  - (b) **recommended**: a per-profile local forwarder (proxy-chain, gost) on `127.0.0.1`, owned by the node agent.

  Add `--webrtc-ip-handling-policy=disable_non_proxied_udp --force-webrtc-ip-handling-policy`, the process env `TZ=<zone>`, and `--lang=<locale>`.
- **Stagehand v4**: `localBrowser.launch({proxy:{server}})` adds `--proxy-server`, but **throws "Authenticated local browser proxies are not supported yet"** if a username or password is given (`source-code` `index.mjs` L4917-4920). When connecting, the proxy is whatever the browser was launched with. So use the local forwarder.
- **Browser-Use**: `BrowserProfile(proxy=ProxySettings(server=…, username=…, password=…, bypass=…))` when Browser-Use launches the browser (`source-code` `profile.py` L568-580, L942-949). With `cdp_url`, the browser's own proxy applies.

### Q6. What an older local tool's anti-detection results showed

A private results doc (path and commit withheld), test date 2026-06-05, run on a VPS.

**Actually measured (`hands-on` by them):**
- Browserbase (Hermes `browser_*`, free tier):
  - Meta Ad Library: 105 and 92 advertisers extracted, then a login wall or CAPTCHA "after 2-3 searches".
  - Instagram rate-limited after ~24 scrolls.
  - PerimeterX blocked.
  - CreepJS passed.
- Playwright + `playwright-stealth` 2.0.3 + Decodo US residential (sticky 10 min): blocked on Cloudflare, Meta Ad Library and PerimeterX. Fine on unprotected sites.
- An Apify Facebook-ads actor spent real money with zero results.

**Asserted, not measured:**
- Browser Use Cloud's "S-tier":
  - its Meta result is "Should pass… Not empirically verified due to API key constraints";
  - its confidence is "tested architecture + community reports + vendor claims".
- Airtop: vendor claims only.
- rtrvr.ai: largely untested.
- **Steel and Hyperbrowser were never put through the matrix** (the doc says so).

**Why it does not transfer to this question:**
- It tested **logged-out scraping** with **rotating** residential IPs. The fleet's problem is **logged-in, low-volume upkeep** on sticky IPs.
- Some technical claims are dated or inaccurate for 2026. Example: "navigator.webdriver = true is a dead giveaway regardless of IP". Steel and attached-CDP Chromium show `webdriver:false` (`hands-on`).
- Its "S-tier" rating should not flow into the fleet design.

### Q7. Verdict, conditions that flip it, and cost delta

**Is "pinned consistent fingerprint + persistent profile + one static ISP/residential IP + human-like cadence + headful or well-patched Chromium" enough?**

For client accounts that a human logged into once, maintained by agents at a social-media-manager cadence: **yes, it is the whole recipe.**
A commercial anti-detect browser is one way to supply the "pinned consistent fingerprint" part. It is not an extra layer of safety on top
of the recipe. The OSS ways to supply that part are listed under §1.2. The non-negotiables, whichever browser is used:
1. **Never regenerate.** Pin persona values at creation. Steel's built-in injection must be off (`skipFingerprintInjection:true` plus a fixed `userAgent`), or replaced by a pinned plugin.
2. **One dedicated static ISP IP per profile.** Timezone and locale come from that IP and are set natively.
3. **Headful, with WebGL present.** Under Steel's flags, headful has none.
4. **Cadence and volume limits** in the scheduler, not in the browser.
5. **The human logs in through the viewer, once.** Agents never type credentials.
6. **Use Browser-Use, or a patched kernel, for the most detection-sensitive surfaces** until Stagehand's CDP footprint is measured as harmless there. First re-run the test page with real Browser-Use actions (click, type, scroll); only attach and state reads are measured so far.

**When the answer flips toward buying a commercial anti-detect browser:**
- **Measured flags.** A canary cohort shows checkpoint or restriction rates on Linux/SwiftShader "honest" personas above a matched cohort using a vendor's Windows/Mac personas. This is the only evidence that should decide it.
- **Operators on desktops.** Human operators (VAs) need to open the *same* profiles on Windows/Mac. Vendor desktop apps with team sharing do this well; a droplet-only fleet does not.
- **Platform targets Linux personas.** Linux desktop is a small population; if a platform starts weighting it, Windows personas become necessary.
- **Fingerprint maintenance.** The fleet does not want to own fingerprint maintenance: tracking Chrome releases and keeping patched binaries current. A vendor (or CloakBrowser Pro) does this for a fee.
- **App-first platforms.** Mobile app–first platforms (TikTok, Instagram) may push toward cloud phones or mobile personas, which some vendors bundle (MoreLogin cloud phone $0.006/min). That is a different product.

**When it flips away (stay OSS):**
- **Stagehand cannot attach.** Stagehand is the main engine, and the vendor kernel fails the Stagehand attach test (Q2). On any vendor, Browser-Use would then be the only engine.
- **Custody.** Cookies must not leave the fleet's infrastructure, and cloud-synced vendors fail that.
- **Linux agent limits.** The vendor's Linux story is a desktop agent under Xvfb that cannot be packed densely or containerised per profile.

**Cost delta** (licence only; `vendor-claim` list prices, monthly billing; the base totals are scale-infra's self-hosted autoscaled, model mix A, 1 h/day):

| Scale (peak concurrency, scale-infra) | Base total/mo | Cheapest Linux-capable API plan | Typical | Highest (Kameleo, priced by concurrency) | Licence as % of base (EUR at ~1.1 USD) | CloakBrowser Pro (concurrency) |
|---|---|---|---|---|---|---|
| 30 profiles (4-12) | $294 | Multilogin Pro 50 **$29** | GoLogin Prof 100 $39; Octo Base €79 | Kameleo Startup €59 (10 conc.) or Business €299 | **~10-30%** (Kameleo Business: ~110%) | Team $49-79 (20 conc.) |
| 100 profiles (13-38) | $639 | AdsPower ~$36 (`third-party`); GoLogin $39; Multilogin **$40** | Octo €79; Dolphin $89 | **Kameleo Business €299** (100 conc.) | **~6-50%** | Team $49-79 if peak ≤20, else Business $199-249 |
| 1,000 profiles (125-375) | $4,724 | GoLogin Enterprise **$179**; Multilogin $185 | Dolphin $299; Octo €329 | **Kameleo Enterprise €1,499** (1,000 conc.) | **~4-35%** | Business $199-249 (200 conc.) or Scale $499-699 |

At 3 h/day the base totals rise (scale-infra: $405 / $1,007 / $8,413), so the licence share falls further.
**The dollar delta does not decide this.** It is under a third of the bill in every row except Kameleo at 30. What decides it is the integration
constraints above, plus the measured outcome of a canary cohort.

---

## 3. What the open-source projects give us vs what the fleet must build

| Need | Steel OSS gives | Stagehand v4 / Browser-Use give | Fleet must build |
|---|---|---|---|
| Same fingerprint every wake | Nothing pinnable over HTTP; random per launch, inconsistent | Nothing | Persona registry (UA, UA-CH, platform, screen/DPR, GPU strategy, fonts, TZ, locale, languages, hardwareConcurrency/deviceMemory), written at creation and never regenerated. Apply via launch flags + `TZ`, not CDP emulation. Two ways with Steel:
- a fork or plugin that calls the internal `sessionService.startSession({fingerprint})`, which accepts a fingerprint object (`source-code` session.service.ts L102, L130, L225);
- bypassing Steel's injection with `skipFingerprintInjection` + `userAgent`.

`launchMutators` cannot pin it, because `fingerprint` and `userAgent` are read *before* the mutators run (`source-code` cdp.service.ts L704-712). With a `userAgent` pin and no fingerprint object, Steel sets no UA-CH override. Pin the UA to the engine's real major version, or `navigator.userAgentData` will contradict it. Drift alarm: re-hash the probe values each wake |
| WebGL on GPU-less droplets | `--disable-gpu` → none (headful) | — | Decide per persona: SwiftShader (honest, server-like), or a patched kernel with a spoofed GPU. Never "no WebGL" |
| Headful under Xvfb | Stock image cannot launch headful (scale-infra) | — | Custom entrypoint: Xvfb + dbus per browser; window size equals the persona screen |
| One IP per profile | `proxyUrl` per session + proxy-chain forwarder | Stagehand: no authenticated proxies; Browser-Use: `Fetch.authRequired` | Proxy inventory and assignment (1 dedicated ISP IP ↔ 1 profile), credential vault, per-profile local forwarder in the node agent, IP-echo check before each wake, IP-drift incident handling, provider-provenance vetting |
| TZ, locale and geo consistent with the IP | ipinfo lookup per launch (can flip); `timezone` param; locale fixed `en-US` | Stagehand `locale` → `--lang` | Resolve once at creation, pin, pass explicitly every wake |
| Stagehand on a foreign or remote browser | — | Needs the extension on the browser's filesystem, the CDP URL valid inside the browser, and a kernel with `Extensions.*` | Bake the Stagehand extension into every browser image at a fixed path, set `STAGEHAND_EXTENSION_DIRECTORY_PATH`, keep CDP URLs identical inside and outside (same port mapping, or run the client on the browser host); **uninstall the extension after each Stagehand session**; Stagehand-attach conformance test per kernel |
| Anti-detect vendor adapter (if bought) | — | Browser-Use `cdp_url`; Stagehand conditionally | Vendor adapter: start/stop through the vendor API (so it syncs), map vendor profile ↔ fleet profile, translate proxy and persona settings, respect API rate limits (Multilogin 100 RPM; Octo 50-200 RPM; AdsPower 2-5 req/s) |
| Human login and exclusive access | Live viewer (Steel) | — | Lease service: human lease preempts the agent; one writer per profile |
| Behaviour and cadence | — | — | Scheduler-level caps per platform and action type, jitter, active-hours windows in the persona's timezone, cool-downs after any challenge |
| Detection telemetry | — | — | Canary pages (DABI, CreepJS) on wake for drift; checkpoint/challenge detectors on platform pages that pause the profile and page a human; per-profile health scores |
| Engine extension hygiene | — | Browser-Use loads uBlock/cookie/ClearURLs extensions when it launches | `enable_default_extensions=False` for identity profiles; never install sales or automation extensions in client profiles (LinkedIn probes for them) |

---

## 4. Operating notes for a Hermes agent

These feed the skills later.

**Wake sequence (per profile):**
1. Acquire the profile lease. Abort if a human holds it.
2. The node agent starts that profile's local forwarder to its dedicated ISP IP, then runs an IP-echo through it. It must equal the pinned IP. Abort on mismatch.
3. Launch headful Chromium (or call the vendor start API) with:
   - the profile dir;
   - pinned `TZ`, `--lang`, window size;
   - `--proxy-server=http://127.0.0.1:<fwd>`;
   - the WebRTC policy flags;
   - the persona's GPU strategy.
4. Optional drift probe on a neutral page: UA, UA-CH, TZ, screen, WebGL renderer, canvas hash. Compare with the registry. Alert on any change.
5. Hand the CDP URL to the engine.

Two forms for the engine call:

```python
# Browser-Use (any Chromium CDP endpoint, incl. vendor kernels)
session = BrowserSession(cdp_url=cdp_url, keep_alive=True)   # do not let BU launch identity browsers
```

```ts
// Stagehand v4 on a fleet-launched or vendor browser
// env: STAGEHAND_EXTENSION_DIRECTORY_PATH=<path on the BROWSER host>
const browser = await localBrowser.connect({ cdpUrl });       // cdpUrl must resolve identically inside the browser host
const stagehand = await Stagehand.create({ browser });
// ... work ...
await stagehand.close();
// then: CDP Extensions.uninstall({id}) for "Stagehand Runtime" (find it with Extensions.getExtensions), or restart the browser
// do NOT call browser.close() on vendor browsers: stop via the vendor API so the profile is synced
```

**Gotchas:**
- Stagehand error `File path cannot be resolved.` means the extension path is not on the browser host.
- `CDP websocket failed to open` means the extension cannot reach the CDP URL from inside the browser.
- `Method not available.` means the kernel lacks the `Extensions.*` domain. Fall back to Browser-Use for that profile.
- The Stagehand extension stays resident after `close()` and makes every new tab look CDP-automated, so clean up.
- Never let an engine change network or fingerprint settings mid-session. Kameleo's docs say this explicitly, and it applies everywhere: no `setUserAgent`, no `Emulation.*` overrides from the agent.
- Prefer native settings (`TZ` env, `--lang`) over CDP emulation. Emulation is per-target and does not reach every worker.
- Steel sessions for identities: `{"persist":true, "userDataDir":"<profile>", "headless":false, "skipFingerprintInjection":true, "userAgent":"<pinned>", "timezone":"<pinned>", "dimensions":{…pinned…}, "proxyUrl":"http://127.0.0.1:<fwd>"}`. The `userAgent` parameter also disables Steel's generator (`source-code` cdp.service.ts L724-729). Pin it to the engine's real major version (e.g. `Chrome/152.0.0.0`), because Steel then sets no UA-CH override. Steel's proxy forwarder makes the `proxyUrl` credentials safe, but in the fleet the node agent's forwarder owns them anyway. Note that Steel OSS runs one session per instance.
- Browser-Use launching its own browser loads ad-block and cookie extensions by default. Set `BROWSER_USE_DISABLE_EXTENSIONS=1` or `enable_default_extensions=False`.

**On challenge or checkpoint:** stop actions, keep the browser open, raise a human lease request with the live-viewer URL, and never retry
the login automatically. A challenge on a client account is a human task.

**Rate and cadence defaults:**
- Set them per platform in the scheduler (not measured here; the social-platforms dossier owns the numbers).
- Run actions only inside the persona's local active hours.
- Profile sessions should be short and spaced.

**Limits:**
- Vendor API rate limits (above).
- Kameleo prices by concurrency, so wake waves must respect it.
- The CloakBrowser free build allows 1 concurrent session.
- DICloak's agent handles 100 browsers per container.

---

## 5. Risks and unknowns

1. **Platform ToS (highest).**
   - X prohibits scripting its website.
   - LinkedIn prohibits bots, automation extensions, and using another's account via shared credentials or **copied cookies**.
   - Meta prohibits automated access "without our prior permission" and password sharing.

   Agency management through browser agents on personal profiles carries suspension risk regardless of fingerprint quality.
   Mitigation: delegated roles plus official APIs first, browser second, and written client consent.
2. **No platform measurement.** Every stealth result here comes from public test pages. A clean deviceandbrowserinfo or CreepJS result is not a Meta/TikTok/X/LinkedIn result. The verdict must be confirmed by a small, consenting canary cohort with health telemetry before scaling.
3. **Stagehand v4 on vendor kernels is unverified for every vendor.** It fails on CloakBrowser 146 (`hands-on`). Docs and measurements disagree on whether `--enable-unsafe-extension-debugging` is required, so it is build-dependent.
4. **Stagehand's CDP footprint** (`isAutomatedWithCDP`, resident extension). Whether the platforms weight it is unknown. If they do, Stagehand needs a patched kernel or must hand sensitive actions to Browser-Use.
5. **Proxy provenance and legal exposure.** The NetNut/Popa seizure shows that residential and resold pools can be botnet-sourced. ISP pools also have provenance questions (scale-infra §risks). Vet providers, prefer ISP-leased dedicated ranges, and keep the contract terms.
6. **Supply chain.** CloakBrowser and every commercial kernel are closed binaries holding client sessions. CloakBrowser's site names no legal entity. Only checksums were verified in this spike, not the `.sig` signature.
7. **Vendor-cloud custody.** Cloud-synced profiles put client cookies on vendor servers.
8. **Fingerprint upgrades.** Chromium major upgrades change the engine version, and with it the UA and UA-CH. A pinned UA that lags the engine becomes its own inconsistency (Steel's 142-on-152 problem).
   - Plan engine upgrades as **controlled persona migrations**: bump the UA together with the engine.
   - CloakBrowser warns that its seed→persona mapping can change across majors.
9. **Honest-persona tells.** SwiftShader WebGL and Linux UA-CH on a GPU-less droplet are "server-like". Their weight at the platforms is unknown, and it is the key uncertainty behind the buy/build decision.
10. **Pricing volatility.** Vendor prices are list or promo prices, some from third parties (AdsPower), some hidden (DICloak, MoreLogin). Kameleo charges per concurrent browser, not per profile.
11. **Test-host artifacts.** The tests ran on arm64 Docker: `uad.architecture:"arm"` and Mesa/ANGLE strings differ from x86 droplets. Re-run the probes on a droplet before pinning persona values.

---

## 6. Sources

Local files (pinned):
- Steel OSS `steel-browser@1131a0222a27f391bf8f27cca6f278ddf7ace8dd`:
  - `api/src/services/cdp/cdp.service.ts` (L150-165, L379-402, L704-800 fingerprint generation, L860-960 launch args incl. `--disable-gpu`, WebRTC policy, `--proxy-server`, L1493-1560 injection);
  - `api/src/modules/sessions/sessions.controller.ts` L8-60 (no `fingerprint` field);
  - `api/src/modules/sessions/sessions.schema.ts`;
  - `api/src/services/session.service.ts` L95-235;
  - `api/src/utils/proxy.ts` L16-50 (proxy-chain forwarder);
  - `api/src/services/timezone-fetcher.service.ts` (ipinfo.io);
  - `api/src/scripts/index.ts`;
  - `api/src/scripts/fingerprint.js` (obfuscated; decoded copy `spikes/antidetect-proxies/fingerprint.decoded.js` L506);
  - `api/package.json` (`fingerprint-generator`/`-injector` 2.1.82, `proxy-chain`).
- Stagehand `@browserbasehq/stagehand@4.2.0` `dist/index.mjs`:
  - `localBrowser.connect` L5205-5260;
  - `CDPClient.connect` L3572-3620;
  - `resolveExtension` / `loadUnpackedExtension` L3775-3846;
  - `connectBrowser` L5347-5400;
  - proxy auth rejection L4917-4920;
  - `DEFAULT_CHROME_FLAGS` L4777-4803.
- Stagehand extension: `dist/extension/manifest.json`, `dist/extension/service-worker.js`.
- Stagehand docs (monorepo `1fc8849`): `packages/docs/v4/configuration/browser.mdx` (corpus `https://docs.stagehand.dev/v4/configuration/browser.md` L567-619, L813-848).
- Browser-Use `c75e8476e26d18b7617643bc2ae082fae8eae431`:
  - `browser_use/browser/session.py` (L15-23 cdp_use, L206 `cdp_url`, L2049-2160 `Fetch.authRequired`);
  - `browser_use/browser/session_manager.py` (L485, L891-899: Page/Network enable, no Runtime);
  - `browser_use/actor/page.py` L55-72;
  - `browser_use/browser/profile.py` (L568-580 ProxySettings, L648-650 default extensions, L939-949);
  - `browser_use/mcp/manifest.json` L211-216 (stale engine enum).
- An older local tool's anti-detection results doc (private; path and commit withheld).
- Sibling dossiers: `fleet/research/dossiers/browserbase.md`, `fleet/research/dossiers/scale-infra.md` (2026-10-09/10).
- Spike: `fleet/research/spikes/antidetect-proxies/RESULTS.md` and `raw/*.json` (2026-10-10 02:52-08:00 UTC).

Web (fetched 2026-10-09/10):
- Multilogin:
  - https://multilogin.com/help/en_US/how-to-use-headless-mode (updated 2026-08-27)
  - https://multiloginx.helpjuice.com/en_US/getting-started-with-multilogin-x-automation/linux-agent-autolaunch (2026-08-14)
  - https://multiloginx.helpjuice.com/en_US/puppeteer-selenium-and-playwright/playwright-automation-example (2026-03-05)
  - https://multilogin.com/pricing/
- GoLogin:
  - https://gologin.com/pricing
  - https://cdn.jsdelivr.net/npm/gologin@latest/README.md
  - https://pypi.org/project/gologin/ (2026.6.24)
  - https://gologin.com/docs/api-reference/cloud-browser/getting-started.md (via search)
- AdsPower:
  - https://localapi-doc-en.adspower.com/docs/Rdw7Iu
  - https://localapi-doc-en.adspower.com/docs/Open-Browser-V2
  - https://www.adspower.com/download
  - https://www.adspower.com/pricing (no prices rendered)
  - https://afftank.com/blog/adspower-pricing, https://affninja.com/adspower-pricing/ (`third-party`)
- Kameleo:
  - https://kameleo.io/pricing
  - https://developer.kameleo.io/integrations/docker/
  - https://developer.kameleo.io/integrations/playwright/
  - https://kameleo.featurebase.app/changelog/kameleos-linux-docker-image-is-live-penguin (2026-04-24)
- Octo:
  - https://octobrowser.net/pricing/
  - https://blog.octobrowser.net/automating-octo-browser-using-api
- Others:
  - https://dolphin-anty.com/pricing/
  - https://www.morelogin.com/pricing/
  - https://www.nstbrowser.io/en/pricing
  - https://www.nstbrowser.io/en/blog/headlesschrome-in-docker (2024-09-18)
  - https://dicloak.com/pricing, https://dicloak.com/develop/docker
  - https://undetectable.io/pricing
  - https://incogniton.com/pricing/, https://incogniton.com/download-incogniton/
- CloakBrowser:
  - https://github.com/CloakHQ/CloakBrowser (README; release `chromium-v146.0.7680.177.4`, 2026-04-28)
  - https://cloakbrowser.dev
- Castle (`third-party`):
  - https://blog.castle.io/why-a-classic-cdp-bot-detection-signal-suddenly-stopped-working-and-nobody-noticed/ (2025-08-28)
  - https://blog.castle.io/anti-detect-browser-analysis-how-to-detect-the-undetectable-browser/ (2025-03-05)
  - https://blog.castle.io/what-tiktoks-virtual-machine-tells-us-about-modern-bot-defenses/ (2025-06-04)
  - https://blog.castle.io/how-to-detect-scripts-injected-via-cdp-in-chrome-2/
- Platform terms:
  - https://www.linkedin.com/legal/user-agreement (eff. 2025-11-03)
  - https://www.linkedin.com/help/linkedin/answer/a1341387
  - https://www.facebook.com/terms.php (eff. 2025-01-01)
  - https://help.x.com/articles/20174732 (X automation rules; quoted via search, direct fetch 403)
- Detection reporting:
  - https://www.bleepingcomputer.com/news/security/linkedin-secretly-scans-for-6-000-plus-chrome-extensions-collects-data/ (2026-04)
  - https://help.cerby.com/tips-and-troubleshooting/troubleshooting/instagram/suspicious-login-attempt (`third-party`)
  - https://www.mobigyaan.com/how-to-get-unrecognized-login-alerts-on-facebook-guide (`third-party`)
  - https://pkg.go.dev/github.com/go-tiktok/tiktok (`third-party`)
- Proxies:
  - https://decodo.com/proxies/isp-proxies/pricing
  - https://oxylabs.io/pricing/isp-proxies
  - https://iproyal.com/pricing/mobile-proxies/
  - https://docs.iproyal.com/proxies/residential/proxy/rotation
  - https://www.proxy-cheap.com/pricing
  - https://soax.com/pricing
  - https://www.webshare.io/pricing (static tab not rendered)
  - https://netnut.io/pricing/ (FBI seizure banner)
  - https://krebsonsecurity.com/?o=10593, https://www.neowin.net/amp/fbi-seizes-netnut-domain-with-googles-help-after-links-found-to-popa-botnet/ (2026-07)
  - scale-infra's Bright Data and IPRoyal ISP figures
- Test pages:
  - https://deviceandbrowserinfo.com/are_you_a_bot
  - https://abrahamjuliot.github.io/creepjs/
  - https://bot.sannysoft.com/
