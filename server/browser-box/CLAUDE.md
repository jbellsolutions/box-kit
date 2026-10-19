# CLAUDE.md

Read [CHARTER.md](CHARTER.md) (the rules) and [AGENTS.md](AGENTS.md) (how to use and change this repo) before doing anything here. Docs live in [docs/](docs/README.md).

- Tests: `PYTHONPATH=gateway .venv/bin/python -m unittest discover -s tests -t .` (or `make test`).
- After a tool-card change: `make openapi` and commit `docs/openapi.json`.
- Deploys, firewall and `.env` changes on the live box need the user's explicit yes.
