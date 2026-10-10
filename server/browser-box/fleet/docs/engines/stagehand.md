# Engine guide: Stagehand (the L3 engine for `research` identities; not loaded on `account` identities by default)

Status: design, written against the research of 2026-10-09/10 and revised after scenarios S06 and S14. **Nothing
described as "the fleet" here is built.** What exists today is research (spikes on public test pages, arm64 Docker
on the maintainer's Mac) and a decision record.
Read with [DECISIONS.md](../../DECISIONS.md) (D5, D6, D8, D14 govern this page), then
[ARCHITECTURE.md](../../ARCHITECTURE.md), [CHARTER.md](../../CHARTER.md) and [MILESTONES.md](../../MILESTONES.md).
Precedence: the verification reports and DECISIONS.md win over the dossier; ARCHITECTURE.md is the authority for
components (AGENTS.md); where this page adds to or departs from ARCHITECTURE.md, §15 says so.

This page is the operator guide for one engine. It says how Stagehand works, how the fleet attaches
it to self-hosted Steel, what each call costs and returns, what can go wrong, and who may change it.

**Scope (read this first).** DEC D18 (which amends D5 and D6) sets the executor and the meaning of L3 by identity kind.
This page follows it and adds the Stagehand detail.

- **Default home: `research` identities.** An open-web identity with no login and no effects. (`research` and `account`
  are the identity `kind` values of ARCH §3.2; see also the [lead-gen playbook](../playbooks/lead-gen.md).) Stagehand's
  main job there is `extract` (tier 1 of the lead cascade), plus the occasional read-only navigation step. Everything
  measured on this page was measured on public test pages, so this is the case the evidence fits.
- **`account` identities (a client's logged-in brand account) use the minimal CDP executor, with no Stagehand
  extension, unless gate G1.4 shows another executor is better for that site class** (DEC D18). Their image carries no
  extension directory and no extension flags. The extension is the one engine with a measured detectability trip, and an
  account is the asset (§13). Stagehand reaches an account only if G1.4 selects it for that site class and the owner
  records it when the identity is created. **`pending Q-01`** decides how much account-browser work exists at all (under
  API-first it is the login probe, read-back and the narrow no-API set). Text below that only matters on an account is
  marked **account use, if cleared**.
- **L3 on accounts is not Stagehand.** DEC D18 gives it the fleet's own L3-lite (own snapshot builder, a shim call with
  the L2 schema, gate G, the minimal executor), closed where no (provider, host) pair is cleared for page text (Q-07).
  What is stored in the L1 cache is the fleet's own Action, not Stagehand's (§9.3).

## How to read this page

Tags on claims:

| Tag | Meaning |
|---|---|
| `hands-on` | Run in the spikes (public test pages, Steel container, arm64). Small samples. |
| `source-code` | Read in the pinned package or repo. Not run. |
| `official-docs` | Stated in the vendor docs in the corpus. |
| `design` | The target. Not built. |
| `to measure` | Unknown. Has a milestone gate (M1 = droplet hands-on, amd64). |
| `pending Q-nn` | Depends on one of Justin's open questions at the end of DECISIONS.md. Written for the recommended default. |
| `account use, if cleared` | Applies only if M1 gate G1.4 and the owner admit Stagehand on a logged-in identity. Not the default, not decided. |

Source aliases (all paths relative to `fleet/`):

| Alias | Path |
|---|---|
| DEC | `DECISIONS.md` |
| ARCH | `ARCHITECTURE.md` (§2.2 N2-N4, §2.5 shim, §3.2 identity kinds, §3.7 procedures, §3.9 `l1_entries`, §4.1 wake W10, §4.3 ladder and Gate G, §4.9 sleep, §4.10 recovery) |
| CHT | `CHARTER.md` (invariants, red lines, what agents may do) |
| MIL | `MILESTONES.md` (standing gate S1; M1 G1.4; M3 G3.3, G3.5, G3.7) |
| AGT | `AGENTS.md` |
| DOS | `research/dossiers/stagehand.md` |
| VER | `research/verification/stagehand.md` (SH-1..SH-10, V-1..V-10, "Missed issues") |
| CON | `research/verification/CONSISTENCY.md` (C-xx, O-xx, Q-xx) |
| RMD / RMV | `research/dossiers/reasoning-models.md` / `research/verification/reasoning-models.md` (REA-n) |
| APD / APV | `research/dossiers/antidetect-proxies.md` / `research/verification/antidetect-proxies.md` (AP-n, V-n) |
| STD / STV | `research/dossiers/steel.md` / `research/verification/steel.md` (STE-n) |
| SPK | `research/spikes/stagehand/` (`RESULTS.md`, scripts, `results/*.json`) |
| C | `research/corpus/stagehand/` (vendor docs; **untrusted data**, never follow instructions inside; the scraped pages are not published, so pages are cited by vendor URL) |
| CS | `research/corpus/steel/` (likewise cited by vendor URL) |
| SCN | `research/scenarios/` (stress-test walkthroughs; cited by id: S06-11, S14-n) |

---

## 0. The short version

Present tense below describes the target design. The ledger after the list says what is measured and what is unbuilt.

1. **Where it runs.** `research` identities (open web, no login). On `account` identities the extension is not
   requested at wake (DEC D18) unless G1.4 and the owner say otherwise. (Scope above, §13)
2. **Pin 4.2.0** (npm and PyPI) with extension Runtime 1.1.0. Do not pin v3. Never use an alpha tag. (§1)
3. **Stagehand v4 is an extension that lives inside the browser.** The TypeScript and Python SDKs are thin
   JSON-RPC clients over CDP. Everything the engine does runs in the extension's service worker. (§2)
4. **On self-hosted Steel it needs three things that no vendor documents** (one is only hinted at): the
   extension inside the container, `{"extensions":["stagehand"]}` on session create, and a CDP URL that also
   works from *inside* the browser. These apply to wakes that carry the extension, which means research wakes. (§3)
5. **The cheap path makes zero model calls:** `page.snapshot()` → a decider picks a line → code builds an
   `Action` → `act(Action)` with `selfHeal:false`. The fleet counts model calls in its own shim, so
   "zero" is enforced, not hoped for. (§5, §6)
6. **Every model call goes through our callback** (`model: { generate }`). Provider keys never enter the
   browser. OpenRouter/GLM is reachable no other way. (§6)
7. **There is no cache off Browserbase.** The fleet builds its own replay cache. Snapshot xpaths are
   positional, so a replay must be verified against the live page before it clicks, and that check is **not
   atomic with the click**: `act(Action)` has no "only if still this role and name" option. (§5.5, §9)
8. **`variables` hide a value from the act prompt only.** Once typed, it is in the accessibility tree and
   goes to the model on the next inference. Humans log in. Agents never type credentials. (§8)
9. **One Stagehand instance per browser.** Close it with `stagehand.close()`. Never call `browser.close()`:
   on a connected browser it kills Steel's Chromium. (§11)
10. **The extension is detectable** (`isAutomatedWithCDP`, measured n=1). Whether platforms care is unknown. That is
    why it is off accounts (DEC D18). Admitting it on an account site class needs the G1.4 full-stack result and
    the owner. (§13)
11. **Hermes profiles never talk to Stagehand.** They call fleetd tools. Stagehand is an internal
    executor behind the policy gate. (§17)

### Status ledger

| Item | State | Evidence |
|---|---|---|
| v4 TS attach to Steel (three steps) | measured once, headless Chromium 152, arm64, public pages | SPK `RESULTS.md` findings 1-3; VER SH-3 |
| v4 Python 4.2.0 attach and `act(Action)`, 0 calls | measured once; **no saved output** | SPK `spike_v4_python.py`; VER "Unsourced numbers" 3 |
| Zero-call decider path | measured with a **hard-coded regex "decider"**, not a System 1 model | VER SH-2 |
| Model calls via callback to GLM 5.3 Flash | measured: 26 calls, 22 were `json_schema` | VER V-8 |
| No cache on Steel | measured and read in code | VER SH-1 |
| `variables` leak path | measured on a synthetic page | VER SH-5 |
| `fill` on contenteditable | measured on a synthetic composer | SPK finding 5 |
| In-band upload | **26 bytes only** | VER SH-7 |
| Instance guard | measured: second `create` rejected | VER SH-6 |
| Wedge after a worker crash | **source reading only** | VER SH-6, missed issue 3 |
| Extension detectable | measured n=1 per condition, on a **CDP-loaded** extension, not Steel's flag-loaded one. This is why the extension is off `account` wakes by default (§13) | APV AP-2 |
| Proxy in the loop | **not tested** | VER SH-3 (proxy), CON C-08 |
| Headful Steel + Stagehand | **not tested** | VER SH-3 (b) |
| amd64 droplet | **not tested** (O-17) | CON O-17 |
| Real social sites (Lexical/Draft.js composers, FB/X iframes) | **not tested, forbidden in spikes.** Account use, if cleared | DOS §5 |
| Stagehand on a `research` identity (open web, behind a proxy, with the guard) | **not tested.** No `research` identity exists; spikes ran with no identity and no proxy | lead-gen playbook status; CON O-17 |
| Stagehand on an `account` identity | **not loaded** (DEC D18); only if G1.4 selects it for that site class and the owner records it | DEC D6, D18; CON O-02 |
| Gap between the verifying snapshot and the click | **not measured.** `act(Action)` has no role/name precondition (source read for this revision) | §9.3; scenario S06-11 |
| fleet shim, executor wrapper, replay cache, smoke test | **unbuilt** | this page is their spec |

---

## 1. Versions and the pin

| Component | Pin | Notes |
|---|---|---|
| npm `@browserbasehq/stagehand` | **4.2.0** (published 2026-10-08) | MIT. dist-tags at the time: `latest 4.2.0`, `v3-latest 3.7.3`, `alpha 4.2.1-alpha-1fc8849…`. `source-code` DOS Q1 |
| PyPI `stagehand` | **4.2.0** (published 2026-10-08) | MIT. Fully local; needs no Stagehand server and no Browserbase API for the core. Bundles the extension. `hands-on` + `source-code` DOS Q1 |
| Extension "Stagehand Runtime" | **1.1.0** | One extension serves both SDKs: `service-worker.js` is byte-identical in the npm and PyPI artifacts, sha256 `98e6a9874864e6409f55d4e156563b1cf179bda8ebdf485d5b425dcd822bcdaa` (hashed from the installed copies when this page was written; VER missed issue 6 gives the same prefix) |
| Wire protocol | 2.1.0 | `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md`. The SDK checks runtime compatibility on attach and rejects mismatches (DOS Q-extra) |
| Steel image | digest-pinned (DEC D4) | The source read (`1131a02`) is not the tested image (built 2026-09-16). CON §3b D4 |
| Browser tested | Chromium 152.0.7977.82, headless | SPK `RESULTS.md` setup. Manifest minimum is Chrome 116 |
| Runtimes used in spikes | Node 24.14.0, Python 3.12 | SPK `RESULTS.md` |

Never pinned: `latest`, `alpha`, any `*-alpha-*` build. The `alpha` tag moves on almost every commit to main (DOS Q1).

**Citation note.** DOS cites line numbers in the monorepo at `1fc8849`, which is *after* 4.2.0 (the npm `alpha`
tag is `4.2.1-alpha-1fc8849`). The verifier re-read the load-bearing logic in the 4.2.0 bundle and found it
identical (VER missed issue 6). Cite the 4.2.0 bundle or tag in new work.

### Why 4.2.0, and not v3 (3.7.3)

DEC D6 says v3 is not a dependency. The reasons, with the verifier's corrections:

| | v3.7.3 | v4.2.0 |
|---|---|---|
| Release state | Last release 2026-08-28. The `v3` branch has been quiet since. A crash fix (#2910) filed by an outside user is unreleased. | 4.0.0 to 4.2.0 in two months. Stable releases are about four weeks apart (29 days from 4.1.0 to 4.2.0; the longest gap in the v3 line was 33). |
| What that proves | "Low-cadence maintenance" is fair. "Fixes are not shipping" is **overstated**: it rests on six weeks of silence plus one third-party issue (VER V-6). | n/a |
| `npm audit --omit=dev`, fresh lockfile | **5 advisories (3 moderate, 2 high)** via `ai@5.0.273`. `npm audit fix` does not clear them. Reachability not analysed. Reproduced by the verifier (VER SH-9). | **0** |
| Local cache | `cacheDir` replays with zero calls, but **clicked the wrong link with `success:true`** and its agent cache **returns the first run's text answer** (VER SH-8, missed issue 1) | none |
| `selfHeal` default | **true**: a failing Action silently calls the model | **false** |
| Exclusivity | none: two controllers attached | one instance per browser, enforced |
| Python | legacy 3.23.0: a REST client plus an embedded server binary; repo archived | 4.2.0: same extension runtime, fully local |
| Attach to Steel | plain `cdpUrl`, works on stock Steel (Steel documents it) | the three-step recipe in §3 |
| Browser footprint | none | an extension with `debugger`, `offscreen`, `scripting`, `tabs` and a content script on every frame of every URL |

What choosing v4 costs us: **no `agent()`** (we build the loop), **no local cache** (we build it), an
**undocumented attach recipe**, and a **detectable extension** (which is why §13 keeps it off accounts by default).
What it buys: zero advisories, an enforced instance guard, safe defaults, one runtime for TypeScript and Python.

No v3 "bridge". DOS floated v3 as a short-lived bridge if `agent()` were needed early; the verifier showed its
agent cache replays stale answers (VER missed issue 1), and DEC D6 rejects v3. Kernels older than Chromium
149 (patched or vendor builds) cannot take v4 at all; route those profiles to Browser-Use (APV AP-1).

---

## 2. Architecture

```
EXECUTOR (a fleet process)                         BROWSER CONTAINER (Steel, one identity)
  Stagehand SDK, TypeScript or Python                Chromium
    a thin JSON-RPC client                             |
    each call = Runtime.evaluate on the                +-- "Stagehand Runtime" MV3 extension
      extension's service-worker target                |     its service worker is THE ENGINE:
      ------------- CDP WebSocket, URL A ------------>|       snapshot, prompts, act, observe,
                                                       |       extract, locators, instance lock
    model callback                                     |     it dials URL A again, from INSIDE
      ^   llm.generate (JSON-RPC, same link)           |       the browser (the reason for step 3)
      |                                                +-- content script: every frame, every URL
    fleet shim ---> LLM provider                       +-- offscreen heartbeat document
```

Facts, with sources:

- **The engine is the extension.** The SDK sends each call as `Runtime.evaluate` on the service-worker target and
  receives the answer through a runtime binding. The extension holds snapshotting, prompts, act/observe/extract,
  the CDP driver ("understudy") and the LLM and cache HTTP calls. `source-code` DOS Verdict 1; VER V-1.
- **Manifest** (Runtime 1.1.0): permissions `debugger`, `offscreen`, `scripting`, `tabs`; host permission
  `<all_urls>`; content script on `<all_urls>`, all frames, `document_start`, `match_about_blank`; an options page;
  an always-on offscreen heartbeat document that keeps the service worker alive. No `web_accessible_resources`.
  `source-code` (installed 4.2.0 `dist/extension/manifest.json`); VER V-1 and missed issue 9. DOS lists only three
  permissions; VER adds `offscreen`.
- **The extension opens a second CDP connection from inside the browser** to the URL the SDK was given
  (`params.browserCdpUrl`, the SDK's `webSocketDebuggerUrl`). This is why §3 step 3 exists. `source-code` VER SH-3.
- **No Playwright, no Stagehand server.** v3 is also CDP-native; Playwright and Puppeteer are only optional peers.
  `source-code` DOS Q2.
- **Where the model is called.** With a client callback the SDK registers `llm.generate` as a JSON-RPC handler, so
  the call leaves the *SDK process*. With a provider key in `ModelConfig`, the key is sent to the extension and the
  *browser* calls the LLM, through the profile's IP. `source-code` VER SH-4; DOS Verdict 7. The fleet uses only the
  callback (DEC D6).
- **The instance lock lives in the service worker** and is released only by the `stagehand.close` RPC (§11).
- **Domain policy is not a boundary.** `setDomainPolicy` is bypassed by service-worker fetches and WebSockets
  (issue #2945, open). DOS Q11.

What this means for the fleet: a browser that Stagehand drives must carry the extension and be able to reach the
CDP URL; the extension's footprint becomes part of that identity's surface (the reason it is not on accounts by
default, §13); and the SDK process is cheap and replaceable while the browser is not.

---

## 3. Setup on self-hosted Steel (`design`, recipe `hands-on` once)

**Which wakes.** This setup is for wakes of `research` identities (steel.md §9.1 "mode A": the extension is resident
from launch, the measured headless recipe). The node agent derives whether to request the extension from the
identity's `kind` and the wake's purpose, never from the caller (DEC D18). A wake of an `account` identity does not
request it, and the `account` image carries no extension directory and none of the launch-flag overrides below
(`steel-profile.md` §2 has the two image flavors). The persona pins `extension_mode` and `executor_id` (DEC D3, D18): a
change is a persona change and goes through the canary rule (CON O-13), never per wake. ARCH N2 and wake step W10 still
request the extension every time, as read for this revision (§15 row 9). **Account use, if cleared:** mode A or mode B
(steel.md §9.1; mode B, uninstall after the session, is untested) is chosen per site class by G1.4.

Stock Steel fails: `localBrowser.connect` returns `File path cannot be resolved.` in 36 ms, because the SDK finds no
installed extension and asks the browser to load one from the *SDK host's* path. `hands-on` SPK findings 1-3.

Three steps fix it. Steps 2 and 3 are in nobody's docs; step 1 is only hinted at, where Stagehand says "Loading
requires a shared filesystem" (`https://docs.stagehand.dev/v4/configuration/browser.md` lines 569; VER SH-3). Steel's own guide covers v3 on Steel Cloud and says the
framework "is unaware of how the session was provisioned" (`https://docs.steel.dev/integrations/stagehand.md`); that does not hold for
v4 on self-hosted Steel (SPK findings 1-3; VER SH-10).

### Step 1: the extension is inside the container

Bake the extension into the `steel-profile` wrapper image (DEC D4) at the directory Steel reads for named
extensions: `/app/api/extensions/<name>`. Steel's docs say `api/src/extensions/`; the code reads `api/extensions/`
(`source-code` STD Extensions row). The extension is a 2.0 MB directory taken from the pinned npm package
(`dist/extension/`) or the pinned wheel (`stagehand/_extension/`).

```dockerfile
# fragment of the steel-profile image used for research wakes. design, unbuilt.
FROM ghcr.io/steel-dev/steel-browser-api@sha256:<pinned digest>
COPY stagehand-runtime-1.1.0/  /app/api/extensions/stagehand/
# build-time checks: manifest name == "Stagehand Runtime", version == 1.1.0,
# sha256(service-worker.js) == 98e6a987…bcdaa. Fail the build otherwise.
```

The spike mounted it read-only instead (`-v …/dist/extension:/app/api/extensions/stagehand:ro`). SPK `RESULTS.md` setup.
If the wrapper later runs Chromium as a non-root user (Q-08), the directory must be readable by that user. `pending Q-08`.

### Step 2: create the session with `extensions:["stagehand"]`

Steel launches Chromium with `--load-extension` and `--disable-extensions-except` for every extension named on
create. Without it, a runtime `Extensions.loadUnpacked` returns an id but **the extension never runs**, and
`connect` times out after 60 s. `hands-on` SPK findings 1-3; `source-code` VER SH-3. The first create with this
config relaunched Chromium and took 7.2 s. SPK findings 1-3.

Shape of the create call (field names from `https://github.com/steel-dev/steel-browser/blob/1131a02/api/openapi/schemas.json`,
schema `CreateSession`). The node agent owns every field except `extensions`, which is the only one Stagehand adds:

```jsonc
POST /v1/sessions            // inside the container's own network only (DEC D4)
{
  "extensions": ["stagehand"],            // required for Stagehand v4; research wakes only. Names a dir under /app/api/extensions
  "persist": true,                        // profile volume at /app/api/user-data-dir (DEC D4)
  "skipFingerprintInjection": true,       // persona rules, DEC D3/D4
  "userAgent": "<pinned, matches the real Chromium major>",
  "timezone": "<pinned IANA zone>",
  "dimensions": { "width": 0, "height": 0 },   // pinned
  "proxyUrl": "http://127.0.0.1:<node forwarder port>"   // never a credentialed URL (DEC D10)
  // headless: set per the M1 decision. Headful needs Xvfb + dbus (CON C-11). Only headless was tested.
  // do NOT send userDataDir / profileId / persistProfile: Steel ignores them (CON C-04, DEC D4)
}
```

Rules that follow from D4 and the measurements:

- **Create once per wake.** A second `POST /v1/sessions` on a live container either takes over the live browser
  (same config) or relaunches it and drops the first (different config). Nothing returns 409. STV STE-1.
- **Check that the extension is present before handing the browser to an executor:** `Extensions.getExtensions`
  must list "Stagehand Runtime" at the pinned version. `hands-on` SPK findings 1-3 (the call works on Chromium 152 without
  `--enable-unsafe-extension-debugging`; the docs say it is required, the docs are stale; APV AP-1).
- Headless Steel always adds its own recorder extension, which is what triggers `--disable-extensions-except`.
  Headful with no extensions requested adds no extension flags. Headful + Stagehand is `to measure`. VER missed issue 5, SH-3.

### Step 3: the CDP URL must also work from inside the browser

The SDK passes one URL. The extension dials that *same string* from the browser. A URL that is right for the
executor (a published host port, a Docker network name) is often wrong inside the container.

| What happened | Result |
|---|---|
| URL only works from the executor (`ws://127.0.0.1:3301/` with Steel listening on 3000 inside) | `Stagehand.create` fails: `CDP websocket failed to open`. `hands-on` SPK findings 1-3 |
| Container `PORT` = published host port (`-p 127.0.0.1:3301:3301`, `PORT=3301`) | works. Spike set `DOMAIN=127.0.0.1:3301` and `CDP_DOMAIN=127.0.0.1:3301` too; whether each is required was not isolated |

Layouts that satisfy the rule (`design`):

| Layout | Mechanism | State |
|---|---|---|
| **L-B: shared network namespace (chosen by ARCH §2.2)** | The `identity-runtime` sidecar joins the Steel container's network namespace and hosts the forwarder, guard, executor and Stagehand worker. Steel's API and CDP listen on `127.0.0.1:3000`, so one URL, `ws://127.0.0.1:3000/`, is valid for the worker and from inside the browser. Nothing is published on the host | ARCH marks it "design choice to confirm in M1". Not run. Open M1 interactions named by ARCH: the guard's `Fetch` interception against the extension's loopback WebSocket, and the sidecar under Docker's `--init` and restart behaviour. Cost: everything in the namespace can reach everything else on loopback (ARCH §2.2) |
| L-A: identical loopback port (fallback) | Node agent gives each awake identity a unique port N, sets `PORT=N` in the container, publishes `127.0.0.1:N:N`; the worker uses `ws://127.0.0.1:N/` on the node | **The only layout actually run** (N=3301 in the spike). Any local process on the node can reach Steel's unauthenticated API (`inference`); that conflicts with "never published" in ARCH N2 and with DEC D4 unless the node runs nothing else |
| L-C: non-loopback name | e.g. a Docker network alias | Avoid. Chromium sends non-loopback names through the identity proxy unless bypassed. If used, that exact host goes in Steel's `PROXY_INTERNAL_BYPASS`. `source-code` only; VER SH-3 and missed issue 4 |

**Proxy interaction.** Chromium bypasses loopback implicitly, and Steel sets no `--proxy-bypass-list`. With the
fleet's loopback forwarder (DEC D10), L-B and L-A need no bypass entry, and the antidetect rule "keep
`PROXY_INTERNAL_BYPASS` empty" wins (CON C-08). **Not tested with a proxy in the loop** (`to measure`, M1). Also:
provider-key LLM calls and OpenTelemetry exports would leave through the identity proxy; the fleet uses neither (§6, §12).

### Hidden dependencies in Steel's launch flags

The recipe also rides on three Steel behaviours nobody promised us. All three go in the upgrade smoke test (§17).
They matter only for images and wakes that carry the extension (research). Leaving them out of an `account` image
would also drop the admitting `--remote-allow-origins` for no loss; whether Steel lets the fleet filter that flag is
`to measure` (scenario S14-4; the related in-page path to Steel's API is S13-6).

1. `--remote-allow-origins=*` (`cdp.service.ts:870`): the extension's WebSocket carries `Origin: chrome-extension://<id>`,
   and Chromium answers 403 unless the flag admits it. Every spike used `*`, so the raw data cannot show this failure. APV AP-1.
2. `--load-extension` and `--disable-extensions-except` for each requested extension (`cdp.service.ts:808-862`).
3. The feature override `--disable-features=…DisableLoadExtensionCommandLineSwitch,DisableDisableExtensionsExceptCommandLineSwitch`.
   Without it, `--load-extension` stops working on Chrome 137+. VER missed issue 5.

If a future kernel is patched or vendor-built, Stagehand v4 needs Chromium ≥ 149 (147-148 gated, ≤146 absent), the
extension on the browser host's filesystem, an in-browser-resolvable CDP URL and an admitting
`--remote-allow-origins`. APV AP-1. `pending Q-03, Q-04`.

### On a Browserbase-home identity (DEC D11)

Different attach: `browserbase.connect({ apiKey, sessionId })`; sessions are expected to have the extension preloaded
(`preloadedExtension: true`, DOS Q9). Not tested (no key exists). `browser.close()` releases a Browserbase session
even with `keepAlive`, so the login broker never calls it between steps (DEC D6). The fleet leaves server-side caching
off there too (§9). The same callback, the same shim, the same rules apply, and the same scope: `research` identities by
default, an account only if cleared (Scope box).

---

## 4. Attaching (code)

The Stagehand worker runs in the `identity-runtime` sidecar next to the Steel container (ARCH §2.2, N3/N4), under the
executor that owns the ladder. It is started for wakes that carry the extension (`research` identities; account use,
if cleared). The wrapper (`design`, unbuilt) constructs every instance the same way. The options
below are fixed in code, not passed by callers. ARCH N4 makes the worker **Python by default, TypeScript as the
fallback**; the code below shows both. (AGT's proposed layout says "Stagehand worker (Node)"; ARCH wins where they
disagree.)

### TypeScript

```ts
import { Stagehand, localBrowser } from "@browserbasehq/stagehand";

// cdpUrl: the SAME string must resolve for this process and from inside the browser (section 3, step 3).
const browser = await localBrowser.connect({ cdpUrl: "ws://127.0.0.1:3000/" }); // layout L-B; the spike used :3301 (L-A)
const stagehand = await Stagehand.create({
  browser,
  model: { generate: fleetGenerate },       // the shim, section 6. Never { modelName, apiKey }
  selfHeal: false,                          // explicit. v3 defaulted to true
  logging: { level: "warn", format: "json" },
  // deliberately absent: apiKey, apiUrl, cache, telemetry, systemPrompt-as-policy
});
const page = (await browser.context.activePage()) ?? (await browser.context.newPage());

// ... work ...

await stagehand.close();    // releases the one-instance lock. NEVER browser.close()
```

### Python

```python
from stagehand import Stagehand, local_browser

browser = await local_browser.connect(cdp_url="ws://127.0.0.1:3000/")   # layout L-B; the spike used :3301 (L-A)
stagehand = await Stagehand.create(
    browser=browser,
    model=fleet_generate,          # async callable, section 6. Never a "provider/model" string + key
    self_heal=False,
    logging={"level": "warn", "format": "json"},
)
page = await browser.context.active_page()

# ... work ...

await stagehand.close()            # NEVER browser.close()
```

Notes:

- `connect` keeps its deprecated `extensionId` argument; it is ignored. The SDK finds the installed extension itself
  (4.2.0 change, `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md`, #3140). `source-code` DOS Q2.
- `Stagehand` cannot be constructed directly in Python (`await Stagehand.create(...)` only), and has no `env`,
  `cdp_url`, `init()` or `.page`. The shape `Stagehand(env="BROWSERBASE", cdp_url=...)` in the Gemini conversation is
  not real: it raises `TypeError` on 4.2.0. DOS Q2; `research/verification/GEMINI-AUDIT.md` rows 2.10, 10.01-10.05.
- **`browser.close()` on a connected local browser sends `Browser.close` and kills Steel's Chromium.** The Stagehand
  docs' examples call it in `finally` blocks; the docs say Stagehand "never closes a browser it did not launch", which
  is about `stagehand.close()`. APV V-7 (`source-code` over docs). The wrapper never exposes `browser.close`, and a unit
  test fails if the string appears in executor code. A browser that dies this way is an unclean stop: the identity goes
  down DEC D4's restore path (stale `Singleton*` cleanup under the lease, ≥ 31 s cookie-commit rule).
- **Python is the default worker (ARCH N4) on thinner evidence.** The only Python run (attach 43 ms, `act(Action)` 480 ms,
  55 MB, 0 calls) has no saved output, and its 43 ms is 30-50 times faster than the TypeScript attach, unexplained
  (VER SH-2(c), "Unsourced numbers" 3). Condition: the first M1 smoke run (ST-3, ST-4) must save Python output. If it
  fails, the worker falls back to TypeScript, which has raw artifacts behind every figure on this page.
- Measured attach cost: TS `connect` 1.3 s, `create` 0.8 s, `goto` 0.9 s, first `snapshot` 0.2 s (SPK findings 1-3);
  the antidetect spike saw `connect` 0.14-1.9 s and `create` 0.35-2.0 s over n=3 (APV Q2 and its verifier item 5). Plan
  on roughly 1-3 s per attach. `estimate`.
- Python's `Stagehand.create` also takes `api_key`, `api_url`, `cache`, `telemetry`, `system_prompt`,
  `dom_settle_timeout_ms`, `model_api_key`, `model_headers`. The fleet sets none of the first four. `source-code`.

---

## 5. The primitives the fleet uses

Return shapes are `source-code` (DOS Q3) and were confirmed in the spikes. Python mirrors the TypeScript API in
snake_case: `result.data.success`, `snap.formatted_tree`, `snap.xpath_map`, `include_iframes=True`.

```ts
type Action  = { selector: string; description: string; method?: string; arguments?: string[] };
type Usage   = { inputTokens: number; outputTokens: number; reasoningTokens: number;
                 cachedInputTokens: number; inferenceTimeMs: number };
type Meta    = { usage: Usage; cache: { status: "HIT" | "MISS" | "DISABLED" }; actionId?: string };
type ActResult      = { data: { success: boolean; message: string; actionDescription: string; actions: Action[] }; metadata: Meta };
type ObserveResult  = { data: Action[]; metadata: Meta };          // v4 wraps the array in .data; v3 returned it bare
type ExtractResult<T> = { data: T; metadata: Meta };               // default T = { extraction: string }
type Snapshot = { formattedTree: string; xpathMap: Record<string, string>; urlMap: Record<string, string> };
```

### 5.1 What each call costs

Single samples on quotes.toscrape.com, GLM 5.3 Flash at `low`, Steel on arm64 (SPK finding 4, 8). The dollar figures
move about 3x with the OpenRouter provider that happened to serve the call (VER missed issue 7). Treat them as
orders of magnitude.

| Call | Model calls | Time | Tokens in / out | USD |
|---|---:|---:|---|---:|
| `page.snapshot()` | 0 | 0.39 s (6,981 chars); 1.33 s (books page, 21,553 chars) | n/a | 0 |
| `observe(instruction)` | 1 | 2.3 s | 2,495 / 26 | 0.00013 |
| `act("click the Next link")` | 1 (2 if the model sets `twoStep`) | 2.8 s here; 2.5-5.0 s on loaded pages | 3,067 / 33 | 0.00016 |
| `extract(instruction, schema)` | **2** (Extraction, then Metadata) | 2.0 s | 2,403 / 178 | 0.00026 |
| `act(Action)` | **0** | 0.28 s (decider-built), 0.46 s (from `observe`) | n/a | 0 |

On a 6k-token page an uncached act cost $0.00095 (RMV REA-2). Uncached Stagehand calls: p50 about 1.7 s, p90 about
3.5 s, n=12 (RMV REA-2; the headline 1.2 s was cache-flattered by the provider's prompt cache).
"About 5.4k tokens" for the books snapshot is characters divided by four, not a tokenizer count (VER).

### 5.2 `page.snapshot()`: the zero-model-call way to see the page

```ts
const snap = await page.snapshot({ includeIframes: true, timeout: 20_000 });
// snap.formattedTree  lines such as:   [0-1888] link: Next
//                                      [0-4] textbox: Search
//                                      [1-313] paragraph            <- first number = frame ordinal
// snap.xpathMap       { "0-1888": "/html[1]/body[1]/div[1]/.../a[1]" }
// snap.urlMap         { ... }
```
```python
snap = await page.snapshot(include_iframes=True, timeout=20_000)   # snap.formatted_tree, snap.xpath_map
```

- Zero model calls. `timeout` defaults to 20 s; `0` means unlimited (4.2.0, `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md` #3083). Set it.
- A line is `[<frame>-<node id>] <role>: <accessible name or text>`. The id is only good for the snapshot that produced
  it (`inference`: it comes from browser node ids). **The xpath is what persists, and it is positional**
  (`/li[1]/a[1]`). It resolves to whatever sits at that position later. VER missed issue 2.
- Text nodes (`StaticText`) carry a trailing `/text()[n]`; trim it or choose the parent (DOS Q4).
- `ignoreLocators` on `act`/`observe`/`extract` removes each matching target and its descendants from the tree the
  model sees; `locator` scopes the call to one subtree (`https://docs.stagehand.dev/v4/basics/observe.md` lines 378, `extract.md:669`).
  Use `ignoreLocators` to keep DM threads and other private regions out of model input. Those calls bypass the
  server cache (moot off Browserbase). `official-docs`.

### 5.3 `observe()`: plan, with one model call

```ts
const { data: actions } = await stagehand.observe("find the 'Next' pagination link", { timeout: 15_000 });
// actions[0] = { selector: "xpath=/html[1]/body[1]/…/a[1]", description: "...", method: "click", arguments: [] }
```
```python
res = await stagehand.observe("find the 'Next' pagination link")   # res.data -> list[Action]
```

- Returns candidate `Action`s and does not touch the page. This is the interposition point (§5.7).
- Omitting the instruction uses "Find elements that can be used for any future actions…" (`source-code` DOS Q3).
- Variable *names and descriptions* (never values) are sent so the model returns `%name%` placeholders (§8).
- An empty array is a valid answer, and often the correct one. GLM returned `null` correctly 3 of 3 on an impossible
  instruction (RMD §4).

### 5.4 `act("instruction")`: infer and execute in one call

```ts
const r = await stagehand.act("click the Next link", { timeout: 15_000 });   // r.data.success, r.data.message
```
```python
r = await stagehand.act("click the Next link", timeout=15_000)
```

- 1 model call; 2 if the model sets `twoStep:true` for a custom (non-`<select>`) dropdown. The model schema is
  `{ action: { elementId /^\d+-\d+$/, description, method, arguments[] } | null, twoStep }`. `source-code` DOS Q3.
- **It reports a miss as `success:false`; it does not throw.** A model `null` gives
  `"Failed to perform act: No action found"`. Always read `r.data.success`. DOS §4 note 5.
- Write atomic instructions, one action each ("click the Next link"). Anchor repeated widgets with their text
  ("Add to basket for <title>"): runaways and false nulls clustered on repeated widgets (RMD §4).
- Instructions are built from procedure templates by code. Never paste page text or Hermes free text into one (§17).

### 5.5 `act(Action)`: execute a chosen element, zero model calls

```ts
await stagehand.act({
  selector: "xpath=" + snap.xpathMap["0-1888"],   // from snapshot or observe
  description: "Next link",
  method: "click",                                  // the decider picks WHICH; code picks method and arguments
  arguments: [],
});
```
```python
await stagehand.act({"selector": "xpath=" + snap.xpath_map["0-1888"], "description": "Next link",
                     "method": "click", "arguments": []})
```

- **Zero model calls, with `selfHeal:false`**: 0.28 s and 0 calls from a decider-built Action; 0.46 s from an
  `observe` result. `hands-on` SPK finding 4; `source-code` `actService.ts:104-113`. VER SH-2 corrects the wording:
  zero holds when the Action succeeds *or* `selfHeal` is false.
- Methods: `click, fill, type, press, scrollTo, nextChunk, prevChunk, selectOptionFromDropdown, hover, doubleClick,
  dragAndDrop`. The executor also accepts `scrollIntoView, scrollByPixelOffset, scroll, mouse.wheel, selectOption`.
  `source-code` DOS Q3.
- `method` and text `arguments` come from code or the reasoning model, never from a decider (a decider only chooses
  a candidate). DOS Q4.
- Raw `xpathMap` values work as-is for element nodes, and cross-frame xpaths work unchanged. `hands-on`.
- **It skips inference, the page snapshot and the DOM-settle wait** (`https://docs.stagehand.dev/v4/basics/act.md` lines 585). The page may not
  have settled when it returns. Wait on a postcondition yourself.
- A broken xpath with `selfHeal:false` returns `success:false` ("Could not find an element") in 16 ms with 0 calls.
  `hands-on` SPK finding 4.
- **The danger is the xpath that still resolves.** `act(Action)` never checks role, name or description. A positional
  xpath that now points at another element clicks it and returns `success:true`. v3's cache did exactly that
  (`hands-on`, VER SH-8). The same hazard applies to a v4 decider pick and to a batch planned with one `observe()`
  and executed later: after the first mutation, later xpaths can drift (VER missed issue 2, `source-code`; not
  reproduced on v4). `selfHeal` never fires on this failure because nothing failed.
- **Checking first does not make the click safe, because the check is not atomic with the click.** The Action carries
  only `selector, description, method, arguments`, and the extension re-resolves the xpath itself. There is no
  "click only if it still has this role and name" option. §9.3 says what the fleet does about the gap.

Verified act (`design`, sketch of the executor's core step; unbuilt). It narrows the gap and does not close it:

```ts
async function actVerified(sh, page, t /* { xpath, role, name, method, args, description } */) {
  // Anything that needs fleetd (authority, governor, intent row) has already happened. Nothing below calls fleetd or a model.
  const snap = await page.snapshot({ includeIframes: true, timeout: 20_000 });          // 0 model calls
  const tSnap = now();                                                                   // freshness clock starts when the snapshot ends
  const id   = Object.keys(snap.xpathMap).find(k => snap.xpathMap[k] === t.xpath);
  const line = id && snap.formattedTree.split("\n").find(l => l.includes(`[${id}]`));
  if (!line || !sameRoleAndName(line, t)) return { ok: false, reason: "fingerprint_mismatch" };  // a miss, never a click
  policy.checkLocal({ url: await page.url(), role: t.role, name: t.name, method: t.method });     // local code only: judges the REAL element
  if (!(await preActRead(page, t)))  return { ok: false, reason: "pre_act_mismatch" };            // cheap second read of the resolved node, section 9.3
  if (now() - tSnap > T_FRESH_MS)    return { ok: false, reason: "stale_verification" };          // snapshot again; never act on an old check
  const r = await sh.act({ selector: "xpath=" + t.xpath, description: t.description, method: t.method, arguments: t.args });
  return { ok: r.data.success, message: r.data.message };                                // then verify the outcome (D13)
}
```

### 5.6 `extract(instruction, schema)`: structured reads

```ts
import { z } from "zod";
const { data } = await stagehand.extract(
  "the first three quotes with authors",
  z.object({ quotes: z.array(z.object({ text: z.string(), author: z.string() })) }),
  { timeout: 20_000, locator: page.locator("main"), ignoreLocators: [page.locator("nav")], screenshot: false },
);
```
```python
class Quotes(BaseModel): quotes: list[Quote]
res = await stagehand.extract("the first three quotes with authors", Quotes, locator=page.locator("main"))
# res.data is a Quotes instance
```

- **2 model calls**: "Extraction", then a "Metadata" call (`{progress, completed}`). Budget both. `source-code`
  DOS Q3; measured 2.
- It works on the accessibility-tree snapshot, not raw HTML (`research/verification/GEMINI-AUDIT.md` row 2.07). The instruction is required.
- No schema returns `{ extraction: string }`.
- `screenshot:true` adds a viewport image block; use it only when the tree lacks the data. Large full-page images can
  hit the SDK's base64 regex limit (issue #3060, open: about 4-8 MiB). DOS Q7.
- `extract` is a read. It still sends page content to the model. `locator` and `ignoreLocators` are the privacy tools.
- Extract answers are never cached or replayed by the fleet (§9).

### 5.7 Split, don't fuse (fleet rule, `design`; live scope: L3 on `research` identities)

String `act` fuses *choosing* and *clicking* in one call, so the fleet has no moment to look at the chosen element.
That moment is where policy must act (DEC D5, D13). **Scope:** the rule governs L3 on `research` identities, the only
place Stagehand L3 runs by default. There the policy is Gate G's `read_only` allow-list plus the lead-gen rule that
nothing is ever submitted ([lead-gen playbook](../playbooks/lead-gen.md) §3.7). **Account use, if cleared:** the same
rule is the floor for any account site class that G1.4 and the owner admit Stagehand on, with the additions in §9.3
for effect steps. No such clearance exists. Therefore:

- **L3 is `observe()` → verify and policy-check the returned Action → `act(Action)`.**
  Model cost is the same as string `act` (one call). It adds one verification snapshot and the Action step, roughly
  half a second to a second (`estimate` from the timings in §5.1).
- String `act` is allowed only for steps the procedure declares as non-effect, or on a `research` session (no login, no
  effects). DEC D5 requires the effect gate "on every rung, including free-form `act`". ARCH §4.3
  "Gate G" is that gate: a declared `effect` on the step wins; for free-form `act` there is no declaration, so a
  `read_only` positive allow-list applies by default (navigate, scroll, find, extract; links with an `href`, tabs,
  disclosure widgets, dismiss/close; text into search boxes) and anything else on a platform host is `needs_approval`.
  (Lead generation goes further and does not type into search boxes on company sites by default.)
  The element-label classifier is only a deny-list backstop that **fails open on unlabeled icon buttons**. A fused string
  `act` cannot be checked per click, so it is allowed only inside that allow-list. Everything else goes through the split
  path above. ARCH's L3 row says "`observe` / `act`" and "the returned `Action` passes the same gate"; this page fixes the
  reading as observe, then gate, then `act(Action)`.
- Custom dropdowns are two observe/act rounds.
- **Content-bearing methods (`fill`, `type`) take their text from the manifest, not the model.** The executor
  discards the model's text `arguments` and substitutes the approved value; the model only chooses the target
  (DEC D13: content to publish never comes from page text or from a model). `design`.

### 5.8 Other calls the executor uses

`page.goto`, `page.reload`, `page.url()`, `page.title()`, `page.waitForSelector`, `page.waitForTimeout`,
`page.screenshot()` (28,946 bytes measured), `page.locator(css).click/fill/count/innerText/inputValue/isVisible`,
`page.locator(css).setInputFiles(...)`, `browser.context.activePage()/pages()/newPage()/setActivePage()`,
`stagehand.metrics()`. Locator calls default to a 20 s timeout in 4.2.0 (#3033); `0` disables it. Pass explicit
timeouts. `page.evaluate` and raw CDP exist; they are internal-only (§17).

---

## 6. The model callback and the fleet shim

**Rule: every model call comes from a client callback. No `ModelConfig` with an `apiKey`, ever, and no per-call
`model:` override carrying a key** (the vendor docs show one at `https://docs.stagehand.dev/v4/basics/act.md` lines 289-300; the fleet does not
do it). Reasons: a provider-key config ships the key into the browser, the browser then calls the LLM through the
profile's IP, and `ModelConfig` has no `baseURL`, so OpenRouter/GLM is unreachable without the callback.
`source-code` VER SH-4; DEC D6.

### 6.1 Callback contract

```ts
type Block = { type: "text"; text: string } | { type: "image"; mimeType: string; data: string /* base64 */ };
type LLMGenerateParams = {
  messages: Array<{ role: "user" | "assistant"; content: Block | Block[] }>;
  systemPrompt?: string; temperature?: number; stopSequences?: string[];
  responseFormat?: { type: "text" } | { type: "json_schema"; name: string; schema: unknown };
  tools?: unknown; toolChoice?: unknown;
};
// act / observe / extract always send json_schema. Return exactly this:
async function fleetGenerate(p: LLMGenerateParams) {
  return {
    role: "assistant",
    content: { type: "text", text },
    outputFormat: "json_schema",
    structuredContent,          // the parsed object; the SDK validates it against p.responseFormat.schema
    usage: { inputTokens, outputTokens, totalTokens, reasoningTokens, cachedInputTokens },
  };
}
// Stagehand.create({ browser, model: { generate: fleetGenerate } })
```
```python
async def fleet_generate(params):            # params: LLMStructuredGenerateParams
    # params.messages, params.system_prompt, params.temperature, params.response_format (.name, .schema_)
    return LLMStructuredGenerateResult.model_validate({
        "role": "assistant", "content": {"type": "text", "text": text},
        "output_format": "json_schema", "structured_content": parsed,
        "usage": {...}})
```

Sources: `https://docs.stagehand.dev/v4/configuration/models.md` lines 1196-1300 (docs), `C/sdk-python/examples/custom_llm.py.txt` (scraped copy not published),
`SPK/openrouter-llm.mjs` (works end to end), DOS Q4. A text answer to a `json_schema` request is a hard error.
The SDK registers the callback as the JSON-RPC handler `llm.generate`. Every inference needs a configured model, even
one that will not be used.

The four call names (`responseFormat.name`): **Act**, **Observation**, **Extraction**, **Metadata**. The shim caps
tokens and tags logs by name.

### 6.2 What the shim must do (`design`, unbuilt; spec from DEC D8)

1. **Exact model slug** `z-ai/glm-5.3-flash`. Never `~z-ai/glm-flash-latest` (it silently redirects and has another
   price). RMD Q1.
2. **`reasoning: { effort: "low" }`.** Reasoning is mandatory on this model: `enabled:false` and `effort:"none"` return
   HTTP 400; unset means `max`. Low versus high is a statistical tie (67/72 versus 51/52, p=0.40); keep `low`, treat it
   as a knob. RMV REA-5.
3. **`response_format` = `json_schema`, `strict:true`, and `provider.require_parameters:true`, always.**
4. **Validate every answer against the request's full schema, `pattern` included.** Strict `json_schema` is a hint, not a
   guarantee. Seen: one provider emitted `"elementId":"[0-218]"` (breaks `^\d+-\d+$`); another returned non-JSON 4/4;
   with `provider.only` and no `require_parameters` one provider returned YAML at HTTP 200. RMV REA-7.
5. **A mandatory `max_tokens` per call name.** Starting values: Act and Observation 1024, Metadata 256, Extraction about
   30 tokens per expected item plus 512. The extraction formula is a heuristic that was never run, and the cap's effect on
   runaway latency is unmeasured (RMV unsourced list). `to measure`. Runaways ran to 8k tokens and 34-52 s each.
6. **Retry once on another provider** (`provider.ignore=[served provider]`) on invalid output, `finish_reason=length`, or
   a `null` act element. Do not escalate a `null` to a stronger model blindly: it is often the right answer (RMD §4).
7. **A bench-gated provider allowlist** with price and quantization caps. OpenRouter listed 33-38 GLM 5.3 Flash endpoints
   ($0.032-$0.225/M input, several fp4; 22-26 with structured outputs). Cost projections use **list price**
   ($0.15/$0.50 per M): in the bench 150 of 150 calls landed on $0.15 endpoints (RMV REA-14). Pin and log the serving
   provider. The per-provider bench is an M3 gate (DEC D8; CON O-06).
8. **Fix `arguments`.** Stagehand executes only `arguments[0]`, so keep `arguments[:1]`. For a `click`, lowercase the
   button argument and keep only `""`, `left`, `right`, `middle`; otherwise drop it (seen: `"],"`, `"LEFT"`). **Never
   change typed text or key names.** DEC D8.
9. **Sanitize schemas** for strict providers: replace `additionalProperties: {}` with `false` (the Python SDK emits the
   former for pydantic schemas; OpenAI strict mode rejects it). Harmless elsewhere. RMD §3.
10. **Images:** map image blocks to `image_url` data URLs. Only `extract({screenshot:true})` sends one. The vision-based
    repair step in DEC D8 is not a Stagehand primitive; it is fleet-built or Browser-Use's.
11. **Record per call:** call name, model, serving provider, `finish_reason`, latency, tokens, `usage.cost`, validation
    verdict, run id, identity, procedure step. Aggregate per profile for the spend ledger.
12. **Escalation ladder** for failed acts (DEC D8): another provider → DeepSeek V4.1 Flash with
    `reasoning:{enabled:false}` (different failure mode: false nulls) → screenshot path.
13. **Data handling** (`provider.data_collection:"deny"` or `zdr:true`) is `pending Q-07`. Requiring ZDR changes the
    allowlist and invalidates the bench numbers: 29 endpoints are ZDR-listed, but the bench's main provider is not,
    and one ZDR provider failed schema enforcement every time (DEC D8; RMV REA-7). On `research` identities the model
    reads public company pages (no logins, no DMs), the lighter end of Q-07 (lead-gen playbook §3.6); the allowlist
    still applies. **Account use, if cleared:** until Justin answers, the charter's
    conservative default applies (CHT invariant 8): **DM content is never sent to a model provider by the fleet**, and
    other logged-in page content goes only to the bench-gated allowlist. For Stagehand that means: no string `act`,
    `observe` or `extract` on a DM surface (inbox, thread, message request views). DM steps use L0/L1 (and the API
    channel), or `ignoreLocators` over the message content. The executor knows a DM surface from the procedure step's URL
    pattern and a role/name check; the classifier's miss rate is `to measure`. `pending Q-07`.
    **`ignoreLocators` is the only enforcement of this DM rule today** (scenario S14-9). If M1 puts another executor on
    accounts, that executor's snapshot builder must drop the same subtrees before any model call, with a redaction test
    (a DM-thread fixture never appears in a model input). MIL G3.13 carries that test for the fleet executor, if it is
    built (P3.5).
14. **Budgets:** a per-call, per-step and per-identity token and dollar budget; exhaustion returns `budget_exhausted`
    (DEC D17). Caps `pending Q-06`.

### 6.3 The zero-call guard (`design`)

The shim has a mode. On L1 and L2 steps the executor sets it to **forbid**: any `llm.generate` call raises
`ModelCallForbidden`, is counted, and fails the step with a `rung_violation`. A throwing callback is enough for
Action-only use (`hands-on`, `SPK/spike-v4-followup.mjs`). This turns "L1/L2 make zero generative calls" from a
spike observation into a production invariant, and it catches a stray `selfHeal:true` or a string `act` that slipped in.
The shim's counter is the ground truth for the System-1 share metric (DEC D7; CON O-15), not `stagehand.metrics()` (which
agreed with it in the spike). The forbid-mode proof is specific to Stagehand's callback. For the fleet executor, MIL G3.3
is restated structurally (scenario S14-10): its process imports no model client, plus a recorded allow-list of the CDP
methods it sends.

### 6.4 What exists, and where the shim runs

`SPK/openrouter-llm.mjs` is a working adapter (OpenRouter, `require_parameters`, reasoning, `max_tokens`, counting). It
has no response validation, no retry, no allowlist, no per-name caps and no `arguments` fix. It is a start, not the shim.

**Where it runs (settled by ARCH §1.1, §2.5 and CHT invariant 9).** The shim is a fleetd component (ARCH C9). Provider
keys live there and nowhere else. The worker's `generate` callback does not call a provider: it relays the request through
the sidecar's relay and the node agent to fleetd, with a short-lived, job-scoped credential, and returns fleetd's
validated answer. Nothing in an identity's network namespace holds a model key or has a route to a model provider; the
namespace's only egress is the identity's proxy (ARCH §2.2). Prompts therefore leave from fleetd's IP, not the identity's
(DEC D6). This matches the recommendation in an earlier draft of this page.

One consequence to design for: every model call now crosses the relay and the node-agent channel, so its latency adds to
the 1.7 s p50 measured with a direct call (`to measure`, M3 G3.5 / G3.9). The relay's path is not yet specified in ARCH.

### 6.5 Measured model behaviour (GLM 5.3 Flash at `low`)

- 22 of 22 Stagehand `json_schema` calls parsed (the "26 of 26" in DOS counts four v3 agent tool calls too). VER V-8.
- False `null` on an existing element: 3 of 13 act inferences on loaded pages (23%). All three were on the v3 prompt
  path (v4: 0 of 6; v3: 3 of 7), so provider and prompt path are confounded. Retry-on-null stays. VER V-8.
- Defects on click acts of a 6k-token page: 4 of 52 runaways (7.7%, Wilson 3-18%); 6 of 80 including junk arguments
  (7.5%); every one on two provider/task pairs. Plan for about one defective act in 13 on dense pages until the
  provider-pinned bench says otherwise. RMV REA-3; CON C-22.
- All of it ran on local Chrome on a Mac or a Steel container on arm64, with public test pages. Nothing ran on a
  social site, and none ran with a proxy. GLM throughput for 100-1,000 agents is unmeasured (DEC D8).

---

## 7. Self-heal, per version

| | v4.2.0 (the pin) | v3.7.3 (not used) |
|---|---|---|
| Switch | `selfHeal` (TS) / `self_heal` (Python) on `create`. Not per call. | `selfHeal` option |
| Default | **false** (`actService.ts:77`) | **true** (`this.opts.selfHeal ?? true`, `v3.js:729`) |
| What it does | Only for `act(Action)` whose selector no longer resolves: re-infers with the model and retries **once** (`https://docs.stagehand.dev/v4/basics/act.md` lines 585). Measured: 1 call, healed, `success:true` | Same, and on a cache replay: waits up to 15 s per cached selector, heals, **rewrites the cache entry** |
| With it off | Stale selector: `success:false`, 16 ms, 0 calls | n/a |
| Silent wrong-element click | **Not caught.** Heal triggers only on failure to resolve, never on resolving to the wrong thing | Same; proven once (`/tag/love/` instead of `/page/2/`) |
| Server cache replays | Self-heal always off, then fall back to full inference (Browserbase only, §9) | n/a |

Fleet rules:

- `selfHeal:false` everywhere, set explicitly in the wrapper. With it on, a failing Action silently becomes a model
  call, which breaks the System-1 share and the zero-call guard.
- The fleet's "heal" is a deliberate, logged climb: a verified miss at L1 → L2 decider on a fresh snapshot → L3. The
  healed Action becomes a *candidate* cache entry, not an overwrite (§9).

---

## 8. Variables and secrets

How it works, `hands-on` + `source-code` (VER SH-5):

- `variables: { name: "value" }` (or `{ value, description }`). The instruction uses `%name%`. Only the placeholder is
  in the act prompt; the extension substitutes the value just before executing. The returned `actions[].arguments`
  keep `%name%`. Measured: the canary was absent from the act prompt and was typed correctly.
- `observe` sends variable names and descriptions, not values.
- **The leak:** after typing, the value is in the accessibility tree as a `textbox` value. The next `observe`, string
  `act` or `extract` on that page sends it to the model. Measured: the canary appeared in the follow-up observe prompt.
  `<input type=password>` values do **not** appear in the tree (one synthetic field).
- With Browserbase server caching on, variable *values* go to Browserbase (`cacheService.ts:84-94`). The fleet never
  enables it (§9).
- The vendor docs show passwords passed as variables (`https://docs.stagehand.dev/v4/basics/act.md` lines 679-708). **The fleet does not.**

A `research` identity has no login, so there is no credential to type and nothing here should come up. The findings
above stay because the leak path exists for any typed value, and because they bound what Stagehand may do if account
use is ever cleared. Fleet rules:

1. **Agents never type credentials** (DEC D14). A human logs in through the brokered live viewer. `variables` is not a
   login mechanism. The executor refuses `fill`/`type` into `type=password`, `autocomplete` of
   `current-password`/`username`/`one-time-code`, and fields whose names match login or OTP patterns, and answers
   `needs_reauth` (ARCH §4.3). The viewer path is itself untested for special keys, IME, passkeys and dialogs (M1 G1.5).
2. **Infer first, type second.** For text that must not reach a model (DM drafts, client data): run `observe` for the
   target with no text in the instruction, then `act(Action{method:"fill", arguments:[text]})` with code-supplied text.
   Do not call string `act`, `observe` or `extract` on that page again until the field is submitted or cleared.
3. Use `ignoreLocators` on composers when an inference is unavoidable after typing.
4. Content to publish comes from an approved manifest (DEC D13), never from page text.
5. `variables` may carry non-secret placeholders in L3 steps. The decider path never needs them: the text goes straight
   into `arguments[0]`.

---

## 9. Caching: none locally; what the fleet builds instead

### 9.1 What v4 has

- **A Browserbase server-side cache only.** On any other browser the `cache` option does nothing and every call runs
  inference (`https://docs.stagehand.dev/v4/best-practices/caching.md` lines 20; `https://docs.stagehand.dev/v4/configuration/browser.md` lines 636).
- In code, `buildCacheContext` returns `undefined` unless the SDK has a Browserbase `apiKey` **and** a
  `browser.sessionId`, and only the `browserbase.*` factories set a session id. On Steel, `metadata.cache.status` is
  `DISABLED` on every primitive. Measured: the same `act(...,{cache:true})` twice made 2 model calls. `hands-on` +
  `source-code`; VER SH-1 (confirmed; also checked in the 4.2.0 bundle).
- A self-hosted cache cannot sit behind the seam: `apiUrl` is configurable but a local browser cannot be given a
  session id (`StagehandClientCreateConfigSchema` omits `browser`). You would have to fork the SDK and reimplement
  Browserbase's private `/v1/cache/get|set` contract. DOS Q5.
- **Privacy.** When it is on, the cache request carries the raw accessibility tree of every frame (DMs and feeds
  included) and the `variables` *values* to Browserbase (`cacheService.ts:84-94`). DOS Q5.
- **Fleet default: never pass `cache`, never set `apiKey` or `apiUrl` in `Stagehand.create`, on every home.** That
  includes Browserbase-home identities (DEC D11 calls the server cache "a weak reason" to choose Browserbase; privacy
  adds a reason to leave it off). This is a recommendation, not yet a recorded decision. `design`.
- Consequence for planning: the cost model's 40% "cached" action share is the fleet's own L1 replay hit rate, assumed,
  for a cache that does not exist yet (CON C-05). Treat every "cached" saving as a hypothesis.

### 9.2 What v3's `cacheDir` did (reference design only)

Key `sha256({instruction, normalizedUrl, sortedVariableKeys})`; file `<cacheDir>/<sha>.json` with the Actions; replay
waits up to 15 s per cached selector, self-heals, and rewrites the entry; a failed replay returns failed with no
fallback to fresh inference. Zero model calls on a hit (act 0.50 s, agent 1.2 s). `source-code` + `hands-on`, DOS Q5.
Proven hazards: a stale xpath cost 16-23 s and a model call; an xpath that now pointed at a **different** link returned
`success:true`, 0 calls, wrong page (`hands-on`, once, precondition hand-built; the mechanism is deterministic from
source: VER SH-8). The **agent** cache re-executes only mutating steps and returns the first run's text answer with
usage zeroed (VER missed issue 1). Its `configSignature` records the default model, not the custom one used.

### 9.3 What the fleet replay cache must do differently (`design`, unbuilt)

Scope: this is what the Stagehand adapter and the cache must do around `act(Action)`. It applies on `research`
identities and, **account use, if cleared**, on an account site class that G1.4 admits Stagehand on. Under DEC D18 the
stored L1 entry is the fleet's own Action (method, arguments, element identity: role and accessible name, frame path),
not Stagehand's `Action`, snapshot or `xpathMap`; the adapter turns an entry into a Stagehand `Action` when it replays.
Reads are never cached, and `research` work is mostly reads, so the cache matters less there; the check-before-click
rules below apply to every `act(Action)` anyway.

| v3 `cacheDir` | Fleet replay cache |
|---|---|
| Stores an instruction's Actions | **Stores Actions per procedure step**, not instructions (DEC D5) |
| Key: instruction + URL + variable names. No check of the page | Key: procedure step + URL pattern + element fingerprint (role, accessible name, nearby text, frame path). The model is not in the key |
| Replays whatever sits at the xpath | **Verify before every replay:** fresh `page.snapshot()` (0 model calls, 0.2-1.3 s); find the stored xpath in `xpathMap`; compare that line's role and name with the stored fingerprint. Mismatch is a miss, never a click (DEC D5). The check is **not atomic with the click**; see "Verify-then-act is not atomic" below |
| `success:true` on the wrong element | Policy checks the *verified* element, then the executor checks the **outcome** after acting (URL, expected element, read-back receipt: DEC D13). `act(Action)` skips the settle wait, so the outcome check waits on its own condition |
| Waits up to 15 s on a stale selector | Short explicit `timeout`. A stale entry should fail fast (v4 with `selfHeal:false`: 16 ms) |
| Heals and rewrites the entry in place | A heal is a **new candidate**; the old entry keeps serving until the candidate is released by D13's rules (three distinct owner-accepted outcomes) and can be rolled back per procedure |
| A failed replay is just failed | A miss climbs L2 (decider) then L3 (`observe`), each rung logged |
| Agent cache returns the first run's answer | **Reads are never cached or replayed:** `extract`, notification checks, profile reads are always fresh |
| Variable *values* not stored (good) | Content arguments are stored as placeholders. Publishable text comes from the approved manifest at run time (DEC D13), never from the cache |
| A file on the worker's disk | A fleetd store, scoped per client and site. Obsidian holds memory, not this cache (DOS §3) |
| Records the wrong model | Records the real rung, model and serving provider that produced the entry |

Entry sketch (`design`): `executor_id, schema_version, procedure_digest, step_id, url_pattern, frame_path,
action{selector, method, arguments_template, description}, fingerprint{role, name, near_text_hash},
origin{rung, run_id, model, provider}, state{candidate|released|quarantined},
counters{replays, verified, mismatches, outcome_failures}`.

- The sketch is the Stagehand adapter's view. The `selector` is Stagehand's positional xpath, kept as a hint: the fleet
  verifies it against the entry's element identity and treats a mismatch as a miss. `executor_id` and `schema_version`
  are part of the key (DEC D18; MIL G3.13): an entry written under another executor or version is never served and never
  converted; a changed executor rebuilds on first use.
- State names differ from ARCH §3.9 (`candidate|released|retired`). Scenario S06-6 asks for one machine
  (`candidate → released → quarantined → retired`); ARCH settles it and this sketch follows.

**Verify-then-act is not atomic (scenario S06-11).** Verification is one call (a snapshot, 0.2-1.3 s) and the click is
another. `act(Action)` takes `{selector, description, method, arguments}` and is one RPC to the extension, which then runs
several internal steps (`source-code`, read for this revision in the installed 4.2.0 `dist/extension/service-worker.js`:
`takeDeterministicAction` → `performUnderstudyMethod` → `resolveLocatorWithHops`, then a `location.href` read in the frame,
then the method handler). No argument, option or hook carries an expected role or name. So the public API cannot say
"click this xpath only if it still has this role and name", and the window inside the extension is several steps wide,
not one. On a page that re-renders (an SPA), a different node can come to
sit under the same positional xpath between the snapshot and the click. Gate G's post-condition sees that only after the
click. The fleet narrows the window and says plainly that it cannot close it:

1. **Freshness bound.** The verifying snapshot must have finished no more than `T_fresh` before the `act(Action)` call
   is issued. If it is older, discard it and snapshot again; never act on an old check. `T_fresh` is `to measure`
   (§17 smoke test ST-5b; it depends on how fast the target sites re-render). Starting value 500 ms (`estimate`, a
   guess, not a finding).
2. **Nothing slow in between.** From the end of the verifying snapshot to the act call: no fleetd round trip, no model
   call, no sleep, no waiting on a human. Whatever needs fleetd (authority, governor reserve, intent row) runs before the
   snapshot. *Proposed (account use, if cleared; ARCH §3.6 and §4.3 to confirm):* if verification then fails after an
   intent row exists, no click was sent, so the effect is closed as not performed rather than held. ARCH §4.3 lists gate
   G's steps with the intent row after the content check; whether that order can be kept is ARCH's call (§15, row 8).
3. **A cheap second read right before the act.** Re-read the node the stored xpath resolves to now (a locator read or a
   `page.evaluate` returning tag, `role`, `aria-label` and text) and compare with the fingerprint's name text. Any
   difference is a miss. It is a second source of truth beside the accessibility tree, so it can only add misses and
   never overrides a snapshot mismatch. It costs one CDP round trip (`estimate`: tens of milliseconds; `to measure`).
   It shrinks the window to the single `act(Action)` call (0.28-0.46 s end to end in the spike; the part between the
   xpath resolution and the mouse event is not separately measured). It is not atomic.
4. **Effect steps do not rely on timing.** *Account use, if cleared.* DEC D5 (scenario S06-1) now requires every effect
   step to carry a `target_rule` (role, name pattern, region or frame) in its released procedure, and stops the ladder at
   L1 for such steps. ARCH §3.7 procedure `steps[]` had no such field when read (a field of the same name sits on manifest
   items, with no stated meaning), so ARCH has to adopt it (§15, row 10). The verification step checks the resolved
   element against the rule; the pre-submit content check, the post-condition, the read-back and the intent row stay;
   and a repaired target on an effect step is confirmed by a person before its first live click (D5). None of this
   closes the race. It bounds what a lost race can click, and it makes sure the loss is seen. An irreversible step whose
   outcome cannot be verified is held (DEC D13).
5. **The route that shrinks it further is not Stagehand's.** A fleet-owned CDP executor can resolve one backend node,
   read its accessibility role and name, take its box and dispatch the mouse event in back-to-back commands, with no
   xpath re-resolution and no extension hop, then check what sits at the click point. That is tighter, not atomic: the
   page can still change between commands, and nothing over CDP is known to remove that (`to measure`). It is the
   minimal CDP executor of DEC D18 (MIL P3.5: built by default for `account` identities unless G1.4 admits another executor for every account site class; owner and language pending DEC Q-15). Not built.
6. **Where this bites.** `research` identities have no effect steps (lead-gen playbook §0 item 4, §3.7: no form
   submission of any kind). There the risk is a navigation click that lands somewhere the `read_only` allow-list would
   have refused (illustration, not observed: a "Subscribe" button that moved under the xpath), and the gate judged the verified element, not the
   clicked one. Requirements 1-3 apply there. Effect steps exist only if account use is cleared, and then clearing it
   must say how requirements 4 and 5 are met.

Open, `to measure`: which steps of real procedures are cacheable at all. Stable anchors (composer button, nav links) are;
the Nth post in a feed is not, and "nearby text" must not include text that changes per visit. The held-out measurement
that closes the 90% hypothesis (DEC D7; CON O-15) is also what measures this.

---

## 10. Tabs, iframes, shadow DOM, composers, uploads, scrolling

Everything measured here ran on public test pages with 0 model calls (the Action path). **Nothing ran on X, Facebook,
Instagram, TikTok or LinkedIn**, and nothing was run on a proxied or headful browser.

For `research` identities the rows that matter are tabs, iframes, shadow DOM, scrolling and overlays. Rich-text
composers and file uploads are **account use, if cleared**: a research identity posts nothing and uploads nothing
(lead-gen playbook §0 item 4). Those rows stay because they record what was measured and what an account executor of
any kind will have to prove on real composers.

| Topic | Measured (`hands-on`) | Known issues / caveats | Fleet rule |
|---|---|---|---|
| **Tabs** | Clicking a `target=_blank` link took `context.pages()` from 1 to 2, and `activePage()` followed the new tab | The active page is the tab Chrome has focused last (`https://docs.stagehand.dev/v4/best-practices/using-multiple-tabs.md`). A `page` captured before the click still points at the old tab | After any click that may open a tab, re-read `activePage()`. Pass `page` explicitly on every call. Close stray tabs. The SDK allows parallel calls on several tabs; **the fleet runs one step at a time per identity** (DEC D12 lease) |
| **Iframes** | `snapshot({includeIframes:true})` shows child-frame nodes with a frame ordinal. A cross-frame xpath from `xpathMap` filled a contenteditable inside a **same-origin srcdoc** iframe | #870 (open): nested iframes with `observe`. #2324 (closed): cross-origin iframe still loading. 4.2.0 fixed locator failures when entering loading iframes (#2978). Cross-origin and nested frames on real sites were not tested | `includeIframes:true` only when needed. Replay across real cross-origin frames is an M1 gate (DEC D5) |
| **Shadow DOM** | Shadow-root and slotted text appear in the snapshot | #2693 (open): once any shadow root exists, xpath resolution switches to a composed-tree parser that ignores unsupported predicates. 4.2.0 fixed `text()` predicates only (#3052) | Use only xpaths that Stagehand produced. Never hand-write predicate xpaths. Acting *inside* a shadow root was not tested |
| **Rich-text composers** (account use, if cleared) | `fill` on a contenteditable returned `needsinput`, then issued **`Input.insertText`** (trusted input). On a synthetic composer: `beforeinput:insertText:true` and `input:insertText:true`; emoji and hashtags set. `type` dispatches per-key events | Lexical (Facebook) and Draft.js (X) expect this event shape, but **were not tested**. Mention and hashtag popups are untested | Target the `textbox` node. Read `innerText` back after `fill`. Treat any mismatch as `outcome_uncertain` (DEC D13). Real composers are an M1 gate. Social posting is API-first anyway (DEC D2) |
| **File upload** (account use, if cleared) | `locator.setInputFiles(path \| {name, mimeType, buffer} \| [...])` reads the file in the SDK process and sends base64 over CDP. A **26-byte** file attached over remote Steel | Cap in code: 50 MiB per file. One 50 MiB file is about 67 MB of base64 in one CDP message through Steel's WebSocket proxy: untested. #972 (open): `observe` cannot see `input[type=file]` | Small files in-band only until M1 finds the ceiling. Videos: Steel files API (`POST /v1/sessions/:id/files`) plus raw CDP `DOM.setFileInputFiles` on the container path. **Fleet-built, unverified.** Target the input by selector, not by `observe`. Upload only manifest assets (DEC D13) |
| **Infinite scroll / feeds** | `act({selector:"xpath=/html", method:"nextChunk"})` three times took items from 3 to 6; `mouse.wheel` also worked | Stagehand does not loop for you | The fleet writes the scroll-until-N loop: count items with `page.evaluate`, stop at N, dedupe, apply cadence and rate limits (DEC D9) |
| **Date / time inputs** | not tested | #908, #1249 (open) | Set them with a pinned deterministic locator step |
| **Overlays and modals** | not tested | A promo modal can swallow clicks | `ignoreLocators` for model calls; a deterministic dismiss step for the modal |

Sources: DOS Q7, Q11; SPK `RESULTS.md` finding 5; VER SH-7; `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md`.

---

## 11. Concurrency, lifecycle and recovery

**One Stagehand instance per browser, enforced.** A second `Stagehand.create` on a live browser fails with
`A Stagehand instance is already initialized`; after `close()` a new one attaches. v3 has no guard (two controllers
attached and could fight). `hands-on` + `source-code`, VER SH-6.

- One instance can work several tabs through `page`. The unit is: identity = one Steel container = one browser = one
  Stagehand instance = one lease holder (DEC D4, D12).
- **The executor checks the fencing token** before each command it sends, not only at start (DEC D12: the token is
  checked by whatever executes the effect). `design`.
- **Overhead.** Node SDK process about 98 MB RSS, flat across attach and snapshot (n=3); Python 4.2.0 peaked at 55 MB
  but has no saved output; the extension's service worker used 25 MB heap (34 MB total); a snapshot takes 0.2-1.3 s of
  browser CPU; the browser (about 700 MB in this container, no raw artifact) dominates. `hands-on`; VER V-10.
  scale-infra's planning slot reserves 0.35 GiB for the agent runtime (an `estimate`, `research/dossiers/scale-infra.md`
  line 43); one executor process fits inside it. One process can hold several instances; the per-extra-instance cost
  was not measured.
- **The lock is released only by an explicit `stagehand.close` RPC.** The extension-side client closing only rejects
  pending requests, and an offscreen heartbeat keeps the service worker alive. The verifier found nothing that detects a dead
  SDK and frees the lock. So **a crashed or killed executor probably wedges the browser** for the next `create`
  (`source-code`, VER SH-6 and missed issue 3; **unverifiable without a droplet**).
- **Recovery ladder (`design`, all unverified).** ARCH §4.10 says "recreate the Steel session, not the container".
  That needs care, because a bare `POST /v1/sessions` does one of two things: with the same config it **takes over the
  live Chromium** and the extension's lock stays held; with a different config it **relaunches Chromium**, which clears the
  lock but drops in-browser state (STV STE-1). So:
  1. The fleet's lease says no live worker holds this identity, yet `create` says "already initialized": it is a wedge.
  2. Try a raw `stagehand.close` JSON-RPC to the service worker, then `create` again (VER missed issue 3).
  3. Otherwise read ARCH §4.10 as "release, then create": the ARCH §4.9 order (hold the lease, export the session context,
     wait for 31 s of quiet, raw CDP `Browser.close` by the node agent, Steel release), then a fresh create. Not a bare
     recreate, and not `docker stop` (SIGKILL, leaves the lock: DEC D4).
  4. Rerun the step only if it is a non-effect step. An effect in flight follows the ledger (`outcome_uncertain`, hold).
- **Order at the end of a window:** finish or abandon the step → `stagehand.close()` → (only if M1 shows it works)
  extension cleanup → node agent runs the D4 release. Stagehand never stops the browser.
- **Time budget.** A Hermes tool call is designed to a 90 s budget (DEC D1). A string `act` is 2.5-5 s and a verified
  Action about 1 s, so single steps fit; any procedure with more than a few steps runs as a fleetd job that the profile
  polls (DEC D17).
- **Timeouts to set explicitly:** `snapshot` 20 s default, locator calls 20 s default, `act/observe/extract` `timeout`
  option, `goto` (the-internet `/key_presses` timed out at 15 s `domcontentloaded` in the main v4 run: VER missed
  issue 10). An effect step that times out is `outcome_uncertain`, never retried blindly (DEC D13).

---

## 12. Observability

What Stagehand 4.2.0 gives (`source-code` DOS Q8; `official-docs` `https://docs.stagehand.dev/v4/configuration/{logging,observability}.md`):

- Per result: `metadata.usage` (tokens, `inferenceTimeMs`) and `metadata.cache`. No dollars.
- `stagehand.metrics()`: cumulative counters per instance (prompt/completion tokens, inference time). It agreed with the
  shim's count in the spike.
- `logging: { level, format, onLog }` (Python: `on_log`). The callback runs *in addition to* console output. `off`
  silences both. #3035 (open): `onLog` cannot be used without also writing to stderr, so route the executor's stderr
  into the container log.
- `page.screenshot()`, `page.pdf()` (4.2.0).
- **No `history`, no inference-to-file log, no recording in OSS v4** (those were v3 or Browserbase). Steel's recorder
  extension (headless only) posts to `/v1/events`, in memory unless `LOG_STORAGE_ENABLED` (STD Recordings row); the fleet
  does not rely on it.
- OpenTelemetry `telemetry: {traces: {endpoint}}` exists, but the exporter runs **inside the extension**, so traces would
  leave through the browser's network and the identity's IP. Telemetry stays off unless an OTLP endpoint is set
  (4.2.0 #3045). **The fleet never sets it.**

What the fleet records (`design`; the shim and executor are the source of truth, not Stagehand):

| Record | Fields |
|---|---|
| Step journal | run id, identity, procedure step, rung (L1/L2/L3), Action (selector, method, argument *template*), fingerprint verdict, policy verdict, outcome verdict, `success`, message, timings |
| Model ledger | per call: name, model, serving provider, `finish_reason`, tokens, `usage.cost`, validation verdict, retries; per profile and per day |
| Evidence | screenshot on failure; snapshot **hash** by default. Full trees contain DMs, so storing them waits for an evidence-retention policy that DEC does not yet have |
| Rates | System-1 share per procedure; L1 mismatch rate; act defect and false-null rate per provider; shim retry rate; latency per rung |

---

## 13. Why Stagehand is not loaded on `account` identities by default

One measured trip, read cautiously. It is not a finding that any platform punishes it: whether Meta, TikTok, X or
LinkedIn weigh the signal is unknown (APV AP-2; CON C-13). An account is the asset and a research identity is not, so
DEC D18 keeps the extension off `account` images and wakes (§3), and Stagehand runs on `research` identities.

### 13.1 What was measured (`hands-on`, n=1 per condition, stock Chromium 152, public detector page)

- Stagehand v4 trips `isAutomatedWithCDP`: the extension sends `Runtime.enable` on page sessions and
  `Target.setAutoAttach{waitForDebuggerOnStart:true}` for every new target. After `stagehand.close()` it stays loaded and
  keeps tripping new tabs (seen about 40 s later). `Extensions.uninstall` or a browser restart cleared it; a CDP-loaded
  extension is not persisted. APV AP-2.
- Browser-Use 0.13.11 attach + navigate + state did not trip it. Its actor API, the MCP coordinate click and the Anthropic
  computer-use integration do. APV AP-3. Behavioural input timing was not tested for any executor.
- No `web_accessible_resources`, so `chrome-extension://` URL probing cannot see it (`inference`). Content-script and
  offscreen side effects are not measured.

### 13.2 Why it does not transfer to Steel

AP-2 used a CDP-loaded extension. Steel loads it with `--load-extension` (mode A, steel.md §9.1). Unknown: (1) whether
`Extensions.uninstall` removes a flag-loaded extension; (2) whether a restart drops it (`inference`: the flag re-adds it);
(3) whether a session can re-attach after an uninstall in the same process (a runtime `loadUnpacked` on Steel returned an id
but never ran: SPK findings 1-3). If not, "uninstall after each session" means a browser relaunch per window. DEC D6 lists
uninstall-after-session as a candidate; on Steel it is unproven.

### 13.3 What would admit Stagehand on an account site class (`to measure`; droplet; Q-12)

MIL **G1.4** (as revised for scenarios S14-5 and S14-6) owns the measurement: three executors, each alone, inside the real
stack and on behavioural input; Stagehand loaded the way the fleet loads it (`--load-extension`), with `Extensions.uninstall`
on that flag-loaded extension tested first; a `research` arm with the extension on and off; and an outcome table. The first
row of that table is the one that would keep Stagehand on accounts: uninstall removes the trip and the stack stays clean
afterwards. Two Stagehand-specific checks G1.4 does not list, to add (on amd64, CON O-17):

1. **Re-attach** after an uninstall, without a relaunch. If it needs one, "uninstall after the session" costs a browser
   relaunch per window (that is the price of the mitigation).
2. **Extension visibility:** a probe page requesting `chrome-extension://<id>/…`; content-script side effects on timing and DOM.

The research arm in G1.4 reads public test pages. A bot-wall and extraction-yield figure on real company sites waits for N-4
(live runs there need Justin's yes). Real-site checkpoint rates on accounts wait for the pilot milestones (MIL M6a, CON O-13).
No threshold is set here.

Output: executor per identity kind first and site class second, written into the router and DEC D6 (CON O-02, as updated
by D18). **Until it says otherwise, Stagehand does not run on `account` identities**; a site class where no executor passes
is handled by the G1.4 outcome table (API only plus a person's clicks, or the owner's written acceptance in the risk register,
R-42). If the trip holds on the full stack and no mitigation removes it, accounts keep the minimal CDP executor (MIL P3.5)
and L3-lite (DEC D18).

### 13.4 Mitigations, cheapest first (`design`)

1. **Do not load the extension on `account` wakes.** DEC D18; derived by identity kind in the node agent (§3).
2. Treat a Stagehand window as the unit; restart the browser afterwards if the extension cannot be removed cleanly.
3. `Extensions.uninstall` after `stagehand.close()`, only if 13.3 shows it works on a flag-loaded extension (mode B is the
   untested variant).
4. Route detection-sensitive actions to Browser-Use `Tools.act` or the minimal CDP executor. DEC D18's default for accounts.
5. Patched kernel (e.g. CloakBrowser): Stagehand needs Chromium ≥ 149, the extension on the host filesystem, an
   in-browser-resolvable CDP URL and an admitting `--remote-allow-origins`. It hid Playwright's `isAutomatedWithCDP`
   (APV AP-8); whether it hides Stagehand's extension is untested. Proprietary, and spoofing. `pending Q-02, Q-03, Q-04`.

---

## 14. Failure modes and the fleet's handling

An effect that might have happened is never retried blindly: it becomes `outcome_uncertain` and is held for
reconciliation (DEC D13). Errors the profile sees are the answers in DEC D17 (`infra_unavailable`,
`outcome_uncertain`, `needs_reauth`, `checkpoint`, `needs_approval`, `budget_exhausted`, ...).

| # | What you see | Cause | Fleet handling |
|---|---|---|---|
| F1 | `File path cannot be resolved.` from `localBrowser.connect`, in ~36 ms | No Stagehand extension is installed in the browser, so the SDK asks the browser to load one from the SDK host's path | The wake's pre-handoff check (extension listed at the pinned version) should have caught it. Fail the wake as `infra_unavailable`; alert a maintainer. Do not "fix" it with `STAGEHAND_EXTENSION_DIRECTORY_PATH` (SPK findings 1-3) |
| F2 | `connect` hangs about 60 s, then times out | The extension was loaded at runtime but Steel's `--disable-extensions-except` disabled it: the session was created without `extensions:["stagehand"]` | Same as F1. Give `connect` and `create` explicit deadlines far below the 90 s tool budget |
| F3 | `CDP websocket failed to open` from `Stagehand.create` | The extension cannot dial the SDK's URL from inside the browser: wrong host or port (§3 step 3), a non-loopback host sent through the proxy, or Chromium refused the `chrome-extension://` Origin (`--remote-allow-origins`) | `infra_unavailable`. Check the layout (L-A/L-B), the live argv, and the proxy path. Smoke tests ST-2, ST-12 |
| F4 | `Method not available.` from `Extensions.*` | Kernel is Chromium ≤ 146 (147-148 gated). APV AP-1 | Cannot happen on Steel's Chromium 152. On a vendor or patched kernel below 149: route the profile to Browser-Use |
| F5 | `A Stagehand instance is already initialized` | Another instance holds the lock, or a previous executor died without `close` | §11 recovery ladder. Never a bare `POST /v1/sessions` |
| F6 | `An LLM was not configured` | No `model` was passed. Act/observe/extract throw even for Action-only use | The wrapper always passes the shim (in forbid mode on L1/L2) |
| F7 | `act` returns `success:false`, "No action found" | The model answered `null`. Often correct; also a false null on 3 of 13 loaded-page acts (VER V-8) | Retry once on another provider. If still null, report "target absent" to the ladder or Hermes. No blind escalation to a stronger model (RMD §4) |
| F8 | `act(Action)` returns `success:false`, "Could not find an element", 0 calls | Stale xpath (16 ms with `selfHeal:false`) | A verified miss: mark the cache entry, climb to L2/L3 on a fresh snapshot. No silent heal |
| F9 | `act(Action)` returns `success:true`, but the wrong element was acted on | A positional xpath now resolves to another node, including after a good check: verification is not atomic with the click (§9.3). Stagehand cannot see this | Fingerprint check before, with a freshness bound and a second read right before the act; policy on the verified element; outcome check after. Effect steps (account use, if cleared) also need a step-level `target_rule` (S06-1, not yet in the design). If an irreversible step's outcome cannot be verified, hold it (DEC D5, D13). The highest-severity failure here |
| F10 | A model call runs to `finish_reason=length` (34-52 s at an 8k cap) | Constrained decoding degenerates inside `arguments` (7.7% of 6k-page click acts, two provider/task pairs: RMV REA-3) | Mandatory `max_tokens` per call name; retry once on another provider; per-provider bench |
| F11 | Non-JSON, fenced, YAML-at-200, or pattern-violating output | Provider enforces `json_schema` incompletely (RMV REA-7) | Shim validates the full schema; retry on another provider; repeated offenders leave the allowlist |
| F12 | Junk click argument (`"],"`, `"LEFT"`) | Same degeneration | Shim keeps `arguments[:1]`, normalises only a click's button (DEC D8) |
| F13 | `goto`, `snapshot` or a locator call times out | Flaky or heavy page; the test page `/key_presses` timed out in one run (VER missed issue 10) | Explicit timeouts. Read steps retry once. An effect step is `outcome_uncertain`, not retried |
| F14 | Executor dies mid-step | OOM, deploy, host loss | The lease expires; §11 recovery ladder. Any effect in flight is `outcome_uncertain` and held |
| F15 | The browser vanished after the executor finished | Someone called `browser.close()` (it sends `Browser.close`) | Forbidden by wrapper and unit test. If it happens, treat as an unclean stop and run DEC D4's restore path |
| F16 | The CDP link drops mid-request | Chromium restart, node trouble; the v3-lineage crash is #2910 | `outcome_uncertain` if an effect was in flight. Re-verify identity values (UA, exit IP, profile dir: DEC D3) before reuse |
| F17 | Network errors from the page after an IP change | The forwarder failed closed (DEC D10) | `infra_unavailable`. No retries until the identity check passes |
| F18 | Attach rejected: SDK and extension disagree | Runtime compatibility check | One pin file builds both images (§17). Smoke test ST-1 |
| F19 | A login wall, checkpoint, 2FA or CAPTCHA appears | Stagehand does not detect these | The fleet verifier (page-state check before and after steps) stops the run. On a `research` identity: stop that domain, record `login_wall` or `captcha`, never sign in, never solve (lead-gen playbook §3.8). On an account (account use, if cleared): `needs_reauth` or `checkpoint`, owner notified with a fresh viewer link. Agents never type credentials or solve CAPTCHAs (DEC D14) |
| F20 | The model picks a button the page text told it to pick | The accessibility tree is untrusted input to the model | Instructions come from procedure templates, never page text or free Hermes text. Irreversible steps are gated by deterministic policy on the verified element. Publishable text comes from the manifest; the executor discards the model's `arguments` for `fill`/`type` on content-bearing steps (§5.7, §17) |
| F21 | Upload fails or stalls; screenshot call errors | 50 MiB cap, one huge CDP message (untested), base64 regex overflow above ~6 MiB (#3060) | Small files in-band; videos via the Steel files path (unverified); no full-page screenshots of huge pages |
| F22 | Navigation outside the allowed sites | Stagehand's `setDomainPolicy` is bypassed by service-worker fetches and WebSockets (#2945, open) | Scope is enforced by fleetd and the in-browser Guard, never by Stagehand |
| F23 | A model call on an L1/L2 step | `selfHeal:true`, or a string `act` slipped in | Forbid-mode raises `ModelCallForbidden`; the step fails as a `rung_violation` and is logged |
| F24 | `observe` misses a file input; date inputs misbehave; nested iframes | #972, #908/#1249, #870 (all open) | Deterministic locator steps for these |
| F25 | Stagehand attach or calls fail only when the guard runs | The guard's `Fetch.enable` interception (every tab, frame and worker) interacts with the extension's loopback WebSocket or its own fetches. ARCH §2.2 lists it as an open M1 interaction | Smoke test ST-12 runs with the guard on. If the guard must exempt the extension, that exemption is a charter-level change (CHT: never loosen a guard), so it needs Justin's yes |

---

## 15. Pending Justin's answers

Written for the recommended default of each question in DEC. If an answer changes, the listed spots change.

| Q | What it decides | Spots in this page |
|---|---|---|
| Q-01 | API-first (recommended) or browser-first for client social | Scope box, §10 (composers), §13: how much account-browser work exists, and so how much the account executor matters. Stagehand's research scope does not change with Q-01 |
| Q-02 | Anti-detect: continuity only (recommended) or buy | §13.4 |
| Q-03, Q-04 | A proprietary patched kernel; spoofing stance | §3 (kernel rule), §13.4 item 5 |
| Q-06 | Monthly caps for model spend, proxies, droplets | §6.2 item 14 |
| Q-07 | Zero-data-retention routing and/or per-client consent | §6.2 item 13; the provider allowlist and the bench |
| Q-08 | Steel's Chromium non-root with sandbox on, or accept the risk | §3 step 1 (extension readable by the non-root user); the smoke test must pass after the change |
| Q-11 | Jev Workforce trial path (owner-approved `native_guide` prose, no plugins) | §17: trial guides carry no executable authority and can only describe fleetd tools |
| Q-12 | A capped throwaway droplet for M1 hands-on | §13.3, §11 recovery, §17 smoke test: nothing marked `to measure` closes without it |
| Q-13 | Cross-client unlinkability (one client per node) | §11 sizing: executors per node |
| Q-09 | Keep `fleet/` out of box-kit's public export, or move it to a private repo | This page names providers, internal paths and unreleased design. It must not leave through that export |

Q-05, Q-10 and Q-14 change nothing on this page.

### Where this page adds to, or departs from, ARCHITECTURE.md

ARCHITECTURE.md is the authority for components, and it still has pending sections (its §9, "Deviations from, and
extensions to, DECISIONS.md", and §10). These are the places where this page says something ARCHITECTURE does not, or
reads it differently. None of them changes a DECISIONS entry: this page follows D5, D6 and D18 as amended.

DECISIONS.md, MILESTONES.md and ARCHITECTURE.md were being revised in parallel for the same scenarios when this page was
revised. DECISIONS.md and MILESTONES.md had landed their S06 and S14 changes; the "ARCH says" column is ARCHITECTURE.md as
read then. Re-check rows 8 to 10 when its revision lands, and delete a row where ARCH has adopted it.

| # | Topic | This page | ARCH says | Where |
|---|---|---|---|---|
| 1 | Recovery from a wedged Stagehand lock | A bare "recreate the Steel session" either keeps the lock (same config takes over the live browser) or relaunches Chromium and drops in-browser state. Use raw `stagehand.close`, else release-then-create in ARCH §4.9's close order | §4.10: "Recreate the Steel session, not the container" | §11 |
| 2 | "Uninstall the extension after the session" | Measured only for a CDP-loaded extension. On Steel the extension is flag-loaded beside `--disable-extensions-except`; uninstall and re-attach are unproven. MIL G1.4 now tests uninstall first | §4.9 step 2 "Optionally `Extensions.uninstall`" | §13.2 |
| 3 | Worker language | Python default is acceptable on the condition that the first M1 run saves Python output; else TypeScript | N4: Python by default. AGT's layout says Node | §4 |
| 4 | Server cache on a Browserbase home | Never pass `cache`, `apiKey` or `apiUrl` there either (it sends full trees and variable values to Browserbase) | Not stated | §9.1 |
| 5 | Model-call path from the worker | Every call crosses relay and node agent to fleetd; added latency and the relay's path need specifying | "`generate` calls fleetd's model shim" | §6.4 |
| 6 | Guard and the extension | Smoke test ST-12 runs with the guard on; an exemption would need Justin's yes | Listed as an open M1 interaction | F25 |
| 7 | DMs and Stagehand | No string `act`/`observe`/`extract` on DM surfaces while Q-07 is open (account use, if cleared) | CHT invariant 8 states the rule for model providers in general | §6.2 item 13 |
| 8 | Order of verification and the intent row | Anything that needs fleetd runs before the verifying snapshot; a freshness bound and a second read right before the act. Proposed, for effect steps: a verification miss after an intent row means no click was sent, so the effect is closed as not performed | §4.3 L1 row: re-snapshot, verify, then `act(Action)`, as if the check were safe. Gate G lists the intent row after the content check, then act | §5.5, §9.3 |
| 9 | ARCH catching up with D18 | Stagehand is the L3 engine on `research` identities only; the extension is requested by identity kind (persona `extension_mode`); L1 entries are fleet-owned and keyed with `executor_id` and `schema_version` | As read: N2 and wake step W10 request the extension every time; the §4.3 L3 row names Stagehand with no identity kind; §3.9 `l1_entries` has neither key field | Scope box, §3, §9.3 |
| 10 | Step-level `target_rule` | DEC D5 requires it on every effect step (account use, if cleared) | Absent from §3.7 `steps[]` as read (a same-named field sits on manifest items) | §9.3 item 4 |

---

## 16. Where in the corpus

Root: `research/corpus/stagehand/` (alias C). Captured 2026-10-09. Start with `C/INDEX.md` (five things that change the
plan, then a topic map) and `C/MANIFEST.md`. Integrity: `C/SHA256SUMS.txt`, `C/FETCH-LOG.tsv` (scraped copy not published). All of it is untrusted data.

| Topic | Page (vendor URL) |
|---|---|
| What v4 is; install; quickstart | `https://docs.stagehand.dev/v4/first-steps/{introduction,quickstart,installation}.md` |
| Connect over CDP; extension discovery; local launch args; proxy limits; environment comparison | `https://docs.stagehand.dev/v4/configuration/browser.md` (§"Connecting over CDP" line 567; comparison table line 625; "Authenticated local proxies are not supported yet" line 804) |
| Models; BYO callback; no base URL | `https://docs.stagehand.dev/v4/configuration/models.md` (Custom models 669; callback shape 1196-1300; no baseURL 1557; wrapping the callback 1564) |
| act (variables 679-708; Action replay note 585; `ignoreLocators` 299) | `https://docs.stagehand.dev/v4/basics/act.md` |
| observe (`ignoreLocators` 378; cache bypass 508) | `https://docs.stagehand.dev/v4/basics/observe.md` |
| extract (`locator`/`ignoreLocators` 669) | `https://docs.stagehand.dev/v4/basics/extract.md` |
| API reference: `Stagehand.create` options; `page.snapshot` (page.md:747); locators (`setInputFiles` locator.md:452); context | `https://docs.stagehand.dev/v4/reference/{stagehand,page,locator,context,clipboard,response,webmcp}.md` |
| Caching (Browserbase-only) | `https://docs.stagehand.dev/v4/best-practices/caching.md` |
| Tabs | `https://docs.stagehand.dev/v4/best-practices/using-multiple-tabs.md` |
| Plan with `observe`, run later | `https://docs.stagehand.dev/v4/best-practices/usecase-observe.md` |
| Cost, speed, prompting | `https://docs.stagehand.dev/v4/best-practices/{cost-optimization,speed-optimization,prompting-best-practices}.md` |
| Persistence and user data; persisted-login recipe | `https://docs.stagehand.dev/v4/best-practices/user-data.md`; `https://docs.stagehand.dev/v4/cookbooks/persisted-login.md` |
| Logging; observability | `https://docs.stagehand.dev/v4/configuration/{logging,observability}.md` |
| Deployments | `https://docs.stagehand.dev/v4/best-practices/deployments.md` |
| "`agent()` is gone" (line 14) | `https://docs.stagehand.dev/v4/migrations/v3.md`; unpublished `https://github.com/browserbase/stagehand/blob/1fc8849/packages/docs/v4/migrations/browser-use.mdx` |
| Moving from Playwright | `https://docs.stagehand.dev/v4/migrations/playwright.md` |
| Architecture: extension runtime and wire protocol | `https://github.com/browserbase/stagehand/blob/1fc8849/packages/extension/README.md`; `api/stagehand.v4.protocol.json` (scraped copy not published); `https://github.com/browserbase/stagehand/blob/1fc8849/packages/protocol/README.md` (the protocol package README, saved under `api/` (scraped copy not published)) |
| Release notes (4.2.0: timeouts, snapshot timeout, extension auto-discovery, telemetry default off) | `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md` |
| Python SDK 4.2.0 | `sdk-python/{README-monorepo-1fc8849.md,PyPI-4.2.0-METADATA.txt}` (scraped copy not published); examples `sdk-python/examples/{act,observe,extract,custom_llm,file_upload,caching}.py.txt` (scraped copy not published) (inert) |
| Legacy Python 3.23.0 (REST client, archived; do not mix) | `https://github.com/browserbase/stagehand-python/blob/a2af713/README.md` |
| v3 (reference only) | `https://docs.stagehand.dev/v3/best-practices/caching.md`; `https://docs.stagehand.dev/v3/basics/agent.md`; `https://docs.stagehand.dev/v3/configuration/browser.md` |
| Browserbase-only features (Model Gateway, server cache, `search`/`fetch`) | `https://docs.stagehand.dev/v4/configuration/models.md`; `https://docs.stagehand.dev/v4/add-ons/{search,fetch}.md` |
| **Not in the corpus:** Stagehand v4 on Steel. No page documents it | `C/INDEX.md` "Known gaps"; the recipe is in SPK `RESULTS.md` and §3 |

Neighbouring corpora: `https://docs.steel.dev/integrations/stagehand.md` (Steel's guide: v3, Steel Cloud);
`https://github.com/steel-dev/steel-browser/blob/1131a02/api/openapi/schemas.json` (`CreateSession`: `extensions`, `persist`,
`timezone`, `dimensions`, `userAgent`, `proxyUrl`, `skipFingerprintInjection`, `headless`);
`research/corpus/browserbase/INDEX.md` (Contexts, Model Gateway).

---

## 17. Governance

### 17.1 The pin and its upgrade gate

**What is pinned, together, in one pin file** (`design`, unbuilt; the executor image and the `steel-profile` image both
build from it, so they cannot drift apart):

| Pinned | Today |
|---|---|
| npm and/or PyPI SDK version | 4.2.0 |
| Extension name, version, and sha256 of `service-worker.js` | Stagehand Runtime 1.1.0, `98e6a987…bcdaa` |
| Steel image digest and the Chromium major it carries | digest per DEC D4; Chromium 152 in the tested image |
| Steel launch-flag expectations (§3) | `--load-extension`, `--disable-extensions-except`, `--remote-allow-origins`, the two feature overrides. Needed on wakes that carry the extension (research) |
| Where the extension is requested | `research` wakes only, by identity kind (persona `extension_mode`), enforced by the node agent (§3, §13; DEC D18). Exceptions only through the G1.4 router table |
| Wrapper-fixed `Stagehand.create` options | `selfHeal:false`; no `cache`, `apiKey`, `apiUrl`, `telemetry` |
| Node / Python runtime major | 24 / 3.12 (as tested) |

Never moved without the gate: `latest`, `alpha`, a Steel image tag. Reading of upstream release notes (CHANGELOG
entries for protocol, runtime and launch behaviour) is part of the gate.

This is the "upgrade smoke test" of MIL standing gate **S1** (pin and upgrade gate), which also requires the ported shield
check and the canary rule (MIL S2) before a new pin touches a client account.

**Triggers.** Any change to the SDK, the extension, the Steel digest, the Chromium major, a Steel launch flag, the
proxy or network layout of §3, or the Node/Python major. (A change to the model or provider allowlist has its own bench
gate: DEC D8, M3; CON O-06.)

**Smoke test** (`design`, unbuilt). Runs on a droplet or CI host with Docker, **not** on the maintainer's Mac (`research/BRIEF.md`: no
Docker container lifecycle there). Throwaway identity, public test pages only, no logins, nothing that posts. Items marked
(M1) cannot be passed until the droplet exists (Q-12).

| # | Check | Pass |
|---|---|---|
| ST-1 | Pin integrity | SDK version, extension manifest name/version and `service-worker.js` sha256 match the pin file; both images built from the same pin file; `npm audit --omit=dev` (and the Python equivalent) no worse than the pin's baseline (4.2.0: 0 advisories) |
| ST-2 | Launch recipe (a `research` wake) | Session created with `extensions:["stagehand"]`; live argv shows `--load-extension` and `--disable-extensions-except` naming the extension, a `--remote-allow-origins` that admits `chrome-extension://`, and both feature overrides; `Extensions.getExtensions` lists Stagehand Runtime at the pinned version; Chromium major recorded. Headless and headful (M1) |
| ST-3 | Attach | `connect` and `create` under a deadline with a forbid-mode shim; a second `create` is rejected with the guard message; after `stagehand.close()` a new one attaches |
| ST-4 | Zero-call path | `snapshot` → code picks → `act(Action)` succeeds with shim count 0; a broken Action gives `success:false` with count 0; the wrapper asserts `selfHeal` is false |
| ST-5 | Fleet verifier | Page mutated so a stored xpath resolves to a different element: the fingerprint check reports a mismatch and no click is sent (tests the fleet's code, since Stagehand will not) |
| ST-5b | Race window (scenario S06-11) | A timer-driven page swaps the node under a stored xpath at controlled offsets around the verifying snapshot and the act. Pass: a swap before the second read is refused (`pre_act_mismatch` or `fingerprint_mismatch`), a snapshot older than `T_fresh` is discarded, and the run records how often a swap after the second read still clicks the new node. That residual rate is expected to be above zero; it is a measurement, and it sets `T_fresh` and tells G1.4 and the owner what an effect step on this API would risk. (M1) |
| ST-6 | Model path | One `observe`, one string `act`, one `extract` through the shim and the allowlisted provider: valid schema, caps applied, `extract` = 2 calls, usage and cost recorded, `cache.status` = `DISABLED` |
| ST-7 | Secrets canary | A `variables` canary is absent from the act prompt dump and present in the next snapshot. If either flips, §8 is reviewed before the pin moves |
| ST-8 | Composer (account use, if cleared) | `fill` on a synthetic contenteditable fires trusted `beforeinput`/`input` `insertText`; read-back matches |
| ST-9 | Frames and shadow | Cross-frame xpath fill in a same-origin iframe; shadow-root text present in the snapshot |
| ST-10 | Upload (account use, if cleared) | 26 B and 1 MiB attach over remote CDP. (The ceiling hunt to 50 MiB is an M1 measurement, not a per-upgrade check) |
| ST-11 | Detector probe | A public CDP-automation detector page, run through the executor, per pin. Stagehand is expected to trip `isAutomatedWithCDP` (§13); fail if the set of flagged signals widens versus the previous pin. Record the result. (M1) |
| ST-12 | Proxy path | With the node forwarder in the loop (exit IP matches), ST-3 and ST-4 still pass and the extension's WebSocket does not traverse the proxy. (M1) |
| ST-13 | Crash recovery | Kill the executor mid-session; the recovery ladder (§11) restores attach. (M1) |
| ST-14 | Hygiene | No `browser.close` in executor code; the container stops through the D4 release order, never `docker stop` |
| ST-15 | No extension on account wakes (scenario S14-4) | A throwaway `account`-kind wake: `Extensions.getExtensions` lists no Stagehand Runtime, the live argv has no `--load-extension` naming it, the image has no `/app/api/extensions/stagehand`, and the wrapper refuses `Stagehand.create` for that identity unless the G1.4 router table admits its site class. (The argv part is M1) |

**Canary and rollout.** A new pin first serves a canary identity that touches no client account; the same canary rule as
for procedures applies (three distinct owner-accepted outcomes: DEC D13; CON O-13). Then the owner says yes to roll it to
client identities. **Rollback** is the previous pin file: previous images and SDK together (the extension must match the
SDK). Old artifacts stay until every executor and container has recycled.

### 17.2 What agents may and may not do through this property

"Agents" here means Hermes profiles (the callers), and the model inside Stagehand. Profiles hold only a scoped token
and reach Stagehand only through fleetd tools (DEC D1, D17). fleetd enforces scope itself; on the Jev trial every tool
on the server is allowed once connected, so nothing may rely on the caller's restraint (DEC D1; `research/verification/hermes-packaging.md` HP-5).

**Profiles may:**
- run a *released* procedure on an identity bound to their token (`run`);
- ask for a scoped step (`act`, ladder L1-L3). Profiles never choose the engine: on a `research` identity L3 is
  Stagehand; on an `account` identity it is the fleet's L3-lite run by the minimal executor (DEC D18), or a person where
  L3-lite is closed (Q-07). Steps that would post, send, reply, DM, delete, follow or submit return `needs_approval` unless
  tied to an approved manifest item and allowed by the token's scope (DEC D17, D13);
- ask for a read (`extract`) with a bounded schema (size and depth limits not yet set), from the current page or a URL
  (navigation only, no effects). The same engine note applies on accounts;
- write drafts for human approval (scope `draft`), research the open web read-only (public pages; no paid enrichment),
  read the evidence and step journal of their own runs, and report a wrong result (`feedback`) (CHT "What agents may do").

**Profiles may not:**
- reach Stagehand, the SDK, CDP, Steel's API or a viewer link except through fleetd;
- pass a model, a provider key, `selfHeal`, `cache`, `telemetry`, a custom `systemPrompt`, a raw xpath or selector, or code
  for `page.evaluate` or CDP. Profiles supply *intent* (a procedure step or a scoped instruction), not mechanism;
- type credentials, solve CAPTCHAs or handle 2FA on a client account (DEC D14);
- trigger any irreversible action without an approved manifest item or per-action approval, **on any rung, including
  free-form `act` and `task`** (DEC D5);
- publish text taken from page content (DEC D13);
- upload anything except manifest assets;
- run two steps at once on an identity, or take a lease held by another writer (only a human preempts: DEC D12);
- navigate outside the identity's declared scope. The boundary is fleetd and the Guard, not Stagehand (#2945);
- do anything on DEC D2's never-built list or the charter's red lines (CHT "Red lines"): cold or outbound DMs, automated
  likes/follows/engagement, identical posts across client accounts, fake accounts, ban evasion, scraping platforms for
  lead data, **any agent-driven browser on x.com**, **any LinkedIn action by browser automation**, downloading TikTok
  content to repost;
- point the browser at a private, internal, loopback or metadata address, or try to get around a refusal (CHT "What
  nobody does, ever").

**The model inside Stagehand may** choose among candidates and write extraction output. It **may not** decide whether an
action is allowed, and on content-bearing steps (`fill`, `type`) its text `arguments` are discarded in favour of the
manifest value: the model only chooses the target (`design`).

**Trial note.** Owner-approved `native_guide` prose skills on the Jev trial are limited (≤ 6,000 chars), appended with
a fixed host instruction that restricts execution to the host's own procedure tool, and bypass the procedure
authority/verifier match. So any guide that mentions this property carries no executable authority and only describes
fleetd tools (DEC D1, D13). `pending Q-11`.

### 17.3 Who may change this property's configuration

The charter sets the rule (CHT "What agents may do" and "must not do without Justin's explicit yes"; AGT "Rules for
changes"). **Anyone, human or Claude session, may change fleet code on a branch, test first, and open a pull request.**
**Justin (the owner) must say yes** before anything is deployed to, restarted on or reconfigured on a live fleet host;
before an engine, a model or System 1 provider is added; before a procedure is released or promoted; before a ceiling,
scope, budget or threshold is raised; before a guard, refusal, lease rule, egress rule or red line is loosened; and before
spend beyond an approved cap. During research: no Docker, no native browser, nothing privileged or interactive on
the maintainer's workstation (`research/BRIEF.md`). Nothing under `fleet/` merges to `main` until Q-09 is closed (CHT).

| Surface | Examples | Proposed by | Approved by | Gate |
|---|---|---|---|---|
| Version pin | SDK, extension, Steel digest, Chromium major, runtime majors | Anyone, by branch and PR with the new pin file | **Owner** | Smoke test ST-1 to ST-14, MIL S1/S2 canary, owner's explicit yes before any droplet deploy |
| Wrapper-fixed options | `selfHeal:false`; no cache/apiKey/apiUrl/telemetry; no `browser.close` | Anyone, by code change | **Owner** (it loosens a guard if relaxed) | Unit tests assert them; not runtime-configurable |
| Model, effort, caps, provider allowlist, ZDR flag | slug, `low`, `max_tokens`, `only`/`order`, `zdr` | Anyone, with bench results | **Owner** (a model or provider is added) | Per-provider bench (MIL G3.5; CON O-06); `pending Q-07` |
| Executor per identity kind, then site class | router table (kind first, site-class override second; Stagehand / Browser-Use / minimal CDP). Default (DEC D18): Stagehand on `research`, the minimal CDP executor on `account` | Anyone, with G1.4 evidence | **Owner** | MIL G1.4 results on the full stack (CON O-02) |
| Replay-cache entries | release, quarantine, rollback | The executor, automatically, as a *candidate* (DEC D5) | Released by D13's rule: three distinct owner-accepted outcomes. Rollback is per procedure; the owner decides | Outcome checks; MIL G3.3 |
| Extension presence | by identity kind (`research` yes, `account` no), pinned in the persona as `extension_mode` with `executor_id` (DEC D18); a change is a persona change under the canary rule; exceptions only through the router table | Anyone, as a node-agent policy change | **Owner** | G1.4 evidence; ST-15 |
| Budgets | tokens and dollars per call, step, identity | Anyone | **Owner** (`pending Q-06`) | Ledger review |
| Logging level, evidence and snapshot retention | | Anyone | **Owner** | Retention policy (not yet written) |
| Hermes profiles | | none | none | fleetd rejects any attempt (scope) |

### 17.4 Soul

**Stagehand is the hand, not the judge: it performs one verified step at a time on a browser the fleet already pinned,
and every decision that matters is made before it moves.**

It works on open-web research browsers. A client's logged-in browser does not carry it until the measurement and the
owner say so.

This line is for the people and agents who maintain the property. The profile-facing character, for a Hermes
`SOUL.md`, is [SOUL.md](../../SOUL.md).
