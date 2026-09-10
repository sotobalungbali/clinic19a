

# clinic_booking 19.0.1.0.2 — Weekly Schedule Timezone Repair

## Root cause
`booking.room`, `booking.resource`, and `clinic.doctor` weekly schedules store business-local
wall-clock hours, but `_fits_weekly_schedule()` compared those hours directly against Odoo
`fields.Datetime` values stored in UTC. In non-UTC deployments, a valid 09:00 local booking
could therefore be evaluated as 01:00 UTC and rejected.

## Repair
The three owner availability implementations now convert UTC datetimes with
`fields.Datetime.context_timestamp()` before comparing weekday/hour windows. Blackout and
overlap comparisons remain UTC as they should. Existing API/workflow/security semantics are
unchanged. Callers may provide `with_context(tz=...)`; otherwise normal Odoo user timezone
resolution applies.

This is an additive owner repair required for source-valid Prompt-14 scheduling.
