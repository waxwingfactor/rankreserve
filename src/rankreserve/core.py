"""Durable, replayed coordination for pre-approved ordered reserve lists.

The SHA256 chain detects accidental damage. It is not an authentication scheme:
someone able to rewrite the database can also recalculate its hashes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata
import uuid as uuid_module
from datetime import date, datetime, timezone
from typing import Any


SCHEMA_VERSION = 1
MAX_SITES = 5_000
MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 50_000
APPLICATION_ID = 0x52525631  # RRV1
OUTCOMES = frozenset(
    {
        "pending", "ready", "deferred", "sampled", "non_target",
        "access_denied", "inaccessible", "not_sampleable",
    }
)
UNFINALIZED = frozenset({"pending", "ready", "deferred"})
_DESIGN_KEYS = {"site_id", "pool", "rank", "role", "label"}
_METADATA_KEYS = {
    "schema_version", "uuid", "design", "actor", "approval_note",
    "protocol_ref", "completion_rule", "created_at",
}
_EVENT_KEYS = {
    "revision", "kind", "site_id", "status", "actor", "note", "observed_on",
    "recorded_at", "amendment_of", "previous_hash", "hash",
}
_TABLE_SQL = {
    "metadata": (
        "CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK (id = 1), "
        "document TEXT NOT NULL, digest TEXT NOT NULL)"
    ),
    "events": (
        "CREATE TABLE events (revision INTEGER PRIMARY KEY, "
        "document TEXT NOT NULL, digest TEXT NOT NULL)"
    ),
}


class RankReserveError(Exception):
    """A clear input, unsupported-state, concurrency, or ledger error."""


def _plain(value: Any, field: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise RankReserveError(f"{field} must be text")
    if (not empty and not value) or len(value) > maximum:
        raise RankReserveError(f"{field} must contain {'0' if empty else '1'}-{maximum} characters")
    if value != value.strip():
        raise RankReserveError(f"{field} must not have surrounding whitespace")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise RankReserveError(f"{field} must not contain control or format characters")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise RankReserveError(f"{field} must be an integer >= {minimum}")
    return value


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise RankReserveError(f"{field} must be a valid date in YYYY-MM-DD format")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise RankReserveError(f"{field} must be a valid date in YYYY-MM-DD format") from exc
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ):
        raise RankReserveError(f"{field} must be a UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise RankReserveError(f"{field} is not a valid UTC timestamp") from exc
    return value


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise RankReserveError("ledger content cannot be represented as canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RankReserveError(f"{field} must be a lowercase SHA256 digest")
    return value


def _path(value: Any, field: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise RankReserveError(f"{field} must be a filesystem path")
    if isinstance(value, str) and (not value or "\x00" in value):
        raise RankReserveError(f"{field} must be a nonempty filesystem path without NUL characters")
    return Path(value).absolute()


def _parse_json(document: Any, field: str) -> dict:
    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise RankReserveError(f"{field} contains a duplicate JSON key")
            result[key] = value
        return result

    if not isinstance(document, str):
        raise RankReserveError(f"{field} must contain JSON text")
    try:
        result = json.loads(
            document,
            object_pairs_hook=unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise RankReserveError(f"{field} contains invalid JSON") from exc
    if not isinstance(result, dict):
        raise RankReserveError(f"{field} must be a JSON object")
    if _json(result) != document:
        raise RankReserveError(f"{field} is not canonical JSON")
    return result


def _validate_design(design: Any) -> list[dict]:
    if not isinstance(design, list) or not 1 <= len(design) <= MAX_SITES:
        raise RankReserveError(f"design must contain 1-{MAX_SITES} sites")
    ids: set[str] = set()
    ranks: set[tuple[str, int]] = set()
    groups: dict[str, dict[str, list[int]]] = {}
    for site in design:
        if not isinstance(site, dict) or set(site) != _DESIGN_KEYS:
            raise RankReserveError("each design site must have exactly site_id, pool, rank, role, label")
        site_id = _plain(site["site_id"], "site_id", 128)
        pool = _plain(site["pool"], "pool", 128)
        rank = _integer(site["rank"], "rank", minimum=1)
        if site["role"] not in ("base", "reserve"):
            raise RankReserveError("role must be base or reserve")
        _plain(site["label"], "label", 500, empty=True)
        if site_id in ids:
            raise RankReserveError(f"duplicate site_id: {site_id}")
        if (pool, rank) in ranks:
            raise RankReserveError(f"duplicate rank {rank} in pool {pool}")
        ids.add(site_id)
        ranks.add((pool, rank))
        groups.setdefault(pool, {"base": [], "reserve": []})[site["role"]].append(rank)
    for pool, roles in groups.items():
        if not roles["base"]:
            raise RankReserveError(f"pool {pool} must have at least one base site")
        if roles["reserve"] and max(roles["base"]) >= min(roles["reserve"]):
            raise RankReserveError(f"all base ranks must precede reserve ranks in pool {pool}")
    return sorted(design, key=lambda site: (site["pool"], site["rank"]))


def read_design(csv_path: str | Path) -> list[dict]:
    """Read a bounded strict UTF-8 design CSV and return canonical site records."""
    try:
        path = _path(csv_path, "design CSV")
        if not path.is_file():
            raise RankReserveError("design CSV must be a regular file")
        if path.stat().st_size > MAX_CSV_BYTES:
            raise RankReserveError("design CSV exceeds the 10 MiB limit")
        with path.open("rb") as stream:
            data = stream.read(MAX_CSV_BYTES + 1)
        if len(data) > MAX_CSV_BYTES:
            raise RankReserveError("design CSV exceeds the 10 MiB limit")
        text = data.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            header = next(rows)
        except StopIteration as exc:
            raise RankReserveError("design CSV has no header") from exc
        required = _DESIGN_KEYS - {"label"}
        if len(header) != len(set(header)) or set(header) not in (required, _DESIGN_KEYS):
            raise RankReserveError("design CSV columns must be site_id,pool,rank,role with optional label")
        design = []
        for row_number, row in enumerate(rows, start=2):
            if not row:
                raise RankReserveError(f"design CSV row {row_number} is blank")
            if len(row) != len(header):
                raise RankReserveError(f"design CSV row {row_number} has the wrong number of fields")
            record = dict(zip(header, row))
            rank_text = record["rank"]
            if not re.fullmatch(r"[0-9]{1,15}", rank_text):
                raise RankReserveError(f"design CSV row {row_number}: rank must be a positive integer")
            record["rank"] = int(rank_text)
            record.setdefault("label", "")
            design.append(record)
            if len(design) > MAX_SITES:
                raise RankReserveError(f"design has more than {MAX_SITES} sites")
        return _validate_design(design)
    except (OSError, UnicodeError, csv.Error, ValueError, OverflowError) as exc:
        raise RankReserveError(f"cannot read design CSV: {exc}") from exc


def _database_path(database: str | Path) -> Path:
    path = _path(database, "database")
    if path.is_symlink() or not path.is_file():
        raise RankReserveError("database must be an existing regular file, not a symlink")
    if path.stat().st_size > MAX_DATABASE_BYTES:
        raise RankReserveError("database exceeds the 64 MiB limit")
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm")):
        raise RankReserveError("WAL databases are unsupported; use the original local DELETE-journal ledger")
    return path


def _connect(database: str | Path, *, write: bool) -> sqlite3.Connection:
    path = _database_path(database)

    def open_transaction(mode: str) -> sqlite3.Connection:
        uri = path.as_uri() + f"?mode={mode}"
        connection = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
        try:
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.execute("PRAGMA busy_timeout = 5000")
            if mode == "rw":
                connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if not write:
                # Force the first page read before query_only. SQLite may need to
                # roll back a hot journal left by a crashed writer. A mode=ro
                # connection reports SQLITE_READONLY_ROLLBACK instead of doing
                # that standard recovery; a narrowly gated rw retry permits it.
                connection.execute("PRAGMA application_id").fetchone()
                connection.execute("PRAGMA query_only = ON")
            return connection
        except BaseException:
            _close(connection)
            raise

    try:
        return open_transaction("rw" if write else "ro")
    except sqlite3.OperationalError as exc:
        journal = Path(str(path) + "-journal")
        code = getattr(exc, "sqlite_errorcode", None)
        # Python 3.10 does not expose SQLite's extended error code. Its fallback
        # is restricted to this first-page read, this exact error, and an actual
        # nonempty regular rollback journal. Never create the existing database.
        old_python_recovery = (
            code is None and str(exc) == "attempt to write a readonly database"
            and journal.is_file() and not journal.is_symlink() and journal.stat().st_size > 512
        )
        if write or not (code == 776 or old_python_recovery):
            raise
        try:
            return open_transaction("rw")
        except sqlite3.Error as recovery_error:
            raise RankReserveError(
                "an interrupted SQLite write needs rollback recovery; the database and its "
                "directory must be writable before inspection or backup"
            ) from recovery_error


def _validate_schema(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise RankReserveError("not a supported RankReserve database")
    if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        raise RankReserveError("unsupported database schema version")
    if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
        raise RankReserveError("only DELETE-journal local databases are supported")
    page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    if page_count * page_size > MAX_DATABASE_BYTES:
        raise RankReserveError("database exceeds the 64 MiB limit")
    objects = [
        row for row in connection.execute("SELECT type, name, sql FROM sqlite_master")
        if not row[1].startswith("sqlite_")
    ]
    expected = {("table", name, sql) for name, sql in _TABLE_SQL.items()}
    if set(objects) != expected:
        raise RankReserveError("database schema is missing, modified, or contains unsupported objects")
    result = connection.execute("PRAGMA quick_check(1)").fetchone()
    if result != ("ok",):
        raise RankReserveError("database integrity check failed")


def _metadata(document: Any) -> dict:
    if not isinstance(document, dict) or set(document) != _METADATA_KEYS:
        raise RankReserveError("metadata has missing or unsupported fields")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise RankReserveError("unsupported metadata schema version")
    value = _plain(document["uuid"], "uuid", 36)
    try:
        parsed_uuid = uuid_module.UUID(value)
    except ValueError as exc:
        raise RankReserveError("metadata uuid is invalid") from exc
    if str(parsed_uuid) != value or parsed_uuid.version != 4:
        raise RankReserveError("metadata uuid must be a canonical version-4 UUID")
    _plain(document["actor"], "actor", 200)
    _plain(document["approval_note"], "approval_note", 4000)
    _plain(document["protocol_ref"], "protocol_ref", 2000)
    _plain(document["completion_rule"], "completion_rule", 2000)
    _timestamp(document["created_at"], "created_at")
    design = _validate_design(document["design"])
    if design != document["design"]:
        raise RankReserveError("metadata design is not in canonical pool/rank order")
    return document


def _event_shape(event: dict, revision: int, head_hash: str) -> None:
    if set(event) != _EVENT_KEYS:
        raise RankReserveError(f"event {revision} has missing or unsupported fields")
    if _integer(event["revision"], "event revision", minimum=1) != revision:
        raise RankReserveError("event revisions must be contiguous from 1")
    if event["kind"] not in ("outcome", "activate", "incident"):
        raise RankReserveError(f"event {revision} has an unsupported kind")
    _plain(event["site_id"], "event site_id", 128)
    _plain(event["actor"], "event actor", 200)
    _plain(event["note"], "event note", 4000)
    _date(event["observed_on"], "observed_on")
    _timestamp(event["recorded_at"], "recorded_at")
    if event["amendment_of"] is not None:
        _integer(event["amendment_of"], "amendment_of", minimum=1)
    _hash(event["previous_hash"], "previous_hash")
    _hash(event["hash"], "hash")
    if event["previous_hash"] != head_hash:
        raise RankReserveError(f"event {revision} has a broken hash-chain predecessor")
    unhashed = {key: value for key, value in event.items() if key != "hash"}
    if _digest(unhashed) != event["hash"]:
        raise RankReserveError(f"event {revision} hash does not match its content")


def _pool_summary(pool: str, sites: list[dict]) -> dict:
    members = [site for site in sites if site["pool"] == pool]
    target = sum(site["role"] == "base" for site in members)
    sampled = sum(site["active"] and site["status"] == "sampled" for site in members)
    unresolved = sum(site["active"] and site["status"] in UNFINALIZED for site in members)
    remaining = sum(not site["active"] for site in members)
    incidents = sum(len(site["incidents"]) for site in members)
    open_slots = max(target - sampled - unresolved, 0)
    overcommitted = max(sampled + unresolved - target, 0)
    if incidents:
        state = "exception"
    elif overcommitted:
        state = "conflict"
    elif sampled == target and unresolved == 0:
        state = "complete"
    elif open_slots and not remaining:
        state = "exhausted"
    elif open_slots:
        state = "needs_reserve"
    else:
        state = "in_progress"
    return {
        "pool": pool, "target": target, "sampled": sampled, "unresolved": unresolved,
        "open_slots": open_slots, "overcommitted": overcommitted,
        "remaining_reserves": remaining, "incidents": incidents, "state": state,
    }


def _apply(
    event: dict, sites: list[dict], by_id: dict[str, dict], activated_on: dict[str, str]
) -> None:
    site = by_id.get(event["site_id"])
    if site is None:
        raise RankReserveError(f"event {event['revision']} references an unknown site")
    kind = event["kind"]
    if kind == "incident":
        if event["status"] is not None or event["amendment_of"] is not None:
            raise RankReserveError("incident events cannot change status or amend outcomes")
        site["incidents"].append(event["revision"])
        return
    if kind == "activate":
        if event["status"] != "pending" or event["amendment_of"] is not None:
            raise RankReserveError("activation event has unsupported status or amendment")
        pool = _pool_summary(site["pool"], sites)
        if pool["incidents"]:
            raise RankReserveError(f"pool {site['pool']} has an incident review hold; activation is frozen")
        if pool["overcommitted"]:
            raise RankReserveError(f"pool {site['pool']} is overcommitted; activation is frozen")
        if not pool["open_slots"]:
            raise RankReserveError(f"pool {site['pool']} has no open replacement slots")
        available = [member for member in sites if member["pool"] == site["pool"] and not member["active"]]
        if not available:
            raise RankReserveError(f"pool {site['pool']} has exhausted its reserves")
        if site is not min(available, key=lambda member: member["rank"]):
            raise RankReserveError("reserve activation violates the approved rank order")
        site["active"] = True
        site["status"] = "pending"
        site["last_revision"] = event["revision"]
        activated_on[site["site_id"]] = event["observed_on"]
        return
    if not site["active"]:
        raise RankReserveError("outcomes can only be recorded for active sites; use an incident for off-plan observations")
    if not isinstance(event["status"], str) or event["status"] not in OUTCOMES:
        raise RankReserveError("unsupported outcome status")
    if (
        event["status"] == "sampled" and site["role"] == "reserve"
        and event["observed_on"] < activated_on[site["site_id"]]
    ):
        raise RankReserveError(
            "reserve sampling predates its activation date; record an incident to preserve "
            "the off-plan observation instead of authorizing it retrospectively"
        )
    if event["amendment_of"] is None:
        if site["status"] not in UNFINALIZED:
            raise RankReserveError("a finalized outcome requires an explicit amendment")
    elif event["amendment_of"] != site["last_outcome_revision"]:
        raise RankReserveError("amendment_of must reference the site's latest outcome-event revision")
    site["status"] = event["status"]
    site["last_revision"] = event["revision"]
    site["last_outcome_revision"] = event["revision"]


def _load(connection: sqlite3.Connection) -> dict:
    _validate_schema(connection)
    rows = connection.execute("SELECT id, document, digest FROM metadata").fetchall()
    if len(rows) != 1 or rows[0][0] != 1:
        raise RankReserveError("database must contain exactly one metadata record")
    metadata = _metadata(_parse_json(rows[0][1], "metadata"))
    head_hash = _digest(metadata)
    if _hash(rows[0][2], "metadata digest") != head_hash:
        raise RankReserveError("metadata hash does not match its content")
    count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if count > MAX_EVENTS:
        raise RankReserveError(f"ledger exceeds the {MAX_EVENTS} event limit")
    sites = [
        {
            **site, "active": site["role"] == "base",
            "status": "pending" if site["role"] == "base" else "unused",
            "last_revision": 0, "last_outcome_revision": None, "incidents": [],
        }
        for site in metadata["design"]
    ]
    by_id = {site["site_id"]: site for site in sites}
    activated_on: dict[str, str] = {}
    events = []
    for revision, (stored_revision, document, digest) in enumerate(
        connection.execute("SELECT revision, document, digest FROM events ORDER BY revision"), start=1
    ):
        if type(stored_revision) is not int or stored_revision != revision:
            raise RankReserveError("event revisions must be contiguous from 1")
        event = _parse_json(document, f"event {revision}")
        _event_shape(event, revision, head_hash)
        if digest != event["hash"]:
            raise RankReserveError(f"event {revision} stored digest disagrees with its hash")
        _apply(event, sites, by_id, activated_on)
        events.append(event)
        head_hash = event["hash"]
    pools = [_pool_summary(pool, sites) for pool in sorted({site["pool"] for site in sites})]
    return {
        "metadata": metadata, "revision": len(events), "pools": pools, "sites": sites,
        "events": events, "queue": [site for site in sites if site["active"] and site["status"] in UNFINALIZED],
        "head_hash": head_hash,
    }


def _cleanup_new(path: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            Path(str(path) + suffix).unlink(missing_ok=True)
        except OSError:
            pass


def _close(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        if connection.in_transaction:
            connection.rollback()
    except sqlite3.Error:
        # Preserve the original clear operation error if damaged storage also
        # prevents rollback. Closing releases SQLite's transaction and locks.
        pass
    finally:
        try:
            connection.close()
        except sqlite3.Error:
            pass


def initialize(
    database: str | Path,
    design_csv: str | Path,
    *,
    actor: str,
    approval_note: str,
    protocol_ref: str,
    completion_rule: str,
) -> dict:
    """Create a new exclusive ledger from an approved ordered design."""
    metadata = _metadata({
        "schema_version": SCHEMA_VERSION, "uuid": str(uuid_module.uuid4()),
        "design": read_design(design_csv), "actor": actor, "approval_note": approval_note,
        "protocol_ref": protocol_ref, "completion_rule": completion_rule, "created_at": _now(),
    })
    path = _path(database, "database")
    connection = None
    owned = False
    complete = False
    try:
        if any(Path(str(path) + suffix).exists() for suffix in ("-journal", "-wal", "-shm")):
            raise RankReserveError("database sidecar already exists; choose a new database path")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        owned = True
        os.close(descriptor)
        connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        for sql in _TABLE_SQL.values():
            connection.execute(sql)
        connection.execute("INSERT INTO metadata VALUES (1, ?, ?)", (_json(metadata), _digest(metadata)))
        result = _load(connection)
        connection.commit()
        complete = True
        return result
    except FileExistsError as exc:
        raise RankReserveError("database path already exists; initialization never overwrites it") from exc
    except (OSError, sqlite3.Error) as exc:
        raise RankReserveError(f"cannot initialize database: {exc}") from exc
    finally:
        _close(connection)
        if owned and not complete:
            _cleanup_new(path)


def snapshot(database: str | Path) -> dict:
    """Validate the complete ledger and return its transactionally consistent replay."""
    connection = None
    try:
        connection = _connect(database, write=False)
        return _load(connection)
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        raise RankReserveError(f"cannot read database: {exc}") from exc
    finally:
        _close(connection)


def _mutate(
    database: str | Path, *, kind: str, site_id: str | None, pool: str | None,
    status: str | None, actor: str, note: str, observed_on: str,
    expected_revision: int, amendment_of: int | None = None,
) -> dict:
    _integer(expected_revision, "expected_revision")
    _plain(actor, "actor", 200)
    _plain(note, "note", 4000)
    _date(observed_on, "observed_on")
    if site_id is not None:
        _plain(site_id, "site_id", 128)
    if pool is not None:
        _plain(pool, "pool", 128)
    if amendment_of is not None:
        _integer(amendment_of, "amendment_of", minimum=1)
    connection = None
    try:
        connection = _connect(database, write=True)
        current = _load(connection)
        if expected_revision != current["revision"]:
            raise RankReserveError(
                f"stale revision: expected {expected_revision}, current {current['revision']}; refresh before retrying"
            )
        if current["revision"] >= MAX_EVENTS:
            raise RankReserveError(f"ledger has reached the {MAX_EVENTS} event limit")
        if kind == "activate":
            summary = next((item for item in current["pools"] if item["pool"] == pool), None)
            if summary is None:
                raise RankReserveError(f"unknown pool: {pool}")
            if summary["incidents"]:
                raise RankReserveError(f"pool {pool} has an incident review hold; activation is frozen")
            if summary["overcommitted"]:
                raise RankReserveError(f"pool {pool} is overcommitted; activation is frozen")
            if not summary["open_slots"]:
                raise RankReserveError(f"pool {pool} has no open replacement slots")
            available = [site for site in current["sites"] if site["pool"] == pool and not site["active"]]
            if not available:
                raise RankReserveError(f"pool {pool} has exhausted its reserves; consult the design owner")
            site_id = min(available, key=lambda site: site["rank"])["site_id"]
        event = {
            "revision": current["revision"] + 1, "kind": kind, "site_id": site_id,
            "status": status, "actor": actor, "note": note, "observed_on": observed_on,
            "recorded_at": _now(), "amendment_of": amendment_of,
            "previous_hash": current["head_hash"],
        }
        event["hash"] = _digest(event)
        _event_shape(event, current["revision"] + 1, current["head_hash"])
        activated_on = {
            historical["site_id"]: historical["observed_on"]
            for historical in current["events"] if historical["kind"] == "activate"
        }
        _apply(
            event, current["sites"], {site["site_id"]: site for site in current["sites"]},
            activated_on,
        )
        connection.execute("INSERT INTO events VALUES (?, ?, ?)", (event["revision"], _json(event), event["hash"]))
        # Replay the persisted row before committing, including bounds and schema.
        result = _load(connection)
        connection.commit()
        return result
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        raise RankReserveError(f"cannot update database: {exc}") from exc
    finally:
        _close(connection)


def record_outcome(
    database: str | Path,
    site_id: str,
    status: str,
    *,
    actor: str,
    note: str,
    observed_on: str,
    expected_revision: int,
    amendment_of: int | None = None,
) -> dict:
    """Record an active site's outcome, or explicitly amend its latest outcome."""
    if not isinstance(status, str) or status not in OUTCOMES:
        raise RankReserveError(f"status must be one of: {', '.join(sorted(OUTCOMES))}")
    return _mutate(
        database, kind="outcome", site_id=site_id, pool=None, status=status,
        actor=actor, note=note, observed_on=observed_on,
        expected_revision=expected_revision, amendment_of=amendment_of,
    )


