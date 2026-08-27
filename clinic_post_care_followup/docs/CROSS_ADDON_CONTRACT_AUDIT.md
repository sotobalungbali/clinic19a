# Cross-Addon Contract Audit

Authoritative bundle: ClinicOne source supplied by the user on 2026-08-20.

## `clinic_staff`

Verified live contracts:
- model `clinic.staff`;
- `partner_id`;
- `company_id`;
- `branch_id`;
- `is_active`;
- `postcare_task_count`;
- `action_open_postcare_tasks()`.

The current Staff implementation explicitly anticipates:

`res_model = "clinic.postcare.task"`

and historically comments an intended domain using:

`assignee_id`.

Addon 26 supplies exactly that technical contract and overrides Staff's shared
count compute only to populate the already-existing Post-Care counter.

Staff master, roster, assignment and KPI ownership remain in `clinic_staff`.

## `clinic_patient`

Verified live contracts:
- `clinic.patient`;
- `partner_id`;
- `company_id`;
- phone/mobile/email.

Addon 26 adds only navigation/count relationships to its own Post-Care models.

## `clinic_encounter`

Verified live contracts:
- `patient_id -> clinic.patient`;
- `doctor_id -> clinic.doctor`;
- `treatment_id -> clinic.treatment`;
- `procedure_line_ids`;
- `date_end`;
- state `done`.

Addon 26 does not replace `action_done`.
Automatic generation is performed by an opt-in Post-Care cron after completed
Encounters, preserving Encounter workflow ownership.

## `clinic_booking`

Verified live contracts:
- `patient_id -> res.partner`;
- `doctor_id`;
- `treatment_id`;
- `end_datetime`;
- state `done`.

Addon 26 resolves the Patient Card by Partner and creates a Post-Care Plan only
through an explicit action.

## `clinic_care_plan`

Verified live contracts:
- `patient_id`;
- `doctor_id`;
- `encounter_id`;
- `booking_id`;
- `protocol_template_id`;
- `instruction_note`.

Post-Care may reuse the Care Plan instruction note but does not move care
pathway ownership.

## `clinic_treatment_catalog` / `clinic_encounter`

Post-Care Protocol applicability uses existing:
- `clinic.treatment.catalog`;
- `clinic.procedure.catalog`.

The live `clinic.treatment` is a public/delegated service model whose
`catalog_id` points to `clinic.treatment.catalog`; it is **not** a
patient-specific treatment episode.  Accordingly, Post-Care patient ownership
is validated through Encounter / Booking / Care Plan, while
`clinic.postcare.plan.treatment_id` is service-context traceability only.

It does not create parallel treatment/procedure masters.

## `clinic_branch`

Current company/user branch infrastructure is reused.
Company consistency is enforced in backend constraints.
No branch master or branch-access model is duplicated.

## `clinic_insurance_authorization`

Addon 25 remains upstream and frozen.
Post-Care does not duplicate insurance Policy, Authorization or Claim models.

## Future addons

Hard dependency count on future official addons: **0**.

In particular:
- `clinic_feedback`: not referenced;
- `clinic_incident_event`: not referenced;
- `clinic_portal`: not referenced;
- `clinic_marketing`: not referenced;
- `clinic_telemedicine_secure_messaging`: not referenced;
- `clinic_integration_api`: not referenced.

## Result

- unresolved required upstream technical contracts: 0
- duplicated upstream ownership: 0
- future-addon hard dependencies: 0
- fake SMS/WhatsApp/API delivery paths: 0
