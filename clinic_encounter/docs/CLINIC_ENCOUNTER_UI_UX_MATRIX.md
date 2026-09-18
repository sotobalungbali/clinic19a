# ClinicOne — clinic_encounter UI/UX Matrix

All persistent custom models retain Search/List/Form coverage. Primary clinical models receive workflow-first professional forms; support models remain maintainable without pretending to be independent workflows.

| Model | Search | List | Form | Enterprise treatment |
|---|:---:|:---:|:---:|---|
| `clinic.adverse.event` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.ae.action` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.ae.category` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.ae.factor` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.ae.followup` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.ae.type` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.anesthesia.airway` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.anesthesia.case` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.anesthesia.event` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.anesthesia.fluid` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.anesthesia.medication` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.anesthesia.vital` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.audit.log` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.checklist` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.checklist.item` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.checklist.template` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.checklist.template.item` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.checklist.template.item.option` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.consent.document` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.consent.risk` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.consent.risk.template` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.consent.template` | ✓ | ✓ | ✓ | Canonical consent template support surface; ownership remains upstream |
| `clinic.diagnosis` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.diagnosis.category` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.encounter` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.encounter.procedure` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.encounter.stage` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.execution.log` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.procedure.catalog` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.procedure.category` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.procedure.consumable` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.procedure.session` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.procedure.step` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.procedure.step.checklist` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.procedure.tag` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.result.document` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.result.group` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.result.value` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.soap.note` | ✓ | ✓ | ✓ | Primary workflow form with lifecycle/actions/smart navigation |
| `clinic.soap.tag` | ✓ | ✓ | ✓ | Professional support/master-data form |
| `clinic.soap.template` | ✓ | ✓ | ✓ | Professional support/master-data form |

## Advanced interaction examples

- `clinic.encounter`: lifecycle header, 7 smart buttons, Procedure Plan One2many navigation, sessions/vitals/governance/financial tabs, chatter, calendar.
- `clinic.procedure.session`: lifecycle header, billing/inventory/result/checklist/adverse-event actions and smart buttons.
- `clinic.result.document` and `clinic.consent.document`: evidence lifecycle, print actions and ledger-oriented One2many views.
- `clinic.anesthesia.case`: pre-op → intra-op → recovery workflow with medication/vitals/fluids/airway/event lines.
- `clinic.adverse.event`: review/CAPA/regulatory workflow with action and follow-up ledgers.
- `clinic.checklist`: execution/scoring surface with item-level parent navigation.
- One2many child navigation buttons are implemented in `models/navigation_helpers.py` and kept human-readable.

