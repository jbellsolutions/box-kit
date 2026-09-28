"""Rung 0 of the scrape ladder: a direct HTTP GET that cannot be talked into the private network.

Three guards, each learned the hard way in Super Browser and browser-box:
- the URL as written must be public, and EVERY address its host resolves to must be public;
- the connection goes to the address that was checked (pinned, with SNI and Host set to the real
  name), so DNS cannot answer differently between the check and the connect;
- redirects are followed by hand and every hop is checked the same way before it is fetched.
httpx's own follow_redirects checks nothing: by the time response.history shows an internal hop,
the request to it has already been made.

Then a code-only judgement of whether the page is the real page or a block, a challenge or an
empty JavaScript shell, so the ladder knows when to climb.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from . import config
from .security import UnsafeUrl, require_public_addresses, require_public_web

MAX_HOPS = 5
STANDARD_PORTS = {None, 80, 443}


@dataclass
class Page:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    truncated: bool = False
    hops: list[str] = field(default_factory=list)

    def text(self) -> str:
        charset = "utf-8"
        match = re.search(r"charset=([\w-]+)", self.content_type, re.I)
        if match:
            charset = match.group(1)
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower() or self.body[:200].lstrip().lower().startswith((b"<!doctype html", b"<html"))


async def cleared(url: str) -> tuple[str, list[str]]:
    """The URL, validated and public, plus the public addresses its host resolves to."""
    target = require_public_web(url)
    parsed = urlparse(target)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("url port must be a valid integer") from exc
    if port not in STANDARD_PORTS:
        raise UnsafeUrl(f"refused: {target} uses port {port}; data-box fetches only ports 80 and 443")
    addresses = await asyncio.to_thread(require_public_addresses, parsed.hostname)
    return target, addresses


async def get(url: str, *, timeout: float | None = None, max_bytes: int | None = None,
              headers: dict[str, str] | None = None) -> Page:
    """GET a public URL, pinned to its checked address, following redirects by hand."""
    timeout = timeout or config.fetch_timeout()
    max_bytes = max_bytes or config.fetch_max_bytes()
    request_headers = {"User-Agent": config.user_agent(), "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                       "Accept-Language": "en-US,en;q=0.8", **(headers or {})}
    original = url
    hops: list[str] = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_HOPS + 1):
            try:
                target, addresses = await cleared(url)
            except (UnsafeUrl, ValueError) as exc:
                if hops:
                    raise UnsafeUrl(f"refused: {original} redirected to {url} — {exc}") from None
                raise
            parsed = urlparse(target)
            extensions = {"sni_hostname": parsed.hostname} if parsed.scheme == "https" else {}
            last_error: Exception | None = None
            for address in connect_order(addresses):
                pinned = httpx.URL(target).copy_with(host=address)
                try:
                    async with client.stream("GET", pinned, headers={**request_headers, "Host": parsed.netloc},
                                             extensions=extensions) as response:
                        location = response.headers.get("location")
                        if 300 <= response.status_code < 400 and location:
                            hops.append(target)
                            url = urljoin(target, location)
                            break
                        body = bytearray()
                        truncated = False
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                del body[max_bytes:]
                                truncated = True
                                break
                        return Page(url=original, final_url=target, status_code=response.status_code,
                                    content_type=response.headers.get("content-type", ""), body=bytes(body),
                                    truncated=truncated, hops=hops)
                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                    # This address did not answer (an AAAA record on a host with no IPv6 route is the
                    # usual case): try the next checked address, never an unchecked one.
                    last_error = exc
                    continue
            else:
                raise ConnectionError(f"could not connect to {parsed.hostname} on any of its addresses "
                                      f"({', '.join(addresses)}): {last_error}")
    raise UnsafeUrl(f"refused: {original} redirected more than {MAX_HOPS} times")


def connect_order(addresses: list[str]) -> list[str]:
    """IPv4 first. A resolver answers AAAA whether or not this host can route IPv6 (DigitalOcean
    droplets cannot by default), and the guard's sorted list would otherwise put 2600:… before 54.…"""
    return [a for a in addresses if ":" not in a] + [a for a in addresses if ":" in a]


# --- reading the page ------------------------------------------------------------------------

HIDDEN = {"script", "style", "noscript", "template", "svg", "head"}
BLOCK = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside", "table", "tr", "ul", "ol",
         "blockquote", "pre", "form", "figure", "br", "hr", "dl", "dt", "dd"}


