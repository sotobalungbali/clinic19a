# ClinicOne `clinic_treatment_catalog` — UI/UX Matrix

| Model | Search | List | Form | Enterprise interaction |
|---|---:|---:|---:|---|
| `clinic.treatment.catalog` | YES | YES | YES | Smart button: Pricing Rules; professional notebook; image/product/pricing/validity. |
| `clinic.treatment.category` | YES | YES | YES | Smart button: Treatments; hierarchical subcategory One2many. |
| `clinic.treatment.tag` | YES | YES | YES | Smart button: Treatments. |
| `clinic.treatment.attribute` | YES | YES | YES | Smart button: Treatments; One2many Values includes object button to Treatments. |
| `clinic.treatment.attribute.value` | YES | YES | YES | Smart button: Treatments. |
| `clinic.treatment.attribute.line` | YES | YES | YES | Typed-value professional form. |
| `clinic.treatment.bundle` | YES | YES | YES | Smart button: Treatments; editable Bundle Lines. |
| `clinic.treatment.bundle.line` | YES | YES | YES | Detailed quota/pricing form. |
| `clinic.treatment.pricelist` | YES | YES | YES | Smart button: Rules; editable pricing rules. |
| `clinic.treatment.pricelist.item` | YES | YES | YES | Rule applicability + calculation notebook. |
| `clinic.treatment` | YES | YES | YES | Body button: Open Canonical Catalog; Smart button: Pricing Rules. |
| `clinic.consent.template` | YES | YES | YES | Default acknowledgements and version management. |
| `clinic.consent.template.item` | YES | YES | YES | Standalone search/list/form. |
| `clinic.consent.template.version` | YES | YES | YES | Statusbar: Draft / Published / Archived. |
| `clinic.consent.request` | YES | YES | YES | Workflow statusbar + Request/Sign/Revoke/Expire/Cancel action buttons. |
| `clinic.consent.request.item` | YES | YES | YES | Standalone search/list/form and inline acknowledgements. |

## UI security rule

Visibility, `invisible`, statusbar, and buttons are usability controls only. CRUD authorization is enforced by ACLs and record rules at ORM level.

