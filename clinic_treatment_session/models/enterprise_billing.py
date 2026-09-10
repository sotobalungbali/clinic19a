
# -*- coding: utf-8 -*-
from odoo import Command, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicTreatmentSessionBilling(models.Model):
    """Bridge completed Treatment Session delivery to Clinic Billing."""

    _inherit = "clinic.treatment.session"

    def _can_create_clinic_billing(self):
        return (
            self.env.user.has_group(
                "clinic_treatment_session.group_treatment_session_manager"
            )
            or self.env.user.has_group("clinic_billing.group_clinic_billing_user")
        )

    def action_create_clinic_billing(self):
        self.ensure_one()
        if not self._can_create_clinic_billing():
            raise AccessError(
                _("Clinic Billing User or Treatment Session Manager access is required.")
            )
        if self.billing_invoice_id:
            return self.action_view_clinic_billing()
        if self.state != "done":
            raise UserError(_("Clinic Billing can only be created for a Done session."))

        Billing = self.env["clinic.billing.invoice"]
        vals = {}
        candidates = {
            "company_id": self.company_id.id,
            "currency_id": self.company_id.currency_id.id,
            "patient_id": self.patient_id.id,
            "clinic_patient_id": self.clinic_patient_id.id if self.clinic_patient_id else False,
            "clinic_doctor_id": self.doctor_id.id if self.doctor_id else False,
            "booking_id": self.booking_id.id if self.booking_id else False,
            "encounter_id": self.encounter_id.id if self.encounter_id else False,
            "external_origin": self.name,
            "invoice_date": fields.Date.context_today(self),
            "note": _("Generated from Treatment Session %s.") % self.display_name,
        }
        for key, value in candidates.items():
            if key in Billing._fields:
                vals[key] = value

        line_model = Billing._fields["line_ids"].comodel_name if "line_ids" in Billing._fields else False
        if line_model:
            Line = self.env[line_model]
            commands = []
            for payload in self.action_prepare_billing()["lines"]:
                product = self.env["product.product"].browse(payload["product_id"])
                lv = {}
                line_candidates = {
                    "product_id": product.id,
                    "name": payload["name"],
                    "quantity": payload["qty"],
                    "unit_price": payload["price_unit"],
                    "price_unit": payload["price_unit"],
                    "discount_percent": payload["discount"],
                    "discount": payload["discount"],
                }
                for key, value in line_candidates.items():
                    if key in Line._fields:
                        lv[key] = value
                if "tax_ids" in Line._fields:
                    lv["tax_ids"] = [Command.set(payload.get("tax_ids", []))]
                commands.append(Command.create(lv))
            if not commands:
                raise UserError(_("No billable Treatment Session lines are available."))
            vals["line_ids"] = commands

        invoice = Billing.create(vals)
        self.billing_invoice_id = invoice
        if hasattr(invoice, "action_recompute_totals"):
            invoice.action_recompute_totals()
        return self.action_view_clinic_billing()

    def action_view_clinic_billing(self):
        self.ensure_one()
        if not self.billing_invoice_id:
            raise UserError(_("No Clinic Billing Invoice is linked."))
        return {
            "type": "ir.actions.act_window", "name": _("Clinic Billing Invoice"),
            "res_model": "clinic.billing.invoice", "view_mode": "form",
            "res_id": self.billing_invoice_id.id,
        }

    def action_link_payment(self):
        result = super().action_link_payment()
        self.mapped("is_fully_invoiced")
        return result
