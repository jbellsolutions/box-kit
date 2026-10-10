"""Summarize bench.py JSONL output into markdown tables.
Usage: python summarize.py <results.jsonl> [more.jsonl ...]
"""
import json
import statistics
import sys
from collections import Counter, defaultdict

rows = [json.loads(l) for f in sys.argv[1:] for l in open(f) if l.strip()]

# Strict execution check (post-hoc): Stagehand's clickElement passes arguments[0] straight to CDP
# as the mouse button (actHandlerUtils.ts: button: args[0] || undefined), so a click whose first
# argument is anything other than empty/"left" would fail or mis-click when executed.
OK_BUTTON = ("", "left")
for r in rows:
    if not r.get("valid") or r.get("score", 0) < 1 or not r["task"].startswith(("sh_act", "sh_observe")):
        continue
    try:
        obj = json.loads(r["content"])
    except Exception:
        continue
    acts = obj.get("elements") if "elements" in obj else [obj.get("action")]
    for a in acts or []:
        if a and a.get("method") == "click" and a.get("arguments") and a["arguments"][0] not in OK_BUTTON:
            r["score"] = 0.0
            r["note"] = f"junk click args {a['arguments'][:4]}"
            r["strict_fail"] = True
# Execution semantics: select/fill/type use only arguments[0]; re-score runs judged by the older
# exact-array rule.
for r in rows:
    if r["task"] in ("sh_act_dropdown", "sh_act_type") and r.get("valid") and r.get("score", 0) < 1:
        try:
            a = json.loads(r["content"])["action"]
        except Exception:
            continue
        if not a:
            continue
        if r["task"] == "sh_act_dropdown":
            ok = a["elementId"] == "0-77" and a["method"] == "selectOptionFromDropdown" and a["arguments"][:1] == ["Option 2"]
        else:
            ok = a["elementId"] == "0-218" and a["method"] in ("fill", "type") and a["arguments"][:1] == ["42"]
        if ok:
            r["score"], r["note"] = 1.0, (r.get("note") or "") + " (args[0] ok)"
by_conf = defaultdict(list)
for r in rows:
    by_conf[r["config"]].append(r)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


TASKS = []
for r in rows:
    if r["task"] not in TASKS:
        TASKS.append(r["task"])

print("| config | calls | HTTP/API errors | schema-valid | truncated (length) | correct (all tasks) | act+observe correct | extract mean | BU step | p50 s | p90 s | mean $/call | sum $ | providers |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for conf, rs in by_conf.items():
    n = len(rs)
    errs = sum(1 for r in rs if r.get("status") != 200)
    ok = [r for r in rs if r.get("status") == 200]
    valid = sum(1 for r in rs if r.get("valid"))
    trunc = sum(1 for r in rs if r.get("finish_reason") == "length")
    correct = sum(r.get("score", 0) for r in rs)
    ao = [r for r in rs if r["task"].startswith(("sh_act", "sh_observe"))]
    ex = [r for r in rs if r["task"].startswith("sh_extract")]
    bu = [r for r in rs if r["task"].startswith("bu_")]
    lat = [r["latency_s"] for r in ok if r.get("latency_s") is not None]
    costs = [float(r.get("cost") or 0) for r in ok]
    prov = Counter(r.get("provider") for r in ok)
    fmt = lambda xs: f"{sum(x.get('score', 0) for x in xs):.1f}/{len(xs)}" if xs else "-"
    print(f"| {conf} | {n} | {errs} | {valid}/{n} | {trunc} | {correct:.1f}/{n} | {fmt(ao)} | "
          f"{(sum(r.get('score', 0) for r in ex) / len(ex)) if ex else 0:.2f} | {fmt(bu)} | "
          f"{pct(lat, .5) if lat else '-':.2f} | {pct(lat, .9) if lat else 0:.2f} | "
          f"{(sum(costs) / len(costs)) if costs else 0:.5f} | {sum(costs):.4f} | "
          f"{', '.join(f'{k}:{v}' for k, v in prov.most_common(4))} |")

print()
print("Per task: correct/runs (p50 latency s)")
print("| config | " + " | ".join(TASKS) + " |")
print("|---|" + "---|" * len(TASKS))
for conf, rs in by_conf.items():
    cells = []
    for t in TASKS:
        tr = [r for r in rs if r["task"] == t]
        if not tr:
            cells.append("-")
            continue
        lat = [r["latency_s"] for r in tr if r.get("status") == 200 and r.get("latency_s") is not None]
        cells.append(f"{sum(r.get('score', 0) for r in tr):.2g}/{len(tr)} ({statistics.median(lat):.1f})" if lat else f"0/{len(tr)} (err)")
    print(f"| {conf} | " + " | ".join(cells) + " |")

print()
print("Failures (invalid, truncated, wrong, or errors):")
for r in rows:
    if r.get("score", 0) < 1:
        print(f"- {r['config']} {r['task']} r{r['run']}: status={r.get('status')} prov={r.get('provider')} "
              f"finish={r.get('finish_reason')} valid={r.get('valid')} parse={r.get('parse')} "
              f"note={str(r.get('note') or '')[:120]} err={str(r.get('schema_error') or r.get('error') or r.get('http_error') or '')[:160]}")
print()
print(f"total calls {len(rows)}, total usage.cost ${sum(float(r.get('cost') or 0) for r in rows):.4f}")
