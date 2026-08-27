from odoo import api, fields, models, _


class ClinicBillingInvoice(models.Model):
    _inherit = "clinic.billing.invoice"

    ap_cost_line_ids = fields.One2many("clinic.ap.line", "billing_invoice_id", string="AP Cost Lines")
    ap_cost_count = fields.Integer(compute="_compute_ap_cost_count")

    def _compute_ap_cost_count(self):
        for rec in self:
            rec.ap_cost_count = len(rec.ap_cost_line_ids)

    def action_view_ap_costs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("AP Cost Allocations"),
            "res_model": "clinic.ap.line",
            "view_mode": "list,form",
            "domain": [("billing_invoice_id", "=", self.id)],
            "context": {"create": False},
        }


class ClinicBillingLine(models.Model):
    _inherit = "clinic.billing.line"

    ap_cost_line_ids = fields.One2many("clinic.ap.line", "billing_line_id", string="AP Cost Lines")
    ap_cost_count = fields.Integer(compute="_compute_ap_cost_count")

    def _compute_ap_cost_count(self):
        for rec in self:
            rec.ap_cost_count = len(rec.ap_cost_line_ids)

    def action_view_ap_costs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("AP Cost Allocations"),
            "res_model": "clinic.ap.line",
            "view_mode": "list,form",
            "domain": [("billing_line_id", "=", self.id)],
            "context": {"create": False},
        }
