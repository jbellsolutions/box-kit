"""Browser Use Cloud, the default engine: tested against a fake REST API (httpx's real request builder over a
mock transport) and a fake CDP browser. The properties that matter are about money and leaks: every
browser stopped, no residential proxy and no CAPTCHA solving unless asked, the plan's ceiling and the
monthly cap respected, the key and the CDP address in no message."""
import asyncio
import base64
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import httpx

from gateway import cloud
from gateway.cloud import BrowserUseCloud, CloudUnavailable
from gateway.security import UnsafeUrl

KEY = "bu_test_key_not_real"
PAGE = {"url": "https://example.com/", "title": "Example Domain", "text": "Example Domain\nThis domain is for use",
        "links": ["https://iana.org/domains/example"]}
JPEG = b"\xff\xd8fakejpeg"


class FakeApi:
    def __init__(self, balance=5.0, limit=10, spent=0.0, fail=None, strays=0):
        self.balance, self.limit, self.spent, self.fail, self.strays = balance, limit, spent, fail or {}, strays
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        path, method = request.url.path, request.method
        for prefix, code in self.fail.items():
            if path.startswith(prefix) and (method, path) != ("PATCH", "/api/v4/browsers/br-1"):
                return httpx.Response(code, json={"detail": "nope"})
        if path == "/api/v2/billing/account":
            return httpx.Response(200, json={"totalCreditsBalanceUsd": self.balance, "concurrentSessionLimit": self.limit})
        if path == "/api/v4/browsers" and method == "GET":
            now = datetime.now(timezone.utc).isoformat()
            items = [{"id": "old", "status": "stopped", "startedAt": "2020-01-01T00:00:00Z", "browserCost": "9"}]
            items.insert(0, {"id": "this-month", "status": "stopped", "startedAt": now, "browserCost": str(self.spent)})
            items += [{"id": f"stray-{i}", "status": "active", "startedAt": now, "browserCost": "0"} for i in range(self.strays)]
            return httpx.Response(200, json={"items": items})
        if path == "/api/v4/browsers" and method == "POST":
            return httpx.Response(201, json={"id": "br-1", "cdpUrl": "https://br-1.cdp.example", "liveUrl": "https://live/br-1"})
        if path == "/json/version":
            return httpx.Response(200, json={"webSocketDebuggerUrl": "wss://br-1.cdp.example/devtools/browser/x"})
        if method == "PATCH" and path.startswith("/api/v4/browsers/"):
            return httpx.Response(200, json={"status": "stopped"})
        return httpx.Response(404, json={"detail": f"no route {path}"})

    def bodies(self, method, path):
        return [json.loads(r.content) for r in self.seen if r.method == method and r.url.path == path]

    def stops(self):
        return [r.url.path for r in self.seen if r.method == "PATCH"]


class FakeBrowser:
    def __init__(self, page=PAGE, status=200, nav_error=None):
        self.page, self.status, self.nav_error = page, status, nav_error
        self.queue: asyncio.Queue = asyncio.Queue()
        self.calls: list[str] = []

    def __call__(self, url):
        self.url = url
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.queue.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self.queue.get()
        if msg is None:
            raise StopAsyncIteration
        return json.dumps(msg)

    async def send(self, raw):
        msg = json.loads(raw)
        self.calls.append(msg["method"])
        result = {
            "Target.getTargets": {"targetInfos": [{"targetId": "t1", "type": "page"}]},
            "Target.attachToTarget": {"sessionId": "s1"},
            "Page.navigate": {"frameId": "f1", **({"errorText": self.nav_error} if self.nav_error else {})},
            "Runtime.evaluate": {"result": {"value": json.dumps(self.page)}},
            "Page.captureScreenshot": {"data": base64.b64encode(JPEG).decode()},
        }.get(msg["method"], {})
        if msg["method"] == "Page.navigate" and not self.nav_error:
            await self.queue.put({"method": "Network.responseReceived", "sessionId": "s1",
                                  "params": {"type": "Document", "response": {"status": self.status}}})
        await self.queue.put({"id": msg["id"], "result": result})
        if msg["method"] == "Page.navigate" and not self.nav_error:
            await self.queue.put({"method": "Page.loadEventFired", "sessionId": "s1", "params": {}})


def engine(api=None, browser=None, **kw):
    api = api or FakeApi()
    browser = browser or FakeBrowser()
    return BrowserUseCloud(KEY, transport=httpx.MockTransport(api), cdp_connect=browser, **kw), api, browser


def public_dns():
    return mock.patch.object(cloud, "require_public_addresses", lambda host: ["93.184.215.14"])


