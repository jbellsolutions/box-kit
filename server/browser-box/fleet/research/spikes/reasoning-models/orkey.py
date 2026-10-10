"""Snapshot OpenRouter key usage (spend tracking). Never prints the key.

Usage: python orkey.py <label> <out.jsonl>
Reads OPENROUTER_API_KEY from the environment, or from the repository's .env if unset.
"""
import json
import os
import sys
import time
import urllib.request

ENV_FILE = os.environ.get("ENV_FILE", ".env")


def load_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    with open(ENV_FILE) as fh:
        for line in fh:
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENROUTER_API_KEY not found")


def snapshot() -> dict:
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {load_key()}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)["data"]
    # keep only non-secret accounting fields
    return {k: data.get(k) for k in ("label", "usage", "usage_daily", "limit", "limit_remaining", "is_free_tier")}


if __name__ == "__main__":
    snap = snapshot()
    snap["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    snap["tag"] = sys.argv[1] if len(sys.argv) > 1 else ""
    if snap.get("label"):
        snap["label"] = "redacted"  # label can embed a key prefix
    print(json.dumps(snap))
    if len(sys.argv) > 2:
        with open(sys.argv[2], "a") as fh:
            fh.write(json.dumps(snap) + "\n")
