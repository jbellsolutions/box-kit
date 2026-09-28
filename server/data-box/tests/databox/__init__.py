"""data-box tests. Put src/ on the path and start from a box with no provider configured,
whatever the developer's shell exports; tests opt in explicitly where they need one."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

os.environ["DATABOX_TOKEN"] = "test-token-not-a-secret"
os.environ["DATABOX_STATE_DIR"] = tempfile.mkdtemp(prefix="data-box-test-")

from data_box import config  # noqa: E402

for _spec in config.PROVIDERS.values():
    for _var in _spec["env"]:
        os.environ.pop(_var, None)
