# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ClinicWalletUI(models.Model):
    _inherit = "clinic.wallet"

    transaction_count = fields.Integer(compute="_compute_wallet_counts")
    posted_transaction_count = fields.Integer(compute="_compute_wallet_counts")
    rule_count = fields.Integer(compute="_compute_wallet_counts")

    @api.depends("transaction_ids.state", "rule_ids.active")
    def _compute_wallet_counts(self):
        for wallet in self:
            wallet.transaction_count = len(wallet.transaction_ids)
            wallet.posted_transaction_count = len(
                wallet.transaction_ids.filtered(lambda tx: tx.state == "posted")
            )
            wallet.rule_count = len(wallet.rule_ids.filtered("active"))

    def _open_operation_wizard(self, operation_type):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": dict(
                self.env["clinic.wallet.operation.wizard"]._fields["operation_type"].selection
            ).get(operation_type, _("Wallet Operation")),
            "res_model": "clinic.wallet.operation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_wallet_id": self.id,
                "default_operation_type": operation_type,
                "default_journal_id": self.get_wallet_journal().id,
            },
        }

    def action_topup(self):
        return self._open_operation_wizard("topup")

    def action_refund(self):
        return self._open_operation_wizard("refund")

    def action_adjust_in(self):
        self._check_access_manager()
        return self._open_operation_wizard("adjust_in")

    def action_adjust_out(self):
        self._check_access_manager()
        return self._open_operation_wizard("adjust_out")

    def action_view_partner(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient / Customer"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
            "target": "current",
        }

    def action_view_rules(self):
        self.ensure_one()
        action = self.env.ref("clinic_wallet.action_wallet_rules").read()[0]
        action["domain"] = [("wallet_id", "in", [False, self.id])]
        action["context"] = {"default_wallet_id": self.id, "default_company_id": self.company_id.id}
        return action

    def action_print_statement(self):
        self.ensure_one()
        return self.env.ref("clinic_wallet.action_report_wallet_statement").report_action(self)




