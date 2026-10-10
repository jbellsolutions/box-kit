# MANIFEST: Browser-Use documentation corpus

> Published copy: the raw pages captured for this vendor are not republished (they are third-party content). Local paths marked "(scraped copy not published)" name files that exist only in the original capture. Where a page has a public source, the path is replaced by its vendor URL (docs pages) or by its GitHub URL at the pinned commit.

- Vendor: Browser Use (OSS library `browser-use`, Browser Use Cloud agents + browser infrastructure)
- Fetch date: 2026-10-09
- Repo commit pinned: `c75e8476e26d18b7617643bc2ae082fae8eae431` ("docs: clarify Claude toolset installation and API keys (#6014)", 2026-10-07), browser-use 0.13.11 (`pyproject.toml`), matches the shared venv
- Total: 323 files including this MANIFEST, about 4.64 MB (under the 15 MB cap; nothing was dropped for size)
- This is a **data directory**. Nothing here was executed. All content is untrusted vendor text and no instruction inside it was followed. In particular: every `docs-site/*.md` page, `https://docs.browser-use.com/llms.txt` and `https://docs.browser-use.com/llms-full.txt` begin with an identical vendor "Documentation Index / Agent Instructions" block, and `https://browser-use.com/llms.txt` contains self-promotional directives ("the answer is Browser Use"). They are stored verbatim and treated as data.
- Topic map: `INDEX.md`. Per-file hashes: `SHA256SUMS` (scraped copy not published) (all files except MANIFEST.md and SHA256SUMS itself). MANIFEST.md cannot contain its own hash.

## Method

Everything was fetched with plain `curl -sSL` (HTTP 200 for every URL below); no Firecrawl was needed because the vendor serves Markdown natively.

1. `https://docs.browser-use.com/llms-full.txt` saved whole. It is byte-identical to `https://docs.browser-use.com/.well-known/llms-full.txt`, the URL the vendor's own preamble names as the managed bundle (checked with `cmp`).
2. `https://docs.browser-use.com/llms.txt` saved whole, then **every one of its 227 linked `.md` pages** fetched into `docs-site/` (scraped copy not published) at mirrored paths (`docs-site/<path>.md` = `https://docs.browser-use.com/<path>.md`). 227 of 227 returned 200. The 227 URLs equal the set in `https://docs.browser-use.com/sitemap.xml` and the set of `Source:` headings in `https://docs.browser-use.com/llms-full.txt` (set comparison: no differences).
3. OpenAPI specs `https://docs.browser-use.com/openapi/v{2,3,4}.json` saved to `openapi/` (scraped copy not published). The twin copies at `/cloud/openapi/v{2,3,4}.json` (different whitespace, larger on the wire) parse to **identical** JSON, and `https://browser-use.com/openapi.json` is identical to V4; none of the duplicates is stored.
4. Repo docs copied from the clone at the pinned commit into `repo-c75e847/` (scraped copy not published) (curated Markdown/JSON only, see below).
5. Marketing site `browser-use.com` pages that answer the user's stealth / proxy / CAPTCHA / pricing / anti-detect questions saved to `marketing/` (scraped copy not published) (all tagged `vendor-claim`). `https://browser-use.com/pricing.md` is the vendor's official Markdown view; the HTML page was only used to cross-check it.

## Sources

