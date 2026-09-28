"""Rung 0 against a real local HTTP server. Hosts ending in .test "resolve" to it, so the pinning,
the hand-walked redirects and the byte cap are exercised over a real socket; every other host is
refused as if it resolved inward."""
import asyncio
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from data_box import fetch
from data_box.security import UnsafeUrl

PAGES = {
    "/": (200, "text/html; charset=utf-8",
          "<html><head><title> Acme  Tools </title><meta name='description' content='We sell tools'>"
          "<script>var x=1</script></head><body><h1>Acme</h1><p>Hammers and <a href='/saws'>saws</a>.</p>"
          "<ul><li>One</li><li>Two</li></ul><a href='https://other.test/x'>Other</a></body></html>"),
    "/json": (200, "application/json", '{"ok": true}'),
    "/forbidden": (403, "text/html", "<html><body>no</body></html>"),
    "/missing": (404, "text/html", "<html><body><h1>Not found</h1></body></html>"),
    "/challenge": (200, "text/html", "<html><head><title>Just a moment...</title></head><body>checking</body></html>"),
    "/shell": (200, "text/html", "<html><head><script src=a.js></script><script src=b.js></script><script src=c.js>"
                                 "</script></head><body><div id=\"root\"></div></body></html>"),
    "/big": (200, "text/plain", "x" * 50_000),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = self.path
        if path.startswith("/to-private"):
            return self._redirect("http://127.0.0.1/")
        if path.startswith("/to-other"):
            return self._redirect(f"http://other.test:{self.server.server_port}/")
        if path.startswith("/loop"):
            return self._redirect("/loop")
        if path == "/host":
            return self._send(200, "text/plain", self.headers.get("Host", ""))
        status, ctype, body = PAGES.get(path, (404, "text/plain", "nope"))
        self._send(status, ctype, body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, status, ctype, body):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def fake_resolve(host):
    if host and host.endswith(".test"):
        return ["127.0.0.1"]
    raise UnsafeUrl(f"refused: {host} resolves inward")


class Rung0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        patches = [mock.patch.object(fetch, "require_public_addresses", fake_resolve),
                   mock.patch.object(fetch, "STANDARD_PORTS", {None, 80, 443, self.port})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def url(self, path, host="site.test"):
        return f"http://{host}:{self.port}{path}"

    def get(self, path, **kw):
        return asyncio.run(fetch.get(self.url(path), **kw))

    def test_reads_title_description_markdown_and_links(self):
        page = self.get("/")
        reading = fetch.read(page)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(reading.title, "Acme Tools")
        self.assertEqual(reading.description, "We sell tools")
        self.assertIn("# Acme", reading.markdown)
        self.assertIn("[saws](http://site.test:%d/saws)" % self.port, reading.markdown)
        self.assertIn("- One", reading.markdown)
        self.assertNotIn("var x", reading.text)
        self.assertEqual([link["text"] for link in reading.links], ["saws", "Other"])
        self.assertIsNone(fetch.judge(page, reading))

    def test_the_connection_is_pinned_but_carries_the_real_host(self):
        self.assertEqual(self.get("/host").body.decode(), f"site.test:{self.port}")

    def test_follows_a_public_redirect_by_hand(self):
        page = self.get("/to-other")
        self.assertEqual(page.final_url, self.url("/", "other.test"))
        self.assertEqual(len(page.hops), 1)

    def test_a_redirect_inward_is_refused_before_it_is_fetched(self):
        with self.assertRaises(UnsafeUrl) as caught:
            self.get("/to-private")
        self.assertIn("redirected to http://127.0.0.1/", str(caught.exception))

    def test_a_redirect_loop_ends(self):
        with self.assertRaises(UnsafeUrl):
            self.get("/loop")

    def test_the_body_is_capped(self):
        page = self.get("/big", max_bytes=1000)
        self.assertEqual(len(page.body), 1000)
        self.assertTrue(page.truncated)

    def test_non_html_passes_through(self):
        reading = fetch.read(self.get("/json"))
        self.assertEqual(reading.text, '{"ok": true}')

    def test_ipv4_is_tried_before_ipv6(self):
        self.assertEqual(fetch.connect_order(["2600:1f18::1", "54.1.2.3", "3.4.5.6"]), ["54.1.2.3", "3.4.5.6", "2600:1f18::1"])

    def test_an_address_that_does_not_answer_falls_through_to_the_next_checked_one(self):
        # 2001:db8::1 is the documentation range: it never answers, so the fetch must move on to IPv4.
        with mock.patch.object(fetch, "require_public_addresses", lambda host: ["2001:db8::1", "127.0.0.1"]), \
                mock.patch.object(fetch, "connect_order", lambda addrs: addrs):
            page = asyncio.run(fetch.get(self.url("/"), timeout=2))
        self.assertEqual(page.status_code, 200)

    def test_no_answering_address_is_a_named_failure(self):
        with mock.patch.object(fetch, "require_public_addresses", lambda host: ["2001:db8::1"]):
            with self.assertRaises(ConnectionError) as caught:
                asyncio.run(fetch.get(self.url("/"), timeout=1))
        self.assertIn("2001:db8::1", str(caught.exception))

    def test_a_non_standard_port_is_refused(self):
        with mock.patch.object(fetch, "STANDARD_PORTS", {None, 80, 443}):
            with self.assertRaises(UnsafeUrl):
                self.get("/")


class Judge(unittest.TestCase):
    def verdict(self, status, body, ctype="text/html"):
        page = fetch.Page(url="https://x.test", final_url="https://x.test", status_code=status, content_type=ctype,
                          body=body.encode())
        return fetch.judge(page, fetch.read(page))

    def test_block_statuses(self):
        self.assertEqual(self.verdict(403, "<html><body>no</body></html>")["kind"], "blocked")
        self.assertEqual(self.verdict(429, "slow down", "text/plain")["kind"], "blocked")

    def test_not_found_is_an_answer_not_a_block(self):
        self.assertIsNone(self.verdict(404, "<html><body><h1>Not found</h1></body></html>"))

    def test_challenge_page(self):
        self.assertEqual(self.verdict(200, PAGES["/challenge"][2])["kind"], "challenge")

    def test_javascript_shell(self):
        self.assertEqual(self.verdict(200, PAGES["/shell"][2])["kind"], "needs_javascript")

    def test_a_short_real_page_is_the_real_page(self):
        self.assertIsNone(self.verdict(200, "<html><body><h1>Example Domain</h1><p>Short.</p></body></html>"))

    def test_server_error(self):
        self.assertEqual(self.verdict(502, "<html>bad gateway</html>")["kind"], "http_error")


if __name__ == "__main__":
    unittest.main()
