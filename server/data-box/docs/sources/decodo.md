# Decodo

Decodo sells two separate products, each with its own credentials.

## Residential proxy: `scrape` rung 2, first half (D3)

**Status (2026-09-23).** The proxy user and password are verified:
- the sticky endpoint (port 10001) returned a residential exit in Brazil;
- the rotating endpoint (port 7000) returned a different exit, in Lithuania.

Both are set on the droplet.

| Endpoint | Behaviour |
|---|---|
| `gate.decodo.com:7000` | Rotating: a new IP per request, unless the username asks for a session |
| `gate.decodo.com:10001`–`49999` | Sticky: each port holds one IP for the session length set in the dashboard (10 minutes on this account) |

- **Targeting, on port 7000.** Put the country and session in the username: `user-<USERNAME>-country-us-session-<id>-sessionduration-10`.
- **Usage in data-box.** data-box keeps one sticky session per job and domain.
- **Env vars.** `DECODO_PROXY_USER` and `DECODO_PROXY_PASSWORD`. The password contains characters that must be URL-encoded in a proxy URL.
- **Metering.** Bytes × the plan's $/GB. The worst case is reserved before the request and settled after.
- **Guard.** DNS resolves at the proxy, so data-box resolves the target itself first and refuses non-public addresses before sending CONNECT. Every redirect hop is re-checked.

## Web Scraping API: `scrape` rung 2, second half (D3)

**Status (2026-09-23).** The token has not been supplied. `status` will list rung 3 as unconfigured until `DECODO_SCRAPER_API_TOKEN` is set.

- **Endpoint.** `POST https://scraper-api.decodo.com/v2/scrape`.
- **Auth.** `Authorization: Basic <token>`. This token comes from the Web Scraping API section of the dashboard; it is not the proxy login.
- **JavaScript.** Rendering is on for rung 3, because the rungs before it failed on a plain fetch.
- **Templates.** Decodo's platform templates join the survey as tier 2 data lanes in D4. If Decodo publishes no template list through its API, data-box builds one from Decodo's docs using its own `scrape`.

## Primary docs

- https://help.decodo.com (residential endpoints and ports, advanced parameters, Web Scraping API quick start)
