# RankReserve v1.0.0 — independent public source verification

Verified 2026-10-15 by a separate AI acceptance and release-verification agent. **Result: passed.** This report uses the actual anonymously downloaded public source distribution. No development-checkout tests or package were used as release evidence.

## Public artifact and source identity

Release: [RankReserve v1.0.0](https://github.com/waxwingfactor/rankreserve/releases/tag/v1.0.0), public release ID `414198198`, published 2026-10-15 19:35:33 UTC, neither draft nor prerelease.

| Downloaded asset | SHA-256 |
| --- | --- |
| [rankreserve-1.0.0.tar.gz](https://github.com/waxwingfactor/rankreserve/releases/download/v1.0.0/rankreserve-1.0.0.tar.gz) | `3d05123cd85559a2ffda0bcd2cf94dd2e4b06cfec958a72163b402be2f4a2ca9` |
| [SHA256SUMS](https://github.com/waxwingfactor/rankreserve/releases/download/v1.0.0/SHA256SUMS) | `2ec5f4ae1baf27d8a3c4b6af4f8daf69976662440cf5d5f40c729296e2b87e1f` |
| [provenance.json](https://github.com/waxwingfactor/rankreserve/releases/download/v1.0.0/provenance.json) | `ae3a5b9d5e223f0560cdc9c818b46cf67b87c1490bcc21d20087814a87cba176` |

All three computed hashes matched the anonymous GitHub release API's asset digests. The source archive also matched both the downloaded checksum manifest and publisher provenance. Downloads used public URLs without authentication headers.

The annotated tag object `d46d71203c68cd31e773f60b029ff6b871f075e0` resolves to [source commit e36121c5de1b8378ac1e11ae56245f4427586e92](https://github.com/waxwingfactor/rankreserve/commit/e36121c5de1b8378ac1e11ae56245f4427586e92). Its tree `23b2aaf72c631185b72c79709bb70a57f1e25d32` matches the provenance. The [recorded CI run](https://github.com/waxwingfactor/rankreserve/actions/runs/38794852686) is complete and successful at that exact commit; public API metadata reported success for all 11 jobs, including `quality`.

Before extraction, all 37 archive members were checked for absolute paths, parent traversal, unexpected roots, symlinks, hardlinks and special files. Only regular files and directories were accepted. Required documentation, license, security guidance, contracts, research, positioning, architecture, tests, smoke/distribution scripts, and packaged example CSV/instructions were present. No user-home or CI-workspace path markers were found in archive contents.

## Fresh source build and installation

Environment: **CPython 3.12.13; macOS 26.5 arm64; SQLite 3.53.0; pip 26.0.1**. A fresh virtual environment built and non-editably installed the downloaded archive through isolated PEP 517. Only the declared build dependency required network access; runtime has no third-party dependency.

Command pattern, with portable placeholders:

```sh
env -u PYTHONPATH -u PYTHONHOME <fresh-venv>/bin/python -I -m pip --isolated install \
  --no-deps --no-cache-dir --use-pep517 <downloaded-sdist.tar.gz>
```

Installation metadata records the downloaded archive's SHA-256 above and no editable install. The imported package resides inside the fresh environment's `site-packages`. Installed `core.py` and `cli.py` hashes match both provenance and independently downloaded raw files at the public source commit:

| Installed module | SHA-256 |
| --- | --- |
| `core.py` | `c06f6be185938ff992b96dd289b958ba187a1951dcdfdc9ed59c517c65041873` |
| `cli.py` | `3392688e3ea5f5aa2a8633280e2ebfa33e5891b8d6f353d6ebb0d1c8a4823aa8` |

## Observed execution

From a working directory outside both extracted source and development checkout:

```sh
<fresh-venv>/bin/python -I -m unittest discover -s <extracted-sdist>/tests -v
<fresh-venv>/bin/python -I <extracted-sdist>/scripts/smoke.py
```

**All 33 shipped tests passed in 27.613 seconds, with zero failures, errors or skips.** This includes the installed-CLI acceptance suite and integrity/fault tests, including hot-journal status/backup recovery. The shipped smoke script passed ordered activation, premature/stale mutation refusal, completed sampling, full export, backup and source-database removal.

The entire learning-workflow shell block from the downloaded README ran verbatim through the installed console command in a fresh directory and reached complete revision 5. Its export contained the final manifest. Additional independent checks observed:

- Stale mutation, unnecessary activation and sampling an unactivated reserve return exit 2 without changing the snapshot.
- An explicit correction after replacement retains activation, reports overcommitment, blocks activation, and causes completeness inspection to return exit 3.
- The downloaded README's incident command runs successfully, preserves the unused reserve's disposition, and holds the pool as an exception.
- A backup moved to a new directory remains inspectable and exportable after deleting the extracted source tree, original campaign database, and example design CSV. The resulting snapshot exactly matches the expected recorded conflict.

`PYTHONPATH` and `PYTHONHOME` were removed throughout these independent execution checks. Isolated Python mode was used for package commands, and the runtime checks ran in the restricted default sandbox without needing network access. Evidence is recorded in the adjacent sanitized `evidence.json`.

An initial extraction helper invoked the older host default interpreter and stopped before extraction because that interpreter lacked the requested tar filter API. Safe extraction and every product build/test were then performed with the specified CPython 3.12.13 interpreter. This was a verifier setup correction; no product test failed.

This agent independently exercised one local OS/Python environment and inspected public CI metadata for the remaining jobs. Publisher hashes establish identity against those records, not independent trust in the publisher. Synthetic workflow verification does not establish adoption, production use, scientific design validity, legal access or field safety. No release artifact failure was found.
