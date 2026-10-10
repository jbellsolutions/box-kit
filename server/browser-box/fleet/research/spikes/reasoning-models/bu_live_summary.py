"""Summarize live Browser-Use runs (run_bu_live.sh output dirs).
Correct = final answer contains the ground truth (quotes page 3 first author: "Pablo Neruda";
dynamic_loading/2 text: "Hello World!"), task marked done.
Usage: python bu_live_summary.py <bu_live_dir>
"""
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
TRUTH = {"q": "Pablo Neruda", "d": "Hello World!"}
rows = []
for d in sorted(root.iterdir()):
    if not (d / "bu_summary.json").exists():
        continue
    s = json.loads((d / "bu_summary.json").read_text())
    calls = [json.loads(l) for l in (d / "bu_calls.jsonl").open()] if (d / "bu_calls.jsonl").exists() else []
    model, task, run = d.name.split("_")
    final = s.get("final") or ""
    rows.append({"run": d.name, "model": s["model"], "task": task, "correct": bool(s.get("done")) and TRUTH[task] in final,
                 "steps": s["steps"], "wall_s": s["wall_s"], "llm_calls": len(calls),
                 "llm_s": round(sum(c.get("latency_s") or 0 for c in calls), 1),
                 "cost": round(sum(float(c.get("cost") or 0) for c in calls), 5),
                 "lengths": sum(c.get("finish_reason") == "length" for c in calls),
                 "http_err": sum(c.get("status") != 200 for c in calls),
                 "providers": sorted({c.get("provider") or "?" for c in calls}), "final": final[:120].replace("\n", " ")})
print("| run | model | task | correct | steps | LLM calls | LLM s | wall s | $ | length | providers | final answer (start) |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['run']} | {r['model']} | {r['task']} | {r['correct']} | {r['steps']} | {r['llm_calls']} | {r['llm_s']} | {r['wall_s']} | "
          f"{r['cost']} | {r['lengths']} | {', '.join(r['providers'])} | {r['final']} |")
print()
for m in sorted({r["model"] for r in rows}):
    rs = [r for r in rows if r["model"] == m]
    print(f"- {m}: {sum(r['correct'] for r in rs)}/{len(rs)} correct, median steps {statistics.median(r['steps'] for r in rs)}, "
          f"median LLM time {statistics.median(r['llm_s'] for r in rs)} s, median wall {statistics.median(r['wall_s'] for r in rs)} s, "
          f"total ${sum(r['cost'] for r in rs):.4f}")
