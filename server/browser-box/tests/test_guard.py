"""The in-browser guard. Its decisions are tested directly; its socket plumbing against a fake
browser that speaks CDP over a real websocket, including a paused request with a 2 MB URL.
Whether Chromium really pauses what it should is proven against Steel by make guard-check."""
import asyncio
import json
import unittest
from unittest import mock

import httpx
from websockets.asyncio.server import serve

from gateway import guard, steel
from gateway.guard import Guard
from gateway.security import UnsafeUrl


def public(host):
    return ["93.184.216.34"]


class Verdict(unittest.IsolatedAsyncioTestCase):
    async def test_public_web_passes_and_everything_inward_is_refused(self):
        g = Guard("ws://127.0.0.1:1/")
        with mock.patch.object(guard, "require_public_addresses", public):
            self.assertIsNone(await g.verdict("https://example.com/a.png"))
            for url in ("http://127.0.0.1:3000/v1/sessions", "http://169.254.169.254/latest/", "http://0x7f000001/",
                        "http://gateway:8080/mcp", "file:///etc/passwd", "http://[::ffff:127.0.0.1]/"):
                self.assertIsNotNone(await g.verdict(url), url)

    async def test_in_browser_schemes_never_leave_the_browser(self):
        g = Guard("ws://127.0.0.1:1/")
        for url in ("data:text/html,hi", "blob:https://example.com/x", "about:blank", "chrome-extension://abc/x.js"):
            self.assertIsNone(await g.verdict(url), url)

    async def test_a_public_name_that_resolves_inward_is_refused_and_remembered(self):
        calls = []

        def inward(host):
            calls.append(host)
            raise UnsafeUrl(f"refused: {host} resolves to 10.0.0.5")

        g = Guard("ws://127.0.0.1:1/")
        with mock.patch.object(guard, "require_public_addresses", inward):
            for _ in range(5):
                self.assertIn("10.0.0.5", await g.verdict("https://looks-fine.example/x"))
        self.assertEqual(calls, ["looks-fine.example"])


