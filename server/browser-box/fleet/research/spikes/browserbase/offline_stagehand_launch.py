"""Offline spike: what does Stagehand 4.2.0 `browserbase.launch()` send to the Browserbase API?
Mocked HTTP (httpx.MockTransport), dummy key, no network, no spend. The CDP connect step is
expected to fail against the dummy wss URL; we only want the captured API requests.
"""
import asyncio
import json

import httpx

captured = []


def handler(request: httpx.Request) -> httpx.Response:
    ctype = request.headers.get("content-type", "")
    body = request.content.decode(errors="replace") if request.content else ""
    if "multipart" in ctype:
        body = f"<multipart {len(request.content)} bytes>"
    captured.append({"method": request.method, "path": request.url.path, "body": body[:1500]})
    if request.url.path.endswith("/v1/extensions"):
        return httpx.Response(200, json={"id": "ext_dummy", "createdAt": "x", "fileName": "stagehand-extension.zip",
                                         "projectId": "p", "updatedAt": "x"})
    if request.url.path.endswith("/v1/sessions") and request.method == "POST":
        return httpx.Response(201, json={
            "id": "sess_dummy", "connectUrl": "ws://127.0.0.1:9/devtools/browser/dummy",
            "seleniumRemoteUrl": "http://x.invalid", "signingKey": "k",
            "createdAt": "x", "expiresAt": "x", "keepAlive": False, "projectId": "p",
            "proxyBytes": 0, "region": "us-west-2", "startedAt": "x", "status": "RUNNING", "updatedAt": "x"})
    return httpx.Response(200, json={})


async def main():
    from stagehand import BrowserbaseBrowserSettings
    from stagehand import browserbase as sh_bb
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        await asyncio.wait_for(sh_bb.launch(
            api_key="dummy-not-a-key",
            base_url="https://bb.example.invalid",
            client_options={"http_client": client, "max_retries": 0},
            region="us-east-1",
            timeout=1800,
            keep_alive=False,
            proxies=True,
            # 4.2.0 exports BrowserbaseBrowserSettings as a TypedDict: the docs' .model_validate() fails,
            # so pass a plain dict (BrowserbaseBrowserSettings(context=...) also works).
            browser_settings=BrowserbaseBrowserSettings(context={"id": "ctx_dummy", "persist": True}),
            user_metadata={"profile_id": "p-0001"},
        ), timeout=20)
    except Exception as e:  # expected: CDP connect to dummy URL fails
        print("launch ended with (expected):", type(e).__name__, str(e)[:200])
    print(json.dumps(captured, indent=1))


asyncio.run(main())
