> **Read with its verification report.** [verification/social-platforms.md](../verification/social-platforms.md) re-checked every load-bearing claim here; where they disagree, the verification report and [DECISIONS.md](../../DECISIONS.md) win. Cross-dossier contradictions: [CONSISTENCY.md](../verification/CONSISTENCY.md). <!-- VERIFIED-BANNER -->

# Dossier: social platforms (Facebook, Instagram, TikTok, X, LinkedIn) for client accounts

Date of research: 2026-10-09/10. Author: social-platforms deep-dive agent (rerun after a usage-limit cut-off).
Provenance tags follow BRIEF.md: `hands-on`, `source-code`, `official-docs`, `vendor-claim`, `third-party`, `unverified`.
Scratch evidence (not committed): `S=<scratch>/spikes/social-platforms`.
Official doc pages were rendered with headless Chromium (`$S/render/render.cjs`) or pulled as Markdown
(`docs.x.com/*.md`), then grepped. Every number below comes from those files, not from memory.
Spend: $0. Containers started: none.

---

## 1. Verdict

1. **On four of the five platforms, the platform's own terms explicitly prohibit driving the logged-in web
   UI with a bot.**
   - **X** is the most explicit: non-API automation "results in permanent suspension" (docs.x.com developer
     guidelines, Oct 2026).
   - **Meta** forbids accessing the Products "using automated means (without our prior permission) ...
     regardless of whether such automated access or collection is undertaken while logged-in". It also
     forbids attempts to "circumvent, bypass, or override any technological measures".
   - **LinkedIn** bans "bots or other unauthorized automated methods to access the Services ... send or
     redirect messages, create, comment on, like, share, or re-share posts".
   - **TikTok** is narrower in wording. It bans automated *data extraction*, and automation tools "designed
     to bypass our systems". Its own Accounts API is the sanctioned route for posting.

   A browser agent that posts, replies or DMs as a client is a **terms violation, or on TikTok at best a
   gray area, and puts the client's account at risk**. `official-docs`
2. **Every routine "maintain the page" task has a free or cheap official API for business account types:**
   publishing, comment moderation, inbound-DM replies and analytics. The exception is X, which is
   pay-per-use. The API path is safer (sanctioned), cheaper (no browser RAM, no proxy, no LLM page reading)
   and more deterministic, which is the property the brief wants. **The fleet's social work should be API-first.**
   The per-profile browser stays the main tool for open-web lead generation and a small set of no-API features.
3. **Several capabilities do not exist through any channel.** The fleet must not build them:
   - cold or outbound DMs (Meta, TikTok and X APIs only reply to people who wrote first; LinkedIn requires
     a human click for every message),
   - automated likes (X bans them for every app),
   - bulk follows,
   - identical posts across many client accounts (X; Meta treats repetitive content as a spam signal),
   - AI auto-replies on X without X's prior written approval.
   `official-docs`
4. **The real browser-only surface is small:**
   - Facebook Groups (the API was removed on 2024-04-22),
   - Facebook personal profiles (no publish API since 2018),
   - Instagram personal (non-professional) accounts (no API since 2024-12-04),
   - LinkedIn connection requests and DMs (no usable API),
   - a few UI-only features (for example TikTok and Instagram story stickers; not verified).

   Each of these is a ToS-exposed action. It needs human approval per action, low volume, and the client's
   written risk acceptance. The better fix is often converting the account: switching Instagram to a
   professional account is free. `official-docs` + `unverified` where marked.
5. **Approvals are the long pole, and they are milestone dependencies, not per-client steps.** One developer
   app per platform, owned by Justin's business, which every client then authorizes:
   - **Meta:** App Review, Advanced Access and Business Verification.
   - **TikTok:** the Accounts API access form (mandatory since 2026-03-20) and app approval. Business
     Messaging needs a data-security review, plus a US data-security review for US accounts.
   - **LinkedIn:** the vetted Community Management API (Development tier, then Standard tier with a screencast).
   - **X:** a developer account and prepaid credits.

   TikTok's Content Posting API audit explicitly rejects "a utility tool to help upload contents to the
   account(s) you or your team manages". Agencies must use the TikTok API for Business (Accounts API)
   instead. `official-docs`
6. **Some scale ceilings are per account, and the ones that bite at 100-1,000 accounts are per app,
   shared by every client on the fleet's single developer app:**
   - **Per app:** X allows **10,000 posts** and **1,440 DMs** per 24 h across all clients. LinkedIn's
     Development tier allows 500 requests per app per day.
   - **Per account:** Instagram allows 100 API posts per 24 h. Facebook Reels are 30 per 24 h per Page.
     TikTok allows 15 posts per day.

   The fleet needs a central rate and budget governor. `official-docs`
7. **X costs real money at scale.** A post costs $0.015; **a post containing a URL costs $0.20**; a DM costs
   $0.015; reads cost $0.005-0.010 per resource. Example: 1,000 X accounts × 3 link posts a day ≈ $600/day.
   The cheap "Owned Reads" rate ($0.001) applies only to the app owner's own account, not to client
   accounts. The Basic and Pro subscriptions are gone from the docs. `official-docs`
8. **There are no official numbers for checkpoint triggers or for safe action cadence on any platform.**
   The only hard numbers are published ceilings: X account limits and the API caps above. Treat them as
   ceilings, never targets. "Safe daily action" numbers (for example LinkedIn ≈100 invites/week) are vendor
   folklore. The triggers that are documented officially are:
   - automated behaviour, and aggressive following or engagement (X),
   - scripting, high frequency, repetitive content and **prolonged dormancy** (Meta),
   - automation tools (TikTok),
   - third-party software (LinkedIn).

   `official-docs` / `third-party`
9. **Stealth and anti-detect tooling pointed at Meta is itself a ToS issue.** Meta prohibits attempts "to
   circumvent, bypass, or override any technological measures". For client accounts the goal is
   **continuity** (same device, same IP, same human-like rhythm), not evasion. On X the fleet should not
   drive a browser at all, except a human using the live viewer. `official-docs`
10. **Lead generation is legitimate on the open web, not on the platforms.**
    - **Open web:** public company websites with robots.txt honoured, JSON-LD and contact pages.
    - **Platform APIs are not lead sources:**
      - Meta Platform Terms §3.a.v prohibits "Processing Platform Data without valid User consent in order
        to build or augment user profiles for any purpose".
      - X prohibits "Profiling, tracking, or monitoring users without consent".
      - Instagram Business Discovery is for benchmarking, not lead databases.
    - **Scraping platforms:** doing it from a logged-in client identity breaches the platform contract that
      client accepted. *Meta v. Bright Data* (2024) covered logged-off scraping only; *hiQ v. LinkedIn* ended
      in a $500k consent judgment.
    - **Hands-on spike:** a stdlib tier-0 fetch handled static pages for $0 in 70-344 ms per page.
      Escalation to a browser must key on whether the extraction goal was met, not on page shape: both
      shape heuristics misfired.

