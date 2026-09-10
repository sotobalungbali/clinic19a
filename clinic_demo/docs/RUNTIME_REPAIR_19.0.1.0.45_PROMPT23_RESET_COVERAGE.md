# Runtime Repair 19.0.1.0.45 — Prompt 23 Reset Coverage

## Runtime evidence

The Prompt 23 integrity/reset/regeneration gate rejected Queue/Triage Appointment
references because `clinic.appointment` was not registered in the reset policy
registry. These records are created by the official Booking owner workflow and
then bound to demo references, so a direct-create-only source audit missed them.

## Contract correction

- `clinic.appointment` is explicitly classified as `FRESH_DB_RESET_ONLY`.
- Clinical Appointment evidence is retained with Queue/Triage provenance.
- Unknown models remain blocked from reset.
- Regression coverage connects `_create_or_link_appointment()` and
  `appointment_key` bindings to the reset registry.
- Reset error messages now interpolate the actual model/state instead of
  displaying literal placeholders.

The correction is deterministic, does not use a production sequence, and does
not mutate business data during validation.

