from odoo import fields, models, _


class AccountMove(models.Model):
    """Reverse traceability from standard accounting entries to Clinic Finance."""

    _inherit = "account.move"

    # Reverse links provide traceability without moving account.move ownership into Clinic Finance.
    clinic_finance_transaction_id = fields.Many2one(
        "clinic.finance.transaction", string="Clinic Finance Transaction",
        copy=False, index=True, ondelete="set null",
    )
    clinic_finance_transfer_id = fields.Many2one(
        "clinic.finance.transfer", string="Clinic Finance Transfer",
        copy=False, index=True, ondelete="set null",
    )

    def action_open_clinic_finance_source(self):
        self.ensure_one()
        if self.clinic_finance_transaction_id:
            return {
                "type": "ir.actions.act_window", "name": _("Clinic Finance Transaction"),
                "res_model": "clinic.finance.transaction", "view_mode": "form",
                "res_id": self.clinic_finance_transaction_id.id,
            }
        if self.clinic_finance_transfer_id:
            return {
                "type": "ir.actions.act_window", "name": _("Clinic Finance Transfer"),
                "res_model": "clinic.finance.transfer", "view_mode": "form",
                "res_id": self.clinic_finance_transfer_id.id,
            }
        return False


class AccountJournal(models.Model):
    """Non-invasive reverse mapping to Clinic Finance operating accounts."""

    _inherit = "account.journal"

    clinic_finance_account_ids = fields.One2many(
        "clinic.finance.account", "journal_id", string="Clinic Finance Accounts"
    )
    clinic_finance_account_count = fields.Integer(
        compute="_compute_clinic_finance_account_count"
    )

    def _compute_clinic_finance_account_count(self):
        for journal in self:
            journal.clinic_finance_account_count = len(journal.clinic_finance_account_ids)

    def action_open_clinic_finance_accounts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Clinic Finance Accounts"),
            "res_model": "clinic.finance.account", "view_mode": "list,form",
            "domain": [("journal_id", "=", self.id)],
            "context": {
                "default_journal_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }
