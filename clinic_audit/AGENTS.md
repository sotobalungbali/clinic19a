# ClinicOne `clinic_audit` — Enterprise Development Guardrail

Codex is a bounded implementation worker only: not architect, not simplifier,
and not an unbounded retry engine.

Hard boundaries:

- The authoritative source baseline is `clinic19a(20260822-092627).md`.
- Basenames beginning with a digit are backup artifacts and are never packaged.
- `clinic.audit.log` remains a compatibility surface because historical modules
  already emit to it and `clinic_encounter` also defines that model.
- Immutable #38-owned compliance evidence is stored in `clinic.audit.event`.
- No business model from addons 1–37 is re-owned or shadowed.
- Coverage uses an Odoo registry hook with origin chaining; no source monkey patch
  is written into upstream addons.
- Business create/write/unlink remains subject to the original model ACL/rules.
- Audit capture fails closed by default.
- Odoo 19 `models.Constraint` is mandatory.
- Maximum bounded implementation repair attempts for this build: 3.
