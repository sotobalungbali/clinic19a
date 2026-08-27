# Architecture Decision — Authoritative Audit Event vs Legacy Audit Log

## Collision found in the authoritative snapshot

The historical source contains more than one `_name = "clinic.audit.log"` owner, including
`clinic_audit` legacy code and `clinic_encounter`.  Because `clinic_audit` is a low-level
dependency of many existing addons, adding enterprise fields directly to that duplicate model
would be load-order fragile and could be replaced later in registry construction.

## Decision

- Keep `clinic.audit.log` as a compatibility surface only.
- Own immutable compliance evidence in the new `clinic.audit.event` / `clinic.audit.event.line` ledger.
- Preserve historical custom producers that still write `clinic.audit.log`.
- Provide an explicit Legacy Evidence Import wizard to seal historical provenance into the new ledger.
- Install suite-wide create/write/unlink coverage only after the registry exists, using fixed model
  catalog generated from the source snapshot and the same `method.origin` family of patching used
  by Odoo's `base_automation` runtime mechanism.
- Do not create a manifest dependency on `clinic_encounter`, `clinic_integration_api`, or
  `clinic_analytics`; doing so would create or risk dependency cycles with existing ClinicOne addons.