---

## 2. Answers

### Q1. Official APIs per platform (October 2026)

#### 1a. Facebook Pages (Meta Graph API v26.0)

| Capability | API | Limits / requirements | Provenance |
|---|---|---|---|
| Text/link/photo post, scheduled post | `POST /{page_id}/feed`, `/{page_id}/photos`; `published=false` + `scheduled_publish_time` | Page access token; `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`; user must have CREATE_CONTENT, MANAGE, MODERATE tasks on the Page | `official-docs` developers.facebook.com/docs/pages-api/posts (`$S/meta/https_developers_facebook_com_docs_pages_api_posts.txt`, rendered 2026-10-10) |
| Video | Video API | `publish_video` permission | same |
| Reels | `POST /{page_id}/video_reels` (upload session) | **30 API-published reels per 24 h moving window per Page**; 3-90 s; 24-60 fps; "You can only publish Reels to Facebook Pages" | `official-docs` /docs/video-api/guides/reels-publishing |
| Stories | `/{page_id}/photo_stories`, `/{page_id}/video_stories` | video story ≤ 60 s; CREATE_CONTENT task; `business_management` if using a system user | `official-docs` /docs/page-stories-api |
| Comments, @mentions, moderation | `/{post_id}/comments` etc. | `pages_manage_engagement`, `pages_read_engagement`, `pages_read_user_engagement` | `official-docs` /docs/pages-api/comments-mentions |
| Inbound DMs (Messenger) | Send API, Conversations API | Standard window **24 h** after the user's message (up to **7 days** after a click-to-Messenger ad). Message tags outside the window for approved use cases, including **HUMAN_AGENT (7 days)**. Private reply to a comment within **7 days**. Automated bots must answer within **30 s**. Bot disclosure where the law requires it (California, Germany called out). | `official-docs` /docs/messenger-platform/policy/policy-overview |
| Messenger rate limits | — | 200 × engaged users per 24 h; Send API 300 calls/s per Page (text); Conversations API 2 calls/s per Page; private replies 750/h | `official-docs` /docs/graph-api/overview/rate-limiting |
| Groups | **None.** `publish_to_groups`, `groups_access_member_info` and the Groups API were deprecated in v19.0 and removed for all versions on **2024-04-22**. `/docs/groups-api` now redirects to the docs root. | — | `official-docs` /docs/graph-api/changelog/version19.0 |
| Personal profile posting | **None.** `publish_actions` was closed to new apps on 2018-04-24 and removed for existing apps on 2018-08-01 (some extensions later). | — | `official-docs` developers.facebook.com/ads/blog/post/2018/04/24/platform-product-changes/ (via search; not re-rendered) |
| Server-side automation identity | Business Manager **system users**: "represent servers or software making API calls to assets owned or managed by a Business Manager" | System user tokens must not be used to act for a real user of your software | `official-docs` /docs/business-management-apis/system-users |
| Price | $0 | — | `official-docs` (no pricing in any Graph API doc) |

#### 1b. Instagram (Instagram Platform)

| Capability | API | Limits / requirements | Provenance |
|---|---|---|---|
| Account types | **Professional accounts only** (business or creator). Two login flavours: **Instagram Login** (no Page needed; `graph.instagram.com`; `instagram_business_*` permissions) and **Facebook Login for Business** (Page-linked; `graph.facebook.com`). | Personal accounts: **no API**. Basic Display API returned errors from **2024-12-04** (its doc URL now redirects to the platform overview). | `official-docs` /docs/instagram-platform/overview; Basic Display date from the Meta doc as quoted in search + redirect observed 2026-10-10 |
| Image, video, Reels, carousel, Stories | `POST /{ig_id}/media` (container) → `POST /{ig_id}/media_publish`; `media_type` = `VIDEO`/`REELS`/`STORIES`/`CAROUSEL`; trial Reels via `trial_params`; `is_ai_generated` flag | **100 API-published posts per 24 h moving window** (a carousel counts as 1). The carousel section of the same page still says 50, a stale internal inconsistency. Check usage with `GET /{ig_id}/content_publishing_limit`. Carousel ≤ 10 items. **JPEG only.** Shopping tags and filters not supported. Media must be on a **public URL** (Meta cURLs it), or a resumable upload (Facebook Login only). | `official-docs` /docs/instagram-platform/content-publishing |
| Page Publishing Authorization | A professional account linked to a Page that requires PPA cannot be published to until PPA is done | — | same |
| Comments | get / reply / delete / hide / unhide / disable comments on owned media; `instagram_business_manage_comments` | — | `official-docs` overview |
| DMs | `POST /{ig_id}/messages` | **Only after the user messages first.** 24 h standard window (up to 7 days after a click-to-Direct ad). `human_agent` tag gives 7 days. **Private reply** to a commenter within **7 days** (Live: only during broadcast). No group messaging. Requests-folder threads idle 30 days are not returned. Webhook delivery does not mark messages read. | `official-docs` /docs/instagram-platform/instagram-api-with-instagram-login/messaging-api, /private-replies |
| Rate limits | Non-messaging: **4,800 × impressions per 24 h** per app-user pair. Messaging: 2 calls/s per account (Conversations); 100/s text, 10/s audio/video sends; private replies 750/h (posts/reels). Business Discovery and Hashtag Search fall under Platform Rate Limits. | — | `official-docs` /docs/graph-api/overview/rate-limiting |
| Analytics | Insights endpoints (`instagram_business_manage_insights`) | — | `official-docs` overview |
| Access | **Standard Access** suffices "if your app only serves your Instagram professional account or an account you manage" (or accounts added to the app in the dashboard). **Advanced Access** for accounts you don't own or manage requires **App Review + Business Verification**. | — | `official-docs` overview; /docs/development/release/business-verification (updated 2023-07-07) |
| Price | $0 | — | `official-docs` |

#### 1c. TikTok

TikTok has **two different posting products**, and only one fits an agency.

