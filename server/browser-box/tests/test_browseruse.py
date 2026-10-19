"""task(surface="browser"), tested through httpx's real request builder over a mock transport.
Each task gets a hosted browser of its own (faked here). The property that matters most: the agent
is stopped before its browser is, whether the caller gave up or the call failed."""
import asyncio
import json
import unittest
from unittest import mock

import httpx

from contextlib import asynccontextmanager

from gateway import browseruse, orgo, server, tools
from gateway.browseruse import BrowserUseUnavailable

ENV = {"BB_BROWSERUSE_URL": "http://agent-browseruse:3120", "BB_BROWSERUSE_TOKEN": "bu-test-token"}
DONE = {"status": "done", "answer": "GPT-6 Sol and Luna, 646 comments", "steps_taken": 3, "steps": [],
        "urls": ["https://news.ycombinator.com/"], "final_url": "https://news.ycombinator.com/item?id=1",
        "tokens": {"prompt": 32779, "completion": 1329, "cached": 0}, "estimated_cost_usd": 0.005581}


class FakeCloud:
    """A hosted browser per task; records whether the agent was still running when it was stopped."""

    def __init__(self):
        self.open, self.opened, self.profiles = 0, 0, []
        self.agent = None
        self.running_at_stop: list[bool] = []

    @asynccontextmanager
    async def hosted(self, *, proxy=None, minutes=None, **kw):
        profile_id = kw.get("profile_id")
        self.open += 1
        self.opened += 1
        self.profiles.append(profile_id)
        try:
            yield f"wss://browser-{self.opened}.example/devtools/browser/x", {"session_id": f"br-{self.opened}"}
        finally:
            self.running_at_stop.append(bool(self.agent and not self.agent.release.is_set() and self.agent.hang))
            self.open -= 1

    async def status(self):
        return {"up": True}


class Agent:
    """A fake agent-browseruse. /task answers `task_answer`, or hangs until released; /cancel
    records which task it was asked to stop."""

    def __init__(self, task_answer=None, hang=False):
        self.task_answer = task_answer if task_answer is not None else DONE
        self.hang = hang
        self.release = asyncio.Event()
        self.task_arrived = asyncio.Event()
        self.seen: list[httpx.Request] = []
        self.cancelled_ids: list = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.url.path == "/api/task":
            self.task_arrived.set()
            if self.hang:
                await self.release.wait()
            status, body = self.task_answer if isinstance(self.task_answer, tuple) else (200, self.task_answer)
            return httpx.Response(status, json=body)
        if request.url.path == "/api/cancel":
            self.cancelled_ids.append(json.loads(request.content or b"{}").get("task_id"))
            self.release.set()
            return httpx.Response(200, json={"cancelled": True})
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"ok": True, "busy": False, "model": "z-ai/glm-5.3-flash", "llm_key": True,
                                             "self_check": "ok", "browser": "reachable"})
        return httpx.Response(404, json={"error": "no such route"})

    def paths(self):
        return [r.url.path for r in self.seen]


def serving(agent):
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(agent)
        return real(*args, **kwargs)

    return mock.patch.object(browseruse.httpx, "AsyncClient", client)


