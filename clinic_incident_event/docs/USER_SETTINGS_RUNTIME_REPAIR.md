# User Settings Runtime Repair — 19.0.1.0.1

## Runtime evidence

Opening the Odoo 19 User Access Rights / User Settings UI failed in OWL while
parsing a generated privilege template containing:

`<group string="ClinicOne Incident & Event">`

The source XML itself used `&amp;` correctly. After module data is loaded,
however, `ir.module.category.name` and `res.groups.privilege.name` contain the
literal display value `ClinicOne Incident & Event`. Odoo's group hierarchy
feeds those display values to the web access-rights widget.

## Repair

Only the display labels owned by `clinic_incident_event` are changed:

- `ir.module.category` XML ID `module_category_incident`
- `res.groups.privilege` XML ID `privilege_incident`

New label: `ClinicOne Incident and Event`

No security group external ID, implied-group relation, ACL, record rule,
business model, action, menu, or workflow is changed.

## Regression hard gate

The package guardrail rejects XML-sensitive ampersands in
`ir.module.category` and `res.groups.privilege` display labels used by the
dynamic User Access Rights hierarchy.
