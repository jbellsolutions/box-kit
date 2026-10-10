# System 1 decision-model spike: results

Date: 2026-10-09 (calls made around 02:53 UTC on 2026-10-10). Run from a workstation on a residential
network. Cloudflare reported the same edge for both TypeSafe and OpenRouter (`cf-ray`
response header). Script: [`spike_decide.py`](spike_decide.py). Raw request and response bodies
are in [`raw/`](raw/); no request headers or keys are stored.

## What was called

The fixtures are built from the live public page `https://quotes.toscrape.com/` and its `/login`
page, both fetched with curl on 2026-10-09. No browser was opened, nothing was logged in to, and
nothing was posted.

The payload shape follows `jev-automation` `core/decide.ts` and `core/verify.ts` at `edcbbae` (the
tip of `feat/steel-cdp`):

- `state = {command, page: {url, title, ...}}`.
- The target question's `instructions` is an object, `{question, command}`.
- `criteria` maps element ids to `describeElement`-style strings, plus a `none` option.
- The `blocker` question uses verify.ts's `BLOCKERS`.

I added `page.text_excerpt` and `page.fields` so the login-wall question has some evidence to read.

- **Goal:** "Find more quotes beyond the ones shown on this page".
- **Candidates:** 10 links plus `none`.
- **Right answer, written down before any call:** `e7` (`link "Next ->" -> /page/2/`).
- **Near-distractor:** `e9` (`link "GoodReads.com" -> https://www.goodreads.com/quotes`). It contains the word "quotes", and Jev reads instructions literally.

| id | endpoint | model | questions |
|---|---|---|---|
| ts1 | `POST https://api.typesafe.ai/v1/systemone` | `jev-1.13.0` (pinned) | target choice (11 options) + login_wall noul + blocker choice (9 options), one request |
| ts2 | same | `jev-1.13.0` | `/login` page: login_wall noul + blocker choice |
| ts3 | same | `jev-1.13.0` | ts1 with the option order reversed in both choice questions |
| or1 | `POST https://openrouter.ai/api/v1/systemone` | `perplexity/pplx-decider-v1.1-27b` | the exact ts1 body, only `model` changed |

Command:
`.venv/bin/python spike_decide.py <outdir> ts1` (then `ts2 ts3`, then `or1`), using the shared venv
at `<scratch>/py/.venv` (httpx 0.28.1).

## Raw numbers

| id | HTTP | wall ms | model echoed | input tok | target (p) | login_wall noul | blocker (confidence) | matches expectation |
|---|---|---:|---|---:|---|---:|---|---|
| ts1 | 200 | 329.4 (includes the TLS handshake) | `jev-1.13.0` | 1,032 | `e7` (1.00; every other option 0.00) | 0.04 | `none` (0.91; login_wall 0.08) | yes |
| ts2 | 200 | 263.6 | `jev-1.13.0` | 668 | n/a | **0.95** | `login_wall` (0.98) | yes |
| ts3 | 200 | 138.6 (warm connection) | `jev-1.13.0` | 1,032 | `e7` (1.00) | 0.04 | `none` (0.87; login_wall 0.12) | yes |
| or1 | 200 | 270.8 | `perplexity/pplx-decider-v1.1-27b-20261006`, provider `Perplexity` | 1,000 | `e7` (0.9985; e9 0.0004) | 0.0009 | `none` (0.978) | yes |

Observations, all hands-on and all n=1 per cell, so anecdotal:

- **Jev response shape** (direct TypeSafe):
  `{"model":"jev-1.13.0","answers":{"<id>":{"type":"choice","choice":"e7","confidence":1.0,"probabilities":{...}}, "<id>":{"type":"noul","noul":0.04}},"usage":{"input_tokens":1032,"output_tokens":208}}`.
  - **Probabilities are rounded to 2 decimals.** Most options come back as exactly `0.0`. That limits log-loss and calibration analysis.
  - **Correction: TypeSafe does send a request id.**
    - The first run kept only an allowlist of header names, so `x-typesafe-request-id` was dropped.
    - A free follow-up `GET https://api.typesafe.ai/v1/models` (03:01 UTC) captured the full header set: `date, content-type, transfer-encoding, connection, x-typesafe-request-id: req_…, server: cloudflare, cf-cache-status, set-cookie (redacted), content-encoding, cf-ray, alt-svc`. That GET response had **no rate-limit headers**.
    - Whether `POST /v1/systemone` sends rate-limit headers is **unconfirmed**: its full header set was not captured.
    - The script now records every header name, so the next run will show it.
    - Log `x-typesafe-request-id`.
