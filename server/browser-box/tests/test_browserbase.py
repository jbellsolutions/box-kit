"""Browserbase, the last rung: tested against a fake REST API (httpx's real request builder over a mock
transport) and a fake CDP browser. The properties that matter are about money and leaks: no session
without a reason and headroom, every session released, CAPTCHA solving off, the key in no message."""
import asyncio
import json
import unittest
from unittest import mock

import httpx
from websockets.exceptions import ConnectionClosedError, InvalidStatus

from gateway import browserbase
from gateway.browserbase import Browserbase, BrowserbaseUnavailable
from gateway.security import UnsafeUrl

KEY = "bb_test_key_not_real"
PAGE = {"url": "https://example.com/", "title": "Example Domain", "text": "Example Domain\nThis domain is for use"}


class FakeApi:
    def __init__(self, minutes=0, projects=None, fail=None, concurrency=25):
        self.minutes, self.concurrency = minutes, concurrency
        self.projects = projects if projects is not None else [{"id": "proj-1"}]
        self.fail = fail or {}
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        path = request.url.path
        for prefix, code in self.fail.items():
            if path.startswith(prefix):
                return httpx.Response(code, json={"message": "nope"})
        if path == "/v1/projects":
            return httpx.Response(200, json=self.projects)
        if path.startswith("/v1/projects/") and path.count("/") == 3:
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[1], "concurrency": self.concurrency})
        if path.endswith("/usage"):
            return httpx.Response(200, json={"browserMinutes": self.minutes, "proxyBytes": 0})
        if path == "/v1/sessions" and request.method == "POST":
            return httpx.Response(201, json={"id": "sess-1", "connectUrl": "wss://connect.example/sess-1"})
        if path == "/v1/sessions/sess-1" and request.method == "POST":
            return httpx.Response(200, json={"id": "sess-1", "status": "COMPLETED"})
        return httpx.Response(404, json={"message": f"no route {path}"})

    def bodies(self, method, path):
        return [json.loads(r.content) for r in self.seen if r.method == method and r.url.path == path]


class FakeBrowser:
    """A CDP websocket: answers each call by method, and fires Page.loadEventFired after navigate."""

    def __init__(self, page=PAGE, nav_error=None, drop=None, close_on=None):
        self.page, self.nav_error, self.drop, self.close_on = page, nav_error, drop, close_on
        self.queue: asyncio.Queue = asyncio.Queue()
        self.calls: list[str] = []

    def __call__(self, url):
        self.url = url
        return self

    async def __aenter__(self):
        if self.drop:
            raise self.drop
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
        if msg["method"] == self.close_on:
            raise ConnectionClosedError(None, None)
        result = {
            "Target.getTargets": {"targetInfos": [{"targetId": "t1", "type": "page"}]},
            "Target.attachToTarget": {"sessionId": "s1"},
            "Page.navigate": {"frameId": "f1", **({"errorText": self.nav_error} if self.nav_error else {})},
            "Runtime.evaluate": {"result": {"value": json.dumps(self.page)}},
        }.get(msg["method"], {})
        await self.queue.put({"id": msg["id"], "result": result})
        if msg["method"] == "Page.navigate" and not self.nav_error:
            await self.queue.put({"method": "Page.loadEventFired", "sessionId": "s1", "params": {}})


def box(api=None, browser=None, **kw):
    api = api or FakeApi()
    browser = browser or FakeBrowser()
    bb = Browserbase(KEY, transport=httpx.MockTransport(api), cdp_connect=browser, **kw)
    return bb, api, browser


def public_dns():
    return mock.patch.object(browserbase, "require_public_addresses", lambda host: ["93.184.215.14"])


class Configuration(unittest.TestCase):
    def test_without_a_key_there_is_no_browserbase(self):
        self.assertIsNone(Browserbase.from_env({}))
        self.assertIsNone(Browserbase.from_env({"BROWSERBASE_API_KEY": "  "}))

    def test_env_sets_the_caps_and_defaults_match_the_developer_plan(self):
        bb = Browserbase.from_env({"BROWSERBASE_API_KEY": KEY})
        self.assertEqual((bb.monthly_hours, bb.max_concurrent, bb.timeout_s), (100.0, 25, 120))
        bb = Browserbase.from_env({"BROWSERBASE_API_KEY": KEY, "BB_BROWSERBASE_MONTHLY_HOURS": "40",
                                   "BB_BROWSERBASE_MAX_CONCURRENT": "5", "BB_BROWSERBASE_TIMEOUT": "10"})
        self.assertEqual((bb.monthly_hours, bb.max_concurrent, bb.timeout_s), (40.0, 5, 60))


