# Using the boxes from Hermes

1. **Skills.** Copy both folders into your Hermes skills directory:
   ```bash
   cp -R hermes/skills/browser-box hermes/skills/data-box ~/.hermes/skills/
   ```
   (For a profile: `~/.hermes/profiles/<profile>/skills/`.) `data-box` is a category: the router
   plus one skill per data tool (Firecrawl, Alexandria, Firecrawl's browser, DiscoLike, MoltSets,
   GetLeads, Consulti, Lead Radar, Jev). If a profile already has a skill with one of those names,
   use the installer instead; it installs the clashing ones as `data-box-<name>`, adds files only
   under `skills/data-box/`, and never overwrites a file you edited:
   ```bash
   python3 plugins/data-box/hermes/install.py <profile> --dry-run   # then without --dry-run
   ```
2. **Servers.** Add the two entries from [config-snippet.yaml](config-snippet.yaml) under
   `mcp_servers:` in `~/.hermes/config.yaml` (or the profile's `config.yaml`).
3. **Tokens.** Add `BROWSER_BOX_TOKEN=` and `DATABOX_TOKEN=` lines to `~/.hermes/.env` (or the
   profile's `.env`). `make env` in the kit prints the values.
4. **Check.**
   ```bash
   hermes mcp test browser-box
   hermes mcp test data-box
   ```
   Each should connect and list its tools.
5. **Restart** the Hermes gateway (`hermes gateway restart`) and any open desktop app so running
   agents pick the servers up.

Coming from Super Browser: remove or disable the old `super-browser` entry once your agents use
these. Browsing and clicking through public pages map to browser-box (`read`, `act`, `session`, `task`); page
data maps to data-box (`scrape`, `job`).
