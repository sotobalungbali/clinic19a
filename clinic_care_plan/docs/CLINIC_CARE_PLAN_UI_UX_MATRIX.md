# ClinicOne — clinic_care_plan UI/UX Matrix

| Model | Search | List | Form | Lifecycle / Enterprise controls |
|---|---:|---:|---:|---|
| `clinic.care.plan` | Yes | Yes | Yes | Statusbar; Activate/Hold/Resume/Complete/Cancel/Archive; Print Summary; Smart Lines/Sessions/Prescriptions/Invoices; protocol-generation body button; advanced One2many execution actions |
| `clinic.care.plan.line` | Yes | Yes | Yes | Statusbar; Schedule/Start/Complete/Skip/Cancel; smart parent/dependents/invoices; body Session/eMAR/Inventory actions; calendar |
| `clinic.care.protocol` | Yes | Yes | Yes | Version statusbar; Submit Review/Publish/Deprecate/New Version; Smart Care Plans/Steps; Create Care Plan body action; governed protocol notebook |
| `clinic.care.protocol.step` | Yes | Yes | Yes | Smart Protocol/Dependents; clinical, product, dependency and evidence pages |

## Optional upstream form integration
Installed defensively in `post_init_hook` when compatible primary forms exist:
- Patient: Care Plans smart button + Care Plans page + New Care Plan action.
- Doctor: Care Plans smart button.
- Encounter: Care Plans smart button.

No sibling presentation XML-ID is a manifest-load blocker.
