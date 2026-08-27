# ClinicOne — clinic_package (Odoo 19 CE)

Version: `19.0.3.0.0`

Enterprise treatment-package management for bundled care, reusable pricing and policy rules,
patient allocations, immutable entitlement snapshots, controlled redemption, voucher issuance,
booking/care-plan integration, and medication-workflow traceability to ClinicOne eMAR.

## Ownership boundary

`clinic_package` owns package catalog, entitlement, pricing/policy, voucher and redemption logic.
It does not own medication workflow, billing, finance, wallet, membership, portal, marketing,
reporting, analytics, or public API domains.

- eMAR remains the owner of prescription/order/schedule/administration.
- Package redemption may link to eMAR records for auditable entitlement traceability.
- Later downstream owners consume `clinic.package.integration.event` without reverse dependency.

## Main models

- `clinic.package`, `clinic.package.line`, `clinic.package.tag`
- `clinic.package.pricing`, `clinic.package.pricing.rule`
- `clinic.package.policy`, `clinic.package.benefit`
- `clinic.package.allocation`, `clinic.package.allocation.line`
- `clinic.package.usage`
- `clinic.package.voucher`, `clinic.package.voucher.batch`
- `clinic.package.integration.event`

## Enterprise changes in 19.0.3.0.0

- package company settings are schema-safe non-stored `res.company` compatibility proxies;
- legacy stored company setting values are preserved through a pre-upgrade migration;
- package usage can link to eMAR Order, Schedule and Administration;
- eMAR Order/Schedule/Administration/Prescription receive non-invasive reverse package navigation;
- patient/booking/care-plan/eMAR form decorations use runtime-safe idempotent view bridges;
- package manager implies package user;
- package tags now receive an explicit multi-company rule;
- all XML/ACL files are normalized for strict parsers;
- static guardrail enforces Odoo 19 constraints, UI matrix, action integrity, migration presence,
  schema-safe company settings, and the no-multiple-Python-base ORM rule.

## Odoo 19 constraint convention

Executable legacy `_sql_constraints` declarations are forbidden. SQL-persistent constraints use
`models.Constraint`; non-stored company configuration is validated in Python before parameter
persistence.

## Runtime status

A source/static PASS is not a Windows Odoo runtime PASS. After replacing the folder, upgrade
`clinic_package` on the target database and complete workflow/UI smoke tests before freezing.
