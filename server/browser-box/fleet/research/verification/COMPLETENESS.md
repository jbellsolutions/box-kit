# Completeness review of the browser fleet design

Role: completeness critic. Branch `feat/system1-browser-fleet`. Review date: 2026-10-10.
Status: **complete.** Small fixes are made in place (section 3). Larger gaps are listed, ranked, in section 4.

Scope: everything under `fleet/` except the raw corpus (`research/corpus/`) and raw spike data. Compared against
Justin's request as captured in [BRIEF.md](../BRIEF.md), against [DECISIONS.md](../../DECISIONS.md) (which
wins), [CONSISTENCY.md](CONSISTENCY.md) and [GEMINI-AUDIT.md](GEMINI-AUDIT.md).

Nothing was run: no Docker, no browser, no Hermes CLI, no sudo. Reads, `grep` and small offline Python scripts
(`python3 -I`) only. No commit. `DECISIONS.md`, the dossiers, the verification reports (other than this file) and
the scenarios were not edited.

**The short verdict.** The design answers all seven of Justin's questions and the 100-to-1,000 plan, and it is
consistent enough to build from once he answers the gating questions. It is a paper design: nothing is built, no
vendor was tested on a droplet, and the scenarios are walkthroughs, not runs. Eighteen cross-file inconsistencies
were fixed in place (section 3). Nine larger items remain (section 4). The biggest are the operator console (a
dependency of every human control, and not designed), the missing `moderate` effect kind, and the uneven governance
coverage across the guides.

## 1. Method and coverage

**What I read in full:** BRIEF.md, DECISIONS.md, CONSISTENCY.md, GEMINI-AUDIT.md, CHARTER.md, AGENTS.md, SOUL.md,
ANSWERS.md, hermes/README.md, the `fleet-evidence` skill.

**What I read in part (the sections that carry the contract):**

| File | Read |
|---|---|
| ARCHITECTURE.md | sections 0-2, 3.11, 4.8, 5, 8-10 and the tool cards edited below |
| MILESTONES.md | sections 0-2, 4.2-4.4, 5 (the gate and question tables) |
| docs/engines/steel.md | section 14 (governance) |
| docs/engines/browser-use.md | the detectability comparison (about line 896) |
| docs/models/reasoning.md | section 12 |
| docs/models/system1.md | section 9 |
| docs/engines/stagehand.md | the opening |
| docs/identity/identity-and-proxies.md | sections 12 and 13 |

**What I checked by heading list, `grep` or script only:** the rest of every engine, model, identity, channel,
infra and playbook guide; the other seven skills; the 14 scenario files; the 11 dossiers and 11 verification
reports. I did not re-verify any factual claim in them. The verification reports are the evidence layer, and this
review leans on them.

**Automated scans (section 6):** links, paths, banned enrichment names, timeline language, future dates, memory
wording, dossier banners, refuted claims from CONSISTENCY 3a, the scenario gap ledger against the design docs, skill
drift, the question matrix, and a heuristic for numbers without a source.

**Caveat on how I edited.** The review plan called for small, single-purpose edits with the Edit tool. For a few multi-site changes in shared
docs (ANSWERS, CHARTER, SOUL, AGENTS, MILESTONES, ARCHITECTURE) I used a short Python read-modify-write with an
`assert count == 1` on every replaced string. I checked file mtimes before and after and no other writer touched
those files in that window. A second writer on the same file would still have lost a write. If a sibling agent
reports a lost edit in those six files, compare against the list in section 3.

## 2. Goal checklist

Justin's request is seven numbered questions plus a plan for 100 to 1,000 profiles
([BRIEF.md](../BRIEF.md) "What the user (Justin) wants"). The harness also asked for properties, skills,
governance and soul. "Each property fully charted" has two readings, so I report both.

