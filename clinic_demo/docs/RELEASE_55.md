# clinic_demo 19.0.1.0.55

Authoritative baseline: clinic19a(20260916-071217).md. User evidence: 13/40 validated journeys, operations.encounter PARTIAL, expected in_progress but found done. The supplied screenshot shows the top of the form; the existing notebook page lies lower down. No new log attachment was provided in this upload set.

## Corrections

The operations.treatment_session generator explicitly completes DEMO-ENC-LIVE-001 through owner workflow. Encounter validation now accepts this downstream completion only when DEMO-SESSION-001 belongs to operations.treatment_session, is done, references the same encounter and declared booking, matches company and patient, has valid actual chronology matching the encounter and a completed procedure. An unrelated done record or missing downstream evidence still fails. No state is reverted and no business record is changed by this validation correction.

Journey Progress now has both a visible header button and a top smart button. Both open the existing run-scoped journey list with Details and Execute Current. The existing notebook tab remains. All 40 journeys and the single execution engine remain unchanged.

Predecessor version/source adoption includes 19.0.1.0.54 as well as the existing .53 lineage. Latest modelbymodel prompt retained verbatim in GOVERNING_MODEL_BY_MODEL.md.

## Install and resume

Replace the full clinic_demo folder; restart Odoo, Update Apps List and upgrade clinic_demo to 19.0.1.0.55. Other addons do not require replacement. Open the same Demo Run, Refresh Compatibility, then Reconcile Existing Dataset. Click Journey Progress at the top to inspect the table, then Execute Next / Resume as needed. No Reset. PASS count is determined from actual records, not predetermined by this release.

## Evidence

214 source/behavior tests PASS. Main addon guardrail PASS. Composite Python/XML parsing PASS; raw counts in evidence_55/parse.json. Native Odoo database upgrade and reconciliation NOT RUN here. Reporting L1–L8 volume completion remains a separate outstanding scope. This release does not claim full dataset runtime acceptance.






