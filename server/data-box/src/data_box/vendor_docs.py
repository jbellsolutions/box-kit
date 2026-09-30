"""Vendor documentation, mirrored into each tool's skill so an agent reads the real docs, offline.

Each skill that mirrors docs has references/vendor-docs/ with:
- SOURCES.json    what to fetch: {"tool", "home", "terms_note", "sources": [{"url", "path", "why", "embedded"?}],
                  "not_mirrored"?: [{"url", "why"}]} (pages known to refuse a plain fetch, said once)
- pages/...       what was fetched. Text, markdown and JSON are kept as served; an HTML page is kept as
                  the markdown data-box's own reader makes of it (path ends in .md). A single-page app
                  whose docs ship inside its JavaScript (GetLeads) names the document's first line in
                  "embedded": the page's scripts are read and that markdown string is kept, unchanged
- manifest.json   one entry per page: {path, url, final_url, fetched_at, bytes, sha256, content_type}
- PROVENANCE.md   who fetched what, when and how, and the vendor's terms note

Only free, public sources are fetched, through data-box's pinned fetch (public addresses only, every
redirect checked). A page the free fetch cannot read is left out and reported; mirroring it through a
paid rung is a plan like any other paid call. Each mirror is capped at MAX_BYTES and MAX_PAGES.

    python -m data_box.vendor_docs fetch plugins/data-box/skills/firecrawl
    python -m data_box.vendor_docs validate plugins/data-box/skills/*
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 5_000_000
MAX_PAGES = 400
FETCH_MAX_BYTES = 3_000_000  # one page; Firecrawl's llms-full.txt is 1.8 MB


def docs_dir(skill: Path) -> Path:
    return Path(skill) / "references" / "vendor-docs"


JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def js_string(source: str, marker: str) -> str | None:
    """The JavaScript string literal in `source` that starts with `marker`, decoded; None if absent."""
    for quote in ("'", '"', "`"):
        at = source.find(quote + marker)
        if at < 0:
            continue
        end = at + 1
        while True:
            end = source.find(quote, end)
            if end < 0:
                return None
            slashes = 0
            while source[end - 1 - slashes] == "\\":
                slashes += 1
            if slashes % 2 == 0:
                break
            end += 1

        def unescape(m: re.Match) -> str:
            code = m.group(1)
            if code[0] in "ux" and len(code) > 1:
                return chr(int(code[1:], 16))
            return JS_ESCAPES.get(code, code)
        return re.sub(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", unescape, source[at + 1:end], flags=re.S)
    return None


async def _embedded(http, page, marker: str) -> bytes | None:
    """The markdown document a single-page app ships inside one of its scripts."""
    for src in re.findall(r"<script[^>]+src=\"([^\"]+\.js)\"", page.text()):
        script = urljoin(page.final_url, src)
        if urlsplit(script).hostname != urlsplit(page.final_url).hostname:
            continue  # the site's own bundle, never a tracker's
        bundle = await http.get(script, max_bytes=FETCH_MAX_BYTES)
        found = js_string(bundle.text(), marker) if bundle.status_code < 400 else None
        if found:
            return found.encode()
    return None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(path: str) -> str:
    parts = [p for p in Path(path).parts if p not in ("", ".", "..", "/")]
    if not parts:
        raise ValueError(f"bad page path {path!r}")
    return str(Path(*parts))


async def fetch(skill: Path, now: float | None = None) -> dict[str, Any]:
    """Fetch every source in SOURCES.json into pages/, and rewrite manifest.json and PROVENANCE.md."""
    from . import fetch as http

    folder = docs_dir(skill)
    sources = json.loads((folder / "SOURCES.json").read_text())
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time()))
    entries: list[dict[str, Any]] = []
    missed: list[dict[str, str]] = []
    total = 0
    for source in sources["sources"][:MAX_PAGES]:
        rel = _safe(source["path"])
        try:
            page = await http.get(source["url"], max_bytes=FETCH_MAX_BYTES,
                                  headers={"Accept": "text/plain,text/markdown,application/json,text/html;q=0.8,*/*;q=0.5"})
        except Exception as exc:  # a source that cannot be read is reported, never fatal to the rest
            missed.append({"url": source["url"], "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        if page.status_code >= 400 or page.truncated:
            missed.append({"url": source["url"], "why": f"HTTP {page.status_code}" + (", cut at the size cap" if page.truncated else "")})
            continue
        body = page.body
        if source.get("embedded"):
            body = await _embedded(http, page, source["embedded"])
            if body is None:
                missed.append({"url": source["url"], "why": f"no script on the page carries {source['embedded']!r}"})
                continue
        elif page.is_html:
            reading = http.read(page)
            body = (f"# {reading.title}\n\n" if reading.title else "").encode() + reading.markdown.encode()
            if not rel.endswith(".md"):
                rel += ".md"
        if total + len(body) > MAX_BYTES:
            missed.append({"url": source["url"], "why": f"over the mirror's {MAX_BYTES:,}-byte cap"})
            continue
        target = folder / "pages" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        total += len(body)
        entries.append({"path": f"pages/{rel}", "url": source["url"], "final_url": page.final_url, "fetched_at": stamp,
                        "bytes": len(body), "sha256": _sha(body), "content_type": page.content_type.split(";")[0]})
    kept = {e["path"] for e in entries}
    for old in (folder / "pages").rglob("*") if (folder / "pages").exists() else []:
        if old.is_file() and str(old.relative_to(folder)) not in kept:
            old.unlink()  # a page the vendor dropped is dropped here too
    manifest = {"tool": sources["tool"], "fetched_at": stamp, "pages": entries, "missed": missed}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    (folder / "PROVENANCE.md").write_text(_provenance(sources, manifest))
    return manifest


def _provenance(sources: dict, manifest: dict) -> str:
    lines = [f"# {sources['tool']} vendor docs: provenance", "",
             f"Fetched {manifest['fetched_at']} by `python -m data_box.vendor_docs fetch`, through data-box's pinned "
             "public fetch: plain GETs of free, public pages, no login, no paid rung.", "",
             f"**Vendor:** {sources.get('home', '')}  ",
             f"**Terms:** {sources.get('terms_note') or 'the vendor publishes these pages for developers and AI agents; they are mirrored unchanged except HTML, kept as markdown'}", "",
             "| Page | Source | Bytes | sha256 (first 12) |", "|---|---|---|---|"]
    for e in manifest["pages"]:
        lines.append(f"| `{e['path']}` | {e['url']} | {e['bytes']:,} | `{e['sha256'][:12]}` |")
    skipped = manifest["missed"] + sources.get("not_mirrored", [])
    if skipped:
        lines += ["", "**Not mirrored:**", ""] + [f"- {m['url']}: {m['why']}" for m in skipped]
    lines += ["", "`python -m data_box.vendor_docs validate` rechecks every hash against manifest.json.", ""]
    return "\n".join(lines)


def validate(skill: Path, max_age_days: float | None = None) -> list[str]:
    """What is wrong with a skill's mirror, or [] when it holds. A skill without a mirror is fine."""
    folder = docs_dir(skill)
    if not folder.exists():
        return []
    problems: list[str] = []
    for name in ("SOURCES.json", "manifest.json", "PROVENANCE.md"):
        if not (folder / name).exists():
            problems.append(f"{folder}: no {name}")
    if problems:
        return problems
    manifest = json.loads((folder / "manifest.json").read_text())
    listed = set()
    total = 0
    for entry in manifest.get("pages", []):
        path = folder / entry["path"]
        listed.add(entry["path"])
        if not path.exists():
            problems.append(f"{path}: listed in the manifest but missing")
            continue
        data = path.read_bytes()
        total += len(data)
        if _sha(data) != entry["sha256"]:
            problems.append(f"{path}: changed since it was fetched (sha256 differs from the manifest)")
    for path in (folder / "pages").rglob("*") if (folder / "pages").exists() else []:
        if path.is_file() and str(path.relative_to(folder)) not in listed:
            problems.append(f"{path}: not in the manifest")
    if total > MAX_BYTES:
        problems.append(f"{folder}: {total:,} bytes, over the {MAX_BYTES:,} cap")
    if len(listed) > MAX_PAGES:
        problems.append(f"{folder}: {len(listed)} pages, over the {MAX_PAGES} cap")
    if not manifest.get("fetched_at"):
        problems.append(f"{folder}: the manifest has no fetch date")
    elif max_age_days is not None:
        age = (time.time() - time.mktime(time.strptime(manifest["fetched_at"], "%Y-%m-%dT%H:%M:%SZ"))) / 86400
        if age > max_age_days:
            problems.append(f"{folder}: fetched {age:.0f} days ago; refetch it")
    if manifest.get("fetched_at") and manifest["fetched_at"] not in (folder / "PROVENANCE.md").read_text():
        problems.append(f"{folder}: PROVENANCE.md does not match the manifest's fetch")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m data_box.vendor_docs", description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["fetch", "validate"])
    parser.add_argument("skills", nargs="+", type=Path, help="skill folders, e.g. plugins/data-box/skills/firecrawl")
    args = parser.parse_args(argv)
    failed = 0
    for skill in args.skills:
        if args.action == "fetch":
            if not (docs_dir(skill) / "SOURCES.json").exists():
                continue
            manifest = asyncio.run(fetch(skill))
            size = sum(e["bytes"] for e in manifest["pages"])
            print(f"{skill}: {len(manifest['pages'])} pages, {size:,} bytes; missed {len(manifest['missed'])}")
            for m in manifest["missed"]:
                print(f"  missed {m['url']}: {m['why']}")
            failed += bool(manifest["missed"])
        else:
            problems = validate(skill)
            for p in problems:
                print(p)
            failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