| # | Goal | Verdict | Where it is answered | What is thin |
|---|---|---|---|---|
| 1 | Docs captured and understood: Stagehand, Steel, Browser-Use, Browserbase | **Done** | About 1,450 corpus files under `research/corpus/`: Stagehand 414, Steel 458, Browserbase 255, Browser-Use 323 (file counts per vendor folder, each including its MANIFEST.md, INDEX.md and SHA256SUMS), and the four guides in `docs/engines/`; ANSWERS Q1 | Understanding is in the guides. No vendor was run on a droplet. |
| 2 | Structure to fill the gaps the open-source projects leave | **Done (design)** | ARCHITECTURE.md; `docs/infra/steel-profile.md`; DECISIONS D1-D18 | Unbuilt. 17 tools, node agent, ledger, viewer broker, shim are all targets. |
| 3 | System 1 models and the 90% goal | **Done, with a hypothesis flagged** | `docs/models/system1.md`; ANSWERS Q3; D7 | The 90% figure is unmeasured (O-15). The plan to measure it is in system1.md section 6. |
| 3b | Reasoning model | **Done** | `docs/models/reasoning.md` (GLM 5.3 Flash at `low`, shim, fallbacks); ANSWERS Q3 | Measured on small samples, arm64 and public pages only. |
| 4 | Everything up in the air answered | **Done as far as the evidence allows** | ANSWERS section 1 and the 14 questions at the end of DECISIONS (Q-01..Q-14); 17 open decisions in CONSISTENCY (O-01..O-17) | 14 questions wait on Justin. The documents proceed on the recommended default and mark each spot **pending Q-nn**. |
| 5 | Anti-detect browsers driven from a Hermes profile | **Done** | ANSWERS Q5; `docs/identity/identity-and-proxies.md` (the anti-detect position) | No anti-detect vendor was tested hands-on. The answer rests on vendor docs and one spike on detection pages. |
| 6 | Proxies | **Done** | ANSWERS Q6; identity doc sections 4-5; D9, D10 | No proxy vendor was bought or measured. Prices are list prices. |
| 7 | Skip anti-detect if proxies and stealth are enough | **Done** | ANSWERS Q7; D3 ("continuity, not evasion") | Rests on the same untested base as 5. |
| 8 | Plan for 100 to 1,000 profiles | **Done, upper bound** | ARCHITECTURE section 7; D12; MILESTONES M5-M7; ANSWERS 3.5 | The cost table has no single total. The share `f` of accounts that need a browser is unestimated, by design (S09-8). |
| 9 | Skills | **Done as drafts** | `hermes/skills/` (8 skills) and `hermes/README.md` (packaging, provisioner, vault) | Tool names the architecture adds are marked **[proposed]** in the skills until the tool card is final (section 4, item 3). |
| 10 | Governance | **Done for the fleet; uneven per guide** | CHARTER.md (invariants, red lines, duplicate content, names not final); steel, stagehand, browser-use, browserbase, identity, channels and lead-gen each have a governance section | `system1.md`, `reasoning.md` and `steel-profile.md` have none (section 4, item 4). |
| 11 | Soul | **Done** | SOUL.md, long and short forms; the short block is about 1.85K characters | A soul line sits in only the four engine guides. That is acceptable: the soul is per profile, not per guide. |
| 12 | Scenarios run | **Done as 14 paper walkthroughs, not executed** | `research/scenarios/S01.md` to `S14.md`; gap ledger of 204 ids folded into the drafts | README says so. Executed scenarios wait for M1 and Q-12 (a droplet and Justin's yes). |
| 13 | Information verified | **Done** | 11 dossiers, 11 verification reports, CONSISTENCY, GEMINI-AUDIT (124 claims). All 11 dossiers carry a banner pointing at their verifier | Hands-on evidence is thin (arm64, public pages, small n). |

**Reading A of "each property fully charted" (per vendor and per component).** Each of Stagehand, Browser-Use, Steel
and Browserbase has a guide with a capability chart, a gap chart, a governance section and (for those four) a soul
line. Steel also has the `steel-profile` build spec. System 1 and the reasoning model each have a guide.
Identity, proxies and anti-detect share one guide. **Complete,** except for the governance gap in item 4.

**Reading B of "each property" (per social platform: Facebook, Instagram, TikTok, X, LinkedIn).**
`docs/channels/social-channels.md` charts, for each platform, what the official API allows, windows and limits,
tokens, browser-only gaps and red lines, and D2's allowed-uses table binds them. **Complete.** LinkedIn is
API-only for posts and comments, and a Charter red line for any browser action.

## 3. Fixed in place

These are the small inconsistencies found and corrected. Every edit is to a fleet doc other than DECISIONS.md. Each
makes a sibling doc agree with DECISIONS.md or with a verification report.

| # | File | What changed | Why |
|---|---|---|---|
| 1 | README.md | The ladder paragraph now says `account` identities default to the minimal CDP executor (D18, gate G1.4) and that this narrows the brief's "Stagehand is the main browser agent" | README still described Stagehand as the L3 engine for all identities |
| 2 | README.md | "D1-D17" became "D1-D18"; "seven skills" became "eight skills"; a COMPLETENESS.md entry added to the verification tree | D18 and `fleet-inbox` were added after the README was drafted |
| 3 | ANSWERS.md | Section 0 item 2 and the "surprise" bullet; Q2 "D1 to D18", the roles paragraph and two table rows; Q3 L3 sentence; Q5 intro; section 4 item 8 now "Resolved by D18" | ANSWERS still carried the pre-D18 position that D18 "would" amend D6 |
| 4 | ANSWERS.md | Section 3.1 browser-use bullet: the "personal profiles" wording is withdrawn. No browser identity for a Facebook personal profile, an Instagram personal account, LinkedIn or X (`draft_for_human`) | D2's allowed-uses table rows 3, 4, 6, 7 withdraw it |
| 5 | ANSWERS.md | Section 3.2: the amendment is adopted as D18; `account` identities default to the minimal CDP executor and M1 gate G1.4 can overturn that | Same as 3 |
| 6 | ARCHITECTURE.md | `docs/engines/system1.md` became `docs/models/system1.md` (all occurrences) | The file is in `docs/models/`; the old path does not resolve |
| 7 | ARCHITECTURE.md | H2 now lists eight skills, adds `fleet-inbox`, and notes the `fleet-stagehand-operator` to `fleet-steps` rename | Matched to `hermes/skills/` and hermes/README section 1 |
| 8 | ARCHITECTURE.md | 5.5 error table: `needs_reauth` (the caller never receives a viewer URL; tell the owner; do not call `reauth` again while a ticket is out); `identity_held` (only `uncertain_effect` waits; other holds are cleared by the owner or operator); new `duplicate_content` row (proposed) | Contradicted 4.8 and D14 |
| 9 | ARCHITECTURE.md | 10.1: Q-05 (treated as required, no X publishing for client brands), Q-06 (nothing applied for, no paid call until yes), Q-07 (both required), Q-11 (not connected until he answers) | Defaults now match CHARTER and MILESTONES |
| 10 | ARCHITECTURE.md | Section 9: rows 13-23 had been displaced from the 9.1 table; moved back in order (22 before 23) | Table was split and read as two tables |
| 11 | ARCHITECTURE.md | Tool cards: `fleet_status` takes optional `skill_version`; `job` `include` gains `obsidian_notes` and `artifacts`, adds `started_by`, batch-note rendering, and the "never inline stranger text; tag untrusted" rule; `extract` gets a goal verdict, per-field evidence and `unsupported_on_identity`; `feedback` kind `red_line_request` raises a notifier event. All marked **[extension]** | hermes/README revision-1 gap 1 and revision-2 rows 13-17 |
| 12 | ARCHITECTURE.md | H1 provisioner tool policy (G11-8); 4.8 step 7 next-day `verify` system job; H5 vault folders now `{Daily,Runs,Identities,Leads}` | hermes/README revision-1 gap 5 and revision-2 rows 12 and 18 |
| 13 | docs/engines/steel.md | Governance 14.2 "May" row: agents get a ticket id, never a viewer URL | The row contradicted D14, D17 and CHARTER |
| 14 | SOUL.md | Long form: "If an ask is vague, I ask which account and what limits before I act"; "...offer the allowed way, and tell the owner". Short form: "Vague ask: ask which account and what limits." and "I bring the allowed route and tell the owner." The short block is about 1.85K characters | Scenario gaps S11/G11 (vague or risky asks) had reached the architecture but not the soul |
| 15 | AGENTS.md | Layout: the Stagehand worker is "Python by default, TypeScript as the fallback; ARCH N4"; the sibling-docs line updated; added that API-first is the record's default and is pending Q-01, and that DM text never goes to a model until Q-07 is answered | Stale against ARCHITECTURE and DECISIONS |
| 16 | CHARTER.md | Invariant 5 now says what code enforces about page text (the sent text hashes to the approved text) and what only the human approver catches (D13, S13-18). The red-lines intro says red lines are only as strong as the profile's other tools, with the provisioner tool policy as the control (G11-8) | Invariant 5 overstated what code can check |
| 17 | MILESTONES.md | M0 reads "D1-D18"; N-12 note says the Stagehand worker language now agrees and the executor's language is still open; new M2 Built row "Operator console and roles" (scope not yet designed); new gates G2.12 (operator functions and roles) and G2.13 (profile isolation and tool policy) | The console had no row; G2.13 closes hermes/README revision-2 row 20 |
| 18 | hermes/README.md | Added a "Status after the completeness review" block in section 7 listing which edits landed and which remain open; the note about ARCHITECTURE H2 no longer says H2 is stale | Keeps the sibling drafts honest about what is closed |
| 19 | ANSWERS.md | The two cost tables in section 3.5 now carry the `estimate` label (model output at list prices, not quotes) | The lead-in cited the cost model but did not label the numbers |
| 20 | docs/models/system1.md, docs/models/reasoning.md | The "open correction" line about `docs/engines/system1.md` now says only DECISIONS D5 still cites the old path; ARCHITECTURE §2.4 and §4.3 were corrected in item 6 | Item 6 made the old line (which also named ARC) false |

## 4. Larger issues, ranked

Ranked by what breaks if left alone. None needs a timeline; each says what closes it.

**1. The operator console and roles are a dependency of every human control, and they are not designed.**
ARCHITECTURE C1 lists the console as a door, 5.3 puts `approve` in the console and not in Hermes tokens (`approve`
**[extension]**), and 6.5 and D14 require an authenticated operator before a viewer ticket is exchanged. But there
is no spec for roles (owner, operator, approver, viewer), sign-in and second factor, the approval queue, hold
clearing, `identity create`, takeover closure, or the audit view. M2 now has a placeholder row and gates G2.12 and
G2.13 (section 3, item 17), but the scope is "not yet designed". AQ-1 (operator authentication) and AQ-3 (where
owner alerts go) already block M2. **Closes with:** a design section or `docs/infra/operator-console.md`, the
answers to AQ-1, AQ-3, AQ-5 and AQ-14, and the M2 row filled in from it.

**2. `moderate` is not an effect kind.** D2's allowed-uses table row 1 says an API acts for "Publish, comment, reply,
moderate, analytics". The `fleet-social` skill says it can "moderate". But D17's `publish` kinds are `post`,
`comment`, `reply`, `dm`, `private_reply` ([DECISIONS.md](../../DECISIONS.md) D17), and neither ARCHITECTURE 5.3 nor
the ledger has a moderation kind. ARCHITECTURE mentions "comment moderation" only in the default channel policy
(about line 2555). CHARTER.md says plainly that the `moderate` kind is only proposed (hide, unhide, delete; scenario
gap S03-11). Hide and delete change a client's page and are hard to undo, so they need an intent
record, a read-back and a red-line decision on `delete`. **Closes with:** a DECISIONS change (item 5 below), a ledger
kind with a read-back rule (fetch the comment and check visibility), and a line in the `fleet-social` skill.

**3. The skills use tool names that the architecture only proposes.** Six of the eight skills (`fleet-router`,
`fleet-identity`, `fleet-steps`, `fleet-browser-use`, `fleet-social`, `fleet-evidence`) mark ARCHITECTURE extensions
(`approve`, `skill_version`, `obsidian_notes`, `duplicate_content`, `red_line_request`) as **[proposed]**.
`fleet-inbox` and `fleet-leadgen` carry no such mark. This is honest, and a drift scan is in the plan (D1: `fleet-*` names, drift
scan on every host). But until the tool card is frozen, a skill can promise an answer the service never returns.
**Closes with:** freezing the tool card in M2, then removing the **[proposed]** marks in one pass, checked by the drift
scan.

**4. Governance and soul coverage is uneven across the guides.** Seven of ten guides have a governance section.
`docs/models/system1.md`, `docs/models/reasoning.md` and `docs/infra/steel-profile.md` do not. The rules are in the
right places for enforcement (CHARTER; system1.md section 5 "Why a decider is never a safety gate"; steel-profile
section 10 on the Guard), but a reader of those three guides does not see what an agent may and may not do with that
component. Only the four engine guides carry a soul line. **Closes with:** a short "Governance" section in each of
the three, pointing to CHARTER and listing the component's own limits (which model tier may see page text, who may
change a persona record). Low effort; no new decision.

