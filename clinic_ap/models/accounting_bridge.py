from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    clinic_ap_ids = fields.One2many("clinic.ap", "move_id", string="Clinic AP")
    clinic_ap_count = fields.Integer(compute="_compute_clinic_ap_count")

    def _compute_clinic_ap_count(self):
        for move in self:
            move.clinic_ap_count = len(move.clinic_ap_ids)

    def action_view_clinic_ap(self):
        self.ensure_one()
        if len(self.clinic_ap_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Clinic AP"),
                "res_model": "clinic.ap",
                "view_mode": "form",
                "res_id": self.clinic_ap_ids.id,
                "context": {"create": False},
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic AP"),
            "res_model": "clinic.ap",
            "view_mode": "list,form",
            "domain": [("move_id", "=", self.id)],
            "context": {"create": False},
        }


class AccountPayment(models.Model):
    _inherit = "account.payment"

    clinic_ap_ids = fields.Many2many(
        "clinic.ap",
        compute="_compute_clinic_ap_relations",
        string="Clinic AP",
    )
    clinic_ap_count = fields.Integer(compute="_compute_clinic_ap_relations")

    @api.depends("reconciled_bill_ids")
    def _compute_clinic_ap_relations(self):
        for payment in self:
            aps = payment.reconciled_bill_ids.mapped("clinic_ap_ids")
            payment.clinic_ap_ids = aps
            payment.clinic_ap_count = len(aps)

    def action_view_clinic_ap(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic AP"),
            "res_model": "clinic.ap",
            "view_mode": "list,form",
            "domain": [("id", "in", self.clinic_ap_ids.ids)],
            "context": {"create": False},
        }

