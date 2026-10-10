# Spike results: antidetect-proxies

Agent: antidetect-proxies (rerun). Host: macOS arm64 (Docker, linux/arm64 containers).
Spend: **$0** (no LLM calls, no paid proxy, no paid browser, no vendor accounts).
Pages touched: `example.com`, `deviceandbrowserinfo.com/are_you_a_bot` (DABI), `abrahamjuliot.github.io/creepjs`,
`bot.sannysoft.com`, `data:` URLs. No logins, no social sites.
Containers: one at a time, named `fleet-spike-antidetect`, `127.0.0.1:3303`, `--memory 2g --cpus 1.5`. **Removed** at the end
(`docker ps -a | grep fleet-spike-antidetect` returns nothing). Other `fleet-spike-*` containers belong to other agents and were not touched.

Two sessions:
- **First attempt** (interrupted), 2026-10-10 02:52-03:19 UTC: Steel runs A-E (`probe.mjs`) and CloakBrowser runs cloak1-3 (`fpprobe.mjs`).
  The Steel container launch command was not saved. Headful worked in run E, while the scale-infra agent got HTTP 500 for
  `headless:false` on the stock image. The first attempt probably started Xvfb itself (unverified).
- **Rerun**, 2026-10-10 07:28-08:00 UTC: vanilla Chromium tests (`v_*`, `n_*`, `r_*`) and CloakBrowser driver tests (`c_*`).

Raw outputs are in `raw/`. Scripts are in this folder (paths inside scripts point at the scratch tree, `<scratch>/npm`, `<scratch>/py/.venv`).

## Engines under test

