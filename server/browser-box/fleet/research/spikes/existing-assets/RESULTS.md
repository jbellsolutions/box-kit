# Spike: does self-hosted Steel keep a profile, and where? (existing-assets agent)

Date: 2026-10-10 03:03-03:08 UTC (2026-10-09 local). Spend: $0 (no model calls, no paid APIs).
Host: a Mac (Apple Silicon, arm64 Docker). Public test domain only (example.com); no logins.

## Why

browser-box's `gateway/gateway/steel.py:create_session` sends `persistProfile: true` and optionally
`profileId`. The fleet's core promise ("the same browser every time, still logged in") depends on what
self-hosted Steel actually does with a profile. Source code @1131a02 suggested:

- `api/src/modules/sessions/sessions.schema.ts` accepts `persist` and `userDataDir`; there is no
  `persistProfile` / `profileId` (zod `z.object` strips unknown keys, so they are silently ignored).
- `api/src/services/session.service.ts:180-183`:
  `options.userDataDir || options.persist === true ? path.join(<build>/../.., "user-data-dir") : env.CHROME_USER_DATA_DIR || /tmp/steel-chrome`
  i.e. a caller's `userDataDir` is only a truthy flag; every persisted session uses ONE fixed directory.
- `SessionService` holds a single `activeSession`: one Steel process = one browser = one session.

## Image under test

`ghcr.io/steel-dev/steel-browser-api:latest` = `sha256:7a161b95e8a9b20ddc2f87d380c61636bb13507f7fe99fd4704cb105c5478f99`,
created 2026-09-16 (the source clone is 2026-10-06, so the compiled image was checked directly):

```
$ docker run --rm --entrypoint sh <image> -c 'grep -n "user-data-dir" -B3 -A2 /app/api/build/services/session.service.js'
89-        const userDataDir = options.userDataDir || options.persist === true
90:            ? path.join(dirname(fileURLToPath(import.meta.url)), "..", "..", "user-data-dir")
91-            : env.CHROME_USER_DATA_DIR || path.join(os.tmpdir(), "steel-chrome");
$ grep -rn "persistProfile\|profileId" /app/api/build   -> (no output)
```

So the fixed persist path inside the image is `/app/api/user-data-dir`.

## Method

Container `fleet-spike-assets-steel`, `--memory 1536m --cpus 1.2`, `127.0.0.1:3901->3000`, named volume
`fleet-spike-assets-profA` mounted at `/app/api/user-data-dir`. Scripts (no secrets):
`steel_persist_probe.py` (write/read/readnp phases) and `steel_persist_probe2.py` (write with readback
and a flush wait). Cookies are set via CDP (`Storage.setCookies` and a page `document.cookie` on
https://example.com/), read back with `Storage.getCookies`, and the on-disk `Default/Cookies` SQLite was
copied out and queried.

## Raw results

| # | Step | Result |
|---|---|---|
| 1 | `POST /v1/sessions {"persist":true,"userDataDir":"/tmp/custom-profile-x","persistProfile":true,"profileId":"fleet-probe"}` | 200, `status: live`. Steel log: `"userDataDir": "/app/api/user-data-dir"`. `/tmp/custom-profile-x` does **not exist** afterwards. Custom path ignored; Cloud-style fields silently dropped. |
| 2 | set cookie, release **~5 s** later, new persist session, read | cookie **absent**; on-disk `Cookies` table **empty** (`[]`). |
| 3 | set 2 cookies (CDP + page), readback before release = `['fleetprobe','fleetprobe2']`, wait **40 s**, release | on disk: `[('example.com','fleetprobe',1),('example.com','fleetprobe2',1)]` |
| 4 | new persist session, same container | `['fleetprobe','fleetprobe2']` present: **True** |
| 5 | new NON-persist session (`{}`), same container | present: False (uses `/tmp/steel-chrome`) |
| 6 | `docker rm -f`, new container, **same volume** | present: **False**, `POST /sessions` still **200**. Volume still holds both cookies (verified by copying `Cookies` out). Steel log: `LAUNCH ERROR (BROWSER_PROCESS) ... process_singleton_posix.cc:365 The profile appears to be in use by another Chromium process` -- the profile's `SingletonLock` symlink names the OLD container's hostname (`a50d8ce60a5f-1274`). Steel fell back silently to a non-persisted browser. |
| 7 | delete `SingletonLock`/`SingletonCookie`/`SingletonSocket` in the volume, new container, same volume | present: **True** |
| 8 | new container, different volume (`profB`) | present: False (fresh profile; isolation by volume) |
| - | `POST /v1/sessions/release` | 200 in 5 runs, **500** in 2 runs; the 500s coincide with `[RetryManager] Browser Launch failed after 3 attempts` (process_singleton again) when Steel relaunches its default browser after a release. |
| - | Memory | Steel container 552 MiB right after a session on example.com (`docker stats`). |

## Conclusions (hands-on, n = 1 per row; repeat before relying on exact timings)

1. Self-hosted Steel persists **one** profile per Steel process, at the fixed path `/app/api/user-data-dir`.
   `userDataDir` values, `persistProfile` and `profileId` do nothing. Per-profile isolation therefore needs
   one Steel container per awake profile with that profile's volume mounted at the fixed path (or a
   patched Steel).