class _Reader(HTMLParser):
    """One pass over the HTML: title, meta description, links, and the visible text as both plain
    text and rough markdown (headings, list items, links). Good enough for rung 0; the paid rungs
    return their own, better markdown."""

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.hidden = 0
        self.in_title = False
        self.title = ""
        self.description = ""
        self.text: list[str] = []
        self.md: list[str] = []
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []
        self.scripts = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if tag == "script":
            self.scripts += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attr.get("name", "").lower() in ("description", "og:description") and not self.description:
            self.description = attr.get("content", "").strip()
        if tag in HIDDEN and tag != "head":
            self.hidden += 1
            return
        if self.hidden:
            return
        if tag in BLOCK:
            self._newline()
        if re.fullmatch(r"h[1-6]", tag):
            self._newline()
            self.md.append("#" * int(tag[1]) + " ")
        elif tag == "li":
            self._newline()
            self.md.append("- ")
        elif tag == "a":
            href = attr.get("href", "").strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                self._href = urljoin(self.base, href)
                self._anchor = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in HIDDEN and tag != "head":
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == "a" and self._href:
            label = " ".join(" ".join(self._anchor).split())
            if label:
                self.links.append({"url": self._href, "text": label[:200]})
                self.md.append(f"]({self._href})")
            self._href = None
        if tag in BLOCK or re.fullmatch(r"h[1-6]", tag) or tag == "li":
            self._newline()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
            return
        if self.hidden:
            return
        chunk = " ".join(data.split())
        if not chunk:
            return
        self.text.append(chunk)
        if self._href is not None:
            if not self._anchor:
                self.md.append("[")
            self._anchor.append(chunk)
        self.md.append(chunk + " ")

    def _newline(self) -> None:
        if self.text and self.text[-1] != "\n":
            self.text.append("\n")
        if self.md and self.md[-1] != "\n":
            self.md.append("\n")


def _join(parts: list[str]) -> str:
    lines, current = [], []
    for part in parts:
        if part == "\n":
            if current:
                lines.append("".join(current).strip() if current else "")
                current = []
        else:
            current.append(part if part.endswith(" ") or part.startswith("]") else part + " ")
    if current:
        lines.append("".join(current).strip())
    cleaned = [re.sub(r" +", " ", re.sub(r"\[ ", "[", re.sub(r" \]\(", "](", line))).strip() for line in lines]
    return "\n".join(line for line in cleaned if line)


@dataclass
class Reading:
    title: str
    description: str
    text: str
    markdown: str
    links: list[dict[str, str]]
    scripts: int


def read(page: Page) -> Reading:
    raw = page.text()
    if not page.is_html:
        return Reading(title="", description="", text=raw, markdown=raw, links=[], scripts=0)
    reader = _Reader(page.final_url)
    reader.feed(raw)
    reader.close()
    seen: set[str] = set()
    links = []
    for link in reader.links:
        if link["url"] not in seen:
            seen.add(link["url"])
            links.append(link)
    return Reading(title=" ".join(reader.title.split()), description=reader.description,
                   text=_join(reader.text), markdown=_join(reader.md), links=links, scripts=reader.scripts)


# --- is this the real page? --------------------------------------------------------------------

BLOCK_STATUSES = {401: "the site wants a login (401)", 403: "the site refused this client (403)",
                  407: "a proxy wants credentials (407)", 429: "rate limited (429)",
                  451: "unavailable for legal reasons (451)", 503: "the site is refusing or overloaded (503)"}
CHALLENGE_MARKERS = (
    ("challenge-platform", "a Cloudflare challenge page"), ("cf-browser-verification", "a Cloudflare challenge page"),
    ("just a moment...", "a Cloudflare challenge page"), ("attention required! | cloudflare", "a Cloudflare block page"),
    ("px-captcha", "a PerimeterX captcha"), ("captcha-delivery.com", "a DataDome challenge"),
    ("_incapsula_resource", "an Imperva challenge"), ("are you a robot", "a bot check"),
    ("verify you are human", "a bot check"), ("unusual traffic from your computer network", "a Google bot check"),
    ("enable javascript and cookies to continue", "a JavaScript/cookie wall"),
)
THIN_TEXT_CHARS = 200  # below this, a page that looks like a JS app shell needs a browser


def judge(page: Page, reading: Reading) -> dict[str, Any] | None:
    """None when this looks like the real page; otherwise why it does not, and whether a better rung
    (a real browser, an unblocker) would likely help. Code only: cheap, and wrong only on odd pages."""
    if page.status_code in BLOCK_STATUSES:
        return {"reason": BLOCK_STATUSES[page.status_code], "kind": "blocked"}
    if page.status_code in (404, 410):
        return None  # the real answer: the page does not exist, and no unblocker changes that
    if page.status_code >= 400:
        return {"reason": f"HTTP {page.status_code}", "kind": "http_error"}
    head = page.body[:60_000].decode("utf-8", errors="ignore").lower()
    for marker, what in CHALLENGE_MARKERS:
        if marker in head and len(reading.text) < 3000:
            return {"reason": f"this is {what}, not the page", "kind": "challenge"}
    # A short page is still the real page (example.com is 127 characters). Only an almost-empty
    # page that is clearly a JavaScript app shell is worth a browser.
    if page.is_html and len(reading.text) < THIN_TEXT_CHARS and (
            reading.scripts >= 3 or any(m in head for m in ('id="root"', 'id="__next"', 'id="app"', "ng-app"))):
        return {"reason": "almost no text: the page is built by JavaScript", "kind": "needs_javascript"}
    return None
