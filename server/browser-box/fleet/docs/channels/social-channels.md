# Social channels: the platform connector layer, per platform

> **Superseded in part (Justin, 2026-10-19; DECISIONS "guardrails, not rules").** The red lines here
> (cold DMs, engagement, X, LinkedIn, research browsing, downloads) are now guardrails per client.

Status: **design, written 2026-10-10 and revised the same day after the scenario stress tests (gap ledger in
section 15). Nothing here is built.** No connector, no developer app, no token, no
webhook receiver exists. No platform approval has been applied for. What exists is research: platform
documentation read on 2026-10-09 and 2026-10-10, plus the verifiers' re-reads. No platform behaviour was ever
observed, because the brief forbids touching a social site.

Read with [DECISIONS.md](../../DECISIONS.md) (D2 governs this page; D13 and D14 constrain it) and
[CHARTER.md](../../CHARTER.md) (invariant 6, the red lines). **Where a dossier and its verification report
disagree, the verification report and DECISIONS win.** This page cites the social-platforms dossier only for
claims the verifier confirmed, or it states the correction.

Platform facts here are **dated and move**. Every limit, price and version below must be re-read from the
platform's page at build time (DEC D2 says the same).

## How to read this page

| Tag | Meaning |
|---|---|
| `official-docs` | Stated on the platform's own page, as read by the dossier author and re-read by the verifier. |
| `vendor-claim` | A marketing or third-party statement. |
| `third-party` | Law-firm notes, blogs, press. |
| `design` | The target. Not built. |
| `estimate` | A planning figure with a stated basis. Not a measurement. |
| `to measure` | Unknown. |
| `unverified` | Not confirmed, or an absence ("no API found") that could be wrong. |
| `pending Q-nn` | Depends on one of Justin's questions. The text proceeds on the recommended default. |
| `[Branch B]` | Applies only if Q-01 goes browser-first (section 1). |

Source aliases (paths relative to this file):

