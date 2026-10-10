// Send a few raw CDP commands to a browser websocket and print results.
const url = process.argv[2];
const cmds = JSON.parse(process.argv[3]);
const ws = new WebSocket(url);
let id = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
await new Promise((r, j) => { ws.onopen = r; ws.onerror = () => j(new Error("ws error")); });
for (const [method, params] of cmds) {
  const myId = ++id;
  const res = await new Promise((r) => { pending.set(myId, r); ws.send(JSON.stringify({ id: myId, method, params: params ?? {} })); setTimeout(() => r({ timeout: true }), 8000); });
  console.log(method, JSON.stringify(res.result ?? res.error ?? res).slice(0, 600));
}
ws.close(); process.exit(0);
