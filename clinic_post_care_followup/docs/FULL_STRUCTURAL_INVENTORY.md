# HARD GATE 4 — Full Structural Inventory

## Owned persistent models

1. `clinic.postcare.protocol`
   - reusable post-treatment instructions;
   - treatment/procedure/Care Protocol applicability;
   - risk level;
   - default coordinator;
   - warning/emergency guidance.

2. `clinic.postcare.protocol.step`
   - timed follow-up step;
   - task type/channel;
   - email automation;
   - required response;
   - overdue escalation policy.

3. `clinic.postcare.plan`
   - patient-specific follow-up episode;
   - Encounter/Booking/Care Plan/Treatment source;
   - instructions acknowledgment;
   - task/check-in/escalation rollup;
   - source drill-down and PDFs.

4. `clinic.postcare.task`
   - concrete staff work item;
   - exact historical technical contract expected by `clinic_staff`;
   - automated email reminder;
   - phone/internal/manual work item;
   - due/contact/completion evidence;
   - overdue escalation.

5. `clinic.postcare.checkin`
   - structured patient-reported follow-up evidence;
   - recovery/wellbeing/pain/fever/bleeding/breathing signals;
   - attachments;
   - clinical review and escalation.

6. `clinic.postcare.escalation`
   - internal clinical attention record;
   - owner/staff activity;
   - acknowledge/start/resolve lifecycle;
   - source task/check-in traceability.

## Abstract model

- `clinic.postcare.company.mixin`

## Inherited upstream models

- `clinic.staff`
- `clinic.patient`
- `clinic.encounter`
- `booking.booking`
- `clinic.care.plan`
- `clinic.treatment`
- `res.company`
- `res.config.settings`

## Services

- 4 sequences;
- 1 patient email reminder template;
- hourly due-task processor;
- hourly opt-in Encounter-to-Post-Care creator;
- 2 PDFs;
- 4-level security hierarchy;
- 6 company record rules;
- Enterprise Development Guardrail;
- runtime regression/contract test suite.
