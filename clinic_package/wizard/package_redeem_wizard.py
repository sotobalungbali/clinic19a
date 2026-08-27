
# -*- coding: utf-8 -*-
"""Front-desk redemption wizard with explicit validation and audit trail."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicPackageRedeemWizard(models.TransientModel):
    _name = "clinic.package.redeem.wizard"
    _description = "Redeem Clinic Package Benefit"

    allocation_id = fields.Many2one("clinic.package.allocation", required=True, check_company=True)
    allocation_line_id = fields.Many2one("clinic.package.allocation.line", required=True, check_company=True)
    line_type = fields.Selection(related="allocation_line_id.line_type", readonly=True)
    remaining_qty = fields.Float(related="allocation_line_id.remaining_qty", readonly=True)
    remaining_credit = fields.Monetary(related="allocation_line_id.remaining_credit", readonly=True)
    currency_id = fields.Many2one(related="allocation_id.currency_id", readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", check_company=True)
    booking_id = fields.Many2one("booking.booking", check_company=True)
    care_plan_line_id = fields.Many2one("clinic.care.plan.line", check_company=True)
    visit_id = fields.Many2one("clinic.queue.visit", check_company=True)
    room_id = fields.Many2one("clinic.room", check_company=True)
    device_id = fields.Many2one("clinic.device", check_company=True)
    qty_used = fields.Float(default=1.0)
    credit_used = fields.Monetary(default=0.0)
    note = fields.Text()

    @api.onchange("allocation_id")
    def _onchange_allocation_id(self):
        for wizard in self:
            wizard.allocation_line_id = False
            if wizard.allocation_id:
                wizard.doctor_id = wizard.allocation_id.doctor_id

    @api.onchange("allocation_line_id")
    def _onchange_allocation_line_id(self):
        for wizard in self:
            line = wizard.allocation_line_id
            if not line:
                continue
            if line.line_type == "credit":
                wizard.qty_used = 0.0
                wizard.credit_used = min(line.remaining_credit, line.credit_amount_total)
            else:
                wizard.qty_used = min(line.consume_per_use or 1.0, line.remaining_qty)
                wizard.credit_used = 0.0

    def action_confirm_redeem(self):
        self.ensure_one()
        if self.allocation_line_id.allocation_id != self.allocation_id:
            raise UserError(_("Selected benefit does not belong to this package allocation."))
        usage = self.env["clinic.package.usage"].create(
            {
                "allocation_id": self.allocation_id.id,
                "allocation_line_id": self.allocation_line_id.id,
                "doctor_id": self.doctor_id.id,
                "booking_id": self.booking_id.id,
                "care_plan_line_id": self.care_plan_line_id.id,
                "visit_id": self.visit_id.id,
                "room_id": self.room_id.id,
                "device_id": self.device_id.id,
                "qty_used": self.qty_used,
                "credit_used": self.credit_used,
                "note": self.note,
            }
        )
        usage.action_confirm()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemption"),
            "res_model": "clinic.package.usage",
            "view_mode": "form",
            "res_id": usage.id,
        }