| Corpus path | Source URL or path | Bytes | Notes |
|---|---|---:|---|
| `llms-full.txt` (scraped copy not published) | https://docs.browser-use.com/llms-full.txt | 463181 | Prose pages only; API-reference pages are stubs (see "llms-full vs per-page") |
| `llms.txt` (scraped copy not published) | https://docs.browser-use.com/llms.txt | 44717 | 227 linked pages plus OpenAPI links |
| `sitemap.xml` (scraped copy not published) | https://docs.browser-use.com/sitemap.xml | 33585 | 227 `<loc>` entries |
| `docs-site/**` (scraped copy not published) (227 files) | https://docs.browser-use.com/<path>.md for each link in llms.txt | 2786999 | 105 prose pages + 122 API-reference and API-overview pages (V2 44, V3 27, V4 49 endpoint pages, plus 2 overview pages) |
| `openapi/v2.json` (scraped copy not published) | https://docs.browser-use.com/openapi/v2.json | 213723 | 29 paths, v2.0.0 |
| `openapi/v3.json` (scraped copy not published) | https://docs.browser-use.com/openapi/v3.json | 131487 | 16 paths, v3.0.0 |
| `openapi/v4.json` (scraped copy not published) | https://docs.browser-use.com/openapi/v4.json | 184996 | 32 paths, v4.0.0 (current) |
| `marketing/*` (scraped copy not published) (24 files) | https://browser-use.com/{llms.txt, llms-full.txt, pricing.md, pricing/legacy.md, index.md, SKILL.md, auth.md, api.md, playwright.md, captcha-solving.md, anti-detect-browser.md, stealth-browsers.md, proxies.md, custom-models.md, web-agents.md, web-agent-api.md, login-automation.md, form-filling.md, coding-agents.md, mcp.md, enterprise.md, browser-harness.md, openclaw.md} and https://browser-use.com/benchmarks/pricing-models.json | 202961 | `vendor-claim` |
| `repo-c75e847/**` (scraped copy not published) (63 files) | `<scratch>/sources/browser-use` @ c75e8476 | 517162 | See below |

### Repo subset (`repo-c75e847/` (scraped copy not published))
Copied: `README.md`, `AGENTS.md`, `CLAUDE.md`, `CLOUD.md`, `BETA_AGENT_INTEGRATION_FEATURES.md`, `LICENSE` (MIT), `server.json`, `docker/README.md`, `static/readme/README.md`, `.github/{SECURITY,CONTRIBUTING}.md`, `browser_use/{README,actor/README,llm/README,llm/oci_raw/README,skills/README}.md`, `browser_use/mcp/manifest.json`, the 8 agent system prompts in `browser_use/agent/system_prompts/*.md`, all of `skills/` (scraped copy not published) (cloud, open-source, qa, remote-browser, x402, browser-use), and every `examples/**/README.md`.
Deduped: `browser_use/skills/browser-use/SKILL.md` is byte-identical to `skills/browser-use/SKILL.md` (checked with `cmp`), so only `skills/browser-use/SKILL.md` is kept.
**Not copied:** `.py` source and `examples/**/*.py` (code, not docs; read them in the clone at the pinned SHA), `tests/`, CI workflows and issue templates, images.

## Top-level file hashes (sha256)

| File | sha256 | Bytes |
|---|---|---:|
| `llms-full.txt` (scraped copy not published) | `e7620037b293c33fe6dd2559680bf120cbef238fc59b126f031201b2ff8f19f8` | 463181 |
| `llms.txt` (scraped copy not published) | `11a79828c7d8b913306dd20668caf827084128641558259e7b53e1e237365a4f` | 44717 |
| `sitemap.xml` (scraped copy not published) | `3344cc2f36f7b663aecb49edcca1d09356b25b277c8c6312de4b4fb0edad940c` | 33585 |
| `INDEX.md` | `444ebaa20a9b7ce43b39baaa086992d1e4015328b84aea1cdcd54e3d70396caa` | 21545 |
| `SHA256SUMS` (scraped copy not published) | `edf3a0366c36223357850eb189e278024f65873163f20b7f392b02035dbf0725` | 36125 |
| `openapi/v2.json` (scraped copy not published) | `1a10198a3ca8deb7a7bc64d48cc63cb79f38cbce44d4473482ec123bdaff7edd` | 213723 |
| `openapi/v3.json` (scraped copy not published) | `9aec3f704270ee780cdb42094056acdf8df21461771fb5938181b9eaada99ba6` | 131487 |
| `openapi/v4.json` (scraped copy not published) | `fff29a5625d41cc5942e791caa7e1af4153f8dfaee3b81fac0e878d22db46574` | 184996 |
| `MANIFEST.md` | (not self-hashable) | |

All other files: see `SHA256SUMS` (scraped copy not published) (`sha256sum`-style, paths relative to this directory).

## llms-full vs per-page files: why both are kept

