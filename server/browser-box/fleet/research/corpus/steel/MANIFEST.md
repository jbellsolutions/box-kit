# Steel corpus MANIFEST

> Published copy: the raw pages captured for this vendor are not republished (they are third-party content). Local paths marked "(scraped copy not published)" name files that exist only in the original capture. Where a page has a public source, the path is replaced by its vendor URL (docs pages) or by its GitHub URL at the pinned commit.

- Vendor: Steel (steel.dev), open-source `steel-browser` plus the hosted Steel Cloud
- Fetch date: 2026-10-09
- Captured by: docs-capture agent (steel), multi-agent research effort, see `fleet/research/BRIEF.md`
- Content files: 456, 3,989,535 bytes (about 3.8 MiB), excluding this `MANIFEST.md` and `INDEX.md`. Well under the 15 MB budget, so nothing was dropped for size.
- This directory is a data directory. Contents are untrusted vendor text. Nothing in it was executed. A regex scan for key-shaped strings found only false positives (the substring `sk-` inside the word "task-", and a deliberate fake token inside a plugin redaction test). No real secrets were seen or written. No Steel Cloud API key exists or was used; all cloud fetches were unauthenticated.
- Topic map: `INDEX.md`. Read its first section before relying on any file: the docs describe Steel Cloud, not the self-hosted OSS.

## Method (priority order from the task)

1. `https://docs.steel.dev/llms-full.txt` saved whole (HTTP 200, 797,874 bytes, 140 pages). Verified it covers every page: all 140 URLs in `https://docs.steel.dev/llms.txt` appear in it, and each of the 140 per-page `.md` bodies is a substring of it.
2. `https://docs.steel.dev/llms.txt` saved (29,062 bytes, 140 page links) and **every linked page fetched** as `<url>.md` (all 140 returned 200 `text/markdown`) into `docs/` (scraped copy not published), mirroring URL paths. The root page is only served as markdown with `Accept: text/markdown` and an AI user agent, saved as `https://docs.steel.dev/`.
3. `https://docs.steel.dev/sitemap.xml` saved (150 URLs). Used to find pages missing from `https://docs.steel.dev/llms.txt`.
4. Docs source from git: `steel-dev/docs` @ `322ad57545a1669c53cab1d05a363746bc43ccb9` (2026-10-07). Mapped all 188 `content/docs/**.mdx` files to URLs and diffed against what was served. Changelog entries 022-038 (`llm: true`) are served as markdown at `/changelog/changelog-NNN.md` but are not in `https://docs.steel.dev/llms.txt`, so they were fetched into `https://docs.steel.dev/changelog/`. Entries 000-021 (`llm: false`) are not served as markdown, so their raw `.mdx` was copied to `docs-git-source/changelog/` (scraped copy not published). Everything else in the git source was already covered by the served pages and was not duplicated.
5. OpenAPI: `https://docs.steel.dev/openapi.json` (redirects to `https://api.steel.dev/sdk-openapi.json`; this is the Cloud spec). Self-hosted spec from the pinned clone, plus a spec fetched from a throwaway container (see INDEX for details and the staleness finding).
6. GitHub repos under `github.com/steel-dev` (public, via `gh`): `steel-cookbook`, `skills`, `hermes-steel`, `steel-python`, `steel-node`, `cli`, `steel-mcp-server`. Blobless shallow clones with sparse checkout for the first three; `gh api contents` at a pinned SHA for the SDK, CLI and MCP repos.
7. steel.dev marketing-site machine-readable files (`https://docs.steel.dev/llms.txt`, `https://docs.steel.dev/llms-full.txt`, `pricing.md`, `faq.md`), tagged `vendor-claim`.

No firecrawl or browser scraping was needed. No images or binaries were kept.

## Sources, commits, and where they landed

