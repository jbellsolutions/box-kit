import asyncio
import unittest
from contextlib import ExitStack, contextmanager
from unittest import mock

from gateway import guard, lock, steel, tools
from gateway.lock import LaneBusy
from gateway.security import UnsafeUrl


class FakeResponse:
    def __init__(self, url, status_code=200, text="", content_type="text/html", location=None):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location


class FakeClient:
    """Answers each requested URL from a script, so a redirect chain can be walked."""

    def __init__(self, pages):
        self.pages = pages
        self.requested: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def request(self, _method, url, **_kw):
        self.requested.append(str(url))
        try:
            return self.pages[str(url)]
        except KeyError:
            raise AssertionError(f"unscripted request to {url}") from None


def serving(pages):
    """Return a scripted client and a context manager that installs it.

    Only the client factory is patched — never the httpx module. Replacing tools.httpx with
    a Mock would make any other httpx attribute the code later reaches for (Timeout, Limits)
    silently return a Mock, so the tests would keep passing while production broke.
    """
    client = FakeClient(pages)
    patches = [
        mock.patch.object(tools.httpx, "AsyncClient", lambda *a, **k: client),
        mock.patch.object(tools, "require_public_addresses", lambda host: ["93.184.216.34"]),
    ]

    @contextmanager
    def installed():
        with ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            yield

    return client, installed()


class ToolCards(unittest.TestCase):
    def test_exactly_the_promised_surface(self):
        """Every tool that can exist has a handler, and nothing else does."""
        self.assertEqual([t["name"] for t in tools.TOOLS], ["fetch", "read", "session", "act", "computer", "task", "status"])
        self.assertEqual(set(tools.HANDLERS), {t["name"] for t in tools.TOOLS})

    def test_an_unconfigured_integration_is_not_listed(self):
        """A box without an Orgo key has no computers; listing one would be the lie this repo exists to stop."""
        with mock.patch.dict("os.environ", {"ORGO_API_KEY": ""}):
            self.assertEqual([t["name"] for t in tools.offered_tools()], ["fetch", "read", "session", "status"])
        with mock.patch.dict("os.environ", {"ORGO_API_KEY": "sk_live_test"}):
            self.assertEqual([t["name"] for t in tools.offered_tools()], ["fetch", "read", "session", "computer", "task", "status"])
        with mock.patch.dict("os.environ", {"BB_JEV_URL": "http://agent-jev:3111", "BB_JEV_TOKEN": "t"}):
            self.assertEqual([t["name"] for t in tools.offered_tools()], ["fetch", "read", "session", "act", "status"])
        with mock.patch.dict("os.environ", {"BB_JEV_URL": "http://agent-jev:3111", "BB_JEV_TOKEN": ""}):
            self.assertNotIn("act", [t["name"] for t in tools.offered_tools()])

    def test_every_card_says_when_not_to_use_it(self):
        for card in tools.TOOLS:
            if card["name"] == "status":
                continue
            self.assertIn("Do NOT", card["description"], card["name"])

    def test_schemas_are_closed_and_declare_their_required_fields(self):
        for card in tools.TOOLS:
            schema = card["inputSchema"]
            self.assertIs(schema["additionalProperties"], False, card["name"])
            for field in schema.get("required", []):
                self.assertIn(field, schema["properties"], card["name"])


class StripHtml(unittest.TestCase):
    def test_drops_script_and_style(self):
        html = "<html><head><style>b{color:red}</style><script>var x=1</script></head><body><h1>Hi</h1><p>There</p></body></html>"
        self.assertEqual(tools.strip_html(html), "Hi\nThere")

    def test_plain_text_passes_through(self):
        self.assertEqual(tools.strip_html("just words"), "just words")

    def test_bounded_marks_truncation_and_keeps_the_true_length(self):
        long = "x" * (tools.TEXT_LIMIT + 500)
        out = tools._bounded(long)
        self.assertEqual(out["text_chars"], len(long))
        self.assertTrue(out["text"].endswith("…"))
        self.assertLessEqual(len(out["text"]), tools.TEXT_LIMIT + 1)


