# Security

The box sits next to other services, so a page must never be able to reach them. This was real: on
2026-09-22, when the browser ran on this host, a public URL that 302-redirected to
`http://127.0.0.1:3000/v1/sessions` made the browser read its own session list and hand it back as
page content. The redirect exploit is in the test suite still.

## What changed: the browsers are not on this host

`read`, `session`, `act` and `task` run on hosted browsers: Browser Use's, and Browserbase's in an
emergency ([choosing.md](choosing.md#browserbase-the-emergency-lane)). Those browsers run on the
providers' networks. A page loaded in one cannot reach this host's loopback, its compose network or
its cloud metadata address. From there it reaches this host only the way any internet client does,
through its public ports, where the MCP endpoint is bearer-gated.

So two controls from the Steel days are gone, on purpose:

- **The host egress `iptables` rules.** They stopped a Chromium on this host from reaching the
  host's private services. There is no such Chromium.
- **The in-browser request guard** (`guard.py`, a CDP client that paused and checked every request
  Chromium made). It guarded the same route. `make shield-check` and `make guard-check` went with
  it.

Nothing replaces them, because the route they closed no longer exists. SSRF against this host is
closed by where the browsers live, not by a rule we maintain. What remains is the gateway's own
checks, below, and `act`'s check after each step.

## URL checks (`gateway/gateway/security.py`, `safe_target`)

Every URL is validated and classified before any browser opens or connection is made — only
`target_scope() == "public_web"` passes, and then every address the host name resolves to must be
public too (`safe_target` in `tools.py`):

- **Obfuscated loopback is handled.** Browsers accept `0x7f000001`, `2130706433`, `0177.0.0.1`
  and `127.1` as loopback; Python's `ipaddress.ip_address` rejects all four as unparseable, so a
  naive check falls through to "public" and happily fetches localhost.
  `security._canonical_ipv4` normalizes octal/hex/decimal/short-dotted IPv4 before judging it.
- **Every hostname is resolved and every address it answers with is checked**
  (`require_public_addresses`). A public name that A-records to `10.0.0.5` is refused — one
  public record does not launder a second one pointing at the metadata service.
- **`fetch` walks redirects by hand, one hop at a time, and clears each hop before connecting**
  (`tools.follow_public_chain`, at most `BB_MAX_REDIRECTS` hops, default 8). `fetch` is the one tool
  that makes an HTTP request from this host, so it is the one where a redirect into an internal
  address would be a real exposure. Inspecting `response.history` afterwards is too late — the
  request to the internal address has already happened.
- **A page that lands off the public web is dropped.** `read` checks where the page ended
  (`final_url`) and refuses it if it is not public, on either provider. `act` checks the page after
  each step; if a click or a typed address led somewhere non-public, the tab is sent to
  `about:blank` and the step is reported as refused.
- Cloud metadata (`169.254.169.254`) is link-local and blocked.
- Carrier-grade NAT (`100.64.0.0/10` — Tailscale's tailnet address space) is treated as private,
  since Python's `ipaddress` calls it neither private nor global and it would otherwise slip
  through as "public".
- Bare hostnames with no dot, and hostnames ending `.local`/`.internal`/`.lan`/`.home`/`.corp`,
  are classified `private_network` rather than resolved as public.

For the hosted browsers these checks are the box's policy, not the last line of defence: they stop
the box being used to open internal-looking targets, and a rebound or redirected request that
slips past them goes to the provider's network.

## What this does NOT cover

1. **DNS rebinding.** A name that resolves public at check time can resolve private a second
   later. For `fetch` this is real: the gateway resolves the name to check it and the HTTP client
   resolves it again to connect, so a rebound answer is fetched from this host. For the hosted
   browsers a rebound answer points into the provider's network, not this host.
2. **Requests a page makes after it loads.** The gateway checks the URL it hands a browser and,
   in `read` and `act`, where the page landed. Subresource requests, popups and iframes happen on
   the provider's machines and are not seen here.
3. **The box keeps no logins, and never touches a Browser Use profile.** `cloud.py` refuses any API
   path containing "profile" before making the request, and no browser is created with a
   `profileId`, because the Browser Use account also holds other tools' logged-in profiles
   (for example a lead-gen tool). A `session` is a fresh, logged-out browser that is gone once released or closed
   when idle. `live_url` lets whoever holds it drive that session's browser, so it is returned only
   to the caller that created the session and is never logged. Crash cleanup stops only browsers
   this box created, by the ids recorded in `BB_OWNED_BROWSERS`; it never searches the account.
4. **Browser-Use reads untrusted pages and acts on them.** A page can instruct it, and it may
   follow the instructions: go elsewhere on the public web, type what the page asks, click what
   the page wants clicked. The hosted browser keeps it off this host. `upload_file` is excluded,
   so it cannot post this container's files. Its process holds one secret, the OpenRouter key, and
   no tool of its reads the environment. A task takes no `session_id` and runs in a fresh, logged-out
   browser of its own, so a page that steers it has no login to act as.
5. **Bot walls are not reliably bypassed.** CAPTCHA solving is on by default (`BB_SOLVE_CAPTCHAS=1`)
   on both providers, but Browser Use's residential proxy is off (it is billed per GB), so a
   challenge the provider cannot solve still comes back as a failed or blocked read.

## Secrets handling

- `.env` is gitignored and must stay `chmod 600`.
- Tokens are never in the repo — `.env.example` lists variable names only, no values.
- `BB_TOKEN` and `BB_BROWSERUSE_TOKEN` are generated with `openssl rand -hex …` (`make token` for
  `BB_TOKEN`).
- Provider keys (`BROWSER_USE_API_KEY`, `BROWSERBASE_API_KEY`, `TYPESAFE_API_KEY`,
  `OPENROUTER_API_KEY`, `ORGO_API_KEY`) are never returned, logged or put in an error. Browser Use's
  CDP URLs, which are credentials for a live browser, are not either.
- The gateway refuses to start without `BB_TOKEN` — an open browser endpoint is not a degraded
  mode, it is a breach.
- `/health` is unauthenticated liveness only and never reports what is configured or up.
- Nothing is published beyond `127.0.0.1`; Caddy terminates TLS and is the only public surface.
- agent-browseruse listens on the compose network, not loopback, so it refuses to start without
  its token.

## Spend is a safety guard too

Hosted browsers bill by the minute, so a runaway loop spends money. Each is stopped explicitly when
its call ends (closing the websocket does not stop it), started with a short timeout
(`BB_BROWSERUSE_SESSION_MINUTES`, default 5), and tagged so browsers a crashed gateway left running
are stopped when it restarts. `BB_BROWSERUSE_MONTHLY_USD` and `BB_BROWSERBASE_MONTHLY_HOURS` refuse
new browsers at the cap. These are budget guards, not limits of the tools.

## Browser-Use confinement

`agents/browseruse/runner.py` confines each task to the one tab opened for it: every
pre-existing tab is filtered out of every listing it can see, it cannot open a CDP session on a
tab that isn't its own, it cannot close a foreign tab, its downloads watchdog is disabled, and it
is granted no browser permissions (`permissions=[]`, no clipboard/notifications grants). Each task
now has a hosted browser to itself, so this confinement is belt and braces rather than the only
thing keeping tasks apart. These patches are written against Browser-Use 0.13.10 specifically;
`confine()` self-checks the installed version and refuses to run if it or a patched method has
drifted. See [architecture.md](architecture.md) for where this sits in the call flow.

## Jev's risky-action confirmations

Jev never generates text and cannot plan — it only picks which element a step means. Two safety
behaviors sit on top of that: a low-confidence pick comes back as `needs_clarification` with
options rather than a guess (`act(pick=…)` to answer), and anything that looks hard to undo —
buy, delete, send, post — comes back as `needs_confirmation` and does not run until the caller
answers `act(confirm=true|false)`. Risk is judged twice: once from the caller's words and once from
the element Jev picked, so "click the button" on a form whose one button is "Submit order" is
stopped.

## Orgo `bash` runs in your own Orgo account

`computer(action="bash", command=...)` is a real shell on an Orgo cloud desktop, inside the
account whose `ORGO_API_KEY` this box holds. There is no sandboxing beyond what Orgo itself
provides. A computer bills until stopped — there is no auto-stop — so call `action="stop"` when
finished, and creating one requires `BB_ORGO_AUTOCREATE=1` explicitly.

## Checks to run

- `make test` — the SSRF vectors (`tests/scope_vectors.json`), the redirect-into-loopback exploit,
  the emergency fallbacks and the refusals, with no Docker, browser or key.
- `make smoke` — against a running box: a read with a screenshot, obfuscated loopback refused, a
  public redirect into loopback refused, and, when offered, the same redirect through `act`.
