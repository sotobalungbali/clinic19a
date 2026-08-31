# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BookingBookingReferral(models.Model):
    """Attach ClinicOne referral attribution to the real Booking model."""

    _inherit = "booking.booking"

    referral_id = fields.Many2one(
        "clinic.referral",
        string="Referral",
        ondelete="set null",
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    referral_source_id = fields.Many2one(
        related="referral_id.source_id",
        store=True,
        readonly=True,
        index=True,
    )
    referral_program_id = fields.Many2one(
        related="referral_id.program_id",
        store=True,
        readonly=True,
        index=True,
    )

    @api.constrains("referral_id", "patient_id", "company_id")
    def _check_referral_booking_consistency(self):
        for booking in self:
            referral = booking.referral_id
            if not referral:
                continue
            if referral.company_id != booking.company_id:
                raise ValidationError(
                    _("Referral and Booking must belong to the same Company.")
                )
            if referral.patient_partner_id and referral.patient_partner_id != booking.patient_id:
                raise ValidationError(
                    _("Referral Patient and Booking Patient must match.")
                )

    @api.onchange("referral_id")
    def _onchange_referral_id(self):
        for booking in self:
            referral = booking.referral_id
            if not referral:
                continue
            if referral.patient_partner_id:
                booking.patient_id = referral.patient_partner_id
            if referral.target_doctor_id and not booking.doctor_id:
                booking.doctor_id = referral.target_doctor_id

    def action_open_referral(self):
        self.ensure_one()
        if not self.referral_id:
            raise UserError(_("No Referral is linked to this Booking."))
        return self.referral_id.action_open_self()

    def action_create_referral(self):
        self.ensure_one()
        if self.referral_id:
            return self.action_open_referral()

        patient = self.patient_id.patient_id
        if not patient:
            raise UserError(
                _(
                    "The Booking contact must have a linked Clinic Patient "
                    "before a Referral can be created."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("New Referral from Booking"),
            "res_model": "clinic.referral",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": patient.id,
                "default_target_doctor_id": self.doctor_id.id,
                "default_company_id": self.company_id.id,
                "default_origin_model_id": self.env["ir.model"]._get(
                    self._name
                ).id,
                "default_origin_res_id": self.id,
            },
        }

