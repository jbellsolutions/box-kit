"""Firecrawl: tier 1, and the default for anything web-shaped.

Everything here is one HTTP call to https://api.firecrawl.dev and returns what it cost in credits:

- `tools(...)` / `inspect(...)`: Alexandria discovery through the free find-tools capability. Each
  tool comes back as a Contract: price, whether it bills per record, its inputs (required, default,
  min, max), where its records live in the response, whether it paginates, and its fields.
- `run_tool(...)`: execute one Alexandria provider tool; records come out of the contract's key.
- `search`, `scrape`, `map`, `crawl`: the plain Firecrawl endpoints.
- `credits()`: the live balance, checked before a plan and during execution.

Nothing here decides whether to spend: planning.py builds the plan and execution.py reserves each
call's worst case in the ledger before calling in here. This is the port of Justin's
firecrawl-alexandria skill (scripts/alexandria.py) minus its four defects: it never swaps in a tool
other than the one asked for, it reports every required input, it never pays on its own, and an
empty or error result is a failure, not a success.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .. import config

SEARCH_CREDITS_PER_10 = 2   # /v2/search: 2 credits per 10 results (docs.firecrawl.dev/billing)
SCRAPE_CREDITS = 1          # /v2/scrape: 1 credit a page
JSON_FORMAT_CREDITS = 4     # + 4 when a json/schema format is asked for
MAP_CREDITS = 1             # /v2/map: 1 credit a call
CRAWL_CREDITS_PER_PAGE = 1  # /v2/crawl: 1 credit a page

# "up to 30 <unit>" in a contract's text is a page size unless the unit is not a record.
NOT_RECORDS = {"seconds", "second", "minutes", "minute", "hours", "hour", "days", "day", "weeks", "months", "years",
               "credits", "credit", "pages", "page", "characters", "chars", "words", "mb", "kb", "times", "calls"}


class FirecrawlError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


class TermsRequired(FirecrawlError):
    """The provider's data terms must be accepted by a person before its tools run."""


class OutOfCredits(FirecrawlError):
    """Firecrawl refused for lack of credits (402)."""


@dataclass
class Contract:
    provider: str
    capability: str
    description: str = ""
    credits: float = 0            # per call, or per record when per_record
    per_record: bool = False
    options: list[dict] = field(default_factory=list)
    response_key: str = ""
    paginated: bool = False
    fields: list[str] = field(default_factory=list)
    about: str = ""
    similarity: float = 0.0
    category: str = ""

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.capability}"

    def option(self, name: str) -> dict | None:
        return next((o for o in self.options if o.get("name") == name), None)

    @property
    def required(self) -> list[str]:
        return [o["name"] for o in self.options if str(o.get("required", "")).lower() == "true"]

    @property
    def page_option(self) -> str | None:
        return "page" if self.option("page") else None

    @property
    def max_page(self) -> int | None:
        page = self.option("page")
        return _int(page.get("max")) if page else None

    @property
    def size_option(self) -> str | None:
        for name in ("count", "limit", "page_size", "per_page"):
            if self.option(name):
                return name
        return None

    @property
    def page_size(self) -> int | None:
        """Records per call: the size option's max (data-box asks for full pages), else what the
        contract's text says ("15 results per page", "up to 20"), else unknown."""
        size = self.size_option
        if size:
            spec = self.option(size) or {}
            return _int(spec.get("max")) or _int(spec.get("default"))
        text = f"{self.about} {self.description}"
        for pattern in (r"(\d+)\s+(?:\w+\s+)?per\s+page", r"one page of\s+(?:up to\s+)?(\d+)",
                        r"up to\s+(\d+)\s+([a-z]+)", r"returns?\s+(\d+)\s+([a-z]+)"):
            for match in re.finditer(pattern, text, re.I):
                unit = match.group(2).lower() if match.lastindex and match.lastindex > 1 else ""
                if unit not in NOT_RECORDS:
                    return int(match.group(1))
        return None

    @property
    def location_option(self) -> str | None:
        for name in ("location", "near", "city", "address", "where"):
            if self.option(name):
                return name
        return None

    @property
    def query_option(self) -> str | None:
        for name in ("query", "q", "search", "keyword", "keywords", "term"):
            if self.option(name):
                return name
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "source": "firecrawl", "provider": self.provider, "capability": self.capability,
            "credits_per_call" if not self.per_record else "credits_per_record": self.credits,
            "page_size": self.page_size, "paginates": bool(self.page_option) and self.paginated,
            "max_page": self.max_page, "required_inputs": self.required,
            "inputs": [o.get("name") for o in self.options], "fields": self.fields,
            "about": (self.about or self.description)[:300],
        }


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def contract_from_item(item: dict, category: str = "") -> Contract:
    response = item.get("response") or {}
    return Contract(
        provider=item.get("provider", ""), capability=item.get("capability", ""),
        description=item.get("description") or item.get("name") or "",
        credits=float(item.get("creditsCost") or 0), per_record=bool(item.get("perRecord")),
        options=[o for o in item.get("options") or [] if isinstance(o, dict)],
        response_key=response.get("key") or "", paginated=bool(response.get("paginated")),
        fields=[f.get("name") for f in response.get("fields") or [] if isinstance(f, dict) and f.get("name")],
        about=response.get("about") or "", similarity=float(item.get("similarity") or 0),
        category=category or str(item.get("category") or ""),
    )


