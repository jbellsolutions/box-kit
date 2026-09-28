"""The ledger: jobs, the money they may spend, and a record of every call.

Money is integer micro-dollars, rounded up, the way Super Browser's advisor kept it
(src/super_browser/advisor/store.py). A paid step reserves its worst case against the job's
cap BEFORE it runs and settles to the real charge after; a step whose reservation does not fit
never starts. A job that was running when the process died is marked interrupted and its
reservations are charged in full: the provider may have billed, and a guess below the cap
would understate spend.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

TERMINAL = ("succeeded", "failed", "cancelled", "interrupted")


class Conflict(ValueError):
    """The request cannot proceed as asked (a reused request_id, a cap that does not fit)."""


def money(usd: float) -> int:
    if isinstance(usd, bool) or not math.isfinite(float(usd)):
        raise ValueError("invalid money amount")
    return math.ceil(float(usd) * 1_000_000)


def usd(micro: int | None) -> float:
    return round((micro or 0) / 1_000_000, 6)


def args_hash(tool: str, args: dict) -> str:
    material = json.dumps({"tool": tool, "args": {k: v for k, v in args.items() if k not in ("request_id", "wait_seconds")}},
                          sort_keys=True, default=str)
    return hashlib.sha256(material.encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, tool TEXT NOT NULL, request_id TEXT, args TEXT NOT NULL, args_hash TEXT NOT NULL,
              status TEXT NOT NULL, result TEXT, error TEXT,
              budget INTEGER NOT NULL DEFAULT 0, spent INTEGER NOT NULL DEFAULT 0, reserved INTEGER NOT NULL DEFAULT 0,
              created REAL NOT NULL, updated REAL NOT NULL, finished REAL);
            CREATE UNIQUE INDEX IF NOT EXISTS jobs_request ON jobs(request_id) WHERE request_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS jobs_recent ON jobs(created);
            CREATE TABLE IF NOT EXISTS reservations(
              id TEXT PRIMARY KEY, job TEXT NOT NULL, amount INTEGER NOT NULL, charged INTEGER,
              settled INTEGER NOT NULL DEFAULT 0, provider TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS calls(
              id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT NOT NULL, job TEXT, ok INTEGER NOT NULL,
              detail TEXT NOT NULL DEFAULT '', seconds REAL NOT NULL, cost INTEGER NOT NULL DEFAULT 0, at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS calls_at ON calls(at);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    # --- jobs -------------------------------------------------------------------------------

    def create_job(self, tool: str, args: dict, request_id: str | None = None, budget_usd: float = 0) -> tuple[dict, bool]:
        """Returns (job, created). The same request_id with the same arguments returns the first
        job, so a retry after a timeout never runs (or pays for) the work twice."""
        if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 100):
            raise ValueError("request_id must be 1-100 characters")
        budget = money(budget_usd)
        if budget < 0:
            raise ValueError("a cost cap cannot be negative")
        digest = args_hash(tool, args)
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if request_id is not None:
                prior = db.execute("SELECT * FROM jobs WHERE request_id=?", (request_id,)).fetchone()
                if prior:
                    if prior["args_hash"] != digest:
                        raise Conflict(f"request_id {request_id!r} was already used for a different {prior['tool']} call")
                    return self._row(prior), False
            job_id = "job_" + secrets.token_hex(8)
            db.execute(
                "INSERT INTO jobs(id,tool,request_id,args,args_hash,status,budget,created,updated) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, tool, request_id, json.dumps(args, default=str), digest, "queued", budget, now, now))
        return self.job(job_id), True

    def job(self, job_id: str) -> dict:
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(f"no job {job_id!r}")
        return self._row(row)

    def jobs(self, limit: int = 20, status: str | None = None, tool: str | None = None) -> list[dict]:
        query, params = "SELECT * FROM jobs WHERE 1=1", []
        if status:
            query += " AND status=?"
            params.append(status)
        if tool:
            query += " AND tool=?"
            params.append(tool)
        query += " ORDER BY created DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        with self.db() as db:
            return [self._row(r, with_result=False) for r in db.execute(query, params)]

    def set_status(self, job_id: str, status: str, *, result: Any = None, error: str | None = None) -> dict:
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(f"no job {job_id!r}")
            if row["status"] in TERMINAL:
                # First outcome wins: a job cancelled while its work finished stays cancelled.
                return self._finished(db, job_id)
            db.execute(
                "UPDATE jobs SET status=?, result=COALESCE(?,result), error=COALESCE(?,error), updated=?, finished=? WHERE id=?",
                (status, None if result is None else json.dumps(result, default=str, ensure_ascii=False), error, now,
                 now if status in TERMINAL else None, job_id))
            if status in TERMINAL:
                # A finished job holds nothing back: any reservation still open is charged in full.
                self._close_reservations(db, job_id)
        return self.job(job_id)

    def _finished(self, db: sqlite3.Connection, job_id: str) -> dict:
        return self._row(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def recover(self) -> int:
        """At startup: a job still queued or running belonged to a process that died."""
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')").fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET status='interrupted', error=?, updated=?, finished=? WHERE id=?",
                           ("data-box restarted while this job ran; paid steps already taken are charged in full "
                            "and were not replayed", now, now, row["id"]))
                self._close_reservations(db, row["id"])
        return len(rows)

    # --- money ------------------------------------------------------------------------------

    def reserve(self, job_id: str, amount_usd: float, provider: str, detail: str = "") -> str:
        amount = money(amount_usd)
        if amount < 0:
            raise ValueError("negative reservation")
        key = "res_" + secrets.token_hex(8)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE jobs SET reserved=reserved+?, updated=? WHERE id=? AND status IN ('queued','running') "
                "AND spent+reserved+?<=budget", (amount, time.time(), job_id, amount)).rowcount
            if not changed:
                job = db.execute("SELECT status, budget, spent, reserved FROM jobs WHERE id=?", (job_id,)).fetchone()
                if not job:
                    raise KeyError(f"no job {job_id!r}")
                if job["status"] not in ("queued", "running"):
                    raise Conflict(f"job {job_id} is {job['status']}; no further paid step was started")
                raise Conflict(
                    f"{provider} needs up to ${usd(amount):.4f} but this job's cap has ${usd(job['budget'] - job['spent'] - job['reserved']):.4f} "
                    f"left (cap ${usd(job['budget']):.4f}); raise max_cost_usd to allow it")
            db.execute("INSERT INTO reservations(id,job,amount,provider,detail,created) VALUES(?,?,?,?,?,?)",
                       (key, job_id, amount, provider, detail[:200], time.time()))
        return key

    def settle(self, key: str, actual_usd: float | None = None) -> None:
        """Charge the real amount (or the whole reservation when the real one is unknown)."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM reservations WHERE id=?", (key,)).fetchone()
            if not row or row["settled"]:
                return
            amount = row["amount"] if actual_usd is None else money(actual_usd)
            if amount < 0:
                raise ValueError("negative charge")
            db.execute("UPDATE reservations SET settled=1, charged=? WHERE id=?", (amount, key))
            db.execute("UPDATE jobs SET reserved=reserved-?, spent=spent+? WHERE id=?", (row["amount"], amount, row["job"]))

    @staticmethod
    def _close_reservations(db: sqlite3.Connection, job_id: str) -> None:
        for row in db.execute("SELECT * FROM reservations WHERE job=? AND settled=0", (job_id,)).fetchall():
            db.execute("UPDATE reservations SET settled=1, charged=amount WHERE id=?", (row["id"],))
            db.execute("UPDATE jobs SET reserved=reserved-?, spent=spent+? WHERE id=?", (row["amount"], row["amount"], job_id))

    def spend_since(self, since: float) -> float:
        with self.db() as db:
            total = db.execute("SELECT COALESCE(SUM(spent),0) FROM jobs WHERE created>=?", (since,)).fetchone()[0]
        return usd(total)

    # --- calls ------------------------------------------------------------------------------

    def record_call(self, tool: str, ok: bool, seconds: float, detail: str = "", job_id: str | None = None,
                    cost_usd: float = 0) -> None:
        with self.db() as db:
            db.execute("INSERT INTO calls(tool,job,ok,detail,seconds,cost,at) VALUES(?,?,?,?,?,?,?)",
                       (tool, job_id, int(ok), detail[:200], round(seconds, 3), money(cost_usd), time.time()))
            db.execute("DELETE FROM calls WHERE id <= (SELECT MAX(id) FROM calls) - 5000")

    def recent_calls(self, n: int = 10) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT * FROM calls ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [{"tool": r["tool"], "ok": bool(r["ok"]), "seconds": r["seconds"], "detail": r["detail"],
                 "cost_usd": usd(r["cost"]), "job_id": r["job"], "at": r["at"]} for r in rows]

    # --- rows -------------------------------------------------------------------------------

    @staticmethod
    def _row(row: sqlite3.Row, with_result: bool = True) -> dict:
        job = {
            "job_id": row["id"], "tool": row["tool"], "status": row["status"], "request_id": row["request_id"],
            "args": json.loads(row["args"]), "cost_cap_usd": usd(row["budget"]), "spent_usd": usd(row["spent"]),
            "reserved_usd": usd(row["reserved"]), "created": row["created"], "updated": row["updated"],
            "finished": row["finished"],
        }
        if row["error"]:
            job["error"] = row["error"]
        if with_result and row["result"] is not None:
            job["result"] = json.loads(row["result"])
        return job