class Setup(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cloud = FakeCloud()
        for patch in (mock.patch.dict("os.environ", ENV), mock.patch.object(tools, "cloud_client", lambda: self.cloud),
                      mock.patch.object(tools, "browserbase_client", lambda: None)):
            patch.start()
            self.addCleanup(patch.stop)


class Task(Setup):
    async def test_hands_the_goal_and_its_own_browser_over_with_the_token(self):
        agent = Agent()
        with serving(agent):
            out = await tools.task({"goal": "top HN story and its comment count", "max_steps": 8, "timeout_seconds": 120})
        request = agent.seen[0]
        body = json.loads(request.content)
        self.assertEqual((request.method, request.url.path), ("POST", "/api/task"))
        self.assertEqual((body["goal"], body["max_steps"], body["timeout_seconds"]), ("top HN story and its comment count", 8, 120))
        self.assertEqual(body["cdp_url"], "wss://browser-1.example/devtools/browser/x")
        self.assertEqual(request.headers["authorization"], "Bearer bu-test-token")
        self.assertEqual((out["surface"], out["status"], out["answer"], out["engine"]), ("browser", "done", DONE["answer"], "browseruse"))
        self.assertEqual(self.cloud.open, 0, "the task's browser was not stopped")

    async def test_the_only_configured_surface_is_the_default(self):
        agent = Agent()
        with serving(agent):
            out = await tools.task({"goal": "anything"})
        self.assertEqual(out["surface"], "browser")
        self.assertEqual(json.loads(agent.seen[0].content)["max_steps"], 25)

    async def test_its_cost_shows_in_status(self):
        with serving(Agent()), mock.patch.object(tools, "_CALLS", []):
            await tools.task({"goal": "anything"})
            out = await tools.status({})
        self.assertEqual(out["recent_calls"][0]["cost_usd"], DONE["estimated_cost_usd"])
        self.assertEqual(out["model_spend_recent_usd"], DONE["estimated_cost_usd"])

    async def test_tasks_run_side_by_side_each_in_its_own_browser(self):
        agent = Agent(hang=True)
        with serving(agent):
            calls = [asyncio.create_task(tools.task({"goal": f"job {n}"})) for n in range(3)]
            for _ in range(50):
                if self.cloud.open == 3:
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(self.cloud.open, 3, "tasks queued instead of running at once")
            agent.release.set()
            await asyncio.gather(*calls)
        self.assertEqual(len({json.loads(r.content)["cdp_url"] for r in agent.seen if r.url.path == "/api/task"}), 3)

    async def test_a_caller_that_gives_up_stops_the_agent_before_its_browser(self):
        """An MCP client that times out cancels this handler; the agent must not be left driving a dead browser."""
        agent = Agent(hang=True)
        self.cloud.agent = agent
        with serving(agent):
            call = asyncio.create_task(tools.task({"goal": "something long"}))
            await asyncio.wait_for(agent.task_arrived.wait(), 5)
            call.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await call
        task_id = json.loads(agent.seen[0].content)["task_id"]
        self.assertEqual(agent.cancelled_ids, [task_id])
        self.assertEqual(self.cloud.running_at_stop, [False], "the browser was stopped while the agent still ran")

    async def test_a_task_never_carries_a_profile_or_a_session(self):
        props = next(t for t in tools.TOOLS if t["name"] == "task")["inputSchema"]["properties"]
        self.assertNotIn("session_id", props)
        with serving(Agent()):
            await tools.task({"goal": "anything"})
        self.assertEqual(self.cloud.profiles, [None])

    async def test_a_failed_call_stops_the_agent_and_says_why(self):
        agent = Agent(task_answer=(401, {"error": "unauthorized"}))
        with serving(agent), self.assertRaises(BrowserUseUnavailable) as caught:
            await tools.task({"goal": "anything"})
        self.assertIn("BB_BROWSERUSE_TOKEN must equal", str(caught.exception))
        self.assertEqual(agent.paths(), ["/api/task", "/api/cancel"])


class Cancel(Setup):
    async def test_cancel_stops_the_running_tasks(self):
        agent = Agent(hang=True)
        with serving(agent):
            running = asyncio.create_task(tools.task({"goal": "something long"}))
            await asyncio.wait_for(agent.task_arrived.wait(), 5)
            answer = await asyncio.wait_for(tools.task({"cancel": True}), 5)
            await asyncio.wait_for(running, 5)
        self.assertIs(answer["cancelled"], True)
        self.assertIn(None, agent.cancelled_ids, "cancel=true stops every task, not one by id")

    async def test_cancel_and_a_goal_together_are_refused(self):
        with self.assertRaises(ValueError):
            await tools.task({"cancel": True, "goal": "anything"})

    async def test_a_goal_is_needed_to_start_one(self):
        with self.assertRaises(ValueError) as caught:
            await tools.task({})
        self.assertIn("cancel=true", str(caught.exception))


class Startup(unittest.TestCase):
    def test_a_task_left_running_by_a_dead_gateway_is_stopped_at_startup(self):
        """Its caller is gone; left running it would spend on nobody's behalf."""
        from starlette.testclient import TestClient

        seen = []

        def agent(request):
            seen.append(request.url.path)
            return httpx.Response(200, json={"cancelled": True})

        with mock.patch.dict("os.environ", ENV), serving(agent), TestClient(server.build_app()):
            pass
        self.assertIn("/api/cancel", seen)


class Surfaces(Setup):
    def card(self):
        return next(t for t in tools.offered_tools() if t["name"] == "task")

    async def test_a_browser_only_box_offers_only_the_browser(self):
        card = self.card()
        props = card["inputSchema"]["properties"]
        self.assertEqual(props["surface"], {"type": "string", "enum": ["browser"], "default": "browser"})
        self.assertIn("max_steps", props)
        self.assertNotIn("computer_id", props)
        self.assertIn('surface="browser"', card["description"])
        self.assertNotIn('surface="computer"', card["description"])

    async def test_with_both_surface_is_required_and_both_are_described(self):
        with mock.patch.dict("os.environ", {"ORGO_API_KEY": "sk_live_test"}):
            card = self.card()
            with self.assertRaises(ValueError):
                await tools.task({"goal": "anything"})
        self.assertIn("surface is required", card["description"])
        self.assertEqual(card["inputSchema"]["properties"]["surface"]["enum"], ["browser", "computer"])
        self.assertIn('surface="computer"', card["description"])

    async def test_a_surface_this_box_lacks_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            await tools.task({"goal": "anything", "surface": "computer"})
        self.assertIn("not configured", str(caught.exception))

    async def test_no_surfaces_means_no_task_tool(self):
        with mock.patch.dict("os.environ", {"BB_BROWSERUSE_URL": ""}):
            self.assertNotIn("task", [t["name"] for t in tools.offered_tools()])
        with mock.patch.object(tools, "cloud_client", lambda: None):
            self.assertNotIn("task", [t["name"] for t in tools.offered_tools()], "the agent alone has no browser to drive")
        with mock.patch.dict("os.environ", {"BB_BROWSERUSE_URL": ""}):
            blocks = await server.call_tool("task", {"goal": "anything"})
        self.assertIn("not offered", json.loads(blocks[0].text)["error"])


class Status(Setup):
    async def test_reports_the_agent_and_its_model(self):
        with serving(Agent()):
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("browser-use agent"))
        self.assertTrue(row["up"])
        self.assertEqual(row["detail"]["model"], "z-ai/glm-5.3-flash")
        self.assertIn("task", out["tools_working_now"])

    async def test_an_unreachable_agent_takes_the_browser_surface_down(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)

        with serving(refuse):
            out = await tools.status({})
        self.assertNotIn("task", out["tools_working_now"])
        self.assertEqual([(u["tool"], u["surface"]) for u in out["tools_unavailable"]], [("task", "browser")])

    async def test_one_surface_down_leaves_task_up_while_the_other_works(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)

        async def orgo_ok():
            return {"computers": 1}

        with serving(refuse), \
                mock.patch.dict("os.environ", {"ORGO_API_KEY": "sk_live_test"}), mock.patch.object(orgo, "health", orgo_ok):
            out = await tools.status({})
        self.assertIn("task", out["tools_working_now"])
        self.assertEqual([u.get("surface") for u in out["tools_unavailable"] if u["tool"] == "task"], ["browser"])

    async def test_unconfigured_is_reported_not_broken(self):
        with mock.patch.dict("os.environ", {"BB_BROWSERUSE_URL": ""}):
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("browser-use agent"))
        self.assertIs(row["configured"], False)
        self.assertEqual(out["tools_unavailable"], [])


