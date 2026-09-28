"""Prove the endpoint with a real MCP client: initialize, notifications, session headers, SSE negotiation."""
import asyncio, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

token = [l.split("=",1)[1].strip() for l in open(".env") if l.startswith("BB_TOKEN=")][0]

async def check(url):
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            out = (await s.call_tool("read", {"url": "https://example.com"})).content[0].text
            print(f"{url}\n  server: {init.serverInfo.name}\n  tools: {tools}\n  read: {out[:110]}\n")

async def main():
    for url in ("http://127.0.0.1:8080/mcp", "http://127.0.0.1:8080/mcp/"):
        await check(url)
    # And the token must still be required through a real client.
    try:
        async with streamablehttp_client("http://127.0.0.1:8080/mcp", headers={"Authorization": "Bearer wrong"}) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
        print("NO-TOKEN CHECK FAILED: an unauthorized client completed initialize")
        sys.exit(1)
    except Exception as exc:
        print("unauthorized client rejected:", type(exc).__name__, str(exc)[:80])

asyncio.run(main())
