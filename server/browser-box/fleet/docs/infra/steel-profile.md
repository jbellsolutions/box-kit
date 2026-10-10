# `steel-profile`: build spec for the wrapper image and the node-agent contract

> **SPEC. NOT BUILT. Nothing here has been run.** No image, entrypoint, forwarder, node agent or firewall rule
> described below exists yet. Code blocks are sketches, not tested code. Every test in section 12 that is not
> marked "local" needs a droplet, so it waits for Justin's yes to a small capped throwaway droplet ([DEC] Q-12) and for an amd64
> re-run of every Steel measurement ([CONS] O-17). All research numbers come from arm64 Docker on a Mac.

This is the build spec for the browser host in [`../engines/steel.md`](../engines/steel.md). Read that file for
how Steel behaves and why the fleet does what it does. This file says exactly what to build and what it must
pass. When built it lives at `fleet/infra/steel-profile/`, with the node agent inside fleetd's infra module
([EA-dos] Q4 layout). Neither path exists today.

**Precedence.** Where a dossier and its verification report disagree, the verification report and
[DEC] win. Tags: `measured` (in [RES], arm64, small n), `source` (a verifier ID such as STE-3),
`source (new)` (read by the author of this spec in the scratch clone of `steel-browser@1131a02`, not covered
by any verifier, re-checked first in M1), `to measure`, `estimate`, `pending Q-xx`. Corpus pages are cited by
their vendor URL; [`../../research/corpus/steel/`](../../research/corpus/steel/INDEX.md) holds the topic map and capture method only.

| Key | File |
|---|---|
| [DEC] | [`../../DECISIONS.md`](../../DECISIONS.md) |
| [CONS] | [`../../research/verification/CONSISTENCY.md`](../../research/verification/CONSISTENCY.md) |
| [S-dos], [S-ver] | [steel dossier](../../research/dossiers/steel.md), [steel verification](../../research/verification/steel.md) |
| [AP-dos], [AP-ver] | [antidetect-proxies dossier](../../research/dossiers/antidetect-proxies.md), [verification](../../research/verification/antidetect-proxies.md) |
| [SC-dos], [SC-ver] | [scale-infra dossier](../../research/dossiers/scale-infra.md), [verification](../../research/verification/scale-infra.md) |
| [EA-dos], [EA-ver] | [existing-assets dossier](../../research/dossiers/existing-assets.md), [verification](../../research/verification/existing-assets.md) |
| [SH-dos], [SH-ver] | [stagehand dossier](../../research/dossiers/stagehand.md), [verification](../../research/verification/stagehand.md) |
| [RES] | [`../../research/spikes/steel/RESULTS.md`](../../research/spikes/steel/RESULTS.md), blocks written `[t1 #42]` |
| [BOX-SEC], [BOX-OPS], [BOX-COMPOSE] | the box's [`docs/security.md`](../../../docs/security.md), [`docs/operations.md`](../../../docs/operations.md), [`compose.yml`](../../../compose.yml) |
| [SCN] | the stress-test walkthroughs in [`../../research/scenarios/`](../../research/scenarios/) (S01, S05, S07, S08, S12, S13, S14). They are design reviews, not measurements. Each use below names the gap id. |
| [ARCH] | [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) |
| [MS] | [`../../MILESTONES.md`](../../MILESTONES.md) |
| [ENG-S] | [`../engines/steel.md`](../engines/steel.md) (the sibling guide to how Steel behaves) |
| [ID] | [`../identity/identity-and-proxies.md`](../identity/identity-and-proxies.md) |

**Revision note.** This revision applies twelve gaps from the stress tests (listed in section 15). Where this
file now differs from [ARCH], this file says so in place, and section 15 lists the lines [ARCH] should change.
Nothing was run. Every new rule below is a design, and every new number is "to set" or "to measure".

---

## 1. What this is, and the choices this spec makes

`steel-profile` is five things:

1. a **wrapper image** around a digest-pinned `steel-browser-api`, in two flavors (sections 2 to 5);
2. a **network holder and a credential-holding forwarder** that give the browser its only way out (section 6);
3. **probes** that replace Steel's untrustworthy health and ownership answers (section 7);
4. the **wake, release, flush and snapshot sequences**, with encrypted, tagged state bundles (section 8);
5. the **node-agent contract** that fleetd calls (section 9), plus the **tests** (section 12).

Not in scope: leases and placement (fleetd, [DEC] D12), the engines' own logic (Stagehand, Browser-Use), the
persona registry, procedures, the proxy vetting rule ([DEC] D10 / O-10).

```
fleetd (control plane)  --lease, persona, secrets, bundle pointer-->  node agent (host process, one per droplet)
One network namespace per awake identity <id8>, owned by the holder. Everything below joins it:
  fleet-net-<id8>    network holder (owns the namespace and the hostname; runs nothing else)
  fleet-fwd-<id8>    forwarder sidecar (holds the proxy credentials; nothing else can read them)
  fleet-steel-<id8>  the wrapped Steel (profile volume at /app/api/user-data-dir; the only container that mounts it)
  fleet-rt-<id8>     runtime: Guard, exporter, login prober. Sends no input to the browser, except the
                     prober's read-only navigation.
  fleet-wk-<id8>-<kind>  actors, one container each: executor, Stagehand worker, Browser-Use worker.
                     Each is its own kill unit. None mounts the profile volume.
Inside the namespace the browser, the Guard and every actor use  ws://127.0.0.1:3000/  (topology T-L, 10.4).
The node agent (host) reaches Steel at the holder's bridge IP on port 3000 and talks to the forwarder and the
runtime over host-mounted unix sockets. It also hosts the egress rules, the viewer route allowlist and the
watchdog (a bare CDP connection that acts only when the Guard is lost, 10.1).
```

**Choices this spec makes** (each is a design decision of this spec, not of [DEC]; each is marked where it
matters):

| Choice | Why |
|---|---|
| **Topology T-L: one namespace, loopback CDP, no proxy exception for the bridge IP.** The Guard and every actor run inside the identity's namespace and dial `127.0.0.1:3000`. The forwarder refuses every private destination, with no exception. *(S13-6; matches [ARCH] section 2.2.)* | The earlier draft ran workers outside and gave the forwarder a rule to serve a `CONNECT` to its own bridge IP on port 3000. That rule also let any page request reach Steel's unauthenticated API through the proxy path. Inside the namespace, Chromium's own loopback bypass already covers the extension's dial-back, so the rule is not needed. The fallback T-O (10.4) keeps the old shape for one case only. |
| Actors (executor, Stagehand, Browser-Use) run one per container, apart from the Guard and the runtime. *(S08-12.)* | "Kill the workers on a higher token" must be one operation with one meaning: `docker kill` of the actor containers. The Guard stays up. [ARCH] section 2.2 draws the actors inside one `identity-runtime` container; that is a packaging difference to settle in M1 (10.3). |
| The forwarder is a sidecar sharing the browser's network namespace, through a small holder container | `127.0.0.1` inside a container is that container's own loopback, so [DEC] D4's "Steel gets `127.0.0.1:<port>`" needs a forwarder in the same namespace. The holder lets the forwarder be up and checked before Steel exists. The forwarder stays a separate container from the runtime so that a compromised actor cannot read the proxy credentials. |
| A wrapper script sets Chromium's environment (`CHROME_EXECUTABLE_PATH`) | Steel launches Chromium with an `env` of only `HOME`, `TZ`, `DISPLAY` (`source (new)`), so container-level `LANG` and `LANGUAGE` never reach it. |
| The recorder extension is deleted from the image | It posts page events to Steel's own log store, and a person types logins into this browser (`source (new)`). |
| Two image flavors: `account` carries no Stagehand extension; `research` does. The extension mode is part of the persona, fixed at creation, never chosen per wake. A human-login or canary wake never loads it. *(S14-12, S14-4.)* | Steel's `extensions:["stagehand"]` loads the extension with `--load-extension`, so it is resident from launch, and it trips a public automation check ([AP-ver] AP-2). A logged-in client account should not carry it unless M1 picks Stagehand for that site class. |
| No `apt-get` in the image build | The base already has Xvfb, dbus and Chromium. A package install could pull a Chromium upgrade, which changes the persona's UA major (inference from [AP-dos] risk 8). |
| No Docker `HEALTHCHECK` is ever read as "ready" | Steel's `/v1/health` is `ok` with no browser ([S-ver] STE-3). |
| The Guard and the engines attach only after the persist create | A persist create relaunches Chromium ([EA-ver] M-3). |
| The context is exported twice per release; the second export is the journal of record | Cookies rotate during the hold. The second export is untested. |
| Every bundle generation and journal carries tags (`auth_result`, `tainted_ip`, `incident`). The pointer moves only to a clean generation. *(S05-12, S07-12.)* | A generation written while logged out, challenged or on a wrong IP is real data, but it is not a state to restore from by default. |
| The local volume is deleted after the bundle is verified, and after any failed wake in which no session ran | Cookie encryption in the profile uses a fixed key, so a volume on disk is plaintext in practice ([SC-ver] SCA-4). *(S07-15.)* |

---

## 2. The image

**Base.** `ghcr.io/steel-dev/steel-browser-api@sha256:<manifest-list digest>`. Never `:latest`, which tracks
`main` ([S-ver] STE-14). Which digest, and the upgrade gate, are in
[`../engines/steel.md`](../engines/steel.md) section 14.1. The Chromium major of that digest is recorded in the
image and in every persona.

**What the base already has** (corpus: `https://github.com/steel-dev/steel-browser/blob/1131a02/api/Dockerfile`): Debian `chromium` and
`chromium-driver`, `xvfb`, `dbus`, `dbus-x11`, `nginx`, `procps`, `curl`, `x11-xserver-utils`, a set of CJK,
Thai, Arabic and free fonts, and `ENV DISPLAY=:10 DBUS_SESSION_BUS_ADDRESS=autolaunch:`. It has **no `USER`**, so
Steel and Chromium run as root. It exposes 3000 and 9223.

**What the wrapper adds (files only):**

| Path in image | What |
|---|---|
| `/opt/fleet/entrypoint.sh` | Wrapper entrypoint (section 4) |
| `/opt/fleet/chromium` | Wrapper that Steel runs as "Chromium" (section 4.3) |
| `/app/api/extensions/stagehand/` | **`research` flavor only.** The Stagehand extension, copied from the pinned SDK package (`dist/extension/`). The PyPI wheel's copy is byte-identical (sha256 `98e6a987...`), so one directory serves both SDKs ([SH-ver] missed issue 6). Size is about 2 MB ([SH-dos] Q-extra). The `account` flavor has no such directory. |
| (deleted) `/app/api/extensions/recorder/` | Steel loads it by default in headless sessions. If the directory is absent, `getExtensionPaths` skips the name (`source (new)` `utils/extensions.ts`). **To verify** that a headless create works without it. |
| `/opt/fleet/PIN` | Image digest, Chromium version, Steel source pin, Stagehand pin (`research` flavor), flavor |
| `/opt/fleet/FLAVOR` | One word, `account` or `research`, checked against the persona at start (4.2) |

**Labels:** `fleet.steel.digest`, `fleet.chromium.major`, `fleet.wrapper.version`, `fleet.flavor`.

**Flavors** *(S14-12; the choice of executor per site class stays an M1 decision, [DEC] D6 / O-02)*.

| | `account` flavor | `research` flavor |
|---|---|---|
| Used by | Identities of kind `account` (a logged-in client account) | Identities of kind `research` (open web, no login) |
| Stagehand extension directory | Absent | Present |
| `extension_mode` allowed in the persona | `none` (default). `A` or `B` only if M1 selects Stagehand for that site class **and** the owner records it at creation. Such an identity then runs the `research` image, as its cohort, for good. It is never a per-wake switch. | `A` (default, the measured recipe) or `B` |
| Steel's static `--disable-features` string | Replaced (4.5): the two `DisableLoadExtension...` overrides are dropped | Kept as Steel ships it |
| `--remote-allow-origins=*` | Filtered out through `FILTER_CHROME_ARGS`, if puppeteer's origin-less websocket still attaches (**to measure**) | Kept (the extension's dial-back needs it) |
| Executor | Whatever M1 selects for the site class: Browser-Use, a minimal CDP executor or Stagehand with the extension. This file does not choose. | Stagehand v4, mode A or B |
| Tests that apply | T11n (negative: no extension anywhere); T20 if variant N is built. T18 and T19 apply to both flavors. | T11 (positive: attach, replay, uninstall) |

The flavor is part of the image cohort. A flavor change for an existing identity is a persona migration with the
canary rule ([DEC] D13, [CONS] O-13). A human-login wake and a canary wake request no extension whatever the
persona says (5, 8.1).

**Entrypoint:** `ENTRYPOINT ["/opt/fleet/entrypoint.sh"]`, `CMD ["--no-nginx"]`. The stock entrypoint supports
`--no-nginx` and then does not start the nginx that exposes raw CDP on 9223 (`source (new)`
`api/entrypoint.sh`). **To verify** that nothing in the session path needs port 9223. The browser-box already
runs without 9223 ([BOX-COMPOSE] comment on `ports`).

**Variants (pending Q-08).** Steel's Chromium runs as root with no sandbox because there is no `USER`
([S-ver] missed issue 3).

