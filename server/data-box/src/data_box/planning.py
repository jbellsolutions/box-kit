"""Steps 1-3 of every paid request: take it in, scope every source, narrow it to a game plan.

Justin's rule (2026-09-28), from his firecrawl-alexandria skill: no pull locks onto one familiar
source and silently misses most of the market, and nothing paid runs until the user approves a plan.

1. INTAKE   what is wanted: kind, entity, how many, which fields, where, named sources, budget.
2. SURVEY   every source that could serve, across the tiers, each with price, page size,
            pagination, inputs, field fit and terms status, and why it can or cannot run here.
            Tier 1 is Firecrawl (Alexandria's providers, read live through find-tools), MoltSets and
            DiscoLike; tier 2 Decodo and Bright Data; tier 3 Apify, the backup's backup.
3. PLAN     the chosen lanes, ranked by records per credit x coverage x field fit, split into
            cells (query x place) and pages, priced against the live balance, and a preflight of one
            real call per lane so the plan does not rest on catalog text alone.
4. EXECUTE  is execution.py, and only after approval.

A named source is honoured; the survey still lists everything so the user sees what was passed over.
Preflight is the only spend before approval: capped (25 credits by default, and never more than the
request's max_cost_usd), metered through the plan's own job, and its records are kept so execution
does not pay for those pages twice.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import config, recipes
from .ledger import Conflict, Ledger
from .providers import firecrawl as fc_mod
from .providers.firecrawl import Contract, Firecrawl, FirecrawlError, OutOfCredits

KINDS = ("pull", "search", "scrape", "crawl", "extract")
ENTITIES = ("business", "person", "property", "any")
SURVEY_CONCURRENCY = 3  # Firecrawl Hobby runs 5 jobs at once; the survey leaves room for Hermes

# Field names differ by provider; these are the ones a request asks for and what providers call them.
FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "name": ("name", "business_name", "title", "bbb_name", "company_name", "full_name", "display_name"),
    "phone": ("phone", "phones", "phone_number", "display_phone", "telephone", "e164_phone", "phone_e164",
              "phone_numbers", "formatted_phone_number", "international_phone_number"),
    "email": ("email", "emails", "email_address", "work_email", "business_email"),
    "website": ("website", "url", "site", "website_url", "domain", "web", "homepage"),
    "address": ("address", "address_lines", "street", "full_address", "street_address", "formatted_address"),
    "city": ("city", "locality"),
    "state": ("state", "region", "state_code", "province"),
    "rating": ("rating", "rating_score", "stars", "aggregate_rating", "bbb_rating"),
    "category": ("category", "categories", "primary_category", "type"),
    "linkedin": ("linkedin", "linkedin_url"),
}

# Providers data-box knows beyond Firecrawl. Every survey lists them in tier order, with whether they
# can run on this box yet; the milestone that wires each is named, never hidden.
OTHER_SOURCES: list[dict[str, Any]] = [
    {"source": "moltsets", "tier": 1, "entities": ("person", "business"), "role": "enrichment",
     "about": "people and company contact data: search_people, search_companies, linkedin_to_* email and phone, "
              "reverse lookups; contact reveal runs on the deduped shortlist only", "wired": "D2"},
    {"source": "discolike", "tier": 1, "entities": ("business",), "role": "discovery",
     "about": "company discovery by similarity and firmographics, bizdata, contacts", "wired": "D2"},
    {"source": "decodo", "tier": 2, "entities": ("any",), "role": "scrape",
     "about": "residential proxy re-fetch and the Web Scraping API (JS rendering, platform templates)", "wired": "D3"},
    {"source": "brightdata", "tier": 2, "entities": ("business", "person", "property", "any"), "role": "discovery",
     "about": "Web Unlocker, SERP, 1,762 marketplace datasets (measured 2026-09-23) and scrapers", "wired": "D3-D4"},
    {"source": "apify", "tier": 3, "entities": ("business", "person", "property", "any"), "role": "discovery",
     "about": "65,004 Store actors (measured 2026-09-23); the backup's backup: expensive, used only when no "
              "tier 1-2 lane fits, and only inside an approved plan", "wired": "D5"},
]

SCRAPE_LADDER = [
    {"rung": 0, "source": "fetch", "what": "free pinned HTTP fetch (runs without a plan)", "wired": True},
    {"rung": 1, "source": "firecrawl", "what": "Firecrawl /v2/scrape: JS rendering, proxy auto", "wired": True},
    {"rung": 2, "source": "decodo", "what": "Decodo: residential re-fetch, then the Web Scraping API", "wired": "D3"},
    {"rung": 3, "source": "brightdata", "what": "Bright Data Web Unlocker", "wired": "D3"},
    {"rung": 4, "source": "firecrawl-browser", "what": "Firecrawl Browser Sandbox: clicks and logins, no proxy", "wired": "D3"},
    {"rung": 5, "source": "hyperbrowser", "what": "Hyperbrowser: stealth browser with proxies and CAPTCHA solving", "wired": "D3"},
    {"rung": 6, "source": "browser-box", "what": "browser-box read: the Steel browser, last resort", "wired": "D3"},
]


# --- step 1: intake -------------------------------------------------------------------------

def intake(args: dict) -> dict[str, Any]:
    from .security import require_public_web

    request = (args.get("request") or "").strip()
    urls = [u for u in ([args["url"]] if args.get("url") else []) + list(args.get("urls") or []) if u]
    kind = args.get("kind") or _infer_kind(request, urls, args)
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    for url in urls:
        require_public_web(url)
    queries = [q.strip() for q in args.get("queries") or [] if q and q.strip()]
    geo = [g.strip() for g in args.get("geo") or [] if g and g.strip()]
    if not queries and kind == "pull" and request and not geo:
        # "roofing contractors in Austin TX": the place goes to each lane's location input, never
        # into the query, where a directory would search every city for the whole sentence.
        match = re.match(r"^(.+?)\s+(?:in|near|around)\s+(.+)$", request, re.I)
        if match:
            queries, geo = [match.group(1).strip()], [match.group(2).strip()]
    if not queries and kind in ("pull", "search") and request:
        queries = [request]
    if kind in ("pull", "search") and not queries:
        raise ValueError(f"a {kind} plan needs a request or queries saying what to look for")
    if kind in ("scrape", "crawl") and len(urls) != 1:
        raise ValueError(f"a {kind} plan needs exactly one url")
    if kind == "extract" and not urls:
        raise ValueError("an extract plan needs urls")
    if kind == "extract" and not (args.get("schema") or args.get("prompt")):
        raise ValueError("an extract plan needs a schema or a prompt saying what to pull out")
    entity = args.get("entity") or ("business" if kind == "pull" else "any")
    if entity not in ENTITIES:
        raise ValueError(f"entity must be one of {', '.join(ENTITIES)}")
    max_cost = args.get("max_cost_usd")
    return {
        "kind": kind, "request": request or "; ".join(queries) or (urls[0] if urls else ""),
        "entity": entity, "count": int(args.get("count") or (100 if kind == "pull" else 10)),
        "fields": [f.lower().strip() for f in args.get("fields") or [] if f and f.strip()],
        "queries": queries, "geo": geo,
        "sources": [s.strip() for s in args.get("sources") or [] if s and s.strip()],
        "urls": urls, "schema": args.get("schema"), "prompt": args.get("prompt"),
        "format": args.get("format", "markdown"), "search_sources": args.get("search_sources") or ["web"],
        "limit": int(args.get("limit") or 0) or None,
        "max_cost_usd": None if max_cost is None else float(max_cost),
        "oversample": float(args.get("oversample") or 1.5), "max_lanes": int(args.get("max_lanes") or 3),
        "preflight": args.get("preflight", True) is not False,
    }


def _infer_kind(request: str, urls: list[str], args: dict) -> str:
    text = request.lower()
    if urls and (args.get("schema") or args.get("prompt")):
        return "extract"
    if urls and re.search(r"\b(crawl|every page|whole site|all pages)\b", text):
        return "crawl"
    if urls:
        return "scrape"
    if args.get("entity") or args.get("count") or args.get("geo") or re.search(r"\b(list|leads?|contacts?|every|all)\b", text):
        return "pull"
    return "search"


# --- step 2: survey -------------------------------------------------------------------------

def field_key(name: str) -> str:
    """Field names compared without case or punctuation: displayPhone, display_phone and
    Display-Phone are one field."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def synonyms(field: str) -> set[str]:
    return {field_key(n) for n in FIELD_SYNONYMS.get(field, (field,))}


def field_fit(wanted: list[str], fields: list[str]) -> tuple[float, list[str]]:
    """How many of the wanted fields a source returns, and which."""
    if not wanted:
        return 1.0, []
    have = {field_key(f) for f in fields}
    covered = [w for w in wanted if have & synonyms(w)]
    return len(covered) / len(wanted), covered


def matches_named(wanted: list[str], *names: str | None) -> bool:
    """Whether a source is one the request named: exact, alias ("google maps"), or a prefix of an id
    ("disco" -> discolike, "bbb" -> the BBB provider)."""
    ids = [n.lower() for n in names if n]
    for raw in wanted:
        w = raw.lower().strip()
        w = recipes.ALIASES.get(w, w)
        for name in ids:
            if w == name or (len(w) >= 3 and name.startswith(w)):
                return True
    return False


def _role(contract: Contract) -> str:
    known = recipes.recipe(contract.provider, contract.capability)
    if known:
        return known["role"]
    cap = contract.capability.lower()
    if contract.per_record or any(w in cap for w in ("match", "enrich", "email", "profile", "reveal", "phone")):
        return "enrichment"
    if any(w in cap for w in ("search", "list", "find", "members", "directory")):
        return "discovery"
    return "lookup"


def _fill(contract: Contract) -> dict[str, str | None]:
    """The inputs data-box knows how to fill for a lane: what to look for, where, how many, which page."""
    return {"query": contract.query_option, "location": contract.location_option,
            "size": contract.size_option, "page": contract.page_option}


def _returns_entity(contract: Contract, entity: str) -> bool | None:
    """Whether a tool's declared response carries the entity (a name plus, for a business, a phone,
    address or website). None when the contract declares no fields: preflight decides then."""
    if not contract.fields:
        return None
    return looks_like(entity, {f: 1 for f in contract.fields})


