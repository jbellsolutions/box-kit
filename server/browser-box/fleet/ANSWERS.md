# Answers to Justin's questions

Status: designed, not built. Nothing here runs. No hands-on work has been done on a droplet. Every
hands-on measurement cited below was taken on arm64 Docker on a Mac, or on local Chrome on
that Mac. DigitalOcean droplets are amd64, so each number is to be re-measured there (M1) before it is
relied on.

How to read this file. Each answer gives the short answer first, then why, then the evidence. Evidence
links point at verification reports (`research/verification/`), which win over the dossiers
(`research/dossiers/`) wherever the two disagree. Row ids such as `STE-1` or `SP-3` are that report's own
ids. The decision record is [DECISIONS.md](DECISIONS.md); items such as `D4` or `Q-07` are its ids.
Tags: `hands-on` (somebody ran it), `source-code`, `official-docs`, `vendor-claim`, `third-party`,
`estimate`, `to measure`, `unverified`. Where an answer waits on one of your decisions it says
**pending Q-xx**. Milestone labels (M1, M3, M4 and so on) are sequenced in [MILESTONES.md](MILESTONES.md);
this file uses only the labels, plus what DECISIONS attaches to them, and names one gate (G1.4, the
executor measurement inside M1). The structure the fleet is
designed around is in [ARCHITECTURE.md](ARCHITECTURE.md) and [CHARTER.md](CHARTER.md), both drafts.

## 0. The short version

1. **Docs (Q1).** Yes. About 1,450 files from the four vendors, covering every page each docs index
   listed. But the docs mostly describe the paid cloud products. How the self-hosted pieces really behave
   came from source code and small tests, and several docs claims turned out to be wrong.
2. **Gaps (Q2).** The open-source projects give us engines (Stagehand for scoped steps, Browser-Use for
   open-ended goals) and a browser (Steel). They do not give us identities, durable logins, a rule that
   two workers never share an identity, honest health checks, a human-login path, a replay cache, safe
   handling of posts and DMs, scheduling or cost control. [DECISIONS.md](DECISIONS.md) says what we build
   for each. None of it is built. One change to your brief: Stagehand is the main engine for open-web
   `research` identities, but on a client's logged-in account the default executor is the fleet's own
   minimal CDP executor, unless the M1 measurement shows another is better (D18, section 3.2).
3. **Models (Q3).** Plan: Jev for text decisions, Perplexity Decider for screenshots, Clef after an
   image test, OpenAI Decisions optional, all behind one `/decide` service. GLM 5.3 Flash at low
   reasoning effort is the reasoning model, behind a validation shim. The 90% goal is a hypothesis.
   Nothing measured supports it yet.
4. **Up in the air (Q4).** 19 questions only you can answer (section 1), 17 open engineering items, and
   about 30 behaviours that cannot be checked without a droplet.
5. **Anti-detect from a Hermes profile (Q5).** The profile never touches a browser; the fleet service's
   engines do. Browser-Use can drive any Chromium-based anti-detect browser that exposes a CDP address.
   Stagehand v4 can only if that browser is Chromium 149 or newer and three more conditions hold. No
   vendor product has been tested.
6. **Proxies (Q6).** Yes. One dedicated static ISP IP per identity, never rotating, bound through a
   node-local forwarder that stops the browser if the exit IP changes.
7. **Skip anti-detect (Q7).** Yes by default, with a correction. Steel's built-in stealth must be turned
   off: it invents a new, self-contradicting fingerprint on every launch. We pin values instead. The
   remaining weakness is that identities on one node look alike, so different clients do not share a
   node until that is fixed or you say it does not matter (**pending Q-13**).

The four things most likely to surprise you (section 3):

- Most client social work should go through official APIs, not a browser. X, Meta, LinkedIn and TikTok
  all restrict scripted use of the logged-in site.
- Stagehand v4 has no local action cache. The "cached, $0 replays" idea only works on Browserbase's
  servers, and only sometimes. And its in-browser extension trips one public automation check, so a
  *logged-in* account defaults to the fleet's own minimal executor instead of Stagehand, and M1 can change
  that per site class (D18, section 3.2).
- Open-source Steel can hand you a logged-out browser behind an HTTP 200, and can lose a login if you
  close it within 30 seconds of the last cookie change.
- The Gemini document: of 124 claims, 26 were flatly wrong, 48 were partly right and 17 could not be
  checked. Only 33 held up.

## 1. Decisions only you can make

These are the 19 `[Justin]` questions at the end of [DECISIONS.md](DECISIONS.md). Q-15 to Q-19 were added
after the completeness review. I use DECISIONS numbering. The consistency review
([CONSISTENCY.md](research/verification/CONSISTENCY.md) section 5) numbers some questions differently:
its Q-13 is a workstation housekeeping question and its Q-14 is a lead-gen and client-risk question, while
DECISIONS Q-13 is cross-client unlinkability. Q-12 means the same thing in both, and DECISIONS Q-19 is the consistency review's Q-13.

"Record default" is what [DECISIONS.md](DECISIONS.md) recommends. Thirteen questions have no recommended
default in the record. For those I give a **holding position**. That is my proposal, not the record's.
It is the safe thing to do until you answer. Nothing below is scheduled; each row says what it blocks.
Rows are ordered by how much they unblock, not by number.

