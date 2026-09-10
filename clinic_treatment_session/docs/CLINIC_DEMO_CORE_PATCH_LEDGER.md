
# CLINIC_DEMO_CORE_PATCH_LEDGER

## 2026-09-01 — clinic_treatment_session 19.0.2.0.3

| Field | Result |
|---|---|
| Runtime blocker | `operations.booking` |
| Error | `BookingRoom.is_available() got an unexpected keyword argument 'ignore_booking_id'` |
| Owner/extension addon changed | `clinic_treatment_session` |
| `clinic_demo` source changed | No |
| Root cause | Treatment Session override narrowed the `clinic_booking` room-availability public API |
| Repair | Superset signature + `super()` owner delegation + preserved Treatment Session overlap |
| Workflow redesign | No |
| Security bypass | No |
| Direct state bypass | No |
| Version bump | `19.0.2.0.2` → `19.0.2.0.3` |
| Static regression | Required/PASS before release |
| Target Odoo runtime | PENDING |
