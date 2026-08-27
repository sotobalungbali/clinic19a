# -*- coding: utf-8 -*-

from odoo import Command, fields, models, _
from odoo.exceptions import AccessError, UserError


class ClinicTreatmentSessionBilling(models.Model):
    """Bridge completed treatment delivery to the upstream Billing owner."""

    _inherit = "clinic.treatment.session"

    def _can_create_clinic_billing(self):
        return (
            self.env.user.has_group(
                "clinic_treatment_session."
                "group_treatment_session_manager"
            )
            or self.env.user.has_group(
                "clinic_billing.group_clinic_billing_user"
            )
        )

    def action_create_clinic_billing(self):
        self.ensure_one()

        if not self._can_create_clinic_billing():
            raise AccessError(
                _(
                    "Clinic Billing User or Treatment Session Manager "
                    "access is required."
                )
            )

        if self.billing_invoice_id:
            return self.action_view_clinic_billing()

        if self.state != "done":
            raise UserError(
                _("Clinic Billing can only be created for a Done session.")
            )

        if not self.patient_id:
            raise UserError(
                _("A Patient/Contact is required before billing.")
            )

        payload = self.action_prepare_billing()
        line_commands = []

        for payload_line in payload.get("lines", []):
            product = self.env["product.product"].browse(
                payload_line["product_id"]
            )
            source_line = (
                self.env["clinic.treatment.session.line"].browse(
                    payload_line.get("session_line_id")
                )
                if payload_line.get("session_line_id")
                else False
            )

            line_commands.append(
                Command.create(
                    {
                        "product_id": product.id,
                        "treatment_id": (
                            source_line.treatment_id.id
                            if source_line and source_line.treatment_id
                            else self.treatment_id.id
                        ),
                        "name": (
                            payload_line.get("name")
                            or product.display_name
                        ),
                        "quantity": (
                            payload_line.get("qty")
                            or 1.0
                        ),
                        "product_uom_id": (
                            source_line.product_uom_id.id
                            if source_line and source_line.product_uom_id
                            else product.uom_id.id
                        ),
                        "booking_id": self.booking_id.id,
                        "encounter_id": self.encounter_id.id,
                        "performed_datetime": (
                            self.actual_end_datetime
                            or self.end_datetime
                            or self.start_datetime
                        ),
                        "unit_price": (
                            payload_line.get("price_unit")
                            or 0.0
                        ),
                        "discount_percent": (
                            payload_line.get("discount")
                            or (
                                source_line.discount
                                if source_line
                                else 0.0
                            )
                        ),
                        "tax_ids": [
                            Command.set(
                                payload_line.get("tax_ids")
                                or (
                                    source_line.tax_ids.ids
                                    if source_line
                                    else []
                                )
                            )
                        ],
                    }
                )
            )

        if not line_commands:
            raise UserError(
                _(
                    "No billable session lines are available. "
                    "Add billable Treatment Session Lines first."
                )
            )

        invoice = self.env["clinic.billing.invoice"].create(
            {
                "company_id": self.company_id.id,
                "currency_id": self.company_id.currency_id.id,
                "patient_id": self.patient_id.id,
                "clinic_patient_id": self.clinic_patient_id.id,
                "clinic_doctor_id": self.doctor_id.id,
                "booking_id": self.booking_id.id,
                "encounter_id": self.encounter_id.id,
                "external_origin": self.name,
                "invoice_date": fields.Date.context_today(self),
                "note": _(
                    "Generated from Treatment Session %s."
                )
                % self.display_name,
                "line_ids": line_commands,
            }
        )
        self.billing_invoice_id = invoice.id

        if hasattr(invoice, "action_recompute_totals"):
            invoice.action_recompute_totals()

        return self.action_view_clinic_billing()

    def action_view_clinic_billing(self):
        self.ensure_one()
        if not self.billing_invoice_id:
            raise UserError(
                _("No Clinic Billing Invoice is linked.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Billing Invoice"),
            "res_model": "clinic.billing.invoice",
            "res_id": self.billing_invoice_id.id,
            "view_mode": "form",
        }

    def action_link_payment(self):
        """Preserve historical payment-sync API without missing-field failure."""
        result = super().action_link_payment()
        # is_fully_invoiced is computed in the enterprise overlay; accessing it
        # here also ensures callers of the historical API receive a valid value.
        self.mapped("is_fully_invoiced")
        return result
