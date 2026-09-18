# Runtime Repair 19.0.3.0.6 — Membership Plan ACL Reload

## Runtime evidence

ClinicOne demo generation reached `master.commercial` and Odoo rejected creation of
`membership.plan` with: `No group currently allows this operation`.

## Source diagnosis

The owner source already contains the correct Odoo ACL contract:

- `clinic_membership.group_clinic_membership_manager`
- `model_membership_plan` with create/write/unlink permission
- `model_membership_plan_benefit` with create/write/unlink permission
- `security/ir.model.access.csv` is present in the manifest data list

Therefore the source contract and the installed database ACL registry had drifted.
The safe repair is to upgrade the owner addon so Odoo reloads its declared ACL data.

## Change

- version bumped from `19.0.3.0.5` to `19.0.3.0.6`;
- no business workflow/state semantics changed;
- no ACL was widened beyond the already-declared Membership Manager contract;
- guardrail now verifies that the ACL CSV is manifest-loaded and that Membership
  Manager has create permission for plan and plan-benefit;
- post-install regression verifies a Membership Manager can create a plan.

## Required runtime order

`clinic_membership` upgrade -> `clinic_demo` upgrade -> Refresh Compatibility ->
Generate Full on the same failed Demo Run.

