"""task(surface="browser"), tested through httpx's real request builder over a mock transport,
as act is. The properties that matter most are about the browser lane: the agent must never be
left driving the browser after the lane is released, whether the caller gave up, the call
failed or the guard went away mid-task."""
import asyncio
import json
import unittest
from unittest import mock

import httpx

from gateway import browseruse, guard, lock, orgo, server, tools
from gateway.browseruse import BrowserUseUnavailable
from gateway.lock import LaneBusy

ENV = {"BB_BROWSERUSE_URL": "http://agent-browseruse:3120", "BB_BROWSERUSE_TOKEN": "bu-test-token"}
DONE = {"status": "done", "answer": "GPT-6 Sol and Luna, 646 comments", "steps_taken": 3, "steps": [],
        "urls": ["https://news.ycombinator.com/"], "final_url": "https://news.ycombinator.com/item?id=1",
        "tokens": {"prompt": 32779, "completion": 1329, "cached": 0}, "estimated_cost_usd": 0.005581}


def guard_attached(up=True):
    event = asyncio.Event()
    if up:
        event.set()
    return mock.patch.object(guard.GUARD, "_attached", event)


class Agent:
    """A fake agent-browseruse. /task answers `task_answer`, or hangs until released; /cancel
    records whether the browser lane was still held when it arrived."""

    def __init__(self, task_answer=None, hang=False):
        self.task_answer = task_answer if task_answer is not None else DONE
        self.hang = hang
        self.release = asyncio.Event()
        self.task_arrived = asyncio.Event()
        self.seen: list[httpx.Request] = []
        self.lane_held_at_cancel: bool | None = None

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.url.path == "/api/task":
            self.task_arrived.set()
            if self.hang:
                await self.release.wait()
            status, body = self.task_answer if isinstance(self.task_answer, tuple) else (200, self.task_answer)
            return httpx.Response(status, json=body)
        if request.url.path == "/api/cancel":
            try:
                async with lock.lane(wait_seconds=0, label="probe"):
                    self.lane_held_at_cancel = False
            except LaneBusy:
                self.lane_held_at_cancel = True
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
        for patch in (mock.patch.dict("os.environ", ENV), guard_attached()):
            patch.start()
            self.addCleanup(patch.stop)


class Task(Setup):
    async def test_hands_the_goal_over_with_its_bounds_and_the_token(self):
        agent = Agent()
        with serving(agent):
            out = await tools.task({"goal": "top HN story and its comment count", "max_steps": 8, "timeout_seconds": 120})
        request = agent.seen[0]
        self.assertEqual((request.method, request.url.path), ("POST", "/api/task"))
        self.assertEqual(json.loads(request.content), {"goal": "top HN story and its comment count", "max_steps": 8, "timeout_seconds": 120})
        self.assertEqual(request.headers["authorization"], "Bearer bu-test-token")
        self.assertEqual((out["surface"], out["status"], out["answer"]), ("browser", "done", DONE["answer"]))

    async def test_the_only_configured_surface_is_the_default(self):
        agent = Agent()
        with serving(agent):
            out = await tools.task({"goal": "anything"})
        self.assertEqual(out["surface"], "browser")
        self.assertEqual(json.loads(agent.seen[0].content)["max_steps"], 25)

    async def test_its_cost_shows_in_status(self):
        with serving(Agent()), mock.patch.object(tools, "_CALLS", []), mock.patch.object(tools.steel, "health", self.steel_ok):
            await tools.task({"goal": "anything"})
            out = await tools.status({})
        self.assertEqual(out["recent_calls"][0]["cost_usd"], DONE["estimated_cost_usd"])
        self.assertEqual(out["model_spend_recent_usd"], DONE["estimated_cost_usd"])

    async def steel_ok(self):
        return {"status": "ok"}

    async def test_refuses_to_run_without_the_in_browser_guard(self):
        agent = Agent()
        with serving(agent), guard_attached(up=False), mock.patch.object(guard, "READY_WAIT", 0.1):
            with self.assertRaises(guard.GuardDown):
                await tools.task({"goal": "anything"})
        self.assertEqual(agent.seen, [])

    async def test_holds_the_browser_lane(self):
        with serving(Agent()), mock.patch.object(lock, "WAIT_SECONDS", 0.2):
            async with tools.lane(label="a read"):
                with self.assertRaises(LaneBusy):
                    await tools.task({"goal": "anything"})

    async def test_a_caller_that_gives_up_stops_the_agent_before_the_lane_is_released(self):
        """An MCP client that times out cancels this handler; the agent must not keep driving
        the browser while the next read or act runs in it."""
        agent = Agent(hang=True)
        with serving(agent):
            call = asyncio.create_task(tools.task({"goal": "something long"}))
            await asyncio.wait_for(agent.task_arrived.wait(), 5)
            call.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await call
        self.assertIn("/api/cancel", agent.paths())
        self.assertIs(agent.lane_held_at_cancel, True, "the lane was released before the agent was stopped")
        async with tools.lane(wait_seconds=0, label="after"):
            pass

    async def test_losing_the_guard_mid_task_stops_the_agent(self):
        agent = Agent(hang=True)
        attached = asyncio.Event()
        attached.set()
        with serving(agent), mock.patch.object(guard.GUARD, "_attached", attached):
            call = asyncio.create_task(tools.task({"goal": "something long"}))
            await asyncio.wait_for(agent.task_arrived.wait(), 5)
            attached.clear()  # the guard fails open: nothing may keep browsing now
            out = await asyncio.wait_for(call, 5)
        self.assertEqual(out["status"], "stopped")
        self.assertIn("guard", out["reason"])
        self.assertEqual(out["answer"], DONE["answer"], "the stopped task's own report was thrown away")
        self.assertIs(agent.lane_held_at_cancel, True)

    async def test_a_failed_call_stops_the_agent_and_says_why(self):
        agent = Agent(task_answer=(401, {"error": "unauthorized"}))
        with serving(agent), self.assertRaises(BrowserUseUnavailable) as caught:
            await tools.task({"goal": "anything"})
        self.assertIn("BB_BROWSERUSE_TOKEN must equal", str(caught.exception))
        self.assertEqual(agent.paths(), ["/api/task", "/api/cancel"])


