# Operations

Runbook for the live box. See [security.md](security.md) for the threat model and
[architecture.md](architecture.md) for what each component is.

## Sizing, measured

On a 1 vCPU / 2 GB droplet with 2 GB swap: 10 reads at once in 4 s; 4 browser tasks at once in
73 s, agent-browseruse peaking at 444 MiB (about 110 MB a task, so roughly 8–9 at once fit its
1200 MB cap). Idle: gateway 43 MB, agent 35 MB. A droplet built from
[deploy/droplet/cloud-init.yaml](../deploy/droplet/cloud-init.yaml) is ready for `make up`.

## Host requirements

- Ubuntu 24.04
- Docker Engine
- 2 GB swap
- UFW allowing only 22, 80 (the certificate challenge), and 443
- `python3-venv` (for `make venv` and `make smoke`)
- Caddy installed on the **host**, not in compose, so a stack restart never drops TLS
- No browser runs on this host, so there is no Chromium to size it for. The stack's compose caps
  are 256 MB for the gateway and 1200 MB for agent-browseruse (`GATEWAY_MEMORY`,
  `BROWSERUSE_MEMORY`). The live droplet is 1 vCPU / 2 GB with 2 GB swap; measured
  figures are under "The live box". Raise the droplet before raising `BROWSERUSE_MEMORY` past ~1.2 GB.
- Accounts and keys instead of hardware: a Browser Use Cloud account (`BROWSER_USE_API_KEY`) for
  the browsers, and optionally TypeSafe, Browserbase, OpenRouter and Orgo keys for the tools in
  [tools.md](tools.md).

## First deploy

On DigitalOcean: create an Ubuntu 24.04 droplet with a DO-registered SSH key and
[deploy/droplet/cloud-init.yaml](../deploy/droplet/cloud-init.yaml) as user data (it makes the
`deploy` user, swap, Docker, Caddy and the firewall), attach a Reserved IP, then as `deploy`:

```bash
gh repo clone jbellsolutions/browser-box && cd browser-box
cp .env.example .env
make token          # paste the value into BB_TOKEN in .env
chmod 600 .env
make up
make status
make smoke
```

`make smoke` lists the tools, calls `status`, reads a real page with a screenshot through the MCP
endpoint, and asserts obfuscated loopback and a public redirect into loopback are refused. When
`act` is offered it opens a page and checks that a redirect into loopback is refused; when
`task(surface="browser")` is offered it runs a one-page goal. If it passes, the box works. It is
the deploy gate. A smoke run spends a little at Browser Use (a read is about $0.0003) and at the
model for `task`.

## `.env`

Copy from `.env.example`, then `chmod 600 .env`. Never commit values or paste them anywhere
outside the box's own `.env`. Variable **names** (no values):

```
BB_TOKEN
GATEWAY_MEMORY
GATEWAY_CPUS
BB_LANE_WAIT_SECONDS
ORGO_API_KEY
ORGO_COMPUTER_ID
ORGO_MODEL
BB_ORGO_AUTOCREATE
COMPOSE_PROFILES
BROWSER_USE_API_KEY
BB_BROWSERUSE_MONTHLY_USD
BB_BROWSERUSE_MAX_CONCURRENT
BB_BROWSERUSE_SESSION_MINUTES
BB_SOLVE_CAPTCHAS
BB_OWNED_BROWSERS
BB_SESSION_IDLE_SECONDS
BB_SESSION_MAX_MINUTES
TYPESAFE_API_KEY
BB_DECISION_URL
BB_DECISION_MODEL
BROWSERBASE_API_KEY
BROWSERBASE_PROJECT_ID
BB_BROWSERBASE_MONTHLY_HOURS
BB_BROWSERBASE_MAX_CONCURRENT
BB_BROWSERBASE_TIMEOUT
BB_BROWSERUSE_URL
BB_BROWSERUSE_TOKEN
OPENROUTER_API_KEY
BB_BROWSERUSE_MODEL
BB_BROWSERUSE_REASONING_EFFORT
BB_BROWSERUSE_PARALLEL
BROWSERUSE_MEMORY
BROWSERUSE_CPUS
```

