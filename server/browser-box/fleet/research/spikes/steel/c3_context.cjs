// (c3) Session context export/import as the persistence unit (no volume).
// export: create {}, set cookie (+httpOnly via CDP), localStorage, IndexedDB on example.com, GET context -> file
// import: create {sessionContext: <file>}, check cookies before navigation, then navigate and check storage.
// Usage: node c3_context.cjs export <file> | node c3_context.cjs import <file>
const fs = require("fs");
const { chromium } = require("playwright-core");
const { api, WS, log, sleep } = require("./lib.cjs");
(async () => {
  const [mode, file] = process.argv.slice(2);
  if (mode === "export") {
    const s = await api("POST", "/v1/sessions", {});
    log("create", s.status, s.json.id);
    const b = await chromium.connectOverCDP(WS);
    const ctx = b.contexts()[0];
    const p = await ctx.newPage();
    await p.goto("https://example.com/");
    await ctx.addCookies([{ name: "ctx_httponly", value: "h1", domain: "example.com", path: "/", httpOnly: true, secure: true, sameSite: "Lax", expires: Math.floor(Date.now() / 1000) + 86400 * 30 }]);
    await p.evaluate(async () => {
      document.cookie = "ctx_js=j1; max-age=2592000; path=/";
      localStorage.setItem("ctx_ls", "l1");
      sessionStorage.setItem("ctx_ss", "s1");
      await new Promise((res, rej) => {
        const r = indexedDB.open("fleetdb", 1);
        r.onupgradeneeded = () => r.result.createObjectStore("kv");
        r.onsuccess = () => { const tx = r.result.transaction("kv", "readwrite"); tx.objectStore("kv").put({ token: "idb-v1" }, "auth"); tx.oncomplete = () => { r.result.close(); res(); }; tx.onerror = rej; };
        r.onerror = rej;
      });
    });
    const t0 = Date.now();
    const c = await api("GET", `/v1/sessions/${s.json.id}/context`);
    log("GET context", c.status, (Date.now() - t0) + "ms", "bytes", JSON.stringify(c.json).length);
    const j = c.json;
    log("export keys:", JSON.stringify(Object.keys(j)),
      "cookies:", JSON.stringify((j.cookies || []).filter((x) => x.domain.includes("example.com")).map((x) => `${x.name}${x.httpOnly ? "(httpOnly)" : ""}`)),
      "localStorage origins:", JSON.stringify(Object.keys(j.localStorage || {})),
      "sessionStorage origins:", JSON.stringify(Object.keys(j.sessionStorage || {})),
      "indexedDB:", JSON.stringify(Object.fromEntries(Object.entries(j.indexedDB || {}).map(([k, v]) => [k, v.map((d) => d.name + ":" + d.data.map((st) => st.name + "#" + st.records.length).join(","))]))));
    fs.writeFileSync(file, JSON.stringify(j));
    const r = await api("POST", "/v1/sessions/release", {});
    log("release", r.status);
    await b.close().catch(() => {});
  } else {
    const ctxData = JSON.parse(fs.readFileSync(file, "utf8"));
    const s = await api("POST", "/v1/sessions", { sessionContext: ctxData });
    log("create with sessionContext", s.status, s.ms + "ms", s.json.id || JSON.stringify(s.json).slice(0, 300));
    const b = await chromium.connectOverCDP(WS);
    const ctx = b.contexts()[0];
    log("cookies before any navigation:", JSON.stringify((await ctx.cookies("https://example.com")).map((c) => c.name + (c.httpOnly ? "(httpOnly)" : "")).sort()));
    const p = await ctx.newPage();
    await p.goto("https://example.com/");
    await sleep(500);
    const st = await p.evaluate(async () => {
      const idb = await new Promise((res) => {
        const r = indexedDB.open("fleetdb");
        r.onsuccess = () => { try { const g = r.result.transaction("kv").objectStore("kv").get("auth"); g.onsuccess = () => res(JSON.stringify(g.result)); g.onerror = () => res("get-error"); } catch (e) { res("no-store: " + e.name); } };
        r.onerror = () => res("open-error");
      });
      return { ls: localStorage.getItem("ctx_ls"), ss: sessionStorage.getItem("ctx_ss"), idb };
    });
    log("after navigating to example.com: localStorage", st.ls, "sessionStorage", st.ss, "indexedDB fleetdb/kv/auth", st.idb);
    const r = await api("POST", "/v1/sessions/release", {});
    log("release", r.status);
    await b.close().catch(() => {});
  }
})().catch((e) => { console.error("FATAL", e); process.exit(1); });
