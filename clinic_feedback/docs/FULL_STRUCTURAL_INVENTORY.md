# HARD GATE 4 — Full Structural Inventory

## Owned persistent models

1. `clinic.feedback.survey`
   - reusable patient satisfaction survey;
   - source type;
   - overall/NPS/recommendation/comment policy;
   - introduction and thank-you content.

2. `clinic.feedback.question`
   - dynamic question;
   - rating 1-5 / NPS 0-10 / Yes-No / Free Text;
   - required flag;
   - analytic category and weight.

3. `clinic.feedback.request`
   - tokenized invitation;
   - Patient + journey source;
   - Email send/reminder;
   - expiration;
   - public URL and submission lifecycle.

4. `clinic.feedback`
   - canonical patient response;
   - 1-5 satisfaction;
   - NPS;
   - recommendation;
   - feedback type;
   - source traceability;
   - immutable submitted evidence;
   - review and escalation trigger.

5. `clinic.feedback.answer`
   - structured Survey answer;
   - immutable after submission.

6. `clinic.feedback.escalation`
   - service-recovery case;
   - severity/category;
   - owner;
   - SLA;
   - investigation, recovery action, patient contact and resolution.

## Inherited integrations

- `booking.feedback.link`
- `booking.booking`
- `clinic.queue`
- `clinic.encounter`
- `clinic.postcare.plan`
- `clinic.patient`
- `clinic.doctor`
- `clinic.staff`
- `res.partner`
- `res.company`
- `res.config.settings`

## Delivery / service layer

- tokenized public controller;
- responsive Website QWeb Survey;
- 3 sequences;
- Email invitation;
- expiry cron;
- source automation cron;
- escalation SLA cron;
- Patient Feedback Summary PDF;
- Pivot and Graph analysis;
- 4-role security hierarchy;
- 6 company record rules;
- Enterprise Development Guardrail;
- runtime contract/regression suite.
