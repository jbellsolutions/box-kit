#!/usr/bin/env python3
"""Build, activate and verify one data-box release on the droplet; put the last one back on failure.

    sudo python3 deploy/data-box/activate_release.py <revision>

Standard library only, so it runs on the host's own python3 before any release (or venv) exists.

1. Refuse a revision that is not reachable from origin/master (production once ran a branch that
   had never been pushed; nobody could say what was deployed).
2. Build /opt/data-box/releases/<rev>: `git archive` of that commit, its own venv, `.[databox]`.
3. Wait for running jobs to finish, point /opt/data-box/current at the release, install its unit
   file, restart data-box.
4. Verify: /health shows the revision; /mcp/ and /api/v1/status refuse a missing token;
   /openapi.json equals the committed docs/openapi.json; an authenticated status answers.
5. On any failure, restore the previous release and verify it; on a first activation (no previous
   release) stop the service instead of leaving a half-working box.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(os.getenv("DATABOX_BASE", "/opt/data-box"))
SOURCE = BASE / "source"
RELEASES = BASE / "releases"
ENV_FILE = Path(os.getenv("DATABOX_ENV_FILE", "/etc/data-box.env"))
UNIT_PATH = Path("/etc/systemd/system/data-box.service")
SERVICE = "data-box"
SOURCE_BRANCH = "origin/master"
KEEP_RELEASES = 3
DRAIN_SECONDS = 180
HEALTH_SECONDS = 60


def parse_env(text: str) -> dict[str, str]:
    """KEY=VALUE lines, as systemd's EnvironmentFile reads them (comments and blanks skipped)."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), check=True, text=True, **kwargs)


def git(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return run("git", "-C", str(SOURCE), *args, **kwargs)


def require_merged(revision: str) -> str:
    """The full commit id for `revision`, or an error if it is not on origin/master."""
    git("fetch", "--quiet", "origin", timeout=120)
    resolved = subprocess.run(["git", "-C", str(SOURCE), "rev-parse", "--verify", "--quiet", revision + "^{commit}"],
                              capture_output=True, text=True, timeout=30)
    if resolved.returncode != 0:
        raise RuntimeError(f"{revision} is not a commit the source checkout knows; push it first")
    commit = resolved.stdout.strip()
    if os.getenv("DATABOX_RELEASE_GUARD_OVERRIDE") == revision:
        print(json.dumps({"warning": "release guard overridden by operator", "revision": revision}))
        return commit
    merged = subprocess.run(["git", "-C", str(SOURCE), "merge-base", "--is-ancestor", commit, SOURCE_BRANCH], timeout=30)
    if merged.returncode != 0:
        raise RuntimeError(f"{revision} is not reachable from {SOURCE_BRANCH}; merge it before deploying")
    return commit


def build(commit: str) -> Path:
    """The release directory for `commit`. Built in place (a venv remembers where it was made);
    release.json is written last, so a directory without it is an unfinished build and is redone."""
    short = commit[:7]
    target = RELEASES / short
    if (target / "release.json").exists() and (target / ".venv/bin/python").exists():
        return target
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    archive = subprocess.Popen(["git", "-C", str(SOURCE), "archive", "--format=tar", commit], stdout=subprocess.PIPE)
    run("tar", "-x", "-C", str(target), stdin=archive.stdout, timeout=120)
    if archive.wait(timeout=30) != 0:
        raise RuntimeError("git archive failed")
    python = target / ".venv/bin/python"
    run(sys.executable, "-m", "venv", str(target / ".venv"), timeout=120)
    run(str(python), "-m", "pip", "install", "--quiet", "--no-cache-dir", "--upgrade", "pip", timeout=300)
    run(str(python), "-m", "pip", "install", "--quiet", "--no-cache-dir", f"{target}[databox]", timeout=600)
    run(str(python), "-c", "import data_box.server, data_box.cli", timeout=60, stdout=subprocess.DEVNULL)
    frozen = run(str(python), "-m", "pip", "freeze", capture_output=True, timeout=60).stdout
    (target / "requirements.frozen.txt").write_text(frozen)
    (target / "release.env").write_text(f"DATABOX_REVISION={short}\n")
    (target / "release.json").write_text(json.dumps({"revision": short, "commit": commit, "built_at": time.time()}) + "\n")
    return target


def active_jobs(state_dir: Path) -> int:
    database = state_dir / "data-box.sqlite"
    if not database.exists():
        return 0
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=10)
    try:
        return db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
    finally:
        db.close()