def activate_next(
    database: str | Path,
    pool: str,
    *,
    actor: str,
    note: str,
    observed_on: str,
    expected_revision: int,
) -> dict:
    """Activate the next ranked reserve when this pool has an open slot."""
    return _mutate(
        database, kind="activate", site_id=None, pool=pool, status="pending",
        actor=actor, note=note, observed_on=observed_on, expected_revision=expected_revision,
    )


def record_incident(
    database: str | Path,
    site_id: str,
    description: str,
    *,
    actor: str,
    observed_on: str,
    expected_revision: int,
) -> dict:
    """Preserve an off-plan observation and permanently hold its pool for review."""
    return _mutate(
        database, kind="incident", site_id=site_id, pool=None, status=None,
        actor=actor, note=description, observed_on=observed_on, expected_revision=expected_revision,
    )


def backup_database(
    database: str | Path,
    destination: str | Path,
    *,
    expected_revision: int,
) -> dict:
    """Copy an exact, validated read transaction with SQLite's backup API."""
    _integer(expected_revision, "expected_revision")
    source = None
    target = None
    owned = False
    complete = False
    path = _path(destination, "backup destination")
    try:
        source = _connect(database, write=False)
        current = _load(source)
        if expected_revision != current["revision"]:
            raise RankReserveError(f"stale revision: expected {expected_revision}, current {current['revision']}")
        if any(Path(str(path) + suffix).exists() for suffix in ("-journal", "-wal", "-shm")):
            raise RankReserveError("backup sidecar already exists; choose a new destination")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        owned = True
        os.close(descriptor)
        target = sqlite3.connect(path, timeout=5.0, isolation_level=None)
        source.backup(target)
        target.execute("BEGIN")
        copied = _load(target)
        if copied != current:
            raise RankReserveError("backup replay does not match the source snapshot")
        target.rollback()
        complete = True
        return current
    except FileExistsError as exc:
        raise RankReserveError("backup destination already exists; backups never overwrite files") from exc
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        raise RankReserveError(f"cannot back up database: {exc}") from exc
    finally:
        for connection in (target, source):
            _close(connection)
        if owned and not complete:
            _cleanup_new(path)
