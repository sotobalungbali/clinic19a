# ClinicOne — clinic_consent_legal Structural Inventory

## Active import graph
1. `consent_form_template.py`
2. `consent_form.py`
3. `consent_signature.py`
4. `consent_attachment.py`
5. `res_partner_inherit.py`
6. `treatment_inherit.py`
7. `appointment_inherit.py`
8. `billing_invoice_inherit.py`

Dormant and intentionally not imported: `doctor_schedule_inherit.py`, `models.py`, `xxx_clinic_consent_legal.py`.

## Core user-facing models

### clinic.consent.template
Canonical owner exists in `clinic_treatment_catalog`; this addon extends it in place with mail/activity and legal governance. Added legal fields include `legal_governed`, `legal_reference`, `title`, `company_id`, legal `state`, version controls, effective/supersession fields, `applicability`, legal content/evidence fields, checksum, usage metrics and mail template. Canonical fields such as `name`, `scope`, `category`, `validity_days`, `treatment_id`, `notes`, `default_item_ids` and `version_ids` remain available from the canonical model.

Primary lifecycle/actions: Publish, Retire, Duplicate New Version, Create Consent, View Related Consents.

### clinic.consent.form
Patient legal document with clinical references, content snapshot, state, signer/guardian data, signature capture, integrity hash, expiry, portal URL, reminders, signature ledger and legal attachment ledger.

Lifecycle: Draft → To Sign → Signed → Archived, with Cancel and Reset where permitted.

### clinic.consent.signature
Append-only-oriented signature evidence ledger with signer role, signature image, timestamp, IP/user-agent/device hint, content snapshot/checksum and signed/revoked/superseded lifecycle.

### clinic.consent.attachment
Legal/evidence attachment registry with confidentiality, portal visibility/redaction controls, checksum, provenance and attachment/external URL support.

## Odoo / ClinicOne extensions
- `res.partner`: consent metrics, last consent, portal links, smart actions.
- `clinic.treatment`: consent policy, templates, validity override, autogeneration policy and metrics.
- `clinic.appointment`: effective consent policy/status/template and create/view actions.
- `account.move`: consent enforcement/status and post-time validation.

## Controllers / hooks
- `/my/consents`: authenticated read-only portal listing.
- `/my/consents/<id>`: token/ownership-checked read-only document page.
- `post_init_hook`: resilient optional UI integrations for partner/treatment/appointment/invoice and optional root-menu reparenting without force-upgrading sibling addons.

## Security
- Local ACLs: consent form, signature, attachment.
- Canonical template ACL remains inherited from canonical owner `clinic_treatment_catalog`.
- Company record rules: template/form/signature/attachment.
- No public/portal ORM ACL.

## Constraints
- Active `models.Constraint`: 4.
- Full non-backup source including dormant aggregate: 8.
- Legacy `_sql_constraints`: 0.
