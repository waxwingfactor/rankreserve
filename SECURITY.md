# Security and data boundaries

RankReserve operates on local files and makes no network calls. Site IDs, labels, actor names and notes can contain sensitive information. Store the database, backups and exports under your organization's access controls. Nothing is encrypted by this application. No secrets or personal data belong in public issues.

The SQLite file must come from a trusted coordinator. Hashes detect accidental modification; they are not a digital signature or an adversarial integrity guarantee. A person with file access can rewrite the entire ledger. Neither audit history nor an approval note authenticates a person's identity.

CSV exports prefix formula-like text with an apostrophe for spreadsheet safety. Exact original values remain in JSON. Exports are evidence for people and are not supported import formats. Do not open an untrusted modified CSV as a spreadsheet.

Run on local storage. Network filesystems, concurrent disconnected copies, automatic multi-device merges and database edits with other tools are unsupported. Back up using the supported command, not a live filesystem copy. Keep a separate backup before moving a campaign between machines.

For a suspected vulnerability, use GitHub's private vulnerability reporting if available; otherwise open a minimal issue without sensitive data. This volunteer project has no response-time guarantee.
