# clinic_inventory — Root Cause Audit After Retry Limit

## Why the previous static gates were insufficient
The active `stock.lot` extension declared both:

- `clinic_is_expired = fields.Boolean(...)`
- `def clinic_is_expired(self): ...`

in the same Python class.

Python retains only the later class attribute under a duplicated name. The
method therefore shadowed the field object before Odoo could register the field.
The XML view was correct to report that `stock.lot.clinic_is_expired` did not
exist at runtime.

## Surgical correction
The field remains `clinic_is_expired` because it is the business/UI data
contract. The conflicting helper method had no active callers anywhere in the
user-provided ClinicOne source and is renamed to `clinic_get_is_expired()`.

This is an unavoidable technical namespace repair, not a redesign.

## Additional audit performed
- Searched all active `clinic_inventory` Python classes for field/method
  namespace collisions: no collisions remain.
- Cross-checked `clinic_*` fields referenced by active Clinic Inventory XML
  views against the corresponding local model extension.
- Cross-checked custom `clinic_*` roots used in `@api.depends` and
  `@api.constrains`.
- Corrected the Lot form modifier that compared
  `clinic_quality_state` with the nonexistent selection value `quarantine`;
  the existing hold state is `on_hold`.
- Preserved models, fields, workflows, dependencies, ACLs and enterprise UI.

## Guardrail change
Added machine-checkable:
- `FIELD_METHOD_NAMESPACE_COLLISION_GATE`
- `XML_CUSTOM_FIELD_MODEL_CONTRACT_GATE`
- `CUSTOM_DECORATOR_FIELD_CONTRACT_GATE`

This work is classified as a root-cause audit after the retry limit, not an
unbounded fourth blind retry.




