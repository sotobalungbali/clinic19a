# clinic_demo 19.0.1.0.49 — Compatibility adoption repair

## Install and complete the existing run

1. Stop Odoo and replace the complete clinic_demo folder with this package.
2. Start Odoo, Update Apps List, and upgrade clinic_demo to 19.0.1.0.49.
3. Open the SAME Demo Run with Demo Safe Mode enabled. Click Refresh Compatibility.
4. Once Compatible, click Complete Source Journeys. This refreshes the five source journeys and Reports/Dashboard/Analytics, resumes pending acceptance checkpoints through the normal generation engine, then runs Validate. Any generation failure retains its normal failure notification and evidence.
5. READY FOR DEMO is the target result. Upgrade success and Compatible alone are not readiness acceptance.

Do not Reset Dataset, edit fingerprints manually, or create a replacement run. The five owner fixes delivered in v48 must remain installed: clinic_inventory 19.0.1.0.3, clinic_encounter 19.0.1.0.1, clinic_membership 19.0.3.0.7, clinic_wallet 19.0.3.0.6 and clinic_dashboard 19.0.1.0.2. They are unchanged in the latest supplied composite and are not included in this one-addon repair ZIP. All other 41-companion contract requirements remain unchanged; see services/constants.py.

## Diagnosis and explicit migration contract

The v48 release-stage adoption predicate required a stored run version between .43 and .47, exactly 35 checkpoint rows, and every registered generator Done. The stored run version can lag the installed addon, and acceptance failures can legitimately leave an otherwise complete producer chain below 35 Done. These restrictions could block source closure before it had a chance to resolve readiness failures.

The supplied short Odoo log does not include the actual run metadata or checkpoint inventory. Thus the exact predicate that rejected this particular run is not proven from the log. This repair covers the identified source-level migration defects and adds precise rejection diagnostics.

The supported predecessor matrix is explicit:

| Stored source SHA-256 | Stored generator versions |
|---|---|
| 8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2 | 19.0.1.0.31 through 19.0.1.0.47 |
| b087fa986bed9b26d1ee87b10d02f277ffd4557dad05f81d236fdcf552b8fb0e | 19.0.1.0.48 |

For release-stage adoption, management.analytics must be Done and each Done generator must have all its dependencies Done. Every checkpoint must identify a known generator, declared scenario, matching phase and canonical phase:generator:scenario key. Historical additional scenario rows are permitted. Reference producers must be registered and reference identities must use DEMO-. Busy runs, running checkpoints, missing provenance, unknown lineage and inconsistent dependencies are blocked. Pending/failed MP23 acceptance gates are allowed and executed normally after source closure.

Both on-disk AND database-installed companion versions must match the current build before migration. A recognized old hash alone cannot authorize migration. Release-stage rejection cannot fall through to the older progressive-stage adoption rules.

Only the run's build metadata is adopted. A control log records previous and new version/source/suite plus retained reference/checkpoint counts. Business data, checkpoint identities, original checkpoint fingerprints and execution history remain intact. Acceptance is never marked Done by migration. Refresh Compatibility and Validate use the same native run lock as generation to serialize these actions.

The five source journeys, deterministic names/dates, ownership checks, mandatory report metrics and retain/reverse reset contracts from v48 are preserved. No production sequence is introduced by this repair. Executive script and completeness matrix remain in docs; v49 changes migration/orchestration, not the described clinical or commercial scenarios.

## Acceptance boundary

See TEST_REPORT_49.md for executed checks. This package has not been run against the user's database or a native fresh Odoo database. Overall completion requires the target READY FOR DEMO evidence and the separate disposable-database reset/regeneration rehearsal; source tests alone do not establish runtime acceptance.












