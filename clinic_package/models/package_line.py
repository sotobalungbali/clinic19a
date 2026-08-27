
# -*- coding: utf-8 -*-
"""Atomic package components and snapshot preparation."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ClinicPackageLine(models.Model):
    _name = "clinic.package.line"
    _description = "Clinic Package Component"
    _order = "package_id, sequence, id"
    _check_company_auto = True

    package_id = fields.Many2one(
        "clinic.package", required=True, ondelete="cascade", index=True, check_company=True
    )
    company_id = fields.Many2one(
        "res.company", related="package_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="package_id.currency_id", store=True, readonly=True
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    line_type = fields.Selection(
        [
            ("treatment", "Treatment Sessions"),
            ("product", "Product Quantity"),
            ("credit", "Monetary Credit"),
            ("discount", "Discount Benefit"),
        ],
        required=True,
        default="treatment",
        index=True,
    )
    benefit_id = fields.Many2one("clinic.package.benefit", ondelete="set null", check_company=True)
    treatment_id = fields.Many2one("clinic.treatment", ondelete="restrict", check_company=True)
    treatment_categ_id = fields.Many2one("clinic.treatment.category", ondelete="restrict")
    product_id = fields.Many2one(
        "product.product",
        ondelete="restrict",
        check_company=True,
        domain="[('active', '=', True)]",
    )
    product_categ_id = fields.Many2one("product.category", ondelete="restrict")
    apply_to_all_treatments = fields.Boolean(default=False)
    apply_to_all_products = fields.Boolean(default=False)

    qty = fields.Float(default=1.0)
    uom_id = fields.Many2one("uom.uom", ondelete="restrict")
    consume_per_use = fields.Float(default=1.0)
    credit_amount = fields.Monetary(default=0.0)
    discount_type = fields.Selection(
        [("percent", "Percentage"), ("fixed", "Fixed Amount")],
        default="percent",
    )
    discount_value = fields.Float(default=0.0)
    discount_max_amount = fields.Monetary(default=0.0)

    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "clinic_package_line_doctor_rel",
        "line_id",
        "doctor_id",
        string="Allowed Doctors",
        check_company=True,
    )
    allowed_room_ids = fields.Many2many(
        "clinic.room",
        "clinic_package_line_room_rel",
        "line_id",
        "room_id",
        string="Allowed Rooms",
        check_company=True,
    )
    allowed_device_ids = fields.Many2many(
        "clinic.device",
        "clinic_package_line_device_rel",
        "line_id",
        "device_id",
        string="Allowed Devices",
        check_company=True,
    )
    limit_per_visit = fields.Float(default=0.0)
    limit_per_day = fields.Float(default=0.0)
    cooldown_days = fields.Integer(default=0)

    list_price = fields.Monetary(string="Reference Unit Value")
    cost_price = fields.Monetary(string="Reference Unit Cost")
    total_value = fields.Monetary(compute="_compute_totals", store=True)
    total_cost = fields.Monetary(compute="_compute_totals", store=True)

    usage_count = fields.Integer(compute="_compute_usage_stats")
    total_redeemed = fields.Float(compute="_compute_usage_stats")
    remaining_units = fields.Float(compute="_compute_usage_stats")
    is_depleted = fields.Boolean(compute="_compute_usage_stats")

    note = fields.Text()
    internal_note = fields.Text()

    _qty_nonnegative = models.Constraint(
        "CHECK(qty >= 0 AND consume_per_use >= 0 AND credit_amount >= 0 "
        "AND discount_value >= 0 AND discount_max_amount >= 0 AND limit_per_visit >= 0 "
        "AND limit_per_day >= 0 AND cooldown_days >= 0 AND list_price >= 0 AND cost_price >= 0)",
        "Package component quantities, limits, discounts, and prices must be zero or positive.",
    )

    @api.depends("line_type", "qty", "credit_amount", "list_price", "cost_price")
    def _compute_totals(self):
        for record in self:
            if record.line_type == "credit":
                record.total_value = record.credit_amount
                record.total_cost = 0.0
            elif record.line_type == "discount":
                record.total_value = 0.0
                record.total_cost = 0.0
            else:
                record.total_value = (record.qty or 0.0) * (record.list_price or 0.0)
                record.total_cost = (record.qty or 0.0) * (record.cost_price or 0.0)

    def _compute_usage_stats(self):
        Usage = self.env["clinic.package.usage"]
        for record in self:
            domain = [("package_line_id", "=", record.id), ("state", "=", "confirmed")]
            usages = Usage.search(domain)
            record.usage_count = len(usages)
            if record.line_type == "credit":
                redeemed = sum(usages.mapped("credit_used"))
                total = record.credit_amount
            else:
                redeemed = sum(usages.mapped("qty_used"))
                total = record.qty
            record.total_redeemed = redeemed
            record.remaining_units = max(total - redeemed, 0.0)
            record.is_depleted = bool(total) and float_compare(
                record.remaining_units, 0.0, precision_digits=4
            ) <= 0

    @api.constrains(
        "line_type",
        "treatment_id",
        "treatment_categ_id",
        "product_id",
        "product_categ_id",
        "apply_to_all_treatments",
        "apply_to_all_products",
        "qty",
        "credit_amount",
        "discount_type",
        "discount_value",
    )
    def _check_required_fields_by_type(self):
        for record in self:
            if record.line_type == "treatment":
                if not (record.treatment_id or record.treatment_categ_id or record.apply_to_all_treatments):
                    raise ValidationError(_("Treatment components need a treatment, category, or Apply to All Treatments."))
                if record.qty <= 0:
                    raise ValidationError(_("Treatment session quantity must be greater than zero."))
            elif record.line_type == "product":
                if not (record.product_id or record.product_categ_id or record.apply_to_all_products):
                    raise ValidationError(_("Product components need a product, category, or Apply to All Products."))
                if record.qty <= 0:
                    raise ValidationError(_("Product quantity must be greater than zero."))
            elif record.line_type == "credit" and record.credit_amount <= 0:
                raise ValidationError(_("Credit components need a credit amount greater than zero."))
            elif record.line_type == "discount":
                if record.discount_type == "percent" and not 0.0 < record.discount_value <= 100.0:
                    raise ValidationError(_("Percentage discount must be greater than 0 and at most 100."))
                if record.discount_type == "fixed" and record.discount_value <= 0:
                    raise ValidationError(_("Fixed discount amount must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            package = self.env["clinic.package"].browse(vals.get("package_id")) if vals.get("package_id") else False
            if package and package.state not in ("draft", "paused"):
                raise UserError(_("Package components can only be added while the package is Draft or Paused."))
        return super().create(vals_list)

    def write(self, vals):
        if any(line.package_id.state not in ("draft", "paused") for line in self):
            raise UserError(_("Package components can only be changed while the package is Draft or Paused."))
        return super().write(vals)

    def unlink(self):
        if any(line.package_id.state not in ("draft", "paused") for line in self):
            raise UserError(_("Package components can only be removed while the package is Draft or Paused."))
        return super().unlink()

    @api.onchange("benefit_id")
    def _onchange_benefit_id(self):
        for record in self:
            if record.benefit_id:
                record.update(record.benefit_id._prepare_package_line_vals())

    @api.onchange("treatment_id")
    def _onchange_treatment_id(self):
        for record in self:
            if record.treatment_id:
                record.name = record.treatment_id.display_name
                record.list_price = record.treatment_id.base_price or 0.0
                record.treatment_categ_id = record.treatment_id.category_id

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.name = record.product_id.display_name
                record.uom_id = record.product_id.uom_id
                record.list_price = record.product_id.lst_price
                record.product_categ_id = record.product_id.categ_id

    def _prepare_allocation_line_vals(self, allocation):
        self.ensure_one()
        return {
            "allocation_id": allocation.id,
            "package_line_id": self.id,
            "benefit_id": self.benefit_id.id,
            "sequence": self.sequence,
            "name": self.name,
            "line_type": self.line_type,
            "treatment_id": self.treatment_id.id,
            "treatment_categ_id": self.treatment_categ_id.id,
            "product_id": self.product_id.id,
            "product_categ_id": self.product_categ_id.id,
            "apply_to_all_treatments": self.apply_to_all_treatments,
            "apply_to_all_products": self.apply_to_all_products,
            "qty_total": self.qty * allocation.qty,
            "uom_id": self.uom_id.id,
            "consume_per_use": self.consume_per_use,
            "credit_amount_total": self.credit_amount * allocation.qty,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "discount_max_amount": self.discount_max_amount,
            "allowed_doctor_ids": [(6, 0, self.allowed_doctor_ids.ids)],
            "allowed_room_ids": [(6, 0, self.allowed_room_ids.ids)],
            "allowed_device_ids": [(6, 0, self.allowed_device_ids.ids)],
            "limit_per_visit": self.limit_per_visit,
            "limit_per_day": self.limit_per_day,
            "cooldown_days": self.cooldown_days,
            "list_price": self.list_price,
            "cost_price": self.cost_price,
            "note": self.note,
        }

    def action_view_usage(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("package_line_id", "=", self.id)],
            "context": {"default_package_id": self.package_id.id, "default_package_line_id": self.id},
        }

    def action_view_related_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocations"),
            "res_model": "clinic.package.allocation",
            "view_mode": "list,form",
            "domain": [("line_ids.package_line_id", "=", self.id)],
        }
