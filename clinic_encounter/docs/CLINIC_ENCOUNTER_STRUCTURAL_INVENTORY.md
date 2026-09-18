# ClinicOne — clinic_encounter Structural Inventory

## Active import graph

1. `models.py`
2. `mixin_audit.py`
3. `encounter_stage.py`
4. `encounter.py`
5. `encounter_integration.py`
6. `soap_note.py`
7. `diagnosis.py`
8. `procedure_catalog.py`
9. `procedure_step.py`
10. `encounter_procedure.py`
11. `procedure_session.py`
12. `execution_log.py`
13. `result_document.py`
14. `consent.py`
15. `anesthesia.py`
16. `adverse_event.py`
17. `checklist.py`
18. `wizards.py`
19. `navigation_helpers.py`

Dormant and intentionally not imported: `models/xxx_clinic_encounter.py`.

## Model inventory

| Model | Role | Source | Fields | Methods |
|---|---|---|---:|---:|
| `clinic.adverse.event` | Persistent model | `adverse_event.py` | 52 | 17 |
| `clinic.ae.action` | Persistent model | `adverse_event.py, navigation_helpers.py` | 10 | 2 |
| `clinic.ae.category` | Persistent model | `adverse_event.py` | 6 | 0 |
| `clinic.ae.factor` | Persistent model | `adverse_event.py` | 7 | 0 |
| `clinic.ae.followup` | Persistent model | `adverse_event.py, navigation_helpers.py` | 6 | 1 |
| `clinic.ae.type` | Persistent model | `adverse_event.py` | 7 | 0 |
| `clinic.anesthesia.airway` | Persistent model | `anesthesia.py, navigation_helpers.py` | 11 | 1 |
| `clinic.anesthesia.case` | Persistent model | `anesthesia.py` | 75 | 24 |
| `clinic.anesthesia.event` | Persistent model | `anesthesia.py, navigation_helpers.py` | 6 | 1 |
| `clinic.anesthesia.fluid` | Persistent model | `anesthesia.py, navigation_helpers.py` | 9 | 1 |
| `clinic.anesthesia.medication` | Persistent model | `anesthesia.py, navigation_helpers.py` | 8 | 2 |
| `clinic.anesthesia.vital` | Persistent model | `anesthesia.py, navigation_helpers.py` | 15 | 1 |
| `clinic.audit.log` | Persistent model | `mixin_audit.py` | 22 | 4 |
| `clinic.audit.mixin` | Abstract mixin | `mixin_audit.py` | 1 | 20 |
| `clinic.checklist` | Persistent model | `checklist.py` | 40 | 15 |
| `clinic.checklist.item` | Persistent model | `checklist.py, navigation_helpers.py` | 28 | 2 |
| `clinic.checklist.template` | Persistent model | `checklist.py` | 18 | 3 |
| `clinic.checklist.template.item` | Persistent model | `checklist.py, navigation_helpers.py` | 16 | 1 |
| `clinic.checklist.template.item.option` | Persistent model | `checklist.py, navigation_helpers.py` | 8 | 1 |
| `clinic.consent.document` | Persistent model | `consent.py` | 44 | 22 |
| `clinic.consent.risk` | Persistent model | `consent.py, navigation_helpers.py` | 10 | 1 |
| `clinic.consent.risk.template` | Persistent model | `consent.py` | 7 | 0 |
| `clinic.consent.template` | Persistent model | `consent.py` | 8 | 1 |
| `clinic.diagnosis` | Persistent model | `diagnosis.py` | 33 | 23 |
| `clinic.diagnosis.category` | Persistent model | `diagnosis.py` | 5 | 0 |
| `clinic.diagnosis.plan.procedure.wizard` | Transient wizard | `wizards.py` | 4 | 2 |
| `clinic.encounter` | Persistent model | `encounter.py` | 42 | 34 |
| `clinic.encounter.bill.wizard` | Transient wizard | `wizards.py` | 8 | 2 |
| `clinic.encounter.procedure` | Persistent model | `encounter_procedure.py` | 36 | 24 |
| `clinic.encounter.stage` | Persistent model | `encounter_stage.py` | 16 | 10 |
| `clinic.execution.log` | Persistent model | `execution_log.py` | 23 | 10 |
| `clinic.patient.vital` | Extension | `encounter_integration.py` | 1 | 0 |
| `clinic.procedure.catalog` | Persistent model | `procedure_catalog.py` | 28 | 11 |
| `clinic.procedure.category` | Persistent model | `procedure_catalog.py` | 8 | 0 |
| `clinic.procedure.consumable` | Persistent model | `navigation_helpers.py, procedure_catalog.py` | 11 | 3 |
| `clinic.procedure.session` | Persistent model | `procedure_session.py` | 50 | 39 |
| `clinic.procedure.step` | Persistent model | `procedure_step.py` | 25 | 11 |
| `clinic.procedure.step.checklist` | Persistent model | `navigation_helpers.py, procedure_step.py` | 8 | 1 |
| `clinic.procedure.tag` | Persistent model | `procedure_catalog.py` | 4 | 0 |
| `clinic.result.document` | Persistent model | `result_document.py` | 35 | 19 |
| `clinic.result.group` | Persistent model | `result_document.py` | 6 | 0 |
| `clinic.result.value` | Persistent model | `navigation_helpers.py, result_document.py` | 24 | 5 |
| `clinic.soap.note` | Persistent model | `soap_note.py` | 28 | 18 |
| `clinic.soap.tag` | Persistent model | `soap_note.py` | 4 | 0 |
| `clinic.soap.template` | Persistent model | `soap_note.py` | 10 | 0 |

## Ownership notes

- `clinic.consent.template`: canonical identity remains upstream; encounter extends it in place without redefining canonical fields.
- `clinic.audit.log`: retained in this finished encounter baseline; later reconciliation belongs to addon `clinic_audit`.
- `clinic.patient.vital`: extended only with `encounter_id`; base model remains owned by `clinic_patient`.

## Preserved integration domains

Patient, doctor, room, booking, queue, triage/vitals, consent/legal, inventory/stock, product/UoM, accounting/invoice, portal, mail/activity.