**5. DECISIONS.md needs six edits that only its owner can make (section 5).** They are not gaps in the design. The
design docs already behave as if they were made (ARCHITECTURE 9.1 rows 2, 11, 16, 20). **Closes with:** the
DECISIONS owner applying section 5.

**6. Nothing was run, and the measurements are one architecture.** All hands-on numbers come from arm64 Docker or a
local Chrome, on public test pages, with small n. DigitalOcean droplets are amd64. The scenarios are walkthroughs.
This is declared everywhere (README, DECISIONS preface, every guide), so it is not an inconsistency, but it is the
largest unknown. **Closes with:** M1 on a droplet after Justin's yes (Q-12).

**7. A default exists in hermes/README that DECISIONS does not hold.** "Profiles of different clients do not share a
host" (hermes/README section 2.2) is a Hermes-side rule, introduced in the packaging draft, matching D3's
one-client-per-node rule for browsers (Q-13). It raises host count at 1,000. ARCHITECTURE 7 says to shard profiles across Hermes hosts (about line 2454) but does
not size the Hermes hosts by client count.
**Closes with:** either a line in DECISIONS (D15 or D12) and a Hermes-host term in 7, or a measured pass of G2.2 that
removes the need.

**8. Open items the hermes/README revision lists, not closed by any file in `fleet/`.** Gap 2 (D1 should say "and",
not "and/or"), gap 3 (D17 `approvals` as one write tool), gap 7 (what the caller does after an approval on the API
channel), gap 8 (the Messenger 30-second bot-response window against a Hermes model turn; AQ-8), gap 9 (the trial's
appended line), and the D14 `verify`-job sentence. First two and the last are DECISIONS edits (section 5). **Closes
with:** the DECISIONS edits, the Q-01 answer for gap 7, and the M1 trial for gaps 8 and 9.

