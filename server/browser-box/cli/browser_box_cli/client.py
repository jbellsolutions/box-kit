"""Talk to a browser-box gateway over MCP.

Deliberately the same path an agent uses — MCP over streamable HTTP with a bearer token —
so the CLI is not a second, privileged way in that can drift from what agents see.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

CONFIG = Path(os.getenv("BB_CONFIG") or (Path.home() / ".config" / "browser-box" / "config.json"))


class NotConfigured(RuntimeError):
    pass


def settings() -> dict:
    """Env wins, then ~/.config/browser-box/config.json, then a local .env in this repo."""
    data: dict[str, str] = {}
    if CONFIG.is_file():
        try:
            data.update(json.loads(CONFIG.read_text()))
        except (OSError, ValueError):
            pass
    env_file = Path.cwd() / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.startswith("BB_TOKEN=") and "token" not in data:
                data["token"] = line.split("=", 1)[1].strip()
    if os.getenv("BB_URL"):
        data["url"] = os.environ["BB_URL"]
    if os.getenv("BB_TOKEN"):
        data["token"] = os.environ["BB_TOKEN"]
    data.setdefault("url", "http://127.0.0.1:8080")
    if not data.get("token"):
        raise NotConfigured(
            "No token. Set BB_TOKEN, or run: bb login --url https://your-box/mcp --token <BB_TOKEN>"
        )
    return data


def endpoint(url: str) -> str:
    return url if url.rstrip("/").endswith("/mcp") else url.rstrip("/") + "/mcp"


@asynccontextmanager
async def session():
    conf = settings()
    url = endpoint(conf["url"])
    headers = {"Authorization": f"Bearer {conf['token']}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client


async def call(name: str, arguments: dict) -> dict:
    """Run one tool and return its parsed result. Refusals arrive as {"error": ...}."""
    async with session() as client:
        result = await client.call_tool(name, arguments)
    blocks = result.content or []
    text = next((b.text for b in blocks if getattr(b, "type", "") == "text"), "{}")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = {"text": text}
    # Screenshots arrive as real image blocks (so agents can see them). The CLI writes them
    # to a file, so fold the first one back into the dict under the key the CLI expects.
    image = next((b for b in blocks if getattr(b, "type", "") == "image"), None)
    if image is not None and isinstance(parsed, dict):
        parsed["screenshot_base64"] = image.data
        parsed.setdefault("screenshot_media_type", image.mimeType)
    return parsed


async def tool_list() -> list:
    async with session() as client:
        return list((await client.list_tools()).tools)
