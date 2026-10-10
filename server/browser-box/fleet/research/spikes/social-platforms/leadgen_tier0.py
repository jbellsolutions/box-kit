#!/usr/bin/env python3
"""Tier-0 of the lead-gen cascade: plain HTTP fetch, no browser, no LLM, no paid service.

For each URL:
  1. robots.txt check for our user agent (skip if disallowed),
  2. one GET with a timeout and a byte cap,
  3. extract public business-contact signals from the HTML:
     schema.org JSON-LD (Organization / LocalBusiness / Person), mailto:, tel:,
     links to the company's own social profiles, and contact/about page links,
  4. decide whether the page needs a browser (escalate to tier 1/2) with cheap heuristics.

Stdlib only. Spikes run against public test pages and a local fixture only (BRIEF.md rules).
Usage: python3 -I leadgen_tier0.py [--expect REGEX] URL [URL ...]
       python3 -I leadgen_tier0.py --fixture FILE
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

UA = "JevFleetLeadBot/0.1 (+contact: ops@example.invalid)"
MAX_BYTES = 2_000_000
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com", "youtube.com")
CONTACT_WORDS = ("contact", "about", "team", "impressum", "kontakt")
EXPECT = ""  # optional regex the extraction goal needs to see in static HTML (--expect)


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.jsonld, self.text_len, self.scripts = [], [], 0, 0
        self._in_ld = False
        self._in_script = False
        self._buf = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        if tag == "script":
            self.scripts += 1
            self._in_script = True
            if (a.get("type") or "").lower() == "application/ld+json":
                self._in_ld, self._buf = True, []
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "script":
            if self._in_ld:
                self.jsonld.append("".join(self._buf))
            self._in_ld = self._in_script = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)
        elif self._in_title:
            self.title += data.strip()
        elif not self._in_script:
            self.text_len += len(data.strip())


def robots_ok(url):
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True, "robots.txt unreadable -> treated as allow"
    return rp.can_fetch(UA, url), "robots.txt checked"


def flatten_ld(raw):
    out = []
    try:
        obj = json.loads(raw)
    except Exception:
        return out
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, list):
            stack.extend(o)
        elif isinstance(o, dict):
            if "@graph" in o:
                stack.extend(o["@graph"] if isinstance(o["@graph"], list) else [o["@graph"]])
            t = o.get("@type")
            t = t if isinstance(t, list) else [t]
            if any(x in ("Organization", "LocalBusiness", "Corporation", "Person", "ProfessionalService") for x in t if x):
                out.append({k: o.get(k) for k in ("@type", "name", "email", "telephone", "url", "sameAs", "address") if o.get(k)})
    return out


def analyse(base, html, status, elapsed, nbytes):
    ex = Extract()
    ex.feed(html)
    absl = [urllib.parse.urljoin(base, h) for h in ex.links]
    mailto = sorted({h[7:].split("?")[0] for h in absl if h.lower().startswith("mailto:")})
    tel = sorted({h[4:] for h in absl if h.lower().startswith("tel:")})
    social = sorted({h for h in absl if any(s in urllib.parse.urlsplit(h).netloc for s in SOCIAL_HOSTS)})
    contact = sorted({h for h in absl if h.startswith("http") and any(w in h.lower() for w in CONTACT_WORDS)})
    orgs = [o for raw in ex.jsonld for o in flatten_ld(raw)]
    # Escalation heuristic: little visible text but many scripts, or an empty SPA root.
    spa_root = bool(re.search(r'<div[^>]+id="(root|app|__next)"[^>]*>\s*</div>', html))
    # v1 heuristic (scripts >= 3) missed quotes.toscrape.com/js/ (2 scripts, 65 chars): see RESULTS.md.
    # v2: any script + thin visible text, or an empty SPA root, or the caller's expected
    # pattern is absent from the static HTML while scripts are present.
    expect_missing = bool(EXPECT) and not re.search(EXPECT, html) and ex.scripts >= 1
    needs_browser = (ex.text_len < 400 and ex.scripts >= 1) or spa_root or expect_missing
    return {
        "url": base, "status": status, "ms": round(elapsed * 1000), "bytes": nbytes, "title": ex.title[:80],
        "visible_text_chars": ex.text_len, "scripts": ex.scripts, "jsonld_entities": orgs,
        "mailto": mailto, "tel": tel, "social_profiles": social[:10], "contact_pages": contact[:10],
        "needs_browser": needs_browser,
    }


def fetch(url):
    ok, why = robots_ok(url)
    if not ok:
        return {"url": url, "skipped": "disallowed by robots.txt"}
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(MAX_BYTES)
            status = r.status
    except Exception as e:
        return {"url": url, "error": str(e)[:200]}
    res = analyse(url, body.decode("utf-8", "ignore"), status, time.time() - t0, len(body))
    res["robots"] = why
    return res


def main(argv):
    global EXPECT
    if argv and argv[0] == "--expect":
        EXPECT, argv = argv[1], argv[2:]
    if argv and argv[0] == "--fixture":
        html = open(argv[1], encoding="utf-8").read()
        print(json.dumps(analyse("https://fixture.invalid/", html, 200, 0.0, len(html)), indent=1))
        return
    for u in argv:
        print(json.dumps(fetch(u)))


if __name__ == "__main__":
    main(sys.argv[1:])
