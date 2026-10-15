# Release verification

The release is complete only after the actual public assets have been independently downloaded, checked and installed. Local build results alone do not establish public release verification.

## Reproducible checks

The repository includes independent installed-CLI acceptance tests, integrity/fault tests, `scripts/smoke.py`, and `scripts/check_dist.py`. CI installs a non-editable package on Linux, macOS and Windows with Python 3.10, 3.12 and 3.14. A separate job builds and installs wheel and source distributions in fresh environments. `quality` aggregates all required jobs and gates protected main. AI-agent reviews are recorded as AI reviews; no human or separate-account approval is implied.

Release assets include a universal Python wheel, source archive, `SHA256SUMS` and a provenance JSON with the exact source revision, build environment and artifact hashes. Compare local SHA256 values with both the manifest and GitHub's asset digest. A hash match establishes artifact identity against those records, not independent trust in the publisher.

Public verification must use a fresh directory outside the development checkout, separate wheel/source environments, no editable install or `PYTHONPATH`, and the actual downloaded assets. It exercises the learning workflow, incomplete/guard failures, corrections, incidents, exports and relocated backup use. A final dated report records observed results, exact source/check revisions, hashes and public download URLs. Until that report is present, verification is pending.

No production deployment, customer adoption, measured time savings or external human review is claimed. The program's hash chain is an operational consistency check, not a signature, identity proof or complete deletion detector.
