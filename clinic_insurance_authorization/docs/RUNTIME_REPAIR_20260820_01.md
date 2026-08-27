# Runtime Repair 2026-08-20 / 01

## Runtime evidence

Activation failed during model setup with:

`KeyError: Field authorization_id referenced in related field definition clinic.treatment.insurance_authorization_state does not exist.`

The failing field is defined by addon 25 as:

`clinic.treatment.insurance_authorization_state -> authorization_id.state`

## Proven root cause

The latest user baseline contains historical files in `clinic_queue_room`:

- `models/treatment_inherit.py`
- `models/appointment_inherit.py`
- `models/res_partner_inherit.py`

Those files contain the expected insurance bridge fields:

- `clinic.treatment.insurance_policy_id`
- `clinic.treatment.authorization_id`
- `clinic.appointment.insurance_policy_id`
- `clinic.appointment.authorization_id`
- `res.partner.insurance_policy_id`

However, the current `clinic_queue_room/models/__init__.py` comments out all
three imports:

- `# from . import res_partner_inherit`
- `# from . import appointment_inherit`
- `# from . import treatment_inherit`

Therefore those source definitions are dead source and do not exist in the
runtime registry.

The previous source audit incorrectly treated their mere presence in the
repository as a live Odoo contract.

## Corrective action

`clinic_insurance_authorization` now defines the live insurance bridge fields
it actually requires on:

- `res.partner`
- `clinic.appointment`
- `clinic.treatment`

The related state fields now resolve against fields owned by the active addon
itself.

No Queue/Room source file is re-enabled and no frozen upstream module is
modified.

## Preservation

- `clinic_queue_room` remains frozen and untouched.
- Booking, Appointment and Treatment workflow ownership is unchanged.
- `clinic_billing` remains owner of `clinic.insurance.claim` and
  `clinic.insurance.claim.line`.
- Claim settlement remains in `clinic.billing.payment`.

## Prevention

The Enterprise Development Guardrail now requires the live bridge fields to be
declared inside `models/integration_bridge.py`.

The runtime regression suite verifies:
- Partner primary Policy field;
- Appointment Policy/Authorization fields;
- Treatment Policy/Authorization fields;
- Appointment/Treatment related authorization-state chains.

Static cross-addon validation distinguishes **imported/live files** from dead
commented source files.

Runtime status remains PENDING until installation succeeds on the target Odoo
19 CE environment.
