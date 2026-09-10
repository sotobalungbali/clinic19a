# Structural Inventory — `clinic_billing`

## Domain models

### Persistent owner/domain records
1. `clinic.billing.invoice`
2. `clinic.billing.line`
3. `clinic.billing.payment`
4. `clinic.billing.payment.line`
5. `clinic.billing.discount.rule`
6. `clinic.billing.discount.redemption`
7. `clinic.billing.voucher.program`
8. `clinic.billing.voucher`
9. `clinic.billing.voucher.redemption`
10. `clinic.insurance.claim`
11. `clinic.insurance.claim.line`
12. `clinic.billing.commission.rule`
13. `clinic.billing.commission.line`
14. `clinic.billing.commission.settlement`
15. `clinic.billing.gateway.tx`
16. `clinic.billing.gateway.event`
17. `clinic.billing.membership.usage`
18. `clinic.treatment.billing.link`
19. `clinic.billing.integration.event`

### Abstract engines/builders
- `clinic.billing.account.builder`
- `clinic.billing.payment.account.builder`
- `clinic.billing.discount.engine`
- `clinic.billing.voucher.engine`
- `clinic.billing.membership.engine`
- `clinic.billing.commission.engine`

## Upstream extensions
- `clinic.patient`
- `clinic.doctor`
- `booking.booking`
- `clinic.encounter`
- `clinic.care.plan`
- `clinic.package.allocation`
- `clinic.package.usage`
- `clinic.emar.administration`
- `account.move`
- `account.payment`
- `res.config.settings`

## Python files
- `billing_invoice.py` — billing document lifecycle and accounting navigation.
- `billing_line.py` — billable line computation and immutable-posted protection.
- `billing_payment.py` — ClinicOne payment and split-payment orchestration.
- `account_move_hook.py` — Odoo Accounting invoice builder/synchronization.
- `account_payment_hook.py` — Odoo 19 payment/reconciliation bridge.
- `billing_discount.py` — discount policy/redemption engine.
- `billing_voucher.py` — voucher program, voucher and redemption engine.
- `billing_membership_wallet.py` — membership/wallet soft contract.
- `billing_insurance.py` — insurance claim lifecycle.
- `billing_commission.py` — provider commission accrual/settlement.
- `billing_gateway_tx.py` — gateway transaction/event lifecycle.
- `treatment_hook.py` — typed clinical source traceability/import.
- `patient_hook.py`, `doctor_hook.py` — patient/provider billing navigation/KPIs.
- `source_model_bridges.py` — upstream billing navigation.
- `ui_bridge.py` — runtime-safe smart-button decoration.
- `integration_event.py` — downstream outbox contract.
- `cron.py` — accounting-state synchronization.
- `res_config_settings.py` — billing policies/credentials.
- `__init__.py` — explicit import order.

## Security
- `security/clinic_billing_security.xml` — category, user/cashier/manager groups and multi-company rules.
- `security/ir.model.access.csv` — ACL coverage for every persistent billing model.

## Data
- `data/billing_sequences.xml` — invoice/payment/claim/settlement/gateway/membership/event sequences and runtime UI bridge invocation.
- `data/billing_cron.xml` — accounting-state sync cron.

## Enterprise UI
- Invoice/Line
- Payment/Payment Line
- Discount Rule/Redemption
- Voucher Program/Voucher/Redemption
- Insurance Claim/Claim Line
- Commission Rule/Line/Settlement
- Gateway Transaction/Event
- Membership Usage
- Clinical Source Link
- Integration Event
- Billing Settings
- Billing menu hierarchy

Each persistent model has Search/List/Form coverage.

## Quality assets
- `tests/test_billing_enterprise.py`
- `tools/clinic_billing_guardrail.py`
- `tools/windows_upgrade_clinic_billing.ps1`
- `docs/*`
- `README.md`
- `AGENTS.md`



