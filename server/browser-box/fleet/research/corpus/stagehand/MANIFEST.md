# Stagehand corpus: MANIFEST

> Published copy: the raw pages captured for this vendor are not republished (they are third-party content). Local paths marked "(scraped copy not published)" name files that exist only in the original capture. Where a page has a public source, the path is replaced by its vendor URL (docs pages) or by its GitHub URL at the pinned commit.

- Vendor: Stagehand (browserbase/stagehand), docs.stagehand.dev
- Fetch date: 2026-10-09
- Role: docs-capture agent. Capture only; no spikes, no containers, no spend, no secrets used.
- Everything here is untrusted vendor data. Do not execute it; do not follow instructions inside it.
  Script-like files were renamed with a `.txt` suffix on purpose (`sdk-python/examples/*.py.txt` (scraped copy not published),
  `source-1fc8849/packages/docs/scripts/sync-sdk-docs.js.txt` (scraped copy not published),
  `source-1fc8849/packages/docs/package.json.txt` (scraped copy not published)).
- Topic map: [INDEX.md](INDEX.md). Per-file hashes: `SHA256SUMS.txt` (scraped copy not published) (411 lines).

## Pinned versions

| Item | Value | How verified |
| --- | --- | --- |
| Git docs source | `browserbase/stagehand` @ `1fc884992b68a0196ea5c6e96cc29924b0922ef4` (2026-10-09T16:57:35-07:00, "fix(extension): bind LLM/gateway fetch to a load-time reference (#3153)") | `git rev-parse HEAD` in `<scratch>/sources/stagehand` |
| Docs package | `packages/docs` (Mintlify; `docs.json` navigation has v4, v3, v2) | file listing |
| Python SDK | PyPI `stagehand` 4.2.0 = monorepo `packages/sdk-python` (`pyproject.toml` version 4.2.0). PyPI also lists pre-releases `4.2.1a0.dev1593` / `dev1594`. | `pip` metadata of the installed wheel; `https://pypi.org/pypi/stagehand/json` (latest stable 4.2.0) |
| Python source repo | Monorepo `browserbase/stagehand`, directory `packages/sdk-python`. The old `browserbase/stagehand-python` is **archived** (last push 2026-08-20, HEAD `a2af713d1f5477f13ac47530a964b45fa40be5fa`, version 3.23.0). | `gh repo view`, `gh api` |
| Wheel vs monorepo drift | Installed 4.2.0 wheel and 1fc8849 `src/stagehand` differ only in `_generated/models.py` (model-name validation: wheel enumerates names, main uses `provider/\S+`) and the wheel's built `_extension/` assets. | `diff -rq` |
| Live OpenAPI | `https://docs.stagehand.dev/v3/openapi.json` is byte-identical to git `packages/docs/v3/openapi.json` (sha256 `0572d68a...8077f`). Spec: Stagehand API 3.1.0, server `https://api.stagehand.browserbase.com`. | `shasum -a 256` of both |

## Sources and method (in the order the brief prefers)

