"""The Firecrawl client: contracts read right, never a different tool, and every failure named."""
import asyncio
import unittest

import httpx

from data_box.providers import firecrawl as fc_mod
from data_box.providers.firecrawl import Contract, Firecrawl, FirecrawlError, OutOfCredits, TermsRequired, contract_from_item

from .fake_firecrawl import BASE, TOOLS, FakeFirecrawl


def run(coro):
    return asyncio.run(coro)


class Contracts(unittest.TestCase):
    def contract(self, provider):
        return contract_from_item(next(t for t in TOOLS if t["provider"] == provider))

    def test_required_inputs_page_limits_and_page_size(self):
        bing = self.contract("bing-com")
        self.assertEqual(bing.required, ["query"])
        self.assertEqual((bing.page_option, bing.max_page, bing.size_option, bing.page_size), ("page", 5, "count", 30))
        self.assertEqual((bing.query_option, bing.location_option), ("query", "location"))

    def test_page_size_from_the_contract_text_when_there_is_no_size_input(self):
        self.assertEqual(self.contract("maps-google-com").page_size, 20)
        self.assertEqual(self.contract("bbb-business-profiles-ratings-complaint").page_size, 15)

    def test_maps_does_not_paginate_without_a_page_input(self):
        self.assertFalse(self.contract("maps-google-com").summary()["paginates"])
        self.assertTrue(self.contract("bbb-business-profiles-ratings-complaint").summary()["paginates"])

    def test_prices(self):
        self.assertEqual(fc_mod.search_credits(10), 2)
        self.assertEqual(fc_mod.search_credits(25, 2), 12)
        self.assertEqual(fc_mod.scrape_credits(["markdown"]), 1)
        self.assertEqual(fc_mod.scrape_credits([{"type": "json", "schema": {}}]), 5)


class Client(unittest.TestCase):
    def setUp(self):
        self.fake = FakeFirecrawl()
        self.fc = self.fake.client()

    def test_inspect_returns_exactly_the_tool_asked_for_or_nothing(self):
        contract = run(self.fc.inspect("bing-com", "businesses/search"))
        self.assertEqual(contract.id, "bing-com/businesses/search")
        self.assertIsNone(run(self.fc.inspect("bing-com", "businesses/nope")))

    def test_a_missing_required_input_is_refused_before_any_call(self):
        contract = run(self.fc.inspect("bing-com", "businesses/search"))
        with self.assertRaises(ValueError):
            run(self.fc.run_tool(contract, {"location": "Austin, TX"}))
        self.assertEqual(self.fake.paid_calls(), [])

    def test_run_tool_returns_records_and_what_it_cost(self):
        contract = run(self.fc.inspect("bbb-business-profiles-ratings-complaint", "businesses/search"))
        out = run(self.fc.run_tool(contract, {"query": "roofing", "page": 3}))
        self.assertEqual((len(out["records"]), out["credits"]), (10, 1.0))

    def test_out_of_credits_and_terms_are_named(self):
        contract = run(self.fc.inspect("bing-com", "businesses/search"))
        self.fake.fail["bing-com"] = 402
        with self.assertRaises(OutOfCredits):
            run(self.fc.run_tool(contract, {"query": "x"}))

        def terms(_request):
            return httpx.Response(403, json={"success": False, "error": {"code": "THIRD_PARTY_DATA_TERMS_REQUIRED",
                                                                         "message": "accept the terms"}})
        gated = Firecrawl(key="k", base=BASE, transport=httpx.MockTransport(terms))
        with self.assertRaises(TermsRequired):
            run(gated.run_tool(Contract("apollo", "people/search"), {}))

    def test_an_error_inside_the_result_is_a_failure_not_an_empty_success(self):
        def errored(_request):
            return httpx.Response(200, json={"success": True, "data": {"alexandria": [{"error": {"message": "upstream down"}}]}})
        fc = Firecrawl(key="k", base=BASE, transport=httpx.MockTransport(errored))
        with self.assertRaises(FirecrawlError) as caught:
            run(fc.run_tool(Contract("bing-com", "businesses/search"), {}))
        self.assertIn("upstream down", str(caught.exception))

    def test_a_429_is_retried_once(self):
        seen = []

        def limited(_request):
            seen.append(1)
            if len(seen) == 1:
                return httpx.Response(429, json={"success": False, "error": "slow down"}, headers={"retry-after": "0"})
            return httpx.Response(200, json={"success": True, "data": {"remainingCredits": 7}})
        fc = Firecrawl(key="k", base=BASE, transport=httpx.MockTransport(limited))
        self.assertEqual(run(fc.credits())["remaining"], 7)
        self.assertEqual(len(seen), 2)

    def test_a_transport_failure_is_an_unknown_outcome(self):
        def broken(_request):
            raise httpx.ConnectTimeout("timed out")
        fc = Firecrawl(key="k", base=BASE, transport=httpx.MockTransport(broken))
        with self.assertRaises(FirecrawlError) as caught:
            run(fc.credits())
        self.assertEqual(caught.exception.status, 0)

    def test_no_key_no_call(self):
        with self.assertRaises(FirecrawlError):
            run(Firecrawl(key="").credits())


if __name__ == "__main__":
    unittest.main()
