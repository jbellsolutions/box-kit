"""Estimate only. List prices fetched 2026-10-09 (see dossier sources). 30-day month, 1 GB = 1,000 MB.
Browserbase: docs.browserbase.com/account/billing/plans (official-docs) == browserbase.com/pricing (vendor-claim).
Steel Cloud: steel.dev/pricing.md + docs.steel.dev/overview/pricinglimits (vendor-claim / official-docs).
"""
DAYS = 30
MB_PER_HOUR = 50

BB = {  # name: (base, incl_hours, hour_overage, incl_gb, gb_overage, concurrency)
    "Developer": (20, 100, 0.12, 1, 12, 25),
    "Startup": (99, 500, 0.10, 5, 10, 100),
}
STEEL_SCALE = dict(base=250, credit=100, hour=0.08, gb=6, ip=5, concurrency=100)


def bb_cost(plan, hours, gb, bb_proxy=True):
    base, ih, ho, ig, go, _ = BB[plan]
    c = base + max(0, hours - ih) * ho
    if bb_proxy:
        c += max(0, gb - ig) * go
    return c


def steel_scale(hours, gb, n_ips):
    s = STEEL_SCALE
    usage = hours * s["hour"] + gb * s["gb"]
    return s["base"] + max(0, usage - s["credit"]) + n_ips * s["ip"]


print("| Profiles x h/day | Browser-h/mo | Proxy GB/mo | Avg conc (24h) | Peak conc (12h window) | BB Developer, BB proxy | BB Startup, BB proxy | BB Startup, browser only (BYO proxy, proxy cost excluded) | Steel Cloud Scale, Steel proxy + $5 dedicated IP/profile | Steel Cloud Scale, no dedicated IPs |")
print("|" + " - |" * 10)
for n in (30, 100, 1000):
    for h in (1, 3):
        hours = n * h * DAYS
        gb = hours * MB_PER_HOUR / 1000
        avg = n * h / 24
        peak = n * h / 12
        dev = bb_cost("Developer", hours, gb)
        st = bb_cost("Startup", hours, gb)
        st_b = bb_cost("Startup", hours, gb, bb_proxy=False)
        ss_ip = steel_scale(hours, gb, n)
        ss = steel_scale(hours, gb, 0)
        print(f"| {n} x {h} | {hours:,} | {gb:,.0f} | {avg:.1f} | {peak:.1f} | ${dev:,.0f} | ${st:,.0f} (${st/n:,.2f}/profile) | ${st_b:,.0f} | ${ss_ip:,.0f} | ${ss:,.0f} |")
