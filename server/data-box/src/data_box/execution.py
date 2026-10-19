"""Step 4: run an approved plan, and nothing else.

`execute` only ever runs a plan the caller approved, for at most the amount approved, as one job:

- Lanes run in the plan's order (the base layer first). Within a lane, cells (query x place) run in
  parallel, at most DATABOX_EXECUTE_CONCURRENCY at a time; a cell's pages run in order and stop at
  the first short or empty page, because the source has nothing more there.
- No new call starts once the deduped list reaches the requested count: the oversample in the plan
  covers dedupe collapse, it is not a quota to spend.
- Every call is reserved in the ledger at its listed price before it is sent and settled to what
  Firecrawl says it cost: nothing for a refusal, in full when the outcome is unknown. The job's cap
  is the approved amount minus what the plan already spent, so resumes share one budget.
- The Firecrawl balance is read before the first call and every 15 calls after, and tracked call by
  call in between (calls in flight included): no call starts that could take the balance below
  DATABOX_FIRECRAWL_BALANCE_FLOOR (0), so a run can never drive the account negative.
- A cell stops paging when a page brings less than DATABOX_MIN_NEW_RATIO (30%) new unique records:
  deep pages re-fetch the same chains. This, and the page caps in the plan, are the guards against
  the 2026-09-28 Hermes pull that paged Bing 8 deep x 4 queries a metro and spent ~8,000 credits for
  a list quoted at ~1,300.
- Every record lands in the plan's raw.jsonl tagged lane|geo|query|page, and each page is marked done
  once written, so running execute again resumes where it stopped and never pays for a page twice.
- records.jsonl is the deduped list, merged across lanes on normalised name+phone and name+address.
  It stays on the box (the job result carries counts, not rows) and is deleted after the retention
  period; `job results` and `job export` read it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import config, planning
from .jobs import JobContext
from .ledger import Conflict, Ledger
from .providers import firecrawl as fc_mod
from .providers.firecrawl import Firecrawl, FirecrawlError, OutOfCredits, TermsRequired

BALANCE_EVERY = 15
LANE_ERROR_LIMIT = 3
NAME_SUFFIXES = re.compile(r"\b(llc|l\.l\.c|inc|incorporated|co|corp|corporation|company|ltd|limited|the|pllc|lp)\b")
OUTPUT_FIELDS = ("name", "phone", "email", "website", "address", "city", "state", "category", "rating")


# --- normalising and deduping ------------------------------------------------------------------

def _text(value: Any, join: bool = False) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, list):
        parts = [_text(v) for v in value]
        parts = [p for p in parts if p]
        return (", ".join(parts) if join else parts[0]) if parts else None
    if isinstance(value, dict):
        for key in ("display", "number", "value", "formatted", "full", "text", "name", "url"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        parts = [str(v) for v in value.values() if isinstance(v, (str, int, float)) and v != ""]
        return ", ".join(parts) or None
    return str(value).strip() or None


def normalize(record: dict) -> dict[str, str | None]:
    keyed = {planning.field_key(k): v for k, v in record.items() if not k.startswith("_")}
    out: dict[str, str | None] = {}
    for name in OUTPUT_FIELDS:
        value = None
        for key in planning.FIELD_SYNONYMS[name]:
            value = _text(keyed.get(planning.field_key(key)), join=name == "address")
            if value:
                break
        out[name] = value
    return out


def _norm_name(name: str | None) -> str:
    text = NAME_SUFFIXES.sub(" ", re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower().replace("&", " and ")))
    return " ".join(text.split())


def _norm_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else ""


def _norm_address(address: str | None) -> str:
    tokens = re.sub(r"[^a-z0-9 ]+", " ", (address or "").lower()).split()
    return " ".join(tokens[:3])


def _domain(website: str | None) -> str:
    if not website:
        return ""
    host = urlparse(website if "://" in website else f"http://{website}").hostname or ""
    return host.removeprefix("www.")


def dedupe_keys(row: dict[str, str | None], raw: dict) -> list[str]:
    name = _norm_name(row.get("name"))
    keys = []
    if name:
        for prefix, value in (("np", _norm_phone(row.get("phone"))), ("na", _norm_address(row.get("address"))),
                              ("nw", _domain(row.get("website")))):
            if value:
                keys.append(f"{prefix}:{name}|{value}")
    if not keys:
        material = json.dumps({k: v for k, v in raw.items() if not k.startswith("_")}, sort_keys=True, default=str)
        keys.append("raw:" + hashlib.sha256(material.encode()).hexdigest()[:16])
    return keys


class Merger:
    """The deduped list: one row per real-world entity, filled in from every lane that found it."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.index: dict[str, int] = {}
        self.raw = 0

    def add(self, record: dict) -> None:
        self.raw += 1
        row = normalize(record)
        keys = dedupe_keys(row, record)
        at = next((self.index[k] for k in keys if k in self.index), None)
        lane = record.get("_lane")
        if at is None:
            at = len(self.rows)
            self.rows.append({**row, "sources": [lane] if lane else [], "raw": {k: v for k, v in record.items()
                                                                             if not k.startswith("_")}})
        else:
            merged = self.rows[at]
            for name, value in row.items():
                if value and not merged.get(name):
                    merged[name] = value
            if lane and lane not in merged["sources"]:
                merged["sources"].append(lane)
        for k in keys:
            self.index.setdefault(k, at)

    @property
    def unique(self) -> int:
        return len(self.rows)

    def write(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as out:
            for row in self.rows:
                out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        tmp.replace(path)


# --- the run ---------------------------------------------------------------------------------

@dataclass
class Run:
    ctx: JobContext
    fc: Firecrawl
    rate: float
    stop: str | None = None
    calls: int = 0
    credits: float = 0.0
    lanes: dict[str, dict] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    headroom: float | None = None  # credits above the floor, as last read, minus what was spent since
    in_flight: float = 0.0

    async def check_balance(self, need: float, force: bool = False) -> None:
        if not force and self.calls % BALANCE_EVERY:
            return
        async with self.lock:
            try:
                remaining = (await self.fc.credits()).get("remaining")
            except FirecrawlError:
                return  # the balance is a guard, not the meter; the ledger cap still binds
            if remaining is None:
                return
            # The balance read already reflects finished calls; calls still in flight are held apart.
            self.headroom = float(remaining) - config.firecrawl_balance_floor()
            if self.headroom - self.in_flight < need:
                self.stop = self.stop or (f"the Firecrawl balance ({remaining} credits) cannot cover the next call; "
                                          "add credits and run execute again to resume")

    async def claim(self, credits: float) -> bool:
        """Hold a call's credits against the balance before it is sent; False (and stop) if they do not fit."""
        async with self.lock:
            if self.stop:
                return False
            if self.headroom is not None and self.headroom - self.in_flight < credits:
                self.stop = (f"the next call would take the Firecrawl balance below "
                             f"{config.firecrawl_balance_floor():g} credits; add credits and run execute again to resume")
                return False
            self.in_flight += credits
            return True

    async def paid(self, provider_label: str, credits: float, detail: str, call) -> Any:
        """Reserve credits x rate, make the call, settle to what it cost. Returns the call's result,
        or None when it was refused, failed or the budget is spent (self.stop says which)."""
        if not await self.claim(credits):
            return None
        try:
            key = self.ctx.reserve(credits * self.rate, "firecrawl", detail)
        except Conflict as exc:
            self.in_flight -= credits
            self.stop = self.stop or f"the approved budget is spent: {exc}"
            return None
        charged = credits
        try:
            out = await call()
            charged = float(out.get("credits", credits)) if isinstance(out, dict) else credits
            return out
        except OutOfCredits as exc:
            charged = 0.0
            self.stop = self.stop or f"{exc}; add credits and run execute again to resume"
        except (FirecrawlError, ValueError) as exc:
            status = getattr(exc, "status", 400)
            charged = 0.0 if isinstance(exc, ValueError) or 400 <= status < 500 else credits
            lane = self.lanes.setdefault(provider_label, {"lane": provider_label, "calls": 0, "records": 0, "credits": 0.0, "errors": []})
            lane["errors"].append(str(exc)[:200])
            if isinstance(exc, TermsRequired):
                lane["terms_required"] = True
        finally:
            self.ctx.settle(key, charged * self.rate)
            self.in_flight -= credits
            if self.headroom is not None:
                self.headroom -= charged
            self.calls += 1
            self.credits += charged
            lane = self.lanes.setdefault(provider_label, {"lane": provider_label, "calls": 0, "records": 0, "credits": 0.0, "errors": []})
            lane["calls"] += 1
            lane["credits"] += charged
        return None


async def run(plan: dict, ctx: JobContext, fc: Firecrawl, ledger: Ledger, drop_lanes: list[str] | None = None) -> dict:
    """The execute job's work. Always hands the plan back: done when it finished, approved otherwise
    (so execute can resume it), whatever happened, including a cancel."""
    plan_id = plan["plan_id"]
    ledger.attach_job(plan_id, ctx.job_id)
    after = "approved"
    try:
        state = Run(ctx, fc, config.firecrawl_usd_per_credit())
        body = plan["body"]
        if plan["kind"] == "pull":
            result = await _pull(plan_id, body, state, set(drop_lanes or []))
        else:
            result = await _plain(plan_id, body, state)
        if result.get("complete"):
            after = "done"
        return result
    finally:
        ledger.set_plan_status(plan_id, after)


async def _pull(plan_id: str, body: dict, state: Run, drop: set[str]) -> dict:
    it = body["step_1_intake"]
    game = body["step_3_game_plan"]
    store = planning.store_for(plan_id)
    contracts = planning.load_contracts(store)
    target = it["count"]
    entity = it["entity"]
    lanes = [lane for lane in game["lanes"] if lane["lane"] not in drop]
    names = {lane["lane"] for lane in lanes}
    done = planning.done_keys(store)
    merger = Merger()
    off_target = 0
    for record in planning.read_records(store, "raw.jsonl"):
        # Preflight records of lanes the plan dropped, or the user struck, do not count.
        if record.get("_lane") not in names:
            continue
        if planning.looks_like(entity, record):
            merger.add(record)
        else:
            off_target += 1
    gate = asyncio.Semaphore(config.execute_concurrency())
    nonlocal_off = [0]
    top_price = max((lane["credits_per_call"] for lane in lanes), default=0)
    await state.check_balance(top_price, force=True)
    exhausted = True  # every planned page ran or its cell ran dry

    for lane in lanes:
        report = state.lanes.setdefault(lane["lane"], {"lane": lane["lane"], "calls": 0, "records": 0, "credits": 0.0, "errors": []})
        contract = contracts.get(lane["lane"])
        if contract is None:
            report["errors"].append("this lane's contract was not saved with the plan; make a new plan")
            exhausted = False
            continue
        if state.stop or merger.unique >= target:
            exhausted = exhausted and merger.unique >= target
            break

        async def run_cell(cell: dict, lane=lane, contract=contract, report=report) -> bool:
            """True when the cell ran to its end (all pages or a short page); False when it stopped early."""
            finished = planning.key_for(lane["lane"], cell, "end")
            if finished in done:
                return True  # an earlier run stopped this cell because its pages repeated
            for page in range(1, lane["pages_per_cell"] + 1):
                key = planning.key_for(lane["lane"], cell, page)
                if key in done:
                    if done[key] < lane["page_size"]:
                        return True
                    continue
                if state.stop or merger.unique >= target or len(report["errors"]) >= LANE_ERROR_LIMIT:
                    return False
                async with gate:
                    if state.stop or merger.unique >= target:
                        return False
                    out = await state.paid(lane["lane"], lane["credits_per_call"], key,
                                           lambda: state.fc.run_tool(contract, planning.lane_options(lane, cell, page)))
                await state.check_balance(top_price)
                if out is None:
                    return False
                records = [planning.tag(r, lane["lane"], cell, page) for r in out["records"]]
                planning.write_records(store, records, "raw.jsonl")
                planning.mark_done(store, key, len(records))
                done[key] = len(records)
                report["records"] += len(records)
                before = merger.unique
                for record in records:
                    if planning.looks_like(entity, record):
                        merger.add(record)
                    else:
                        nonlocal_off[0] += 1
                if len(records) < lane["page_size"]:
                    return True
                if page >= 2 and records and (merger.unique - before) / len(records) < config.min_new_ratio():
                    # Mostly records this run already has: the next pages would repeat them too. Marked,
                    # so a resumed run does not come back and buy them.
                    report["cells_stopped_repeating"] = report.get("cells_stopped_repeating", 0) + 1
                    planning.mark_done(store, finished, 0)
                    done[finished] = 0
                    return True
            return True

        finished = await asyncio.gather(*(run_cell(cell) for cell in lane["cells"]))
        exhausted = exhausted and all(finished)
        if len(report["errors"]) >= LANE_ERROR_LIMIT:
            report["stopped"] = f"{LANE_ERROR_LIMIT} failed calls; the rest of this lane was skipped"

    merger.write(store / "records.jsonl")
    off_target += nonlocal_off[0]
    reached = merger.unique >= target
    complete = state.stop is None and (reached or exhausted)
    bought = sum(lane["records"] for lane in state.lanes.values())
    note = ("reached the requested count" if reached else
            f"the lanes ran out at {merger.unique} of {target}" if complete else
            state.stop or "some calls failed; run execute again to retry them (done pages are not paid for twice)")
    result = {
        "plan_id": plan_id, "kind": "pull", "complete": complete, "target": target,
        "unique_records": merger.unique, "raw_records": merger.raw + off_target, "off_target": off_target,
        "found_by_2_or_more_lanes": sum(1 for row in merger.rows if len(row["sources"]) > 1), "note": note,
        "lanes": list(state.lanes.values()), "calls": state.calls, "credits": round(state.credits, 2),
        "records_file": f"plans/{plan_id}/records.jsonl", "sample": [_sample(r) for r in merger.rows[:3]],
        "_detail": f"{merger.unique}/{target} unique, {state.calls} calls",
    }
    if not complete and not bought:
        result["error"] = note  # a run that bought nothing did not succeed, whatever the reason
    return result


def _sample(row: dict) -> dict:
    return {k: row.get(k) for k in ("name", "city", "state", "category", "sources")}


async def _plain(plan_id: str, body: dict, state: Run) -> dict:
    it = body["step_1_intake"]
    lanes = body["step_3_game_plan"]["lanes"]
    if not lanes:
        return {"error": "this plan has no runnable lane; make a new plan"}
    lane = lanes[0]
    store = planning.store_for(plan_id)
    done = planning.done_keys(store)
    kind = it["kind"]
    await state.check_balance(1, force=True)
    if state.stop:
        return {"plan_id": plan_id, "kind": kind, "complete": False, "note": state.stop, "error": state.stop}
    items: list[dict] = []
    extra: dict[str, Any] = {}
    if kind == "search":
        per_query = fc_mod.search_credits(lane["limit"], len(lane["sources"]))
        for query in lane["queries"]:
            key = f"search|{query}"
            if key in done or state.stop:
                continue
            out = await state.paid(lane["lane"], per_query, key, lambda q=query: state.fc.search(
                q, sources=lane["sources"], limit=lane["limit"]))
            if out is not None:
                rows = [{**r, "_query": query} for r in out["records"]]
                planning.write_records(store, rows, "records.jsonl")
                planning.mark_done(store, key, len(rows))
    elif kind == "scrape":
        key = f"scrape|{lane['url']}"
        if key not in done:
            out = await state.paid(lane["lane"], lane["credits"], key,
                                   lambda: state.fc.scrape(lane["url"], formats=lane["formats"]))
            if out is not None:
                doc = out["document"]
                metadata = doc.get("metadata") or {}
                content = doc.get("markdown") or doc.get("html") or ""
                limit = config.text_limit()
                extra = {"url": lane["url"], "final_url": metadata.get("url") or metadata.get("sourceURL"),
                         "status_code": metadata.get("statusCode"), "title": metadata.get("title"), "rung": 1,
                         "content": content[:limit] + ("…" if len(content) > limit else ""),
                         "content_chars": len(content), "content_truncated": len(content) > limit}
                if doc.get("json") is not None:
                    extra["json"] = doc["json"]
                if doc.get("links"):
                    extra["links"] = doc["links"][:500]
                planning.write_records(store, [{"url": lane["url"], **{k: v for k, v in doc.items() if k != "rawHtml"}}],
                                       "records.jsonl")
                planning.mark_done(store, key, 1)
    elif kind == "crawl":
        key = f"crawl|{lane['url']}"
        if key not in done:
            out = await state.paid(lane["lane"], lane["credits"], key,
                                   lambda: state.fc.crawl(lane["url"], limit=lane["limit"]))
            if out is not None:
                rows = [{"url": (d.get("metadata") or {}).get("sourceURL") or (d.get("metadata") or {}).get("url"),
                         "title": (d.get("metadata") or {}).get("title"), "markdown": d.get("markdown")}
                        for d in out["records"]]
                planning.write_records(store, rows, "records.jsonl")
                planning.mark_done(store, key, len(rows))
    else:
        per_url = fc_mod.scrape_credits([lane["format"]])
        for url in lane["urls"]:
            key = f"extract|{url}"
            if key in done or state.stop:
                continue
            out = await state.paid(lane["lane"], per_url, key,
                                   lambda u=url: state.fc.scrape(u, formats=[lane["format"]]))
            if out is not None:
                planning.write_records(store, [{"url": url, "data": out["document"].get("json")}], "records.jsonl")
                planning.mark_done(store, key, 1)
    items = planning.read_records(store, "records.jsonl")
    report = state.lanes.get(lane["lane"], {"errors": []})
    planned = {"search": len(lane.get("queries") or []), "extract": len(lane.get("urls") or [])}.get(kind, 1)
    complete = state.stop is None and len(planning.done_keys(store)) >= planned
    note = "done" if complete else state.stop or "; ".join(report.get("errors") or []) or "not finished; run execute again"
    result = {"plan_id": plan_id, "kind": kind, "complete": complete, "note": note, "records": len(items),
              "calls": state.calls, "credits": round(state.credits, 2), "lanes": list(state.lanes.values()),
              "records_file": f"plans/{plan_id}/records.jsonl", **extra,
              "_detail": f"{kind}: {len(items)} records, {state.calls} calls"}
    if not complete and not items:
        result["error"] = note
    return result


def records_for(plan_id: str) -> list[dict]:
    """A plan's deduped records (empty once the retention period has deleted them)."""
    return planning.read_records(config.plans_dir() / plan_id, "records.jsonl")
