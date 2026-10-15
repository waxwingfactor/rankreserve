# RankReserve

An offline coordinator's ledger for **already approved, ranked environmental survey replacement pools**.

RankReserve records human site dispositions, activates the next reserve when a slot opens, and preserves the history needed for analyst handoff. Temporary holds keep their slots. Exhaustion and corrections that overcommit a target are visible exceptions.

## Install

Use Python **3.10 or newer** on Linux, macOS or Windows. Download the wheel from the [v1.0.0 release](https://github.com/waxwingfactor/rankreserve/releases/tag/v1.0.0), then install into a virtual environment:

```sh
python -m venv .venv
# macOS/Linux; on Windows use .venv\Scripts\activate
. .venv/bin/activate
python -m pip install --no-deps rankreserve-1.0.0-py3-none-any.whl
rankreserve --version
```

The downloaded wheel installs and runs offline with no third-party runtime packages. The source distribution includes documentation, tests and examples; building it also needs setuptools 77 or newer (pip normally obtains the build dependency). GitHub Releases is the distribution channel; this project does not claim a PyPI publication. Compare downloaded files with `SHA256SUMS` and the GitHub asset digest; see [verification](docs/verification.md).

## A complete learning workflow

These are **constructed sites and observations**, not a real survey or an approved protocol. Every write requires the campaign revision you last inspected. The sequence below starts at revision zero; rejected input and guard checks do not advance it.

```sh
rankreserve examples --out example
rankreserve init example/design.csv --db campaign.sqlite --actor coordinator \
  --approval-note "Learning exercise only" --protocol-ref "Constructed protocol v1" \
  --completion-rule "Coordinator confirms all required sampling complete"
rankreserve status --db campaign.sqlite

# A permanent human disposition opens one Inland slot. Temporary holds do not.
rankreserve record I-001 access_denied --db campaign.sqlite --actor coordinator \
  --note "Constructed denial recorded" --observed-on 2026-10-15 --expect 0
rankreserve activate --pool Inland --db campaign.sqlite --actor coordinator \
  --note "Use next approved reserve" --observed-on 2026-10-15 --expect 1

# I-003 is now active. Active sites may be completed in any travel order.
rankreserve record I-003 sampled --db campaign.sqlite --actor coordinator \
  --note "Required work confirmed complete" --observed-on 2026-10-15 --expect 2
rankreserve record I-002 sampled --db campaign.sqlite --actor coordinator \
  --note "Required work confirmed complete" --observed-on 2026-10-15 --expect 3
rankreserve record T-001 sampled --db campaign.sqlite --actor coordinator \
  --note "Required work confirmed complete" --observed-on 2026-10-15 --expect 4
rankreserve status --db campaign.sqlite --check-complete
rankreserve export --db campaign.sqlite --out handoff
rankreserve backup --db campaign.sqlite --out safe-copy.sqlite --expect 5
```

`--json` on any database command returns the full machine-readable snapshot. `python -m rankreserve` is equivalent to the console command. Shell commands above use POSIX line continuation; on PowerShell enter each command on one line.

## Use with an approved real design

Have the design authority approve the mapping into these exact CSV columns:

```csv
site_id,pool,rank,role,label
B-10,Watershed-A,10,base,First planned site
B-20,Watershed-A,20,base,Second planned site
R-30,Watershed-A,30,reserve,First reserve
R-40,Watershed-A,40,reserve,Second reserve
```

Each independent pool's base count is its fixed completion target. The rank is an explicit positive integer, with every base before its reserves. The program never derives rank from a site ID or pool from a stratum/panel label. It never modifies the imported design. `label` is optional; every other column is required. Other columns are rejected so unintended data loss is visible. Keep coordinates, statistical weights, permission forms and measurement data in the original authoritative system; join exports by unchanged site ID.

An `approval-note` records your assertion; the software cannot verify approval. `protocol-ref` and `completion-rule` describe the common policy applicable to the campaign. A visit, partial measurements or pending lab result alone do not establish `sampled`.

| Human disposition | Effect |
| --- | --- |
| `pending`, `ready`, `deferred` | Keep an active commitment; no replacement slot. `ready` is a coordinator label, not an access permit. |
| `sampled` | Count one protocol-confirmed completion. |
| `non_target`, `access_denied`, `inaccessible`, `not_sampleable` | Final human rejection opens a slot, with a required reason. |
| `unused` | Read-only status of a reserve that has never been activated. |

Activation chooses exactly the lowest unused reserve rank in that pool when a slot is open. A failed reserve leaves the same deficit open. There is no arbitrary reserve selection, skipping, automatic cross-pool substitution or automatic activation. `sampled + unresolved == target` means work is committed; completion requires all target completions and no unresolved work.

## Corrections and exceptions

Ordinary `record` updates an active unfinalized site. To correct an outcome, inspect `status --json`, find that site's `last_outcome_revision`, and supply it as `--amend N`, alongside the current campaign `--expect N`. These are different revision numbers. Changing a final outcome requires an amendment. Both old and new facts remain in history.

If a correction makes completions plus active commitments exceed the target, that pool enters `conflict`. Further activation is blocked. Existing activations remain visible; truthful corrections and exports remain possible. Consult the design authority; the tool never cancels downstream work to hide the conflict.

For an off-plan observation, such as an unactivated reserve being sampled, the following continues the learning campaign at revision 5:

```sh
rankreserve incident I-004 --db campaign.sqlite --actor coordinator \
  --note "Crew reported off-plan sampling; analyst review needed" \
  --observed-on 2026-10-15 --expect 5
```

An incident records evidence without authorizing a past action or changing disposition. It permanently places that pool on `exception` hold in version 1. Export it for analyst review. Incident clearance, design changes and retroactive authorization are outside this release's supported scope. A reserve `sampled` date earlier than its activation decision date is rejected with incident guidance, including on amendment. Day precision cannot prove the order of same-day activity.

## Handoff, recovery and limits

An export contains a consistent `snapshot.json`, `history.json`, all-site `sites.csv`, active-unfinalized `queue.csv`, readable `summary.txt`, and a completion/hash `manifest.json` written last. It includes untouched reserves distinctly from pending active sites. JSON preserves exact original text; CSV neutralizes formula-like text for spreadsheet use. Treat an interrupted export without its manifest as incomplete and create a fresh export. Export folders and backup files must be new. Neither operation overwrites existing paths.

Use `backup`, close all commands, and move the resulting SQLite file to relocate a campaign. The database stores no absolute paths. Keep one authoritative copy; disconnected database copies cannot merge. A stale write fails without a new event. Inspect the current revision and reconcile the intended observation before retrying. After an interruption or output/disk failure, inspect before retrying: a commit may have succeeded before its receipt was delivered. Local SQLite transactions serialize competing writes and roll back interrupted uncommitted operations. Keep a crashed database with its rollback journal until SQLite recovery completes. A backup is a snapshot, not another ledger event.

Exit codes: **0** command completed; **2** input, guard, storage or corruption failure; **3** `status --check-complete` found at least one incomplete, exhausted, conflicted or incident-held pool. Ordinary `status` is an inspection command and returns 0 for valid incomplete campaigns.

It does not draw samples, decide eligibility, adjust weights, infer replacement pools, or certify statistical validity. One local coordinator owns the authoritative database. Survey-specific panel cascades, revisits, shared pools, nearest-neighbor replacements, distributed synchronization, and automatic EPA submission are outside its scope.

MIT licensed. No accounts, telemetry, services, or runtime dependencies.

Read [contracts and failure modes](docs/contracts.md), [bounded research and alternatives](docs/research.md), [positioning and constructed scenarios](docs/positioning.md), [architecture](docs/architecture.md), [verification](docs/verification.md), and [security boundaries](SECURITY.md). Report bugs through [GitHub issues](https://github.com/waxwingfactor/rankreserve/issues); maintenance is best effort and no service-level promise is offered.
