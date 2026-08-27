# Runtime Repair 19.0.2.0.1 — Odoo 19 Multi-Create and MRO Safety

## Concrete runtime evidence

Upgrade failed while loading `data/session_stage_data.xml`:

`AttributeError: 'list' object has no attribute 'get'`

The failing owner method was `clinic.treatment.session.stage.create()`.

## Root cause

The historical Stage `create()` used `@api.model` and expected a single dict.
Odoo 19 invoked `create()` with a list of value dictionaries.

A same-pattern audit found the historical Treatment Session `create()` had the
same single-dict assumption.

The previous Hard Gate 5 file split also left three
`super(ClinicTreatmentSession, self)` calls inside the new extension class,
where `ClinicTreatmentSession` is not defined. Those calls could become
runtime NameError/MRO blockers after Stage creation succeeded.

## Repair

- Stage `create()` is now `@api.model_create_multi`, copies each values dict,
  applies the historical defaults per record, calls cooperative `super()`,
  then enforces single-default stage governance on the created recordset.
- Session legacy `create()` is now `@api.model_create_multi`, preserves
  company/sequence/follower behavior per record and calls cooperative `super()`.
- All stale `super(ClinicTreatmentSession, self)` references in the split
  legacy behavior file are replaced by cooperative zero-argument `super()`.

No historical public field, method name, workflow state, ACL, record rule,
billing bridge, stock bridge, UI, or downstream integration is removed.
