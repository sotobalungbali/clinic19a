# ClinicOne — clinic_consent_legal Enterprise Completeness Matrix

| Area | Acceptance criterion | Status |
|---|---|---|
| Identity | Correct ClinicOne/addon/platform and exact dependency contract | PASS |
| Preservation | Active imports + baseline models/fields/methods preserved subject only to explicit canonical-template reconciliation | PASS |
| Canonical ownership | `clinic.consent.template` extends frozen canonical model without overwriting canonical name/order/description semantics; legal copy clears canonical unique code | PASS |
| Odoo 19 constraints | No legacy `_sql_constraints`; class-level `models.Constraint` used | PASS |
| Legal migration safety | Existing canonical templates remain valid unless `legal_governed` is enabled | PASS |
| Template governance | Versioning, publish/retire, checksum, applicability and legal reference available | PASS |
| Consent lifecycle | Request/sign/cancel/reset/archive with integrity and expiry controls | PASS |
| Signature evidence | Signature ledger records signer context and content checksum/snapshot | PASS |
| Attachment evidence | Confidentiality, portal visibility, redaction and provenance controls | PASS |
| Portal | Read-only portal access uses server-side document access checking | PASS |
| Treatment integration | Consent policy/templates/metrics and request actions available | PASS |
| Appointment integration | Consent effective policy/status and creation path available | PASS |
| Billing integration | Consent enforcement/status available before invoice posting | PASS |
| UI coverage | Search/List/Form for 4 user-facing legal surfaces | PASS |
| Advanced UI | Statusbars, lifecycle buttons, smart buttons, body/O2M navigation are backed by real server methods | PASS |
| Security | ORM ACL + company rules authoritative; no Public/Portal ORM ACL | PASS |
| XML-ID resilience | Sibling presentation integration is runtime-discovered/optional, not a manifest installation blocker | PASS |
| Human-friendly code | Domain-oriented modules and useful ownership/legal comments | PASS |
| Codex boundedness | Max 3 focused attempts per root-cause; STOP thereafter | PASS |
| Runtime | Target PC fresh/upgrade activation | PENDING |
