# ClinicOne — clinic_inventory Runtime Fix Attempt 2

## Runtime failure
Target Odoo 19 stopped while validating:
`views/treatment_product_usage_views.xml`

Error:
`Invalid view clinic.treatment.product.usage.search definition`

## Root cause
The generated search views still used a legacy search-group presentation pattern:

`<group expand="0" string="Group By">`

The group-by filters themselves are preserved. The unsupported `expand` search-group
attribute was removed.

## Surgical repair
Pattern changed from:

`<group expand="0" string="Group By">`

to:

`<group>`

The same active pattern was proactively corrected in:
- views/treatment_product_usage_views.xml
- views/inventory_adjustment_views.xml
- views/patient_product_history_views.xml
- views/doctor_allowed_product_views.xml
- views/integration_event_log_views.xml

No search field, filter, group-by function, model, business field, workflow, ACL,
record rule, dependency, or menu was removed.

## Guardrail regression protection
Added:
`ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE`

The guardrail now fails if legacy `expand` is reintroduced on a search-view
`<group>` element.

## Attempt accounting
Overall Clinic Inventory runtime repair: 2
This blocker/root-cause class (search-view architecture): attempt 1 / 3

## Static result after repair
- PYTHON_COMPILE: PASS
- XML_PARSE: PASS
- ODOO19_SEARCH_VIEW_ARCHITECTURE_GATE: PASS
- OPTIONAL_FIELD_DECORATOR_DEPENDENCY_GATE: PASS
- OWNER_HARD_GATES_PASS: 15 / 15

`CLINIC_INVENTORY_STATIC_MOVE_FORWARD_READY: YES`
`CLINIC_INVENTORY_MOVE_FORWARD_READY: PENDING`

A target-PC Odoo 19 install/upgrade retest is still required.

