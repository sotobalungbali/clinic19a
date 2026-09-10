# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class ClinicBillingInvoiceARBridge(models.Model):
    _inherit = "clinic.billing.invoice"

    ar_invoice_ids = fields.One2many("clinic.ar.invoice", "billing_id", string="AR Documents")
    ar_invoice_count = fields.Integer(compute="_compute_ar_invoice_count")

    def _compute_ar_invoice_count(self):
        for rec in self:
            rec.ar_invoice_count = len(rec.ar_invoice_ids)

    def action_create_or_open_ar(self):
        self.ensure_one()
        ar = self.env["clinic.ar.invoice"].create_from_billing(self)
        return ar._get_records_action(name=_("Accounts Receivable"))

    def action_view_ar(self):
        self.ensure_one()
        if not self.ar_invoice_ids:
            raise UserError(_("No Accounts Receivable document exists for this Billing document."))
        return self.ar_invoice_ids._get_records_action(name=_("Accounts Receivable"))


class ClinicBillingPaymentARBridge(models.Model):
    _inherit = "clinic.billing.payment"

    ar_payment_ids = fields.One2many("clinic.ar.payment", "billing_payment_id", string="AR Receipts")
    ar_payment_count = fields.Integer(compute="_compute_ar_payment_count")

    def _compute_ar_payment_count(self):
        for rec in self:
            rec.ar_payment_count = len(rec.ar_payment_ids)

    def action_view_ar_receipts(self):
        self.ensure_one()
        return self.ar_payment_ids._get_records_action(name=_("AR Receipts"))



