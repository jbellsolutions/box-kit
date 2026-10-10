# Spike results: hermes-packaging

Date: 2026-10-09 (local evening; logs carry 2026-10-10 UTC timestamps).
Spend: **$0.00**. No model calls, no API keys used, no containers started.
Hermes under test: a checkout at
**09681e7959c0510e404221d7a34610715d25ed00** (2026-10-01, "v0.21.5+4958.g09681e7"). This is
NOT upstream main (46d7718a, 2026-10-09) and NOT an older host pin (8a92051f, 2026-09-19).
Every number below is "hands-on at 09681e7".

Isolation: every command ran against a scratch `HERMES_HOME`, cwd an empty temp dir, `--no-alias` on every profile
create. The scratch root was deleted after the measurements (it had grown to 1.4 GB).

## SAFE RE-VERIFICATION (read before reproducing anything here)

- **Never bootstrap a new HERMES_HOME root on a machine with a real Hermes install.** A scratch `HERMES_HOME` isolates profile
  state. It does NOT isolate the shared code checkout or the first-run update
  path (see S1).
- **Never wrap a first-run Hermes command in a short `timeout`.** Killing it mid-bootstrap can leave an
  "interrupted source update" that the next run resumes against the shared checkout.
- **Reproduce hands-on claims only in a capped `fleet-spike-*` container** with its own Hermes clone at
  09681e7 (or the commit under test). Otherwise verify from the cited source paths.
- Every number here is "at 09681e7", not at upstream main.

## Files in this directory

- `stub_mcp_server.py` loopback-only MCP server (mcp 2.0.0 `MCPServer`, one read-only tool).
  Logs a sha256 prefix of the Authorization header (never the value) and `X-Hermes-Profile`.
- `stub-plugin/browser-fleet/` 3-file native plugin (manifest v2, one tool, one
  `post_tool_call` hook, one bundled skill via `ctx.register_skill`).
- `shared-skills/browser-fleet/fleet-router/SKILL.md` stub shared skill for `skills.external_dirs`.

## Commands and raw results

### S1. Fresh Hermes root bootstrap (side effect, read this)
`hermes profile create p1 --no-alias` in a brand-new HERMES_HOME first ran the whole
first-run/update path: PM environment sync, per-root toolchain download, bundled skill sync,
then "Installing agent-browser". `timeout 180` killed it there. The scratch root then held:

| path | size |
|---|---|
| `.hermes/tools` (python 3.14.7, node 26.7.0, uv, ffmpeg, npm) | 417 MB |
| `.hermes/installs/<env>` | 608 MB |
| `.hermes/cache/uv` | 451 MB |
| total | 1.4 GB |

The retry resumed an interrupted source update and **rebuilt front-end artifacts
inside the shared code checkout**, at the same commit
09681e7. Git HEAD was unchanged and nothing was deleted.

Not established: whether a clean, uninterrupted first run also touches the checkout. This rebuild
followed my killed first attempt.

Lesson for the fleet: **a new HERMES_HOME root is a heavyweight, side-effecting install event, not a
cheap profile.** Use one root plus named profiles, set `security.allow_lazy_installs: false`, and bake
tools into the image.

With `security: {allow_lazy_installs: false}` in the root `config.yaml`, the retry finished in
104 s (mostly the resumed checkout build).

### S2. Named profile creation cost (root already bootstrapped)
```
hermes profile create p2 --no-alias            1.2 s
hermes profile create p3 --no-alias            0.8 s
hermes profile create p4 --no-alias --no-skills
```
| profile | disk | files | bundled skills |
|---|---|---|---|
| p1/p2/p3 (default) | 3,480 KB | 330 | 58 |
| p4 (`--no-skills`) | 184 KB | 27 | 0 (+1 core) |

Projection to 1,000 profiles before any sessions: ~3.4 GB and ~330k files with bundled skills;
~184 MB and ~27k files with `--no-skills`.

### S3. Fixed prompt budget (`hermes -p <p> prompt-size --json`, offline, empty cwd)
| profile | system prompt chars | skills index chars | skills in index | tools | tool-schema JSON |
|---|---|---|---|---|---|
| p1 (58 bundled skills) | 14,485 | 5,641 | 57 | 24 | 43,811 B |
| p4 (`--no-skills`) | 9,175 | 331 | 1 | 24 | 43,811 B |
| p4 + shared external skill | n/a | 429 | 2 | 24 | 43,811 B |

