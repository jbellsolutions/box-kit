> **Read with its verification report.** [verification/hermes-packaging.md](../verification/hermes-packaging.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: packaging the browser fleet for 1 to 1,000 Hermes profiles

Agent: hermes-packaging research agent. Date: 2026-10-09. Spend: $0.00. No containers started.

**Revisions referenced.** Hermes moves very fast: about 12,600 upstream commits landed between the
Jev trial pin and today. Every Hermes claim below is tagged with the revision it was read at.

| Label | Commit | Date | What it is |
|---|---|---|---|
| `main` | NousResearch/hermes-agent `46d7718a52ff` | 2026-10-09 | upstream main today (read via `git show`, read-only, from a local checkout) |
| `local` | `09681e7959c0` | 2026-10-01 | A local Hermes install; all hands-on spikes ran on this |
| `trial` | `8a92051f20e6` | 2026-09-19 | Hermes pin used by a plugin-less host (details withheld) |
| `fork` | jbellsolutions/hermes-agent `main` | last push 2026-05-06 | 0 commits ahead of upstream and 43,660 behind. It has no packaging-relevant changes, so build against upstream. |

Provenance tags: `[hands-on]` means I ran it today (see `fleet/research/spikes/hermes-packaging/RESULTS.md`).
`[source-code]` means read at the stated commit. `[official-docs]` means upstream `website/docs/...` at `main`, also
live at hermes-agent.nousresearch.com/docs (HTTP 200 checked 2026-10-09). `[vendor-claim]`, `[third-party]`
and `[unverified]` are used as in the brief.

---

## 1. Verdict

1. **The primary integration surface is a remote MCP server, one per fleet, with a bearer token per profile.**
   Each profile's `config.yaml` carries the same entry: `mcp_servers.browser_fleet` with header
   `Authorization: "Bearer ${BROWSER_FLEET_TOKEN}"`. The token lives in that profile's `.env`.
   - Hermes resolves `${VAR}` from the routed profile's own secret scope.
   - It fails closed when the variable is unset, and keeps a separate MCP connection per distinct
     credential, including under the default multiplexed gateway.
   - I verified this hands-on: profile p1 sent token A, p2 sent token B, and p3 (no token) was refused
     before any request left the machine `[hands-on S7]`.
   - This is also the **only** route into the Jev Workforce trial that needs no code change (see 2.2).
2. **Skills ship as one read-only shared directory per host, attached with `skills.external_dirs`. They do
   not ship as copies or as plugin-bundled skills.**
   - External skills enter the system-prompt skill index on all three revisions. Verified hands-on for two
     profiles from one `chmod a-w` directory `[hands-on S4]`.
   - Plugin-registered skills reach that index only from commit `19cb1cbfed` (2026-10-07) onward. At
     `local` and `trial` they are invisible unless something tells the model they exist `[source-code]`
     `[hands-on S6]`.
3. **A Hermes plugin is optional.** Keep it thin, with no Python dependencies. Its main job is to write
   evidence into Obsidian from a `post_tool_call` hook, plus a `/fleet` status command.
   - It must be installed and enabled per profile: the `plugins/` dir is per `HERMES_HOME`.
   - Pip entry points are not a supported path for managed installs `[official-docs]`.
   - The plugin will **not** load in the Jev trial, which builds `AIAgent` with a fixed toolset list and
     monkeypatches `registry.dispatch` `[source-code trial repo]`.
4. **Profile-to-identity binding belongs in the fleet service, not in Hermes.** The profile holds only an
   opaque token. The fleet maps it to `(installation, profile)`, then to the set of bound identities and
   their scopes (read / draft / publish / dm).
   - Infra (Steel or Browserbase), proxy and fingerprint are fixed when the identity is created.
   - The identity-header label (`identity_header value_from: profile`) is not authentication. It is
     missing on the HEAD/GET preflight `[hands-on S7]`.
5. **Server-side enforcement is mandatory.**
   - The trial's authority layer allows *every* tool of an MCP toolset once the owner adds the connection.
     Its publish/send guard only inspects its own `browser_click/type/navigate` `[source-code authority.py]`.
   - `trust: untrusted` on the Hermes side would make every write prompt a human and fail closed in cron
     `[official-docs]`.
   - So the fleet itself must gate draft vs publish, rate limits, spend and the reserved actions, per token.
6. **Long browser jobs must be submit-then-poll, and every write must be idempotent.**
   - The MCP tool timeout defaults to 300 s.
   - When a Streamable-HTTP session expires, Hermes replays only tools annotated `readOnlyHint: true`.
     Write tools return `outcome_uncertain` instead `[official-docs mcp-config-reference]`.
7. **One Hermes root with many named profiles, never one root per profile.**
   - A fresh root bootstrapped about 1.4 GB of toolchain, environment and cache at `local` `[hands-on S1]`.
   - A first run killed mid-bootstrap leaves an "interrupted source update" that the next run resumes,
     rebuilding artifacts inside the shared code checkout.
   - Not established: whether a clean, uninterrupted first run also touches the checkout.
   - After that, a named profile costs about 1 s to create and 3.4 MB with bundled skills, or 184 KB with
     `--no-skills` `[hands-on S2]`.
   - Recommended for fleet profiles: `--no-skills` plus the shared fleet skills. That gives a system prompt
     of about 9.2k characters instead of 14.5k `[hands-on S3]`.
8. **Use only documented Hermes surfaces (MCP, skills, plugin `ctx`), and pin the Hermes commit per host.**
   - Hermes Skill Sync was removed upstream on 2026-10-03 `[source-code 64ad33e32d]`.
   - Profile distributions have no ref pinning `[official-docs]` `[source-code profile_distribution.py]`.
   - Version fleet skills yourself: release directories, a `current` symlink and a server-enforced
     minimum skill version.
9. **Memory means Obsidian, written on the Hermes side.**
   - The fleet is remote and cannot see the vault. Each profile writes run and daily notes into its own
     vault folder: the plugin hook does this where plugins load, and skill or Training instructions do it
     in the trial.
   - Built-in `MEMORY.md` holds only 2,200 characters, so it keeps pointers, not evidence `[official-docs memory]`.
   - There is no Obsidian memory provider upstream (bundled at `main`: byterover, holographic, retaindb),
     so a mem0-style layer over the vault is a later build.

---

## 2. Answers

### 2.1 Hermes: what a profile is and how one install serves many

**What a profile is.**
- A profile is a separate Hermes home directory (`HERMES_HOME`), holding `config.yaml`, `.env`, `SOUL.md`,
  `memories/`, `sessions/`, `skills/`, `cron/`, `plugins/`, `state.db` and logs.
- The wrapper sets `HERMES_HOME=~/.hermes/profiles/<name>`, and "119+ files" resolve paths through
  `get_hermes_home()` `[official-docs user-guide/profiles.md]`.
- A directory counts as a profile only if it holds one of `config.yaml`, `.env`, `SOUL.md`, `profile.yaml`,
  `auth.json` or `state.db`.
- Hard rule from the docs: "Never point two agent processes at the same profile"; each process loads the
  other's memory writes `[official-docs profiles.md]`.
- Profiles are **not** sandboxes. On the local terminal backend the agent keeps full access to the user's
  files. `HOME` stays the real user home unless `terminal.home_mode: profile` is set
  `[official-docs profiles.md]`.

**Config, SOUL and memory.**
- `config.yaml` holds model, toolsets and everything else. `SOUL.md` is the persona or system prompt, and
  changes apply to new sessions only.
- Built-in memory is `memories/MEMORY.md` (2,200 characters, about 800 tokens) plus `USER.md` (1,375
  characters) `[official-docs features/memory.md]`.
- External memory providers are exclusive plugins, one active per profile (`memory.provider`). Honcho,
  mem0, Hindsight and others come from the catalog. There is **no Obsidian provider**: only a bundled
  `note-taking/obsidian` skill that uses `OBSIDIAN_VAULT_PATH` `[source-code main plugins/memory]`
  `[official-docs skills/bundled/note-taking-obsidian]`.

**Skills: format.**
- A skill is `SKILL.md` with YAML frontmatter: `name`, `description`, optional `version`, `platforms`, and
  `metadata.hermes.{tags,category,requires_toolsets,fallback_for_toolsets,requires_tools,config}`.
- Optional subdirectories: `references/`, `templates/`, `scripts/`, `assets/`.
- Discovery is progressive: an index line (name: description) sits in the system prompt, and
  `skill_view(name)` loads the body `[official-docs features/skills.md]`.

**Skills: limits** `[source-code main tools/skill_manager_tool.py]`.
- Name: at most 64 characters, matching `^[a-z0-9][a-z0-9._-]*$`.
- Description: at most 1,024 characters.
- Body: at most 100,000 characters when written through `skill_manage`.
- Supporting file: at most 1 MiB.
- Up to 5 skills can be stacked in one command.
- Skill text containing "ignore previous instructions", "you are now", "system prompt:", `<system>`, etc.
  is logged as a possible injection: a warning, not a block `[source-code tools/skills_tool.py]`.

**Skills: where they come from.** In precedence order: project, then local `<HERMES_HOME>/skills`, then
`skills.create_dir`, then `skills.external_dirs`.
- A same-named local skill **silently shadows** the shared one `[hands-on S5]`.
- External dirs are "not a write-protection boundary". The system prompt even tells the model to fix skills
  with `skill_manage(action='patch')`, so filesystem read-only is required `[official-docs]`
  `[source-code main agent/prompt_builder.py]`.

**Plugins.**
- A native plugin is a directory with `plugin.yaml` plus an `__init__.py` exposing `register(ctx)`.
  `ctx.register_tool`, `register_hook` (27 hooks, including `pre_llm_call`, `pre_tool_call`,
  `post_tool_call` and `on_session_start/end`), `register_skill`, `register_command`,
  `register_cli_command`, `ctx.llm`, `ctx.call_mcp` (default off, per-server allowlist) and
  `ctx.profile_name` are the documented surface `[official-docs developer-guide/plugins/index.md]`
  `[source-code main hermes_cli/plugins.py]`.
- Manifest v2: `provides_tools` and `provides_hooks` must match what is registered, or
  `hermes plugins validate` fails; `config_schema` and `requires_env` are supported `[official-docs]`.
- Installation:
  - Plugins live in `<HERMES_HOME>/plugins/` and are opt-in: they must be listed in `plugins.enabled`.
  - `hermes plugins install owner/repo --ref <40-char SHA>` pins exactly.
  - Packs (`hermes-pack.yaml`) pin sets of plugins, but cannot be installed non-interactively
    `[official-docs features/plugins.md]`.
- Python dependencies are resolved into **one shared environment** that is the union across every
  profile's `plugins.enabled`. A single unparsable profile `config.yaml` fails dependency preparation for
  *all* profiles `[official-docs features/plugins.md]`.
- Pip entry points are "discovery, not permission to inject packages into a PM-selected generation"
  `[official-docs plugins/index.md]`.
- `plugins.isolation: host` runs user plugins in a per-profile host process `[official-docs]`.
- Portable "Agent Plugins v1" packages (`plugin.json` + `skills/` + `mcp.json`) are also accepted, but
  install disabled `[official-docs]`.

**MCP per profile.**
- MCP servers are configured under `mcp_servers.<name>` in the profile's `config.yaml`.
- HTTP keys: `url`, `headers`, `timeout` (default 300 s), `connect_timeout`, `lazy`, `trust`, `tools.include/exclude`,
  `identity_header`, `auth: oauth` and mTLS `[official-docs reference/mcp-config-reference.md]`.
- Tools are registered as `mcp__<server>__<tool>`, clamped to 64 characters with a hash suffix. This holds
  at `trial`, `local` and `main` `[source-code tools/mcp_tool_schema.py]`. The user-guide MCP page still
  shows a single-underscore form, which is stale.
- Each server also becomes toolset `mcp-<server>`. A server named after a built-in toolset (for example
  `browser`) merges with it, so call ours `browser_fleet` `[official-docs toolsets-reference]`.
- Under the multiplexed gateway:
  - Identical entries share one connection; distinct credentials get their own.
  - OAuth connections are never shared.
  - Startup connects profiles one after another, with `mcp.discovery_concurrency` (default 4) per profile
    `[official-docs multi-profile-gateways.md]`.
- MCP `ImageContent` is re-sent on every later turn (up to 4 images, downscaled). Return links, not
  inline screenshots `[official-docs features/mcp.md]`.
- Form-mode elicitation works through the approval surface. **URL-mode elicitation is declined**, so a
  "go log in here" handoff must be a link in the tool result `[official-docs features/mcp.md]`.
- I found no code path that injects an MCP server's `instructions` into the prompt; this is a negative grep
  at `main`, medium confidence `[source-code]`. Put guidance in tool descriptions, MCP prompts or skills.

**Toolsets.** Toolsets are configured per platform (`hermes tools`, `platform_toolsets`) and disabled with
`agent.disabled_toolsets`. The built-in `browser` toolset includes `browser_vault_*` credential autofill
tools `[official-docs toolsets-reference]`. Disable it on fleet profiles, so agents never touch an account
from an unmanaged local browser and never type credentials.

**Secrets and env.**
- Each profile has its own `.env`. Under multiplexing, the secrets are installed in a context-local scope
  (`agent.secret_scope.get_secret`) and never merged into `os.environ` `[source-code main agent/secret_scope.py]`.
- Cron scripts "do not inherit provider credentials" `[official-docs guides/cron-script-only.md]`.
- Managed scope (`/etc/hermes/config.yaml`, `.env`, root-owned) pins keys for every profile on a machine
  `[official-docs managed-scope.md]`. Two limits, from `[source-code main hermes_cli/managed_scope.py, config.py]`:
  - Lists are replaced wholesale, so pinning `plugins.enabled` would wipe each profile's own list.
  - Its `${VAR}` references expand against the **process** env only, so never put per-profile tokens there.

**How one install serves many profiles.**
- One code checkout and one Python environment serve every named profile under `<root>/profiles/`.
  `hermes update` pulls once and syncs bundled skills into every profile `[official-docs profiles.md]`.
- One multiplexing gateway process serves every profile by default (`gateway.multiplex_profiles` resolves
  to `true`) and hot-adds new profiles within 30 s `[official-docs multi-profile-gateways.md]`.
- Profile distributions (`hermes profile install <git>` / `update`) package SOUL, config, skills, cron and
  MCP config. Caveats `[official-docs profile-distributions.md]`:
  - They track the default branch with no ref pin, and are unsigned.
  - Updates overwrite `SOUL.md`, `mcp.json` and skills unless `distribution_owned` narrows them.
  - They are better for **creating** role-template profiles than for updating 1,000 live ones.
- I found no documented or tested scale limit for 1,000 profiles on one host `[unverified]`.

### 2.2 A plugin-less host (the Jev Workforce)

The Jev Workforce host runs each employee as an isolated container with a fixed Hermes toolset, so
plugins never load there. The fleet can reach it only as an MCP server (HTTPS, short timeout, literal
token) plus owner-approved prose guides. The host may allow every tool on a connected server, so the
fleet enforces scope itself. Consequences for the fleet: design to a 90 s tool timeout,
submit-then-poll, prose guides without executable authority, one login per account. Internals of the
host are withheld from this public copy.

### 2.3 The existing plugin format and fleet orchestration

**hermes-workforce-router** @ `7d9bb0e` (2026-07-20).
- The format is a plugin plus one skill:
  - The plugin (`plugins/workforce_router/`) registers 7 `workforce_*` tools through `ctx.register_tool`
    and a `pre_llm_call` hook. The hook injects a compact "WORKFORCE ROUTE CHECK" block built locally, with
    no LLM, no network and no file writes, and fails open.
  - The skill sits in a category directory: `skills/autonomous-ai-agents/workforce-router/SKILL.md`.
- `install.py` copies both into `~/.hermes` (default root only), backs up and rolls back atomically, and
  runs `hermes plugins enable workforce-router --no-allow-tool-override` `[source-code]`.
- Gotchas:
  - Its manifest uses `tools:` and `hooks:` instead of `provides_tools` and `provides_hooks`. It loads, but
    `hermes plugins validate` fails "declared tools/hooks" `[hands-on S6]`.
  - The installer does not target named profiles.
  - GOAL.md: "No custom MCP server in v1. Super Browser remains its existing MCP server and is routed to."
    That is the same plugin + skill + existing MCP split recommended here.

**A prior internal fan-out project** (details withheld).
- An A2A server, a NATS publisher and subscriber, and a Temporal fan-out workflow exist
  `[source-code, private repo]`.
- The fan-out is **LLM sub-prompt fan-out** with the coordinator holding tasks in memory and a cap on
  subtasks; Temporal is optional.
- It is a reusable pattern (durable workflow per job, NATS events), not a browser-job scheduler. Scheduling
  persistent per-identity browser jobs would be new activity code.
- Its vault contract wants Obsidian as the source of truth `[source-code]`.
- Upstream Hermes now has its own durable SQLite Kanban across profiles, built for "Fleet work: one
  specialist managing N subjects (50 social accounts...)", plus per-profile cron and no-LLM script cron.
  It is single-host by design `[official-docs features/kanban.md, guides/cron-script-only.md]`.

### 2.4 Recommended packaging

**The four pieces, in priority order.**

1. **The fleet MCP server** (part of the shared fleet service, HTTPS, Streamable HTTP).
   - It is the only thing every profile needs, and it works unchanged in the trial.
   - Tool surface, kept small in browser-box style ("if a tool is listed, it works"):
     `status`, `run`, `job`, `cancel`, `read`, `login_link`, `procedures`, `feedback`.
   - MCP prompts carry versioned playbooks for clients that cannot take skills.
   - Annotate `readOnlyHint` truthfully: `status`, `job`, `read` and `procedures` are read-only, so they
     are retried after session expiry.
2. **The shared skills release**: `/opt/jev-fleet/skills/releases/<semver>/browser-fleet/fleet-*/SKILL.md`,
   with `current` and `canary` symlinks, made read-only. Each profile sets
   `skills.external_dirs: [/opt/jev-fleet/skills/current]`.
3. **Optional plugin `browser-fleet`**: no dependencies, pinned by `--ref <sha>`, one copy per profile, a
   few kB each. It provides:
   - (a) a `post_tool_call` hook that writes Obsidian evidence for `mcp__browser_fleet__*` results;
   - (b) a `/fleet` slash command;
   - (c) an optional `pre_llm_call` one-liner, local and cached and fail-open like the router, naming any
     identity that needs a human;
   - (d) an *experimental* `BrowserProvider` that leases the bound identity's CDP URL for Hermes' native
     `browser_*` tools.
   For (d), read the secret with `get_secret`, never `os.environ`; `steel-dev/hermes-steel` reads
   `os.environ` and creates ephemeral sessions, so it is unsafe here `[source-code hermes-steel@d8a1e39]`.
   Keep (d) disabled by default. It hands clicks to the Hermes LLM and bypasses Stagehand and System 1.
4. **The provisioner** (fleet admin CLI, not agent-facing). For each profile it:
   - mints a token and writes `BROWSER_FLEET_TOKEN` and `OBSIDIAN_VAULT_PATH` into `.env`;
   - merges the config block below into `config.yaml` and **validates the YAML** (one bad file breaks
     dependency prep fleet-wide);
   - runs `hermes -p <p> mcp test browser_fleet`;
   - records the binding in the fleet DB.
   For trial employees, it calls the host's integrations route instead.

Per-profile Hermes config, the native-profile path (the trial writes its own equivalent):
```yaml
mcp_servers:
  browser_fleet:
    url: https://fleet.<domain>/mcp
    headers: {Authorization: "Bearer ${BROWSER_FLEET_TOKEN}"}
    identity_header: {name: X-Hermes-Profile, value_from: profile}   # label only, not auth
    timeout: 120          # every call returns fast; long work is run -> job polling
    connect_timeout: 20
    lazy: true            # 1,000 profiles: connect on first use, not at gateway start
    trust: full           # untrusted would block cron writes; the fleet enforces scopes
skills:
  external_dirs: [/opt/jev-fleet/skills/current]
agent:
  disabled_toolsets: [browser]   # no second, unmanaged browser identity; no browser_vault_* typing
security:
  allow_lazy_installs: false
```
Note: the experimental `BrowserProvider` (plugin item d) works only if the `browser` toolset is enabled
again. That brings back `browser_vault_*` credential typing. Enable it only on a profile that is
deliberately exempt, with no saved vault credentials.

**Binding a profile to its browser identities.** All of this lives in fleet tables:
- `identities`:
  - account and platform, with a unique constraint on `(platform, handle)` so one account can never be
    bound twice;
  - infra (`steel-selfhost` or `browserbase`) and node;
  - profile-state location, fingerprint seed and sticky proxy;
  - health: `ok`, `needs_login`, `challenge`, `cooldown` or `locked`.
- `bindings`: `token_hash`, then `(installation_id, hermes_profile)`, then
  `[{identity_id, alias, scopes, daily_caps}]`.
- Agents refer to identities by alias (`acme-instagram`) and can only name identities bound to their token.
- Infra, proxy and fingerprint are chosen at identity creation and never by the agent.
- Rotating a token is a provisioner action: rewrite `.env`, and the next connect uses it.

**Versioning across 1,000 profiles.**
- **Skills.** Flip the `current` symlink atomically. New sessions see the new release; running sessions keep
  their snapshot.
  - Canary by pointing some profiles at `canary`.
  - Every skill has `version:`. Tools accept `skill_version`, and `status` returns `min_skill_version`. The
    server warns or refuses stale callers, which also gives a fleet-wide census of who runs what.
  - Name every fleet skill `fleet-*`. A nightly drift scan flags any profile with a local `skills/**/fleet-*`
    (a shadow, per S5) or a non-read-only release directory.
  - Agent "learning" goes to `feedback`, and a human releases it, like the trial's quarantine.
- **Tool descriptions** are versioned server-side and change fleet-wide at once (Hermes re-fetches on
  `tools/list_changed`).
- **Hermes core.** Pin one commit per host. Upgrade only after the checks in RESULTS.md pass on the new
  commit: plugin doctor and validate, `prompt-size`, `mcp test`, and the external-dirs listing.
- **Not for this:** Skill Sync (removed), profile distributions (no ref pin, overwrites SOUL), and pip
  entry points (not for managed installs).

**Per-profile memory and evidence into Obsidian.**
- Vault layout: one org vault, or one per client, with `Agents/<profile>/` holding:
  - `Daily/YYYY-MM-DD.md`, one line per fleet job with `[[Runs/<job_id>]]`, `[[Identities/<alias>]]`,
    engine and cost;
  - `Runs/<job_id>.md`: intent, inputs digest, outcome, evidence links (screenshots and traces stay in fleet
    object storage, linked, not copied), receipts, and `needs_human`;
  - `Identities/<alias>.md`: health history and login events, never credentials.
- The writer is the plugin hook where plugins load. In the trial, the `job` result carries a ready-made
  `obsidian_note` markdown block, and the skill or Training tells the agent to save it with file tools.
- Built-in memory gets only one pointer line, such as "fleet evidence lives in Agents/<profile>/". A mem0
  layer over the vault files comes later.
- Vault sync between DigitalOcean hosts and the owner's workstation (git or Syncthing) is unsolved here; see Risks.

### 2.5 Draft skill set (shared release `browser-fleet/`)

Every skill **except `fleet-router`** sets `metadata.hermes.requires_toolsets: [mcp-browser_fleet]`, so it
hides on profiles that are not bound.
- How the gate works: at prompt-build time it compares against the toolsets of the tools actually
  registered (`agent/system_prompt.py::_skills_prompt` @46d7718a) `[source-code]`.
- When it would hide skills: if the MCP server is unreachable and has no lazy schema cache, the gated
  skills disappear. This is untested hands-on.
- So `fleet-router` stays ungated. The front door must survive even then, so the agent can report "fleet
  unavailable".

Keep index descriptions under about 200 characters.

| Skill | Purpose (one line) | Triggers |
|---|---|---|
| `fleet-router` | Front door: fetch vs fleet, which identity, draft vs publish, which engine (`auto` by default), call order `status`, then `run`, then `job`. | Any web, browser, social, page-maintenance or lead task; "post / reply / DM / check my page"; WebFetch blocked or JS-only. |
| `fleet-identity-keeper` | Keep identities logged in without the agent ever typing credentials: read health, request `login_link`, hand the human the viewer URL, verify, honour cooldowns. | `status` or a job shows `needs_login`, `challenge`, 2FA, CAPTCHA or checkpoint; onboarding "connect my Instagram"; an account warning. |
| `fleet-stagehand-operator` | Run released deterministic procedures (Stagehand act/extract/observe, cached): exact inputs, extraction schemas, idempotency keys, reading cache-miss and self-heal signals. | A released procedure exists for site plus intent: post, reply, like or follow, inbox check, page edit, list scrape. |
| `fleet-browseruse-explorer` | Open-ended exploration under a step and spend budget. Read-only unless the scope allows writes. Ends by proposing a procedure through `feedback`. | No procedure; unfamiliar flow; multi-hop research; a procedure failed twice on layout drift. |
| `fleet-social-ops` | Platform playbooks (`references/facebook.md`, `instagram.md`, `tiktok.md`, `x.md`): pacing, daily caps, approval states, what counts as proof of posting. | Any Facebook, Instagram, TikTok or X action; page or profile maintenance; content calendars. |
| `fleet-lead-gen` | Self-enrichment through the agent's own fleet browsing (no paid enrichment services): sources, output schema, dedupe, storage. | "Find / enrich / qualify leads", building prospect lists, finding contact routes. |
| `fleet-checkpoint-escalation` | Never replay an uncertain effect: reconcile by `read` or `job`, checkpoint, escalate to a human with the exact blocker. | `outcome_uncertain`, timeout, a job in `unknown`, restart mid-job, budget exhausted, repeated failure. |
| `fleet-evidence-vault` | Write and verify the Obsidian run and daily notes. If the plugin hook already wrote them, verify instead of duplicating. | After any fleet job ends; end of session; "what did you do today". |

Constraints that apply `[source-code]`:
- Name at most 64 characters, lowercase `[a-z0-9._-]`.
- Description at most 1,024 characters. It sits in every session's prompt, so keep it short.
- Body at most 100k characters. Push platform detail into `references/`, at most 1 MiB per file.
- Avoid injection-pattern phrases, and avoid "do not tell/mention" and "system:" in MCP tool descriptions;
  they trigger warnings.
- Refer to tools by MCP tool name (`browser_fleet`'s `run`), not by the registered wire name, which can be
  hash-clamped.

---

## 3. What Hermes and the trial give us vs what the fleet must build

| Need | Hermes / trial provides | Fleet must build |
|---|---|---|
| Per-profile auth to a shared service | `${VAR}` headers from the profile `.env`, fail-closed, a connection per credential `[hands-on S7]`; trial `/integrations` | Token mint and rotation, token-to-binding table, provisioner, revocation |
| Profile-to-identity binding | Nothing (Camofox `managed_persistence` is the only built-in "stable identity per profile", and it is Firefox-only) | Identity registry, exclusive account binding, scopes, health states |
| Persistent browser state, proxy, fingerprint | Trial: per-employee Chromium user-data-dir, no proxy or fingerprint; hermes-steel: ephemeral Steel sessions only | All of it (other dossiers: Steel or Browserbase persistence) |
| Engine choice (Stagehand vs Browser-Use) | Nothing; Hermes' own browser stack is agent-browser plus Browser Use CLI (`browser_exec`) | Router inside the fleet; `engine=auto` default |
| Human login handoff | Elicitation form-mode only (URL-mode declined); trial noVNC takeover | `login_link` viewer flow, notification, verification |
| Effect safety (publish, DM) | Trial reserved-label gate (its own browser tools only); Hermes `trust: untrusted` (blocks cron) | Server-side draft/publish scopes, rate caps, idempotency keys, receipts |
| Long jobs | MCP timeout config; `outcome_uncertain` on expiry | Durable job queue (`run` then `job`), cancel, wake-on-demand browsers |
| Skill delivery and updates | `skills.external_dirs` (shared, indexed) `[hands-on S4]` | Release dirs, symlink flip, drift scan, `min_skill_version` |
| Evidence and memory | Built-in 2.2k-character memory; bundled obsidian skill; plugin hooks | Vault layout, note writer (hook), trial note format |
| Spend control | Trial $10 ledger (its own model calls only) | Per-token fleet spend caps and per-call cost reporting |
| Fleet-level scheduling | Hermes cron, script cron, Kanban (single host); super-agent Temporal pattern (LLM fan-out) | Per-identity schedules or routines in the fleet, or Kanban/cron integration |
| Observability | `hermes mcp test`, `prompt-size`, plugin doctor | Census of profiles, versions, identities and job outcomes |

---

## 4. Operating notes for a Hermes agent (feeds the skills)

- **Call order.**
  - Once per session: `status`, which returns bound identities and health, `min_skill_version` and spend.
  - Then `run`, which returns a `job_id` immediately.
  - Then `job(job_id)`, polled with backoff until it reaches `done`, `failed`, `needs_human` or `unknown`.
  - Never loop on `run` for the same intent: reuse the same `idempotency_key`.
- **Fetch first.** Public pages go through plain HTTP fetch or `read`. Use `run` only for logged-in or
  interactive work, because it wakes a browser.
- **Draft vs publish.** Default to `mode: draft`. `publish` works only if the token's scope allows it; when
  the server refuses, the refusal names the missing scope, which is an answer, not a bug.
- **`outcome_uncertain` or a timeout on a write.** Do not call it again. Call `job` or `read` to check
  whether the post or DM exists, then decide. This rule is non-negotiable.
- **Never type credentials.** No `browser_vault_*`; the `browser` toolset is disabled on fleet profiles.
  On `needs_login`, call `login_link`, send the human the URL, checkpoint, and stop.
- **Identity.** Pass the alias (`acme-instagram`). Never ask for or handle proxies, CDP URLs or cookies.
- **Screenshots** come back as links. Fetch one only when you must look at it: inline images are re-sent
  every turn.
- **Evidence.** After every job, the run note and daily line exist in `Agents/<profile>/`. Verify them;
  write them if the plugin did not.
- **Learning.** A repeatable success from explorer mode goes to `feedback` as a proposed procedure. Never
  edit `fleet-*` skills.
- **Limits.**
  - The client times each call out at 120 s (90 s in the trial), so `run` must return immediately.
  - Tool wire names may be hash-clamped beyond 64 characters.
  - The `X-Hermes-Profile` header is not on every request. The server trusts the token only.

---

## 5. Risks and unknowns

1. **Hermes velocity.** About 12,600 commits in 20 days. Behaviour differs across the three revisions in
   this dossier (plugin skills in the index; Skill Sync removed). Anything outside MCP, skills and the
   documented `ctx` will break. The trial's `registry.dispatch` monkeypatch is exactly that kind of
   coupling.
2. **1,000 profiles on one multiplexer is unmeasured.** That means about 1,000 MCP connections (distinct
   tokens never share), gateway startup time, RAM, and session DB growth. Mitigate with `lazy: true` and
   sharding profiles across hosts. Measure before committing.
3. **One bad `config.yaml`** fails plugin dependency prep for every profile on the install `[official-docs]`.
   The provisioner must validate. Prefer no-dependency plugins.
4. **Shadowing and self-edits.** A local `fleet-*` skill silently overrides the release `[hands-on S5]`.
   Writable external dirs let one agent's `skill_manage` patch reach every profile `[official-docs]`.
5. **Trial gaps.**
   - Authority allows a whole MCP toolset, so the fleet is the only gate on publish and DM.
   - Fleet model spend falls outside the trial's $10 ledger.
   - The trial's 90 s MCP timeout.
   - No skill or plugin channel.
   - Dual-login hazard if an account stays connected in the employee's Chromium.
   - No Phase 2 or migration is authorized, so the trial can only *consume* the fleet over MCP.
6. **Fresh-root bootstrap side effects.** A scratch `HERMES_HOME` isolates profile state but not the
   shared code checkout or the first-run update path. An interrupted first run can resume a source update
   that rebuilds artifacts inside the shared checkout. For fleet hosts: use baked images,
   `security.allow_lazy_installs: false`, and never create ad-hoc roots on a live host. Re-verify only in
   a capped `fleet-spike-*` container with its own Hermes clone.
7. **Plugin-provider path under multiplexing.** Third-party providers that read `os.environ` (for example
   hermes-steel) get the wrong secret or none for secondary profiles. `get_secret` is the internal accessor
   bundled providers use; it is mentioned in docs, but its stability is unverified.
8. **Unknowns.**
   - Whether MCP server `instructions` are ever surfaced (none found).
   - Whether `requires_toolsets: [mcp-browser_fleet]` gating works with lazy MCP toolsets.
   - Whether cron script jobs can read the profile's `BROWSER_FLEET_TOKEN`.
   - The vault sync topology between DigitalOcean hosts and the owner's workstation.
   - Whether a Steel or Browserbase identity can be shared with the trial's Cua Chromium (it should not be).

---

## 6. Sources

Upstream Hermes (read with `git show <rev>:<path>` from a local checkout; docs also live under
https://hermes-agent.nousresearch.com/docs/, HTTP 200 checked 2026-10-09):
- `website/docs/user-guide/profiles.md`, `profile-distributions.md`, `multi-profile-gateways.md`, `managed-scope.md` @46d7718a
- `website/docs/user-guide/features/{skills,plugins,mcp,memory,memory-providers,browser,kanban}.md` @46d7718a
- `website/docs/developer-guide/{plugins/index.md,browser-provider-plugin.md,creating-skills.md}` @46d7718a
- `website/docs/reference/{mcp-config-reference,toolsets-reference,profile-commands}.md`, `guides/cron-script-only.md` @46d7718a
- `agent/prompt_builder.py` (`_plugin_skill_prompt_rows`, added in 19cb1cbfed 2026-10-07) @46d7718a; absent @09681e7 and @8a92051f
- `tools/skill_manager_tool.py` (limits), `tools/skills_tool.py`, `tools/skills_tool_plugin.py`, `tools/mcp_tool_schema.py` @46d7718a (prefix also @8a92051f, @09681e7)
- `agent/browser_provider.py`, `agent/secret_scope.py`, `plugins/browser/browserbase/provider.py`, `hermes_cli/plugins.py` (`VALID_HOOKS`, `profile_name`) @46d7718a
- `hermes_cli/managed_scope.py`, `hermes_cli/config.py` (`_deep_merge`, `_expand_env_vars`), `hermes_cli/profile_distribution.py` @46d7718a
- `hermes_cli/subcommands/sync.py` @09681e7; removed in 64ad33e32d (2026-10-03)
- `hermes_cli/update_cmd_maint.py` (`_install_default_tools_after_update`) @09681e7
- Fork: `gh api repos/NousResearch/hermes-agent/compare/main...jbellsolutions:hermes-agent:main` reports ahead 0, behind 43,660 (2026-10-09)

Steel's Hermes plugin: https://github.com/steel-dev/hermes-steel @d8a1e39 (2026-07-17): `README.md`, `provider.py`, `config.py`, `plugin.yaml`.

Jev Workforce host (private repo, read-only; file list withheld).

`jbellsolutions/hermes-workforce-router` @7d9bb0e (2026-07-20): `GOAL.md`, `install.py`, `plugins/workforce_router/{plugin.yaml,plugin.py,hook.py}`, `skills/autonomous-ai-agents/workforce-router/SKILL.md`.

A prior internal fan-out project (private repo; file list withheld).

Local, read-only: a local Hermes config (shape only, secrets redacted). It shows the box attached the
same way, as a remote HTTPS MCP server with a Bearer header.

Spike: `fleet/research/spikes/hermes-packaging/{RESULTS.md,stub_mcp_server.py,stub-plugin/,shared-skills/}`.
