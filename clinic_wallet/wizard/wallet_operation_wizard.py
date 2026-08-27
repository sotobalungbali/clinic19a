# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError


class ClinicWalletOperationWizard(models.TransientModel):
    _name = "clinic.wallet.operation.wizard"
    _description = "Wallet Operation Wizard"

    wallet_id = fields.Many2one("clinic.wallet", required=True, readonly=True)
    company_id = fields.Many2one(related="wallet_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="wallet_id.currency_id", readonly=True)
    partner_id = fields.Many2one(related="wallet_id.partner_id", readonly=True)
    operation_type = fields.Selection(
        [
            ("topup", "Top-Up"),
            ("refund", "Refund"),
            ("adjust_in", "Adjustment In"),
            ("adjust_out", "Adjustment Out"),
        ],
        required=True,
        readonly=True,
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    journal_id = fields.Many2one(
        "account.journal",
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank','cash','general'))]",
    )
    reference = fields.Char()
    note = fields.Text()
    available_balance = fields.Monetary(
        related="wallet_id.balance", currency_field="currency_id", readonly=True
    )

    @api.constrains("amount")
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_("Amount must be greater than zero."))

    def action_confirm(self):
        self.ensure_one()
        if self.operation_type in ("topup", "refund") and not (
            self.env.su or self.env.user.has_group("clinic_wallet.group_wallet_accountant")
        ):
            raise AccessError(_("Wallet Accountant rights are required for manual top-up/refund posting."))
        if self.operation_type in ("adjust_in", "adjust_out") and not self.env.user.has_group(
            "clinic_wallet.group_wallet_manager"
        ):
            raise AccessError(_("Only Wallet Managers can post balance adjustments."))
        if self.operation_type in ("refund", "adjust_out") and self.amount > self.wallet_id.balance:
            raise UserError(_("Amount exceeds the current available Wallet balance."))
        tx = self.env["clinic.wallet.transaction"].create({
            "wallet_id": self.wallet_id.id,
            "transaction_type": self.operation_type,
            "amount": self.amount,
            "journal_id": self.journal_id.id or False,
            "reference": self.reference or "",
            "note": self.note or "",
        })
        tx.action_post()
        return {
            "type": "ir.actions.act_window",
            "name": _("Wallet Transaction"),
            "res_model": "clinic.wallet.transaction",
            "view_mode": "form",
            "res_id": tx.id,
            "target": "current",
        }