### S4. One read-only shared skills directory serving several profiles
Copied `shared-skills/` to a scratch dir, `chmod -R a-w`, set
`skills.external_dirs: [<dir>]` in p2 and p4 `config.yaml`.
- `hermes -p p2 skills list` and `hermes -p p4 skills list` list `fleet-router` (category
  `browser-fleet`); p1 (not configured) does not.
- `prompt-size` for p4 shows `fleet-router` in the skills index, path under the shared dir.

### S5. Shadowing
Created `p2/skills/browser-fleet/fleet-router/SKILL.md` (same name, different text).
`prompt-size` for p2 now resolves `fleet-router` to the **local** copy. No warning surfaced at
default log level. A drifted local copy silently wins over the fleet release.

### S6. Plugin packaging checks
- `hermes plugins doctor <stub> --ci` -> exit 0: "runtime discovery, manifest parsing,
  import, and registration passed; registrations: 1 tool(s), 1 hook(s)".
- `hermes plugins validate <stub>` -> exit 0, all checks pass (declared tools/hooks match,
  security scan safe).
- `hermes plugins validate` on a copy of `hermes-workforce-router/plugins/workforce_router`
  (@7d9bb0e) -> **exit 1**: "declared tools / declared hooks: undeclared ... (not in
  provides_tools / provides_hooks)". Its manifest uses `tools:`/`hooks:` keys. It still loads
  (the field does not gate loading) but would fail catalog admission.
- Stub plugin copied into `p4/plugins/browser-fleet` and added to `plugins.enabled`:
  `plugins list` shows it enabled, `plugins show` lists toolset `browser_fleet_client` enabled
  for cli. Its bundled skill `browser-fleet:fleet-plugin-demo` is **not** in the skills index
  at 09681e7 (index = `hermes-agent`, `fleet-router`). Upstream added plugin skills to the
  index in 19cb1cbfed (2026-10-07), after this build.

### S7. Per-profile MCP bearer token via `${VAR}` (loopback stub server, port 18931)
Each of p1, p2, p3 got the same `mcp_servers.browser_fleet` entry:
```yaml
url: http://127.0.0.1:18931/mcp
headers: {Authorization: "Bearer ${BROWSER_FLEET_TOKEN}"}
identity_header: {name: X-Hermes-Profile, value_from: profile}
timeout: 900
connect_timeout: 20
```
p1 `.env`: `BROWSER_FLEET_TOKEN=spike-dummy-token-A`; p2: `...-B`; p3: none (dummy strings,
not secrets). `hermes -p <p> mcp test browser_fleet`:
- p1: connected 1,028 ms, 1 tool discovered.
- p2: connected 578 ms, 1 tool discovered.
- p3: `✗ Connection failed (0.0s): MCP server 'browser_fleet': ${BROWSER_FLEET_TOKEN} in
  url/headers is not set in this profile's .env or secret source` (fail closed, no request
  reached the server).

Server log (auth sha8 per request):
```
HEAD /mcp ab25052b None     <- preflight: token present, identity header absent
GET  /mcp ab25052b None
POST /mcp ab25052b p1       (x3), GET p1, DELETE p1
HEAD /mcp 0977a2e3 None
GET  /mcp 0977a2e3 None
POST /mcp 0977a2e3 p2       (x3), GET p2, DELETE p2
```
sha8("Bearer spike-dummy-token-A") = ab25052b, sha8("Bearer spike-dummy-token-B") = 0977a2e3.
So each profile sent only its own token. The `identity_header` is missing on the HEAD/GET
preflight, so the server must authenticate by token, not by the profile-name header.

Stub server process was killed after the test; port 18931 confirmed closed.

## Not tested here (needs a model or a live fleet)
- Real tool calls from an LLM turn, `outcome_uncertain` on session expiry, elicitation.
- 1,000 profiles on one multiplexed gateway (connection count, startup time, RAM).
- Behaviour on upstream main 46d7718a or on the older pin 8a92051f.
