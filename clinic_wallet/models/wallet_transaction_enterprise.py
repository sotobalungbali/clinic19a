# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError, AccessError


class ClinicWalletTransactionEnterprise(models.Model):
    _inherit = "clinic.wallet.transaction"

    reversal_of_id = fields.Many2one(
        "clinic.wallet.transaction", string="Reversal Of", readonly=True, copy=False, index=True
    )
    reversal_tx_id = fields.Many2one(
        "clinic.wallet.transaction", string="Reversal Transaction", readonly=True, copy=False
    )

    def action_reverse(self):
        if not self.env.user.has_group("clinic_wallet.group_wallet_manager"):
            raise AccessError(_("Only Wallet Managers can reverse posted Wallet transactions."))
        mapping = {
            "topup": "adjust_out",
            "redeem": "adjust_in",
            "refund": "adjust_in",
            "adjust_in": "adjust_out",
            "adjust_out": "adjust_in",
        }
        for tx in self:
            if tx.state != "posted":
                raise UserError(_("Only posted transactions can be reversed."))
            if tx.reversal_tx_id:
                raise UserError(_("This transaction already has a reversal."))
            reverse = self.create({
                "wallet_id": tx.wallet_id.id,
                "transaction_type": mapping[tx.transaction_type],
                "amount": tx.amount,
                "journal_id": tx.journal_id.id or False,
                "reference": _("Reversal of %s") % tx.name,
                "note": _("Enterprise reversal generated from posted transaction %s.") % tx.name,
                "reversal_of_id": tx.id,
            })
            reverse.action_post()
            tx.reversal_tx_id = reverse.id
        return True




