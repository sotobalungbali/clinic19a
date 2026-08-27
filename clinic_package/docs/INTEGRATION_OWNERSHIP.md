
# Integration Ownership — `clinic_package`

## Hard dependencies available before/with this addon

`clinic_package` integrates directly with patient, treatment catalog, doctor, room/device,
queue, inventory, booking, triage, consent, encounter, eMAR, imaging, and care plan because these
models are already upstream in the current ClinicOne dependency chain.

## Later addon owners

The package core deliberately does not inherit models from later owners such as membership,
billing, AR/AP, wallet, finance, accounting, insurance, portal, marketing, reports, dashboard,
eCommerce, or integration API.

Downstream addons can consume `clinic.package.integration.event` and/or add their own explicit
Many2one fields to package records from their owner addon. This keeps dependency direction one-way.

## Event examples

- `package.activated`, `package.paused`
- `allocation.activated`, `allocation.paused`, `allocation.resumed`, `allocation.transferred`
- `usage.confirmed`, `usage.cancelled`
- `voucher.issued`, `voucher.redeemed`

Payload is JSON and the source is expressed as `source_model` + `source_res_id`, avoiding an
uninstall-order trap against models that do not yet exist.
