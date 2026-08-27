

# Clinic Membership — Runtime Repair 2026-08-18 / 01

## Runtime evidence
Activation failed while loading `security/clinic_membership_security.xml` with:

`ValueError: Invalid field 'category_id' in 'res.groups'`

The failing records were the Membership User and Membership Manager groups.

## Root cause
Odoo 19 changed the access-group hierarchy. `res.groups` no longer owns `category_id`; it owns
`privilege_id` pointing to `res.groups.privilege`. The privilege record owns the module category.

## Repair
- Added `clinic_membership.privilege_clinic_membership` (`res.groups.privilege`).
- Moved Membership category ownership to that privilege through `category_id`.
- Replaced `res.groups.category_id` with `res.groups.privilege_id`.
- Preserved User -> Manager implied-group hierarchy.
- Preserved all ACLs and multi-company record rules.
- Added static guardrail against reintroducing legacy Odoo <=18 group-category syntax.
- Added runtime regression test for privilege linkage.
- Bumped release to `19.0.3.0.1`.

## Preservation
No membership business model, workflow, entitlement, voucher, points, hold, integration-event,
clinical bridge, menu, ACL, record rule, or enterprise UI feature was removed.

## Status
SOURCE/STATIC: PASS after repair.
WINDOWS ODOO INSTALL: PENDING.

