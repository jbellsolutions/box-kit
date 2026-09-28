"""bb — chat with, or drive, a browser-box gateway."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

from . import __version__
from .client import CONFIG, NotConfigured, call, endpoint, settings, tool_list


def out(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False) if not isinstance(value, str) else value)


def _save_screenshot(result: dict, destination: str | None) -> dict:
    """Keep base64 out of the terminal: write the image, report the path."""
    blob = result.pop("screenshot_base64", None)
    if not blob:
        return result
    path = Path(destination or "screenshot.jpg")
    path.write_bytes(base64.b64decode(blob))
    result["screenshot_saved_to"] = str(path.resolve())
    return result


async def cmd_status(_args) -> int:
    out(await call("status", {}))
    return 0


async def cmd_tools(_args) -> int:
    for tool in await tool_list():
        print(f"{tool.name}\n  {tool.description.splitlines()[0]}")
    return 0


async def cmd_fetch(args) -> int:
    result = await call("fetch", {"url": args.url})
    if args.text and "text" in result:
        print(result["text"])
    else:
        out(result)
    return 1 if "error" in result else 0


async def cmd_read(args) -> int:
    payload = {"url": args.url}
    if args.screenshot or args.out:
        payload["screenshot"] = True
    if args.delay_ms:
        payload["delay_ms"] = args.delay_ms
    result = _save_screenshot(await call("read", payload), args.out)
    if args.text and "text" in result:
        print(result["text"])
        if result.get("screenshot_saved_to"):
            print(f"\n[screenshot: {result['screenshot_saved_to']}]", file=sys.stderr)
    else:
        out(result)
    return 1 if "error" in result else 0


async def cmd_session(args) -> int:
    payload = {"action": args.action}
    if args.session_id:
        payload["session_id"] = args.session_id
    result = await call("session", payload)
    out(result)
    return 1 if "error" in result else 0


async def cmd_computer(args) -> int:
    payload: dict = {"action": args.action}
    for field in ("x", "y", "text", "key", "command", "direction", "amount", "button", "computer_id"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    if args.double:
        payload["double"] = True
    if args.after:
        payload["screenshot_after"] = True
    wants_image = args.action == "screenshot" or args.after
    result = await call("computer", payload)
    if wants_image:
        result = _save_screenshot(result, args.out)
    if args.action == "bash" and "output" in result and not args.json:
        print(result["output"] or "")
    else:
        out(result)
    return 1 if "error" in result else 0


async def cmd_act(args) -> int:
    if args.pick:
        payload: dict = {"pick": args.pick}
    elif args.confirm:
        payload = {"confirm": args.confirm == "yes"}
    elif args.command:
        payload = {"command": " ".join(args.command)}
    else:
        print("say what to do: bb act \"click the pricing link\" (or --pick / --confirm to answer a question)", file=sys.stderr)
        return 2
    if args.read:
        payload["read_page"] = True
    result = await call("act", payload)
    if args.json or "error" in result:
        out(result)
        return 1 if "error" in result else 0
    for step in result.get("steps") or []:
        print(f"  {'✓' if step.get('outcome') == 'ok' else '·'} {step.get('did') or step.get('command')}")
    status = result.get("status")
    if status == "needs_clarification":
        print(result.get("question") or "Which one?")
        for option in result.get("options") or []:
            print(f"  --pick {option['pick']}   {option['label']} ({option['probability']:.0%})")
    elif status == "needs_confirmation":
        print(f"{result.get('action')}: {result.get('reason')}\n  answer with --confirm yes or --confirm no")
    else:
        print(f"[{status}] {result.get('title') or ''} {result.get('url') or ''}".rstrip())
    if result.get("refused"):
        print(result["refused"], file=sys.stderr)
    if result.get("text"):
        print("\n" + result["text"])
    elif result.get("text_note"):
        print(result["text_note"], file=sys.stderr)
    return 0 if status in ("done", "needs_clarification", "needs_confirmation") else 1


async def cmd_task(args) -> int:
    if args.cancel:
        result = await call("task", {"cancel": True})
        out(result)
        return 0 if result.get("cancelled") else 1
    if not args.goal:
        print("give the goal: bb task \"what to achieve and report\" (or --cancel to stop the running one)", file=sys.stderr)
        return 2
    payload: dict = {"goal": " ".join(args.goal)}
    for field, value in (("surface", args.surface), ("timeout_seconds", args.timeout), ("max_steps", args.max_steps),
                         ("computer_id", args.computer_id)):
        if value is not None:
            payload[field] = value
    result = await call("task", payload)
    if args.json or "error" in result:
        out(result)
    else:
        print(result.get("answer") or f"[{result.get('status')}] no answer")
        if result.get("estimated_cost_usd") is not None:
            print(f"[{result.get('status')}: {result.get('steps_taken')} steps, {result.get('seconds')}s, "
                  f"~${result['estimated_cost_usd']}]", file=sys.stderr)
    return 1 if "error" in result or result.get("status") != "done" else 0


async def cmd_ask(args) -> int:
    from .agent import LlmUnavailable, ask

    def note(name, arguments):
        if not args.quiet:
            print(f"  · {name} {json.dumps(arguments)[:100]}", file=sys.stderr)

    try:
        answer, _ = await ask(" ".join(args.goal), on_step=note)
    except LlmUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(answer)
    return 0


async def cmd_chat(args) -> int:
    from .agent import LlmUnavailable, ask

    print("browser-box. Ask for anything on the web. Ctrl-D or 'exit' to leave.\n")
    history: list[dict] | None = None
    while True:
        try:
            goal = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if goal in ("exit", "quit"):
            return 0
        if not goal:
            continue
        try:
            answer, history = await ask(
                goal, history, on_step=lambda n, a: print(f"  · {n} {json.dumps(a)[:100]}", file=sys.stderr)
            )
        except LlmUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"\n{answer}\n")


async def cmd_login(args) -> int:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"url": args.url, "token": args.token}, indent=2))
    CONFIG.chmod(0o600)
    print(f"Saved to {CONFIG} (mode 600).")
    try:
        health = await call("status", {})
    except Exception as exc:
        print(f"Saved, but the box did not answer: {exc}", file=sys.stderr)
        return 1
    print(f"Connected to {endpoint(args.url)} — browser: {health['components'][0]['up']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bb", description="Chat with, or drive, a browser-box gateway.")
    parser.add_argument("--version", action="version", version=f"bb {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Interactive session. Needs OPENROUTER_API_KEY.")
    chat.set_defaults(run=cmd_chat)

    ask = sub.add_parser("ask", help="One request, answered. Needs OPENROUTER_API_KEY.")
    ask.add_argument("goal", nargs="+")
    ask.add_argument("-q", "--quiet", action="store_true", help="Hide the tool calls")
    ask.set_defaults(run=cmd_ask)

    fetch = sub.add_parser("fetch", help="Plain HTTP GET. No browser, no model.")
    fetch.add_argument("url")
    fetch.add_argument("-t", "--text", action="store_true", help="Print the text, not the JSON")
    fetch.set_defaults(run=cmd_fetch)

    read = sub.add_parser("read", help="Open a URL in the real browser. No model.")
    read.add_argument("url")
    read.add_argument("-t", "--text", action="store_true", help="Print the text, not the JSON")
    # -s is a flag, not a path. An optional-value flag swallows the URL when it comes first
    # ("bb read -s https://x" reads the URL as the filename), which is a confusing failure.
    read.add_argument("-s", "--screenshot", action="store_true", help="Also capture a screenshot")
    read.add_argument("-o", "--out", metavar="FILE", help="Where to write it (default screenshot.jpg)")
    read.add_argument("--delay-ms", type=int, help="Wait this long after load for late content")
    read.set_defaults(run=cmd_read)

    sess = sub.add_parser("session", help="Persistent logged-in browser sessions.")
    sess.add_argument("action", choices=["create", "list", "release"])
    sess.add_argument("session_id", nargs="?")
    sess.set_defaults(run=cmd_session)

    comp = sub.add_parser("computer", help="Drive an Orgo cloud computer (needs Orgo on the box).")
    comp.add_argument("action", choices=["screenshot", "click", "type", "key", "scroll", "bash", "start", "stop"])
    comp.add_argument("--x", type=int)
    comp.add_argument("--y", type=int)
    comp.add_argument("--text")
    comp.add_argument("--key")
    comp.add_argument("--command", help="For bash")
    comp.add_argument("--direction", choices=["up", "down", "left", "right"])
    comp.add_argument("--amount", type=int)
    comp.add_argument("--button", choices=["left", "right", "middle"])
    comp.add_argument("--double", action="store_true")
    comp.add_argument("--after", action="store_true", help="Also take a screenshot after the action")
    comp.add_argument("-o", "--out", metavar="FILE", help="Where to write a screenshot (default screenshot.jpg)")
    comp.add_argument("--computer-id", dest="computer_id")
    comp.add_argument("--json", action="store_true", help="Print the full result")
    comp.set_defaults(run=cmd_computer)

    act = sub.add_parser("act", help="Drive the browser in plain-words steps; Jev picks the element (needs Jev on the box).")
    act.add_argument("command", nargs="*", help='e.g. "open https://example.com then click More information"')
    act.add_argument("--pick", help="Answer a clarification with one option's pick")
    act.add_argument("--confirm", choices=["yes", "no"], help="Answer a confirmation")
    act.add_argument("--read", action="store_true", help="Also print the page's text afterwards")
    act.add_argument("--json", action="store_true", help="Print the full result")
    act.set_defaults(run=cmd_act)

    task = sub.add_parser("task", help="Hand a whole goal to an agent and wait for the answer.")
    task.add_argument("goal", nargs="*")
    task.add_argument("--surface", choices=["browser", "computer"],
                      help="browser = Browser-Use in the box's browser; computer = an Orgo desktop. "
                           "Optional when the box has only one")
    task.add_argument("--max-steps", dest="max_steps", type=int, help="browser only: the most model steps (default 25)")
    task.add_argument("--timeout", type=int, help="Seconds; hitting it stops the run (default 300 browser, 600 computer)")
    task.add_argument("--computer-id", dest="computer_id")
    task.add_argument("--cancel", action="store_true", help="Stop the running browser task instead of starting one")
    task.add_argument("--json", action="store_true")
    task.set_defaults(run=cmd_task)

    status = sub.add_parser("status", help="What is up, and what it cost.")
    status.set_defaults(run=cmd_status)

    tools = sub.add_parser("tools", help="What this box offers.")
    tools.set_defaults(run=cmd_tools)

    login = sub.add_parser("login", help="Save the box URL and token.")
    login.add_argument("--url", required=True)
    login.add_argument("--token", required=True)
    login.set_defaults(run=cmd_login)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(args.run(args))
    except NotConfigured as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
