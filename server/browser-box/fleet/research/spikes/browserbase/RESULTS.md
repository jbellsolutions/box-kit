# Browserbase spikes: RESULTS

Date: 2026-10-09. Agent: browserbase deep-dive. Spend: **$0** (no Browserbase account, no API key, no network calls to Browserbase).
Containers: none started, none left running.

Both spikes are **offline**. They swap the HTTP layer for `httpx.MockTransport`, use a dummy API key string (`dummy-not-a-key`) and point
`base_url` at `https://bb.example.invalid`. They show what the client libraries **send**. They say nothing about how the Browserbase
server responds. Tag: `hands-on` (client-side request shapes only).

Interpreter: `<scratch>/py/.venv/bin/python` (Python 3.12) with
`browserbase==1.20.0`, `stagehand==4.2.0`, `browser-use==0.13.11` (shared venv, nothing installed by this agent).

## Spike 1: `offline_request_shapes.py`

Command:

```bash
cd fleet/research/spikes/browserbase
<scratch>/py/.venv/bin/python -I offline_request_shapes.py
```

Raw output: `out_offline_request_shapes.txt`. Findings:

1. Browserbase Python SDK 1.20.0 `sessions.create()` parameters:
   `browser_settings, extension_id, keep_alive, project_id, proxies, proxy_settings, region, api_timeout, user_metadata, extra_headers, extra_query, extra_body, timeout`.
   - `api_timeout=3600` goes on the wire as `"timeout": 3600` (session lifetime, seconds).
   - **Trap:** the SDK's own `timeout=` kwarg is the *HTTP request* timeout, not the session lifetime. `bb.sessions.create(timeout=3600)` does not set a 6-hour-capped session lifetime.
2. snake_case is converted to camelCase (`keepAlive`, `userMetadata`, `solveCaptchas`, `recordSession`).
3. An unknown `browser_settings.fingerprint` key is **passed through unvalidated**: `"fingerprint":{"operatingSystems":["windows"]}` appears in the request body.
   Whether the server honours, ignores or rejects it is unknown (needs a key). It is not in the SDK source or the docs-site spec.
4. Wire body captured:
   ```json
   {"browserSettings":{"context":{"id":"ctx_dummy","persist":true},"solveCaptchas":true,"recordSession":true,
    "fingerprint":{"operatingSystems":["windows"]}},"keepAlive":true,"projectId":"proj_dummy",
    "proxies":[{"type":"external","server":"http://proxy.example.invalid:8000","username":"u","password":"p"}],
    "region":"us-east-1","timeout":3600,"userMetadata":{"profile_id":"p-0001","owner":"fleet"}}
   ```
5. Stagehand 4.2.0 `browserbase.launch` params: `api_key, base_url, client_options, browser_settings, extension_id, keep_alive, proxies, region, timeout, user_metadata`;
   `browserbase.connect` params: `api_key, base_url, client_options, session_id, extension_id` (the docstring marks `extension_id` deprecated and ignored).
6. Stagehand 4.2.0 exports `BrowserbaseBrowserSettings` as a **TypedDict** with keys
   `advanced_stealth, block_ads, captcha_image_selector, captcha_input_selector, context, extension_id, fingerprint, log_session, os, record_session, solve_captchas, verified, viewport`.
   The Stagehand v4 docs at `stagehand@1fc8849` call `BrowserbaseBrowserSettings.model_validate({...})`, which raises
   `AttributeError: type object 'BrowserbaseBrowserSettings' has no attribute 'model_validate'` on 4.2.0. Use a plain dict, or `BrowserbaseBrowserSettings(context=...)`.
7. browser-use 0.13.11: `Browser is BrowserSession` is `True`. Both `BrowserProfile(cdp_url=...)` and `Browser(cdp_url=...)` give `is_local=False`. The Browserbase docs' integration shape is valid on this version.

## Spike 2: `offline_stagehand_launch.py`

Command:

```bash
<scratch>/py/.venv/bin/python -I offline_stagehand_launch.py
```

