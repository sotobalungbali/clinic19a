# v50 verification

- 187 source-contract and isolated behavioral tests: PASS.
- Actual 35-generator registry is inspected, including phase, declared scenarios and dependencies. The reported v45 historical resource checkpoint is exercised against this full matrix.
- Exact historical-key acceptance is checked with both legacy and canonical scenario metadata. Unknown scenarios/cross-owner tuples and absent owner provenance remain blocked.
- Checkpoint service behavior is executed with record doubles: Done alias reuse without writes/creation, failed retry without identity or completion-state rewriting, canonical-row precedence.
- Six guardrails: clinic_demo, clinic_inventory, clinic_encounter, clinic_membership, clinic_wallet, clinic_dashboard: PASS.
- Entire composite: 916 Python AST parses and 516 XML parses, zero errors.
- All 41 companion manifests and canonical suite fingerprint: MATCH.
- Raw output is included in validation_50. ZIP CRC and per-file SHA-256 inventory are checked during packaging.

Authoritative input: clinic19a(20260914-092045).md. Source SHA-256: bc1a2c4bbaae99e279c91c23f3ad5b8bd8da5e6d2960e84a397491134386755c.

These are source checks and isolated behavior tests, not native Odoo transaction tests. The user-visible error identifies the exact blocked key; the supplied server log records the compatibility button call but does not contain a database checkpoint dump. Native upgrade, final target Validate, concurrency and disposable-database reset/regeneration have not been executed here. READY FOR DEMO must be established by the target runtime.











