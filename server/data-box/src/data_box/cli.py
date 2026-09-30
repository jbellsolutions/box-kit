"""`data-box`: the command line. A thin client over the HTTP/JSON door, plus `serve` and `openapi`.

  data-box status
  data-box scrape https://example.com --format text
  data-box job get job_ab12cd34 --wait-seconds 30
  data-box job export job_ab12cd34 --format csv > rows.csv
  data-box sources "roofing contractors in Austin TX" --fields '["phone","website"]'
  data-box plan "roofing contractors" --geo '["Austin, TX"]' --count 50 --fields '["phone","website"]'
  data-box execute plan_ab12cd34 --approve true     # only after the user said yes to the plan
  data-box call scrape '{"url": "https://example.com"}'
  data-box serve          # run the server (needs DATABOX_TOKEN)
  data-box openapi        # print the OpenAPI document generated from the tool cards

Any verb works the same way: the first required argument (and for `job`, the action and job_id)
may be given positionally; every other argument is --name value, where a value that parses as
JSON (numbers, true/false, objects) is sent as JSON. Output is the tool's JSON; the exit code is 1
when the box refused (the JSON's error says why) and 2 for a usage or connection problem.

Settings: DATABOX_URL (default http://127.0.0.1:8092) and DATABOX_TOKEN.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from . import config

USAGE = __doc__


def _value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def parse(tool: str, argv: list[str]) -> dict[str, Any]:
    """Map `data-box <tool> [positionals] [--key value ...]` onto the tool's arguments."""
    from .tools import card

    spec = card(tool)
    if spec is None:
        raise SystemExit(f"data-box: no tool {tool!r}")
    props = spec.input_schema.get("properties", {})
    positional_names = list(spec.input_schema.get("required", []))
    if tool == "job":
        positional_names = ["action", "job_id"]
    elif tool in ("plan", "sources"):
        positional_names = ["request"]
    elif tool == "execute":
        positional_names = ["plan_id"]
    args: dict[str, Any] = {}
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            key = token[2:].replace("-", "_")
            if "=" in key:
                key, raw = key.split("=", 1)
            elif i + 1 < len(argv):
                i += 1
                raw = argv[i]
            else:
                raise SystemExit(f"data-box: --{key} needs a value")
            if key not in props:
                raise SystemExit(f"data-box: {tool} has no argument --{key.replace('_', '-')} (it takes: "
                                 + ", ".join("--" + p.replace("_", "-") for p in props) + ")")
            args[key] = raw if props[key].get("type") == "string" else _value(raw)
        else:
            positionals.append(token)
        i += 1
    for name, raw in zip(positional_names, positionals):
        args.setdefault(name, raw)
    if len(positionals) > len(positional_names):
        raise SystemExit(f"data-box: too many positional arguments for {tool}")
    return args


def call(tool: str, args: dict[str, Any]) -> tuple[int, dict]:
    import httpx

    base = config.env("DATABOX_URL", "http://127.0.0.1:8092").rstrip("/")
    headers = {"Authorization": f"Bearer {config.token()}"}
    try:
        with httpx.Client(timeout=90) as client:
            if tool == "status":
                response = client.get(f"{base}/api/v1/status", headers=headers)
            else:
                response = client.post(f"{base}/api/v1/{tool}", json=args, headers=headers)
    except httpx.HTTPError as exc:
        raise SystemExit(f"data-box: cannot reach {base}: {exc}") from None
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:400] or f"HTTP {response.status_code}"}
    return response.status_code, body


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    command, rest = argv[0], argv[1:]
    if command == "serve":
        from .server import main as serve
        serve()
        return 0
    if command == "openapi":
        from .rest import spec_text
        sys.stdout.write(spec_text())
        return 0
    if command == "call":
        if not rest:
            raise SystemExit("data-box: call needs a tool name")
        tool, args = rest[0], (json.loads(rest[1]) if len(rest) > 1 else {})
    else:
        tool, args = command, parse(command, rest)
    if not config.token():
        raise SystemExit("data-box: set DATABOX_TOKEN")
    code, body = call(tool, args)
    if tool == "job" and args.get("action") == "export" and code == 200 and "content" in body:
        sys.stdout.write(body["content"])
        if not body["content"].endswith("\n"):
            sys.stdout.write("\n")
    else:
        print(json.dumps(body, indent=2, ensure_ascii=False))
    if code == 200:
        return 0
    if code in (401, 404, 400):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