| Capability | API | Limits / requirements | Provenance |
|---|---|---|---|
| **Accounts API (TikTok API for Business, "Organic API")**: publish, comments, insights | `/business/video/publish/`, `/business/photo/publish/`, `/business/comment/*` (create, reply, like, hide, delete, list), `/business/get/`, `/business/video/list/` | Authorized uses: "Manage the organic presence of brands or creators' owned accounts" covering publishing, moderating comments, insights and ad authorization. Covers **Business and Personal accounts**. **6 video posts/min, 15/day per account** via the endpoint. **40 QPM** per account per endpoint; 600-1,000 QPM per app. `video_url` must be on a **verified domain**; .mp4/.mov/.webm, ≤ 1 GB, 3-600 s. Since **2026-03-20** the Accounts API Access Application Form is required. **Prohibited**: downloading TikTok media or migrating it to other platforms, and building creator-discovery programs. Access token valid **1 day**; refresh token up to **365 days**. | `official-docs` business-api.tiktok.com docs ids 1737944384433218, 1762228496095234, 1738084416214017, 1776065099288577, 1776983576127490, 1738084387220481 (`$S/render/ttnode_*.txt`) |
| **Content Posting API (developers.tiktok.com)**: Direct Post / Upload-to-draft | `/v2/post/publish/creator_info/query/`, `.../video/init/`, `.../content/init/` (photos) | Unaudited clients: **SELF_ONLY (private) posts only, max 5 users per 24 h**. Audit criteria list as **not acceptable**: "A utility tool to help upload contents to the account(s) you or your team manages" and "an app that copies arbitrary contents from other platforms". Posting cap "typically around 15 posts per day / creator account", shared across all clients. | `official-docs` developers.tiktok.com/doc/content-sharing-guidelines, /content-posting-api-get-started |
| **Business Messaging API** (DMs) | Webhook on inbound message → `/business/message/send/`; conversation list (≤ 100); content list (latest 20); media upload (`media_id` valid 30 days) | **Open beta** (APAC, LATAM, METAP, North America); **not available in EEA, Switzerland or UK**. Requires an approved app plus the **Data Security & Privacy Review**; US accounts also need the **US Data Security Review** and USDS Addendum. "**You are prohibited from initiating a conversation**." Non-mutual-follow limits: 10 messages in the first 48 h, unlimited within 48 h of the user's last reply, then max 3 until the user replies. | `official-docs` ids 1832183871604753, 1832184145137922, 1832184236919810, 1854823717597185 |
| Stories, LIVE | No API found in either product | — | `unverified` (absence in docs read) |
| Price | $0 (gated by approval) | — | `official-docs` |

#### 1d. X (X API v2, docs.x.com, fetched as Markdown 2026-10-10)

| Capability | API | Limits / price | Provenance |
|---|---|---|---|
| Pricing model | **Pay-per-usage credits, "no subscriptions"**. Monthly cap of 3 M Post reads, then Enterprise. Spending limits and auto-recharge are configurable. Basic/Pro tiers do not appear anywhere in the current pricing docs. Third-party blogs say legacy Basic/Pro were closed to new sign-ups and migrated during 2026; not verified on an X page. | Writes: **Post create $0.015; Post create with URL $0.200**; DM create $0.015; user interaction (follow etc.) $0.015; delete $0.010. Reads: Post $0.005, User $0.010, DM event $0.010 per resource. Owned Reads $0.001 only "when `{id}` matches the authenticated user and that user is the owner of the developer app". 24 h UTC de-duplication. | `official-docs` docs.x.com/x-api/getting-started/pricing.md, /x-api/fundamentals/post-cap.md; `third-party` for the legacy-tier history (postproxy.dev, wearefounders.uk, 2026) |
| Post (text, media, poll, quote, reply, community, `made_with_ai`, `paid_partnership`, `reply_settings`) | `POST /2/tweets` (`CreatePostsRequest` has `community_id`, `poll`, `media`, `made_with_ai`, `paid_partnership`, `reply_settings`, ...) | **100 per 15 min per user; 10,000 per 24 h per app** | `official-docs` docs.x.com/openapi.json; /x-api/fundamentals/rate-limits.md |
| DMs (legacy DM events) | `POST /2/dm_conversations/with/:participant_id/messages` etc. | **15 per 15 min per user; 1,440 per 24 h per user AND per app.** Reads 15/15 min per user. | `official-docs` rate-limits.md |
| Encrypted DMs (X Chat API) | `/2/chat/*` + Chat XDK (client-side encryption, key management) | Separate product. It is unknown whether legacy `dm_events` sees chats that clients' users start in encrypted X Chat. | `official-docs` /xchat/introduction.md; `unverified` for coverage |
| Account-level limits (all clients, API included) | — | 500 DMs/day; **50 original posts + 200 replies/day for unverified accounts**; 400 follows/day; follow ratios after 5,000 following. The same page still mentions a legacy "2,400 updates per day". | `official-docs` help.x.com/en/rules-and-policies/x-limits (Wayback snapshot 2026-09-26, `$S/x/wb_rules-and-policies_x-limits.txt`; live page now Cloudflare-challenged) |
| Analytics | Metrics fields on posts; reads billed per resource | — | `official-docs` /x-api/fundamentals/metrics.md (index only) |

#### 1e. LinkedIn (Microsoft Learn docs)

