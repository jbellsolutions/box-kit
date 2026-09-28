"""Orgo, tested through httpx's real request builder over a mock transport.

A fake client would accept whatever the code sends. MockTransport sees the actual method,
path, query, headers and JSON body — which is what Orgo sees — so a wrong path or a wrong
field name fails here instead of against a billed computer.
"""
import json
import unittest
from unittest import mock

import httpx

from gateway import orgo, server, tools
from gateway.orgo import OrgoUnavailable

KEY = "sk_live_test"


class Recorder:
    """Answers requests from a routing function and remembers every one it saw."""

    def __init__(self, route):
        self.route = route
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self.route(request)

    def bodies(self):
        return [json.loads(r.content) if r.content else None for r in self.seen]

    def paths(self):
        return [f"{r.method} {r.url.path}" for r in self.seen]


def orgo_serving(route):
    recorder = Recorder(route)
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder)
        return real(*args, **kwargs)

    return recorder, mock.patch.object(orgo.httpx, "AsyncClient", client)


def configured(**extra):
    return mock.patch.dict("os.environ", {"ORGO_API_KEY": KEY, **extra})


class Setup(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        orgo.forget()


class Model(unittest.TestCase):
    def test_the_hyphenated_id_that_broke_super_browser_is_refused_before_any_request(self):
        with mock.patch.dict("os.environ", {"ORGO_MODEL": "claude-sonnet-4-6"}):
            with self.assertRaises(OrgoUnavailable) as caught:
                orgo.model()
        self.assertIn("note the dot in 4.6", str(caught.exception))

    def test_every_documented_model_is_accepted(self):
        for name in orgo.MODELS:
            with mock.patch.dict("os.environ", {"ORGO_MODEL": name}):
                self.assertEqual(orgo.model(), name)

    def test_default_is_documented(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("ORGO_MODEL", None)
            self.assertIn(orgo.model(), orgo.MODELS)


class Ids(unittest.TestCase):
    def test_an_id_cannot_walk_the_url_path(self):
        for bad in ("../workspaces", "a/b", "", "id?x=1", "id#frag", "a" * 200, None):
            with self.assertRaises(ValueError, msg=bad):
                orgo.computer_id_or_raise(bad)

    def test_real_ids_pass(self):
        for good in ("9f4360e8-e6c5-495e-b579-be5eb35022db", "vm_123", "ABC"):
            self.assertEqual(orgo.computer_id_or_raise(good), good)


class Actions(Setup):
    async def test_screen_actions_keep_exact_screen_and_context(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={
            "success": True, "image": "QUJD", "context": {"focused_window": {"elements": []}}}))
        with configured(), patched:
            shot = await orgo.screenshot("vm1", screen_id="screen-2", context=True)
            await orgo.click("vm1", 100, 200, screen_id="screen-2", context=True)
        assert [r.url.params["screen"] for r in rec.seen] == ["screen-2", "screen-2"]
        assert [r.url.params["context"] for r in rec.seen] == ["1", "1"]
        assert shot["context"]["focused_window"]["elements"] == []

    async def test_no_key_says_what_to_set(self):
        with mock.patch.dict("os.environ", {"ORGO_API_KEY": ""}):
            with self.assertRaises(OrgoUnavailable) as caught:
                await orgo.click("vm1", 1, 2)
        self.assertIn("ORGO_API_KEY", str(caught.exception))

    async def test_click_sends_exactly_the_documented_body_with_the_bearer(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={"success": True}))
        with configured(), patched:
            await orgo.click("vm1", 100, 200, button="right", double=True)
        self.assertEqual(rec.paths(), ["POST /api/computers/vm1/click"])
        self.assertEqual(rec.bodies(), [{"x": 100, "y": 200, "button": "right", "double": True}])
        self.assertEqual(rec.seen[0].headers["authorization"], f"Bearer {KEY}")

    async def test_type_key_scroll_bash_bodies(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={"success": True, "output": "Linux"}))
        with configured(), patched:
            await orgo.type_text("vm1", "hello")
            await orgo.press("vm1", "ctrl+c")
            await orgo.scroll("vm1", 640, 400, direction="up", amount=10)
            out = await orgo.bash("vm1", "uname -a")
        self.assertEqual(rec.paths(), ["POST /api/computers/vm1/type", "POST /api/computers/vm1/key",
                                       "POST /api/computers/vm1/scroll", "POST /api/computers/vm1/bash"])
        self.assertEqual(rec.bodies(), [{"text": "hello"}, {"key": "ctrl+c"},
                                        {"x": 640, "y": 400, "direction": "up", "amount": 10},
                                        {"command": "uname -a", "timeout": 200}])
        self.assertEqual(out["output"], "Linux")

    async def test_screenshot_asks_for_inline_base64(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={
            "success": True, "image": "QUJD", "mime_type": "image/jpeg", "width": 1280, "height": 720}))
        with configured(), patched:
            shot = await orgo.screenshot("vm1")
        self.assertEqual(rec.seen[0].url.params["response_format"], "base64")
        self.assertEqual(shot, {"image": "QUJD", "mime_type": "image/jpeg", "width": 1280, "height": 720})

    async def test_an_orgo_error_is_named_not_swallowed(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(401, json={"error": "Invalid API key"}))
        with configured(), patched:
            with self.assertRaises(OrgoUnavailable) as caught:
                await orgo.press("vm1", "Return")
        self.assertIn("401", str(caught.exception))
        self.assertIn("Invalid API key", str(caught.exception))


