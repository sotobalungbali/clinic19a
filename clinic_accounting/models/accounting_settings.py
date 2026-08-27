from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Company-scoped Accounting governance settings."""

    _inherit = "res.company"

    clinic_accounting_default_ledger_id = fields.Many2one(
        "clinic.accounting.ledger",
        string="Default Clinic Accounting Ledger",
        check_company=True,
    )
    clinic_accounting_adjustment_journal_id = fields.Many2one(
        "account.journal",
        string="Accounting Adjustment Journal",
        check_company=True,
        domain="[('company_id', '=', id), ('type', '=', 'general')]",
    )
    clinic_accounting_adjustment_approval_threshold = fields.Monetary(
        string="Adjustment Approval Threshold",
        currency_field="currency_id",
        default=0.0,
        help="Adjustments at or above this amount require Accounting Approver review. Zero auto-approves after submit.",
    )
    clinic_accounting_close_require_reconciled_receivable = fields.Boolean(
        string="Block Close on Unreconciled Receivables",
        default=False,
    )
    clinic_accounting_close_require_reconciled_payable = fields.Boolean(
        string="Block Close on Unreconciled Payables",
        default=False,
    )
    clinic_accounting_auto_monthly_trial_balance = fields.Boolean(
        string="Auto-Generate Prior-Month Trial Balance",
        default=False,
    )

    @api.constrains(
        "clinic_accounting_default_ledger_id",
        "clinic_accounting_adjustment_journal_id",
    )
    def _check_clinic_accounting_company_settings(self):
        for company in self:
            ledger = company.clinic_accounting_default_ledger_id
            if ledger and ledger.company_id != company:
                raise ValidationError(
                    _("Default Clinic Accounting Ledger must belong to this company.")
                )

            journal = company.clinic_accounting_adjustment_journal_id
            if journal and (
                journal.company_id != company
                or journal.type != "general"
            ):
                raise ValidationError(
                    _("Accounting Adjustment Journal must be a General journal of this company.")
                )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_accounting_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    clinic_accounting_default_ledger_id = fields.Many2one(
        related="company_id.clinic_accounting_default_ledger_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    clinic_accounting_adjustment_journal_id = fields.Many2one(
        related="company_id.clinic_accounting_adjustment_journal_id",
        readonly=False,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
    )
    clinic_accounting_adjustment_approval_threshold = fields.Monetary(
        related="company_id.clinic_accounting_adjustment_approval_threshold",
        readonly=False,
        currency_field="clinic_accounting_currency_id",
    )
    clinic_accounting_close_require_reconciled_receivable = fields.Boolean(
        related="company_id.clinic_accounting_close_require_reconciled_receivable",
        readonly=False,
    )
    clinic_accounting_close_require_reconciled_payable = fields.Boolean(
        related="company_id.clinic_accounting_close_require_reconciled_payable",
        readonly=False,
    )
    clinic_accounting_auto_monthly_trial_balance = fields.Boolean(
        related="company_id.clinic_accounting_auto_monthly_trial_balance",
        readonly=False,
    )