def records_from(payload: Any, key: str = "") -> list[dict]:
    """The list of records in a tool's data: at the contract's key when it names one, else the
    first list of objects found a few levels down."""
    data = payload
    if key and isinstance(data, dict) and isinstance(data.get(key), list):
        return [r for r in data[key] if isinstance(r, dict)]
    for _ in range(4):
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if not isinstance(data, dict):
            return []
        for name in ("results", "items", "records", "rows", "data", "businesses", "people", "companies"):
            if isinstance(data.get(name), list):
                return [r for r in data[name] if isinstance(r, dict)]
        data = next((data[k] for k in ("data", "result", "payload") if isinstance(data.get(k), (dict, list))), None)
    return []


class Firecrawl:
    def __init__(self, key: str | None = None, base: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, timeout: float = 90):
        self.key = key if key is not None else config.firecrawl_key()
        self.base = (base or config.firecrawl_base()).rstrip("/")
        self.transport = transport
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base, transport=self.transport, timeout=self.timeout,
                                 headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})

    async def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        if not self.key:
            raise FirecrawlError("FIRECRAWL_API_KEY is not set on this box")
        async with self._client() as client:
            for attempt in (1, 2):
                try:
                    response = await client.request(method, path, json=body)
                except httpx.HTTPError as exc:
                    # status 0: the request may or may not have run, so a paid call is charged in full.
                    raise FirecrawlError(f"Firecrawl {path}: {type(exc).__name__}: {exc}"[:300], 0, "transport") from None
                if response.status_code != 429 or attempt == 2:
                    break
                # Hobby runs 5 jobs at once; a 429 was not run, so one polite retry is free.
                await asyncio.sleep(min(float(response.headers.get("retry-after") or 2), 10))
        try:
            data = response.json()
        except ValueError:
            data = {"error": response.text[:300]}
        if response.status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
            message = data.get("error") if isinstance(data, dict) else None
            code = data.get("code", "") if isinstance(data, dict) else ""
            if isinstance(message, dict):
                code = message.get("code", code)
                message = message.get("message")
            message = str(message or f"HTTP {response.status_code}")[:300]
            if response.status_code == 402:
                raise OutOfCredits(f"Firecrawl is out of credits: {message}", 402, code)
            if "TERMS" in str(code).upper() or "terms" in message.lower():
                raise TermsRequired(f"Firecrawl: {message}", response.status_code, code)
            raise FirecrawlError(f"Firecrawl {path} failed ({response.status_code}): {message}", response.status_code, code)
        return data

    # --- money -------------------------------------------------------------------------------

    async def credits(self) -> dict[str, Any]:
        data = (await self._call("GET", "/v2/team/credit-usage")).get("data") or {}
        return {"remaining": data.get("remainingCredits"), "plan": data.get("planCredits"),
                "period_end": data.get("billingPeriodEnd")}

    # --- Alexandria --------------------------------------------------------------------------

    async def _alexandria(self, provider: str, capability: str, options: dict) -> dict:
        data = await self._call("POST", "/v2/scrape", {"alexandria": {"provider": provider, "capability": capability,
                                                                      "options": options}})
        results = (data.get("data") or {}).get("alexandria") or data.get("alexandria") or []
        if not results or not isinstance(results[0], dict):
            raise FirecrawlError(f"Firecrawl returned no result for {provider}/{capability}")
        result = results[0]
        if result.get("error"):
            error = result["error"]
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            code = error.get("code", "") if isinstance(error, dict) else ""
            if "TERMS" in str(code).upper():
                raise TermsRequired(f"{provider}: {message}", 403, code)
            raise FirecrawlError(f"{provider}/{capability}: {message}", 0, code)
        return result

    async def tools(self, query: str, *, providers: list[str] | None = None, capabilities: list[str] | None = None,
                    limit: int = 10) -> list[Contract]:
        """find-tools: Alexandria's catalog, semantically searched, with each tool's full contract. Free."""
        options: dict[str, Any] = {"level": "tools", "expand": ["options", "response"], "limit": limit}
        if query:
            options["query"] = query
        if providers:
            options["providers"] = providers
        if capabilities:
            options["capabilities"] = capabilities
        result = await self._alexandria("firecrawl", "find-tools", options)
        items = (result.get("data") or {}).get("items") or []
        return [contract_from_item(item) for item in items if isinstance(item, dict)]

    async def categories(self) -> list[dict[str, Any]]:
        """Alexandria's category index (GET /exchange/discover): every category with what it covers
        and how many providers it holds. Free."""
        data = await self._call("GET", "/exchange/discover")
        rows = data.get("cohorts") or []
        return [{"id": r["cohort"], "about": r.get("about") or "", "providers": int(r.get("providers") or 0)}
                for r in rows if isinstance(r, dict) and isinstance(r.get("cohort"), str) and r["cohort"].strip()]

    async def catalog(self, category: str, *, max_tools: int = 300) -> list[Contract]:
        """Every tool in one category, with its full contract, following find-tools' pagination. Free."""
        options: dict[str, Any] = {"categories": [category], "level": "tools", "expand": ["options", "response"],
                                   "limit": 100}
        found: list[Contract] = []
        for _ in range(max(1, -(-max_tools // 100))):
            result = await self._alexandria("firecrawl", "find-tools", options)
            page = result.get("data") or {}
            found += [contract_from_item(item, category) for item in page.get("items") or [] if isinstance(item, dict)]
            nxt = page.get("next")
            if not isinstance(nxt, dict) or not isinstance(nxt.get("options"), dict) or len(found) >= max_tools:
                break
            options = nxt["options"]
        return found[:max_tools]

    async def inspect(self, provider: str, capability: str) -> Contract | None:
        """The one contract for provider/capability, or None. Never a different tool."""
        found = await self.tools("", providers=[provider], capabilities=[capability], limit=5)
        return next((c for c in found if c.provider == provider and c.capability == capability), None)

    async def discover(self, query: str, limit: int = 10) -> list[dict]:
        """/v2/search over the alexandria source: tools ranked for a plain-language need. Free."""
        data = await self._call("POST", "/v2/search", {"query": query, "sources": ["alexandria"], "limit": limit})
        tools = (data.get("data") or {}).get("tools") or []
        return [{"provider": t.get("provider"), "capability": t.get("capability"), "description": t.get("description", "")}
                for t in tools if isinstance(t, dict) and t.get("provider") and t.get("capability")]

    async def terms(self, provider: str) -> dict[str, Any]:
        """Whether a provider's data terms need accepting. Free; data-box never accepts terms itself."""
        try:
            result = await self._alexandria("firecrawl", "terms/show", {"provider": provider})
        except TermsRequired as exc:
            return {"required": True, "accepted": False, "detail": str(exc)}
        data = result.get("data") or {}
        required = bool(data.get("required"))
        status = data.get("status") or {}
        accepted = bool(status.get("accepted")) or not required
        version = status.get("version")
        if not version and isinstance(data.get("terms"), dict):
            match = re.search(r"^version:\s*(\S+)", data["terms"].get("document") or "", re.M)
            version = match.group(1) if match else None
        detail = ("no terms to accept" if not required else
                  "accepted" if accepted else
                  f"terms {version or ''} must be accepted by a person in Firecrawl before this provider runs".replace("  ", " "))
        return {"required": required, "accepted": accepted, "version": version, "detail": detail}

    async def run_tool(self, contract: Contract, options: dict) -> dict[str, Any]:
        """Execute one provider tool. Returns records and the credits it cost."""
        missing = [name for name in contract.required if options.get(name) in (None, "")]
        if missing:
            raise ValueError(f"{contract.id} needs {', '.join(missing)}")
        result = await self._alexandria(contract.provider, contract.capability, options)
        payload = result.get("data")
        records = records_from(payload, contract.response_key)
        charged = result.get("creditsCost")
        credits = float(charged) if isinstance(charged, (int, float)) else (
            contract.credits * max(1, len(records)) if contract.per_record else contract.credits)
        meta = {k: payload.get(k) for k in ("total", "total_results", "next_page", "page", "has_more", "pages")
                if isinstance(payload, dict) and k in payload}
        return {"records": records, "credits": credits, "meta": meta}

    # --- plain Firecrawl ---------------------------------------------------------------------

    async def search(self, query: str, *, sources: list[str] | None = None, limit: int = 10,
                     location: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "sources": sources or ["web"], "limit": limit}
        if location:
            body["location"] = location
        data = await self._call("POST", "/v2/search", body)
        payload = data.get("data") or {}
        results = []
        for source in body["sources"]:
            for item in payload.get(source) or []:
                if isinstance(item, dict):
                    results.append({"source": source, **item})
        credits = data.get("creditsUsed")
        if not isinstance(credits, (int, float)):
            credits = search_credits(limit, len(body["sources"]))
        return {"records": results, "credits": float(credits)}

    async def scrape(self, url: str, *, formats: list | None = None, proxy: str = "auto",
                     only_main_content: bool = True, timeout_ms: int = 60000) -> dict[str, Any]:
        body = {"url": url, "formats": formats or ["markdown"], "proxy": proxy,
                "onlyMainContent": only_main_content, "timeout": timeout_ms}
        data = await self._call("POST", "/v2/scrape", body)
        doc = data.get("data") or {}
        metadata = doc.get("metadata") or {}
        credits = metadata.get("creditsUsed")
        if not isinstance(credits, (int, float)):
            credits = scrape_credits(body["formats"])
        return {"document": doc, "credits": float(credits)}

    async def map(self, url: str, *, limit: int = 5000, search: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "limit": limit}
        if search:
            body["search"] = search
        data = await self._call("POST", "/v2/map", body)
        links = data.get("links") or (data.get("data") or {}).get("links") or []
        links = [link if isinstance(link, dict) else {"url": link} for link in links]
        return {"records": links, "credits": float(data.get("creditsUsed") or MAP_CREDITS)}

    async def crawl(self, url: str, *, limit: int, include_paths: list[str] | None = None,
                    exclude_paths: list[str] | None = None, formats: list | None = None,
                    poll_seconds: float = 3, max_wait_seconds: float = 1800) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "limit": limit, "scrapeOptions": {"formats": formats or ["markdown"]}}
        if include_paths:
            body["includePaths"] = include_paths
        if exclude_paths:
            body["excludePaths"] = exclude_paths
        started = await self._call("POST", "/v2/crawl", body)
        crawl_id = started.get("id")
        if not crawl_id:
            raise FirecrawlError("Firecrawl did not return a crawl id")
        waited = 0.0
        documents: list[dict] = []
        while True:
            status = await self._call("GET", f"/v2/crawl/{crawl_id}")
            if status.get("status") in ("completed", "failed", "cancelled"):
                documents = [d for d in status.get("data") or [] if isinstance(d, dict)]
                credits = status.get("creditsUsed")
                if status.get("status") != "completed" and not documents:
                    raise FirecrawlError(f"crawl {crawl_id} {status.get('status')}")
                return {"records": documents, "credits": float(credits if isinstance(credits, (int, float))
                                                                 else len(documents) * CRAWL_CREDITS_PER_PAGE * scrape_credits(body["scrapeOptions"]["formats"])),
                        "crawl_id": crawl_id, "status": status.get("status")}
            if waited >= max_wait_seconds:
                raise FirecrawlError(f"crawl {crawl_id} still running after {int(waited)} s")
            await asyncio.sleep(poll_seconds)
            waited += poll_seconds


def search_credits(limit: int, sources: int = 1) -> float:
    return float(SEARCH_CREDITS_PER_10 * max(1, -(-limit // 10)) * max(1, sources))


def scrape_credits(formats: list | None) -> float:
    json_format = any(isinstance(f, dict) and f.get("type") == "json" or f == "json" for f in formats or [])
    return float(SCRAPE_CREDITS + (JSON_FORMAT_CREDITS if json_format else 0))