| Label | Browser | How launched |
|---|---|---|
| Steel A-E | Chromium 152.0.7977.82 inside `ghcr.io/steel-dev/steel-browser-api:latest` (image pulled 2026-09-16), Steel's own launch + fingerprint injection | `POST /v1/sessions` with the body shown per run |
| vanilla (`v_`) | Same image's Debian Chromium 152.0.7977.82, **headful under Xvfb**, `--enable-unsafe-extension-debugging` | `vanilla_up.sh` |
| vanilla no-ext (`n_`) | Same, **without** `--enable-unsafe-extension-debugging` | `vanilla_noext_up.sh`, `vanilla_args_up.sh` |
| CloakBrowser (`c_`, `cloak*`) | CloakBrowser free binary `chromium-v146.0.7680.177.4`, linux-arm64 (SHA256 matched the release's SHA256SUMS; the `.sig` was not verified), headful under Xvfb, `--fingerprint=<seed> --fingerprint-platform=windows` | `cloak_up.sh <seed> [extra args]` |

Drivers: `playwright-core` (scratch npm), `@browserbasehq/stagehand@4.2.0` (`localBrowser.connect` + `Stagehand.create`, no LLM call),
`browser-use==0.13.11` (`BrowserSession(cdp_url=...)`, no LLM call), and a raw CDP client that never sends `Runtime.enable`
(`rawctrl.mjs`: `Target.createTarget` + `Target.attachToTarget` + `Runtime.evaluate` only).

## 1. DABI verdict by browser x driver (the CDP-leak question)

DABI = deviceandbrowserinfo.com/are_you_a_bot, read 20-35 s after load. The flags are the page's own `details` keys.

| Browser | Driver | isBot | Flags | File |
|---|---|---|---|---|
| vanilla headful 152 | raw CDP (no Runtime.enable) | **false** | none | `v_rawctrl.json`, `n_rawctrl.json` |
| vanilla headful 152 | Playwright `connectOverCDP` | **true** | isAutomatedWithCDP, isAutomatedWithCDPInWebWorker | `v_pw.json` |
| vanilla headful 152 | Browser-Use 0.13.11, navigate + wait | false | none | `v_bu.json` (first try at 15 s read the page before the verdict rendered; 35 s run is the one recorded), `n_bu.json` |
| vanilla headful 152 | Browser-Use + `get_browser_state_summary` x2 (an agent step's DOM/screenshot work, no LLM) | **false** | none | `n_bu_state.json` (fresh browser) |
| vanilla headful 152 | same, but the Stagehand extension was still resident from an earlier Stagehand attach | true | isAutomatedWithCDP | `v_bu_state.json`. This is a **confounded run**: see the next rows |
| vanilla headful 152 | Stagehand 4.2.0 attach, `page.goto`, wait 30 s | **true** | isAutomatedWithCDP | `v_sh_dabi.json` |
| vanilla headful 152 | raw CDP **after** Stagehand attached and `close()`d | **true** | isAutomatedWithCDP | `n_rawctrl_after_sh.json` |
| vanilla headful 152 | raw CDP after `Extensions.uninstall` of "Stagehand Runtime" | false | none | `n_rawctrl_after_uninstall.json` |
| Steel default headless (fingerprint injected) | Playwright | true | isAutomatedWithCDP, hasInconsistentWorkerValues | `runD.json` |
| Steel headful (fingerprint injected) | Playwright | true | isAutomatedWithCDP, hasInconsistentWorkerValues, hasInconsistentTimingResolution | `runE.json` |
| CloakBrowser 146 | raw CDP | false | none | `c_rawctrl.json` |
| CloakBrowser 146 | Playwright `connectOverCDP` | **false** | none | `c_pw.json` |
| CloakBrowser 146 | Browser-Use + state summary x2 | false | none | `c_bu_state.json` |
| CloakBrowser 146 | Stagehand 4.2.0 | **cannot attach** | `Method not available.` | `c_sh_dabi.json`, `c_sh_dabi_flag.json`, `c_sh_preload.json` |

Reading:
- The classic console-`Error.stack` CDP check did **not** fire on Chromium 152, even with Playwright attached (`rawLeak` and
  `leakWithPlaywright` in runs A-E are empty). Castle reported this V8 change in Aug 2025. DABI still flags CDP automation through other signals.
- On stock Chromium, the flag tracks the **driver**: Playwright and Stagehand trip it, and Browser-Use 0.13.11 (which does not
  send `Runtime.enable` on its page sessions; see `browser_use/browser/session_manager.py`) did not trip it in these tests.
- **Stagehand v4 leaves a resident leak.** Its "Stagehand Runtime" MV3 extension stays loaded after `stagehand.close()`. New tabs
  are then flagged even when only a raw client is attached. Uninstalling the extension clears it.
- A source-patched build (CloakBrowser) hid Playwright's CDP signal. Browser-Use was clean there too.

## 2. Can Stagehand 4.2.0 attach to a browser it did not launch?

| Condition | Result | File |
|---|---|---|
| Browser in a container, extension path only on the client host | `File path cannot be resolved.` (`Extensions.loadUnpacked` runs on the browser's filesystem) | `v_sh_noshared.json` |
| Extension copied into the container + `STAGEHAND_EXTENSION_DIRECTORY_PATH=/tmp/sh-ext`, CDP URL `http://127.0.0.1:3303` (host-mapped) | `CDP websocket failed to open`: the extension's service worker dials the **same CDP URL from inside the browser**, where `127.0.0.1:3303` did not exist | (console, run before the `fwd3303.js` mirror) |
| + in-container forwarder so `127.0.0.1:3303` also resolves inside the container (`fwd3303.js`) | **works**: connect 139 ms, create 345 ms, `example.com` title read | `v_sh_dabi.json` |
| Same, Chromium 152 **without** `--enable-unsafe-extension-debugging` | **works** (connect 1.86 s). The Stagehand docs say the flag is required, and the CDP docs say `Extensions.getExtensions` needs `--remote-debugging-pipe` too. Debian Chromium 152 served both over WebSocket without either | `n_sh_noflag.json` |
| CloakBrowser Chromium 146, no flag | `Method not available.` (`Extensions.getExtensions` "wasn't found", `Extensions.loadUnpacked` "Method not available.") | `c_sh_dabi.json` |
| CloakBrowser 146 + `--enable-unsafe-extension-debugging` | same failure | `c_sh_dabi_flag.json` |
| CloakBrowser 146 + flag + extension preloaded with `--load-extension` (service worker visible in `/json/list`) | same failure: Stagehand cannot *discover* a preinstalled extension without `Extensions.getExtensions` | `c_sh_preload.json` |

## 2b. Does the Stagehand extension persist in the profile across a browser restart? (07:57-08:00 UTC)

These are hands-on checks on vanilla Chromium 152 with no extension flag. Steps:
1. Run `sh_connect.mjs` once. It attached and the extension loaded (`r_sh_before_restart.json`).
2. Kill Chromium.
3. Relaunch it with the **same** `--user-data-dir=/tmp/vanilla`. The profile's `History` file survived from before the restart.

| Check after restart | Result | File |
|---|---|---|
| `Extensions.getExtensions` | `{"extensions":[]}` | `r_ext_after_restart.json` |
| `chrome-extension://<stagehand id>` targets in `/json/list` | 0 | console |
| Extension ID in `Default/Preferences` and `Default/Secure Preferences` | 0 matches each | console |
| DABI via raw CDP | `isBot:false`, no flags | `r_rawctrl_after_restart.json` |

Conclusion: an extension loaded through CDP `Extensions.loadUnpacked` is **session-only** on this build. It is not written into the
profile, so a browser restart clears the resident leak, as `Extensions.uninstall` does.

## 2c. Which Browser-Use code paths send `Runtime.enable` (source-code, browser-use `c75e847`)

- `actor/page.py` L55-72 (`Page._ensure_session`) sends `Runtime.enable`. That function is reached through `BrowserSession.get_current_page()`.
  Callers:
  - `get_dom_element_at_coordinates` (`browser/session.py` L2506-2528), used by `on_ClickCoordinateEvent` only when `force` is false
    (`browser/watchdogs/default_action_watchdog.py` L390-407);
  - the user-facing actor API.
- The Agent's default `click` tool dispatches coordinate clicks with `force=True` (`tools/service.py` L679), which skips that path.
- The **MCP server's** coordinate click dispatches without `force` (`mcp/server.py` L793), and **would** send `Runtime.enable`.
- Hands-on coverage is only attach + navigate + `get_browser_state_summary`. Clicks, typing and scrolling were **not** run against DABI.

## 3. Fingerprint measurements (`fpprobe.mjs` / `probe.mjs`, example.com)

| Run | UA (navigator) | Engine | screen vs window | Main WebGL renderer | Worker WebGL renderer | toString native? | TZ | CreepJS headless / like-headless / stealth |
|---|---|---|---|---|---|---|---|---|
| Steel A (persist, profA) | Chrome/142 Linux | 152 | 800x600 vs 1920x1080 | SwiftShader | NVIDIA GTX 1070 **D3D11** | no (6/6 patched fns leak) | America/New_York | n/a |
| Steel B (persist, profB) | Chrome/144 Linux | 152 | 800x600 vs 1860x1048 | AMD Radeon Vega 8 | NVIDIA GTX 1070 D3D11 | no | America/New_York | n/a |
| Steel C (`skipFingerprintInjection`, headless) | **HeadlessChrome/152** | 152 | 800x600 | SwiftShader | SwiftShader | yes | America/New_York | 67% / 69% / 0% |
| Steel D (default headless) | Chrome/143 Linux | 152 | 800x600 vs 1920x1080 | AMD Radeon Vega 3 | NVIDIA GTX 1070 D3D11 | no | America/New_York | 33% / 75% / 20% |
| Steel E (default headful) | Chrome/144 Linux | 152 | 1920x1080 | **no WebGL context** | no WebGL | no | America/New_York | 0% / 69% / 0% |
| vanilla headful, no injection | Chrome/152 Linux | 152 | 1920x1080 | **no WebGL context** | no WebGL | yes | UTC | 0% / 44% / 0% |
| vanilla headful + `--use-angle=swiftshader --enable-unsafe-swiftshader`, `TZ=America/Chicago` | Chrome/152 Linux | 152 | 1920x1080 | **SwiftShader** | SwiftShader | yes | America/Chicago (native, via env) | n/a |
| CloakBrowser seed 48151, run 1 | Chrome/146 **Windows** | 146 | 1920x1080 | NVIDIA RTX 4070 Ti D3D11 | same | yes | UTC | 0% / 25% / 0% |
| CloakBrowser seed 48151, run 2 (restart, same profile) | identical | 146 | identical | identical | identical | yes | UTC | identical (FP ID 8f814486976f22a5 both runs) |
| CloakBrowser seed 77777 | Chrome/146 Windows | 146 | 1920x1080 | NVIDIA RTX 3060 Ti D3D11 | same | yes | UTC | FP ID f626bf75f0debf3b |

Notes:
- Steel's worker renderer string is hardcoded in its obfuscated `api/src/scripts/fingerprint.js`
  (`ANGLE (NVIDIA, NVIDIA GeForce GTX 1070 Direct3D11 vs_5_0 ps_5_0, D3D11)`, decoded by `deobf.js` without executing the patches,
  `fingerprint.decoded.js` line 506). It is a Windows renderer inside a Linux persona, and it differs from the main thread.
- Steel's canvas hash was identical across A-E (126949219). Its "fingerprint" does not touch canvas.
- Steel regenerates a different fingerprint at every launch (A vs B vs D vs E: UA 142/144/143/144, GPU, hardwareConcurrency 32/16/7/5).
- `uad.architecture: "arm"` in the vanilla and CloakBrowser rows is an artifact of the arm64 test host. It is not a property of the x86 builds a droplet would run.
- CloakBrowser defaults to `UTC` unless a timezone is passed, so the timezone must be pinned per profile.
- `bot.sannysoft.com` (runs C-E): `Plugins is of type PluginArray: failed`, plugins length 0 under Steel.

## Commands (reproduce)

```sh
cd fleet/research/spikes/antidetect-proxies     # scripts expect the scratch tree's npm/ and py/.venv
sh vanilla_up.sh                                  # or vanilla_noext_up.sh / vanilla_args_up.sh "<args>" <TZ>
node rawctrl.mjs 3303
node pw_attach.mjs http://127.0.0.1:3303
python bu_attach.py http://127.0.0.1:3303         # with the browser-use venv active
python bu_attach_state.py http://127.0.0.1:3303
docker cp <stagehand>/dist/extension fleet-spike-antidetect:/tmp/sh-ext
docker cp fwd3303.js fleet-spike-antidetect:/tmp/ && docker exec -d fleet-spike-antidetect node /tmp/fwd3303.js
STAGEHAND_EXTENSION_DIRECTORY_PATH=/tmp/sh-ext node sh_connect.mjs http://127.0.0.1:3303 --dabi
node fpprobe.mjs http://127.0.0.1:3303 <label> --creep
# CloakBrowser: gh release download chromium-v146.0.7680.177.4 -R CloakHQ/CloakBrowser -p cloakbrowser-linux-arm64.tar.gz
#   into dl-cloak/, then: docker rm -f fleet-spike-antidetect; sh cloak_up.sh 48151 [--enable-unsafe-extension-debugging ...]
docker rm -f fleet-spike-antidetect
```

## Limits of these measurements

- They use public test pages, not Meta, TikTok, X or LinkedIn. A clean DABI or CreepJS result does **not** show that a platform accepts the session.
- The host is arm64 Docker. Droplets are x86_64, so GPU and WebGL strings differ there. The absence of a GPU is the same.
- No proxy was used, so network-level signals (IP/ASN, TLS through a proxy, WebRTC through a proxy) were not measured.
- The CloakBrowser build tested is the old free v146. The vendor says newer Pro builds differ, and that a seed may map to a different identity across major versions.