| | R: root, accepted risk | N: non-root, sandbox on |
|---|---|---|
| Image | As built above | Adds a `RUN useradd` step (not `apt`). Chowns the dirs Steel writes: `/app/api/user-data-dir`, `/tmp`, `/files`, `/app/.cache`, the log path. |
| Chromium sandbox | Off: Steel adds `--no-sandbox --disable-setuid-sandbox --no-zygote` when uid is 0 | On. May need user namespaces in the container (a seccomp profile that allows them, or an added capability). **To measure.** |
| dbus | `dbus-daemon --system --fork`, as the stock entrypoint does under `DEBUG=true` | `--system` needs root. Start a session bus and put its address in `persona.env`. |
| Site isolation | Off in Steel's flags (one `--disable-features=` string, see section 4.5) | Same flags unless 4.5 is done |
| Written acceptance | Required from Justin | Not needed |

Build R first. Build N as soon as Q-08 asks for it. Both go through the same tests.

---

## 3. The container run contract

One Steel container per awake identity, started only by the node agent. This is a sketch; flags marked
**to measure** are added one at a time and gate-tested.

```
docker run -d --name fleet-steel-<id8>
  --init --restart no
  --network container:fleet-net-<id8>             # joins the holder's network namespace
  --memory 1536m --memory-swap 1536m --cpus 1.2   # the box's values [BOX-COMPOSE]; no swap
  --pids-limit 512                                # estimate: 132-167 pids measured [S-dos] Q6
  --security-opt no-new-privileges --cap-drop ALL # hardening; to measure. See the dbus note below.
  -v /var/lib/fleet/profiles/<id8>:/app/api/user-data-dir
  -v /run/fleet/<id8>/persona.env:/run/fleet/persona.env:ro
  -e TZ=<tz> -e DEFAULT_TIMEZONE=<tz>
  -e TIMEZONE_SERVICE_URL=http://127.0.0.1:9/     # a closed port: Steel's boot-time zone lookup fails at once
  -e SKIP_FINGERPRINT_INJECTION=true
  -e CHROME_HEADLESS=<true|false>                 # from the persona
  -e CHROME_EXECUTABLE_PATH=/opt/fleet/chromium
  -e CHROME_ARGS="--accept-lang=en-US,en --use-angle=swiftshader --enable-unsafe-swiftshader"
  -e NODE_OPTIONS=--unhandled-rejections=warn     # a closed tab once killed the whole server 4 of 5 times [BOX-COMPOSE]
  --label fleet.identity=<id> --label fleet.fencing=<token> --label fleet.wake=<uuid>
  <wrapper image>@sha256:<digest>
```

Rules:

- **No `-p`.** Nothing is published. The node agent reaches Steel at the holder's bridge IP on port 3000, over
  a per-identity network that only the node agent can route to ([SC-dos] Q6; [DEC] D4).
- **`--init` always.** Without it, 8 create/release cycles left 151 zombies ([RES] `[t1 #72]`).
- **`--restart no`.** A crashed container must come back through the wake path, which clears `Singleton*` and
  runs the probes. Docker's restart would skip both.
- **Never `docker stop` a live identity.** It is a SIGKILL after 10 s and it leaves the lock
  ([RES] `[t1 #74]`). After a verified snapshot there is no live profile, so stopping is safe then.
- **The volume** is a dedicated host directory mounted at the fixed path. Steel ignores any per-session
  `userDataDir` ([EA-ver] EA-1). The directory is mode 0700 and holds a marker file `.fleet-identity` that the
  entrypoint checks (section 4.2).
- **Hostname.** A fixed `--hostname fleet-<id8>` is a supplement to deleting `Singleton*`, not a fix
  ([EA-ver] M-5). Docker may refuse `--hostname` on a container that joins another's network, so set it on the
  holder (**to verify**).
- **The `HEALTHCHECK` from the box compose** (`curl /v1/health`) is not copied. It only proves Node answers.
- **Headful costs more:** about +0.2 vCPU and +150 MB per slot (**estimate**, unmeasured, [SC-dos] Q1).
- **Capabilities versus dbus.** `dbus-daemon --system` drops to the `messagebus` user, which needs `SETUID` and
  `SETGID`, and `Xvfb` may need more. So `--cap-drop ALL` and the system bus can conflict (inference). Add back
  only the capabilities a measured failure names, one at a time, or use a session bus in both variants and
  drop the system bus. Variant N also needs whatever its sandbox needs (user namespaces, **to measure**).
  Every capability that is added back is written down with the failing test that required it.

### 3.1 The other containers in the namespace

All of them join the holder with `--network container:fleet-net-<id8>`, run with `--init`, `--restart no`,
`--cap-drop ALL`, `--security-opt no-new-privileges`, a read-only root filesystem, and memory and CPU caps. None
publishes a port. **Only the Steel container mounts the profile volume.** (A sketch; flags are added one at a time.)

| Container | Holds | Mounts | Killed by |
|---|---|---|---|
| `fleet-fwd-<id8>` | The proxy credentials (tmpfs file, mode 0400). Listener on `127.0.0.1:<port>`. | `/run/fleet/secrets/<id8>/upstream` (ro), directory `/run/fleet/<id8>/fwd/` (holds `fwd.sock`) | The node agent at sleep or on an exit-IP change |
| `fleet-rt-<id8>` | Guard, exporter, login prober. No credentials, no input to the browser (the prober only navigates, read-only). | directory `/run/fleet/<id8>/rt/` (holds `rt.sock`), directory `/run/fleet/<id8>/fence/` (ro) | The node agent at sleep. If it dies earlier, that is a Guard loss (10.1). |
| `fleet-wk-<id8>-executor`, `-stagehand`, `-browseruse` | One actor each. These are the only containers that send input or navigation to the browser for the agent. | directory `/run/fleet/<id8>/fence/` (ro) | `docker kill` on a higher fencing token, on sleep, on abort (10.3) |

**The fence file.** The node agent writes the highest fencing token it has seen for the identity into
`/run/fleet/<id8>/fence/token` (written by atomic rename) before it does anything else on a takeover. The
*directory* is mounted, not the file, because a bind-mounted file keeps pointing at the old inode after a
rename. Every actor and the runtime read the file before each command and refuse a command whose token is
lower. This is the second check beside the node agent's own, and it is the one that works while the node agent
is busy killing containers. The same directory-mount rule applies to the sockets.

**The runtime control socket** (`rt.sock`, shared with the node agent only) carries: `status`, `journal`,
`probe_login`, `guard_status`. The runtime never receives a credential, a data key or a bundle. The exporter
hands the cookie journal back over the socket, and the node agent encrypts and uploads it. The watchdog does
not use this socket, because it must still work when the runtime is gone.

---

## 4. Entrypoint steps

The wrapper entrypoint runs these steps in order and then `exec`s the stock entrypoint, so Node ends up as
the container's main process under `--init`. Any failure exits non-zero and the node agent treats the wake as
failed. It never starts Steel with defaults.

### 4.1 Persona in

`/run/fleet/persona.env` is written by the node agent from the identity's persona record (section 5). It is
plain `NAME=value` lines. It is **sourced by a shell**, so the node agent validates every value against a strict
character set (`[A-Za-z0-9_./:+,-]`) before writing it.

### 4.2 The steps

1. **Read and validate `persona.env`.** Missing or invalid: exit.
2. **Engine and persona must agree.** Compare the major in `chromium --version` with
   `FLEET_CHROMIUM_MAJOR`, and the image flavor in `/opt/fleet/FLAVOR` with `FLEET_FLAVOR`. Mismatch: exit. A
   pinned UA that lags the engine is its own inconsistency ([AP-dos] risk 8).
3. **Right volume.** The marker `/app/api/user-data-dir/.fleet-identity` must equal `FLEET_IDENTITY`. Mismatch:
   exit. A wrong mount must never come up logged in as the wrong client.
4. **Clean `Singleton*`.** Delete `SingletonLock`, `SingletonSocket` and `SingletonCookie` from the volume.
   The real deletion is done by the node agent on the host, under the lease, before the container starts
   ([DEC] D4). Finding any here is logged as an alarm (`FLEET_ALARM stale_singleton`), because it means the
   previous release was not clean. Steel's own handling of a stale lock is a silent fallback to a blank
   profile ([EA-ver] EA-4).
5. **Time zone.** Export `TZ` and `DEFAULT_TIMEZONE` from the persona. The create call also always sends
   `timezone`; Steel passes it to Chromium as `TZ`. `TIMEZONE_SERVICE_URL` points at a closed loopback port so
   Steel's boot-time lookup, which otherwise calls ipinfo.io **directly, outside any proxy**, fails at once
   (`source (new)` `cdp.service.ts` ~L150, `timezone-fetcher.service.ts`). The egress rules would drop it
   anyway.
6. **Headful only: Xvfb and dbus.** Start `Xvfb :10 -screen 0 <W>x<H>x24 -nolisten tcp` where `<W>x<H>` is the
   persona's screen. Wait for the socket `/tmp/.X11-unix/X10`. Start dbus. The stock entrypoint starts dbus
   only when `DEBUG=true` and never starts Xvfb ([SC-ver] SCA-2, [S-dos] section 5), and the stock image
   cannot launch headful (`headless:false` returned 500). Whether dbus is truly needed, or Xvfb alone is
   enough, is **to measure** ([SC-ver] SCA-2 note). Setting the Xvfb screen to the persona screen may pin
   `screen`, because headful gave 1920x1080 where headless gave 800x600 ([AP-ver] AP-4); **to measure**.
7. **Chromium flags (via `CHROME_ARGS`, already in the container env).** See 4.4. The entrypoint refuses to
   start if `CHROME_ARGS` contains `--proxy-server` or anything that looks like credentials.
8. **Extension directory.** In the `research` flavor the Stagehand extension is baked into the image, not
   bind-mounted, because it must match the pinned SDK byte for byte ([SH-ver] missed issue 6) and a mount could
   drift. The entrypoint does nothing with it. Steel loads it only when the create asks for
   `extensions:["stagehand"]` (mode A). In mode B the SDK loads it by path (section 10.3). In the `account`
   flavor there is no such directory, and the entrypoint exits non-zero if it finds one or if `FLEET_FLAVOR` and
   the image label disagree. A bind mount would be the alternative if the pin ever has to change without an
   image rebuild.
9. **Proxy wiring check.** The forwarder shares this namespace and is already running (wake step 8). The
   entrypoint probes `127.0.0.1:<FLEET_FWD_PORT>` and exits if nothing answers. A missing forwarder is cheaper
   to catch here than as a page that never loads. The create call later sends only this address as `proxyUrl`.
10. **Egress is not the entrypoint's job.** The node agent installs the egress chain on the host and reads it
    back before this container starts (section 6.3). The entrypoint cannot see or change host rules. As a last
    local check it fails to start if it can open a direct TCP connection to the metadata address
    `169.254.169.254:80` (1 s timeout, a self-test of the rule).
11. **Hand over.** `exec /app/api/entrypoint.sh "$@"` with `--no-nginx`. The stock script sets
    `CDP_REDIRECT_PORT` and `DISPLAY` and `exec`s Node.

```sh
#!/bin/sh
# SKETCH. Not built, not tested.
set -eu
. /run/fleet/persona.env   # TZ LANG LANGUAGE FLEET_IDENTITY FLEET_FLAVOR FLEET_DISPLAY_MODE FLEET_SCREEN_W FLEET_SCREEN_H FLEET_CHROMIUM_MAJOR FLEET_FWD_PORT
DATA=/app/api/user-data-dir

major=$(/usr/bin/chromium --version | sed -n 's/[^0-9]*\([0-9][0-9]*\)\..*/\1/p')
[ "$major" = "$FLEET_CHROMIUM_MAJOR" ] || { echo "chromium $major != persona $FLEET_CHROMIUM_MAJOR" >&2; exit 65; }
[ "$(cat "$DATA/.fleet-identity" 2>/dev/null)" = "$FLEET_IDENTITY" ] || { echo "wrong volume" >&2; exit 66; }
[ "$FLEET_FLAVOR" = "$(cat /opt/fleet/FLAVOR)" ] || { echo "flavor mismatch" >&2; exit 70; }
if [ "$FLEET_FLAVOR" = account ] && [ -e /app/api/extensions/stagehand ]; then echo "extension in account image" >&2; exit 71; fi
for f in SingletonLock SingletonSocket SingletonCookie; do
  if [ -e "$DATA/$f" ] || [ -L "$DATA/$f" ]; then echo "FLEET_ALARM stale_singleton $f" >&2; rm -f "$DATA/$f"; fi
done
if [ "$FLEET_DISPLAY_MODE" = headful ]; then
  rm -f /tmp/.X10-lock
  Xvfb :10 -screen 0 "${FLEET_SCREEN_W}x${FLEET_SCREEN_H}x24" -nolisten tcp &
  i=0; while [ ! -S /tmp/.X11-unix/X10 ] && [ "$i" -lt 50 ]; do sleep 0.1; i=$((i+1)); done
  [ -S /tmp/.X11-unix/X10 ] || { echo "Xvfb did not start" >&2; exit 67; }
  mkdir -p /var/run/dbus; rm -f /var/run/dbus/pid; dbus-daemon --system --fork   # variant R
fi
# proxy wiring and egress self-test (steps 9 and 10). Node is in the image, so no new package.
tcp_open() { node -e 'const s=require("net").connect({host:process.argv[1],port:+process.argv[2],timeout:1000});s.on("connect",()=>process.exit(0));s.on("error",()=>process.exit(1));s.on("timeout",()=>process.exit(1))' "$1" "$2"; }
tcp_open 127.0.0.1 "$FLEET_FWD_PORT" || { echo "no forwarder" >&2; exit 68; }
if tcp_open 169.254.169.254 80; then echo "egress open" >&2; exit 69; fi
export TZ DEFAULT_TIMEZONE="$TZ" DISPLAY=:10
exec /app/api/entrypoint.sh "$@"
```

