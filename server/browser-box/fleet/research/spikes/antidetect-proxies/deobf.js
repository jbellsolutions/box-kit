// Decode the string table of Steel's obfuscated fingerprint.js without executing its patches.
const fs = require('fs'); const vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8'); const L = src.split('\n');
const pick = (a,b) => L.slice(a-1,b).join('\n');
const code = pick(40,50) + '\n' + pick(55,318) + '\n' + pick(2,21) + '\nthis.dec=_0x5610;';
const ctx = {}; vm.createContext(ctx); vm.runInContext(code, ctx, {timeout: 2000});
let out = src.replace(/_0x[0-9a-f]+\((0x[0-9a-f]+)\)/g, (m, h) => { try { return JSON.stringify(ctx.dec(parseInt(h,16))); } catch(e){ return m; } });
for (let i=0;i<5;i++) out = out.replace(/"([^"\n]*)"\s*\+\s*"([^"\n]*)"/g, '"$1$2"');
fs.writeFileSync(process.argv[3], out);
