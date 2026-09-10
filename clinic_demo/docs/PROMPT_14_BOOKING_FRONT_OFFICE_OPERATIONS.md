




# MASTER PROMPT 14 — Booking & Front Office Operations

**Build:** `clinic_demo 19.0.1.0.19`

## Bounded Generators

1. `operations.referral` — depends on `history.patient_longitudinal`.
2. `operations.booking` — depends on `operations.referral`.

The registered scope grows from 10 to 12 generators. Queue/Triage/Encounter and
Treatment Session remain later prompts.

## Referral Coverage

Prompt 14 creates deterministic synthetic referral program/source masters and
referrals covering Draft, Confirmed, Converted, Cancelled and Expired states.
`DEMO-REF-001` is the golden acquisition anchor: it is confirmed by the Referral
generator and converted by the Booking generator only after
`DEMO-BOOK-TODAY-REF-001` exists.

Historical referral transitions use the additive owner APIs in
`clinic_referral 19.0.2.0.6`; no technical audit timestamp is falsified.

## Booking Coverage

Profile budgets:

| Profile | Historical | Current | Future | Total Booking | Referral |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compact | 12 | 6 | 6 | 24 | 5 |
| Standard | 18 | 8 | 8 | 34 | 7 |
| Full Enterprise | 24 | 10 | 12 | 46 | 10 |

Booking lifecycle uses owner methods only: `action_confirm`, `action_done`,
`action_cancel`, `action_mark_no_show`, and `action_apply_reschedule`.
Current-day coverage remains front-office safe (Draft / Confirmed / Cancelled /
No-show / Rescheduled). Arrival/Queue/Triage and clinical completion are not
fabricated ahead of their owner prompts. Historical Done records use source
business dates in `start_datetime`, `end_datetime`, `checkin_time`, and
`checkout_time`.

## Scheduling / Timezone

`clinic_booking 19.0.1.0.3` preserves the timezone fix and additionally makes `booking.channel.create()` Odoo-19 multi-create safe; 19.0.1.0.2 fixed weekly room/resource/doctor schedule evaluation so
Odoo UTC datetimes are converted to the business/user context timezone before
comparison with local wall-clock `hour_from/hour_to` values. Prompt 14 executes
booking lifecycle methods with `tz=Demo Run.timezone`.

Current-day lanes use actual per-doctor counters and remain inside the Prompt-12
Monday-Saturday operating windows, including Saturday 14:00 closing. A Sunday
Demo Anchor Date uses the immediately preceding Saturday as the live
front-office snapshot.

## Safe Mode Boundary

Generated channels set:
- `website_published=False`;
- `auto_create_appointment=False`;
- `lock_slot_on_confirm=False`;
- prepaid deposit disabled.

No Queue, Triage, Encounter, Treatment Session, imaging/eMAR, invoice/payment or
external outbound transaction is created by Prompt 14.



## Runtime Repair — `operations.booking` list/get failure

Runtime evidence after Prompt-14 deployment showed:

`'list' object has no attribute 'get'`

The root cause was the owner `booking.channel.create()` override using legacy
`@api.model` / `vals.get(...)`. `clinic_booking 19.0.1.0.3` converts it to
`@api.model_create_multi` and processes every values dictionary independently.

`clinic_demo 19.0.1.0.17` requires the repaired owner version and allows the same
failed Demo Run to adopt the repair only when `operations.referral` is already
DONE and the failed `operations.booking` savepoint left no booking references
committed.

Authoritative source fingerprint: `1b91d4402f242a91bbbb7a483403187936eab960cc1b9858b059bc7987af2c7e`

Expected owner-suite fingerprint: `58bdfcce0d5385599f06a081a21f35ecfcf298298becddf5c0a667e0154fa9f1`


## Runtime Repair 3 — clinic.appointment Field Contract

Runtime evidence showed `clinic_booking` querying `clinic.appointment.start_datetime`,
while canonical `clinic_doctor` owns `start/end/state`. `clinic_booking 19.0.1.0.4`
uses field-aware overlap and create/link bridges. `clinic_demo 19.0.1.0.19` requires
that owner version and preserves same-run bounded adoption after the
`operations.booking` savepoint rollback.

### Runtime Repair — Treatment Session room availability API

Prompt 14 requires `clinic_treatment_session 19.0.2.0.3`. The owner
extension now composes with `clinic_booking` rather than replacing Booking room
availability semantics.

Expected owner-suite fingerprint: `58bdfcce0d5385599f06a081a21f35ecfcf298298becddf5c0a667e0154fa9f1`.