| Capability | API | Limits / requirements | Provenance |
|---|---|---|---|
| Company Page posts, comments, reactions, org analytics | **Community Management API** | **Vetted** product. Development tier: 500 requests/app/day, 100/member/day; finish the integration within 12 months. Standard tier needs a **screencast** of each use case. Standard rate limits are not published (see the app's Analytics tab). Marketing version 202510 sunsets **2026-10-15**. | `official-docs` learn.microsoft.com/linkedin/marketing/community-management/community-management-overview (updated 2026-05-15), /marketing/increasing-access |
| Member (personal) posts | "Share on LinkedIn", `w_member_social`, `POST /v2/ugcPosts` | 150 requests/member/day; 100,000/app/day | `official-docs` /consumer/integrations/self-serve/share-on-linkedin (updated 2025-02-05) |
| Member post analytics | `r_member_social` | "**closed** permission. We're not accepting access requests" | `official-docs` CM overview FAQ |
| Messages | Messages API | "restricted to approved partners". **Each message must follow a specific member action; "Member actions do not include an automated or scheduled event."** The member must take an affirmative action to send. | `official-docs` /shared/integrations/communications/messages (updated 2023-05-08) |
| Connection requests, groups | No public API found | — | `unverified` (absence) |
| Price | $0 (gated by vetting) | — | `official-docs` |

### Q2. What still requires a browser, and the risk

| Browser-only feature | Why no API | Risk of doing it by browser | Provenance |
|---|---|---|---|
| Facebook Groups: posting as a member or admin, moderation | Groups API removed 2024-04-22 | Meta ToS forbids automated access even when logged in. Meta Spam policy: "Posting ... either manually or automatically, at very high frequencies"; restrictions "at lower frequencies when ... posting repetitive content". Cross-posting one message into many groups is the classic spam pattern. | `official-docs` Graph v19 changelog; facebook.com/legal/terms §3.2 (Wayback `20261010002416`, verbatim); Meta Community Standards (Open Terms Archive pga-versions `7f52733`, 2026-09-24) |
| Facebook personal profile posting | `publish_actions` gone since 2018 | All of the above, plus Facebook ToS §3.1: "Not share your password, give access to your Facebook account to others, or transfer your account to anyone else (without our permission)". Letting a fleet operate a client's *personal* profile without Meta's permission is itself a ToS breach. | `official-docs` facebook.com/legal/terms (Wayback `20261010002416`, verbatim) |
| Instagram personal (non-professional) account | Instagram APIs serve professional accounts only | Instagram ToS: no "accessing or collecting information in an automated way without our express permission, regardless of whether ... logged-in". **Mitigation: switch the client to a professional account, then use the API.** | `official-docs` Instagram ToS (pga-versions `2858b63`, 2026-08-29) |
| Instagram/TikTok UI-only creative features (story stickers, licensed music, some edit tools) | Not documented in the publishing APIs (Instagram lists shopping tags and filters as unsupported) | Same ToS exposure; low volume, human-approved | `official-docs` (IG limitations) + `unverified` (stickers/music) |
| LinkedIn connection requests, DMs, InMail, groups | No API, or API restricted to partners with a per-message human action | User Agreement §8.2 bans "bots or other unauthorized automated methods to access the Services, add or download contacts, send or redirect messages, create, comment on, like, share, or re-share posts". The help center says third-party automation tools risk accounts being "restricted or shut down". | `official-docs` LinkedIn User Agreement (pga-versions `1f64470`, 2025-11-04); linkedin.com/help/linkedin/answer/a1341387 (Wayback `20261002024940`, verbatim) |
| Anything on X | X offers an API for everything the fleet should do | **"Non-API automation (scraping, browser automation) results in permanent suspension."** | `official-docs` docs.x.com/developer-guidelines.md; help.x.com/en/rules-and-policies/x-automation ("Updated April 2026", dateModified 2026-09-28) |
| OAuth consent, login, 2FA, checkpoints | By design | None if a human does it. This is the legitimate core use of the per-profile live viewer. | design |

### Q3. Platform automation rules (quoted), checkpoint triggers, account health

**Rules (verbatim):**
- **Meta / Facebook ToS §3.2** (facebook.com/legal/terms, "Effective January 1, 2025"; verbatim from
  Wayback `20261010002416`, `$S/wbk/fb_terms.txt`):
  - "You may not access or collect data from our Products using automated means (without our prior
    permission) or attempt to access data you do not have permission to access, regardless of whether such
    automated access or collection is undertaken while logged-in to a Facebook account."
  - "You may not do, or attempt to do, anything to circumvent, bypass, or override any technological
    measures that Meta uses to control or limit access to our Products or data."
  - §3.1: "Create only one account (your own) and use it for personal purposes. Not share your password,
    give access to your Facebook account to others, or transfer your account to anyone else (without our
    permission)."
  - The Open Terms Archive EU copy (pga-versions `7bbe3fc`) drops these list items. `official-docs`
- **Instagram ToS** (pga-versions `2858b63`, 2026-08-29): "You can't attempt to create accounts or access or
  collect information in unauthorized ways. This includes creating accounts or accessing or collecting
  information in an automated way without our express permission, regardless of whether such automated
  access or collection is undertaken while logged-in to an Instagram account." Also: "you can't create an
  account for someone else unless you have their express permission." `official-docs`
- **Meta Community Standards, account integrity** (pga-versions `7f52733`, 2026-09-24; the Facebook and
  Instagram "Community Guidelines" snapshots are byte-identical, so they are one source): "we may request
  additional information about an account to ascertain ownership and/or permissible activity" in these
  cases: "Compromised accounts; Creating or using an account or other entity through automated means, such
  as scripting (unless the scripting activity occurs through authorized routes ...); Empty accounts with
  prolonged dormancy". This is the documented basis of Facebook checkpoints. `official-docs`
- **Meta Developer Policies** (developers.facebook.com/devpolicy, rendered 2026-10-10):
  - "Don't contact people in Messenger or Instagram Messaging unless you ... have obtained legally
    sufficient consent, permission, and/or opt-in".
  - Spam includes "creating bots ... at very high frequencies". `official-docs`
- **X:**
  - Automation rules (help.x.com, Updated April 2026): "Don't! ... Use non-API-based forms of automation,
    such as scripting the X website. The use of these techniques may result in the permanent suspension of
    your account."
  - Also: "You may not like posts or hide replies in an automated manner".
  - Also: "You may not post duplicative or substantially similar posts on one account or over multiple
    accounts you operate".
  - "sending automated replies to posts based on keyword searches alone is not permitted".
  - AI reply bots "require prior written and explicit approval from X".
  - Automated DMs are allowed only after the recipient "requested or ... clearly indicated an intent", with
    an easy opt-out.
  - "A user authorizing your app ... through OAuth does not by itself constitute sufficient consent to take
    automated actions through that user's account". You must "clearly describe ... the types of automated
    actions", "receive express consent", and honour opt-out.
  - Developer guidelines: "Non-API automation (scraping, browser automation) results in permanent
    suspension."
  - X ToS (pga-versions `990ea3e`, 2026-10-10): "crawling or scraping the Services in any form, for any
    purpose without our prior written consent is expressly prohibited". `official-docs`
- **TikTok ToS** (pga-versions `350770f`, 2026-09-17): you must not "extract any data or content from the
  Platform using any automated system or software that is not provided by TikTok or approved in writing by
  TikTok" or "use or attempt to use another user's account without their permission".
  - Community Guidelines (pga-versions `2aa5ad0`, 2026-09-24): "We strictly prohibit automation tools,
    scripts, or other tricks designed to bypass our systems ... If your account is restricted or banned, you
    may not create or use another account to get around it." `official-docs`
- **LinkedIn User Agreement §8.2** (pga-versions `1f64470`, 2025-11-04):
  - "Develop, support or use software, devices, scripts, robots or any other means or processes (such as
    crawlers, browser plugins and add-ons ...) to scrape or copy the Services, including profiles".
  - "Use bots or other unauthorized automated methods to access the Services, add or download contacts,
    send or redirect messages, create, comment on, like, share, or re-share posts, or otherwise drive
    inauthentic engagement". `official-docs`

**What triggers checkpoints (sourced vs folklore):**