| Alias | Path |
|---|---|
| DEC | [`../../DECISIONS.md`](../../DECISIONS.md) |
| CH | [`../../CHARTER.md`](../../CHARTER.md) |
| ARCH | [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) (§2.6, §3.12, §4.6, §4.7, §4.8, §4.12 are cited. §8 matches this page's Q-01 branch point, with the one LinkedIn difference noted in section 13) |
| MS | [`../../MILESTONES.md`](../../MILESTONES.md) |
| CON | [`../../research/verification/CONSISTENCY.md`](../../research/verification/CONSISTENCY.md) |
| SPD / SPV | [`social-platforms` dossier](../../research/dossiers/social-platforms.md) / [verification](../../research/verification/social-platforms.md) (SP-1..SP-12, V-1..V-13, "missed issues"). The dossier's own sections: Q1 (APIs), Q2 (browser-only), Q3 (rules, checkpoints), Q4 (red lines, human-in-the-loop), Q5 (leads), Q6 (decision table). |
| APD / APV | [`antidetect-proxies` dossier](../../research/dossiers/antidetect-proxies.md) / [verification](../../research/verification/antidetect-proxies.md) |
| SCD / SCV | [`scale-infra` dossier](../../research/dossiers/scale-infra.md) / [verification](../../research/verification/scale-infra.md) |
| GEMINI-AUDIT | [`GEMINI-AUDIT.md`](../../research/verification/GEMINI-AUDIT.md) (a hypothesis list, not a source) |
| SCN | [`../../research/scenarios/`](../../research/scenarios/) (S01 to S14). Gap ids such as S03-6 or G11-10 are those files' own ids. |
| ID | [`../identity/identity-and-proxies.md`](../identity/identity-and-proxies.md) |

---

## 0. The short version

1. **API first.** Publishing, comment moderation, inbound-DM replies and analytics go through the platforms'
   official APIs: Meta Graph (Pages, Instagram professional accounts, Messenger), TikTok API for Business
   (Accounts API), LinkedIn Community Management, X API v2 (DEC D2). That route is sanctioned, cheaper (no
   browser RAM, no proxy, no page reading by a model), and deterministic. Whether this is the default for every
   client or only some is **Q-01, an explicit branch point (section 1).**
2. **The browser is for the gaps:** human login, re-auth and checkpoints; open-web lead generation; a narrow
   no-API set (Facebook Groups and a few UI-only features); and sites with no API. Each browser write in the
   narrow set is human-approved, low volume, and needs the client's written risk acceptance. A person clicks
   (`human_clicks`) unless the owner sets otherwise (section 6.1). Personal profiles get **no** browser identity
   at all (DEC D2 rows 3 and 4). DEC D2's allowed-uses table is the whole list (section 6).
3. **Two hard exclusions.** An agent never drives a browser on x.com. LinkedIn is draft-only: agents draft, a
   human sends from their own session (CH red lines).
4. **Nothing cold, nothing automated in the engagement sense.** No cold DMs on any platform, no automated likes,
   no bulk follows, no identical posts across client accounts (section 7).
5. **Approvals are the long pole and they are milestone dependencies, not per-client steps.** One developer
   app per platform, owned by Justin's business and authorized by each client. **None has been applied for**
   (`pending Q-06`). A channel without its approval is not offered (CH invariant 6) (section 9).
6. **Some ceilings are per account, some per app.** The X per-app figures in the research are legacy Pro-plan
   columns on a pay-per-use page and are unproven. Per-account X limits bind first. The governor reads live
   response headers and never hard-codes a constant (section 4).
7. **X costs real money:** $0.015 a post, $0.20 for a post with a URL, $0.015 a DM, plus metered reads and
   webhook events (`official-docs`). Meta, TikTok and LinkedIn APIs have no price, only approval gates.
8. **Receipts are API reads.** A post is "done" when the platform shows it, not when the call returned 2xx
   (section 8). Browser-channel receipts are a hypothesis `[Branch B]`.
9. **Consent-based lead channels** (Lead Ads, opt-in DM capture, LinkedIn Lead Gen Forms, TikTok instant forms)
   are official lead sources, and the way the browser stays away from platform lead scraping (`pending Q-14`).
   Their API details are **unresearched**. See [lead-gen.md](../playbooks/lead-gen.md).
10. **Open and unresearched:** whether Composio's connectors already wrap these APIs (MS N-9); the egress IP of
    the connector layer (CH invariant 9); the read-back endpoints and fields on each platform; GDPR and CCPA
    (MS N-10).

### Status ledger

| Item | State |
|---|---|
| Connector layer, token vault, webhooks, governor | `design` |
| Developer apps and approvals (Meta, TikTok, LinkedIn, X) | **none applied for**; `pending Q-06` |
| Spend caps, including X fees | **$0 until Justin names one** (MS §5.1) |
| Platform limits and prices | read 2026-10-09/10, `official-docs`; **re-read at build time** |
| Platform behaviour (checkpoints, cadence, detection) | **never observed** |
| Receipts per platform | endpoints named from docs; read-side fields not read |
| Consent-based lead channel APIs | **unresearched** |
| The conversation record: window, opt-out, X reply counter, `human_agent_until` | `design`; ARCH §3.12 has the window and opt-out fields, and lacks the counter and `human_agent_until` (section 2.6) |
| `HUMAN_AGENT` tag | **Off.** Needs a person-written compose path and a decision from Justin (section 2.6; `pending AQ-8`) |
| X replies and DMs | Per-action approval only; no template route; X off until Q-05 (section 3.4.2) |
| Prior contact or opt-in | A closed list of four (section 7.1) |
| Per-platform re-auth playbook | `design` (section 6.3); the client-opened viewer is `pending AQ-1` |
| Composio versus our own connectors | **unresearched** (MS N-9) |

---

## 1. BRANCH POINT: Q-01, API-first or browser-first for client social `pending Q-01`

> **This is a decision only Justin can make.** DEC Q-01: "API-first for client social (recommended) or
> browser-first; which clients accept the terms risk in writing?" The plan proceeds on **Branch A**. M1 to M3
> are identical in both branches. The decision is needed before M4 starts (MS §2.2).

### 1.1 The two branches

| | **Branch A: API-first** (recommended, plan default) | **Branch B: browser-first** (per client, with written acceptance) |
|---|---|---|
| What M4 builds beyond the common core | Connectors, a token vault, webhook receivers, a messaging-window tracker, media hosting | Browser effect procedures, each with a human approval per action |
| Receipt | An API read of the post or message (strong) | A browser read-back from the feed or thread (**a hypothesis**: DEC D13, SCV SCA-9) |
| External dependency | App approvals, any of which can be refused or stall | A written risk acceptance per client |
| Role of the browser | Login and re-auth, checkpoints, open-web leads, the narrow no-API set | All of that, plus posting, replying and messaging |
| Browser hours per identity | Few or none for most identities | Many. DEC D12's all-browser rows become the likely case. |
| Effect on M5 to M7 sizing | Node count driven by the share of identities that need a browser | Node count driven by all identities |
| Dominant risk | An approval is refused or stalls | An account is restricted; a high rate of uncertain holds |
| What the client signs | Normal authorization of the app | A risk acceptance that the platform's terms can lead to suspension |

Source: MS §2.2 and §4.6.2. The branches are not new inventions here.

### 1.2 What does not change in either branch

- **X is never driven by a browser.** Not by an agent, in either branch. There is no browser identity for X. A
  person who must use x.com uses their own device (DEC D2 row 7; CH red lines; SPV SP-1).
- **LinkedIn is draft-only.** Agents draft; a human sends. No bot sends a message or a connection request and no
  LinkedIn action is done by browser automation (CH red lines; SPV SP-8).
- **The red lines** in section 7, the effect ledger, approved manifests, the governor, the first-post gates and
  the checkpoint handler.
- **A human logs in.** Agents never type credentials or solve challenges (CH invariant 4).
- **The X "Automated" label question** (`pending Q-05`).

### 1.3 What moves on this page if Q-01 goes browser-first

Only Facebook Pages, Instagram professional accounts and TikTok can move, and only for clients who sign.

| Where | Branch A | Branch B |
|---|---|---|
| Section 5 decision table, cells for Facebook, Instagram, TikTok: publish, comment reply, inbound-DM reply | API | A browser procedure with a human approval per action, run on that client's browser identity |
| Section 5, X and LinkedIn cells | unchanged | **unchanged** |
| Section 6 (the human-in-the-loop set) | The only browser writes | A larger set, same approval rule |
| Section 8 (receipts) | API read-back | Browser read-back, `to measure` (MS G4B.1: at least 100 read-backs per platform and effect kind, with a Wilson interval) |
| Section 9 (approvals) | Required before a connector is ready | Not required for the browser path, but the client's written acceptance is |
| Identity cost | Browser identity only for the gaps | A browser identity per account, with its own IP ([identity-and-proxies.md](../identity/identity-and-proxies.md)) |

### 1.4 Why Branch A is recommended

1. **Terms.** X: non-API automation "results in permanent suspension". LinkedIn bans bots that post, comment or
   message. Meta bars automated access and collection without permission and requires an authorized route for
   scripted account use. TikTok bans automated data extraction and sanctions its Accounts API for posting
   (DEC D2; SPV SP-1, SP-2, SP-6, SP-8, V-6).
2. **A human approving does not make UI driving permitted.** Only a human *doing* it is clean (SPD §5 risk 7).
3. **Cost and determinism.** No browser RAM, no proxy, no page reading by a model for routine work.
4. **A strong receipt.** The platform's own API says whether the post exists.

### 1.5 Why someone might still want Branch B

- A feature has no API (Groups, stories, other UI-only features). That is the section 6 set. It exists in
  Branch A too, but small. Personal profiles are not in it: they get no browser identity.
- **An approval is refused or stalls.** Under the default, a platform without its approval is **not offered**
  (CH invariant 6). The only other routes are "the human does it" or a client-signed Branch B for that platform.
- The client's expectation is "browser agents replying to and messaging people". Cold DMs and engagement
  automation are prohibited everywhere, so that expectation has to be reset in the client contract whichever
  branch is chosen (SPD §5 risk 1).

### 1.6 What Justin decides

1. The fleet default: A or B.
2. Which clients, if any, may sign for Branch B, and for which platforms and effect kinds.
3. The risk-acceptance wording. That is a contract and legal matter (MS N-10, not researched).

Cheaper to decide with data: Branch B's viability for an effect kind rests on the measured browser read-back
false-negative rate (MS G4B.1). If it is above the tolerance Justin sets (MS N-6), Branch B is not viable for
that effect kind.

---

## 2. The connector layer `design`

One interface, four implementations. ARCH §2.6 states it; this section adds the rules around it.

```
 PlatformConnector
   capabilities(account)  -> {publish, comment, reply_dm, analytics, ...}
   publish(item, idem)    -> {platform_id, url?}          # an EFFECT: goes through the ledger
   reply(thread, text)    -> {...}                         # an EFFECT
   readback(effect)       -> {found, observed_hash, ref}   # the receipt source
   limits(account)        -> {windows from live headers, daily caps}
   health(account)        -> {token_ok, scopes, expires_at}
```

### 2.1 Rules

- **Where it runs.** Inside fleetd. Connector credentials (OAuth tokens, system-user tokens) never leave fleetd,
  and never reach a Hermes profile, a note or a log (ARCH §2.6; CH "what nobody does").
- **Effects go through the ledger.** An idempotency key, an intent row committed before the call, an
  independent read-back, and a hold when the outcome is uncertain. Never a blind retry (DEC D13). Calls are
  serialized per `(identity, platform)` (ARCH §4.6).
- **Content comes from an approved manifest item or a per-action approval,** never from page text, DM text or a
  model's invention (DEC D13).
- **No browser is woken and no lease is needed** for an API publish. The identity must not be on hold (ARCH §4.6).
- **A token vault** holds tokens per identity per platform, encrypted. A refresh scheduler keeps them alive:
  Instagram long-lived tokens last 60 days and refresh; TikTok access tokens last 1 day and refresh tokens up to
  365 days (`official-docs`); X and LinkedIn lifetimes were not fetched (`unverified`). A 401 or a revoked token
  moves the identity to `needs_reauth` with kind `api_connection`, fixed by an OAuth link in the client's own
  browser, not by the viewer (ARCH §4.6, MS G4A.3).
- **Webhook receivers** for Meta (comments, messages), TikTok (messages, post status) and X (the Activity API,
  billed per event). Idempotent, tolerant of duplicate and out-of-order delivery (MS G4A.4).
- **A per-conversation window tracker:** Messenger 24 hours (7 days after a click-to-Messenger ad), private
  replies to comments within 7 days; Instagram 24 hours and the 7-day private reply; TikTok's
  non-mutual-follow limits (SPD Q1). The HUMAN_AGENT tag is **not** in the default tracker: see section 2.6.
  The record is in section 2.6.
- **Media hosting.** Meta fetches media by public URL; Instagram accepts JPEG only for images; TikTok requires a
  verified domain for `video_url`. So the fleet needs a verified public domain and a media host (MS §4.6.3).
- **Consent and opt-out ledgers.** X needs express consent per automated action type, and OAuth alone is not
  consent (X automation rules; SPV V-7). An opt-out ledger is honoured on every platform.
- **A cross-client duplicate-content check** runs before every publish (X bars duplicative posts across
  accounts you operate; Meta treats repetitive content as spam).
- **One developer app per platform,** owned by Justin's business and authorized by each client (DEC D2). Splitting
  into many apps to dodge limits risks a "circumvent rate limits" enforcement (SPD §5 risk 4), so it is not done.

### 2.2 Onboarding models (Meta)

Two different models are easy to confuse (SPV missed issue 9). Pick per client.

| Model | How | Note |
|---|---|---|
| **Per-client OAuth** to the one app | The client authorizes the app in their own browser | The client's identity is the grant. Fits "an account you manage" under Standard Access, subject to the interpretation risk in 3.1.4. |
| **Business Manager system user** | The client gives the agency partner access in Business Manager; the app uses a system-user token | Meta: system users "represent servers or software making API calls to assets owned or managed by a Business Manager". Their tokens must not be used to act for a real user of your software (`official-docs`, SPD Q1a). |

### 2.3 The Messenger 30-second rule

Messenger policy says "Automated bots must respond to user input within 30 seconds" (`official-docs`, SPD Q1a).
The Hermes tool budget is 90 seconds, and a reasoning-model reply can take far longer (runaways of 34 to 52 s
were measured at an 8k token cap; DEC D8). So a free-text generated reply cannot be the same call as the
inbound webhook. The design consequence, `design`: the inbound path answers inside 30 seconds from approved
templates chosen by **deterministic code** (quick-reply and button payloads, a fixed menu, a window check). Any
reply that Hermes has to write is drafted, approved by a person, and sent inside the standard window. The
HUMAN_AGENT tag is not used for it (section 2.6). On X there is no template route at all (section 3.4.2). Whether a
*slower* reply breaks the rule or reclassifies the thread is **not established** by the page read. Resolve it at
build time (SPV missed issue 8).

Why deterministic code and not a decider. Under the Q-07 default the fleet does not send DM content to a model
provider (CH invariant 8), and a System 1 vendor is a model provider. So the inbound DM text is not shown to Jev,
Clef or any other model by the fleet. A reply that Hermes writes means the DM text reaches Hermes' own model,
which is outside the fleet. Whether that is allowed is part of `Q-07` (per-client consent) and is not decided
here.

### 2.4 The governor

Per account and per app, built from live response headers and the platforms' own limit endpoints, never from
constants. **Published ceilings are ceilings, not targets.** "Run at or under 50% of every cap" is a policy
proposal with no source behind it (SPV unsourced numbers); the actual rate is the owner's setting. Read before
every publish: Instagram `GET /{ig_id}/content_publishing_limit` (the page itself says both 100 and 50, so
hard-code neither); TikTok creator info or `/business/video/settings/`; X `x-rate-limit-*` headers on a live
user-context call. Section 4 has the numbers.

### 2.5 Two open items

- **The connector layer's egress IP is not decided** (CH invariant 9). Options: (a) fleetd's own egress, with one
  fixed set of addresses that is easy to allow-list; (b) each identity's pinned IP, so that API calls and the
  browser share an origin, at the cost of the forwarder on the connector path and a tie to node placement. No
  platform page read says API tokens are bound to an IP (`unverified`). Decide at M4 design.
- **Composio.** Justin's agents already use Composio. Its connectors may already wrap these official APIs. Whose
  app review they ride on, and how they handle per-app caps, was **not researched** (SPD §5 risk 9; MS N-9).
  Research it before building connectors. If it is usable it changes what the connector layer is.

### 2.6 The conversation record, and the two rules that need it `design`

Every reply and DM is checked against a record the fleet keeps for each conversation. ARCH §3.12 and §4.12
define it. It has `conversation_id`, `account_id`, `platform`, `external_thread_ref`, `author_ref`, `kind`,
`first_inbound_at`, `last_inbound_at`, `last_outbound_at`, `window_kind`, `window_expires_at`, `opted_out` and
`closed`. This page needs three more things from it.

| Field | Meaning | Default |
|---|---|---|
| `human_agent_until` | The time until which the HUMAN_AGENT tag could be used on this conversation: the last inbound message plus 7 days | `null`. It stays null while the tag path is off (below). |
| `replies_to_event` | On X, for each inbound event (the post, mention or DM being answered), how many automated replies were sent for that interaction | 0. A second one is refused. |
| `contact_basis` | Which entry of the closed list in section 7.1 makes the conversation eligible: `inbound_message`, `keyword_optin` or `private_reply_window` | Set when the conversation is written. No entry means not eligible. |

ARCH §3.12 does not carry `human_agent_until` or `replies_to_event` yet. `contact_basis` can be derived from
`kind` and the times. The refusal for a second reply needs a reason code in ARCH §5.5 (this page proposes
`one_reply_per_interaction`; D17 lists none for it).

**The tag and an AI draft (SCN S03-6).** HUMAN_AGENT is for a genuine human reply (SPD Q4). The approval in this
design is "approve this exact text". A person who clicks approve on a draft Hermes wrote has not written a
human reply. Sending that under the tag is a policy risk the platform pages do not settle (AQ-8). So:

1. **The tag is disabled.** No connector call sets it, and `human_agent_until` stays null. Outside the
   standard window, a reply is `refused` (`window_closed`).
2. **If Justin wants the tag** (a new part of AQ-8), it exists only on an **operator compose path**. A person
   types or edits the text in the console. The Hermes draft is shown beside it as a suggestion. The tag is
   applied only there, and the effect is recorded as `channel=human` with the operator named. ARCH §4.12 step 6
   already lets a message "written or edited by a person" use the tag, pending AQ-8. ARCH has no compose path
   yet.
3. **Meanwhile** a person may answer from the platform's own inbox on their own device. The fleet may write the
   draft for them (`draft_for_human`, DEC D2). That is the person's act, not a fleet send.

**One automated reply per interaction on X (SCN S03-7).** The counter is `replies_to_event`. The rules are in
section 3.4.2.

---

## 3. Per platform

Each platform lists what the official API can do, the rules specific to it, and what stays in the browser.
Ceilings and prices are collected in section 4. Receipts are in section 8. Approvals are in section 9.
Endpoint paths are those the dossier recorded from the platform pages (SPD Q1). Read-side details were not
read; confirm them at build time.

### 3.1 Meta: Facebook Pages, Instagram, Messenger (Graph API; the dossier recorded v26.0)

#### 3.1.1 Facebook Pages

| Capability | API | Requirements and limits | Evidence |
|---|---|---|---|
| Text, link or photo post; scheduled post | `POST /{page_id}/feed`, `/{page_id}/photos`; `published=false` with `scheduled_publish_time` | A Page access token. Permissions `pages_manage_posts`, `pages_read_engagement`, `pages_manage_engagement`, `pages_read_user_engagement`. Page tasks CREATE_CONTENT, MANAGE, MODERATE. **Scheduling window: 10 minutes to 30 days** from the request. `pages_show_list` is not on the cited page; it may still be needed to list Pages (`unverified`). | `official-docs`; SPV V-10 |
| Video | Video API | `publish_video` | `official-docs` |
| Reels | `POST /{page_id}/video_reels` (upload session) | **30 API-published Reels per 24-hour moving window per Page**; 3 to 90 s; 24 to 60 fps | `official-docs`; SPV V-5 |
| Stories | `/{page_id}/photo_stories`, `/{page_id}/video_stories` | Video story up to 60 s; CREATE_CONTENT task; `business_management` if a system user is used | `official-docs` |
| Comments, mentions, moderation | `/{post_id}/comments` and related | `pages_manage_engagement`, `pages_read_engagement`, `pages_read_user_engagement` | `official-docs` |
| Inbound DMs (Messenger) | Send API, Conversations API | See 3.1.3 | `official-docs` |
| Analytics | Insights endpoints | Permissions not read in detail | `official-docs` (index only) |
| **Groups** | **None.** The Groups API (`publish_to_groups`, `groups_access_member_info`) was deprecated in v19.0 and removed for all versions on **2024-04-22**. | Group work is browser-only (section 6). The removal rests on forward-looking changelog text plus vendor corroboration and a dead docs URL. | SPV SP-7 |
| **Personal profile posting** | **None** since `publish_actions` closed in 2018 | A person posts on their own device; the fleet may draft. No browser identity (section 6; DEC D2 row 3) | `official-docs` (via search) |
| Price | $0 | | `official-docs` |

#### 3.1.2 Instagram (professional accounts only)

| Capability | API | Requirements and limits | Evidence |
|---|---|---|---|
| Account types | **Professional only** (business or creator). Two login flavours: Instagram Login (no Page needed, `graph.instagram.com`) and Facebook Login for Business (Page-linked, `graph.facebook.com`). **Do not mix tokens and hosts.** | **Personal accounts have no API.** Basic Display returned errors from 2024-12-04. Converting a client's account to professional is free and moves it onto the API. | `official-docs` |
| Image, video, Reel, carousel, Story | `POST /{ig_id}/media` (a container, not an effect) then `POST /{ig_id}/media_publish` (the effect) | **100 API-published posts per 24-hour moving window** (a carousel counts as 1). The same page elsewhere says 50, so **read `content_publishing_limit` before every publish and hard-code neither.** Carousel up to 10 items. **JPEG only.** Media on a **public URL** (Meta fetches it). Video: poll `status_code` until `FINISHED`. Shopping tags and filters are not supported. A Page that requires Page Publishing Authorization blocks publishing until it is done. | `official-docs`; SPV SP-5 |
| Comments | Get, reply, delete, hide, unhide, disable on owned media | `instagram_business_manage_comments` | `official-docs` |
| DMs | `POST /{ig_id}/messages` | **Only after the user messages first.** 24-hour window (7 days after a click-to-Direct ad); the `human_agent` tag gives 7 days (off in the fleet, section 2.6); a **private reply** to a commenter within 7 days; no group messaging; Requests-folder threads idle for 30 days are not returned; webhook delivery does not mark messages read | `official-docs`; SPV SP-10 |
| Analytics | Insights endpoints | `instagram_business_manage_insights` | `official-docs` |
| Business Discovery | Returns basic metadata and metrics for other professional accounts | **Not a lead source.** Meta Platform Terms §3.a.v bars "Processing Platform Data without valid User consent in order to build or augment user profiles for any purpose". Client-facing benchmarking only. | SPV SP-11 |
| Price | $0 | | `official-docs` |

#### 3.1.3 Messenger and the messaging windows

| Rule | Value | Evidence |
|---|---|---|
| Standard window | **24 hours** after the user's message (up to 7 days after a click-to-Messenger ad) | `official-docs` |
| Message tag | **HUMAN_AGENT: 7 days**, only for a genuine human reply. **Off in the fleet** (section 2.6): an AI draft that a person only approved is not a human reply | `official-docs`; SPD Q4; SCN S03-6 |
| Private reply to a comment | Within **7 days** | `official-docs` |
| Bot response time | "Automated bots must respond to user input within **30 seconds**" | `official-docs`; section 2.3 |
| Bot disclosure | Where the law requires it (California and Germany are called out) | `official-docs` |
| Consent | "Don't contact people in Messenger or Instagram Messaging unless you ... have obtained legally sufficient consent, permission, and/or opt-in" (Developer Policies) | `official-docs` |
| Other channels that exist | One-Time Notification (user opt-in, not on Instagram), Sponsored Messages outside the 24 hours. **Not used by the fleet.** | SPV SP-10 |

So "only reply to people who messaged first" is a simplification on the platform's side. Every route needs prior
contact or an opt-in, and the conclusion (no cold DMs) holds (SPV SP-10). The fleet's own rule is narrower and
is a closed list (section 7.1).

#### 3.1.4 Meta access, approvals and terms

- **Standard Access suffices** if the app "only serves your Instagram professional account or an account you
  manage", or accounts added to the app in the dashboard. **Advanced Access** is required for accounts you
  *do not own or manage*, and needs **App Review plus Business Verification** (SPV V-1; `official-docs`).
- Whether "an account you manage" covers agency-managed *client* accounts without Advanced Access is an
  interpretation. At 100 to 1,000 clients, plan for Advanced Access (SPD §5 risk 3).
- Justin's own accounts, and accounts added in the app dashboard, work under Standard Access, which is what lets
  M4 development and the M6a canary proceed before App Review (MS §4.6.3).
- **Terms, stated precisely** (SPV SP-2, SP-9). Terms §3.2 bars accessing or collecting data from Meta products
  "using automated means (without our prior permission) ... regardless of whether such automated access or
  collection is undertaken while logged-in". It is a scraping clause with a permission carve-out. It does not by
  itself ban posting by script. The firmer basis is the Community Standards line that creating or using an
  account "through automated means, such as scripting (unless the scripting activity occurs through authorized
  routes ...)" can lead Meta to request additional information. **The API is that authorized route.** The
  circumvention clause ("anything to circumvent, bypass, or override any technological measures") is separate.
