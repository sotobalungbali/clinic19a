
# clinic_treatment_session 19.0.2.0.3 — Final Validation Report

**Release class:** Full Replacement / targeted runtime repair  
**Target:** Odoo 19 Community Edition  
**Runtime trigger fixed:** `operations.booking`  
**Original error:** `BookingRoom.is_available() got an unexpected keyword argument 'ignore_booking_id'`

## Root Cause

`clinic_booking` owns:

`booking.room.is_available(start_dt, end_dt, ignore_booking_id=None, consider_capacity=True)`

The previous `clinic_treatment_session` extension narrowed the method to a
Treatment Session-specific signature and therefore rejected a valid owner
keyword before room availability logic could execute.

## Repair

The replacement exposes an owner-compatible superset:

`is_available(start_dt=None, end_dt=None, ignore_booking_id=None, consider_capacity=True, ignore_session_ids=None, **kwargs)`

Behavior:

1. preserves `start_dt` / `end_dt`;
2. preserves `ignore_booking_id`;
3. preserves `consider_capacity`;
4. delegates owner room logic through `super().is_available(...)`;
5. preserves Treatment Session overlap validation;
6. preserves legacy `start_datetime` / `end_datetime` aliases;
7. preserves `ignore_session_ids` for Treatment Session rescheduling.

## Static / Source Validation

- Source-contract tests: **14/14 PASS**
- Test failures: **0**
- Test errors: **0**
- Enterprise Guardrail HARD GATE 0–15: **PASS**
- Python compileall: **PASS**
- Manifest missing files: **0**
- XML parse errors: **0**
- Legacy `tree/attrs/states` view syntax: **0**
- View-field mismatches: **0**
- Object-button/method mismatches: **0**
- Local import errors: **0**
- ACL rows: **8**
- Digit-prefixed backup files: **0**
- Room owner signature: **PASS**
- Room `super()` delegation: **PASS**
- Legacy room datetime keyword aliases: **PASS**

## Runtime Status

**PENDING TARGET ODOO RUNTIME.**

This environment cannot claim the user's Odoo database runtime result. Runtime
PASS is established only after:

1. complete folder replacement;
2. Odoo restart;
3. Apps List refresh;
4. `clinic_treatment_session` upgrade;
5. Demo Control Center → Refresh Compatibility;
6. reuse existing Demo Run;
7. Continue Generation;
8. `operations.booking` passes and generation moves to the next checkpoint.
