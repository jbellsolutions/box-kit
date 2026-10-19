"""What Justin's firecrawl-alexandria skill verified live (2026-09), kept as data the planner uses as
priors. A recipe never decides alone: every plan re-reads the live contract (price, inputs,
pagination) through find-tools, and preflight proves the lane returns the entity before anyone pays
for the bulk pull.

role: "discovery" lanes build the raw list; "enrichment" lanes reveal contacts and run only on the
deduped shortlist, never at discovery scale (5K names through a per-record lane is 25K credits).

max_pages: the skill's cost discipline. The per-call price is not the real cost; pages per cell is
the multiplier that blows budgets (deep Maps and Bing pagination re-fetches the same chains, ~70%
dedupe collapse observed). BBB goes deep because it costs 1 credit; Bing stops at 3 (it silently
truncates around page 5); Maps has no pages at all.
"""
from __future__ import annotations

ALEXANDRIA_LANES: list[dict] = [
    {"provider": "bbb-business-profiles-ratings-complaint", "capability": "businesses/search", "entity": "business",
     "role": "discovery", "max_pages": 100, "partition": "state code or city (pagination stops at page 100)",
     "why": "base layer: the cheapest listing call in the catalog (1 credit, 15 a page), no terms; skews to accredited firms, so never the only lane"},
    {"provider": "bing-com", "capability": "businesses/search", "entity": "business", "role": "discovery",
     "max_pages": 3, "max_queries_per_geo": 2, "partition": "category x metro, at most 2 queries a metro",
     "why": "top-up: name, address, phone and website, up to 30 a page; cap 3 pages a metro (it silently truncates near page 5)"},
    {"provider": "maps-google-com", "capability": "businesses/search", "entity": "business", "role": "discovery",
     "max_pages": 1, "max_queries_per_geo": 2, "partition": "one call per 'category in city' cell (no pagination)",
     "why": "top-up: up to 20 places a call with phone and website; overlaps Bing on chains, so dedupe"},
    {"provider": "houzz-com", "capability": "professionals/search", "entity": "business", "role": "discovery",
     "max_pages": 3, "why": "home-trades professionals (not property agents)"},
    {"provider": "apollo", "capability": "people/search", "entity": "person", "role": "discovery",
     "max_pages": 5, "why": "free identity discovery by title and location once its terms are accepted"},
    {"provider": "bbb-business-profiles-ratings-complaint", "capability": "businesses/profile", "entity": "business",
     "role": "enrichment", "why": "website, email (obfuscated; decode it), LinkedIn, employees; ~30% have email"},
    {"provider": "apollo", "capability": "people/match", "entity": "person", "role": "enrichment",
     "why": "email reveal, per record: shortlist only"},
    {"provider": "fullenrich", "capability": "contacts/work-email", "entity": "person", "role": "enrichment",
     "why": "work email, per record: shortlist only"},
]

ANTI_PATTERNS = [
    "Using BBB as the only source for a broad vertical: it skews to accredited firms and misses most operators.",
    "Paying per-record people search for discovery: enrichment lanes are for the shortlist.",
    "Deep Maps or Bing pagination without page and query caps: the runaway-cost pattern.",
    "Running Bing and Google Maps sweeps without dedupe keys: they overlap heavily on chains.",
]

# What people call a source, to the ids the survey uses. A named source is matched on these and on
# substrings ("disco" -> discolike, "bbb" -> the BBB provider).
ALIASES = {
    "google maps": "maps-google-com", "gmaps": "maps-google-com", "google": "maps-google-com",
    "bing maps": "bing-com", "better business bureau": "bbb-business-profiles-ratings-complaint",
    "molt": "moltsets", "bright data": "brightdata", "bright-data": "brightdata", "alexandria": "firecrawl",
}


def recipe(provider: str, capability: str) -> dict | None:
    return next((r for r in ALEXANDRIA_LANES if r["provider"] == provider and r["capability"] == capability), None)


# Alexandria categories worth browsing for each entity: "ids" match a category's id, "phrases" its
# description. The request's own words are matched too, so a vertical ("real estate", "restaurants")
# pulls in its category. Kept specific: on the live index (2026-09-28) loose words like "review" and
# "service" pulled in shopping, travel and apps for a roofing pull.
ENTITY_CATEGORY_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "business": {"ids": ("places", "compan", "local", "business"),
                 "phrases": ("local business", "company records", "business directo")},
    "person": {"ids": ("people", "person", "professional"), "phrases": ("the people at", "professional profiles")},
    "property": {"ids": ("real-estate", "propert", "housing"), "phrases": ("property", "real estate")},
    "any": {"ids": (), "phrases": ()},
}

# A general directory for an entity takes the request's words as its search, so it serves any
# vertical (Bing, Google Maps and both BBBs are "businesses/search"). Any other tool the catalog turns
# up must be about the request itself: live, a roofing survey otherwise marked GolfNow tee times,
# SeatGeek and Trader Joe's as lanes that could serve.
DIRECTORY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "business": ("businesses/search",),
    "person": ("people/search", "professionals/search"),
    "property": ("properties/search", "listings/search", "homes/search"),
}

# Words too general to say what a request is about: "roofing contractors" is about roofing, and a
# firestop contractors' directory is not a roofers' one.
GENERIC_WORDS = {
    "contractor", "contractors", "company", "companies", "business", "businesses", "service", "services",
    "agency", "agencies", "firm", "firms", "shop", "shops", "store", "stores", "provider", "providers", "local",
    "near", "best", "owner", "owners", "professional", "professionals", "expert", "experts", "specialist",
    "specialists", "vendor", "vendors", "supplier", "suppliers", "people", "person", "persons", "agent", "agents",
}
