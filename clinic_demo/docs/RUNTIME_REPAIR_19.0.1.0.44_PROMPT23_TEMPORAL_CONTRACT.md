# Runtime Repair 19.0.1.0.44 - Prompt 23 Temporal Contract

## Root cause

The previous Temporal gate applied one strict `start_datetime < end_datetime`
rule to every referenced model exposing those field names. That was broader
than the owner contracts. `clinic.triage.session` explicitly allows equality:
its owner constraint rejects only an end earlier than the start. Start and
completion may occur in the same persisted second during one deterministic ORM
workflow, producing a valid zero-minute observation.

## Repair

The generic field-name inference was replaced by
`DATETIME_INTERVAL_CONTRACTS`, keyed by exact model name. Reservable resources,
bookings, blackouts, room sessions and treatment sessions use `strict` positive
intervals. Triage, Care Plan execution, and Imaging downtime use
`non_decreasing` chronology consistent with their owner constraints.

The gate remains read-only. It does not modify timestamps, repeat workflows,
backdate technical fields, or invoke a production sequence.

## Whole-path closure

The same repair audits downstream Workflow, Journey/Exception, Analytics, and
Integrity gates. Reset-policy decisions now explicitly cover every model
declared by the 35 registered generators. Unknown future models remain blocked.
The failed-prefix adoption contract resumes at `validation.temporal` while the
completed `validation.structural` checkpoint remains authoritative.