class Recorder:
    """Stands in for the CDP connection: remembers every call, answers from a table."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail or {}

    async def __call__(self, method, params=None, session=None):
        self.calls.append((method, session))
        if method in self.fail:
            raise guard.CdpError(self.fail[method])
        return {}


class Handlers(unittest.IsolatedAsyncioTestCase):
    async def test_a_service_worker_is_intercepted_before_it_is_allowed_to_run(self):
        g, rec = Guard("ws://127.0.0.1:1/"), Recorder()
        with mock.patch.object(g, "_call", rec):
            await g._on_worker({"sessionId": "SW", "targetInfo": {"type": "service_worker", "targetId": "T"}})
        self.assertEqual(rec.calls, [("Fetch.enable", "SW"), ("Runtime.runIfWaitingForDebugger", "SW")])

    async def test_a_worker_that_cannot_be_watched_is_closed_not_run(self):
        g, rec = Guard("ws://127.0.0.1:1/"), Recorder(fail={"Fetch.enable": "Internal error"})
        with mock.patch.object(g, "_call", rec):
            await g._on_worker({"sessionId": "SW", "targetInfo": {"type": "service_worker", "targetId": "T"}})
        methods = [m for m, _ in rec.calls]
        self.assertIn("Target.closeTarget", methods)
        self.assertNotIn("Runtime.runIfWaitingForDebugger", methods)

    async def test_allowed_continues_refused_fails_and_is_recorded(self):
        g, rec = Guard("ws://127.0.0.1:1/"), Recorder()
        with mock.patch.object(g, "_call", rec), mock.patch.object(guard, "require_public_addresses", public):
            await g._on_paused("S", {"requestId": "1", "request": {"url": "https://example.com/"}})
            await g._on_paused("S", {"requestId": "2", "request": {"url": "http://127.0.0.1:3000/v1/sessions"}})
        self.assertEqual([m for m, _ in rec.calls], ["Fetch.continueRequest", "Fetch.failRequest"])
        self.assertEqual(g.counts["refused"], 1)
        self.assertEqual(g.refusals[0]["url"], "http://127.0.0.1:3000/v1/sessions")

    async def test_steel_recorder_posts_are_refused_but_counted_apart(self):
        g, rec = Guard("ws://127.0.0.1:1/"), Recorder()
        with mock.patch.object(g, "_call", rec):
            for rid, url in (("1", "http://localhost:3000/v1/events"), ("2", "http://0.0.0.0:3000/v1/events?x=1")):
                await g._on_paused(None, {"requestId": rid, "request": {"url": url}})
            await g._on_paused(None, {"requestId": "3", "request": {"url": "http://127.0.0.1:3000/v1/sessions"}})
        self.assertEqual([m for m, _ in rec.calls], ["Fetch.failRequest"] * 3)
        self.assertEqual((g.counts["refused_steel_events"], g.counts["refused"]), (2, 1))
        self.assertEqual([r["url"] for r in g.refusals], ["http://127.0.0.1:3000/v1/sessions"])

    async def test_a_check_that_hangs_fails_the_request_rather_than_holding_it(self):
        async def forever(url):
            await asyncio.sleep(3600)

        g, rec = Guard("ws://127.0.0.1:1/"), Recorder()
        with mock.patch.object(g, "_call", rec), mock.patch.object(g, "verdict", forever), mock.patch.object(guard, "DECIDE_TIMEOUT", 0.05):
            await g._on_paused("S", {"requestId": "1", "request": {"url": "https://slow.example/"}})
        self.assertEqual(rec.calls[0][0], "Fetch.failRequest")


class Readiness(unittest.IsolatedAsyncioTestCase):
    async def test_a_detached_guard_refuses_quickly_and_says_why(self):
        g = Guard("ws://127.0.0.1:1/")
        g.last_error = "ConnectionRefusedError: [Errno 111]"
        with self.assertRaises(guard.GuardDown) as caught:
            await g.wait_ready(0.05)
        self.assertIn("ConnectionRefusedError", str(caught.exception))


class AgainstAFakeBrowser(unittest.IsolatedAsyncioTestCase):
    async def test_intercepts_on_the_browser_target_and_survives_a_two_megabyte_url(self):
        """A page picks the size of a paused request's URL; an oversize frame must not close us."""
        answered = {}
        enabled = []
        done = asyncio.Event()
        huge = "https://example.com/?" + "a" * 2_000_000

        async def browser(ws):
            async for raw in ws:
                msg = json.loads(raw)
                method, sid = msg["method"], msg.get("sessionId")
                await ws.send(json.dumps({"id": msg["id"], "result": {}}))
                if method == "Target.setAutoAttach":
                    kinds = [f.get("type") for f in msg["params"]["filter"] if not f.get("exclude")]
                    self.assertEqual(kinds, ["service_worker", "shared_worker"])
                if method == "Fetch.enable":
                    enabled.append(sid)
                    # Browser-level interception: paused requests arrive with no sessionId.
                    for rid, url in (("r-huge", huge), ("r-bad", "http://127.0.0.1:3000/v1/sessions"), ("r-ok", "https://example.com/")):
                        await ws.send(json.dumps({"method": "Fetch.requestPaused", "params": {"requestId": rid, "request": {"url": url}}}))
                elif method in ("Fetch.continueRequest", "Fetch.failRequest"):
                    self.assertNotIn("sessionId", msg)
                    answered[msg["params"]["requestId"]] = method
                    if len(answered) == 3:
                        done.set()

        async with serve(browser, "127.0.0.1", 0, max_size=None) as server:
            port = server.sockets[0].getsockname()[1]
            g = Guard(f"ws://127.0.0.1:{port}/")
            with mock.patch.object(guard, "require_public_addresses", public):
                g.start()
                try:
                    await g.wait_ready(5)
                    await asyncio.wait_for(done.wait(), 5)
                    self.assertTrue(g.up, "a 2 MB URL knocked the guard off")
                finally:
                    await g.stop()
        self.assertEqual(enabled, [None], "interception must be switched on for the whole browser, once")
        self.assertEqual(answered, {"r-huge": "Fetch.continueRequest", "r-bad": "Fetch.failRequest", "r-ok": "Fetch.continueRequest"})

    async def test_notices_a_closed_connection_at_once(self):
        async def browser(ws):
            async for raw in ws:
                msg = json.loads(raw)
                await ws.send(json.dumps({"id": msg["id"], "result": {}}))
                if msg["method"] == "Target.setAutoAttach":  # the last setup call
                    await asyncio.sleep(0.1)
                    await ws.close()

        async with serve(browser, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            g = Guard(f"ws://127.0.0.1:{port}/")
            g.start()
            try:
                await g.wait_ready(5)
                await asyncio.sleep(0.5)
                self.assertFalse(g.up, "a guard with a closed socket still claims to be attached")
            finally:
                await g.stop()


class SteelErrors(unittest.IsolatedAsyncioTestCase):
    async def test_a_guard_refusal_is_a_refusal_not_an_outage(self):
        def respond(request):
            return httpx.Response(500, json={"message": "net::ERR_BLOCKED_BY_CLIENT at https://httpbin.org/redirect-to?url=..."})

        real = httpx.AsyncClient

        def client(*a, **k):
            k["transport"] = httpx.MockTransport(respond)
            return real(*a, **k)

        with mock.patch.object(steel.httpx, "AsyncClient", client):
            with self.assertRaises(UnsafeUrl):
                await steel.scrape("https://httpbin.org/redirect-to?url=x")


if __name__ == "__main__":
    unittest.main()