class Cancel(Setup):
    async def test_cancel_stops_the_running_task_without_waiting_for_the_lane(self):
        agent = Agent(hang=True)
        with serving(agent):
            running = asyncio.create_task(tools.task({"goal": "something long"}))
            await asyncio.wait_for(agent.task_arrived.wait(), 5)
            answer = await asyncio.wait_for(tools.task({"cancel": True}), 5)
            await asyncio.wait_for(running, 5)
        self.assertIs(answer["cancelled"], True)
        self.assertIs(agent.lane_held_at_cancel, True)

    async def test_cancel_and_a_goal_together_are_refused(self):
        with self.assertRaises(ValueError):
            await tools.task({"cancel": True, "goal": "anything"})

    async def test_a_goal_is_needed_to_start_one(self):
        with self.assertRaises(ValueError) as caught:
            await tools.task({})
        self.assertIn("cancel=true", str(caught.exception))

    async def test_a_busy_lane_held_by_a_task_says_how_to_stop_it(self):
        with mock.patch.object(lock, "WAIT_SECONDS", 0.2):
            async with tools.lane(label="task visit 15 random pages"):
                with self.assertRaises(LaneBusy) as caught:
                    async with tools.lane(label="read"):
                        pass
        self.assertIn("task(cancel=true)", str(caught.exception))


class Startup(unittest.TestCase):
    def test_a_task_left_running_by_a_dead_gateway_is_stopped_at_startup(self):
        """The dead gateway's lane went with it, so an orphaned task would share the browser."""
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
            blocks = await server.call_tool("task", {"goal": "anything"})
        self.assertIn("not offered", json.loads(blocks[0].text)["error"])


class Status(Setup):
    async def steel_ok(self):
        return {"status": "ok"}

    async def test_reports_the_agent_and_its_model(self):
        with serving(Agent()), mock.patch.object(tools.steel, "health", self.steel_ok):
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("browser-use"))
        self.assertTrue(row["up"])
        self.assertEqual(row["detail"]["model"], "z-ai/glm-5.3-flash")
        self.assertIn("task", out["tools_working_now"])

    async def test_an_unreachable_agent_takes_the_browser_surface_down(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)

        with serving(refuse), mock.patch.object(tools.steel, "health", self.steel_ok):
            out = await tools.status({})
        self.assertNotIn("task", out["tools_working_now"])
        self.assertEqual([(u["tool"], u["surface"]) for u in out["tools_unavailable"]], [("task", "browser")])

    async def test_one_surface_down_leaves_task_up_while_the_other_works(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)

        async def orgo_ok():
            return {"computers": 1}

        with serving(refuse), mock.patch.object(tools.steel, "health", self.steel_ok), \
                mock.patch.dict("os.environ", {"ORGO_API_KEY": "sk_live_test"}), mock.patch.object(orgo, "health", orgo_ok):
            out = await tools.status({})
        self.assertIn("task", out["tools_working_now"])
        self.assertEqual([u.get("surface") for u in out["tools_unavailable"] if u["tool"] == "task"], ["browser"])

    async def test_without_the_guard_the_browser_surface_is_unavailable(self):
        with serving(Agent()), mock.patch.object(tools.steel, "health", self.steel_ok), guard_attached(up=False):
            out = await tools.status({})
        self.assertIn(("task", "browser"), [(u["tool"], u.get("surface")) for u in out["tools_unavailable"]])

    async def test_unconfigured_is_reported_not_broken(self):
        with mock.patch.dict("os.environ", {"BB_BROWSERUSE_URL": ""}), mock.patch.object(tools.steel, "health", self.steel_ok):
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("browser-use"))
        self.assertIs(row["configured"], False)
        self.assertEqual(out["tools_unavailable"], [])


if __name__ == "__main__":
    unittest.main()