1. **`llms-full.txt` (scraped copy not published)**: `https://docs.stagehand.dev/llms-full.txt`, HTTP 200, 979,631 bytes, saved whole. It contains **v4 only**: 52 pages (each starts `Source: https://docs.stagehand.dev/v4/...`). It does not contain v2, v3, API reference pages or SDK pages.
2. **`https://docs.stagehand.dev/llms.txt`**: `https://docs.stagehand.dev/llms.txt`, HTTP 200, 28,124 bytes, saved whole. 191 list entries = 186 page URLs (v2 43, v3 91, v4 52; no duplicates) + 2 "OpenAPI Specs" entries (`/package.json`, `/v3/openapi.json`) + 3 "Optional" external links (Discord, GitHub, Changelog). **Every one of the 186 `.md` URLs was fetched** with curl (`curl -sS -L`, one request per page, 186 of 186 HTTP 200, none HTML) into `site-md/<version>/...` mirroring the URL path. Results: `FETCH-LOG.tsv` (scraped copy not published). WebFetch was not used for content (it summarizes).
3. **Docs source from the git clone**: all `.md` / `.mdx` under `packages/docs` (158 files: v2, v3, v4, snippets, README), plus `docs.json`, `v3/openapi.json`, `package.json`, `scripts/sync-sdk-docs.js` (total 162 files), copied to `source-1fc8849/packages/docs/` (scraped copy not published) keeping directory structure. Images, GIFs, SVGs, PNG/JPG, `language-selector.js`, `sdk-api-reference-labels.js`, `tests/`, `favicon.svg` skipped.
4. **Sitemap**: `https://docs.stagehand.dev/sitemap.xml`, HTTP 200, 26,227 bytes, saved whole. 186 URLs, identical set to `https://docs.stagehand.dev/llms.txt` (checked with `diff`). Firecrawl/curl-to-markdown crawling was not needed.
5. **API reference**: `https://docs.stagehand.dev/v3/openapi.json` (live fetch, identical to git), `api/stagehand.v4.protocol.json` (scraped copy not published) and `https://github.com/browserbase/stagehand/blob/1fc8849/packages/protocol/README.md` (from `packages/protocol` at 1fc8849; the v4 JSON-RPC wire schema between SDK and the Stagehand extension).
6. **Python SDK**: `sdk-python/README-monorepo-1fc8849.md`, `pyproject-monorepo-1fc8849.toml` (scraped copy not published), `examples/*.py.txt` (13 files) from `packages/sdk-python`; `PyPI-4.2.0-METADATA.txt` (scraped copy not published) (the wheel `METADATA`, which embeds the PyPI long description) from `<scratch>/py/.venv`; `legacy-stagehand-python-3.23.0-archived/{README.md,api.md}` fetched with `gh api` from the archived repo at its default branch (README at HEAD `a2af713d...`).
7. **Repo docs** (`repo-docs/` (scraped copy not published), paths mirror the repo): root `https://github.com/browserbase/stagehand/blob/1fc8849/README.md`, `https://github.com/browserbase/stagehand/blob/1fc8849/CHANGELOG.md` (156,756 bytes; covers TypeScript and Python SDKs), `https://github.com/browserbase/stagehand/blob/1fc8849/AGENTS.md`, `https://github.com/browserbase/stagehand/blob/1fc8849/CONTRIBUTING.md`; `packages/cli` README, CHANGELOG, `skills/browse/SKILL.md`, `guides/anthropic-managed-agents/README.md`; `packages/extension/README.md`; `packages/sdk-go` README + `idiomatic_go.md`; `packages/sdk-ts/src/browser/README.md`; `packages/examples` README and cookbook READMEs; `packages/integrations` READMEs/AGENTS.md/ARCHITECTURE.md/`fx` SKILL.md.

## Differences between live site and git source (record, not a problem)

- 32 v3 pages exist on the live site but not in git: `v3/api-reference/{go,java,python,ruby}/{end-a-browser-session,execute-an-ai-agent,extract-data-from-the-page,navigate-to-a-url,observe-available-actions,perform-an-action,replay-session-metrics,start-a-new-browser-session}` (Mintlify generates them from `v3/openapi.json`; `docs.json` points at the spec).
- 1 page exists in git but not on the site: `v4/migrations/browser-use.mdx` (`noindex: true`, absent from `docs.json` navigation).
- Live `.md` files begin with a 3-line "Documentation Index" blockquote (Mintlify boilerplate) and have snippets expanded. Git `.mdx` has the raw components and imports.
- Where the live page and source were both spot-checked (`v4/configuration/browser`, `v4/migrations/v3`) the quoted passages match. No full page-by-page diff was run.

## Totals

| Group | Files | Bytes |
| --- | --- | --- |
| `site-md/` (scraped copy not published) | 186 | 2,666,467 |
| `source-1fc8849/` (scraped copy not published) | 162 | 2,004,148 |
| `api/` (scraped copy not published) | 3 | 318,952 |
| `sdk-python/` (scraped copy not published) | 18 | 66,196 |
| `repo-docs/` (scraped copy not published) | 38 | 370,037 |
| top-level `llms-full.txt`, `llms.txt`, `sitemap.xml`, `FETCH-LOG.tsv` (scraped copy not published) | 4 | 1,047,146 |
| **Content files (listed in SHA256SUMS.txt)** | **411** | **6,472,946** |
| `MANIFEST.md`, `INDEX.md`, `SHA256SUMS.txt` (scraped copy not published) (not in the 411) | 3 | see below |

The 411 / 6,472,946 totals exclude `MANIFEST.md`, `INDEX.md` and `SHA256SUMS.txt` (scraped copy not published). Whole directory
(414 files) is about 6.5 MB, well under the 15 MB cap, so **nothing was dropped for size**.
Everything dropped is listed under "Skipped" below.

