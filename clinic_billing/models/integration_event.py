# -*- coding: utf-8 -*-
# ClinicOne Billing — downstream integration outbox.
# This keeps clinic_billing upstream of clinic_ar, clinic_wallet, clinic_audit, etc.

from odoo import api, fields, models, _


class ClinicBillingIntegrationEvent(models.Model):
    _name = "clinic.billing.integration.event"
    _description = "Clinic Billing Integration Event"
    _order = "created_on desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default="/", copy=False, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    event_type = fields.Selection(
        [
            ("invoice_created", "Invoice Created"),
            ("invoice_confirmed", "Invoice Confirmed"),
            ("invoice_posted", "Invoice Posted"),
            ("invoice_paid", "Invoice Paid"),
            ("invoice_cancelled", "Invoice Cancelled"),
            ("payment_posted", "Payment Posted"),
            ("payment_cancelled", "Payment Cancelled"),
            ("claim_changed", "Insurance Claim Changed"),
            ("gateway_changed", "Gateway Changed"),
        ],
        required=True,
        index=True,
    )
    invoice_id = fields.Many2one(
        "clinic.billing.invoice", ondelete="cascade", index=True, check_company=True
    )
    payment_id = fields.Many2one(
        "clinic.billing.payment", ondelete="cascade", index=True, check_company=True
    )
    payload = fields.Json(default=dict)
    created_on = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    state = fields.Selection(
        [("pending", "Pending"), ("processed", "Processed"), ("ignored", "Ignored"), ("failed", "Failed")],
        default="pending",
        required=True,
        index=True,
    )
    processed_on = fields.Datetime()
    retry_count = fields.Integer(default=0)
    error_message = fields.Text()
    note = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = sequence.next_by_code("clinic.billing.integration.event") or "/"
        return super().create(vals_list)

    def action_mark_processed(self):
        self.write({
            "state": "processed",
            "processed_on": fields.Datetime.now(),
            "error_message": False,
        })
        return True

    def action_retry(self):
        self.write({
            "state": "pending",
            "retry_count": self.retry_count + 1,
            "error_message": False,
        })
        return True

    def action_ignore(self):
        self.write({"state": "ignored", "processed_on": fields.Datetime.now()})
        return True


class ClinicBillingInvoiceIntegrationOutbox(models.Model):
    _inherit = "clinic.billing.invoice"

    integration_event_ids = fields.One2many(
        "clinic.billing.integration.event", "invoice_id", string="Integration Events", readonly=True
    )
    integration_event_count = fields.Integer(compute="_compute_integration_event_count")

    def _compute_integration_event_count(self):
        for rec in self:
            rec.integration_event_count = len(rec.integration_event_ids)

    def _emit_billing_event(self, event_type, payload=None):
        Event = self.env["clinic.billing.integration.event"].sudo()
        for rec in self:
            Event.create({
                "company_id": rec.company_id.id,
                "event_type": event_type,
                "invoice_id": rec.id,
                "payload": payload or {
                    "invoice_id": rec.id,
                    "number": rec.name,
                    "partner_id": rec.patient_id.id,
                    "clinic_patient_id": rec.clinic_patient_id.id if rec.clinic_patient_id else False,
                    "amount_total": rec.amount_total,
                    "currency_id": rec.currency_id.id,
                    "state": rec.state,
                },
            })

    def _on_after_create(self):
        result = super()._on_after_create()
        self._emit_billing_event("invoice_created")
        return result

    def _on_after_confirm(self):
        result = super()._on_after_confirm()
        self._emit_billing_event("invoice_confirmed")
        return result

    def _on_after_move_posted(self, move):
        result = super()._on_after_move_posted(move)
        self._emit_billing_event(
            "invoice_paid" if move.payment_state == "paid" else "invoice_posted",
            payload={
                "invoice_id": self.id if len(self) == 1 else self.ids,
                "account_move_id": move.id,
                "account_move_name": move.name,
                "payment_state": move.payment_state,
            },
        )
        return result

    def _on_after_cancel(self):
        result = super()._on_after_cancel()
        self._emit_billing_event("invoice_cancelled")
        return result

    def action_open_integration_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Integration Events"),
            "res_model": "clinic.billing.integration.event",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id, "default_company_id": self.company_id.id},
        }


class ClinicBillingPaymentIntegrationOutbox(models.Model):
    _inherit = "clinic.billing.payment"

    integration_event_ids = fields.One2many(
        "clinic.billing.integration.event", "payment_id", string="Integration Events", readonly=True
    )

    def _emit_payment_event(self, event_type):
        Event = self.env["clinic.billing.integration.event"].sudo()
        for rec in self:
            Event.create({
                "company_id": rec.company_id.id,
                "event_type": event_type,
                "invoice_id": rec.invoice_id.id,
                "payment_id": rec.id,
                "payload": {
                    "payment_id": rec.id,
                    "number": rec.name,
                    "invoice_id": rec.invoice_id.id,
                    "amount_total": rec.amount_total,
                    "currency_id": rec.currency_id.id,
                    "state": rec.state,
                },
            })

    def _on_after_post(self):
        result = super()._on_after_post()
        self._emit_payment_event("payment_posted")
        return result

    def _on_after_cancel(self):
        result = super()._on_after_cancel()
        self._emit_payment_event("payment_cancelled")
        return result