### 4.3 The Chromium wrapper (`/opt/fleet/chromium`)

Steel starts Chromium with `env: { HOME, TZ, DISPLAY }` and nothing else (`source (new)` `cdp.service.ts`,
`finalLaunchOptions`). Puppeteer hands that object to the child process, which replaces the container's
environment (inference from Puppeteer's documented `env` option; **to verify** by reading
`/proc/<chromium pid>/environ` from the host). So `LANG`, `LANGUAGE` and `DBUS_SESSION_BUS_ADDRESS` set on the
container would never reach Chromium. [DEC] D4's "`LANG`/`LANGUAGE` plus `--accept-lang`" is only half
effective on stock Steel. Steel honours `CHROME_EXECUTABLE_PATH` when the file exists (`source (new)`
`utils/browser.ts`), so:

```sh
#!/bin/sh
# SKETCH. Not built, not tested.
export PATH=/usr/local/bin:/usr/bin:/bin
. /run/fleet/persona.env
export LANG LANGUAGE
[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ] && export DBUS_SESSION_BUS_ADDRESS
exec /usr/bin/chromium "$@"
```

`exec` keeps Steel's kill path unchanged (the process Steel holds is Chromium itself). Glibc locale files are
not needed for Chromium to read the variables (**to verify**), so no package install.

### 4.4 Persona flags and the locale and WebGL recipe

| Persona value | How it is applied | Notes |
|---|---|---|
| User agent | Session `userAgent` + `skipFingerprintInjection:true` (section 9) | Chrome major equals the real engine major |
| Time zone | `TZ`, `DEFAULT_TIMEZONE`, session `timezone` | Always sent; with the proxy down and no value Steel used UTC ([RES] `[t1 #75]`) |
| UI language | `LANG`, `LANGUAGE` in `persona.env`, read by the Chromium wrapper | **To measure.** `--lang` does nothing on Linux ([AP-ver] V-1), so it is not used. |
| `Accept-Language` and `navigator.languages` | `--accept-lang=<list>` in `CHROME_ARGS` | Backup: session `userPreferences` with `intl.accept_languages`. Nobody has measured locale; every spike was en-US ([AP-ver] V-1). |
| WebGL | `--use-angle=swiftshader --enable-unsafe-swiftshader` in `CHROME_ARGS` | The cause of missing WebGL is **unproven**: a vanilla headful run without `--disable-gpu` also had none, and only these flags gave WebGL ([AP-ver] V-5; [S-ver] STE-11). Steel's own `--disable-gpu` and `--use-gl=swiftshader` may interact. Try (a) the flags alone, then (b) the flags plus `FILTER_CHROME_ARGS=--disable-gpu`. Keep the first that gives a stable, non-empty renderer in both modes. |
| Screen | Headful: the Xvfb `-screen` geometry | **To measure** |
| Window size | Session `dimensions` | Does not set `screen` in headless |
| Fonts | Not pinned. The base image has a CJK, Thai and Arabic font set. | An unusual set for an en-US persona. **To measure**; not changed in v0. |
| Cores, GPU string, canvas hash, UA-CH brands | Not pinned. Host-real. | Identical for every identity on a node ([DEC] D3) |

`CHROME_ARGS` is split on spaces, so no value may contain a space.

### 4.5 The `--disable-features` string: site isolation and the extension overrides

Steel's static flags carry **one** string: `--disable-features=TranslateUI,...,IsolateOrigins,site-per-process,...,
DisableLoadExtensionCommandLineSwitch,DisableDisableExtensionsExceptCommandLineSwitch` (`source (new)`
`cdp.service.ts` ~L873). Stagehand needs the last two. `FILTER_CHROME_ARGS` removes only whole arguments, so
changing any part of the string means filtering all of it and supplying a replacement in `CHROME_ARGS`. Two
`--disable-features` flags may not merge (the last may win). **To measure.**

- **`research` flavor.** Keep Steel's string. Re-enabling site isolation (only if Q-08 or the owner asks) means a
  replacement that drops `IsolateOrigins,site-per-process` and keeps the two extension features. Do not do this
  in v0 without a test that Stagehand still attaches.
- **`account` flavor** *(S14-4, S14-12)*. The replacement drops the two extension overrides, because nothing in
  this flavor loads an extension and the overrides only keep that capability alive. Whether the same
  replacement also drops `IsolateOrigins,site-per-process` is the Q-08 choice and is **not made here**.
  `--remote-allow-origins=*` is filtered separately (it is its own argument). Puppeteer connects from node with
  no `Origin` header, so Steel itself should not need the flag; the browser-based viewer talks to Steel, not to
  Chromium's own debugging port. All of this is **to measure** (T11n).

---

## 5. The persona record

Written once at identity creation by the owner, stored by fleetd, never regenerated ([DEC] D3). A change after
creation is a new identity and a new human login, except a **controlled persona migration** when the engine's
Chromium major changes (the UA follows the engine). Sketch of the fields the node agent needs:

```json
{
  "identity_id": "<uuid>",
  "persona_version": 1,
  "image_digest": "sha256:<digest>",
  "chromium_major": 152,
  "display_mode": "headful",
  "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
  "timezone": "America/Chicago",
  "locale": { "ui": "en_US", "languages": ["en-US", "en"] },
  "viewport": { "width": 1366, "height": 768 },
  "screen": { "width": 1920, "height": 1080 },
  "webgl_profile": "swiftshader-explicit",
  "proxy": { "secret_ref": "<fleetd secret id>", "expected_exit_ip": "203.0.113.7" },
  "kind": "account",
  "image_flavor": "account",
  "extension_mode": "none",
  "node_class": {
    "id": "<hash of the fields below>",
    "size_slug": "s-8vcpu-16gb",
    "base_image": "<droplet base image id>",
    "cpu_model": "<model name as /proc/cpuinfo reports it>",
    "vcpus": 8
  }
}
```

The **host-real baselines are not in the persona.** They are separate rows, one per node class, recorded by the
node agent and stored by fleetd (`persona_baselines`: persona id, node class id, `host_real_hash`, the fields
behind it, `recorded_at`, `admitted_by`). The persona stays immutable; a baseline is added only as described
under "Node classes" below.

Rules:

- The UA string is the amd64 form. Its Chrome major must equal the engine's real major, read from the image
  at build. On the arm64 test host the UA said `Linux aarch64` while `navigator.platform` said `Linux x86_64`;
  droplets are amd64 ([AP-ver] missed issue 11).
- **`kind`, `image_flavor` and `extension_mode` are persona fields, fixed at creation** *(S14-12, S14-7)*.
  `extension_mode` is `none`, `A` or `B` and follows the flavor table in section 2. It is not a per-wake
  argument and the caller cannot pass it. The node agent derives the **effective** mode for a wake: the
  persona's mode, except `none` for a human-login wake (`purpose=reauth`) and for a canary wake. A change of
  flavor or mode is a persona migration under the canary rule ([DEC] D13, [CONS] O-13).
- The IP, timezone and locale come from the proxy's geo at creation and are never looked up again
  ([AP-dos] Q5).
- fleetd gives the node agent a persona **reference and version**. The node agent builds `persona.env` and the
  create body from it. The agent profile never sees either.

### Node classes *(S08-8)*

Host-real values (core count, WebGL renderer, canvas hash, UA-CH brands, screen) come from the node, not from
the persona ([DEC] D3). Whether they differ between two droplets of the same size is **unverified** ([S-dos]
Q5; [ENG-S] 8.5), so the spec does not assume either answer.

- **A node class** is the set `{size slug, base image, CPU model, vcpus}`. The node agent reads the CPU model
  from `/proc/cpuinfo` at boot and reports its class id in the heartbeat. A node whose reported class does not
  match what the placer asked for is not used.
- **The persona holds the identity's home class.** The identity's first wake, on its home class, records the
  baseline for that class. P5 (section 7) compares the live host-real values to the baseline **of the class the node reports**.
  A mismatch inside a class means the class definition is incomplete: refuse the wake (`persona_mismatch`,
  detail `class_baseline`) and fix the definition in M1. It is never "an alarm and carry on".
- **Failover stays inside the class.** The placer filters nodes by class, by infra home and by tenant affinity
  ([DEC] D12, Q-13). This includes a `reconcile` wake after a node loss. P5 is never relaxed to let a wake
  through.
- **When no node of the class exists:** (1) the job waits in `queued` with reason `capacity`, and the scaler
  is asked for a droplet of the class (same size slug and base image; at most 10 droplets are created at once
  and the account's droplet limit is unchecked, [CONS] section 3b, D12). The new node joins only after its reported
  class matches. (2) If the scaler cannot supply one, or the job's window closes first, the job fails
  `infra_unavailable` with reason `no_node_in_class`. A `reconcile` job that fails this way leaves its effect
  `uncertain` and tells the owner, with the reason. (3) The owner may admit a second class for one identity:
  `class_admit(identity, class_id, reason)`. That records a new baseline, writes an audit row, marks the
  identity's next wake a canary (8.1), and means the account will see different hardware. It is never
  automatic.
- **M1 measures it** (T6, and [MS] G1.3 as [SCN] S09-2 asks): at least two droplets of the same size and base
  image, one of a different size, same host-real table on each. **Two outcomes, both reopen a decision.**
  *Equal across droplets:* a class collapses to "any node of this image", the one-client-per-node rule may buy
  nothing, and Q-13 and [DEC] D3 are reopened (the options become per-identity hardware values, Q-04, or a
  written linkability risk). *Different:* classes are real, failover and the autoscaler respect them, and
  [DEC] D12's "wake on any node" narrows to "any node in the class". The decision rule is the milestone's; this
  file only records the numbers and keeps both paths working.

---

## 6. Network, forwarder, egress

### 6.1 Per-identity network and holder

- The node agent creates a bridge network `fleet-<id8>` at wake and removes it at sleep. Docker's default
  address pools allow about 30 bridges per host (unverified, [SC-ver] SCA-14 note), and a node holds about 7
  to 13 awake identities ([SC-ver] SCA-5), so per-wake creation is enough. IPv6 is off.
- The **holder** `fleet-net-<id8>` is a container that only sleeps. It owns the network namespace and
  the hostname. It uses the wrapper image with `--entrypoint sleep ... infinity`, so no extra image is pulled.
  Steel, the forwarder, the runtime and every actor join it with `--network container:fleet-net-<id8>`
  (section 3.1). The holder is not an exposed surface: it has no listener and no mounts.

### 6.2 The forwarder (`fleet-fwd-<id8>`)

A small program that [DEC] D10 calls the node-local, credential-less forwarder. "Credential-less" means the
browser presents no credentials; the forwarder adds them. Candidates: proxy-chain (already proven inside
Steel) or gost; pick at build.

Requirements:

1. Listen on `127.0.0.1:<fixed port>` **inside the shared namespace** only.
2. Forward to the identity's dedicated static ISP IP. The upstream is addressed **by IP**, resolved at identity
   creation and re-checked at wake. A changed IP is an incident.
3. **Fail closed.** Upstream down, auth failure (407), timeout or an exit-IP change means no traffic and a
   signal to the node agent. There is no direct fallback, ever ([DEC] D10). The signal carries a **class**,
   because the two kinds need different handling upstream of this file *(S07-1, S07-13)*: `unreachable`
   (refused, timeout, DNS), `auth_failed` (407) and `mismatch` (the echo returned another IP). The first two
   are a vendor or network fault; `mismatch` is an incident. How fleetd names and acts on them is fleetd's
   call; the node agent only reports the class and never guesses.
4. **Credentials** come from a file on the host's tmpfs (`/run/fleet/secrets/<id8>/upstream`, mode 0400),
   bind-mounted read-only into the sidecar alone. Not in env, not in argv, not in `docker inspect`, not in the
   Steel container, not in any log. A separate process space matters because Steel's Chromium runs as root in
   the same PID namespace as everything else in its container (variant R).
5. **Control socket** on a host-mounted unix socket (`/run/fleet/<id8>/fwd/fwd.sock`) shared with the node
   agent only, not with the Steel container. Operations: `status`, `check_exit_ip`, `block`, `byte_counts`. Events it
   pushes to the node agent: `exit_ip_changed{first_bad_echo_at, last_good_echo_at}`, `upstream_error{class}`.
   The two timestamps are what the taint rule in 8.2 uses.
6. **Exit-IP check** against a **fleet-owned echo endpoint** (a third-party echo would see every identity),
   before Steel starts, then on a timer (interval **to measure**), and at sleep. A mismatch blocks all new
   connections and tells the node agent to stop the session (`infra_unavailable` for the call in flight; the
   identity hold, `proxy_mismatch`, is fleetd's). IPRoyal-style "sticky"
   sessions swap IPs silently unless `_killswitch-1` is set ([AP-ver] missed issue 8).
7. Count bytes (Steel's own counters stay at zero, issue #331).
8. Resource cap: tiny (**estimate** 64 MB, 0.1 CPU).
9. **No exception for private destinations, and no plain-HTTP service on the listener** *(S13-6)*. The
   forwarder serves proxy requests (`CONNECT`, and absolute-URI `GET` for plain HTTP) to **public**
   destinations only. It refuses every loopback, private, link-local and fleet destination, including **its
   own namespace's bridge IP on port 3000**, with no exception and no port carve-out. It answers any request
   that is not a proxy request (a page doing `fetch('http://127.0.0.1:<port>/')` at the listener) with a
   fixed refusal and nothing else. A destination written as an IP is checked after canonicalisation
   (`2130706433`, `0x7f000001`, `[::ffff:127.0.0.1]`), using the box's `security.py` canonicalizer
   ([DEC] D16). A destination written as a hostname is passed upstream and resolved on the vendor's side, so a
   name that points at a private address is not stopped here, and the Guard's local DNS check is advisory
   ([SC-dos] Q6; [SCN] S13 section 3.1 names the residual: a private target reached inside the vendor's
   network; **to measure**).

`PROXY_INTERNAL_BYPASS` stays empty and `--proxy-bypass-list=<-loopback>` is **not used**. With the forwarder at
`127.0.0.1`, `<-loopback>` would send the forwarder's own address through the proxy ([CONS] C-08; unverified
until a droplet run). Chromium's implicit bypass sends `127.0.0.0/8` direct, so loopback inside the namespace
is guarded by the Guard and by Local Network Access, **not** by the egress chain (6.3). That is the weak spot;
section 10.1 says what covers it.

**Why the old rule 9 is gone.** The earlier draft ran the workers outside the namespace, so they dialed the
bridge IP, and Stagehand's extension dialed that same address from inside Chromium. A bridge IP is not
loopback, so Chromium sent it to the proxy, and the forwarder needed a rule to serve a `CONNECT` to it. That
rule was indistinguishable from a page's own request to Steel's unauthenticated API at the same address. With
topology T-L (10.4) the actors and the extension dial `127.0.0.1:3000`, which Chromium bypasses on its own, so
[CONS] C-08 holds without any exception. **Fallback T-O** (workers outside the namespace) brings the exception
back for the `research` flavor only and never for `account` (10.4).

### 6.3 Egress rules

The identity's namespace may reach **only** the upstream proxy's IP and port. Everything else is dropped,
including DNS, the VPC, the host, `169.254.169.254` and every other public address. That also kills Steel's
boot-time direct ipinfo call and Chromium's implicit-bypass paths to link-local space. Stronger than the box,
which allows the public internet ([SC-dos] Q6). The template follows the box's rules
([BOX-OPS] "Host egress rules"), including the **INPUT** rule: traffic from a container to the host itself goes
through `INPUT`, not `DOCKER-USER`, and the box verified on a droplet that without it the browser reached the
host's sshd (2026-09-23).

```sh
# SKETCH. Not applied. NET = the identity's subnet. UP_IP:UP_PORT = its upstream proxy.
iptables -N FLEET-<id8>
iptables -A FLEET-<id8> -d "$UP_IP" -p tcp --dport "$UP_PORT" -j ACCEPT
iptables -A FLEET-<id8> -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FLEET-<id8> -j DROP
iptables -I DOCKER-USER -s "$NET" -j FLEET-<id8>
iptables -I INPUT 1 -s "$NET" -m conntrack --ctstate NEW -j DROP     # NEW only: replies to the node agent still flow
```

- The node agent installs the chain at wake and removes it at sleep, and **reads it back** (`iptables -S`)
  before starting Steel. No rule, no start.
- A packet from the container to its own bridge IP is delivered locally by the kernel and is not forwarded, so
  the iptables chain never sees it (reasoning; **to measure**). A page that tries its own bridge IP on port
  3000 does not get that far: Chromium sends it to the proxy setting, which is the forwarder, and forwarder
  rule 9 refuses it. Test T18 injects exactly that request.
- The echo endpoint is reached by the forwarder through the same upstream, so the check also proves the
  proxy path.
- **Applying these rules changes the firewall of a droplet. It needs Justin's explicit yes** ([`CLAUDE.md`](../../../CLAUDE.md)).
- The deny list in the Guard also includes the fleet's own public hostnames and droplet IPs ([SC-dos] Q6).
  The Guard's local DNS check can disagree with what the proxy resolves, so it is advisory; the network rule is
  the control ([SC-dos] Q6).

---

## 7. Health and auth probes

Steel's health and session answers are not evidence ([S-ver] STE-1, STE-3). These probes replace them. Run in
order; stop at the first failure.

| # | Probe | How | Pass | On failure |
|---|---|---|---|---|
| P0 | Container up | Docker state, not a `HEALTHCHECK` | Running | Teardown, `infra_unavailable` |
| P1 | Node answers | `GET /v1/health` | 200 | Same. **Liveness only.** |
| P2 | A browser exists | CDP `Browser.getVersion` | Product major equals `chromium_major` | Same |
| P3 | Right profile | Chromium's argv from the host (`docker top`, no exec in the container) | Has `--user-data-dir=/app/api/user-data-dir`; the only `--proxy-server` is `http://127.0.0.1:<port>`; no credential-like strings; extension flags match the wake's mode; sandbox flags match the variant | One retry after clearing `Singleton*` under the lease, else `held` |
| P4 | Guard attached | The Guard's generation matches the browser generation, and the watchdog (10.1) holds its connection | Ready | No actor is started |
| P5 | Persona | JS on `about:blank` (no network): UA, `navigator.languages`, time zone, `innerWidth/Height`, `screen`, WebGL renderer (non-empty), `hardwareConcurrency`, a fixed canvas hash, UA-CH brands, `navigator.webdriver`, any `#__cursor__` element; plus, from the flavor, that no extension target exists (`account`) | Pinned fields equal the persona. Host-real fields equal the baseline **of the node class the node reports** (section 5). | Refuse the wake (`persona_mismatch`). No baseline for this class: refuse unless this is the identity's first wake or a `class_admit` was recorded. |
| P6 | Exit IP | Forwarder control socket | Equals `expected_exit_ip` | Refuse the wake; block. Record the class (`mismatch` or `unreachable`). |
| P7 | Login | A deterministic per-site check (below) | Logged-in marker present | `needs_reauth` or `checkpoint` |