class Read(unittest.IsolatedAsyncioTestCase):
    async def test_a_read_returns_the_page_and_says_which_engine_and_why(self):
        bb, api, browser = box()
        with public_dns():
            out = await bb.read("https://example.com", reason="engine_down")
        self.assertEqual(out["engine"], "browserbase")
        self.assertEqual(out["reason"], "engine_down")
        self.assertEqual(out["why"], browserbase.REASONS["engine_down"])
        self.assertEqual((out["title"], out["final_url"]), ("Example Domain", "https://example.com/"))
        self.assertIn("This domain", out["text"])
        self.assertEqual(browser.url, "wss://connect.example/sess-1")

    async def test_every_session_is_fresh_logged_out_and_solves_captchas(self):
        bb, api, _ = box()
        with public_dns():
            await bb.read("https://example.com", reason="blocked")
        (create,) = api.bodies("POST", "/v1/sessions")
        self.assertIs(create["keepAlive"], False)
        self.assertIs(create["browserSettings"]["solveCaptchas"], True)
        self.assertEqual(create["timeout"], 120)
        self.assertNotIn("context", create["browserSettings"])
        self.assertEqual(create["projectId"], "proj-1")

    async def test_the_key_goes_only_in_the_header(self):
        bb, api, _ = box()
        with public_dns():
            await bb.read("https://example.com", reason="blocked")
        for request in api.seen:
            self.assertEqual(request.headers["X-BB-API-Key"], KEY)
            self.assertNotIn(KEY, str(request.url))
            self.assertNotIn(KEY.encode(), request.content)

    async def test_the_session_is_released_after_a_read(self):
        bb, api, _ = box()
        with public_dns():
            await bb.read("https://example.com", reason="blocked")
        self.assertEqual(api.bodies("POST", "/v1/sessions/sess-1"), [{"projectId": "proj-1", "status": "REQUEST_RELEASE"}])
        self.assertEqual(bb.running, 0)

    async def test_a_failed_connection_is_a_clean_error_and_the_session_is_released(self):
        rejected = InvalidStatus(httpx.Response(403))  # an expired or refused connectUrl
        for browser in (FakeBrowser(drop=OSError("connection refused")), FakeBrowser(drop=rejected),
                        FakeBrowser(close_on="Page.navigate"), FakeBrowser(close_on="Runtime.evaluate")):
            bb, api, _ = box(browser=browser)
            with self.subTest(browser=browser.drop or browser.close_on), public_dns(), \
                    self.assertRaisesRegex(BrowserbaseUnavailable, "connection failed"):
                await bb.read("https://example.com", reason="blocked")
            self.assertEqual(len(api.bodies("POST", "/v1/sessions/sess-1")), 1)
            self.assertEqual(bb.running, 0)

    async def test_the_session_is_released_when_the_page_does_not_open(self):
        bb, api, _ = box(browser=FakeBrowser(nav_error="net::ERR_NAME_NOT_RESOLVED"))
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "ERR_NAME_NOT_RESOLVED"):
            await bb.read("https://example.com", reason="blocked")
        self.assertEqual(len(api.bodies("POST", "/v1/sessions/sess-1")), 1)

    async def test_a_page_that_lands_somewhere_private_is_dropped(self):
        bb, _, _ = box(browser=FakeBrowser(page={**PAGE, "url": "http://10.0.0.5/admin"}))
        with public_dns(), self.assertRaises(UnsafeUrl):
            await bb.read("https://example.com", reason="blocked")

    async def test_long_pages_are_cut_and_say_so(self):
        bb, _, _ = box(browser=FakeBrowser(page={**PAGE, "text": "x" * (browserbase.MAX_TEXT + 5)}))
        with public_dns():
            out = await bb.read("https://example.com", reason="blocked")
        self.assertEqual(len(out["text"]), browserbase.MAX_TEXT)
        self.assertTrue(out["truncated"])

    async def test_a_region_read_sends_the_region(self):
        bb, api, _ = box()
        with public_dns():
            out = await bb.read("https://example.com", reason="region", region="eu-central-1")
        self.assertEqual(api.bodies("POST", "/v1/sessions")[0]["region"], "eu-central-1")
        self.assertEqual(out["region"], "eu-central-1")


