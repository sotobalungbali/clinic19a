# Runtime Repair 2026-08-20 / 01

## Evidence

Activation failed while validating `views/numbering_policy_views.xml`.

Odoo reported:

`Unsearchable field "compliant" in path "compliant"`

The search filter is:

`[('compliant', '=', False)]`

## Root cause

`clinic.l10n.id.numbering.policy.compliant` was a computed Boolean without
`store=True` and without a custom search method. It was safe for display and
decorations but not searchable in a domain.

## Repair

The field remains computed from native Odoo journal controls and is now
`store=True, index=True`.

The existing compute dependencies remain unchanged:

- `journal_id.code`
- `journal_id.refund_sequence`
- `journal_id.restrict_mode_hash_table`
- `expected_code`
- `dedicated_credit_note_sequence`
- `secure_posted_entries`

No view/filter/workflow/model/feature was removed.

## Prevention

The runtime regression suite asserts that `compliant` is stored/indexed.
The Enterprise Guardrail also rejects the mismatch search filter when the field
is not stored/searchable.

A full search-domain scan found no other ClinicOne-owned computed non-stored
field used by a search filter in this addon.

Runtime status remains PENDING until activation succeeds on the target Odoo 19 CE.
