"""act on a hosted browser: the step engine (stepper.py), with the page and Jev faked.

The page is faked at the Stepper's own seams (js, elements, mouse, key), so these tests pin the
decisions, the questions back to the caller, and the outcome reporting, not CDP plumbing.
"""
import time
import unittest
from unittest import mock

from gateway import decide, stepper, tools
from gateway.sessions import Sessions


def choice(pick, confidence=0.95, probs=None):
    return {"type": "choice", "choice": pick, "confidence": confidence, "probabilities": probs or {pick: confidence}}


def answers(intent="click", target="e0", target_p=0.95, risky=0.05, submit=0.1, probs=None, direction="down"):
    return {"answers": {"intent": choice(intent), "target": choice(target, target_p, probs),
                        "risky": {"type": "noul", "noul": risky}, "submit": {"type": "noul", "noul": submit},
                        "direction": choice(direction)},
            "model": "jev-test", "ms": 12, "input_tokens": 100}


ELEMENTS = [{"kind": "link", "text": "Pricing", "label": "", "placeholder": "", "name": "", "href": "/pricing", "shown": True},
            {"kind": "button", "text": "Delete account", "label": "", "placeholder": "", "name": "", "href": "", "shown": True},
            {"kind": "text box", "text": "", "label": "Search", "placeholder": "Search", "name": "q", "href": "", "shown": True}]


class FakePage(stepper.Stepper):
    def __init__(self, url="https://example.com/", box=True):
        super().__init__(cdp=None, page="p", check_url=self._check)
        self.url, self.box, self.did = url, box, []

    async def _check(self, url):
        return url

    async def js(self, expr):
        if "location.href" in expr and "title" in expr:
            return {"url": self.url, "title": "Example"}
        if "readyState" in expr:
            return "complete"
        if "getBoundingClientRect" in expr:
            return {"x": 10, "y": 20, "tag": "a"} if self.box else None
        return None

    async def elements(self):
        return ELEMENTS

    async def mouse(self, x, y):
        self.did.append(("click", x, y))

    async def key(self, name):
        self.did.append(("key", name))


class Steps(unittest.TestCase):
    def test_then_and_a_new_verb_after_and_split_steps(self):
        self.assertEqual(stepper.split_steps("open https://x.com then click Pricing and type 'shoes' into search"),
                         ["open https://x.com", "click Pricing", "type 'shoes' into search"])

    def test_and_inside_a_name_does_not_split(self):
        self.assertEqual(stepper.split_steps("click salt and pepper"), ["click salt and pepper"])

    def test_more_than_four_steps_is_refused(self):
        with self.assertRaises(ValueError):
            stepper.split_steps("click a then click b then click c then click d then click e")

    def test_text_to_type_comes_from_quotes_or_after_the_verb(self):
        self.assertEqual(stepper.text_to_type("type 'running shoes' into the search box"), "running shoes")
        self.assertEqual(stepper.text_to_type("search for blue widgets"), "blue widgets")
        self.assertIsNone(stepper.text_to_type("click Pricing"))


class Running(unittest.IsolatedAsyncioTestCase):
    element_risk = 0.05

    def jev(self, first):
        """Jev's step answer, then its answer about the chosen element whenever the stepper asks that."""
        queue = list(first) if isinstance(first, list) else [first]

        async def ask(state, questions):
            if "element" in state:
                return {"answers": {"risky": {"type": "noul", "noul": self.element_risk}}, "ms": 9}
            return queue.pop(0)
        return mock.patch.object(decide, "ask", mock.AsyncMock(side_effect=ask))

    async def run_steps(self, page, steps, jev, **kw):
        with self.jev(jev):
            return await page.run(steps, **kw)

    async def test_a_clear_click_runs_and_reports_jev_decided(self):
        page = FakePage()
        out, pending = await self.run_steps(page, ["click Pricing"], answers())
        self.assertIsNone(pending)
        self.assertEqual(out["status"], "done")
        self.assertEqual(out["steps"][0]["decided_by"], "jev")
        self.assertIn('link "Pricing"', out["steps"][0]["did"])
        self.assertEqual(page.did, [("click", 10, 20)])

    async def test_an_open_step_navigates_without_asking_jev(self):
        page = FakePage()
        page.cdp = mock.Mock(send=mock.AsyncMock(return_value={}))
        ask = mock.AsyncMock()
        with mock.patch.object(decide, "ask", ask):
            out, _ = await page.run(["open https://example.org/a"])
        ask.assert_not_awaited()
        self.assertEqual((out["status"], out["steps"][0]["decided_by"]), ("done", "code"))
        page.cdp.send.assert_awaited_with("Page.navigate", {"url": "https://example.org/a"}, session="p")

    async def test_unsure_asks_then_the_pick_runs_on_the_picked_element(self):
        page = FakePage()
        unsure = answers(target="e0", target_p=0.3, probs={"e0": 0.3, "e2": 0.25, "none": 0.4})
        out, pending = await self.run_steps(page, ["click the search thing"], unsure)
        self.assertEqual(out["status"], "needs_clarification")
        self.assertEqual([o["pick"] for o in out["options"]], ["e0", "e2"])
        self.assertEqual(page.did, [])
        with self.jev([]):
            out, pending = await page.run([], pending=pending, pick="e2")
        self.assertIsNone(pending)
        self.assertEqual((out["status"], out["steps"][0]["decided_by"]), ("done", "you"))
        self.assertIn("Search", out["steps"][0]["did"])

    async def test_a_pick_outside_the_options_is_refused(self):
        page = FakePage()
        unsure = answers(target_p=0.2, probs={"e0": 0.2, "e1": 0.2})
        _, pending = await self.run_steps(page, ["click it"], unsure)
        with self.assertRaises(ValueError):
            await page.run([], pending=pending, pick="e9")

    async def test_a_risky_step_waits_for_confirm(self):
        page = FakePage()
        out, pending = await self.run_steps(page, ["click delete account"], answers(target="e1", risky=0.9))
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertIn("Delete account", out["action"])
        self.assertEqual(page.did, [])
        cancelled, again = await page.run([], pending=pending, confirm=False)
        self.assertEqual((cancelled["status"], again, page.did), ("failed", None, []))
        done, _ = await page.run([], pending=pending, confirm=True)
        self.assertEqual(done["status"], "done")
        self.assertEqual(page.did, [("click", 10, 20)])

    async def test_a_risky_pick_after_a_clarification_still_needs_confirm(self):
        page = FakePage()
        unsure = answers(target="e1", target_p=0.3, risky=0.85, probs={"e1": 0.3, "e0": 0.3})
        _, pending = await self.run_steps(page, ["click the button"], unsure)
        with self.jev([]):
            out, pending = await page.run([], pending=pending, pick="e1")
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertEqual(page.did, [])

    async def test_a_harmless_wording_on_a_risky_element_still_needs_confirm(self):
        page = FakePage()
        self.element_risk = 0.9                    # "click the button" when the button is "Submit order"
        out, _ = await self.run_steps(page, ["click the button"], answers(target="e1", risky=0.1))
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertEqual(page.did, [])

    async def test_a_vanished_element_fails_the_step(self):
        page = FakePage(box=False)
        out, _ = await self.run_steps(page, ["click Pricing"], answers())
        self.assertEqual((out["status"], out["steps"][0]["outcome"]), ("failed", "failed"))

    async def test_typing_without_text_fails_the_step(self):
        page = FakePage()
        out, _ = await self.run_steps(page, ["fill the search box"], answers(intent="type_text", target="e2"))
        self.assertEqual(out["status"], "failed")

    async def test_landing_off_the_public_web_is_refused(self):
        page = FakePage(url="http://127.0.0.1:3000/")
        page.cdp = mock.Mock(send=mock.AsyncMock(return_value={}))
        out, _ = await self.run_steps(page, ["click Pricing"], answers())
        self.assertEqual((out["status"], out["steps"][0]["outcome"]), ("failed", "refused"))

    async def test_a_blank_tab_is_not_off_the_public_web(self):
        page = FakePage(url="about:blank")
        out, _ = await self.run_steps(page, ["scroll down"], answers(intent="scroll"))
        self.assertEqual(out["status"], "done")


