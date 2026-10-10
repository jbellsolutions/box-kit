// Control: vanilla Chromium launched with only --remote-debugging-port (no Steel, no puppeteer),
// open the bot test via Target.createTarget, read the verdict 20s later with Runtime.evaluate only.
const port = process.argv[2];
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const v = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
const ws = new WebSocket(v.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
const send = (method, params = {}, sessionId) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params, ...(sessionId ? { sessionId } : {}) })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'https://deviceandbrowserinfo.com/are_you_a_bot' });
await sleep(20000);
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
const r = await send('Runtime.evaluate', { expression: 'document.body.innerText', returnByValue: true }, sessionId);
const txt = r.result?.result?.value || '';
const m = txt.match(/\{\s*"isBot"[\s\S]*?\n\}/);
let parsed = null; try { parsed = JSON.parse(m[0]); } catch {}
console.log(JSON.stringify({ browser: v.Browser, isBot: parsed?.isBot, flagged: parsed ? Object.entries(parsed.details).filter(([k, x]) => x).map(([k]) => k) : txt.slice(0, 300) }));
ws.close();