- Facebook Terms §3.1 bars giving others access to an account without Meta's permission. See the personal-profile
  row in section 6.

### 3.2 TikTok

TikTok has **two different posting products. Only one fits an agency.**

| Product | What it is | Requirements and limits | Evidence |
|---|---|---|---|
| **Accounts API** (TikTok API for Business, "Organic API") | Publish video and photo posts, moderate comments, read insights. Covers Business **and Personal** accounts. Authorized use: "Manage the organic presence of brands or creators' owned accounts". | **6 video posts a minute and 15 a day per account** through the endpoint. **40 QPM per account per endpoint; 600 to 1,000 QPM per app.** `video_url` must be on a **verified domain**; .mp4, .mov or .webm, up to 1 GB, 3 to 600 s. **Since 2026-03-20 the Accounts API access application form is required.** Access token valid **1 day**; refresh token up to **365 days**. **Prohibited:** downloading TikTok media or migrating it to other platforms, and building creator-discovery programs. | `official-docs`; SPV SP-6 |
| **Content Posting API** (developers.tiktok.com) | Direct Post and upload-to-draft | Unaudited clients post **private (SELF_ONLY) only, up to 5 users in 24 hours.** The audit criteria list as **not acceptable** "A utility tool to help upload contents to the account(s) you or your team manages", and require "a wide audience, not limited to internal groups/private use". | `official-docs`; SPV SP-6, missed issue 10 |
| **Business Messaging API** (DMs) | Webhook on an inbound message, then `/business/message/send/`. Conversation list up to 100; content list latest 20; `media_id` valid 30 days. | **Open beta** (APAC, LATAM, METAP, North America); **not available in the EEA, Switzerland or the UK.** Needs an approved app plus the Data Security and Privacy Review; US accounts also need the US Data Security Review and an addendum. "**You are prohibited from initiating a conversation.**" For non-mutual-follow conversations: 10 messages in the first 48 hours, unlimited within 48 hours of the user's last reply, then at most 3 until the user replies. | `official-docs`; SPV V-4, SP-10 |
| Stories, LIVE | No API found in either product | Browser-only (section 6) | `unverified` (an absence in the docs read) |
| Price | $0, gated by approval | | `official-docs` |

