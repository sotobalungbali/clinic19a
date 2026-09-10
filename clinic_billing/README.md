# ClinicOne — Billing (`clinic_billing`)

Enterprise clinical billing and financial orchestration for ClinicOne on Odoo 19 Community Edition.

## Ownership

`clinic_billing` owns ClinicOne billing documents, billing lines, split-payment orchestration, discount/voucher policy, insurance claims, provider commissions, gateway traceability, membership/wallet usage contracts, clinical source links, and downstream integration events.

It does **not** take ownership away from:
- Odoo Accounting (`account.move`, `account.payment`);
- ClinicOne Patient, Doctor, Booking, Encounter, Care Plan, Package, eMAR, Inventory, Room/Device, or Treatment Catalog;
- future/downstream AR, AP, Wallet, Audit, reporting, or analytics modules.

## Primary flow

Clinical source → Clinic Billing Invoice → Billing Lines → Accounting Invoice → Payment / Insurance / Voucher / Commission → Integration Event.

## Enterprise highlights

- Typed traceability to Booking, Encounter, Care Plan, Package, eMAR and treatment consumption.
- Odoo 19-native accounting/payment bridge.
- Split-payment orchestration.
- Discounts, vouchers, membership/wallet soft integration.
- Insurance claim lifecycle and provider commission settlement.
- Payment gateway transaction/event traceability.
- Multi-company ACL + record-rule security.
- Search/List/Form views for all 19 persistent billing models.
- Statusbars, smart buttons, body actions and One2many actions.
- ORM financial locks after posted accounting documents.
- Runtime-safe smart-button bridges into upstream ClinicOne forms.
- Integration-event outbox instead of hard forward dependencies to future finance/audit modules.

## Odoo 19 compatibility

Legacy executable `_sql_constraints` is not used. SQL-backed uniqueness rules use `models.Constraint`.
Standard payment integration uses the Odoo 19 `account.payment` contract (`memo`, `payment_reference`, and current payment states).

## Installation / upgrade

The authoritative addon folder must be:

`D:\projects\odoo19v\clinic19a\clinic_billing`

After replacing the complete folder, run a targeted Odoo update or use:

`tools/windows_upgrade_clinic_billing.ps1`

Source/static validation does not equal Windows runtime completion. Freeze the addon only after install/upgrade and smoke scenarios pass.



