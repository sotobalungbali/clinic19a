# ClinicOne — `clinic_treatment_catalog` Odoo 19 Enterprise Hardening Review

## Baseline decision
The addon is treated as functionally FINISHED. No domain redesign or simplification was performed. Backup files beginning with digit `0` are excluded.

## Odoo 19 compatibility repairs
1. Migrated 12 legacy `_sql_constraints` declarations / 15 SQL constraints to `models.Constraint`.
2. Migrated legacy `read_group()` backend aggregations to `_read_group()`.
3. Migrated legacy `name_search(..., args=None, ...)` signatures to Odoo 19 `domain=None` and added native `_compute_display_name()` while keeping `name_get()` compatibility wrappers.
4. Migrated Odoo pricelist fallback to `_get_product_price(...)`; fixed callers to consume its scalar result.
5. Removed obsolete base-product create keys `uom_po_id` and `property_cost_method`; `invoice_policy` is only sent when the optional Sale extension exposes the field.
6. Removed obsolete `discount_policy` from `product.pricelist` create values.
7. Migrated Python window action `tree,form` terminology to `list,form`.

## Existing-code contract repairs
- Added sequence records already referenced by treatment/category/tag/attribute/bundle/pricelist/rule creation logic.
- Added `clinic.consent.request` sequence code already used by `next_by_code()`.
- Restored active consent `patient_id` field because existing create/onchange/enforcement code already reads/searches it.
- Added explicit `clinic_patient` manifest dependency for that existing active contract.
- Restored computed consent `display_name` used by `_rec_name`.
- Optional consent scope parameters now fail clearly if the corresponding optional integration field is not available instead of building an invalid domain.
- Invalid tutorial demo data was replaced by a safe empty demo file.

## Enterprise completeness layer
- 16 persistent custom models: Search/List/Form coverage 16/16.
- ACL coverage 16/16 using `base.group_user`; no invented clinical role architecture.
- Multi-company ORM record rules for company-scoped models and consent request items.
- Professional treatment/bundle/pricelist/consent forms.
- Smart buttons expose existing navigation actions.
- Consent request workflow uses existing state as a statusbar plus existing Request/Sign/Revoke/Expire/Cancel actions.
- Public treatment form exposes body action `action_open_catalog_record`.
- Treatment Attribute Values One2many exposes existing `action_open_treatments` button.

## Preserved intentional architecture
- Dormant pricing engines and booking/billing/inventory/report bridges remain dormant.
- No sibling ClinicOne addon was modified.
- Consent model ownership overlap with the later `clinic_consent_legal` addon is documented but not redesigned in this finished-addon hardening pass.

## Static status
`CLINIC_TREATMENT_CATALOG_STATIC_MOVE_FORWARD_READY: YES` only after the bundled validator passes.
Final target-PC runtime status remains PENDING until install/upgrade/repeat-upgrade and focused smoke pass.

