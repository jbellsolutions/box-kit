"""act, tested through httpx's real request builder over a mock transport, as Orgo is: a wrong
path or field fails here rather than against the running agent-jev."""
import asyncio
import json
import unittest
from unittest import mock

import httpx

from gateway import guard, jev, lock, server, tools
from gateway.jev import JevUnavailable
from gateway.lock import LaneBusy

ENV = {"BB_JEV_URL": "http://agent-jev:3111", "BB_JEV_TOKEN": "jev-test-token"}
PAGE = {"url": "https://example.com/", "title": "Example Domain"}


def guard_attached(up=True):
    event = asyncio.Event()
    if up:
        event.set()
    return mock.patch.object(guard.GUARD, "_attached", event)


def result(ok=True, steps=None, pending=None, **extra):
    return {"ok": ok, "steps": steps or [], "page": PAGE, "pending": pending, **extra}


def step(command, text, level="ok", **extra):
    return {"stepId": 1, "command": command, "decision": None, "result": {"text": text, "level": level}, **extra}


class Recorder:
    def __init__(self, route):
        self.route = route
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self.route(request)

    def calls(self):
        return [(f"{r.method} {r.url.path}", json.loads(r.content) if r.content else None) for r in self.seen]


def jev_serving(route):
    recorder = Recorder(route)
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder)
        return real(*args, **kwargs)

    return recorder, mock.patch.object(jev.httpx, "AsyncClient", client)


def answers(by_path):
    """Route by path; a value is a JSON body (200) or an (status, body) pair."""
    def route(request):
        answer = by_path.get(request.url.path, (404, {"error": "no such route"}))
        status, body = answer if isinstance(answer, tuple) else (200, answer)
        return httpx.Response(status, json=body)
    return route


