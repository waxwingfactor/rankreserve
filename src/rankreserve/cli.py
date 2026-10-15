"""Command line workflow. There is no service or network access."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from importlib import metadata, resources
from pathlib import Path
import shutil
import sqlite3
import sys

from . import core


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Keep approved reserve activation order and every human disposition locally.",
        epilog="One authoritative local database; activation order is not travel order. See docs/contracts.md.",
    )
    parser.add_argument("--version", action="version", version=metadata.version("rankreserve"))
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new campaign from an approved design CSV")
    init.add_argument("design", type=Path)
    init.add_argument("--actor", required=True)
    init.add_argument("--approval-note", required=True, help="Recorded assertion of approval, not software certification")
    init.add_argument("--protocol-ref", required=True)
    init.add_argument("--completion-rule", required=True, help="Definition of full successful sampling")

    status = commands.add_parser("status", help="Inspect a consistent snapshot, current queue and pool deficits")
    status.add_argument("--check-complete", action="store_true", help="Exit 3 unless every pool is complete")
    activate = commands.add_parser("activate", help="Activate the next ranked reserve for one open slot")
    activate.add_argument("--pool", required=True)
    record = commands.add_parser("record", help="Record a human outcome for an already active site")
    record.add_argument("site")
    record.add_argument("status", choices=("pending", "ready", "deferred", "sampled", "non_target", "access_denied", "inaccessible", "not_sampleable"))
    record.add_argument("--amend", type=int, help="Exact latest outcome revision for this site; required to change a final outcome")
    incident = commands.add_parser("incident", help="Preserve an off-plan observation and hold that pool for review")
    incident.add_argument("site")
    export = commands.add_parser("export", help="Export all sites, crew queue and history into a new directory")
    export.add_argument("--out", required=True, type=Path)
    backup = commands.add_parser("backup", help="Copy a consistent, verified database into a new file")
    backup.add_argument("--out", required=True, type=Path)
    backup.add_argument("--expect", required=True, type=int)
    examples = commands.add_parser("examples", help="Copy the packaged constructed example into a new directory")
    examples.add_argument("--out", required=True, type=Path)

    for command in (init, status, activate, record, incident, export, backup):
        command.add_argument("--db", required=True, type=Path)
        command.add_argument("--json", action="store_true", help="Print the complete snapshot as JSON")
    for command in (activate, record, incident):
        command.add_argument("--actor", required=True)
        command.add_argument("--note", required=True)
        command.add_argument("--observed-on", required=True, help="Calendar date YYYY-MM-DD of the observation/decision")
        command.add_argument("--expect", required=True, type=int, help="Last inspected campaign revision")
    return parser


def _csv(rows: list[dict], fields: list[str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Prevent spreadsheet formulas in human-supplied text. JSON retains exact values.
        safe = {}
        for key in fields:
            value = row.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return buffer.getvalue()


def _summary(snap: dict) -> str:
    lines = [f"RankReserve | revision {snap['revision']} | campaign {snap['metadata']['uuid']}"]
    lines.append("Pool | target | sampled | unresolved | open slots | overcommitted | unused reserves | state")
    for pool in snap["pools"]:
        lines.append(" | ".join(str(pool[key]) for key in ("pool", "target", "sampled", "unresolved", "open_slots", "overcommitted", "remaining_reserves", "state")))
    lines.append("\nCurrent work (activation rank is not travel order):")
    for site in snap["queue"]:
        lines.append(f"  {site['site_id']} | {site['pool']} | rank {site['rank']} | {site['status']} | last outcome {site['last_outcome_revision']}")
    if not snap["queue"]:
        lines.append("  (none)")
    held = [pool["pool"] for pool in snap["pools"] if pool["state"] in {"conflict", "exception"}]
    if held:
        lines.append("\nREVIEW HOLD: " + ", ".join(held) + ". Preserve truth; consult the design authority before field action.")
    return "\n".join(lines) + "\n"


def export_snapshot(snap: dict, destination: Path) -> None:
    """A new output directory, with a completion manifest written last."""
    destination.mkdir(exist_ok=False)
    try:
        fields = ["site_id", "pool", "rank", "role", "label", "active", "status", "last_revision", "last_outcome_revision", "incidents"]
        payloads = {
            "snapshot.json": json.dumps(snap, ensure_ascii=False, indent=2) + "\n",
            "history.json": json.dumps(snap["events"], ensure_ascii=False, indent=2) + "\n",
            "sites.csv": _csv(snap["sites"], fields),
            "queue.csv": _csv(snap["queue"], fields),
            "summary.txt": _summary(snap),
        }
        hashes = {}
        for name, content in payloads.items():
            encoded = content.encode("utf-8")
            (destination / name).write_bytes(encoded)
            hashes[name] = hashlib.sha256(encoded).hexdigest()
        manifest = {"schema_version": 1, "campaign_uuid": snap["metadata"]["uuid"], "revision": snap["revision"], "head_hash": snap["head_hash"], "sha256": hashes, "complete": True}
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(destination)
        raise


def _examples(destination: Path) -> None:
    destination.mkdir(exist_ok=False)
    try:
        for item in resources.files("rankreserve").joinpath("examples").iterdir():
            if item.is_file():
                (destination / item.name).write_bytes(item.read_bytes())
    except BaseException:
        shutil.rmtree(destination)
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "examples":
            _examples(args.out)
            print("Constructed example copied to " + str(args.out))
            return 0
        if args.command == "init":
            snap = core.initialize(args.db, args.design, actor=args.actor, approval_note=args.approval_note, protocol_ref=args.protocol_ref, completion_rule=args.completion_rule)
        elif args.command == "status":
            snap = core.snapshot(args.db)
        elif args.command == "activate":
            snap = core.activate_next(args.db, args.pool, actor=args.actor, note=args.note, observed_on=args.observed_on, expected_revision=args.expect)
        elif args.command == "record":
            snap = core.record_outcome(args.db, args.site, args.status, actor=args.actor, note=args.note, observed_on=args.observed_on, expected_revision=args.expect, amendment_of=args.amend)
        elif args.command == "incident":
            snap = core.record_incident(args.db, args.site, args.note, actor=args.actor, observed_on=args.observed_on, expected_revision=args.expect)
        elif args.command == "backup":
            snap = core.backup_database(args.db, args.out, expected_revision=args.expect)
        else:
            snap = core.snapshot(args.db)
            export_snapshot(snap, args.out)
        print(json.dumps(snap, ensure_ascii=False, indent=2) if args.json else _summary(snap), end="\n" if args.json else "")
        if args.command == "status" and args.check_complete and any(pool["state"] != "complete" for pool in snap["pools"]):
            return 3
        return 0
    except (core.RankReserveError, OSError, UnicodeError, csv.Error, sqlite3.Error) as error:
        print(f"rankreserve: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