**P7, the login probe.** Read-only. It navigates the primary tab under the Guard, looks for a logged-in marker,
a login wall, or a checkpoint (CAPTCHA, 2FA, "suspicious activity"), and reports one `auth_result` per site:
`ok` (the wake is `ready`), `login_wall` (`needs_reauth`), `checkpoint`, `captcha`, `restricted` or `error`.
That is [ARCH] 3.3's `auth_markers.last_result` vocabulary plus `restricted`, which [SCN] S05-4 proposes. A
tag `unknown` is used where no probe ran in the wake (8.2). It never types, never clicks "log in", never
retries a login. The marker is code
(layer L0, [DEC] D5); the probe definitions are released procedures owned by the engine docs. A System 1
`login_wall` question may be a second opinion, never the only check, because a decider is not a safety control
([DEC] D7). It runs when an identity wakes for work and after a human login. **There is no keep-warm schedule**:
a weekly scripted login on Meta adds terms exposure for little benefit, and API-channel identities use token
health checks instead ([DEC] D14, [CONS] O-12).

**P6 on its own.** `probe_ip` (section 9.2) is P6 run for a sleeping identity, with no Steel, no volume and no
bundle, so a dead or swapped IP is found before a wake needs it *(S07-13)*.

**Fault injection must be caught.** The probes exist because of these failures, and the tests in section 12
inject each: a stale lock that makes Steel answer 200 on a blank profile ([RES] `[t1 #56]`); a health route
that says `ok` with no browser; a made-up `released` record for a live session ([S-ver] STE-1).

---

## 8. Wake, release, flush, snapshot, and state bundles

### 8.1 Wake

A wake is asynchronous: fleetd submits it and polls. The tool budget is 90 s, and a cold wake is at least
11.7-21.6 s as one composite on arm64, **excluding** bundle download and decrypt, proxy connect, the IP and
persona checks, and node creation ([CONS] C-27, C-15; [DEC] D1, D12). Treat that as a floor.

**Wake modes.** The lease purpose is fleetd's ([ARCH] 3.5: `work`, `reconcile`, `reauth`, `maintenance`). The
node agent adds one **mode** that limits what may run:

| Mode | Actors | Prober (P7) | Used for |
|---|---|---|---|
| `normal` | Started after P4, P6, P7 pass | At wake | `work`, `reconcile`, `maintenance` |
| `reauth` | None | Not at wake. Runs after the human presses "login done". | A human login or takeover |
| `canary` | None | At wake, plus read-only passes the owner sets | The first wake after an IP hold is cleared, after a `class_admit`, or after the owner promoted an `incident` generation *(S07-12)* |

No mode loads the Stagehand extension unless the persona's `extension_mode` is `A` or `B` and the mode is
`normal` (section 5).

1. **Pre-wake.** fleetd calls `probe_ip` (9.2) before it plans the wake. A failed probe means nothing below
   starts and no bundle ever reaches a node. fleetd then holds the lease (agent kind) and sends
   `wake(identity, persona_ref, bundle_ptr, purpose, mode)` with the fencing token.
2. The node agent checks the token against the highest it has seen for the identity, checks capacity and disk,
   checks the **one-client-per-node rule** (pending Q-13), and checks that the node's reported **class**
   is the persona's home class or one the owner admitted (section 5).
3. Fetch the bundle named by `bundle_ptr`. fleetd names `current_bundle_gen`, which is always a **clean**
   generation (8.2, 8.4). Two exceptions, both explicit and recorded: a `reauth` wake may be given the newest
   *parked* generation that is not `tainted_ip` (to resume an interrupted login), and the owner may `promote`
   a parked generation to current. **A generation tagged `tainted_ip` is never restored.** If no clean
   generation exists, the directory is empty and the first wake is a human login. Verify size and hash.
   Decrypt (section 8.5). Extract into a fresh 0700 directory.
4. Delete `Singleton*`. Write or verify `.fleet-identity`.
5. Write `persona.env` and the forwarder secret (tmpfs).
6. Create the network and the holder.
7. Install the egress chain and read it back.
8. Start the forwarder. Wait for its socket. Run P6. Fail: tear down (failure rule below).
9. Start Steel. Wait for P1, with a start period like the box's 40 s.
10. Send the one create call ([ENG-S] section 2.2). One call, never two. `extensions:["stagehand"]` only when
    the effective mode is `A`.
11. P2, P3, P5.
12. Start the runtime. Attach the Guard (P4). The node agent's watchdog opens its connection (10.1).
13. P6 again.
14. P7 for each site the identity maintains (not in `reauth` mode). **From here on a session has run.**
    *Re-injecting the journal (S05-12).* If P7 says `login_wall` and a journal exists, the cookies are
    re-injected once (untested: either `sessionContext` with `persist` or `Network.setCookies` over CDP), then
    P7 runs again. Re-injection is allowed only when **all** hold: (a) the journal is newer than the restored
    generation; (b) the journal is tagged `auth_result: ok`, is not `tainted_ip` and has no `incident`; (c)
    the identity's most recent recorded result is not `checkpoint`, `captcha` or `restricted`. Otherwise it is
    skipped, because replaying the cookies of a session the platform has revoked or challenged can itself look
    like suspicious reuse. Still out after one re-injection: `needs_reauth`. Never loop.
15. Report `ready`, `needs_reauth` or `checkpoint`. Start the timers: journal (each journal is tagged like a
    snapshot, 8.2), maximum wake time, inactivity, exit-IP check, memory watch. In `normal` mode the node
    agent starts actors with `worker_start` (9.2), which it refuses until P4 has passed.

**"A session ran"** means the first of: P7 began its first navigation (step 14), an actor was started, or a
viewer route was opened. Before that, the browser has made no request to any platform, so the profile on disk
is byte-for-byte the restored bundle plus the lock cleanup.

**Failure rule.** Only the stale-lock case gets one automatic retry, after clearing the lock under the lease.
Anything else tears down (stop containers, remove network and rules) and reports an error from the D17
vocabulary. The agent does not retry blind ([S-dos] section 4 note 10). What happens to the volume depends on
whether a session ran *(S07-15)*:

- **No session ran.** The node agent deletes the decrypted volume and the tmpfs secrets as part of the
  teardown. The bundle in Spaces is unchanged, so nothing is lost and no plaintext cookie store is left behind.
- **A session ran.** A snapshot is owed. The node agent runs the sleep path (8.2) as far as it can and the
  generation is tagged by what happened. If the sleep path cannot finish, the identity is `held`, the volume is
  kept, an alarm is raised, and `salvage` (9.2) is the only way it leaves the node: it encrypts the volume as a
  parked generation tagged `salvage`, verifies it, and deletes the plaintext. There is no silent keep (8.6).

### 8.2 Release, flush, snapshot, tags, and the pointer (the only way an identity sleeps)

**This is the one spec of the sleep.** [ENG-S] section 4.4 gives the reasons and the evidence; [ARCH] section
4.9 should point here for the order, the numbers and the flag name instead of restating them *(S01-6)*. Steps
and the node-agent operation that does each:

