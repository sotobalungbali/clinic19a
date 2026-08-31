# Runtime Repair 19.0.1.0.2 — `res.partner.is_doctor`

## Runtime evidence

`workforce.staff` failed while creating the first synthetic `res.partner` with:

`AttributeError: 'res.partner' object has no attribute 'is_doctor'`

The traceback passed through `clinic_doctor`'s active `res.partner` extension.

## Root cause

`clinic_doctor/models/res_partner_inherit.py` is imported at runtime and contains both
`write()` behavior and an `@api.constrains("is_company", "is_doctor")` constraint, but
the actual `is_doctor` field declaration had been commented out with a stale comment
claiming ownership had moved to `clinic_audit`.  The authoritative source confirms
`clinic_audit` does not define that field.  A dormant/unimported Staff bridge must not
be used as the owner.

## Targeted fix

Restore the Boolean field in the active `clinic_doctor` partner extension.  No workflow
semantics are changed; the existing write side-effect and constraint now operate on the
field they already contractually require.

## Upgrade order

1. Upgrade `clinic_doctor` to 19.0.1.0.2.
2. Upgrade `clinic_demo` to the matching Prompt-09 runtime-repair build.
3. Open the failed Demo Run and click **Refresh Compatibility**.
4. Run **Generate Full Enterprise Dataset** again (or Continue Generation).
