"""The four steps: a plan surveys every source, nothing paid runs without approval, execution stays
inside the approved amount, resumes without paying twice, and dedupes across lanes."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data_box import config, execution, planning
from data_box.jobs import Runner
from data_box.ledger import Conflict, Ledger
from data_box.providers.firecrawl import Contract
from data_box.tools import Box, HANDLERS

from .fake_firecrawl import FakeFirecrawl

PULL = {"request": "roofing contractors in Austin TX", "queries": ["roofing contractors"], "geo": ["Austin, TX"],
        "count": 50, "fields": ["phone", "website"]}


class Harness(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test", "DATABOX_STATE_DIR": str(self.state)})
        env.start()
        self.addCleanup(env.stop)
        self.fake = FakeFirecrawl()
        self.ledger = Ledger(self.state / "l.sqlite")
        self.box = Box(self.ledger, Runner(self.ledger), firecrawl=self.fake.client)

    def call(self, tool, args):
        async def go():
            result = await HANDLERS[tool](args, self.box)
            await self.box.runner.shutdown()
            return result
        return asyncio.run(go())

    def plan(self, **extra):
        answer = self.call("plan", {**PULL, **extra})
        self.assertEqual(answer["status"], "succeeded", answer)
        return answer["plan"]

    def execute(self, plan_id, **extra):
        return self.call("execute", {"plan_id": plan_id, "approve": True, "wait_seconds": 60, **extra})


class Survey(Harness):
    def test_every_tier_is_listed_in_order_with_why_each_can_or_cannot_run(self):
        body = self.call("sources", {"request": "roofing contractors in Austin TX", "fields": ["phone"]})
        tiers = [c["tier"] for c in body["candidates"]]
        self.assertEqual(tiers, sorted(tiers))
        names = {c.get("provider") or c["source"] for c in body["candidates"]}
        for expected in ("bing-com", "maps-google-com", "bbb-business-profiles-ratings-complaint",
                         "discolike", "brightdata", "apify"):
            self.assertIn(expected, names)
        for c in body["candidates"]:
            self.assertTrue(c["can_run"] or c["why_not"], c)
        apify = next(c for c in body["candidates"] if c["source"] == "apify")
        self.assertIn("not needed", apify["note"])
        self.assertEqual(self.fake.paid_calls(), [], "the survey is free")

    def test_terms_gated_and_unfillable_lanes_cannot_run(self):
        people = self.call("sources", {"request": "roofing company owners", "entity": "person"})
        apollo = next(c for c in people["candidates"] if c.get("provider") == "apollo")
        self.assertFalse(apollo["can_run"])
        self.assertIn("accepted by a person", apollo["why_not"])
        body = self.call("sources", {"request": "roofing contractors in Austin TX"})
        fcia = next(c for c in body["candidates"] if c.get("provider") == "fcia-org")
        self.assertFalse(fcia["can_run"])

    def test_without_a_firecrawl_key_the_survey_still_lists_every_source(self):
        with mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": ""}):
            body = self.call("sources", {"request": "roofing contractors"})
        bbb = next(c for c in body["candidates"] if c.get("provider") == "bbb-business-profiles-ratings-complaint")
        self.assertIn("FIRECRAWL_API_KEY", bbb["why_not"])


class Catalog(Harness):
    """The survey reads Alexandria's whole catalog for what the request is about, not a fixed list."""

    def test_the_categories_a_request_is_about_are_browsed_in_full(self):
        body = self.call("sources", {"request": "roofing contractors in Austin TX", "fields": ["phone"]})
        browsed = [c["id"] for c in body["alexandria"]["categories_browsed"]]
        self.assertIn("local-businesses", browsed)
        self.assertNotIn("jobs", browsed)
        self.assertNotIn("real-estate", browsed)
        local = next(c for c in body["alexandria"]["categories_browsed"] if c["id"] == "local-businesses")
        self.assertEqual(local["tools"], 7, "every page of the category was followed")
        self.assertNotIn("people", browsed, "a business pull does not browse people")
        names = {c.get("provider") for c in body["candidates"]}
        self.assertIn("yellowpages-com", names, "a lane only the category browse finds")
        realty = self.call("sources", {"request": "real estate agents in Austin TX"})
        self.assertIn("real-estate", [c["id"] for c in realty["alexandria"]["categories_browsed"]])

    def test_a_tool_that_does_not_return_the_entity_is_listed_but_not_used(self):
        body = self.call("sources", {"request": "roofing contractors in Austin TX"})
        jobs = next(c for c in body["candidates"] if c.get("provider") == "ziprecruiter-com")
        self.assertFalse(jobs["can_run"])
        self.assertIn("no business fields", jobs["why_not"])

    def test_a_tool_about_something_else_is_listed_but_never_planned_or_paid(self):
        body = self.call("sources", {"request": "roofing contractors in Austin TX", "fields": ["phone", "website"]})
        for provider in ("golfnow-com", "seatgeek-com"):
            trap = next(c for c in body["candidates"] if c.get("provider") == provider)
            self.assertFalse(trap["can_run"], trap)
            self.assertIn("not about this request", trap["why_not"])
            self.assertIn("roof", trap["why_not"])
        plan = self.plan(max_lanes=6)
        lanes = [lane["lane"] for lane in plan["body"]["step_3_game_plan"]["lanes"]]
        self.assertFalse([lane for lane in lanes if lane.startswith(("golfnow", "seatgeek"))], lanes)
        self.assertEqual(self.fake.paid_calls("golfnow-com") + self.fake.paid_calls("seatgeek-com"), [])
        self.fake.balance = -330  # preflight is skipped, so ranking alone picks the lanes
        broke = self.plan(max_lanes=6)
        lanes = [lane["lane"] for lane in broke["body"]["step_3_game_plan"]["lanes"]]
        self.assertFalse([lane for lane in lanes if lane.startswith(("golfnow", "seatgeek"))], lanes)

    def test_a_place_in_the_request_goes_to_the_location_input(self):
        it = planning.intake({"request": "roofing contractors in Austin TX", "kind": "pull"})
        self.assertEqual((it["queries"], it["geo"]), (["roofing contractors"], ["Austin TX"]))
        plan = self.call("plan", {"request": "roofing contractors in Austin TX", "fields": ["phone", "website"], "count": 50})["plan"]
        self.assertTrue(plan["body"]["step_3_game_plan"]["lanes"])
        for lane in plan["body"]["step_3_game_plan"]["lanes"]:
            for cell in lane["cells"]:
                self.assertNotIn("Austin", cell["query"], lane["lane"])
                self.assertEqual(cell["geo"], "Austin TX")
        kept = planning.intake({"request": "roofers in Austin", "queries": ["roofers"], "kind": "pull"})
        self.assertEqual(kept["geo"], [], "explicit queries are taken as given")

    def test_what_a_request_is_about(self):
        it = planning.intake({"request": "roofing contractors in Austin TX"})
        self.assertEqual(planning.topic(it), ["roof"], "the place is not the topic")
        it = planning.intake({"request": "roofers", "geo": ["Austin, TX"]})
        self.assertEqual(planning.topic(it), ["roof"])

        def tool(capability, description, provider="x-com"):
            return Contract(provider=provider, capability=capability, description=description)
        self.assertIsNone(planning.about_request(tool("contractors/find", "Find roofing contractors near a city"), it))
        self.assertIsNone(planning.about_request(tool("businesses/search", "Any local business"), it))
        self.assertIn("not about", planning.about_request(tool("businesses/search_members", "Firestop contractors"), it))
        generic = planning.intake({"request": "contractors", "geo": ["Austin, TX"]})
        self.assertIn("names no trade", planning.about_request(tool("members/search", "Contractors directory"), generic))

    def test_a_named_source_skips_the_topic_check(self):
        body = self.call("sources", {"request": "roofing contractors in Austin TX", "sources": ["golfnow"]})
        golf = next(c for c in body["candidates"] if c.get("provider") == "golfnow-com")
        self.assertTrue(golf["can_run"], golf)

    def test_a_person_pull_does_not_run_business_lanes(self):
        body = self.call("sources", {"request": "roofing company owners", "entity": "person"})
        bing = next(c for c in body["candidates"] if c.get("provider") == "bing-com")
        self.assertFalse(bing["can_run"])
        self.assertIn("business lane", bing["why_not"])

    def test_the_catalog_is_read_once_a_day(self):
        self.call("sources", {"request": "roofing contractors"})
        self.call("sources", {"request": "roofing contractors"})
        self.assertEqual(sum(1 for c in self.fake.calls if c["provider"] == "discover-categories"), 1)

    def test_every_source_that_serves_can_be_chosen_and_preflight_is_the_judge(self):
        plan = self.plan(max_lanes=5)
        game = plan["body"]["step_3_game_plan"]
        lanes = [lane["lane"] for lane in game["lanes"]]
        self.assertIn("yellowpages-com/businesses/search", lanes, "an unverified lane that proves itself is used")
        self.assertNotIn("junk-directory/businesses/search", lanes)
        junk = next(p for p in game["passed_over"] if p["lane"].startswith("junk-directory"))
        self.assertIn("preflight", junk["why"])
        result = self.execute(plan["plan_id"])
        self.assertEqual(result["off_target"], 0, "the dropped lane's preflight rows are not in the list")
        self.assertGreater(result["found_by_2_or_more_lanes"], 0)


