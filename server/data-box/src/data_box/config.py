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


# Providers data-box knows how to use, and the variables that turn each on. `status` reports each
# one; a verb backed by a provider is only listed once that provider is wired and configured.
PROVIDERS: dict[str, dict] = {
    "firecrawl": {"env": ["FIRECRAWL_API_KEY"], "for": "scrape rung 1, websearch (incl. Alexandria), crawl, extract"},
    "brightdata": {"env": ["BRIGHTDATA_API_KEY"], "for": "scrape rung 2 (Unlocker), websearch fallback (SERP), datasets and scrapers"},
    "decodo": {"env": ["DECODO_SCRAPER_API_TOKEN"], "for": "scrape rung 3 (Web Scraping API), templates"},
    "decodo-proxy": {"env": ["DECODO_PROXY_USER", "DECODO_PROXY_PASSWORD"], "for": "residential egress for scrape rung 0b (gate.decodo.com: port 7000 rotates, 10001+ are sticky sessions)"},
    "brightdata-proxy": {"env": ["BRIGHTDATA_PROXY_USER", "BRIGHTDATA_PROXY_PASSWORD"], "for": "residential egress (port 44445)"},
    "apify": {"env": ["APIFY_TOKEN"], "for": "sources and run (Apify Store actors)"},
    "moltsets": {"env": ["MOLTSETS_API_KEY"], "for": "run: B2B people and contact data (never automatic)"},
    "discolike": {"env": ["DISCOLIKE_API_KEY"], "for": "run: company discovery (never automatic)"},
    "browser-box": {"env": ["DATABOX_BROWSERBOX_URL", "DATABOX_BROWSERBOX_TOKEN"], "for": "scrape rung 4 (a real browser)"},
    "jev": {"env": ["TYPESAFE_API_KEY"], "for": "ask: fast routing; checks on results"},
    "openrouter": {"env": ["OPENROUTER_API_KEY"], "for": "ask: the LLM behind Jev; lead intent specs"},
}


def configured(provider: str) -> bool:
    return all(env(name) for name in PROVIDERS[provider]["env"])