class Refusals(unittest.IsolatedAsyncioTestCase):
    async def test_there_is_no_default_reason(self):
        bb, api, _ = box()
        for reason in ("", "default", "cheaper"):
            with self.assertRaisesRegex(ValueError, "last rung"):
                await bb.read("https://example.com", reason=reason)
        self.assertEqual(api.seen, [])

    async def test_region_needs_a_known_region(self):
        bb, _, _ = box()
        with self.assertRaises(ValueError):
            await bb.read("https://example.com", reason="region")
        with self.assertRaises(ValueError):
            await bb.read("https://example.com", reason="region", region="mars-1")

    async def test_a_private_url_is_refused_before_anything_is_spent(self):
        bb, api, _ = box()
        for url in ("http://127.0.0.1:3000/v1/sessions", "http://0x7f000001/", "http://169.254.169.254/", "file:///etc/passwd"):
            with self.assertRaises((UnsafeUrl, ValueError)):
                await bb.read(url, reason="blocked")
        self.assertEqual(api.seen, [])

    async def test_no_session_once_the_monthly_hours_are_used(self):
        bb, api, _ = box(api=FakeApi(minutes=100 * 60 - 1))
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "used up"):
            await bb.read("https://example.com", reason="blocked")
        self.assertEqual(api.bodies("POST", "/v1/sessions"), [])

    async def test_sessions_already_running_count_against_the_hours_left(self):
        bb, api, _ = box(api=FakeApi(minutes=100 * 60 - 5), max_concurrent=3)
        bb.running = 2  # two sessions out, each able to bill up to 2 minutes more
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "used up"):
            await bb.read("https://example.com", reason="engine_down")
        self.assertEqual(api.bodies("POST", "/v1/sessions"), [])

    async def test_no_session_when_usage_cannot_be_read(self):
        bb, api, _ = box(api=FakeApi(fail={"/v1/projects/proj-1/usage": 500}))
        with public_dns(), self.assertRaises(BrowserbaseUnavailable):
            await bb.read("https://example.com", reason="blocked")
        self.assertEqual(api.bodies("POST", "/v1/sessions"), [])

    async def test_no_session_past_the_concurrency_cap(self):
        bb, api, _ = box(max_concurrent=1)
        bb.running = 1
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "in use"):
            await bb.read("https://example.com", reason="engine_down")
        self.assertEqual(api.bodies("POST", "/v1/sessions"), [])

    async def test_the_projects_own_limit_is_read_not_assumed(self):
        bb, api, _ = box(api=FakeApi(concurrency=3), max_concurrent=25)
        self.assertEqual(await bb.ceiling(), 3)
        bb.running = 3
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "project's own limit"):
            await bb.read("https://example.com", reason="engine_down")
        self.assertEqual(api.bodies("POST", "/v1/sessions"), [])

    async def test_our_cap_stands_when_the_project_cannot_be_read(self):
        bb, _, _ = box(api=FakeApi(fail={"/v1/projects/proj-1": 500}), max_concurrent=25, project_id="proj-1")
        self.assertEqual(await bb.ceiling(), 25)

    async def test_a_rejected_key_is_named_but_not_shown(self):
        bb, _, _ = box(api=FakeApi(fail={"/v1/projects": 401}))
        with public_dns(), self.assertRaises(BrowserbaseUnavailable) as caught:
            await bb.read("https://example.com", reason="blocked")
        self.assertIn("BROWSERBASE_API_KEY", str(caught.exception))
        self.assertNotIn(KEY, str(caught.exception))

    async def test_several_projects_need_one_chosen(self):
        bb, _, _ = box(api=FakeApi(projects=[{"id": "a"}, {"id": "b"}]))
        with public_dns(), self.assertRaisesRegex(BrowserbaseUnavailable, "BROWSERBASE_PROJECT_ID"):
            await bb.read("https://example.com", reason="blocked")

    async def test_a_set_project_is_used_without_listing(self):
        bb, api, _ = box(project_id="proj-9")
        with public_dns():
            await bb.read("https://example.com", reason="blocked")
        self.assertFalse([r for r in api.seen if r.url.path == "/v1/projects"])
        self.assertEqual(api.bodies("POST", "/v1/sessions")[0]["projectId"], "proj-9")


