# Odoo Settings Routing Runtime Repair — 19.0.3.0.2

## Runtime symptom

Opening `/odoo/settings` displayed the dedicated
**ClinicOne Accounts Payable Settings** form instead of Odoo's global Settings.

## Root cause

Suite-wide source audit found 23 ClinicOne `res.config.settings` view records:

- 22 inherit `base.res_config_settings_view_form`;
- only `clinic_ap.view_clinic_ap_settings_form` was a standalone primary form.

That standalone view could participate in Odoo's default primary-view
resolution for `res.config.settings`. The AP action additionally pinned that
view through `view_id`.

## Upgrade-safe repair

The SAME view XML-ID is converted into an extension:

- `inherit_id = base.res_config_settings_view_form`
- `mode = extension`
- AP settings rendered as an Odoo 19 `<app>` with `<block>/<setting>`
- existing action `view_id` explicitly cleared with `eval="False"`
- AP action path made unique: `clinic-ap-settings`
- AP configuration menu renamed from generic `Settings` to `AP Settings`

The AP company fields, business logic, security, ACLs, workflows and existing
external IDs are preserved.
