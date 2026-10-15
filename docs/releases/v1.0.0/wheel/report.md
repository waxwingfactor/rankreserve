# Independent verification of the actual public wheel

Separate AI-agent verification, completed 2026-10-15. **Passed; no release-artifact bug found.** Source and release assets were not modified by this verifier.

The [v1.0.0 release](https://github.com/waxwingfactor/rankreserve/releases/tag/v1.0.0) and all four assets were downloaded anonymously, without GitHub credentials. Each asset returned HTTP 200. Public GitHub API records resolve the tag to source commit `e36121c5de1b8378ac1e11ae56245f4427586e92`, tree `23b2aaf72c631185b72c79709bb70a57f1e25d32`. The [identified CI run](https://github.com/waxwingfactor/rankreserve/actions/runs/38794852686) has the same commit and all 11 jobs concluded successfully.

## Artifact identity

| Actual downloaded artifact | SHA256 |
| --- | --- |
| Wheel | `39c0a778a9bc5645e9bab31ef6b75b8c3a62f5f5097aa95fc9c98b7b761deb57` |
| Source distribution | `3d05123cd85559a2ffda0bcd2cf94dd2e4b06cfec958a72163b402be2f4a2ca9` |
| provenance.json | `ae3a5b9d5e223f0560cdc9c818b46cf67b87c1490bcc21d20087814a87cba176` |
| SHA256SUMS | `2ec5f4ae1baf27d8a3c4b6af4f8daf69976662440cf5d5f40c729296e2b87e1f` |

Computed hashes match the separately downloaded SHA256SUMS entries, provenance artifact hashes where listed, and every GitHub API asset digest. The wheel RECORD covers every archive member; all 11 hashed entries have valid SHA256 and size. Runtime metadata declares no third-party dependencies. The source archive was extracted after rejecting absolute/traversing paths and non-regular members. All 22 tracked package, documentation, test and script files in the source distribution match GitHub's exact commit tree using Git blob identities.

## Installation and tests

A fresh CPython **3.14.4** virtual environment on **macOS 26.5 arm64** installed the actual downloaded wheel with `python -I -m pip install --no-index --no-deps <downloaded-wheel>`. This installation did not need network access. Installed metadata confirms an archive install with the downloaded wheel hash, not an editable installation. The environment contains only pip 26.0.1 and RankReserve 1.0.0. Imports resolve to its site-packages; Python isolated mode was enabled and PYTHONPATH/PYTHONHOME were absent. Commands launched outside the development checkout.

The full test suite from the **actual downloaded source distribution** ran against that wheel: **33 passed in 25.520 seconds, zero failures, errors or skips**. This includes the 11 independent corruption/fault tests, hot-journal inspection and backup recovery, exact revision guards, two-process activation, outcome amendments and rank/date constraints. The downloaded smoke script also passed successful completion, exports, backup and operation after source-database removal. The installed console entry point reports version 1.0.0.

Installed core SHA256 is `c06f6be185938ff992b96dd289b958ba187a1951dcdfdc9ed59c517c65041873`; installed CLI SHA256 is `3392688e3ea5f5aa2a8633280e2ebfa33e5891b8d6f353d6ebb0d1c8a4823aa8`. Both match the wheel, provenance and committed source.

## Additional offline workflow

A verification wrapper actively rejected every Python `socket.*` operation for **24 additional CLI commands**. All commands produced their expected results, with **zero socket attempts**:

- Packaged example extraction and new synthetic campaign initialization worked.
- Premature activation and stale writes failed without state changes; `deferred` retained capacity.
- Only the lowest-ranked reserve activated. An explicit correction created a visible conflict, preserved activation and blocked more activation; a subsequent truthful correction remained possible.
- A separate pool exhausted its reserve supply and `--check-complete` returned 3.
- An off-plan incident held its pool while leaving the unused reserve unauthorized. An ordinary outcome on that unused reserve failed.
- Exported snapshot/history and every manifest hash matched revision 8. A backup moved to a different directory remained identical after the original database, design and example directory were removed.
- Missing and corrupt databases returned clear exit-2 failures; the missing path stayed absent and corrupt bytes stayed unchanged.

The constructed workflow deliberately ended with one incident-held pool and one exhausted pool. The successful-completion path was separately exercised by the downloaded acceptance suite and smoke script; neither exception state was reported as a completed campaign.

Machine-readable sanitized details, exact command arguments, public URLs, environment and observations are in `evidence.json`; test names/results are in `tests.log`.

## Limits

Publisher-supplied provenance, checksums and GitHub asset digests establish identity against those records, not independent publisher authenticity. This local verification covers the actual wheel on the environment above; it is separate from the public CI matrix. No customer adoption, production deployment or scientific validity was established. The supported single-coordinator independent-pool scope and documented security/statistical exclusions still apply. Source-distribution installation is a separate release check owned by another verifier.
