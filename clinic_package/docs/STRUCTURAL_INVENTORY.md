# Structural Inventory — clinic_package 19.0.3.0.0

## Owner / extension models

Catalog and governance:
- `clinic.package`
- `clinic.package.tag`
- `clinic.package.line`
- `clinic.package.benefit`
- `clinic.package.pricing`
- `clinic.package.pricing.rule`
- `clinic.package.policy`

Entitlement and operational ledger:
- `clinic.package.allocation`
- `clinic.package.allocation.line`
- `clinic.package.usage`

Voucher/integration:
- `clinic.package.voucher`
- `clinic.package.voucher.batch`
- `clinic.package.integration.event`

Wizards:
- `clinic.package.redeem.wizard`
- `clinic.package.transfer.wizard`

Extensions:
- `clinic.patient`
- `res.partner`
- `booking.booking`
- `clinic.care.plan`
- `clinic.care.plan.line`
- `res.company` and `res.config.settings`
- `clinic.emar.order`
- `clinic.emar.schedule`
- `clinic.emar.administration`
- `clinic.emar.prescription`

## Enterprise contracts

- immutable allocation benefit snapshot after activation;
- governed package/allocation/usage/voucher lifecycle;
- pricing floor/ceiling and ordered rules;
- pause/transfer/refund policy;
- patient/contact consistency;
- booking and care-plan redemption;
- eMAR entitlement-to-medication traceability;
- durable downstream integration events with bounded retry;
- multi-company record rules;
- schema-safe company package settings;
- migration preservation from legacy stored company fields.