class Guards(Harness):
    """The ways a pull burned ~8,000 credits on 2026-09-28, each closed."""

    def test_a_cell_stops_paging_when_pages_repeat(self):
        self.fake.repeat_from_page = 2  # Bing's deep pages re-fetch page 1
        plan = self.plan(count=500, sources=["bing"])
        self.assertEqual(plan["body"]["step_3_game_plan"]["lanes"][0]["pages_per_cell"], 3)
        result = self.execute(plan["plan_id"])
        pages = [c["options"].get("page", 1) for c in self.fake.paid_calls("bing-com")]
        self.assertEqual(pages, [1, 2], "page 2 repeated page 1, so page 3 was never bought")
        self.assertEqual(result["lanes"][0]["cells_stopped_repeating"], 1)

    def test_a_resumed_run_does_not_come_back_for_repeating_pages(self):
        self.fake.repeat_from_page = 2
        plan = self.plan(count=500, queries=["roofing contractors"], geo=["Austin, TX", "Dallas, TX"], sources=["bing"])
        spent = plan["preflight_spent_usd"]
        rate = config.firecrawl_usd_per_credit()
        first = self.execute(plan["plan_id"], max_cost_usd=round(spent + 2 * 5 * rate, 6))  # 2 more Bing calls: one page short
        self.assertFalse(first["complete"])
        self.execute(plan["plan_id"])
        by_cell = {}
        for c in self.fake.paid_calls("bing-com"):
            by_cell.setdefault(c["options"]["location"], []).append(c["options"].get("page", 1))
        for place, pages in by_cell.items():
            self.assertNotIn(3, pages, f"{place}: page 3 bought after page 2 repeated")
            self.assertEqual(len(pages), len(set(pages)))

    def test_the_balance_never_goes_below_the_floor(self):
        plan = self.plan(count=500, queries=["roofing contractors", "roofers"], geo=["Austin, TX", "Dallas, TX"])
        self.fake.balance = 12
        result = self.execute(plan["plan_id"])
        self.assertGreaterEqual(self.fake.balance, 0)
        self.assertFalse(result["complete"])
        self.assertIn("balance", result["note"])

    def test_bing_and_maps_run_two_queries_a_place(self):
        plan = self.plan(queries=["roofing contractors", "roofers", "roof repair"], max_lanes=6, preflight=False)
        lanes = {lane["provider"]: lane for lane in plan["body"]["step_3_game_plan"]["lanes"]}
        self.assertEqual(len(lanes["bing-com"]["cells"]), 2)
        self.assertIn("2 queries a place", lanes["bing-com"]["note"])
        self.assertEqual(len(lanes["bbb-business-profiles-ratings-complaint"]["cells"]), 3)

    def test_the_plan_says_its_cost_is_a_worst_case(self):
        game = self.plan()["body"]["step_3_game_plan"]
        self.assertIn("worst case", game["cost_note"])


