
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicTreatmentSessionLine(models.Model):
    """Detail line for service steps, consumables, medication, packages and notes."""

    _name = "clinic.treatment.session.line"
    _description = "Clinic Treatment Session Line"
    _order = "session_id, sequence, id"
    _rec_name = "display_name"
    _check_company_auto = True

    session_id = fields.Many2one("clinic.treatment.session", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="session_id.company_id", store=True, readonly=True)
    patient_id = fields.Many2one("res.partner", related="session_id.patient_id", store=True, readonly=True)
    clinic_doctor_id = fields.Many2one("hr.employee", related="session_id.clinic_doctor_id", store=True, readonly=True)
    treatment_id = fields.Many2one("clinic.treatment", related="session_id.treatment_id", store=True, readonly=True)
    sequence = fields.Integer(default=10)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    display_type = fields.Selection(
        [("line", "Normal Line"), ("section", "Section"), ("note", "Note")],
        default="line",
    )
    usage_type = fields.Selection(
        [
            ("service", "Service / Procedure Step"),
            ("consumable", "Consumable / Material"),
            ("medication", "Medication"),
            ("package", "Package Component"),
            ("note", "Note / Documentation"),
        ], default="service", required=True,
    )
    name = fields.Char()
    product_id = fields.Many2one("product.product", domain=[("sale_ok", "=", True)])
    product_type = fields.Selection(related="product_id.type", readonly=True)
    product_uom_id = fields.Many2one("uom.uom")
    quantity = fields.Float(default=1.0, digits="Product Unit of Measure")
    consumed_qty = fields.Float(default=0.0, digits="Product Unit of Measure")
    is_billable = fields.Boolean(default=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)
    price_unit = fields.Monetary(default=0.0)
    discount = fields.Float(default=0.0)
    tax_ids = fields.Many2many("account.tax", "clinic_treatment_session_line_tax_rel", "session_line_id", "tax_id")
    price_subtotal = fields.Monetary(compute="_compute_amounts", store=True)
    price_total = fields.Monetary(compute="_compute_amounts", store=True)
    consumption_state = fields.Selection(
        [("planned", "Planned"), ("ready", "Ready"), ("consumed", "Consumed")],
        default="planned", required=True, index=True,
    )
    date_consumed = fields.Datetime(copy=False)
    is_stock_relevant = fields.Boolean(compute="_compute_is_stock_relevant", store=True)
    stock_move_id = fields.Many2one("stock.move", copy=False, index=True)
    location_id = fields.Many2one("stock.location")
    location_dest_id = fields.Many2one("stock.location")
    note_internal = fields.Text()
    package_line_id = fields.Many2one("clinic.package.allocation.line")
    referral_id = fields.Many2one("clinic.referral")

    _quantity_nonnegative = models.Constraint("CHECK (quantity >= 0)", "Planned Quantity cannot be negative.")
    _consumed_nonnegative = models.Constraint("CHECK (consumed_qty >= 0)", "Consumed Quantity cannot be negative.")

    @api.depends("name", "product_id", "usage_type")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or (rec.product_id.display_name if rec.product_id else False) or dict(rec._fields["usage_type"].selection).get(rec.usage_type) or _("Treatment Session Line")

    @api.depends("product_id", "display_type")
    def _compute_is_stock_relevant(self):
        for rec in self:
            rec.is_stock_relevant = bool(rec.display_type == "line" and rec.product_id and rec.product_id.type in ("consu", "product"))

    @api.depends("quantity", "price_unit", "discount", "tax_ids", "display_type")
    def _compute_amounts(self):
        for rec in self:
            if rec.display_type != "line":
                rec.price_subtotal = rec.price_total = 0.0
                continue
            price = rec.price_unit * (1 - min(max(rec.discount, 0.0), 100.0) / 100.0)
            if rec.tax_ids:
                taxes = rec.tax_ids.compute_all(price, currency=rec.currency_id, quantity=rec.quantity, product=rec.product_id, partner=rec.patient_id)
                rec.price_subtotal = taxes["total_excluded"]; rec.price_total = taxes["total_included"]
            else:
                rec.price_subtotal = rec.price_total = price * rec.quantity

    @api.constrains("consumed_qty", "quantity")
    def _check_consumed_qty(self):
        for rec in self:
            if rec.consumed_qty > rec.quantity:
                raise ValidationError(_("Consumed Quantity cannot exceed Planned Quantity."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.display_name
                rec.product_uom_id = rec.product_id.uom_id
                rec.price_unit = rec.product_id.lst_price

    @api.onchange("usage_type", "display_type")
    def _onchange_usage_type_display_type(self):
        for rec in self:
            if rec.display_type != "line":
                rec.is_billable = False

    def _get_default_consumption_locations(self):
        self.ensure_one()
        source = self.location_id or self.env["stock.location"].search(
            [("usage", "=", "internal"), ("company_id", "in", [False, self.company_id.id])], limit=1
        )
        dest = self.location_dest_id or self.env["stock.location"].search(
            [("usage", "=", "inventory"), ("company_id", "in", [False, self.company_id.id])], limit=1
        )
        return source, dest

    def action_mark_ready(self):
        self.filtered(lambda r: r.display_type == "line").write({"consumption_state": "ready"})
        return True

    def action_mark_consumed(self):
        for rec in self.filtered(lambda r: r.display_type == "line"):
            rec.write({"consumption_state": "consumed", "consumed_qty": rec.quantity, "date_consumed": fields.Datetime.now()})
        return True

    def action_reset_consumption(self):
        for rec in self:
            if rec.stock_move_id and rec.stock_move_id.state == "done":
                raise UserError(_("A completed inventory movement cannot be hidden by resetting the session line."))
            rec.write({"consumption_state": "planned", "consumed_qty": 0.0, "date_consumed": False})
        return True

    def prepare_billing_payload_line(self):
        self.ensure_one()
        if self.display_type != "line" or not self.is_billable or not self.product_id:
            return {}
        return {
            "session_line_id": self.id, "product_id": self.product_id.id,
            "name": self.name or self.product_id.display_name,
            "qty": self.quantity, "price_unit": self.price_unit,
            "discount": self.discount, "tax_ids": self.tax_ids.ids,
        }
