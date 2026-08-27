# ClinicOne — clinic_care_plan Structural Inventory

## Authoritative scope
- Baseline: user-supplied ClinicOne source dump dated 2026-08-14.
- Backup rule: every file whose basename begins with `0` is excluded.
- Functional baseline status: FINISHED; hardening is preservation-first.
- Manifest dependency list: preserved exactly (28 dependencies).

## Active Python graph
Required baseline imports:
- `models/care_plan.py`
- `models/procedure_session_inherit.py`
- `models/emar_prescription_inherit.py`
- `models/care_protocol.py`
- `models/care_plan_line.py`
- `models/care_protocol_step.py`
- `models/practitioner_inherit.py`

Additive enterprise integration imports:
- `models/patient_inherit.py`
- `models/doctor_inherit.py`
- `models/encounter_inherit.py`

Dormant source preserved and not imported:
- `models/models.py`

## Persistent custom models
1. `clinic.care.plan`
2. `clinic.care.plan.line`
3. `clinic.care.protocol`
4. `clinic.care.protocol.step`

## In-place model extensions
- `clinic.procedure.session`
- `clinic.emar.prescription`
- `clinic.practitioner`
- `clinic.patient`
- `clinic.doctor`
- `clinic.encounter`

## Data/UI/security/report surface
- Python files: 18
- XML files: 11
- Active model modules: 10
- Persistent custom models: 4
- In-place extensions: 6
- Active `models.Constraint`: 4
- Active legacy `_sql_constraints`: 0
- ACL rows: 4
- Company record rules: 4
- Sequences: 2
- Search/List/Form coverage: 4 / 4 / 4
- Calendar views: Care Plan, Care Plan Line
- QWeb reports: Care Plan Summary
- Optional post-init UI integrations: Patient, Doctor, Encounter, ClinicOne root menu

## Integration contracts
`clinic.care.plan` anchors Patient, Doctor, Practitioner, Encounter, Consent,
Vitals/Triage, Booking, Treatment, Procedure Sessions, eMAR Prescriptions,
Products, Invoices and Attachments.

`clinic.care.plan.line` anchors Booking, Treatment, Product/UoM, Procedure
Session, eMAR Prescription, invoice lines, attachments and dependency DAG.

Procedure Session and eMAR receive both `care_plan_id` and
`care_plan_line_id`, with company/parent consistency checks and direct-link
synchronization back to the Care Plan Line.
