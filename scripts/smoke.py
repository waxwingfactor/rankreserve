"""Exercise an installed distribution in a fresh directory. No source imports."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(python=sys.executable):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    with tempfile.TemporaryDirectory(prefix="rankreserve-smoke-") as temporary:
        root = Path(temporary)

        def call(*arguments, code=0):
            result = subprocess.run([str(python), "-I", "-m", "rankreserve", *map(str, arguments)], cwd=root, env=environment, text=True, capture_output=True, timeout=30)
            if result.returncode != code:
                raise AssertionError(f"{arguments}: expected {code}, got {result.returncode}\n{result.stdout}\n{result.stderr}")
            return result

        call("examples", "--out", "example")
        initialized = call("init", "example/design.csv", "--db", "campaign.sqlite", "--actor", "coordinator", "--approval-note", "Constructed learning exercise only", "--protocol-ref", "Constructed protocol v1", "--completion-rule", "Coordinator confirms full required sampling", "--json")
        assert json.loads(initialized.stdout)["revision"] == 0

        def event(command, *arguments, revision, code=0):
            return call(command, *arguments, "--db", "campaign.sqlite", "--actor", "coordinator", "--note", "Constructed observation", "--observed-on", "2026-10-15", "--expect", revision, "--json", code=code)

        event("activate", "--pool", "Inland", revision=0, code=2)
        event("record", "I-001", "access_denied", revision=0)
        activated = json.loads(event("activate", "--pool", "Inland", revision=1).stdout)
        assert next(site for site in activated["sites"] if site["site_id"] == "I-003")["active"]
        event("record", "I-002", "sampled", revision=2)
        event("record", "I-003", "sampled", revision=3)
        event("record", "T-001", "sampled", revision=4)
        event("record", "T-001", "pending", revision=4, code=2)
        complete = json.loads(call("status", "--db", "campaign.sqlite", "--json", "--check-complete").stdout)
        assert all(pool["state"] == "complete" for pool in complete["pools"])
        call("export", "--db", "campaign.sqlite", "--out", "handoff")
        assert (root / "handoff/manifest.json").is_file()
        call("backup", "--db", "campaign.sqlite", "--out", "relocated.sqlite", "--expect", 5)
        (root / "campaign.sqlite").unlink()
        moved = json.loads(call("status", "--db", "relocated.sqlite", "--json", "--check-complete").stdout)
        assert moved == complete
        print("Installed workflow passed: ordered activation, blocked premature/stale mutation, complete ledger export, backup and source-database removal.")


if __name__ == "__main__":
    run()
