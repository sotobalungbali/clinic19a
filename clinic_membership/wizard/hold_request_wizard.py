


# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class MembershipHoldRequestWizard(models.TransientModel):
    _name = "membership.hold.request.wizard"
    _description = "Request Membership Hold"

    contract_id = fields.Many2one("membership.contract", required=True, readonly=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True)
    reason = fields.Text(required=True)

    def action_create_request(self):
        self.ensure_one()
        if self.contract_id.state not in ("active", "on_hold"):
            raise UserError(_("A hold request requires an Active or On Hold membership."))
        hold = self.env["membership.hold"].create({"contract_id": self.contract_id.id, "date_from": self.date_from, "date_to": self.date_to, "reason": self.reason})
        hold.action_submit()
        return {"type": "ir.actions.act_window", "name": _("Membership Hold"), "res_model": "membership.hold", "res_id": hold.id, "view_mode": "form", "target": "current"}

