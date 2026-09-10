
# Cross-Addon Contract Audit

Confirmed contracts preserved by this release:

- Booking owner: `booking.booking`.
- Room availability owner: `clinic_booking` / `booking.room`.
- Booking canonical Doctor: `clinic.doctor`.
- Historical Treatment Session Doctor: `hr.employee`.
- Treatment Session Patient public contract: `res.partner`.
- Canonical Patient card: `clinic.patient`.
- Encounter owner: `clinic.encounter`.
- Referral owner: `clinic.referral`.
- Billing owner: `clinic.billing.invoice`.
- Accounting invoice compatibility: `account.move`.
- Inventory movement owner: `stock.move`.
- Audit evidence owner: `clinic.audit.event`.

## 19.0.2.0.3 correction

`clinic_treatment_session` no longer narrows
`booking.room.is_available(...)`. It accepts the owner parameters
`ignore_booking_id` and `consider_capacity`, delegates them to `super()`, and
then adds Treatment Session overlap validation.
