import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from browser_box_cli import agent, client, main


class Endpoint(unittest.TestCase):
    def test_adds_mcp_when_missing_and_never_twice(self):
        self.assertEqual(client.endpoint("https://box.example"), "https://box.example/mcp")
        self.assertEqual(client.endpoint("https://box.example/"), "https://box.example/mcp")
        self.assertEqual(client.endpoint("https://box.example/mcp"), "https://box.example/mcp")
        self.assertEqual(client.endpoint("https://box.example/mcp/"), "https://box.example/mcp/")


class Settings(unittest.TestCase):
    """Precedence matters: a stale config file must never shadow an explicit env var."""

    def elsewhere(self):
        """Point config at a path that does not exist and run from a directory with no .env."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, cwd)
        return mock.patch.object(client, "CONFIG", Path(tmp.name) / "nothing-here.json")

    def test_env_wins_over_the_config_file(self):
        with self.elsewhere(), mock.patch.dict("os.environ", {"BB_URL": "https://env.example", "BB_TOKEN": "from-env"}, clear=False):
            conf = client.settings()
        self.assertEqual(conf, {"url": "https://env.example", "token": "from-env"})

    def test_config_file_is_used_when_env_is_silent(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "config.json"
        path.write_text(json.dumps({"url": "https://saved.example", "token": "from-file"}))
        cwd = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, cwd)
        with mock.patch.object(client, "CONFIG", path), mock.patch.dict("os.environ", {}, clear=True):
            conf = client.settings()
        self.assertEqual(conf["token"], "from-file")

    def test_missing_token_says_what_to_run(self):
        with self.elsewhere(), mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(client.NotConfigured) as caught:
                client.settings()
        self.assertIn("bb login", str(caught.exception))


class Screenshot(unittest.TestCase):
    def test_base64_is_written_to_a_file_not_the_terminal(self):
        import base64
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "shot.jpg")
            result = main._save_screenshot(
                {"text": "hi", "screenshot_base64": base64.b64encode(b"JPEGBYTES").decode(), "screenshot_bytes": 8},
                target,
            )
        self.assertNotIn("screenshot_base64", result)
        self.assertTrue(result["screenshot_saved_to"].endswith("shot.jpg"))

    def test_no_screenshot_is_left_alone(self):
        self.assertEqual(main._save_screenshot({"text": "hi"}, None), {"text": "hi"})


class Parser(unittest.TestCase):
    def test_every_command_is_wired_to_a_handler(self):
        parser = main.build_parser()
        for argv in (["status"], ["tools"], ["fetch", "https://x.example"], ["read", "https://x.example"],
                     ["session", "list"], ["ask", "do", "a", "thing"], ["chat"],
                     ["computer", "screenshot"], ["computer", "click", "--x", "1", "--y", "2"],
                     ["computer", "bash", "--command", "uname -a"], ["task", "open", "a", "terminal"],
                     ["task", "--cancel"], ["task", "--surface", "browser", "--max-steps", "8", "find", "it"],
                     ["act", "open", "https://x.example"], ["act", "--pick", "e3"], ["act", "--confirm", "no"],
                     ["login", "--url", "https://x", "--token", "t"]):
            self.assertTrue(callable(parser.parse_args(argv).run), argv)

    def test_screenshot_flag_never_swallows_the_url(self):
        """-s used to take an optional value, so `bb read -s <url>` read the URL as a filename."""
        parser = main.build_parser()
        before = parser.parse_args(["read", "-s", "https://x.example"])
        self.assertEqual(before.url, "https://x.example")
        self.assertTrue(before.screenshot)
        self.assertIsNone(before.out)

        after = parser.parse_args(["read", "https://x.example", "-s", "-o", "a.jpg"])
        self.assertEqual(after.url, "https://x.example")
        self.assertEqual(after.out, "a.jpg")

        plain = parser.parse_args(["read", "https://x.example"])
        self.assertFalse(plain.screenshot)

    def test_out_alone_implies_a_screenshot(self):
        parser = main.build_parser()
        args = parser.parse_args(["read", "https://x.example", "-o", "a.jpg"])
        self.assertFalse(args.screenshot)
        self.assertEqual(args.out, "a.jpg")


class ActAndTask(unittest.IsolatedAsyncioTestCase):
    """What bb sends: only what was asked for, so the box picks its own defaults and surface."""

    async def sent(self, argv, answer=None):
        calls = []

        async def call(name, payload):
            calls.append((name, payload))
            return answer or {"status": "done", "steps": [], "answer": "ok"}

        with mock.patch.object(main, "call", call):
            code = await main.build_parser().parse_args(argv).run(main.build_parser().parse_args(argv))
        return calls, code

    async def test_task_sends_only_what_was_given(self):
        calls, code = await self.sent(["task", "find", "the", "price"])
        self.assertEqual(calls, [("task", {"goal": "find the price"})])
        calls, _ = await self.sent(["task", "--surface", "browser", "--max-steps", "8", "--timeout", "120", "go"])
        self.assertEqual(calls, [("task", {"goal": "go", "surface": "browser", "timeout_seconds": 120, "max_steps": 8})])

    async def test_task_cancel_sends_cancel_alone(self):
        calls, code = await self.sent(["task", "--cancel"], {"surface": "browser", "cancelled": True})
        self.assertEqual((calls, code), ([("task", {"cancel": True})], 0))

    async def test_act_answers_a_confirmation_with_a_boolean(self):
        calls, _ = await self.sent(["act", "--confirm", "no"])
        self.assertEqual(calls, [("act", {"confirm": False})])
        calls, _ = await self.sent(["act", "--read", "click", "the", "pricing", "link"])
        self.assertEqual(calls, [("act", {"command": "click the pricing link", "read_page": True})])

    async def test_a_clarification_is_not_a_failure(self):
        question = {"status": "needs_clarification", "question": "Which?", "steps": [],
                    "options": [{"pick": "e0", "label": "link Learn more", "probability": 0.61}]}
        _, code = await self.sent(["act", "click", "learn", "more"], question)
        self.assertEqual(code, 0)


class ImageBlocks(unittest.IsolatedAsyncioTestCase):
    """The server now returns screenshots as image blocks; the CLI must still get a file out."""

    async def test_an_image_block_is_folded_back_for_the_cli(self):
        from types import SimpleNamespace

        result = SimpleNamespace(content=[
            SimpleNamespace(type="text", text=json.dumps({"action": "screenshot", "width": 1280})),
            SimpleNamespace(type="image", data="QUJD", mimeType="image/jpeg"),
        ])

        class Session:
            async def call_tool(self, name, arguments):
                return result

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_session():
            yield Session()

        with mock.patch.object(client, "session", fake_session):
            parsed = await client.call("computer", {"action": "screenshot"})
        self.assertEqual(parsed["screenshot_base64"], "QUJD")
        self.assertEqual(parsed["screenshot_media_type"], "image/jpeg")
        self.assertEqual(parsed["width"], 1280)


class FakeTool:
    def __init__(self, name):
        self.name = name
        self.description = f"{name} does a thing"
        self.inputSchema = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}


class AskLoop(unittest.IsolatedAsyncioTestCase):
    """The brain runs HERE, in the client. Proven against a stub model, so no key and no spend."""

    def stub_model(self, replies):
        sent = []

        class Response:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload
                self.text = json.dumps(payload)

            def json(self):
                return self._payload

        class Client:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *_exc):
                return False

            async def post(self_inner, _url, headers=None, json=None):
                sent.append(json)
                return Response({"choices": [{"message": replies.pop(0)}]})

        return sent, mock.patch.object(agent.httpx, "AsyncClient", lambda *a, **k: Client())

    async def test_calls_a_tool_then_answers(self):
        replies = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "fetch", "arguments": '{"url": "https://example.com"}'}}]},
            {"role": "assistant", "content": "The page says Example Domain."},
        ]
        sent, patched = self.stub_model(replies)
        seen = []

        async def fake_call(name, arguments):
            seen.append((name, arguments))
            return {"text": "Example Domain", "status_code": 200}

        with patched, mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}, clear=False), \
                mock.patch.object(agent, "call", fake_call), \
                mock.patch.object(agent, "tool_list", lambda: _async([FakeTool("fetch"), FakeTool("read")])):
            answer, messages = await agent.ask("what is on example.com")

        self.assertEqual(answer, "The page says Example Domain.")
        self.assertEqual(seen, [("fetch", {"url": "https://example.com"})])
        # The box's own tool cards are what the model is handed — not a second description.
        self.assertEqual([t["function"]["name"] for t in sent[0]["tools"]], ["fetch", "read"])
        self.assertEqual(messages[-2]["role"], "tool")

    async def test_a_screenshot_never_enters_the_context(self):
        trimmed = agent._trim({"text": "hi", "screenshot_base64": "A" * 50000, "screenshot_bytes": 37500})
        self.assertNotIn("A" * 100, trimmed["screenshot_base64"])
        self.assertIn("37500 bytes", trimmed["screenshot_base64"])

    async def test_stops_at_the_step_ceiling_instead_of_looping_forever(self):
        forever = [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "fetch", "arguments": '{"url":"https://x.example"}'}}]}] * 40
        sent, patched = self.stub_model(forever)

        async def fake_call(_name, _arguments):
            return {"text": "again"}

        with patched, mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}, clear=False), \
                mock.patch.object(agent, "call", fake_call), \
                mock.patch.object(agent, "tool_list", lambda: _async([FakeTool("fetch")])), \
                mock.patch.object(agent, "MAX_STEPS", 3):
            answer, _ = await agent.ask("loop forever")
        self.assertIn("Stopped after 3 steps", answer)
        self.assertEqual(len(sent), 3)

    async def test_no_key_says_what_still_works(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(agent.LlmUnavailable) as caught:
                await agent.ask("anything")
        self.assertIn("bb fetch", str(caught.exception))


async def _async(value):
    return value


if __name__ == "__main__":
    unittest.main()
