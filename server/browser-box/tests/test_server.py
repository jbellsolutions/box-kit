import json
import unittest

from starlette.testclient import TestClient

from gateway import server, tools

TOKEN = server.TOKEN
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def rpc(method, params=None, rid=1):
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    return body


class Door(unittest.TestCase):
    """The gateway is the only thing exposed. What it lets through is the security boundary."""

    def setUp(self):
        self.client = TestClient(server.build_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_health_is_liveness_only_and_needs_no_token(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body, {"ok": True, "service": "browser-box"})
        # Liveness must never leak what is configured or what is up.
        self.assertNotIn("steel", json.dumps(body).lower())

    def test_status_requires_the_token(self):
        self.assertEqual(self.client.get("/status").status_code, 401)
        self.assertEqual(self.client.get("/status", headers={"Authorization": "Bearer wrong"}).status_code, 401)

    def test_mcp_requires_the_token(self):
        response = self.client.post("/mcp", json=rpc("tools/list"), headers=MCP_HEADERS)
        self.assertEqual(response.status_code, 401)
        response = self.client.post("/mcp", json=rpc("tools/list"), headers={**MCP_HEADERS, "Authorization": "Bearer nope"})
        self.assertEqual(response.status_code, 401)

    def test_tools_list_is_what_this_box_can_do(self):
        response = self.client.post(
            "/mcp", json=rpc("tools/list"), headers={**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}
        )
        self.assertEqual(response.status_code, 200)
        listed = [t["name"] for t in response.json()["result"]["tools"]]
        # tests/__init__ clears every engine key: with no hosted browser, only fetch and status can work.
        self.assertEqual(listed, ["fetch", "status"])

    def test_bare_mcp_path_is_served_without_a_redirect(self):
        """Clients are configured with .../mcp; a 307 on a streaming POST is a coin flip."""
        response = self.client.post(
            "/mcp",
            json=rpc("tools/list"),
            headers={**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)

    def test_a_refusal_comes_back_as_an_answer_not_a_crash(self):
        """The model has to read the reason and pick another route; an exception tells it nothing."""
        response = self.client.post(
            "/mcp",
            json=rpc("tools/call", {"name": "fetch", "arguments": {"url": "http://0x7f000001/"}}, rid=2),
            headers={**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"},
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertFalse(result.get("isError", False))
        body = json.loads(result["content"][0]["text"])
        self.assertIn("loopback", body["error"])
        self.assertEqual(body["tool"], "fetch")


class NoTokenNoServer(unittest.TestCase):
    def test_refuses_to_start_unauthenticated(self):
        """An open browser endpoint on the public internet is not a degraded mode; it is a breach."""
        original = server.TOKEN
        server.TOKEN = ""
        try:
            with self.assertRaises(SystemExit):
                server.build_app()
        finally:
            server.TOKEN = original


if __name__ == "__main__":
    unittest.main()


class HttpDoor(unittest.TestCase):
    """The HTTP/JSON door is the same tools behind the same token."""

    def setUp(self):
        self.client = TestClient(server.build_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.auth = {"Authorization": f"Bearer {TOKEN}"}

    def test_every_route_but_the_spec_needs_the_token(self):
        self.assertEqual(self.client.post("/api/v1/fetch", json={"url": "https://example.com"}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/status", headers={"Authorization": "Bearer nope"}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/tools").status_code, 401)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)

    def test_a_refusal_is_422_with_the_reason(self):
        response = self.client.post("/api/v1/fetch", json={"url": "http://0x7f000001/"}, headers=self.auth)
        self.assertEqual(response.status_code, 422)
        self.assertIn("loopback", response.json()["error"])

    def test_a_tool_this_box_lacks_is_404_and_an_unknown_one_too(self):
        self.assertEqual(self.client.post("/api/v1/act", json={"command": "scroll down"}, headers=self.auth).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/rm", json={}, headers=self.auth).status_code, 404)

    def test_a_body_that_is_not_an_object_is_400(self):
        response = self.client.post("/api/v1/fetch", content=b"[1]", headers={**self.auth, "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 400)

    def test_tools_lists_what_mcp_lists(self):
        listed = [t["name"] for t in self.client.get("/api/v1/tools", headers=self.auth).json()["tools"]]
        self.assertEqual(listed, [t["name"] for t in tools.offered_tools()])

    def test_the_spec_covers_every_tool_with_its_own_schema(self):
        spec = self.client.get("/openapi.json").json()
        for card in tools.TOOLS:
            if card["name"] == "status":
                self.assertIn("get", spec["paths"]["/api/v1/status"])
                continue
            op = spec["paths"][f"/api/v1/{card['name']}"]["post"]
            self.assertEqual(op["requestBody"]["content"]["application/json"]["schema"], card["inputSchema"])
        self.assertNotIn("{surfaces}", json.dumps(spec))

    def test_the_committed_spec_is_current(self):
        """docs/openapi.json is what the CLI is generated from: it must match the code."""
        from pathlib import Path
        from gateway import rest
        committed = json.loads((Path(__file__).resolve().parents[1] / "docs" / "openapi.json").read_text())
        self.assertEqual(committed, rest.openapi(), "run: make openapi")
