# Runtime Repair 19.0.2.0.5 — Odoo 19 Menu Group Field

## Concrete runtime evidence

Upgrade of `clinic_referral` 19.0.2.0.4 reached `referral_menus.xml` and failed
with:

`ValueError: Invalid field 'groups_id' in 'ir.ui.menu'`

## Root cause

Odoo 19 `ir.ui.menu` uses `group_ids` as its visibility Many2many field.
The previous repair converted the Referral root from native `<menuitem>` syntax
to a raw `<record model="ir.ui.menu">` and accidentally used `groups_id`.

## Repair

The Referral root returns to Odoo-native menu syntax:

```xml
<menuitem id="menu_referral_root"
          name="Referrals"
          sequence="42"
          groups="clinic_referral.group_referral_user"/>
```

This is deliberately parentless at load time. Odoo's `<menuitem>` converter
maps `groups="..."` to the correct `group_ids` field internally.

The 19.0.2.0.4 runtime UI bridge still reparents the menu under a compatible
Patient/ClinicOne root when available.

## Same-pattern guard

The Enterprise Development Guardrail now rejects any raw
`<record model="ir.ui.menu">` using `groups_id` in `clinic_referral`.

No workflow, security group, ACL, record rule, business model, sequence,
booking integration, Patient/Branch runtime bridge or company-settings repair
is changed.

