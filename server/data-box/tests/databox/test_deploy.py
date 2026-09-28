"""The droplet deploy files agree with the code: port, paths, unit hardening, and an activator that
runs on the host's bare python3."""
import ast
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from data_box import config

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "data-box"


def load_activator():
    spec = importlib.util.spec_from_file_location("databox_activate_release", DEPLOY / "activate_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployFiles(unittest.TestCase):
    def test_caddy_and_env_example_use_the_default_port(self):
        port = str(config.port())
        self.assertIn(f"reverse_proxy 127.0.0.1:{port}", (DEPLOY / "Caddyfile.data-box").read_text())
        self.assertIn(f"DATABOX_PORT={port}", (DEPLOY / "data-box.env.example").read_text())

    def test_the_env_example_names_every_provider_variable_and_no_values(self):
        example = (DEPLOY / "data-box.env.example").read_text()
        for provider in config.PROVIDERS.values():
            for name in provider["env"]:
                self.assertIn(f"\n{name}=\n", example, name)

    def test_the_unit_runs_the_release_as_an_unprivileged_capped_user(self):
        unit = (DEPLOY / "data-box.service").read_text()
        for line in ("User=databox", "MemoryMax=600M", "ProtectSystem=strict", "NoNewPrivileges=yes",
                     "ReadWritePaths=/var/lib/data-box", "EnvironmentFile=/etc/data-box.env",
                     "EnvironmentFile=/opt/data-box/current/release.env",
                     "ExecStart=/opt/data-box/current/.venv/bin/python -m data_box.server"):
            self.assertIn(line + "\n", unit)


class Activator(unittest.TestCase):
    def test_it_imports_only_the_standard_library(self):
        tree = ast.parse((DEPLOY / "activate_release.py").read_text())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
        modules.discard("__future__")
        self.assertEqual(modules - set(sys.stdlib_module_names), set())

    def test_it_reads_the_env_file_the_way_systemd_does(self):
        values = load_activator().parse_env('# note\n\nDATABOX_TOKEN="abc"\nDATABOX_PORT=8092\nbroken line\n')
        self.assertEqual(values, {"DATABOX_TOKEN": "abc", "DATABOX_PORT": "8092"})

    def test_it_counts_only_unfinished_jobs(self):
        activator = load_activator()
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            self.assertEqual(activator.active_jobs(state), 0)  # no ledger yet: nothing to wait for
            with sqlite3.connect(state / "data-box.sqlite") as db:
                db.execute("CREATE TABLE jobs (id TEXT, status TEXT)")
                db.executemany("INSERT INTO jobs VALUES (?, ?)",
                               [("a", "queued"), ("b", "running"), ("c", "succeeded"), ("d", "interrupted")])
            self.assertEqual(activator.active_jobs(state), 2)


if __name__ == "__main__":
    unittest.main()
