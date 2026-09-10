
# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class ClinicTreatmentSessionNavigation(models.Model):
    """Focused enterprise drill-down actions."""

    _inherit = "clinic.treatment.session"

    def _open_record(self, record, title):
        self.ensure_one()
        if not record:
            raise UserError(_("No %s is linked.") % title)
        return {
            "type": "ir.actions.act_window", "name": title,
            "res_model": record._name, "view_mode": "form", "res_id": record.id,
        }

    def action_view_booking(self):
        return self._open_record(self.booking_id, _("Booking"))

    def action_view_encounter(self):
        return self._open_record(self.encounter_id, _("Encounter"))

    def action_view_referral(self):
        return self._open_record(self.referral_id, _("Referral"))

    def action_view_package_allocation(self):
        return self._open_record(self.package_allocation_id, _("Package Allocation"))

    def action_view_stock_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped("stock_move_id")
        return {
            "type": "ir.actions.act_window", "name": _("Session Stock Moves"),
            "res_model": "stock.move", "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }

    def action_view_audit_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Session Audit Events"),
            "res_model": "clinic.audit.event", "view_mode": "list,form",
            "domain": [("ref_model", "=", self._name), ("ref_res_id", "=", self.id)],
        }

    def action_view_ar_invoices(self):
        self.ensure_one()
        try:
            ARInvoice = self.env["clinic.ar.invoice"]
        except KeyError:
            raise UserError(_("Clinic AR is not installed."))
        if "treatment_session_id" not in ARInvoice._fields:
            raise UserError(_("Installed Clinic AR has no Treatment Session bridge."))
        return {
            "type": "ir.actions.act_window", "name": _("AR Invoices"),
            "res_model": "clinic.ar.invoice", "view_mode": "list,form",
            "domain": [("treatment_session_id", "=", self.id)],
        }
