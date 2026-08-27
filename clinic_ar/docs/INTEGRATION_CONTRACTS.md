# Integration Contracts

## Upstream
- `clinic_billing`: commercial/clinical billing owner; AR imports billing identity and reuses its legal accounting invoice.
- `clinic_membership`: canonical membership contract is `membership.contract`.
- `clinic_booking`: canonical booking is `booking.booking`.
- `clinic_treatment_session`: canonical treatment session is `clinic.treatment.session`.
- Patient/Doctor/Treatment/Package/Encounter ecosystem remains traceable through typed links.

## Odoo Accounting
- `account.move` is legal customer-invoice authority.
- `account.payment` is customer-receipt authority.
- Reconciliation outcome is authoritative for residual/open credit.
- Accounting errors are fatal to the corresponding AR workflow; no fake success state.

## Downstream
`clinic_wallet`, `clinic_ap`, reporting and analytics may consume AR integration events. `clinic_ar` must not depend back on those downstream addons.

## Billing UI Decoration Contract

`clinic_billing` remains a mandatory upstream business dependency.  AR fields and
actions extend `clinic.billing.invoice` and `clinic.billing.payment` directly.
Only form decoration is runtime-safe: the bridge resolves the upstream form XML
IDs with `raise_if_not_found=False`, tries validated XPath candidates, and skips
cosmetic integration if the current database form layout is incompatible.
