# clinic_demo 19.0.1.0.56 — canonical patient bridge

Baseline: clinic19a(20260916-082029).md and supplied odoo(20260916-081859).log. The user's Execute Current action correctly addressed operations.encounter. The failure is a defect in the v55 validator, not an incorrect user action.

## Root cause

The v55 downstream-completion check compared session.patient_id (res.partner) directly with encounter.patient_id (clinic.patient). Distinct ORM models are not the same patient record even if their numeric IDs happen to match. The old test used the same scalar on both sides and therefore failed to model the real contract.

## Correction

Validate session.clinic_patient_id against encounter.patient_id, session.patient_id against encounter.patient_id.partner_id, and booking.patient_id against the session partner. Preserve the other provenance, owner, encounter/session/booking link, company, completed-procedure and chronology checks. No status rollback, reset, business-data deletion or sequence calls were introduced. Every unmet downstream condition now has an explicit diagnostic instead of only the generic expected-state message.

The Journey Progress primary model for operations.encounter is now clinic.encounter, rather than the first auxiliary owned model clinic.encounter.stage. Registry keys and dependency order do not change.

## Upgrade and exact steps

1. Stop Odoo, replace the entire clinic_demo folder, start Odoo and upgrade clinic_demo to 19.0.1.0.56. Companion addons stay unchanged.
2. Open DEMO-RUN-00001 (the same run). Refresh Compatibility, then Reconcile Existing Dataset.
3. Open Journey Progress. If row 14 passes, return through Demo Run and click Execute Next / Resume. No checkbox selection is required; the first non-PASS journey is selected automatically.
4. To run one chosen journey, open its Details and click Execute Current there. The Execute Current button on the main run instead requires Selected Journey to be set.
5. If row 14 remains non-PASS, its diagnostic will list the specific unmatched completion evidence. Do not Reset or manually alter clinical state to force a pass.

Existing FAILED state can reconcile to PASS when actual evidence validates. No fixed PASS count or acceptance of later journeys is promised.

## Evidence

216 source/behavior tests PASS, including typed patient records with equal numeric IDs but different comodels, valid canonical mapping and negative relationship/chronology/provenance cases. Owner field declarations are checked directly from the composite. Addon and Encounter/Treatment Session guardrails pass at source/static level; composite Python/XML parsing passes. Native Odoo database execution is NOT RUN here. Reporting L1–L8 population completion remains separate and outstanding.

The latest modelbymodel prompt is retained verbatim in GOVERNING_MODEL_BY_MODEL.md. Existing 40-journey execution architecture and supported build lineage remain in force, including explicit v55 adoption.





