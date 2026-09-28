"""Thin client for a self-hosted Steel browser (steel-dev/steel-browser, Apache-2.0).

Steel owns the only Chromium on the box. It exposes a REST API for one-shot work and
CDP for agents that want to drive the browser step by step. The gateway only speaks
REST, which is why it needs no Playwright and no browser binary of its own.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from .security import UnsafeUrl

BASE = os.getenv("BB_STEEL_URL", "http://steel:3000").rstrip("/")
CDP = os.getenv("BB_STEEL_CDP_URL", "ws://steel:3000/")
TIMEOUT = float(os.getenv("BB_STEEL_TIMEOUT_SECONDS", "120"))
_PREFIXES = ("/v1", "")


class SteelUnavailable(RuntimeError):
    """Steel is not answering. The caller should say so rather than substitute silently."""


def _failed(method: str, path: str, response: httpx.Response) -> Exception:
    # The in-browser guard failing a request surfaces as a Steel 500. That is a refusal, not an
    # outage: reporting it as "the browser is down" is the misreporting this repo exists to stop.
    if "ERR_BLOCKED_BY_CLIENT" in response.text:
        return UnsafeUrl(
            "refused inside the browser: the page went to a private or internal address (loopback, a "
            "private network, cloud metadata, or a name that resolves to one), and only the public web is reachable"
        )
    return SteelUnavailable(f"steel {method} {path} returned {response.status_code}: {response.text[:300]}")


async def _call(method: str, path: str, payload: dict | None = None, *, timeout: float | None = None) -> Any:
    """Try /v1 then bare. The OSS build has moved this prefix before; probing beats guessing."""
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout or TIMEOUT) as client:
        for prefix in _PREFIXES:
            url = f"{BASE}{prefix}{path}"
            try:
                response = await client.request(method, url, json=payload)
            except httpx.HTTPError as exc:
                last = exc
                continue
            if response.status_code == 404 and prefix:
                continue
            if response.status_code >= 400:
                raise _failed(method, path, response)
            return response.json() if response.content else {}
    raise SteelUnavailable(f"steel is unreachable at {BASE} ({last})")


async def _binary(method: str, path: str, payload: dict | None = None) -> bytes:
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for prefix in _PREFIXES:
            try:
                response = await client.request(method, f"{BASE}{prefix}{path}", json=payload)
            except httpx.HTTPError as exc:
                last = exc
                continue
            if response.status_code == 404 and prefix:
                continue
            if response.status_code >= 400:
                raise _failed(method, path, response)
            return response.content
    raise SteelUnavailable(f"steel is unreachable at {BASE} ({last})")


async def health() -> dict:
    return await _call("GET", "/health", timeout=10)


async def scrape(url: str, *, delay: int | None = None, proxy_url: str | None = None) -> dict:
    """Render a page and return {content:{markdown,html}, metadata:{...}, links:[{url,text}]}.

    Verified against steel-browser-api: the only accepted formats are markdown, html,
    readability and cleaned_html. A screenshot is NOT a format here — it is its own
    endpoint, which is why capturing one costs a second page load.
    """
    body: dict[str, Any] = {"url": url, "format": ["markdown", "html"]}
    if delay:
        body["delay"] = delay
    if proxy_url is not None:
        body["proxyUrl"] = proxy_url
    return await _call("POST", "/scrape", body)


async def screenshot(url: str, *, full_page: bool = True, delay: int | None = None) -> bytes:
    """Capture the page as image bytes (JPEG). Separate endpoint, separate page load."""
    body: dict[str, Any] = {"url": url, "fullPage": full_page}
    if delay:
        body["delay"] = delay
    return await _binary("POST", "/screenshot", body)


async def create_session(*, timeout_seconds: int = 900, persist_profile: bool = True, profile_id: str | None = None) -> dict:
    body: dict[str, Any] = {"timeout": timeout_seconds * 1000}
    if persist_profile:
        body["persistProfile"] = True
    if profile_id:
        body["profileId"] = profile_id
    return await _call("POST", "/sessions", body)


async def release_session(session_id: str | None = None) -> dict:
    return await _call("POST", "/sessions/release", {"sessionId": session_id} if session_id else {})


async def sessions() -> Any:
    return await _call("GET", "/sessions")
