# Scale-infra spike: self-hosted Steel as a per-profile unit

Date: 2026-10-09 (run 03:04–03:10 UTC on 2026-10-10). Spend: **$0** (no model calls, no cloud
resources created; one read-only `GET /v2/sizes` to DigitalOcean).

Host: a Mac running arm64 Docker (`aarch64`).
None of those were touched. **All numbers are linux/arm64 Docker. An amd64 droplet will
differ, and its Chromium will not be smaller.**

Image: `ghcr.io/steel-dev/steel-browser-api:latest`, `sha256:7a161b95e8a9…`, built 2026-09-16,
`@steel-browser/api` 0.5.3, Chromium 152.0.7977.82. The compiled code in this image matches
`steel-browser@1131a02` on every line checked: the `user-data-dir` expression, the
`persist`/`userDataDir` schema, `--password-store=basic`, and the WebRTC flags.

Containers were named `fleet-spike-scale-{a,b,c,d,e}`. Each ran with `--memory 1536m --cpus 1.2`,
loopback ports 3311–3313, and `NODE_OPTIONS=--unhandled-rejections=warn`. All of them were
removed by the scripts' exit trap, and `docker ps -a --filter name=fleet-spike-scale` came back empty.

Pages visited: example.com, quotes.toscrape.com, books.toscrape.com, the-internet.herokuapp.com.
No logins, no social sites, nothing posted.

## Scripts

- [`run_spike.sh`](run_spike.sh) `<workdir>`: cold start, the fields the server honors,
  fingerprint within one container, persist, browse with memory sampling, context export, tarball,
  headful, restore into container B, `sessionContext` restore into C, and 3-way density.
- [`run_spike2.sh`](run_spike2.sh) `<run1 dir> <workdir>`: restore without Chromium's `Singleton*`
  lock files, fingerprint across real relaunches, and a pinned UA.
- [`probe.mjs`](probe.mjs): a CDP probe using `playwright-core` `connectOverCDP`. Modes are
  `fp`, `setstate`, `getstate` and `browse`. It exits without calling `browser.close()`.
- [`cost_model.py`](cost_model.py): the cost arithmetic used in the dossier. Its output is in
  [`raw/cost_model.out`](raw/cost_model.out).

Commands:

```
PW_CORE=<scratch>/npm/node_modules/playwright-core run_spike.sh  <scratch>/spikes/scale-infra/run1
PW_CORE=...                                              run_spike2.sh <...>/run1 <...>/run2
python3 -I cost_model.py
```

Raw logs: [`raw/run1-spike.log`](raw/run1-spike.log) and [`raw/run2-spike2.log`](raw/run2-spike2.log).
The `du` of the profile directory is in [`raw/run1-profile-du.txt`](raw/run1-profile-du.txt) and the
DigitalOcean size subset is in [`raw/do-sizes-subset-2026-10-10.json`](raw/do-sizes-subset-2026-10-10.json).

## Raw numbers

### Start and launch latency (arm64 Docker)

| step | measured |
|---|---|
| `docker run` until `/v1/health` = 200 | 3.1 s, 4.4 s, 6.6 s (the last two ran with other containers busy) |
| create a session with the same config as the running browser (Steel reuses the browser) | 0.28 s, 0.33 s |
| create a session that relaunches Chromium (config changed) | 1.0–3.1 s |
| create a `persist:true` session on a **restored** profile | 6.5 s, 9.3 s, 11.0 s |
| first navigation after a restored-profile launch (`getstate` on example.com) | 2.2–3.6 s |
| cold wake end to end (container start, restore, session, first page) | **about 15–20 s** |
| release (`POST /v1/sessions/release`) | 1.1–3.0 s |

### Memory and CPU (container total = Node API + Chromium)

| state | measured |
|---|---|
| idle container after boot (Steel launches a default Chromium at boot) | 344–407 MiB |
| one session and one page | 578–642 MiB |
| after 8 public test pages, sequential | 699 MiB; sampled peak **851 MiB** (35 samples) |
| 3 containers idle, one session each | 486 + 630 + 642 MiB |
| 3 containers browsing the same 8 pages at once (43 s wall) | peaks of 826 / 796 / 814 MiB, **sum 2,435 MiB** |
| CPU while browsing, per container (cap 1.2 CPU) | mean 32–54 % of one core; p90 128–131 %, which is at the cap |

Light test pages only. Social sites were not and cannot be visited under the brief's rules. The
browser-box README measured 1.08–1.36 GiB on Hacker News and agent tasks (2026-09-23). The fleet
plan uses **1.5 GiB per active browser** as a labeled estimate.

