// Read deviceandbrowserinfo.com/are_you_a_bot with a raw CDP client that never calls Runtime.enable
// (only Target.* + Runtime.evaluate), to isolate what the browser host (Steel) leaks by itself.
const [base, bodyJson] = process.argv.slice(2);
const post = (p, b) => fetch(base + '/v1' + p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b || {}) }).then(r => r.json());
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const s = await post('/sessions', JSON.parse(bodyJson || '{}'));
await sleep(1500);
const ws = new WebSocket(base.replace('http', 'ws') + '/');
let id = 0; const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
const send = (method, params = {}, sessionId) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params, ...(sessionId ? { sessionId } : {}) })); });
const { result: { targetId } } = await send('Target.createTarget', { url: 'https://deviceandbrowserinfo.com/are_you_a_bot' });
await sleep(20000);
const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
const r = await send('Runtime.evaluate', { expression: 'document.body.innerText', returnByValue: true }, sessionId);
const txt = r.result?.result?.value || JSON.stringify(r);
const m = txt.match(/\{\s*"isBot"[\s\S]*?\n\}/);
let parsed = null; try { parsed = JSON.parse(m[0]); } catch {}
const flagged = parsed ? Object.entries(parsed.details).filter(([k, v]) => v).map(([k]) => k) : null;
console.log(JSON.stringify({ session: s.id, ua: s.userAgent, isBot: parsed?.isBot, flagged, raw: parsed ? undefined : txt.slice(0, 600) }));
await send('Target.closeTarget', { targetId }); ws.close();
await post('/sessions/release');
