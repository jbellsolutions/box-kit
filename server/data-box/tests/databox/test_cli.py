import unittest

from data_box.cli import parse


class Parse(unittest.TestCase):
    def test_the_first_required_argument_is_positional(self):
        self.assertEqual(parse("scrape", ["https://a.test", "--format", "text"]), {"url": "https://a.test", "format": "text"})

    def test_values_that_are_json_are_sent_as_json(self):
        args = parse("scrape", ["https://a.test", "--max-cost-usd", "0.2", "--wait-seconds=5"])
        self.assertEqual(args["max_cost_usd"], 0.2)
        self.assertEqual(args["wait_seconds"], 5)

    def test_a_string_argument_stays_a_string(self):
        self.assertEqual(parse("scrape", ["--url", "123"])["url"], "123")

    def test_job_takes_action_and_id_positionally(self):
        self.assertEqual(parse("job", ["get", "job_1", "--wait-seconds", "10"]),
                         {"action": "get", "job_id": "job_1", "wait_seconds": 10})

    def test_unknown_flag_and_tool_are_usage_errors(self):
        with self.assertRaises(SystemExit):
            parse("scrape", ["https://a.test", "--colour", "red"])
        with self.assertRaises(SystemExit):
            parse("teleport", [])
        with self.assertRaises(SystemExit):
            parse("scrape", ["https://a.test", "https://b.test"])


if __name__ == "__main__":
    unittest.main()
