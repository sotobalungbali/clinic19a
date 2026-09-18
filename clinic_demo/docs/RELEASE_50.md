# clinic_demo 19.0.1.0.50 — Historical checkpoint continuity

## Installation and target workflow

1. Stop Odoo and replace the complete clinic_demo folder from this ZIP.
2. Start Odoo, Update Apps List, and upgrade clinic_demo to 19.0.1.0.50.
3. Open the SAME Demo Run. Keep Demo Safe Mode enabled; click Refresh Compatibility.
4. Once Compatible, click Complete Source Journeys. Existing source records are resolved by their deterministic keys, reports and dashboard/analytics evidence are refreshed, pending acceptance gates run normally, then Validate executes automatically.
5. Expected final target: READY FOR DEMO. No reset, new run, or manual fingerprint edit is needed.

Only clinic_demo changes. The v48 companion contract remains required: clinic_inventory 19.0.1.0.3, clinic_encounter 19.0.1.0.1, clinic_membership 19.0.3.0.7, clinic_wallet 19.0.3.0.6, clinic_dashboard 19.0.1.0.2; all other companion versions remain pinned in services/constants.py.

## Exact historical contract

The reported run stores version 19.0.1.0.45 and source 8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2. These are supported. v49 rejected the checkpoint key 12_resources:resources.rooms_devices:SCN-QUEUE-01 because the current generator declares SCN-BOOKING-TODAY-01.

v50 explicitly recognizes that persisted resource checkpoint as historical. The current resource generator retains its canonical booking scenario for new runs. No global relaxation of scenario validation is introduced.

| Generator | Phase | New-run scenario | Accepted historical checkpoint key |
|---|---|---|---|
| resources.rooms_devices | 12_resources | SCN-BOOKING-TODAY-01 | 12_resources:resources.rooms_devices:SCN-QUEUE-01 |

The historical row must have the exact resource generator and phase, owner provenance, and either its historical SCN-QUEUE-01 scenario metadata or canonical SCN-BOOKING-TODAY-01 metadata (older retry code could update metadata without renaming its key). Unknown keys/scenarios, wrong owners/phases, running checkpoints and dependency gaps still block adoption. Native companion versions must match on disk and in the database.

The same mapping is used before checkpoint creation during generation. If no canonical row exists, the existing historical row is reused. Done rows are untouched and skipped normally. Failed/pending rows retain their original key and scenario metadata while the ordinary execution engine retries them; no Done state is fabricated. If a canonical row already exists, it takes precedence. Historical execution records are not deleted or renamed.

Supported source lineage additionally includes v49 so successful v49 runs can adopt v50. The migration updates build metadata and logs its prior values. The five report-source journeys, deterministic business names/dates, reset policies and source-backed readiness requirements remain intact.

See CANONICAL_CHECKPOINT_MATRIX_50.md for all 35 generator contracts, and TEST_REPORT_50.md for executed evidence. Older release notes are historical; these instructions supersede them.