class Status(unittest.IsolatedAsyncioTestCase):
    async def test_status_shows_hours_used_against_the_cap(self):
        bb, _, _ = box(api=FakeApi(minutes=90))
        row = await bb.status()
        self.assertEqual((row["up"], row["hours_used"], row["hours_cap"]), (True, 1.5, 100.0))
        self.assertEqual((row["at_once"], row["plan_concurrency"]), (25, 25))
        self.assertIn("last rung", row["role"])

    async def test_status_never_raises(self):
        bb, _, _ = box(api=FakeApi(fail={"/v1/projects": 401}))
        row = await bb.status()
        self.assertFalse(row["up"])
        self.assertNotIn(KEY, json.dumps(row))


if __name__ == "__main__":
    unittest.main()


# ── read's fallback, wired in gateway.tools (the Browser Use side is in test_cloud.Dispatch) ──────
from gateway import tools  # noqa: E402
from gateway.cloud import CloudUnavailable  # noqa: E402


class FakeBB:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    async def read(self, url, *, reason, region=None):
        self.calls.append((url, reason, region))
        if self.fail:
            raise BrowserbaseUnavailable(self.fail)
        return {"engine": "browserbase", "reason": reason, "why": browserbase.REASONS[reason], "region": region or "us-west-2",
                "url": url, "final_url": url, "title": "From Browserbase", "links": ["https://example.com/a"],
                "text": "hosted text", "truncated": False, "seconds": 1.8, "session_id": "s"}

    async def status(self):
        return {"up": True, "configured": True, "hours_used": 0.3, "hours_cap": 100.0}


class FailingCloud:
    async def read(self, url, **_kw):
        raise CloudUnavailable("Browser Use is out of credit")


class ReadFallback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.patches = [mock.patch.object(tools, "safe_target", mock.AsyncMock(side_effect=lambda u: u))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def engines(self, bb, cloud=None):
        return mock.patch.object(tools, "browserbase_client", lambda: bb), mock.patch.object(tools, "cloud_client", lambda: cloud)

    async def test_engine_browserbase_goes_straight_there(self):
        bb = FakeBB()
        b, c = self.engines(bb, FailingCloud())
        with b, c:
            out = await tools.read({"url": "https://example.com/", "engine": "browserbase", "screenshot": True})
        self.assertEqual(out["fallback_reason"], "requested")
        self.assertIn("text and links only", out["screenshot_note"])

    async def test_a_region_implies_browserbase(self):
        bb = FakeBB()
        b, c = self.engines(bb)
        with b, c:
            out = await tools.read({"url": "https://example.com/", "region": "eu-central-1"})
        self.assertEqual(bb.calls, [("https://example.com/", "region", "eu-central-1")])
        self.assertEqual(out["region"], "eu-central-1")

    async def test_asking_for_browserbase_without_a_key_says_so(self):
        b, c = self.engines(None)
        with b, c, self.assertRaisesRegex(BrowserbaseUnavailable, "not configured"):
            await tools.read({"url": "https://example.com/", "engine": "browserbase"})

    async def test_when_both_fail_the_error_names_both(self):
        b, c = self.engines(FakeBB(fail="hours used up"), FailingCloud())
        with b, c, self.assertRaises(BrowserbaseUnavailable) as caught:
            await tools.read({"url": "https://example.com/"})
        self.assertIn("out of credit", str(caught.exception))
        self.assertIn("hours used up", str(caught.exception))

    def test_a_bot_wall_is_told_apart_from_a_page_about_captchas(self):
        self.assertFalse(tools.looks_blocked(200, "an article about captcha design " * 200))
        self.assertTrue(tools.looks_blocked(429, "anything"))


class StatusRow(unittest.IsolatedAsyncioTestCase):
    async def test_status_shows_browserbase_hours(self):
        with mock.patch.object(tools, "browserbase_client", lambda: FakeBB()), mock.patch.object(tools, "cloud_client", lambda: None):
            out = await tools.status({})
        (row,) = [c for c in out["components"] if c["name"].startswith("browserbase")]
        self.assertEqual((row["up"], row["detail"]["hours_used"]), (True, 0.3))
        self.assertIn("read", out["tools_working_now"])


class Card(unittest.TestCase):
    def test_read_offers_engine_and_region(self):
        props = next(c for c in tools.TOOLS if c["name"] == "read")["inputSchema"]["properties"]
        self.assertEqual(props["engine"]["enum"], ["auto", "browseruse", "browserbase"])
        self.assertEqual(props["region"]["enum"], list(browserbase.REGIONS))
