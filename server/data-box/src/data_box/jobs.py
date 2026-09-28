"""Every call that can take a while runs as a job.

The caller says how long it is willing to wait (wait_seconds, at most 60). A job that finishes
in time comes back inline with its job_id; one that does not comes back as {job_id, status}, and
`job` fetches it later. A request_id makes the call idempotent: a retry after a timeout attaches
to the first job instead of running (and paying for) the work again.

Paid steps go through JobContext.reserve/settle, so a job can never spend past its cap.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from .ledger import TERMINAL, Conflict, Ledger

log = logging.getLogger("data-box")

MAX_WAIT_SECONDS = 60


class JobContext:
    def __init__(self, ledger: Ledger, job_id: str):
        self.ledger = ledger
        self.job_id = job_id

    def reserve(self, usd: float, provider: str, detail: str = "") -> str:
        return self.ledger.reserve(self.job_id, usd, provider, detail)

    def settle(self, key: str, actual_usd: float | None = None) -> None:
        self.ledger.settle(key, actual_usd)


Work = Callable[[JobContext], Awaitable[dict]]


class Runner:
    def __init__(self, ledger: Ledger, expected: tuple[type[BaseException], ...] = ()):
        self.ledger = ledger
        self.expected = expected
        self.tasks: dict[str, asyncio.Task] = {}

    async def start(self, tool: str, args: dict, work: Work, *, cap_usd: float = 0) -> dict:
        request_id = args.get("request_id")
        job, created = self.ledger.create_job(tool, args, request_id, cap_usd)
        if created:
            task = asyncio.create_task(self._run(job["job_id"], tool, work))
            self.tasks[job["job_id"]] = task
        return job

    async def _run(self, job_id: str, tool: str, work: Work) -> None:
        started = time.monotonic()
        self.ledger.set_status(job_id, "running")
        ok, detail = False, ""
        try:
            result = await work(JobContext(self.ledger, job_id))
            if isinstance(result, dict) and "error" in result:
                detail = str(result["error"])[:200]
                self.ledger.set_status(job_id, "failed", result=result, error=detail)
            else:
                ok = True
                detail = (result or {}).pop("_detail", "") if isinstance(result, dict) else ""
                self.ledger.set_status(job_id, "succeeded", result=result)
        except asyncio.CancelledError:
            self.ledger.set_status(job_id, "cancelled", error="cancelled by the caller")
            detail = "cancelled"
            raise
        except (Conflict, *self.expected) as exc:
            detail = str(exc)
            self.ledger.set_status(job_id, "failed", error=detail)
        except Exception as exc:  # a named failure the caller can act on, never a stack trace
            log.exception("job %s (%s) failed", job_id, tool)
            detail = f"{type(exc).__name__}: {exc}"[:400]
            self.ledger.set_status(job_id, "failed", error=detail)
        finally:
            self.tasks.pop(job_id, None)
            job = self.ledger.job(job_id)
            self.ledger.record_call(tool, ok, time.monotonic() - started, detail, job_id, job["spent_usd"])

    async def wait(self, job_id: str, seconds: float) -> dict:
        task = self.tasks.get(job_id)
        seconds = max(0.0, min(float(seconds), MAX_WAIT_SECONDS))
        if task is not None and seconds:
            await asyncio.wait({task}, timeout=seconds)
        return self.ledger.job(job_id)

    async def cancel(self, job_id: str) -> dict:
        job = self.ledger.job(job_id)
        if job["status"] in TERMINAL:
            return job
        task = self.tasks.get(job_id)
        if task is None:
            # Queued or running in a process that no longer has it: nothing to stop, just close it.
            return self.ledger.set_status(job_id, "cancelled", error="cancelled by the caller")
        task.cancel()
        await asyncio.wait({task}, timeout=10)
        return self.ledger.job(job_id)

    async def shutdown(self) -> None:
        for task in list(self.tasks.values()):
            task.cancel()
        if self.tasks:
            await asyncio.wait(set(self.tasks.values()), timeout=10)


def answer(job: dict) -> dict[str, Any]:
    """What a long-running tool returns: the result inline when the job finished, else a handle."""
    handle = {"job_id": job["job_id"], "status": job["status"], "cost_usd": job["spent_usd"]}
    if job["status"] == "succeeded":
        return {**(job.get("result") or {}), **handle}
    if job["status"] in TERMINAL:
        body = {"error": job.get("error") or f"job {job['status']}", "tool": job["tool"], **handle}
        if isinstance(job.get("result"), dict):
            body = {**job["result"], **body}
        return body
    return {**handle, "hint": f"still running: call job with action=get, job_id={job['job_id']} (wait_seconds up to 60)"}