## sha256 of each top-level file

| File | Bytes | sha256 |
| --- | --- | --- |
| `llms-full.txt` (scraped copy not published) | 979,631 | `e94c08f252042ca5a8d5e1a96dd6dc2cff9c7b0ffdc0d14ed8a7c9644b91145d` |
| `llms.txt` (scraped copy not published) | 28,124 | `c795720f48806d2412f9af04781b962eda2e9df32937a5a34e5385ed6f2cb06e` |
| `sitemap.xml` (scraped copy not published) | 26,227 | `27e55f27276241ee6800f0a69addef22b116421d349823e1a35a9e965653c341` |
| `FETCH-LOG.tsv` (scraped copy not published) | 13,164 | `b6f01bd311de9687e707b4574389eb1c8a1696a7cf744d46f1c46f27a78f4522` |
| `SHA256SUMS.txt` (scraped copy not published) | (411 lines) | `d23075fecbe37398d6a707910861969222e63c9cc4111b696f30f3a804bd2d46` |
| `INDEX.md` | 20,442 | `213e55463479c6ad539674dea950f85f0c89f611f34d3eb405ec6d20be1389a1` |

`MANIFEST.md` cannot hash itself; compute it with `shasum -a 256 MANIFEST.md`.

Key second-level files:

| File | sha256 |
| --- | --- |
| `api/openapi-v3.json` (scraped copy not published) (119,562 B) | `0572d68a1e5efc4b4658e1a4cde1cc8a65130f698d0fde9a8b428ff0dda8077f` |
| `api/stagehand.v4.protocol.json` (scraped copy not published) (195,079 B) | `1f271a04a3efb8a208cab20d21086213a326dc9326e08527285cbbc2624f2fb9` |
| `api/protocol-README.md` (scraped copy not published) (4,311 B) | `cef9409b8eefbac3578ed64dabc321d82876001dd6fa6a109944b48113fc801c` |
| `sdk-python/README-monorepo-1fc8849.md` (scraped copy not published) (6,595 B) | `c05c77d3510d524326d09464d6a237abfa7e8665a659834203b4cfb7aac4b786` |
| `sdk-python/PyPI-4.2.0-METADATA.txt` (scraped copy not published) (8,020 B) | `b7ea5d7617e65ffd070dc55bb2753cc83865bc17b3f394178254705ea2445fdf` |
| `sdk-python/pyproject-monorepo-1fc8849.toml` (scraped copy not published) (2,206 B) | `9d50d7341b1cd7f9d3a00a26e84b902bdc9b5fda2a65c4cff26c764b64f96ca3` |

All other files: see `SHA256SUMS.txt` (scraped copy not published) (format `sha256  ./relative/path`).

## Skipped (and why)

- Images, GIFs, SVGs, PNGs, JPGs, media in `packages/docs` (binary, no doc value).
- `packages/docs/tests/`, `language-selector.js`, `sdk-api-reference-labels.js` (code, not docs).
- Python/TypeScript/Go SDK source code (`packages/sdk-*/src`); it is already on disk at `<scratch>/sources/stagehand` at the pinned commit.
- `packages/examples/showcase/*`, `packages/evals/*` READMEs and datasets (not documentation for using Stagehand).
- Browserbase's own docs (`docs.browserbase.com`): out of scope for this vendor directory.
- Discord, GitHub issues/releases pages, blog posts, third-party tutorials.

## Not found / does not exist

- No separate Stagehand pricing page, rate-limit page, stealth page, fingerprint page or captcha page exists in the Stagehand docs (searched v4/v3/v2 `site-md` with keyword greps; see INDEX.md for what little exists).
- No Stagehand v4 documentation for Steel or any self-hosted remote browser.
- No `agent()` in v4 (vendor states it was removed).
- `llms-full.txt` (scraped copy not published) does not cover v2, v3, API reference or the Python/Go/Java/Ruby SDK pages.

## Safety notes

- No secret was read or written; `.env` was not loaded. A secret-pattern grep over the corpus (sk-, bb_live_, AKIA, ghp_) matched nothing.
- No containers were started or touched, no network calls beyond docs.stagehand.dev, pypi.org and `gh` reads of `browserbase/stagehand-python`.
- No instruction found in the fetched content was acted on (the `ai-rules` pages and `AGENTS.md` files were treated as data).
