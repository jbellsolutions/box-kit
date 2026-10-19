import asyncio
import unittest
from contextlib import ExitStack, contextmanager
from unittest import mock

from gateway import tools
from gateway.cloud import CloudUnavailable
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
        def listed(**env):
            with mock.patch.dict("os.environ", env):
                return [t["name"] for t in tools.offered_tools()]
        self.assertEqual(listed(), ["fetch", "status"])
        self.assertEqual(listed(ORGO_API_KEY="sk_live_test"), ["fetch", "computer", "task", "status"])
        self.assertEqual(listed(BROWSER_USE_API_KEY="bu_test"), ["fetch", "read", "session", "status"])
        self.assertEqual(listed(BROWSER_USE_API_KEY="bu_test", TYPESAFE_API_KEY="t"), ["fetch", "read", "session", "act", "status"])
        self.assertEqual(listed(BROWSERBASE_API_KEY="bb_test"), ["fetch", "read", "status"])
        self.assertEqual(listed(TYPESAFE_API_KEY="t"), ["fetch", "status"], "act needs a browser as well as Jev")

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
    async def test_refuses_an_inward_url_before_any_browser_opens(self):
        cloud = mock.Mock(read=mock.AsyncMock(side_effect=AssertionError("no browser for an inward URL")))
        with mock.patch.object(tools, "cloud_client", lambda: cloud), mock.patch.object(tools, "browserbase_client", lambda: None):
            for url in ("http://127.0.0.1:8080/status", "http://0x7f000001/", "http://169.254.169.254/latest/meta-data"):
                with self.assertRaises(UnsafeUrl):
                    await tools.read({"url": url})

    async def test_a_session_read_needs_browser_use(self):
        with mock.patch.object(tools, "cloud_client", lambda: None), self.assertRaises(ValueError):
            await tools.read({"url": "https://example.com/", "session_id": "s1"})


class FakeCloud:
    """Opens a fake browser; counts what was opened and stopped."""

    def __init__(self):
        self.opened = self.stopped = 0

    def browser(self, **kw):
        from contextlib import asynccontextmanager
        test = self
        assert "profile_id" not in kw, "a session must never carry a profile"

        @asynccontextmanager
        async def cm():
            test.opened += 1
            cdp = mock.Mock(page=mock.AsyncMock(return_value="p"), reader=mock.Mock(done=lambda: False))
            try:
                yield cdp, {"session_id": f"br-{test.opened}", "live_url": f"https://live.example/{test.opened}"}
            finally:
                test.stopped += 1
        return cm()


class Session(unittest.IsolatedAsyncioTestCase):
    def store(self):
        from gateway.sessions import Sessions
        cloud = FakeCloud()
        store = Sessions(cloud)
        return store, cloud, mock.patch.object(tools, "sessions_store", lambda: store)

    async def test_create_opens_a_fresh_browser_of_its_own(self):
        store, cloud, patched = self.store()
        with patched:
            a = await tools.session({"action": "create", "name": "agent a"})
            b = await tools.session({"action": "create"})
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertEqual((cloud.opened, a["live_url"]), (2, "https://live.example/1"))
        await store.close_all()

    async def test_release_closes_the_browser_and_forgets_the_session(self):
        store, cloud, patched = self.store()
        with patched:
            made = await tools.session({"action": "create"})
            out = await tools.session({"action": "release", "session_id": made["session_id"]})
            self.assertEqual((out["was_open"], cloud.stopped), (True, 1))
            with self.assertRaises(ValueError):
                await tools.session({"action": "release", "session_id": made["session_id"]})

    async def test_there_is_no_login_or_delete_action(self):
        card = next(t for t in tools.TOOLS if t["name"] == "session")
        self.assertEqual(card["inputSchema"]["properties"]["action"]["enum"], ["create", "list", "release"])

    async def test_without_browser_use_there_are_no_sessions(self):
        with mock.patch.object(tools, "sessions_store", lambda: None), self.assertRaises(CloudUnavailable):
            await tools.session({"action": "list"})

    async def test_a_busy_session_answers_busy_instead_of_hanging(self):
        store, _, patched = self.store()
        held = store.create()
        await held.lock.acquire()
        with patched, mock.patch.object(tools, "SESSION_WAIT", 0.05), mock.patch.object(tools, "hosted_act", lambda: True), \
                self.assertRaises(ValueError) as caught:
            await tools.act({"command": "scroll down", "session_id": held.session_id})
        self.assertIn("busy", str(caught.exception))


class Status(unittest.IsolatedAsyncioTestCase):
    def engines(self, cloud_row=None, bb_row=None):
        cloud = mock.Mock(status=mock.AsyncMock(return_value=dict(cloud_row))) if cloud_row else None
        bb = mock.Mock(status=mock.AsyncMock(return_value=dict(bb_row))) if bb_row else None
        return mock.patch.object(tools, "cloud_client", lambda: cloud), mock.patch.object(tools, "browserbase_client", lambda: bb)

    async def test_nothing_configured_offers_fetch_and_says_what_to_set(self):
        c, b = self.engines()
        with c, b:
            out = await tools.status({})
        self.assertEqual((out["tools_working_now"], out["tools_unavailable"]), (["fetch", "status"], []))
        row = next(r for r in out["components"] if r["name"].startswith("browser-use cloud"))
        self.assertIn("BROWSER_USE_API_KEY", row["detail"])

    async def test_with_browser_use_up_the_browser_tools_work(self):
        c, b = self.engines({"up": True, "balance_usd": 5})
        with c, b:
            out = await tools.status({})
        self.assertEqual(out["tools_working_now"], ["fetch", "read", "session", "status"])

    async def test_browser_use_down_takes_its_tools_down_with_the_reason(self):
        c, b = self.engines({"up": False, "problem": "out of credit"})
        with c, b:
            out = await tools.status({})
        self.assertEqual(out["tools_working_now"], ["fetch", "status"])
        self.assertTrue(all("not usable" in u["reason"] or "no hosted" in u["reason"] for u in out["tools_unavailable"]))

    async def test_browserbase_keeps_read_working_when_browser_use_is_down(self):
        c, b = self.engines({"up": False, "problem": "out of credit"}, {"up": True})
        with c, b:
            out = await tools.status({})
        self.assertIn("read", out["tools_working_now"])
        self.assertNotIn("session", out["tools_working_now"])