**9. A heuristic scan found 25 number-bearing paragraphs without a citation token.** I read 13 of them: the ten in
ANSWERS and DECISIONS, and three in the guides. All were table rows or headings whose source sits in a lead-in
line, a "Source" column or an "all estimates" label (for example the Browserbase pricing table cites
`official-docs` `https://docs.browserbase.com/account/billing/plans.md` one heading above; the Browser-Use run table cites the
spike results above it; the D12 cost block says "all estimates, scale-infra Q4"). Two ANSWERS cost tables cited
their source but did not say `estimate`; I added the label (section 3, item 19). None looked wrong. I did not read
the other twelve (MILESTONES 3, steel 2, browserbase 1, browser-use 1, reasoning 1, system1 1, identity 1,
social-channels 1, ARCHITECTURE 1).

**Smaller items noticed, not fixed.**
- LinkedIn API version 202510 sunsets 2026-10-15, five days after this review (`research/verification/social-platforms.md`
  row on the Development tier; [social-channels.md](../../docs/channels/social-channels.md)). The docs say to send "the
  current header" and name no replacement version. Nothing is built, so only a connector build is affected.
- The same version is called "Community Management API version 202510" in ARCHITECTURE and DECISIONS and "Marketing
  API version 202510" in social-channels.md. The verifier's wording is "Marketing Version 202510". Fixing one side
  would split the text, so I left both and note it here.
