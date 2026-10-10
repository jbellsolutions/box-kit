# Browser-Use 0.13.x attached by cdp_url; navigate to the bot test, then run the per-step DOM/state
# extraction an agent step performs (get_browser_state_summary, no LLM), then read the verdict.
import asyncio, json, re, sys
from browser_use import BrowserSession

async def main(url: str):
    s = BrowserSession(cdp_url=url, keep_alive=True)
    await s.start()
    await s.navigate_to('https://deviceandbrowserinfo.com/are_you_a_bot')
    await asyncio.sleep(3)
    st = await s.get_browser_state_summary(include_screenshot=True)
    n_el = len(st.dom_state.selector_map) if st and st.dom_state else None
    await asyncio.sleep(30)
    st2 = await s.get_browser_state_summary(include_screenshot=False)
    cdp = await s.get_or_create_cdp_session()
    r = await cdp.cdp_client.send.Runtime.evaluate(params={'expression': 'document.body.innerText', 'returnByValue': True}, session_id=cdp.session_id)
    txt = r.get('result', {}).get('value', '')
    m = re.search(r'\{\s*"isBot"[\s\S]*?\n\}', txt)
    p = json.loads(m.group(0)) if m else None
    print(json.dumps({'driver': 'browser-use BrowserSession(cdp_url) + get_browser_state_summary x2', 'interactive_elements': n_el, 'isBot': p and p['isBot'], 'flagged': [k for k, v in p['details'].items() if v] if p else txt[:200]}))
    await s.stop()

asyncio.run(main(sys.argv[1]))
