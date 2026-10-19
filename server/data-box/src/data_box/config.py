"""Settings, read from the environment at call time so a test (or an operator) can change them
without re-importing anything. Every variable data-box reads is named here and nowhere else."""
from __future__ import annotations

import os
from pathlib import Path


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def token() -> str:
    """The one bearer token every door checks. data-box refuses to start without it."""
    return env("DATABOX_TOKEN")


def port() -> int:
    return int(env("DATABOX_PORT", "8092"))


def host() -> str:
    return env("DATABOX_HOST", "127.0.0.1")


def state_dir() -> Path:
    return Path(env("DATABOX_STATE_DIR") or Path.home() / ".data-box")


def revision() -> str:
    """The deployed commit, written into the release env by the activator."""
    return env("DATABOX_REVISION", "dev")


def text_limit() -> int:
    return int(env("DATABOX_TEXT_LIMIT", "24000"))


def fetch_timeout() -> float:
    return float(env("DATABOX_FETCH_TIMEOUT_SECONDS", "30"))


def fetch_max_bytes() -> int:
    return int(env("DATABOX_FETCH_MAX_BYTES", str(2_000_000)))


def user_agent() -> str:
    return env("DATABOX_USER_AGENT",
               "Mozilla/5.0 (compatible; data-box/0.1; +https://github.com/jbellsolutions/data-box)")


def default_scrape_cap_usd() -> float:
    return float(env("DATABOX_SCRAPE_MAX_COST_USD", "0.05"))


# --- plans: every paid call goes through plan -> approve -> execute ---------------------------

def plan_ttl_hours() -> float:
    """An approved-or-not plan expires after this; prices and balances are re-checked by a new plan."""
    return float(env("DATABOX_PLAN_TTL_HOURS", "24"))


def preflight_max_credits() -> int:
    """The only spend allowed before approval: 1-2 real calls per lane to prove it returns the entity."""
    return int(env("DATABOX_PREFLIGHT_MAX_CREDITS", "25"))


def execute_concurrency() -> int:
    """Parallel provider calls in one execute job. Firecrawl Hobby runs 5 jobs at once; leave one spare."""
    return max(1, int(env("DATABOX_EXECUTE_CONCURRENCY", "4")))


def retention_days() -> float:
    """Records a plan collected (which may hold contact data) are deleted after this many days."""
    return float(env("DATABOX_RETENTION_DAYS", "30"))


def firecrawl_balance_floor() -> float:
    """Credits an execution never spends below. 0 means it stops before the balance would go negative."""
    return float(env("DATABOX_FIRECRAWL_BALANCE_FLOOR", "0"))


def min_new_ratio() -> float:
    """A cell stops paging when a page adds less than this share of new unique records: deep pages of
    Bing and Maps re-fetch the same chains (a 75% duplicate collapse burned ~8,000 credits on 2026-09-28)."""
    return float(env("DATABOX_MIN_NEW_RATIO", "0.3"))


def survey_max_categories() -> int:
    """Alexandria categories a survey browses in full, the most relevant first."""
    return int(env("DATABOX_SURVEY_MAX_CATEGORIES", "6"))


def catalog_ttl_hours() -> float:
    """How long a category's tool list is reused before it is read again (discovery is free, but slow)."""
    return float(env("DATABOX_CATALOG_TTL_HOURS", "24"))


def plans_dir() -> Path:
    return state_dir() / "plans"


# --- Firecrawl ----------------------------------------------------------------------------------

def firecrawl_key() -> str:
    return env("FIRECRAWL_API_KEY")


def firecrawl_base() -> str:
    return env("FIRECRAWL_API_BASE", "https://api.firecrawl.dev").rstrip("/")


def firecrawl_usd_per_credit() -> float:
    """Hobby is $19 a month for 5,000 credits (about $0.0038 each). Set this to the real plan's rate."""
    return float(env("DATABOX_FIRECRAWL_USD_PER_CREDIT", "0.0038"))


# Providers data-box knows how to use, and the variables that turn each on. `status` reports each
# one; a verb backed by a provider is only listed once that provider is wired and configured.
PROVIDERS: dict[str, dict] = {
    "firecrawl": {"env": ["FIRECRAWL_API_KEY"], "tier": 1,
                  "for": "tier 1: pulls through Alexandria's providers, web and news search, scrape rung 1, crawl, extract"},
    "moltsets": {"env": ["MOLTSETS_API_KEY"], "tier": 1,
                 "for": "tier 1: people and contact data, on a plan's deduped shortlist (wired in D2)"},
    "discolike": {"env": ["DISCOLIKE_API_KEY"], "tier": 1,
                  "for": "tier 1: company discovery and firmographics (wired in D2)"},
    "decodo": {"env": ["DECODO_SCRAPER_API_TOKEN"], "tier": 2, "for": "tier 2: scrape rung 2b (Web Scraping API), templates (wired in D3)"},
    "decodo-proxy": {"env": ["DECODO_PROXY_USER", "DECODO_PROXY_PASSWORD"], "tier": 2,
                     "for": "tier 2: residential re-fetch, scrape rung 2a (gate.decodo.com: port 7000 rotates, 10001+ are sticky sessions)"},
    "brightdata": {"env": ["BRIGHTDATA_API_KEY"], "tier": 2, "for": "tier 2: scrape rung 3 (Web Unlocker), SERP, datasets and scrapers (wired in D3-D4)"},
    "brightdata-proxy": {"env": ["BRIGHTDATA_PROXY_USER", "BRIGHTDATA_PROXY_PASSWORD"], "tier": 2, "for": "tier 2: residential egress (port 44445)"},
    "hyperbrowser": {"env": ["HYPERBROWSER_API_KEY"], "tier": 2, "for": "scrape rung 5: stealth browser with proxies and CAPTCHA solving (wired in D3)"},
    "browser-box": {"env": ["DATABOX_BROWSERBOX_URL", "DATABOX_BROWSERBOX_TOKEN"], "tier": 2, "for": "scrape rung 6, the last one: browser-box's Steel browser (wired in D3)"},
    "apify": {"env": ["APIFY_TOKEN"], "tier": 3, "for": "tier 3, the backup's backup: Apify Store actors, only when no tier 1-2 lane fits (wired in D5)"},
    "jev": {"env": ["TYPESAFE_API_KEY"], "tier": 0, "for": "engine: ranks lanes and checks samples in plans (wired in D6)"},
    "openrouter": {"env": ["OPENROUTER_API_KEY"], "tier": 0, "for": "engine: the LLM behind Jev (wired in D6)"},
}


def configured(provider: str) -> bool:
    return all(env(name) for name in PROVIDERS[provider]["env"])