if __name__ == "__main__":
    unittest.main()


class Emergency(Setup):
    """Browser Use is the only main lane; Browserbase is the emergency browser when it cannot open one."""

    def broken_cloud(self):
        @asynccontextmanager
        async def hosted(**_kw):
            from gateway.cloud import CloudUnavailable
            raise CloudUnavailable("Browser Use is out of credit")
            yield  # pragma: no cover
        self.cloud.hosted = hosted

    def bb(self):
        bb = mock.Mock()
        opened = []

        @asynccontextmanager
        async def hosted(minutes=None):
            opened.append(minutes)
            yield "wss://connect.browserbase.example/x", {"session_id": "bb-1", "engine": "browserbase"}
        bb.hosted = hosted
        return bb, opened

    async def test_a_task_falls_back_to_browserbase_and_says_so(self):
        self.broken_cloud()
        bb, opened = self.bb()
        agent = Agent()
        with serving(agent), mock.patch.object(tools, "browserbase_client", lambda: bb):
            out = await tools.task({"goal": "anything"})
        self.assertEqual((out["engine"], len(opened)), ("browserbase", 1))
        self.assertIn("out of credit", out["fallback_reason"])
        self.assertEqual(json.loads(agent.seen[0].content)["cdp_url"], "wss://connect.browserbase.example/x")

    async def test_without_browserbase_the_outage_is_the_answer(self):
        from gateway.cloud import CloudUnavailable
        self.broken_cloud()
        with serving(Agent()), self.assertRaises(CloudUnavailable):
            await tools.task({"goal": "anything"})
