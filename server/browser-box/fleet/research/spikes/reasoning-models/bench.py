"""Replay frozen Stagehand 4.2.0 / Browser-Use 0.13.11 LLM requests against OpenRouter models.

Inputs are the byte-for-byte requests captured by capture_stagehand.py / capture_browseruse.py
(real accessibility trees from books.toscrape.com, quotes.toscrape.com,
the-internet.herokuapp.com), so every model sees identical prompts and schemas.
Each call: response_format json_schema strict, provider.require_parameters=true,
usage.include=true. Scoring = JSON parses directly, validates against the exact schema
(jsonschema Draft 2020-12), finish_reason != length, and the task-specific correct answer.

Usage: python bench.py <data_dir> <out_jsonl> <runs> <config_names|all> <task_names|all|text|vision> [budget_usd]
The key is read from env or browser-box/.env and never printed.
"""
import base64
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import jsonschema

ENV_FILE = os.environ.get("ENV_FILE", ".env")
DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])
RUNS = int(sys.argv[3])
CONF_SEL = sys.argv[4]
TASK_SEL = sys.argv[5]
BUDGET = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5


def load_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in open(ENV_FILE):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = load_key()

# model configs: fastest sensible reasoning setting per model (off where allowed, low where mandatory)
CONFIGS = {
    "glm-5.3-flash@low": {"model": "z-ai/glm-5.3-flash", "reasoning": {"effort": "low"}, "vision": True},
    "glm-5.3-flash@low-t0": {"model": "z-ai/glm-5.3-flash", "reasoning": {"effort": "low"}, "temperature": 0.0, "vision": True},
    "glm-5.3-flash@high": {"model": "z-ai/glm-5.3-flash", "reasoning": {"effort": "high"}, "vision": True},
    "mimo-v2.6-flash@off": {"model": "xiaomi/mimo-v2.6-flash", "reasoning": {"enabled": False}, "vision": True},
    "qwen3.8-flash@off": {"model": "qwen/qwen3.8-flash", "reasoning": {"enabled": False}, "vision": True},
    "deepseek-v4.1-flash@off": {"model": "deepseek/deepseek-v4.1-flash", "reasoning": {"enabled": False}, "vision": True},
    "deepseek-v4.1-flash@low": {"model": "deepseek/deepseek-v4.1-flash", "reasoning": {"effort": "low"}, "vision": True},
    "gemma-4-31b@default": {"model": "google/gemma-4-31b-it", "reasoning": None, "vision": True},
    "gpt-oss-120b@low": {"model": "openai/gpt-oss-120b", "reasoning": {"effort": "low"}, "vision": False},
    "nemotron-3.5-lightning@off": {"model": "nvidia/nemotron-3.5-lightning", "reasoning": {"enabled": False}, "vision": False},
    "mistral-small-2603@none": {"model": "mistralai/mistral-small-2603", "reasoning": {"effort": "none"}, "vision": True},
    "REF-closed:gpt-6-luna@none": {"model": "openai/gpt-6-luna", "reasoning": {"effort": "none"}, "vision": True},
}


def stagehand_task(capture: str, replace: tuple[str, str] | None = None) -> dict:
    d = json.loads((DATA / "captures" / capture).read_text())
    msgs = [{"role": "system", "content": d["system_prompt"]}]
    for m in d["messages"]:
        c = m["content"]
        text = c["text"] if isinstance(c, dict) else c
        if replace:
            assert replace[0] in text, replace[0]
            text = text.replace(replace[0], replace[1])
        msgs.append({"role": m["role"], "content": text})
    return {"messages": msgs, "schema_name": d["name"], "schema": d["schema"], "max_tokens": 8000}


def bu_task(path: str) -> dict:
    body = json.loads((DATA / path).read_text())
    js = body["response_format"]["json_schema"]
    return {"messages": body["messages"], "schema_name": js["name"], "schema": js["schema"],
            "max_tokens": body.get("max_completion_tokens", 4096), "bu": True}


