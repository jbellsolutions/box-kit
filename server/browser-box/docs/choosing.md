# Choosing a tool

Use the cheapest tool that can do the job, and move down this list only when the one above it
cannot. Every step down is slower, holds a browser for longer, or costs more money.

| # | Use | When | Cost and speed | Holds a browser? |
|---|---|---|---|---|
| 1 | `fetch` | The page is server-rendered: news, docs, APIs, RSS, most marketing pages | free, under a second | no |
| 2 | `read` | `fetch` came back empty or wrong because the page needs JavaScript | ~$0.0003 a read on Browser Use Cloud (a minute at $0.02/h), ~3 s | no: each read gets its own hosted browser |
| 3 | `act` (a `session` for a browser of your own) | You need to click or type, and you can say the steps | free plus Jev's decisions; ~0.3 s a decision, page loads dominate | yes, a session's own browser while it is open (or the shared scratch browser) |
| 4 | `task` (browser) | An open-ended goal you would rather not plan step by step | model tokens (cents), 10 s to several minutes | yes, a hosted browser of its own for the whole run |
| 5 | `computer` / `task` (computer) | A whole desktop: native apps, a shell, a download you open | an Orgo computer, billed by the hour until stopped | no, it runs off the box |
| 6 | **Browserbase** | The emergency lane, through `read`, `act` and `task`: see below | Browserbase hours ($20 plan: 100 h a month) | no, it runs on Browserbase |

## The questions, in order

1. **Can a plain HTTP GET answer it?** Try `fetch`. Check `text_chars`: a near-empty result on a
   page you know has content means the page renders with JavaScript.
2. **Do you only need to read a rendered page?** `read`. Ask for `screenshot` only when the
   picture is the evidence: it is a second page load.
3. **Can you write the steps?** `act`, one step or up to four joined by "then". It was faster
   and as accurate or more than `task` on every measured job but one ([benchmark.md](benchmark.md)).
   Answer `needs_clarification` with `pick`, and `needs_confirmation` with `confirm`.
4. **Want a browser of your own?** `session(action="create")` returns a fresh, logged-out browser that
   stays open between calls; give its `session_id` to `act` or `read`, and `release` it when done. Without
   a `session_id`, `act` shares one scratch browser. A site that needs a login is not for this box: it
   keeps none, so use a tool built for logged-in work.
5. **Can't or won't plan it?** `task(surface="browser")` with a goal that says what to report back,
   and a `max_steps` that fits the job. Stop it with `task(cancel=true)` if you give up.
6. **Not a web page at all?** `computer`. Stop it when finished: it bills until stopped.
7. **Did Browser Use fail where Browserbase would succeed?** `read` falls back on its own; ask for
   `engine="browserbase"` only when you already know Browser Use can't serve the page.

## Browser Use Cloud: the default engine for `read`

When `BROWSER_USE_API_KEY` is set (status shows "browser-use cloud"), every `read` opens its own hosted
Chromium on Browser Use Cloud, reads the page, photographs that same load if asked, and stops the
browser. Reads run side by side up to the plan's `concurrentSessionLimit` (10 at $0 of payments, 50
after $100); there is no queue on the box. Measured 2026-10-12: Hacker News with a screenshot in
3.6 s; three different pages at once in 3.2 s.

- **Cost:** $0.02 per browser-hour, billed by the minute with a one-minute minimum, so about $0.0003 a
  read. `BB_BROWSERUSE_MONTHLY_USD` (default 10) caps this month's spend, counted from Browser Use's own
  per-browser costs; the read is refused at the cap, or when the wallet is empty.
- **No proxy; CAPTCHA solving on.** Browser Use's default residential proxy is billed per GB, so it is
  turned off. Browser Use's CAPTCHA solving is on (`BB_SOLVE_CAPTCHAS=1`, the default); set it to 0 to
  turn it off.
- **Public, logged-out pages only**, like every read. URLs are checked before the browser opens, and a
  page that lands off the public web is dropped.
- **Falls back to Browserbase** (below) when its browser fails or the site blocks it, if Browserbase is
  configured. `engine="browseruse"` never falls back.

## Sessions and `act` on Browser Use Cloud

`session` runs on Browser Use Cloud with `BROWSER_USE_API_KEY`; `act` needs `TYPESAFE_API_KEY` as well.
The box keeps no logins and never touches a Browser Use profile: the account also holds other tools'
logged-in profiles (for example a lead-gen tool), and a browser here is always fresh and clean.

- **A session is a fresh, logged-out browser that stays open between calls.** `session(action="create")`
  opens it and returns a `live_url` (a view of it); `act` and `read` take its `session_id`. The actions
  are `create`, `list` and `release` only: there is no `login` and no `delete`. A released session, or
  one closed when idle, is gone, and a call with its id is refused; create a new one.
