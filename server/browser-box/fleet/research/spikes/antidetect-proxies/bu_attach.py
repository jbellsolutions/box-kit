# Browser-Use 0.13.x BrowserSession attached by cdp_url -> navigate to bot test -> read verdict. No LLM call.
import asyncio, json, re, sys
from browser_use import BrowserSession

async def main(url: str):
    s = BrowserSession(cdp_url=url, keep_alive=True)
    await s.start()
    await s.navigate_to('https://deviceandbrowserinfo.com/are_you_a_bot')
    await asyncio.sleep(35)
    cdp = await s.get_or_create_cdp_session()
    r = await cdp.cdp_client.send.Runtime.evaluate(params={'expression': 'document.body.innerText', 'returnByValue': True}, session_id=cdp.session_id)
    txt = r.get('result', {}).get('value', '')
    m = re.search(r'\{\s*"isBot"[\s\S]*?\n\}', txt)
    p = json.loads(m.group(0)) if m else None
    print(json.dumps({'driver': 'browser-use BrowserSession(cdp_url)', 'isBot': p and p['isBot'], 'flagged': [k for k, v in p['details'].items() if v] if p else txt[:200]}))
    await s.stop()

asyncio.run(main(sys.argv[1]))