Notes worth keeping in mind:
- `BB_TOKEN`: generate with `make token` (wraps `openssl rand -hex 32`); the gateway refuses to
  start without it.
- `BROWSER_USE_API_KEY` turns on the main browser lane: `read`, `session`, `task(surface="browser")`
  and (with `TYPESAFE_API_KEY`) `act`. `BB_BROWSERUSE_MONTHLY_USD` (default 10) caps this box's
  monthly Browser Use spend; `BB_BROWSERUSE_MAX_CONCURRENT` (default 10) caps browsers at once
  below the plan's own limit.
- `BB_SOLVE_CAPTCHAS` (default 1) turns CAPTCHA solving on for both Browser Use and Browserbase
  browsers; set 0 to turn it off. `BB_OWNED_BROWSERS` is the file where the gateway records the id of
  every Browser Use browser it creates: after a crash it stops those, and only those. It never
  searches the account, which also holds other tools' browsers and profiles.
- `BB_BROWSERUSE_PARALLEL` defaults to 0: no cap of ours on tasks at once. The agent container's
  memory (`BROWSERUSE_MEMORY`, default 1200m) is the real bound, at about 100-300 MB per running task.
- `BROWSERBASE_API_KEY` adds the emergency lane (`BROWSERBASE_PROJECT_ID` is optional when the key
  has one project). On Browserbase's $0 Free plan (3 browsers at once, 60 browser-minutes a month, no CAPTCHA solving) set
  `BB_BROWSERBASE_MONTHLY_HOURS=1` to match; the defaults (100 hours, 25 at once) are the $20
  Developer plan's.
- `COMPOSE_PROFILES=browseruse` starts agent-browseruse, which `task(surface="browser")` needs
  (with `BB_BROWSERUSE_URL=http://agent-browseruse:3120`, a `BB_BROWSERUSE_TOKEN` made with
  `openssl rand -hex 24`, and `OPENROUTER_API_KEY`). There is no Steel or Jev container, and no
  `JEV_DIR` or `JEV_REF`.
- `BB_LANE_WAIT_SECONDS` and the `lane` volume now matter only for Orgo computers.
- Leaving a key empty means the tools that need it are simply not offered: no `ORGO_API_KEY`, no
  `computer`; no `TYPESAFE_API_KEY`, no `act`. `status` says what is missing.

## `make` targets

| target | what it does |
|---|---|
| `make up` | build and start the stack |
| `make down` | stop the stack (volumes survive) |
| `make status` | containers, resource use, and the gateway's own `/status` |
| `make smoke` | every offered tool end to end through the MCP endpoint (the deploy gate) |
| `make logs` | tail all logs |
| `make test` | 238 tests, no Docker, no browser, no API key needed |
| `make venv` | local venv for `make test` |
| `make token` | print a fresh `BB_TOKEN` value |
| `make openapi` | regenerate `docs/openapi.json` from the tool cards |
| `make plugin` | validate the plugin/marketplace manifests |
| `make caddy-check` | validate the Caddyfile as it will actually be installed |
| `make cli`, `make cli-test` | install / test the Go command line in `pp-cli/` |

There is no browser to restart: the old `restart-browser`, `logs-steel`, `jev-image`,
`shield-check` and `guard-check` targets went with Steel and the in-browser guard.

## Moving a box off Steel

`compose.yml` no longer defines `steel` or `agent-jev`, and `docker compose up -d --build` only
warns about services removed from the file: it leaves them running as orphans, so Steel's Chromium
would stay up on the box network with `127.0.0.1:3000` still published. When you deploy this
version, run `docker compose up -d --build --remove-orphans` (or `make down` first), then check
that `docker compose ps -a` shows no `steel` or `agent-jev`. Only after that are the old egress
rules dead weight. Set `BROWSER_USE_API_KEY` in `.env` before the restart, or `read` has no
browser.

