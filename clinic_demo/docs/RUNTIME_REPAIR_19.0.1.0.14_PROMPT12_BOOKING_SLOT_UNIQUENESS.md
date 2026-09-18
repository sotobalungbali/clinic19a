




# Runtime Repair 19.0.1.0.14 — Prompt 12 Booking Slot Uniqueness

## Runtime evidence

`resources.rooms_devices` failed with PostgreSQL/Odoo constraint
`booking_slot_name_company_unique` for:

`Demo General Clinical Consultation — Dr. Alya Permata`

## Root cause

`booking.slot` correctly enforces `unique(name, company_id)` and
`unique(code, company_id)`. Prompt 12 Full Enterprise creates 12 reusable slot templates.
The treatment list cycles every six slots; the doctor selection can cycle to the same
provider. Therefore slot 001 and slot 007 can represent the same treatment/provider pair
at a different weekday/hour but previously received the same human-facing name.

## Repair

The demo orchestrator now sets:

`Demo <Treatment> — <Doctor> — Slot ###`

while keeping the stable technical code/reference `DEMO-SLOT-###`. This preserves the
owner constraints and makes profile expansion deterministic and idempotent.

No owner-addon patch, SQL cleanup, `sudo()`, or constraint bypass is used.

Authoritative source SHA-256: `75fd525c05123c40c0e44a800c1d71cdd6f020cddd420c9199534cecf6692453`.
