- **One browser per session, no lock across sessions.** Calls on one `session_id` wait for each other
  (up to `BB_SESSION_WAIT_SECONDS`, default 30, then "busy"); different sessions run side by side.
  `task` takes no `session_id`: it always opens a browser of its own.
- **Idle browsers close themselves** after `BB_SESSION_IDLE_SECONDS` (default 300), so a session
  costs nothing while unused. `act` without `session_id` uses one shared scratch browser, forgotten when it closes.
- **`act` asks before anything risky**, and judges risk twice: once from your words and once from the
  element Jev picked. Measured 2026-10-12: "click the button" on a form whose one button is "Submit
  order" read as harmless from the words alone (it submitted). The element check now stops it.
- Crash cleanup stops only browsers this box created, by the ids it recorded (`BB_OWNED_BROWSERS`); it
  never searches the account.

## Browserbase: the emergency lane

Browser Use Cloud is the only main lane. Browserbase exists so that an outage there leaves the box
with *something* rather than nothing. It is never a default and never chosen because it is "better".

### What happens in each emergency

| Emergency | `read` | `act` (scratch or any session) | `task` |
|---|---|---|---|
| Browser Use out of credit, or the wallet is under $0.02 | Browserbase (`engine_down`) | Browserbase | Browserbase |
| This box's monthly Browser Use cap (`BB_BROWSERUSE_MONTHLY_USD`) is reached | Browserbase | Browserbase | Browserbase |
| Every Browser Use browser slot is taken (the plan's limit, 10 today) | Browserbase | Browserbase | Browserbase |
| Browser Use API down, erroring or timing out | Browserbase | Browserbase | Browserbase |
| Browser Use key revoked or wrong (401) | Browserbase; `status` shows Browser Use down | Browserbase | Browserbase |
| The site blocks Browser Use's browser (a bot wall) | Browserbase (`blocked`) | not automatic: the step reports what it saw | not automatic |
| A Browser Use browser dies mid-call | the call fails | the call fails; the next `act` on that session opens a fresh browser (Browserbase if Browser Use still cannot) | the task fails with what it did |
| Browserbase fails too | the error names both | the error names Browser Use's failure | the error names Browser Use's failure |
| Browser Use not configured at all | Browserbase (`no_browser_use`) | `act` is not listed | `task` is not listed, and `session` is not listed |

Every browser here is fresh and logged out, so nothing is lost by running on the emergency lane. A
session whose browser could not open on Browser Use is opened on Browserbase instead; `engine` on
its result says which.

Every fallback says so in its result: `engine: "browserbase"`, plus `fallback_reason` (and, for
`read`, `engine_error` with Browser Use's own error). `status` shows both engines.

### What the emergency lane cannot do

- **No logins.** Each Browserbase browser is fresh and logged out, like every browser here. CAPTCHA
  solving is on by default (`BB_SOLVE_CAPTCHAS=1`); set it to 0 to turn it off.
- **No screenshot or status code on `read`**: text and links only.
- **Small.** It runs on whatever Browserbase plan the key is on. On the $0 Free plan (no subscription) that is 3 browsers
  at once and 60 browser-minutes a month, so set `BB_BROWSERBASE_MONTHLY_HOURS=1` to match; the box
  refuses new Browserbase browsers at that cap. The default (100) is the $20 Developer plan's.
- **Proxies are a paid-plan feature** on Browserbase; the box sends none.

### Asking for it on purpose

`read(engine="browserbase")` goes straight there (`requested`), and `read(region=...)` reads from one
of Browserbase's regions (`us-west-2`, `us-east-1`, `eu-central-1`, `ap-southeast-1`).
`read(engine="browseruse")` never falls back.

Operator settings: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` (optional when the key has one
project), `BB_BROWSERBASE_MONTHLY_HOURS`, `BB_BROWSERBASE_MAX_CONCURRENT`, `BB_BROWSERBASE_TIMEOUT`.

## Things that look like shortcuts and are not

- **`task` for a single page.** One `read` is free and seconds; `task` is paid and holds the
  browser for the whole run.
- **`read` with a screenshot "just in case".** The picture comes from the same page load as the text,
  so it adds no second load; ask for it when the picture is the evidence. Browserbase reads return
  no screenshot at all.
- **A `session` for a one-off public read.** It keeps a browser open (and billing) until you release
  it or it goes idle. A plain `read` opens, reads and stops its own browser.
- **Running your own copy because a call was refused at a limit.** Retry, use `fetch`, or ask the
  operator to raise the cap. See [self-host.md](self-host.md).
