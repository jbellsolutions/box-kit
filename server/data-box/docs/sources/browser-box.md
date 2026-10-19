# browser-box

**Status (2026-09-23).** browser-box is live at `https://your-box.example.com` ([repo](https://github.com/jbellsolutions/browser-box)). data-box is not pointed at it yet; it becomes scrape rung 6, the last one, in D3.

## What it gives data-box

A real Chromium (Steel), for pages that nothing cheaper can read: heavy JavaScript apps, pages that fingerprint the client, and pages that need a logged-in session. It is `scrape`'s last rung, rung 4.

browser-box has one browser lane, so a busy lane counts as a failed rung. data-box does not queue behind it.

## How data-box calls it

- **Request:** `POST $DATABOX_BROWSERBOX_URL/api/v1/read` with `{"url": ...}`, and `Authorization: Bearer $DATABOX_BROWSERBOX_TOKEN`.
- **URL checks:** browser-box runs its own URL guard, using the same scope vectors as data-box. It also holds a host egress rule and a Chrome DevTools Protocol guard, because a browser navigates on its own.
- **Cost:** browser-box runs on its own droplet, so a read costs no provider fees, only time. data-box records it in the ledger at $0.

## Primary docs

- browser-box's README and `docs/tools.md`
