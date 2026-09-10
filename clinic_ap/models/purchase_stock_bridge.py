from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    clinic_ap_ids = fields.One2many("clinic.ap", "purchase_id", string="Clinic AP")
    clinic_ap_count = fields.Integer(compute="_compute_clinic_ap_count")

    def _compute_clinic_ap_count(self):
        for po in self:
            po.clinic_ap_count = len(po.clinic_ap_ids)

    def action_create_clinic_ap(self):
        self.ensure_one()
        existing = self.clinic_ap_ids.filtered(lambda ap: ap.state != "cancelled")
        if existing:
            return existing[0]._get_records_action(name=_("Clinic AP"))
        ap = self.env["clinic.ap"].create({
            "vendor_id": self.partner_id.id,
            "purchase_id": self.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "reference": self.partner_ref,
            "payment_term_id": self.payment_term_id.id or self.partner_id.property_supplier_payment_term_id.id,
            "line_ids": [
                (0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.name,
                    "product_uom_id": line.product_uom.id,
                    "quantity": line.product_qty,
                    "price_unit": line.price_unit,
                    "tax_ids": [(6, 0, line.taxes_id.ids)],
                    "purchase_line_id": line.id,
                })
                for line in self.order_line
                if not line.display_type
            ],
        })
        ap._autolink_stock_moves()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic AP"),
            "res_model": "clinic.ap",
            "view_mode": "form",
            "res_id": ap.id,
        }

    def action_view_clinic_ap(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic AP"),
            "res_model": "clinic.ap",
            "view_mode": "list,form",
            "domain": [("purchase_id", "=", self.id)],
            "context": {"default_purchase_id": self.id},
        }


class StockMove(models.Model):
    _inherit = "stock.move"

    clinic_ap_line_ids = fields.One2many("clinic.ap.line", "stock_move_id", string="Clinic AP Lines")
    clinic_ap_line_count = fields.Integer(compute="_compute_clinic_ap_line_count")

    def _compute_clinic_ap_line_count(self):
        for move in self:
            move.clinic_ap_line_count = len(move.clinic_ap_line_ids)

    def action_view_clinic_ap_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic AP Lines"),
            "res_model": "clinic.ap.line",
            "view_mode": "list,form",
            "domain": [("stock_move_id", "=", self.id)],
            "context": {"create": False},
        }


class ClinicAP(models.Model):
    _inherit = "clinic.ap"

    def _autolink_stock_moves(self):
        for ap in self:
            for line in ap.line_ids.filtered(lambda l: l.purchase_line_id and not l.stock_move_id):
                candidates = line.purchase_line_id.move_ids.filtered(
                    lambda move: move.state == "done" and move.product_id == line.product_id
                )
                if candidates:
                    line.stock_move_id = candidates[-1].id
        return True

    def _refresh_line_match_state(self):
        # Accessing computed fields forces current match values before workflow decisions.
        for ap in self:
            ap.line_ids.mapped("match_state")
        return True

