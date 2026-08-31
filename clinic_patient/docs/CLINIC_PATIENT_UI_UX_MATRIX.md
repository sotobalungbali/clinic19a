
# ClinicOne — clinic_patient UI/UX Matrix

Every custom persistent model must have a Search, List, and Form view. UI complements ORM security; it never replaces ACLs/record rules.

| Model | Role | Search | List | Form | Enterprise interaction |
|---|---|---:|---:|---:|---|
| `clinic.patient.stage` | Configuration | Yes | Yes | Yes | Sequence/functional flags |
| `clinic.patient.tag` | Configuration | Yes | Yes | Yes | Tag color |
| `clinic.patient` | Primary | Yes | Yes | Yes | Header actions, M2O statusbar, smart/body buttons, O2M buttons |
| `clinic.allergen.category` | Configuration | Yes | Yes | Yes | Catalog |
| `clinic.allergen` | Configuration | Yes | Yes | Yes | Catalog/product linkage |
| `clinic.allergy.reaction.type` | Configuration | Yes | Yes | Yes | Catalog |
| `clinic.patient.allergy` | Clinical | Yes | Yes | Yes | Selection statusbar, resolve action, attachment smart button |
| `clinic.patient.allergy.reaction` | Clinical child | Yes | Yes | Yes | Attachment smart button |
| `clinic.condition.category` | Configuration | Yes | Yes | Yes | Catalog |
| `clinic.condition` | Configuration | Yes | Yes | Yes | Condition code One2many |
| `clinic.condition.code` | Configuration child | Yes | Yes | Yes | Code dictionary |
| `clinic.patient.condition` | Clinical | Yes | Yes | Yes | Selection statusbar, resolve action, attachment smart button |
| `clinic.patient.condition.episode` | Clinical child | Yes | Yes | Yes | Attachment smart button |
| `clinic.patient.identifier.type` | Configuration | Yes | Yes | Yes | Validation/sequence configuration |
| `clinic.patient.identifier` | Clinical identity | Yes | Yes | Yes | Statusbar, Set Primary action/list button |
| `clinic.patient.vital` | Clinical | Yes | Yes | Yes | Open Patient + attachment buttons, professional notebook |

## Canonical Odoo extensions
- `res.partner`: inherited `base.view_partner_form`; Patient Card / Invoices / Attachments smart buttons and a ClinicOne Patient notebook page.
- `res.users`: inherited `base.view_users_form`; patient linkage smart buttons and a ClinicOne Patient notebook page.

## Button policy
- Buttons call existing model methods wherever possible.
- The only additive presentation helper is `clinic.patient.action_open_contact()`; it opens the already-existing `partner_id` relationship.
- No button creates a bypass around ACL or company record rules.
