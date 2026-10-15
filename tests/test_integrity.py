"""Independent AI-agent integrity/fault tests against the installed package.

No development-tree path injection; suitable for wheel and sdist installations.
The crash fixture is skipped if the platform SQLite build does not produce a
hot rollback journal. Fault injection is intentionally limited to test fixtures.
"""

from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rankreserve import core


class CoreFaultReview(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rankreserve-review-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.design = self.root / "design.csv"
        self.design.write_text(
            "site_id,pool,rank,role\nA,P,1,base\nB,P,2,reserve\n",
            encoding="utf-8",
        )
        self.db = self.root / "campaign.sqlite"
        core.initialize(
            self.db, self.design, actor="Reviewer", approval_note="Synthetic",
            protocol_ref="TEST", completion_rule="Full test",
        )

    def outcome(self, status="ready", revision=0, note="Review decision"):
        return core.record_outcome(
            self.db, "A", status, actor="Reviewer", note=note,
            observed_on="2026-10-15", expected_revision=revision,
        )

    def change(self, sql, values=()):
        with sqlite3.connect(self.db) as connection:
            connection.execute(sql, values)

    @staticmethod
    def failing_commit_connection():
        original = sqlite3.connect

        class FailCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("injected commit I/O failure")

        def connect(*arguments, **keywords):
            return original(*arguments, **keywords, factory=FailCommit)

        return connect

    def leave_hot_journal(self):
        # Deliberately invalid, uncommitted rows force dirty pages to disk. A
        # normal SQLite recovery must discard them and preserve committed state.
        child = """
import os
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
connection.execute('PRAGMA cache_size=1')
connection.execute('BEGIN IMMEDIATE')
for revision in range(1, 9):
    connection.execute(
        'INSERT INTO events VALUES (?,?,?)',
        (revision, 'X' * 10000, 'x'),
    )
os._exit(0)
"""
        subprocess.run(
            [sys.executable, "-c", child, str(self.db)], check=True, timeout=30,
        )
        journal = Path(str(self.db) + "-journal")
        if not journal.exists() or journal.stat().st_size <= 512:
            self.skipTest("SQLite build did not produce a hot rollback journal")
        if journal.read_bytes()[:8] != bytes.fromhex("d9d505f920a163d7"):
            self.skipTest("SQLite build did not finalize a hot journal header")

    def test_mutation_commit_failure_rolls_back_entire_event(self):
        before = core.snapshot(self.db)
        with patch.object(core.sqlite3, "connect", self.failing_commit_connection()):
            with self.assertRaises(core.RankReserveError):
                self.outcome()
        self.assertEqual(core.snapshot(self.db), before)

    def test_initialization_commit_failure_leaves_no_partial_file(self):
        destination = self.root / "new.sqlite"
        with patch.object(core.sqlite3, "connect", self.failing_commit_connection()):
            with self.assertRaises(core.RankReserveError):
                core.initialize(
                    destination, self.design, actor="Reviewer",
                    approval_note="Synthetic", protocol_ref="TEST",
                    completion_rule="Full test",
                )
        self.assertFalse(destination.exists())

    def test_added_lookalike_sqlite_object_is_rejected(self):
        self.change("CREATE TABLE sqliteXextra (payload TEXT)")
        with self.assertRaises(core.RankReserveError):
            core.snapshot(self.db)

    def test_wrong_sqlite_application_id_is_rejected(self):
        self.change("PRAGMA application_id=7")
        with self.assertRaises(core.RankReserveError):
            core.snapshot(self.db)

    def test_edited_event_document_is_rejected(self):
        self.outcome()
        self.change(
            "UPDATE events SET document=replace(document,?,?)",
            ("Review decision", "Altered note"),
        )
        with self.assertRaises(core.RankReserveError):
            core.snapshot(self.db)

    def test_duplicate_json_metadata_key_is_rejected(self):
        with sqlite3.connect(self.db) as connection:
            document = connection.execute(
                "SELECT document FROM metadata",
            ).fetchone()[0]
            document = document[:-1] + ',"schema_version":1}'
            connection.execute("UPDATE metadata SET document=?", (document,))
        with self.assertRaises(core.RankReserveError):
            core.snapshot(self.db)

    def test_event_limit_refuses_without_changing_existing_ledger(self):
        self.outcome()
        before = core.snapshot(self.db)
        with patch.object(core, "MAX_EVENTS", 1):
            with self.assertRaises(core.RankReserveError):
                self.outcome(revision=1)
        self.assertEqual(core.snapshot(self.db), before)

    def test_database_size_growth_is_rolled_back_before_commit(self):
        limit = self.db.stat().st_size
        # Page size varies by SQLite build; continue until a write grows beyond
        # the initial page allocation rather than assuming 4 KiB pages.
        for revision in range(128):
            before = core.snapshot(self.db)
            try:
                with patch.object(core, "MAX_DATABASE_BYTES", limit):
                    self.outcome(revision=revision, note="x" * 4000)
            except core.RankReserveError:
                self.assertEqual(core.snapshot(self.db), before)
                return
        self.fail("fixture did not reach the database page-size limit")

    def test_symlink_backup_cannot_clobber_target(self):
        victim = self.root / "keep.txt"
        victim.write_text("preserve", encoding="utf-8")
        destination = self.root / "linked.sqlite"
        try:
            destination.symlink_to(victim)
        except (OSError, NotImplementedError):
            self.skipTest("platform does not permit creating test symlinks")
        with self.assertRaises(core.RankReserveError):
            core.backup_database(self.db, destination, expected_revision=0)
        self.assertEqual(victim.read_text(encoding="utf-8"), "preserve")

    def test_booleans_are_not_expected_revisions(self):
        with self.assertRaises(core.RankReserveError):
            self.outcome(revision=False)

    def test_hot_journal_status_and_backup_recover_without_new_event(self):
        before = core.snapshot(self.db)
        self.leave_hot_journal()
        self.assertEqual(core.snapshot(self.db), before)
        # Test backup independently, while the source again has a hot journal.
        self.leave_hot_journal()
        destination = self.root / "recovered-backup.sqlite"
        core.backup_database(self.db, destination, expected_revision=0)
        self.assertEqual(core.snapshot(destination), before)
        self.assertEqual(core.snapshot(self.db), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