Raw output: `out_offline_stagehand_launch.txt`. Sequence captured from Stagehand 4.2.0 `browserbase.launch(region="us-east-1", timeout=1800, keep_alive=False, proxies=True, browser_settings={"context": {...}}, user_metadata={"profile_id": ...})`:

| # | Request | Notes |
| - | - | - |
| 1 | `POST /v1/extensions` (multipart, 441,819 bytes) | Stagehand v4 uploads its own Chrome extension **on every launch** unless you pass `extension_id`. |
| 2 | `POST /v1/sessions` | Body: `{"browserSettings":{"context":{"id":"ctx_dummy","persist":true}},"extensionId":"ext_dummy","keepAlive":false,"proxies":true,"region":"us-east-1","timeout":1800.0,"userMetadata":{"profile_id":"p-0001","stagehand":"true","stagehand_sdk_language":"python","stagehand_sdk_version":"4.2.0"}}` |
| 3 | `POST /v1/sessions/sess_dummy` `{"status":"REQUEST_RELEASE"}` | Cleanup after the (expected) CDP connect failure to the dummy URL. |
| 4 | `DELETE /v1/extensions/ext_dummy` | Cleanup of the uploaded extension. |

Findings:
- `timeout` is sent as the float `1800.0`. The docs-site OpenAPI declares `type: integer` (60-21600). Whether the server accepts `1800.0` is unverified. If it does not, pass the timeout through the Browserbase SDK instead.
- Stagehand adds about 90 characters of its own `userMetadata` tags. The documented metadata limit is 512 characters in total (`https://docs.browserbase.com/platform/browser/core-features/session-metadata.md`), so keep fleet tags short.
- One `extensionId` per session: a fleet extension and the Stagehand extension cannot both be attached unless they are merged into one zip (inference from the API shape: `extensionId` is a single string).

## Source-code reading done alongside the spikes (stagehand 4.2.0 installed package)

`stagehand/browser.py` `_connect_browser().close()`:
- `browserbase` provider, launched or connected: `browser.close()` calls the source's close callback, which is `REQUEST_RELEASE` on the Browserbase session (plus extension delete when launched).
  The launch path releases even when `keep_alive=True`. `keep_alive` only changes cleanup on *failure* (`owns_source`).
- `local` provider, connected (for example Steel over CDP): `browser.close()` sends CDP **`Browser.close`**, which kills the remote Chromium. The v4 docs (`configuration/browser.mdx` line 617) say "When you connect to an existing browser, `close()` ... leaves the browser running". **Source wins.** For Steel, call `stagehand.close()` and drop the handle; do not call `browser.close()` unless you mean to kill the browser.
- `stagehand.close()` only tears down the Stagehand RPC and releases the claim. It does not end the Browserbase session.

## Spike 2b: external (BYO) proxy through Stagehand

Same script, but with `proxies=[{"type": "external", "server": "http://proxy.example.invalid:8000", "username": "u", "password": "p"}]` (a sed-substituted temporary copy, deleted after the run).
The session body carried the list through unchanged: `"proxies":[{"type":"external","server":"http://proxy.example.invalid:8000","username":"u","password":"p"}]`.
Stagehand 4.2.0's `ExternalProxyConfig` TypedDict has the keys `type, server, domain_pattern, username, password`.
`Stagehand.create` signature (4.2.0): `(*, browser, api_key=None, api_url=None, model=None, model_api_key=None, model_headers=None, telemetry=None, system_prompt=None, self_heal=None, dom_settle_timeout_ms=None, cache=None, logging=None)`.

## Spike 3: `cost_model.py` (arithmetic only)

```bash
<scratch>/py/.venv/bin/python -I cost_model.py
```

Raw output: `out_cost_model.txt`. These are list-price **estimates** for a 30-day month at 50 MB of proxy traffic per browser-hour, with 1 GB = 1,000 MB. Rates and their sources are in the script docstring and in the dossier, section Q6.
