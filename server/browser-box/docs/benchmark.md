# Benchmark: B5, act vs task

*Measured on the retired Steel engine (a self-hosted browser). They have not been rerun on hosted browsers.*

## Method

`scripts/bench.py` runs 5 jobs, each 3 times through `act` (the caller plans the steps, Jev
grounds each one) and 3 times through `task(surface="browser")` (Browser-Use, with
`z-ai/glm-5.3-flash` on OpenRouter, plans them) — 30 runs total, against the same Steel browser
on a Mac, through the real MCP endpoint. Run it yourself with:

```bash
.venv/bin/python scripts/bench.py 3 > bench/results.json
```

Success is checked against ground truth fetched **separately** — the Wikipedia search API, the
quotes pages, the live form and to-do DOM — never against the agent's own claim. The five jobs:
search a site and open the top result, fill a form and stop before submitting, paginate and
collect results, carry state across pages (a cookie standing in for a login), and drive a
JS-heavy SPA (TodoMVC React).

Measured 2026-09-23, Jev at commit `edcbbae` (`edcbbae8e0f7d31359294c93d53cad159d00696a`, per
`bench/results-2026-09-23.json`'s `jev_ref`). Raw rows — one per run, with the command log,
timings, and Jev's decision counts — are in
[`bench/results-2026-09-23.json`](../bench/results-2026-09-23.json).

Two things to know before reading the numbers (from the README):
- `act`'s wall time does **not** include the caller's own thinking between steps, and its cost
  does not include the caller's tokens: in real use, every caller turn is also a model call on
  the caller's side (2–4 turns per job here). `task`'s numbers include all of its planning.
  "Caller turns" is the column that shows the difference.
- Steel peaked at 1.36 GiB during a task; the memory cap in `compose.yml` is 1.5 GiB.

## Results

| job | via | success | median s | caller turns | agent steps | model cost (median) | Steel peak |
|---|---|---|---|---|---|---|---|
| search a site, open the top result | act | 0/3 | 3.8 | 3 | 3 | caller's | 1219 MiB |
| search a site, open the top result | task | 2/3 | 126.8 | 1 | 4 | $0.0059 | 1355 MiB |
| fill a form, stop before submit | act | 3/3 | 4.7 | 3 | 7 | caller's | 1104 MiB |
| fill a form, stop before submit | task | 3/3 | 118.6 | 1 | 5 | $0.0052 | 1155 MiB |
| paginate and collect | act | 3/3 | 2.2 | 3 | 3 | caller's | 1154 MiB |
| paginate and collect | task | 3/3 | 37.0 | 1 | 4 | $0.0042 | 1206 MiB |
| state across pages (a cookie, standing in for a login) | act | 3/3 | 0.5 | 2 | 2 | caller's | 984 MiB |
| state across pages | task | 1/3 | 31.1 | 1 | 2 | $0.0026 | 1111 MiB |
| JS-heavy SPA (TodoMVC React) | act | 3/3 | 3.0 | 3 | 4 | caller's | 1164 MiB |
| JS-heavy SPA | task | 0/3 | 300 (timeout) | 1 | 2 | $0.0064 | 1129 MiB |

## Conclusions

**Which to use:** `act` whenever the caller can say the steps. It was 10–60x faster and won or
tied every job but one. `task` is for a goal that cannot be broken into steps, or when the
caller should not spend its own turns. Read its answer with care.

- **Search, `act` 0/3: a real Jev grounding miss**, not a design flaw in `act` itself. Asked to
  click "the first article title in the list of search results", Jev picked Wikipedia's red
  *create this page* link above the results, three times. The step reports the link as
  `(page does not exist)`, so a caller that reads the step would notice and correct it in one
  more turn — the harness scores it as a miss because it doesn't correct.
- **`task`'s misses are the step model.** GLM 5.3 Flash garbled the URL it had to open
  (`http bin .org/co okies`), answered from an invented host, cut its own JSON off at the
  4,096-token limit, and on the SPA tried to reach into a shadow root that does not exist,
  running out of steps or time. A stronger `BB_BROWSERUSE_MODEL` may do better — that was not
  measured here.
- **The first dry run found four Jev defects, fixed before these rounds** (jev-automation
  `feat/steel-cdp`): a tick-box click or a second identical list row counted as "no change" and
  stopped the sequence as stuck; quoted text was typed lowercase ("test user"); unlabelled row
  checkboxes were one deduplicated element; custom-drawn (opacity 0) checkboxes were not listed
  at all.
- **Jev's own decision time**, measured separately through `act` on real pages (Hacker News,
  python.org, Wikipedia, example.com): 209–424 ms (median ~300 ms, n=20; one 8.8 s outlier). A
  whole click step, gateway to page settled, took 1.2–2.5 s, up to ~11 s when the page itself
  was slow — page load and settling dominate, not the decision. `act` reports each step's
  `decided_by` and `decision_ms` so this stays checkable.
- **What Browser-Use costs**, measured outside this benchmark on simpler jobs: example.com's
  heading (2 steps, 9.7 s, $0.0011), Hacker News top story and points (2 steps, 13.3 s,
  $0.0021), Hacker News top story's comment count from its comments page (3 steps, 31.4 s,
  $0.0056), Hacker News first top-level comment (3 steps, 24.8 s, $0.0053). Cost is the model's
  tokens at OpenRouter's list price, an upper bound since prompt-cache discounts are not
  applied.