| Platform | Documented trigger → challenge | Source |
|---|---|---|
| X | "automated behavior that violates the X Rules" → lock + **recaptcha**. "aggressive following or aggressive engagements (such as, like, repost, and quote)" → features limited "for a specified time". "Suspicious behavior ... compromised" → forced password change. Phone/email verification. | `official-docs` help.x.com/en/managing-your-account/locked-and-limited-accounts (Wayback 2026-09-21). The help page says "recaptcha". Arkose/FunCaptcha on X is reported only by third parties; not verified here. |
| Meta | Automated or scripted use, compromise, prolonged dormancy → "request additional information" (checkpoint). High-frequency posting or engagement, or repetitive content → restrictions. | `official-docs` Community Standards (above) |
| TikTok | Automation tools/scripts → removal, bans, restriction of posting/search/FYF. New device/IP/VPN → verification code. | `official-docs` Community Guidelines; `third-party` (low-quality SEO pages) for device/IP |
| LinkedIn | "we don't permit the use of any third party software, including 'crawlers', bots, browser plug-ins, or browser extensions that scrape, modify the appearance of, or automate activity on LinkedIn's website ... they risk having their accounts restricted or shut down." "~100 invitations/week" | `official-docs` help a1341387 (verbatim, Wayback `20261002024940`, `$S/wbk/li_a1341387.txt`); the number is `third-party` folklore (vendor blogs; LinkedIn publishes no figure) |
| Instagram | "We restrict certain activity to protect our community" action blocks after bursts of follows, likes, comments or DMs. VPN IPs flagged. | `third-party` (Vista Social, Publer, Guiding Tech). No official Instagram help page was found. |
| Prior internal test | Meta Ad Library, logged out: blocked (login wall/CAPTCHA) after 2-3 searches. Instagram, logged out: rate-limited after ~24 scrolls. | `unverified` (an older local tool's test of 2026-06-05; private, details withheld; not re-run, and social sites are off-limits to this research) |

**Account-health practices for long-lived logged-in sessions.** No platform publishes cadence or volume norms
for browser sessions, so everything below is policy, not a sourced figure.

1. **One account, one identity, one place.** Same fingerprint, same sticky residential or ISP IP in the
   client's region, never shared across identities. Never log the account in from two fleet locations
   (hermes-packaging dossier). Rationale: X's "locked for security purposes" path and Meta's "compromised
   accounts" checkpoint both key on unusual-access signals. `official-docs` for the existence of the
   triggers; `unverified` for which signals.
2. **Do not log in repeatedly.** Keep cookies and storage; resume sessions; never script the login (agents
   never type credentials anyway).
3. **Dormancy is a documented Meta checkpoint trigger.** Genuine account activity matters. API-driven posting
   provides it without a browser. Whether API activity counts against "dormancy" is `unverified`.
4. **Keep-warm (the input scale-infra.md asked for):**
   - **API-connected accounts need no browser keep-warm.** They need token refresh:
     - Instagram long-lived tokens are valid 60 days and refreshable (`official-docs`).
     - TikTok access tokens are valid 1 day; refresh tokens up to 365 days (`official-docs`).
     - X and LinkedIn token lifetimes were not fetched (`unverified`).
   - **Browser identities on Meta, TikTok and LinkedIn** (only where a browser-only feature is in use): wake
     on demand. Proposed ceiling: one read-only login-state probe per account per week, in the client's
     daytime, single page load, no scrolling loops. If logged out, page a human.
   - **X: no browser keep-warm at all**, because "scripting the X website" is the violation.
5. **Volume ceilings = published caps, run well under them.** Proposal: never exceed 50% of any per-account
   cap. Spread posts across the day. Never post the same or substantially similar content to more than one
   client account.

### Q4. Red lines and human-in-the-loop points

**Red lines** (the fleet refuses these in code, not by prompt):

| Red line | Rule it enforces | Provenance |
|---|---|---|
| Creating accounts, fake personas, or accounts for clients without their express permission | Facebook ToS §3.1 (one account, your own); Instagram ToS; X authenticity policy ("Fake personas ... AI-generated profile photos"); TikTok ToS (impersonation, spam accounts); hiQ (fake LinkedIn profiles) | `official-docs` |
| Ban evasion (new account after a ban or restriction) | Facebook ToS §3.1; TikTok Community Guidelines; X | `official-docs` |
| Unsolicited or bulk DMs, cold outreach DMs on any platform | X automation rules C; Meta opt-in policy; TikTok BM ("prohibited from initiating a conversation"); LinkedIn Messages (member action per message) | `official-docs` |
| Automated likes, follows/unfollows in bulk, list stuffing, engagement pods, buying/selling engagement | X rules D + developer guidelines; X platform-manipulation policy; Meta Spam policy; TikTok fake engagement | `official-docs` |
| Keyword-triggered auto-replies or AI auto-replies on X without written approval; more than one automated reply per interaction | X automation rules B.2-B.3 | `official-docs` |
| Same or substantially similar content across multiple client accounts (X), repetitive content (Meta) | X automation rules A; Meta Spam | `official-docs` |
| Auto-posting about trending topics on X | X automation rules A | `official-docs` |
| Scraping personal data from platforms (logged in or out), building people databases from social profiles | Meta and Instagram ToS; X ToS; TikTok ToS; LinkedIn §8.2; TikTok Accounts API prohibited uses | `official-docs` |
| Browser automation on X | X automation rules + developer guidelines | `official-docs` |
| Downloading TikTok content to repost on other platforms or accounts | TikTok Accounts API "Prohibited Uses" | `official-docs` |
| Anti-detect techniques aimed at defeating a platform's access controls on client accounts | Facebook ToS ("circumvent, bypass, or override any technological measures"); X ToS ("work around any technical limitations") | `official-docs` |

**Human-in-the-loop points** (the job pauses until a human acts):
1. Every login, 2FA, CAPTCHA, checkpoint, "verify your account", security lock or appeal. The agent alerts
   with a live-viewer link and stops.
2. OAuth connection of each client account to each platform app. Capture **express consent per action type**
   (the X requirement); store it in the consent ledger.
3. The first post on each account, the first post of each new content type (Reel, Story, carousel), and the
   first post to each new destination (Facebook Group, X Community).
4. Every outbound message to a person who has not messaged the account in the current window. On LinkedIn,
   every message, full stop: a human must click send.
5. Every browser-only write (Groups, personal profiles, UI-only features): approval per action.
6. Any AI-generated reply on X until X has granted written approval for an AI reply bot.
7. Deletes, profile and bio changes, privacy/visibility changes, ad or boost actions, anything with money.
   This reuses the publishing-safety taxonomy of an older local tool (private; details withheld).
8. Any uncertain outcome (timeout mid-publish). Reconcile by API read, never auto-retry a write
   (publishing-safety retry rule).

### Q5. Lead generation via the agent's own browser (no paid enrichment)

**What is practical and ToS-safe:**
- **Public company websites.** About, contact, team and footer pages; schema.org JSON-LD
  (`Organization`/`LocalBusiness`: name, email, telephone, address, `sameAs` social links); `mailto:` and
  `tel:` links. Honour robots.txt, identify the bot in the User-Agent, rate-limit per domain, cache per
  domain. `hands-on` (spike below).
- **First-party platform APIs are *not* lead sources.**
  - Instagram **Business Discovery** (Facebook Login only) returns "basic metadata and metrics about other
    Instagram professional accounts". But Meta Platform Terms §3.a.v prohibits "Processing Platform Data
    without valid User consent in order to build or augment user profiles for any purpose". Use it only for
    client-facing competitor benchmarking, never to populate lead records `official-docs`.
  - X lookups ($0.010/user, $0.005/post): X's developer guidelines prohibit "Profiling, tracking, or
    monitoring users without consent". Off-X matching without consent is limited to public X data and
    public directories, and "Never match if it would surprise the user". At most, confirm a company's
    official handle that its own website links to `official-docs`.
  - Public registries (company registers, SEC EDGAR) are a natural next source. Not researched here
    `unverified`.
- **The platforms themselves:**
  - Using a logged-in client identity to scrape profiles breaches the contract that client accepted (all five
    ToS, above).
  - *Meta v. Bright Data* (N.D. Cal., 2024-01-23) held that Bright Data's **logged-off** scraping of public
    data did not breach Meta's terms. That does not cover logged-in identities `third-party` (fbm.com,
    quinnemanuel.com law-firm alerts).
  - *hiQ v. LinkedIn* ended with a stipulated **$500,000 judgment** and a permanent injunction (December 2022).
    The Nov 2022 order held that anti-scraping and anti-fake-profile terms are enforceable in contract
    `third-party` (proskauer.com, natlawreview.com).
  - Instagram's ToS explicitly says "regardless of whether ... logged-in".