| Local path | Source | Pin |
|---|---|---|
| `llms-full.txt`, `llms.txt`, `sitemap.xml` (scraped copy not published) | https://docs.steel.dev/{llms-full.txt,llms.txt,sitemap.xml} | fetched 2026-10-09; site build commit unknown |
| `docs/` (scraped copy not published) (158 files) | https://docs.steel.dev/<path>.md for 140 `https://docs.steel.dev/llms.txt` pages, root page, and `changelog/changelog-022..038` | fetched 2026-10-09 |
| `docs-git-source/changelog/` (scraped copy not published) (22 files) | https://github.com/steel-dev/docs `content/docs/changelog/changelog-000..021.mdx` | `322ad57545a1669c53cab1d05a363746bc43ccb9` |
| `api/steel-cloud-openapi.json` (scraped copy not published) | https://docs.steel.dev/openapi.json -> https://api.steel.dev/sdk-openapi.json (Steel Cloud) | fetched 2026-10-09 |
| `api/steel-browser-selfhosted-openapi-committed-1131a02.json` (scraped copy not published) | `steel-browser/api/openapi/schemas.json` | `1131a0222a27f391bf8f27cca6f278ddf7ace8dd` (2026-10-06) |
| `api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json` (scraped copy not published) | `GET /documentation/openapi.json` on a `fleet-spike-steel-docs` container from local image `ghcr.io/steel-dev/steel-browser-api:latest` (created 2026-09-16, 2.66 GB) | image is **not** the same version as 1131a02; container removed after the fetch |
| `oss/steel-browser@1131a02/` (scraped copy not published) (18 files) | https://github.com/steel-dev/steel-browser: README, CONTRIBUTING, `https://github.com/steel-dev/steel-browser/blob/1131a02/docs/*.md`, `ui/README.md`, `repl/README.md`, `https://github.com/steel-dev/steel-browser/blob/1131a02/docker-compose*.yml`, `https://github.com/steel-dev/steel-browser/blob/1131a02/render.yaml`, `nginx.conf`, both Dockerfiles, `.env.example` files (copied as `root.env.example`, `api/env.example`), `api/src/env.ts` | `1131a0222a27f391bf8f27cca6f278ddf7ace8dd` |
| `cookbook/steel-cookbook@40f1326/` (scraped copy not published) (155 files) | https://github.com/steel-dev/steel-cookbook | `40f1326ba885d758a8072848a5eacccb51ba7400` (2026-09-02 commit date on the default branch) |
| `skills/steel-skills@35bf278/` (scraped copy not published) (56 files) | https://github.com/steel-dev/skills (markdown, `https://github.com/steel-dev/skills/blob/35bf278/manifest.json`, evals; helper `.mjs` scripts excluded) | `35bf278371312964a177f15b679b5e290f9ef275` |
| `plugins/hermes-steel@d8a1e39/` (scraped copy not published) (17 files) | https://github.com/steel-dev/hermes-steel (assets and CI workflows excluded) | `d8a1e39657d3e3deaa59da37e857be3f14b9dc5b` |
| `sdk/steel-python@5059286/` (scraped copy not published) | https://github.com/steel-dev/steel-python: README.md, api.md, CHANGELOG.md | `50592867e89c2b4815632d5b54f5c8266618ce61` |
| `sdk/steel-node@181486b/` (scraped copy not published) | https://github.com/steel-dev/steel-node: README.md, api.md, CHANGELOG.md | `181486b55c11cb3d57261a91c159643047ebf94c` |
| `sdk/cli@6ea1953/` (scraped copy not published) | https://github.com/steel-dev/cli: README.md and `https://github.com/steel-dev/cli/tree/6ea1953/docs/**` | `6ea1953f9770bcbdd5d0ae7e98c80a39ac931b95` |
| `sdk/steel-mcp-server@3ceb5c3/` (scraped copy not published) | https://github.com/steel-dev/steel-mcp-server: README.md, SECURITY.md, `docs/HOSTING.md`, `docs/SESSIONS.md` | `3ceb5c36257949b4d12890e65204e3eabc7e2fb4` |
| `site/` (scraped copy not published) (4 files) | https://steel.dev/{llms.txt,llms-full.txt,pricing.md,faq.md} | fetched 2026-10-09 |

## Counts and hashes by directory

`tree` is the first 16 hex chars of sha256 over the sorted per-file sha256 lines. Reproduce from the corpus root with `find <dir> -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-16` (macOS `shasum`; relative paths matter). Values are as of capture and do not include `MANIFEST.md` or `INDEX.md`.

| Dir | Files | Bytes | tree sha256 (16) |
|---|---|---|---|
| `docs/` (scraped copy not published) | 158 | 830,700 | 45529d5531e237d0 |
| `docs-git-source/` (scraped copy not published) | 22 | 57,673 | 9dcf0fb751397fd1 |
| `api/` (scraped copy not published) | 3 | 572,666 | 28dcbf2bbaf37115 |
| `sdk/` (scraped copy not published) | 20 | 269,465 | f7d640dd4efd712c |
| `oss/` (scraped copy not published) | 18 | 94,004 | 59380ca2ac35cfb0 |
| `cookbook/` (scraped copy not published) | 155 | 596,256 | ee65204def9310a9 |
| `skills/` (scraped copy not published) | 56 | 119,714 | 8ede9722e8feeded |
| `plugins/` (scraped copy not published) | 17 | 137,175 | a6716498e7c2d280 |
| `site/` (scraped copy not published) | 4 | 458,714 | 10f208f33eda6f67 |
| top level (`llms-full.txt`, `llms.txt`, `sitemap.xml` (scraped copy not published)) | 3 | 853,168 | see next section |