def _stem(word: str) -> str:
    for suffix in ("ings", "ing", "ers", "er", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def topic(it: dict) -> list[str]:
    """What a pull is about, as word stems: "roofing contractors in Austin TX" -> ["roof"]. Places,
    stopwords and words that fit any trade are left out."""
    places = {w for g in it["geo"] for w in re.findall(r"[a-z]+", g.lower())}
    what = [re.split(r"\s(?:in|near|around)\s", q.lower())[0] for q in it["queries"] or [it["request"]]]
    words = re.findall(r"[a-z]{4,}", " ".join(what))
    stems = [_stem(w) for w in words if w not in STOPWORDS and w not in recipes.GENERIC_WORDS and w not in places]
    return list(dict.fromkeys(stems))


def about_request(contract: Contract, it: dict) -> str | None:
    """None when a tool is a general directory for the entity or its own words mention what the
    request is about; otherwise why it is not."""
    if contract.capability in recipes.DIRECTORY_CAPABILITIES.get(it["entity"], ()):
        return None
    stems = topic(it)
    text = " ".join([contract.provider.replace("-", " "), contract.capability.replace("/", " ").replace("_", " "),
                     contract.description or "", contract.about or ""]).lower()
    if stems and any(re.search(rf"\b{re.escape(s)}", text) for s in stems):
        return None
    if stems:
        return f"not about this request: nothing in it mentions {', '.join(stems[:3])}, and it is not a general {it['entity']} directory"
    return f"not a general {it['entity']} directory, and the request names no trade or topic to match it on"


def _candidate(contract: Contract, it: dict, terms: dict | None) -> dict[str, Any]:
    fit, covered = field_fit(it["fields"], contract.fields)
    role = _role(contract)
    known = recipes.recipe(contract.provider, contract.capability)
    fill = _fill(contract)
    unfillable = [r for r in contract.required if r not in {v for v in fill.values() if v}]
    why_not = None
    if terms and not terms.get("accepted", True):
        why_not = terms.get("detail") or "its data terms must be accepted by a person in Firecrawl first"
    elif unfillable:
        why_not = f"needs inputs a plan cannot fill yet: {', '.join(unfillable)}"
    elif role != "discovery":
        why_not = f"{role} lane: runs on a deduped shortlist, not at discovery scale"
    elif not fill["query"]:
        why_not = "takes no search query"
    elif _returns_entity(contract, it["entity"]) is False:
        why_not = f"its response has no {it['entity']} fields (a name plus phone, address or website)"
    elif known and it["entity"] != "any" and known["entity"] != it["entity"]:
        why_not = f"a {known['entity']} lane; this pull wants {it['entity']} records"
    elif not known and it["kind"] == "pull" and not matches_named(it["sources"], contract.provider):
        why_not = about_request(contract, it)  # a source the user named is theirs to judge
    size = contract.page_size
    per_call = contract.credits * (size or 1) if contract.per_record else contract.credits
    summary = contract.summary()
    summary.pop("credits_per_record", None)
    candidate = {
        **summary, "category": contract.category or None, "tier": 1, "role": role, "credits_per_call": per_call,
        "field_fit": round(fit, 2), "fields_covered": covered,
        "terms": (terms or {}).get("detail", "not checked"), "can_run": why_not is None, "why_not": why_not,
        "records_per_credit": round((size or 0) / per_call, 2) if per_call else None,
        "verified": bool(known), "why": known["why"] if known else None,
        "max_pages": (known or {}).get("max_pages"), "similarity": round(contract.similarity, 3), "fill": fill,
    }
    if contract.per_record:
        candidate["credits_per_record"] = contract.credits
    return candidate


def _brief(candidate: dict) -> dict[str, Any]:
    """How a source that cannot serve this request is listed: enough to see it was considered and why not."""
    keys = ("source", "provider", "capability", "category", "tier", "role", "credits_per_call", "can_run", "why_not")
    return {k: candidate.get(k) for k in keys if k in candidate}


# --- Alexandria's categories: the whole catalog, browsed by what the request is about -------------

STOPWORDS = {"with", "and", "the", "for", "near", "from", "that", "list", "lists", "lead", "leads", "find", "phone",
             "phones", "website", "websites", "email", "emails", "address", "contact", "contacts", "records", "record",
             "data", "want", "need", "every", "each", "some", "their", "them", "this", "these", "into", "only"}


def pick_categories(it: dict, cohorts: list[dict], limit: int) -> list[dict]:
    """The Alexandria categories worth browsing in full for this request: those whose id or description
    shares its words (the vertical: "real estate", "restaurants", "roofing"), then those that hold the
    entity (companies, places, local businesses for a business pull; people for a person pull)."""
    words = set(topic(it))
    hints = recipes.ENTITY_CATEGORY_HINTS.get(it["entity"], recipes.ENTITY_CATEGORY_HINTS["any"])
    scored = []
    for cohort in cohorts:
        cid = cohort["id"].lower()
        name = cid.replace("-", " ")
        about = (cohort.get("about") or "").lower()
        why, score = [], 0.0
        in_name = sorted(w for w in words if w in name)
        if in_name:
            score += 3
            why.append("the request's words: " + ", ".join(in_name[:3]))
        in_about = sorted(w for w in words if re.search(rf"\b{re.escape(w)}", about) and w not in in_name)
        if in_about:
            score += min(2, len(in_about))
            why.append("its description mentions " + ", ".join(in_about[:3]))
        if any(h in cid for h in hints["ids"]) or any(h in about for h in hints["phrases"]):
            score += 1.5
            why.append(f"holds {it['entity']} records")
        if score and cohort.get("providers", 1):
            scored.append({**cohort, "score": score, "why": "; ".join(why)})
    scored.sort(key=lambda c: (-c["score"], -c.get("providers", 0), c["id"]))
    return scored[:limit]


def _cache_path(name: str) -> Path:
    folder = config.state_dir() / "cache"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder / ("alexandria-" + re.sub(r"[^a-z0-9_-]+", "_", name.lower()) + ".json")


def _cache_get(name: str) -> Any:
    path = _cache_path(name)
    try:
        if time.time() - path.stat().st_mtime < config.catalog_ttl_hours() * 3600:
            return json.loads(path.read_text())
    except (OSError, ValueError):
        pass
    return None


def _cache_put(name: str, value: Any) -> None:
    try:
        _cache_path(name).write_text(json.dumps(value, default=str))
    except OSError:
        pass  # a cache that cannot be written only costs a slower survey next time


async def _alexandria_contracts(fc: Firecrawl, it: dict) -> tuple[dict[str, Contract], list[dict], list[str], dict]:
    """Every Alexandria tool that could carry the entity, found four ways, all free:
    1. the skill's verified lanes, each inspected exactly (never swapped for another tool);
    2. every tool in the Alexandria categories the request is about, read in full with contracts;
    3. a semantic find-tools search over the need;
    4. /v2/search's alexandria ranking of the raw request.
    Returns contracts, verified lanes that could not be read, notes, and what was browsed."""
    gate = asyncio.Semaphore(SURVEY_CONCURRENCY)
    notes: list[str] = []
    found: dict[str, Contract] = {}
    unread: list[dict] = []

    def add(contract: Contract) -> None:
        known = found.get(contract.id)
        if known is None:
            found[contract.id] = contract
            return
        known.similarity = max(known.similarity, contract.similarity)
        known.category = known.category or contract.category

    async def inspect(provider: str, capability: str, lane: dict | None = None) -> None:
        async with gate:
            try:
                contract = await fc.inspect(provider, capability)
            except FirecrawlError as exc:
                if lane:
                    unread.append({**lane, "error": str(exc)[:200]})
                else:
                    notes.append(f"{provider}/{capability}: {exc}"[:200])
                return
        if contract:
            add(contract)
        elif lane:
            unread.append({**lane, "error": "find-tools no longer lists this tool"})

    lanes = [r for r in recipes.ALEXANDRIA_LANES if it["entity"] in (r["entity"], "any")]
    await asyncio.gather(*(inspect(r["provider"], r["capability"], r) for r in lanes))

    cohorts = _cache_get("categories")
    if cohorts is None:
        try:
            async with gate:
                cohorts = await fc.categories()
            _cache_put("categories", cohorts)
        except FirecrawlError as exc:
            cohorts = []
            notes.append(f"the Alexandria category index could not be read: {exc}"[:200])
    browsed = pick_categories(it, cohorts, config.survey_max_categories())

    async def browse(category: dict) -> None:
        cached = _cache_get(f"catalog-{category['id']}")
        if cached is not None:
            contracts = [Contract(**c) for c in cached]
        else:
            try:
                async with gate:
                    contracts = await fc.catalog(category["id"])
            except FirecrawlError as exc:
                category["error"] = str(exc)[:200]
                return
            _cache_put(f"catalog-{category['id']}", [asdict(c) for c in contracts])
        category["tools"] = len(contracts)
        for contract in contracts:
            add(contract)
    await asyncio.gather(*(browse(c) for c in browsed))

    need = f"find {it['entity']} records: {it['queries'][0]}" + (f" in {it['geo'][0]}" if it["geo"] else "")
    try:
        async with gate:
            semantic = await fc.tools(need, limit=25)
        for contract in semantic:
            add(contract)
    except FirecrawlError as exc:
        notes.append(f"find-tools: {exc}"[:200])
    try:
        async with gate:
            ranked = await fc.discover(it["request"], limit=10)
    except FirecrawlError as exc:
        ranked = []
        notes.append(f"alexandria search: {exc}"[:200])
    await asyncio.gather(*(inspect(t["provider"], t["capability"]) for t in ranked
                           if f"{t['provider']}/{t['capability']}" not in found))
    catalog = {"categories_available": len(cohorts),
               "categories_browsed": [{k: c.get(k) for k in ("id", "about", "providers", "tools", "why", "error") if c.get(k) is not None}
                                      for c in browsed],
               "tools_read": len(found)}
    return found, unread, notes, catalog


async def survey(it: dict, fc: Firecrawl | None) -> tuple[dict[str, Any], dict[str, Contract]]:
    """Step 2: every source considered, tier by tier, and whether each can run here.
    Returns the survey and the Alexandria contracts it read (for the plan and for execution)."""
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []
    contracts: dict[str, Contract] = {}
    catalog: dict[str, Any] = {}
    fc_ready = fc is not None and bool(fc.key)
    kind = it["kind"]
    if kind == "pull":
        unread: list[dict] = []
        if fc_ready:
            contracts, unread, notes, catalog = await _alexandria_contracts(fc, it)
        else:
            unread = [{**r, "error": "FIRECRAWL_API_KEY is not set on this box"} for r in recipes.ALEXANDRIA_LANES
                      if it["entity"] in (r["entity"], "any")]
        drafts = [_candidate(c, it, None) for c in contracts.values()]
        # Terms are read only for tools that could otherwise serve: a terms check per provider in a
        # 300-tool catalog would be hundreds of calls to learn nothing.
        terms: dict[str, dict] = {}
        providers = sorted({c["provider"] for c in drafts if c["can_run"]})
        if providers:
            gate = asyncio.Semaphore(SURVEY_CONCURRENCY)

            async def read_terms(provider: str) -> None:
                async with gate:
                    try:
                        terms[provider] = await fc.terms(provider)
                    except FirecrawlError as exc:
                        terms[provider] = {"accepted": True, "detail": f"terms unknown ({exc})"[:200]}
            await asyncio.gather(*(read_terms(p) for p in providers))
        candidates += [_candidate(c, it, terms.get(c.provider)) for c in contracts.values()]
        for lane in unread:
            candidates.append({"source": "firecrawl", "provider": lane["provider"], "capability": lane["capability"],
                               "tier": 1, "role": lane["role"], "verified": True, "why": lane["why"],
                               "can_run": False, "why_not": f"could not read its contract: {lane['error']}"})
    else:
        candidates.append(_plain_candidate(it, fc_ready))
    if kind == "scrape":
        for rung in SCRAPE_LADDER[2:]:
            candidates.append({"source": rung["source"], "tier": 2, "role": "scrape", "rung": rung["rung"],
                               "about": rung["what"], "can_run": False,
                               "why_not": f"not wired on this box yet (milestone {rung['wired']})"})
    for other in OTHER_SOURCES:
        if kind == "scrape":
            break  # the ladder above is the scrape survey
        if kind in ("search", "crawl", "extract") and other["source"] not in ("brightdata", "apify"):
            continue
        if kind == "pull" and not ({it["entity"], "any"} & set(other["entities"])):
            continue
        candidates.append({"source": other["source"], "tier": other["tier"], "role": other["role"],
                           "about": other["about"], "configured": config.configured(other["source"]),
                           "can_run": False, "why_not": f"not wired on this box yet (milestone {other['wired']})"})
    candidates.sort(key=lambda c: (c["tier"], not c["can_run"], not c.get("verified", False),
                                   -(c.get("field_fit") or 0), -(c.get("records_per_credit") or 0)))
    covered = any(c["can_run"] and c["tier"] in (1, 2) for c in candidates)
    for c in candidates:
        if c["source"] == "apify" and covered:
            c["note"] = "not needed: a tier 1-2 lane covers this request"
    by_tier = {str(t): sum(1 for c in candidates if c["tier"] == t) for t in (1, 2, 3)}
    # Everything that could serve is listed in full; every other tool read is listed briefly, so the
    # survey shows what was passed over without burying the answer.
    shown = [c if (c["can_run"] or c.get("verified") or c["source"] != "firecrawl") else _brief(c) for c in candidates]
    fits = sum(1 for c in candidates if c["can_run"] and c.get("role") == "discovery")
    return {"sources_considered": len(candidates), "by_tier": by_tier, "can_serve": fits, "alexandria": catalog,
            "candidates": shown, "notes": notes}, contracts


def _plain_candidate(it: dict, ready: bool) -> dict[str, Any]:
    about = {
        "search": "Firecrawl /v2/search: web and news results (2 credits per 10 results)",
        "scrape": "Firecrawl /v2/scrape, rung 1 of the scrape ladder: JS rendering, proxy auto (1 credit, +4 for a schema)",
        "crawl": "Firecrawl /v2/crawl: every page of a site up to a limit (1 credit a page)",
        "extract": "Firecrawl /v2/scrape with a json format per URL: schema or prompt in, JSON out (5 credits a page)",
    }[it["kind"]]
    return {"source": "firecrawl", "tier": 1, "role": it["kind"], "about": about, "can_run": ready,
            "why_not": None if ready else "FIRECRAWL_API_KEY is not set on this box"}


# --- step 3: the game plan -----------------------------------------------------------------

COVERAGE_PRIOR = {"bing-com": 1.0, "maps-google-com": 0.8, "bbb-business-profiles-ratings-complaint": 0.5}
DEFAULT_MAX_PAGES = 5
PREFLIGHT_EXTRA_TRIES = 3  # lanes preflight may try beyond max_lanes, to replace ones that fail


def _cells(it: dict, candidate: dict, queries: list[str]) -> list[dict[str, Any]]:
    """One call site per query x place. A tool with a location input takes the place there; one with
    only free text takes "<query> in <place>"."""
    fill = candidate["fill"]
    cells = []
    for query in queries:
        for place in it["geo"] or [None]:
            options: dict[str, Any] = {}
            if fill["location"] and place:
                options[fill["query"]] = query
                options[fill["location"]] = place
            else:
                options[fill["query"]] = f"{query} in {place}" if place else query
            cells.append({"query": query, "geo": place, "options": options})
    return cells


def _score(c: dict) -> float:
    if not c.get("credits_per_call"):
        rpc = 30.0  # free once its terms are accepted; preflight proves it returns anything
    else:
        rpc = min(c.get("records_per_credit") or 0.5, 30)
    coverage = COVERAGE_PRIOR.get(c.get("provider"), 0.4 + 0.5 * (c.get("similarity") or 0))
    return rpc * coverage * max(c.get("field_fit") or 0, 0.1)


def lane_id(c: dict) -> str:
    return f"{c['provider']}/{c['capability']}"


def rank(it: dict, surveyed: dict) -> list[dict]:
    """Every Alexandria tool that can serve this pull, best first: records per credit x coverage x
    field fit. Verified and unverified lanes compete alike; preflight is what proves a lane."""
    runnable = [c for c in surveyed["candidates"] if c.get("can_run") and c.get("role") == "discovery"]
    if it["sources"]:
        runnable = [c for c in runnable if matches_named(it["sources"], c.get("source"), c.get("provider"))]
    usable = [c for c in runnable if c["field_fit"] > 0 or not it["fields"]]
    return sorted(usable, key=_score, reverse=True)


def size_lanes(it: dict, chosen: list[dict]) -> list[dict]:
    """Cells and pages per lane. Only the base layer (the first lane) pages deep, and never past the
    skill's caps; top-ups make one call per cell. Lanes the skill caps at 2 queries a place get 2."""
    want = math.ceil(it["count"] * it["oversample"])
    lanes = []
    for index, c in enumerate(chosen):
        known = recipes.recipe(c["provider"], c["capability"]) or {}
        per_geo = known.get("max_queries_per_geo")
        queries = it["queries"][:per_geo] if per_geo else it["queries"]
        cells = _cells(it, c, queries)
        size = c.get("page_size") or 10
        pages = 1
        if index == 0 and c.get("paginates"):
            cap = min(c.get("max_pages") or DEFAULT_MAX_PAGES, c.get("max_page") or 10_000)
            pages = max(1, min(cap, math.ceil(math.ceil(want / max(1, len(cells))) / size)))
        calls = len(cells) * pages
        credits = calls * c["credits_per_call"]
        lane = {
            "lane": lane_id(c), "provider": c["provider"], "capability": c["capability"],
            "category": c.get("category"), "verified": c.get("verified", False),
            "role": "base layer" if index == 0 else "top-up", "cells": cells, "pages_per_cell": pages,
            "page_option": c["fill"]["page"] if c.get("paginates") else None, "size_option": c["fill"]["size"],
            "page_size": size, "calls": calls, "credits_per_call": c["credits_per_call"], "credits": credits,
            "usd": round(credits * config.firecrawl_usd_per_credit(), 4), "expected_records": calls * size,
            "field_fit": c["field_fit"], "why": c.get("why") or c.get("about"),
        }
        if per_geo and len(it["queries"]) > per_geo:
            lane["note"] = f"{per_geo} queries a place on this lane (the skill's cost discipline); the rest run on the other lanes"
        lanes.append(lane)
    return lanes


def game_plan(it: dict, surveyed: dict, chosen: list[dict] | None = None,
              dropped: list[tuple[dict, str]] | None = None) -> dict[str, Any]:
    """Step 3 for a pull: the chosen lanes, sized and priced, and every runnable lane not chosen with why."""
    ranked = rank(it, surveyed)
    if chosen is None:
        chosen = ranked[: it["max_lanes"]]
    lanes = size_lanes(it, chosen)
    taken = {lane["lane"] for lane in lanes}
    passed_over = [{"lane": lane_id(c), "why": why} for c, why in dropped or []]
    gone = {p["lane"] for p in passed_over}
    for c in ranked:
        if lane_id(c) not in taken and lane_id(c) not in gone:
            passed_over.append({"lane": lane_id(c), "why": "ranked below the chosen lanes"})
    for c in surveyed["candidates"]:
        if c.get("can_run") and c.get("role") == "discovery" and c not in ranked and lane_id(c) not in taken:
            why = ("not among the sources the user named" if it["sources"] else "returns none of the requested fields")
            passed_over.append({"lane": lane_id(c), "why": why})
    return {"lanes": lanes, "passed_over": passed_over, "want_records": math.ceil(it["count"] * it["oversample"]),
            "dedupe_keys": ["name+phone", "name+address"], "anti_patterns": recipes.ANTI_PATTERNS}


def lane_options(lane: dict, cell: dict, page: int) -> dict[str, Any]:
    options = dict(cell["options"])
    if lane.get("size_option"):
        options[lane["size_option"]] = lane["page_size"]
    if lane.get("page_option") and page > 1:
        options[lane["page_option"]] = page
    return options


def looks_like(entity: str, record: dict) -> bool:
    have = {field_key(k) for k, v in record.items() if v not in (None, "", [], {})}
    named = bool(have & synonyms("name"))
    if entity == "business":
        return named and bool(have & (synonyms("phone") | synonyms("address") | synonyms("website")))
    return named


def preview(record: dict) -> dict[str, Any]:
    """A sample row small enough to read in a plan: identity and place, not contact details."""
    wanted = ("name", "business_name", "title", "city", "state", "category", "primary_category")
    return {k: record[k] for k in wanted if k in record and not isinstance(record[k], (dict, list))}


class Meter:
    """Credits spent so far by a plan's preflight: kept outside the call so a failure never loses it."""

    def __init__(self) -> None:
        self.credits = 0.0
        self.out_of_credits = False


def preflight_cap(it: dict) -> float:
    cap = float(config.preflight_max_credits())
    if it["max_cost_usd"] is not None:
        cap = min(cap, it["max_cost_usd"] / config.firecrawl_usd_per_credit())
    return cap


async def preflight_lane(it: dict, lane: dict, contract: Contract | None, fc: Firecrawl, balance: float | None,
                         store: Path, meter: Meter, ctx=None) -> dict:
    """One real call on a lane's first cell. With a job context the call is reserved first, so the
    ledger enforces the cap too. The records are kept, so execution does not buy that page again."""
    rate = config.firecrawl_usd_per_credit()
    cost = float(lane["credits_per_call"])
    if contract is None or not lane["cells"]:
        return {"lane": lane["lane"], "skipped": "no contract to call"}
    if balance is not None and balance - config.firecrawl_balance_floor() - meter.credits < cost:
        return {"lane": lane["lane"], "skipped": "the Firecrawl balance cannot cover it"}
    if meter.credits + cost > preflight_cap(it):
        return {"lane": lane["lane"], "skipped": f"over the preflight cap ({preflight_cap(it):g} credits)"}
    reservation = None
    if ctx is not None:
        try:
            reservation = ctx.reserve(cost * rate, "firecrawl", f"preflight {lane['lane']}")
        except Conflict as exc:
            return {"lane": lane["lane"], "skipped": str(exc)[:200]}
    cell = lane["cells"][0]
    charged = cost
    try:
        out = await fc.run_tool(contract, lane_options(lane, cell, 1))
        charged = out["credits"]
    except (FirecrawlError, ValueError) as exc:
        # Refused (4xx) or never sent: free. Unknown outcome (timeout, 5xx): charged in full.
        status = getattr(exc, "status", 400)
        charged = 0.0 if isinstance(exc, ValueError) or 400 <= status < 500 else cost
        meter.out_of_credits = isinstance(exc, OutOfCredits)
        return {"lane": lane["lane"], "ok": False, "error": str(exc)[:200], "credits": charged}
    finally:
        meter.credits += charged
        if reservation:
            ctx.settle(reservation, charged * rate)
    records = out["records"]
    fit, covered = field_fit(it["fields"], sorted({k for r in records for k in r}))
    write_records(store, [tag(r, lane["lane"], cell, 1) for r in records], "raw.jsonl")
    mark_done(store, key_for(lane["lane"], cell, 1), len(records))
    return {"lane": lane["lane"], "ok": bool(records), "records": len(records),
            "matching_entity": sum(1 for r in records if looks_like(it["entity"], r)),
            "fields_present": covered, "field_fit": round(fit, 2), "credits": charged,
            "sample": [preview(r) for r in records[:3]]}


async def preflight_pick(it: dict, ranked: list[dict], fc: Firecrawl, contracts: dict[str, Contract],
                         balance: float | None, store: Path, meter: Meter, ctx=None
                         ) -> tuple[list[dict], list[dict], list[tuple[dict, str]]]:
    """The skill's rule: never trust the catalog alone. Walk the ranked lanes, preflight each, keep
    those that return the entity, drop those that do not and try the next, until max_lanes are kept.
    A lane preflight could not afford is kept, marked unverified."""
    kept: list[dict] = []
    results: list[dict] = []
    dropped: list[tuple[dict, str]] = []
    for candidate in ranked:
        if len(kept) >= it["max_lanes"] or len(results) >= it["max_lanes"] + PREFLIGHT_EXTRA_TRIES:
            break
        if meter.out_of_credits:
            kept.append(candidate)
            continue
        lane = size_lanes(it, [*kept, candidate])[-1]
        result = await preflight_lane(it, lane, contracts.get(lane["lane"]), fc, balance, store, meter, ctx)
        results.append(result)
        if result.get("skipped") or (result.get("ok") and result.get("matching_entity")):
            kept.append(candidate)
        elif result.get("ok"):
            dropped.append((candidate, f"preflight: {result['records']} records came back, none of them {it['entity']} records"))
        else:
            dropped.append((candidate, f"preflight: {result.get('error') or 'no records came back'}"))
    return kept, results, dropped


# --- the plan's files ------------------------------------------------------------------------

def key_for(lane: str, cell: dict, page: int | str) -> str:
    return f"{lane}|{cell.get('geo') or '-'}|{cell['query']}|{page}"


def tag(record: dict, lane: str, cell: dict, page: int) -> dict[str, Any]:
    return {**record, "_lane": lane, "_geo": cell.get("geo"), "_query": cell["query"], "_page": page}


def store_for(plan_id: str) -> Path:
    root = config.plans_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / plan_id
    path.mkdir(exist_ok=True, mode=0o700)
    return path


def write_records(store: Path, records: list[dict], name: str) -> None:
    if not records:
        return
    with (store / name).open("a", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_records(store: Path, name: str) -> list[dict]:
    path = store / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # a line cut short by a crash; the page it belonged to is not marked done
    return rows


def mark_done(store: Path, done_key: str, records: int) -> None:
    """A page is done once its records are written; the count says whether it was a short page."""
    with (store / "done.txt").open("a", encoding="utf-8") as out:
        out.write(f"{done_key}\t{records}\n")


def done_keys(store: Path) -> dict[str, int]:
    path = store / "done.txt"
    done: dict[str, int] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, count = line.rpartition("\t")
            if key:
                done[key] = int(count) if count.isdigit() else 0
    return done


def save_contracts(store: Path, contracts: dict[str, Contract]) -> None:
    (store / "contracts.json").write_text(json.dumps({k: asdict(v) for k, v in contracts.items()}, default=str))


def load_contracts(store: Path) -> dict[str, Contract]:
    path = store / "contracts.json"
    if not path.exists():
        return {}
    return {k: Contract(**v) for k, v in json.loads(path.read_text()).items()}


def purge_old(now: float | None = None) -> int:
    """Delete plan folders older than the retention period. Their records may hold contact data."""
    root = config.plans_dir()
    if not root.exists():
        return 0
    cutoff = (now or time.time()) - config.retention_days() * 86400
    removed = 0
    for folder in root.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed


# --- assembling a plan ------------------------------------------------------------------------

async def make_plan(args: dict, ledger: Ledger, fc: Firecrawl | None, ctx=None) -> dict[str, Any]:
    """Steps 1-3. Returns the stored plan: everything the user needs to say yes or no.

    The plan row exists from the start (status preparing), so a failure part-way still records
    what preflight spent and leaves a cancelled plan, never one that can be approved half-built."""
    it = intake(args)
    plan = ledger.create_plan(it["kind"], it["request"], {"step_1_intake": it}, 0,
                              config.plan_ttl_hours() * 3600, status="preparing")
    plan_id = plan["plan_id"]
    meter = Meter()
    rate = config.firecrawl_usd_per_credit()
    body: dict[str, Any] = {"step_1_intake": it}
    try:
        surveyed, contracts = await survey(it, fc)
        body["step_2_survey"] = surveyed
        warnings: list[str] = []
        for name in it["sources"]:
            hits = [c for c in surveyed["candidates"] if matches_named([name], c.get("source"), c.get("provider"))]
            if not hits:
                warnings.append(f"the named source {name!r} is not one data-box knows")
            elif not any(c["can_run"] for c in hits):
                warnings.append(f"the named source {name!r} cannot run here: {hits[0].get('why_not')}")
        balance = None
        if fc is not None and fc.key:
            try:
                balance = (await fc.credits()).get("remaining")
            except FirecrawlError as exc:
                warnings.append(f"could not read the Firecrawl balance: {exc}"[:240])
        broke = balance is not None and balance <= 0
        if broke:
            warnings.append(f"the Firecrawl balance is {balance} credits: add credits before executing; preflight was skipped")

        store = store_for(plan_id)
        results: list[dict] = []
        if it["kind"] == "pull":
            ranked = rank(it, surveyed)
            chosen, dropped = None, []
            if ranked and not broke and it["preflight"] and fc is not None:
                chosen, results, dropped = await preflight_pick(it, ranked, fc, contracts, balance, store, meter, ctx)
                if results and not any(r.get("ok") for r in results):
                    warnings.append("no lane returned records in preflight: read each lane's result before approving")
                if meter.out_of_credits:
                    warnings.append("Firecrawl ran out of credits during preflight: add credits before executing")
            elif ranked and not it["preflight"]:
                warnings.append("preflight is off: the lanes are unverified until execution")
            plan_body = game_plan(it, surveyed, chosen, dropped)
            proven = {r["lane"] for r in results if r.get("ok") and r.get("matching_entity")}
            tried = {r["lane"]: r for r in results}
            for lane in plan_body["lanes"]:
                lane["preflight"] = ("confirmed" if lane["lane"] in proven else
                                     f"not run: {tried[lane['lane']]['skipped']}" if lane["lane"] in tried else "not run")
        else:
            plan_body = plain_plan(it, surveyed)
        if not plan_body["lanes"]:
            warnings.append("no runnable lane covers this request; the survey lists every source and why each cannot run")
        credits = sum(lane["credits"] for lane in plan_body["lanes"])
        estimate = round(credits * rate, 4)
        cap = it["max_cost_usd"]
        budget = round(max(estimate * 1.2, 0.01), 4) if cap is None else cap
        if cap is not None and estimate > cap:
            warnings.append(f"the worst case (${estimate:.4f}) is over max_cost_usd (${cap:.4f}): execution stops at the cap")
        if balance is not None and 0 < balance < credits:
            warnings.append(f"the worst case needs ~{credits:g} credits and Firecrawl has {balance}: execution stops "
                            f"before the balance runs out")
        save_contracts(store, {lane["lane"]: contracts[lane["lane"]] for lane in plan_body["lanes"]
                               if lane["lane"] in contracts})
        body["step_3_game_plan"] = {
            **plan_body, "credits_total": credits, "usd_total": estimate, "budget_usd": budget, "usd_per_credit": rate,
            "cost_note": ("credits_total is the worst case: every planned page. Execution stops sooner, when the "
                          "deduped list reaches the count, when a cell's pages run short or start repeating, or at "
                          "the approved amount, whichever comes first."),
            "firecrawl_balance_credits": balance,
            "preflight": {"credits": meter.credits, "usd": round(meter.credits * rate, 4), "results": results},
            "warnings": warnings,
        }
        body["step_4"] = ("Nothing but the preflight above has been spent. Show this whole plan to the user; only "
                          "after they say yes, call execute with this plan_id and approve=true.")
        return ledger.write_plan(plan_id, body, preflight_spent_usd=meter.credits * rate, budget_usd=budget,
                                 status="awaiting_approval")
    except BaseException as exc:
        body["error"] = f"{type(exc).__name__}: {exc}"[:400]
        ledger.write_plan(plan_id, body, preflight_spent_usd=meter.credits * rate, status="cancelled")
        raise


def plain_plan(it: dict, surveyed: dict) -> dict[str, Any]:
    """Step 3 for search, scrape, crawl and extract: one Firecrawl lane, priced up front."""
    runnable = next((c for c in surveyed["candidates"] if c["source"] == "firecrawl" and c["can_run"]), None)
    if runnable is None:
        return {"lanes": []}
    kind = it["kind"]
    if kind == "search":
        limit = min(it["limit"] or 10, 100)
        credits = fc_mod.search_credits(limit, len(it["search_sources"])) * len(it["queries"])
        lane = {"lane": "firecrawl/search", "queries": it["queries"], "sources": it["search_sources"], "limit": limit}
    elif kind == "scrape":
        fmt = it["format"] if it["format"] in ("markdown", "html", "links") else "markdown"
        formats = [{"type": "json", "schema": it["schema"]}] if it["schema"] else [fmt]
        credits = fc_mod.scrape_credits(formats)
        lane = {"lane": "firecrawl/scrape", "url": it["urls"][0], "formats": formats, "rung": 1,
                "ladder": [{"rung": r["rung"], "source": r["source"], "what": r["what"],
                            "wired": r["wired"] is True} for r in SCRAPE_LADDER]}
    elif kind == "crawl":
        limit = min(it["limit"] or 50, 1000)
        credits = float(limit * fc_mod.CRAWL_CREDITS_PER_PAGE)
        lane = {"lane": "firecrawl/crawl", "url": it["urls"][0], "limit": limit}
    else:
        fmt_spec: dict[str, Any] = {"type": "json"}
        if it["schema"]:
            fmt_spec["schema"] = it["schema"]
        if it["prompt"]:
            fmt_spec["prompt"] = it["prompt"]
        credits = fc_mod.scrape_credits([fmt_spec]) * len(it["urls"])
        lane = {"lane": "firecrawl/extract", "urls": it["urls"], "format": fmt_spec}
    lane.update({"credits": credits, "usd": round(credits * config.firecrawl_usd_per_credit(), 4)})
    return {"lanes": [lane]}
