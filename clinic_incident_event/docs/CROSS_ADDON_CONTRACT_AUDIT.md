# Cross-Addon Contract Audit

## `clinic_encounter`

Existing Adverse Event owner: `clinic.adverse.event`.

Consumed live fields:
- company / Encounter / Patient / Doctor / Room;
- occurrence/detection timestamps;
- classification;
- severity;
- recurrence risk;
- narrative;
- immediate action;
- patient impact;
- regulator evidence;
- `action_ids -> clinic.ae.action`;
- `followup_ids -> clinic.ae.followup`.

Addon 34:
- does not redefine Adverse Event;
- does not redefine `clinic.ae.action`;
- creates at most one central Incident per Adverse Event;
- never changes the Adverse Event state automatically.

## `clinic_staff`

Current live source contains historical placeholder contracts for:
- `clinic.incident`;
- `occurred_at`;
- `involved_staff_ids`;
- Staff `incident_count`;
- KPI `incidents_count`;
- KPI `incidents_rate_per_100_assign`.

Addon 34 activates them while calling existing Staff/KPI logic first.

## Patient / Contact typing

- `clinic.patient.partner_id -> res.partner`
- `res.partner.patient_id -> clinic.patient`
- Booking Patient -> `res.partner`
- Queue Patient -> `res.partner`
- Feedback Escalation Patient -> related `res.partner`
- eMAR Patient -> `clinic.patient`
- Telemedicine Patient -> `clinic.patient`.

The Contact smart button uses stable native `base.view_partner_form`.

## Queue typing

`clinic.queue.doctor_id -> hr.employee`.

Addon 34 does not silently map Queue Doctor to `clinic.doctor`.

## eMAR

`clinic.emar.administration` is loaded through the nested live import graph.
Consumed:
- company;
- patient -> clinic.patient;
- doctor -> clinic.doctor;
- state.

eMAR state remains upstream-owned.

## Feedback

`clinic.feedback.escalation` remains service-recovery owner.
Incident stores provenance and does not resolve/cancel the Feedback Escalation.

## Telemedicine Secure Messaging

Consumed:
- Session company/branch/Patient/Doctor/Host Staff/Encounter/Booking;
- Thread company/branch/Patient/Doctor/Handler/Session/attention flag.

Security rule:
- Secure Message bodies are not copied;
- secure internal notes are not copied;
- Incident stores provenance plus Incident-specific narrative only.

## Branch

Existing Company policy:
`policy_branch_scope_incident_event`.

When enabled:
- Incident Branch is mandatory;
- branch must belong to Incident company;
- selected branch must be allowed for the user;
- record rules restrict branch visibility.

When disabled:
- Incident Branch must be empty.

## Future addons

No hard dependency on:
- `clinic_quality`
- `clinic_integration_api`
- `clinic_audit`
- `clinic_analytics`