class Configuration(unittest.TestCase):
    def test_without_a_key_there_is_no_engine(self):
        self.assertIsNone(BrowserUseCloud.from_env({}))
        self.assertIsNone(BrowserUseCloud.from_env({"BROWSER_USE_API_KEY": " "}))

    def test_env_sets_the_caps(self):
        bu = BrowserUseCloud.from_env({"BROWSER_USE_API_KEY": KEY})
        self.assertEqual((bu.monthly_usd, bu.max_concurrent, bu.session_minutes), (10.0, 10, 5))
        bu = BrowserUseCloud.from_env({"BROWSER_USE_API_KEY": KEY, "BB_BROWSERUSE_MONTHLY_USD": "3",
                                       "BB_BROWSERUSE_MAX_CONCURRENT": "50", "BB_BROWSERUSE_SESSION_MINUTES": "999"})
        self.assertEqual((bu.monthly_usd, bu.max_concurrent, bu.session_minutes), (3.0, 50, 240))


class Read(unittest.IsolatedAsyncioTestCase):
    async def test_a_read_returns_the_page_status_and_stops_the_browser(self):
        bu, api, browser = engine()
        with public_dns():
            out = await bu.read("https://example.com/")
        self.assertEqual((out["engine"], out["title"], out["status_code"]), ("browseruse", "Example Domain", 200))
        self.assertEqual(out["links"], PAGE["links"])
        self.assertEqual(api.stops(), ["/api/v4/browsers/br-1"])
        self.assertEqual(browser.url, "wss://br-1.cdp.example/devtools/browser/x")
        self.assertEqual(bu.running, 0)

    async def test_the_browser_is_fresh_without_a_proxy_solves_captchas_and_is_tagged(self):
        bu, api, _ = engine()
        with public_dns():
            await bu.read("https://example.com/")
        body = api.bodies("POST", "/api/v4/browsers")[0]
        self.assertIsNone(body["proxyCountryCode"])
        self.assertTrue(body["solveCaptchas"])
        self.assertNotIn("profileId", body)
        self.assertEqual(body["metadata"], {"owner": "browser-box"})
        bu, api, _ = engine()
        with mock.patch.dict("os.environ", {"BB_SOLVE_CAPTCHAS": "0"}), public_dns():
            await bu.read("https://example.com/")
        self.assertFalse(api.bodies("POST", "/api/v4/browsers")[0]["solveCaptchas"])
        self.assertEqual(body["timeout"], 5)
        self.assertNotIn("customProxy", body)

    async def test_the_screenshot_is_of_the_same_load_not_a_second_navigation(self):
        bu, _, browser = engine()
        with public_dns():
            out = await bu.read("https://example.com/", screenshot=True)
        self.assertEqual(out["screenshot"], JPEG)
        self.assertEqual(browser.calls.count("Page.navigate"), 1)

    async def test_a_failed_navigation_still_stops_the_browser(self):
        bu, api, _ = engine(browser=FakeBrowser(nav_error="net::ERR_NAME_NOT_RESOLVED"))
        with public_dns(), self.assertRaises(CloudUnavailable) as caught:
            await bu.read("https://example.com/")
        self.assertIn("ERR_NAME_NOT_RESOLVED", str(caught.exception))
        self.assertEqual(api.stops(), ["/api/v4/browsers/br-1"])
        self.assertEqual(bu.running, 0)

    async def test_private_targets_are_refused_before_any_browser(self):
        bu, api, _ = engine()
        with self.assertRaises(UnsafeUrl):
            await bu.read("http://127.0.0.1:3000/")
        self.assertEqual(api.bodies("POST", "/api/v4/browsers"), [])

    async def test_a_page_that_lands_off_the_public_web_is_dropped(self):
        bu, _, _ = engine(browser=FakeBrowser(page={**PAGE, "url": "http://10.0.0.5/"}))
        with public_dns(), self.assertRaises(UnsafeUrl):
            await bu.read("https://example.com/")