## Host egress rules

None. The old rules (`iptables` on `DOCKER-USER` and `INPUT` for the Steel subnet) existed to stop
a Chromium on this host from reaching the host's private services. The browsers now run on Browser
Use's and Browserbase's networks, which have no route to this host's loopback or compose network.
A box that ran Steel may still have those rules. Once the Steel container is gone (see above) they
are harmless and no longer needed: they match a subnet that no longer carries a browser (`sudo iptables -L DOCKER-USER -n --line-numbers` shows
them). The
checks that remain, and what they do not cover, are in [security.md](security.md).

## The DigitalOcean root-password-expiry gotcha

DigitalOcean expires root's password on a droplet created without a DO-registered SSH key. An
expired password blocks every non-interactive login, even with a valid key
(`"Password change required but no TTY available"`). Fix: create the droplet with
`chpasswd: {expire: false}` in its cloud-init, and give it a key-only sudo user (the `deploy`
user this box uses).

## Updating code on a box with no GitHub credentials

The droplet has no GitHub auth, so ship code as a git bundle:

```bash
# on your machine
git bundle create /tmp/bb.bundle main
scp /tmp/bb.bundle deploy@<box>:/tmp/bb.bundle

# on the box
cd /opt/browser-box
git pull /tmp/bb.bundle main
docker compose up -d --build --remove-orphans <service>
```

(`--remove-orphans` matters on the first deploy after Steel was removed; see "Moving a box off
Steel" below.)

## Updating the Caddyfile

```bash
sudo sed "s|{\$BB_DOMAIN}|<domain>|" Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null && sudo systemctl reload caddy
```

`BB_DOMAIN=x cp ...` does **not** work: `cp` does no substitution, and Caddy reads
`{$BB_DOMAIN}` from the caddy *service's* environment, not from the shell that copied the file.
An unset value yields an empty site address.

## Rotating `BB_TOKEN`

```bash
make token                  # generate a new value
# edit .env: BB_TOKEN=<new value>
docker compose up -d --build gateway   # or: make up
# update every client's Authorization header (MCP config, bb CLI, curl scripts, Hermes config)
```

## Troubleshooting

| symptom | likely cause | fix |
|---|---|---|
| `status` shows Browser Use down, or `read` answers with `engine: "browserbase"` | Browser Use is out of credit or the wallet is under $0.02, this box's monthly cap (`BB_BROWSERUSE_MONTHLY_USD`) was reached, every browser slot is taken, the API is erroring, or the key is wrong (401) | read `status`'s `detail` for `browser-use cloud`; the full table of emergencies and what each tool does is in [choosing.md](choosing.md#browserbase-the-emergency-lane). Top up, raise the cap, or fix the key |
| a call says a session is busy | another call is using that session's browser for longer than `BB_SESSION_WAIT_SECONDS` | wait, or create another session (each is its own browser) |
| a computer is busy | another call is driving that Orgo desktop past `BB_LANE_WAIT_SECONDS` | wait for the other caller; `task(cancel=true)` stops browser tasks only, not a computer task |
| `status` shows a component down | browser-use cloud, browserbase, the decision model, agent-browseruse or orgo failed a health check | read `status`'s `detail` for that component — it names the reason, not just "down" |
| browsers still running at Browser Use after a crash | the gateway died between opening and stopping one | they are stopped when the gateway next starts; check Browser Use's dashboard for any that remain, since a lost one bills until its timeout (`BB_BROWSERUSE_SESSION_MINUTES`, default 5) |
| 401 on any call | missing or wrong bearer token | check the `Authorization: Bearer <BB_TOKEN>` header against the current `.env` value |
| 404 tool not offered | the tool's integration isn't configured on this box (e.g. `act` without `TYPESAFE_API_KEY`, `computer` without Orgo) | `GET /api/v1/tools` or `status` shows what's configured; set the missing env vars and `make up` |
