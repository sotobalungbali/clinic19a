from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    # Company-scoped settings prevent one clinic company from silently sharing treasury policy with another.
    finance_general_journal_id = fields.Many2one(
        "account.journal", string="Finance General Journal", check_company=True,
        domain="[('company_id', '=', id), ('type', '=', 'general')]",
    )
    finance_default_account_id = fields.Many2one(
        "clinic.finance.account", string="Default Finance Account", check_company=True
    )
    finance_approval_threshold = fields.Monetary(
        string="Finance Approval Threshold", currency_field="currency_id", default=0.0
    )
    finance_cash_variance_tolerance = fields.Monetary(
        string="Cash Variance Tolerance", currency_field="currency_id", default=0.0
    )
    finance_variance_gain_account_id = fields.Many2one(
        "account.account", string="Cash Variance Gain Account", check_company=True
    )
    finance_variance_loss_account_id = fields.Many2one(
        "account.account", string="Cash Variance Loss Account", check_company=True
    )
    finance_auto_daily_position = fields.Boolean(
        string="Create / Refresh Daily Treasury Position", default=True
    )
    finance_position_include_ar = fields.Boolean(string="Include AR in Position", default=True)
    finance_position_include_ap = fields.Boolean(string="Include AP in Position", default=True)
    finance_position_include_wallet = fields.Boolean(string="Include Wallet in Position", default=True)

    @api.constrains(
        "finance_general_journal_id", "finance_default_account_id",
        "finance_variance_gain_account_id", "finance_variance_loss_account_id",
    )
    def _check_finance_configuration_company(self):
        for company in self:
            if company.finance_general_journal_id and (
                company.finance_general_journal_id.company_id != company
                or company.finance_general_journal_id.type != "general"
            ):
                raise ValidationError(_("Finance General Journal must be a General journal of this company."))
            if company.finance_default_account_id and company.finance_default_account_id.company_id != company:
                raise ValidationError(_("Default Finance Account must belong to this company."))
            for account in (
                company.finance_variance_gain_account_id,
                company.finance_variance_loss_account_id,
            ):
                if account and company not in account.company_ids:
                    raise ValidationError(_("Cash variance accounts must be available to this company."))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    finance_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    finance_general_journal_id = fields.Many2one(
        related="company_id.finance_general_journal_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
    )
    finance_default_account_id = fields.Many2one(
        related="company_id.finance_default_account_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    finance_approval_threshold = fields.Monetary(
        related="company_id.finance_approval_threshold", readonly=False,
        currency_field="finance_currency_id",
    )
    finance_cash_variance_tolerance = fields.Monetary(
        related="company_id.finance_cash_variance_tolerance", readonly=False,
        currency_field="finance_currency_id",
    )
    finance_variance_gain_account_id = fields.Many2one(
        related="company_id.finance_variance_gain_account_id", readonly=False
    )
    finance_variance_loss_account_id = fields.Many2one(
        related="company_id.finance_variance_loss_account_id", readonly=False
    )
    finance_auto_daily_position = fields.Boolean(
        related="company_id.finance_auto_daily_position", readonly=False
    )
    finance_position_include_ar = fields.Boolean(
        related="company_id.finance_position_include_ar", readonly=False
    )
    finance_position_include_ap = fields.Boolean(
        related="company_id.finance_position_include_ap", readonly=False
    )
    finance_position_include_wallet = fields.Boolean(
        related="company_id.finance_position_include_wallet", readonly=False
    )