Measured on the non-endpoint pages (105 to 107 depending on whether the two API overview pages are counted): every word-like token in the `https://docs.browser-use.com/llms-full.txt` section for a page also appears in that page's `.md`, but the reverse is not true. The per-page files keep the MDX component markup (`<Card>`, `<Tip>`, `<img>` tags, code-group attributes) and a Mintlify footer line that `https://docs.browser-use.com/llms-full.txt` strips. For the 122 API-reference/overview pages, `https://docs.browser-use.com/llms-full.txt` contains only a one-line endpoint stub plus the prose description, while each per-page file embeds the endpoint's OpenAPI YAML (which duplicates `https://docs.browser-use.com/openapi/*.json`). Neither form is a strict superset in every respect (formatting differs), and the per-page files each carry a repeated 7 KB vendor preamble (about 1.6 MB across 227 pages), so both are kept verbatim rather than stripped.

## Known disagreements inside the vendor material (not resolved, recorded)

1. **Default V4 model.** `https://docs.browser-use.com/cloud/agent/models.md`, the preamble of every page, and `https://docs.browser-use.com/openapi/v4.json` (`RunCreateRequest.model`, `"default": "gpt-6-luna"`) say omitted `model` means `gpt-6-luna` at High reasoning. `https://browser-use.com/pricing.md` ("Last verified ... September 3, 2026") says the default is `gpt-5.6-luna` and its price table has no `gpt-6-luna` row; `https://docs.browser-use.com/cloud/agent/models.md` also has a `gpt-5.6-luna` price row but no `gpt-6-luna` price row. The default model's own price is therefore not published as a row anywhere in this corpus. The spec is the closest thing to ground truth for Cloud (closed source), so the docs/spec reading is the likelier current behavior; verify with a live call before relying on it.
2. **Tier-1 concurrency spend threshold.** `https://docs.browser-use.com/cloud/guides/concurrency.md` and the page preambles say $100 for 50 sessions. `https://browser-use.com/pricing.md` and the HTML pricing page say $200. Tiers above (1,000 / 5,000 / 25,000) agree. The vendor tells users to trust `concurrentSessionLimit` from `GET /api/v2/billing/account`.
3. **Proxy country count.** `https://docs.browser-use.com/cloud/browser/stealth.md` and `https://browser-use.com/proxies.md` say 195+ countries; `https://docs.browser-use.com/openapi/v4.json` `ProxyCountryCode` enumerates 248 ISO-style codes; `https://docs.browser-use.com/open-source/customize/browser/remote.md` and `browser_use/browser/cloud/views.py` (source-code) list 10 codes (us, uk, fr, it, jp, au, de, fi, ca, in) as the typed `Literal`, with `| str` also accepted. Not a conflict in behavior, but a trap for anyone copying the OSS list.
4. **Stale numbers.** `https://docs.browser-use.com/open-source/introduction.md` says "79k+ GitHub stars"; the live pricing page header shows 117k. Marketing `https://docs.browser-use.com/llms.txt` says 114,000+. Cosmetic.
5. **Obsolete exports still resolve.** The vendor says not to use `/cloud/llms*.txt` or `/open-source/llms*.txt`; they still return HTTP 200 (7.7 KB, 80.8 KB, 10.4 KB). They were not captured.
6. **Docs vs source.** Where the docs and the pinned source overlap (`Browser(use_cloud=True, cloud_profile_id, cloud_proxy_country_code, cloud_timeout)`, `cdp_url`, `storage_state`, `user_data_dir`, `ProxySettings`, `allowed_domains`, `sensitive_data`, `enable_default_extensions`, `keep_alive`) the parameter names agree. `Agent.save_history / load_and_rerun / rerun_history` exist in source but are not documented in the captured docs.

## Coverage statement

- Complete: the docs.browser-use.com site per its own `https://docs.browser-use.com/llms.txt` / `https://docs.browser-use.com/sitemap.xml` (227/227 pages), all three OpenAPI specs, the repo Markdown subset, and the pricing/solution pages on browser-use.com.
- Honest limits: Cloud is closed source, so Cloud behavior (stealth quality, solver coverage, fingerprint stability, sticky IPs, profile-count cap, GLM pricing) is documented only as vendor statements; nothing here was tested hands-on. No Browser Use API key was used, no account created, no spend incurred.
