# -*- coding: utf-8 -*-
# ClinicOne Billing — Odoo 19 account.payment bridge.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountPaymentClinicBridge(models.Model):
    _inherit = "account.payment"

    clinic_invoice_id = fields.Many2one(
        "clinic.billing.invoice", string="Clinic Invoice", index=True, copy=False
    )
    clinic_payment_id = fields.Many2one(
        "clinic.billing.payment", string="Clinic Billing Payment", index=True, copy=False
    )
    clinic_gateway_tx_id = fields.Many2one(
        "clinic.billing.gateway.tx", string="Gateway Transaction", index=True, copy=False
    )
    is_clinic_payment = fields.Boolean(compute="_compute_is_clinic_payment")
    clinic_note = fields.Char(string="Clinic Note")

    @api.depends("clinic_invoice_id", "clinic_payment_id")
    def _compute_is_clinic_payment(self):
        for rec in self:
            rec.is_clinic_payment = bool(rec.clinic_invoice_id or rec.clinic_payment_id)

    def action_post(self):
        result = super().action_post()
        self._clinic_try_reconcile_and_notify()
        return result

    def action_draft(self):
        result = super().action_draft()
        for payment in self.filtered("clinic_invoice_id"):
            payment.clinic_invoice_id.message_post(
                body=_("Accounting payment %s was reset to Draft.") % payment.display_name
            )
        return result

    def _clinic_try_reconcile_and_notify(self):
        """Reconcile the payment receivable with its ClinicOne accounting invoice."""
        for payment in self:
            invoice = payment.clinic_invoice_id
            move = invoice.move_id if invoice else False
            payment_move = payment.move_id
            if not invoice or not move or move.state != "posted" or not payment_move:
                continue
            if payment.state not in ("in_process", "paid"):
                continue

            invoice_lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
                and not line.reconciled
            )
            payment_lines = payment_move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
                and not line.reconciled
            )
            for payment_line in payment_lines:
                counterparts = invoice_lines.filtered(
                    lambda line: line.account_id == payment_line.account_id
                    and line.partner_id == payment_line.partner_id
                )
                candidates = counterparts | payment_line
                if len(candidates) > 1:
                    candidates.reconcile()

            invoice._sync_state_from_move()
            invoice.message_post(
                body=_("Accounting payment %s processed for this clinic invoice.")
                % payment.display_name
            )

    def action_open_clinic_invoice(self):
        self.ensure_one()
        if not self.clinic_invoice_id:
            raise UserError(_("No Clinic Billing Invoice is linked to this payment."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Billing Invoice"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "form",
            "res_id": self.clinic_invoice_id.id,
            "target": "current",
        }


class ClinicBillingPaymentAccountBuilder(models.AbstractModel):
    """Compatibility service that delegates to the authoritative split-payment flow."""

    _name = "clinic.billing.payment.account.builder"
    _description = "Clinic Billing Payment to Account Payment Builder"

    def build_account_payment(self, clinic_payment):
        clinic_payment.ensure_one()
        if clinic_payment.payments_generated_ids:
            return clinic_payment.payments_generated_ids[:1]
        if not clinic_payment.line_ids:
            raise UserError(_("Add at least one payment split line first."))

        generated = self.env["account.payment"]
        for line in clinic_payment.line_ids:
            payment = line._create_account_payment()
            if payment:
                generated |= payment
        if generated:
            clinic_payment.payments_generated_ids = [(6, 0, generated.ids)]
            if len(generated) == 1:
                clinic_payment.account_payment_id = generated.id
        return generated[:1]


class ClinicBillingPaymentAPBridge(models.Model):
    _inherit = "clinic.billing.payment"

    account_payment_id = fields.Many2one(
        "account.payment",
        string="Primary Accounting Payment",
        copy=False,
        readonly=True,
        help="Convenience link when the Clinic Billing Payment generated exactly one accounting payment.",
    )

    def action_create_account_payment(self):
        builder = self.env["clinic.billing.payment.account.builder"]
        for rec in self:
            builder.build_account_payment(rec)
        return True

    def action_post(self):
        """Keep split-payment posting authoritative; never create a duplicate aggregate payment."""
        result = super().action_post()
        for rec in self:
            if len(rec.payments_generated_ids) == 1:
                rec.account_payment_id = rec.payments_generated_ids.id
        return result


class ClinicBillingInvoiceRegisterPaymentShortcut(models.Model):
    _inherit = "clinic.billing.invoice"

    def action_register_account_payment(self):
        self.ensure_one()
        if not self.move_id:
            self.action_generate_account_move()
        if self.move_id.state != "posted":
            self.move_id.action_post()
        return self.move_id.action_register_payment()



