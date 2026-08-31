# Runtime Repair 19.0.1.0.1 — Odoo 19 `res.users.group_ids`

## Concrete runtime evidence

ClinicOne MASTER PROMPT 09 `workforce.staff` failed after creating a presentation
user with:

`AttributeError: 'res.users' object has no attribute 'groups_id'`

The failure occurred inside `clinic_patient.models.res_users_inherit` after
`super().create()` returned the new user.

## Root cause

Odoo 19 defines the explicit user-group Many2many as `res.users.group_ids`.
The ClinicOne patient extension still contained two active legacy references:

- a `write()` trigger checking the incoming key `groups_id`;
- `_ensure_patient_link_post_create()` reading `self.groups_id`.

The latter was executed for every newly created user and therefore blocked the
Prompt-09 workforce generator.

## Targeted owner-addon repair

The active references are migrated to `group_ids` without changing patient,
portal, security, or company semantics.

A hard static guard now rejects active `groups_id` usage in
`models/res_users_inherit.py`.

No model, field, ACL, record rule, workflow, or menu is added or removed.
