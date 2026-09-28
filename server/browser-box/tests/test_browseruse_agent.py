"""agent-browseruse's own process handling, with a stand-in runner: which tabs it closes, and
that a task that overruns or is cancelled is killed and still reports what it did."""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bu_server", ROOT / "agents" / "browseruse" / "server.py")
bu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bu)

# Behaves by goal: "slow" writes a step then hangs, "finish" writes a result, "crash" dies.
FAKE_RUNNER = textwrap.dedent('''
    import json, os, sys, time
    spec = json.loads(sys.stdin.read())
    with open(spec["progress"], "a") as fh:
        fh.write(json.dumps({"step": 1, "url": "https://example.com/", "actions": [], "tokens": {"prompt": 1000, "completion": 50}}) + "\\n")
    if spec["goal"] == "slow":
        with open(os.path.join(os.path.dirname(spec["progress"]), "pid"), "w") as fh:
            fh.write(str(os.getpid()))
        time.sleep(60)
    elif spec["goal"] == "finish":
        with open(spec["result"], "w") as fh:
            json.dump({"status": "done", "success": True, "answer": "42", "steps": [{"step": 1, "url": "https://example.com/"}],
                       "urls": ["https://example.com/"], "final_url": "https://example.com/",
                       "tokens": {"prompt": 2000, "completion": 100, "cached": 0}}, fh)
    else:
        print("Traceback: something broke", file=sys.stderr)
        sys.exit(3)
''')


class Tabs(unittest.IsolatedAsyncioTestCase):
    async def test_closes_the_tasks_tabs_and_nobody_elses(self):
        foreign = {"JEV": {}, "OTHER": {}}
        now = {"JEV": {"opener": None}, "OTHER": {"opener": None}, "TASK": {"opener": None},
               "TASKPOPUP": {"opener": "TASK"}, "JEVPOPUP": {"opener": "JEV"}}
        sent = []

        async def cdp(*calls):
            sent.extend(calls)
            return [{} for _ in calls]

        with mock.patch.object(bu, "pages", mock.AsyncMock(return_value=now)), mock.patch.object(bu, "cdp", cdp):
            closed = await bu.close_task_tabs(foreign)
        self.assertEqual(closed, 2)
        self.assertEqual(sent, [("Target.closeTarget", {"targetId": "TASK"}), ("Target.closeTarget", {"targetId": "TASKPOPUP"})])

    async def test_never_closes_the_last_tab(self):
        sent = []

        async def cdp(*calls):
            sent.extend(calls)
            return [{} for _ in calls]

        with mock.patch.object(bu, "pages", mock.AsyncMock(return_value={"TASK": {"opener": None}})), mock.patch.object(bu, "cdp", cdp):
            await bu.close_task_tabs({})
        self.assertEqual(sent[0], ("Target.createTarget", {"url": "about:blank"}))
        self.assertEqual(sent[1:], [("Target.closeTarget", {"targetId": "TASK"})])


class Runs(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner = Path(tempfile.mkdtemp(prefix="bu-fake-")) / "runner.py"
        runner.write_text(FAKE_RUNNER)
        self.cleaned = mock.AsyncMock(return_value=1)
        for patch in (mock.patch.object(bu, "RUNNER", runner),
                      mock.patch.object(bu, "pages", mock.AsyncMock(return_value={"JEV": {"opener": None}})),
                      mock.patch.object(bu, "open_tab", mock.AsyncMock(return_value="TASK")),
                      mock.patch.object(bu, "dialable", mock.AsyncMock(return_value="ws://10.0.0.2:3000/")),
                      mock.patch.object(bu, "close_task_tabs", self.cleaned),
                      mock.patch.object(bu, "price", mock.AsyncMock(return_value=(1e-7, 4e-7)))):
            patch.start()
            self.addCleanup(patch.stop)

    async def test_a_finished_task_reports_its_result_and_cost(self):
        out = await bu.run_task(bu.Run(), "finish", 5, 30)
        self.assertEqual((out["status"], out["answer"], out["final_url"]), ("done", "42", "https://example.com/"))
        self.assertEqual(out["estimated_cost_usd"], round(2000 * 1e-7 + 100 * 4e-7, 6))
        self.cleaned.assert_awaited_once_with({"JEV": {"opener": None}})

    async def test_an_overrun_is_killed_and_still_reports_what_it_did(self):
        run = bu.Run()
        out = await bu.run_task(run, "slow", 5, 2)
        self.assertEqual(out["status"], "timed_out")
        self.assertEqual((out["steps_taken"], out["final_url"]), (1, "https://example.com/"))
        self.assertEqual(out["tokens"], {"prompt": 1000, "completion": 50})
        self.assertIsNotNone(run.proc.returncode, "the agent process is still alive")
        self.cleaned.assert_awaited_once()

    async def test_a_cancel_kills_it_at_once(self):
        run = bu.Run()
        going = asyncio.create_task(bu.run_task(run, "slow", 5, 60))
        await asyncio.sleep(1.5)
        run.cancelled.set()
        out = await asyncio.wait_for(going, 5)
        self.assertEqual(out["status"], "cancelled")
        self.assertIsNotNone(run.proc.returncode)
        self.cleaned.assert_awaited_once()

    async def test_a_cancelled_handler_still_kills_the_agent_and_closes_its_tabs(self):
        """If the request handler itself is cancelled (a client disconnect, say), nothing of the
        task may survive it."""
        run = bu.Run()
        going = asyncio.create_task(bu.run_task(run, "slow", 5, 60))
        await asyncio.sleep(1.5)
        going.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await going
        self.assertIsNotNone(run.proc.returncode, "the agent outlived its cancelled handler")
        self.cleaned.assert_awaited_once()

    async def test_a_crash_is_an_error_with_the_reason(self):
        out = await bu.run_task(bu.Run(), "crash", 5, 30)
        self.assertEqual(out["status"], "error")
        self.assertIn("something broke", out["errors"][0])
        self.cleaned.assert_awaited_once()

    async def test_an_infinite_number_in_a_result_still_serializes(self):
        out = bu.finite({"steps": [{"actions": [{"scroll": {"pages": float("inf")}}]}], "cost": 0.5})
        json.dumps(out, allow_nan=False)
        self.assertEqual((out["steps"][0]["actions"][0]["scroll"]["pages"], out["cost"]), ("inf", 0.5))

    async def test_the_child_gets_the_key_but_not_the_rest_of_the_environment(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test", "BU_TOKEN": "gateway-secret"}):
            env = bu.child_env("/tmp/x")
        self.assertEqual(env["OPENROUTER_API_KEY"], "sk-or-test")
        self.assertNotIn("BU_TOKEN", env)
        self.assertEqual((env["ANONYMIZED_TELEMETRY"], env["HOME"]), ("false", "/tmp/x"))


if __name__ == "__main__":
    unittest.main()
