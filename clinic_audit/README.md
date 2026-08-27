# ClinicOne Audit & Compliance

`clinic_audit` 19.0.2.0.3 is addon #38 of the ClinicOne 39-addon plan.

The legacy project contains two independent definitions of `clinic.audit.log`
(`clinic_audit` and `clinic_encounter`). To avoid registry ownership instability,
this build preserves a minimal compatibility surface for that legacy model but
stores the authoritative immutable compliance trail in `clinic.audit.event`.

Key capabilities:

- suite-wide create/write/unlink coverage for audited ClinicOne model catalog;
- compatibility integration with `clinic.mixin.audit` from `clinic_base`;
- company/branch-aware immutable evidence;
- per-company SHA-256 hash chain;
- field-level before/after digests with privacy-aware redaction;
- compliance policies and review workflow;
- integrity verification;
- JSON evidence export;
- bounded legacy-log import for historical preservation;
- complete Search/List/Form UI for all operational governance models;
- Enterprise Development Guardrail HARD GATE 0–15.

Runtime installation on the user's Odoo 19 CE system is still required before
the addon can be declared frozen.
