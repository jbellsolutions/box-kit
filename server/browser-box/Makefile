# Every answer to "is it running?" lives in this file.
SHELL := /bin/bash
COMPOSE := docker compose
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

up: .env ## Build and start the stack
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory status

down: ## Stop the stack (volumes survive)
	$(COMPOSE) down

logs: ## Tail all logs
	$(COMPOSE) logs -f --tail=100

status: ## What is up, and what the gateway says about itself
	@echo "── containers ─────────────────────────────"
	@$(COMPOSE) ps
	@echo
	@echo "── resource use ───────────────────────────"
	@docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' $$($(COMPOSE) ps -q 2>/dev/null) 2>/dev/null || true
	@echo
	@echo "── gateway /status ────────────────────────"
	@curl -fsS -H "Authorization: Bearer $$(grep -E '^BB_TOKEN=' .env | cut -d= -f2-)" http://127.0.0.1:8080/status | python3 -m json.tool || echo "gateway not answering"

test: ## Run the gateway test suite (no Docker, no browser, no network)
	PYTHONPATH=gateway $(PY) -m unittest discover -s tests -t . -v

cli: ## Install browser-box-pp-cli and browser-box-pp-mcp from pp-cli/ into your Go bin
	cd pp-cli && go install ./cmd/browser-box-pp-cli ./cmd/browser-box-pp-mcp

cli-test: ## Run the Go CLI's tests (needs Go; the box's env vars are unset for them)
	cd pp-cli && env -u BROWSER_BOX_BASE_URL -u BROWSER_BOX_TOKEN go test ./...

venv: ## Local venv for `make test`
	python3 -m venv .venv && .venv/bin/pip install -q -r gateway/requirements.txt

openapi: ## Regenerate docs/openapi.json from the tool cards (the CLI is generated from it)
	PYTHONPATH=gateway $(PY) -c "import json; from gateway import rest; open('docs/openapi.json','w').write(json.dumps(rest.openapi(), indent=2)+'\\n')"

plugin: ## Validate the plugin and marketplace manifests
	claude plugin validate .

caddy-check: ## Validate the Caddyfile as it will actually be installed
	sed "s|{\$$BB_DOMAIN}|example.com|" Caddyfile | caddy validate --config /dev/stdin --adapter caddyfile

smoke: ## Prove the tools end to end through the MCP endpoint
	@scripts/smoke.sh

token: ## Generate a BB_TOKEN value
	@openssl rand -hex 32

.env:
	@echo "No .env. Copy .env.example to .env and set BB_TOKEN (make token)." >&2
	@exit 1

.PHONY: help up down logs status test cli cli-test venv plugin caddy-check smoke token
