# Running Box Kit on a server

Use a server when agents on other machines need to reach the boxes. On your own computer,
`make up` is all you need.

## Size

- **browser-box** runs a real Chromium. Measured: the browser sat around 0.7 GB and climbed to
  about 1.1 GB during use; the Browser-Use agent peaked at about 330 MB. Give it **2 vCPU / 4 GB**.
  Not 1 vCPU / 2 GB: that is how a browser gets killed for memory mid-task.
- **data-box** runs no browser and is capped at 600 MB.
- Both on one server: start at 2 vCPU / 4 GB with 2 GB of swap, and watch `docker stats`
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

### Keep the browser off your private network — not optional

The server checks every address it is asked to open, but once the browser has a page,
Chromium does its own networking. Deny its container network everything private:

```bash
STEEL_NET=$(docker network inspect browser-box_box -f '{{(index .IPAM.Config 0).Subnet}}')
for range in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 127.0.0.0/8; do
  sudo iptables -I DOCKER-USER -s "$STEEL_NET" -d "$range" -j DROP
done
sudo iptables -I DOCKER-USER 1 -s "$STEEL_NET" -d "$STEEL_NET" -j ACCEPT   # must be line 1
sudo iptables -I INPUT -s "$STEEL_NET" -m conntrack --ctstate NEW -j DROP  # no reaching the host
sudo apt-get install -y iptables-persistent
```

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

Add them to `server/browser-box/.env` and `server/data-box/.env`, then `make up` again. Each
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