class Planning(Harness):
    def test_a_plan_has_all_three_steps_and_waits_for_approval(self):
        plan = self.plan()
        self.assertEqual(plan["status"], "awaiting_approval")
        body = plan["body"]
        self.assertEqual(set(body) >= {"step_1_intake", "step_2_survey", "step_3_game_plan", "step_4"}, True)
        game = body["step_3_game_plan"]
        lanes = {lane["lane"]: lane for lane in game["lanes"]}
        self.assertEqual(list(lanes)[0], "bing-com/businesses/search", "phone+website: Bing leads on field fit")
        self.assertLessEqual(lanes["bing-com/businesses/search"]["pages_per_cell"], 3, "the skill's Bing page cap")
        self.assertTrue(all(lane["pages_per_cell"] == 1 for lane in game["lanes"][1:]), "top-ups make one call a cell")
        self.assertEqual(len({lane["provider"] for lane in game["lanes"]}), 3, "three sources, not one")
        self.assertTrue(all(lane["preflight"] == "confirmed" for lane in game["lanes"]))
        self.assertNotIn("apify", json.dumps(game["lanes"]))
        self.assertGreater(plan["budget_usd"], game["usd_total"])

    def test_preflight_is_the_only_spend_and_is_reported(self):
        plan = self.plan()
        preflight = plan["body"]["step_3_game_plan"]["preflight"]
        self.assertTrue(all(r.get("ok") for r in preflight["results"]), preflight)
        self.assertEqual(len(self.fake.paid_calls()), len(preflight["results"]))
        self.assertLessEqual(preflight["credits"], config.preflight_max_credits())
        self.assertAlmostEqual(plan["preflight_spent_usd"], preflight["usd"], places=4)
        self.assertEqual(5000 - self.fake.balance, preflight["credits"])

    def test_preflight_never_spends_past_max_cost(self):
        plan = self.plan(max_cost_usd=0.01)  # 2.6 credits: BBB (1) fits, Bing and Maps (5 each) do not
        results = plan["body"]["step_3_game_plan"]["preflight"]["results"]
        self.assertLessEqual(plan["preflight_spent_usd"], 0.01)
        self.assertTrue(any("cap" in (r.get("skipped") or "") for r in results), results)

    def test_a_named_source_is_honoured(self):
        plan = self.plan(sources=["bbb"])
        lanes = [lane["lane"] for lane in plan["body"]["step_3_game_plan"]["lanes"]]
        self.assertEqual(lanes, ["bbb-business-profiles-ratings-complaint/businesses/search"])
        disco = self.plan(sources=["disco"])
        game = disco["body"]["step_3_game_plan"]
        self.assertEqual(game["lanes"], [])
        self.assertTrue(any("disco" in w and "D2" in w for w in game["warnings"]), game["warnings"])

    def test_an_empty_balance_skips_preflight_and_says_so(self):
        self.fake.balance = -330
        plan = self.plan()
        game = plan["body"]["step_3_game_plan"]
        self.assertEqual(game["preflight"]["results"], [])
        self.assertTrue(any("-330" in w for w in game["warnings"]))
        self.assertEqual(self.fake.paid_calls(), [])

    def test_a_failure_part_way_cancels_the_plan_and_keeps_what_preflight_spent(self):
        self.fake.fail["bbb-business-profiles-ratings-complaint"] = RuntimeError("boom")
        answer = self.call("plan", PULL)
        self.assertEqual(answer["status"], "failed")
        plans = self.ledger.plans(5)
        self.assertEqual(plans[0]["status"], "cancelled")
        self.assertGreater(plans[0]["preflight_spent_usd"], 0)
        with self.assertRaises(Conflict):
            self.ledger.approve_plan(plans[0]["plan_id"], 1)

    def test_intake_refuses_before_a_job_exists(self):
        with self.assertRaises(ValueError):
            self.call("plan", {"kind": "scrape"})
        self.assertEqual(self.ledger.jobs(5), [])


