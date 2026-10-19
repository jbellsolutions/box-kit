# Running Box Kit on a server

Use a server when agents on other machines need to reach the boxes. On your own computer,
`make up` is all you need.

## Size

- **browser-box** runs no browser: its browsers are hosted (Browser Use Cloud, Browserbase as the
  backup). Measured on a 1 vCPU / 2 GB server with 2 GB swap: 10 reads at once in 4 s, 4 browser
  tasks at once in 73 s, the Browser-Use agent peaking at about 450 MB (roughly 110 MB a task).
  Idle, the gateway is about 45 MB.
- **data-box** runs no browser and is capped at 600 MB.
- Both on one server: 1 vCPU / 2 GB with 2 GB of swap is enough to start; watch `docker stats`
  before adding more work.

## Steps (Ubuntu 24.04)

```bash
# Docker, swap, firewall
curl -fsSL https://get.docker.com | sudo sh
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile \
  && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw --force enable

# The kit
git clone https://github.com/jbellsolutions/box-kit && cd box-kit
make up && make status
```

### No egress firewall to add

No browser runs on the server, so there is no browser network to fence off. The gateway checks
every address it is asked to open, on every redirect, and refuses loopback, private, link-local
and file addresses; the hosted browsers live on the providers' networks, not yours. If an older
kit left `iptables` rules for a Steel subnet, they are harmless and can be removed.

### HTTPS

Install Caddy on the host and give each server a name (a real domain, or
`<your-ip-with-dashes>.sslip.io`):

```
browser.example.com {
    reverse_proxy 127.0.0.1:8080
}
data.example.com {
    reverse_proxy 127.0.0.1:8092
}
```

Then point agents at `https://browser.example.com/mcp` and `https://data.example.com/mcp`
with the tokens from `make env`.

## Keys

Add them to `server/browser-box/.env` and `server/data-box/.env`, then `make up` again. To start
browsing, browser-box needs only `BROWSER_USE_API_KEY` (pay as you go, no subscription); add
`BROWSERBASE_API_KEY` for the backup lane. On Browserbase's Free plan, also set
`BB_BROWSERBASE_MONTHLY_HOURS=1` and `BB_BROWSERBASE_MAX_CONCURRENT=3` to match it. Each
file lists every key it understands and what it switches on. `status` on each server shows
what is configured and what it has spent recently.

## Tokens

One token per server; anyone holding it can use that server and the keys on it. To cut
everyone off, put a new value in the `.env` (`openssl rand -hex 32`), `make up`, and give the
new value to the agents that should keep access.

## Updating

```bash
git pull && make up
```