class Resolve(Setup):
    def workspace(self, computers):
        def route(request):
            if request.url.path == "/api/workspaces":
                return httpx.Response(200, json={"projects": [{"id": "ws1", "name": "browser-box"}]})
            if request.url.path == "/api/workspaces/ws1":
                return httpx.Response(200, json={"desktops": computers})
            return httpx.Response(200, json={"id": "new1", "success": True})
        return route

    async def test_pinned_id_skips_discovery(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(500))
        with configured(ORGO_COMPUTER_ID="pinned1"), patched:
            self.assertEqual(await orgo.resolve(), ("pinned1", "pinned via ORGO_COMPUTER_ID"))
        self.assertEqual(rec.seen, [])

    async def test_reuses_a_running_computer_and_remembers_it(self):
        rec, patched = orgo_serving(self.workspace([{"id": "vm1", "name": "browser-box", "status": "running"}]))
        with configured(), patched:
            first = await orgo.resolve()
            second = await orgo.resolve()
        self.assertEqual(first[0], "vm1")
        self.assertEqual(second, first)
        self.assertEqual(len(rec.seen), 2, "the second resolve must come from memory, not two more API calls")

    async def test_starts_a_frozen_computer_and_says_it_bills(self):
        rec, patched = orgo_serving(self.workspace([{"id": "vm2", "name": "browser-box", "status": "frozen"}]))
        with configured(), patched:
            cid, how = await orgo.resolve()
        self.assertEqual(cid, "vm2")
        self.assertIn("POST /api/computers/vm2/start", rec.paths())
        self.assertIn("bills until stopped", how)

    async def test_never_creates_a_billed_computer_unasked(self):
        rec, patched = orgo_serving(self.workspace([]))
        with configured(), patched:
            with self.assertRaises(OrgoUnavailable) as caught:
                await orgo.resolve()
        self.assertIn("BB_ORGO_AUTOCREATE", str(caught.exception))
        self.assertNotIn("POST /api/computers", rec.paths())

    async def test_creates_only_when_explicitly_allowed(self):
        rec, patched = orgo_serving(self.workspace([]))
        with configured(BB_ORGO_AUTOCREATE="1"), patched:
            cid, how = await orgo.resolve()
        self.assertEqual(cid, "new1")
        self.assertIn("POST /api/computers", rec.paths())
        self.assertEqual(rec.bodies()[-1], {"workspace_id": "ws1", "name": "browser-box"})

    async def test_stop_forgets_the_remembered_computer(self):
        rec, patched = orgo_serving(self.workspace([{"id": "vm1", "name": "browser-box", "status": "running"}]))
        with configured(), patched:
            await orgo.resolve()
            await orgo.stop("vm1")
        self.assertEqual(orgo._RESOLVED, {})


