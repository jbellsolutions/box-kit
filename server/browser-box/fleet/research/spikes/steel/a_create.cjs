// (a) create a session and print the response shape.
const { api, log } = require("./lib.cjs");
(async () => {
  const body = process.argv[2] ? JSON.parse(process.argv[2]) : {};
  const r = await api("POST", "/v1/sessions", body);
  log("create", r.status, r.ms + "ms", JSON.stringify(r.json));
  const s = await api("GET", "/v1/sessions");
  log("list", s.status, JSON.stringify(s.json.sessions?.map((x) => ({ id: x.id, status: x.status, proxy: x.proxy }))));
})();
