"""Uncached (list-price) cost per call, next to the measured OpenRouter usage.cost.

Measured cost includes provider prompt-cache discounts on repeated identical prompts (the bench
replays the same tree 3-5x). In production Stagehand puts the instruction before the tree, so
most act/observe/extract calls are uncached. Uncached = prompt_tokens * endpoint prompt price +
completion_tokens * endpoint completion price, for the provider that served the call (if a provider
has several endpoints, the cheapest is used; image surcharges ignored).

Usage: python costs.py <endpoints_dir> <glm_endpoints.json> <results.jsonl> [...]
"""
import glob
import json
import statistics
import sys
from collections import defaultdict

ep_dir, glm_ep, files = sys.argv[1], sys.argv[2], sys.argv[3:]
prices = defaultdict(dict)  # model -> provider -> (p, c)
for f in glob.glob(f"{ep_dir}/*.json") + [glm_ep]:
    d = json.load(open(f))["data"]
    for e in d["endpoints"]:
        p, c = float(e["pricing"]["prompt"]), float(e["pricing"]["completion"])
        cur = prices[d["id"]].get(e["provider_name"])
        if cur is None or p + c < cur[0] + cur[1]:
            prices[d["id"]][e["provider_name"]] = (p, c)

rows = [json.loads(l) for f in files for l in open(f) if l.strip()]
agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    if r.get("status") != 200 or r.get("prompt_tokens") is None:
        continue
    pc = prices.get(r["model"], {}).get(r.get("provider"))
    if not pc:
        continue
    unc = r["prompt_tokens"] * pc[0] + (r.get("completion_tokens") or 0) * pc[1]
    a = agg[r["config"]]
    a["measured"].append(float(r.get("cost") or 0))
    a["uncached"].append(unc)
    a["cached_share"].append((r.get("cached_tokens") or 0) / max(r["prompt_tokens"], 1))
    a[f"unc_{r['task']}"].append(unc)

tasks = sorted({k[4:] for a in agg.values() for k in a if k.startswith("unc_")})
print("| config | calls | mean measured $ | mean uncached list $ | cached prompt share | " + " | ".join(f"uncached $ {t}" for t in tasks) + " |")
print("|---|---|---|---|---|" + "---|" * len(tasks))
for conf, a in agg.items():
    cells = [f"{statistics.mean(a['unc_' + t]):.5f}" if a.get("unc_" + t) else "-" for t in tasks]
    print(f"| {conf} | {len(a['measured'])} | {statistics.mean(a['measured']):.5f} | {statistics.mean(a['uncached']):.5f} | "
          f"{statistics.mean(a['cached_share']):.0%} | " + " | ".join(cells) + " |")
