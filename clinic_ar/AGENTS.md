# clinic_ar Implementation Guardrail

`clinic_ar` is an enterprise Accounts Receivable subledger for ClinicOne on Odoo 19 CE.

Codex or any implementation agent is a **bounded implementation worker** only. Architecture, ownership, preservation rules, dependency direction, UI completeness and acceptance criteria belong to the ClinicOne design authority.

Hard limits:
- Maximum 2 bounded implementation attempts for a proven defect.
- Maximum 1 repetition of the same root cause.
- Never delete, collapse, rename or move business models/fields/methods/views to make tests pass.
- Never add a dependency from `clinic_ar` to downstream `clinic_ap` or `clinic_wallet`.
- Never duplicate the accounting invoice owned by `clinic_billing`; Billing-linked AR must reuse its `account.move`.
- Never swallow accounting/reconciliation exceptions and still mark an AR workflow successful.
- Odoo 19 SQL objects (`models.Constraint` / `models.Index`) must use private class attribute names beginning with `_`.
- Legacy `_sql_constraints` is forbidden.
- `res.groups.category_id` is forbidden; use Odoo 19 `res.groups.privilege` + `privilege_id`.
- `account.account.company_id` assumptions are forbidden; use Odoo 19 company-aware account contracts.


- `res.currency` is global in Odoo 19; direct Many2one fields to it must not use `check_company=True`.



