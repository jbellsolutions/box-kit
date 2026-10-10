"""Capture the exact LLM requests Stagehand 4.2.0 (Python SDK) makes, while proving the
client-LLM callback route to OpenRouter works end to end.

Stagehand's `model=` accepts an async callable (ClientLLM). Every act/observe/extract
inference is handed to it as LLMStructuredGenerateParams (system_prompt, messages,
response_format{name, schema}). This script:
  1. launches a local headless Chrome for Testing through stagehand.local_browser,
  2. records each request verbatim to <out>/captures/NN_<name>.json,
  3. forwards it to OpenRouter (default z-ai/glm-5.3-flash, reasoning effort low,
     json_schema strict, provider.require_parameters=true) and returns the result,
  4. logs per-call latency/cost/provider to <out>/capture_calls.jsonl.

Public test pages only. The key is read from the env (or browser-box/.env) into this
process and never printed.

Usage: python capture_stagehand.py <out_dir> [model]
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from stagehand import (LLMStructuredGenerateParams, LLMStructuredGenerateResult, LLMTextContent,
                       LLMUsage, LLMRole, Stagehand, local_browser)

CHROME = os.environ["CHROME_BIN"]  # path to a Chrome for Testing binary
ENV_FILE = os.environ.get("ENV_FILE", ".env")
OUT = Path(sys.argv[1])
MODEL = sys.argv[2] if len(sys.argv) > 2 else "z-ai/glm-5.3-flash"
(OUT / "captures").mkdir(parents=True, exist_ok=True)
COUNTER = {"n": 0, "label": ""}


def load_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in open(ENV_FILE):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no key")


KEY = load_key()


def to_openai_messages(params: LLMStructuredGenerateParams) -> list[dict]:
    msgs = []
    if params.system_prompt:
        msgs.append({"role": "system", "content": params.system_prompt})
    for m in params.messages:
        d = m.model_dump(mode="json", by_alias=True)
        blocks = d["content"] if isinstance(d["content"], list) else [d["content"]]
        parts = []
        for b in blocks:
            if b["type"] == "text":
                parts.append({"type": "text", "text": b["text"]})
            elif b["type"] == "image":
                parts.append({"type": "image_url",
                              "image_url": {"url": f"data:{b.get('mimeType') or b.get('mime_type')};base64,{b['data']}"}})
        content = parts[0]["text"] if len(parts) == 1 and parts[0]["type"] == "text" else parts
        msgs.append({"role": d["role"], "content": content})
    return msgs


async def generate(params: LLMStructuredGenerateParams) -> LLMStructuredGenerateResult:
    if not isinstance(params, LLMStructuredGenerateParams):
        raise TypeError("only structured generation is used by act/observe/extract")
    COUNTER["n"] += 1
    rf = params.response_format
    schema = rf.schema_.model_dump(mode="json", by_alias=True) if hasattr(rf.schema_, "model_dump") else rf.schema_
    record = {"label": COUNTER["label"], "name": rf.name, "system_prompt": params.system_prompt,
              "messages": [m.model_dump(mode="json", by_alias=True) for m in params.messages],
              "temperature": params.temperature, "schema": schema}
    path = OUT / "captures" / f"{COUNTER['n']:02d}_{COUNTER['label']}_{rf.name}.json"
    path.write_text(json.dumps(record, indent=1))

    body = {"model": MODEL, "messages": to_openai_messages(params),
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": rf.name, "strict": True, "schema": schema}},
            "reasoning": {"effort": "low"}, "max_tokens": 8000,
            "provider": {"require_parameters": True}, "usage": {"include": True}}
    t0 = time.time()
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=body,
                              headers={"Authorization": f"Bearer {KEY}"})
    dt = time.time() - t0
    data = r.json()
    if r.status_code != 200 or "choices" not in data:
        (OUT / "capture_calls.jsonl").open("a").write(json.dumps({"file": path.name, "status": r.status_code, "error": data.get("error")}) + "\n")
        raise RuntimeError(f"OpenRouter error {r.status_code}")
    choice = data["choices"][0]
    text = choice["message"].get("content") or ""
    usage = data.get("usage") or {}
    (OUT / "capture_calls.jsonl").open("a").write(json.dumps({
        "file": path.name, "model": MODEL, "provider": data.get("provider"), "latency_s": round(dt, 2),
        "finish_reason": choice.get("finish_reason"), "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "cost": usage.get("cost"), "content": text[:3000]}) + "\n")
    return LLMStructuredGenerateResult.model_validate({
        "role": LLMRole.assistant, "content": LLMTextContent(type="text", text=text),
        "output_format": "json_schema", "structured_content": json.loads(text),
        "stop_reason": choice.get("finish_reason"),
        "usage": LLMUsage(input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0),
                          total_tokens=usage.get("total_tokens", 0)),
    })


class Book(BaseModel):
    title: str
    price: str


class Books(BaseModel):
    books: list[Book]


class Quote(BaseModel):
    text: str
    author: str


class Quotes(BaseModel):
    quotes: list[Quote]


async def step(label, coro):
    COUNTER["label"] = label
    t0 = time.time()
    try:
        res = await coro
        out = res.data.model_dump(mode="json", by_alias=True) if hasattr(res.data, "model_dump") else (
            [a.model_dump(mode="json", by_alias=True) for a in res.data] if isinstance(res.data, list) else res.data)
        ok = True
    except Exception as exc:  # record and continue
        out, ok = f"{type(exc).__name__}: {exc}"[:1500], False
    rec = {"label": label, "ok": ok, "wall_s": round(time.time() - t0, 2), "result": out}
    (OUT / "capture_steps.jsonl").open("a").write(json.dumps(rec, default=str) + "\n")
    print(label, ok, rec["wall_s"], str(out)[:300])


async def main() -> None:
    browser = await local_browser.launch(headless=True, executable_path=CHROME)
    try:
        sh = await Stagehand.create(browser=browser, model=generate)
        try:
            page = (await browser.context.pages())[0]
            await page.goto("https://books.toscrape.com/")
            await step("books_observe_categories", sh.observe("find the category links for Travel and Poetry"))
            await step("books_extract", sh.extract("extract the title and price of every book on this page", Books))
            await step("books_act_book", sh.act("click the link to the book 'Tipping the Velvet'"))
            await page.goto("https://books.toscrape.com/")
            await step("books_act_negative", sh.act("click the 'Log out' button"))
            await page.goto("https://quotes.toscrape.com/")
            await step("quotes_extract", sh.extract("extract every quote's text and author on this page", Quotes))
            await page.goto("https://the-internet.herokuapp.com/dropdown")
            await step("dropdown_act", sh.act("select 'Option 2' from the dropdown"))
            await page.goto("https://the-internet.herokuapp.com/inputs")
            await step("inputs_act", sh.act("type 42 into the number field"))
        finally:
            await sh.close()
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