| ID | Question | Record default, or my holding position | Blocks |
|---|---|---|---|
| Q-12 | Approve a small, capped, throwaway DigitalOcean droplet for hands-on work, and set a spend ceiling? | No record default. **Holding position (mine):** no droplet, and no Docker container or network changes on your Mac (BRIEF rule). Every droplet-dependent claim stays `unverified`. | M1 (droplet re-measurement). Every measured number. |
| Q-01 | API-first or browser-first for client social? Which clients accept the terms risk in writing? | Record default: API-first. Browser only for human login, open-web lead gen, a narrow no-API set (each action human-approved, low volume, client's written risk acceptance), and QA of public pages. | D2, M4, and how much logged-in executor and L3 code gets built if Stagehand's extension is ruled out on accounts (section 3.2) |
| Q-15 | Confirm D18: on a client's logged-in account, the default executor is the fleet's own minimal CDP executor, not Stagehand; Stagehand v4 stays for open-web `research` identities. Who builds the executor, and in which language? | Record default (D18): yes, unless gate G1.4 in M1 shows another executor is better for a site class. This changes your brief, so it needs your yes. | D6, D18, M1, M3 |
| Q-06 | Apply for Meta App Review and Business Verification, the TikTok Accounts API form, LinkedIn Community Management API and an X pay-per-use app? Monthly caps for X fees, models, proxies, droplets? | No record default. **Holding position (mine):** treat every cap as $0 until you name a number, and do not prepay X credits. The approvals are the longest dependency, so this one is worth answering early. | D2, M4 |
| Q-07 | Data handling: require zero-data-retention (ZDR) model routing, per-client consent, or both? | No record default. **Holding position (mine):** assume both are required. It costs a re-benchmark of the model providers, not a redesign. The charter's stricter default also applies until you answer: DM content is never sent to a model provider ([CHARTER.md](CHARTER.md) invariant 8). | D8, M3 |
| Q-13 | Is cross-client unlinkability required? | Record default (D3): identities of different clients do not share a node until per-identity hardware values exist. A node holds at most about 7 identities, so small clients leave nodes part empty and the bill rises (D3, D12). | D3, D12 |
| Q-02 | Anti-detect: continuity only with measured upgrades, or buy a product now? | Record default: continuity only. A measured per-identity upgrade after M1 if a site fails. | D9 |
| Q-03 | May the fleet depend on a proprietary patched kernel (CloakBrowser)? It sends licence and session-count telemetry, its latest build is paid, and it may need an OEM licence if client staff use our live viewer. | No record default. **Holding position (mine):** no. At most one measured comparison arm in M1. | D9 |
| Q-04 | Spoofing stance: continuity only, or allow seed-pinned spoofing? An earlier private SDR harness says it does no spoofing. | Record default: continuity only. | D9 |
| Q-05 | Will client brand accounts carry X's "Automated" label if X requires it for API-driven accounts? | No record default; the rule text is plain but whether human-approved scheduled brand posting counts is unresolved. **Holding position (mine):** do not publish to X for client brand accounts until you decide. Everything else proceeds. | D2 |
| Q-14 | Add consent-based lead channels (Meta Lead Ads, opt-in DM capture, LinkedIn Lead Gen Forms, TikTok instant forms) as first-class? | Record default: yes. | D2 |
| Q-08 | Run Steel's Chromium as non-root with the sandbox on, or accept the risk in writing? It runs as root with no sandbox and site isolation off. | No record default. **Holding position (mine):** no real client session runs on a root, no-sandbox browser. Non-root with the sandbox is the target and M1 measures how hard that is. | D4, M1 |
| Q-11 | Jev trial: may the owner add the fleet through the integrations route plus owner-approved guides? Who holds the owner role? | No record default. **Holding position (mine):** change nothing in the trial. Write the guides to fit its 6,000-character limit and its appended "no external outreach" line, but do not connect anything. | D1 |
| Q-09 | Exclude `fleet/` from box-kit's public export, or move the fleet to its own private repo? | No record default; the record says this must be closed before any merge to `main`. **Holding position (mine):** do not merge this branch, and do not run the box-kit export on any ref that contains `fleet/`. | D16 |
| Q-10 | A separate exposure question about a public companion repo is tracked privately. | No record default. **Holding position (mine):** nothing in this work touches that repo. This exposure exists today and does not depend on the fleet. | D16 |
| Q-16 | Add a `moderate` publish kind (hide, unhide, delete) with an intent row and a read-back? Is delete a red line? | No record default. **Holding position (mine):** no `moderate` kind; moderation stays with a person, and delete is treated as a red line. | D2, D13, D17 |
| Q-17 | A near-duplicate post across client accounts: refuse it outright (`duplicate_content`) or hold it for approval? | No record default. **Holding position (mine):** refuse, as ARCHITECTURE and CHARTER already propose. | D2, D17 |
| Q-18 | Hermes side: may profiles of different clients share a gateway host? | No record default; `hermes/README.md` assumes they do not, which raises host count at 1,000. **Holding position (mine):** they do not share until you say otherwise. | D1, D3, D12 |
| Q-19 (consistency Q-13, section 7) | A housekeeping question about the maintainer's local Hermes install (kept out of the public copy). | No record default. **Holding position (mine):** nobody touches the local Hermes install, and no Hermes CLI runs on the workstation. | Nothing in the design. |

If you only have time for a few: **Q-12** unlocks every unmeasured number; **Q-01** decides whether most
identities need a browser at all (the largest swing in cost, section 3.5, and in how much logged-in
browser code we must build, section 3.2); **Q-06** starts the approvals
that take longest ([social-platforms dossier](research/dossiers/social-platforms.md) verdict 5); and
**Q-09** and **Q-10** are exposure that exists today whether or not the fleet is ever built.

Evidence: [DECISIONS.md](DECISIONS.md) "Questions only Justin can answer";
[CONSISTENCY.md](research/verification/CONSISTENCY.md) sections 4, 5 and 7; export leak:
[EA-11](research/verification/existing-assets.md); public repos: [V-09](research/verification/system1-models.md),
[V-5](research/verification/existing-assets.md); root and no sandbox:
[missed issue 3](research/verification/steel.md); CloakBrowser licence: [V-9](research/verification/antidetect-proxies.md);
trial route: [HP-5](research/verification/hermes-packaging.md); X label: [V-8](research/verification/social-platforms.md).

## 2. Your seven questions

### Q1. Did we get all the docs, and do we understand them?

**Short answer.** We captured the docs. We understand what they say and the parts we tested. We do not
yet fully understand how the self-hosted pieces behave on real social sites, and the docs themselves
are wrong or silent in several places that matter.

**What was captured** (fetched 2026-10-09; each vendor folder has a `MANIFEST.md` with method, pins and
hashes, an `INDEX.md` topic map, and a `SHA256SUMS` file; the raw pages and `SHA256SUMS` are not in the published copy):

| Vendor | Files | Doc pages fetched / listed | Pinned source |
|---|---:|---|---|
| Stagehand | 414 | 186 / 186 (v2 43, v3 91, v4 52) plus docs git source, protocol schema, Python SDK, repo docs | `stagehand` @1fc8849; PyPI and npm 4.2.0 |
| Steel | 458 | 140 / 140, plus changelog, cookbook, SDKs, MCP server, `hermes-steel` | `steel-browser` @1131a02 |
| Browserbase | 255 | 234 / 234, plus the OpenAPI file and Node and Python SDK docs | `sdk-node` @adef824, `sdk-python` @b3d67ac |
| Browser-Use | 323 | 227 / 227, three OpenAPI specs, repo docs, vendor pricing and product pages | `browser-use` @c75e847 (0.13.11) |

That is about 1,450 files in the original capture. The published copy keeps only each vendor's `MANIFEST.md` and `INDEX.md` under `research/corpus/<vendor>/`:
[stagehand](research/corpus/stagehand/MANIFEST.md), [steel](research/corpus/steel/MANIFEST.md),
[browserbase](research/corpus/browserbase/MANIFEST.md) and
[browser-use](research/corpus/browser-use/MANIFEST.md). Every page began with vendor instructions aimed
at AI agents. We stored them as data and followed none of them.

**Why "captured" is not "understood".** Five honest gaps:

1. **The docs describe the paid cloud products.** Steel's docs describe Steel Cloud, not the
   self-hosted `steel-browser` we would run. Four of Steel's self-hosting pages are empty stubs
   (`clustering`, `extensions`, `profiles`, `webrtc`). There is no Steel stealth or fingerprint page.
   Six places where Steel's docs and source disagree are listed in the
   [Steel INDEX](research/corpus/steel/INDEX.md) and its
   [MANIFEST](research/corpus/steel/MANIFEST.md) ("Honest limits").
2. **No Stagehand v4 guide exists for Steel or any self-hosted remote browser.** Steel's own Stagehand
   docs and cookbook cover v3 only ([SH-10](research/verification/stagehand.md)).
3. **Browserbase has no page on stealth, fingerprint persistence or a sticky IP.** Its own sources
   disagree on which plan includes `keepAlive` ([V-3](research/verification/browserbase.md)), and its
   docs and its marketing page disagree on plan details
   ([MANIFEST](research/corpus/browserbase/MANIFEST.md)).
4. **Browser-Use Cloud is closed source.** Browser-Use's replay functions exist in source but not in the
   captured docs, and its docs and pricing page disagree on the default model and the first
   concurrency tier ([MANIFEST](research/corpus/browser-use/MANIFEST.md)).
5. **No Steel Cloud, Browserbase or Browser Use Cloud key exists.** Everything about their behaviour
   (stealth quality, CAPTCHA solving, latency, sticky IPs) is a vendor statement. Nothing was run.

**Where the docs were wrong and source or tests showed the truth** (all verified):

- Stagehand's docs say it "never closes a browser it did not launch". In 4.2.0, `browser.close()` on an
  attached browser sends CDP `Browser.close` ([V-7](research/verification/antidetect-proxies.md)). On
  Browserbase, `close()` releases the session even with `keep_alive` set
  ([BB-9](research/verification/browserbase.md)).
- Self-hosted Steel accepts `userDataDir`, `persistProfile` and `profileId` and answers HTTP 200, then
  ignores them ([EA-1, EA-2](research/verification/existing-assets.md)). The box's own `steel.py` sends
  them.
- Stagehand's "required" flag for loading its extension over CDP is stale. The real rule is a Chromium
  version threshold ([AP-1](research/verification/antidetect-proxies.md)).
- Hermes' docs say the identity header goes on every request. It does not go on the preflight probe
  ([HP-9](research/verification/hermes-packaging.md)).

**What this means.** Treat vendor docs as a starting point. The behaviour we rely on was re-derived from
source and small tests, mostly on arm64 containers on a Mac. Re-measuring on amd64 droplets is M1
(**pending Q-12**). The open items are in Q4.

Evidence: the four `MANIFEST.md` files above; [CONSISTENCY.md](research/verification/CONSISTENCY.md)
section 3a lists every refuted claim a dossier still carries.

### Q2. What gaps do the open-source projects leave, and what do we build?

**Short answer.** Stagehand and Browser-Use give you engines, and Steel gives you a browser. They do not
give you a fleet. Almost everything that makes "1,000 profiles, each the same browser every time" true is
missing, and some of it is silently broken. The structure we build is the decision record
([DECISIONS.md](DECISIONS.md), D1 to D18). **None of it exists yet.**

Roles, as the record sets them: Stagehand is the main engine for scoped steps and typed reads on open-web
`research` identities (D6, D18). Browser-Use is the backup for open-ended goals. Steel is the main browser
host. One thing is a default, not a settled fact: which executor drives a **logged-in** account. Stagehand's
in-browser extension is detectable on one public check, so D18 gives `account` identities the fleet's own
minimal CDP executor, and the M1 measurement (gate G1.4, O-02, section 3.2) can overturn that per site class.
Open-web `research` identities have no account to protect, so they keep Stagehand.

**What does work out of the box** (small samples, arm64 containers):

- Steel runs Chromium, exposes CDP and a live viewer, and plumbs a proxy through a local forwarder that
  failed closed in one test ([STE-7](research/verification/steel.md)).
- Stagehand's `act(Action)` replays a chosen element with zero model calls when `selfHeal` is false
  ([SH-2](research/verification/stagehand.md)). Browser-Use's `Tools.act` does the same for an element
  index ([S1-07](research/verification/system1-models.md)). These are the building blocks of an
  executor. Which one drives a logged-in identity is the M1 decision above.
- Browser-Use attached to self-hosted Steel and finished 9 of 9 runs on two easy public tasks
  ([BRO-1](research/verification/browser-use.md)). Easy means scripted 2-to-3-click flows on one static
  site, not open-ended work.

**The gaps, and what we build.** Left column is the need; middle is what the open-source tool gives;
right is what the record says we build.

| Need | What the open-source tool gives | What we build (all unbuilt) | Decision |
|---|---|---|---|
| Many isolated identities | Steel runs one browser per container. A second create silently takes over the live browser, and `GET /v1/sessions/{id}` then returns a made-up "released" stub ([STE-1](research/verification/steel.md)). | One container per awake identity, started by a node agent. A lease in Postgres with fencing tokens. | D4, D12 |
| Logins that survive a restart | Steel ignores `userDataDir`. Chromium commits cookies on a 30 s timer, so a release inside 30 s lost the cookie 6 of 6 times. A stale `Singleton*` lock gives a blank profile behind HTTP 200 ([STE-2, STE-3](research/verification/steel.md)). | Safe release order, a cookie journal from the context export, an encrypted profile tarball, a login probe after every wake. | D4, D14 |
| Honest health | Steel's `/v1/health` is `ok` even with no browser, by a source-level bug ([STE-3](research/verification/steel.md)). | Health means: the live Chromium has this identity's profile directory, and a per-site login probe passes. | D4 |
| Control-plane security | No authentication on REST, CDP or viewer. Quick starts publish raw CDP on 9223. Proxy credentials are echoed in API responses ([STE-8, STE-7](research/verification/steel.md)). | Only the node agent reaches a container, on a per-identity network. A credential-less proxy forwarder. | D4, D10 |
| The same fingerprint every wake | Steel makes a new random one each launch ([AP-4](research/verification/antidetect-proxies.md)). Browserbase cannot pin one below its Scale plan ([BB-2](research/verification/browserbase.md)). | A persona pinned at creation (user agent, timezone, locale, viewport) and checked at every wake. | D3 |
| The same IP every time | Steel takes a proxy per session. Browserbase's built-in proxies rotate ([BB-1](research/verification/browserbase.md)). | One dedicated static ISP IP per identity, with a forwarder that fails closed on any exit-IP change. | D10 |
| Human login | Steel's viewer is unauthenticated. Special keys, IME, passkeys and native dialogs are untested ([STE-9](research/verification/steel.md)). | A viewer link brokered by the fleet service, signed and short-lived. The human holds the lease while connected. | D14 |
| A cache that skips the model | Stagehand v4 has none off Browserbase ([SH-1](research/verification/stagehand.md)). Browser-Use's `rerun_history` still ends with a model call ([V-12](research/verification/system1-models.md)). | Our own replay of stored `Action` objects, re-checked against the page before every click. | D5, D18. (The record format follows the executor, so entries are keyed by executor and schema version and never converted; section 3.2.) |
| Choosing elements with a System 1 model | Both frameworks' model hooks demand full generative output ([V-06](research/verification/system1-models.md)). | Our own loop: snapshot, decider picks, the identity's executor acts (Stagehand, Browser-Use `Tools.act` or a minimal CDP executor; for logged-in identities the M1 result decides). A central `/decide` service. | D5, D7 |
| A driver with a known footprint on logged-in pages | Stagehand's extension trips a public check and stays resident after `close()`. Browser-Use's attach does not trip it, its actor API does ([AP-2, AP-3](research/verification/antidetect-proxies.md)). Neither was tested against a real platform. | An executor chosen by identity kind (D18): the fleet's own minimal CDP executor, a new component, is the default for logged-in `account` identities; `research` identities keep Stagehand. M1 can overturn it per site class: Stagehand with uninstall-after-session if that works on Steel, or Browser-Use `Tools.act`. | D6 as amended by D18, O-02 (section 3.2) |
| Model plumbing | Stagehand v4 cannot point at OpenRouter except through a callback ([SH-4](research/verification/stagehand.md)). Strict JSON schemas are not enforced by every provider ([REA-7](research/verification/reasoning-models.md)). | A client shim: schema validation, token caps, retry on another provider, a provider allowlist. | D8 |
| Scheduling and capacity | None. | A pre-wake scheduler, a Postgres job queue, a placer across droplets. | D12 |
| Safe posting, replying, messaging | None. | Intent row before the effect, an independent read-back receipt, approved campaign manifests, scoped tokens, a rate governor. | D13 |
| Official API channels | None. | Connectors for Meta, TikTok, LinkedIn and X, behind one `publish` tool. | D2, D17 |
| Reaching Hermes profiles | None. | One shared service with an MCP door and an HTTP door, one shared read-only skills directory, a scoped token per profile. | D1, D17 |
| Memory | None. | The service returns evidence; each profile writes its own notes into its Obsidian vault. | D15 |
| Upstream drift | Steel's fixes are outsider PRs with no maintainer review ([STE-14](research/verification/steel.md)). | Pinned digests and versions, an upgrade smoke test, our own takeover guard and profile handling. | D4, D6 |

**Two honest notes.**

- Open-source Steel gives us less than "main browser infrastructure" suggests. We carry our own takeover
  guard, health check, authentication by isolation, profile handling and persona. Because of that, the
  record treats "plain Chromium plus a small session API" as a real alternative. M1 measures both and
  writes the winner into D4 ([C-24](research/verification/CONSISTENCY.md)).
- The existing code we hoped to reuse needs work too. The lease pattern in an earlier internal job-claim design is not
  safe under concurrent claimers, and the lease SQL in the scale dossier cannot implement human takeover
  ([EA-7](research/verification/existing-assets.md), [SCA-10](research/verification/scale-infra.md)).
  D12 specifies a fresh design.

Evidence: [steel dossier gap table](research/dossiers/steel.md) (section 3, read with
[verification/steel.md](research/verification/steel.md)); [existing-assets gap table](research/dossiers/existing-assets.md)
(section 3, read with [verification/existing-assets.md](research/verification/existing-assets.md)).

### Q3. System 1 models, the 90% goal, and the reasoning model

**Short answer.**

- **System 1 models.** One `/decide` service inside the fleet service fronts the decision models. Jev
  is the default for text. Perplexity Decider handles screenshots. Clef handles screenshots once its
  image path is tested. OpenAI Decisions is optional. None of them writes text (D7).
- **The 90% goal.** It is a hypothesis. Nothing measured supports it yet, and it should not be quoted to
  a client.
- **Reasoning model.** `z-ai/glm-5.3-flash` at low reasoning effort, behind a shim that validates every
  reply (D8). Among the models tested, nothing beat it. That is a weaker statement than "GLM is proven
  best" (see below). It drives rung L3 (Stagehand on `research` identities) and rung L4 (Browser-Use). On
  logged-in `account` identities L3 is the fleet's own L3-lite run by its minimal executor (D18), and
  where no model provider is cleared for page text (Q-07) L3 is closed there (section 3.2).

**System 1: what exists and the catches.** All four are live and none generates text
([V-01](research/verification/system1-models.md)). Jev answered in 139 to 329 ms from the Mac, and
earlier projects saw production-path medians of 443 to 487 ms
([S1-10](research/verification/system1-models.md)).

| Model | Takes | Limit | The catch |
|---|---|---|---|
| Jev (TypeSafe) | Text only | 100K tokens/s and 80 requests/s, "dynamic"; on 2026-09-17 it was 250K tokens/s and 1,200 requests/min | It accepts an image without error and bills it as text, so a misrouted screenshot step gives a plausible wrong number ([S1-02](research/verification/system1-models.md)). It leans to the first option in a list. |
| Perplexity Decider | Text and base64 images | 10 requests/s per organisation plus a token limit | Image token cost is documented two different ways, a 6x gap ([V-14](research/verification/system1-models.md)). |
| Clef (Cloudflare) | Text and up to 4 images | About 300 requests/min is an assumption inferred from a page that predates Clef ([S1-03](research/verification/system1-models.md)) | Image calls through OpenRouter are untested, and OpenRouter's alpha decisions request has no image field. It silently truncates long text. |
| OpenAI Decisions | Text and images | Published tiers exist for `gpt-6-luna`; whether they apply to Decisions is unconfirmed | Public beta, closed weights, option cap unstated, and a different request shape when called directly. |

Four rules follow from the verification, and D7 carries them:

1. **Token caps bind before request caps.** A 180-candidate step is 4,911 to 6,217 input tokens
   (measured), so Jev's cap allows about 16 to 20 steps a second. On the dossier's own estimate of load
   (10% of 1,000 agents active, one decision every 2 to 3 seconds) demand is 35 to 50 steps a second,
   which is 1.7 to 3.1 times that cap ([V-04](research/verification/system1-models.md)). So we prune
   candidates and spill over to other providers. The old claim that this "fits Jev alone" is wrong.
2. **Confidence does not travel.** The same Clef-flash weights gave blocker confidence 0.43 on
   Cloudflare and 0.74 on PrimeIntellect, and unpinned OpenRouter calls went to the second host
   ([V-03](research/verification/system1-models.md)). Thresholds are set per template, model and serving
   provider, and the provider is pinned and logged.
3. **A decider is not a safety control.** Adversarial page text can move its answer
   ([V-07](research/verification/system1-models.md)). Posts, sends, replies, DMs, deletes and payments
   are gated by deterministic policy and approved manifests, never by a probability (D5, D13).
4. **The router enforces modality.** Because Jev takes images silently, the router, not the model,
   decides who sees a screenshot.

**The 90% goal: why it is a hypothesis.**

- D7 defines the metric as "System-1 share": actions completed without a generative call (plain code,
  official API calls, replay and decider together) divided by all browser actions, per procedure.
- The research estimate is `unverified`: at least 90% is plausible for repetitive posting-style
  procedures; about 30 to 60% for the decider alone across all work; well below 90% for lead-gen
  research ([V-05](research/verification/system1-models.md)). Those ranges are guesses, and the
  dossier states two different ones (30 to 60% and 30 to 55%).
- What was actually measured is thin. The Stagehand zero-call proof picked elements with a hard-coded
  rule, not a System 1 model ([SH-2](research/verification/stagehand.md)). The Browser-Use proof used
  real Jev on one easy page: it chose "Poetry" from 71 options at 0.94 to 0.96 confidence in 315 to 388 ms
  ([BRO-3](research/verification/browser-use.md)). Jev's one logged browser miss (0 of 3 on "first search
  result") is one deterministic miss repeated ([V-2](research/verification/existing-assets.md)). The
  trial measured zero live cases; its 100 of 100 was scripted
  ([EA-10](research/verification/existing-assets.md)). Element-choice accuracy on dense social pages has
  not been measured by anyone.
- Where the misses go matters. Those ranges assumed that when the replay cache and the decider miss, a
  generative L3 step absorbs the work. If Stagehand's extension is ruled out on logged-in accounts, a miss
  climbs to Browser-Use, to a fleet-built L3 of our own, or to a human instead (section 3.2). The share's
  definition does not change. The generative cost and the human load per miss do, and both are `estimate`s
  to re-measure.
- Writing text (posts, replies, DMs) always needs the reasoning model or an approved manifest. A high
  action share does not mean the model is out of the loop for content.
- **My suggestion, not in the record:** report two numbers, the decider's own share (rung L2) and the
  no-generative-call share (L0 plus L1 plus L2). Rung L0 includes plain code and official API calls, and
  API-first work (section 3.1) raises that second number without any decider doing anything. A high
  figure could be true and still not mean what you want it to mean. O-15 already says to define the
  procedures, the held-out set and the metric before any target is quoted
  ([CONSISTENCY.md](research/verification/CONSISTENCY.md)).

**The reasoning model: what the evidence says.**

- **Correctness at low effort** (small, frozen prompts): Stagehand act and observe 48 of 53, extract
  11 of 11, replayed Browser-Use steps 8 of 8, one tool call 3 of 3. Pixel-accurate click coordinates
  from a screenshot 3 of 3, the only model to manage it, on one screenshot
  ([REA-1](research/verification/reasoning-models.md), [REA-8](research/verification/reasoning-models.md)).
  Live Browser-Use runs: 6 of 6 on local Chrome on the Mac, easy pages
  ([REA-9](research/verification/reasoning-models.md)); 9 of 9 on self-hosted Steel
  ([BRO-1](research/verification/browser-use.md)).
- **The defect is bigger than first reported.** Click acts on a 6,000-token page ran away or returned
  junk arguments in 6 of 80 calls (7.5%; 4 of 52 runaways, 7.7%, 95% interval 3 to 18%). All of them fell
  on two provider-and-task pairs, so we cannot tell if the cause is the model or the provider. A runaway
  cost 34 to 52 s and about $0.004. Plan for roughly one defective act in 13 on dense pages until a
  per-provider benchmark says otherwise. The per-call token cap is mandatory
  ([REA-3](research/verification/reasoning-models.md)).
- **Speed and cost.** Uncached Stagehand calls: p50 about 1.7 s and p90 about 3.5 s (n=12; the 1.2 s
  headline was flattered by the provider's prompt cache). About $0.001 per uncached act on a 6,000-token
  page at list price ([REA-2](research/verification/reasoning-models.md),
  [REA-14](research/verification/reasoning-models.md)).
- **Reasoning cannot be turned off.** Disabling it returns HTTP 400, and leaving it unset means the
  maximum. Browser-box notes say that costs "about 40 s a step"; nobody re-measured that
  ([REA-5](research/verification/reasoning-models.md)).
- **JSON validity is not solved by strict schemas.** Enforcement depends on the provider. One provider
  (Phala) returned non-JSON or wrong-shape output in 4 of 4 probes, another (Friendli) broke the
  element-id pattern in a 22-provider sweep, and with a narrowed provider list Z.AI returned YAML with
  HTTP 200. So the shim validates every reply against the full
  schema, retries once on another provider, and uses a provider allowlist that passes a per-provider
  benchmark ([REA-7](research/verification/reasoning-models.md)).
- **Stagehand v4 reaches OpenRouter only through a client callback**, which also keeps the key out of the
  browser ([SH-4](research/verification/stagehand.md)).
- **Repair ladder:** retry GLM on another provider; then DeepSeek V4.1 Flash with reasoning off
  (different failure mode, MIT); then the screenshot path with GLM vision. Do not use Nemotron 3.5
  Lightning (fabricated a click on an impossible instruction in 2 of 3 runs) or Mistral Small 2603
  (rate-limited). Qwen 3.8 Flash scored 27 of 27 but is a fragile dependency: one provider, no required
  tool choice, 0-to-1000 coordinates, a custom licence
  ([REA-10, REA-11](research/verification/reasoning-models.md)).

**Limits on that evidence.** The benchmark is 9 frozen prompts from 4 pages on 2 sites, each served by a
single provider, so "GLM scored X" really means "GLM on provider P for task T"
([REA-1](research/verification/reasoning-models.md)). The act, observe and extract numbers above come
from requests captured from Stagehand 4.2.0 ([reasoning-models dossier](research/dossiers/reasoning-models.md),
`raw/captures/`). They do not transfer to an L3 built on a different executor, which needs its own
prompt, schema and benchmark before anyone relies on it (section 3.2). The Stagehand end-to-end proof
and the latency numbers came from local Chrome on the Mac, not Steel. Nobody has measured GLM throughput
for 100 to 1,000 agents; 429 errors already appeared. **Pending Q-07:** requiring zero data retention changes the provider
list, because the benchmark's main provider is not ZDR-listed and a ZDR-listed one failed schema
enforcement every time ([missed issue 12](research/verification/reasoning-models.md)). A per-provider
benchmark is the M3 gate (O-06).

Evidence: [system1-models dossier](research/dossiers/system1-models.md) with
[verification](research/verification/system1-models.md); [reasoning-models dossier](research/dossiers/reasoning-models.md)
with [verification](research/verification/reasoning-models.md); D5, D7, D8 in [DECISIONS.md](DECISIONS.md).

### Q4. What was up in the air?

**Short answer.** We closed what documents, source code and a few small API calls could close. What is
left falls into four buckets: your decisions (section 1), things only a droplet can show, design work
that needs no hardware, and accounts or keys that someone has to apply for. The one unknown that moves
cost the most is how many identities need a browser at all. Nobody has estimated that yet
([C-17](research/verification/CONSISTENCY.md)).

**Settled by the research** (each was open, or wrongly believed, before):

| Question | Answer | Evidence |
|---|---|---|
| Is Stagehand v4 detectable? | Yes on one public check: its extension trips `isAutomatedWithCDP` on stock Chromium 152 and stays resident after `close()` until uninstalled or the browser restarts (n=1 per condition, extension loaded over CDP). Whether any social platform weighs that signal is unknown. So the executor for logged-in identities is an open M1 decision (O-02, section 3.2). | [AP-2](research/verification/antidetect-proxies.md) |
| Can Stagehand v4 attach to a vendor or patched browser? | Only on Chromium 149 or newer, plus the extension on the browser's own filesystem, a CDP address the browser can reach, and an admitting `--remote-allow-origins`. | [AP-1](research/verification/antidetect-proxies.md) |
| Does Stagehand v4 cache on Steel? | No. | [SH-1](research/verification/stagehand.md) |
| Does self-hosted Steel keep a per-profile login? | Only with one container and volume per identity, a careful release, and lock cleanup. | [STE-1 to STE-5](research/verification/steel.md) |
| Is Jev's option cap 180? | No. The provider cap is 255; 180 is a client-side convention. | [BRO-4](research/verification/browser-use.md), [S1-08](research/verification/system1-models.md) |
| Does the Jev endpoint Gemini gave exist? | No. The real call is `POST https://api.typesafe.ai/v1/systemone`. | [GEMINI-AUDIT](research/verification/GEMINI-AUDIT.md) row 10.06 |
| Do all four decision models answer through one OpenRouter key? | Yes, 4 of 4 answered one call each. | [S1-04](research/verification/system1-models.md) |
| Can skills and tools reach the Jev Workforce trial? | The MCP server, yes, through the integrations route. Skills, yes, as owner-approved prose guides of up to 6,000 characters. Plugins, no. | [HP-5](research/verification/hermes-packaging.md) |
| Can we release a skill by flipping a `current` symlink? | No. Hermes caches the resolved path. Use versioned paths and roll gateways. | [X-1](research/verification/hermes-packaging.md) |
| Do X's "10,000 posts and 1,440 DMs per day per app" ceilings bind us? | Unproven. They are legacy plan columns. Build the governor from live rate-limit headers. | [SP-3](research/verification/social-platforms.md) |

**Needs a droplet (M1, pending Q-12).** About 30 behaviours, listed in
[CONSISTENCY.md](research/verification/CONSISTENCY.md) section 6. The ones that can change the design:

- Steel: special keys, IME, passkeys and native dialogs through the viewer (needed for human login);
  restoring a profile tarball on a different host and on x86; memory and CPU on real social pages;
  whether a page can reach the cloud metadata address around the proxy; whether a graceful browser close
  flushes cookies.
- Stagehand: replaying a stored `Action` across iframes and shadow DOM; whether
  `Extensions.uninstall` removes the flag-loaded extension on Steel, and whether the next session can
  re-attach; detectability of each candidate executor inside the full stack (guard, persona check, login
  probe, viewer, proxy), not on its own; a large file upload; whether a crashed worker wedges the
  browser. How the extension behaves against real sites cannot be tested in M1, which uses public pages
  only.
- System 1: element-choice accuracy on dense social pages; Clef image calls through OpenRouter; OpenAI
  Decisions limits.
- Models: the benchmark on Steel rather than local Chrome; a per-provider benchmark; GLM throughput for
  100 to 1,000 agents.
- Scale: wake latency p50 and p95 on amd64; the CPU cost of the in-browser URL guard; lease behaviour
  under concurrency (the SQL part can be tested locally with no network).
- Platforms: X limits on a live pay-per-use app; how often a keep-warm probe triggers a checkpoint.
- Hermes: token isolation under a multiplexed gateway (the hands-on used separate processes).

**Needs design only, no hardware or spend.** The lease and fencing design (O-03); a rewritten job claim
(O-04); where state bundles are encrypted and who holds the key (O-09); the proxy acceptance rule
(O-10); per-identity network isolation (O-11); the keep-warm policy (O-12); a canary rule for new
identities and new pins (O-13); where the Obsidian vault lives (O-14); the measurement plan for the 90%
hypothesis (O-15). Added by the stress tests: the executor interface and what L3 means on a logged-in
account if the Stagehand extension is ruled out there (section 3.2). D17 already reconciles the tool
surface (C-16). The "fleet charter" it refers to is drafted in [CHARTER.md](CHARTER.md).

**Needs an account, key or approval (O-08).** An X developer app with prepaid credits; Meta App Review
and Business Verification; the TikTok Accounts API form; LinkedIn Community Management API access;
proxy accounts; a Browserbase key only if it is ever used. The research did not check which of these
keys already sit in `.env`.

Evidence: [CONSISTENCY.md](research/verification/CONSISTENCY.md) sections 4 (O-01 to O-17), 5 and 6.

### Q5. Can Stagehand or Browser-Use, called from a Hermes profile, drive an anti-detect browser?

**Short answer.** The Hermes profile never touches a browser. It holds a token and calls the fleet
service. The service's workers run the engines against a browser host (D1, D17). So the real question
is whether the fleet's engines can drive an anti-detect browser:

- **Browser-Use: yes**, for any Chromium-based anti-detect browser whose start call returns a CDP address.
- **Stagehand v4: only under four conditions**, and only some products will meet them. **No vendor
  product has been tested with either engine.** Every vendor path below is a `vendor-claim`.

These conditions only matter on an identity where Stagehand is the engine. On logged-in `account`
identities the default executor is the fleet's own minimal CDP executor, with Stagehand only if M1 shows it
is better for a site class (D18, section 3.2), so the conditions bite mostly on `research` identities.

**Why.**

*Browser-Use* is pure CDP and attaches to any Chromium endpoint. In tests it attached to stock Chromium
152 and to CloakBrowser's free build (Chromium 146), navigated and read page state without tripping a
public CDP-automation check ([AP-3](research/verification/antidetect-proxies.md); n=1 per condition, and
clicks, typing and scrolling were not run). Two cautions. Its actor API and coordinate clicks do trip
that check. And it injects a visible overlay into pages unless `highlight_elements=False`
([missed issue 1](research/verification/browser-use.md)).

*Stagehand v4* runs inside the browser as an extension. To attach to a browser it did not start, all of
these must hold ([AP-1](research/verification/antidetect-proxies.md)):

1. The browser is **Chromium 149 or newer**. At 146 and below the kernel refuses to load the extension
   over CDP ("Method not available."); 147 and 148 gate it.
2. The extension is on the **browser host's own filesystem**.
3. The **CDP address resolves from inside the browser**, because the extension dials it back.
4. **`--remote-allow-origins`** admits the extension's origin. Vendor launchers may not set that flag.

It failed on CloakBrowser's free 146 build and worked on Debian Chromium 152. CloakBrowser's paid builds
(150 to 154) probably pass but are untested. For kernels at 148 or below the only Stagehand route is
v3.7.3, which is in maintenance limbo and has 5 npm advisories (2 high)
([SH-9](research/verification/stagehand.md), [V-6](research/verification/stagehand.md)).

*DICloak specifically.* Its vendor page describes a Docker agent image (Agent API on port 52100, CDP
ports 45000 to 45099, up to 100 concurrent). A local API opens a profile and returns a `debug_port`,
from which you read the CDP WebSocket address
([antidetect dossier Q1](research/dossiers/antidetect-proxies.md); `vendor-claim`). The vendor documents no
custom flags or extensions, publishes nothing about its kernel's CDP surface (as with every vendor in
the dossier), and hides profile counts on its pricing page. So Browser-Use will probably work. Stagehand v4 is unknown until a conformance test
checks the kernel version first, then conditions 2 to 4. The claim that its runtime image is non-headless
was not found on the vendor page ([verification, unsourced number 14](research/verification/antidetect-proxies.md)).

*The others.* Linux-capable with a documented CDP path: Kameleo, Multilogin X, AdsPower, Octo, GoLogin,
Nstbrowser, Dolphin, MoreLogin and CloakBrowser (Dolphin's and MoreLogin's API shapes are third-party
only). Windows or macOS only, so out for DigitalOcean: Undetectable and Incogniton. Firefox-based
kernels (Multilogin Stealthfox, Kameleo Junglefox, Camoufox) cannot be driven by either engine, because
both are CDP-only ([AP-6](research/verification/antidetect-proxies.md)).

*Two costs people forget.* Cloud-synced vendors hold your clients' session cookies on their servers. And
vendor kernels trail stable Chrome, so every candidate needs its own attach test.

**Pending Q-02, Q-03, Q-04.** Whether we use any of these at all is your call. The default is no
(see Q7).

Evidence: [antidetect-proxies dossier](research/dossiers/antidetect-proxies.md) §1 and Q1 to Q2, read
with [verification/antidetect-proxies.md](research/verification/antidetect-proxies.md) (AP-1, AP-2, AP-3,
AP-6, missed issue 1); D6 and D9 in [DECISIONS.md](DECISIONS.md).

### Q6. Can we apply proxies?

**Short answer.** Yes. One **dedicated static ISP IP per identity**, bought on a term, never shared and
never rotating, bound through a node-local forwarder that stops the browser if the exit IP changes (D10).

**Why, and how.**

- **Price.** About $2.5 to $3.3 per IP-month at list (`vendor-claim`; Decodo $3.33 at 3 IPs down to
  $2.50 at 200; Bright Data $2.50 at 1,000). That is about $2,500 a month for 1,000 identities
  ([V-3](research/verification/antidetect-proxies.md)). Bright Data adds a 100 GB per-IP fair-use
  allowance. Dedicated mobile ports (about $117 to $130 a month) are a targeted exception only.
- **The forwarder.** Three engines handle proxy credentials badly. Steel echoes the credentialed upstream
  URL over its unauthenticated API ([STE-7](research/verification/steel.md)). Stagehand's local launch
  refuses authenticated proxies. Browser-Use answers proxy authentication by intercepting every request
  on the focused tab ([BRO-11](research/verification/browser-use.md)). So the proxy and its credentials
  live in a forwarder owned by the node agent. The browser is given only `http://127.0.0.1:<port>`
  ([AP-5](research/verification/antidetect-proxies.md)).
- **Fail closed.** IPRoyal "sticky" sessions silently swap the IP unless `_killswitch-1` is set. The
  forwarder checks the exit IP during the session and stops the browser on any change, not only at wake.
- **Vetting rule (O-10).** A vendor name does not tell you where the IPs come from. The FBI seized NetNut
  in July 2026 over the Popa botnet, and its pool was widely resold
  ([AP-7](research/verification/antidetect-proxies.md)). A new IP is accepted only after: exit-IP match,
  an ISP (not datacenter) network class, reputation checks, geo and timezone match, and a written
  statement of sourcing. If any check fails, reject it.
- **What not to do.** No shared ISP IPs (Oxylabs: "Shared with up to 3 users"). No rotating residential
  for logged-in identities. No Browserbase built-in proxies: they rotate, and Browserbase's own blog
  recommends static IPs for logged-in sessions ([BB-1](research/verification/browserbase.md)).
- **Locale and timezone follow the IP.** Timezone is always passed explicitly; with the proxy down, Steel
  fell back to UTC. On Linux, `--lang` does nothing; use `LANG` and `LANGUAGE` plus `--accept-lang`
  ([V-1](research/verification/antidetect-proxies.md)).
- **If an identity lives on Browserbase,** it needs a bring-your-own proxy (`type: "external"`, HTTP or
  HTTPS only, Developer plan or above) and a CDP timezone override, which may not survive reconnects
  ([BB-8](research/verification/browserbase.md)).

**Not yet verified (needs a droplet):** whether a page can reach the cloud metadata address
(169.254.169.254) around the proxy, because Chromium bypasses the proxy for loopback and link-local
addresses; and what `PROXY_INTERNAL_BYPASS` does with a loopback forwarder
([STE-7](research/verification/steel.md), C-08 in [CONSISTENCY.md](research/verification/CONSISTENCY.md)).
**Pending Q-06** for the proxy spend cap.

Evidence: [antidetect-proxies dossier](research/dossiers/antidetect-proxies.md) Q5 to Q7 with
[verification](research/verification/antidetect-proxies.md) (V-3, AP-5, AP-7); D10 in [DECISIONS.md](DECISIONS.md).

### Q7. If proxies and stealth are enough, can we skip the anti-detect browser?

**Short answer.** Yes, by default (**pending Q-02**). But "proxies plus stealth" is the wrong pair.
Steel's built-in stealth makes things worse, so we turn it off and pin values ourselves. The pair that
works is a dedicated IP, plus a pinned persona, plus a persistent profile, plus human-paced behaviour.

**Why.**

1. **The big risks are not fingerprints.** For client accounts the dominant risks are behaviour, platform
   terms and IP history. A commercial anti-detect browser adds no capability that changes those
   (antidetect dossier verdict 2; [section 3.1](#31-terms-of-service-on-social-platforms-and-the-api-first-recommendation)).
2. **The aim is continuity, not evasion.** Same device, same IP, same rhythm, for the client's own
   account. Meta's terms forbid circumventing its technological measures, and the patched-kernel route
   would be spoofing (D9). An earlier private SDR harness states it does no spoofing (**pending Q-04**).
3. **Licences are cheap, integration is not.** For API-capable plans the licence runs about $29 to €79
   a month at 30 profiles, $36 to €299 at 100, and $179 to €1,499 at 1,000 (`vendor-claim`). That is 4%
   to 30% of the base bill for most vendors, but Kameleo is 51% at 100 profiles and 35% at 1,000
   ([V-2](research/verification/antidetect-proxies.md)). The larger costs are Linux desktop agents,
   per-kernel Stagehand tests, lock-in, and a vendor holding client cookies.

**Why Steel's stealth is out.** Open-source Steel generates a new random fingerprint on every launch, and
it contradicts itself: a user agent saying Chrome 139 to 145 on a Chromium 152 engine, an 800x600
screen, a hard-coded Windows NVIDIA GPU string in workers, failed native-function checks, empty
client-hint brands, and an `aarch64` user agent beside an `x86_64` platform
([AP-4](research/verification/antidetect-proxies.md), [STE-10](research/verification/steel.md)). That
is the opposite of "same browser every time". With injection off and the user agent pinned, the
fingerprint was stable (no field changed across 2 sessions, so n=2).

**The price of skipping it.** The stable fingerprint is the host's real one. CPU core count, GPU and
WebGL string, canvas hash and screen size are identical for every identity on a node, so a platform could
link them. Until per-identity values exist, identities of different clients do not share a node, which
means about 7 identities per node and a higher bill (**pending Q-13**; D3). Per-identity values would
come from CDP injection in the node agent (to measure in M1) or from a seed-pinned patched kernel such as
CloakBrowser. That kernel is proprietary, reports licence and session telemetry, and is spoofing
([V-9](research/verification/antidetect-proxies.md); **pending Q-03**).

**When we would buy one.** Only after a measured failure on a named site class, and only a product that
runs on Linux, speaks CDP, and passes our attach test. The record keeps this as a per-identity choice made
at creation (D9).

**Limits of the evidence.** Every bot-page result is from public test pages, n=1 or 2 per condition,
on arm64. "Normal" on a test page does not predict how Meta or TikTok will react. Nothing here was run
against a real social platform, and the brief forbids it.

Evidence: [antidetect-proxies dossier](research/dossiers/antidetect-proxies.md) §1 with
[verification](research/verification/antidetect-proxies.md) (AP-4, AP-8, V-2, V-9);
[STE-10, STE-11](research/verification/steel.md); D3, D9 in [DECISIONS.md](DECISIONS.md).

## 3. Things you did not ask but need to know

### 3.1 Terms of service on social platforms, and the API-first recommendation

**Short answer.** A bot driving the logged-in website of a client's account breaks, or sits in a grey
area of, every major platform's rules. Matching fingerprints and IPs only reduces how often you get
checked. It does not make the automation allowed. The Gemini document said accounts get banned "when two
things mismatch" (browser identity and network identity). That is wrong: platforms ban the automation
itself ([GEMINI-AUDIT](research/verification/GEMINI-AUDIT.md) row 9.02). So the record recommends
**API-first** for client social work (D2, **pending Q-01**).

| Platform | What the rules say | The sanctioned route, and its limits |
|---|---|---|
| **X** | Non-API automation "results in permanent suspension" (developer guidelines; the help page says "may result in"). No automated likes, no duplicate posts across accounts, AI reply bots need X's prior written approval, keyword-only auto-replies are banned ([SP-1](research/verification/social-platforms.md), [V-7](research/verification/social-platforms.md)). Automated accounts using the API must carry an "Automated" label, name the operator in the bio and link a human-managed account ([V-8](research/verification/social-platforms.md); **pending Q-05**). Competitive benchmarking is prohibited. | X API v2, pay-per-use: $0.015 per post, **$0.20 per post with a URL**, $0.015 per DM ([SP-4](research/verification/social-platforms.md); prices subject to change). For an unverified client account the binding limits are 50 original posts plus 200 replies, 500 DMs and 400 follows a day, and they include API use ([V-2](research/verification/social-platforms.md)). The "10,000 posts and 1,440 DMs per app per day" ceilings are legacy plan columns and unproven ([SP-3](research/verification/social-platforms.md)). |
| **Meta** (Facebook, Instagram) | Terms §3.2 bar accessing or collecting data by automated means "without our prior permission", even when logged in. That is a data-collection clause, not a ban on posting ([SP-2](research/verification/social-platforms.md)). The firmer basis is Meta's Community Guidelines, which allow scripted use of an account only "through authorized routes". The terms also bar circumventing Meta's technological measures. | Graph API for Pages, Instagram professional accounts and Messenger. Accounts you do not own or manage need Advanced Access, which means App Review and Business Verification ([V-1](research/verification/social-platforms.md)). Instagram: 100 API posts a day (the page also says 50; read the live limit endpoint). Messenger: 24 h reply window, 7-day human-agent window, bot reply within 30 s ([V-5](research/verification/social-platforms.md), [SP-5](research/verification/social-platforms.md)). No API for Facebook Groups since 2024-04-22 (corroborated by vendors, [SP-7](research/verification/social-platforms.md)). The dossier also reports no publish API for Facebook personal profiles, and Instagram's Basic Display API for personal accounts ended on 2024-12-04 ([SP-5](research/verification/social-platforms.md)). |
| **LinkedIn** | Bars bots and unauthorised automation, and "copying cookies" to use another's account ([V-6](research/verification/social-platforms.md), [V-4](research/verification/antidetect-proxies.md)). The Messages API is for approved partners, and each message must follow a member action: "Member actions do not include an automated or scheduled event" ([SP-8](research/verification/social-platforms.md)). | Community Management API for company pages. Development tier: 500 calls per app and 100 per member per day. Version 202510 sunsets on 2026-10-15, so connectors must target a current version ([V-3](research/verification/social-platforms.md)). |
| **TikTok** | Bans automated extraction by unapproved systems and "automation tools, scripts, or other tricks designed to bypass our systems" ([V-6](research/verification/social-platforms.md)). The Content Posting API audit rejects "a utility tool to help upload contents to the account(s) you or your team manages" and wants a wide audience ([SP-6](research/verification/social-platforms.md)). | TikTok API for Business (Accounts API). Its access form is mandatory since 2026-03-20; up to 15 posts a day per account. Business Messaging is open beta, unavailable in the EEA, Switzerland and the UK, and needs privacy reviews ([V-4](research/verification/social-platforms.md)). An agency-internal fleet may fail the same "wide audience" test. Approval odds are unknown. |

**What this means for the design.**

- **The browser fleet is for:** human login, re-auth and checkpoints; open-web lead generation; a narrow
  set with no API (Facebook Groups and a few UI-only features of Pages, professional and TikTok business
  accounts), each action human-approved, low volume, with the client's written risk acceptance; and sites
  with no API plus visual checks of clients' own public pages (D2 table). **No browser identity at all** for
  a Facebook personal profile, an Instagram personal account, LinkedIn actions or X: a person acts on their
  own device and the fleet may only draft (`draft_for_human`). The earlier "personal profiles" wording is
  withdrawn (D2 revision).
- **Never built, on any channel:** cold or outbound DMs, automated likes or follows, identical posts
  across client accounts, AI auto-replies on X without X's approval, fake accounts, ban evasion,
  scraping platforms for lead data (D2).
- **Approvals are the long dependency.** One developer app per platform, owned by your business and
  authorised by each client. Meta App Review, the TikTok form, LinkedIn access and X credits are
  milestone dependencies (**pending Q-06**).
- **Consent-based lead capture is a sanctioned source:** Meta Lead Ads, opt-in DM capture, LinkedIn Lead
  Gen Forms, TikTok instant forms (**pending Q-14**). Platform APIs are not lead databases: Meta bars
  building profiles without consent, and X bars profiling without consent
  ([SP-11](research/verification/social-platforms.md)). Open-web lead generation (public company sites,
  robots.txt honoured) stays with the browser.
- **The weekly "keep-warm" login probe is dropped for Meta.** The rule it relied on covers only
  "empty accounts with prolonged dormancy", and the probe itself is scripted access
  ([SP-9](research/verification/social-platforms.md), O-12). No platform publishes a safe probe cadence
  ([V-12](research/verification/social-platforms.md)).
- **Cost moves, it does not vanish.** API-first removes browser hours and proxies for most identities and
  adds X fees (section 3.5).

**Limits of the evidence.** Everything here is document analysis. Nobody observed a checkpoint, a ban or
a safe cadence on any platform ([missed issue 12](research/verification/social-platforms.md)). The
court cases cited in the dossier (*Meta v. Bright Data*, *hiQ v. LinkedIn*) are known only from
secondary commentary ([V-9](research/verification/social-platforms.md)). Whether Meta, TikTok or X weigh
Stagehand's CDP signal is unknown.

Evidence: [social-platforms dossier](research/dossiers/social-platforms.md) with
[verification](research/verification/social-platforms.md); D2 in [DECISIONS.md](DECISIONS.md).

### 3.2 Stagehand v4: no local cache, an extension runtime, and an open question for logged-in accounts

**Short answer.** Three facts about Stagehand 4.2.0 change the plan.

1. It has no action cache off Browserbase. The brief assumed Stagehand would be "cached".
2. Its whole runtime is a Chrome extension running inside the browser.
3. That extension trips one public automation check. So Stagehand is the main engine for scoped steps and
   typed reads on the open web, but whether it may run on a client's logged-in account is an M1
   measurement, not a given (D5, D6; **pending the M1 executor measurement, O-02**). The part headed "If
   the extension is ruled out" below says what rides on that answer.

**No local cache.**

- v4's act, observe and extract cache lives on Browserbase's servers and needs a Browserbase API key and
  a session id. The old `cacheDir` and `enableCaching` options were removed. On Steel every string `act`
  reported `cache.status: DISABLED` and cost a model call ([SH-1](research/verification/stagehand.md),
  [BB-4](research/verification/browserbase.md)). The vendor's own page says so:
  [caching.md](https://docs.stagehand.dev/v4/best-practices/caching.md).
- Even on Browserbase it is gated per project, keyed on page content plus URL, and applies only after a
  hit-count threshold, so feed-like pages are unlikely to hit ([browserbase V-1 and missed issue 7](research/verification/browserbase.md)).
- v3 still has a local cache, and it is unsafe. It replayed a click onto whatever element now sat at the
  cached position and reported `success: true`, and its agent cache returned the first run's text answer
  with zero usage on later runs ([SH-8, missed issue 1](research/verification/stagehand.md)).
- So the idea behind "leads 2 to 1,000 cost $0" is false on our infrastructure
  ([GEMINI-AUDIT](research/verification/GEMINI-AUDIT.md) row 2.05). Any saving must come from a replay
  cache we build (rung L1 in D5), and that cache is unbuilt and unmeasured.
- What we do get: `act(Action)` is a documented replay primitive that skips model inference, the page
  snapshot and the settle wait ([S1-05](research/verification/system1-models.md)). We store and key
  `Action` objects (Stagehand's record format; the last part of this section covers what another
  executor changes). Snapshot and `observe` selectors are positional, so before every replayed or decided
  act we re-snapshot and verify the target's role and accessible name. A mismatch is a miss, never a click
  ([SH-2, missed issue 2](research/verification/stagehand.md)). `selfHeal` stays false on that path, or a
  failed replay quietly calls the model.

**The extension runtime.**

- The TypeScript and Python SDKs are thin JSON-RPC clients. The extension asks for the `debugger`,
  `offscreen`, `scripting` and `tabs` permissions, runs a content script in all frames on every URL at
  `document_start`, and keeps an always-on offscreen heartbeat document
  ([V-1](research/verification/stagehand.md)).
- On Steel it needs three undocumented steps: the extension mounted inside the container,
  `{"extensions":["stagehand"]}` on session create, and a CDP address reachable from inside the browser.
  Stock Steel fails with "File path cannot be resolved." It also leans on Steel's launch flags, so those
  belong in the upgrade smoke test ([SH-3](research/verification/stagehand.md)).
- It trips `isAutomatedWithCDP` on a public check and stays resident after `close()` until
  `Extensions.uninstall` or a browser restart. Browser-Use attach and navigation did not trip it; its
  actor API and coordinate clicks do ([AP-2, AP-3](research/verification/antidetect-proxies.md)). Both
  results are n=1 per condition on a public detector page. The executor for logged-in identities is
  therefore chosen in M1 among three candidates: Stagehand v4 (with uninstall after the session),
  Browser-Use `Tools.act`, or a minimal CDP executor (D6, O-02). Whether Meta, TikTok or X weigh this
  signal is unknown, and M1 cannot find out: spikes are limited to public pages.
- The uninstall mitigation is the cheapest way out and is untested where it matters. The trips were
  measured with the extension loaded over CDP; the Steel recipe loads it with `--load-extension`, so
  whether `Extensions.uninstall` removes it, and whether the next session can re-attach without a
  browser relaunch, are `to measure`
  ([stagehand guide](docs/engines/stagehand.md) sections 13.2 to 13.4).
- One Stagehand instance per browser. The lock is released only by an explicit `close` call, so a crashed
  worker may wedge the browser until it is recreated (`unverified`,
  [SH-6](research/verification/stagehand.md)).
- It has no `agent()` ([V-3](research/verification/stagehand.md)). The Python SDK 4.2.0 ships the same
  extension byte for byte as the TypeScript package ([missed issue 6](research/verification/stagehand.md)).
- Model calls go through our client callback, because `ModelConfig` has no `baseURL`. With no model set
  on Browserbase it would use Browserbase's own `auto` gateway, so the fleet always passes its own
  ([SH-4](research/verification/stagehand.md), [REA-4](research/verification/reasoning-models.md)).
- `variables` keep a secret out of the `act` prompt only. Once typed, the value appears in the
  accessibility tree sent to the model on later calls ([SH-5](research/verification/stagehand.md)). That
  is one more reason agents never type credentials (D14).

**If the extension is ruled out on logged-in accounts.** Walkthrough:
[S14](research/scenarios/S14.md). All of this is design: unbuilt, and `to measure`.

Two identity kinds matter ([ARCHITECTURE.md](ARCHITECTURE.md) section 3.2). A `research` identity is an
open-web browser with no social login, so there is no account to burn. An `account` identity is a
client's logged-in brand account. The stress test's amendment was adopted as D18 (and D5, D6 were edited
to match): the executor is set by identity kind first, with a site-class override as an M1 result.

- **`research` identities keep Stagehand.** It is the main engine there for scoped steps and typed
  reads. A detectable extension may raise the bot-wall rate on open-web sites; that yield is `to measure`.
- **`account` identities default to the minimal CDP executor (D18), and M1 can overturn it.** Their
  image carries no Stagehand extension. The best M1 outcome for Stagehand is that uninstall-after-session
  works and a measured site class prefers it. If the extension trips on a logged-in persona's real setup
  (in-browser guard, persona check, login probe, live viewer), it stays out. The earlier data tested each
  driver alone on public detector pages (AP-2, AP-3), so the full stack is what M1 has to
  measure ([MILESTONES.md](MILESTONES.md) gate G1.4).

That costs more than swapping one executor for another, because the extension is the whole engine
([stagehand guide](docs/engines/stagehand.md) section 2). What goes with it:

| Lost with the extension | Why it matters |
|---|---|
| Page snapshot and element map | The System 1 decider's candidate list and the replay cache's re-check ("verify role and accessible name before every click", D5) are built on them. |
| `act(Action)` and the `Action` record | The replay cache stores these. Another executor means another record, so entries are keyed by executor and schema version and never converted. |
| `observe` and `extract` | L3 on accounts has no engine. |
| `ignoreLocators` | How the guide masks message content when an engine must read near a DM. The rule itself is engine-neutral: DM content never reaches a model ([CHARTER.md](CHARTER.md) invariant 8, **pending Q-07**). A replacement must enforce it and prove it with a test. |
| The forbid-mode proof | "L1 and L2 make zero model calls" is checked in the Stagehand callback today ([guide](docs/engines/stagehand.md) section 6.3). A replacement check has to be structural: the executor imports no model client, and a list of allowed CDP methods is tested. |
| Frame and shadow-DOM handling | Untested for any other executor. |

Not affected: Steel, the in-browser Guard, the proxy forwarder, the model shim, the effect journal and
approvals, Browser-Use, official-API calls (L0) and the human rung (L5).

What would replace it is a fleet-built executor: snapshot builder, candidate builder, action runner,
post-action check, a refusal to type into credential fields, and DM redaction. **That is unbuilt. D18 makes
it the default for `account` identities (the minimal CDP executor); M1 gate G1.4 can overturn it per site
class.** L3 on accounts then takes one of three forms:

- **L3-lite.** The fleet's own snapshot, a reasoning-model call that picks the element, the method and
  the arguments (the shape `{elementId, method, arguments}` that Stagehand's model hook returns today;
  the System 1 decider picks only the element, [system1 guide](docs/models/system1.md)), the
  deterministic approval policy (D5, D13), then the executor. New code and a new benchmark; Stagehand's
  numbers in Q3 do not transfer.
- **Climb to Browser-Use (L4).** Fewer new parts, more steps and spend. Whether a plain element click
  through it trips the check is untested ([AP-3](research/verification/antidetect-proxies.md): attach,
  navigate and state reads only).
- **Climb to a human (L5).** No build cost, more human load.

**Holding position (mine, not in the record).** Under the record default for Q-01 (API-first), browser
work on accounts is small: the login probe, read-backs and the narrow no-API set. Let misses go to a
human. Under browser-first, L3-lite has to be built, because the cost case rests on something absorbing
the misses. Either way, the System-1-share and human-load figures were estimates that assumed Stagehand's
L3 absorbs misses; re-estimate them before quoting them. **Pending Q-01.**

**If no executor passes M1 on a site class,** that is a product decision, not an engineering one: accept
the signal on that class with the client's written risk acceptance, or hold the class to official APIs
plus a human in the viewer. There is nothing to decide today.

**v3 is not a dependency.** It is in low-cadence maintenance (3.7.3 on 2026-08-28), and a fresh
`npm audit` reports 5 advisories, 2 of them high, for its required packages (19 with optional ones). v4
reports 0 ([SH-9](research/verification/stagehand.md)). It remains a fallback only for kernels older
than Chromium 149 (Q5).

Evidence: [stagehand dossier](research/dossiers/stagehand.md) with
[verification](research/verification/stagehand.md); [antidetect-proxies verification](research/verification/antidetect-proxies.md)
(AP-2, AP-3); [stagehand guide](docs/engines/stagehand.md) sections 2, 6 and 13; stress test
[S14](research/scenarios/S14.md); D5, D6 in [DECISIONS.md](DECISIONS.md).

### 3.3 Open-source Steel: persistence and fingerprint traps

**Short answer.** Self-hosted Steel looks like a multi-session browser service with profiles. It is a
single-browser runtime that accepts profile settings and ignores them. Several failures return HTTP 200.
Every item below was measured or read in source at the pin. The tests ran on arm64, once or a few times
each. Re-measuring on amd64 droplets is M1.

| Trap | What happens | Our rule (D4) |
|---|---|---|
| One browser, not many | A second `POST /v1/sessions` silently takes over the live Chromium. `GET /v1/sessions/{id}` returns a made-up `released` stub for any id, and the list drops a taken-over session. Nothing returns 409 ([STE-1](research/verification/steel.md)). | One session per container, enforced by the node agent. Ownership truth is the lease plus a live-process check. |
| Profile fields are ignored | `userDataDir` is only a true/false flag (a precedence bug). `persistProfile`, `profileId` and `timeout` are dropped with HTTP 200 ([EA-1, EA-2](research/verification/existing-assets.md)). The box's own `steel.py` sends them. | Volume at the fixed path, one per container. Never copy the box's call shape. |
| The 30-second cookie window | Chromium commits cookies to disk on a 30 s timer. Releasing at 2 or 5 s lost the cookie 6 of 6 times; 31, 35 and 40 s kept it ([STE-2](research/verification/steel.md)). Social pages rewrite cookies constantly, so waiting after login is necessary but not enough ([M-6](research/verification/existing-assets.md)). | Export the context first (an instant cookie journal), wait at least 31 s since the last cookie change, CDP `Browser.close`, then release, then snapshot. |
| Silent blank profile | A stale `Singleton*` lock makes the next create return 200 on a blank browser; the one after returned 500 after 27 s ([STE-3](research/verification/steel.md)). Steel's own release left the lock 6 of 6 times in persist mode; a raw `Browser.close` left none 3 of 3, and nobody knows why. | Delete `Singleton*` under the lease before start. After every launch, check that the live process has this identity's profile directory and that the login probe passes. |
| `docker stop` is a kill | It took 10.4 s and ended in SIGKILL, leaving the lock. Without `--init`, 8 create-and-release cycles left 151 zombies ([STE-4](research/verification/steel.md)). | Run with `--init`. Never stop a live identity. |
| Health lies | `/v1/health` is structurally always `ok` ([STE-3](research/verification/steel.md)). | Do not use it. |
| No authentication | REST, CDP and viewer are open, CORS allows any origin, and Steel's quick starts publish raw CDP on port 9223 ([STE-8](research/verification/steel.md)). The proxy URL, credentials included, is echoed in create, list and get responses ([STE-7](research/verification/steel.md)). | Only the node agent reaches a container, on its own network. Port 9223 is never published. Steel gets only a credential-less local forwarder address. |
| No sandbox | Chromium runs as root with `--no-sandbox` and with site isolation off, on pages inside logged-in client sessions ([missed issue 3](research/verification/steel.md)). | **Pending Q-08.** |
| Random, inconsistent fingerprint | New on every launch; see Q7 ([AP-4](research/verification/antidetect-proxies.md)). | Injection off; pin user agent, timezone, viewport; check every wake. |
| Headful and WebGL | Headful cannot launch without Xvfb and dbus, which the image lacks. WebGL appeared only with explicit SwiftShader flags; removing `--disable-gpu` alone did not help ([STE-11](research/verification/steel.md), [SCA-2](research/verification/scale-infra.md)). | Add Xvfb and dbus to the wrapper; set the SwiftShader flags. |
| Timezone fallback | With the proxy down, the timezone silently fell back to UTC ([STE-7](research/verification/steel.md)). | Always pass `timezone`. |
| No timeouts | `KILL_TIMEOUT` is parsed and never used ([STE-8](research/verification/steel.md)). | The fleet enforces maximum session and idle timers. |
| The viewer for human login | Typed printable text and popups worked in one synthetic test. Enter, Backspace, Tab, arrows, IME, paste, passkeys, native dialogs and HTTP auth are untested ([STE-9](research/verification/steel.md)). | An M1 gate. D14 is a plan, not an established path. |
| Upstream will not save us | The fixes (#348 `userDataDir`, #375 singleton guard) and the auth request (#235) are outside-contributor items with no maintainer review. `:latest` tracks `main`, not releases, and the image we tested predates the pinned source ([STE-14](research/verification/steel.md)). | Pin by digest. Carry our own takeover guard, isolation, profile handling and persona. |

Two more things to know. First, **cross-host restore is unverified**: the plan says "wake an identity on
any node", but no one has restored a profile tarball on a different host or on x86 ([STE-5 correction
(4)](research/verification/steel.md)). Second, the safe-release order above worked end to end **once**
(n=1) with a synthetic cookie, not a real login.

Evidence: [steel dossier](research/dossiers/steel.md) with [verification](research/verification/steel.md);
[existing-assets verification](research/verification/existing-assets.md) (EA-1 to EA-5, M-1 to M-7); D4 in
[DECISIONS.md](DECISIONS.md).

### 3.4 Browserbase lock-in

**Short answer.** Browserbase is a reasonable paid home for an identity that Steel cannot serve, but an
identity created there is hard to move out, and several features the brief assumed do not exist. The
record makes it an opt-in home chosen when the identity is created (D11).

- **You cannot take the login with you.** Contexts persist the browser profile, but on self-serve plans
  they cannot be listed, exported or uploaded through the API, and suspending or deleting the account
  invalidates all of them ([BB-3](research/verification/browserbase.md)). Enterprise "bring your own
  storage" can write context files to your own S3 bucket; the format is undocumented. The fleet snapshots
  cookies and storage over CDP at the end of every session as a partial backup (`inference`, untested;
  IndexedDB and service workers are not covered).
- **No sticky IP of its own.** The built-in proxies rotate, and Browserbase's own blog recommends static
  proxies for logged-in sessions. The only way to pin an IP is a bring-your-own HTTP or HTTPS proxy
  (no SOCKS5) on the Developer plan or above ([BB-1](research/verification/browserbase.md)).
- **Fingerprint pinning needs the Scale plan.** Below that, sessions are always Linux and `os` is
  rejected. Verified mode is Scale-only and in beta ([BB-2](research/verification/browserbase.md)).
- **Its terms limit how we can scale.** They forbid "creating multiple accounts to avoid restrictions",
  so we cannot shard across Browserbase accounts to escape concurrency caps. They also ban spam and
  impersonation and allow suspension "for any or no reason". API keys are per project, with a concurrency
  allotment each, so one project per client group gives coarse isolation (up to 5 on Startup)
  ([BB-6, missed issues 4 and 5](research/verification/browserbase.md)).
- **A trap in Stagehand 4.2.0.** `browser.close()` releases a Browserbase session even when
  `keep_alive` is set. The login broker must never call it between steps
  ([BB-9](research/verification/browserbase.md)).
- **The keepAlive plan gate is unclear.** Browserbase's docs, its Node SDK and Stagehand's docs name three
  different plans. Check on the plan you would actually buy ([V-3](research/verification/browserbase.md)).
- **The Stagehand server cache is a weak reason to pick it** (section 3.2).
- **Rules for any Browserbase identity (D11):** a bring-your-own sticky proxy, a CDP timezone override
  (fragile across reconnects and Live View; to measure), `recordSession: false`, a per-Context lock, a
  fleet-held key, and our own model callback. Hermes' built-in Browserbase provider is not used, because
  it sends no Context ([BB-5](research/verification/browserbase.md)).
- **Cost.** The $18 and $54 per profile-month in the Browserbase dossier rest on an unsourced 50 MB per
  browser-hour. At the scale-infra dossier's bandwidth estimate (also unsourced) the same setup is about $273 to
  $279 per profile-month, and that configuration uses rotating proxies we cannot use
  ([BB-10](research/verification/browserbase.md)). The figures in section 3.5 use the scale-infra model.

Steel Cloud would add Profiles (300 MB cap, deleted after 30 days unused), concurrency and CAPTCHA
solving, but its terms forbid using it "to violate any website's terms of service", its stealth browser is
Enterprise-only, and self-serve dedicated IPs cap at 25 ([STE-13](research/verification/steel.md),
[V-5](research/verification/browserbase.md)). No key exists for either vendor, so none of their runtime
behaviour has been measured.

Evidence: [browserbase dossier](research/dossiers/browserbase.md) with
[verification](research/verification/browserbase.md); D11 in [DECISIONS.md](DECISIONS.md).

### 3.5 Costs at 30, 100 and 1,000 identities

**Short answer.** Roughly $300 a month at 30 identities, $1,000 at 100 and $8,400 at 1,000, if every
identity needs a browser for the stated hours. These are `estimate`s from a model, **not measurements**,
and they are an upper bound for the browser share of the work. Self-hosting with autoscaled nodes is the
cheapest in every row (with static nodes at 30 x 1 it ties Browserbase). Proxies and models, not
browsers, are most of the bill at 1,000 identities.

Monthly totals (`estimate`: model output at list prices, not quotes), model mix A, self-hosted nodes autoscaled
([cost_model.out](research/spikes/scale-infra/raw/cost_model.out), confirmed by
[SCA-7 and SCA-11](research/verification/scale-infra.md)). Rows in bold are the three in D12.

| Identities x browser hours per day | Self-hosted Steel | Steel Cloud + our workers | Browserbase + our workers |
|---|---:|---:|---:|
| **30 x 1** | **$294** | $470 | $359 |
| 30 x 3 | $405 | $644 | $597 |
| 100 x 1 | $639 | $893 | $852 |
| **100 x 3** | **$1,007** | $1,662 | $1,741 |
| 1,000 x 1 | $4,724 | $6,537 (custom) | $7,137 (custom) |
| **1,000 x 3** | **$8,413** | $13,949 (custom) | $15,749 (custom) |

What makes up the self-hosted number (same source and `estimate` label; rounded; storage under $12 left out):

| | Nodes | Control plane | Proxies | Models (mix A) |
|---|---:|---:|---:|---:|
| 30 x 1 | $122 | $53 | $90 | $29 |
| 100 x 3 | $358 | $83 | $275 | $290 |
| 1,000 x 3 | $2,720 | $283 | $2,500 | $2,900 |

At 1,000 identities proxies plus models are 64% of the bill at 3 hours a day and 73% at 1 hour a day,
as D12 says. At 30 identities they are 40%. One always-on browser per identity for contrast: about
$19,400 at 1,000 x 3, and 1,000 always-on browsers need about 1,850 GiB of RAM
([SCA-7](research/verification/scale-infra.md)).

**How to read it (the caveats are large).**

1. **It is an all-browser upper bound.** The table sizes every identity as needing a browser for the
   stated hours. Under API-first (section 3.1) most social identities need little or none. The share of
   identities that need a browser at all is the real driver, and nobody has estimated it
   ([C-17](research/verification/CONSISTENCY.md)).
2. **It leaves out costs that exist:**
   - X API fees: $0.015 per post, **$0.20 per post with a URL**, $0.015 per DM
     ([SP-4](research/verification/social-platforms.md)). As arithmetic only, 1,000 accounts making 3
     link posts a day would be $600 a day. The "3 a day" is an invented workload; the point is that one
     link post on X ($0.20) costs far more than the model and browser cost of the same action.
   - The 31-second hold before every sleep (container time), the CPU of the in-browser URL guard, and
     the one-client-per-node rule, which means about 7 identities per node (**pending Q-13**)
     ([C-03, C-25](research/verification/CONSISTENCY.md)).
   - Engineering and fork upkeep, anti-detect licences if bought (4 to 30% of base, Kameleo 35 to 51%),
     and connector and app-review work.
3. **The model line is soft.** Its 40% "cached" share assumes our own replay cache, which is unbuilt
   (Stagehand has none on Steel), and whose record format depends on which executor an identity runs
   (section 3.2). It prices a System 1 decision at 1,000 tokens, where 4,911 to 6,217
   were measured: the dollar effect is small (about $0.0002 to $0.00026 a step on Jev), but any
   capacity sizing built on it is 5 to 6 times too small. About $1,566 of the $2,900 at 1,000 x 3 comes
   from an unsourced planner guess ([SCA-11](research/verification/scale-infra.md)).
4. **Sizing inputs are estimates.** A browser slot of 1.5 GiB (plus 0.35 GiB for the agent) and 7 slots
   on a $96 droplet. Measured memory was 0.65 to 0.85 GiB on light pages and up to about 1.3 GiB under
   task load. The 16-hour active window and 2x peak factor have no source. Nobody has soak-tested a
   1-to-3-hour session ([SCA-5, SCA-7](research/verification/scale-infra.md)). Cold wake was 11.7 to
   21.6 s as a chain of parts on arm64; treat it as a floor ([SCA-6](research/verification/scale-infra.md)).
5. **Vendor rows are not like for like.** Browserbase is browser time only: its bring-your-own static IP
   is not modelled. Cheaper plans were skipped (Browserbase Developer would give $116 instead of $139 in
   browser time at 30 x 1; Steel Launch would put Steel Cloud nearer $310 at 30 x 1). At 30 x 3,
   Browserbase ($597) is dearer than self-hosting ($405 to $518). Steel Cloud's stealth browser is
   Enterprise-only, and its self-serve dedicated IPs stop at 25
   ([SCA-11, SCA-13](research/verification/scale-infra.md)).
6. **The ranking is robust.** Even with a 3 GiB slot (4 per node), self-hosting stays cheapest
   (about $10.3k at 1,000 x 3), because vendor hour rates are about 3 times the node cost
   ([SCA-11](research/verification/scale-infra.md)).
7. **Droplet billing details:** v5 droplets bill $0.1953 an hour for the same shape with no monthly cap;
   at most 10 droplets can be created at once; the account's own droplet limit was never checked
   ([CONSISTENCY.md](research/verification/CONSISTENCY.md) D12 notes).

Replace every row with M1 and M6 measurements before budgeting. **Pending Q-06** for the spend caps.

Evidence: [scale-infra dossier](research/dossiers/scale-infra.md) with
[verification](research/verification/scale-infra.md); D12 in [DECISIONS.md](DECISIONS.md).

### 3.6 The Gemini document's error rate

**Short answer.** Do not build from it. We checked 124 specific claims against dossiers, source, docs and
live calls ([GEMINI-AUDIT.md](research/verification/GEMINI-AUDIT.md)):

| Verdict | Claims | Share |
|---|---:|---:|
| Confirmed | 33 | 27% |
| Partly right | 48 | 39% |
| Wrong | 26 | 21% |
| Could not be checked | 17 | 14% |

Roughly one claim in four survived untouched, and one in five is flatly wrong. **What held up:**
separating the router from the execution sandbox; Stagehand and Browser-Use in the roles the brief
gave them; the idea that decision models only choose and cannot extract; the Steel Cloud Python SDK call
shapes; Steel's 30-day profile expiry; one dedicated ISP proxy per account; the E2B and Cua descriptions;
and the sample router and SQL (they run).

**The errors that would have hurt most:**

1. **Stagehand call shapes are not real.** `Stagehand(env="BROWSERBASE", cdp_url=...)`, `init()`,
   `.page` and `extract(schema=...)` all fail on 4.2.0. The real entry is `Stagehand.create(browser=...,
   model=..., self_heal=False)`.
2. **"Cached selectors, $0 replay" is false on Steel** (section 3.2).
3. **Steel Cloud features were credited to the self-hosted Steel we run:** Profiles, `useProxy`, CAPTCHA
   solving, stealth, 1,000-way concurrency. Self-hosted Steel strips those fields and returns 200.
4. **The Jev endpoint and request shape were invented.** `api.typesafe.com/v1/jev/decide` does not
   resolve. The real call is `POST https://api.typesafe.ai/v1/systemone`.
5. **System 1 economics were unsourced or wrong:** "$0.00 to $0.02 per million tokens" (real: $0.02 to
   $0.24), a 0.85 confidence threshold, a "70% saving". Confidence is not portable across models.
6. **"browser-use uses LiteLLM/LangChain" is false,** and its sample would not run.
7. **Persistence and identity were overstated.** Steel does not store fingerprints permanently; Browserbase
   has no sticky IP and no Context export; a cookie set under 30 s before release is lost.
8. **"Under 50 ms" spin-up** is Browser-Use's API returning HTTP 202 after queuing a task. Browser
   readiness was 6.5 to 11 s to create on a restored profile on arm64.
9. **The social-account blueprint ignores platform terms,** and its Redis lock (`SET key NX EX 600` with
   no value) never excludes anyone.
10. **Stale vendor and model facts:** Claude 3.5 and 3.7 Sonnet are retired; Hyperbrowser and Browserless
    rows are wrong; CUA-S1 is a 706,048-parameter forms-only research model that scored 29.3% out of
    catalogue.

**Why it failed this way.** It treats Steel Cloud and the open-source steel-browser as one product. It
describes Stagehand v3 behaviour under a v4 name. Its numbers carry no source. And it does not see terms
of service.

**One caveat on the audit itself.** It predates two later corrections. Its row 7.06 still gives the
GLM runaway rate as about 3%; the verified figure is 7.5 to 7.7% on click acts
([REA-3](research/verification/reasoning-models.md)). Its row 11.01 quotes 15 to 20 s cold wake; the
verified figure is an 11.7 to 21.6 s composite floor on arm64
([SCA-6](research/verification/scale-infra.md)). The Gemini file stays a hypothesis list
([BRIEF.md](research/BRIEF.md)); nothing from it is carried forward without a primary source or a
measurement.

### 3.7 Process and exposure findings

Findings about how the research was done, and about things already exposed. Several are yours to act on
(section 1).

- **Process note.** Some early spikes ran a browser on the maintainer's workstation instead of a
  container. The data is usable, but the Stagehand end-to-end proof and the model latencies came from
  local Chrome, not from Steel ([CONSISTENCY.md](research/verification/CONSISTENCY.md) §7). No container
  or browser work is planned on the workstation; hands-on work waits for a droplet.
- **Public companion repos are reviewed separately.** A separate exposure question is tracked privately
  (details withheld). `box-kit`'s export publishes the whole box repo
  publicly. It is manual, so the leak happens when someone exports a ref containing `fleet/`, and this
  branch already tracked 1,736 `fleet/` files when that was checked. Its unanchored excludes would also strip `fleet/**/skills`
  while publishing the rest ([EA-11, M-10](research/verification/existing-assets.md)). **Pending Q-09,
  Q-10.**
- **Client data goes to third parties.** Logged-in page text, DMs included, and screenshots go to
  OpenRouter-routed model providers and up to four System 1 vendors. This is your decision, not an
  engineering one (**pending Q-07**).
- **The Jev Workforce trial is a narrow door.** The only no-code route is the owner adding the MCP server
  through the integrations call (HTTPS only, employee paused, 90 s tool timeout, 20 s connect). Plugins do
  not load there. Skills arrive as owner-approved prose guides of up to 6,000 characters, and the trial
  appends a fixed instruction that restricts execution to its own procedure tool and forbids shell scripts and external outreach
  ([HP-5](research/verification/hermes-packaging.md); **pending Q-11**). Once connected, the trial allows
  every tool on the server, so the fleet service enforces scopes itself.
- **Token hygiene.** At the trial's Hermes pin an unset `${VAR}` is sent literally as the bearer token, so
  the fleet service rejects any token that looks like `${...}`. Never export `BROWSER_FLEET_TOKEN`
  host-wide ([HP-1](research/verification/hermes-packaging.md)). Profiles are not a sandbox; a
  prompt-injected agent may be able to read a sibling profile's token (untested, missed issue 5).
- **Every measurement is arm64.** DigitalOcean droplets are amd64. Re-measuring is a dependency for M1,
  not a nicety (O-17).
- **The box itself overclaims in one place.** Its `session` card says it keeps cookies and a profile
  across calls, which holds only within one Steel lifetime. That is the box owner's fix and was reported,
  not changed ([existing-assets dossier](research/dossiers/existing-assets.md) risk 3).

## 4. Where this file differs from the decision record

I followed [DECISIONS.md](DECISIONS.md). These are the places where I found it wrong, incomplete or
ambiguous. I did not edit it.

1. **Question numbering collides with the consistency review.** DECISIONS Q-13 is cross-client
   unlinkability; the review's Q-13 is a workstation housekeeping question. DECISIONS Q-14 is consent-based lead
   channels; the review's Q-14 is a client-risk question. I used DECISIONS numbering.
2. **DECISIONS has no question for the workstation housekeeping item.** I added it as a separate
   row in section 1. [MILESTONES.md](MILESTONES.md) also notes an item DECISIONS dropped.
3. **D8 puts the Browser-Use 9 of 9 runs under "local Chrome on a Mac".** Those nine ran against
   self-hosted Steel in an arm64 container ([BRO-1](research/verification/browser-use.md)). Only the 6 of 6
   live runs, the Stagehand end-to-end proof and the latency numbers were local Chrome
   ([REA-9](research/verification/reasoning-models.md)).
4. **D3's "pinned now" list is firmer than the evidence.** Locale was never measured (every spike run was
   en-US), and the recipe that replaces `--lang` on Linux (`LANG`, `LANGUAGE`, `--accept-lang`) is untested.
   The viewport can be pinned but Steel's reported screen stayed 800x600
   ([SCA-3](research/verification/scale-infra.md)). Stability of a pinned user agent was seen across 2
   sessions ([STE-10](research/verification/steel.md)).
5. **D1's "tested" token isolation covers separate processes only.** The hands-on used one `hermes -p`
   process per profile; the multiplexed gateway path was read from source ([HP-1, X-3](research/verification/hermes-packaging.md)).
6. **D17 and the milestone labels need definitions.** D17 refers to a "fleet charter", and DECISIONS names
   M1, M3, M4 and M6 without defining them. [CHARTER.md](CHARTER.md) and [MILESTONES.md](MILESTONES.md) now
   exist as drafts. I used only the labels DECISIONS attaches (M1 droplet re-measurement, M3 model
   provider gate, M4 channels).
7. **An addition, not a disagreement:** report the decider's own share (rung L2) separately from the
   no-generative-call share (Q3).
8. **D5 and D6: the M1 executor choice is bigger than D6 said. Resolved by D18.** D6 framed it as the
   L1/L2 executor per site class. The stress test ([S14](research/scenarios/S14.md), gaps S14-3 and S14-8)
   showed that on logged-in accounts the same choice also decides whether L3 has an engine, what format
   the replay cache uses, and who enforces the rule that DMs never reach a model. It asked for two
   amendments: define L3 as "a model call that chooses among structured candidates, executed by the
   identity's executor", and set the executor by identity kind first (`research` identities may keep
   Stagehand) with a site-class override. DECISIONS adopted both after this file was first written (D18, with
   edits to D5 and D6), and this file now follows D18. The default for `account` identities is the minimal CDP
   executor; whether uninstall-after-session makes it unnecessary, or another executor wins a site class,
   is still the M1 result (gate G1.4, O-02). I did not edit DECISIONS.

A note on the consistency review: it says it found no source for "38 GLM endpoints from $0.04" (D8 section
of CONSISTENCY 3b). The Stagehand verification does give it: 38 endpoints on 2026-10-10, from $0.04 per
million input tokens ([missed issue 7](research/verification/stagehand.md)). The reasoning-model
verification gives 33 endpoints from $0.032 a day earlier. D8's "33 to 38" is a correct dated range, and
prices drifted overnight ([reasoning-models verification](research/verification/reasoning-models.md),
"Prices that drifted").
