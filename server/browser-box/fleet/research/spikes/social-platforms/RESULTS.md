# Spike: lead-gen cascade, tier 0 (plain HTTP, no browser, no LLM)

Date: 2026-10-10 (UTC 07:35-07:36). Spend: **$0** (stdlib Python, no model calls, no paid services).
Targets: public test pages from BRIEF.md plus a local fixture. No social sites, no logins.
No containers were started.

## What it tests
Tier 0 of the cascade "plain HTTP fetch -> Stagehand extract on known pages -> Browser-Use exploration":
robots.txt check, one GET, extraction of public business-contact signals (schema.org JSON-LD
Organization/LocalBusiness, `mailto:`, `tel:`, links to the company's own social profiles,
contact/about links), and the decision "does this page need a browser?".

## Commands
```
python3 -I leadgen_tier0.py https://example.com/ https://books.toscrape.com/ \
  https://quotes.toscrape.com/ https://quotes.toscrape.com/js/ https://the-internet.herokuapp.com/   # run1 (v1 heuristic), run2 (v2)
python3 -I leadgen_tier0.py --expect 'class="quote"' https://quotes.toscrape.com/ https://quotes.toscrape.com/js/   # run3
python3 -I leadgen_tier0.py --fixture fixture_company.html
```
Raw output: `run1.jsonl`, `run2.jsonl`, `run3.jsonl`, `fixture_out.json`.
Note: `run1.jsonl` came from the first version of the script (v1 heuristic `text < 400 and scripts >= 3`).
The committed script carries the v2 heuristic plus `--expect`, so it reproduces run2 and run3, not run1.

## Raw numbers (hands-on)
| URL | status | ms | bytes | visible text chars | scripts | v1 needs_browser | v2 needs_browser | goal-based (`--expect`) |
|---|---|---|---|---|---|---|---|---|
| example.com | 200 | 94 / 70 | 577 | 324 | 1 | False | **True (false positive)** | n/a |
| books.toscrape.com | 200 | 236 / 344 | 51,294 | 1,665 | 7 | False | False | n/a |
| quotes.toscrape.com | 200 | 195 / 191 / 276 | 11,064 | 1,564 | 0 | False | False | False (correct) |
| quotes.toscrape.com/js/ | 200 | 224 / 145 / 142 | 5,808 | 65 | 2 | **False (false negative)** | True | **True (correct)** |
| the-internet.herokuapp.com | 200 | 114 / 197 | 4,072 | 783 | 6 | False | False | n/a |

Fixture (`fixture_company.html`): extracted the LocalBusiness JSON-LD (name, email, telephone,
url, sameAs Facebook/Instagram, address), one `mailto:`, one `tel:`, the LinkedIn company link,
and both contact/about links. All in one pass, 0 ms network.

## Findings
1. Tier 0 costs ~0.1-0.35 s and $0 per page. For lead gen on company websites, most of the
   contact data lives in static HTML (JSON-LD, mailto/tel, footer social links). This tier should
   handle the bulk of the work.
2. **Page-shape heuristics are unreliable escalation signals.** v1 ("thin text and >= 3 scripts")
   missed the JS-only page. v2 ("thin text and any script") flagged example.com. Escalate to a
   browser when **the extraction goal is not met in the static HTML** (the `--expect` check, or
   "no JSON-LD/mailto/contact link found"), not on page shape.
3. robots.txt is honored before every fetch (urllib.robotparser). All five test hosts allowed the
   fetch.
4. Not measured here: tiers 1 and 2 (Stagehand `extract`, Browser-Use). Their per-call token
   costs are in the stagehand, browser-use and reasoning-models spikes; this spike does not
   repeat them.