class Fetch(unittest.IsolatedAsyncioTestCase):
    async def test_returns_readable_text(self):
        client, patched = serving({"https://example.com/": FakeResponse("https://example.com/", text="<html><body><p>Hello</p></body></html>")})
        with patched:
            out = await tools.fetch({"url": "https://example.com/"})
        self.assertEqual(out["status_code"], 200)
        self.assertEqual(out["text"], "Hello")
        self.assertEqual(out["final_url"], "https://example.com/")

    async def test_refuses_an_inward_url_before_any_request(self):
        client, patched = serving({})
        with patched:
            with self.assertRaises(UnsafeUrl):
                await tools.fetch({"url": "http://0x7f000001/"})
        self.assertEqual(client.requested, [])

    async def test_refuses_a_redirect_before_connecting_to_it(self):
        """Proven necessary live: a public page that 302s to 127.0.0.1 made the browser read
        Steel's own session list. Checking response.history is too late — the request happened."""
        client, patched = serving({
            "https://evil.example/": FakeResponse("https://evil.example/", status_code=302, location="http://127.0.0.1:3000/v1/sessions"),
        })
        with patched:
            with self.assertRaises(UnsafeUrl) as caught:
                await tools.fetch({"url": "https://evil.example/"})
        self.assertIn("redirected", str(caught.exception))
        self.assertEqual(client.requested, ["https://evil.example/"])

    async def test_follows_an_ordinary_redirect(self):
        client, patched = serving({
            "https://example.com/": FakeResponse("https://example.com/", status_code=301, location="/final"),
            "https://example.com/final": FakeResponse("https://example.com/final", text="<p>Arrived</p>"),
        })
        with patched:
            out = await tools.fetch({"url": "https://example.com/"})
        self.assertEqual(out["final_url"], "https://example.com/final")
        self.assertEqual(out["text"], "Arrived")

    async def test_refuses_an_endless_redirect_loop(self):
        client, patched = serving({"https://example.com/": FakeResponse("https://example.com/", status_code=302, location="https://example.com/")})
        with patched:
            with self.assertRaises(UnsafeUrl) as caught:
                await tools.fetch({"url": "https://example.com/"})
        self.assertIn("more than", str(caught.exception))

    async def test_refuses_a_public_name_that_resolves_inward(self):
        client, patched = serving({})
        def inward(host):
            raise UnsafeUrl(f"refused: {host} resolves to 10.0.0.5, which is private_network.")
        with patched, mock.patch.object(tools, "require_public_addresses", inward):
            with self.assertRaises(UnsafeUrl) as caught:
                await tools.fetch({"url": "https://looks-fine.example/"})
        self.assertIn("10.0.0.5", str(caught.exception))
        self.assertEqual(client.requested, [])


