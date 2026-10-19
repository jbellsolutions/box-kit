#!/usr/bin/env python3
"""Refresh the data-box plugin's skills, commands and Hermes installer from the private repo,
under the kit's public rule, into plugins/data-box/ and hermes/skills/data-box/.

    python3 scripts/export_skills.py <data-box clone> <ref>

The public rule, per tool skill:
- references/handoff.md is the owner's own install state (keys, balances, live checks). It is
  replaced by a short note; data-box's test_skills keeps every other file free of owner paths/hosts.
- references/vendor-docs/ keeps SOURCES.json only. The vendors' pages are theirs to publish, so the
  kit ships the list of sources and PROVENANCE.md says how to fetch your own copy; manifest.json
  goes too, so nothing claims pages that are not there.
The kit's own plugin.json and .mcp.json are kept: they point at the kit's local server.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
HANDOFF = """# {tool}: handoff

This file holds one install's own state in the private repo: which keys are set, balances, live
checks and open issues. It is not part of the public kit.

On your install:
- `status` (MCP, `POST /api/v1/status`, or `data-box status`) says whether {tool} is configured
  on your server, and if not, which setting turns it on.
- [charter.md](charter.md) has the rules the tool follows, and [cost-map.md](cost-map.md) the
  prices as last checked.
"""
PROVENANCE = """# {tool} vendor docs

The kit ships the list of sources ([SOURCES.json](SOURCES.json)) but not the vendor's pages: they
are the vendor's to publish. Fetch your own dated, hashed copy from the kit's root:

```bash
cd server/data-box && python3 -m data_box.vendor_docs fetch ../../plugins/data-box/skills/{tool}
```

That writes pages/, manifest.json and a new PROVENANCE.md here, through the same public-only fetch
data-box uses for scraping. Only free, public pages are fetched.
"""


def public(skill: Path) -> None:
    tool = skill.name
    refs = skill / "references"
    if (refs / "handoff.md").exists():
        (refs / "handoff.md").write_text(HANDOFF.format(tool=tool))
    docs = refs / "vendor-docs"
    if docs.exists():
        for child in docs.iterdir():
            if child.name != "SOURCES.json":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        (docs / "PROVENANCE.md").write_text(PROVENANCE.format(tool=tool))


def main(clone: str, ref: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "plugin.tar"
        subprocess.run(["git", "-C", clone, "archive", "-o", str(archive), ref,
                        "plugins/data-box/skills", "plugins/data-box/commands", "plugins/data-box/hermes"], check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
        src = Path(tmp) / "plugins" / "data-box"
        for skill in (src / "skills").iterdir():
            if skill.is_dir():
                public(skill)
        plugin = KIT / "plugins" / "data-box"
        for part in ("skills", "commands", "hermes"):
            if (plugin / part).exists():
                shutil.rmtree(plugin / part)
            shutil.copytree(src / part, plugin / part)
        hermes = KIT / "hermes" / "skills" / "data-box"
        if hermes.exists():
            shutil.rmtree(hermes)
        shutil.copytree(src / "skills", hermes)
        (hermes / "DESCRIPTION.md").write_text("---\ndescription: data-box's data tools, one skill per tool, and "
                                               "the data-box router: plan first, pay only on approval.\n---\n")
    print(f"plugins/data-box and hermes/skills/data-box refreshed from {ref}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