- **The Decider response via OpenRouter** has the same shape plus `id` (`gen-dec-...`), `provider`, and `usage.cost` (`2e-05`). Its probabilities are full precision. `output_tokens` is 3 (Jev's was 208), and output is free on both.
- **One Jev-shaped body worked unchanged on a second provider.** That body uses an object `instructions` and object `state`, and OpenRouter's `/api/v1/systemone` accepted it for Perplexity's model. This is evidence (n=1) that one payload shape can serve several providers.
- **Option order (ts1 vs ts3):**
  - The target pick did not change.
  - Blocker confidence moved from 0.91 to 0.87, and `login_wall` moved from 0.08 to 0.12.
  - The pilot's 16-call validation saw shifts of up to 0.09 (`jev-agent-kit/source/jev-pilot-acceptance.md`).
- **Fan-out latency:** ts1 asked 3 questions and ts2 asked 2. Their latencies are within network noise. This is consistent with TypeSafe's claim that questions run in parallel, but n=1 does not prove it.
- **Context for these latencies:**
  - The browser-box README measured Jev's decision at 209–424 ms (median ~300 ms, n=20, one 8.8 s outlier) through `act` (2026-09-23).
  - An older local tool's staging acceptance measured a median of 443 ms (range 378–701 ms, n=5).
  - The Jev pilot measured a median of 487 ms (max 775 ms, n=16).
  - Cloudflare's own benchmark reports a Jev median of 524 ms (vendor-claim, measured from their side).
- **This test was easy.** Both models put ≥0.998 on the right answer. It shows that the wiring and shapes work. It is not an accuracy measurement. The README records a real Jev grounding miss: 0/3 on picking the first Wikipedia search result.

## Spend

| provider | calls | input tokens | cost | how computed |
|---|---:|---:|---:|---|
| TypeSafe (Jev, direct) | 3 | 2,732 | **$0.000115** | 2,732 × $0.042 / 1M (TypeSafe models page; output free) |
| OpenRouter (Decider) | 1 | 1,000 | **$0.00002** | `usage.cost` in the response |
| **Total** | 4 | 3,732 | **≈ $0.000135** | caps were $0.25 (TypeSafe) and $0.10 (OpenRouter) |

The OpenRouter key's `usage` field (`GET /api/v1/key`) rose by $0.002046 between the before and
after reads. Other agents share the same key concurrently, so that delta is not attributable to
this spike. The call's own `usage.cost` is the number to use.

## Catalog check (no key, free)

- `GET https://openrouter.ai/api/v1/models?output_modalities=decisions` returned **19** entries:
  - `cloudflare/clef`, `cloudflare/clef-flash`, `cloudflare/clef-omni`
  - `inception/mercury-decide` (and `:free`), `jaredpalmer/kev-4b`, `liquid/d1`, `microsoft/microsoft-decision-1`, `nace-ai/drex-v1.5`
  - `openai/gpt-6-luna-decisions`
  - `perplexity/pplx-decider-v1.1-27b`
  - `respan/span-01`, `respan/span-01-lite` (and `:free`), `togethercomputer/tev1-4b-experimental`
  - `typesafe/jev-1.13`, `~typesafe/jev-latest`
  - `upstage/solar-decide`, `upstage/solar-decide-flash`
- The default `/api/v1/models` listing does not show them.
- `cloudflare/clef` and `cloudflare/clef-flash` each have two OpenRouter endpoints:
  - Cloudflare, context 65,536.
  - PrimeIntellect, context 16,384.

## Not run (scope)

Clef, Clef-flash, Clef-omni and `openai/gpt-6-luna-decisions` all appear in OpenRouter's catalog
under `output_modalities=decisions`, so the same OpenRouter key would reach them. The task made
hands-on calls for Clef and OpenAI Decisions conditional on a `CLOUDFLARE_*` or `OPENAI_API_KEY`
being in the environment. Neither is, so they are documented from docs only.

Follow-up for the orchestrator to approve, at roughly $0.001: run `or1` against `cloudflare/clef`,
`cloudflare/clef-flash` and `openai/gpt-6-luna-decisions`. This checks whether OpenRouter
translates the System One shape for OpenAI's differently shaped Decisions API.
