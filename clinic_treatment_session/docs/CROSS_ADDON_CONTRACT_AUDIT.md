# CROSS-ADDON CONTRACT AUDIT

Confirmed from the authoritative 41-addon source snapshot:

- Booking owner is `booking.booking`.
- Booking canonical doctor is `doctor_id → clinic.doctor`.
- Historical Treatment Session doctor is `clinic_doctor_id → hr.employee`.
- Booking carries `referral_id`, `package_allocation_id`,
  `package_allocation_line_id`, and `package_usage_id`.
- Patient card owner is `clinic.patient` linked to `res.partner`.
- Encounter owner is `clinic.encounter`.
- Billing owner is `clinic.billing.invoice`.
- Audit evidence owner is `clinic.audit.event`.
- `clinic_membership` is already a downstream consumer of
  `clinic.treatment.session`.

Critical draft defect corrected:
the legacy Booking payload copied `clinic.doctor.id` directly into an
`hr.employee` field. The full-corrected build resolves the employee separately
and stores the canonical Clinic Doctor in `doctor_id`.