class Caps(unittest.IsolatedAsyncioTestCase):
    async def test_the_plans_ceiling_is_respected_with_no_lock_below_it(self):
        bu, api, _ = engine(api=FakeApi(limit=2))
        bu.running = 2
        with public_dns(), self.assertRaises(CloudUnavailable) as caught:
            await bu.read("https://example.com/")
        self.assertIn("all 2", str(caught.exception))
        self.assertEqual(api.bodies("POST", "/api/v4/browsers"), [])
        bu.running = 1
        with public_dns():
            await bu.read("https://example.com/")

    async def test_our_cap_bounds_a_bigger_plan(self):
        bu, _, _ = engine(api=FakeApi(limit=50), max_concurrent=10)
        self.assertEqual(await bu.ceiling(), 10)

    async def test_out_of_credit_is_refused_before_a_create(self):
        bu, api, _ = engine(api=FakeApi(balance=0.0))
        with public_dns(), self.assertRaises(CloudUnavailable) as caught:
            await bu.read("https://example.com/")
        self.assertIn("out of credit", str(caught.exception))
        self.assertEqual(api.bodies("POST", "/api/v4/browsers"), [])

    async def test_the_monthly_cap_counts_only_this_months_browsers(self):
        bu, _, _ = engine(api=FakeApi(spent=0.5), monthly_usd=1.0)
        self.assertAlmostEqual(await bu.month_spend(), 0.5)  # last year's $9 is not counted
        bu, api, _ = engine(api=FakeApi(spent=1.0), monthly_usd=1.0)
        with public_dns(), self.assertRaises(CloudUnavailable) as caught:
            await bu.read("https://example.com/")
        self.assertIn("BB_BROWSERUSE_MONTHLY_USD", str(caught.exception))
        self.assertEqual(api.bodies("POST", "/api/v4/browsers"), [])

    async def test_a_402_is_reported_as_out_of_credit_and_the_key_never_appears(self):
        bu, _, _ = engine(api=FakeApi(fail={"/api/v4/browsers": 402}))
        with public_dns(), self.assertRaises(CloudUnavailable) as caught:
            await bu.read("https://example.com/")
        self.assertIn("out of credit", str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))


class Housekeeping(unittest.IsolatedAsyncioTestCase):
    async def test_only_browsers_this_box_created_are_stopped_after_a_crash(self):
        import tempfile
        path = tempfile.mktemp(suffix=".json")
        bu, api, _ = engine(api=FakeApi(strays=2), owned_path=path)
        bu._own("ours-1")                      # created, then the gateway died before stopping it
        self.assertEqual(await bu.stop_strays(), 1)
        self.assertEqual(api.stops(), ["/api/v4/browsers/ours-1"], "a browser tagged like ours but not created here was stopped")
        self.assertFalse([r for r in api.seen if r.method == "GET" and r.url.path == "/api/v4/browsers"],
                         "the account was searched for strays")
        self.assertEqual(bu._owned(), set())

    async def test_a_finished_browser_is_no_longer_recorded(self):
        import tempfile
        bu, api, _ = engine(owned_path=tempfile.mktemp(suffix=".json"))
        with public_dns():
            await bu.read("https://example.com/")
        self.assertEqual(bu._owned(), set())

    async def test_the_profiles_api_is_refused_before_any_request(self):
        bu, api, _ = engine()
        for path in ("/v4/profiles", "/v4/profiles/abc", "/v2/Profiles"):
            with self.assertRaises(CloudUnavailable):
                await bu._api("GET", path)
        self.assertEqual(api.seen, [])

    async def test_status_never_raises_and_holds_no_key(self):
        bu, _, _ = engine(api=FakeApi(fail={"/api/v2": 500}))
        row = await bu.status()
        self.assertFalse(row["up"])
        self.assertNotIn(KEY, json.dumps(row))
        bu, _, _ = engine()
        row = await bu.status()
        self.assertTrue(row["up"])
        self.assertEqual((row["at_once"], row["balance_usd"]), (10, 5.0))


class FakeCloud:
    def __init__(self, page=None, error=None):
        self.page, self.error, self.calls = page, error, []

    async def read(self, url, *, screenshot=False, delay_ms=0):
        self.calls.append(url)
        if self.error:
            raise self.error
        return {"engine": "browseruse", "url": url, "final_url": url, "title": "T", "status_code": 200, "links": [],
                "text": "hello", "truncated": False, "screenshot": JPEG if screenshot else None, "seconds": 1.0,
                **(self.page or {})}


class FakeBB:
    def __init__(self):
        self.calls = []

    async def read(self, url, *, reason, region=None):
        self.calls.append(reason)
        return {"title": "BB", "final_url": url, "links": [], "text": "from browserbase", "why": "w",
                "region": "us-west-2", "seconds": 2.0}


