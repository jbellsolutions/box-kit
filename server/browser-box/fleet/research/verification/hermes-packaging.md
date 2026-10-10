# Adversarial verification: hermes-packaging dossier

Verifier: adversarial verifier (did not write the dossier). Date: 2026-10-10.
Spend: $0.00 (no model or paid API calls). Containers started: none. Browsers launched: none.
Hermes CLI run: never. `HOME` overridden: never.

Dossier: `fleet/research/dossiers/hermes-packaging.md`.
Claims file: `fleet/research/verification/claims/hermes-packaging.json`.

## Method

The author read upstream Hermes with `git show` from a local checkout and ran spikes at `09681e7`. I used a
different route where I could:

- **Upstream source.** Fetched the exact pinned files from GitHub with `gh api .../contents/<path>?ref=<sha>` at all
  three pins: `46d7718a` (main), `09681e79` (the author's hands-on pin) and `8a92051f` (an older pin). Local copies
  are in `<scratch>/spikes/verify-hermes-packaging/src/<pin>/`.
- **Commits.** Commit ancestry and counts came from `gh api .../compare`.
- **Host repo.** Read the plugin-less host's source through `gh api` at a pinned commit.
- **Steel plugin.** Read `steel-dev/hermes-steel@d8a1e39` through `gh api`.
- **Live docs.** Re-fetched four pages with `curl` on 2026-10-10 14:25 UTC: `reference/mcp-config-reference`,
  `user-guide/features/skills`, `developer-guide/plugins` and `user-guide/profile-distributions`. All returned HTTP 200.
- **Raw spike outputs.** Checked `<scratch>/spikes/hermes-packaging/*` against `RESULTS.md`, and recomputed the
  stub server's sha256 prefixes.

No hands-on reproduction was done this round, per the task rules.

Commit facts I established, which the claims below lean on:

- `8a92051f...46d7718a`: ahead 12,606.
- `09681e79...46d7718a`: ahead 4,595. The hands-on pin is 4,595 commits behind the main the design targets.
- `19cb1cbfed` is an ancestor of main (main is 635 ahead of it) and comes after `09681e7`.
- `64ad33e32d` is 1,794 commits after `09681e7`. Its committer date is 2026-10-04 06:05 UTC; the dossier says
  2026-10-03, which matches US local time.
- Fork `jbellsolutions/hermes-agent`: ahead 0, behind 43,783 today. The dossier's 43,660 was correct on 2026-10-09.
  Last push 2026-05-06.

## Verdict table

| id | claim | verdict | method | evidence | correction | impact |
|---|---|---|---|---|---|---|
| HP-1 | A `Bearer ${BROWSER_FLEET_TOKEN}` header resolves from each profile's own `.env`. Each profile sends only its own token. A profile without the variable fails closed before any request. | partially-confirmed | Source at all 3 pins via `gh api`. Raw `stub-mcp.log`. Recomputed sha8. | **Raw log.** Recomputed `sha256("Bearer spike-dummy-token-A")[:8]` = `ab25052b` and B = `0977a2e3`, matching the log. p3 has no log line.<br>**Fail-closed code.** `tools/mcp_tool_config.py::_require_rendered_remote` at 09681e7 and main raises "…is not set in this profile's .env or secret source". It is called on the shared connect path (`mcp_tool_discovery._connect_server`).<br>**Not at the older pin.** At `8a92051f`, `_interpolate_env_vars` "Unset vars keep the literal placeholder" and no `_require_rendered_remote` exists, so the literal `${VAR}` is sent.<br>**Fallback.** `agent/secret_scope.get_secret`: when a scope is bound, a miss falls through to `os.environ` unless the process serves a routed or multiplexed profile.<br>**Test scope.** S7 ran separate `hermes -p pX mcp test` processes. It never exercised the multiplexed gateway. | Fail-closed holds only at ≥09681e7, and only when the variable is also absent from the **process** env. In a single-profile process, a host-wide `BROWSER_FLEET_TOKEN` (systemd, compose, shell) would be used by any profile that lacks its own. Never set it host-wide. On a multiplexed host, do not give the launch/default profile a fleet token: `load_hermes_dotenv` puts the launch profile's `.env` into `os.environ`. Per-profile isolation under the multiplexer is source/docs-verified, not hands-on. | detail |
| HP-2 | `skills.external_dirs` lets one read-only shared dir serve several profiles, and its skills appear in each profile's skill index. | confirmed | Source at 3 pins, docs, live docs. Raw artifacts checked. | `agent/prompt_builder.py` scans `get_all_skills_dirs()[1:]` / `get_skill_search_roots` external roots into the index at 8a92051f, 09681e7 and main. `features/skills.md` "External Skill Directories" @46d7718a, also live 2026-10-10. **Raw gap:** no saved `skills list` output for S4. The only p4 `prompt-size` JSON (`promptsize-p4.json`, 23:02:13) predates the external-dir config and lists 1 skill (`hermes-agent`). | Mechanism confirmed by source. The S4 hands-on observation has no artifact. See also the symlink-cache finding X-1, which affects how this dir can be versioned. | none |
| HP-3 | A same-named local skill silently shadows the shared external skill. | partially-confirmed | Source at 3 pins, docs and live docs. | **Precedence.** project > local > create_dir > external_dirs at all pins.<br>**09681e7 and 8a92051f.** External names "already indexed are skipped" with no log. Shadowing is silent there.<br>**Main.** `agent/skill_utils.resolve_skill_catalog` logs `WARNING "Skill '%s' at %s is shadowed by a higher-precedence copy"` once per process, unless the copy is byte-identical.<br>**Docs.** main's `skills.md` says "The hidden copy is logged as shadowed" (live 2026-10-10). The dossier cites this doc but omits that sentence. | Shadowing is real on every pin. It is silent at 09681e7 and the trial pin. At main it writes a log WARNING, which is not visible to the agent. The drift scan is still needed. | detail |
| HP-4 | Plugin `ctx.register_skill` skills reach the `<available_skills>` index only from `19cb1cbfed` (2026-10-07). They are absent at 09681e7 and 8a92051f. Plugin docs at main still say they are not listed. | confirmed | Commit diff via `gh api`, grep at 3 pins, live docs. | `19cb1cbfed`: "fix: disclose enabled plugins' registered skills in the system prompt's available_skills index" (+44 lines in `agent/prompt_builder.py`). `_plugin_skill_prompt_rows` count: 0 / 0 / 2 at 8a92051f / 09681e7 / main. The live `developer-guide/plugins` page (2026-10-10) still says "Plugin skills are **not** listed in the system prompt's `<available_skills>` index". | none | none |
| HP-5 | On a host that cannot load plugins the only no-code route is the host's own MCP integration route, which requires HTTPS and stores the token as a literal. The host may allow every tool of a connected server and guards only its own browser tools. Prose guides of limited length are admitted on owner approval alone, so they carry no executable authority. | partially-confirmed | Read the host's source at a pinned commit. | Integration route, authority check and guide-admission path read in source. | Facts confirmed. "Skills cannot reach such employees" is refuted: owner-approved prose guides are a no-code skill channel. The host appends its own restriction on outreach to guides, so guide wording must be designed around it. Plugins remain unreachable. | design-changing |
| HP-6 | Skill Sync was removed on 2026-10-03. Profile distributions have no git-ref pinning: they shallow-clone the default branch and strip `.git`. | partially-confirmed | Commit via `gh api`, source, live docs. | **Skill Sync.** `64ad33e32d` deletes `hermes_cli/subcommands/sync.py` and `tools/skills_sync_client*.py`. Its message says Skill Sync "only worked against a Nous Portal sync plane that was never made publicly accessible, so no install has ever used it".<br>**Distributions.** `profile_distribution._git_clone` runs `git clone --depth 1`, and `_stage_source` runs `rmtree_readonly(staged/".git")`. The live doc (2026-10-10) says "Git ref pinning (#v1.2.0) is planned but not in the initial release".<br>**Local installs.** The same doc documents `hermes profile install ~/my-profile-in-progress/`, and `_stage_source` says "a local directory is used in place". | Dates are UTC 2026-10-04. Nothing usable was lost when Skill Sync went. "Unpinned" is true only for git-URL installs. A provisioner can pin by checking out a SHA locally and installing from that directory. The dossier's other objections to distributions still stand: they overwrite SOUL and are unsigned. | detail |
| HP-7 | Managed scope replaces lists wholesale and expands `${VAR}` only against the process env, not profile `.env` files. | partially-confirmed | Source @46d7718a. | **Lists.** `hermes_cli/config.py::_deep_merge` recurses dict-over-dict only and replaces everything else. Confirmed.<br>**Env expansion.** The "PROCESS env only" wording is in the docstrings (`managed_scope.apply_managed_overlay`, `config._merge_managed_overlay`). The code path is `_expand_env_vars → _env_expand_match → _env_ref_lookup`, which calls `get_secret` (the bound profile scope) whenever a scope is installed. In single-profile processes, `load_hermes_dotenv` loads the profile's `.env` into `os.environ`, so there the "process env" is that profile's `.env`. | List replacement is confirmed. The env claim describes intent, not reliable behaviour: actual resolution depends on scope and context. The recommendation stands and is stronger: never put per-profile tokens in managed scope, because the result depends on undocumented context. | detail |
| HP-8 | After session expiry, only `readOnlyHint: true` MCP tools are replayed. Unannotated tools return `outcome_uncertain`. Default timeout is 300 s. `trust: untrusted` makes writes need approval and fail closed in cron or unattended runs. | confirmed | Docs (author's route), plus source at 3 pins, plus live docs. | **Docs.** Live `mcp-config-reference` (2026-10-10): "only readOnlyHint: true tools are replayed, while unannotated (write-capable) tools return an outcome_uncertain error".<br>**Timeout.** `mcp_tool_common._DEFAULT_TOOL_TIMEOUT = 300` at all 3 pins.<br>**Replay guard.** `mcp_tool_handlers` passes `call_may_have_side_effects=not read_only` at all 3 pins.<br>**Untrusted.** `_trust_gate_check` → `request_elicitation_consent` returns `"decline"` when `_no_user_can_answer()` (cron, `-q`, unattended). | Addition: in a gateway chat session, an untrusted write asks the human through the platform, so it is not always a hard failure. The fleet also controls when its own MCP sessions expire, which decides how often `outcome_uncertain` happens (see missed issue 7). | none |
| HP-9 | `identity_header` is not sent on the HEAD/GET preflight, only on MCP session traffic. The bearer is on all of them. | confirmed | Raw log plus source at 09681e7 and main. | **Raw log.** HEAD and GET carry `auth_sha8` with `x_hermes_profile: null`. POST, GET and DELETE carry p1/p2. n = 2 profiles.<br>**Source.** `mcp_tool_server_run.py:291` calls `_preflight_content_type(..., headers=dict(config.get("headers")))`, while `_apply_identity_header` is applied only in `_connect_inputs` (the SDK connection).<br>**Docs contradict the code.** `features/mcp.md:465` says the identity header is sent "on every request". | Strengthens the dossier: the docs are wrong here, so authenticate by token only. `skip_preflight: true` removes the HEAD/GET probe. | none |
| HP-10 | A fresh `HERMES_HOME` root is heavyweight (~1.4 GB). A killed first run can leave an interrupted "source update" that the next run resumes inside the shared checkout. A named profile costs ~1 s and 3.4 MB, or 184 KB with `--no-skills`. | partially-confirmed | Raw `create-*.log`, file mtimes. | **Checkout rebuild.** `create-p1.log` shows "hermes: finishing an interrupted source update…" followed by front-end build steps. This supports the claim.<br>**Profile creation.** `create-p2/p3.log` show "58 bundled skills synced". `create-p4.log` shows "No bundled skills seeded (--no-skills)". The p2 and p3 logs both have mtime 23:01:12, which is weakly consistent with ~1 s each.<br>**No artifact for any size or time figure.** The scratch root was deleted. There is no `du` output and no timing output. | Qualitative claims are supported by raw logs. Every size and duration figure is unverifiable from recorded artifacts (needs hands-on on a droplet). | detail |
| X-1 | (Section 2.4, versioning) "Flip the `current` symlink atomically. New sessions see the new release." | refuted | Source @09681e7 and @46d7718a. | **Resolved-path cache.** `agent/skill_utils.get_external_skills_dirs` calls `.resolve()` on each entry, which follows the `current` symlink to `releases/<semver>`. It caches the **resolved** list in `_EXTERNAL_DIRS_CACHE`, keyed by config.yaml path + file signature. The only cache clear is a "Test hook".<br>**Index cache.** `prompt_builder._SKILLS_PROMPT_CACHE` (LRU, 32 entries) is keyed by root path strings. `conversation_loop.py` notes "The skills index cache (LRU + disk snapshot) does not watch the skills dir".<br>**What clears it.** Outside tests, the cache is cleared only by `tools/skills_sync._build_external_skill_index`. That runs at gateway **start** (`gateway/run.py::_start_gateway_configure_logging` → `sync_skills`) and in CLI update/profile/hub paths. There is no periodic invalidation. For `.no-bundled-skills` profiles, `sync_skills` returns before that call.<br>Result: a long-lived process (the multiplexed gateway) keeps the old release path until that profile's config.yaml changes or the process restarts.<br>Source-only. Not reproduced; hands-on confirmation needs a droplet. | Release by one of three means: write the versioned path (`/opt/jev-fleet/skills/releases/<semver>`) into each profile's config.yaml, which changes the cache key; restart or roll gateways after a flip; or both. Keep old release dirs on disk until every process has recycled. Canary switching has the same caveat. | design-changing |
| X-2 | (Section 2.4 config) `lazy: true`: "1,000 profiles: connect on first use, not at gateway start". | partially-confirmed | Docs plus source @46d7718a. | The `mcp-config-reference` `lazy` row says it "Needs one prior live connect to fill the cache; a missing or stale entry falls back to the normal eager connect". `tools/mcp_schema_cache._cache_path()` is `get_hermes_home()/cache/mcp_schema_cache.json`, i.e. per profile. It is written by `_write_schema_cache` during live registration. `multi-profile-gateways.md`: "Startup connects profiles one after another". | On first boot each new profile connects eagerly, one profile after another. Lazy only helps from the second boot on. Not verified whether `hermes mcp test` fills the cache. The provisioner should warm it, or the first-boot cost should be measured. | detail |
| X-3 | (Verdict 1) The multiplexer keeps a separate MCP connection per distinct credential. | confirmed | Source at 3 pins plus docs. | **Connection keys.** `tools/mcp_tool_scope.py` keys connections by `(owner_scope, name)` under a multiplexer.<br>**Sharing rule.** `_connection_identity` includes headers. At 09681e7 and main, cross-profile adoption also requires `_adopter_identity_digest` over the resolved URL, headers and identity header. At the trial pin, configs are interpolated per profile at load, so headers compare as rendered values.<br>**Docs.** `multi-profile-gateways.md:585-592` agrees. | Source/docs only; S7 did not test this, despite the dossier's "verified hands-on" sentence right after it. | none |
| X-4 | (Section 2.1) Plugins can register "27 hooks". | partially-confirmed | Docs vs source. | `features/plugins.md:330` says "27 lifecycle events". `hermes_cli/plugins.py::VALID_HOOKS` has 44 names at main and 41 at 09681e7. `post_tool_call` and `pre_llm_call` are present on both. | The docs number is stale. The hooks the dossier relies on exist. | none |
| X-5 | (Verdict 9, Section 2.1) There is no Obsidian memory provider upstream; bundled providers are byterover, holographic and retaindb. | partially-confirmed | Tree at main plus catalog files via `gh api`. | Bundled `plugins/memory/*` = {byterover, holographic, retaindb}. Confirmed. The built-in limits are confirmed too: `features/memory.md` gives MEMORY.md 2,200 characters (~800 tokens) and USER.md 1,375. The community catalog does have Obsidian-related entries:<br>- `plugin-catalog/obsidian-memory.yaml`: category desktop, a vault browser with graph view, no tools or hooks.<br>- `vault-view.yaml`: "Compatible with Obsidian vaults".<br>- `icarus.yaml`: a memory-category plugin with a `fabric_init_obsidian` tool. | Correct for a `memory.provider`. The dossier missed community Obsidian viewers and plugins that matter under Justin's Obsidian rule. All are community tier and unvetted. | detail |
| X-6 | (Section 2.4) MCP prompts carry versioned playbooks; tool descriptions change fleet-wide at once on `tools/list_changed`. | partially-confirmed | Docs @46d7718a. | `features/mcp.md:771-775`: tools are re-fetched on `notifications/tools/list_changed`, but "Prompt and resource change notifications (`prompts/list_changed`, `resources/list_changed`) are received but not yet acted on." | Tool-description changes propagate. Prompt and resource playbook changes do not propagate live. | detail |
| X-7 | (Section 2.4 config) `agent.disabled_toolsets: [browser]` removes the unmanaged browser, including `browser_vault_*` and Browser-Use `browser_exec`. | confirmed | Source @46d7718a and @09681e7. | `toolsets.py` builds `browser` from every `_HERMES_CORE_TOOLS` entry that starts with `browser_`, which includes `browser_exec` and `browser_vault_*`. `model_tools._select_tool_names` subtracts disabled toolsets last. `browser_exec` is registered under the registry toolset `browser-use`, but the static `browser` set still contains it by name. | none | none |
| X-8 | (Header, Risks) About 12,600 upstream commits between the older pin and main; the fork is 0 ahead and 43,660 behind. | confirmed | `gh api compare`. | 12,606 ahead. Fork: 0 ahead, 43,783 behind on 2026-10-10. | The behind count is time-varying. | none |
| X-9 | (Verdict 7) `--no-skills` gives a ~9.2k vs ~14.5k character system prompt. | confirmed | Raw `promptsize-p1.json` and `promptsize-p4.json`. | 14,485 vs 9,175 chars. The 5,310-char difference equals the skills-index difference (5,641 − 331). Both profiles carry 24 tools and 43,811 B of tool-schema JSON. | The tool schemas (about 44 KB) dominate the fixed budget, not the skills index. Disabling `browser` and `browser-use` saves 4,407 + 3,498 B per the raw p4 breakdown. | none |

## Unsourced numbers

These are numbers in the dossier or its `RESULTS.md` that have no recorded artifact or primary source behind them:

- **Fresh-root footprint.** 1.4 GB total, with 417 MB tools, 608 MB installs and 451 MB uv cache. The scratch root was
  deleted and no `du` output was saved.
- **Retry duration.** "the retry finished in 104 s". No timing output.
- **Profile creation time.** "1.2 s and 0.8 s" and "about 1 s". No timing output; log mtimes only show that p2 and p3
  finished in the same second.
- **Profile disk cost.** "3,480 KB / 3.4 MB, 330 files" (default) and "184 KB, 27 files" (`--no-skills`). The "58
  bundled skills" figure is in the raw logs.
- **1,000-profile projections.** "~3.4 GB and ~330k files" and "~184 MB and ~27k files". These are derived from the
  unsourced per-profile figures.
- **External-skill prompt size.** "p4 + shared external skill: 429-char skills index, 2 skills". No saved JSON exists.
- **MCP connect times.** "p1 connected 1,028 ms" and "p2 connected 578 ms". The `mcp test` output was not saved.
- **Index description length.** "Keep index descriptions under about 200 characters". This is an author heuristic.
- **Plugin size.** "a few kB each" per plugin copy. The stub plugin is about 1.8 KB, so this is plausible but unmeasured.
- **Box attachment timeout.** A long timeout in a local Hermes config. Not re-checked: I did not read a live
  config.
- **Hook count.** "27 hooks". This is the docs number; source has 44 at main.
- **Fork lag.** "43,660 behind". Correct on 2026-10-09; 43,783 on 2026-10-10.

## Missed issues

1. **The symlink-flip skill release does not reach long-lived gateways** (X-1, source-verified, design-changing).
   `get_external_skills_dirs` resolves the symlink and caches the resolved release path, keyed by config.yaml's file
   signature. The skills index is cached separately and does not watch directories. Release by writing a versioned
   path into each profile's config, or by restarting gateways. Never delete a release dir while a process may still
   hold it.
2. **Plugin-less hosts do have a no-code skill channel** (HP-5). Owner-approved prose guides of limited length become
   native `SKILL.md` files at each work start. Caveats: the index description is fixed, and the host's appended
   footer restricts outreach, which fleet posting and DM guidance must work around.
3. **Hosts may run employees with tight per-turn limits.** Run-then-job polling spends iterations, so the fleet's `job` tool should long-poll for up to
   about 80 s, inside the 90 s client timeout, rather than answering instantly.
4. **Fail-closed has conditions** (HP-1).
   - It is absent at some older pins, where an unset `${VAR}` is sent literally. That is moot today because such
     hosts write literal tokens.
   - In non-multiplexed processes, a missing profile value falls back to the process env. Never export
     `BROWSER_FLEET_TOKEN` host-wide.
   - Never give the launch/default profile of a multiplexed host a fleet token: its `.env` is in `os.environ`.
5. **Profiles are not a sandbox, and the dossier did not connect this to token secrecy.** This applies to native
   multi-profile hosts only; each trial employee is its own container. `profiles.md`: "Profiles do **not** sandbox the
   agent". On the local terminal backend all profiles share one Unix user.
   - `read_file` blocks any `.env` by basename (`agent/file_safety.get_read_block_error`).
   - The terminal tool is not a boundary, so a prompt-injected agent can plausibly read a sibling profile's
     `BROWSER_FLEET_TOKEN`. Untested.
   - Fleet hosts should use a sandboxed terminal backend or per-profile Unix users, and fleet tokens should carry
     least-privilege scopes, so that one leaked token cannot publish for another client.
6. **`lazy: true` does not avoid first-boot eager connects** (X-2). The schema cache is per profile and filled only by
   a live registration. On a 1,000-profile host, the first boot connects every profile one after another.
7. **The fleet controls `outcome_uncertain` frequency.** Write tools get `outcome_uncertain` only on session-expiry or
   transport errors. Because the fleet owns the MCP server, it should not expire idle Streamable-HTTP sessions
   aggressively, or should run stateless. The dossier treated expiry as a given, not a server-side lever.
8. **Hermes docs are wrong about the identity header.** `features/mcp.md` says it is sent "on every request", but the
   preflight sends only the configured headers (HP-9). `skip_preflight: true` exists if the HEAD/GET probe is unwanted.
9. **The raw artifacts behind several hands-on claims are thin.**
   - No saved output for S4, S5 or S6 index observations, S7 `mcp test` results, or any size or timing.
   - The only p4 `prompt-size` file predates the external-dir config.
   - `stub-mcp.log` begins with an unauthenticated `GET /mcp` at 03:03:15Z, likely the author's readiness probe, which
     `RESULTS.md` does not mention.
   - The S4–S6 conclusions survive because the source confirms them.
10. **Pin skew.** Hands-on ran at `09681e7`, which is 4,595 commits behind the targeted main and 8,011 commits after the
    older pin (`gh api compare`). I checked the relevant paths at main: interpolation, fail-closed, preflight,
    external-dir scan and replay guard. All are unchanged in behaviour except the shadow warning (HP-3).
11. **Bootstrap side effect.** A resumed first run rebuilds artifacts inside the shared Hermes checkout. Fleet hosts use baked images and never bootstrap ad-hoc roots.
12. **MCP prompt playbooks do not hot-update** (X-6). Hermes ignores `prompts/list_changed`, so versioned guidance
    that must change live belongs in tool descriptions or `job` results.
13. **Managed scope has an unconsidered upside, and a mismatch worth watching** (HP-7).
    - Upside: a root-owned `/etc/hermes/config.yaml` can pin the `mcp_servers.browser_fleet` URL immutably, so an agent
      cannot redirect its own fleet entry. Keep the token out of it.
    - Risk: the docstring and code disagree on how `${VAR}` expands. Do not rely on either behaviour.
14. **Obsidian community catalog entries were not surveyed** (X-5): `obsidian-memory` (a desktop vault viewer),
    `vault-view` and `icarus` (which has `fabric_init_obsidian`). All are community tier and unvetted.
15. **Skill Sync was never viable.** Its removal commit says it never worked against a public sync plane. The
    dossier's framing that it was "removed" understates this: nothing usable was lost.
