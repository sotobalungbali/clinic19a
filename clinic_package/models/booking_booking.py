
# -*- coding: utf-8 -*-
"""Explicit scheduling/redemption bridge to ClinicOne Booking."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BookingBooking(models.Model):
    _inherit = "booking.booking"

    package_allocation_id = fields.Many2one(
        "clinic.package.allocation", string="Package Allocation", ondelete="set null", check_company=True
    )
    package_allocation_line_id = fields.Many2one(
        "clinic.package.allocation.line", string="Package Benefit", ondelete="set null", check_company=True
    )
    package_usage_id = fields.Many2one(
        "clinic.package.usage", string="Package Redemption", ondelete="set null", readonly=True, copy=False
    )
    package_id = fields.Many2one(
        "clinic.package", related="package_allocation_id.package_id", store=True, readonly=True
    )
    package_redeem_ready = fields.Boolean(compute="_compute_package_redeem_status")
    package_redeem_message = fields.Char(compute="_compute_package_redeem_status")

    @api.depends(
        "package_allocation_id",
        "package_allocation_id.state",
        "package_allocation_line_id",
        "package_usage_id",
        "patient_id",
        "treatment_id",
    )
    def _compute_package_redeem_status(self):
        for booking in self:
            ready = True
            message = _("Ready to redeem")
            if booking.package_usage_id:
                ready, message = False, _("Already redeemed")
            elif not booking.package_allocation_id:
                ready, message = False, _("Select a package allocation")
            elif not booking.package_allocation_line_id:
                ready, message = False, _("Select a package benefit")
            elif booking.package_allocation_id.state not in (
                ["active", "paused"] if booking.package_allocation_id.package_id.allow_usage_when_paused else ["active"]
            ):
                ready, message = False, _("Package allocation is not currently redeemable")
            elif booking.package_allocation_id.partner_id and booking.patient_id != booking.package_allocation_id.partner_id:
                ready, message = False, _("Booking patient does not match package patient")
            booking.package_redeem_ready = ready
            booking.package_redeem_message = message

    @api.onchange("package_allocation_id")
    def _onchange_package_allocation_id(self):
        for booking in self:
            booking.package_allocation_line_id = False
            allocation = booking.package_allocation_id
            if allocation and allocation.partner_id and not booking.patient_id:
                booking.patient_id = allocation.partner_id

    @api.constrains("package_allocation_id", "package_allocation_line_id", "patient_id")
    def _check_package_booking_consistency(self):
        for booking in self:
            allocation = booking.package_allocation_id
            line = booking.package_allocation_line_id
            if line and line.allocation_id != allocation:
                raise ValidationError(_("Selected package benefit must belong to the selected allocation."))
            if allocation and allocation.partner_id and booking.patient_id != allocation.partner_id:
                raise ValidationError(_("Booking patient must match the package allocation patient."))

    def action_redeem_package(self):
        self.ensure_one()
        if self.package_usage_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Package Redemption"),
                "res_model": "clinic.package.usage",
                "view_mode": "form",
                "res_id": self.package_usage_id.id,
            }
        if not self.package_redeem_ready:
            raise UserError(self.package_redeem_message or _("This booking is not ready for package redemption."))
        context = {
            "default_allocation_id": self.package_allocation_id.id,
            "default_allocation_line_id": self.package_allocation_line_id.id,
            "default_booking_id": self.id,
            "default_doctor_id": self.doctor_id.id,
        }
        return {
            "type": "ir.actions.act_window",
            "name": _("Redeem Package for Booking"),
            "res_model": "clinic.package.redeem.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