- Scenario gap S14-13 (the Browser-Use detectability tilt) is already handled in `docs/engines/browser-use.md` (the
  comparison table says no candidate was measured clicking or typing). The ledger line is stale, not the guide.

## 5. Issues in DECISIONS.md (listed, not edited)

I did not touch DECISIONS.md. These are the places where it disagrees with a verification report, with CONSISTENCY,
or with itself. The design docs already follow the "should be" column.

| # | Where | Now says | Should say | Why |
|---|---|---|---|---|
| 1 | D5, about line 321 | "`docs/engines/system1.md` §3.6 rule 5" | `docs/models/system1.md` §3.6 rule 5 | The file is under `docs/models/`. `system1.md` and `reasoning.md` both list this as an open correction |
| 2 | D1, about line 58 | "writes ... into each profile config and/or rolls gateways" | "and rolls gateways" | A release path in `config.yaml` is not read until the gateway restarts (hermes/README revision-1 gap 2) |
| 3 | D17, `approvals` row, and its last bullet | `approvals` is one write tool that lists and answers approvals; a later bullet says "No tool lets an agent ... approve" | `approvals` (read) plus `approve` (write, scope `approve`, never held with `publish` or `dm` on one account, not listed for Hermes profile tokens) | Internal contradiction; a token that answers its own approvals is no gate (ARCHITECTURE 9.1 row 2, HP-8) |
| 4 | D17, `publish` kinds | `post`, `comment`, `reply`, `dm`, `private_reply` | Add `moderate` (hide, unhide, delete), or say moderation is not offered | D2 row 1 offers moderation by API (this file, section 4 item 2) |
| 5 | D17, error list | No `duplicate_content` code | Add `duplicate_content` (non-retryable; no manifest waives it; the text or media matches this account's history, another account of the same client, or another client's) | "Identical posts across client accounts" is a "never built" item in D2; code needs a name for the refusal (ARCHITECTURE 5.5, proposed; CHARTER "Duplicate content") |
| 6 | D14 | No mention of a post-effect `verify` job | One sentence: after an effect with a browser read-back, a next-day system job re-reads it | ARCHITECTURE 4.8 step 7; hermes/README gap 12 |
| 7 | Question list (Q-01..Q-14) | Q-13 is cross-client unlinkability; Q-14 is consent-based lead channels. No question about a workstation housekeeping item | Add a note on a workstation housekeeping item | CONSISTENCY's own Q-13 (a workstation housekeeping item) collides in number with DECISIONS Q-13. A reader moving between the two files gets the wrong question |

