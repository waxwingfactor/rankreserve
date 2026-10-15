# Release verification

**Version 1.0.0 is publicly released and verified.** The actual published wheel and source distribution passed separate independent download, identity, installation, full-suite and relocated/offline workflow checks on 2026-10-15. Read the [dated public verification report](releases/v1.0.0.md), including exact revisions, artifact hashes, CI and separate verifier evidence. Local builds alone were not used to establish public verification.

## Reproducible checks

The repository includes independent installed-CLI acceptance tests, integrity/fault tests, `scripts/smoke.py`, and `scripts/check_dist.py`. CI installs a non-editable package on Linux, macOS and Windows with Python 3.10, 3.12 and 3.14. A separate job builds and installs wheel and source distributions in fresh environments. `quality` aggregates all required jobs and gates protected main. AI-agent reviews are recorded as AI reviews; no human or separate-account approval is implied.

Release assets include a universal Python wheel, source archive, `SHA256SUMS` and a provenance JSON with the exact source revision, build environment and artifact hashes. Compare local SHA256 values with both the manifest and GitHub's asset digest. A hash match establishes artifact identity against those records, not independent trust in the publisher.

The completed public checks used fresh directories outside the development checkout, separate wheel/source environments, no editable install or `PYTHONPATH`, and the actual downloaded assets. They exercised the learning workflow, incomplete/guard failures, corrections, incidents, exports and relocated backup use. The report distinguishes those two actual-public macOS environments from the nine exact-source CI combinations. The v1.0.0 source archive was built before this external verification; this post-release report is published separately without replacing its assets.

No production deployment, customer adoption, measured time savings or external human review is claimed. The program's hash chain is an operational consistency check, not a signature, identity proof or complete deletion detector.