def vision_extract_task() -> dict:
    """Stagehand extract-with-screenshot shape (prompt.ts buildExtractSystemPrompt(includeScreenshot=true)
    + buildExtractUserPrompt(screenshot)), on the books tree, asking for something only the pixels show."""
    t = stagehand_task("02_books_extract_Extraction.json")
    sys_p = t["messages"][0]["content"].replace(
        "A list of DOM elements to extract from.",
        "A list of DOM elements to extract from and a screenshot of the current viewport to extract from. "
        "Use them together to extract content from the page.")
    user = t["messages"][1]["content"].replace(
        "Instruction: extract the title and price of every book on this page",
        "Instruction: extract the title and the star rating (number of filled stars, 1 to 5) of each of the "
        "four books in the first row of products")
    user += "\nUse the screenshot of the current viewport together with the accessibility tree to extract content from the page."
    img = base64.b64encode((DATA / "books_viewport.png").read_bytes()).decode()
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
              "properties": {"books": {"type": "array", "items": {"type": "object", "properties": {
                  "title": {"type": "string"}, "rating": {"type": "integer"}},
                  "required": ["title", "rating"], "additionalProperties": False}}},
              "required": ["books"], "additionalProperties": False}
    return {"messages": [{"role": "system", "content": sys_p},
                         {"role": "user", "content": [{"type": "text", "text": user},
                                                      {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]}],
            "schema_name": "Extraction", "schema": schema, "max_tokens": 8000, "vision": True}


def vision_click_task() -> dict:
    img = base64.b64encode((DATA / "books_viewport.png").read_bytes()).decode()
    schema = {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
              "required": ["x", "y"], "additionalProperties": False}
    return {"messages": [{"role": "system", "content": "You control a web browser by clicking pixel coordinates. "
                                                        "The screenshot is exactly 1280 pixels wide and 1024 pixels tall. "
                                                        "Return the x,y pixel coordinates (origin top-left) to click."},
                         {"role": "user", "content": [{"type": "text", "text": "Click the 'Add to basket' button for the book 'Sharp Objects'."},
                                                      {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]}],
            "schema_name": "Click", "schema": schema, "max_tokens": 4000, "vision": True}


GT = json.loads((DATA / "ground_truth.json").read_text())
VT = json.loads((DATA / "vision_truth.json").read_text())
OLD_ACT = "given the following action: click the link to the book 'Tipping the Velvet'."
TASKS = {
    "sh_observe_categories": stagehand_task("01_books_observe_categories_Observation.json"),
    "sh_act_book_link": stagehand_task("04_books_act_book_Act.json"),
    "sh_act_sharp_basket": stagehand_task("04_books_act_book_Act.json", (OLD_ACT, "given the following action: click the 'Add to basket' button for the book 'Sharp Objects'.")),
    "sh_act_negative": stagehand_task("05_books_act_negative_Act.json"),
    "sh_act_dropdown": stagehand_task("08_dropdown_act_Act.json"),
    "sh_act_type": stagehand_task("09_inputs_act_Act.json"),
    "sh_extract_books": stagehand_task("02_books_extract_Extraction.json"),
    "sh_extract_quotes": stagehand_task("06_quotes_extract_Extraction.json"),
    "bu_step_poetry": bu_task("bu_request_01.json"),
    "v_extract_ratings": vision_extract_task(),
    "v_click_coords": vision_click_task(),
}


def norm(s: str) -> str:
    return re.sub(r"[\s“”\"'’‘.…]+", " ", s or "").strip().lower()


def score(task: str, obj) -> tuple[float, str]:
    """Return (score 0..1, note)."""
    if task == "sh_observe_categories":
        ids = sorted(e["elementId"] for e in obj["elements"])
        junk = [e["arguments"][:2] for e in obj["elements"] if e["method"] == "click" and e["arguments"] and e["arguments"][0] not in ("", "left")]
        if junk:
            return 0.0, f"junk click args {junk}"
        return (1.0 if ids == ["0-175", "0-91"] else 0.0), ",".join(ids)
    # Stagehand executes only arguments[0] (actHandlerUtils.ts); click passes it to CDP as the mouse
    # button, so a click whose arguments[0] is not ""/"left" would fail or mis-click (scored wrong).
    if task.startswith("sh_act"):
        a = obj["action"]
        if a and a["method"] == "click" and a["arguments"] and a["arguments"][0] not in ("", "left"):
            return 0.0, f"junk click args {a['arguments'][:4]}"
        if task == "sh_act_negative":
            return (1.0 if a is None else 0.0), "null" if a is None else f"{a['elementId']}/{a['method']}"
        if a is None:
            return 0.0, "null"
        note = f"{a['elementId']}/{a['method']}/{a['arguments']}"
        if task == "sh_act_book_link":
            ok = a["elementId"] in ("0-348", "0-362", "0-349") and a["method"] in ("click", "doubleClick")
        elif task == "sh_act_sharp_basket":
            ok = a["elementId"] == "0-433" and a["method"] == "click"
        elif task == "sh_act_dropdown":
            ok = a["elementId"] == "0-77" and a["method"] == "selectOptionFromDropdown" and a["arguments"][:1] == ["Option 2"]
        elif task == "sh_act_type":
            ok = a["elementId"] == "0-218" and a["method"] in ("fill", "type") and a["arguments"][:1] == ["42"]
        return (1.0 if ok else 0.0), note
    if task == "sh_extract_books":
        got = obj.get("books") or []
        hit = 0
        for g in GT["books"]:
            for b in got:
                bt = norm(b.get("title", ""))
                if b.get("price", "").strip() == g["price"] and bt and (bt == norm(g["title"]) or norm(g["title"]).startswith(bt)):
                    hit += 1
                    break
        return hit / len(GT["books"]), f"{hit}/{len(GT['books'])} matched, {len(got)} returned"
    if task == "sh_extract_quotes":
        got = obj.get("quotes") or []
        hit = sum(1 for g in GT["quotes"] if any(norm(q.get("text", "")) == norm(g["text"]) and norm(q.get("author", "")) == norm(g["author"]) for q in got))
        return hit / len(GT["quotes"]), f"{hit}/{len(GT['quotes'])} matched, {len(got)} returned"
    if task == "bu_step_poetry":
        acts = obj.get("action") or []
        first = acts[0] if acts else {}
        ok = (first.get("click") or {}).get("index") == 347 or "poetry" in json.dumps(first.get("navigate") or {}).lower()
        return (1.0 if ok else 0.0), json.dumps(acts)[:200]
    if task == "v_extract_ratings":
        words = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        want = {norm(b["title"]): words[b["rating"]] for b in VT["books"]}
        got = {norm(b["title"]): b["rating"] for b in obj.get("books") or []}
        hit = sum(1 for t, r in want.items() if any((gt == t or t.startswith(gt)) and gr == r for gt, gr in got.items()))
        return hit / 4, json.dumps([b.get("rating") for b in obj.get("books") or []])
    if task == "v_click_coords":
        bb = VT["sharp_add_to_basket_bbox"]
        x, y = obj["x"], obj["y"]
        inside = lambda px, py: bb["x"] <= px <= bb["x"] + bb["w"] and bb["y"] <= py <= bb["y"] + bb["h"]
        ok = inside(x, y)
        alt = inside(x * 1280 / 1000, y * 1024 / 1000)
        return (1.0 if ok else 0.0), f"({x},{y}) pixel_hit={ok} norm1000_hit={alt}"
    raise KeyError(task)


SPENT = {"usd": 0.0}
LOCK = threading.Lock()


def call(conf_name: str, task_name: str, run: int) -> dict:
    conf, task = CONFIGS[conf_name], TASKS[task_name]
    body = {"model": conf["model"], "messages": task["messages"],
            "response_format": {"type": "json_schema", "json_schema": {"name": task["schema_name"], "strict": True, "schema": task["schema"]}},
            "max_tokens": task["max_tokens"], "provider": {"require_parameters": True}, "usage": {"include": True}}
    if conf["reasoning"] is not None:
        body["reasoning"] = conf["reasoning"]
    if conf.get("temperature") is not None:
        body["temperature"] = conf["temperature"]
    rec = {"config": conf_name, "model": conf["model"], "task": task_name, "run": run, "ts": time.strftime("%H:%M:%S")}
    t_all = time.time()
    rec["attempts"] = 0
    for attempt in range(3):  # retry 429/5xx twice, like an SDK client would; latency = final attempt
        rec["attempts"] = attempt + 1
        t0 = time.time()
        try:
            r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=180,
                           headers={"Authorization": f"Bearer {KEY}"})
            rec["latency_s"] = round(time.time() - t0, 2)
            data = r.json()
        except Exception as exc:
            rec.update(latency_s=round(time.time() - t0, 2), http_error=f"{type(exc).__name__}: {exc}"[:300], score=0.0, valid=False)
            return rec
        err_code = (data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None
        if r.status_code in (429, 500, 502, 503) or err_code in (429, 500, 502, 503):
            rec.setdefault("retried_errors", []).append(str(err_code or r.status_code))
            time.sleep(3 * (attempt + 1))
            continue
        break
    rec["total_s"] = round(time.time() - t_all, 2)
    rec["status"] = r.status_code
    if r.status_code != 200 or "choices" not in data:
        rec.update(error=json.dumps(data.get("error") or data)[:600], score=0.0, valid=False)
        return rec
    ch = data["choices"][0]
    usage = data.get("usage") or {}
    content = (ch.get("message") or {}).get("content") or ""
    rec.update(provider=data.get("provider"), finish_reason=ch.get("finish_reason"),
               prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
               reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
               cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
               cost=usage.get("cost"), content=content[:6000])
    with LOCK:
        SPENT["usd"] += float(usage.get("cost") or 0)
    obj, rec["parse"] = None, "fail"
    try:
        obj = json.loads(content)
        rec["parse"] = "direct"
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                rec["parse"] = "lenient"
            except Exception:
                pass
    rec["valid"] = False
    if obj is not None:
        try:
            jsonschema.Draft202012Validator(task["schema"]).validate(obj)
            rec["valid"] = rec["parse"] == "direct" and ch.get("finish_reason") != "length"
        except jsonschema.ValidationError as exc:
            rec["schema_error"] = str(exc.message)[:300]
    try:
        s, note = score(task_name, obj) if obj is not None else (0.0, "unparsable")
    except Exception as exc:
        s, note = 0.0, f"score error {type(exc).__name__}: {exc}"[:200]
    rec["score_raw"], rec["note"] = s, note
    rec["score"] = s if rec["valid"] else 0.0  # Stagehand/BU would reject invalid output
    return rec


def main() -> None:
    confs = list(CONFIGS) if CONF_SEL == "all" else CONF_SEL.split(",")
    if TASK_SEL == "all":
        tasks = list(TASKS)
    elif TASK_SEL == "text":
        tasks = [t for t in TASKS if not TASKS[t].get("vision")]
    elif TASK_SEL == "vision":
        tasks = [t for t in TASKS if TASKS[t].get("vision")]
    else:
        tasks = TASK_SEL.split(",")
    jobs = [(c, t, r) for c in confs for t in tasks for r in range(RUNS)
            if not (TASKS[t].get("vision") and not CONFIGS[c]["vision"])]
    random.seed(7)
    random.shuffle(jobs)
    print(f"{len(jobs)} calls; budget ${BUDGET}")
    out = OUT.open("a")

    def work(job):
        if SPENT["usd"] > BUDGET:
            return None
        rec = call(*job)
        with LOCK:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
        print(f"{rec['config']:<28} {rec['task']:<22} r{rec['run']} {rec.get('latency_s')}s "
              f"valid={rec.get('valid')} score={rec.get('score')} prov={rec.get('provider')} "
              f"cost={rec.get('cost')} {rec.get('note') or rec.get('error') or rec.get('schema_error') or ''}"[:260], flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(work, jobs))
    print(f"spent this run (sum of usage.cost): ${SPENT['usd']:.5f}")


if __name__ == "__main__":
    main()
