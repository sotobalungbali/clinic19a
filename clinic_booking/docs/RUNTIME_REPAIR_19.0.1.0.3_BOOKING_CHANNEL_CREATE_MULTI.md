# clinic_booking 19.0.1.0.3 — Odoo 19 Booking Channel Multi-Create Repair

## Runtime evidence

ClinicOne Demo MASTER PROMPT 14 reached `operations.booking` and failed with:

`'list' object has no attribute 'get'`

## Root cause

`booking.channel.create()` was still declared with `@api.model` and
`def create(self, vals)`, then immediately called `vals.get(...)`.

Under the Odoo 19 create pipeline the override can receive a `vals_list`.
The legacy override therefore attempted `.get()` on a Python list.

## Targeted repair

The owner method now uses:

- `@api.model_create_multi`
- `def create(self, vals_list)`
- per-row `dict(original)` preparation
- the existing default-policy lookup for each row
- one `super().create(prepared)` call

No ACL, constraint, workflow, channel semantics, or external side effect was changed.

## Regression

`tests/test_booking_channel_create_multi.py` creates two channels in one ORM call.
The Enterprise Guardrail also rejects reintroduction of the legacy
`def create(self, vals)` contract on `booking.channel`.

## Change control

Owner version: `19.0.1.0.3`

This is an Odoo 19 compatibility repair under ClinicOne Demo V2 owner-addon
change control. It does not redesign Booking.
