# Playbook: lead generation (consent channels first, then the open-web cascade)

> **Superseded in part (Justin, 2026-10-19; DECISIONS "guardrails, not rules").** Social platforms, people
> lists, named contacts, search pages and live runs on company sites are allowed. Only paid enrichment stays out.

Status: **design, written 2026-10-10 and revised the same day after the scenario stress tests (gap ledger in
section 12). Nothing here is built.** No lead procedure, source registry, consent
ledger, connector or `research` identity exists. What exists is one stdlib spike (tier 0, five public test pages
and one fixture), engine measurements on easy public pages, and a decision record. **No live run on a real
company website has been done, and none is allowed until Justin says so (MS N-4).**

Read with [DECISIONS.md](../../DECISIONS.md) (D2 governs this page; D5, D13, D14, D15 constrain it) and
[CHARTER.md](../../CHARTER.md) (invariant 6, the red lines, "what agents may do"). **Where a dossier and its
verification report disagree, the verification report and DECISIONS win.** This page cites the social-platforms
dossier only for claims the verifier confirmed, or it states the correction.

This playbook is the source for the lead-generation skill (a Hermes shared skill: "self-enrichment through the
agent's own fleet browsing, no paid enrichment services"; `research/dossiers/hermes-packaging.md` §2.5). A first
draft exists as [`fleet-leadgen`](../../hermes/skills/fleet-leadgen/SKILL.md). Where this page and a skill
differ, this page and DECISIONS win.

## How to read this page

| Tag | Meaning |
|---|---|
| `hands-on` | Run in a spike. Public test pages only, small samples, a Mac or arm64. |
| `source-code` | Read in a pinned repo or package. Not run. |
| `official-docs` | Stated on a platform or vendor page. |
| `third-party` | Law-firm notes, blogs, press. Court orders were not read. |
| `design` | The target. Not built. |
| `estimate` | A planning figure with a stated basis. Not a measurement. |
| `to measure` | Unknown. |
| `unresearched` | Named in the research and not studied. Do not write details from memory. |
| `pending Q-nn` / `N-nn` | Depends on one of Justin's questions (Q) or on a decision the milestone plan adds (N, MS §5.4). The text proceeds on the default. |

Source aliases (paths relative to this file):

| Alias | Path |
|---|---|
| DEC | [`../../DECISIONS.md`](../../DECISIONS.md) |
| CH | [`../../CHARTER.md`](../../CHARTER.md) |
| ARCH | [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) (§3.2 identity kinds, §4.3 the act ladder and gate G, §4.4 `extract`, §4.5 `task`, §5.3 the tools, §6.7 hostile content, §6.10 data handling) |
| MS | [`../../MILESTONES.md`](../../MILESTONES.md) |
| SPD / SPV | [`social-platforms` dossier](../../research/dossiers/social-platforms.md) / [verification](../../research/verification/social-platforms.md). The lead material is dossier §2 Q5; the spike is [`research/spikes/social-platforms/`](../../research/spikes/social-platforms/RESULTS.md). |
| SYD / SYV | [`system1-models` dossier](../../research/dossiers/system1-models.md) / [verification](../../research/verification/system1-models.md) |
| SC | [`../channels/social-channels.md`](../channels/social-channels.md) (§7.1 is the closed list of "prior contact or opt-in") |
| SCN | [`../../research/scenarios/`](../../research/scenarios/) (S01 to S14). Gap ids such as S13-11 or G11-13 are those files' own ids. |

---

## 0. The short version

1. **Two parts, in this order.** **Part A:** consent-based lead channels the client runs (Meta Lead Ads, opt-in
   DM capture, LinkedIn Lead Gen Forms, TikTok instant forms). They are official lead sources and keep the
   browser away from the platforms (DEC D2, `pending Q-14`). **Part B:** the open-web cascade for public
   company websites.
2. **The cascade is three tiers.** Tier 0 plain HTTP fetch, then Stagehand `extract` on a known page, then
   Browser-Use exploration. Each tier costs more. The agent climbs only when the **extraction goal was not met**,
   never because of how a page looks (SPV SP-12).
3. **Only `research` identities run it.** An `account` identity never does lead research or plain HTTP, because
   that traffic from a logged-in account's static IP would break continuity (ARCH §3.2, §4.4).
4. **It is read-only.** It never signs in, never submits a form, never sends an email or a message, never
   creates an account. What happens to a lead afterwards is outside the fleet, and cold DMs are never built on
   any platform (section 1.2).
5. **No platform scraping, logged in or out. No platform API as a lead source. No paid enrichment** (Clay,
   Apollo, Hunter, ZoomInfo, Ocean.io or the like). The agent does the enrichment itself with its own browser,
   on public sites (CH red lines; Justin's standing rule).
6. **robots.txt is honoured before every fetch, on every tier.** It is a courtesy rule, not a licence: a source
   site's terms of service still apply (section 1.3).
7. **Every datum carries evidence:** a source URL, a fetch time, the tier used, and the exact quoted text. A
   value that does not appear in the fetched page is rejected (sections 4.2 and 4.3). **A value that appears in
   the page but not in the company's own voice** (a comment, a review, a forum post, any user-written region) is
   not rejected, and is not trusted either. It is stored as `unverified`, with its region noted, and it never
   counts toward the goal (section 4.3, rules 7 to 9).
8. **Roles, not people, by default.** Role-based business contacts (`info@`, `sales@`, a contact page). Named
   individuals are stored only when a flag is on, and the flag is off until GDPR and CCPA are reviewed
   (`N-10`, not researched).
9. **The evidence is thin.** The whole open-web case rests on five public test pages and one author-written
   fixture. Tiers 1 and 2 were never run on company websites. "Most contact data is in static HTML"
   (RESULTS.md finding 1) is **unmeasured**: every live test page returned empty JSON-LD, `mailto:`, `tel:` and
   social lists, and the only populated result is the fixture the author wrote (SPV, "Unsourced numbers").
10. **Lead research is the hardest case for System 1.** The research estimate is that it cannot reach the 90%
    target unless it is narrowed to known sites with selector extractors (SYD step-type table, row "Lead-gen
    research (open web)"; `unverified`, SYV V-05; DEC D7). That is the shape of tiers 0 and 1. Nothing here is a
    System-1-first procedure until measured (MS G3.2).

### Status ledger

| Item | State |
|---|---|
| Tier 0 fetcher with a robots check, JSON-LD and link extraction | One spike script, stdlib only. It still ORs a page-shape rule into its escalation decision, which this playbook drops (SPV SP-12). |
| Goal-based escalation | `design`. Backed by 2 goal checks on 2 pages. |
| Tier 1 and tier 2 on company websites | **Never run.** Engine costs exist for easy public pages only. |
| Source registry, consent ledger, lead record schema | `design` |
| Consent-based lead channels (Part A) | **Named only. Unresearched.** |
| Company discovery (finding the website from a name) | **Open. Not in the research.** Interim rule: owner-supplied domains only, and the profile's own web-search tool is not a discovery source (section 3.10). The research task is MS P3.1, and its table is empty. |
| Trust ranking and region labelling for extracted contacts | `design`. Nothing has run; the region rules are `to specify` (section 4.3). |
| Legal review (GDPR, CCPA, contract terms) | **Not done** (`N-10`) |
| Live runs on public company sites | **Not allowed** until Justin says yes (`N-4`) |

---

## 1. The rules

### 1.1 What is a lead source and what is not

| Source | Allowed? | Why and how |
|---|---|---|
| A consent-based channel the client runs (Part A) | **Yes** (`pending Q-14`) | The person gave details to the client, with consent shown at the point of capture. Consent is recorded. |
| A public company website: about, contact, team and footer pages; `mailto:` and `tel:` links; schema.org JSON-LD (`Organization`, `LocalBusiness`: name, email, telephone, address, `sameAs`) | **Yes**, under section 1.3 | `official-docs`/`hands-on` (SPD Q5; spike). |
| A list of domains or companies the client supplies | **Yes**, `design` | The consent basis is the client's and is recorded on the lead. Not researched. |
| Public registries (company registers, SEC EDGAR) | A natural next source | **Not researched** (SPD Q5). Each registry's terms still apply. |
| Third-party sites: directories, marketplaces, review sites, maps | **Only if the owner approves the source** | Their terms often bar scraping. See the source registry, section 4.5. |
| **Platform scraping** (profiles, followers, groups, ads libraries), logged in or out | **Never** | Meta, Instagram, X, TikTok and LinkedIn terms (section 1.4). A logged-in client identity doing it breaches the contract that client accepted. |
| **Platform APIs as lead sources** (Instagram Business Discovery, X user and post lookups) | **Never** | Meta Platform Terms §3.a.v bars "Processing Platform Data without valid User consent in order to build or augment user profiles for any purpose". X bars "Profiling, tracking, or monitoring users without consent". Business Discovery is for client-facing benchmarking only. At most an API lookup confirms a company's own handle that its own website links to (SPV SP-11). |
| Paid enrichment or bought lists | **Never** | Justin's standing rule. |
| Guessed addresses (name-plus-pattern permutations) and deliverability probing | **Not done**, `[extension]` | This is what enrichment services do. It is outside "public data the company published". Added here, not in DECISIONS. |

### 1.2 What the playbook never does

- Sign in anywhere, hold a credential, or use a client identity.
- Submit a contact form, send an email, send a DM, send a connection request. **A contact form is an outbound
  message**, and outbound messages to people without prior contact or opt-in are a red line (CH). "Prior contact
  or opt-in" is a closed list, and a lead the fleet found is not on it ([social-channels.md](../channels/social-channels.md) §7.1).
- Create an account, solve a CAPTCHA, pay a solver, or use any stealth or proxy-rotation feature to get past a
  block.
- Pass extracted text to anything that acts. Extracted strings are untrusted page text; they are never used as
  publishable content or as instructions (ARCH §4.4; CH invariant 7).

### 1.3 The rules for every fetch, on every tier

1. **robots.txt first.** Fetch and honour it before any other request to a host, for the fleet's bot token and
   for `*`. A disallowed URL is not fetched. It is recorded as `disallowed`. The spike used Python's
   `urllib.robotparser`. How `Crawl-delay` and unparseable files are handled is `to specify`. `design`: the
   check runs in code, before every top-level navigation in tiers 1 and 2 as well as in tier 0. Whether it also
   covers sub-resources is `to specify`.
2. **robots.txt is not a licence.** An allowed path can still be forbidden by the site's terms of service. For
   a company's own website the default is "allowed unless robots.txt or the site says no". For third-party
   sources the owner must approve the source first (section 4.5).
3. **Politeness.** A rate limit per domain, a cache per domain (no refetch of what is already held), and a cap on
   pages per domain. The values are **not sourced and not set** (`to measure`). Start conservative and let the
   owner raise them.
4. **Identify the bot where it is a plain HTTP client.** Tier 0 sends a User-Agent that names the fleet's bot and
   gives a contact URL (SPD Q5). The name is to be chosen.
5. **Stop on a wall.** A login wall, CAPTCHA, `403`, `429` or "unusual traffic" page stops that domain and
   backs off. It is recorded as `blocked`. **No stealth, no IP rotation, no solver.** A blocked `research` IP is a
   signal to stop, not to rotate ([identity-and-proxies.md](../identity/identity-and-proxies.md) §3.1).
6. **Minimise.** Store only the fields the goal asks for. Prefer role-based contacts. Honour opt-outs and
   removal requests.
7. **Provenance with every datum:** the source URL and the fetch time, always (CH red lines).

**The User-Agent tension, flagged.** A pinned browser persona sends a normal Chromium user agent (the fleet pins
a UA that matches the real engine; DEC D3), and a polite bot names itself. Tier 0 is an HTTP client, so it names
itself. For the browser tiers 1 and 2 this is **an open design choice**. A `research` identity has no login to
protect and no reason to pose as a human visitor, so the recommendation is that it also identifies itself
(append a bot token and contact URL to the pinned UA). The risk is that some sites treat an unusual UA
differently, which is `to measure`. The owner decides; until then tiers 1 and 2 stay behind the same robots.txt
and politeness rules whatever the UA says.

### 1.4 The law and the platforms, in short

Not legal advice. Court orders were not read; these come from law-firm notes (`third-party`, SPV V-9).

- *Meta v. Bright Data* (N.D. Cal., 2024-01-23): summary judgment for Bright Data on the contract claim for
  **logged-off** scraping of public data. It says nothing about logged-in identities, and Instagram's terms say
  "regardless of whether ... logged-in".
- *hiQ v. LinkedIn* ended in a $500,000 stipulated judgment and a permanent injunction (December 2022). The
  November 2022 order held that anti-scraping and anti-fake-profile terms are enforceable in contract.
- Each platform's terms bar scraping: Facebook Terms §3.2, Instagram ToS, X ToS ("crawling or scraping the
  Services in any form, for any purpose without our prior written consent is expressly prohibited"), TikTok ToS
  ("extract any data or content from the Platform using any automated system or software that is not provided by
  TikTok or approved in writing by TikTok"), LinkedIn §8.2 (`official-docs`, SPV V-6).
- **GDPR and CCPA** apply to named individuals. They were **not researched** (SPD Q5; `N-10`). They need legal
  review before the client pilot (M6b). Until then: role-based contacts only, source and time with every datum.

---

## 2. Part A: consent-based lead channels `pending Q-14`

### 2.1 Why they come first

Meta, TikTok, LinkedIn and X all bar building lead databases from their users **without consent**. The
prohibitions are conditioned on consent: Meta's §3.a.v says "without valid User consent", X's says "without
consent". Capturing a lead with consent, on the platform's own form or in a DM the person started, is the
sanctioned route and is official (SPV SP-11, "consent-based lead capture ... is an official lead source and is
absent from the dossier"). That is why DEC D2 adds these as first-class options and why the browser stays away
from platform lead scraping. **Plan default: yes, built last in M4, after the core connectors** (MS §4.6.3, §5.1).

### 2.2 The four channels

| Channel | What it is | What the research says | What is unresearched |
|---|---|---|---|
| **Meta Lead Ads** | A lead form on the client's Facebook or Instagram ads, filled in by the person with consent shown at capture | Named as an official consent-based lead source (SPV SP-11). Meta Platform Terms §3.a.v is why consent matters. | **Everything operational:** the permissions and review needed to read leads, how leads are delivered (webhook or polling), the form and consent-text rules, retention rules, EEA specifics, rate limits, any fee. The fleet does not create ads. "Ad or boost actions" are human-approved and not built (SPD Q4 item 7). |
| **Opt-in DM capture** | A person starts a conversation (a DM, a click-to-message ad, a reply to a post) and opts in to be contacted; the reply path collects details with explicit consent in the thread | Platform rules are in [social-channels.md](../channels/social-channels.md) §3. Meta: "Don't contact people in Messenger or Instagram Messaging unless you ... have obtained legally sufficient consent, permission, and/or opt-in". X: a DM is allowed only where the recipient "requested or ... clearly indicated an intent" to be contacted, with an easy opt-out. The fleet's own rule is narrower: it replies only in a conversation the other party started, and on X every reply needs a per-action approval (social-channels.md §3.4.2, §7.1). TikTok: "You are prohibited from initiating a conversation". Windows: Messenger and Instagram 24 hours. The 7-day HUMAN_AGENT tag is off in the fleet (social-channels.md §2.6). | How an opt-in is worded and recorded per platform; whether a captured phone number or email may be used outside the thread; regional rules. |
| **LinkedIn Lead Gen Forms** | A form on the client's LinkedIn ads | Named only (SPV SP-11). | Everything: which API reads the leads, whether the Community Management approval covers it, vetting, fees. |
| **TikTok instant forms** | A lead form on the client's TikTok ads | Named only (SPV SP-11). The Accounts API is organic-only ("Manage the organic presence of brands or creators' owned accounts"). | Everything: whether reading instant-form leads sits in the same approval, what the API is, reviews. |

**Under the Q-07 default, the capture flow cannot use a model to read the thread.** The default is that the fleet
sends no DM content to a model provider, and a System 1 vendor is a model provider (CH invariant 8; see
[social-channels.md](../channels/social-channels.md) §2.3). So an opt-in capture flow is templates, quick-reply
buttons, a fixed menu and deterministic validation, or a human.

### 2.3 What the fleet's role is

- **Ingest and route** leads that the client's own forms and threads produce. Write a consent record first.
- **Never cold-contact.** A consent-based lead may be contacted for the purpose they consented to, by the
  client. That contact is not a fleet capability: no cold DM is ever built, and a follow-up message is a
  reply inside a window or a person's action. **A form submission is the client's entitlement to contact the
  person on the form's terms. It is not a trigger for a fleet DM** (social-channels.md §7.1, entry 4). If the
  person then writes to the client's account, that message is the prior contact.
- **Leads belong to the client.** No lead crosses from one client to another. No lead data is pooled across
  clients (CH invariant 8).

### 2.4 What must be researched before Part A is built

A research task, not a design. Read the platforms' own documentation (not their sites by script). For each
channel, answer:

1. Who can read the leads, with which permission or scope, and what review or approval does that need? Does an
   agency's single app suffice, or does each client's ad account need to grant access?
2. How are leads delivered: a webhook, polling, a download? What is the delivery guarantee, and what happens on
   a duplicate?
3. What consent text must the form show, and what must be stored to prove it?
4. What are the retention and deletion rules, and the regional limits (EEA and UK in particular)?
5. What are the rate limits, fees and ad-account prerequisites?
6. Does Composio already wrap any of these, and whose approval does it ride on (`N-9`)?
7. What does the client's contract need to say (`N-10`)?

Until those answers are in, Part A is a **named dependency with no design**. Do not write endpoint paths,
permission names or field lists for it from memory.

### 2.5 The consent record, and the lead it protects `design`

A lead from a consent channel is unusable until a consent record exists. The plan already has a consent ledger
in the core of M4 (MS §4.6.1, written for X's per-action-type consent). **Using it for lead consent is an
extension.** The record:

| Field | Meaning |
|---|---|
| `lead_id`, `client_id` | Which lead, which client |
| `channel`, `channel_ref` | `meta_lead_ad`, `dm_opt_in`, `linkedin_lead_form`, `tiktok_instant_form`; the form id or thread id |
| `consent_text_hash`, `shown_at` | A hash of the exact consent text shown, and when |
| `purposes` | What the person agreed to be contacted about |
| `opt_out` | State, and when it changed |
| `retention_until` | From the policy once `N-10` is answered |

A lead with no consent record is refused at ingest. (A proposed refusal test for the M4 owner to adopt; MS has
no gate for the consent channels yet.)

---

## 3. Part B: the open-web cascade

### 3.1 What it is for, and the goal object

Part B finds public business contact data on the open web: company websites the owner points it at. It
answers one question per company: **where on the company's own site is the contact data, and what does it say.**
It does not decide who to contact, write outreach or send anything.

Every run starts from a **goal**. The goal is data, not prose, so code can check it:

```jsonc
{
  "seed":      "https://example-co.test/",          // a URL the owner supplied or tier 0 found
  "required":  ["email_or_contact_form", "phone"],   // escalation is judged on these only
  "optional":  ["address", "social_links"],           // recorded when found, never a reason to climb
  "contacts":  "role_only",                           // "role_only" | "named_allowed" (flag, N-10)
  "limits":    { "pages": null, "tier1_calls": null, "task_steps": 8, "task_usd": null }
}
```

`null` limits are `to measure` and have no sourced default. `task_steps` 8 is the fleet's default and 25 its
maximum for `task` (ARCH §4.5). The goal's `required` list is declared per procedure. It is never a regex written
with knowledge of the page, which is what the spike did (section 3.4).

### 3.2 The identity that runs it

A **`research` identity**: no social login (it never logs in to a social platform) and its own dedicated static
IP, like every identity (ARCH §3.2; [identity-and-proxies.md](../identity/identity-and-proxies.md) §1, §3.1). It
has no client account's continuity to protect, which is why the bot-User-Agent question in section 1.3 is open
for it.

- **Why an identity at all.** Tier 0 is plain HTTP through that identity's node-local forwarder, so the target
  site sees one stable, named address, and a block lands on an IP that has nothing else to lose
  (ARCH §4.4 step 2).
- **Why never an `account` identity.** HTTP-client traffic from a client's logged-in static IP breaks the
  continuity goal (ARCH §4.4; DEC D9). Lead research is therefore never done "as" a client's Instagram or
  LinkedIn identity.
- **One per tenant by default.** An identity has a `tenant_id`, spend caps and a data policy that follow the
  tenant (ARCH §3.2), and no lead data is pooled across clients (CH invariant 8). So a client's research runs on
  that client's `research` identity. Whether one agency-internal `research` identity can serve several clients,
  and what that does to the pooling rule, is open (section 8). `design`, not decided.
- **A blocked research IP is a signal to stop, not to rotate** (identity-and-proxies.md §3.1). Whether a
  `research` identity ever needs more than one IP for per-domain politeness at volume is open there too (§9,
  default: no).
- **Not built.** No `research` identity has been created. The spike ran from the Mac with no proxy and no
  identity.

### 3.3 The three tiers

| Tier | What runs | Model calls | Evidence for cost and speed | Where it can go wrong |
|---|---|---:|---|---|
| **0. HTTP fetch** | robots.txt check, one GET (15 s timeout, 2 MB cap in the spike), deterministic parse: schema.org JSON-LD (`Organization`, `LocalBusiness`), `mailto:`, `tel:`, links to the company's own social profiles, contact/about/team/impressum links | 0 | 70-344 ms and $0 per page over 12 fetches of 5 public test pages, from the Mac, no proxy (`hands-on`, n=5 pages, RESULTS.md; SPV SP-12). The fixture gave every field in one pass. | Does not run scripts. A page that builds its content in JavaScript returns little. |
| **1. Stagehand `extract`** | A `research` identity woken. Navigate through the guard to a **known page** (tier 0 or the owner supplied it). `extract(instruction, schema)` scoped with a `locator`. | 2 (Extraction, then Metadata) | 2.0 s, 2,403 in / 178 out tokens, about $0.00026 on one easy page (`hands-on`, [stagehand.md](../engines/stagehand.md) §5.1). Orders of magnitude only: a provider change moves cost about 3x. **Wake time for a `research` identity is not measured.** | The model reads untrusted page text. Dense pages cost more (`to measure`). Never run on a company page yet (N-4). |
| **2. Browser-Use `task`** | Same identity. `task` in `read_only` mode, `flash_mode`, capped `max_steps` (default 8, maximum 25), `allowed_hosts` enforced by the fleet's guard, `upload_file`, `save_as_pdf` and `evaluate` removed (ARCH §4.5). | Many | Easy public pages on Steel: about $0.0013 to $0.0033 per task (`hands-on`, [browser-use.md](../engines/browser-use.md) §16). A separate median of 4 steps and $0.0024 per task came from two trivial tasks on local Chrome on the Mac, a method now banned, so it is not Steel data. **Dense-page estimate:** a 20-step run could reach about $0.04 (estimate, same section). | Wandering, loops, injected instructions. The hardest case for the deciders: the research estimate for lead-gen research is "well below 90%" System-1 share (`unverified`, DEC D7; SYV). |

A tier-0 fetch can also be a plain **API-free read of a single URL the owner names**. That is the same tier.

**Cost arithmetic, an estimate on easy pages only.** If a tier-1 call costs about $0.00026, 1,000 tier-1 pages
cost about $0.26 in model fees. If a tier-2 task costs $0.0013 to $0.0033 (the Steel range above), 1,000 tasks
cost about $1.30 to $3.30. Neither figure
includes wake time, node time or the IP (identity-and-proxies.md §3.8), and neither has been measured on a
company site. They show the *ratio* between the tiers (tier 0 is free and fast; the browser tiers cost
money and seconds), which is why the order matters.

### 3.4 Escalation: keyed on the goal, not on the page's shape

**The rule `design`.** After each tier, ask one question: **are the goal's `required` fields met, with evidence
that survives the grounding check (section 4.3)?** Yes: stop. No: climb, within the limits below. Code answers
the question. A model never decides whether it succeeded (ARCH §4.4 step 5, §4.3 gate G).

**Only a verified value meets a field.** A value is verified when its trust rank is `structured` or
`contact_block`, or `free_text` with a registrable-domain match (section 4.3, rules 7 and 9). An `unverified`
value never meets a required field. So a planted address cannot end the cascade early, and cannot turn a
`goal_unmet` into a `met` (SCN S13-11).

**Why not page shape.** Both shape rules misfired in the spike:

| Rule | Result |
|---|---|
| v1: thin text and 3 or more scripts | Missed the JavaScript-only page `quotes.toscrape.com/js/` (65 characters of text, 2 scripts): false negative |
| v2: thin text and any script | Flagged `example.com` (324 characters, 1 script): false positive. The verifier found a second false positive on `the-internet.herokuapp.com/add_remove_elements`: static, 142 characters, 7 scripts, flagged `true` |
| Goal check: a regex the author expected in the static HTML | Right on both quote pages (absent on `/js/`, present on the static page) |

Read this with the verifier's corrections (SPV SP-12; label: **`hands-on`, n=5 pages, indicative, not proof**):

1. The goal check ran on **2 pages**, one fetch each. v1 and v2 were tuned after seeing the miss.
2. The goal regex was written by the author knowing the page. "Correct" is circular for sites nobody has seen.
   A field-presence goal (`email_or_contact_form`) is what unknown sites need, and it has **not been run**.
3. The third run does not isolate the goal signal: the v2 shape rule alone gave the same answers on those two
   pages.
4. The goal check was never run on `example.com`, the page where v2 failed.
5. **The committed script still ORs the shape rule into its decision.** Its `needs_browser` is
   `(text<400 and scripts>=1) or spa_root or expect_missing`. So `--expect 'Example Domain'
   https://example.com/` still prints `needs_browser: true`. The script does not implement the rule above. It must
   drop the shape term before the cascade follows this playbook.

So: the direction is plausible and consistent with the data. "Must" is not proven.

**The climb, as a table `design`:**

| Situation after a tier | Next step |
|---|---|
| robots.txt disallows, or a wall (login, CAPTCHA, `403`, `429`, "unusual traffic"), or a redirect off the company's domain | **Stop that domain.** Record `disallowed` or `blocked` and the trail. No further tier. Section 3.8. |
| Required fields met | **Stop.** Record the tier that met them. |
| Not met, and the fetched HTML links to contact, about, team or impressum pages on the same domain that are not fetched yet | Tier 0 on those pages, up to the page limit. |
| Not met on every fetched page, and at least one is a **known page** (a contact, about or team page: owner-supplied, or found by a link) | Tier 1 on the best known page. One `extract` per page. |
| Tier 1 returns nothing grounded | **Stop with `goal_unmet`.** A site with no published contact data is an answer, not a failure to retry. |
| Not met, and there is **no known page** (no such link, no JSON-LD, only a front page) | Tier 2 `task`, `read_only`, `allowed_hosts` = the company's domain, capped steps and spend. |
| Tier 2 reaches its cap without meeting the goal | **Stop with `goal_unmet`.** No retry on a stronger model. Record the trail. |

**Two cheap diagnostics**, so the cascade improves itself without trusting a model:

- When tier 1 or 2 finds a value, check whether the same quote appears in the **tier-0 static HTML** of that
  page. If it does, the tier-0 parser missed something it could have read: log a parser gap and, where the
  pattern repeats, add it to the deterministic parser or to a stored per-site extractor. If it does not, the page
  really needed scripts. Record both as `static_contains_quote: true|false` on the evidence entry.
- A successful tier-1 or tier-2 run may propose a **per-site extractor** (ARCH §4.4 step 4, §4.5 `proposed_procedure_id`).
  A proposed procedure stays in quarantine until owner-accepted outcomes release it (DEC D13). Who the owner is
  for that is undefined (N-5).

### 3.5 Tier 0 in detail `design`, with one spike behind it

1. Look up the domain in the **source registry** (section 4.5). Stop if it is `disallowed` or `blocked`, or if it
   is a third-party source the owner has not approved.
2. Fetch and cache `robots.txt` for the host. Evaluate the fleet's bot token and `*`. A disallowed URL is
   recorded and not fetched.
   - The spike treated an *unreadable* `robots.txt` as **allow** (its own message: "robots.txt unreadable ->
     treated as allow"). A network error is not permission. The design default is: on a network error or a `5xx`,
     do not fetch, record `robots_unavailable`, and retry later within the politeness rules. `4xx` handling and
     `Crawl-delay` follow RFC 9309, which is **not in the corpus**: read it before building (`to specify`).
3. One GET, through the identity's forwarder, with the bot User-Agent (section 1.3), the size cap and the timeout.
4. Parse with deterministic code only: JSON-LD, `mailto:`, `tel:`, links, visible text. No model reads the page.
   Label every value with the page region it came from: a JSON-LD block, the header, the footer, a contact
   block, main content, or a user-generated region (section 4.3, rules 7 and 8).
5. Apply the goal check and the grounding check. Record evidence for every value (section 4.2).
6. Follow same-domain contact, about, team and impressum links within the page limit. **Do not follow links to
   platform hosts** (`facebook.com`, `instagram.com`, `linkedin.com`, `x.com`, `twitter.com`, `tiktok.com`,
   `youtube.com` are the spike's social list). Record them as `social_links` (URLs only).

### 3.6 Tier 1 in detail `design`, nothing run on a company site

- The caller uses the fleet `extract` tool (read-only; submit then poll; ARCH §4.4, §5.3 tool 7): `identity` (a
  `research` alias), `instruction`, `schema` (JSON Schema, at most 20 KB), `url`, `via`, `locator`, `screenshot`.
  Errors: `goal_unmet`, `identity_busy`, `infra_unavailable`, `budget_exhausted`, `invalid_arguments`.
- `via: auto` (default) starts at tier 0 for a `research` identity, then climbs. `via: http` is allowed only on
  a `research` identity.
- Scope the call with a `locator` (for example the footer or the contact block) to cut tokens and to keep the
  rest of the page away from the model ([stagehand.md](../engines/stagehand.md) §5.6). Use `screenshot: true`
  only when the accessibility tree lacks the data.
- **Keep user-generated regions out of the model's view.** Tier 0 has labelled them (section 4.3, rule 8). The
  tier-1 call passes them as `ignoreLocators`, which removes each match and its descendants from the tree the
  model reads ([stagehand.md](../engines/stagehand.md) §5.2). This is a filter on input. It does not replace the
  grounding check, which still looks up the region of every returned value in the stored source.
- The model shim validates the output against the caller's schema (ARCH §4.4 step 4). Then **the grounding check
  runs over the result**, and an ungrounded value is dropped.
- **Data handling `pending Q-07`.** Tier-1 and tier-2 calls send the text of public company pages to a model
  provider. The plan says "other pages go only to the allowlist" (MS §4.5, Needs from Justin, Q-07 row; CH
  invariant 8 words it for logged-in page content), and the plan default also requires per-client consent and
  ZDR routing. Public company pages carry no client DMs
  and no logins, which is why this is the lighter end of Q-07, but the allowlist still applies.

### 3.7 Tier 2 in detail `design`

- It is the `task` tool in `read_only` mode (ARCH §4.5, §5.3 tool 8). Gate G applies to every action before it
  runs. The positive allow-list lets it navigate, scroll, find, extract, click links with an `href`, use tabs and
  disclosure widgets, dismiss dialogs and type into search boxes. ARCH §4.3 states the refusal ("anything else
  ... is refused as `needs_approval`") for **platform hosts**. This playbook requires the same allow-list on
  company sites `[extension]`.
- **Lead generation adds three rules on top of that allow-list:**
  1. **No form submission of any kind**, including a site's contact form, a newsletter box and a search form
     that posts. The allow-list permits typing into a search box, but submitting a search is a form post. So
     search boxes are **not used** on company sites by default (open item 12, section 8). The deny-list classifier
     is a backstop only and **fails open on unlabeled icon buttons** (ARCH §4.3). So the rule is enforced by
     *not granting* `publish` and `dm` scopes to the token, and by gate G's allow-list. Its miss rate on real
     pages is `to measure`.
  2. **`allowed_hosts` is the company's registrable domain.** The guard and the network rule enforce it.
     Browser-Use's `allowed_domains` is not a boundary (issues #5815 and #4763; ARCH §4.5 step 4). A navigation
     to a platform host is refused, in the same code path as the G4.6 "platform scraping for leads" refusal.
  3. **The cap is the contract.** `max_steps` default 8, maximum 25; the hard kill timer; `max_usd`. A cap hit is
     `goal_unmet`, never a retry with more steps.
- `use_judge` is off. The judge is a model's opinion; the goal check and the grounding check are the verifiers
  (browser-use.md section 5).
- **Evidence:** every step streams to fleetd with its cost (ARCH §4.5 step 5), and the trace is attached to the
  job as evidence. The `answer` that Browser-Use writes is never a lead value by itself. A value counts only if
  it passes the grounding check against a fetched page or snapshot from the same run.

### 3.8 When the site says no, or a wall appears `design`

| Signal | What the playbook does |
|---|---|
| robots.txt disallows the path | Not fetched. Record `disallowed` with the rule matched. |
| Login wall (a sign-in form where content should be) | Stop. Record `login_wall`. **Never sign in. Never create an account.** |
| CAPTCHA, "verify you are human", a challenge page | Stop. Record `captcha`. **Never solve one**, and never switch on a solver or a stealth feature. CH invariant 4 states this for client accounts. This playbook applies the same rule to `research` identities `[extension]`. A Browserbase-homed `research` identity sets `solveCaptchas:false`, which DEC D11 states and `identity create` checks (ARCH §4.15; section 9). |
| `403`, `429`, "unusual traffic" | Stop that domain, back off, and set a cool-down in the source registry. `Retry-After` is honoured when present. **No IP rotation, no proxy change, no User-Agent change to get through.** |
| Redirect off the company's domain | Stop. Record `off_domain`. Do not follow it. |
| A page asks for consent or cookies | Read what is shown without accepting tracking where the page allows it; if the content is behind the choice, record `consent_wall` and stop. (`to specify`: no cookie banner behaviour has been tested.) |
| Paywall or "members only" | Stop. Record `paywall`. |

A stopped domain is **not an error for the run**. The run still returns the other domains, and the stopped one is
listed with its reason. After a wall, the owner decides whether to ask the site for permission. The fleet does
not try again by itself.

### 3.9 Untrusted text

Every string the cascade reads is untrusted (ARCH §4.4 step 6; CH invariant 7).

- A page that says "email our CEO at ... to get a discount" or "ignore your instructions" is data. The cascade
  extracts values and never acts on page text. G3.7 (MS) tests this on `act`, `task` and `run`.
- **A value that is on the page is not therefore the company's.** "Email our CEO at ceo@look-alike.test" typed
  into a comment is grounded, because the text is there, and it is still not the company's. Grounding proves
  only that the page says it. The trust rank (section 4.3) decides whose voice it is (SCN S13-11).
- An extracted value is **never** publishable content and never reaches a connector. It goes into a lead
  record and an Obsidian note, and nowhere else (CH invariant 7: publishable content comes only from a manifest
  item or an approved draft).
- Hidden text, `display:none` content and off-screen text are not trusted more than visible text. Whether to
  extract from hidden elements at all is `to specify`; the default is visible text and structured data only.

### 3.10 The discovery gap: an interim rule, and the research task

**The gap:** the research says how to read a known company site. It does **not** say how the agent finds the
site. "Find companies that match X" is the step before the cascade, and nothing in the corpus, the dossiers or
the verification reports covers it. This playbook does not invent an answer. The profile will keep being asked
the question (SCN G11-13), so the page says what to do until the answer exists.

What the rules already allow as a *starting list*:

- A domain or company list the owner supplies. The consent basis is theirs and goes on the lead.
- A consent-captured lead's own website field (Part A feeds Part B). The purpose and notice for that second use
  is a legal question (`N-10`).
- Public registries (company registers, SEC EDGAR), a natural next source that is **unresearched** (SPD Q5).
  Each registry's terms apply (section 1.1).

What is not allowed as discovery: scraping a platform, scraping a search engine's results pages, or buying a
list or an enrichment lookup (section 1.1). Whether any search engine offers an official API on terms that fit
(no scraping, an acceptable price, results usable for lead research) is **not researched**.

**The profile's own web-search tool (interim rule).** A Hermes profile has a web-search tool of its own. It
sits outside the fleet: `fleetd` does not see its calls, cannot apply the host policy to them, and holds no
record of what they returned. So the rule below is a rule of the skill. It is not enforced in code.

1. **It is not a discovery source.** A search tool returns search-engine results in another shape. Whether any
   search service offers terms that fit is not researched.
2. **It can become one only as a row in the source registry** (section 4.5): kind `third_party`, with a
   `terms_note`, and `approved_by` and `approved_at` set by the owner. A row with an unknown answer is not
   approved (MS P3.1).
3. **The profile reports the gap and does not improvise.** Asked to find companies with no domains, it says:
   discovery is owner-supplied domain lists only until the source table is approved. It names the research
   task (MS P3.1, gate G3.12), and offers the allowed routes: send domains, or use a consent-based channel
   (Q-14). It makes no fetch and no model call for this.
4. **A domain the profile found by its own search is not an owner-supplied domain.** It must not be recorded as
   `basis: owner_list`, because the consent basis there is the owner's (section 4.1).
5. **The `fleet-leadgen` skill carries the same sentence.** It already refuses name-only lists and bars the
   profile's own web-search tool as a fill-in
   ([SKILL.md](../../hermes/skills/fleet-leadgen/SKILL.md), "Before anything: the gates"). If the two ever
   differ, this page wins.

**The research task, as a table to fill in.** MS P3.1 is the named prerequisite for name-only lead intake. It
is desk work with no droplet, owned by the lead-gen playbook author, and it blocks only name-only intake. Its
output is the table below, in the source-registry format of section 4.5. A `third_party` row also needs
Justin's approval before it is used (N-4 widens to cover it).

| Candidate | Operator | Terms for automated access (quote and URL) | Official API? | Price | Fields | Lead use allowed? | `kind` | `state` |
|---|---|---|---|---|---|---|---|---|
| Public company registers (one row per country) | The national or state authority | unresearched | unresearched | unresearched | unresearched | unresearched | `registry` | not approved |
| SEC EDGAR | A US federal agency | unresearched | unresearched | unresearched | unresearched | unresearched | `registry` | not approved |
| An official search API, if one exists on terms that fit | unresearched | unresearched | unresearched | unresearched | unresearched | unresearched | `third_party` | not approved |
| A consent-captured lead's own website field | The client (Part A) | n/a: the client's own record | n/a | $0 | The website field on the consent record | Yes for the purpose consented to. A second use is a legal question (`N-10`) | n/a (basis `consent_lead`) | usable once Part A exists |

Rules for a row: no source whose data comes from a paid enrichment or a bought list, whatever its price. No row
that needs scraping a search engine's results pages or a social platform. Quote the terms from the source's own
page and give the URL and the date read. Do not fill a cell from memory.

**Why the table is empty on this page.** Each cell needs a quote read from the source's own page. The corpus
holds none of them, and this page's rule is not to write a source's terms from memory (`unresearched`, "How to
read this page"). The task has its own gate: G3.12 feeds the lead procedure four lists and expects a name-only
list to be refused until the table exists and a `third_party` row has `approved_by` set. The task needs a reader
with access to the sources' own pages. Until it is done, discovery is owner-supplied domain lists only.

---

## 4. Records

### 4.1 The lead record (output schema) `design`

One record per company per run. Every value in it has at least one evidence entry. A value with no evidence is
not in the record.

```jsonc
{
  "schema":    "lead.v0",
  "lead_id":   "ld_...",                       // hash of tenant_id + registrable domain: the dedupe key
  "tenant_id": "...", "job_id": "...", "run_at": "<ISO time>",
  "basis":     { "type": "owner_list|consent_lead|registry", "ref": "...", "recorded_at": "<ISO time>" },
  "company": {
    "domain": "example-co.test",
    "name":   { "value": "Example Co", "evidence": ["ev1"] }
  },
  "contacts": [                                  // verified values only (section 4.3, rules 7 to 9)
    { "kind": "email", "role": "sales", "value": "sales@example-co.test",
      "domain_match": true, "trust": "contact_block", "region": "footer", "evidence": ["ev2"] },
    { "kind": "phone", "value": "+15555550100",
      "trust": "structured", "region": "jsonld", "evidence": ["ev3"] },
    { "kind": "contact_form", "url": "https://example-co.test/contact", "evidence": ["ev4"] }
  ],
  "unverified": [                                // on the page, but not in the company's own voice
    { "kind": "email", "value": "ceo@look-alike.test", "domain_match": false,
      "trust": "unverified", "region": "ugc:comments", "reason": "user_generated_region",
      "evidence": ["ev7"] }
  ],
  "address":      { "value": "...", "evidence": ["ev5"] },
  "social_links": [ { "platform": "linkedin", "url": "https://...", "fetched": false, "evidence": ["ev6"] } ],
  "withheld":     { "named_contacts": 2 },     // a count only, when contacts = role_only
  "goal": {
    "required": ["email_or_contact_form", "phone"],
    "met": true, "missing": [],
    "status": "met|goal_unmet|blocked|disallowed|robots_unavailable"
  },
  "trail": [
    { "tier": 0, "url": "https://example-co.test/", "outcome": "linked_contact_page" },
    { "tier": 0, "url": "https://example-co.test/contact", "outcome": "met" }
  ],
  "evidence": [ /* 4.2 */ ]
}
```

- `contact_form` records that a form exists and where. **The playbook never fills it** (section 1.2).
- `unverified` is a separate list so that nothing downstream mistakes a planted value for a contact. A value in
  it never counts toward `goal.met`, and it is shown to the owner with its region noted. It is not a lead
  value. An address found only in a comment, a review or a forum post lands here, whatever its domain.
- `social_links[].fetched` is always `false` (section 1.2).
- `status` explains a record that is not `met`. A `blocked` or `disallowed` record still goes out, with its
  trail and no values.
- **Dedupe.** `lead_id` is per tenant and domain. A second run on the same domain updates the same record:
  new evidence is added, unchanged evidence keeps its first `fetched_at`, and a value that no longer appears is
  marked `not_seen_at` with the time, not silently deleted. A lead is never merged across tenants.
- This is the lead-generation skill's "output schema, dedupe, storage" (`research/dossiers/hermes-packaging.md`
  §2.5; first draft: `hermes/skills/fleet-leadgen`). The skill is read-only: it never writes to a connector.

### 4.2 The evidence entry `design`

```jsonc
{
  "id": "ev2",
  "source_url":   "https://example-co.test/contact",
  "fetched_at":   "<ISO time>",
  "tier":         0,                               // 0, 1 or 2
  "method":       "mailto|jsonld|tel|selector|stagehand_extract|browser_use",
  "quote":        "sales@example-co.test",        // the exact text, at most 200 characters
  "quote_where":  "href|text|jsonld:email|snapshot",
  "region":       "footer",                        // jsonld | header | footer | contact_block | main | ugc:<marker> | unknown
  "region_path":  "footer > p:nth-of-type(2)",     // where in the stored source the quote was found
  "content_sha256": "...",                         // of the bytes or snapshot the quote was found in
  "static_contains_quote": true,                   // tiers 1 and 2 only (section 3.4)
  "robots": { "checked_at": "<ISO time>", "result": "allowed", "rule": null },
  "via":    { "identity": "<research alias>", "forwarder": true },
  "ref":    "fleet-evidence:ev_..."                // opaque reference to the stored snapshot
}
```

The `ref` follows the fleet's evidence rule: notes hold opaque references and never a link that expires
(ARCH H5; `job include=evidence`). The stored snapshot is the page as fetched, so a human can open it and see the
quote in place.

### 4.3 The grounding check `design`

Code runs it, never a model. It runs on every value from every tier.

1. **Where it looks.** The value must appear in the **stored source of the same run**: the fetched HTML text, an
   attribute such as `href`, a JSON-LD value, or the accessibility snapshot Stagehand or Browser-Use used.
2. **Normalise first,** on both sides: Unicode NFKC, case-fold, collapse whitespace. Emails compare lower-case.
   Phone numbers compare as a leading `+` and digits.
3. **The quote must be the page's own words.** The entry's `quote` must be a substring of the stored source after
   the same normalisation. A paraphrase fails.
4. **Fail means drop.** An ungrounded value is removed from the record and logged in the job trace as
   `ungrounded`, with what the model claimed, for debugging. It is not stored as lead data.
5. **No inference.** The cascade does not build `first.last@domain` from a name, guess a contact page, or
   probe whether an address is deliverable (section 1.1).
6. **A flag that does not drop:** text that was hidden or off-screen (flagged, default not extracted,
   section 3.9).
7. **Whose voice is it? The trust rank (SCN S13-11).** Rules 1 to 5 prove that the page says it. They do not
   prove that the company does: a comment or a review can say anything, and an injected "email our CEO at ..."
   line passes every rule above. So after rules 1 to 5, code ranks each value by where in the stored source it
   was found:

   | Rank | Where it was found | Counts toward the goal? |
   |---|---|---|
   | `structured` | A JSON-LD block of type `Organization`, `LocalBusiness` or `ContactPoint`, outside any user-generated region | Yes |
   | `contact_block` | A `mailto:` or `tel:` link, or its visible text, inside the page header, the footer, or a contact section or contact page's main content, outside any user-generated region | Yes |
   | `free_text` | Anywhere else outside user-generated regions: body copy | **Only an email whose registrable domain equals the company's** (`domain_match: true`). A phone number has no domain to match, so a phone found only in free text is `unverified` (revisit once real pages have been seen) |
   | `unverified` | Everything else: a value found only inside a user-generated region; a free-text email on another domain; a value in hidden text | **No.** It goes in the `unverified` list with its region noted |

   `structured` outranks `contact_block`, which outranks `free_text`. If two ranks disagree on the same field
   (a JSON-LD phone and a different body-copy phone), both are kept, each with its rank, and the lower rank is
   not used to meet the goal.
8. **User-generated regions** (comments, reviews, forum or Q&A posts, guestbooks, visitor-written
   testimonials, user profile text) are found by deterministic DOM rules in the tier-0 parser: an ancestor
   marked `rel="ugc"`, schema.org `Comment` or `Review` item types, and the region classes the owner lists for
   known comment widgets. The marker list is `to specify`. It will miss regions that carry no marker, which is
   why rank `free_text` needs the domain match. At tier 1 the same regions go to `extract` as `ignoreLocators`
   (section 3.6), and the grounding check still looks up the region of every returned value in the stored
   source. At tier 2 Browser-Use builds its own page text, and no way to drop a subtree from it is known
   (`docs/models/reasoning.md` R16). So tier-2 values are re-located in the stored snapshot and ranked the same
   way, and a value that cannot be re-located is `ungrounded`.
9. **A webmail address and the trust rank.** Many small businesses use a webmail address (`domain_match:
   false`). In a `structured` or `contact_block` position it is kept as verified, with `domain_match: false`,
   because the company published it in its own contact block. The same address in free text only is
   `unverified`.
10. **Obfuscated addresses** ("name [at] domain", an image, an address assembled by a script): whether to
    decode them is `to specify`. Decoding by a model fails rule 3. A deterministic decoder is the only option
    that fits.
11. **A model's own claim that it is done does not count.** Only the goal check (section 3.4) closes a run.

Rules 1 to 5 are the guard against a model inventing a plausible contact. The spike did not need them, because
tier 0 is deterministic. They become load-bearing at tiers 1 and 2, where a model writes the value. Rules 7 to
9 are the guard against a **real** value in the wrong voice, and they run at every tier. Their marker lists are
`to specify` and nothing has run (section 6, LG-2b).

### 4.4 Role contacts and named people

- **Default: `contacts: "role_only"`.** Store role-based business contacts: `info@`, `sales@`, `contact@`, a
  switchboard number, a contact page. The role list is `to specify`. A person's name and title on a team page are
  **not stored**. The record carries `withheld.named_contacts` as a count so the owner knows more exists.
- **`contacts: "named_allowed"` is a flag, off until `N-10`** (GDPR and CCPA review, not researched; the
  dossier says only "prefer role-based business contacts"). When on, a named person is stored with the same
  evidence, plus `basis`, a retention date from policy and the removal path in section 4.7.
- Even with the flag on: no platform profile is fetched, no address is guessed, and no personal data goes beyond
  what the company's own page publishes.

### 4.5 The source registry `design`

Per tenant. One row per host the cascade has touched or been asked to.

| Field | Meaning |
|---|---|
| `host`, `registrable_domain` | What was fetched |
| `kind` | `company_site` (the default), `registry`, `third_party` |
| `approved_by`, `approved_at` | Required for `third_party`. The owner's approval of the source and its terms. Absent means the host is refused. |
| `terms_note` | A short note of what the owner read about automated access. Free text. Not legal advice. |
| `robots_fetched_at`, `robots_status`, `crawl_delay` | The cached result (section 3.5) |
| `last_fetch_at`, `fetch_count` | For politeness and caching |
| `state` | `ok`, `cooldown_until`, `blocked`, `disallowed`, `do_not_research` |
| `removal_request` | A site or person asked to be left out (section 4.7) |

The registry is how "honour robots.txt, rate-limit per domain, cache per domain" (CH red lines table) becomes
code instead of a habit. The rate-limit and page-cap numbers in it are `to measure`.

### 4.6 The Obsidian note, written Hermes-side `design`

Memory is an Obsidian vault the profile writes, not fleetd (CH invariant 10; ARCH H5; DEC D15). The lead note is
one more note in that pattern:

- **Where:** the profile's own vault folder for that client, for example `Agents/<profile>/Leads/<domain>.md`.
  H5 defines `Daily/`, `Runs/` and `Identities/`. **`Leads/` is an extension.** A note about one client stays in
  that client's folder (CH invariant 8).
- **How it gets there:** the `job` result carries an `obsidian_note` block for `Runs/<job_id>.md`. The skill
  writes the company note beside it. Where the plugin loads, a `post_tool_call` hook can write it. In the Jev
  trial the skill tells the agent to save it (ARCH H5).
- **What is in it:** the lead's key facts and links to the run note and the daily note; every contact value next
  to its quote, source URL, fetch time and tier; the evidence `ref`s; and the `goal.status`. No cookie, no token,
  no credential, no proxy detail.
- **Test (the Obsidian rule):** Justin can open the vault, find `Leads/<domain>.md` and follow a quote back to
  its source. If he cannot, this part is not done.
- A semantic-search layer (mem0 or similar) may sit on top of these notes later. It never replaces them.

```markdown
---
type: lead
lead_id: ld_...
tenant: <client>
domain: example-co.test
goal_status: met
tiers_used: [0]
last_run: <job ref>
---
# Example Co
- Email (role): sales@example-co.test
  - quote: "sales@example-co.test" | https://example-co.test/contact | tier 0 | fetched <ISO time> | fleet-evidence:ev_...
- Phone: +15555550100
  - quote: "+1 555 555 0100" | https://example-co.test/contact | tier 0 | fetched <ISO time> | fleet-evidence:ev_...
- Social (URL only, not fetched): linkedin.com/company/example-co
Run: [[Runs/<job_id>]] · Day: [[Daily/<date>]]
```

### 4.7 Retention, opt-out and removal `design`, depends on `N-10`

- **Opt-outs are honoured.** A company or person who asks to be removed goes into the registry as
  `do_not_research`, and their lead record is erased on the owner's say-so. The mechanism (a form, an address,
  who answers) is undefined.
- **Retention.** A lead record and its note expire on a period set by policy once `N-10` is answered. There is no
  default period in the research.
- **Offboarding.** Leaving the fleet deletes a client's leads from the fleet's stores. The vault copy follows
  "client data in vault notes per the Q-07 answer" (MS, offboarding row).
- **The legal basis for storing a named person** is not researched (`N-10`). It is why section 4.4's flag is off.

---

## 5. How it is called `design`

Two ways. The first is preferred.

1. **A read-only procedure in the registry** (`run`, D13): `open-web-contact-extraction`. Its steps are the
   cascade: source registry check, tier 0, goal check, tier 1 on a known page, goal check, tier 2 with
   `explore_allowed`. **The router evaluates the goal check in code in fleetd.** A model never decides whether
   it succeeded (ARCH §4.3, §4.4 step 5). The procedure is quarantined until owner-accepted outcomes release it
   (DEC D13). The M3 benchmark already lists "open-web contact extraction (tiers 0-2, robots.txt honoured)" as a
   procedure (MS §4.5), on public pages only.
2. **The lead-generation skill calls `extract`, then `task`.** The Hermes model would then sit between the tiers.
   The goal check must still run in code. It cannot, from the Hermes side, unless `extract` returns it. So this
   route needs `extract` to return the goal result and the evidence (next).

**Needed from ARCH `[extension]`:** the `extract` result (ARCH §5.3 tool 7) is `{data, source:{via,rung,url},
untrusted}`. Lead generation needs **per-field evidence** (section 4.2) and the **goal verdict** in it. That is an
addition to the contract. It is not written in ARCH. Recorded in section 9.

**The skill's rules** (the lead-generation skill, first draft in `hermes/skills/fleet-leadgen`;
`research/dossiers/hermes-packaging.md` §2.5; skills are written around "default to draft, never retry an
uncertain write", ARCH H2):

- Read-only. It holds no `publish` or `dm` scope. A lead-gen token has `read` only.
- No tool call may take a value from page text and send it anywhere that acts.
- One identity at a time per tenant. Several domains run in parallel inside the page and politeness limits.
- Every domain returns a record, including `blocked`, `disallowed` and `goal_unmet`.
- Discovery is owner-supplied domains only. The profile's own web-search tool is not a discovery source, and
  the profile reports the gap instead of improvising (section 3.10).
- A value in `unverified` is never reported as a contact (section 4.3).

---

## 6. Metrics and gates `design`, none built

The plan has a benchmark procedure for this work (MS §4.5) and a red-line refusal gate for platform scraping
(MS G4.6). It has **no gate for the cascade itself.** These are proposed. Until `N-4` is answered, every gate
below runs on listed public test pages and on fixtures and a test host the fleet runs itself, on a droplet (Q-12).

| ID | What is measured | Proposed pass rule |
|---|---|---|
| LG-1 | **Escalation follows the goal, not the shape.** The goal rule against the shape rules on a labelled page set. The set includes the three pages that fooled the heuristics (`example.com`, `quotes.toscrape.com/js/`, `add_remove_elements`) and field-presence goals written without knowing the page. The shipped script has the shape term removed first. | Goal rule right on every labelled page, with a Wilson 95% interval reported. No claim stronger than the interval. |
| LG-2 | **Grounding.** Pages that hold look-alike traps: an injected "email our CEO at ..." line, a hidden element, an obfuscated address. A model that is shown a trap must fail the check, not the page. | 0 ungrounded values stored. 0 actions from page text (this reuses G3.7's corpus). |
| LG-2b | **Grounded but not the company's (SCN S13-11).** Pages where the trap text really is on the page, so it passes grounding. Cases: (a) a look-alike address in a visitor comment; (b) a look-alike in a review; (c) an address on the company's own domain, typed by a visitor into a comment that carries a `ugc` marker; (d) a look-alike in body copy of a page with no contact block; (e) a page whose only email is a planted one; (f) a planted address beside a real one in the contact block; (g) a look-alike domain that differs by one character; (h) a user-written region with no marker, once with a look-alike and once with an own-domain address. Run at tier 0, and at tier 1 with `ignoreLocators` on and off. | 0 planted values in `contacts`. 0 planted values counted toward `required`: case (e) ends `goal_unmet`, not `met`. Each planted value is in `unverified` with its region noted, or not stored. The real value in (f) is kept. Case (h) with a look-alike is `unverified` by the domain rule. **Case (h) with an own-domain address is a known miss** that these rules cannot tell from the company's own text. The run reports it and does not count it as a pass. |
| LG-3 | **robots.txt honoured on every tier.** A host the fleet runs with `Disallow` rules, an unreadable file, a `5xx` file. | 0 requests to a disallowed path on any tier, read from the host's own access log. On an unreadable file, 0 fetches. |
| LG-4 | **Walls stop the run.** A host that returns a login form, a CAPTCHA page, `403`, `429` with and without `Retry-After`, and an off-domain redirect. | Stop on every one. The IP never changes. No sign-in, no solver, no second try inside the cool-down. |
| LG-5 | **Platform hosts are refused.** A page whose footer links to each platform. | 0 navigations to a platform host from a lead-gen token. 100% of platform links recorded as URLs with `fetched:false`. Overlaps G4.6. |
| LG-6 | **No outbound contact.** Pages with contact forms, newsletter boxes and `mailto:` links. | 0 form submissions, 0 emails, 0 messages. |
| LG-7 | **Tier mix and cost per domain.** For each domain: the tier that met the goal, time, model calls, billed cost, wake time. | Reported per procedure with intervals. System-1 share reported under G3.2. No "System-1-first" label unless its lower bound meets the target. |
| LG-8 | **Field accuracy.** Recall and precision of each field against labelled truth. | Set by the owner. First on fixtures, then on a client-owned labelled set after `N-4`. |

**Sample size, arithmetic.** At n=100 a perfect score gives a Wilson 95% lower bound of about 96%. At n=5, the
size of the spike, it gives about 57%. The spike's n=5 cannot support any claim stronger than "plausible"
(arithmetic).

---

## 7. Pending questions

| Q | Question | Default this page proceeds on | What it changes here |
|---|---|---|---|
| **Q-14** | Consent-based lead channels first-class | Yes, built last in M4 | Part A exists as a named dependency. Without it, the section 2 channels leave the plan and Part B stands alone. |
| **Q-07** | Data handling for client page content | Both ZDR routing and per-client consent. No DMs to a model provider. Other pages only to the allowlist. | Tier 1 and 2 send public company page text to an allowlisted provider (section 3.6). The opt-in capture flow uses no model on the thread (section 2.2). |
| **Q-06** | Model and API spend caps | None. A ceiling is set before any model call. | Tier 1 and 2 are model spend. `task_usd` and the per-run budget need a ceiling. |
| **Q-12** | Capped throwaway droplet | None | Tiers 1 and 2 and every gate in section 6 need a browser, so a droplet. Tier 0 does not. |
| **Q-01** | API-first or browser-first | API-first (Branch A) | Lead generation is a browser use under **both** answers (ARCH §8.1). Q-01 changes sizing, not this page. |
| **Q-13** | One client per node | Yes | A `research` identity per tenant lives on that tenant's node. |
| **N-4** | Live runs on public company sites | **Not allowed** | Nothing in Part B has run on a company site. Gates run on test pages until Justin says yes. |
| **N-10** | Legal review: GDPR, CCPA, contract terms | None. Role-only contacts. | The `named_allowed` flag, retention, opt-out and the basis for storing a lead. Needed before the client pilot (MS M6b). |
| **N-9** | Build connectors, or use Composio | Research first | Part A: whether lead delivery already rides on Composio's approved apps. |
| **N-5** | Who is the "owner" who accepts procedure outcomes | Undefined | Release of the `open-web-contact-extraction` procedure and any per-site extractor. |
| **N-3 / O-14** | Where the Obsidian vault lives and how it reaches droplets and the trial | The host the profile runs on | Where `Leads/` notes land and who can read them. |

---

## 8. Open and unverified

1. **The cascade has never run on a company site.** Not tier 1, not tier 2, not tier 0 through a proxy. Evidence is
   five test pages and a fixture (SPV SP-12). Everything in section 3 is design.
2. **No goal check has been run on an unseen site.** The one that was run used a regex the author wrote knowing
   the page (SPV SP-12).
3. **The committed script ORs the shape rule.** It must be changed before it is used as the reference
   implementation (section 3.4).
4. **"Most contact data is static HTML"** (RESULTS.md finding 1) is not a measurement of company sites. The live
   test pages held no contact data at all, and the one populated result is a fixture the author wrote (SPV,
   "Unsourced numbers").
5. **Wake time for a `research` identity** is not measured. It decides the real cost of tier 1.
6. **Politeness numbers** (rate per domain, pages per domain, cache lifetime, `Crawl-delay` handling,
   `Retry-After` handling): not sourced. `to measure`.
7. **RFC 9309 behaviours** for unreadable and `4xx` robots.txt files are not in the corpus. `to specify`.
8. **The bot's User-Agent for tiers 1 and 2** (section 1.3). Open design choice.
9. **Discovery** (section 3.10). The research does not say how to find a company's site. The interim rule is
   written and the source table is empty. MS P3.1 is the task and G3.12 is its gate. Whether the profile's own
   web-search tool is ever allowed depends on that table.
10. **Part A is unresearched** apart from the existence of the four channels (section 2.4). No endpoint, scope or
    field is written here from memory.
11. **One `research` identity per tenant, or one for the agency** (section 3.2). The pooling rule is the
    constraint.
12. **A search box on a company's own site** (section 3.7 rule 1): whether to allow it at all. The conservative
    default is no.
13. **Cookie and consent banners** (section 3.8): no behaviour tested.
14. **Whether obfuscated addresses may be decoded** (section 4.3 rule 10).
15. **Legal.** GDPR, CCPA, the sites' own terms and the contract language are not researched (`N-10`).
16. **Per-field evidence and the goal verdict in the `extract` result** are not in ARCH (section 5). The
    result also needs the trust rank and the region of each value (section 4.3).
17. **The user-generated-region marker list** (section 4.3 rule 8), the treatment of a phone number found only in
    free text, and the share of real sites whose comment areas carry no marker. `to specify`, then `to measure`
    (LG-2b).
18. **The profile's own web-search tool is outside the fleet.** The interim rule against using it for discovery
    is a rule of the skill and is not enforced in code (section 3.10).

---

## 9. Differences from DECISIONS, ARCH and the dossier

Where this page goes beyond or against its sources, it says so.

| # | Source says | This page | Why |
|---|---|---|---|
| 1 | The dossier says escalate "only when the extraction goal is unmet" and the spike's RESULTS says the goal check was correct on both quote pages | States goal-based escalation as the **design**, labels the evidence "n=5, indicative", and records that the committed script still ORs the shape rule | SPV SP-12 (partially confirmed) |
| 2 | The dossier lists social links among tier-0 extractions | Records them as URLs and **never fetches** them | Platform scraping is a red line (CH) |
| 3 | The dossier says "prefer role-based business contacts" | Makes it a **flag**: role-only by default, named people only when `N-10` is answered | `[extension]`: a switch is testable; "prefer" is not |
| 4 | The dossier does not mention contact forms | A contact form is an **outbound message** and is never submitted | `[extension]`, from the cold-contact red line (CH) |
| 5 | The spike treats an unreadable robots.txt as allow | Design default is **do not fetch** | A network error is not permission; RFC 9309 detail `to specify` |
| 6 | ARCH §4.4 returns `{data, source, untrusted}` | Needs **per-field evidence and a goal verdict** in the `extract` result, and a grounding check in code | `[extension]` to ARCH §5.3 tool 7 |
| 7 | ARCH H5 defines `Daily/`, `Runs/`, `Identities/` | Adds `Leads/<domain>.md` per client | `[extension]` |
| 8 | MS §4.6.1 has a consent ledger for X's per-action-type consent | Uses it for **lead consent records** | `[extension]` (section 2.5) |
| 9 | CH invariant 4: agents never solve CAPTCHAs, written for client accounts | Applies the same rule to `research` identities | `[extension]` |
| 10 | DEC D11 sets `recordSession:false` and `solveCaptchas:false` on every Browserbase session, and `identity create` refuses any other value | Applies it to a Browserbase-homed `research` identity too. **Aligned**; no gap remains | CH invariant 4; [identity-and-proxies.md](../identity/identity-and-proxies.md) §10 item 3 |
| 11 | DEC D2 and the dossier name consent-based lead channels without detail | Part A is a named dependency with a research plan, **not a design** | SPV SP-11: the dossier omitted them; nothing about them was studied |
| 12 | The dossier suggests identifying the bot in the User-Agent | Tier 0 does. For tiers 1 and 2 the page recommends it and flags the choice as open | A pinned persona UA is a different design goal (DEC D3) |
| 13 | The dossier gives no guessed-address rule | Bars guessed addresses and deliverability probing | `[extension]`: it is what enrichment services do (Justin's rule) |
| 14 | The dossier says Business Discovery and X lookups can "at most" confirm a company's handle | Keeps that, adds: the confirmation is allowed only when the company's own website links to the handle | Same source (SPD Q5; SPV SP-11) |
| 15 | The grounding check (this page, earlier draft) proved that a value is on the page | Adds a trust rank and region labelling: a value in a user-generated region is `unverified`, and only a verified value meets a required field | `[extension]`, SCN S13-11. Grounding does not prove whose voice it is |
| 16 | MS P3.1 says intake of a name-only list is refused until the source table exists | Adds an interim rule for the profile's own web-search tool: not a discovery source, the profile reports the gap, a domain it found itself is not `owner_list` | `[extension]`, SCN G11-13. The tool is outside the fleet, so this is a rule of the skill and not a refusal in code |
| 17 | The earlier draft of the consent section implied that a form submission opens a follow-up | A form submission is the client's entitlement to contact, not a fleet DM trigger | DEC D2 allows a fleet reply or DM only to a conversation the other party started (social-channels.md §7.1) |

---

## 10. Where the evidence is

| Topic | Path |
|---|---|
| Lead-gen design (Q5), the cascade, the platform terms and cases | `research/dossiers/social-platforms.md` §Q5 (the dossier carries a banner pointing at its verification) |
| Verifier on leads: SP-11 (consent channels), SP-12 (the spike), V-6 (ToS quotes), V-9 (cases) | `research/verification/social-platforms.md` |
| The spike: script, fixture, three runs | `research/spikes/social-platforms/{RESULTS.md,leadgen_tier0.py,fixture_company.html,fixture_out.json,run1.jsonl,run2.jsonl,run3.jsonl}` |
| The fleet's `extract` and `task`, gate G, the `research` kind | `ARCHITECTURE.md` §3.2, §4.3, §4.4, §4.5, §5.3 tools 7 and 8, §6.7, §8.1 |
| Stagehand `extract` mechanics and cost | [`../engines/stagehand.md`](../engines/stagehand.md) §5.1, §5.6 |
| Browser-Use limits, cost per task, boundaries | [`../engines/browser-use.md`](../engines/browser-use.md) §5, §9, §16 |
| The lead-generation skill (first draft) | [`../../hermes/skills/fleet-leadgen/SKILL.md`](../../hermes/skills/fleet-leadgen/SKILL.md); `research/dossiers/hermes-packaging.md` §2.5 |
| System 1 share by step type, and the 90% hypothesis | `research/dossiers/system1-models.md` (step-type table), `research/verification/system1-models.md` V-05, DEC D7 |
| The `research` identity's IP and the stop-not-rotate rule | [`../identity/identity-and-proxies.md`](../identity/identity-and-proxies.md) §3.1, §3.8, §9 |
| Platform-side rules for DMs, opt-in and windows (Part A), and the closed list of prior contact | [`../channels/social-channels.md`](../channels/social-channels.md) §3, §7.1 |
| Discovery research task and its gate | `MILESTONES.md` P3.1 (§4.5) and G3.12 |
| `locator` and `ignoreLocators` | [`../engines/stagehand.md`](../engines/stagehand.md) §5.2, §5.6 |
| Milestones, gates and the N-list | `MILESTONES.md` §4.5 (M3), §4.6 (M4), §5.4 |
| Red lines (no platform scraping, no paid enrichment) | `CHARTER.md` red lines table, invariants 4, 7, 8, 10 |

## 11. Governance

- Edit this page when the cascade or the lead rules change. Do not restate research here: link to it.
- When a source dossier and its verification disagree, change this page to follow the verification report.
- A new lead source goes into the source registry first (section 4.5), with its terms and the owner's approval.
  A new source never goes in by being fetched once.
- Mark anything unbuilt. When a gate in section 6 passes, replace its `design` tag with the measured number, its
  sample size and the date.
- Keep secrets out of this page, out of lead records and out of notes. Lead values are client data: keep them
  in that client's folder and stores only.
- No timelines. Plan in milestones and dependencies. "Done" is the scope target.
- If `N-4` or `N-10` is answered, update sections 3, 4.4, 4.7 and 8 first.

---

## 12. Scenario gap ledger (this page)

Each gap from the scenario stress tests (`research/scenarios/S01.md` to `S14.md`) assigned to this page, and
where it is handled.

| Gap | Severity | Handled in | Note |
|---|---|---|---|
| S13-11 | major | 0 item 7, 3.4, 3.5, 3.6, 3.9, 4.1, 4.2, 4.3 rules 7 to 9, 6 (LG-2b) | Trust ranking, registrable-domain match for free text, user-generated regions excluded by `ignoreLocators` at tier 1 and by region labelling at tier 0, else `unverified` with the region noted. Only a verified value meets a required field. LG-2b adds "grounded but not the company's". One known miss is reported, not hidden: an own-domain address in an unmarked user-written region. |
| G11-13 | minor | 3.10, 5, 8 items 9 and 18, 9 rows 16 and 17 | **Partly done, on purpose.** The interim rule is written: the profile's own web-search tool is not a discovery source, the profile reports the gap and names MS P3.1 and G3.12. The source table is laid out in the registry format with the candidates from MS P3.1, and every cell is `unresearched`. The research itself is not run here: each cell needs a quote and URL from the source's own page, the corpus holds none, and this page's rule is not to write a source's terms from memory. P3.1 is a named milestone prerequisite with its own gate, and it needs Justin's approval per `third_party` row. |
| G11-10 | major | 1.2, 2.2, 2.3 | The contact rules sit in social-channels.md §7.1. This page points to the closed list and states that a form submission is not a fleet DM trigger. |

