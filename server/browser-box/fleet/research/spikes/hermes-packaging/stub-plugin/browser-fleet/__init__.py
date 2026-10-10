"""Spike stub for the browser-fleet client plugin. Registers one tool, one hook, one skill."""
import json
from pathlib import Path

_SCHEMA = {
    "name": "fleet_ping",
    "description": "Spike stub. Returns the active Hermes profile name; makes no network call.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def register(ctx):
    def fleet_ping(args, **kwargs):
        return json.dumps({"profile": ctx.profile_name})

    def on_post_tool_call(tool_name=None, args=None, result=None, **kwargs):
        # Real plugin: when tool_name starts with "mcp__browser_fleet__", append an evidence
        # line to the profile's Obsidian daily note. The stub does nothing.
        return None

    ctx.register_tool(name="fleet_ping", toolset="browser_fleet_client", schema=_SCHEMA, handler=fleet_ping)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        if (child / "SKILL.md").is_file():
            ctx.register_skill(child.name, child / "SKILL.md")
