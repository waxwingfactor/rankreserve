"""Independent installed-CLI acceptance tests.

These tests intentionally use only subprocesses, exported files, and public JSON.
Run with an installed distribution from outside its source tree. No implementation
functions or development-path overrides are used.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DESIGN = """site_id,pool,rank,role,label
A1,ALPHA,10,base,First base
A2,ALPHA,20,base,Second base
Z-FIRST,ALPHA,30,reserve,First ranked reserve
A-SECOND,ALPHA,40,reserve,Second ranked reserve
M-THIRD,ALPHA,50,reserve,Third ranked reserve
B1,BETA,1,base,Independent base
BR1,BETA,2,reserve,Independent reserve
BR2,BETA,3,reserve,Unused independent reserve
"""


class InstalledCLIAcceptance(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rankreserve-acceptance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.design = self.root / "design.csv"
        self.design.write_text(DESIGN, encoding="utf-8")
        self.db = self.root / "campaign.sqlite"
        self.invoke(
            "init", str(self.design), "--db", str(self.db),
            "--actor", "Acceptance coordinator",
            "--approval-note", "Synthetic independent pools approved for testing",
            "--protocol-ref", "SYNTHETIC-PROTOCOL-2026",
            "--completion-rule", "Coordinator confirms full synthetic protocol",
        )

    def invoke(self, *arguments, expected=0, cwd=None):
        result = subprocess.run(
            [sys.executable, "-m", "rankreserve", *arguments],
            cwd=cwd or self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, expected,
            f"command: {arguments!r}\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        if expected:
            self.assertNotIn("Traceback (most recent call last)", result.stderr)
        return result

    def snapshot(self, db=None):
        result = self.invoke("status", "--db", str(db or self.db), "--json")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"status --json was not machine JSON: {error}: {result.stdout!r}")

    def site(self, snapshot, identifier):
        return next(site for site in snapshot["sites"] if site["site_id"] == identifier)

    def pool(self, snapshot, identifier="ALPHA"):
        return next(pool for pool in snapshot["pools"] if pool["pool"] == identifier)

    def record(self, identifier, outcome, *, expected=0, amendment=None, revision=None, observed_on="2026-10-15"):
        if revision is None:
            revision = self.snapshot()["revision"]
        args = [
            "record", identifier, outcome, "--db", str(self.db),
            "--actor", "Acceptance coordinator", "--note", "Explicit test decision",
            "--observed-on", observed_on, "--expect", str(revision),
        ]
        if amendment is not None:
            args.extend(["--amend", str(amendment)])
        return self.invoke(*args, expected=expected)

    def activate(self, pool="ALPHA", *, expected=0, revision=None):
        if revision is None:
            revision = self.snapshot()["revision"]
        return self.invoke(
            "activate", "--db", str(self.db), "--pool", pool,
            "--actor", "Acceptance coordinator", "--note", "Activate next approved reserve",
            "--observed-on", "2026-10-15", "--expect", str(revision),
            expected=expected,
        )

    def incident(self, identifier, *, expected=0):
        return self.invoke(
            "incident", identifier, "--db", str(self.db),
            "--actor", "Acceptance coordinator", "--note", "Unexpected unapproved field observation",
            "--observed-on", "2026-10-15", "--expect", str(self.snapshot()["revision"]),
            expected=expected,
        )

    def assert_unchanged_after(self, function):
        before = self.snapshot()
        function()
        self.assertEqual(self.snapshot(), before)

    def test_initialization_preserves_assertions_and_unused_sites(self):
        state = self.snapshot()
        self.assertEqual(state["revision"], 0)
        self.assertEqual(state["events"], [])
        self.assertEqual(len(state["sites"]), 8)
        self.assertEqual(self.pool(state)["target"], 2)
        self.assertEqual(self.pool(state)["unresolved"], 2)
        self.assertEqual(self.pool(state)["open_slots"], 0)
        self.assertEqual(self.pool(state)["remaining_reserves"], 3)
        self.assertEqual(len(state["queue"]), 3)
        self.assertEqual(state["metadata"]["protocol_ref"], "SYNTHETIC-PROTOCOL-2026")
        self.assertEqual(state["metadata"]["completion_rule"], "Coordinator confirms full synthetic protocol")
        for site in state["sites"]:
            self.assertEqual(site["active"], site["role"] == "base")
            self.assertEqual(site["status"], "pending" if site["role"] == "base" else "unused")

    def test_existing_database_is_not_overwritten(self):
        digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.invoke(
            "init", str(self.design), "--db", str(self.db), "--actor", "Other actor",
            "--approval-note", "Other approval", "--protocol-ref", "Other protocol",
            "--completion-rule", "Other rule", expected=2,
        )
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.snapshot()["revision"], 0)

    def test_unresolved_labels_never_release_capacity(self):
        for outcome in ("ready", "deferred", "pending"):
            with self.subTest(outcome=outcome):
                self.record("A1", outcome)
                self.assert_unchanged_after(lambda: self.activate(expected=2))
                state = self.snapshot()
                self.assertEqual(self.pool(state)["unresolved"], 2)
                self.assertEqual(self.pool(state)["open_slots"], 0)
                self.assertEqual(self.site(state, "Z-FIRST")["status"], "unused")

    def test_reserves_follow_rank_and_failures_cascade_without_cross_pool_use(self):
        self.record("A1", "non_target")
        self.activate()
        state = self.snapshot()
        self.assertTrue(self.site(state, "Z-FIRST")["active"])
        self.assertFalse(self.site(state, "A-SECOND")["active"])
        self.record("Z-FIRST", "inaccessible")
        self.activate()
        self.record("A2", "access_denied")
        self.activate()
        state = self.snapshot()
        activations = [event["site_id"] for event in state["events"] if event["kind"] == "activate"]
        self.assertEqual(activations, ["Z-FIRST", "A-SECOND", "M-THIRD"])
        self.assertEqual(self.pool(state, "BETA")["unresolved"], 1)
        self.assertEqual(self.pool(state, "BETA")["remaining_reserves"], 2)
        self.assertFalse(self.site(state, "BR1")["active"])

    def test_every_terminal_failure_releases_capacity(self):
        # Each correction is explicit and references the site's latest outcome.
        latest = None
        for outcome in ("non_target", "access_denied", "inaccessible", "not_sampleable"):
            with self.subTest(outcome=outcome):
                self.record("A1", outcome, amendment=latest)
                state = self.snapshot()
                latest = self.site(state, "A1")["last_outcome_revision"]
                self.assertEqual(self.pool(state)["open_slots"], 1)
                self.assertEqual(self.pool(state)["state"], "needs_reserve")

    def test_terminal_change_requires_exact_site_outcome_revision(self):
        self.record("A1", "non_target")
        outcome_revision = self.site(self.snapshot(), "A1")["last_outcome_revision"]
        self.record("B1", "ready")
        self.assertNotEqual(self.snapshot()["revision"], outcome_revision)
        self.assert_unchanged_after(lambda: self.record("A1", "sampled", expected=2))
        self.assert_unchanged_after(lambda: self.record("A1", "sampled", amendment=0, expected=2))
        self.record("A1", "sampled", amendment=outcome_revision)
        state = self.snapshot()
        self.assertEqual(self.site(state, "A1")["status"], "sampled")
        self.assertEqual(state["events"][-1]["amendment_of"], outcome_revision)
        self.assert_unchanged_after(lambda: self.record("A1", "pending", amendment=outcome_revision, expected=2))

    def test_amendment_creates_conflict_without_retracting_activation(self):
        self.record("A1", "non_target")
        failure_revision = self.site(self.snapshot(), "A1")["last_outcome_revision"]
        self.activate()
        self.record("A1", "sampled", amendment=failure_revision)
        state = self.snapshot()
        self.assertEqual(self.pool(state)["overcommitted"], 1)
        self.assertEqual(self.pool(state)["state"], "conflict")
        self.assertTrue(self.site(state, "Z-FIRST")["active"])
        self.assertEqual(self.site(state, "Z-FIRST")["status"], "pending")
        self.assertEqual(len([e for e in state["events"] if e["kind"] == "activate"]), 1)
        self.assert_unchanged_after(lambda: self.activate(expected=2))
        self.invoke("status", "--db", str(self.db), "--check-complete", expected=3)
        # Truthful outcomes remain recordable while the pool is conflicted.
        self.record("Z-FIRST", "inaccessible")
        self.assertEqual(self.pool(self.snapshot())["overcommitted"], 0)

    def test_sampled_correction_to_unresolved_holds_capacity_then_failure_opens_it(self):
        self.record("A1", "sampled")
        revision = self.site(self.snapshot(), "A1")["last_outcome_revision"]
        self.record("A1", "deferred", amendment=revision)
        state = self.snapshot()
        self.assertEqual(self.pool(state)["sampled"], 0)
        self.assertEqual(self.pool(state)["unresolved"], 2)
        self.assertEqual(self.pool(state)["open_slots"], 0)
        self.record("A1", "not_sampleable")
        self.assertEqual(self.pool(self.snapshot())["open_slots"], 1)

    def test_stale_global_revision_cannot_overwrite_another_sites_update(self):
        old_revision = self.snapshot()["revision"]
        self.record("B1", "ready")
        self.assert_unchanged_after(lambda: self.record("A1", "non_target", revision=old_revision, expected=2))
        self.assert_unchanged_after(lambda: self.activate(revision=old_revision, expected=2))

    def test_ordinary_record_does_not_authorize_unused_reserve(self):
        self.assert_unchanged_after(lambda: self.record("Z-FIRST", "sampled", expected=2))
        self.incident("Z-FIRST")
        state = self.snapshot()
        reserve = self.site(state, "Z-FIRST")
        self.assertFalse(reserve["active"])
        self.assertEqual(reserve["status"], "unused")
        self.assertEqual(len(reserve["incidents"]), 1)
        self.assertEqual(self.pool(state)["state"], "exception")
        self.record("A1", "non_target")
        self.assert_unchanged_after(lambda: self.activate(expected=2))
        self.record("A2", "sampled")
        self.assertEqual(self.pool(self.snapshot())["state"], "exception")
        self.invoke("status", "--db", str(self.db), "--check-complete", expected=3)

    def test_reserve_sample_cannot_predate_activation_but_historical_preparation_can(self):
        self.record("A1", "non_target")
        self.activate()  # Activation decision observed on 2026-10-15.
        before = self.snapshot()
        rejected = self.record("Z-FIRST", "sampled", observed_on="2026-10-14", expected=2)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("incident", rejected.stderr.lower())
        # Permission/preparation information may predate the decision to release
        # this reserve; that information does not claim authorized sampling.
        self.record("Z-FIRST", "ready", observed_on="2026-10-14")
        self.assertEqual(self.snapshot()["events"][-1]["observed_on"], "2026-10-14")
        self.record("Z-FIRST", "sampled", observed_on="2026-10-15")
        state = self.snapshot()
        self.assertEqual(self.site(state, "Z-FIRST")["status"], "sampled")
        sampled_revision = self.site(state, "Z-FIRST")["last_outcome_revision"]
        self.record("Z-FIRST", "pending", amendment=sampled_revision)
        self.record("Z-FIRST", "sampled", observed_on="2026-10-16")
        self.assertEqual(self.snapshot()["events"][-1]["observed_on"], "2026-10-16")

    def test_sampled_amendment_cannot_rewrite_pre_activation_observation_as_authorized(self):
        self.record("A1", "non_target")
        self.activate()
        self.record("Z-FIRST", "not_sampleable")
        before = self.snapshot()
        failure_revision = self.site(before, "Z-FIRST")["last_outcome_revision"]
        rejected = self.record(
            "Z-FIRST", "sampled", observed_on="2026-10-14",
            amendment=failure_revision, expected=2,
        )
        self.assertEqual(self.snapshot(), before)
        self.assertIn("incident", rejected.stderr.lower())
        self.record("Z-FIRST", "sampled", observed_on="2026-10-15", amendment=failure_revision)
        same_day = self.snapshot()
        sampled_revision = self.site(same_day, "Z-FIRST")["last_outcome_revision"]
        self.record("Z-FIRST", "sampled", observed_on="2026-10-16", amendment=sampled_revision)
        state = self.snapshot()
        self.assertEqual(self.site(state, "Z-FIRST")["status"], "sampled")
        self.assertEqual(state["events"][-1]["observed_on"], "2026-10-16")

    def test_incident_does_not_replace_outcome_revision(self):
        self.record("A1", "non_target")
        before = self.site(self.snapshot(), "A1")
        self.incident("A1")
        after = self.site(self.snapshot(), "A1")
        self.assertEqual(after["last_revision"], before["last_revision"])
        self.assertEqual(after["last_outcome_revision"], before["last_outcome_revision"])
        self.record("A1", "sampled", amendment=before["last_outcome_revision"])
        self.assertEqual(self.site(self.snapshot(), "A1")["status"], "sampled")

    def test_completion_requires_sampled_sites_in_every_pool(self):
        self.invoke("status", "--db", str(self.db))
        self.invoke("status", "--db", str(self.db), "--check-complete", expected=3)
        self.record("A1", "sampled")
        self.record("A2", "sampled")
        self.assertEqual(self.pool(self.snapshot())["state"], "complete")
        self.invoke("status", "--db", str(self.db), "--check-complete", expected=3)
        self.record("B1", "sampled")
        self.invoke("status", "--db", str(self.db), "--check-complete")
        self.assertTrue(all(pool["state"] == "complete" for pool in self.snapshot()["pools"]))

    def test_exhaustion_is_a_shortfall_and_not_success(self):
        self.record("B1", "non_target")
        self.activate("BETA")
        self.record("BR1", "inaccessible")
        self.activate("BETA")
        self.record("BR2", "not_sampleable")
        pool = self.pool(self.snapshot(), "BETA")
        self.assertEqual(pool["state"], "exhausted")
        self.assertEqual(pool["sampled"], 0)
        self.assertEqual(pool["open_slots"], 1)
        self.assertEqual(pool["remaining_reserves"], 0)
        self.assert_unchanged_after(lambda: self.activate("BETA", expected=2))
        self.invoke("status", "--db", str(self.db), "--check-complete", expected=3)

    def test_bad_inputs_fail_without_mutation(self):
        for site, outcome in (("UNKNOWN", "sampled"), ("A1", "visited")):
            with self.subTest(site=site, outcome=outcome):
                self.assert_unchanged_after(lambda: self.record(site, outcome, expected=2))
        self.assert_unchanged_after(lambda: self.activate("UNKNOWN", expected=2))
        before = self.snapshot()
        for date in ("2026-02-30", "2026-2-03", "15-10-2026"):
            self.invoke(
                "record", "A1", "ready", "--db", str(self.db), "--actor", "Coordinator",
                "--note", "Test invalid date", "--observed-on", date,
                "--expect", str(before["revision"]), expected=2,
            )
        self.assertEqual(self.snapshot(), before)

    def test_export_is_complete_consistent_and_no_clobber(self):
        self.record("A1", "non_target")
        self.activate()
        self.incident("M-THIRD")
        before = self.snapshot()
        destination = self.root / "handoff"
        self.invoke("export", "--db", str(self.db), "--out", str(destination))
        for name in ("snapshot.json", "sites.csv", "queue.csv", "history.json", "summary.txt"):
            self.assertTrue((destination / name).is_file(), name)
        self.assertEqual(json.loads((destination / "snapshot.json").read_text()), before)
        with (destination / "sites.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["site_id"] for row in rows}, {site["site_id"] for site in before["sites"]})
        unused = next(row for row in rows if row["site_id"] == "BR2")
        self.assertEqual(unused["status"], "unused")
        history = json.loads((destination / "history.json").read_text())
        self.assertEqual(history, before["events"])
        files_before = {p.name: p.read_bytes() for p in destination.iterdir() if p.is_file()}
        self.invoke("export", "--db", str(self.db), "--out", str(destination), expected=2)
        self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir() if p.is_file()}, files_before)
        self.assertEqual(self.snapshot(), before)

    def test_backup_is_revision_guarded_independent_and_relocatable(self):
        self.record("A1", "ready")
        before = self.snapshot()
        backup = self.root / "relocated" / "backup.sqlite"
        backup.parent.mkdir()
        self.invoke("backup", "--db", str(self.db), "--out", str(backup), "--expect", "0", expected=2)
        self.assertFalse(backup.exists())
        self.invoke("backup", "--db", str(self.db), "--out", str(backup), "--expect", str(before["revision"]))
        self.assertEqual(self.snapshot(backup), before)
        self.record("A1", "deferred")
        self.assertEqual(self.snapshot(backup), before)
        self.invoke("backup", "--db", str(self.db), "--out", str(backup), "--expect", str(self.snapshot()["revision"]), expected=2)
        self.design.unlink()
        self.db.unlink()
        result = self.invoke("status", "--db", str(backup), "--json", cwd=backup.parent)
        self.assertEqual(json.loads(result.stdout), before)

    def test_examples_are_installable_package_resources(self):
        destination = self.root / "packaged-examples"
        self.invoke("examples", "--out", str(destination))
        csv_files = list(destination.rglob("*.csv"))
        self.assertTrue(csv_files, "examples must contain a usable design CSV")
        for index, path in enumerate(csv_files):
            self.invoke(
                "init", str(path), "--db", str(self.root / f"example-{index}.sqlite"),
                "--actor", "Example reviewer", "--approval-note", "Synthetic example review",
                "--protocol-ref", "EXAMPLE-ONLY", "--completion-rule", "Synthetic complete sampling",
            )

    def test_invalid_designs_never_create_a_partial_campaign(self):
        invalid_designs = {
            "duplicate-site": "site_id,pool,rank,role\nA,P,1,base\nA,P,2,reserve\n",
            "duplicate-rank": "site_id,pool,rank,role\nA,P,1,base\nB,P,1,reserve\n",
            "missing-column": "site_id,pool,rank\nA,P,1\n",
            "unknown-role": "site_id,pool,rank,role\nA,P,1,initial\n",
            "no-base": "site_id,pool,rank,role\nA,P,1,reserve\n",
            "reserve-before-base": "site_id,pool,rank,role\nA,P,2,base\nB,P,1,reserve\n",
            "zero-rank": "site_id,pool,rank,role\nA,P,0,base\n",
            "surrounding-whitespace": "site_id,pool,rank,role\n A,P,1,base\n",
            "extra-column": "site_id,pool,rank,role,unexpected\nA,P,1,base,x\n",
        }
        for name, content in invalid_designs.items():
            with self.subTest(name=name):
                design = self.root / f"{name}.csv"
                database = self.root / f"{name}.sqlite"
                design.write_text(content, encoding="utf-8")
                self.invoke(
                    "init", str(design), "--db", str(database), "--actor", "Reviewer",
                    "--approval-note", "Synthetic", "--protocol-ref", "TEST", "--completion-rule", "Test completion",
                    expected=2,
                )
                self.assertFalse(database.exists(), "invalid design left a database destination behind")

    def test_missing_and_corrupt_databases_fail_clearly_without_changes(self):
        missing = self.root / "missing.sqlite"
        self.invoke("status", "--db", str(missing), "--json", expected=2)
        self.assertFalse(missing.exists())
        corrupt = self.root / "corrupt.sqlite"
        bad_bytes = b"This is deliberately not a SQLite database.\n"
        corrupt.write_bytes(bad_bytes)
        self.invoke("status", "--db", str(corrupt), "--json", expected=2)
        self.assertEqual(corrupt.read_bytes(), bad_bytes)

    def test_two_processes_cannot_activate_the_same_capacity_twice(self):
        self.record("A1", "non_target")
        before = self.snapshot()
        arguments = [
            sys.executable, "-m", "rankreserve", "activate", "--db", str(self.db),
            "--pool", "ALPHA", "--actor", "Concurrent coordinator",
            "--note", "Concurrent activation attempt", "--observed-on", "2026-10-15",
            "--expect", str(before["revision"]),
        ]
        processes = [subprocess.Popen(arguments, cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            results.append((process.returncode, stdout, stderr))
        self.assertEqual(sorted(result[0] for result in results), [0, 2], results)
        state = self.snapshot()
        self.assertEqual(state["revision"], before["revision"] + 1)
        self.assertEqual([event["site_id"] for event in state["events"] if event["kind"] == "activate"], ["Z-FIRST"])
        self.assertEqual(self.pool(state)["overcommitted"], 0)


if __name__ == "__main__":
    unittest.main()
