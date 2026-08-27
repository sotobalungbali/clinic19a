# ClinicOne — clinic_consent_legal UI/UX Matrix

| Model | Search | List | Form | Statusbar / Header | Smart / Body / O2M actions |
|---|---|---|---|---|---|
| clinic.consent.template | Yes | Yes | Yes | Draft / Published / Retired; Publish, Duplicate, Retire, Create Consent | Usage smart button; canonical default items/version history |
| clinic.consent.form | Yes | Yes | Yes | Draft / To Sign / Signed / Cancelled / Archived; Request Signature, Sign, Reminder, Cancel, Reset, Archive | Signatures, Legal Docs, Files, Template; O2M open buttons; portal preview |
| clinic.consent.signature | Yes | Yes | Yes | Signed / Revoked / Superseded | Revoke, Supersede, Open Consent, Portal |
| clinic.consent.attachment | Yes | Yes | Yes | Evidence-focused form | Portal show/hide, Open Attachment, Open Portal |

## Defensive sibling-form integrations
At post-init, the addon may extend compatible primary forms for `res.partner`, `clinic.treatment`, `clinic.appointment`, and `account.move`. Missing sibling presentation XML-IDs/anchors must not block installation.

## Human-friendly principles
- Legal workflow actions remain in headers.
- Smart buttons show evidence/navigation, not decorative counters.
- One2many ledgers provide row navigation where useful.
- Core legal models are fully usable from local menus even if optional sibling UI integration is skipped.
