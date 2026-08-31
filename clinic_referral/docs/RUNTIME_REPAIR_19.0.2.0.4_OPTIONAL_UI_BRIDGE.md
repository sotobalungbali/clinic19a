# Runtime Repair 19.0.2.0.4 — Optional Runtime UI Bridge

## Concrete runtime evidence

`clinic_referral` 19.0.2.0.3 replaced a missing Patient XML-ID with XML
`search=` parent resolution. In the installed database that search returned no
parent view. Odoo therefore saw an extension architecture beginning with
`<xpath>` but no `inherit_id`, classified it as a primary view and raised:

`Invalid view type: 'xpath'.`

## Architectural repair

Patient and Branch smart-button integrations are presentation-only. They are no
longer declared as hard load-time inherited XML records.

They are installed by an idempotent runtime bridge after normal Referral data
and menus have loaded.

Parent resolution order:

1. expected external ID with `raise_if_not_found=False`;
2. stable technical view name;
3. installed `model + type=form + mode=primary`;
4. final active-form candidate whose combined architecture is a real `<form>`.

Before creation, the bridge verifies the required `button_box` anchor.

Creation/update occurs inside a database savepoint. A historical parent layout
can therefore skip the optional decoration without blocking Referral business
installation.

## Menu compatibility

The Referral root menu is intrinsically valid with `parent_id=False`.
The runtime bridge reparents it under a compatible installed Patient/ClinicOne
root when one can be determined safely. Otherwise it remains a top-level app.

## Proven ClinicOne precedent

This follows the same source-actual defensive pattern already used by:
- `clinic_triage_vitals`;
- `clinic_package`;
- `clinic_membership`.

## Preserved repairs

- 19.0.2.0.1 bootstrap-safe company Referral settings;
- 19.0.2.0.2 no-`@string` inherited-view selector;
- 19.0.2.0.3 diagnosis of source/database XML-ID drift.

No Referral workflow, ACL, record rule, sequence, financial ownership or
downstream dependency is changed.

