# ClinicOne `clinic_ap` — Agent Guardrail

This addon is governed by the ClinicOne Enterprise Development Guardrail.

## Codex role
Codex is a bounded implementation worker. It is **not** the architect, simplifier, or an infinite retry engine.

Codex may implement a clearly identified defect only after the architecture, preservation boundary, ownership, acceptance criteria, and permitted files are defined.

Codex must not remove or reduce models, fields, methods, views, security, accounting ownership, integrations, or enterprise UI to make a test pass.

Retry limit:
- maximum 2 bounded implementation attempts;
- maximum 1 repetition of the same root cause;
- after that, STOP and return to root-cause/architecture review.

## Preservation rule
The authoritative baseline capabilities are AP document/header and lines, vendor bill bridge, AP payment-term policy, vendor AP policy/KPIs, purchase integration, inventory/receipt integration, Billing cost traceability, accounting navigation, aging, cashflow, and company configuration. These capabilities may be corrected or hardened, not silently deleted.

## Odoo 19 hard rules
- No executable `_sql_constraints`.
- `models.Constraint` / `models.Index` class attributes must start with `_`.
- `res.groups` uses `privilege_id`; never `category_id`.
- Search filters must have technical `name` attributes.
- Search `<group>` must not use legacy `expand` or `string` attributes.
- Use `<list>`, not `<tree>`.
- Do not use legacy `attrs=` or `states=` view attributes.
- Direct `res.currency` Many2one fields must not use `check_company=True`.
- `account.account` company filtering must follow Odoo 19 `company_ids` / `_check_company_domain` semantics.
- Do not redeclare core `res.partner.credit_limit` for AP vendor exposure; use `ap_vendor_credit_limit`.
- Do not redeclare core `property_supplier_payment_term_id`.
- Do not use `account.payment.state == 'posted'` as an Odoo 19 payment lifecycle contract.
- Do not call legacy `account.payment.term.compute(...)`; use Odoo 19 `_compute_terms(...)` via the AP helper.
- Do not use the pre-19 `stock.valuation.layer` / `stock_move.stock_valuation_layer_ids` contract; Odoo 19 receipt valuation must use native `stock.move.value`.
- Cross-addon Smart Button decorations must be runtime-safe/idempotent; no fragile hard inherited-view XPath against another ClinicOne addon.

