# clinic_booking 19.0.1.0.4 — clinic.appointment Field-Bridge Repair

## Runtime evidence

Prompt 14 `operations.booking` failed while doctor availability was evaluated:

`Invalid field clinic.appointment.start_datetime in condition (...)`

## Root cause

The runtime-loaded `clinic_booking` soft appointment bridge assumed optional
appointment fields `start_datetime`, `end_datetime`, and `active`.

The canonical owner model in `clinic_doctor` uses:

- `start`
- `end`
- `state`

The same stale assumption also existed in the optional booking -> appointment
create/link helper.

## Repair

- Appointment overlap domains are field-aware and prefer canonical `start/end`.
- Terminal appointment states `canceled/no_show` are excluded when `state` exists.
- The create/link bridge writes canonical `partner_id`, `start`, and `end` when
  those fields exist and only writes optional fields actually exposed by the target model.
- The previous Odoo 19 booking-channel multi-create and timezone schedule repairs remain intact.
- No ACL, booking lifecycle, constraint, or queue/clinical workflow was weakened.
