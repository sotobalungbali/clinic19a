


# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class MembershipPointAdjustWizard(models.TransientModel):
    _name = "membership.point.adjust.wizard"
    _description = "Adjust Membership Loyalty Points"

    contract_id = fields.Many2one("membership.contract", required=True, readonly=True)
    points = fields.Float(required=True, digits=(16, 2))
    reason = fields.Text(required=True)

    def action_adjust(self):
        self.ensure_one()
        if not self.points:
            raise ValidationError(_("Point adjustment cannot be zero."))
        tx = self.env["membership.point.tx"].adjust_points(self.contract_id, self.points, note=self.reason)
        return {"type": "ir.actions.act_window", "name": _("Point Adjustment"), "res_model": "membership.point.tx", "res_id": tx.id, "view_mode": "form", "target": "current"}


