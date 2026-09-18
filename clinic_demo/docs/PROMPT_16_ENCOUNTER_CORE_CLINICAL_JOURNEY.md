
# MASTER PROMPT 16 — Encounter & Core Clinical Journey

## Status

SOURCE / STATIC / PACKAGE: PASS  
ODOO RUNTIME: PENDING

## Registry

Prompt 16 adds two bounded generators:

1. `operations.encounter` — phase `16_clinical`, sequence `630`,
   depends on `operations.queue_triage`.
2. `operations.treatment_session` — phase `16_clinical`, sequence `640`,
   depends on `operations.encounter`.

Registered generator count grows from **13 to 15**. The final enterprise target
remains 35 and is completed progressively by later Master Prompts.

## Encounter coverage

Stable clinical anchors:

- `DEMO-ENC-001` — new-patient core completed Encounter.
- `DEMO-ENC-LIVE-001` — Prompt-15 normal-triage journey continued into an active
  Encounter, then completed by the Treatment Session generator.
- `DEMO-ENC-RET-001` — returning-patient historical Encounter.
- `DEMO-ENC-CHRON-001` — recurring/long-term-care Encounter.
- `DEMO-ENC-PKG-001` — package-persona clinical Encounter.

Each Encounter has:
- source-owned patient/provider identity;
- stage-driven workflow;
- synthetic clinical assessment;
- finalized SOAP note;
- source-supported free-text diagnosis classification;
- procedure plan executed by owner workflow methods;
- anchor-relative business dates without touching `create_date`/`write_date`.

## Treatment Session coverage

Stable anchors:

- `DEMO-SESSION-001` — Booking-generated Treatment Session, confirmed, started,
  service line consumed, and completed through owner methods.
- `DEMO-SESSION-NOSHOW-001` — source-valid no-show workflow.
- `DEMO-SESSION-CANCEL-001` — source-valid cancellation workflow.
- `DEMO-SESSION-LINE-001` — non-stock, non-billable consumed service line.

Billing execution is intentionally deferred to MASTER PROMPT 18. The Session
still carries the source-native billing bridge fields and consumed service
lineage.

## Follow-up linkage

A generic synthetic Post-Care Protocol is activated through its owner action and
the completed core Encounter invokes `action_create_postcare_plan()`. Detailed
future follow-up task/check-in population remains MASTER PROMPT 20.

## Safety

- no direct terminal Encounter/Treatment Session state writes;
- no direct SQL;
- no `sudo()` in Prompt-16 generators;
- no audit timestamp backdating;
- no real external messaging/payment/integration side effects;
- all patient/clinical content is synthetic and explicitly non-diagnostic.
