class Agent(Setup):
    def sse(self, *events, done=True):
        lines = [f"data: {json.dumps(e)}\n\n" for e in events]
        if done:
            lines.append("data: [DONE]\n\n")
        return "".join(lines).encode()

    async def test_streams_the_answer_and_sends_a_valid_model(self):
        body = self.sse({"choices": [{"delta": {"content": "Linux "}}], "orgo": {"thread_id": "t1"}},
                        {"choices": [{"delta": {"content": "6.8"}}]})
        rec, patched = orgo_serving(lambda r: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"}))
        with configured(), patched:
            out = await orgo.agent("vm1", "run uname -r")
        self.assertEqual(rec.paths(), ["POST /api/v1/chat/completions"])
        sent = rec.bodies()[0]
        self.assertEqual(sent["computer_id"], "vm1")
        self.assertIn(sent["model"], orgo.MODELS)
        self.assertTrue(sent["stream"], "streamed so a deadline can actually abort the run")
        self.assertEqual(out["status"], "done")
        self.assertEqual(out["answer"], "Linux 6.8")
        self.assertEqual(out["thread_id"], "t1")

    async def test_invalid_model_is_surfaced_verbatim(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(400, json={"error": "invalid_model"}))
        with configured(), patched:
            with self.assertRaises(OrgoUnavailable) as caught:
                await orgo.agent("vm1", "anything")
        self.assertIn("invalid_model", str(caught.exception))


class ComputerTool(Setup):
    async def test_scroll_without_coordinates_is_refused_before_orgo_is_called(self):
        """Orgo warps the pointer to the top-left corner when x/y are missing."""
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={"success": True}))
        with configured(ORGO_COMPUTER_ID="vm1"), patched:
            with self.assertRaises(ValueError) as caught:
                await tools.computer({"action": "scroll"})
        self.assertIn("x, y", str(caught.exception))
        self.assertEqual(rec.seen, [])

    async def test_screenshot_comes_back_as_an_image_block_the_caller_can_see(self):
        rec, patched = orgo_serving(lambda r: httpx.Response(200, json={
            "success": True, "image": "QUJD", "mime_type": "image/jpeg", "width": 1280, "height": 720}))
        with configured(ORGO_COMPUTER_ID="vm1"), patched:
            result = await tools.computer({"action": "screenshot"})
        blocks = server.render(result)
        self.assertEqual([b.type for b in blocks], ["text", "image"])
        self.assertEqual(blocks[1].data, "QUJD")
        self.assertNotIn("QUJD", blocks[0].text, "base64 must not also ride along as text")

    async def test_computer_lane_does_not_block_the_browser(self):
        """Separate resources, separate lanes: a busy desktop must not stall a page read."""
        async with tools.lane(name="computer-vm1", label="a long desktop job"):
            async with tools.lane(wait_seconds=0, label="a page read"):
                pass

    async def test_two_jobs_on_one_computer_are_serialised(self):
        async with tools.lane(name="computer-vm1", label="first"):
            with self.assertRaises(tools.LaneBusy):
                async with tools.lane(wait_seconds=0, name="computer-vm1", label="second"):
                    pass


class StatusWithOrgo(Setup):
    async def test_a_broken_orgo_key_takes_its_tools_offline_with_the_reason(self):
        async def steel_ok():
            return {"status": "ok"}

        rec, patched = orgo_serving(lambda r: httpx.Response(401, json={"error": "Invalid API key"}))
        with configured(), patched, mock.patch.object(tools.steel, "health", steel_ok):
            out = await tools.status({})
        orgo_row = next(c for c in out["components"] if c["name"].startswith("orgo"))
        self.assertFalse(orgo_row["up"])
        self.assertEqual({u["tool"] for u in out["tools_unavailable"]}, {"computer", "task"})
        self.assertIn("Invalid API key", out["tools_unavailable"][0]["reason"])
        self.assertIn("read", out["tools_working_now"])

    async def test_unconfigured_orgo_is_reported_but_nothing_is_advertised(self):
        async def steel_ok():
            return {"status": "ok"}

        with mock.patch.dict("os.environ", {"ORGO_API_KEY": ""}), mock.patch.object(tools.steel, "health", steel_ok):
            out = await tools.status({})
        orgo_row = next(c for c in out["components"] if c["name"].startswith("orgo"))
        self.assertIs(orgo_row["configured"], False)
        self.assertNotIn("computer", out["tools_working_now"])
        self.assertEqual(out["tools_unavailable"], [])


class NotOffered(unittest.IsolatedAsyncioTestCase):
    async def test_calling_an_unlisted_tool_is_refused_with_a_pointer_to_status(self):
        with mock.patch.dict("os.environ", {"ORGO_API_KEY": ""}):
            blocks = await server.call_tool("computer", {"action": "screenshot"})
        body = json.loads(blocks[0].text)
        self.assertIn("not offered", body["error"])


if __name__ == "__main__":
    unittest.main()
