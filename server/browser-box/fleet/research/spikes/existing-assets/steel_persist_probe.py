"""Probe: does self-hosted Steel (OSS) keep a browser profile, and where?

Usage: python steel_persist_probe.py <phase> [port]
  phase = write   -> create persist session (with custom userDataDir + Cloud-style fields), set a
                     persistent cookie for example.com via CDP, release (flushes profile to disk)
  phase = read    -> create persist session, report whether the cookie is there, release
  phase = readnp  -> create a NON-persist session, report whether the cookie is there, release
No secrets, no logins, public test domain only (example.com cookie set locally via CDP).
"""
import asyncio, json, sys, time
import httpx
from websockets.asyncio.client import connect

PHASE = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3901
BASE = f"http://127.0.0.1:{PORT}/v1"
CDP = f"ws://127.0.0.1:{PORT}/"


async def cdp(*calls):
    out = []
    async with connect(CDP, max_size=None, open_timeout=20) as ws:
        for mid, (method, params) in enumerate(calls, 1):
            await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
                if msg.get("id") == mid:
                    out.append(msg.get("result", msg.get("error")))
                    break
    return out


def create(body):
    r = httpx.post(f"{BASE}/sessions", json=body, timeout=90)
    print("create", r.status_code, json.dumps({k: r.json().get(k) for k in ("id", "status")} if r.is_success else r.text[:300]))
    return r


def release():
    r = httpx.post(f"{BASE}/sessions/release", json={}, timeout=60)
    print("release", r.status_code)


async def main():
    if PHASE == "write":
        create({"persist": True, "userDataDir": "/tmp/custom-profile-x", "persistProfile": True, "profileId": "fleet-probe"})
        time.sleep(2)
        res = await cdp(("Storage.setCookies", {"cookies": [{"name": "fleetprobe", "value": "v1", "domain": "example.com",
                        "path": "/", "expires": time.time() + 86400 * 30}]}),
                        ("Target.createTarget", {"url": "https://example.com/"}))
        print("setCookies", res[0])
        time.sleep(5)
        release()
    elif PHASE in ("read", "readnp"):
        create({"persist": True} if PHASE == "read" else {})
        time.sleep(2)
        [res] = await cdp(("Storage.getCookies", {}))
        names = sorted({c["name"] for c in res.get("cookies", []) if "example.com" in c.get("domain", "")})
        print("example.com cookies:", names, "-> fleetprobe present:", "fleetprobe" in names)
        release()

asyncio.run(main())
