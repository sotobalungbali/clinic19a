# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import UserError


class ClinicTreatmentSessionNavigation(models.Model):
    """Focused drill-down actions kept separate from workflow code."""

    _inherit = "clinic.treatment.session"

    def action_view_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("No Booking is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Booking"),
            "res_model": "booking.booking",
            "res_id": self.booking_id.id,
            "view_mode": "form",
        }

    def action_view_encounter(self):
        self.ensure_one()
        if not self.encounter_id:
            raise UserError(_("No Encounter is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Encounter"),
            "res_model": "clinic.encounter",
            "res_id": self.encounter_id.id,
            "view_mode": "form",
        }

    def action_view_referral(self):
        self.ensure_one()
        if not self.referral_id:
            raise UserError(_("No Referral is linked."))
        return self.referral_id.action_open_self()

    def action_view_package_allocation(self):
        self.ensure_one()
        if not self.package_allocation_id:
            raise UserError(_("No Package Allocation is linked."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "res_id": self.package_allocation_id.id,
            "view_mode": "form",
        }

    def action_view_stock_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped("stock_move_id")
        return {
            "type": "ir.actions.act_window",
            "name": _("Session Stock Moves"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }

    def action_view_audit_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Session Audit Events"),
            "res_model": "clinic.audit.event",
            "view_mode": "list,form",
            "domain": [
                ("ref_model", "=", self._name),
                ("ref_res_id", "=", self.id),
            ],
        }

    def action_view_ar_invoices(self):
        self.ensure_one()
        try:
            ARInvoice = self.env["clinic.ar.invoice"]
        except KeyError:
            raise UserError(_("Clinic AR is not installed."))

        if "treatment_session_id" not in ARInvoice._fields:
            raise UserError(
                _("Installed Clinic AR has no Treatment Session bridge.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("AR Invoices"),
            "res_model": "clinic.ar.invoice",
            "view_mode": "list,form",
            "domain": [("treatment_session_id", "=", self.id)],
        }
