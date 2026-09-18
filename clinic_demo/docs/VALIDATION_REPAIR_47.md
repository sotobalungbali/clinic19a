# v47 — Readiness diagnostics and acceptance correction

Status: partial repair. Full enterprise acceptance remains incomplete.

## Confirmed findings

The 20260910-232621 composite contains clinic_demo v46, including the
clinic.appointment fresh_db_reset_only policy and interpolated model errors.
The copied traceback goes through execution_engine.generate, not the current
Validate service. It can be historical evidence; a cached worker is not proven.
The newest attachment set has no new Odoo log file.

Five report source families have no explicit producer in the current generator
source: insurance authorization, completed treatment product usage, membership
contract, posted wallet transaction, and procedure session. This is a dataset
coverage gap. Their owner report engines count different models from the masters
and treatment-session records that the dataset does generate.

## Implemented

- Live loaded Appointment reset policy check in each Validate call.
- Version and timestamp on refreshed validation evidence; old Expected/Actual
  values are replaced together with the result message.
- Missing Done checkpoints fail readiness instead of being skipped.
- Report failures block readiness instead of being downgraded to warnings.
- Source model and period diagnostics for all five missing transaction families.
- Positive primary metric requirements retained; no KPI write or waiver.
- Success wording no longer claims a fresh-DB/reset rehearsal was executed.

## Installation and next work

This is a diagnostic/acceptance repair, not a complete dataset fix. It is not
necessary to rerun the presentation database to confirm the five known gaps.
Complete and audit the missing owner workflows before requesting final acceptance:
authorization; real inventory consumption; member contract; wallet posting;
procedure session. Then refresh owner-generated reports and dependent snapshots
using deterministic references, and validate on a disposable test database.

If installing this package, stop the Odoo process serving the database, replace
the full clinic_demo directory, restart, upgrade clinic_demo to v47, and refresh
compatibility. Never reset the established presentation run for this change.
Historical logs remain unchanged; current Validation Results carry v47/time.

No Odoo/PostgreSQL runtime or native end-to-end test was executed in this workspace.
Do not classify this release as READY FOR DEMO based solely on static tests.