def drain(state_dir: Path) -> None:
    deadline = time.monotonic() + DRAIN_SECONDS
    while active_jobs(state_dir):
        if time.monotonic() > deadline:
            raise RuntimeError("jobs are still running; the release was not activated")
        time.sleep(3)


def swap(target: Path) -> None:
    temporary = BASE / "current.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, BASE / "current")


def install_unit(release: Path) -> None:
    unit = (release / "deploy/data-box/data-box.service").read_text()
    if not UNIT_PATH.exists() or UNIT_PATH.read_text() != unit:
        UNIT_PATH.write_text(unit)
        run("systemctl", "daemon-reload", timeout=60)
        run("systemctl", "enable", SERVICE, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def request(url: str, *, method: str = "GET", token: str = "", body: bytes | None = None) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def verify(release: Path, base_url: str, token: str) -> None:
    revision = json.loads((release / "release.json").read_text())["revision"]
    deadline = time.monotonic() + HEALTH_SECONDS
    while True:
        try:
            status, body = request(base_url + "/health")
            if status == 200 and json.loads(body).get("revision") == revision:
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"/health never reported revision {revision}")
        time.sleep(2)
    checks = {
        "POST /mcp/ without a token": request(base_url + "/mcp/", method="POST", body=b"{}")[0] == 401,
        "GET /api/v1/status without a token": request(base_url + "/api/v1/status")[0] == 401,
    }
    status, body = request(base_url + "/openapi.json")
    committed = json.loads((release / "docs/openapi.json").read_text())
    checks["/openapi.json matches docs/openapi.json"] = status == 200 and json.loads(body) == committed
    status, body = request(base_url + "/api/v1/status", token=token)
    checks["authenticated status answers"] = status == 200 and "components" in json.loads(body or b"{}")
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("verification failed: " + "; ".join(failed))


def prune(current: Path, previous: Path | None) -> None:
    keep = {current.resolve()} | ({previous.resolve()} if previous else set())
    releases = sorted((p for p in RELEASES.iterdir() if p.is_dir() and not p.name.startswith(".")),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in releases[KEEP_RELEASES:]:
        if stale.resolve() not in keep:
            shutil.rmtree(stale, ignore_errors=True)


def activate(revision: str) -> dict:
    settings = parse_env(ENV_FILE.read_text())
    token = settings.get("DATABOX_TOKEN", "")
    if not token:
        raise RuntimeError(f"DATABOX_TOKEN is not set in {ENV_FILE}")
    base_url = f"http://127.0.0.1:{settings.get('DATABOX_PORT', '8092')}"
    state_dir = Path(settings.get("DATABOX_STATE_DIR", "/var/lib/data-box"))
    commit = require_merged(revision)
    release = build(commit)
    current_link = BASE / "current"
    previous = current_link.resolve() if current_link.exists() else None
    if previous == release.resolve():
        verify(release, base_url, token)
        return {"active": release.name, "unchanged": True, "validated": True}
    drain(state_dir)
    try:
        swap(release)
        install_unit(release)
        run("systemctl", "restart", SERVICE, timeout=120)
        verify(release, base_url, token)
    except BaseException:
        if previous:
            swap(previous)
            install_unit(previous)
            run("systemctl", "restart", SERVICE, timeout=120)
            verify(previous, base_url, token)
        else:
            subprocess.run(["systemctl", "stop", SERVICE], timeout=120)
            current_link.unlink(missing_ok=True)
        raise
    if previous:
        (BASE / "previous").unlink(missing_ok=True)
        (BASE / "previous").symlink_to(previous)
    record = {"at": time.time(), "revision": release.name, "commit": commit,
              "previous": previous.name if previous else None, "verified": True}
    with (BASE / "deployments.jsonl").open("a") as log:
        log.write(json.dumps(record) + "\n")
    prune(release, previous)
    return {"active": release.name, "rollback": previous.name if previous else None, "validated": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("revision", help="a commit on origin/master (sha or short sha)")
    args = parser.parse_args()
    print(json.dumps(activate(args.revision)))


if __name__ == "__main__":
    main()