2. A login can be lost if the session is released within Chromium's cookie flush window: 5 s lost it,
   40 s kept it. The fleet must wait/flush before release (or export cookies via CDP as a second copy).
3. Re-creating a container on an existing profile volume **silently** loses the login unless the stale
   `Singleton*` files are removed first; Steel still answers 200 and serves a blank browser. The fleet
   must clear `Singleton*` on container start (safe only while a lease guarantees one container per
   profile) and must verify "still logged in" after every wake, never assume it.
4. A release can return 500 and leave Steel without a browser; health-check after release and recreate.
5. browser-box's `session` tool sends field names OSS Steel ignores, and `compose.yml` mounts no volume at
   `/app/api/user-data-dir`. The box's logged-in session therefore survives calls within one Steel session
   lifetime (the card's actual claim), not a container recreate. Reported, not changed.

## Follow-up checks (same session)

- **What release actually does.** In the pinned build, `/app/api/build/services/cdp/cdp.service.js`,
  `endSession()` (line 984) calls `shutdown()`. That runs `await this.browserInstance?.close()` and then
  `await this.browserInstance?.process()?.kill()` (lines 382-383), and then relaunches the default idle
  browser.
  - So Steel *attempts* a graceful close before killing the process.
  - Two observations suggest Chromium still did not finish a clean shutdown: the cookie set about 5 s
    before release never reached disk, and a stale `SingletonLock` was left in the persist directory.
  - The mechanism is not proven, and this was n = 1.
  - Mitigation options:
    - wait at least 30-40 s after the last auth change (measured once);
    - export Steel's session context before release and inject it on create (`sessionContext.cookies`
      is in the OSS schema). **Not tested.**
- **The "silent fallback" claim is an inference.** It rests on Steel's `LAUNCH ERROR … process_singleton`
  log line plus the empty cookie read, while `POST /v1/sessions` returned 200.
- **Untested alternative to deleting `Singleton*`:** give each profile's container a fixed `--hostname`,
  so Chromium's lock names the same host every time.
- **The Browser-Use pin refuses the shared scratch venv (hands-on).**
  `<scratch>/py/.venv/bin/python -I agents/browseruse/runner.py --self-check` prints
  `self-check failed: RuntimeError: browser-use 0.13.11 is installed; the confinement here is written against 0.13.10`.

## Cleanup

`docker rm -f fleet-spike-assets-steel`; `docker volume rm fleet-spike-assets-profA fleet-spike-assets-profB`;
`rm -rf /tmp/fleet-spike-assets`. Verified: no `fleet-spike-assets*` containers or volumes remain.
(Another agent's `fleet-spike-antidetect` container was running and was not touched.)
