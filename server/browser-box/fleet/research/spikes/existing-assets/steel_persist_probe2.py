"""Probe 2: same as steel_persist_probe.py 'write', but read the cookie back before release and
wait FLUSH seconds so Chromium's periodic cookie-store flush can run before Steel releases.
Usage: python steel_persist_probe2.py <port> <flush_seconds>"""
import asyncio, json, sys, time
import httpx
from websockets.asyncio.client import connect

PORT, FLUSH = int(sys.argv[1]), float(sys.argv[2])
BASE, CDP = f"http://127.0.0.1:{PORT}/v1", f"ws://127.0.0.1:{PORT}/"


async def main():
    r = httpx.post(f"{BASE}/sessions", json={"persist": True}, timeout=90)
    print("create", r.status_code, r.json().get("id"))
    time.sleep(2)
    async with connect(CDP, max_size=None, open_timeout=20) as ws:
        n = 0
        async def call(method, params=None, session=None):
            nonlocal n
            n += 1
            msg = {"id": n, "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
            await ws.send(json.dumps(msg))
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 30))
                if m.get("id") == n:
                    return m.get("result", m.get("error"))
        t = await call("Target.createTarget", {"url": "https://example.com/"})
        s = await call("Target.attachToTarget", {"targetId": t["targetId"], "flatten": True})
        await asyncio.sleep(4)
        ev = await call("Runtime.evaluate", {"expression": "document.cookie='fleetprobe2=v2; max-age=2592000; path=/'; document.cookie"}, s["sessionId"])
        print("page document.cookie ->", ev.get("result", {}).get("value"))
        await call("Storage.setCookies", {"cookies": [{"name": "fleetprobe", "value": "v1", "domain": "example.com", "path": "/", "expires": time.time() + 86400 * 30}]})
        got = await call("Storage.getCookies")
        print("readback before release:", sorted(c["name"] for c in got.get("cookies", []) if "example.com" in c["domain"]))
    print(f"waiting {FLUSH}s for cookie flush")
    time.sleep(FLUSH)
    print("release", httpx.post(f"{BASE}/sessions/release", json={}, timeout=60).status_code)

asyncio.run(main())