class Execution(Harness):
    def test_nothing_runs_without_approve_true(self):
        plan = self.plan()
        before = len(self.fake.paid_calls())
        for bad in ({"plan_id": plan["plan_id"]}, {"plan_id": plan["plan_id"], "approve": False}):
            with self.assertRaises(ValueError):
                self.call("execute", bad)
        self.assertEqual(len(self.fake.paid_calls()), before)
        with self.assertRaises(ValueError):
            self.call("execute", {"plan_id": "plan_nope", "approve": True})

    def test_an_expired_plan_is_refused(self):
        plan = self.plan()
        with self.ledger.db() as db:
            db.execute("UPDATE plans SET expires=0 WHERE id=?", (plan["plan_id"],))
        with self.assertRaises(Conflict):
            self.execute(plan["plan_id"])

    def test_approving_more_than_the_plan_is_refused(self):
        plan = self.plan()
        with self.assertRaises(Conflict):
            self.execute(plan["plan_id"], max_cost_usd=plan["budget_usd"] + 1)

    def test_a_pull_stays_inside_its_budget_dedupes_and_reconciles(self):
        plan = self.plan()
        result = self.execute(plan["plan_id"])
        self.assertEqual(result["status"], "succeeded", result)
        self.assertTrue(result["complete"])
        self.assertGreaterEqual(result["unique_records"], 50)
        self.assertLess(result["unique_records"], result["raw_records"], "lanes overlap, so dedupe must collapse some")
        spent = self.ledger.plan_spent(plan["plan_id"])
        self.assertLessEqual(spent, plan["budget_usd"])
        provider_credits = 5000 - self.fake.balance
        self.assertAlmostEqual(spent, provider_credits * config.firecrawl_usd_per_credit(), places=4)
        self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "done")
        rows = execution.records_for(plan["plan_id"])
        self.assertEqual(len(rows), result["unique_records"])
        merged = [r for r in rows if len(r["sources"]) > 1]
        self.assertTrue(merged, "a business found by two lanes is one row naming both")

    def test_it_stops_calling_once_the_count_is_reached(self):
        plan = self.plan(count=10)
        before = len(self.fake.paid_calls())
        result = self.execute(plan["plan_id"])
        self.assertTrue(result["complete"])
        self.assertEqual(len(self.fake.paid_calls()), before, "preflight already found 10; nothing more to buy")

    def test_a_short_page_ends_the_cell(self):
        self.fake.universe = 25  # Bing: page 1 has 25 of 30, so page 2 is never asked for
        plan = self.plan(count=200, sources=["bing"])
        self.execute(plan["plan_id"])
        pages = [c["options"].get("page", 1) for c in self.fake.paid_calls("bing-com")]
        self.assertEqual(pages, [1])

    def test_resume_never_pays_for_a_page_twice(self):
        plan = self.plan(count=200)  # more than exists: every planned page runs
        game = plan["body"]["step_3_game_plan"]
        first = self.execute(plan["plan_id"], max_cost_usd=round(plan["preflight_spent_usd"] + 0.02, 4))
        self.assertFalse(first["complete"])
        self.assertIn("budget", first["note"])
        self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "approved")
        second = self.execute(plan["plan_id"])
        self.assertTrue(second["complete"], second)
        seen = [(c["provider"], json.dumps(c["options"], sort_keys=True)) for c in self.fake.paid_calls()]
        self.assertEqual(len(seen), len(set(seen)), "a page was bought twice")
        self.assertLessEqual(self.ledger.plan_spent(plan["plan_id"]), plan["budget_usd"])
        failed_preflights = sum(1 for p in game["passed_over"] if p["why"].startswith("preflight"))
        self.assertLessEqual(len(seen), sum(lane["calls"] for lane in game["lanes"]) + failed_preflights)

    def test_running_out_of_credits_stops_and_leaves_the_plan_resumable(self):
        plan = self.plan(count=200)
        self.fake.out_of_credits_after = len(self.fake.paid_calls()) + 1
        result = self.execute(plan["plan_id"])
        self.assertFalse(result["complete"])
        self.assertIn("out of credits", result["note"])
        self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "approved")

    def test_two_executes_at_once_start_one_job_and_never_overspend(self):
        plan = self.plan(count=200)
        self.fake.delay = 0.05

        async def go():
            calls = [HANDLERS["execute"]({"plan_id": plan["plan_id"], "approve": True, "wait_seconds": 30}, self.box)
                     for _ in range(2)]
            results = await asyncio.gather(*calls, return_exceptions=True)
            await self.box.runner.shutdown()
            return results
        results = asyncio.run(go())
        jobs = [j for j in self.ledger.jobs(20) if j["tool"] == "execute"]
        self.assertEqual(len(jobs), 1, results)
        self.assertLessEqual(self.ledger.plan_spent(plan["plan_id"]), plan["budget_usd"])
        seen = [(c["provider"], json.dumps(c["options"], sort_keys=True)) for c in self.fake.paid_calls()]
        self.assertEqual(len(seen), len(set(seen)))

    def test_a_run_that_buys_nothing_is_not_a_success(self):
        plan = self.plan(count=200)
        self.fake.balance = 0
        result = self.execute(plan["plan_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("balance", result["error"])
        self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "approved")

    def test_results_and_export_read_the_deduped_records(self):
        plan = self.plan()
        job_id = self.execute(plan["plan_id"])["job_id"]
        page = self.call("job", {"action": "results", "job_id": job_id, "limit": 5})
        self.assertEqual(len(page["items"]), 5)
        self.assertIn("phone", page["items"][0])
        csv_text = self.call("job", {"action": "export", "job_id": job_id, "format": "csv"})["content"]
        self.assertTrue(csv_text.startswith("name,phone,email,website,address"))

    def test_a_cancelled_run_leaves_the_plan_resumable_and_charges_the_call_in_flight(self):
        plan = self.plan(count=200)
        self.fake.delay = 0.5

        async def go():
            started = await HANDLERS["execute"]({"plan_id": plan["plan_id"], "approve": True, "wait_seconds": 0}, self.box)
            await asyncio.sleep(0.2)
            self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "executing")
            cancelled = await self.box.runner.cancel(started["job_id"])
            await self.box.runner.shutdown()
            return cancelled
        job = asyncio.run(go())
        self.assertEqual(job["status"], "cancelled")
        self.assertGreater(job["spent_usd"], 0, "a call whose outcome is unknown is charged in full")
        self.assertEqual(self.ledger.plan(plan["plan_id"])["status"], "approved")


