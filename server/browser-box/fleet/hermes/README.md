# Hermes packaging for the browser fleet

**Designed, not built.** Nothing in this folder runs. The eight `SKILL.md` files are drafts of text
(revision 2, after the scenario stress tests in [research/scenarios](../research/scenarios/)). The service
they talk to (`fleetd`), the provisioner, the release script and the optional plugin do not exist yet.
Every tool name below is a v0 design from [DECISIONS.md](../DECISIONS.md) D17 as expanded in
[ARCHITECTURE.md](../ARCHITECTURE.md) section 5. A name or code marked **[proposed]** in a skill is not in
ARCHITECTURE 5.x yet: section 7 lists each one with the edit it needs.

**Q-09 is answered (2026-10-10): this folder may merge and go public through the box-kit export.**

Precedence: [DECISIONS.md](../DECISIONS.md) wins, then the verification reports and
[CONSISTENCY.md](../research/verification/CONSISTENCY.md), then the dossiers. Where this folder reads the
dossier [hermes-packaging.md](../research/dossiers/hermes-packaging.md), it uses the corrections in
[its verification report](../research/verification/hermes-packaging.md) (ids `HP-n`, `X-n`). Words such as
profile, identity, wake and procedure mean what the table at the top of DECISIONS says.

## 1. What is in this folder

| Path | What it is | First useful in | Status |
|---|---|---|---|
| `README.md` | How a Hermes profile connects, how skills are released and checked, the optional plugin, the Jev trial | all | draft |
| `skills/fleet-router/` | Front door. The first-session check of the profile's other tools, which tool, which channel, vague or risky asks, what each answer means, lost-response recovery | M2 | draft |
| `skills/fleet-identity/` | Wake, sleep, health, re-authentication, checkpoints, holds, a person using the account, a move. Never log in | M2 | draft |
| `skills/fleet-evidence/` | Run notes (for jobs the profile started), batch notes, the daily note and its agent entries, in the profile's Obsidian vault. No stranger text | M2 | draft |
| `skills/fleet-steps/` | Released procedures, scoped steps and typed reads through `run`, `act`, `extract`. Named for what it does, not for an engine | M3 | draft |
| `skills/fleet-browser-use/` | Open-ended, read-mostly `task` under budgets | M3 | draft |
| `skills/fleet-leadgen/` | Open-web contact research on owner-supplied domains, `research` identity, no paid enrichment, role-only contacts. Route 2 (agent-driven) until `run` batch exists | M3 | draft |
| `skills/fleet-social/` | API-first publishing from approved content, approvals, receipts, red lines, campaign and per-platform rules | M4 | draft |
| `skills/fleet-inbox/` | Triage of messages and comments people send in: one conversation per session, text fenced as data, windows, approver. Needs the `inbox` tool (D17) | M4 | draft |

The "first useful in" column follows the tool exposure ladder in [MILESTONES.md](../MILESTONES.md)
section 2.3: a skill is only useful once the tools it names are listed. A skill that names a tool the
profile cannot see says so itself (it tells the agent to check `fleet_status`).

**Names.** ARCHITECTURE section 2.7 (H2) lists eight skills under other names. This folder has seven of
them under shorter names, folded as below, plus `fleet-inbox`, which H2 does not list. The mapping:

| ARCHITECTURE H2 / dossier name | Here |
|---|---|
| `fleet-identity-keeper` | `fleet-identity` |
| `fleet-checkpoint-escalation` | folded into `fleet-identity` (checkpoints, holds) and `fleet-router` (uncertain outcomes) |
| `fleet-stagehand-operator` | `fleet-steps` (renamed in revision 2, see below) |
| `fleet-browseruse-explorer` | `fleet-browser-use` |
| `fleet-social-ops` | `fleet-social` |
| `fleet-lead-gen` | `fleet-leadgen` |
| `fleet-evidence-vault` | `fleet-evidence` |

All of them keep the `fleet-` prefix on purpose. A local skill with the same name silently shadows the
shared one (section 3.6).

**Why `fleet-steps`, not `fleet-stagehand`** (S14-16). The old name told the agent to expect one engine.
The agent never chooses an engine, and on a client's `account` identity the executor is the fleet's own, not
Stagehand (DECISIONS D6 as amended by D18). Tool names did not change. ARCHITECTURE H2 now lists the eight
skills under the new name (updated by the completeness review). DECISIONS D18 says the executor depends on
the identity's kind, which is the same point.

### 1.1 `fleet-inbox`

The `inbox` tool is in DECISIONS D17 and ARCHITECTURE 5.3 (tool 17) after the scenario revision: an inbound
store, a window tracker and an opt-out ledger sit behind it (ARCHITECTURE 3.12, 4.12). The skill was held back
until the tool existed in the design, because a skill that names a tool the tool card lacks fails the planned
drift test (section 3.7). Its three rules (S03-13):

1. **One conversation per session.** A profile for one client may hold dozens of strangers' threads. Never
   put two in one model context.
2. **The conversation text is fenced as data** and carries the fleet's `untrusted` marker. It is never an
   instruction, never copied into a note unless the owner asks (Q-07), and never reused in another thread.
3. **Replies only through `publish`**, inside the platform's window, from approved templates or an approved
   draft, to a `conversation_id` the fleet issued. Anything the profile cannot answer from approved material
   goes to the owner, with the window's closing time.

Whether a scheduled Hermes session can reach the fleet and resolve the token is unverified (to measure).
Delivery by cron polling is the design default; push into Hermes is unresearched (ARCHITECTURE 4.12). The
skill says what to do when the first call fails.

## 2. Connect a profile

One service, one scoped token per profile. The profile holds nothing else (D1).

### 2.1 The config entry