## 6. Scan results

Run on the final state of the files, after the edits in section 3.

| Scan | Result |
|---|---|
| Relative markdown links | 632 links in 85 files (design docs, hermes, scenarios, verification, dossiers, spikes): **0 broken** |
| Paths in backticks that do not resolve | Three, all benign: `research/corpus/steel/oss/steel-browser` is a short form of `steel-browser@1131a02`; `captures/01` is a range reference; `docs/openapi.json` is the box's file or planned |
| Paid enrichment services (Clay, Apollo, Hunter, ZoomInfo, Ocean.io) | 12 hits in design and scenario docs. **All 12 are prohibitions** (AGENTS, CHARTER, MILESTONES x2, README, social-channels, lead-gen x2, `fleet-leadgen`, `fleet-router`, S04, S11). None proposes one |
| Timelines (day, week, month estimates, "by Friday", "this week", ETA) | 101 regex hits across design docs and scenarios. All are platform windows (24 h, 7-day tag), retention (30 days), token lifetimes, vendor release cadence or price arithmetic. **No delivery estimate.** MILESTONES uses dependencies and gates |
| Future dates | One: 2026-10-15, the LinkedIn API version sunset, an external vendor date |
| Memory wording | Obsidian is the memory substrate wherever memory is mentioned (ARCHITECTURE H5 and 15 mentions, hermes/README 19, CHARTER 4). No "Supabase as memory", "mem0 only" or generic `vault/` proposal |
| Dossier banners | 11 of 11 dossiers carry a banner pointing at their verification report |
| Refuted claims (CONSISTENCY 3a) | Each refuted claim was grepped across the design docs. The design docs carry the corrected version in every case, or do not repeat the claim |
| Scenario gap ledger | 204 ids across S01-S14 and G10, G11, G12. 199 appear by id in a design doc. Five do not: G10-6 and S03-11 (handled in CHARTER without the id), S14-11 (handled in the Stagehand guide), S14-13 (handled in the Browser-Use guide), S14-17 (the wrong `system1.md` path, fixed in ARCHITECTURE in item 6 of section 3; DECISIONS D5 remains, section 5 row 1) |
| Skill drift | 8 skills in `hermes/skills/`; README, ARCHITECTURE H2 and hermes/README all say eight and use the same names. `fleet-stagehand` is deleted and replaced by `fleet-steps`; no live doc still points at the old name as current |
| Stale D-count and path wording | None left: no "D1-D17", "seven skills", `fleet-stagehand-operator` (other than as the old name, explained) or `docs/engines/system1.md` outside DECISIONS D5 and the two guides that list it as a correction |
| Question matrix | All of Q-01..Q-14 appear in ARCHITECTURE, MILESTONES, CHARTER and ANSWERS. The defaults for Q-05, Q-06, Q-07 and Q-11 in ARCHITECTURE 10.1 were out of step and now agree with CHARTER and MILESTONES (section 3, item 9). I did not compare the defaults line by line for the other ten |
| Stale verifier rows | GEMINI-AUDIT rows 7.06 and 11.01 disagree with a later verifier. Left unedited, because verifier rows are evidence |
| Number without a source (heuristic) | 25 paragraphs flagged; 13 read, all sourced by a lead-in, one label added (section 4, item 9) |
| Process breaches in research | CONSISTENCY item 12 records spikes that ran a browser on the maintainer's workstation. This review did not repeat or touch them |

## 7. Limits of this review

- **Paper review.** I compared documents with documents. I did not run anything and I did not re-check any vendor
  fact against its source. The verification reports did that.
- **Partial reads.** The sections named in section 1 were read. The remaining guide sections were scanned by
  heading, `grep` and script. A contradiction that uses none of the strings I searched for could remain in a long
  guide (each is 900 to 1,500 lines).
- **Heuristics.** The timeline, citation and enrichment scans are regex based. They find strings, not intent.
- **Six shared docs were edited with a Python read-modify-write** (section 1). I guarded each replacement, but the
  tool does not lock against a second writer.
- **DECISIONS wins.** Where a fix touches a decision, I made the sibling doc agree with the record and listed the
  gap in section 5. I did not decide for Justin.
- **Open questions for Justin** are the 14 in DECISIONS. The ones that gate the most work are Q-01 (API-first or
  browser-first), Q-06 (developer-app applications), Q-07 (what page content may go to a model), Q-09 (the public
  export of the box repo, which would publish `fleet/`) and Q-12 (a droplet and his yes for hands-on runs).
