"""A fake Firecrawl for tests: the endpoints data-box calls, served through httpx.MockTransport.

The tool contracts copy the shape find-tools returned live on 2026-09-28 for bing-com, maps-google-com
and bbb-business-profiles-ratings-complaint (option names, required as the string 'True', page and
count limits, response key and about text). Their field lists are abbreviated. Apollo's people search
is terms-gated, as it is live.

Every paid call deducts from `balance`, so a test can reconcile the ledger against the provider the
way the live D1 check does.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from data_box.providers.firecrawl import Firecrawl

BASE = "https://api.firecrawl.test"


def _opt(name, type_="string", **extra):
    return {"name": name, "type": type_, "in": "body", "about": extra.pop("about", name), **extra}


TOOLS: list[dict[str, Any]] = [
    {"id": "t1", "provider": "bing-com", "capability": "businesses/search", "name": "Search businesses",
     "description": "Local businesses near a place", "creditsCost": 5, "perRecord": False, "similarity": 0.61,
     "options": [_opt("count", "number", about="Results per page.", default="18", min="1", max="30"),
                 _opt("location", about="Where to look: a street address, city/state or postal code"),
                 _opt("page", "number", about="Result page; page N skips (N-1)*count results.", default="1", min="1", max="5"),
                 _opt("query", about="What to find: a category such as restaurants", required="True")],
     "response": {"about": "One page of up to 30 results with name, street address, phone, website.",
                  "key": "results", "paginated": True,
                  "fields": [{"name": n} for n in ("ypid", "name", "address", "phone", "website", "category", "rating")]}},
    {"id": "t2", "provider": "maps-google-com", "capability": "businesses/search", "name": "Search places",
     "description": "Find businesses on Google Maps", "creditsCost": 5, "perRecord": False, "similarity": 0.58,
     "options": [_opt("latitude", "number", min="-90", max="90"), _opt("longitude", "number", min="-180", max="180"),
                 _opt("query", about="Business name and/or category with a location", required="True")],
     "response": {"about": "Find businesses on Google Maps by free-text query. Returns up to 20 places with "
                           "address, phone and website.", "key": "results", "paginated": True,
                  "fields": [{"name": n} for n in ("place_id", "name", "address", "address_lines", "phone", "website", "categories")]}},
    {"id": "t3", "provider": "bbb-business-profiles-ratings-complaint", "capability": "businesses/search",
     "name": "Search BBB", "description": "Find BBB business profiles", "creditsCost": 1, "perRecord": False, "similarity": 0.55,
     "options": [_opt("query", about="Business name or category", required="True"),
                 _opt("location", about="City and state/province or postal code"),
                 _opt("country", default="us", oneOf="['us', 'ca']"),
                 _opt("page", "number", about="Results page, 1 to 100 (15 results per page).", min="1", max="100", default="1"),
                 _opt("sort", default="Relevance")],
     "response": {"about": "Find BBB business profiles near a place. Returns one page of 15 results with each "
                           "business's grade, address, phones and profile URL.", "key": "results", "paginated": True,
                  "fields": [{"name": n} for n in ("id", "name", "address", "phones", "categories", "profile_url")]}},
    {"id": "t4", "provider": "apollo", "capability": "people/search", "name": "People search",
     "description": "People by title and location", "creditsCost": 0, "perRecord": False, "similarity": 0.4,
     "options": [_opt("query", required="True"), _opt("page", "number", max="100")],
     "response": {"about": "people", "key": "people", "paginated": True, "fields": [{"name": "name"}, {"name": "title"}]}},
    {"id": "t5", "provider": "fcia-org", "capability": "businesses/search_members", "name": "Firestop members",
     "description": "Firestop contractors", "creditsCost": 5, "perRecord": False, "similarity": 0.3,
     "options": [_opt("state", required="True")],
     "response": {"about": "members", "key": "members", "paginated": False, "fields": [{"name": "name"}]}},
]

# Tools only a category browse finds: a good lane the skill never verified, a lane whose contract
# promises businesses but returns bare ids, and tools from categories a business pull should skip.
TOOLS += [
    {"id": "t6", "provider": "yellowpages-com", "capability": "businesses/search", "name": "Yellow Pages",
     "description": "Local businesses by category and city", "creditsCost": 2, "perRecord": False,
     "options": [_opt("query", required="True"), _opt("location"), _opt("page", "number", max="10")],
     "response": {"about": "One page of up to 25 listings.", "key": "listings", "paginated": True,
                  "fields": [{"name": n} for n in ("name", "phone", "website", "street_address")]}},
    {"id": "t7", "provider": "junk-directory", "capability": "businesses/search", "name": "Junk",
     "description": "Claims businesses", "creditsCost": 1, "perRecord": False,
     "options": [_opt("query", required="True")],
     "response": {"about": "Returns up to 50 businesses.", "key": "rows", "paginated": False,
                  "fields": [{"name": n} for n in ("name", "phone")]}},
    {"id": "t8", "provider": "ziprecruiter-com", "capability": "jobs/search_jobs", "name": "Jobs",
     "description": "Job postings", "creditsCost": 5, "perRecord": False,
     "options": [_opt("query", required="True")],
     "response": {"about": "jobs", "key": "jobs", "paginated": True, "fields": [{"name": "title"}, {"name": "company"}]}},
    {"id": "t9", "provider": "realtor-com", "capability": "agents/search", "name": "Agents",
     "description": "Real estate agents by city", "creditsCost": 3, "perRecord": False,
     "options": [_opt("query", required="True"), _opt("location")],
     "response": {"about": "One page of up to 20 agents.", "key": "agents", "paginated": False,
                  "fields": [{"name": n} for n in ("name", "phone", "office_address")]}},
    # Traps seen live on 2026-09-28 in the "places" category: tools that return a name, address,
    # phone and website, rank high on records per credit, and have nothing to do with roofers.
    {"id": "t10", "provider": "golfnow-com", "capability": "tee-times/search_courses", "name": "Golf courses",
     "description": "Golf courses near a place", "creditsCost": 1, "perRecord": False,
     "options": [_opt("query", required="True"), _opt("location")],
     "response": {"about": "One page of up to 30 courses with name, address, phone, website.", "key": "courses",
                  "paginated": False, "fields": [{"name": n} for n in ("name", "address", "phone", "website")]}},
    {"id": "t11", "provider": "seatgeek-com", "capability": "events/search_venues", "name": "Venues",
     "description": "Find a venue id by name or list venues in a city", "creditsCost": 1, "perRecord": False,
     "options": [_opt("query", required="True")],
     "response": {"about": "Returns up to 60 venues.", "key": "venues", "paginated": False,
                  "fields": [{"name": n} for n in ("name", "address", "phone")]}},
]

CATEGORIES = {
    "local-businesses": {"about": "Local business directories, maps and reviews for contractors and services",
                         "tools": ["t1", "t2", "t3", "t6", "t7", "t10", "t11"]},
    "companies": {"about": "Company profiles and firmographics", "tools": ["t5"]},
    "people": {"about": "People and professional profiles", "tools": ["t4"]},
    "real-estate": {"about": "Property listings and real estate agents", "tools": ["t9"]},
    "jobs": {"about": "Job postings and hiring signals", "tools": ["t8"]},
}

TERMS_REQUIRED = {"apollo"}


def business(n: int) -> dict:
    return {"name": f"Roofer {n} LLC", "phone": f"(512) 555-{n:04d}", "website": f"https://roofer{n}.test",
            "address": f"{100 + n} Main St, Austin, TX"}


class FakeFirecrawl:
    """Universe: 60 businesses. Bing pages through all 60; BBB holds the first 40 (15 a page, phones as a
    list, no website); Maps returns 20 starting at 10. So lanes overlap and pages run short."""

    def __init__(self, balance: float = 5000, universe: int = 60):
        self.balance = balance
        self.universe = universe
        self.calls: list[dict] = []
        self.fail: dict[str, Any] = {}  # provider -> status code or exception to raise
        self.out_of_credits_after: int | None = None
        self.delay = 0.0  # seconds each paid call takes, to catch a job mid-flight
        self.catalog_page = 3  # tools per find-tools page when browsing a category, to exercise paging
        self.repeat_from_page: int | None = None  # Bing pages from here on repeat page 1 (the deep-page collapse)

    def client(self, key: str = "fc-test") -> Firecrawl:
        async def handle(request: httpx.Request) -> httpx.Response:
            if self.delay and "alexandria" in (request.content or b"").decode() and b"find-tools" not in request.content:
                await asyncio.sleep(self.delay)
            return self.handle(request)
        return Firecrawl(key=key, base=BASE, transport=httpx.MockTransport(handle), timeout=5)

    def paid_calls(self, provider: str | None = None) -> list[dict]:
        return [c for c in self.calls if c.get("paid") and (provider is None or c["provider"] == provider)]

    # --- routing -----------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content or b"{}")
        if path == "/exchange/discover":
            self.calls.append({"provider": "discover-categories"})
            return httpx.Response(200, json={"cohorts": [{"cohort": k, "about": v["about"], "providers": len(v["tools"])}
                                                         for k, v in CATEGORIES.items()]})
        if path == "/v2/team/credit-usage":
            return self.ok({"data": {"remainingCredits": self.balance, "planCredits": 5000, "billingPeriodEnd": "2026-10-23"}})
        if path == "/v2/search":
            if body.get("sources") == ["alexandria"]:
                return self.ok({"data": {"tools": [{"provider": t["provider"], "capability": t["capability"],
                                                    "description": t["description"]} for t in TOOLS[:3]]}})
            return self.paid("search", 2, {"data": {"web": [{"url": f"https://r{i}.test", "title": f"R{i}"}
                                                            for i in range(body.get("limit", 10))]}, "creditsUsed": 2})
        if path == "/v2/scrape" and "alexandria" in body:
            return self.alexandria(body["alexandria"])
        if path == "/v2/scrape":
            formats = body.get("formats") or []
            cost = 5 if any(isinstance(f, dict) and f.get("type") == "json" for f in formats) else 1
            doc = {"markdown": "# Real page\n\nthe content", "metadata": {"title": "Real", "statusCode": 200,
                                                                          "url": body["url"], "creditsUsed": cost}}
            if cost == 5:
                doc["json"] = {"title": "Real"}
            return self.paid("scrape", cost, {"data": doc})
        return httpx.Response(404, json={"success": False, "error": f"no route {path}"})

    def ok(self, data: dict) -> httpx.Response:
        return httpx.Response(200, json={"success": True, **data})

    def paid(self, provider: str, cost: float, data: dict) -> httpx.Response:
        self.calls.append({"provider": provider, "paid": True, "cost": cost})
        self.balance -= cost
        return self.ok(data)

    def alexandria(self, spec: dict) -> httpx.Response:
        provider, capability, options = spec["provider"], spec["capability"], spec.get("options") or {}
        if provider == "firecrawl" and capability == "find-tools":
            self.calls.append({"provider": "find-tools", "options": options})
            if options.get("categories"):
                ids = [i for c in options["categories"] for i in CATEGORIES.get(c, {}).get("tools", [])]
                every = [t for t in TOOLS if t["id"] in ids]
                offset = int(options.get("offset") or 0)
                size = min(int(options.get("limit") or 20), self.catalog_page)
                page = every[offset:offset + size]
                nxt = ({"provider": "firecrawl", "capability": "find-tools",
                        "options": {**options, "offset": offset + size}} if offset + size < len(every) else None)
                return self.ok({"data": {"alexandria": [{"data": {"level": "tools", "items": page, "total": len(every),
                                                                  "next": nxt}, "creditsCost": 0}]}})
            items = TOOLS
            if options.get("providers"):
                items = [t for t in items if t["provider"] in options["providers"]]
            if options.get("capabilities"):
                items = [t for t in items if t["capability"] in options["capabilities"]]
            return self.ok({"data": {"alexandria": [{"data": {"items": items[: options.get("limit", 10)]}, "creditsCost": 0}]}})
        if provider == "firecrawl" and capability == "terms/show":
            required = options.get("provider") in TERMS_REQUIRED
            return self.ok({"data": {"alexandria": [{"data": {
                "required": required, "terms": {"document": "version: 2026-09\n..."},
                "status": {"accepted": not required, "version": "2026-09" if required else None}}}]}})
        failure = self.fail.get(provider)
        if failure == 402 or (self.out_of_credits_after is not None and len(self.paid_calls()) >= self.out_of_credits_after):
            return httpx.Response(402, json={"success": False, "error": "Insufficient credits"})
        if isinstance(failure, int):
            return httpx.Response(failure, json={"success": False, "error": f"{provider} failed"})
        if isinstance(failure, BaseException):
            raise failure
        tool = next(t for t in TOOLS if t["provider"] == provider and t["capability"] == capability)
        records = self.records(provider, options)
        self.calls.append({"provider": provider, "paid": True, "cost": tool["creditsCost"], "options": options})
        self.balance -= tool["creditsCost"]
        return self.ok({"data": {"alexandria": [{"data": {tool["response"]["key"]: records, "total_results": len(records)},
                                                "creditsCost": tool["creditsCost"]}]}})

    def records(self, provider: str, options: dict) -> list[dict]:
        page = int(options.get("page") or 1)
        if provider == "bing-com":
            size = int(options.get("count") or 18)
            if self.repeat_from_page and page >= self.repeat_from_page:
                page = 1
            ids = range((page - 1) * size, min(page * size, self.universe))
            return [business(n) for n in ids]
        if provider == "yellowpages-com":
            ids = range(40 + (page - 1) * 25, min(40 + page * 25, self.universe + 20))
            return [{"name": f"Roofer {n} Inc", "phone": f"512.555.{n:04d}", "street_address": f"{100 + n} Main St"} for n in ids]
        if provider in ("golfnow-com", "seatgeek-com"):
            return [{"name": f"Course {n}", "address": f"{n} Fairway Dr", "phone": f"512-555-7{n:03d}"} for n in range(30)]
        if provider == "junk-directory":
            return [{"id": str(n)} for n in range(50)]
        if provider == "realtor-com":
            return [{"name": f"Agent {n}", "phone": f"512-555-9{n:03d}", "office_address": "1 Congress Ave"} for n in range(20)]
        if provider == "bbb-business-profiles-ratings-complaint":
            ids = range((page - 1) * 15, min(page * 15, min(40, self.universe)))
            return [{"id": str(n), "name": f"Roofer {n}, LLC", "phones": [f"512-555-{n:04d}"],
                     "address": f"{100 + n} Main Street", "profile_url": f"https://bbb.test/{n}"} for n in ids]
        if provider == "maps-google-com":
            return [{**business(n), "name": f"roofer {n}"} for n in range(10, min(30, self.universe))]
        return []
