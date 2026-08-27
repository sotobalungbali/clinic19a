from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicFinanceCategory(models.Model):
    """Configuration for governed internal Finance receipts and disbursements."""

    _name = "clinic.finance.category"
    _description = "Clinic Finance Category"
    _order = "sequence, code, name"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Finance category code must be unique per company.",
    )
    _approval_limit_nonnegative = models.Constraint(
        "CHECK(approval_limit >= 0)",
        "Finance category approval limit cannot be negative.",
    )

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    direction = fields.Selection(
        [("both", "Receipt & Disbursement"), ("in", "Receipt Only"), ("out", "Disbursement Only")],
        default="both", required=True, index=True,
    )
    # Category owns the default non-liquidity side of internally generated journal entries.
    counterpart_account_id = fields.Many2one(
        "account.account", string="Default Counterpart Account",
        check_company=True, ondelete="restrict",
    )
    approval_required = fields.Boolean(default=False)
    approval_limit = fields.Monetary(currency_field="currency_id", default=0.0)
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    analytic_required = fields.Boolean(default=False)
    notes = fields.Text()
    transaction_count = fields.Integer(compute="_compute_transaction_count")

    def _compute_transaction_count(self):
        Transaction = self.env["clinic.finance.transaction"]
        for record in self:
            record.transaction_count = Transaction.search_count([("category_id", "=", record.id)])

    # Odoo 19 accounts can be shared across company_ids; membership is the correct company check.
    @api.constrains("company_id", "counterpart_account_id")
    def _check_counterpart_company(self):
        for record in self:
            account = record.counterpart_account_id
            if account and record.company_id not in account.company_ids:
                raise ValidationError(_("The counterpart account must be available to the category company."))

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Finance Transactions"),
            "res_model": "clinic.finance.transaction",
            "view_mode": "list,form,pivot,graph",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id, "default_company_id": self.company_id.id},
        }