class Plain(Harness):
    def test_a_blocked_scrape_returns_a_plan_and_executing_it_reaches_rung_1(self):
        from data_box import fetch

        async def blocked(url, **_kw):
            return fetch.Page(url=url, final_url=url, status_code=403, content_type="text/html",
                              body=b"<html><title>Just a moment...</title>cf-chl</html>")
        with mock.patch.object(fetch, "get", blocked):
            scraped = self.call("scrape", {"url": "https://guarded.test/"})
        self.assertIn("blocked", scraped)
        self.assertEqual(scraped["cost_usd"], 0.0)
        made = scraped["plan"]
        self.assertEqual(made["status"], "awaiting_approval")
        self.assertEqual([r["rung"] for r in made["rungs"]], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(self.fake.paid_calls(), [], "a paid rung never runs without approval")
        result = self.execute(made["plan_id"])
        self.assertEqual((result["rung"], result["status"]), (1, "succeeded"))
        self.assertIn("Real page", result["content"])

    def test_search_plan(self):
        made = self.call("plan", {"request": "best roofing software", "kind": "search", "limit": 10})["plan"]
        result = self.execute(made["plan_id"])
        self.assertEqual((result["records"], result["complete"]), (10, True))


class Files(unittest.TestCase):
    def test_retention_deletes_old_plan_folders(self):
        state = Path(tempfile.mkdtemp())
        with mock.patch.dict(os.environ, {"DATABOX_STATE_DIR": str(state)}):
            old = planning.store_for("plan_old")
            new = planning.store_for("plan_new")
            os.utime(old, (0, 0))
            self.assertEqual(planning.purge_old(), 1)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertEqual(oct(new.stat().st_mode & 0o777), "0o700")

    def test_field_names_match_whatever_their_case_or_punctuation(self):
        self.assertEqual(planning.field_fit(["phone", "website"], ["displayPhone", "Website-URL"])[0], 1.0)
        row = execution.normalize({"businessName": "Roofer 9", "displayPhone": "512 555 0009", "websiteUrl": "roofer9.test"})
        self.assertEqual((row["name"], row["phone"], row["website"]), ("Roofer 9", "512 555 0009", "roofer9.test"))

    def test_normalize_and_dedupe_keys(self):
        a = execution.normalize({"name": "Roofer 5, LLC", "phones": ["512-555-0005"], "address": "105 Main Street"})
        b = execution.normalize({"business_name": "roofer 5 llc", "display_phone": "(512) 555-0005"})
        self.assertEqual(execution.dedupe_keys(a, {})[0], execution.dedupe_keys(b, {})[0])


if __name__ == "__main__":
    unittest.main()