| # | Step | Notes |
|---|---|---|
| 1 | `quiesce`: actors finish or cancel the current step, disconnect their own way, and the node agent stops their containers | Stagehand uses `stagehand.close()`, never `browser.close()`. Browser-Use ends its session without closing the browser. Actors hold no profile state, so stopping them is safe. |
| 2 | Record `auth_result` for each site | The newest P7 result of this wake, combined with any blocker an actor reported mid-wake (`login_wall`, `checkpoint`, `captcha`, `restricted`); the worst one wins. `unknown` if no probe ran. |
| 3 | Navigate open tabs to `about:blank` | Stops page timers that rewrite cookies. Added; **to measure** |
| 4 | `journal`: export the context | Journal #1, crash insurance. [DEC] D4 puts the export before the hold. |
| 5 | Hold (below) | Quiet period before close. |
| 6 | `journal` again | Journal #2, the one of record. *Added; untested.* Read-only. |
| 7 | CDP `Browser.close` | 0 `Singleton*` in 3 of 3 runs |
| 8 | `POST /v1/sessions/release` | Without it Steel keeps the session `live` |
| 9 | Volume check | No `Singleton*`. No Chromium holds the volume. |
| 10 | Snapshot (8.4), tag, upload, verify, conditional pointer move (below) | The pointer move checks the fencing token and the tags |
| 11 | Stop the container, the sidecar, the runtime and the holder. Remove the chain and the network. Delete the local volume. | The local copy is plaintext in practice |

**The hold (step 5).** One set of numbers, set in M1 and only then final:

| Parameter | Value | Where it comes from |
|---|---|---|
| Floor | 31 s of quiet | The single measured keep, about 1.5 s over Chromium's 30 s commit timer ([ENG-S] 4.2). Never configure lower. |
| Default | 35 s | A chosen margin, **not a measured threshold** |
| Poll interval | every 5 s | **Estimate.** Each poll exports the in-memory cookie list (instant, includes httpOnly) and compares it with the last one. A changed list restarts the quiet period. |
| Maximum | 90 s | **Estimate.** When it is reached the sleep goes on and the generation is flagged `journal_authoritative`. |

The flag is `journal_authoritative` (bool): the cookies on disk may be stale, so the journal, not the tarball, is
the source of truth for cookies. It is the only name. [ARCH]'s `cookies_unflushed` is retired in its favour.
M1 measures the real threshold, the poll cost on a busy social page, and how often the cap is hit (T5(e)).

**Tags.** Every generation and every journal (including the periodic ones in a long wake) carries these in its
manifest (8.4), set by the node agent at the time it is made:

| Tag | Values | Set when |
|---|---|---|
| `auth_result` *(S05-12)* | `ok`, `login_wall`, `checkpoint`, `captcha`, `restricted`, `error`, `unknown`; plus the per-site map | Step 2 for a snapshot. For a periodic journal, the newest P7 result at that moment. |
| `tainted_ip` *(S07-12)* | bool | The forwarder reported `exit_ip_changed` during this wake. A snapshot made after that is tainted. A journal is tainted if it was taken **after** `last_good_echo_at`, because the swap happened somewhere between the last good echo and the first bad one; journals up to `last_good_echo_at` stay clean. |
| `incident` | none, or `guard_dropped` | The Guard was lost during this wake (10.1) |
| `journal_authoritative` | bool | The hold hit its maximum |
| `salvage` | bool | The generation came from a held volume (8.1) |

**The pointer moves only to a clean generation.** Clean means `auth_result: ok` for every site the identity
maintains, `tainted_ip: false`, and no `incident`. fleetd moves `current_bundle_gen` by compare-and-set on the
fencing token, and the node agent's `sleep` result carries the tags so fleetd can apply the rule. A generation
that is not clean is **still uploaded, encrypted and verified** (so nothing is lost), but it is **parked**:
`current_bundle_gen` stays on the newest clean generation. A parked generation can be used in two explicit
ways, each an audit row with a reason: the next `reauth` wake may resume it (an interrupted login), or the owner
may `promote` it. `tainted_ip` generations cannot be promoted. This is how "unless the diff is explicit"
([SCN] S05-12) is met: advancing the pointer past a generation that is not clean is always an explicit act with
a reason, never a side effect of a sleep.

**After an IP hold clears** *(S07-12)*. The next wake restores the last untainted, clean generation (never a
tainted one) in `canary` mode: no actors, P7 only, plus the read-only passes the owner sets. If no such
generation exists, the first wake is a human login on an empty profile. fleetd allows `work` only after the
canary passes.

