"""Two attacks on the in-browser guard, run by make smoke; exits 1 on a leak.

1. The one that got past per-tab interception: a tab created with its URL already given.
   Target.createTarget starts that tab's first request before any client can intercept the
   tab, so a guard that attaches tab by tab sees neither it nor the redirect riding it. Any CDP
   client in the box (Jev, Browser-Use) can open a tab this way.
2. A cross-site iframe that redirects inward. This one only asserts that nothing leaked:
   Chromium's Local Network Access also stops a public page's frame from navigating to
   loopback, so it cannot say which layer refused. That the guard itself sees frames was
   checked separately (a browser-level interceptor paused both cross-site iframe documents
   and the redirect hop, and the guard logged the refusal).
"""
import asyncio
import json
import os
import sys

from websockets.asyncio.client import connect

CDP = os.getenv("BB_STEEL_CDP", "ws://127.0.0.1:3000/")
REDIRECT = "https://httpbin.org/redirect-to?url=http%3A%2F%2F127.0.0.1%3A3000%2Fv1%2Fsessions"


async def main() -> int:
    async with connect(CDP, max_size=None, open_timeout=10) as ws:
        ids = iter(range(1, 10_000))

        async def call(method, params=None, session=None):
            mid = next(ids)
            msg = {"id": mid, "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
            await ws.send(json.dumps(msg))
            while True:
                reply = json.loads(await asyncio.wait_for(ws.recv(), 20))
                if reply.get("id") == mid:
                    if "error" in reply:
                        raise RuntimeError(f"{method}: {reply['error']}")
                    return reply["result"]

        target = (await call("Target.createTarget", {"url": REDIRECT}))["targetId"]
        try:
            await asyncio.sleep(5)
            session = (await call("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
            got = await call("Runtime.evaluate", {"returnByValue": True, "expression":
                             "location.href + ' ' + (document.body ? document.body.innerText.slice(0, 200) : '')"}, session)
            tab = got["result"].get("value", "")
            await call("Page.navigate", {"url": "https://example.com/"}, session)
            await asyncio.sleep(3)
            await call("Runtime.evaluate", {"expression": f"const f = document.createElement('iframe'); f.src = {json.dumps(REDIRECT)}; "
                                            "document.body.appendChild(f); 1"}, session)
            await asyncio.sleep(5)
            tree = await call("Page.getFrameTree", {}, session)
            frames = [c["frame"] for c in tree["frameTree"].get("childFrames", [])]
        finally:
            await call("Target.closeTarget", {"targetId": target})
    leaked = 0
    if '"sessions"' in tab or "websocketUrl" in tab:
        print("FAILED: a new tab followed a redirect into Steel's own API:", tab[:160], file=sys.stderr)
        leaked = 1
    elif "ERR_BLOCKED_BY_CLIENT" in tab:
        print("new tab, redirect already in flight: refused inside the browser")
    else:
        print("WARNING: the tab landed somewhere unexpected (httpbin down?) — this check proved nothing:", tab[:120])
    if any(f.get("url", "").startswith("http://127.0.0.1") for f in frames):
        print("FAILED: an iframe followed a redirect into Steel's own API:", frames, file=sys.stderr)
        leaked = 1
    elif any("127.0.0.1" in f.get("unreachableUrl", "") for f in frames):
        print("iframe redirected inward: refused inside the browser")
    else:
        print("WARNING: the iframe did not redirect (httpbin down?) — this check proved nothing:", frames)
    return leaked


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
