




# MASTER PROMPT 12 — Rooms, Devices, Resources & Scheduling

## Status
Source/static/package PASS. Runtime confirmation remains required on the target Odoo database.

## Bounded generator
- `resources.rooms_devices`
- phase: `12_resources`
- depends on: `master.commercial`
- registered order after Prompt 11: generator #9 of the progressive 35-generator enterprise registry

## Source-driven coverage
- `clinic.room.type` and `clinic.room`
- `clinic.device.category` and `clinic.device`
- active room-device placement through `clinic.room.device.assignment.action_activate()`
- Monday–Saturday `clinic.room.availability` recurring templates
- delegated `booking.room` wrappers + Monday–Saturday schedules + controlled blackout
- `booking.resource` device mirrors + Monday–Saturday schedules + controlled maintenance blackout
- `booking.doctor.schedule`
- reusable 90-day `booking.slot` templates
- treatment-to-room/resource/doctor compatibility defaults
- doctor-to-branch-compatible room/resource defaults
- branch-location stock mapping where the Prompt-08 location exposes a source-valid internal stock location

## Dataset budgets
| Profile | Rooms | Devices / Booking Resources | Slot Templates |
|---|---:|---:|---:|
| Compact | 4 | 4 | 4 |
| Standard | 6 | 6 | 8 |
| Full Enterprise | 9 | 8 | 12 |

The same stable demo keys are reused across profiles wherever the record is in the profile budget.

## Branch and capacity integrity
Room/resource `allowed_doctor_ids` are restricted to providers assigned to the same generated branch. Device target rooms are checked against each profile budget; cross-branch fallback is prohibited.

The owner `clinic.room.device.assignment` model uses `clinic.room.capacity` as an active-device placement guard. B001 Imaging therefore uses physical room capacity 2 for its two active imaging devices, while the delegated `booking.room.capacity` remains 1 so patient concurrency is still single-session.

## Availability and controlled exceptions
Baseline operating windows are Monday–Friday 08:00–18:00 and Saturday 08:00–14:00. Future exceptions are represented through official blackout models:
- room deep-cleaning blackout at T+14;
- resource preventive-maintenance blackout at T+21.

No illegal double booking is created merely to demonstrate an exception.

## Demo Safe Mode
Room-device assignment uses the owner business method with `create_movement_logs=False`. Prompt 12 does not pre-populate a room supervisor before activation, avoiding unowned `mail.activity` side effects during demo master generation. No external API/email/payment side effect is invoked.

## Boundary
Prompt 12 creates no `booking.booking`, queue/triage transaction, `clinic.room.session`, encounter, treatment session, invoice/payment, journal entry, or stock move. It prepares only source-valid capacity/scheduling prerequisites consumed by later prompts.

## Reset
Reset is child-first because the reset service orders references by `reset_sequence DESC`:
- assignment/schedule/availability/blackout children have higher reset sequences;
- those reversible children use DELETE_SAFE where source permits;
- room/device/booking-resource/slot presentation anchors are DEACTIVATE.

## Runtime target
Existing completed Prompt-11 Demo Run → upgrade `clinic_demo` → Refresh Compatibility → Compatible → Generate Full as System Administrator → `resources.rooms_devices = DONE`.

If the database is still only Prompt-10 complete, this cumulative full-replacement build retains the bounded Prompt-11 adoption route; Prompt-11 generators must complete before Prompt 12 can execute.









