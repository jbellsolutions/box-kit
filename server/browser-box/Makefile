# Every answer to "is it running?" lives in this file.
SHELL := /bin/bash
COMPOSE := docker compose
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

# From .env, so `make jev-image` and compose agree on the commit.
JEV_DIR ?= $(shell grep -E '^JEV_DIR=' .env 2>/dev/null | cut -d= -f2-)
JEV_REF ?= $(shell grep -E '^JEV_REF=' .env 2>/dev/null | cut -d= -f2-)

up: .env ## Build and start the stack
	@if grep -qE '^COMPOSE_PROFILES=.*jev' .env; then $(MAKE) --no-print-directory jev-image; fi
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory status

down: ## Stop the stack (volumes survive)
	$(COMPOSE) down

restart-browser: ## The one recovery action for a wedged browser
	$(COMPOSE) restart steel

logs: ## Tail all logs
	$(COMPOSE) logs -f --tail=100

logs-steel: ## Tail the browser's logs
	$(COMPOSE) logs -f --tail=100 steel

status: ## What is up, and what the gateway says about itself
	@echo "── containers ─────────────────────────────"
	@$(COMPOSE) ps
	@echo
	@echo "── resource use ───────────────────────────"
	@docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' $$($(COMPOSE) ps -q 2>/dev/null) 2>/dev/null || true
	@echo
	@echo "── gateway /status ────────────────────────"
	@curl -fsS -H "Authorization: Bearer $$(grep -E '^BB_TOKEN=' .env | cut -d= -f2-)" http://127.0.0.1:8080/status | python3 -m json.tool || echo "gateway not answering"

test: ## Run the gateway test suite (no Docker, no browser needed)
	PYTHONPATH=gateway $(PY) -m unittest discover -s tests -t . -v

venv: ## Local venv for `make test`
	python3 -m venv .venv && .venv/bin/pip install -q -r gateway/requirements.txt

openapi: ## Regenerate docs/openapi.json from the tool cards (the CLI is generated from it)
	PYTHONPATH=gateway $(PY) -c "import json; from gateway import rest; open('docs/openapi.json','w').write(json.dumps(rest.openapi(), indent=2)+'\\n')"

plugin: ## Validate the plugin and marketplace manifests
	claude plugin validate .

caddy-check: ## Validate the Caddyfile as it will actually be installed
	sed "s|{\$$BB_DOMAIN}|example.com|" Caddyfile | caddy validate --config /dev/stdin --adapter caddyfile

smoke: ## Prove `read` end to end through the MCP endpoint (M3 gate)
	@scripts/smoke.sh

jev-image: ## Build agent-jev from JEV_DIR at exactly JEV_REF (its working files are never read)
	@test -n "$(JEV_REF)" || { echo "set JEV_REF in .env: the jev-automation commit to build" >&2; exit 1; }
	@git -C "$(JEV_DIR)" cat-file -e "$(JEV_REF)^{commit}" 2>/dev/null || { echo "JEV_REF=$(JEV_REF) is not a commit in $(JEV_DIR)" >&2; exit 1; }
	git -C "$(JEV_DIR)" archive "$(JEV_REF)" | docker build -q -t "browser-box-jev:$(JEV_REF)" -

shield-check: ## Attack the running browser from inside the box: every private route must be refused (deploy gate; relaunches Chromium twice)
	@git -C "$(JEV_DIR)" show "$(JEV_REF):scripts/steel-shield-check.ts" > .shield-check.ts
	@$(COMPOSE) --profile jev run --rm --no-deps -e STEEL_URL=http://steel:3000 \
	  -v "$$PWD/.shield-check.ts:/app/scripts/steel-shield-check.ts:ro" agent-jev tsx scripts/steel-shield-check.ts; \
	  rc=$$?; rm -f .shield-check.ts; exit $$rc

guard-check: ## shield-check with Jev's own guard OFF: proves the gateway's in-browser guard refuses every case alone
	@git -C "$(JEV_DIR)" show "$(JEV_REF):scripts/steel-shield-check.ts" > .shield-check.ts
	@$(COMPOSE) --profile jev run --rm --no-deps -e STEEL_URL=http://steel:3000 -e JEV_SHIELD=off -e GUARD_SETTLE_MS=4000 \
	  -v "$$PWD/.shield-check.ts:/app/scripts/steel-shield-check.ts:ro" agent-jev tsx scripts/steel-shield-check.ts; \
	  rc=$$?; rm -f .shield-check.ts; exit $$rc

token: ## Generate a BB_TOKEN value
	@openssl rand -hex 32

.env:
	@echo "No .env. Copy .env.example to .env and set BB_TOKEN (make token)." >&2
	@exit 1

.PHONY: help up down restart-browser logs logs-steel status test venv plugin caddy-check smoke token jev-image shield-check guard-check
