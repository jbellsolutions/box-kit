"""Does Browser-Use apply ProxySettings.server to a REMOTE CDP browser? (no LLM)
A dead proxy (127.0.0.1:9 inside nothing) is configured; if example.com still loads, the setting was ignored."""
import asyncio, json, os, sys
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false"); os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")
from browser_use import Browser, Tools
from browser_use.browser.profile import ProxySettings

async def main():
    out = {}
    b = Browser(cdp_url=sys.argv[1], keep_alive=True, proxy=ProxySettings(server="http://127.0.0.1:9", username="u", password="p"))
    await asyncio.wait_for(b.start(), 30)
    tools = Tools(); AM = tools.registry.create_action_model()
    r = await asyncio.wait_for(tools.act(AM.model_validate({"navigate": {"url": "https://example.com/"}}), browser_session=b), 40)
    out["navigate_result"] = (r.error or r.extracted_content or "")[:160]
    st = await asyncio.wait_for(b.get_browser_state_summary(include_screenshot=False), 30)
    out["url"] = st.url; out["title"] = st.title
    out["proxy_ignored"] = "Example Domain" in (st.title or "")
    print(json.dumps(out), flush=True)
    os._exit(0)

asyncio.run(main())