class Read(unittest.IsolatedAsyncioTestCase):
    async def test_shapes_a_steel_scrape_into_the_documented_result(self):
        payload = {
            "content": {"markdown": "# Title\nbody", "html": "<h1>Title</h1>"},
            "metadata": {"title": "Title", "statusCode": 200, "urlSource": "https://example.com/"},
            "links": [{"url": "https://example.com/a"}, {"text": "no url"}],
        }

        async def fake_scrape(url, **kw):
            return payload

        async def fake_shot(url, **kw):
            return b"ABC"

        attached = asyncio.Event()
        attached.set()
        client, patched = serving({"https://example.com/": FakeResponse("https://example.com/")})
        with patched, mock.patch.object(tools.steel, "scrape", fake_scrape), mock.patch.object(tools.steel, "screenshot", fake_shot), \
                mock.patch.object(guard.GUARD, "_attached", attached):
            out = await tools.read({"url": "https://example.com/", "screenshot": True})
        self.assertEqual(out["title"], "Title")
        self.assertEqual(out["status_code"], 200)
        self.assertEqual(out["links"], ["https://example.com/a"])
        self.assertEqual(out["text"], "# Title\nbody")
        self.assertEqual(out["screenshot_base64"], "QUJD")
        self.assertEqual(out["screenshot_media_type"], "image/jpeg")

    async def test_the_screenshot_is_withheld_while_the_guard_is_detached(self):
        """The picture is a second navigation only the in-browser guard can vet."""
        shots = []

        async def fake_scrape(url, **kw):
            return {"content": {"markdown": "text"}, "metadata": {}}

        async def fake_shot(url, **kw):
            shots.append(url)
            return b"ABC"

        client, patched = serving({"https://example.com/": FakeResponse("https://example.com/")})
        with patched, mock.patch.object(tools.steel, "scrape", fake_scrape), mock.patch.object(tools.steel, "screenshot", fake_shot), \
                mock.patch.object(guard.GUARD, "_attached", asyncio.Event()):
            out = await tools.read({"url": "https://example.com/", "screenshot": True})
        self.assertEqual(shots, [])
        self.assertEqual(out["text"], "text")
        self.assertIn("guard is not attached", out["screenshot_note"])

    async def test_no_screenshot_means_no_second_page_load(self):
        """The screenshot is a separate endpoint and a separate render; never pay for it silently."""
        async def fake_scrape(url, **kw):
            return {"content": {"markdown": "body"}, "metadata": {}, "links": []}

        async def fake_shot(url, **kw):
            raise AssertionError("screenshot endpoint must not be called")

        client, patched = serving({"https://example.com/": FakeResponse("https://example.com/")})
        with patched, mock.patch.object(tools.steel, "scrape", fake_scrape), mock.patch.object(tools.steel, "screenshot", fake_shot):
            out = await tools.read({"url": "https://example.com/"})
        self.assertNotIn("screenshot_base64", out)

    async def test_refuses_an_inward_url_without_taking_the_lane(self):
        async def fake(url, **kw):
            raise AssertionError("steel must not be called")

        client, patched = serving({})
        with patched, mock.patch.object(tools.steel, "scrape", fake):
            with self.assertRaises(UnsafeUrl):
                await tools.read({"url": "http://169.254.169.254/latest/meta-data/"})

    async def test_hands_steel_the_cleared_final_url_not_the_one_asked_for(self):
        """Steel echoes the request URL back as urlSource, so the browser's own landing
        address is invisible from here. Pre-flighting the chain is the only control there is."""
        seen = {}

        async def fake_scrape(url, **kw):
            seen["url"] = url
            return {"content": {"markdown": "arrived"}, "metadata": {}, "links": []}

        client, patched = serving({
            "https://example.com/": FakeResponse("https://example.com/", status_code=302, location="https://example.com/final"),
            "https://example.com/final": FakeResponse("https://example.com/final"),
        })
        with patched, mock.patch.object(tools.steel, "scrape", fake_scrape):
            out = await tools.read({"url": "https://example.com/"})
        self.assertEqual(seen["url"], "https://example.com/final")
        self.assertEqual(out["final_url"], "https://example.com/final")

    async def test_never_lets_the_browser_see_a_redirect_into_a_private_target(self):
        async def fake_scrape(url, **kw):
            raise AssertionError(f"the browser must never be handed {url}")

        client, patched = serving({
            "https://httpbin.example/redirect": FakeResponse("https://httpbin.example/redirect", status_code=302, location="http://127.0.0.1:3000/v1/sessions"),
        })
        with patched, mock.patch.object(tools.steel, "scrape", fake_scrape):
            with self.assertRaises(UnsafeUrl):
                await tools.read({"url": "https://httpbin.example/redirect"})


