// TCP forwarder 0.0.0.0:3000 -> 127.0.0.1:9222 so the host can reach a vanilla Chromium's CDP port.
const net = require('net');
net.createServer((c) => { const u = net.connect(9222, '127.0.0.1'); c.pipe(u); u.pipe(c); c.on('error', () => u.destroy()); u.on('error', () => c.destroy()); }).listen(3000, '0.0.0.0');
