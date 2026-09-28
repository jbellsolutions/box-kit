"""The doors. What the server lets through, and how it answers, is the contract every caller relies on."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from data_box import config, fetch, server

AUTH = {"Authorization": f"Bearer {config.token()}"}
MCP = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def rpc(method, params=None, rid=1):
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    return body


async def fake_get(url, **_kw):
    fetch.require_public_web(url)
    html = f"<html><head><title>Page</title></head><body><h1>Hello</h1><a href='/a'>A</a><a href='/b'>B</a></body></html>"
    return fetch.Page(url=url, final_url=url, status_code=200, content_type="text/html", body=html.encode())


class Doors(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.build_app(Path(tempfile.mkdtemp())))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        patcher = mock.patch.object(fetch, "get", fake_get)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, tool, body):
        return self.client.post(f"/api/v1/{tool}", json=body, headers=AUTH)

    def mcp(self, method, params=None):
        return self.client.post("/mcp", json=rpc(method, params), headers={**MCP, **AUTH})

    def test_health_needs_no_token_and_says_nothing_about_providers(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["service"], "data-box")
        self.assertIn("revision", body)
        self.assertNotIn("firecrawl", json.dumps(body).lower())

    def test_every_door_wants_the_token(self):
        self.assertEqual(self.client.get("/api/v1/status").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/scrape", json={"url": "https://a.test"}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/tools", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/mcp", json=rpc("tools/list"), headers=MCP).status_code, 401)

    def test_mcp_lists_the_tools_this_box_offers(self):
        response = self.mcp("tools/list")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([t["name"] for t in response.json()["result"]["tools"]], ["status", "scrape", "job"])

    def test_bare_mcp_path_is_not_redirected(self):
        response = self.client.post("/mcp", json=rpc("tools/list"), headers={**MCP, **AUTH}, follow_redirects=False)
        self.assertEqual(response.status_code, 200)

    def test_scrape_over_http_and_mcp(self):
        body = self.post("scrape", {"url": "https://a.test/"}).json()
        self.assertEqual(body["status"], "succeeded")
        self.assertIn("# Hello", body["content"])
        self.assertEqual(body["cost_usd"], 0.0)
        result = self.mcp("tools/call", {"name": "scrape", "arguments": {"url": "https://a.test/", "format": "links"}})
        payload = json.loads(result.json()["result"]["content"][0]["text"])
        self.assertEqual(payload["links_count"], 2)

    def test_a_refusal_is_a_422_answer_and_starts_no_job(self):
        response = self.post("scrape", {"url": "http://0x7f000001/"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("loopback", response.json()["error"])
        self.assertNotIn("job_id", response.json())
        self.assertEqual(self.post("job", {"action": "list"}).json()["jobs"], [])

    def test_bad_arguments_name_the_problem(self):
        response = self.post("scrape", {"url": "https://a.test", "format": "pdf"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("format", response.json()["error"])
        self.assertEqual(self.post("scrape", {"nope": 1}).status_code, 422)

    def test_unknown_tool_and_bad_body(self):
        self.assertEqual(self.post("teleport", {}).status_code, 404)
        response = self.client.post("/api/v1/scrape", content=b"[1,2]", headers=AUTH)
        self.assertEqual(response.status_code, 400)

    def test_request_id_attaches_a_retry_to_the_first_job(self):
        first = self.post("scrape", {"url": "https://a.test/", "request_id": "same"}).json()
        second = self.post("scrape", {"url": "https://a.test/", "request_id": "same"}).json()
        self.assertEqual(first["job_id"], second["job_id"])
        clash = self.post("scrape", {"url": "https://b.test/", "request_id": "same"})
        self.assertEqual(clash.status_code, 422)

    def test_job_get_results_and_export(self):
        job_id = self.post("scrape", {"url": "https://a.test/", "format": "links"}).json()["job_id"]
        got = self.post("job", {"action": "get", "job_id": job_id}).json()
        self.assertEqual(got["status"], "succeeded")
        page = self.post("job", {"action": "results", "job_id": job_id, "limit": 1}).json()
        self.assertEqual((page["total"], len(page["items"])), (2, 1))
        csv_text = self.post("job", {"action": "export", "job_id": job_id, "format": "csv"}).json()["content"]
        self.assertTrue(csv_text.startswith("url,text"))
        self.assertEqual(self.post("job", {"action": "get"}).status_code, 422)
        self.assertEqual(self.post("job", {"action": "get", "job_id": "job_nope"}).status_code, 422)

    def test_status_reports_every_provider_and_recent_calls(self):
        self.post("scrape", {"url": "https://a.test/"})
        body = self.client.get("/api/v1/status", headers=AUTH).json()
        names = {c["name"] for c in body["components"]}
        for provider in config.PROVIDERS:
            self.assertIn(provider, names)
        self.assertEqual(body["tools_working_now"], ["status", "scrape", "job"])
        self.assertEqual(body["recent_calls"][0]["tool"], "scrape")
        firecrawl = next(c for c in body["components"] if c["name"] == "firecrawl")
        self.assertFalse(firecrawl["configured"])
        self.assertIn("FIRECRAWL_API_KEY", firecrawl["detail"])


class NoTokenNoServer(unittest.TestCase):
    def test_refuses_to_start_unauthenticated(self):
        with mock.patch.dict("os.environ", {"DATABOX_TOKEN": ""}):
            with self.assertRaises(SystemExit):
                server.build_app(Path(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