**Read these two points together.** "Use the Accounts API, not the Content Posting API" is the dossier's
reasoned conclusion, not a TikTok statement. And the Content Posting audit's "wide audience, not internal or
private use" criterion may be applied in Accounts API review too, so an agency-internal fleet might fail the
same test. Approval odds are unknown (SPV SP-6).

### 3.3 LinkedIn

| Capability | API | Requirements and limits | Evidence |
|---|---|---|---|
| Company Page posts, comments, reactions, org analytics | **Community Management API**, a **vetted** product | **Development tier: 500 requests per app per day, 100 per member per day**, to finish the integration within 12 months of access. **Standard tier** needs a screencast of each use case; its limits are not published (see the app's Analytics tab). **Marketing API version 202510 sunsets 2026-10-15**, so connectors send the current `LinkedIn-Version` header. | `official-docs`; SPV V-3 |
| Member (personal) posts | "Share on LinkedIn", `w_member_social`, `POST /v2/ugcPosts` | **150 requests per member per day; 100,000 per app per day.** | `official-docs` |
| Member post analytics | `r_member_social` | A "**closed** permission. We're not accepting access requests." The overview does list member analytics as an approved use case, so "closed" is narrower than the dossier states. | `official-docs`; SPV V-3 |
| Messages | Messages API | "Restricted to approved partners". **Each message must follow a specific member action. "Member actions do not include an automated or scheduled event."** The member must take an affirmative action to send after the draft is presented. | `official-docs`; SPV SP-8 |
| Connection requests, InMail, groups | No public API found | Browser-only in the market; **not in the fleet** (section 6) | `unverified` (an absence) |
| Price | $0, gated by vetting | LinkedIn reserves the right to review applications and select partners at its discretion | `official-docs` |

**Terms.** User Agreement §8.2 bars scripts, robots and crawlers that scrape or copy the Services, and "bots or
other unauthorized automated methods to access the Services, add or download contacts, send or redirect
messages, create, comment on, like, share, or re-share posts". It also bars using another's account "such as
sharing log-in credentials or copying cookies" (`official-docs`; SPV V-6; APV V-4). The help centre says
third-party software that automates activity risks "accounts restricted or shut down". The "about 100
invitations a week" number in the market is vendor folklore; LinkedIn publishes none.

**The fleet's LinkedIn position, in one line:** Pages and member posts through the official APIs; **everything
else is a draft that a human sends from their own session.** Paid Sponsored Messaging is a separate
automated-at-scale channel that nobody has researched (SPV SP-8, missed issue 7).

### 3.4 X (X API v2)

#### 3.4.1 Capabilities

| Capability | API | Notes | Evidence |
|---|---|---|---|
| Post (text, media, poll, quote, reply, community) | `POST /2/tweets` (`CreatePostsRequest` has `community_id`, `poll`, `media`, `made_with_ai`, `paid_partnership`, `reply_settings`) | Per-user 100 posts per 15 minutes. See section 4 for the per-app question. | `official-docs` |
| DMs (legacy DM events) | `POST /2/dm_conversations/with/:participant_id/messages` and related | 15 per 15 minutes per user; 1,440 per 24 hours (see the caveat in section 4). Whether legacy `dm_events` sees conversations that users start in encrypted **X Chat** is `unverified`. | `official-docs` |
| Analytics | Metrics fields on posts; reads are billed per resource | **Competitive benchmarking is prohibited** ("App benchmarks X performance vs competitors") | `official-docs`; SPV missed issue 5 |
| Pricing model | **Pay-per-usage credits, "no subscriptions".** Spending limits and auto-recharge are configurable. Monthly cap of 3 million Post reads, then Enterprise. | Prices are "subject to change". Legacy Basic and Pro tiers do not appear in the current docs. | `official-docs`; SPV SP-4 |

#### 3.4.2 Rules the connector and governor must carry

- **No browser, ever, by an agent.** "Non-API automation (scraping, browser automation) results in permanent
  suspension." The help page says "may result in the permanent suspension of your account" (SPV SP-1).
- **Automated accounts** using the API must enable the "Automated" profile label, disclose the operator in the
  bio, link a human-managed account, and honour opt-out (SPV V-8). **Whether human-approved, API-scheduled brand
  posting counts as "automated" is unresolved** (`pending Q-05`; default: assume the label is required and
  onboard no X identity until he answers).
- **Consent.** OAuth "does not by itself constitute sufficient consent to take automated actions through that
  user's account". The client must be told the types of automated action and give express consent for each,
  and opt-outs are honoured. This goes in the consent ledger (SPV V-7).
- **Replies.** An AI reply bot requires X's prior written approval. Automated replies based on keyword
  searches alone are not permitted. At most one automated reply per interaction (SPV V-7). The fleet's rule
  (SCN S03-7):
  1. **No reply and no DM goes out on X without a per-action approval of the exact text.** There is no
     unattended route.
  2. **Template items are refused for X.** A manifest item of kind `reply_template`, `dm_template` or
     `comment_template` on an X account is `refused` (non-approvable). A classifier or rule that picks a
     template is an AI-selected automated reply in X's terms, so the template route cannot be used even with a
     person watching it.
  3. **One automated reply per interaction** is counted in the conversation record (`replies_to_event`,
     section 2.6). A second reply to the same interaction is `refused`.
  4. **X stays off until Q-05 is answered**, and an AI reply bot also needs X's written approval, which
     nobody has asked for. X's approval does not remove the per-action approval.
- **DMs.** X allows a DM where the recipient has "requested or ... clearly indicated an intent" to be contacted,
  for example by sending a DM, with an easy opt-out (SPV SP-10). That is wider than the fleet's rule. The fleet
  replies only in a conversation the other party started (DEC D2; section 7.1). "Clearly indicated an intent"
  is not a reason for the fleet to start one.
- **Never:** automated likes; hiding replies in an automated manner (this is a rule for X only; hiding a
  comment on a Facebook Page or Instagram professional account is moderation, CH "Moderation"); duplicative or
  substantially similar posts across accounts you operate; posting about trending topics automatically
  (SPV V-7).
- **Profiling.** X's guidelines bar "Profiling, tracking, or monitoring users without consent". API lookups are
  not a lead source (SPV SP-11).
- **Checkpoints on X** come as a lock plus a CAPTCHA for automated behaviour, or limited features for
  "aggressive following or aggressive engagements" (`official-docs`, help.x.com locked-and-limited; SPV V-13).

---

## 4. Ceilings and costs

**Rule.** The governor is built from live headers and the platforms' own limit endpoints (section 2.4). The
numbers below are what the pages said on 2026-10-09 and 2026-10-10. They are inputs to a design, not constants
to hard-code.

### 4.1 Per-account ceilings (these bind first for client accounts)

| Platform | Ceiling | Evidence |
|---|---|---|
| Facebook Page | Reels: **30 API-published per 24-hour moving window per Page**. Scheduled posts: 10 minutes to 30 days ahead. Messenger: calls in 24 hours = **200 x engaged users**; Send API 300 calls a second per Page (text); Conversations API 2 calls a second per Page; **private replies 750 an hour per Page**. | `official-docs`; SPV V-5, V-10 |
| Instagram | **100 API-published posts per 24-hour moving window** (carousel = 1; the page also says 50: read `content_publishing_limit`). Non-messaging calls: **4,800 x impressions per 24 hours** per app-user pair. Messaging: Conversations 2 calls a second; text sends 100 a second (the same page also says 300; SPV V-5); private replies 750 an hour. | `official-docs`; SPV SP-5, V-5 |
| TikTok (Accounts API) | **6 video posts a minute, 15 a day per account. 40 QPM per account per endpoint.** Business Messaging: the 10 / unlimited-in-48-hours / 3 rule per non-mutual-follow conversation. | `official-docs`; SPV SP-6, V-4 |
| LinkedIn | Share on LinkedIn: **150 requests per member per day**. Community Management, Development tier: **100 per member per day**. | `official-docs`; SPV V-3 |
| X | **For unverified accounts, API use included: 50 original posts and 200 replies a day, 500 DMs a day, 400 follows a day,** plus follow-ratio limits after 5,000 following. The same page also keeps a legacy "2,400 updates per day". Per-user API limits: **100 posts per 15 minutes**; DMs 15 per 15 minutes; reads 15 per 15 minutes. | `official-docs` (Wayback snapshot 2026-09-26); SPV V-2 |

For X, the dossier's governor list used "100 posts per 15 minutes" as the per-account cap. **For an unverified
client account the binding cap is 50 original posts and 200 replies a day, 500 DMs a day** (SPV V-2).

### 4.2 Per-app ceilings

| Platform | Ceiling | Evidence and caveat |
|---|---|---|
| Meta | No per-app daily cap was found in the pages read. Graph "platform rate limits" apply to Business Discovery and Hashtag Search. | `unverified` |
| TikTok (Accounts API) | **600 to 1,000 QPM per app** | `official-docs`; SPV SP-6 |
| LinkedIn | Development tier **500 requests per app per day**. Share on LinkedIn: **100,000 per app per day**. Standard tier: not published. | `official-docs`; SPV V-3 |
| X | The X rate-limit page lists **10,000 posts per 24 hours per app** and **1,440 DMs per 24 hours per user and per app**. **These are legacy plan columns.** A 2025-06-17 snapshot shows them as Pro (10,000 per app; Basic was 1,667) carried onto a pay-per-use page that does not say which plan they apply to. The endpoints' OpenAPI security lists user-context auth only. **"Shared by all clients" is an inference, not something the page states.** | SPV SP-3, missed issue 3. Build the governor from `x-rate-limit-*` headers on live calls. Unverifiable until a live pay-per-use app exists (CON C-28). |

So do **not** plan on "X needs Enterprise at 1,000 accounts". That conclusion rested on the legacy columns
(SPV missed issue 3). Whether pay-per-use apps have a shared daily ceiling is a question for the first live app
(MS G4.4).

### 4.3 Costs

| Platform | API price | What costs money besides the API |
|---|---|---|
| Meta (Pages, Instagram, Messenger) | **$0** | Media hosting; webhook endpoint hosting |
| TikTok | **$0**, gated by approval | Verified domain and media hosting |
| LinkedIn | **$0**, gated by vetting | None |
| **X** | **Pay per use** (`official-docs`, X pricing page; "prices are subject to change"): Post create **$0.015**; Post create **with a URL $0.200**; Post create "summoned" $0.010 (definition not on the page); DM create $0.015; user interaction create (follow and similar) $0.015; delete $0.010. Reads: Post $0.005, User $0.010, DM event $0.010 per resource. "Owned Reads" $0.001 **only** when the id is the authenticated user and that user owns the developer app, so never for client accounts. 24-hour UTC de-duplication. **Webhook events are billed:** `dm.received` $0.010, `post.create` $0.005. | A spend cap per client and fleet-wide (`pending Q-06`; default: $0) |

Arithmetic, to size the line (`estimate`; the prices are `official-docs`, the workloads are mine):

- A link post costs $0.20 against $0.015 for a plain one, **13.3 times** as much.
- 30 plain posts a month on one account: $0.45. 30 link posts: $6.00.
- A read-back receipt on X costs $0.005. That is **33% on top of a plain post**, 2.5% on a link post.
- 1,000 accounts each making one link post a day: $200 a day. The dossier's "$600 a day" assumed 3 link posts a
  day on 1,000 accounts. The arithmetic is right and the workload is invented (SPV SP-4).
- DEC D12's cost table has **no X line at all** (CON C-17). Replace it with the governor's measured spend (MS
  §4.6 exit record).

### 4.4 Governor behaviour

- Reserve in the per-account window and the per-app window before the call; reserve the fee too (X).
- Over a ceiling: `rate_limited` with a retry-after, or `platform_limit` if the daily cap is spent. A 429 releases
  the reservation and is `failed_clean` (ARCH §4.6).
- Update windows from response headers after every call. Settle spend.
- The X cost meter stops at the cap. A client with no cap makes no paid call.

---

## 5. The API-versus-browser decision table

Legend. **API** = use the official API (safer, cheaper, deterministic). **Human** = a person does it, in their
own session or in the viewer; the agent may prepare a draft. **Never** = a red line. The table is **Branch A**.
For Branch B the only changes are in section 1.3.

| Task | Facebook (Page) | Instagram (professional) | TikTok | X | LinkedIn |
|---|---|---|---|---|---|
| Text or image post | API | API (image: JPEG) | API (photo post) | API ($0.015; $0.20 with a URL) | API (Page: Community Management; member: `w_member_social`) |
| Video, Reel, short | API (Reels 30 per 24 h per Page) | API (inside the 100 per 24 h) | API (15 a day) | API | API |
| Carousel | API (multi-photo) | API (up to 10) | API (photo post) | API (media) | API |
| Story | API (photo, video stories) | API (`STORIES`; stickers `unverified`) | **Human** (no API found, `unverified`) | n/a | n/a |
| Comment reply, hide, delete | API (hide and unhide under an owner-set rule, CH "Moderation") | API (same) | API | API, with a per-action approval of the exact text and no templates. Only users who engaged; one automated reply per interaction; AI replies need X's written approval. **Hiding a reply is refused on X.** (`pending Q-05`) | API (Page) |
| Reply to an inbound DM | API (24 h; 30 s bot rule; the 7-day tag is off, section 2.6) | API (24 h; private reply 7 d; the 7-day tag is off, section 2.6) | API (Business Messaging: open beta; not EEA, CH, UK; reviews) | API, only in a conversation the person started, with a per-action approval of the exact text (500 DMs a day per account; `pending Q-05`) | **Never automated.** A human sends. |
| Outbound or cold DM | **Never** | **Never** | **Never** | **Never** | **Never** |
| Likes, follows, engagement | **Never automated** | **Never automated** | **Never automated** | **Never automated** | **Never automated** |
| Analytics | API | API | API | API (paid reads; no competitive benchmarking) | API (Page); member analytics `r_member_social` is closed |
| Groups, communities | **Human** (Groups API removed 2024-04-22) | n/a | n/a | API (`community_id`) | **Human** (no API found, `unverified`) |
| Personal (non-business) account | **Human**, on their own device. The fleet may draft. Terms §3.1 bars giving others access to the account | Convert to professional, then API. Until then a person acts, and the fleet may draft | API (the Accounts API covers Personal accounts) | API | API (member posts only) |
| Login, 2FA, checkpoints | A human. OAuth for the API in the client's own browser; the viewer only for a browser identity. Per-platform playbook: section 6.3 | Same | Same | A human, **in the client's own browser** (OAuth). No agent browser on x.com and no browser identity | Same as Facebook |
| Proof a post is live | API read | API read | API read or webhook | API read (paid) | API read |
| Lead research | Open web only; or a consent-based channel | Open web only. Business Discovery is for benchmarking, not leads. | Open web only | Open web only. API lookups only to confirm a company's own handle that its own site links to. | Open web only |

Source: SPD Q6, corrected by SPV (SP-3, SP-10, SP-11, V-2, V-8) and by the charter on LinkedIn (CH red lines).
Two cells differ from the dossier: LinkedIn Groups and connections read **Human**, not "HITL-browser", because
the charter bans any LinkedIn browser automation; and the X DM cell is **narrower** than X's own rule "asked for
contact or showed intent" (SPV SP-10), because the fleet replies only in a conversation the other party started
(section 7.1).

**Where the browser fleet stays essential:** the human-login viewer (onboarding, re-auth, checkpoints);
open-web lead generation; the narrow no-API set under human-in-the-loop; sites with no API at all (directories,
forums, vendor portals); and sparing visual QA of a client's own public pages (SPD Q6).

**Infrastructure consequence.** Most of the 100 to 1,000 accounts need **no always-on browser for social work.**
Their social activity is API calls plus tokens. This cuts the RAM and proxy budget that scale-infra sized around
about 900 MB per Chromium (SPD Q6). The share of identities that need a browser at all has not been estimated;
M6b measures it (MS G6.5).

---

## 6. The human-in-the-loop browser set

These are the features with no usable API. Each is ToS-exposed. **A human approving does not make automated UI
driving permitted. Only a human doing it is clean** (SPD §5 risk 7).

**And the clean place for the human to do it is their own device, in their own session.** The viewer is not the
same thing (SCN G12-10). A person in the viewer is a human driving an automation-capable browser. Their input
arrives as CDP events in a browser that an automation stack controls, the Guard is attached to it, and the
terms exposure of an agency-run session stays ([identity-and-proxies.md](../identity/identity-and-proxies.md)
§2.2). The viewer is better than an agent clicking, because the act is a person's. It is **not** clean. So the
default for every row is "the human does it", **on their own device wherever they can**, and in the viewer only
where the fleet's own logged-in session is what the task needs. The agent prepares a draft.

DEC D2's allowed-uses table is the whole list. This table is its per-feature reading, and the last column names
the row.

| Feature | Why there is no API | Exposure | Default | Reading of DECISIONS |
|---|---|---|---|---|
| **Facebook Groups**: post or moderate | The Groups API was removed on 2024-04-22 (SPV SP-7) | Meta bars automated access; Spam policy: posting "either manually or automatically, at very high frequencies", with restrictions at lower frequencies for repetitive content. **Cross-posting one message to many groups is the classic spam pattern.** | The person does it, on their own device where they can. If a browser identity is used, a person clicks (section 6.1), and never the same text in many groups. | D2 row 2. **Which account type may act in a group is not researched** (AQ-10): until Justin answers, the acting `account_kind` must be `page` or `business`, and `profile` is refused |
| **Facebook personal profile**: post | No publish API since 2018 | All of the above, plus Terms §3.1: do not "give access to your Facebook account to others ... (without our permission)". **Letting a fleet operate a client's personal profile without Meta's permission is itself a terms breach.** | **Not offered. No browser identity.** The person posts themselves, on their own device. The fleet may draft (`draft_for_human`). | D2 row 3. **Aligned.** DEC D2 withdrew its old wording |
| **Instagram personal account** | Instagram APIs serve professional accounts only | Instagram ToS: no "accessing or collecting information in an automated way without our express permission, regardless of whether ... logged-in" | **Convert to professional (free), then use the API.** Until then the person does it, and the fleet may draft. No browser identity. | D2 row 4 |
| **UI-only creative features** (story stickers, licensed music, some edit tools; TikTok stories and LIVE) | Not in the publishing APIs. Instagram lists shopping tags and filters as unsupported. Stickers and music are `unverified`. | Same ToS exposure | The person does it. Low volume. | D2 row 5 |
| **LinkedIn** connection requests, DMs, InMail, groups | No public API, or a partner-only API with a member action per message | User Agreement §8.2 bans bots and automation add-ons; "restricted or shut down" | **Agents draft. A human sends from their own session.** The fleet runs no LinkedIn browser at all and creates no browser identity. | D2 row 6. **Aligned** (the dossier's "HITL-browser" means "a human does it") |
| **X**: anything | X offers an API for everything the fleet should do | "Non-API automation ... results in permanent suspension" | **No agent browser on x.com and no browser identity.** A person who must use x.com uses their own device. | D2 row 7; CH invariant 6. No exception row exists |
| **OAuth consent, login, 2FA, checkpoints** | By design | None if a human does it | A human. For an API connection, in the client's own browser. For a browser identity, in the viewer. The playbook is section 6.3. | D2 row 9; D14 |
| **Sites with no API** (directories, forums, vendor portals) and **visual QA** of a client's own public pages | n/a | The site's own terms and robots.txt | A `research` identity, read-only, no login, no form submit. Not a social write. | D2 row 8 |

### 6.1 Who authorizes and who clicks (rows 2 and 5; row 10 only if Q-01 goes browser-first)

This was decided in DEC D2 (rows 2, 5 and 10): each action in the narrow set is human-approved, and a person
clicks. ARCH §3.2 (`click_mode`) and §4.7 step 6 now agree on `human_clicks`. **ARCH §4.7 step 2 and §8.2 do
not fully agree.** They still allow `browser_hitl: "manifest"` for an accepted client. For rows 2 and 5 that is
out of line with D2, and ARCH should refuse manifest mode for them. This closes SCN S08-9, where this page said
`human_clicks` and ARCH's earlier draft said `agent_clicks`.

- **The client's signed risk acceptance is on file** before any browser effect (ARCH §3.7; MS G4B.2).
- **Who authorizes: a per-action approval.** `browser_hitl` is `per_action`. For rows 2 and 5, a manifest
  **never** authorizes a browser effect. The approval names the exact content hash, target, account, audience
  and irreversible effects (ARCH §4.7). For row 10, whether a manifest may authorize a browser effect is a
  Q-01 sub-question (ARCH §8.4); the default stays `per_action`.
- **Who clicks: a person.** The default is `human_clicks`. The operator takes over in the viewer, sees the
  filled composer and presses Post. The effect is recorded with `channel=human`. It costs an operator a
  minute. `agent_clicks` exists only when the owner sets it on **that identity** (`channel_policy.click_mode`),
  and then every click needs its own per-action approval.
- **Under `human_clicks`, the intent row is written at takeover.** When the operator takes the lease for an
  approved action, fleetd writes the `intent` row at that moment, before anything can be pressed. If the
  viewer, the node or the operator's connection dies after the click, the effect is already `uncertain` and
  held, and the read-back settles it. It is never forgotten. ARCH §4.7 step 7 puts the intent row before the
  click. This page fixes the moment as takeover.
- **If the operator takes over and never presses Post,** the closure form says "no effect" (ARCH §4.14). The
  person's word alone is not a receipt (DEC D13), so fleetd runs the same read-back as ARCH §4.7 step 7. If it
  returns `absent` with the known-positive check passed, the intent row settles as `failed_clean` and the
  approval and the cap come back. If it returns `found` or `unobservable`, the row stays `uncertain` and the
  owner settles it with `human_resolved`, with the person's answer as evidence. An abandoned takeover therefore
  leaves a hold only when the page cannot show that nothing happened. `design`.
- **A viewer reconnect after a crash shows what was in flight.** The viewer opens with a banner: "An action was
  in progress. Check the group before pressing Post again." It names the target and the approved text. The
  person closes it with the closure form (ARCH §4.14): it posted, it did not post, or cannot tell. Nothing
  retries on its own. The connection must never leave the person looking at a filled composer with no
  warning.
- **Pre-submit check:** the composer text read back must hash to the approved content, and the page's account
  header must equal the identity's handle (ARCH §4.7 step 5).
- **A low-volume cap set by the owner.** There are no official numbers for a safe cadence on any platform
  (SPV V-12). Published ceilings are ceilings, never targets.
- **First-post gates:** the first post per account, per new content type and per new destination always needs a
  human (MS §4.6.1).
- **No scheduled keep-warm login probes on Meta identities.** The dormancy trigger names empty accounts, and a
  scripted probe adds exposure (SPV SP-9; [identity-and-proxies.md](../identity/identity-and-proxies.md) §2.4).
- **Receipt and uncertainty:** a separate read-back step, with a grace window (feeds index late; DM requests
  land in other folders). Not found means `uncertain` and a hold. Never an automatic resend (ARCH §4.7).
- **Never the same text in many destinations.**

### 6.2 Leaving the set

A feature leaves this set when the account is converted (Instagram), the platform adds an API, or the client
stops wanting it. The aim is for the set to shrink.

### 6.3 Re-auth playbook, per platform `design`

This closes SCN S05-10. Two different things share the word "login", and most platforms only ever have the
first.

- **An API connection** (the OAuth grant) expires, is revoked or loses a scope. The state is `needs_reauth` with
  kind `api_connection` (ARCH §4.6). The fix is an OAuth link that the client's authorised person opens in
  **their own browser**, on their own device, with their own password and second factor. The fleet relays
  nothing. The viewer is not involved.
- **A browser identity's login** (the logged-in session in the fleet's own browser) expires or is challenged.
  The fix is a person at the viewer, by the runbook and the second-factor table in
  [identity-and-proxies.md](../identity/identity-and-proxies.md) §2.2.1 and §2.2.2. A browser identity exists
  only for what DEC D2 allows: Facebook Groups and the UI-only features (rows 2 and 5), and row 10 if Q-01 goes
  browser-first. A `research` identity never logs in.

| Platform and account | What needs a login | Who is present | How a code reaches the typist | May the client open the viewer? | What the owner tells the person when a phone approval is needed |
|---|---|---|---|---|---|
| Facebook Page, Instagram professional, TikTok business (D2 row 1) | An API connection only. No browser identity. | The client's authorised person, or a Business Manager admin | It is not relayed. They read it off their own phone and type it into the platform's own page, on their own device | No viewer is involved | Message A (below) |
| Facebook Groups, and UI-only features of a Page, professional or TikTok business account (D2 rows 2 and 5) | A browser identity login, only if the fleet's own session is needed. Otherwise the person acts on their own device and nothing logs in | The person who holds the account login and the second factor | The holder types it at the viewer ([identity-and-proxies.md](../identity/identity-and-proxies.md) §2.2.2). Never sent to staff | Design default: yes, as a `tenant_viewer`, own tenant only. **Pending AQ-1.** Until AQ-1 is closed, the viewer path for a client-held login is blocked (ARCH §4.8), and the person acts on their own device | Message B (below), which is the message in identity-and-proxies.md §2.2.2 |
| Facebook personal profile, Instagram personal account (D2 rows 3 and 4) | Nothing. There is no browser identity and nothing to re-authenticate | n/a | n/a | n/a | n/a. The person acts on their own device |
| LinkedIn (D2 row 6): Page and member posts by API | An API connection, re-authorised by the member in their own browser. Everything else is a person in their own session | The member | Not relayed | No viewer is involved | Message A |
| X (D2 row 7) | An API connection (OAuth) in the client's own browser. No browser identity. X stays off until Q-05 | The account holder | Not relayed | No viewer is involved | Message A |
| A `research` identity (D2 row 8) | Nothing. It never logs in. A login wall on a site is a per-domain `blocked` result (ARCH §3.8) | n/a | n/a | n/a | n/a |

**Message A, for an API connection.** The owner sends it with the link the connector gives. The owner does not
paraphrase it into a request for a code.

> You will get a sign-in link from us for <platform>. Please open it on your own computer. Sign in the way you
> normally do. The platform may ask you to approve on your phone, so keep it near. Approve only if you started
> this sign-in. We never ask for your password or a code, by any route. If something looks wrong, close the
> page and tell us.

**Message B, for a viewer login with an approval on another device.** It is the message in
[identity-and-proxies.md](../identity/identity-and-proxies.md) §2.2.2. Keep one copy of the wording, there.

**A checkpoint instead of a login wall.** The person settles it with the platform on their own device. The
identity cools down. Nobody retries from the viewer the same day (identity-and-proxies.md §2.2.1 step 6,
§2.5).

**The patched-kernel note.** If client staff ever reach a patched-kernel browser through the viewer, the kernel
vendor's OEM or SaaS clause (CloakBrowser in the research) is arguably in play (DEC D9; Q-03). That is moot
under the Q-03 default, which uses no patched kernel. Read the clause again before Q-03 changes.

---

## 7. Red lines

The fleet refuses these **in code, not by prompt**. A refusal is an answer (`refused`, non-approvable: it
creates no approval row, and no per-action approval unlocks it; DEC D17, CH "Tests behind the red lines"), not
an obstacle to route around. The authoritative list is [CHARTER.md](../../CHARTER.md); the test is MS G4.6 (an automated refusal
suite that must refuse 100%). This table adds the per-platform source.

| Never | Platform source (`official-docs` unless marked) |
|---|---|
| Fake accounts or personas, or an account for a client without their express permission | Facebook ToS §3.1; Instagram ToS ("you can't create an account for someone else unless you have their express permission"); X authenticity rules; TikTok ToS; LinkedIn |
| Ban evasion: a new account, identity or IP to get around a ban or restriction; circumventing a platform's technical access measures. Replacing an IP that the vendor took away is allowed, but only through the charter's test (CH "Replacing an IP is not ban evasion") | Facebook ToS §3.1 and §3.2; TikTok Community Guidelines ("you may not create or use another account to get around it"); X |
| Any outbound message to a person without prior contact or opt-in. "Prior contact or opt-in" is the closed list in section 7.1. A like, follow or view is none of it | Meta opt-in rule; TikTok "prohibited from initiating a conversation"; X automation rules; LinkedIn "member action" rule |
| Automated engagement: likes, bulk follows or unfollows, automated reposts, engagement pods, bought engagement | X automation rules and platform-manipulation policy; Meta Spam policy; TikTok fake-engagement rules |
| **On X only:** hiding replies in an automated manner. The fleet hides no reply on X, by any route. On Facebook Pages and Instagram professional accounts, hiding a comment on the client's own content is moderation and is allowed under an owner-set rule (CH "Moderation") | X automation rules: "You may not like posts or hide replies in an automated manner" (SPV V-7) |
| Identical or substantially similar posts across client accounts | X automation rules; Meta repetitive-content spam. A duplicate-content check runs before every publish. |
| AI auto-replies on X without X's prior written approval; keyword-triggered auto-replies; template or classifier-picked replies on X; auto-posting about trends; more than one automated reply per interaction (section 3.4.2) | X automation rules (SPV V-7) |
| **Any agent-driven browser on x.com** | X developer guidelines (SPV SP-1) |
| **Any LinkedIn action by browser automation**, and any LinkedIn message or connection request sent by a bot or script. Posts and comments go through the official API; agents draft the rest | LinkedIn User Agreement §8.2; Messages API rule (SPV SP-8) |
| Competitive benchmarking on X | X developer guidelines: "prohibited competitive analysis" (SPV missed issue 5) |
| Agent-driven browsing of social platforms for research (trends, competitors, audiences, hashtags, other accounts' pages), logged in or out, from any identity. Public performance data comes only through the client's own API analytics | TikTok bans automated extraction; Meta Terms §3.2; CH host policy ("Where an agent may point the browser") |
| Downloading TikTok content to repost elsewhere | TikTok Accounts API prohibited uses |
| Paid enrichment services (Clay, Apollo, Hunter, ZoomInfo, Ocean.io and the like) in how an agent gathers data | Justin's standing rule |
| Typing a credential, answering 2FA, solving or paying to solve a CAPTCHA, clicking through a checkpoint on a client account | CH invariant 4 |
| Splitting one platform across many developer apps to dodge limits | Risk of "circumvent rate limits" enforcement (SPD §5 risk 4); `design` rule here |

Anti-detect techniques aimed at defeating a platform's access controls on a client account are on the same list
(Facebook ToS: "circumvent, bypass, or override any technological measures"; X: "work around any technical
limitations"). See [identity-and-proxies.md](../identity/identity-and-proxies.md) section 5.

### 7.1 "Prior contact or opt-in": the closed list

The charter's rule is absolute: no outbound message to a person without prior contact or opt-in (CH red
lines). "Prior contact or opt-in" is **exactly these entries and nothing else** (SCN G11-10). The fleet checks
them in code against its own inbound store (DEC D2; ARCH §3.12, §4.12 gate R). A reply or DM to a conversation
with no entry is `refused`.

| # | Entry | What the inbound store must show | How long it counts |
|---|---|---|---|
| 1 | **An inbound message** | A signature-checked message from that person to the client's account, in that conversation. A story reply arrives as a message and counts | The platform's window (section 3.1.3; TikTok's counted rule, section 3.2). On X, the conversation the person started, with the limits in section 3.4.2 |
| 2 | **A keyword opt-in** | An inbound message (entry 1) that carries a keyword on the client's owner-set opt-in list, with a consent record for the topics the person asked for. The opt-in is the message itself. A tick box elsewhere is not it | As entry 1. The opt-out phrase ends it at once. Whether a keyword opt-in is sufficient consent under each platform's and each law's wording is unresearched (MS N-10) |
| 3 | **A comment answered by a private reply, inside 7 days** | The person's own comment on the client's own post or ad, and the private reply sent inside 7 days of that comment (section 3.1.3) | 7 days from the comment |
| 4 | **A form submission** | A submission to a form that names the client, as recorded under lead-gen Part A ([lead-gen.md](../playbooks/lead-gen.md) §2.3) | **It makes the client entitled to contact the person on that form's terms. It is not a trigger for a fleet DM.** DEC D2 allows a fleet reply or DM only to a conversation the other party started. If the person then writes, entry 1 applies |

**None of these is prior contact:** a like, a follow, a view, a story view, a profile visit, a share, a repost,
a tag, being on a list, a reaction, an email address found on a public page, or a lead the fleet found. Engaging
with a client's content does not invite a message from the client. A person who liked a post gets no DM.

A **public reply** under a comment or a mention on the client's own content is a reply to someone who wrote
first, in the place they wrote. It is not an outbound message. It still goes through the conversation record
(section 2.6), and on X it needs a per-action approval (section 3.4.2).

**Opt-out** is honoured on every platform. An opt-out phrase sets `opted_out` and ends every entry above.

**Human-in-the-loop points** (the job pauses until a human acts; SPD Q4, MS §4.6.1):

1. Every login, 2FA, CAPTCHA, checkpoint, "verify your account", security lock or appeal.
2. OAuth connection of each client account to each platform app, with express consent per action type (X).
3. The first post on each account, the first post of each new content type (Reel, Story, carousel), and the
   first post to each new destination (a Facebook Group, an X Community).
4. **There is no approval point for an outbound message to a person outside the list in section 7.1.** It is
   refused, so there is nothing to approve. Outside a conversation's window, a person may answer from the
   platform's own inbox on their own device, and the fleet may write the draft (`draft_for_human`). On
   LinkedIn, every message is a person's, sent from their own session (DEC D2 row 6).
5. Every browser-only write: approval per action.
6. On X, every reply and every DM: a per-action approval of the exact text. No template route exists on X
   (section 3.4.2).
7. Deletes, profile and bio changes, privacy or visibility changes, ad or boost actions, anything with money.
8. Any uncertain outcome (a timeout mid-publish). Reconcile by API read. Never auto-retry a write.

---

## 8. Receipts per platform

**A receipt is an independent read-back through the platform, not the HTTP 2xx** (DEC D13; ARCH §4.6). The
sequence: a 2xx with an id, then fetch the object (or list recent posts) and match the id plus the content hash
or a marker, then `committed`. A 4xx that the platform guarantees had no effect is `failed_clean`. A timeout, a
5xx or a network error is `uncertain` and holds the identity. A 429 releases the reservation and is
`failed_clean`.

Endpoint names below are the ones the dossier recorded (SPD Q1). The read-side calls, fields and match keys were
**not read in detail**; confirm each at build time. Every row is `design`.

| Effect | Platform | Write returns | Read-back to confirm | Watch for |
|---|---|---|---|---|
| Page post | Facebook | A post id from `POST /{page_id}/feed` | Fetch the post by id; list recent Page posts to match content or a marker | A scheduled post is not yet live. Match on the scheduled state. |
| Reel | Facebook | An upload session, then publish | Poll the video status, then fetch the video | Reels cap of 30 per 24 hours |
| Image, video, Reel, carousel | Instagram | A container id (not an effect), then a media id from `media_publish` | Fetch the media and its permalink. Poll `status_code` to `FINISHED` first for video. Read `content_publishing_limit`. | The container is not the effect. Two steps, one effect key. |
| Comment reply, hide, delete | Facebook, Instagram | A comment id | List or get the comment | |
| DM reply | Messenger, Instagram | A message id from the Send API | Read the conversation through the Conversations API | Webhook delivery does not mark messages read. Requests-folder threads idle 30 days are not returned (Instagram). |
| Video or photo post | TikTok | A publish result from `/business/video/publish/` or `/business/photo/publish/` | A post-status webhook, or `/business/video/list/` | Daily cap of 15 per account |
| Comment reply | TikTok | A comment id from `/business/comment/*` | List the comments | |
| DM reply | TikTok | A send result from `/business/message/send/` | Conversation content list (latest 20) | Open beta; not EEA, CH, UK |
| Page or member post | LinkedIn | A post identifier (URN) | Fetch or list the post (endpoint to confirm at build; the dossier says only "API read") | Development tier 500 calls a day: read-back competes with writes for the same budget |
| Post | X | A post id from `POST /2/tweets` | `GET /2/tweets/:id`, **$0.005 a read**, or a billed webhook event | 33% overhead on a plain post (arithmetic) |
| DM | X | A DM event | Read the DM event, **$0.010** | Whether legacy `dm_events` sees X Chat conversations is `unverified` |

**What is proven and what is not** (DEC D13). The intent, receipt and hold pattern is proven in the trial's code
against a synthetic CRM. Read-back receipts for **API** channels rest on API reads and are the strong case; their
false-negative rate is still logged (MS G4A.1). Read-back for **browser-driven** social actions is a
**hypothesis** `[Branch B]`; its false-negative rate sets the human reconciliation load (MS G4B.1). Visible
confirmation text on a page is an observation, not proof (SCD Q3).

---

## 9. Approvals are milestone dependencies

One developer app per platform, owned by Justin's business, authorized by each client. Each approval is external
and discretionary; **any can be refused or stall.** None has been applied for (`pending Q-06`; default: nothing
applied for, nothing assumed approved). M4's common gates do not wait on them. **A platform's connector is marked
ready only when its approval is recorded** (MS G4A.5; states: not applied, applied, approved, refused). A
channel without its approval is not offered (CH invariant 6).

| Platform | Approval or dependency | What it unlocks | Can work proceed without it? |
|---|---|---|---|
| **Meta** | A Meta app. **Business Verification** and **App Review** for **Advanced Access**. | Accounts you do not own or manage | **Yes, for development and the M6a canary:** Standard Access works for Justin's own accounts and accounts added in the app dashboard (SPV V-1). Client accounts at scale need Advanced Access. |
| **TikTok** | The **Accounts API access application form** (mandatory since 2026-03-20) and app approval. For Business Messaging: the **Data Security and Privacy Review**, plus the US review and addendum for US accounts. | Publishing, comments, insights; DMs | No for client accounts. The Content Posting API is not a substitute: unaudited clients are private-only, and its audit rejects internal upload tools (SPV SP-6). |
| **LinkedIn** | **Community Management API vetting.** Development tier first, then **Standard** with a screencast of each use case. | Page posts, comments, analytics | Development tier limits apply meanwhile. LinkedIn selects partners at its discretion. |
| **X** | A **developer account and prepaid credits**, with a spending limit. **Written approval from X for any AI reply bot.** The Automated label decision (`pending Q-05`). | Posting, DMs, reads | The X ceilings stay `unverified` until a live pay-per-use app exists (MS G4.4). No X identity is onboarded until Q-05 is answered. |
| Shared infrastructure | A verified public domain for media (Meta fetches by URL; TikTok requires a verified domain); HTTPS webhook endpoints; a Business Manager | Media posts; inbound webhooks | |

Sequence inside M4 Branch A (MS §4.6.3): common core (manifests, ledger, scopes, governor, approvals,
checkpoint handler, spend ledger, consent and opt-out ledgers, red-line refusals) first, then the connectors,
then the consent-based lead channels last (`pending Q-14`). Each platform passes its own gates G4A.1 to G4A.5.

---

## 10. Pending Justin's answers

The text proceeds on the recommended default. Questions are numbered as in DECISIONS.

| Q | Question | Default used here | Where it bites |
|---|---|---|---|
| Q-01 | API-first or browser-first; which clients sign | API-first. Browser-first per client only with written acceptance. | Section 1, 5, 6, 8 |
| Q-05 | X "Automated" label on client brand accounts | Treated as required; **no X identity onboarded** until answered | 3.4, 9 |
| Q-06 | Apply for Meta App Review and Business Verification, TikTok Accounts API, LinkedIn CM API, X pay-per-use; monthly caps | Nothing applied for; every cap $0 | 4.3, 9 |
| Q-07 | Data handling for client page content | Both zero-data-retention routing and per-client consent. No DM content goes to a model provider (CH invariant 8). | 2.3: DM replies come from approved templates or a human, not a model reading the thread |
| Q-14 | Consent-based lead channels as first-class | Yes, built last in M4 | 0, 9; [lead-gen.md](../playbooks/lead-gen.md) |
| AQ-1 | How people sign in to the viewer broker (so the client's own person can open it as a `tenant_viewer`) | Passkeys plus a `tenant_viewer` role (DEC D14, AQ-1). **Pending.** Until it is closed, the viewer path for a client-held login is blocked | 6.3 |
| AQ-8 | Does a human-approved AI draft count as an "automated bot", and may the HUMAN_AGENT tag be used at all | Treated as automated. **The tag is off.** If Justin wants it, only on an operator compose path (section 2.6) | 2.3, 2.6, 3.1.3 |
| AQ-10 | Is a Facebook Groups session a personal-profile session | Not researched. The acting account must be a Page or business account | 6 |
| Q-03 | Patched-kernel dependency | No dependency (so the OEM clause is moot) | 6.3 |

Related decisions this plan adds (MS §5.4): `N-8` where owner approvals show up (not chosen); `N-9` connector
build versus Composio (research first); `N-10` client contract terms and legal review for GDPR and CCPA (not
researched).

---

## 11. Open and unverified

1. **Composio** (N-9): not researched.
2. **The connector layer's egress IP** (section 2.5; CH invariant 9).
3. **Read-side endpoints, fields and match keys** for every receipt (section 8).
4. **The Messenger 30-second rule** against a slower, approved reply (section 2.3), and whether the HUMAN_AGENT
   tag may be used on a message a person only approved (section 2.6; AQ-8).
5. **Consent-based lead channel APIs.** Lead Ads, opt-in DM capture, LinkedIn Lead Gen Forms and TikTok instant
   forms are named as official lead sources (SPV SP-11) and nothing more. Permissions, approvals, retrieval
   method, form rules and fees are **unresearched**. See [lead-gen.md](../playbooks/lead-gen.md) part A.
6. **Whether an agency-managed client account fits Meta Standard Access** (interpretation, SPD §5 risk 3).
7. **TikTok approval odds** for an agency-internal fleet, given the "wide audience" criterion (SPV SP-6).
8. **X per-app ceilings** and the real shape of the pay-per-use limits (needs a live app).
9. **X Chat coverage** by legacy `dm_events`.
10. **Paid LinkedIn Sponsored Messaging**, Messenger One-Time Notification and Sponsored Messages: outbound-after-
    contact or paid channels, not covered, not used (SPV missed issue 7).
11. **Token lifetimes** for X and LinkedIn, and Facebook Page tokens.
12. **Platform behaviour of any kind:** checkpoint triggers, safe cadence, whether API activity resets Meta's
    dormancy clock. Every statement here is document analysis (SPV missed issue 12). Measured only in M6a, on
    Justin's own accounts.
13. **GDPR, CCPA and agency liability** (MS N-10; SPD §5 risk 10).
14. **Whether a keyword opt-in is sufficient consent** under each platform's wording and each law (section 7.1,
    entry 2; MS N-10).
15. **Doc-internal conflicts**, not resolved by the platforms: Instagram publishing 100 versus 50; Instagram text
    send rate 100 versus 300 a second; X's "2,400 updates per day" beside the 50-and-200 daily limits; LinkedIn
    member analytics "closed" versus approved use case text (SPV V-5, V-3, SP-5).

---

## 12. Where the evidence is

The platform pages themselves are not in the corpus (the corpus holds the engine vendors' docs). The dossier's
source list is [SPD §6](../../research/dossiers/social-platforms.md): Meta developer docs rendered 2026-10-10,
TikTok Business API doc ids, X docs as Markdown (docs.x.com, 2026-10-10) and a Wayback copy of help.x.com,
LinkedIn Microsoft Learn pages, and terms files from the Open Terms Archive at pinned commits. The author's
rendered copies live in scratch outside the repository, so **re-fetch each page before building a connector.**
The verifier re-read the load-bearing ones by other routes (SPV method section).

Related corpus paths:

| Topic | Path |
|---|---|
| Browserbase CAPTCHA solving (default on; every Browserbase identity sets it off) | `https://docs.browserbase.com/platform/identity/captcha-solving.md` |
| Steel live viewer and human takeover (the login surface for the browser set) | `https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions.md` |
| Stagehand `extract` (used for visual QA and open-web reads) | `https://docs.stagehand.dev/v4/basics/extract.md` |

---

## 13. Where this page differs from, or adds to, DECISIONS

1. **Personal profiles.** **Aligned.** DEC D2 withdrew "personal profiles" from the narrow browser set. Rows 3
   and 4 give a personal Facebook profile and an Instagram personal account no browser identity, and the fleet
   may only draft. Facebook Terms §3.1 bars giving others access to an account without Meta's permission, so a
   fleet operating a person's profile would be a breach, with or without a human approving (section 6).
2. **LinkedIn.** **Aligned.** DEC D2 row 6 says a person acts in their own session and the fleet drafts. The
   charter bans any LinkedIn browser automation. ARCH §8.3 may still list "LinkedIn connection requests and
   DMs" among the rows that `browser_allowed` can hold under Answer A. That should be reconciled in ARCH: those
   rows stay empty for LinkedIn.
3. **X.** **Aligned.** DEC D2 row 7: no agent browser, no browser identity, no exception row. An earlier draft
   of this page allowed "a human in the viewer if essential". That is withdrawn. A person who must use x.com
   uses their own device.
4. **X per-app ceilings** are not stated as fact (DEC D2 already carries the correction).
5. **Carried forward from the verifiers** into the connector rules: the 30-second Messenger rule (SPV missed
   issue 8), the X Automated label (V-8), the two Meta onboarding models (missed issue 9), the TikTok "wide
   audience" criterion (SP-6), the Instagram `content_publishing_limit` read, the LinkedIn version sunset, the
   dropped `pages_show_list`.
6. **Additions, marked `design`:**
   - DM replies come from approved templates or a person, not a model reading the thread (section 2.3).
   - One developer app per platform is a rule, not a preference (section 2.1).
   - **The HUMAN_AGENT tag is off by default**, with `human_agent_until` in the conversation record (section
     2.6). ARCH §4.12 step 6 permits a person-written message to use the tag, pending AQ-8. This page turns the
     tag off until a compose path exists and Justin decides.
   - **On X, template items are refused and every reply and DM needs a per-action approval**, with a reply
     counter in the conversation record (section 3.4.2). DEC D2 and the charter say "one automated reply per
     interaction" and "no AI reply bot without X's approval". This page goes further, because a classifier-picked
     template is an AI-selected reply.
   - **The closed list of "prior contact or opt-in"** (section 7.1). A form submission is on the list as the
     client's entitlement, and it is not a fleet DM trigger. DEC D2 allows a fleet reply only to a conversation
     the other party started. If Justin wants a form submission to trigger a fleet DM, D2 and ARCH gate R need
     a new eligibility basis.
   - **Under `human_clicks` the intent row is written at takeover**, and a viewer reconnect after a crash warns
     the person (section 6.1).
   - **The viewer is not the client's own device** (section 6), and the per-platform re-auth playbook (section
     6.3).
   - Three ARCH gaps this page needs: the fields `human_agent_until` and `replies_to_event` in ARCH §3.12; a
     refusal reason for a second X reply in ARCH §5.5; and refusing `browser_hitl: "manifest"` for D2 rows 2
     and 5 in ARCH §4.7 step 2 and §8.2.

---

## 14. Governance

**What an agent may do through this property:** publish approved manifest items on identities bound to its token
and inside its scopes (`read`, `draft`, `publish`, `dm`); write drafts for human approval; read analytics; reply
to inbound DMs from approved templates inside the window (never on X: section 3.4.2); report a wrong result
with `feedback`.

**What needs Justin's explicit yes** (CH): applying for or buying anything (developer apps, credits, spend caps);
a browser-driven write on Facebook Groups or UI-only features (and the client's written yes; a personal
Facebook profile and an Instagram personal account get no browser identity at all); turning on the
HUMAN_AGENT tag; any change to a scope, ceiling, approval gate or red line, including the closed list in
section 7.1; adding a platform or connector; connecting the fleet to the Jev trial.

**What nobody does:** cross a red line; put a token or credential anywhere but the vault; retry an effect whose
outcome is uncertain; approve one's own request; report a receipt that was not read back.

**Changing this page.** A platform fact changes only with a dated platform page behind it, tagged. A rule
changes through DECISIONS first. Do not copy any dossier claim the verification report refuted (CON §3a).

---

## 15. Scenario gap ledger (this page)

Each gap from the scenario stress tests (`research/scenarios/S01.md` to `S14.md`) assigned to this page, and
where it is handled.

| Gap | Severity | Handled in | Note |
|---|---|---|---|
| S03-6 | major | 2.6, 2.3, 3.1.2, 3.1.3, 5, 10 | The HUMAN_AGENT tag is disabled. An operator compose path (effect `channel=human`) is the only way it could return, and it is Justin's decision (AQ-8). `human_agent_until` is in the conversation record. ARCH §3.12 lacks the field. |
| S03-7 | major | 3.4.2, 2.6, 5, 7, 7.1 | No X reply or DM without a per-action approval of the exact text. Template items are `refused` for X. The one-reply counter is `replies_to_event`. X stays off until Q-05. |
| S05-10 | major | 6.3; identity-and-proxies.md §2.2.2, §2.5 | Per-platform playbook. The client-opened viewer is pending AQ-1. The OEM note is moot under Q-03. |
| S08-9 | major | 6.1 | Per-action plus `human_clicks` for rows 2 and 5. The intent row is written at takeover. A takeover that ends with "no effect" settles through a read-back. A viewer reconnect after a crash shows "Check the group before pressing Post again". ARCH §4.7 step 6 agrees. ARCH §4.7 step 2 and §8.2 still allow `browser_hitl: "manifest"`; rows 2 and 5 never use it, and row 10 is a Q-01 sub-question. |
| G11-10 | major | 7, 7.1, 3.4.2, 5, 6, 13 | Closed list of four. A like, follow or view is none. HITL point 4 is rewritten. The X DM cell and the personal-profile row are aligned with DEC D2. |
| G12-10 | minor | 6 (intro) | The client's own device is the clean route. The viewer is human-driven automation and keeps the exposure. |

