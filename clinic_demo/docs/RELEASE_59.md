# Release 19.0.1.0.59 — Anchor-relative future pipeline

Baseline: clinic19a(20260917-062845).md, SHA256
8f01b48ec0c689129c5142a25c254211c35308761fd00b22d2dfc2174a48b110.
Only clinic_demo changes. Companion addon versions and suite fingerprint remain unchanged.
The governing Model-by-Model prompt remains bundled as GOVERNING_MODEL_BY_MODEL.md.

## Cause and evidence boundary
The previous validator accepted only pending/scheduled tasks. The source owner cron
unconditionally ages undelivered internal tasks into due when wall time passes their
deadline, even with auto_send=False. A fixed anchor of August 27 produces September
17 failures at +1/+7/+14 consistent with this behavior. The supplied log does not
contain the actual task states; this cause is established as a source-contract defect,
not a claim to have queried the user's database.

## Contract
Future means after the run's fixed anchor, not perpetually after today's wall clock.
All six horizons (+1/+7/+14/+30/+60/+90) accept pending/scheduled/due as open,
undelivered work only when the exact timezone-derived UTC deadline, deterministic
reference, source plan, assignee and company match. sent_at, contacted_at,
completed_at or send_count prohibit adoption. Sent/contacted/completed/cancelled/
overdue/escalated states remain rejected. Channel must be internal, auto_send and
escalate_if_overdue must remain false.

No state rewind, clock shift, delivery-evidence deletion, production sequence,
record recreation or owner cron alteration is performed. Normal internal staff
activities created by the owner cron are retained. Existing follow-ups are checked
as a complete set before creating missing follow-ups. Invalid existing data blocks
with its actual state or mismatched contract, rather than being silently rewritten.
Reference reads use the explicit functional actor policy in both generation and
validation, including the source telemedicine prerequisite. Future booking, care
plan and telemedicine workload checks remain active.

## Installation and continuation
1. Stop Odoo; replace the entire clinic_demo directory from this ZIP.
2. Start Odoo, update Apps List, and upgrade clinic_demo to 19.0.1.0.59.
3. Open the same Demo Run. Refresh Compatibility adopts the explicit v58 lineage.
4. Reconcile Existing Dataset; review Journey Progress.
5. Execute Next / Resume automatically selects the first journey not PASS.
Do not reset the dataset or manually change task states/anchor. A clean due-only
mismatch should now reconcile PASS without executing the existing tasks again.
No promise is made that the remaining journeys or overall readiness are complete.

## Validation
227 source/behavior tests PASS (record doubles, not native Odoo).
clinic_demo guardrail PASS; Post-Care owner guardrail PASS (source/static).
Whole composite: 933 Python and 517 XML parsed, zero failures.
Regression coverage: six horizons, owner cron aging, repeat no-op validation,
delivery and terminal state rejection, missing records, scope/safety corruption,
exact UTC timestamps, DST and extreme timezone offsets.
Native Odoo database execution remains pending on the user's installation.
Raw evidence is bundled in docs/evidence_59.