### Profile at rest

| item | measured |
|---|---|
| `user-data-dir` after 8 pages | 5,196 KB, 255 files. Biggest items: `Default/Cache` 1.6 MB, `GPUCache`/`DawnWebGPUCache`/`DawnGraphiteCache` 548 KB each, `Code Cache` 444 KB |
| `tar` + `zstd -3`, everything | 937,459 bytes in 0.38 s |
| `tar` + `zstd -3`, caches excluded (`Cache`, `Code Cache`, `GPUCache`, `Dawn*Cache`, `GrShaderCache`, `ShaderCache`, `Service Worker/CacheStorage`) | **57,356 bytes** in 0.61 s |
| `GET /v1/sessions/{id}/context` (cookies + localStorage) | 1,829 bytes, 5 cookies |

### Restore and portability (the load-bearing results)

| test | result |
|---|---|
| Restore the slim tarball **with** `SingletonLock`/`SingletonSocket`/`SingletonCookie` into a new container (B) | **FAILED silently.** Session create returned 200 (6.5 s), but the cookie and localStorage were gone. `SingletonLock` still pointed at container A's hostname (`36b2c29d5c45-729`). |
| The same tarball with the three `Singleton*` files **removed** (D) | **Restored.** Cookie `fleetspike=…` and localStorage `ls-ok` were both present. |
| Restart container D (`docker restart`), then create a `persist` session | Still restored. |
| A new container with no volume, state injected as `sessionContext` from A's context export (C) | **Restored.** Both cookie and localStorage came back. |

Cookie ciphertexts in `Default/Cookies` carry the `v10` prefix, which is Chromium's
`--password-store=basic` fixed key. That is why a tarball decrypts in another container, and why
**placement does not have to be sticky for correctness**.

### Fields the self-hosted server honors

| request body | result |
|---|---|
| `{"persistProfile":true,"profileId":"fleet-spike"}`. These are the fields browser-box's `gateway/gateway/steel.py` sends. | 200, but **ignored**. The mounted fixed directory stayed empty (0 KB). State went to `/tmp/steel-chrome` inside the container (2.7 MB), so it is lost when the container is recreated. |
| `{"userDataDir":"/tmp/custom-udd"}` | 200, but **the path is ignored**. `/tmp/custom-udd` was never created, and the fixed `/app/api/user-data-dir` received 12 entries. `options.userDataDir || options.persist === true ? FIXED : TMP` parses as `(a || b) ? FIXED : TMP` (`session.service.ts` L180–183 @1131a02). |
| `{"persist":true}` | Uses `/app/api/user-data-dir`. Mount a per-profile directory there. |
| `{"headless":false}` | **500**: `Browser process error (launch_failed) … Failed to connect to the bus … /run/dbus/system_bus_socket`. The stock entrypoint starts dbus only when `DEBUG=true` and never starts Xvfb, although Xvfb is installed. |

### Fingerprint stability (the other load-bearing result)

Probe: `navigator.userAgent`, `platform`, `hardwareConcurrency`, `deviceMemory`, `screen`,
timezone, and WebGL renderer.

| launch | UA Chrome version | hc | dm | WebGL renderer | tz |
|---|---|---:|---:|---|---|
| A #1 and #2: the same browser reused, so not a relaunch | 139 (UA says `Linux aarch64`; platform says `Linux x86_64`) | 144 | 8 | Intel UHD 630 | America/New_York |
| D, restored profile, persist launch | 144 | 16 | 8 | Intel UHD 630 | America/New_York |
| D after `docker restart`, **same profile** | 142 | 8 | 8 | SwiftShader | **UTC** |
| E, new container | 145 | 32 | 8 | AMD Radeon (radeonsi) | UTC |
| E, persist relaunch | 145 | 18 | **2** | **Adreno (TM) 732** (a phone GPU on "Linux x86_64") | America/New_York |
| E, pinned `userAgent` + `dimensions` + `timezone` | 152 (as pinned) | 10 (= host cores, no injection) | 8 | SwiftShader | America/Chicago (as pinned) |

`screen` read `800x600` in every run.

**Conclusion (hands-on):** self-hosted Steel generates a new random fingerprint on every Chromium
launch, including a relaunch of the same profile, and a new timezone whenever none is pinned.
Pinning `userAgent` turns injection off, so the real values show through: host core count and
SwiftShader. The REST schema has no `fingerprint` field, although `SessionService.startSession`
accepts one. "Same fingerprint every time" therefore requires a patch to Steel. Judging
fingerprint quality is the antidetect agent's job; this spike only records that the fingerprint
is not stable.
