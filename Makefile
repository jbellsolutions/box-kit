# Box Kit: run browser-box and data-box on your own machine or server.
SHELL := /bin/bash
BB := server/browser-box
DB := server/data-box
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

setup: ## Create both .env files with fresh tokens (keeps existing ones)
	@test -f $(BB)/.env || { cp $(BB)/.env.example $(BB)/.env && sed -i.bak "s/^BB_TOKEN=.*/BB_TOKEN=$$(openssl rand -hex 32)/" $(BB)/.env && rm -f $(BB)/.env.bak; echo "created $(BB)/.env"; }
	@test -f $(DB)/.env || { cp $(DB)/.env.example $(DB)/.env && sed -i.bak "s/^DATABOX_TOKEN=.*/DATABOX_TOKEN=$$(openssl rand -hex 32)/" $(DB)/.env && rm -f $(DB)/.env.bak; echo "created $(DB)/.env"; }
	@chmod 600 $(BB)/.env $(DB)/.env
	@echo "Add paid keys to those files if you have them, then: make up"

up: setup ## Build and start both servers (Docker)
	$(MAKE) -C $(BB) up
	docker compose --project-directory $(DB) -f $(DB)/compose.yml up -d --build

down: ## Stop both servers (data survives)
	-$(MAKE) -C $(BB) down
	-docker compose --project-directory $(DB) -f $(DB)/compose.yml down

status: ## Are they up?
	@curl -fsS -o /dev/null -w "browser-box  %{http_code}\n" http://127.0.0.1:8080/health || echo "browser-box  down"
	@curl -fsS -o /dev/null -w "data-box     %{http_code}\n" http://127.0.0.1:8092/health || echo "data-box     down"

env: ## Print the lines that point your agents (Claude Code, Codex, scripts) at these servers
	@echo "export BROWSER_BOX_URL=http://127.0.0.1:8080/mcp"
	@echo "export BROWSER_BOX_TOKEN=$$(grep -E '^BB_TOKEN=' $(BB)/.env | cut -d= -f2-)"
	@echo "export DATABOX_URL=http://127.0.0.1:8092/mcp"
	@echo "export DATABOX_TOKEN=$$(grep -E '^DATABOX_TOKEN=' $(DB)/.env | cut -d= -f2-)"

test: ## Run both servers' test suites (no Docker, no browser, no keys)
	cd $(BB) && python3 -m venv .venv && .venv/bin/pip install -q -r gateway/requirements.txt && PYTHONPATH=gateway .venv/bin/python -m unittest discover -s tests -t .
	cd $(DB) && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]" && .venv/bin/python -m pytest -q tests/databox

.PHONY: help setup up down status env test
