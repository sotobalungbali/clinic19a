



# MASTER PROMPT 15 — Queue, Triage & Arrival Operations

**Build:** `clinic_demo 19.0.1.0.20`

## Bounded Generator

- `operations.queue_triage`
- phase: `15_arrival`
- sequence: `620`
- depends on: `operations.booking`
- registered scope: generator #13 of the progressive 35-generator registry

## Source-Driven Workflow

Prompt 15 consumes current Prompt-14 demo bookings and uses existing owner
workflow methods for the front-to-clinical transition:

1. Booking → Appointment bridge through `_create_or_link_appointment()`;
2. Queue Token create → `action_issue()` / `action_call()`;
3. Queue creation through Token `action_create_queue()`;
4. room assignment through Queue `action_assign_room()` where exact room mapping exists;
5. Queue lifecycle through `action_start()` / `action_done()`;
6. Triage lifecycle through `action_start()` / `action_complete()`;
7. Vitals abnormality is owner-computed. `clinic_demo` never writes `is_abnormal`.

## Required Scenarios

- Waiting patient — `DEMO-QUEUE-WAIT-001`
- Called / in-service — `DEMO-TOKEN-CALLED-001`, `DEMO-QUEUE-SERVICE-001`
- Completed queue — `DEMO-QUEUE-DONE-001`
- Normal triage — `DEMO-TRIAGE-NORMAL-001`, `DEMO-VITALS-NORMAL-001`
- Mild attention-required abnormal vitals — `DEMO-TRIAGE-ABN-001`, `DEMO-VITALS-ABN-001`

The abnormal scenario is synthetic presentation data and does not claim a diagnosis.

## Identity Bridges

- Booking patient (`res.partner`) → exact `clinic.patient.partner_id`.
- Booking doctor (`clinic.doctor`) → exact Prompt-09 provider identity → `hr.employee` for Queue.
- Booking room (`booking.room`) → exact `clinic_room_id` for Queue room where available.
- Triage doctor remains the Booking `clinic.doctor`.

No fuzzy name lookup is used.

## Compatibility

A Demo Run that has completed Prompt 14 normally returns to **Draft**. This cumulative
build may adopt that same Draft run through **Refresh Compatibility** only when the
Prompt-14-and-earlier checkpoint scope is exact, both Prompt-14 generators are Done,
and no `operations.queue_triage` checkpoint/reference exists yet. A defensive Ready
route is accepted only under the same exact Prompt-15 boundary.

Use the same Demo Run and **do not Reset**. For normal progressive generation click
**Generate Full Enterprise Dataset**. `Continue Generation` is only needed if the new
Prompt-15 checkpoint actually fails and the run enters Failed state.

## Owner Addon Changes

None. Prompt 15 uses existing Queue/Triage owner APIs.

## Runtime Acceptance

Prompt 15 becomes runtime PASS only after:

- Refresh Compatibility = Compatible;
- same existing Demo Run, no Reset;
- Generate Full Enterprise Dataset skips the 12 already-Done checkpoints and completes `operations.queue_triage`;
- Waiting, Called/In-Service, Completed Queue, Normal Triage and attention-required
  abnormal-vitals lanes are visible and validate without orphan or identity mismatch.


## Deployment Verification

A successful Prompt-15 deployment must report **13 bounded generator(s)** and the
registered-scope notification must mention **Prompt-15 queue/triage arrival operations**.
If the notification still reports 12 generators, Odoo is still running the Prompt-14
registry and Prompt 15 has not been loaded.


### Runtime repair 19.0.1.0.21

The first `.20` runtime preflight exposed an orchestration-only schema mismatch:
canonical `clinic.appointment` has no `treatment_id`. `.21` removes that invalid
requirement and corrects Appointment/Triage patient comparison to the shared
`clinic.patient` identity. Treatment remains sourced from `booking.booking` and
passed to Queue Token/Queue where supported by owner models.

The failed preflight is savepoint-bounded; adoption is allowed only when
`operations.queue_triage` is Failed and no Prompt-15 reference exists.
























