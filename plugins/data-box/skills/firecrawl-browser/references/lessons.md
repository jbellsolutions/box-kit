# Firecrawl browser: lessons

## 2026-09-30: the endpoint that "did not exist"

- **What happened:** earlier in the week, research on Firecrawl's SDKs concluded that the docs' `POST /v2/interact` did not exist and that `/v2/browser` was the real path. The docs pages were then mirrored into this skill, and they document `/v2/interact`. A keyless call showed both paths answer 401 while an unknown path answers 404.
- **Rule:** before recording that a vendor endpoint does or does not exist, check it against the vendor's current API reference and a free, keyless call. An SDK's path can be an older alias.

## 2026-09-28: minutes are money like pages are

- **What happened:** the Hermes firecrawl profile's credit burn that day came from paging, not browsers; the same pattern would be worse with minutes, which bill while nothing useful happens.
- **Rule:** every session has a TTL, a `finally` delete and a plan-level cap in minutes.
