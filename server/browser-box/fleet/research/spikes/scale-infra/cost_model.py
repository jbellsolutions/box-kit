#!/usr/bin/env python3
"""Fleet cost model: 30 / 100 / 1,000 profiles at 1 and 3 active browser-hours per profile per day.

Every input below is labeled with where it came from. Change a number, rerun, and the tables follow.
No network, no keys. Output is markdown on stdout.

  python3 -I cost_model.py
"""
from math import ceil

# ---------------------------------------------------------------- inputs (provenance in comments)
DAYS = 30
ACTIVE_WINDOW_H = 16      # ESTIMATE: work is spread over a 16 h day across client time zones
PEAK_FACTOR = 2.0         # ESTIMATE: peak hour concurrency vs the window average

# Per active slot (one browser + its agent runtime) on a self-hosted node
BROWSER_GIB = 1.5         # ESTIMATE for social sites. Measured 0.65-0.85 GiB on light test pages
                          # (hands-on, this spike); 1.08-1.36 GiB on HN / agent tasks (browser-box README, 2026-09-23)
AGENT_GIB = 0.35          # browser-box README: agent-browseruse 327 MiB peak, agent-jev 134 MiB (measured)
SLOT_VCPU = 0.6           # ESTIMATE: spike averaged 0.3-0.55 cores per browser while loading pages back to back
NODE = dict(slug="s-8vcpu-16gb", vcpu=8, gib=16, usd_mo=96.0, usd_hr=0.14286)  # DO /v2/sizes, 2026-10-10
NODE_RESERVE_GIB = 2.0    # OS, Docker, node agent, guard
UTIL = 0.7                # ESTIMATE: average slot utilization when autoscaling

# Always-on control plane (fleet API + scheduler + lease table + Temporal + Postgres + Spaces)
CONTROL = {
    30:   [("s-4vcpu-8gb control (API, scheduler, Temporal, self-hosted Postgres)", 48.0), ("Spaces base", 5.0)],
    100:  [("s-4vcpu-8gb control", 48.0), ("Managed Postgres 2 GiB", 30.45), ("Spaces base", 5.0)],
    1000: [("2x s-4vcpu-8gb control", 96.0), ("s-4vcpu-8gb Temporal", 48.0),
           ("Managed Postgres 4 GiB + 1 standby (standby price unlisted; assumed equal)", 121.80),
           ("Spaces base", 5.0), ("Load balancer", 12.0)],
}
# Agent-runtime workers when the BROWSER is in a vendor cloud (Stagehand/Browser-Use still run on our side)
WORKER = dict(slug="s-4vcpu-8gb", gib=8, usd_mo=48.0)

# Static ISP proxy, one dedicated IP per profile (vendor-claim pricing pages, 2026-10-10)
PROXY_USD_IP = {30: 3.00, 100: 2.75, 1000: 2.50}  # Bright Data dedicated ISP $3.5@10, $2.75@100, $2.5@1000 (tab mapping inferred);
                                                  # IPRoyal ISP $2.70/30-day, $2.40/90-day term

# Model calls (OpenRouter /api/v1/models 2026-10-10; TypeSafe price via system1-models spike)
GLM_IN, GLM_OUT = 0.15 / 1e6, 0.50 / 1e6          # z-ai/glm-5.3-flash $/token
JEV_IN = 0.042 / 1e6                               # jev-1.13.0 input; output free
COST = {
    "system1": 1000 * JEV_IN,                      # ~1,000 input tokens per multi-question decision (hands-on)
    "cached": 0.0,                                 # Stagehand cache hit / deterministic replay
    "llm_act": 8000 * GLM_IN + 80 * GLM_OUT,       # Stagehand act/observe/extract: 0.9k-6.4k prompt on test pages
                                                   # (reasoning-models spike main.jsonl); 8k assumed for social DOMs
    "bu_step": 8500 * GLM_IN + 250 * GLM_OUT,      # Browser-Use step: 8.5k prompt, 195-307 completion (same spike)
}
ACTIONS_PER_HOUR = 100    # ESTIMATE: one browser action every ~36 s of active time
MIXES = {
    "A: System-1-first (target)": {"system1": 0.50, "cached": 0.40, "llm_act": 0.08, "bu_step": 0.02},
    "B: LLM-heavy (cold, no cache)": {"system1": 0.30, "cached": 0.00, "llm_act": 0.60, "bu_step": 0.10},
}
PLANNER_PER_TASK = 2 * (8000 * GLM_IN + 500 * GLM_OUT)  # Hermes-side plan + verify per task (ESTIMATE)
TASKS_PER_HOUR = 6        # ESTIMATE

# Vendor clouds (vendor-claim pricing pages in fleet/research/corpus, fetched 2026-10-09)
BB = dict(name="Browserbase Startup", fee=99.0, incl_h=500, rate=0.10, max_conc=100)
BB_SCALE_RATE = 0.10      # Scale plan is custom; list overage rate used as a labeled stand-in
STEEL = dict(name="Steel Cloud Scale", fee=250.0, credit=100.0, rate=0.08, max_conc=100)

# Evidence
SHOT_KB = 200             # ESTIMATE; browser-box measured a 371 KB full-page JPEG (README)
SHOTS_PER_HOUR = 30       # one per side-effecting step and per checkpoint (ESTIMATE)
RETENTION_DAYS = 30
PROFILE_BUNDLE_MB = 50    # ESTIMATE for a social profile, compressed, caches excluded. Spike: 57 KB after 8 test
                          # pages (5.2 MB raw). Steel Cloud caps a profile at 300 MB.
