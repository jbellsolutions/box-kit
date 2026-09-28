"""Test package. Puts the gateway on the path and keeps the lane lock out of /tmp's way."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gateway"))
sys.path.insert(0, str(ROOT / "cli"))

# Must be set before gateway.lock is imported anywhere: LOCK_PATH is read at import time.
os.environ.setdefault("BB_LANE_LOCK", os.path.join(tempfile.mkdtemp(prefix="bb-test-"), "lane.lock"))
os.environ.setdefault("BB_TOKEN", "test-token-not-a-secret")

# Optional integrations are listed only when configured. Tests start from a box with none,
# whatever the developer's shell happens to export, and opt in explicitly where needed.
for _var in ("ORGO_API_KEY", "ORGO_COMPUTER_ID", "BB_ORGO_AUTOCREATE", "ORGO_MODEL", "BB_JEV_URL", "BB_JEV_TOKEN",
             "BB_BROWSERUSE_URL", "BB_BROWSERUSE_TOKEN"):
    os.environ.pop(_var, None)
