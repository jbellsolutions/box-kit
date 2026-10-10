#!/bin/sh
# (j) docker stats samples: idle (idle browser running), one example.com tab, one creepjs tab.
# Usage: j_resources.sh  (expects a fresh fleet-spike-steel container on 3300)
cd "$(dirname "$0")"
samp() { for i in 1 2 3 4 5; do echo "$(docker stats --no-stream --format '{{.MemUsage}} cpu={{.CPUPerc}} pids={{.PIDs}}' fleet-spike-steel) anon=$(docker exec fleet-spike-steel sh -c 'echo $(( $(grep "^anon " /sys/fs/cgroup/memory.stat | cut -d" " -f2) / 1048576 ))')MiB rss_sum=$(docker exec fleet-spike-steel sh -c 'ps -eo rss= | awk "{s+=\$1} END {print int(s/1024)}"')MiB"; sleep 2; done | tr '\n' ';'; echo; }
echo "idle (no session):"; samp
cat > /tmp/fleet-spike-steel-hold.cjs <<'JS'
const { chromium } = require("playwright-core");
(async () => {
  const url = process.argv[2]; const body = process.argv[3] || "{}";
  const r = await fetch("http://127.0.0.1:3300/v1/sessions", { method: "POST", headers: { "content-type": "application/json" }, body });
  console.log("create", r.status);
  const b = await chromium.connectOverCDP("ws://127.0.0.1:3300/");
  const p = b.contexts()[0].pages()[0];
  await p.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 }).catch((e) => console.log("goto", e.message.split("\n")[0]));
  await new Promise((r) => setTimeout(r, Number(process.argv[4] || 30000)));
  await fetch("http://127.0.0.1:3300/v1/sessions/release", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  console.log("released");
})();
JS
for u in https://example.com/ https://abrahamjuliot.github.io/creepjs/; do
  NODE_PATH="$NODE_PATH" node /tmp/fleet-spike-steel-hold.cjs "$u" '{}' 25000 & sleep 9; echo "one tab $u:"; samp; wait
done
rm -f /tmp/fleet-spike-steel-hold.cjs