BUNDLE_VERSIONS = 5

# ---------------------------------------------------------------- model
slot_gib = BROWSER_GIB + AGENT_GIB
slots_per_node = int(min((NODE["gib"] - NODE_RESERVE_GIB) // slot_gib, NODE["vcpu"] // SLOT_VCPU))

def row(P, h):
    bh = P * h * DAYS                                   # active browser-hours per month
    conc = ceil(P * h / ACTIVE_WINDOW_H * PEAK_FACTOR)  # peak concurrent browsers
    n_static = ceil(conc / slots_per_node)
    spare = 1 if n_static < 20 else ceil(n_static * 0.05)
    static = (n_static + spare) * NODE["usd_mo"]
    auto = bh / (slots_per_node * UTIL) * NODE["usd_hr"] + NODE["usd_mo"]  # + one always-on node
    control = sum(v for _, v in CONTROL[P])
    proxy = P * PROXY_USD_IP[P]
    models = {k: bh * ACTIONS_PER_HOUR * sum(m[a] * COST[a] for a in m) + bh * TASKS_PER_HOUR * PLANNER_PER_TASK
              for k, m in MIXES.items()}
    # evidence + profile bundles in Spaces beyond the 250 GiB / $5 base
    ev_gib = bh / DAYS * SHOTS_PER_HOUR * SHOT_KB / 1e6 * RETENTION_DAYS
    bundle_gib = P * PROFILE_BUNDLE_MB * BUNDLE_VERSIONS / 1000
    storage_over = max(0.0, ev_gib + bundle_gib - 250) * 0.02
    workers = ceil(conc * AGENT_GIB / (WORKER["gib"] - 2)) * WORKER["usd_mo"]
    bb = BB["fee"] + max(0, bh - BB["incl_h"]) * BB["rate"] if conc <= BB["max_conc"] else bh * BB_SCALE_RATE
    st = STEEL["fee"] + max(0.0, bh * STEEL["rate"] - STEEL["credit"]) if conc <= STEEL["max_conc"] else bh * STEEL["rate"]
    always_on = ceil(P / slots_per_node) * NODE["usd_mo"]
    return dict(P=P, h=h, bh=bh, conc=conc, n_static=n_static + spare, static=static, auto=auto,
                control=control, proxy=proxy, models=models, ev_gib=ev_gib, bundle_gib=bundle_gib,
                storage_over=storage_over, workers=workers, bb=bb, steel=st, always_on=always_on,
                bb_custom=conc > BB["max_conc"], steel_custom=conc > STEEL["max_conc"])

def money(x):
    return f"${x:,.0f}"

print(f"Slot = {slot_gib:.2f} GiB, {SLOT_VCPU} vCPU. Node {NODE['slug']} ({NODE['vcpu']} vCPU / {NODE['gib']} GiB, "
      f"${NODE['usd_mo']:.0f}/mo) holds {slots_per_node} active slots.\n")
print("Per-action model cost: " + ", ".join(f"{k} ${v:.6f}" for k, v in COST.items()))
for k, m in MIXES.items():
    print(f"  mix {k}: ${sum(m[a]*COST[a] for a in m):.6f}/action")
print(f"  planner per task ${PLANNER_PER_TASK:.5f}\n")

rows = [row(P, h) for P in (30, 100, 1000) for h in (1, 3)]
print("| profiles x h/day | browser-h/mo | peak conc. | nodes (static, incl. spare) | self-host nodes static | self-host nodes autoscaled | control plane | proxies | models mix A | models mix B | storage overage |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in rows:
    ma, mb = r["models"].values()
    print(f"| {r['P']} x {r['h']} | {r['bh']:,} | {r['conc']} | {r['n_static']} | {money(r['static'])} | {money(r['auto'])} | "
          f"{money(r['control'])} | {money(r['proxy'])} | {money(ma)} | {money(mb)} | {money(r['storage_over'])} |")

print("\nMonthly totals, model mix A (System-1-first). Proxies, control plane and models are in every column.\n")
print("| profiles x h/day | self-hosted (static) | self-hosted (autoscaled) | Steel Cloud + our workers | Browserbase + our workers | always-on self-hosted (for contrast) |")
print("|---|---:|---:|---:|---:|---:|")
for r in rows:
    ma = list(r["models"].values())[0]
    common = r["control"] + r["proxy"] + ma + r["storage_over"]
    sh_static = r["static"] + common
    sh_auto = min(r["auto"], r["static"]) + common
    steel = r["steel"] + r["workers"] + common
    bb = r["bb"] + r["workers"] + common
    ao = r["always_on"] + common
    tag_s = " (Enterprise, custom)" if r["steel_custom"] else ""
    tag_b = " (Scale, custom)" if r["bb_custom"] else ""
    print(f"| {r['P']} x {r['h']} | {money(sh_static)} | {money(sh_auto)} | {money(steel)}{tag_s} | {money(bb)}{tag_b} | {money(ao)} |")

print("\nVendor browser line items alone (before proxies/models/control):\n")
print("| profiles x h/day | Steel Cloud browser-hours | Browserbase browser-hours | our agent workers (cloud cases) |")
print("|---|---:|---:|---:|")
for r in rows:
    print(f"| {r['P']} x {r['h']} | {money(r['steel'])} | {money(r['bb'])} | {money(r['workers'])} |")

print("\nStorage: evidence GiB retained / profile-bundle GiB:")
for r in rows:
    print(f"  {r['P']} x {r['h']}: evidence {r['ev_gib']:.0f} GiB, bundles {r['bundle_gib']:.0f} GiB")
