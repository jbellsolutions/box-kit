import tempfile
import unittest
from pathlib import Path

from data_box.ledger import Conflict, Ledger, money


class Money(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(Path(tempfile.mkdtemp()) / "l.sqlite")

    def running_job(self, cap=1.0):
        job, _ = self.ledger.create_job("run", {"x": 1}, None, cap)
        self.ledger.set_status(job["job_id"], "running")
        return job["job_id"]

    def test_money_rounds_up_to_a_micro_dollar(self):
        self.assertEqual(money(0.0000001), 1)
        with self.assertRaises(ValueError):
            money(float("nan"))

    def test_a_reservation_that_does_not_fit_never_starts(self):
        job_id = self.running_job(0.10)
        self.ledger.reserve(job_id, 0.08, "apify")
        with self.assertRaises(Conflict) as caught:
            self.ledger.reserve(job_id, 0.05, "firecrawl")
        self.assertIn("raise max_cost_usd", str(caught.exception))

    def test_settle_charges_the_real_amount_and_frees_the_rest(self):
        job_id = self.running_job(0.10)
        key = self.ledger.reserve(job_id, 0.08, "apify")
        self.ledger.settle(key, 0.03)
        job = self.ledger.job(job_id)
        self.assertEqual((job["spent_usd"], job["reserved_usd"]), (0.03, 0.0))
        self.ledger.reserve(job_id, 0.07, "apify")  # fits now

    def test_settle_without_an_amount_charges_the_whole_reservation(self):
        job_id = self.running_job()
        self.ledger.settle(self.ledger.reserve(job_id, 0.2, "x"))
        self.assertEqual(self.ledger.job(job_id)["spent_usd"], 0.2)

    def test_a_finished_job_charges_open_reservations_in_full(self):
        job_id = self.running_job()
        self.ledger.reserve(job_id, 0.4, "x")
        self.ledger.set_status(job_id, "failed", error="boom")
        job = self.ledger.job(job_id)
        self.assertEqual((job["spent_usd"], job["reserved_usd"]), (0.4, 0.0))
        with self.assertRaises(Conflict):
            self.ledger.reserve(job_id, 0.01, "x")

    def test_recover_interrupts_running_jobs_and_charges_them(self):
        job_id = self.running_job()
        self.ledger.reserve(job_id, 0.3, "x")
        self.assertEqual(self.ledger.recover(), 1)
        job = self.ledger.job(job_id)
        self.assertEqual(job["status"], "interrupted")
        self.assertEqual(job["spent_usd"], 0.3)


class Jobs(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(Path(tempfile.mkdtemp()) / "l.sqlite")

    def test_a_request_id_returns_the_first_job(self):
        first, created = self.ledger.create_job("scrape", {"url": "https://a.test", "request_id": "r1"}, "r1", 0.05)
        again, created_again = self.ledger.create_job("scrape", {"url": "https://a.test", "request_id": "r1", "wait_seconds": 5},
                                                      "r1", 0.05)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["job_id"], again["job_id"])

    def test_a_request_id_reused_for_other_work_is_refused(self):
        self.ledger.create_job("scrape", {"url": "https://a.test"}, "r1", 0)
        with self.assertRaises(Conflict):
            self.ledger.create_job("scrape", {"url": "https://b.test"}, "r1", 0)

    def test_the_first_outcome_wins(self):
        job, _ = self.ledger.create_job("scrape", {}, None, 0)
        self.ledger.set_status(job["job_id"], "cancelled", error="stop")
        self.ledger.set_status(job["job_id"], "succeeded", result={"late": True})
        final = self.ledger.job(job["job_id"])
        self.assertEqual(final["status"], "cancelled")
        self.assertNotIn("result", final)

    def test_list_and_filter(self):
        a, _ = self.ledger.create_job("scrape", {"n": 1}, None, 0)
        self.ledger.create_job("run", {"n": 2}, None, 0)
        self.ledger.set_status(a["job_id"], "succeeded", result={"items": [1, 2]})
        self.assertEqual([j["tool"] for j in self.ledger.jobs(tool="scrape")], ["scrape"])
        self.assertEqual(len(self.ledger.jobs(status="queued")), 1)
        self.assertNotIn("result", self.ledger.jobs()[0])


if __name__ == "__main__":
    unittest.main()
