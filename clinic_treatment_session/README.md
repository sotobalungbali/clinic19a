
# ClinicOne Treatment Session Management

Source-actual ClinicOne addon **#41 / 41**, Odoo 19 Community Edition.

Lifecycle: `Draft → Confirmed → In Progress → Done`, with controlled
`No-show` and `Cancelled` branches.

## 19.0.2.0.3 runtime repair

19.0.2.0.2 narrowed `booking.room.is_available()` to a Treatment Session-only
argument (`ignore_session_ids`). `clinic_booking` legitimately calls its owner
API using `ignore_booking_id=` and `consider_capacity=`, producing the
`operations.booking` checkpoint failure.

19.0.2.0.3 preserves the owner arguments, delegates owner availability through
`super().is_available(...)`, then applies Treatment Session overlap checks.

This package is a full addon replacement, not a partial patch.