class Session(unittest.IsolatedAsyncioTestCase):
    async def test_create_reports_what_this_box_actually_serves(self):
        """sessionViewerUrl points at a UI image we do not run; reporting it would be a lie."""
        async def fake(**kw):
            return {"id": "abc", "status": "live", "debuggerUrl": "http://localhost:3000/v1/devtools/inspector.html",
                    "sessionViewerUrl": "http://localhost:3000/"}

        with mock.patch.object(tools.steel, "create_session", fake):
            out = await tools.session({"action": "create"})
        self.assertEqual(out["session_id"], "abc")
        self.assertIn("devtools", out["devtools_url"])
        self.assertNotIn("live_view_url", out)
        self.assertIn("ssh -L", out["note"])

    async def test_list_is_flattened_and_trimmed(self):
        async def fake():
            return {"sessions": [{"id": "abc", "status": "live", "createdAt": "2026-09-22T19:12:20.450Z",
                                  "duration": 304, "userAgent": "...", "websocketUrl": "..."}]}

        with mock.patch.object(tools.steel, "sessions", fake):
            out = await tools.session({"action": "list"})
        self.assertEqual(out["sessions"], [{"session_id": "abc", "status": "live",
                                            "created_at": "2026-09-22T19:12:20.450Z", "duration_ms": 304}])


class SessionLane(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_release_wait_for_the_browser_lane(self):
        """Both relaunch Steel's Chromium, which would kill a read or act mid-step."""
        async def never(*_a, **_k):
            raise AssertionError("steel was called while another job held the lane")
        with mock.patch.object(tools.steel, "create_session", never), mock.patch.object(tools.steel, "release_session", never), \
                mock.patch.object(lock, "WAIT_SECONDS", 0.2):
            async with tools.lane(label="an act"):
                with self.assertRaises(LaneBusy):
                    await tools.session({"action": "create"})
                with self.assertRaises(LaneBusy):
                    await tools.session({"action": "release", "session_id": "s1"})


class Status(unittest.IsolatedAsyncioTestCase):
    async def test_reports_the_browser_as_down_with_the_reason(self):
        """The failure this whole repo exists to prevent: a capability report that lies."""
        async def broken():
            raise steel.SteelUnavailable("steel is unreachable at http://steel:3000")
        with mock.patch.object(tools.steel, "health", broken):
            out = await tools.status({})
        self.assertFalse(out["components"][0]["up"])
        self.assertEqual(out["tools_working_now"], ["fetch", "status"])
        self.assertEqual({item["tool"] for item in out["tools_unavailable"]}, {"read", "session"})
        self.assertIn("unreachable", out["tools_unavailable"][0]["reason"])

    async def test_reports_every_tool_when_the_browser_is_up(self):
        async def ok():
            return {"status": "ok"}
        with mock.patch.object(tools.steel, "health", ok):
            out = await tools.status({})
        self.assertTrue(out["components"][0]["up"])
        self.assertEqual(out["tools_working_now"], [t["name"] for t in tools.offered_tools()])
        self.assertEqual(out["tools_unavailable"], [])

    async def test_survives_a_broken_lane_lock(self):
        """status is what you call when something else already failed; it must not fail too."""
        async def ok():
            return {"status": "ok"}

        def broken(*_a, **_k):
            raise PermissionError(13, "Permission denied", "/lane/lane.lock")

        with mock.patch.object(tools.steel, "health", ok), mock.patch.object(tools, "lane", broken):
            out = await tools.status({})
        self.assertIn("unusable", out["browser_lane"])
        self.assertEqual(out["tools_working_now"], ["fetch", "status"])

    async def test_reports_the_lane_as_busy_while_a_job_holds_it(self):
        async def ok():
            return {"status": "ok"}
        with mock.patch.object(tools.steel, "health", ok):
            async with tools.lane(label="a job"):
                out = await tools.status({})
        self.assertIn("busy", out["browser_lane"])


if __name__ == "__main__":
    unittest.main()
