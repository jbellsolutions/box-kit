"""Stagehand Python 4.2.0 zero-LLM attach to Steel (TS-mounted extension), snapshot -> act(Action)."""
import asyncio, json, re, resource, time, urllib.request
from stagehand import Stagehand, local_browser

STEEL = "http://127.0.0.1:3301"
calls = 0

async def no_llm(params):
    global calls
    calls += 1
    raise RuntimeError("no LLM allowed")

async def main():
    out = {}
    req = urllib.request.Request(f"{STEEL}/v1/sessions", data=b'{"extensions":["stagehand"]}',
                                 headers={"content-type": "application/json"}, method="POST")
    urllib.request.urlopen(req).read()
    t = time.perf_counter()
    browser = await local_browser.connect(cdp_url="ws://127.0.0.1:3301/")
    sh = await Stagehand.create(browser=browser, model=no_llm, self_heal=False)
    out["attach_ms"] = round((time.perf_counter() - t) * 1000)
    page = await browser.context.active_page()
    await page.goto("https://quotes.toscrape.com/")
    snap = await page.snapshot()
    line = next(l for l in snap.formatted_tree.splitlines() if re.search(r"\]\s+link: Next", l))
    eid = re.search(r"\[(\d+-\d+)\]", line).group(1)
    t = time.perf_counter()
    res = await sh.act({"selector": "xpath=" + snap.xpath_map[eid], "description": "Next", "method": "click", "arguments": []})
    out.update(act_ms=round((time.perf_counter() - t) * 1000), success=res.data.success, url=await page.url(),
               picked=line.strip(), llm_calls=calls,
               usage=res.metadata.usage.model_dump() if hasattr(res.metadata.usage, "model_dump") else str(res.metadata.usage),
               max_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576))
    await sh.close()
    print(json.dumps(out, indent=2, default=str))

asyncio.run(main())