class Dispatch(unittest.IsolatedAsyncioTestCase):
    """read() with the cloud configured: it is the default, Browserbase is its fallback."""

    def setUp(self):
        from gateway import tools
        self.tools = tools
        self.patches = [mock.patch.object(tools, "safe_target", mock.AsyncMock(side_effect=lambda u: u))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def engines(self, cloud_, bb=None):
        return (mock.patch.object(self.tools, "cloud_client", lambda: cloud_),
                mock.patch.object(self.tools, "browserbase_client", lambda: bb))

    async def test_auto_reads_on_the_cloud_with_the_screenshot_of_that_load(self):
        c, b = self.engines(FakeCloud())
        with c, b:
            out = await self.tools.read({"url": "https://example.com/", "screenshot": True})
        self.assertEqual(out["engine"], "browseruse")
        self.assertEqual(base64.b64decode(out["screenshot_base64"]), JPEG)

    async def test_a_cloud_failure_falls_back_to_browserbase(self):
        bb = FakeBB()
        c, b = self.engines(FakeCloud(error=CloudUnavailable("Browser Use is out of credit")), bb)
        with c, b:
            out = await self.tools.read({"url": "https://example.com/"})
        self.assertEqual((out["engine"], bb.calls), ("browserbase", ["engine_down"]))
        self.assertIn("out of credit", out["engine_error"])

    async def test_a_blocked_page_falls_back_to_browserbase(self):
        bb = FakeBB()
        c, b = self.engines(FakeCloud(page={"status_code": 403, "text": "Access denied"}), bb)
        with c, b:
            out = await self.tools.read({"url": "https://example.com/"})
        self.assertEqual(bb.calls, ["blocked"])

    async def test_without_browserbase_a_cloud_failure_is_the_answer(self):
        c, b = self.engines(FakeCloud(error=CloudUnavailable("down")))
        with c, b, self.assertRaises(CloudUnavailable):
            await self.tools.read({"url": "https://example.com/"})

    async def test_engine_browseruse_never_falls_back(self):
        bb = FakeBB()
        c, b = self.engines(FakeCloud(error=CloudUnavailable("down")), bb)
        with c, b, self.assertRaises(CloudUnavailable):
            await self.tools.read({"url": "https://example.com/", "engine": "browseruse"})
        self.assertEqual(bb.calls, [])

    async def test_without_browser_use_browserbase_is_the_engine(self):
        bb = FakeBB()
        c, b = self.engines(None, bb)
        with c, b:
            out = await self.tools.read({"url": "https://example.com/"})
        self.assertEqual(bb.calls, ["no_browser_use"])

    async def test_without_any_engine_read_says_what_to_set(self):
        c, b = self.engines(None)
        with c, b, self.assertRaises(CloudUnavailable) as caught:
            await self.tools.read({"url": "https://example.com/"})
        self.assertIn("BROWSER_USE_API_KEY", str(caught.exception))

    async def test_engine_browseruse_without_a_key_says_so(self):
        c, b = self.engines(None)
        with c, b, self.assertRaises(CloudUnavailable) as caught:
            await self.tools.read({"url": "https://example.com/", "engine": "browseruse"})
        self.assertIn("BROWSER_USE_API_KEY", str(caught.exception))



class HostedTask(unittest.IsolatedAsyncioTestCase):
    """task(surface=browser) with the cloud configured: a browser of its own, stopped after; no lane."""

    async def test_the_task_gets_its_own_browser_which_is_stopped_after(self):
        from gateway import tools
        bu, api, _ = engine()
        run = mock.AsyncMock(return_value={"status": "done", "answer": "42", "tabs_closed": 1})
        with mock.patch.object(tools, "cloud_client", lambda: bu), mock.patch.object(tools.browseruse, "run", run), \
                mock.patch.object(tools, "lane", side_effect=AssertionError("no lane on the hosted path")):
            out = await tools._browser_task({"goal": "g", "max_steps": 5, "timeout_seconds": 300})
        self.assertEqual((out["status"], out["engine"]), ("done", "browseruse"))
        self.assertNotIn("tabs_closed", out)
        self.assertEqual(run.await_args.kwargs["cdp_url"], "wss://br-1.cdp.example/devtools/browser/x")
        self.assertEqual(api.bodies("POST", "/api/v4/browsers")[0]["timeout"], 7)
        self.assertEqual(api.stops(), ["/api/v4/browsers/br-1"])

    async def test_a_caller_giving_up_stops_the_agent_then_the_browser(self):
        from gateway import tools
        bu, api, _ = engine()
        order = []
        run = mock.AsyncMock(side_effect=asyncio.CancelledError())
        cancel = mock.AsyncMock(side_effect=lambda tid: order.append(("cancel", tid)))
        with mock.patch.object(tools, "cloud_client", lambda: bu), mock.patch.object(tools.browseruse, "run", run), \
                mock.patch.object(tools.browseruse, "cancel", cancel), self.assertRaises(asyncio.CancelledError):
            await tools._browser_task({"goal": "g"})
        self.assertEqual(order, [("cancel", run.await_args.kwargs["task_id"])])
        self.assertEqual(api.stops(), ["/api/v4/browsers/br-1"])
        self.assertEqual(bu.running, 0)


if __name__ == "__main__":
    unittest.main()