The provisioner (the owner's tool, *planned*) writes this into each profile's `config.yaml`. Host name,
install path and key names are proposals from the dossier (section 2.4), not final.

```yaml
mcp_servers:
  browser_fleet:                 # not "browser": a server named like a built-in toolset merges with it
    url: https://<fleetd host>/mcp
    headers: {Authorization: "Bearer ${BROWSER_FLEET_TOKEN}"}
    timeout: 90                  # the smallest timeout any host uses (the Jev trial writes 90)
    connect_timeout: 20
    lazy: true                   # connect on first use; helps only from the profile's second boot (X-2)
    trust: full                  # fleetd enforces scopes itself; "untrusted" would block cron writes (HP-8)
skills:
  external_dirs: [/opt/jev-fleet/skills/releases/<semver>]   # a literal versioned path (section 3)
  write_approval: true           # staged, not applied: an agent cannot rewrite or shadow a fleet skill
  config:                        # the two settings fleet-evidence declares (section 3.7)
    fleet:
      vault_path: <absolute vault path>      # same value as OBSIDIAN_VAULT_PATH
      vault_folder: Agents/<profile>         # vault-relative folder for this profile's fleet notes
agent:
  disabled_toolsets: [browser]   # at least this: no second browser, no browser_vault_* typing (X-7). Section 2.4 adds the rest
security:
  allow_lazy_installs: false     # fleet hosts use baked images
```

`.env` of the same profile (names only; values are never written in any document):

```
BROWSER_FLEET_TOKEN=<minted by the provisioner>
OBSIDIAN_VAULT_PATH=<absolute path to this profile's vault>
```

Notes on the keys:

- **`timeout: 90`** and submit-then-poll. The dossier's sample used 120. The Jev trial writes 90 with
  `connect_timeout: 20`, and Hermes' own default is 300 (HP-5, CONSISTENCY C-15). Every call returns inside
  90 s. Anything longer is a job read with `job`. Tool calls take `wait_s` (default 20, maximum 60) and
  `job` long-polls up to 60 s ([ARCHITECTURE](../ARCHITECTURE.md) 4.0).
- **`trust: full`**. With `untrusted`, every write prompts a human and fails closed in cron (HP-8).
  The fleet cannot lean on that anyway: a plugin-less host may allow every tool on a connected server
  (HP-5). So `fleetd` checks the token's scopes (`read`, `draft`, `publish`, `dm`) on every call
  ([ARCHITECTURE](../ARCHITECTURE.md) 3.4, 4.0).
- **`lazy: true`** does not remove the first-boot cost. A new profile connects its MCP servers eagerly,
  one profile after another. The schema cache that makes `lazy` work is per profile and is written by a
  live registration (X-2). Whether `hermes mcp test` fills it is not verified. The provisioner should
  warm it. *To measure on a droplet.*
- **`identity_header`** (`X-Hermes-Profile`) is left out. It is a label, not authentication: it is
  missing on the HEAD and GET preflight, and Hermes' own docs say otherwise (HP-9). `fleetd` trusts the
  token only.
- **`skills.write_approval: true`** is the Hermes setting that stages every `skill_manage` write instead of
  applying it ([Hermes docs `user-guide/features/skills.md` @46d7718a](https://github.com/NousResearch/hermes-agent/blob/46d7718a52ff/website/docs/user-guide/features/skills.md),
  `official-docs`). It stops the background self-improvement loop from creating a local `fleet-*` skill that
  shadows the shared one. Staged writes pile up under the profile's `pending/skills/` and nobody is meant to
  approve them; the drift scan counts them (section 3.6). What an agent learns goes to `feedback`, and a
  human releases it (D13).
- **Tool names.** Hermes registers the tools as `mcp__browser_fleet__<tool>` and may clamp long names to 64
  characters with a hash. The skills use the short names (`run`, `job`) so a clamped name never matters.
- **`mcp_servers` holds `browser_fleet` and nothing else by default.** Section 2.4 explains why.

### 2.2 Token rules

- The token lives in that profile's `.env` and nowhere else. It is **never exported host-wide**. When a
  secret scope is bound, a missing variable can fall through to the process environment (HP-1).
- On a multiplexed gateway host, the **launch (default) profile gets no fleet token**: its `.env` is loaded
  into `os.environ`, where it would reach every profile that lacks its own (HP-1, missed issue 4).
- Fail-closed on a missing variable holds at Hermes `09681e7` and current main. At some older pins
  an unset `${VAR}` is sent **literally** as the bearer. `fleetd` therefore rejects any bearer
  that looks like `${...}` (`token_invalid`; D1, HP-1, ARCHITECTURE 3.4).
- Rotation is a provisioner action: rewrite `.env`; the next connect uses it.
- An auth error is an answer. The agent reports it and does not look for another token
  ([AGENTS.md](../AGENTS.md)).
- **Profiles are not sandboxes: the deployment rule** (S09-11). On the local terminal backend all profiles
  share one Unix user, so a prompt-injected agent can plausibly read a sibling profile's `.env` or vault
  through the terminal or file tools (untested; HP missed issue 5). For client profiles on a shared host:
  - **one OS user or one container per profile;**
  - **each profile's vault folder mode 0700**, owned by that user;
  - **a token only in its own user's environment** (and its own `.env`);
  - **no local terminal backend** for client profiles. A sandboxed backend must show a profile only its own
    folders.
  Tokens also carry the least scope that does the job, so one leaked token cannot publish for another
  client.
  - **Gate (planned; extends MILESTONES G2.2 and G7a.2).** A planted prompt makes profile A try to read
    profile B's token and B's vault, through the terminal and through the file tools. Pass: zero reads. G2.2
    today tests only the fleet-side token lookup, not file reads.
  - **This conflicts with section 5.** One multiplexing gateway process, under one OS user, serves every
    profile and holds every token in its secret scope. Per-user 0700 folders then stop that process (and a
    plugin running inside it) from writing other users' vaults. Two ways out, neither measured: (a) one
    gateway per OS user or container, which gives up the single-process scale assumption; (b) one gateway
    user plus a per-profile sandboxed terminal and file backend whose filesystem view holds only that
    profile's folder, which needs a Hermes backend that does this (unverified). *To measure on a droplet.*
    MILESTONES G2.2 already names (a) as the fallback ("one process per profile" becomes a written
    deployment rule). Until one passes the gate, profiles of different clients do not share a host. This is
    a default introduced here, not a DECISIONS entry. It matches the one-client-per-node default for
    browsers (Q-13) and costs host count at scale.

### 2.3 What the provisioner does per profile (planned)

All of this runs on Hermes hosts. **None of it runs on the maintainer's workstation**: no `hermes` CLI, no Hermes
install, no `HOME` override ([research/BRIEF.md](../research/BRIEF.md)).

1. If the profile is new, create it: `hermes profile create <name> --no-skills` (section 5).
2. Mint a token. Store only its HMAC in `fleetd`. Write `BROWSER_FLEET_TOKEN` and `OBSIDIAN_VAULT_PATH`
   into the profile's `.env`.
3. Merge the config block above into `config.yaml`, including the two `skills.config.fleet` values, and
   **validate the YAML**. One unparsable `config.yaml` fails plugin dependency preparation for every
   profile on the install (dossier risk 3).
4. Write the tool policy (section 2.4): `mcp_servers` and `agent.disabled_toolsets`. Create the profile's
   OS user or container and its 0700 vault folder (section 2.2).
5. Run `hermes -p <profile> mcp test browser_fleet` on the host.
6. Record the binding in `fleetd`: token to profile to identities, scopes, daily caps, the final tool list,
   and the skill release path it just wrote (section 3.5).

Optional hardening: a root-owned `/etc/hermes/config.yaml` can pin the `browser_fleet` URL so an agent
cannot redirect its own entry. Keep tokens out of it. Its `${VAR}` expansion is described one way in the
docstring and behaves another way in the code (HP-7), so do not rely on either.

### 2.4 What else a fleet profile may hold (G11-8)

The red lines bind the fleet. They do not bind the rest of the profile. A fleet profile that also holds a
social-platform toolkit, a LinkedIn lead MCP, a desktop-control tool or Hermes' own browser tools can do
"DM everyone who liked our post" or "scrape LinkedIn" with no fleet involvement. So **the red lines are only
as strong as the profile's other tools**, and the control is the provisioner, not a prompt
(CHARTER sentence still to be added, section 7).

- **`mcp_servers`:** `browser_fleet`, plus only servers on an owner-kept allowlist. A server that can post,
  DM, like, follow or read people on a social platform, a people-data or enrichment server, or a
  desktop-control server is never on it. Hermes has `tools.include/exclude` keys per server
  (dossier 2.1, `official-docs`); `ctx.call_mcp` stays at its default, off.
- **`agent.disabled_toolsets`:** `browser`, plus every other built-in toolset that can drive a browser or a
  desktop. The names come from Hermes' toolset reference. Only `browser` is confirmed (X-7). *Verify the rest
  on a host.*
- **The allowlist is by capability, not by product, and it bites.** Justin's standing directive names
  browser-use, Orgo and Composio as the agent's own enrichment stack. A desktop tool such as Orgo can be
  pointed at any host, so unless the provisioner can limit its reach, Orgo as a general desktop falls on the
  banned side. In effect that is a ban on it in a fleet profile. A Composio or Orgo tool that cannot reach a
  social platform stays allowed. Whether Composio's social toolkits are a problem is unresearched
  (MILESTONES N-9). The skills name no product as banned except paid enrichment services (Justin's absolute
  rule). **Pending Justin.**
- **The drift scan** (3.6) flags a profile whose tool list has gained a server or toolset the policy bars.
- **`fleet-router` first-session check** is the backstop: it lists the categories above and stops the
  agent if it holds one. A prompt-injected agent can skip a prompt, so this is never the control.

## 3. Skills: release, version, drift

### 3.1 Layout on a host

```
/opt/jev-fleet/skills/releases/<semver>/        read-only, never edited after publish
  fleet-router/SKILL.md
  fleet-identity/SKILL.md
  ...
```

The source of each release is `fleet/hermes/skills/` in this repo at a tagged commit. Skills are attached
with `skills.external_dirs`, one read-only directory per host. They are not copied into profiles. They
are not shipped inside the plugin either: plugin-registered skills reach the skill index only from Hermes
commit `19cb1cbfed`, and not at the tested or an older pin (HP-4).

### 3.2 No `current` symlink for Hermes

The dossier proposed flipping a `current` symlink. That does not work (X-1, `source-code`, not reproduced):
`get_external_skills_dirs` resolves the symlink and caches the **resolved** path, keyed by the profile's
`config.yaml` signature. The skills index is cached separately and does not watch directories. Outside
tests it is cleared only at gateway start and in CLI update, profile and hub paths. A long-lived gateway
therefore keeps serving the old release until its profile's `config.yaml` changes or the process
restarts. The provisioner may keep a pointer of its own to know which release is current. Hermes config
never points at it.

### 3.3 Release steps (planned; the release script and the provisioner do not exist)

1. Build `releases/<semver>/` from the tagged commit. Stamp each `version:` with the release semver (the
   value in this repo is a placeholder). Run the checks in section 3.7.
2. Make the directory read-only. **Never patch a published release.** The index cache does not watch the
   directory, so an in-place edit reaches processes unpredictably.
3. Canary: write the new literal path into a few profiles' `config.yaml` **and** roll the gateways that
   serve them (restart them a few at a time). Watch `fleet_status` and the first runs.
4. Roll the rest the same way. Then raise `min_skill_version` on the tokens. `fleetd` answers
   `skill_outdated` below it.
5. Keep old release directories until every process has recycled. Retire one only when a census shows no
   profile points at it.
6. Rollback is the same operation with the previous path.

**Both steps, not either.** D1 says "into each profile config and/or rolls gateways". Do both. The config
write changes the cache key. The roll is the backstop, and for `--no-skills` profiles it is the weaker
half: `sync_skills` returns early for profiles that carry the `.no-bundled-skills` marker, so a restart
alone does not rebuild the external-dir index there (X-1). This is source reading only. **Drill it on a
droplet** (MILESTONES gate G7a.5, "skill rollout drill").

### 3.4 Rules that follow from the cache

- **No `${VAR}` in the release path.** `external_dirs` accepts it, but the cache is keyed on the
  `config.yaml` signature, so an environment change goes stale. Write the literal path.
- **A missing directory is skipped without an error** (Hermes docs, External Skill Directories). Delete an
  old release too early and the profile loses its fleet skills silently. The drift scan checks that the
  path exists.
- The skills are text the agent follows. They are guidance, **not authority**. `fleetd` enforces scope,
  approvals, budgets and the governor on every call, whatever a skill says (D1, D13).

### 3.5 Minimum version, and a gap

`fleetd` stores `min_skill_version` per token. `fleet_status` returns `skill {your_version, min_version,
ok}` and the error code `skill_outdated` exists ([ARCHITECTURE](../ARCHITECTURE.md) 3.4, 5.3, 5.5). But
5.3 lists **no `skill_version` argument**, so `fleetd` has no way to learn which release a profile really
loads. Proposal for ARCHITECTURE: the provisioner records the release path on the token binding when it
writes the config (authoritative for what was *configured*), and `fleet_status` accepts an optional
`skill_version` that the skill passes (catches a gateway that has not rolled). The skill directory path
in Hermes' activation message (`[Skill directory: ...]`) contains the semver, so the agent can read it
without a second copy of the number. **Open: not in ARCHITECTURE yet.**

**Versions in revision 2** (S14-16). Every `version:` placeholder is `0.2.0`, and `fleet-stagehand` became
`fleet-steps`. Nothing is released, so there is no earlier release for `min_skill_version` to rise above:
the first release sets it. If a release ever ships both names, the old one is dropped in the same release,
or a profile would hold two skills for one job.

### 3.6 Drift scan (planned; scheduled on every host)

Flags, per profile and per host:

- a local `skills/**/fleet-*` directory, or one under `skills.create_dir`. A same-named local skill
  silently shadows the shared one at the tested and older pins. At main it only logs a WARNING
  (HP-3, `source-code`);
- a release directory that is writable;
- a profile whose `external_dirs` entry does not exist, is not a published release, or is below
  `min_skill_version`;
- staged skill writes waiting under `pending/skills/` (from `skills.write_approval: true`);
- a profile that carries `BROWSER_FLEET_TOKEN` in a host-wide environment, or the launch profile of a
  multiplexed host carrying a token;
- a profile whose `skills.config.fleet.vault_path` differs from its `OBSIDIAN_VAULT_PATH`, or is empty;
- a profile whose tool list has gained an MCP server or toolset the policy bars (section 2.4);
- a vault folder that is not mode 0700, or is not owned by the profile's own user (section 2.2).

### 3.7 Frontmatter, limits, and the checks on this folder

| Field | Use here | Source |
|---|---|---|
| `name` | `fleet-*`, lowercase, at most 64 characters | Hermes `tools/skill_manager_tool.py` limits, via dossier 2.1 |
| `description` | One line, 100 to 170 characters, with the trigger words. Hermes' own limit is 1,024. Its house style for generated skills is shorter, but this line is all the model sees before it loads the skill | dossier 2.1; Hermes docs, Skills System |
| `version` | Placeholder `0.2.0`, stamped by the release script | Hermes docs, SKILL.md Format |
| `metadata.hermes.requires_toolsets` | `[mcp-browser_fleet]` on every skill **except `fleet-router`**, so they hide on profiles that are not bound. `fleet-router` stays ungated so it can still say "fleet unavailable". Whether the gate works when the server is unreachable and the lazy cache is empty is **untested** | dossier 2.5; Hermes docs, Conditional Activation |
| `metadata.hermes.config` | Only `fleet-evidence` declares settings: two non-secret keys, `fleet.vault_path` and `fleet.vault_folder`. The provisioner sets them per profile. Hermes injects the values into the skill when it loads, so the agent needs no shell to find the vault (the Jev trial forbids shell scripts) | Hermes docs, Skill Config Settings |
| `required_environment_variables` | **Not used for `BROWSER_FLEET_TOKEN`.** Declared variables are passed through into the `terminal` and `execute_code` sandboxes, which would put the token in the agent's shell | Hermes docs, Creating Skills |

Each skill starts with one line saying it targets `fleetd` v0 tools that are designed but not built, and
ends with a `Tools:` line. Planned checks, from [AGENTS.md](../AGENTS.md):

- a drift test between `FLEET_TOOLS`, `docs/openapi.json` and these skills. It fails when a skill names a
  tool or a field that the tool card does not have. A name marked **[proposed]** in a skill is on a list
  the test must either allow while its ARCHITECTURE edit is open, or fail on (section 7);
- a size report. Revision 2 sizes, in characters including frontmatter and the sources line:
  `fleet-browser-use` 4.7 K, `fleet-inbox` 5.1 K, `fleet-steps` 6.0 K, `fleet-leadgen` 8.0 K,
  `fleet-identity` 8.8 K, `fleet-evidence` 9.5 K, `fleet-router` 10.6 K, `fleet-social` 11.7 K. Only the
  first three are near the size cap of a plugin-less host's guides (section 6), so the others need a hand-cut
  version for such a host. Hermes' own limit for a skill is far larger;
- a text scan for the phrases Hermes flags as possible prompt injection ("ignore previous instructions",
  "you are now", "system prompt:", `<system>`). A flag is a warning, not a block
  ([dossier](../research/dossiers/hermes-packaging.md) 2.1);
- a secrets scan, and a scan that no skill carries a date for future work.

## 4. The optional plugin `browser-fleet` (planned)

A thin Hermes plugin that writes evidence into Obsidian without spending a model turn. The skills work
without it: where it is absent, `fleet-evidence` tells the agent to write the note itself (D15).

**Contract.**

- No Python dependencies. Installed and enabled per profile (`plugins/` lives in each `HERMES_HOME`),
  pinned with `hermes plugins install <owner/repo> --ref <40-char SHA>`. The provisioner installs it.
  Manifest v2: `provides_hooks` must match what `register(ctx)` registers, or `hermes plugins validate`
  fails. (`hermes-workforce-router` uses `tools:` and `hooks:` instead and fails validation, dossier 2.3.)
- One hook: `post_tool_call`, an **observer**. Its return is ignored and it runs under
  `plugins.hook_callback_timeout` (default 30 s), failing open. It receives `tool_name`, `args`, `result`
  (a JSON string), `task_id` and `duration_ms`, so it accepts `**kwargs`
  ([Hermes docs `user-guide/features/hooks.md`](https://github.com/NousResearch/hermes-agent/blob/46d7718a52ff/website/docs/user-guide/features/hooks.md)).
- It acts only when `tool_name` ends with `browser_fleet__job`, the parsed result is a **terminal** job,
  and the result carries `obsidian_note`. It then writes `<vault>/<folder>/Runs/<job_id>.md`: to a
  temporary file, then a rename. If the file already holds the same content, it does nothing. `<folder>`
  is `skills.config.fleet.vault_folder` from the profile's config (the value the skill sees), falling
  back to `Agents/<ctx.profile_name>`.
- It reads the vault path through the profile's secret scope (`agent.secret_scope.get_secret`), not
  `os.environ`. Under the multiplexed gateway a profile's `.env` is not merged into the process
  environment. `get_secret`'s long-term stability is unverified (dossier risk 7).
- It has no network and does not call `fleetd`. It sees only results the agent already fetched, which is
  why `fleet-evidence` has the agent call `job` with `include: ["obsidian_note"]` when a job ends.
- **Batches (S04-10).** For a result that carries `obsidian_notes` [proposed], it writes each block, in
  code, word for word, at the vault-relative path the block names. This is the reason lead notes are not
  written by a model: 200 notes re-typed through file tools can change a quote after it was checked. It
  refuses a path that is absolute, contains `..`, or falls outside the vault folder, and it writes nothing
  it cannot place. It writes the index block fleetd made and does not build its own.
- **Second check, before any write (S13-4).** The block must carry the generator's integrity footer
  [proposed], and no live
  `[[`, `![[`, `%%`, `<%`, `{{`, `$=` or HTML may sit outside a fence. A block that fails is not written;
  the plugin logs one line. fleetd's generator is the first check. This is the second.
- Before writing it removes anything that looks like a token, a cookie or a viewer URL. Any error: log
  one line and carry on. It never writes outside the profile's vault folder and never edits skills.
- A `/fleet` command prints local facts only: plugin version, vault folder, the latest run notes.

### 4.1 The vault, as a security surface (S13-4)

Obsidian renders what the profile saves, and a later semantic layer may index it. Stranger text (a comment,
a DM, a page quote) is hostile input that persists. Requirements, none built, none measured:

- **The generator never inlines stranger text.** A quote goes to an evidence file by opaque ref, or into a
  fence longer than any backtick run inside it, with `[[`, `![[`, `%%`, `<%`, `{{`, `$=` and HTML
  neutralized, and a length cap. The same holds for lead notes (`docs/playbooks/lead-gen.md` 4.6). This is a
  rule for the `obsidian_note` and `obsidian_notes` generator (ARCHITECTURE 5.3 tool 10).
- **Blocks that hold stranger text are tagged `untrusted` [proposed].** The later mem0-style layer over the
  vault excludes them from recall, so hostile text is never retrieved as an instruction. That layer sits on
  top of the vault and never replaces it (Justin's standing directive).
- **No auto-run code plugin on fleet folders.** Community plugins that execute code written inside a note
  (the scenario names Dataview inline and JS queries, and Templater-style tags) must not run on the
  profile's fleet folder. This comes from the scenario finding, not from a check of Obsidian's docs. *Verify
  per plugin before the vault is shared.*
- **One vault folder per client, mode 0700** (section 2.2).
- **Evidence links are opaque refs.** Notes never hold a link that expires or that grants access (H5).

**Not in v0.** The experimental `BrowserProvider` that leases the CDP URL to Hermes' native `browser_*`
tools would hand clicks to the Hermes model and bypass the ladder and the gates
([ARCHITECTURE](../ARCHITECTURE.md) 2.7 H3). Hermes' built-in Browserbase provider is also not used (D11).
The optional `pre_llm_call` one-liner is left out.

**Where it does not load.** The Jev trial builds its agent with a fixed toolset and patches
`registry.dispatch`, so plugins never load there (HP-5). Section 6 covers that case.

## 5. One Hermes root, many named profiles

- **One root, never one root per profile.** A fresh root bootstrapped about 1.4 GB (no artifact saved,
  HP unsourced numbers). An interrupted first run can resume "an interrupted source update"
  and rebuild artifacts inside the shared Hermes checkout (HP-10). So: baked images, no ad-hoc roots on a live host, and no Hermes bootstrap on the maintainer's workstation.
- **`hermes profile create <name> --no-skills`** for fleet profiles, plus the shared fleet skills through
  `external_dirs`. The prompt is about 9,175 characters instead of 14,485 (X-9, from the saved
  prompt-size files); most of the fixed budget is tool schemas, not the skills index. The per-profile disk
  figures (184 KB against 3.4 MB) have no saved artifact (HP-10) and are not relied on. The command writes
  a `.no-bundled-skills` marker, so updates and syncs skip bundled skills for that profile (Hermes docs,
  Starting with a blank slate).
- **Do not use** Skill Sync (removed upstream, and it never worked against a public service, HP-6),
  profile distributions to update live profiles (no ref pin for git sources, and updates overwrite
  `SOUL.md`, `mcp.json` and skills unless `distribution_owned` narrows them), or pip entry points.
  Distributions are fine for *creating* a role template.
- **`SOUL.md`.** The character section in [SOUL.md](../SOUL.md) is pasted by the provisioner into each
  profile's `SOUL.md`. It applies to new sessions only, and a distribution update overwrites it, so the
  provisioner re-applies it or excludes the file (HP-6).
- **Pin Hermes per host** and upgrade only after the plugin doctor and validate, `prompt-size`, `mcp test`
  and the external-dirs listing pass on a droplet (dossier 2.4). Hermes moved about 12,600 commits between
  an older pin and main (dossier header); anything outside MCP, skills and the documented plugin
  surface can break.
- **Scale is unmeasured.** No tested limit exists for 1,000 profiles on one multiplexing gateway: about
  1,000 MCP connections (distinct tokens never share one, X-3), startup time, memory and session-database
  growth. Measure before committing. Sharding profiles across hosts is the fallback.
- **One profile, one client.** The provisioner binds a profile to the identities of **one** client. A profile
  may hold several identities of that client (for example its Instagram and its Facebook Page). This keeps a
  vault folder equal to a client's folder (section 7, gap 5). It also keeps several strangers' threads out of
  one model context: a profile with 50 identities of one client still triages **one conversation per
  session** (section 1.1). A client with very many identities may need several profiles, never the reverse.

## 6. Hosts that cannot load plugins (for example the Jev Workforce host)

**Default: the fleet is not connected to the trial. Pending Justin, Q-11.** Everything below applies only
if he says yes and names who holds the owner role.

**How the fleet connects, with no change to the host (HP-5):**

- The owner registers the fleet as an MCP server through the host's own integration route, over HTTPS, with the server paused. The host stores the token as a literal string and applies its own short timeout.
- Use the name **`browser_fleet`**, so the toolset id is `mcp-browser_fleet` and the skills' gate matches.
- Once connected, such a host may allow **every** tool on the server and may guard only its own browser tools. The fleet is the only gate (scopes, approvals, governor).

**How guidance arrives.** Plugins and `external_dirs` are unreachable. Skills are short prose guides the owner approves. They carry **no executable authority** (D13, CONSISTENCY section 3b) and only describe `fleetd` tools; a size cap applies, so the larger skills are cut by hand. **A guide must say that client accounts are touched only through fleet tools** (S13-16). It cannot make it so. See "What the fleet cannot enforce" below.

| Skill | As a prose guide on a plugin-less host (if Q-11 is yes) |
|---|---|
| `fleet-router` | Yes, trimmed: tool choice, the answers table, polling, lost-response recovery, the vague-ask rule |
| `fleet-identity` | Yes: status, the reauth call (the fleet sends the link to the owner; the employee ends the run and does not poll, because its turns are capped), checkpoints, holds |
| `fleet-evidence` | **Yes, essential.** There is no plugin, so the agent writes the note from `obsidian_note` (or `obsidian_notes`) word for word |
| `fleet-steps` | Read-only use only: `extract`, and `act` in `read_only` mode |
| `fleet-browser-use` | Yes: `task` in `read_only` mode |
| `fleet-leadgen` | Yes, on `research` identities, route 2 only until `run` batch exists. Not before N-4 |
| `fleet-inbox` | **No by default,** for the same reason as `fleet-social`: its replies are external outreach. Pending Q-11 |
| `fleet-social` | **No by default.** Hosts that forbid external outreach already cover what this skill does. Draft-only text (draft, `approvals`, read the receipt) is a possible later cut, pending Q-11 |

**Limits to design around:**

- Each employee turn is capped by the host. Guides stay
  short, and the agent long-polls `job` (`wait_s` up to 60) instead of spending turns on short polls.
- **Dual-login hazard.** Never let one social account be logged in from the employee's in-container
  Chromium *and* a fleet identity: two fingerprints, two IPs ([ARCHITECTURE](../ARCHITECTURE.md) 5.6).
- Fleet-side model spend is capped by the fleet's own spend ledger.
- **Unresolved collision.** A host-appended instruction restricting tool use may steer
  the employee away from calling MCP tools directly. Nobody has tested it. It is a gate for the first
  connection, not an assumption.
- **Vault reach.** Whether a trial employee's runtime can write to an Obsidian vault at all is
  unverified (O-14). If it cannot, the guide tells it to put the `obsidian_note` block in its reply to the
  owner instead of dropping it.

**What the fleet cannot enforce here** (S13-16). An employee on such a host may keep Hermes' native `browser_*` tools and
its terminal, and both sit outside the fleet's gate. A prose guide has no executable authority. So nothing on
the fleet side can stop a connected employee from touching a client's account by another route, or from
holding the banned tools of section 2.4. **The default stays "not connected" (Q-11) until employees bound to
fleet identities have no native browser.** That is a change to the host's own employee toolset, which the
fleet does not own.

## 7. Dependencies, gaps and pending answers

**What each part waits on** (milestones, not dates; [MILESTONES.md](../MILESTONES.md)):

| Part | Needs |
|---|---|
| Skills `fleet-router`, `fleet-identity`, `fleet-evidence` | M2: `fleetd` core, tokens, `fleet_status`, `identity_status`, `identity_control`, `job`, `cancel`, `feedback` listed after their end-to-end checks |
| Release and drift tooling, provisioner, tool policy (2.4), isolation rule (2.2) | M2 (gate G2.2 token isolation, extended; G2.5 one profile end to end; G2.7 Obsidian); rollout drill G7a.5; isolation gate G7a.2, extended |
| `fleet-steps`, `fleet-browser-use` | M3: `extract`, `act`, `task`, `run` for read procedures, behind the read-side red-line gate (G11-4) |
| `fleet-leadgen`, route 2 | M3 as above, plus N-4 for any live company site (until then: listed test pages only) |
| `fleet-leadgen`, route 1 | `run` batch and the procedure `open-web-contact-extraction`; fleetd-rendered lead notes (`obsidian_notes`) |
| `fleet-social` | M4: `publish`, `approvals`, connectors, governor, effect ledger. Its campaign section (7) also waits for a manifest tool and a media path |
| `fleet-inbox` | M4: inbound store, webhook receivers, window tracker, the `inbox` tool, approvals that know the window |
| Plugin | M2 (Obsidian gate); batch writes with the lead notes |

**Pending Justin.** Skills proceed on the recommended default and say so where it matters.

| Question | Where it shows up here |
|---|---|
| Q-01 API-first or browser-first | `fleet-social`, `fleet-router` channel rules (ARCHITECTURE 8.5 item 5). Default: API-first |
| Q-05 X "Automated" label | `fleet-social` (X) |
| Q-06 developer apps and spend caps | `fleet-social`: until an approval lands, the API channel answers `channel_unavailable` |
| Q-07 data handling | `fleet-evidence`: what may be written into notes about client pages; `fleet-leadgen`; `fleet-inbox` |
| Q-11 Jev trial | Section 6. Default: not connected, and not connected until employees bound to fleet identities have no native browser |
| Q-13 one client per node | Section 2.2: profiles of different clients do not share a host until the isolation gate passes |
| Q-14 consent-based lead channels | `fleet-leadgen` |
| N-4 live runs on company sites | `fleet-leadgen`. Default: not allowed |
| N-9 build connectors or use Composio | Section 2.4 (the tool policy is by capability; Composio's social toolkits are unresearched) |
| N-10 legal review (GDPR, CCPA) | `fleet-leadgen`: role-based contacts only until answered |
| O-14 vault location and sync | `fleet-evidence`, sections 4 and 6 |
| Q-09 exclude `fleet/` from the public export, or move it to a private repo | This whole folder. It does not merge or export until answered (top of this file) |
| Q-12 a capped throwaway droplet for hands-on work | Every "drill on a droplet" and "to measure" item here waits on it |

**Gaps this folder found, for ARCHITECTURE or DECISIONS** (not edited here). Revision 1:

1. **Skill version reporting** (section 3.5): no `skill_version` input in ARCHITECTURE 5.3. Without it `fleetd`
   cannot see a renamed skill (`fleet-steps`) or a profile that did not roll (S14-16).
2. **D1 says "and/or"** for a skill release. It should say "and" (section 3.3).
3. **D17 `approvals` is one write tool**; ARCHITECTURE splits it into `approvals` (read) and `approve`. The
   skills follow ARCHITECTURE: a profile token never answers approvals.
4. **Skill names differ** between ARCHITECTURE 2.7 (H2) and this folder (section 1). H2 should list
   `fleet-steps` and `fleet-inbox`.
5. **Vault folder per client.** ARCHITECTURE H5 says `Agents/<profile>/{Daily,Runs,Identities}/`.
   [AGENTS.md](../AGENTS.md) and [SOUL.md](../SOUL.md) say "that client's folder only". Section 5's
   one-profile-one-client rule makes them agree. H5 should list `Leads/<domain>.md` (an extension, lead-gen
   playbook 4.6).
6. **No tool lists manifest items.** Scenario S02-1 proposes a `manifest` tool (propose, revise, list, get).
7. **After an approval on the API channel**, ARCHITECTURE 4.7 says a browser-channel job resumes by itself,
   and 5.3 does not say what the caller does for an API-channel `publish`. `fleet-social` follows
   `error.next` and `job`.
8. **Latency-sensitive inbound DMs.** Messenger expects a bot answer within 30 s (social-platforms
   verification SP-10, missed issue 8). A Hermes model turn may be too slow. Which reply path
   is used is undecided; `fleet-social` says to ask.
9. **The trial's appended line** and MCP tool use (section 6).
10. **Fetch manners for lead work.** The dossier's tier-0 fetcher honours robots.txt, identifies itself and
    paces per domain. ARCHITECTURE 4.4 (`extract` with `via: http`) says none of that. It should be a
    stated requirement there. `fleet-leadgen` treats it as a requirement, not as a fact.

**Edits other files need, from the scenario stress tests (revision 2).** Checked against DECISIONS and
ARCHITECTURE as they stood when this folder was revised: both had already taken `reauth` without a URL
(D17, 5.3 tool 3, 4.8), the `refused` code, `inbox`, `manifest` and `manifest_status`, `run` batches
(`seeds`), the `canary` and `migrating` states, the `human_session` lease purpose, `holds[]` with scopes,
`missed` items, and D18 (executor by identity kind). The skills use those names as they are. What was still
open, and what the skills mark **[proposed]**, is below. None of these edits was made here: this folder owns
only itself. Gap ids are those of [research/scenarios](../research/scenarios/).

| # | File | Exact edit | Gap |
|---|---|---|---|
| 11 | ARCHITECTURE 5.5 | Three things. (a) Add `duplicate_content` (CHARTER and SOUL already use it as "rewrite, do not slip past"). (b) The `needs_reauth` row still says "with a viewer link" and "Give the link to a human". That contradicts 4.8, 5.3 tool 3 and D17: the agent never gets a link, and a job that hits a login wall already has a ticket out, so the caller move is "tell the owner and end the run; do not call `reauth` again". (c) The `identity_held` row's caller move says "wait for reconciliation" for every reason. 3.11 says only `uncertain_effect` waits; `proxy_mismatch`, `persona_mismatch`, `upload_failed` and `owner_hold` are owner-or-operator clears (`needs` shows `owner`). The skills implement 3.11. 5.5 also has no `proxy_*` rows: `proxy_mismatch` is a hold reason and a job error, and a vendor outage is a retryable `infra_unavailable` | S07-14, S02-5, S05-13 |
| 12 | ARCHITECTURE 4.8 and 4.11; DECISIONS D14 | A "login done" has no author for the next-day check. The canary rule covers the first read-only probe. If the fleet also queues a verification wake, make it a system job (`verify`) and say in D14: "this is the only probe outside real work; it is not a keep-warm probe". `fleet-identity` is written for that wording | S01-15 |
| 13 | ARCHITECTURE 5.3 tool 10 | `job` list rows say who started the job (`agent`, `scheduler`, `system`, `human`). `fleet-evidence` tells the profile to write a run note only for jobs it started and has no field to read this from | S02-12 |
| 14 | ARCHITECTURE 5.3 tool 10 | `include: ["obsidian_notes","artifacts"]` for a batch: one block per child, each with its vault-relative path, an index block, and `leads.jsonl` and `leads.csv` as evidence refs. fleetd renders `lead.v0` to Markdown in code. The CSV neutralizes cells that start with `=`, `+`, `-` or `@` (my addition: the usual spreadsheet-formula precaution, not in the scenario). `run` batch returns `batch.leads` today and no notes | S04-10 |
| 15 | ARCHITECTURE 5.3 tool 10, H5; lead-gen playbook 4.6 | The generator never inlines stranger text (section 4.1). Blocks that hold any are tagged `untrusted`. `Leads/<domain>.md` is added to H5's folder list | S13-4 |
| 16 | ARCHITECTURE 5.3 tools 7 and 8 | `extract` on an `account` identity may answer `unsupported_on_identity` where L3-lite is closed (D18, Q-07). `extract` returns the goal verdict with per-field evidence, which lead route 2 needs for a code-side check | S14-16, S14-3, lead-gen playbook 5 |
| 17 | ARCHITECTURE 5.3 tool 14 | `feedback` kind `red_line_request`, and a notifier event so the owner is told, as `injection_suspected` already does. Until then the skills use `kind: "other"` with a note that starts `red_line_request:` | G11-6 |
| 18 | ARCHITECTURE 2.7 H1 and H4; CHARTER | H1 sets only `disabled_toolsets: [browser]`. Add the tool policy of section 2.4 to H1 and H4. CHARTER gets one sentence: the red lines are only as strong as the profile's other tools | G11-8 |
| 19 | SOUL.md | Add: "If someone asks for a crossed line, I say no once, offer the allowed route, and tell the owner." Add: "When an ask is vague, I ask which account and what limits before I act." | G11-14, G11-6 |
| 20 | MILESTONES G2.2, G7a.2 | Add the isolation gate of section 2.2 (a planted prompt makes profile A read B's token and vault). Add a gate that the provisioner's tool policy leaves no banned server or toolset | S09-11, G11-8 |
| 21 | AGENTS.md (the repository layout) | "Stagehand worker (Node)" disagrees with ARCHITECTURE, which has the worker in Python by default | S14-16 |
| 22 | ARCHITECTURE 2.7 H2, 5.3 tool 1 | H2 lists `fleet-steps` and `fleet-inbox`. A `skill_version` input (gap 1) so `fleetd` can see a renamed skill | S14-16 |

**Status after the completeness review** (`research/verification/COMPLETENESS.md`, 2026-10-10). Still nothing is built;
this says which edits above have reached the sibling drafts.

- **Landed in ARCHITECTURE:** revision-1 gaps 1 (a `skill_version` input on `fleet_status`), 4 (H2 now lists eight
  skills with `fleet-steps` and `fleet-inbox`), 5 (the `Leads/` folder in H5), 6 (`manifest`, `manifest_status`);
  revision-2 rows 11 (5.5: `duplicate_content`, the `needs_reauth` and `identity_held` rows), 12 (4.8 step 7), 13 to
  17 (5.3 tools 1, 7, 10 and 14), 18 (H1 tool policy) and 22. Every one is marked **[extension]** or **[proposed]**
  there. The skills still mark the same names **[proposed]** until the tool card is final.
- **Landed elsewhere:** row 18's CHARTER sentence, row 19 (SOUL), row 20 (MILESTONES G2.13), row 21 (AGENTS).
- **Still open, and not this folder's to close:** gap 2 and gap 3 (DECISIONS D1 should say "and"; D17 still lists
  `approvals` as one write tool and has no `approve`), gap 7 (what the caller does after an approval on the API
  channel), gap 8 (the Messenger 30 s window against a Hermes model turn), gap 9 (the trial's appended line), and
  the D14 sentence in row 12.

**Where this folder departs from, or adds to, what it was given.**

- The `fleet-social` browser-channel list followed an older wording. It now follows the DECISIONS D2 table:
  no browser identity for Facebook personal profiles, Instagram personal accounts or LinkedIn actions; Groups
  and UI-only features are `human_clicks` by default.
- `fleet-leadgen` now follows the lead-gen playbook where the first draft did not (named people, third-party
  sources, note names, model prose, the route it runs).
- The Orgo and Composio tension in section 2.4 is flagged, not decided.