class FakeCloud:
    def __init__(self, *_):
        pass


class HostedAct(unittest.IsolatedAsyncioTestCase):
    async def test_an_id_this_box_did_not_create_is_not_a_session(self):
        """No id from anywhere else (another tool's profile, a guess) can reach a browser through this box."""
        store = Sessions(FakeCloud())
        for foreign in ("p1", "3f2c-another-tools-profile", ""):
            with self.assertRaises(ValueError):
                store.get(foreign or "nope")

    async def test_an_answer_with_nothing_waiting_is_refused(self):
        store = Sessions(FakeCloud({}))
        with self.assertRaises(ValueError):
            await tools._act_hosted(store, {"pick": "e0"}, "pick", time.monotonic())

    async def test_an_expired_question_is_dropped(self):
        store = Sessions(FakeCloud({}))
        store.items["default"].pending = {"kind": "clarify", "at": time.monotonic() - 999}
        with self.assertRaises(ValueError):
            await tools._act_hosted(store, {"pick": "e0"}, "pick", time.monotonic())
        self.assertIsNone(store.items["default"].pending)

    async def test_the_wrong_kind_of_answer_is_refused(self):
        store = Sessions(FakeCloud({}))
        store.items["default"].pending = {"kind": "confirm", "at": time.monotonic()}
        with self.assertRaises(ValueError):
            await tools._act_hosted(store, {"pick": "e0"}, "pick", time.monotonic())

    async def test_act_is_listed_with_the_cloud_and_a_decision_model(self):
        with mock.patch.object(tools, "cloud_client", lambda: object()), \
                mock.patch.dict("os.environ", {"TYPESAFE_API_KEY": "k"}):
            self.assertIn("act", [t["name"] for t in tools.offered_tools()])
        with mock.patch.object(tools, "cloud_client", lambda: None):
            self.assertNotIn("act", [t["name"] for t in tools.offered_tools()])


if __name__ == "__main__":
    unittest.main()


class ScratchFallback(unittest.IsolatedAsyncioTestCase):
    """When Browser Use cannot open a browser, a session's fresh browser opens on Browserbase instead."""

    def store(self):
        from contextlib import asynccontextmanager
        from gateway.cloud import CloudUnavailable

        class Cloud:
            @asynccontextmanager
            async def browser(self, **_kw):
                raise CloudUnavailable("Browser Use is down")
                yield  # pragma: no cover

        cdp = mock.Mock(page=mock.AsyncMock(return_value="p"), reader=mock.Mock(done=lambda: False))
        bb, opened = mock.Mock(), []

        @asynccontextmanager
        async def browser(minutes=None):
            opened.append(minutes)
            yield cdp, {"session_id": "bb-1", "live_url": None}
        bb.browser = browser
        return Sessions(Cloud(), fallback=bb), opened

    async def test_the_scratch_browser_opens_on_browserbase(self):
        store, opened = self.store()
        held = store.items["default"]
        await store.ensure_open(held)
        self.assertEqual((held.engine, len(opened)), ("browserbase", 1))
        await store.close_all()

    async def test_a_created_session_falls_back_too(self):
        store, opened = self.store()
        held = store.create("agent a")
        await store.ensure_open(held)
        self.assertEqual((held.engine, len(opened)), ("browserbase", 1))
        await store.close_all()
