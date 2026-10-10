// Tiny raw CDP query helper: node cdpq.mjs <ws> <Method> '<paramsJSON>'
const [u, method, params] = process.argv.slice(2);
const ws = new WebSocket(u);
ws.onopen = () => ws.send(JSON.stringify({ id: 1, method, params: JSON.parse(params || '{}') }));
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id === 1) { console.log(JSON.stringify(d).slice(0, 3000)); ws.close(); process.exit(0); } };
setTimeout(() => { console.log('timeout'); process.exit(1); }, 8000);
