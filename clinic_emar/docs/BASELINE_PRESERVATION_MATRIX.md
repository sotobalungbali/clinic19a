# clinic_emar — Baseline Preservation Matrix

| Baseline capability/artifact | Decision | Final treatment |
|---|---|---|
| `models/core/emar_prescription.py` | KEEP_AND_HARDEN | Canonical prescription owner; patient/doctor clinical source-of-truth, safety/prescriber gates, signing, order generation. |
| `models/core/emar_order.py` | KEEP_AND_HARDEN | Canonical execution order owner; state/inventory/billing/schedule lifecycle hardened. |
| `models/core/emar_medication_line.py` | KEEP_AND_HARDEN | Shared medication intent line; Odoo 19-safe UoM handling and richer SIG/profile/pricing data. |
| `models/core/emar_schedule.py` | KEEP_AND_HARDEN | Planned dose owner; due/missed lifecycle moved out of compute into cron/actions; q4h/q6h/q8h/q12h/weekly/PRN semantics. |
| `models/core/emar_administration.py` | KEEP_AND_HARDEN | Actual dose event; verification gate, refusal/skip/missed, inventory/billing linkage. |
| `models/core/emar_alert.py` | KEEP_AND_HARDEN | Deduplicated medication safety/operational alert lifecycle. |
| Root `models/emar_*.py` second generation | MERGE_WITHOUT_LOSS | Not imported wholesale because duplicate `_name` owners would collide; clinically valuable fields/actions/integration intent merged into core/integrations. |
| Medication master/profile intent | MOVE_TO_NAMED_OWNER | New `clinic.emar.medication.profile` owns high-alert, controlled, barcode, lot, substitution, route/frequency and dose-limit policy per product/company. |
| Patient allergy/dose safety intent | MERGE_WITHOUT_LOSS | Implemented in `integrations/patient_safety.py`; uses `clinic.patient.allergy` and medication profile limits. |
| Doctor/prescriber governance intent | MERGE_WITHOUT_LOSS | Implemented in `integrations/prescriber_governance.py`; retains license/scope/controlled authorization/cosign intent. |
| Patient/doctor integration files | MERGE_WITHOUT_LOSS | Backlinks/actions placed in `source_model_bridges.py`; no brittle hard view inheritance. |
| Inventory integration | MERGE_WITHOUT_LOSS | Administration consumption uses governed `clinic.treatment.product.usage`; stock/account bridges retain traceability. |
| Clinical dose vs physical inventory quantity | KEEP_AND_HARDEN | Clinical dose (`administered_qty` + `dose_uom_id`) is separated from stock usage (`inventory_qty` + `inventory_uom_id`) so a dose such as 500 mg can consume one tablet rather than 500 stock units. |
| Treatment integration prototype | REJECT_WITH_REASON | Clinical `treatment_id` context is preserved, but automatically turning generic treatment service/consumable lines into medications would mix service-catalog ownership with medication prescribing. A future medication-protocol owner may create explicit mappings. |
| Billing integration | KEEP_AND_HARDEN | Invoice links retained; canonical ClinicOne patient/doctor resolver prevents cross-comodel ID contamination. |
| Downstream `clinic_imaging` order schema | KEEP_CONTRACT | Order keeps `patient_id=res.partner`, `doctor_id=hr.employee`, while `clinic_patient_id`/`clinic_doctor_id` hold canonical clinical records; `order_line_ids` alias retained. |
| Downstream `clinic_care_plan` prescription schema | KEEP_CONTRACT | Prescription remains `patient_id=clinic.patient`, `doctor_id=clinic.doctor`. |
| `clinic_audit` hard dependency | DEFER_WITH_CONTRACT | Removed as forward dependency; eMAR internal audit mixin works independently and soft-links to `clinic.audit.log` when available later. |
| `clinic_branch` hard dependency | REJECT_WITH_REASON | No owned runtime reference and it is a downstream addon; hard dependency would invert ClinicOne install DAG. |
| Stored signature PIN / secret-style authorization | REJECT_WITH_REASON | Credentials/secrets are not persisted as a convenience feature; governed sign/cosign uses authenticated Odoo users. |
| Public scaffold controller | REJECT_WITH_REASON | No valid eMAR business API contract/security; removed instead of exposing a placeholder route. |
| Scaffold `models/models.py`, commented `views/views.xml`, `templates.xml`, demo | REJECT_WITH_REASON | Non-functional scaffold/dead duplication replaced by complete enterprise artifacts. |
| Legacy `_sql_constraints` | REWRITE | Replaced by Odoo 19 `models.Constraint`. |

No baseline file whose basename begins with digit `0` participates in this matrix or final package.

## Release 19.0.3.0.0 preservation decision

| Baseline capability/artifact | Decision | Final treatment |
|---|---|---|
| Six `res.company.emar_*` settings | KEEP_AND_HARDEN | Public field names and behavior preserved; physical company-column storage replaced with schema-safe company-scoped parameters. |
| `res.config.settings` eMAR UI | KEEP_AND_HARDEN | Same user-facing settings, explicit company-scoped read/write. |
| Reschedule wizard | KEEP_AND_HARDEN | Workflow preserved; transient vacuum tolerates only the pre-upgrade missing-table window. |
| Schedule cron | KEEP_AND_HARDEN | Due/missed logic preserved; cron skips only when owned tables do not yet exist. |
| Legacy company-column values | PRESERVE_ON_UPGRADE | Odoo 19 pre-migration copies existing values to the schema-safe parameter store. |