- **Personal data law.** Prefer role-based business contacts. Store the source URL and fetch time with every
  datum, and honour opt-outs. GDPR and CCPA apply to named individuals `unverified` (not researched in depth).

**The cascade (with the spike's evidence):**
1. **Tier 0, plain HTTP fetch** (`fleet/research/spikes/social-platforms/leadgen_tier0.py`, stdlib only):
   - Steps: robots.txt check, then one GET (15 s timeout, 2 MB cap), then extract JSON-LD, mailto, tel,
     social links and contact links.
   - Measured on public test pages: **70-344 ms, $0 per page**. The fixture extraction got every field
     (`hands-on`, RESULTS.md).
2. **Escalate only when the extraction goal is unmet.** Both page-shape heuristics misfired:
   - v1 missed the JS-only `quotes.toscrape.com/js/` (65 chars of text, 2 scripts),
   - v2 flagged `example.com`.
   - The goal-based check (expected pattern absent from static HTML) was correct on both quote pages
     `hands-on`.
3. **Tier 1, Stagehand `extract`** with a Zod schema on the *known* page (contact or team page found by
   tier 0). Cost per call is in the stagehand and reasoning-models spikes (~$0.001 per call on GLM 5.3 Flash
   per scale-infra.md) `hands-on by those agents`.
4. **Tier 2, Browser-Use exploration** only when the site structure is unknown: find the team page, paginate
   a directory, open accordions. Cap steps and budget per domain.
5. Write results to the Obsidian vault as one note per company, with source URL, timestamp and tier used
   (memory = Obsidian, per BRIEF).

### Q6. Recommendation: API-first vs browser-first decision table

Legend: **API** = use the official API (safer and cheaper). **HITL-browser** = browser in the live viewer
with a human approving each action, or a human doing it. **Never** = red line. Costs: Meta, TikTok and
LinkedIn APIs $0; X per the price list.

| Task | Facebook (Page) | Instagram (professional) | TikTok | X | LinkedIn |
|---|---|---|---|---|---|
| Text/image post | API | API (image; JPEG) | API (photo post) | API ($0.015; $0.20 with URL) | API (Page: CM API; member: `w_member_social`) |
| Video / Reel / short | API (Reels 30/24 h) | API (100 posts/24 h total) | API (15/day) | API | API |
| Carousel | API (multi-photo) | API (≤ 10) | API (photo post) | API (media) | API |
| Story | API (photo/video stories) | API (`STORIES`; stickers `unverified`) | HITL-browser (no API found) | n/a | n/a |
| Comment replies / hide / delete | API | API | API | API (only replies to users who engaged; AI replies need X approval) | API (Page) |
| Reply to inbound DMs | API (24 h; HUMAN_AGENT 7 d) | API (24 h; human_agent 7 d; private reply 7 d) | API (BM API; beta; not EEA/UK/CH; reviews) | API (only after the user DMs; 1,440/day per app) | Never automated; human sends |
| Outbound / cold DMs | Never | Never | Never | Never | Never |
| Likes, follows, engagement | Never automated | Never automated | Never automated | Never automated | Never automated |
| Analytics | API | API | API | API (paid reads) | API (org); member analytics closed |
| Groups / communities | HITL-browser (Groups API removed) | n/a | n/a | API (`community_id`) | HITL-browser (`unverified`) |
| Personal (non-business) account | HITL-browser, and ToS forbids giving others access | Convert to professional, then API; else HITL-browser | API (Accounts API covers personal) | API | API (member posts only) |
| Login, 2FA, checkpoints | HITL-browser (human) | HITL-browser | HITL-browser | HITL-browser (human only) | HITL-browser |
| Proof a post is live | API read | API read | API read / webhook | API read (paid) | API read |
| Lead research | Open web only (tiers 0-2) | Open web only. Business Discovery is for benchmarking, not leads (Platform Terms §3.a.v). | Open web only | Open web only. API lookups only to confirm a company's own handle; profiling is prohibited. | Open web only |

**Where the browser fleet stays essential:**
- the human-login viewer (onboarding, re-auth, checkpoints);
- open-web lead generation (tiers 1-2);
- the narrow no-API set (Facebook Groups, TikTok stories, UI-only features) under HITL;
- sites with no API at all (directories, forums, vendor portals);
- visual QA of clients' own public pages, sparingly.

**Infrastructure consequence:** most of the 100-1,000 profiles need **no always-on browser for social
work**. Their social activity is API calls plus tokens. This cuts the RAM and proxy budget scale-infra.md
sized around ~900 MB per Chromium.

---

## 3. What the open-source projects give us vs what the fleet must build

| Need | Stagehand / Browser-Use / Steel give us | The fleet must build |
|---|---|---|
| Publishing, moderation and DMs on five platforms | Generic browser control only. Nothing platform-specific and nothing ToS-compliant for writes. | **Platform connector layer**: Meta Graph (Pages, IG, Messenger), TikTok API for Business (Accounts + Business Messaging), X v2 (+ X Chat), LinkedIn (CM API + Share). Media hosting on verified public URLs (Meta cURLs media; TikTok requires verified domains). |
| App approvals | — | **Milestone dependencies:** Meta app + Business Verification + App Review (Advanced Access for pages_*, instagram_business_*); TikTok Accounts API access form + app approval; TikTok BM DSPR (+ USDS for US); X developer account + credits + spending limit; LinkedIn CM API Development → Standard (screencast). Optional: X written approval for an AI reply bot. |
| Tokens | Steel persists browser cookies, not OAuth tokens | **Token vault** per identity per platform (encrypted), refresh scheduler (IG 60 d, TikTok 1 d / 365 d), revocation handling, re-consent flow via the live viewer. |
| Webhooks | — | Receiver for Meta webhooks (comments, messages), TikTok webhooks (messages, post status), X Activity API (billed per event). Messaging-window tracker per conversation (24 h / 7 d / 48 h rules). |
| Rate and cost governance | — | **Central governor**: per-account caps (IG 100/24 h, FB Reels 30/24 h, TikTok 15/day and 6/min, X 100/15 min, LinkedIn 150/day) and per-app caps (X 10,000 posts/24 h, X 1,440 DMs/24 h, LinkedIn dev 500/day). X cost meter with a budget per client. Run at ≤ 50% of caps. |
| Policy engine (red lines) | Nothing | Refuse-list in code (Q4). Duplicate-content detector across all client accounts. Opt-in/opt-out ledger. Consent ledger per X rules. Trending-topic guard. |
| Human approval | Publishing-safety taxonomy exists in an older local tool (adapt) | Approval queue with campaign manifests (pre-approved calendars), first-post gates, a per-message human send for LinkedIn. |
| Receipts | Stagehand `extract` could read a page | **Receipts via API reads** (post ID → permalink and status). The browser is not needed and is ToS-exposed. |
| Checkpoint handling | Steel live viewer; Browser-Use has no checkpoint semantics | Detector (login wall, captcha, "verify your account", feature-limited banners), pause identity, page a human with a viewer link, post-incident cool-down. |
| Lead gen | Stagehand `extract` / Browser-Use exploration | Tier-0 fetcher (spike), robots.txt, per-domain politeness, goal-based escalation, provenance store in Obsidian. |
| Browser-only playbooks | Stagehand cached actions | Small set (Facebook Groups post, TikTok story), each with HITL and hard caps. |

---

## 4. Operating notes for a Hermes agent (feeds `fleet-social-ops` and `references/<platform>.md`)

**General**
- **Default path is the API connector, never the browser, for any write on a social platform.** Use the
  browser only for: the login/checkpoint viewer (a human acts), open-web lead research, and the listed
  browser-only features with an approval ID.
- Proposed call shape (fleet-side, not existing code):
  `social.publish{identity, platform, kind: post|reel|story|carousel, media_urls[], caption, schedule_at?, approval_id}`
  → `{job_id}`; then `social.job{job_id}` → `{state, platform_post_id, permalink, receipt}`.
  The pattern is submit-then-poll, because the Hermes MCP timeout is 90 s (hermes-packaging).
- Before every publish, check the cap first (IG `content_publishing_limit`; TikTok `creator_info` or
  `/business/video/settings/`) and the content-uniqueness check across the client set.
- Never retry a write that may have started. Reconcile by listing recent posts through the API.

**Facebook**
- Use a Page access token or a Business Manager system user. Do not use a person's token for server automation.
- Scheduled posts: `published=false` + `scheduled_publish_time`.
- Reels: 3-90 s, 30 per 24 h per Page.
- Stories: video ≤ 60 s.
- Messenger replies only inside 24 h (7 d after a CTM ad). Use HUMAN_AGENT (7 d) only for genuine human replies.
- Disclose bots where the law requires it.
- Groups have no API. Groups work is HITL only, low volume, never the same text into many groups.

**Instagram**
- Two hosts: `graph.instagram.com` (Instagram Login) vs `graph.facebook.com` (Facebook Login). Do not mix
  tokens and hosts.
- Publish flow: container → poll `status_code` until `FINISHED` (video) → `media_publish`.
- JPEG only. Carousel ≤ 10. Media on a public URL.
- Reels report `media_type=VIDEO`; check `media_product_type`.
- DMs only after the user writes first. Private replies to comments within 7 days. 750 private replies/h.
- No browser for anything an API covers. Instagram's ToS bans automated access even logged in.

**TikTok**
- Use the **Accounts API** (business-api.tiktok.com), not the Content Posting API. The latter's audit rejects
  agency tools, and unaudited posts are private-only.
- `video_url` must be on a verified URL property. mp4/mov/webm, ≤ 1 GB, 3-600 s.
- 6 posts/min, 15/day per account. Refresh the access token daily.
- Never download TikTok media to reuse elsewhere (prohibited use).
- DMs: webhook-driven, reply only. Respect the 10 / unlimited-48 h / 3 rules. Not available for EEA, UK or
  CH accounts.

**X**
- API only. **Never open x.com in an agent-driven browser.** Only a human in the viewer, and only if needed.
- Every write costs money. A link post is $0.20. Track budget per client.
- 100 posts/15 min per user, 10,000/24 h for the whole app.
- Replies only to users who engaged first, one per interaction. AI-generated replies need X's written
  approval; until then a human approves each.
- Never like. Never bulk-follow. Never post the same text to two accounts. Never auto-post on trends.
- DMs only after the user DMs first, with an opt-out. 1,440 DMs/24 h is shared across the whole app.
- Record each client's express consent per automated action type at onboarding.

**LinkedIn**
- Company Pages through the Community Management API; send the current `LinkedIn-Version` header
  (202510 sunsets 2026-10-15).
- Member posts through `w_member_social` (150/day).
- Messages and connection requests: **draft only**. The human clicks send in their own session.

**Checkpoints (all platforms)**
- When you see any of the following: stop, mark the identity `challenge`, emit a `login_link`, wait for the
  human, then cool down before the next action.
  - a login wall,
  - "verify your account" or "confirm it's you",
  - a captcha,
  - "temporarily blocked", "try again later" or "we restrict certain activity",
  - "features limited".
- Never attempt the challenge yourself.

---

## 5. Risks and unknowns

1. **Client expectation mismatch.** The brief imagines browser agents "replying to and messaging people" for
   clients. Cold DMs and engagement automation are prohibited everywhere. The product must be scoped to
   inbound-reply plus publishing, and the client contract should say so.
2. **Approval risk and lead time.** Meta App Review, TikTok's Accounts API form and data-security reviews,
   and LinkedIn's vetting are discretionary. Any one can refuse or stall. Unknown approval odds for an
   agency use case. No timeline estimate is given (per rules).
3. **"Accounts you manage" under Meta Standard Access** might cover agency-managed client accounts without
   App Review. Meta says Standard Access suffices for "an account you manage", but "Some features may not
   work properly until your app has been granted Advanced Access". At 100-1,000 clients, plan for
   Advanced Access. `official-docs` + interpretation.
4. **X economics and per-app ceilings.** 10,000 posts/24 h and 1,440 DMs/24 h per app cap the whole fleet on
   one app. Splitting into many apps to dodge limits risks "circumvent rate limits" enforcement.
   Enterprise pricing is not public.
5. **X "automated account" labelling.** It is unclear whether brand accounts posting human-approved, API-scheduled
   content count as "automated accounts" that must carry the Automated label. `unverified`
6. **X Chat (encrypted DMs).** It is unknown whether legacy `dm_events` sees conversations users start in X
   Chat. If not, the fleet needs Chat XDK key management. `unverified`
7. **Browser-only features remain ToS-exposed even with HITL.** A human approving does not make automated
   UI driving permitted. Only a human *doing* it is clean. The fleet should offer "human does it in the
   viewer" as the default for those features.
8. **No official checkpoint thresholds.** Every cadence number in the market is folklore. The fleet's
   numbers must come from its own telemetry: checkpoint rate per identity per platform, logged from day one.
9. **Composio connectors** (endorsed in Justin's directives) may already wrap these official APIs. Not
   researched here. Unknown: whose app review they ride on and how they handle per-app caps. `unverified`
10. **Legal.** GDPR and CCPA treatment of lead data, the client contract language on account risk, and agency
    liability are not researched. `unverified`
11. **Doc inconsistencies:**
    - IG publishing limit appears as both 100 and 50 on the same page.
    - X limits shows "50 posts + 200 replies (unverified accounts)" and a legacy "2,400 updates per day" on
      the same page.
    - Meta's Open Terms Archive EU snapshot lacks the §3.2 bullets present on the live page.

    The dossier uses the most recent and most specific figure and notes each conflict.

---

## 6. Sources

Fetched 2026-10-09/10 unless noted. Scratch copies are under `$S` (not committed).

**Meta.** Rendered to `$S/meta/` on 2026-10-10:
- https://developers.facebook.com/docs/instagram-platform/content-publishing
- https://developers.facebook.com/docs/instagram-platform/overview
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api
- https://developers.facebook.com/docs/instagram-platform/private-replies
- https://developers.facebook.com/docs/messenger-platform/policy/policy-overview
- https://developers.facebook.com/docs/pages-api/posts
- https://developers.facebook.com/docs/pages-api/comments-mentions
- https://developers.facebook.com/docs/video-api/guides/reels-publishing
- https://developers.facebook.com/docs/page-stories-api
- https://developers.facebook.com/docs/graph-api/overview/rate-limiting
- https://developers.facebook.com/docs/graph-api/changelog/version19.0 (Groups API removal 2024-04-22)
- https://developers.facebook.com/docs/groups-api (redirects to docs root)
- https://developers.facebook.com/docs/instagram-basic-display-api (redirects to IG platform overview)
- https://developers.facebook.com/docs/development/release/business-verification (updated 2023-07-07)
- https://developers.facebook.com/docs/business-management-apis/system-users
- https://developers.facebook.com/devpolicy
- https://developers.facebook.com/terms/dfc_platform_terms

Also:
- https://www.facebook.com/legal/terms ("Effective January 1, 2025"; verbatim via Wayback
  `https://web.archive.org/web/20261010002416id_/https://www.facebook.com/legal/terms/`, `$S/wbk/fb_terms.txt`)
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery (rendered 2026-10-10)
- https://developers.facebook.com/ads/blog/post/2018/04/24/platform-product-changes/ (publish_actions, via search)

**TikTok.**
- business-api.tiktok.com/portal/docs, doc ids 1737944384433218, 1738083939371009, 1738084387220481,
  1738084416214017, 1762228496095234, 1776065099288577, 1776983576127490, 1803630424390658,
  1832183871604753, 1832184079395841, 1832184145137922, 1832184206708737, 1832184236919810,
  1839594049581249, 1854823717597185. Pulled via the docs JSON endpoint into `$S/render/ttnode_*.txt`,
  2026-10-09/10.
- https://developers.tiktok.com/doc/content-posting-api-get-started
- https://developers.tiktok.com/doc/content-sharing-guidelines
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post

These three are in `$S/tt/`, rendered 2026-10-10.

**X.**
- https://docs.x.com/x-api/getting-started/pricing.md
- https://docs.x.com/x-api/fundamentals/post-cap.md
- https://docs.x.com/x-api/fundamentals/rate-limits.md
- https://docs.x.com/x-api/direct-messages/manage/introduction.md
- https://docs.x.com/xchat/introduction.md
- https://docs.x.com/developer-guidelines.md
- https://docs.x.com/openapi.json

These are in `$S/x/`. Help pages:
- https://help.x.com/en/rules-and-policies/x-automation (live fetch 2026-10-09, "Updated April 2026", dateModified 2026-09-28; `$S/docs/x_automation_wb.*`)
- x-limits (Wayback `20260926193021`)
- locked-and-limited-accounts (Wayback `20260921142432`)
- authenticity / platform-manipulation (Wayback `20261007195718`)

The live help.x.com now serves a Cloudflare challenge to scripted fetches.

**LinkedIn.** Fetched to `$S/li/`:
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview (updated 2026-05-15)
- https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access
- https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin (updated 2025-02-05)
- https://learn.microsoft.com/en-us/linkedin/shared/integrations/communications/messages (updated 2023-05-08)
- https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits
- https://www.linkedin.com/help/linkedin/answer/a1341387 (verbatim via Wayback `20261002024940`, `$S/wbk/li_a1341387.txt`)

**Terms snapshots.** Open Terms Archive, `github.com/OpenTermsArchive/pga-versions`; files in `$S/docs/ota_*.md`:

| Document | Commit | Date |
|---|---|---|
| Facebook ToS | `7bbe3fc9` | 2026-06-16 |
| Facebook/Instagram Community Guidelines (identical) | `7f527330` / `c5686e7b` | 2026-09-24 |
| Facebook Developer Terms | `9f5f356e` | 2026-02-04 |
| Instagram ToS | `2858b63c` | 2026-08-29 |
| TikTok ToS | `350770fe` | 2026-09-17 |
| TikTok Community Guidelines | `2aa5ad00` | 2026-09-24 |
| X ToS | `990ea3e0` | 2026-10-10 |
| X Community Guidelines | `129c25c4` | 2026-06-29 |
| X Developer Terms | `6b59c5d5` | 2026-09-18 |
| LinkedIn ToS | `1f644705` | 2025-11-04 |
| LinkedIn Community Guidelines | `e32ec743` | 2026-09-29 |
| LinkedIn Developer Terms | `2540920d` | 2025-10-23 |

**Third-party.**
- X pricing history: postproxy.dev/blog/x-api-pricing-2026, wearefounders.uk (2026).
- Meta v. Bright Data: fbm.com, quinnemanuel.com, lowenstein.com (2024).
- hiQ v. LinkedIn: proskauer.com, natlawreview.com, morganlewis.com (Dec 2022).
- Instagram action blocks: support.vistasocial.com, publer.com, guidingtech.com.
- LinkedIn invite folklore: contentin.io, snov.io.
- Basic Display end date: help.zapier.com, Meta community thread (via search).

**Internal.**
- An older local tool's anti-detection results and publishing-safety skill (private; paths and commits withheld)
- Dossiers `existing-assets.md`, `hermes-packaging.md`, `scale-infra.md` in this worktree

**Spike.** `fleet/research/spikes/social-platforms/` (`leadgen_tier0.py`, `fixture_company.html`, `run1-3.jsonl`,
`fixture_out.json`, `RESULTS.md`). Run 2026-10-10 07:35-07:36 UTC, $0.
