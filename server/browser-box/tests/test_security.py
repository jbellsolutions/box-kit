import unittest

from unittest import mock

from gateway import security
from gateway.security import UnsafeUrl, require_public_addresses, require_public_web, target_scope, validate_url


class ValidateUrl(unittest.TestCase):
    def test_accepts_ordinary_https(self):
        self.assertEqual(validate_url(" https://example.com/a "), "https://example.com/a")

    def test_rejects_empty_and_non_string(self):
        for bad in (None, "", "   ", 7):
            with self.assertRaises(ValueError):
                validate_url(bad)

    def test_rejects_other_schemes(self):
        for bad in ("file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "data:text/html,x"):
            with self.assertRaises(ValueError):
                validate_url(bad)

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            validate_url("https://user:pass@example.com")

    def test_rejects_whitespace_and_missing_scheme(self):
        with self.assertRaises(ValueError):
            validate_url("https://example.com/a b")
        with self.assertRaises(ValueError):
            validate_url("example.com")


class TargetScope(unittest.TestCase):
    def test_public_web(self):
        for url in ("https://example.com", "http://1.1.1.1", "https://news.ycombinator.com/news"):
            self.assertEqual(target_scope(url), "public_web", url)

    def test_obfuscated_loopback_is_not_public(self):
        """The whole reason this module exists: browsers accept all four, ip_address accepts none."""
        for url in ("http://127.0.0.1", "http://0x7f000001/", "http://2130706433/", "http://127.1/", "http://localhost:3000"):
            self.assertEqual(target_scope(url), "loopback", url)

    def test_cloud_metadata_is_link_local(self):
        self.assertEqual(target_scope("http://169.254.169.254/latest/meta-data/"), "link_local")

    def test_neighbouring_services_are_private(self):
        for url in ("http://10.0.0.5", "http://192.168.1.1", "http://172.16.0.9", "http://steel:3000", "http://db.internal/x"):
            self.assertEqual(target_scope(url), "private_network", url)

    def test_file_and_garbage(self):
        self.assertEqual(target_scope("file:///etc/passwd"), "local_file")
        self.assertEqual(target_scope(""), "none")
        self.assertEqual(target_scope(None), "none")


class RequirePublicWeb(unittest.TestCase):
    def test_passes_public(self):
        self.assertEqual(require_public_web("https://example.com"), "https://example.com")

    def test_refuses_everything_inward(self):
        for url in ("http://0x7f000001/", "http://169.254.169.254/", "http://10.0.0.5/", "http://steel:3000/scrape"):
            with self.assertRaises(UnsafeUrl, msg=url):
                require_public_web(url)

    def test_refusal_names_the_scope(self):
        with self.assertRaises(UnsafeUrl) as caught:
            require_public_web("http://2130706433/")
        self.assertIn("loopback", str(caught.exception))


class ResolvedAddresses(unittest.TestCase):
    """Scope-by-name is not enough: a perfectly ordinary public name can A-record inward."""

    def resolving_to(self, *addresses):
        return mock.patch.object(
            security.socket, "getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", (addr, 0)) for addr in addresses],
        )

    def test_public_addresses_pass(self):
        with self.resolving_to("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"):
            self.assertEqual(len(require_public_addresses("example.com")), 2)

    def test_any_inward_address_refuses_the_whole_name(self):
        for address in ("10.0.0.5", "127.0.0.1", "169.254.169.254", "192.168.1.1", "172.16.0.9"):
            with self.resolving_to(address):
                with self.assertRaises(UnsafeUrl, msg=address):
                    require_public_addresses("looks-fine.example")

    def test_a_split_answer_is_still_refused(self):
        """One public A record does not launder a second one pointing at the metadata service."""
        with self.resolving_to("93.184.216.34", "169.254.169.254"):
            with self.assertRaises(UnsafeUrl):
                require_public_addresses("looks-fine.example")

    def test_a_name_that_does_not_resolve_is_refused_not_guessed(self):
        def fails(*_a, **_k):
            raise security.socket.gaierror(8, "nodename nor servname provided")
        with mock.patch.object(security.socket, "getaddrinfo", fails):
            with self.assertRaises(UnsafeUrl):
                require_public_addresses("nowhere.invalid")

    def test_no_host_is_refused(self):
        with self.assertRaises(UnsafeUrl):
            require_public_addresses(None)



class SharedVectors(unittest.TestCase):
    """The same file drives the TypeScript guard in jev-automation. Both must agree on every line."""

    def test_every_vector(self):
        import json
        from pathlib import Path

        vectors = json.loads((Path(__file__).parent / "scope_vectors.json").read_text())["vectors"]
        self.assertGreater(len(vectors), 25)
        for url, expected in vectors:
            self.assertEqual(target_scope(url), expected, url)

    def test_the_typescript_copy_is_byte_identical_when_present(self):
        import os
        from pathlib import Path

        root = os.getenv("JEV_AUTOMATION_DIR")
        if not root:
            self.skipTest("set JEV_AUTOMATION_DIR to check the copy in jev-automation")
        ours = (Path(__file__).parent / "scope_vectors.json").read_bytes()
        theirs = (Path(root) / "test" / "scope-vectors.json").read_bytes()
        self.assertEqual(ours, theirs, "the two scope-vector files have drifted")


if __name__ == "__main__":
    unittest.main()
