"""act on a hosted browser: the caller writes the steps, Jev picks the element each step means, CDP does it.

Division of labour:
- code: splits the command into steps, pulls out anything that must be copied exactly (a URL, the text
  to type), lists the page's interactive elements, and does the click or the typing over CDP;
- Jev: one request per step answers every judgment call at once: what the step asks (click, type,
  press enter, scroll...), which element, whether it is hard to undo, whether typing should submit;
- the caller: answers a question when Jev is unsure (``pick``) or a step is risky (``confirm``).

The result keeps act's contract: status done | failed | needs_clarification | needs_confirmation, the
steps that ran and how each went, url and title.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from . import decide
from .cdp import Cdp, CdpError
from .security import target_scope

MAX_STEPS = 4
MAX_ELEMENTS = 180
TARGET_MIN = 0.35      # below this, ask the caller instead of guessing
RISK_MIN = 0.6         # above this, a click/type/press waits for confirm=true
SUBMIT_MIN = 0.6
PENDING_SECONDS = 120
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)
QUOTED_RE = re.compile(r"[\"“']([^\"”']{1,2000})[\"”']")
VERB_START = re.compile(r"^(?:click|press|tap|open|go|navigate|visit|type|enter|write|fill|search|select|choose|pick|tick|check|"
                        r"uncheck|scroll|hit|submit|reload|refresh|back)\b", re.I)

INTENTS = {
    "open_url": "Go to or open a web address",
    "click": "Click, press, tap, open, tick, untick or toggle something on the current page: a link, button, tab, checkbox, radio button",
    "type_text": "Type, enter, write or fill words into a text field, search box or editor on the current page",
    "select_option": "Choose an option from a dropdown list on the current page",
    "press_enter": "Press enter or submit the current form without typing anything new",
    "scroll": "Scroll the page up, down, to the top or to the bottom",
    "go_back": "Go back to the previous page",
    "reload": "Reload or refresh the page",
    "unclear": "Not a browser instruction, or impossible to tell",
}
DIRECTIONS = {"down": "further down the page", "up": "back up the page", "top": "to the very top", "bottom": "to the very bottom"}

# Lists visible interactive elements, tags each with data-bb-id, returns their descriptions' parts.
ELEMENTS_JS = r"""
(max) => {
  const sel = 'a[href],button,input:not([type=hidden]),textarea,select,summary,[role=button],[role=link],[role=tab],' +
              '[role=menuitem],[role=checkbox],[role=radio],[role=option],[role=textbox],[role=combobox],[role=switch],' +
              '[contenteditable=true],[onclick]';
  const squash = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  document.querySelectorAll('[data-bb-id]').forEach(e => e.removeAttribute('data-bb-id'));
  const out = [], seen = new Set();
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || cs.visibility === 'hidden' || cs.display === 'none' || el.disabled) continue;
    const tag = el.tagName.toLowerCase(), type = (el.getAttribute('type') || '').toLowerCase();
    const field = tag === 'textarea' || tag === 'select' || el.isContentEditable ||
                  (tag === 'input' && !['submit', 'button', 'reset', 'image', 'checkbox', 'radio'].includes(type));
    const label = squash(el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) ||
                         el.getAttribute('title') || el.getAttribute('alt') || '', 80);
    const text = field ? '' : squash(el.innerText || el.value || '', 80);
    const placeholder = squash(el.getAttribute('placeholder'), 60);
    const href = tag === 'a' ? (el.getAttribute('href') || '') : '';
    let kind = el.getAttribute('role') || ({a: 'link', button: 'button', select: 'dropdown', textarea: 'text area', summary: 'expander'}[tag]) ||
               (tag === 'input' ? ({checkbox: 'checkbox', radio: 'radio button', submit: 'button', button: 'button', search: 'search box'}[type] || 'text box') : tag);
    const key = [kind, text, label, placeholder, href].join('|');
    if (seen.has(key) || !(text || label || placeholder || href || field)) continue;
    seen.add(key);
    out.push({el, kind, text, label, placeholder, name: squash(el.getAttribute('name'), 40), href: href.slice(0, 60),
              shown: r.bottom > 0 && r.top < innerHeight, top: r.top});
  }
  out.sort((a, b) => (a.shown === b.shown ? a.top - b.top : a.shown ? -1 : 1));
  return out.slice(0, max).map((x, i) => { x.el.setAttribute('data-bb-id', 'e' + i); const {el, top, ...rest} = x; return rest; });
}
"""


def describe(e: dict) -> str:
    main = e.get("text") or e.get("label") or e.get("placeholder") or e.get("name")
    s = e["kind"] + (f' "{main}"' if main else "")
    if e.get("label") and e.get("text") and e["label"] != e["text"]:
        s += f' ({e["label"]})'
    if e.get("placeholder") and main != e["placeholder"]:
        s += f' placeholder "{e["placeholder"]}"'
    if e.get("href") and not e["href"].startswith(("#", "javascript:")):
        s += f" → {e['href']}"
    if not e.get("shown"):
        s += " [off-screen]"
    return s


def split_steps(command: str) -> list[str]:
    parts = [p.strip(" ,.;") for p in re.split(r"\s*(?:,\s*)?\bthen\b\s*", command.strip(), flags=re.I) if p.strip(" ,.;")]
    steps: list[str] = []
    for part in parts:
        pieces = re.split(r"\s+and\s+", part)
        current = pieces[0]
        for piece in pieces[1:]:                 # "and" splits only when a new action follows it
            if VERB_START.match(piece):
                steps.append(current)
                current = piece
            else:
                current += " and " + piece
        steps.append(current)
    if len(steps) > MAX_STEPS:
        raise ValueError(f"act takes at most {MAX_STEPS} steps per call; split the rest into another call")
    return steps


def text_to_type(step: str) -> str | None:
    quoted = QUOTED_RE.search(step)
    if quoted:
        return quoted.group(1)
    m = re.match(r"^(?:type|enter|write|fill in|search for|search)\s+(.+?)(?:\s+(?:into|in|on)\s+the\s+.+)?$", step, re.I)
    return m.group(1).strip() if m else None


class Stepper:
    """One session's act engine. Holds no browser of its own: the caller passes the session's cdp and page."""

    def __init__(self, cdp: Cdp, page: str, *, check_url: Any):
        self.cdp, self.page, self.check_url = cdp, page, check_url

    async def js(self, expr: str) -> Any:
        r = await self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, session=self.page)
        return (r.get("result") or {}).get("value")

    async def where(self) -> dict:
        return await self.js("({url: location.href, title: document.title})") or {}

    async def elements(self) -> list[dict]:
        return await self.js(f"({ELEMENTS_JS})({MAX_ELEMENTS})") or []

    async def settle(self) -> None:
        await asyncio.sleep(0.4)
        for _ in range(30):
            try:
                if await self.js("document.readyState") == "complete":
                    return
            except CdpError:
                pass                     # mid-navigation the old page's context is gone; ask again
            await asyncio.sleep(0.3)

    # ── running ────────────────────────────────────────────────────────────────────────────
    async def run(self, steps: list[str], *, pending: dict | None = None, pick: str | None = None,
                  confirm: bool | None = None) -> tuple[dict, dict | None]:
        """Run steps in order. Returns (result, pending-or-None)."""
        rows: list[dict] = []
        start = 0
        if pending:
            steps, start, rows = pending["steps"], pending["index"], pending["rows"]
        for i in range(start, len(steps)):
            step = steps[i]
            forced = None
            if pending and i == start:
                if pending["kind"] == "clarify":
                    if pick not in pending["options"]:
                        raise ValueError(f"pick one of: {', '.join(pending['options'])}")
                    forced = {"element": pick, "plan": {**pending["plan"], "label": pending["options"][pick]["label"]}}
                elif not confirm:
                    rows.append({"command": step, "did": "cancelled: you answered confirm=false", "outcome": "cancelled"})
                    return await self.result(rows, "failed"), None
                else:
                    forced = {"element": pending["element"], "plan": pending["plan"], "confirmed": True}
            row, ask = await self.one(step, forced)
            if ask:
                held = {**ask, "steps": steps, "index": i, "rows": rows, "at": time.monotonic()}
                out = await self.result(rows, ask["status"])
                out.update({k: v for k, v in ask.items() if k in ("question", "options", "action", "reason", "next")})
                if ask["status"] == "needs_clarification":
                    out["options"] = [{"pick": k, "label": v["label"], "probability": v["p"]} for k, v in ask["options"].items()]
                return out, held
            rows.append(row)
            if row["outcome"] != "ok":
                return await self.result(rows, "failed"), None
        return await self.result(rows, "done"), None

    async def result(self, rows: list[dict], status: str) -> dict:
        here = await self.where()
        return {"status": status, "steps": rows, "url": here.get("url"), "title": here.get("title")}

    async def one(self, step: str, forced: dict | None) -> tuple[dict, dict | None]:
        row: dict[str, Any] = {"command": step}
        url = URL_RE.search(step)
        if forced is None and url and re.match(r"^(?:open|go to|goto|visit|navigate to|load)\b", step, re.I):
            target = await self.check_url(url.group(0).rstrip(".,)"))
            await self.cdp.send("Page.navigate", {"url": target}, session=self.page)
            await self.settle()
            row.update(decided_by="code", did=f"opened {target}")
            return await self._landed(row), None
        if forced:
            plan, element = forced["plan"], forced["element"]
            row["decided_by"] = "you"
            if not forced.get("confirmed"):
                plan = await self.judge_element(step, plan)
                if self.needs_confirming(plan):
                    return row, self.confirmation(plan, element)
        else:
            els = await self.elements()
            options = {f"e{i}": describe(e) for i, e in enumerate(els)}
            options["none"] = "The command does not refer to any element listed here"
            here = await self.where()
            questions = {
                "intent": decide.choice("What is the user asking the browser to do?", INTENTS),
                "target": decide.choice("Which element on the current page is the user referring to? Choose 'none' if the command "
                                        "does not name anything on this page.", options),
                "risky": decide.noul("Would carrying out this command do something hard to undo?",
                                     "It would buy or pay, delete or remove, send a message, post publicly, log out, or submit an order",
                                     "It only reads, navigates, scrolls, searches, types into a field, or opens something"),
                "submit": decide.noul("After the text is typed, should it be submitted right away (press enter / run the search)?",
                                      "Yes: they said search, submit or press enter", "No: just fill in the field"),
                "direction": decide.choice("Which way should the page move?", DIRECTIONS),
            }
            answered = await decide.ask({"command": step, "page": {"url": here.get("url"), "title": here.get("title")}}, questions)
            a = answered["answers"]
            row.update(decided_by="jev", decision_ms=answered["ms"])
            intent, intent_p, _ = decide.picked(a, "intent")
            element, target_p, probs = decide.picked(a, "target")
            plan = {"intent": intent, "text": text_to_type(step), "submit": decide.probability(a, "submit") >= SUBMIT_MIN,
                    "direction": decide.picked(a, "direction")[0] or "down", "label": options.get(element or "", ""),
                    "risky": decide.probability(a, "risky")}
            if intent in ("unclear", None) or intent_p < 0.25:
                row.update(did="not understood as a browser step", outcome="failed")
                return row, None
            needs_element = intent in ("click", "type_text", "select_option")
            if needs_element and (element in (None, "none") or target_p < TARGET_MIN):
                top = sorted(((k, p) for k, p in probs.items() if k != "none" and p >= 0.05), key=lambda kp: -kp[1])[:4]
                if not top:
                    row.update(did="no element on this page matches that step", outcome="failed")
                    return row, None
                return row, {"kind": "clarify", "status": "needs_clarification", "plan": plan,
                             "question": f"Which one did you mean for: {step}?",
                             "options": {k: {"label": options[k], "p": round(p, 2)} for k, p in top},
                             "next": "answer with act(pick=<an option's pick>)"}
            plan = await self.judge_element(step, plan)
            if self.needs_confirming(plan):
                return row, self.confirmation(plan, element)
        did, ok = await self.do(plan, element)
        row["did"] = did
        if not ok:
            row["outcome"] = "failed"
        return await self._landed(row), None

    async def judge_element(self, step: str, plan: dict) -> dict:
        """Risk judged on the element too, not only the words: "click the button" on a form whose one button is
        "Submit order" reads harmless and is not. Measured live 2026-10-12; this second question closes it."""
        acts_on_element = plan["intent"] in ("click", "select_option") or (plan["intent"] == "type_text" and plan.get("submit"))
        if not acts_on_element or plan.get("risky", 0.0) >= RISK_MIN:
            return plan
        here = await self.where()
        answered = await decide.ask(
            {"command": step, "element": plan.get("label"), "page": {"url": here.get("url"), "title": here.get("title")}},
            {"risky": decide.noul("Would doing this to this element do something hard to undo?",
                                  "It would buy or pay, delete or remove, send a message, post publicly, log out, or submit "
                                  "a form or an order",
                                  "It only navigates, opens, expands, selects, ticks a box, or fills a field without submitting")})
        return {**plan, "risky": max(plan.get("risky", 0.0), decide.probability(answered["answers"], "risky"))}

    @staticmethod
    def needs_confirming(plan: dict) -> bool:
        return plan["intent"] in ("click", "type_text", "press_enter", "select_option") and plan.get("risky", 0.0) >= RISK_MIN

    @staticmethod
    def confirmation(plan: dict, element: str | None) -> dict:
        return {"kind": "confirm", "status": "needs_confirmation", "plan": plan, "element": element,
                "action": f"{plan['intent'].replace('_', ' ')} {plan.get('label') or ''}".strip(),
                "reason": f"this looks hard to undo (p={plan.get('risky', 0.0):.2f})",
                "next": "answer with act(confirm=true) to go ahead or act(confirm=false) to cancel"}

    async def _landed(self, row: dict) -> dict:
        here = await self.where()
        url = here.get("url") or ""
        if url and not url.startswith("about:") and target_scope(url) != "public_web":
            await self.cdp.send("Page.navigate", {"url": "about:blank"}, session=self.page)
            row.update(outcome="refused", did=f"{row.get('did')}; refused: it led off the public web")
            return row
        row.setdefault("outcome", "ok")
        return row

    # ── doing ──────────────────────────────────────────────────────────────────────────────
    async def do(self, plan: dict, element: str | None) -> tuple[str, bool]:
        intent = plan["intent"]
        sel = f'[data-bb-id="{element}"]'
        if intent in ("click", "type_text", "select_option"):
            box = await self.js(f"(() => {{ const el = document.querySelector('{sel}'); if (!el) return null;"
                                " el.scrollIntoView({block: 'center'}); const r = el.getBoundingClientRect();"
                                " return {x: r.left + r.width / 2, y: r.top + r.height / 2, tag: el.tagName.toLowerCase()}; })()")
            if not box:
                return "the element is gone from the page", False
        if intent == "click":
            await self.mouse(box["x"], box["y"])
            await self.settle()
            return f"clicked {plan['label']}", True
        if intent == "select_option":
            wanted = json.dumps(plan.get("text") or "")
            chosen = await self.js(f"(() => {{ const el = document.querySelector('{sel}'); const w = {wanted}.toLowerCase();"
                                   " if (el.tagName.toLowerCase() !== 'select') return null;"
                                   " const o = [...el.options].find(o => o.text.toLowerCase().includes(w) || o.value.toLowerCase() === w);"
                                   " if (!o) return ''; el.value = o.value; el.dispatchEvent(new Event('input', {bubbles: true}));"
                                   " el.dispatchEvent(new Event('change', {bubbles: true})); return o.text; })()")
            if chosen is None:
                await self.mouse(box["x"], box["y"])
                return f"clicked {plan['label']}", True
            return (f"chose {chosen!r} in {plan['label']}", True) if chosen else (f"no option like {plan.get('text')!r} in {plan['label']}", False)
        if intent == "type_text":
            text = plan.get("text")
            if not text:
                return "no text to type: put it in quotes", False
            await self.mouse(box["x"], box["y"])
            await self.js(f"(() => {{ const el = document.querySelector('{sel}'); el.focus();"
                          " if ('value' in el) { el.select && el.select(); } })()")
            await self.cdp.send("Input.insertText", {"text": text}, session=self.page)
            if plan.get("submit"):
                await self.key("Enter")
                await self.settle()
            return f"typed {text!r} into {plan['label']}" + (" and pressed enter" if plan.get("submit") else ""), True
        if intent == "press_enter":
            await self.key("Enter")
            await self.settle()
            return "pressed enter", True
        if intent == "scroll":
            by = {"down": "window.scrollBy(0, innerHeight * 0.8)", "up": "window.scrollBy(0, -innerHeight * 0.8)",
                  "top": "window.scrollTo(0, 0)", "bottom": "window.scrollTo(0, document.body.scrollHeight)"}[plan["direction"]]
            await self.js(by)
            return f"scrolled {plan['direction']}", True
        if intent == "go_back":
            await self.js("history.back()")
            await self.settle()
            return "went back", True
        if intent == "reload":
            await self.cdp.send("Page.reload", session=self.page)
            await self.settle()
            return "reloaded", True
        if intent == "open_url":
            return "say the full address to open, starting with https://", False
        return f"cannot do {intent}", False

    async def mouse(self, x: float, y: float) -> None:
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self.cdp.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1},
                                session=self.page)

    async def key(self, name: str) -> None:
        code = {"Enter": 13}[name]
        for kind in ("keyDown", "keyUp"):
            await self.cdp.send("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": name, "windowsVirtualKeyCode": code,
                                                           **({"text": "\r"} if kind == "keyDown" else {})}, session=self.page)