class Act(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for patch in (mock.patch.dict("os.environ", ENV), guard_attached()):
            patch.start()
            self.addCleanup(patch.stop)

    async def test_sends_a_command_to_the_steel_surface_with_the_token(self):
        recorder, patch = jev_serving(answers({"/api/command": result(steps=[step("open https://example.com", "Opened https://example.com")])}))
        with patch:
            out = await tools.act({"command": "open https://example.com"})
        self.assertEqual(recorder.calls(), [("POST /api/command", {"text": "open https://example.com", "session": "playwright"})])
        self.assertEqual(recorder.seen[0].headers["authorization"], "Bearer jev-test-token")
        self.assertEqual(out["status"], "done")
        self.assertEqual((out["url"], out["title"]), (PAGE["url"], PAGE["title"]))
        self.assertEqual(out["steps"], [{"command": "open https://example.com", "did": "Opened https://example.com", "outcome": "ok"}])

    async def test_each_step_says_who_decided_it_and_how_long_that_took(self):
        decided = step("click the pricing link", 'Clicked link "Pricing"', decision={"source": "jev", "latencyMs": 312, "actionLabel": 'Click link "Pricing"'})
        _, patch = jev_serving(answers({"/api/command": result(steps=[decided])}))
        with patch:
            out = await tools.act({"command": "click the pricing link"})
        self.assertEqual((out["steps"][0]["decided_by"], out["steps"][0]["decision_ms"]), ("jev", 312))

    async def test_a_clarification_comes_back_as_a_question_and_a_pick_answers_it(self):
        clarify = {"kind": "clarify", "question": 'Which one did you mean by "learn more"?',
                   "options": [{"elementId": "e0", "label": 'link "Learn more"', "probability": 0.612}]}
        recorder, patch = jev_serving(answers({
            "/api/command": result(ok=False, steps=[{"stepId": 1, "command": "click learn more", "decision": None, "result": None}], pending=clarify),
            "/api/reply": result(steps=[step("click learn more", 'Clicked link "Learn more"')]),
        }))
        with patch:
            asked = await tools.act({"command": "click learn more"})
            answered = await tools.act({"pick": "e0"})
        self.assertEqual(asked["status"], "needs_clarification")
        self.assertEqual(asked["options"], [{"pick": "e0", "label": 'link "Learn more"', "probability": 0.61}])
        self.assertIn("act(pick=", asked["next"])
        self.assertEqual(recorder.calls()[1], ("POST /api/reply", {"pick": "e0", "session": "playwright"}))
        self.assertEqual(answered["status"], "done")

    async def test_a_risky_action_waits_for_confirmation_and_false_cancels_it(self):
        confirm = {"kind": "confirm", "actionLabel": 'Click button "Delete account"', "reason": "This looks hard to undo (risk 91%)."}
        recorder, patch = jev_serving(answers({
            "/api/command": result(ok=False, pending=confirm),
            "/api/reply": result(ok=False, steps=[step("delete my account", "Cancelled", "warn")]),
        }))
        with patch:
            asked = await tools.act({"command": "delete my account"})
            await tools.act({"confirm": False})
        self.assertEqual(asked["status"], "needs_confirmation")
        self.assertEqual(asked["action"], 'Click button "Delete account"')
        # False is an answer, not a missing argument.
        self.assertEqual(recorder.calls()[1], ("POST /api/reply", {"ok": False, "session": "playwright"}))

    async def test_takes_exactly_one_of_command_pick_confirm(self):
        recorder, patch = jev_serving(answers({}))
        with patch:
            for args in ({}, {"command": ""}, {"command": "scroll down", "pick": "e1"}, {"pick": "e1", "confirm": True}):
                with self.assertRaises(ValueError, msg=args):
                    await tools.act(args)
        self.assertEqual(recorder.seen, [])

    async def test_a_refused_navigation_is_named_as_such(self):
        text = "Couldn't open http://127.0.0.1:3000/v1/sessions: page.goto: net::ERR_BLOCKED_BY_CLIENT at http://127.0.0.1:3000/v1/sessions"
        _, patch = jev_serving(answers({"/api/command": result(ok=False, steps=[step("open http://127.0.0.1:3000/v1/sessions", text, "error")])}))
        with patch:
            out = await tools.act({"command": "open http://127.0.0.1:3000/v1/sessions"})
        self.assertEqual(out["status"], "failed")
        self.assertIn("public web", out["refused"])

    async def test_read_page_uses_jev_read_when_the_build_has_it(self):
        _, patch = jev_serving(answers({"/api/command": result(), "/api/read": {"text": "Example Domain. This domain is for use in examples."}}))
        with patch:
            out = await tools.act({"command": "open https://example.com", "read_page": True})
        self.assertIn("for use in examples", out["text"])

    async def test_read_page_says_so_when_the_build_cannot_read(self):
        _, patch = jev_serving(answers({"/api/command": result()}))  # /api/read -> 404
        with patch:
            out = await tools.act({"command": "open https://example.com", "read_page": True})
        self.assertNotIn("text", out)
        self.assertIn("call read on the url", out["text_note"])

    async def test_a_wrong_token_is_explained_and_the_command_cancelled(self):
        recorder, patch = jev_serving(answers({"/api/command": (401, {"error": "unauthorized"}), "/api/cancel": {"ok": True}}))
        with patch, self.assertRaises(JevUnavailable) as caught:
            await tools.act({"command": "scroll down"})
        self.assertIn("BB_JEV_TOKEN must equal", str(caught.exception))
        self.assertEqual(recorder.calls()[-1][0], "POST /api/cancel")

    async def test_refuses_to_run_without_the_in_browser_guard(self):
        """The guard fails open while detached, so act must not run then."""
        recorder, patch = jev_serving(answers({"/api/command": result()}))
        with patch, guard_attached(up=False), mock.patch.object(guard, "READY_WAIT", 0.1), \
                mock.patch.object(guard.GUARD, "last_error", "ConnectionRefusedError"):
            with self.assertRaises(guard.GuardDown) as caught:
                await tools.act({"command": "open https://example.com"})
        self.assertIn("not attached", str(caught.exception))
        self.assertEqual(recorder.seen, [])

    async def test_holds_the_browser_lane(self):
        _, patch = jev_serving(answers({"/api/command": result()}))
        with patch, mock.patch.object(lock, "WAIT_SECONDS", 0.2):
            async with tools.lane(label="a read"):
                with self.assertRaises(LaneBusy):
                    await tools.act({"command": "scroll down"})


class Status(unittest.IsolatedAsyncioTestCase):
    async def steel_ok(self):
        return {"status": "ok"}

    async def test_reports_whose_decisions_act_is_running_on(self):
        health = {"ok": True, "paused": False, "jev": {"enabled": True, "model": "jev-latest"}, "url": "about:blank", "sessions": ["playwright"]}
        _, patch = jev_serving(answers({"/api/health": health}))
        with mock.patch.dict("os.environ", ENV), patch, mock.patch.object(tools.steel, "health", self.steel_ok), guard_attached():
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("jev"))
        self.assertTrue(row["up"])
        self.assertEqual(row["detail"]["decisions"], "TypeSafe Jev (jev-latest)")
        self.assertIn("act", out["tools_working_now"])

    async def test_an_unreachable_jev_is_reported_down_and_act_unavailable(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused", request=request)
        _, patch = jev_serving(refuse)
        with mock.patch.dict("os.environ", ENV), patch, mock.patch.object(tools.steel, "health", self.steel_ok), guard_attached():
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("jev"))
        self.assertFalse(row["up"])
        self.assertNotIn("act", out["tools_working_now"])
        self.assertEqual([u["tool"] for u in out["tools_unavailable"]], ["act"])

    async def test_unconfigured_means_not_listed_not_broken(self):
        with mock.patch.object(tools.steel, "health", self.steel_ok):
            out = await tools.status({})
        row = next(c for c in out["components"] if c["name"].startswith("jev"))
        self.assertIs(row["configured"], False)
        self.assertEqual(out["tools_unavailable"], [])

    async def test_calling_act_on_a_box_without_jev_is_refused(self):
        blocks = await server.call_tool("act", {"command": "scroll down"})
        self.assertIn("not offered", json.loads(blocks[0].text)["error"])


if __name__ == "__main__":
    unittest.main()
