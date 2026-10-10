"""System 1 decision-model spike (2026-10-09).

Makes a handful of real decision calls and records latency + exact response shape:
  ts1  TypeSafe Jev direct, home page: target choice (10 elements + none) + login-wall noul + blocker choice
  ts2  TypeSafe Jev direct, /login page: login-wall noul + blocker choice
  ts3  TypeSafe Jev direct, ts1 with every option order reversed (order sensitivity)
  or1  OpenRouter /api/v1/systemone, the exact ts1 body, model perplexity/pplx-decider-v1.1-27b

Payload shape follows jev-automation core/decide.ts @ edcbbae (state = {command, page:{url,title,...}},
target question instructions = {question, command}, criteria = element id -> describeElement string,
plus a "none" option) and core/verify.ts BLOCKERS. The page.text_excerpt / page.fields additions are
ours: the login-wall and blocker questions need some page evidence.

Keys are read by NAME from the repository's .env into this process only. Nothing here
prints, logs or writes a key or a request header. Output: raw JSON per call to argv[1] (a directory).

Run:  .venv/bin/python spike_decide.py <outdir> [ts1 ts2 ts3 or1]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

ENV_FILE = Path(os.environ.get("ENV_FILE", ".env"))
TS_URL = "https://api.typesafe.ai/v1/systemone"
OR_SYSTEMONE = "https://openrouter.ai/api/v1/systemone"
OR_KEY_INFO = "https://openrouter.ai/api/v1/key"
JEV_MODEL = "jev-1.13.0"  # pinned, not jev-latest
DECIDER_MODEL = "perplexity/pplx-decider-v1.1-27b"
KEEP_RESPONSE_HEADERS = ("x-request-id", "x-typesafe-request-id", "request-id", "retry-after", "x-ratelimit-limit",
                         "x-ratelimit-remaining", "x-ratelimit-reset", "x-ratelimit-used", "server",
                         "cf-ray", "x-generation-id")


def load_key(name: str) -> str:
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{name} not found in .env (name only reported)")


# ---- fixtures built from the live public page https://quotes.toscrape.com/ (fetched 2026-10-09) ----
HOME_ELEMENTS = [  # (id, describeElement-style string), in page order
    ("e1", 'link "Quotes to Scrape" -> /'),
    ("e2", 'link "Login" -> /login'),
    ("e3", 'link "(about)" -> /author/Albert-Einstein'),
    ("e4", 'link "change" -> /tag/change/page/1/'),
    ("e5", 'link "inspirational" -> /tag/inspirational/page/1/'),
    ("e6", 'link "(about)" -> /author/Jane-Austen'),
    ("e7", 'link "Next ->" -> /page/2/'),
    ("e8", 'link "love" -> /tag/love/'),
    ("e9", 'link "GoodReads.com" -> https://www.goodreads.com/quotes'),  # near-distractor: says "quotes"
    ("e10", 'link "Zyte" -> https://www.zyte.com'),
]
NONE_OPTION = ("none", "No element listed here advances the goal")
GOAL = "Find more quotes beyond the ones shown on this page"
EXPECTED = {"ts1": {"target": "e7", "login_wall": "low (<0.5)", "blocker": "none"},
            "ts2": {"login_wall": "high (>0.5)", "blocker": "login_wall"},
            "ts3": {"target": "e7", "login_wall": "low (<0.5)", "blocker": "none"},
            "or1": {"target": "e7", "login_wall": "low (<0.5)", "blocker": "none"}}

BLOCKERS = {  # jev-automation core/verify.ts BLOCKERS @ edcbbae
    "none": "Nothing is in the way",
    "consent_dialog": "A cookie or privacy consent dialog",
    "login_wall": "A sign-in or account prompt",
    "captcha": "A captcha or robot check",
    "error_page": "An error, not found, or cannot-reach page",
    "no_results": "A search or list that says it found nothing",
    "popup": "A newsletter, app-install or other overlay",
    "permission_prompt": "A request for a permission such as location, notifications or camera",
    "no_change": "The page did not change at all",
}

LOGIN_WALL_Q = {
    "type": "noul",
    "instructions": "Is a sign-in or login form the main thing on this page, so the user must log in before they can continue?",
    "criteria": {"true": "The page mainly asks for a username/email and password, or says to sign in to continue",
                 "false": "The page shows its normal content; any sign-in link is just one link among many"},
}


def blocker_q(reverse: bool) -> dict:
    items = list(BLOCKERS.items())
    if reverse:
        items.reverse()
    return {"type": "choice", "instructions": {"question": "What, if anything, on this page is in the way of the goal?", "goal": GOAL},
            "criteria": dict(items)}


def home_body(model: str, reverse: bool = False) -> dict:
    opts = HOME_ELEMENTS + [NONE_OPTION]
    if reverse:
        opts = list(reversed(opts))
    return {
        "model": model,
        "state": {
            "command": GOAL,
            "page": {"url": "https://quotes.toscrape.com/", "title": "Quotes to Scrape",
                     "text_excerpt": "Quotes to Scrape. Login. “The world as we have created it is a process of our "
                                     "thinking...” by Albert Einstein (about) Tags: change deep-thoughts thinking world. "
                                     "... Next →  Top Ten tags: love inspirational life humor books reading friendship "
                                     "friends truth simile. Quotes by: GoodReads.com Made with love by Zyte"},
        },
        "questions": {
            "target": {"type": "choice",
                       "instructions": {"question": "Which element on the current page should be clicked next to advance "
                                                    "the goal? Choose 'none' if no element listed here advances it.",
                                        "command": GOAL},
                       "criteria": dict(opts)},
            "login_wall": LOGIN_WALL_Q,
            "blocker": blocker_q(reverse),
        },
    }


def login_body(model: str) -> dict:
    return {
        "model": model,
        "state": {
            "command": GOAL,
            "page": {"url": "https://quotes.toscrape.com/login", "title": "Quotes to Scrape",
                     "text_excerpt": "Quotes to Scrape. Login. Username Password Login",
                     "fields": ['textbox "username"', 'password field "password"', 'button "Login"']},
        },
        "questions": {"login_wall": LOGIN_WALL_Q, "blocker": blocker_q(False)},
    }


def call(client: httpx.Client, url: str, key: str, body: dict) -> dict:
    t0 = time.perf_counter()
    r = client.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
    ms = (time.perf_counter() - t0) * 1000
    try:
        payload = r.json()
    except ValueError:
        payload = {"_non_json": r.text[:500]}
    return {"url": url, "status": r.status_code, "wall_ms": round(ms, 1), "http_version": r.http_version,
            "response_headers": {k: v for k, v in r.headers.items() if k.lower() in KEEP_RESPONSE_HEADERS},
            # every header NAME (no values), so a missed request-id / rate-limit header is visible
            "response_header_names": sorted(k.lower() for k in r.headers.keys()),
            "request_body": body, "response": payload}


def or_key_usage(client: httpx.Client, key: str) -> dict:
    r = client.get(OR_KEY_INFO, headers={"Authorization": f"Bearer {key}"})
    d = (r.json() or {}).get("data", {}) if r.status_code == 200 else {}
    # Only numeric usage fields: the "label" field can contain a partial key, so it is dropped.
    return {k: d.get(k) for k in ("usage", "usage_daily", "limit", "limit_remaining")} | {"status": r.status_code}


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[2:] or ["ts1", "ts2", "ts3", "or1"]
    results = {}
    with httpx.Client(timeout=30.0) as client:
        if any(w.startswith("ts") for w in wanted):
            ts_key = load_key("TYPESAFE_API_KEY")
            for name in [w for w in wanted if w.startswith("ts")]:
                body = {"ts1": lambda: home_body(JEV_MODEL), "ts2": lambda: login_body(JEV_MODEL),
                        "ts3": lambda: home_body(JEV_MODEL, reverse=True)}[name]()
                results[name] = call(client, TS_URL, ts_key, body)
            del ts_key
        if "or1" in wanted:
            or_key = load_key("OPENROUTER_API_KEY")
            results["or_key_before"] = or_key_usage(client, or_key)
            results["or1"] = call(client, OR_SYSTEMONE, or_key, home_body(DECIDER_MODEL))
            time.sleep(3)
            results["or_key_after"] = or_key_usage(client, or_key)
            del or_key
    for name, res in results.items():
        (out / f"{name}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
        if isinstance(res, dict) and "response" in res:
            resp = res["response"]
            ans = resp.get("answers", {}) if isinstance(resp, dict) else {}
            brief = {q: (a.get("choice"), a.get("confidence"), a.get("noul")) for q, a in ans.items()}
            print(name, res["status"], f'{res["wall_ms"]} ms', resp.get("model") if isinstance(resp, dict) else None,
                  resp.get("usage") if isinstance(resp, dict) else None, brief, "expected:", EXPECTED.get(name))
            if res["status"] >= 400:
                print("   error body:", json.dumps(resp)[:400])
        else:
            print(name, res)


if __name__ == "__main__":
    main()
