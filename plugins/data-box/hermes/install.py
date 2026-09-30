#!/usr/bin/env python3
"""Install data-box's skills into a Hermes profile, as the category skills/data-box/.

    python3 plugins/data-box/hermes/install.py <profile> [--hermes-home ~/.hermes] [--dry-run]

What it does, and what it never does:
- It only ADDS or UPDATES files under <hermes-home>/profiles/<profile>/skills/data-box/. Nothing
  outside that folder is written, and nothing anywhere is deleted, moved or renamed.
- A skill whose name is already used by another skill in the profile (say the profile already has its
  own firecrawl-alexandria or discolike skill) is installed as data-box-<name>,
  and every "**<name>**" mention in the installed skills is rewritten to match, so the router still
  points at the right one. The profile's own skill is left exactly as it was.
- Every file it writes is recorded with its sha256 in skills/data-box/.data-box-managed.json. On a
  later run, a file someone edited since (its hash no longer matches), or a file it never wrote, is
  left alone and reported. A file the plugin no longer ships is reported, not removed.

Standard library only, so it runs from a clone, from box-kit, or from the plugin's install folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent / "skills"
CATEGORY = "data-box"
MANIFEST = ".data-box-managed.json"
CATEGORY_DESCRIPTION = ("---\ndescription: data-box's data tools, one skill per tool, and the data-box router: "
                        "plan first, pay only on approval.\n---\n")
SKIP_PARTS = {"__pycache__", ".DS_Store"}


def skill_name(skill_md: Path) -> str | None:
    match = re.match(r"^---\n(.*?)\n---\n", skill_md.read_text(errors="replace"), re.S)
    found = match and re.search(r"^name:\s*(.+?)\s*$", match.group(1), re.M)
    return found.group(1).strip("'\"") if found else None


def taken_names(profile_skills: Path) -> set[str]:
    """Skill names the profile already has, outside data-box's own category."""
    names = set()
    for skill_md in profile_skills.rglob("SKILL.md"):
        if CATEGORY in skill_md.relative_to(profile_skills).parts[:1]:
            continue
        name = skill_name(skill_md)
        if name:
            names.add(name)
    return names


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan_install(profile_skills: Path) -> tuple[dict[str, str], dict[str, bytes]]:
    """(renames, files): which skills get a data-box- prefix, and every file to write, by path
    relative to skills/data-box/."""
    sources = sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").exists())
    taken = taken_names(profile_skills)
    renames = {}
    for src in sources:
        name = skill_name(src / "SKILL.md") or src.name
        if name in taken and name != CATEGORY:
            renames[name] = f"data-box-{name}"
    files: dict[str, bytes] = {"DESCRIPTION.md": CATEGORY_DESCRIPTION.encode()}
    for src in sources:
        name = skill_name(src / "SKILL.md") or src.name
        folder = renames.get(name, name)
        for path in sorted(src.rglob("*")):
            rel = path.relative_to(src)
            if not path.is_file() or SKIP_PARTS & set(rel.parts):
                continue
            data = path.read_bytes()
            if path.suffix == ".md" and "pages" not in rel.parts:
                text = data.decode()
                if rel == Path("SKILL.md") and name in renames:
                    text = re.sub(r"^name:\s*.+$", f"name: {renames[name]}", text, count=1, flags=re.M)
                for old, new in renames.items():
                    text = text.replace(f"**{old}**", f"**{new}**")
                data = text.encode()
            files[f"{folder}/{rel.as_posix()}"] = data
    return renames, files


def install(profile: str, hermes_home: Path, dry_run: bool = False) -> dict:
    profile_dir = hermes_home / "profiles" / profile
    if not profile_dir.is_dir():
        raise SystemExit(f"no Hermes profile at {profile_dir}")
    profile_skills = profile_dir / "skills"
    target = profile_skills / CATEGORY
    manifest_path = target / MANIFEST
    managed = json.loads(manifest_path.read_text())["files"] if manifest_path.exists() else {}
    renames, files = plan_install(profile_skills)
    report = {"profile": profile, "target": str(target), "renamed": renames, "written": [], "unchanged": [],
              "kept_edited": [], "kept_unmanaged": [], "no_longer_shipped": []}
    recorded = dict(managed)
    for rel, data in files.items():
        dest = target / rel
        if dest.exists():
            current = sha(dest.read_bytes())
            if rel not in managed:
                report["kept_unmanaged"].append(rel)
                continue
            if current != managed[rel]:
                report["kept_edited"].append(rel)
                continue
            if current == sha(data):
                report["unchanged"].append(rel)
                continue
        report["written"].append(rel)
        recorded[rel] = sha(data)
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    report["no_longer_shipped"] = sorted(set(managed) - set(files))
    if not dry_run and report["written"]:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"source": str(SKILLS), "files": recorded}, indent=1, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("profile", help="the Hermes profile, e.g. firecrawl")
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--dry-run", action="store_true", help="say what would be written; write nothing")
    args = parser.parse_args(argv)
    report = install(args.profile, args.hermes_home.expanduser(), args.dry_run)
    verb = "would write" if args.dry_run else "wrote"
    print(f"{report['target']}: {verb} {len(report['written'])} files, {len(report['unchanged'])} unchanged")
    for old, new in report["renamed"].items():
        print(f"  {old}: the profile already has a skill by that name; installed as {new}")
    for key, label in (("kept_edited", "edited since install, left as is"),
                       ("kept_unmanaged", "not written by this installer, left as is"),
                       ("no_longer_shipped", "no longer shipped by the plugin, left in place")):
        for rel in report[key]:
            print(f"  {rel}: {label}")
    if not args.dry_run and report["written"]:
        print("Restart the profile's gateway (or the Hermes desktop app) so it loads the skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
