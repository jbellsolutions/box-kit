"""Just enough Chrome DevTools Protocol over one websocket for a hosted browser: numbered calls,
awaited events, and one page opened, read and optionally photographed.

The hosted engines (Browser Use, Browserbase) hand back a CDP websocket; everything the box does
with a page goes through here. Errors come back as ``CdpError`` and never carry a URL with a token.
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import json
from typing import Any

CALL_WAIT = 30.0
LOAD_WAIT = 30.0

PAGE_JS = ("JSON.stringify({url: location.href, title: document.title, "
           "text: document.body ? document.body.innerText : '', "
           "links: Array.from(document.links, a => a.href).filter(h => /^https?:/.test(h)).slice(0, 50)})")


class CdpError(RuntimeError):
    """The browser refused a call or the connection dropped."""


class Cdp:
    def __init__(self, ws: Any):
        self.ws = ws
        self.ids = itertools.count(1)
        self.waiting: dict[int, asyncio.Future] = {}
        self.events: list[tuple[str, str | None, asyncio.Future]] = []
        self.listeners: list[Any] = []
        self.reader = asyncio.ensure_future(self._read())

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self.waiting:
                    self.waiting.pop(msg["id"]).set_result(msg)
                elif "method" in msg:
                    for listener in self.listeners:
                        listener(msg)
                    for name, sid, fut in list(self.events):
                        if name == msg["method"] and sid == msg.get("sessionId") and not fut.done():
                            fut.set_result(msg.get("params", {}))
        finally:
            for fut in self.waiting.values():
                if not fut.done():
                    fut.set_exception(CdpError("the browser connection closed"))

    def expect(self, method: str, session: str | None) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self.events.append((method, session, fut))
        return fut

    async def send(self, method: str, params: dict | None = None, *, session: str | None = None,
                   wait: float = CALL_WAIT) -> dict:
        call_id = next(self.ids)
        fut = asyncio.get_running_loop().create_future()
        self.waiting[call_id] = fut
        msg: dict[str, Any] = {"id": call_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        try:
            await self.ws.send(json.dumps(msg))
            reply = await asyncio.wait_for(fut, wait)
        finally:
            self.waiting.pop(call_id, None)
        if "error" in reply:
            raise CdpError(f"the browser refused {method}: {str(reply['error'].get('message', ''))[:200]}")
        return reply.get("result", {})

    def close(self) -> None:
        self.reader.cancel()

    async def page(self) -> str:
        """Attach to the browser's first tab (opening one if there is none); returns the CDP session id."""
        targets = (await self.send("Target.getTargets"))["targetInfos"]
        pages = [t for t in targets if t.get("type") == "page"]
        target = pages[0]["targetId"] if pages else (await self.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
        return (await self.send("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]

    async def open_and_read(self, url: str, *, delay_ms: int = 0, screenshot: bool = False,
                            session: str | None = None) -> dict:
        """Navigate a tab (the first one unless ``session`` names another), wait for load, read text and links.
        The screenshot is taken of the page already loaded, never by a second navigation, so it shows exactly
        what was read."""
        sid = session or await self.page()
        await self.send("Page.enable", session=sid)
        await self.send("Network.enable", session=sid)
        status: dict[str, Any] = {}

        def main_response(msg: dict) -> None:
            params = msg.get("params", {})
            if (msg.get("method") == "Network.responseReceived" and msg.get("sessionId") == sid
                    and params.get("type") == "Document" and "code" not in status):
                status["code"] = (params.get("response") or {}).get("status")

        self.listeners.append(main_response)
        loaded = self.expect("Page.loadEventFired", sid)
        nav = await self.send("Page.navigate", {"url": url}, session=sid)
        if nav.get("errorText"):
            raise CdpError(f"the page did not open: {nav['errorText']}")
        try:
            await asyncio.wait_for(loaded, LOAD_WAIT)
        except asyncio.TimeoutError:
            pass  # read what rendered; a slow subresource should not lose the page
        if delay_ms:
            await asyncio.sleep(min(delay_ms, 15000) / 1000)
        out = await self.send("Runtime.evaluate", {"expression": PAGE_JS, "returnByValue": True}, session=sid)
        page = json.loads(out["result"]["value"])
        page["status_code"] = status.get("code")
        if screenshot:
            shot = await self.send("Page.captureScreenshot", {"format": "jpeg", "quality": 70,
                                                              "captureBeyondViewport": True}, session=sid, wait=LOAD_WAIT)
            page["screenshot"] = base64.b64decode(shot.get("data") or "")
        return page
