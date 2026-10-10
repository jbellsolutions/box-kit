"""Offline spike: capture the exact HTTP requests the Browserbase Python SDK and
Stagehand's Browserbase launcher would send, using an httpx MockTransport.

No network, no API key (a dummy string is used), no spend.
Run with: <venv>/bin/python -I offline_request_shapes.py
"""
import asyncio
import inspect
import json

import httpx

captured = []


def handler(request: httpx.Request) -> httpx.Response:
    body = request.content.decode() if request.content else ""
    captured.append({"method": request.method, "path": request.url.path, "body": body[:2000]})
    path = request.url.path
    if path.endswith("/v1/sessions") and request.method == "POST":
        return httpx.Response(201, json={
            "id": "sess_dummy", "connectUrl": "wss://connect.example.invalid/?x=1",
            "seleniumRemoteUrl": "http://x.invalid", "signingKey": "k",
            "createdAt": "2026-10-09T00:00:00Z", "expiresAt": "2026-10-09T01:00:00Z",
            "keepAlive": True, "projectId": "p", "proxyBytes": 0, "region": "us-east-1",
            "startedAt": "2026-10-09T00:00:00Z", "status": "RUNNING", "updatedAt": "2026-10-09T00:00:00Z"})
    if path.endswith("/v1/extensions") and request.method == "POST":
        return httpx.Response(200, json={"id": "ext_dummy", "createdAt": "x", "fileName": "f.zip",
                                         "projectId": "p", "updatedAt": "x"})
    return httpx.Response(200, json={})


def sdk_requests():
    from browserbase import Browserbase
    import importlib.metadata as md
    print("browserbase SDK", md.version("browserbase"))
    bb = Browserbase(api_key="dummy-not-a-key", base_url="https://bb.example.invalid",
                     http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    bb.sessions.create(
        project_id="proj_dummy",
        region="us-east-1",
        keep_alive=True,
        api_timeout=3600,
        proxies=[{"type": "external", "server": "http://proxy.example.invalid:8000",
                  "username": "u", "password": "p"}],
        browser_settings={"context": {"id": "ctx_dummy", "persist": True},
                          "solve_captchas": True, "record_session": True,
                          # not in the SDK's TypedDict; does the SDK pass it through?
                          "fingerprint": {"operatingSystems": ["windows"]}},
        user_metadata={"profile_id": "p-0001", "owner": "fleet"},
    )
    print("create() params:", list(inspect.signature(bb.sessions.create).parameters))


async def stagehand_requests():
    import importlib.metadata as md
    from stagehand import BrowserbaseBrowserSettings
    from stagehand import browserbase as sh_bb
    print("stagehand", md.version("stagehand"))
    print("stagehand browserbase.launch params:", list(inspect.signature(sh_bb.launch).parameters))
    print("stagehand browserbase.connect params:", list(inspect.signature(sh_bb.connect).parameters))
    fields = getattr(BrowserbaseBrowserSettings, "model_fields", None) or getattr(BrowserbaseBrowserSettings, "__annotations__", {})
    print("BrowserbaseBrowserSettings:", BrowserbaseBrowserSettings.__module__, sorted(fields))


def browser_use_shapes():
    import importlib.metadata as md
    from browser_use import Browser, BrowserProfile, BrowserSession
    print("browser-use", md.version("browser-use"), "Browser is BrowserSession:", Browser is BrowserSession)
    p = BrowserProfile(cdp_url="wss://connect.example.invalid/?signingKey=x", keep_alive=False)
    print("BrowserProfile.cdp_url set:", bool(p.cdp_url), "is_local:", p.is_local)
    b = Browser(cdp_url="wss://connect.example.invalid/?signingKey=x")
    print("Browser(cdp_url=...) is_local:", b.is_local)


if __name__ == "__main__":
    sdk_requests()
    asyncio.run(stagehand_requests())
    browser_use_shapes()
    print(json.dumps(captured, indent=1))