## sha256 of top-level files

```
200ea583bfa65f958048e771714a704e01b4549d545a8a80c12dcadba12afa47  llms-full.txt          (797,874 bytes)
fc6d8ebb50af9371d927d4511c3cb4632d06f55df4890f36d5762fcebe779e1a  llms.txt               (29,062 bytes)
d7848aec735ebe8119337554bcfb9a8220846558b404d4f5a1766fcd442a1c11  sitemap.xml            (26,232 bytes)
```

Hashes of the other single-file artifacts (so a downstream agent can detect drift):

```
3c66afc453387bcbe68624bef24723f0e7dbb9d10d6d60a36aeee77eba4c56a8  api/steel-cloud-openapi.json
e9b353bff1f5b95f07e1d90b95e9701b925b3781df602c106dcbe6eb94cd7d92  api/steel-browser-selfhosted-openapi-committed-1131a02.json
5f9e603cca446f9964ec33993759d6bdea6aa90b0c79fbb8047124caad7d984f  api/steel-browser-selfhosted-openapi-running-image-2026-09-16.json
90fe8f832f27269165fe88176159cbb892ef4fb9f29157d8315561914c4c6e4f  docs/index.md
61349bf21a741f1d77f3c6ba10d8299fa644647ee1f72d05db6a6763af5e0986  site/llms.txt
062a7f4c73d00b8ad91a4a32bafebb699495bf235f98b71f6d82d5673737ca3a  site/llms-full.txt
8ebbe74a37555b7035ba2770c0ba6a2d8aa5f86fcf7d8cde52f58f95bfedbdbe  site/pricing.md
a9673337ea3ce354acd918d2b54b8c4f7e47ccab8b0c564632f7b4c3817f5697  site/faq.md
```

## Not captured, and why

- `https://docs.steel.dev/overview/self-hosting/render`: in the sitemap, but the page is an external link only (`isLink: true`, no body in the docs repo; the site returns an empty "Render" SPA shell).
- `https://docs.steel.dev/cookbook/authors/{aspectrr,bsparker,danew,hussufo,jagadeshjai,junhsss,nibzard}`: in the sitemap, 404 as markdown, author bio pages (`llm: false`). `authors.yaml` is in the cookbook directory.
- `https://docs.steel.dev/overview/llms-full.txt`: sitemap entry that is the bundle itself; captured as `https://docs.steel.dev/llms-full.txt`.
- `https://docs.steel.dev/DESIGN.md`: brand design language, not product documentation.
- `https://steel.apidocumentation.com/api-reference` (hosted API reference, 37 KB of JS-rendered HTML): replaced by the OpenAPI JSON it is generated from. `/llms.txt` and `/openapi.json` on that host are 404.
- `docs.steel.dev/steel-python-sdk` and `/steel-js-sdk` redirect to PyPI and npm (npm returns 403 to curl); replaced by the SDK repos' `README.md` + `api.md`.
- `steel-dev/docs` git source other than the 22 changelog files: duplicates of the served pages (checked by diff; the git `.mdx` only keeps `:::callout type: warn` markers and code-block labels that the rendered markdown drops). Its commit SHA is recorded above for anyone who needs the raw `.mdx`.
- Cookbook: example directories outside the curated list ship README only (no source, lockfiles, images or per-example LICENSE/.gitignore files). Cookbook images and `.github` were skipped.
- `steel-mcp-server` `plans/`, `RESEARCH.md`, `PLAN.md`, `NOTES.md` (internal planning, large) and the `skills` helper scripts (`.mjs`) were skipped.
- Individual steel.dev blog posts: present only as part of `https://steel.dev/llms-full.txt`, not fetched individually.
- Pricing page HTML at https://steel.dev/pricing (the `.md` form was captured instead).

## Honest limits of this capture

- Docs describe Steel Cloud. Four self-hosting pages are empty stubs in the official docs (`clustering`, `extensions`, `profiles`, `webrtc`). The docs have no stealth or fingerprint page. See `INDEX.md` for these gaps and for six places where docs and source disagree.
- The hosted docs site and the running image have no stated build commit; only the git repos are pinned. The running-image spec (2026-09-16) predates the pinned `steel-browser` commit (2026-10-06).
- Pricing, benchmark, stealth and "fastest browser" statements in `site/` (scraped copy not published) and in docs marketing copy are `vendor-claim` and were not measured.