**What goes wrong, and the outcome** (this is the failure list for the sleep; the wake's list is in 8.1):

| Event | Outcome |
|---|---|
| Step 7, 8 or 9 fails (`Browser.close`, release, volume check) | `held`. Nothing is deleted. A person looks. |
| Snapshot, upload, verify or the pointer move fails | `held` with reason `upload_failed`. The volume is kept, the upload is retried with backoff, an alarm is raised. `salvage` is the exit if it cannot be fixed. |
| The forwarder reports an exit-IP change during the wake | The forwarder blocks and the session stops. The sleep path still runs (it needs no proxy: the journal export and `Browser.close` are local, and the upload leaves from the host, not the namespace). The generation and the late journals are tagged `tainted_ip`. The identity is `held` with reason `proxy_mismatch`. The pointer does not move. |
| The Guard is lost during the wake | Pages are blanked and actors killed at once (10.1). The sleep path then runs. The generation is tagged `incident`, so it is parked until the owner has looked. |
| `auth_result` is not `ok` | The generation is uploaded and parked. The pointer stays. The owner sees which sites failed. |
| The cookies never go quiet | The hold ends at its maximum. The generation is flagged `journal_authoritative`. Not an error. |
| The node dies or the agent aborts | Section 8.3. |

One site failing its probe parks the whole generation, because the cookie jar cannot be split by site. If the
failing site is not the one the work needs, the owner can `promote` the generation.

### 8.3 Crash recovery

A killed or lost container loses up to 30 s of cookie writes. The lease expires, the run is marked
`interrupted`, any open effect becomes `uncertain` and blocks replay ([DEC] D13). The next wake restores
`current_bundle_gen` (a clean generation, 8.2) and may re-inject the newest **clean** journal under the rule in
8.1 step 14; a journal tagged non-`ok`, `tainted_ip` or `incident` is never used for that. Periodic journals
are tagged when they are made, so a crash does not lose the tags. The node agent, after its own restart, lists
containers labelled `fleet.identity`, asks fleetd for each lease, and `abort`s any container without one (hard
stop, no snapshot, volume kept, identity `held`). The kept volume leaves the node only through `salvage` (8.6).

### 8.4 State bundle

- **Contents:** the profile directory minus caches and locks. Exclusions, from [SC-dos] Q2:
  `Singleton*`, `Cache`, `Code Cache`, `GPUCache`, `Dawn*Cache`, `GrShaderCache`, `ShaderCache`,
  `Service Worker/CacheStorage`. That list is **not tested against a logged-in social profile**; M1 checks that
  a restored slim bundle stays logged in. The list is a versioned file.
- **Format:** tar, then zstd, then an authenticated stream cipher. Use a vetted streaming AEAD library. Do not
  hand-roll the cipher.
- **Manifest** (inside the encrypted body): identity id, generation, fencing token, `chromium_major`,
  `image_digest`, `persona_version`, node class id, created time, sha256 of the plain tar, and the **tags**
  of 8.2 (`auth_result` with its per-site map, `tainted_ip`, `incident`, `journal_authoritative`, `salvage`).
  The node agent also reports the tags in its `sleep` result; fleetd stores them next to the generation row.
  At restore the two copies are compared, and a mismatch refuses the restore.
- **Names:** `identities/<identity_id>/gen-<fencing_token>-<wake_uuid>.bundle.enc` and `....journal.enc`.
  Retention: the last 5 versions (**estimate**, [SC-ver] unsourced list). **Retention never deletes the
  newest clean generation or the newest clean journal**, even when five newer parked ones exist, because a
  run of parked generations (for example during a long IP hold) must not push out the only state that may be
  restored. A `tainted_ip` generation is kept for forensics until ordinary retention removes it.
- **Pointer:** a Postgres row (bundle key, sha256, size, fencing token, `chromium_major`, tags). It moves
  **only to a clean generation** (8.2). The update is **conditional on the fencing token**, so a stale node
  cannot overwrite a newer generation ([SC-dos] Q2). Parked generations have no pointer; `promote` and the
  `reauth` resume are explicit rows in the audit log.
- **Size:** 57 KB slim after 8 light pages (measured, [SC-dos] section 1). 50 MB is the planning figure
  (estimate). Steel Cloud caps a profile at 300 MB (`https://docs.steel.dev/overview/profiles-api/overview.md`); use that
  as a sanity ceiling, not a requirement. Large bundles slow every wake.
- **Compatibility:** refuse to restore a bundle into an image with an older Chromium major than the bundle's
  (profiles are not downgrade-safe; engineering judgment, **to verify**).
- **Cross-host:** tarball to Spaces to another droplet and another architecture was **never run**
  ([S-ver] STE-5). The fleet is amd64 only, so test amd64 to amd64 on two droplets (T13).

### 8.5 Encryption in Spaces

Chromium's cookie store uses `--password-store=basic`, a fixed key, so the profile protects nothing and the
bundle layer does all the work ([SC-ver] SCA-4; [CONS] O-09).

- **Envelope encryption.** A fresh random data key per bundle. The data key is wrapped by a master key held in
  fleetd's secret store. DO has no managed KMS that the research could confirm ([SC-ver] SCA-12 note 5), so
  the master key lives in fleetd.
- **Bound to the identity.** The AEAD associated data is identity id + generation + fencing token + manifest
  version. A bundle swapped between identities, or replayed from an older generation, fails to decrypt.
- **Who can decrypt.** fleetd. A node agent receives the one unwrapped data key it needs for one wake, in
  memory or tmpfs, never the master key.
- **Journals** use the same scheme.
- **Rotation.** New data key per bundle; rotating the master key re-wraps keys, not bundles.
- **Offboarding.** Delete the wrapped keys and the objects. Deleting the keys is a crypto-shred.
- **Spaces.** Private bucket, TLS, no public ACL, keys limited as far as DigitalOcean allows (**to check**;
  Spaces lifecycle rules were not checked, [SC-ver] "Not verifiable").
- **Never in plaintext** on Spaces, in logs, or in a droplet snapshot. Node base snapshots (used to avoid
  pulling the 2.66 GB image at wake, [SC-dos] Q2; that figure is unsourced) are taken from a node with no
  identity volumes.
- **Custody is an open design decision (O-09):** KMS versus a per-identity key versus an operator key. This
  section is the recommendation.

### 8.6 Local volume

The decrypted profile is on a node's disk only while it is needed. The rules, in one place *(S07-15)*:

| Situation | What happens to the plaintext volume |
|---|---|
| Clean sleep | Deleted after the bundle is verified (8.2 step 11) |
| A wake fails and **no session ran** (8.1) | Deleted at teardown. The bundle in Spaces is unchanged. |
| A wake fails and a session ran | The sleep path runs. If it finishes, the volume is deleted as for a clean sleep. |
| The sleep path cannot finish (`held`) or the agent `abort`ed | The volume is kept, an alarm is raised, and a **bounded time** (value to set) after which the alarm escalates. It leaves only through `salvage`: encrypt it as a parked generation tagged `salvage`, verify, then delete the plaintext. |

Whether a held volume should sit on an encrypted local volume in the meantime is **to decide**; today a
profile on disk is plaintext in practice ([SC-ver] SCA-4).

An LRU cache of plaintext profiles on the last node would speed wakes but keeps client cookies on a droplet
disk. Do not add it until wake time is measured, and then only with a bounded TTL and the one-client-per-node
rule.

---

## 9. The node-agent contract

fleetd is the only caller. The node agent listens on the droplet's private (VPC) address behind a DigitalOcean
Cloud Firewall that allows only the control-plane tag ([SC-dos] Q6), with service-to-service authentication
(mechanism: fleetd design). It is a **contract**, not a wire format.

### 9.1 Rules for every call

- Carries `identity_id`, a **fencing token**, and a request id. The agent keeps the highest token seen per
  identity on its own disk and refuses lower ones. A human takeover bumps the token, so the agent's in-flight
  calls fail closed ([DEC] D12). On a higher token the agent first writes the **fence file** (3.1), then kills
  the actors (10.3), then closes older viewer routes (9.4).
- One operation per identity at a time (a per-identity mutex), on top of the lease.
- Idempotent by request id. Slow operations (`wake`, `sleep`) return at once with an id and are polled.
- Errors use the D17 vocabulary: `identity_busy`, `needs_reauth`, `checkpoint`, `outcome_uncertain`,
  `infra_unavailable`, `scope_denied`, plus `persona_mismatch` and `stale_fencing` for this layer. A refusal
  that comes from the node's state carries the state (`identity_busy{state: waking}`).
- Nothing returns a Steel URL, a CDP URL or a proxy value to fleetd except as defined below.
- **Per-identity state at the agent:** `absent`, `waking`, `ready`, `awake` (actors running), `quiescing`,
  `sleeping`, `held`. Operations check it (9.4 uses it for takeover).

### 9.2 Operations

| Operation | Does | Returns |
|---|---|---|
| `probe_ip(identity, proxy_ref, secret)` | P6 for a sleeping identity, with no browser. See 9.6. Refused for an awake identity. | `{match, exit_ip, class: ok / mismatch / unreachable / auth_failed / timeout, latency_ms}` |
| `wake(identity, persona_ref, bundle_ptr, purpose, mode)` | Section 8.1. The agent derives the extension mode from the persona and the mode; the caller cannot pass one. | A wake id; then `ready` / `needs_reauth` / `checkpoint` / `failed` with the failing probe |
| `status(identity)` | Container, probes, Guard, forwarder, timers, viewer routes | State and a one-line reason per component (the box's `status` habit, [`CHARTER.md`](../../../CHARTER.md)) |
| `worker_start(identity, kind)` | Starts one actor container (`executor`, `stagehand` or `browseruse`) in the namespace | A worker id. Refused until P4 has passed, for any token but the current one, and in `reauth` or `canary` mode. |
| `worker_stop(identity)` | `docker kill` of every actor container (10.3) | The list of workers killed and the step each had in flight, if any |
| `cdp_endpoint(identity, client_kind)` | **Fallback topology T-O only (10.4).** Gives a node-local worker outside the namespace the CDP URL. | The URL, only after P4 passes, only for the current fencing token, with an expiry. Refused otherwise. Not present under T-L. |
| `journal(identity)` | Context export through the runtime, encrypted and uploaded, with tags (8.2) | Journal id and tags |
| `quiesce(identity)` | Steps 1 to 3 of 8.2 | Done |
| `sleep(identity)` | Section 8.2 | `slept` with the bundle id and its **tags**, or `held` with the failing step |
| `abort(identity)` | Hard stop for a crash or an orphan; no snapshot; volume kept | `held` |
| `salvage(identity)` | Encrypts a held volume as a parked generation tagged `salvage`, verifies it, deletes the plaintext (8.1, 8.6) | Generation id |
| `viewer_open(identity, mode, subject, limits, human_fencing?)` | Opens a route-allowlisted viewer route. `mode` is `control` or `watch` (9.4, 9.5). | An internal route token for the gateway |
| `viewer_extend(identity, route)` | Resets the idle timer of a control route. Never extends the maximum. | New idle deadline |
| `viewer_close(identity, route?)` | Closes one route, or every route for the identity | Done |
| `probe(identity, kind)` | Runs one probe on demand | Pass or the failure |

**Events the node agent pushes to fleetd** (counts and ids only, never page content): `exit_ip_changed`
(with `first_bad_echo_at` and `last_good_echo_at`), `upstream_error{class}`, `guard_dropped` (with the page
URLs that were open, no cookies), `viewer_activity{route, input_frames, last_input_at}`,
`viewer_closed{route, reason}`, `probe_failed`, `memory_threshold`, `held{reason}`.

### 9.3 What the agent enforces by itself

- **Takeover guard.** At most one create per container. Steel will not refuse a second one
  ([S-ver] STE-1), so this layer does.
- **Route allowlist to Steel.** The agent itself calls only the routes in [ENG-S] section 2.1. The viewer proxy
  passes only `GET /v1/sessions/debug` and the cast websocket upgrade, and the proxy sets the parameters
  itself: in `control` mode `interactive=true`, in `watch` mode `interactive=false` and `showControls=false`,
  whatever the client sent. `theme` and `pageIndex` pass through; the cast upgrade accepts `pageIndex` and
  `tabInfo`. Everything else returns an error: the REST list route (it leaks the proxy URL), the CDP websocket
  at `/`, `/documentation`, `/v1/logs/*`, `/v1/events`, files, scrape.
- **Timers.** Maximum wake time and inactivity (Steel has none, [S-ver] STE-8), exit-IP check, journal, memory
  watch. The memory threshold is set from M1 data (**estimate** until then: a fraction of the 1.5 GiB cap).
  Crossing it triggers a safe sleep and wake, never a kill. **While a control route is open the timers change
  (9.4):** a person is never put to sleep, and never restarted, by a timer meant for an agent.
- **No payload logging** on the viewer path. Logs never contain cookie values, journal contents, proxy values
  or keystrokes. Container logs are collected with a redaction rule and tested (T9). The agent counts input
  frames for liveness and nothing else.
- **Guard watch.** The agent reacts to a lost Guard at once (10.1).
- **Persistent node state** survives an agent restart: highest fencing tokens, the container inventory, wake
  records, open viewer routes.

### 9.4 Human control sessions *(S12 G12-7; G12-1 for the node-agent half)*

A human control route is the viewer opened under a human lease. These rules are the node agent's; the lease,
the ticket and the operator's login are fleetd's ([ARCH] 3.5, 4.8). All time values are **to set**; none is
chosen here.

1. **Timers follow the viewer, not the agent.** While a control route is open, the agent-lease timers (maximum
   wake time, inactivity) are replaced by two viewer timers: an **idle timeout**, reset by viewer activity (a
   count of client input frames, never their content) or by `viewer_extend`; and a **maximum length**, a hard
   bound that `viewer_extend` cannot move. An idle reader is therefore not put to sleep by the agent's
   inactivity timer. When either viewer timer ends, the agent closes the route and tells fleetd
   (`viewer_closed{reason}`). It does not sleep the browser by itself; fleetd decides after the hand-back.
   The memory watch only raises `memory_threshold` during a control route. It does not restart a browser under
   a person.
2. **State guard.** `viewer_open(control)` is refused unless the agent's state is `ready` or `awake`. In
   `waking`, `quiescing` or `sleeping` it returns `identity_busy{state}`. Whether fleetd queues the takeover or
   tells the person to wait is fleetd's choice. In `awake` with actors running, the takeover first runs the
   kill sequence in 10.3, and the route opens only after it has finished.
3. **Reconnect window.** Starting a viewer session uses the ticket once and creates a **viewer session**
   bound to (identity, fencing token, operator). If the websocket drops, the same operator may reopen the route
   for that viewer session within a **reconnect window** (value to set) with no new ticket, no new takeover and
   no token bump. After the window the route is closed and the person must take over again, which bumps the
   token. The reopen is authenticated by fleetd as the same operator; the node agent only checks the route
   token and the window.
4. **One control route at a time; a new takeover closes the old one.** A `viewer_open(control)` with a higher
   token closes every earlier control route for the identity before the new one opens. A second operator with
   the *same* token is refused (`identity_busy`). fleetd also calls `viewer_close` on every token change and at
   lease release, and the agent closes a route by itself the moment it sees a token higher than the route's
   (defence in depth: the route can never outlive its lease).
5. **Watch routes are not touched** by a takeover, because they cannot write. They close when the identity
   sleeps.

### 9.5 Watch tickets *(S12 G12-8)*

A watch route lets a person see the browser without taking the lease from the agent. It exists because the only
other way to look is a takeover, which stops the agent.

- **No lease, no token bump, no kill.** It cannot preempt anyone. It needs the same operator authentication as
  a takeover and is scoped to the operator's tenant. Each watch is an audit row: who, which identity, start,
  end. No payload is logged.
- **The agent enforces read-only itself.** The proxy sets `interactive=false` (9.3), and it terminates the
  viewer's websocket and opens its own to Steel. It forwards server-to-client frames and **drops every
  client-to-server frame**, counting the dropped ones (`viewer_activity`, so an attempted write is visible).
  Reason: in the pinned source, `interactive` appears only in the viewer page template, the query schema and the
  controller that renders the page. The websocket handler (`casting.handler.ts`) never reads it, and it
  acts on `mouseEvent`, `keyEvent`, `navigation`, `closeTab` and `getSelectedText` from any client (`source (new)`, read in
  `steel-browser@1131a02`; **M1 confirms on the tested image**). So the corpus's "read-only view"
  (`https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md`) is a property of the page, not of the
  server.
- **A watch is not free for the browser** (`source (new)`, to measure). Each cast connection makes the handler
  open its own puppeteer connection to the browser, create a CDP session on the page it shows, call
  `bringToFront()` on that page and start a screencast. A watcher who picks another tab would move the
  foreground tab under a running agent. So the proxy allows a watch connection only to the tab the executor
  reports as the active one, plus tab-list mode (`tabInfo`), which does not bring a page to the front. Watching
  also adds CDP activity that a public automation check may see. M1's detectability arm measures it ([SCN]
  S14-5 asks for the viewer in the stack). **Until that is measured, the default is off for `account`
  identities (the owner can switch it on for one identity, knowing the risk) and on for `research`
  identities.** Concurrent watchers per identity are capped (value to set from the CPU cost).
- **Where it is requested.** Watch tickets are minted through the operator console, as takeover tickets are
  ([ARCH] 4.8). They are not a Hermes tool, so the tool surface in [DEC] D17 does not change. How the operator
  authenticates is still open ([ARCH] 9, item 8).
- **Not offered for Browserbase-homed identities.** Their Live View URL is a bearer capability and its
  read-only mode is a property of the embedding page only ([`https://docs.browserbase.com/platform/browser/observability/session-live-view.md`](https://docs.browserbase.com/platform/browser/observability/session-live-view.md)).
  There, screenshots are the substitute. That rule belongs to the Browserbase guide; it is stated here so the
  two stay in step.

### 9.6 `probe_ip`: the IP check for a sleeping identity *(S07-13)*

Idle IP death would otherwise be found only at wake, when a replacement can take longer than the lead time to
the next job.

- **What it does.** Starts only the holder and the forwarder (no Steel, no runtime, no volume, no bundle),
  installs the egress chain, runs the forwarder's `check_exit_ip` against the fleet-owned echo endpoint, and
  tears everything down. It takes seconds and sends nothing to any platform. It is P6 on its own.
- **Credential delivery.** The upstream credential is **not** kept on any node. fleetd's secret store holds it
  at rest. For each call fleetd sends it inside the request body, over the node agent's authenticated channel,
  never in a URL, header or argv. The agent writes it to the tmpfs file (`/run/fleet/secrets/<id8>/upstream`,
  mode 0400), mounts that file into the forwarder only, and removes the file at teardown. It lives in the
  agent's memory only for the call. This is the same path a wake uses, so a probe adds no new place where a
  credential lives. [ARCH] 6.8 says credentials reach a node "at wake"; they now also reach it for a probe.
- **When.** On a schedule per identity, and as the first step of pre-wake (8.1 step 1). The interval is a
  parameter fleetd sets from the vendor's failure rate (unknown, **to measure**) and the shortest lead time
  to a job; this file chooses no figure. fleetd keeps watching `term_expires_at`; the probe covers an IP that
  dies before its term ends.
- **Result and alert.** The result carries a class (`ok`, `mismatch`, `unreachable`, `auth_failed`, `timeout`).
  The first failure raises `probe_failed` and fleetd alerts the owner at once. `mismatch` is an incident;
  the others are a vendor or network fault that fleetd may retry with backoff ([SCN] S07-1 asks [ARCH] to name
  both). A probe never changes an identity's state by itself.
- **Where.** Any node of the identity's allowed set, preferably its affinity node. **If the vendor
  authenticates by source IP, the probe node must be on the vendor's allow-list.** The research does not say how
  the vendor authenticates ([SCN] S07 "Not checked"); it is a provenance-statement question ([ID] 3.3 check 5).
- **Not while awake.** An awake identity's own forwarder already checks on a timer. fleetd does not call
  `probe_ip` for an identity that is awake on any node, and a node refuses it for an identity awake there.

---

## 10. The Guard and where engines attach

### 10.1 The Guard, and what happens when it drops

The box's in-browser `Guard` (one CDP client with browser-wide request interception, [BOX-SEC]) runs **once per
browser launch**, in the identity's runtime container, inside the namespace ([ARCH] 2.3; [SC-dos] Q6). Its
`cdp_url` is `ws://127.0.0.1:3000/`. (The earlier draft dialled the bridge IP by IP, because Chromium rejects
other Host headers ([EA-dos] section 4); an IP literal on loopback satisfies the same rule.)

- The class is reusable by import. Its **gating contract is not** (wait until ready, re-gate after every
  relaunch, cancel work when it drops): that lives in the box's `tools.py` bound to a module singleton, and is
  rebuilt per identity ([EA-ver] EA-12; [DEC] D16). It also hard-codes port 3000 and `/v1/events`, and reads
  `BB_STEEL_URL` at import.
- `Fetch.enable` with `urlPattern "*"` pauses every request in every tab and worker, so its CPU cost per awake
  identity is **unmeasured** ([EA-ver] EA-12, V-13). Measure it in M1 and add it to the slot size.
- It stays on during a human session.
- Reuse `security.py` verbatim, copied at a pinned box commit with a test that fails if it drifts
  ([DEC] D16).

**The Guard fails open.** When its connection goes, Chrome drops its interception ([BOX-SEC]). "Tools fail
closed" stops *new* calls. It does not stop a hostile page that is already loaded, which can request
`127.0.0.1:3000` or `127.0.0.1:9222` in the gap. Inside the namespace the egress chain does not see loopback
(6.2), so in that gap only Local Network Access stands between a page and Steel's unauthenticated API
(**to measure**, T18). So a lost Guard is an **incident**, handled by the node agent without waiting for
anyone *(S13-7)*:

1. **Detect.** The agent learns of the loss from any of: Docker's `die` event for `fleet-rt-<id8>`, a missed
   Guard heartbeat on `rt.sock` (interval **to set**, a second or two is the target), or the Guard reporting
   that its websocket closed. It does not poll slowly.
2. **Watchdog.** At wake, after P4, the node agent opens its own **bare CDP connection** to the browser
   (at the bridge IP, from the host, so it is not a page-reachable path). It enables no domain and sends
   nothing until the Guard is lost. It lives in the node agent and not in the runtime, so it still works when
   the runtime is the thing that died. Whether even an idle connection is visible to a page is **to measure**
   (T19).
3. **Quarantine.** On a loss the watchdog lists the page targets, navigates each to `about:blank` and closes
   all but the primary tab. It then runs `worker_stop` (10.3). This is a blunt cut and it loses in-page state;
   the cost is accepted.
4. **Record.** An incident `guard_dropped` goes to fleetd with the time, the page URLs that were open (no
   cookies, no page text) and what the agent did. The owner is notified. The next snapshot is tagged `incident`
   and parked (8.2). Restarting the Guard or the session is fleetd's retry, as in [ARCH] 4.10.
5. **A second drop in the same wake** ends the wake through the sleep path.

**A second layer for variant N, to evaluate** *(S13-7; needs Q-08)*. Run Chromium under a different uid from
Steel's API, and have the node agent add one rule in the identity's namespace (by `nsenter --net` from the
host, so no container holds `CAP_NET_ADMIN`): drop connections from Chromium's uid to `127.0.0.1:3000` and
`127.0.0.1:9222` (`-m owner --uid-owner`). Pages run as Chromium's uid, so they cannot reach Steel's API even
while the Guard is down, while the Guard and the actors (other uids, other containers) still can. Costs and
open points, all **to measure**: how to give Chromium its own uid (the wrapper can drop privilege with
`setpriv`, which needs `CAP_SETUID` and `CAP_SETGID` in the Steel container, and that conflicts with
`--cap-drop ALL` and must be written down if added); that the profile volume is owned by Chromium's uid; that
Steel's own connection to Chromium on 9222 still works; and that a **Stagehand extension would be blocked by
the same rule**, because the extension's dial-back comes from Chromium's uid. So the layer fits the `account`
flavor only. It is not decided; T20 measures it.

### 10.2 Order of attachment (every wake)

persist create, then P2/P3/P5, then **start the runtime and attach the Guard**, then P7 under the Guard, then
actors are started. Not at container start: the persist create relaunches Chromium and orphans anything
attached earlier ([EA-ver] M-3, M-7).

### 10.3 Actors, the kill, and the extension policy

**Where things run (topology T-L, chosen)** *(S08-12, S13-6)*. The Guard, the runtime and every actor are inside
the identity's namespace and dial `ws://127.0.0.1:3000/`. They get no Steel REST access they do not need and no
credentials. Hermes profiles never get an endpoint ([DEC] D1, D4). [ARCH] 2.2 draws the executor and the
workers inside one `identity-runtime` container; this file splits them into containers of their own so that
the kill below is one operation.

**The kill (what "kill workers on a higher token" means).** On a takeover, or any token above the one the
actors hold, the node agent does these in order:

1. Persist the new highest token, then write the **fence file** (3.1). From this moment every actor and the
   executor refuse any new command, because they check the file before each one.
2. `docker kill` every actor container of the identity (SIGKILL; the actors hold no profile state, so a kill
   is safe). Confirm by inspect that none is running.
3. Report to fleetd the actors killed and the step each had in flight (`worker_stop`'s return).
4. Only then may `viewer_open(control)` open (9.4).

**A click already handed to CDP cannot be recalled.** Once the bytes of a CDP command are on the socket,
Chromium runs it, and killing the actor does not undo it. The window is bounded: the executor sends one step
at a time and waits for the answer before the next ([ARCH] 2.3), so at most one step is in flight. If it was
an effect step, its intent row is already committed, so fleetd marks it `uncertain` ([DEC] D13) and a
human must not repeat it. The gap between the takeover decision and the confirmed kill is one RPC plus the
kill itself (**to measure**: the time from decision to "no actor running", and what a container kill does to a
click mid-dispatch). If container kill proves too slow, the alternative is a process-group kill through a
supervisor in one runtime container, which keeps the same in-flight rule. M1 picks between them; the contract
(`worker_stop` returns only after no actor is running) does not change.

**Engines.**

- **Stagehand, mode A** (`research` flavor, or an `account` identity M1 assigned to Stagehand): create with
  `extensions:["stagehand"]`. Needs the extension in the image (section 2), `--remote-allow-origins=*` and the
  two `DisableLoadExtension...` feature overrides (both Steel defaults), and a CDP URL the browser can also
  dial. The measured recipe, on headless Steel ([SH-ver] SH-3). Under T-L that URL is `ws://127.0.0.1:3000/`,
  which Chromium bypasses on its own, so the forwarder needs no exception. This is also the condition the
  measured attach had (a loopback URL on the same host).
- **Stagehand, mode B (untested on Steel):** no session extension; the worker sets
  `STAGEHAND_EXTENSION_DIRECTORY_PATH=/app/api/extensions/stagehand`, which is the path the **browser** resolves
  ([AP-dos] section 4), and `Extensions.uninstall` removes the extension after the session. This matches
  the condition in which residency and the mitigation were measured ([AP-ver] AP-2). It works on Chromium 149
  and later with no flag ([AP-ver] AP-1); Steel's image is 152. **Uninstalling a flag-loaded extension
  (mode A) is untested.**
- **Open (T11, `research` flavor and any image that carries the extension):** the extension dials
  `127.0.0.1:3000` from inside Chromium; the Guard refuses loopback. Whether the Guard sees that websocket at
  all is unknown. If it blocks it, allowing that one endpoint loosens a guard and needs Justin's explicit yes
  ([`CHARTER.md`](../../../CHARTER.md)).
- **Browser-Use:** attach by `cdp_url` (loopback), no extension. Its tab-confinement patches are written against
  0.13.10 and refuse any other version ([EA-ver] EA-8); re-pin and re-run its self-check.
- Which engine runs which logged-in site class is an M1 decision ([DEC] D6, [CONS] O-02).

**The extension policy by kind** *(S14-12)*. One rule, applied by the node agent from the persona, never by the
caller and never per wake:

| Kind | Default `extension_mode` | When it may differ |
|---|---|---|
| `research` (open web, no login) | `A` | `B` if M1 prefers it |
| `account` (a logged-in client account) | `none` | `A` or `B` only if M1 selects Stagehand for that site class **and** the owner records it at creation. The identity then runs the `research` image for good. |
| Any kind, `reauth` mode (a human logs in) | `none` | Never |
| Any kind, `canary` mode | `none` | Never |

Why `none` for accounts: the extension is resident from launch, trips a public automation check
([AP-ver] AP-2, n=1 per condition), and whether a platform weighs that signal is unknown. The cost of the
default is that an `account` identity needs another executor until M1 decides (the choice is [DEC] D6 /
O-02's; it is not made here). Until it is decided, `account` identities run `none`.

### 10.4 Topologies: T-L (chosen) and T-O (fallback) *(S13-6)*

| | **T-L** (chosen, matches [ARCH] 2.2) | **T-O** (fallback, not built) |
|---|---|---|
| Where the Guard and actors run | Inside the namespace | On the host side, outside it |
| CDP URL | `ws://127.0.0.1:3000/` | `ws://<bridge IP>:3000/` |
| Chromium's route to it | Loopback bypass, no proxy | Not loopback, so it goes to the proxy setting |
| Forwarder exception | None | `CONNECT` to its own bridge IP:3000, **`research` flavor only** (needed so the extension can dial back) |
| `account` flavor | No extension, so no dial-back and no exception | No extension, no exception: the Guard and the actors dial the bridge IP from outside and never use the proxy |
| Page reach to Steel's API | Loopback: the Guard, Local Network Access and (variant N) the uid rule. Bridge IP: refused by the forwarder. | Bridge IP: **open on `research` identities by design.** Accepted only on browsers with no login. |
| Kill | `docker kill` of actor containers | `docker kill` of host-side workers; same rule |

T-O is taken only if M1 shows T-L unworkable (the Guard against the extension's loopback websocket, or a
same-namespace sidecar misbehaving under `--init` or restart, [ARCH] 2.2's own open items). If T-O is taken, the
open Steel-API path is scoped to the extension's origin if the forwarder can see it, and otherwise accepted
only on `research` identities, which have no login. Under no topology does an `account` identity get the
exception.

---

## 11. Limits and observability

**Caps:** browser 1.5 GiB and 1.2 CPU per container (the box's values; measured peaks 0.98-1.32 GiB on real
browsing, [EA-ver] V-6); slot for planning 1.5 GiB + 0.35 GiB agent runtime and 0.6 vCPU (**estimate**,
7 awake per `s-8vcpu-16gb`, [SC-ver] SCA-5). Social pages, amd64 and soak behaviour are unmeasured
([SC-ver] missed issue 3). The node agent restarts a container through the safe path when memory crosses its
threshold.

**Per identity, recorded by the node agent:** wake time by step; every probe result; hold time and whether
`journal_authoritative`; stale `Singleton*` found (an alarm); zombie count; peak memory; Guard refusals and
its CPU; Guard drops and quarantines; forwarder bytes; exit-IP checks (including `probe_ip` results by class);
persona drift and the node class that served each wake; the tags on every generation (how many parked, how
many `tainted_ip`); the kill time from takeover decision to "no actor running"; viewer routes by mode, their
input-frame counts and any dropped watcher frames; bundle size and restore time; held volumes and their age.
These feed fleetd's dashboards ([SC-dos] Q5). They contain no cookie, key, credential or page text.

---

## 12. Tests it must pass

Everything in this section waits for **Q-12** (a droplet) and an **amd64 re-run (O-17)**, except the rows
marked "local". All tests use public test pages or a fleet-owned origin. No real accounts and no social
sites ([BRIEF](../../research/BRIEF.md)). The suite is also the upgrade gate. The ten gate items in
[`../engines/steel.md`](../engines/steel.md) section 14.1 (now twelve items) map to tests as follows: 1 and 2 to
T7; 3 to T8; 4 to T5 and T8; 5 to T5(a) and T5(b); 6 to T9 (and T4); 7 to T6; 8 to T11 for images that carry
the extension, and T11n for the ones that do not; 9 to T10, T1, T2, T18 and T19; 10 to T14; 11 to T22 and T23;
12 to T21. T20 and T24 join the gate when variant N and `probe_ip` are built.

| # | Test | How | Pass |
|---|---|---|---|
| T1 | **Box shield-check, ported** | Run the 11 attack cases and 7 controls against a wrapped container with the Guard on. The box's script cannot run as-is: it drives jev-automation's Playwright executor, uses the compose name `gateway:8080` and relaunches the browser, and is pinned by `JEV_REF` ([EA-ver] V-1, M-12). The port uses a plain CDP client and the container's IP. | All 11 attacks refused; all 7 controls pass |
| T2 | **Guard probe** | `scripts/guard_probe.py` with `BB_STEEL_CDP=ws://<container ip>:3000/`: the in-flight redirect into Steel's own API, and the cross-site iframe | Exit 0, no leak |
| T3 | **Egress and forwarder destinations** | From inside the namespace try: `169.254.169.254`, the VPC gateway, the bridge/host (ssh), a public address directly, DNS. Through the forwarder try a `CONNECT` and an absolute-URI `GET` to each of: another private address, `127.0.0.1`, link-local, canonicalised loopback forms, and **the container's own bridge IP on port 3000 and on every other port**. Send the forwarder's own listener a plain, non-proxy request. | All time out or refuse, **including the bridge IP on port 3000 (there is no exception)**. The listener answers a non-proxy request with the fixed refusal. The proxy path to a public address works. Steel's boot-time ipinfo call fails fast. |
| T4 | **Exit IP** | Match passes. Swap the upstream to a second IP: the forwarder blocks and the session stops, and its event carries `first_bad_echo_at` and `last_good_echo_at`. Credentials appear nowhere. Record how many requests left through the second IP between the swap and the block. | Fail closed within the check interval; the leak count is recorded, not assumed to be zero |
| T5 | **Persistence cycles**, at least 10 per scenario (**estimate**) | A marker set of an httpOnly cookie, a session cookie, a persistent cookie, localStorage and an IndexedDB record, on a fleet-owned origin. Scenarios: (a) clean cycle, marker written 35 s or more before sleep; (b) marker written 5 s before sleep, recovered from journal #2 and not from disk; (c) container killed with `kill -9`, wake clears the lock and restores the last bundle; (d) restore on a second droplet; (e) a page that rewrites a cookie every 5 s, so the hold reaches its maximum and the sleep is `journal_authoritative`; (f) OOM kill mid-wake; (g) the origin drops the login before sleep, so `auth_result` is `login_wall`: the generation is uploaded and parked, and the pointer stays; (h) the upstream is swapped mid-wake: the generation and the late journals are `tainted_ip`, the next wake restores the last clean one in `canary` mode | Marker present after every wake; 0 `Singleton*` after a clean release; 0 zombies; **a wake never reports `ready` on a blank profile** |
| T6 | **Persona stability**, at least 10 wakes | Pinned fields identical every wake. Host-real fields identical across wakes on one node, **and compared on a second droplet of the same size and base image, and on one of a different size** (the node-class measurement, section 5; both outcomes reopen a decision). UA major equals the engine major. `/proc/<chromium pid>/environ` has `LANG` and `LANGUAGE` (proves 4.3). `navigator.languages`, the `Accept-Language` header seen by a fleet-owned echo page, time zone, a non-empty stable WebGL renderer, headful `screen`. The public bot pages used in the research, compared with the recorded baseline ([S-ver] STE-10). | No change in a pinned field; baseline unchanged. The cross-droplet table is recorded and states which outcome of section 5 holds. |
| T7 | **Takeover guard** | A second create is refused by the node agent. Record what Steel itself does (a 409 if PR #375 merged). Also record which profile path a create with its own `userDataDir` selects (PR #348 may change the fixed-path rule, [EA-ver] EA-1). | Refused by our layer; the fixed path still holds |
| T8 | **Lie tests** (fault injection) | Leave `Singleton*` in the volume; kill Chromium while Node stays up; ask for a stub session id | Probes catch each. No wake is `ready`. |
| T9 | **Secrets scan** | Search `docker inspect`, argv (`docker top`), the Steel container env, every Steel API response, container logs and node-agent logs for the proxy credentials, cookie values and keys | Zero hits |
| T10 | **Viewer** | Enter, Backspace, Tab, arrows, modifiers; non-ASCII and IME; paste through the bridge; popups; native dialogs; HTTP auth; file picker; passkeys; headful versus headless; latency. Route allowlist: every other route is refused. Link: single use, TTL, bound to the lease. A human lease stops the agent's calls. | Every login-blocking input either works or is a recorded gap with a workaround |
| T11 | **Stagehand smoke** (mode A and B). **Runs only against an image that carries the extension** (the `research` flavor, or an `account` identity M1 assigned to Stagehand). | Extension present; attach with the worker on `ws://127.0.0.1:3000/` and a proxy set (Chromium bypasses loopback; the forwarder needs no exception); one `observe`; `act(Action)` replay across an iframe and a shadow DOM (an open D5 gate); `close`; residency after close; `Extensions.uninstall` (mode B); the Guard interaction in 10.3. Only if T-L fails: the T-O fallback and its exception. | Attach works with the Guard on, or the gap is recorded for Justin |
| T11n | **No-extension check** (the `account` flavor) *(S14-12)* | The image has no extension directory; the live argv has no `--load-extension` or `--disable-extensions-except`; the features string lacks the two `DisableLoadExtension...` overrides; the target list shows no extension target; `--remote-allow-origins=*` is absent and puppeteer's origin-less websocket still attaches (**to measure**); the executor M1 selected passes its own acceptance gates | All hold, or the gap is recorded |
| T12 | **Bundle crypto** (**local**, no droplet) | Round trip. Wrong key, wrong identity (associated data), a tampered or truncated file, and a stale fencing token on the pointer all fail. Exclusion list applied. | All negative cases fail closed |
| T13 | **Cross-host restore** | A bundle made on droplet A restores on droplet B (amd64 to amd64) and stays logged in. Size and restore time with a 50 MB profile (**estimate**). | Marker present; restore time recorded |
| T14 | **Soak**, 1-3 h on a heavy public page | Memory climb, restart threshold, zombies, Guard CPU, headful cost | Numbers recorded; threshold set |
| T15 | **Lease and contract** (**local** with a fake Steel) | A stub server that reproduces the lies (made-up `released`, `ok` health, 200 on a blank profile) drives the node-agent contract tests, including highest-token enforcement and per-identity mutex. The lease SQL is tested in Postgres without a network ([CONS] O-03). | All contract rules hold |
| T16 | **Variants R and N** | Sandbox state read from the process; site-isolation flags; Stagehand still attaches; locale still applies | Matches the variant's claim |
| T17 | **Entrypoint and config** (**local**) | Static check of the shell scripts; `persona.env` generator and validator tests (hostile values rejected); egress-rule generator tests (string output) | All pass |
| T18 | **Page-to-Steel reach** *(S13-6)*. Added to the box's shield-check vectors. | From a page in the wrapped browser, with the Guard on and again with it off (to see Local Network Access alone): `fetch` and `new WebSocket` to `127.0.0.1:3000`, `127.0.0.1:9222`, `127.0.0.1:<forwarder port>`, and, through the forwarder, to **the bridge IP on port 3000**. Record whether Chromium's Local Network Access applies to a proxied, non-loopback destination. | Every request refused or failed with the Guard on. With the Guard off, the result is recorded as the real size of the gap (feeds T19 and T20). The bridge-IP vectors are refused by the forwarder. |
| T19 | **Guard drop** *(S13-7)* | Kill the runtime container, then only the Guard process, then close its websocket. While a hostile test page tries `127.0.0.1:3000` in a loop, time from the loss to every page being blank, and count the page's requests that succeeded in the gap. Check the watchdog holds an idle connection that a page's public automation check does not see. | Pages blank within the detection interval (value recorded), an incident `guard_dropped` is raised, actors are killed, the next generation is tagged `incident` |
| T20 | **Variant N second layer** *(S13-7; pending Q-08)* | Chromium under its own uid with the owner-match rule installed by `nsenter` from the host. A page loops to `127.0.0.1:3000` and `:9222` with the Guard off. Steel's own link to Chromium still works. Confirm a Stagehand extension is blocked by the same rule, so this layer is `account`-flavor only. Record the capabilities added back. | The page cannot reach Steel's API with the Guard off, or the layer is dropped and the reason is recorded |
| T21 | **Tags, pointer, deletion and classes** (**local**, fake Steel and fake Spaces) | The sleep result's tags drive the pointer: a clean generation advances it; `login_wall`, `tainted_ip` and `incident` generations are uploaded and parked; retention never removes the newest clean generation or journal; a `tainted_ip` generation is never given to a wake; the journal re-injection rule of 8.1 step 14 (skipped for a tagged or non-`ok` journal and for a last result of `checkpoint`, `captcha` or `restricted`). A failed wake with no session deletes the volume and secrets; one after a session runs the sleep path; a held volume leaves only through `salvage`. The placer refuses a node whose reported class is not the identity's (or an admitted) one, and `no_node_in_class` is the answer when none exists. | All rules hold |
| T22 | **Takeover and the kill** *(S08-12, S12 G12-7)* | A takeover while an actor is mid-step: time from the decision to "no actor running"; the fence file refuses the next command; what a container kill does to a click mid-dispatch (`worker_stop` returns the step in flight). Control route: idle timeout reset by input frames only, hard maximum not moved by `viewer_extend`, a reader is not slept by the agent's inactivity timer, memory threshold raises an event and does not restart. State guard: `viewer_open(control)` is refused in `waking`, `quiescing` and `sleeping`. A dropped websocket reopens inside the reconnect window for the same operator with no token bump and not after it. A second takeover closes the first route. | Every rule holds; the kill time is recorded; no moment with two writers |
| T23 | **Watch route** *(S12 G12-8)* | In `watch` mode a client sends mouse, key, navigation and close frames: none reaches the page and each is counted. `interactive=false` forced by the proxy whatever the client asks. Record, on the pinned image, whether the cast websocket honours `interactive=false` by itself (the source says no). Record what a page-mode connection does to the foreground tab, the CPU cost per watcher, and the effect on a public automation check. The proxy refuses a watch connection to a tab other than the active one. | No input reaches the browser. The side effects are recorded and decide whether watch is on for `account` identities. |
| T24 | **`probe_ip`** *(S07-13)* | On a node with no Steel: the call succeeds for the pinned IP, fails closed for another, and reports each failure class (`mismatch`, `unreachable`, `auth_failed`, `timeout`). The credential appears in no log, argv, `docker inspect` or environment (T9 scope), and its tmpfs file is gone after the call. Refused for an awake identity. If the vendor allow-lists source IPs, record which nodes pass. | All hold; the credential path adds no persistent copy |

Local rows can be built before a droplet exists. They need no Docker lifecycle on the Mac.

---

## 13. Build order (dependencies, not dates)

1. Persona schema, `persona.env` generator and validator (T17). Depends on nothing.
2. Bundle format, exclusions and envelope encryption (T12). Depends on the key-custody decision (O-09).
3. Node-agent contract with a fake Steel, and the lease SQL test (T15). Depends on fleetd's lease spec
   ([DEC] D12).
4. Forwarder. Depends on choosing the proxy vendor and the vetting rule ([DEC] D10).
5. Wrapper image and entrypoint. Depends on the pinned digest, the Q-08 variant, and a droplet (Q-12).
6. Holder, egress chain, runtime and actor containers, the watchdog. Depends on a droplet and on Justin's yes to
   firewall changes.
7. The full test suite T1-T24 on an amd64 droplet (M1). Its result also decides the escape-hatch question in
   [DEC] D4 (wrapped Steel versus plain Chromium plus a small session API), the topology (T-L or T-O), the
   node-class outcome, the container-kill versus process-kill choice, and the default for watch tickets on
   `account` identities.
8. The gate harness, so every later digest runs tests T1-T24, then a canary identity ([DEC] D13, [CONS] O-13).

The tag, pointer, deletion and class rules (T21) and the contract with a fake Steel (T15) come before any
droplet, because they are local.

## 14. Pending

| Item | Owner | Where it bites |
|---|---|---|
| **Q-08** root or non-root, sandbox. Also whether the variant N uid rule (10.1) is built. | Justin | Section 2 variants, 10.1, T20 |
| **Q-12** droplet and spend ceiling | Justin | Every row of section 12 |
| **Q-13** one client per node. Reopened by either outcome of the node-class measurement (section 5). | Justin | Section 8.1 step 2, node packing, section 5 |
| **O-09** bundle key custody | Design | Section 8.5 |
| **O-17** amd64 re-run, cross-host restore | M1 | Sections 4, 8, 12 |
| **O-01** per-identity hardware values | M1 | Section 5 |
| **O-02** which executor per site class on accounts. Until decided, `account` identities run `none` (10.3). | M1 | Sections 2, 5, 10.3 |
| Firewall changes on a droplet | Justin's explicit yes | Section 6.3 |
| Topology T-L works (the Guard against the extension's loopback websocket; same-namespace sidecars under `--init` and restart), or T-O is taken | M1 (T11, T18, T19) | Sections 6.2, 10.4 |
| Container kill is fast enough, or a process-group kill is used | M1 (T22) | Section 10.3 |
| Whether Local Network Access applies to proxied destinations, and how large the Guard-off gap is | M1 (T18) | Section 10.1 |
| Cross-droplet equality of host-real fields | M1 (T6) | Section 5 |
| Watch tickets on `account` identities (side effects of a cast connection) | M1 (T23) | Section 9.5 |
| Whether the vendor allow-lists source IPs (which nodes may run `probe_ip`) | Design, vendor | Section 9.6 |
| Whether a held volume sits on an encrypted local volume | Design | Section 8.6 |
| Every `source (new)` and **to measure** item | M1 | Re-checked first |

---

## 15. Stress-test gaps applied in this revision

Each row is a finding from [SCN] and where this file now answers it. The right-hand column lists what
[ARCH] (or another document) should change to match. This file does not edit those.

| Gap | Where answered here | Other documents should |
|---|---|---|
| S01-6 two specs of the sleep | 8.2 is the one spec: order, numbers (31 s floor, 35 s default, 5 s poll, 90 s maximum, all set in M1), and the flag `journal_authoritative` | [ARCH] 4.9 points here and drops `cookies_unflushed`; [ARCH] 3.3 renames the column; [MS] 4.3 stops quoting both |
| S05-12 auth result on generations | 8.1 step 14, 8.2 tags and pointer, 8.4 | [ARCH] 3.3 adds `auth_result`, `tainted_ip`, `incident` columns to `state_bundles`; `restricted` joins `last_result` |
| S07-12 state from a wrong-IP window | 6.2 rule 5 events, 8.1 modes, 8.2 tags, failure list and canary | [ARCH] 4.9 and 4.10 add `tainted_ip` and the canary wake |
| S07-13 idle IP death | 7 (P6 alone), 9.2 and 9.6 `probe_ip` | [ARCH] 6.8: credentials also reach a node for a probe; [ARCH] 4.11 pre-wake calls `probe_ip` first |
| S07-15 plaintext after a failed wake | 8.1 failure rule, 8.6, `salvage` | [ARCH] 4.9 step 8 says the same |
| S08-8 node class | 5 (node classes), 7 P5, 8.1 step 2 | [ARCH] 3.3 persona gains `node_class`, `persona_baselines` table; [ARCH] W4 places by class; [DEC] D3 and Q-13 are reopened by the M1 result (S09-1) |
| S08-12 where workers live | 1, 3.1, 10.3, 10.4 | [ARCH] 2.2 and N3 to N5 split actors into their own containers, or accept the process-kill alternative; [ARCH] 3.5 states the kill and the in-flight rule |
| S12 G12-7 human session timers | 9.3, 9.4 | [ARCH] 3.5 gives the human lease a liveness rule that reads `viewer_activity` (G12-1) |
| S12 G12-8 watch mode | 9.5 | [ARCH] 6.5 and the console add watch tickets; the Browserbase guide states no watch there |
| S13-6 two topologies | 1, 6.2 rule 9, 10.4 | [ARCH] 2.2 notes that the holder owns the namespace (the earlier text had the runtime join Steel's) |
| S13-7 Guard fails open | 10.1, T18 to T20 | [ARCH] 2.3 and 4.10 add the incident and quarantine |
| S14-12 extension policy by kind | 2 (flavors), 5, 10.3, T11 and T11n | [ARCH] N2, W8 and W10 stop requesting the extension on every wake (S14-4); the persona gains `extension_mode` (S14-7); [DEC] D6 records the per-kind default (S14-8) |
