
# -*- coding: utf-8 -*-
"""Reusable component templates for consistent package authoring."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicPackageBenefit(models.Model):
    _name = "clinic.package.benefit"
    _description = "Clinic Package Benefit Template"
    _order = "sequence, name, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(default=0)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    line_type = fields.Selection(
        [
            ("treatment", "Treatment Sessions"),
            ("product", "Product Quantity"),
            ("credit", "Monetary Credit"),
            ("discount", "Discount Benefit"),
        ],
        default="treatment",
        required=True,
    )
    treatment_id = fields.Many2one("clinic.treatment", check_company=True)
    treatment_categ_id = fields.Many2one("clinic.treatment.category")
    product_id = fields.Many2one("product.product", check_company=True)
    product_categ_id = fields.Many2one("product.category")
    apply_to_all_treatments = fields.Boolean(default=False)
    apply_to_all_products = fields.Boolean(default=False)
    qty_default = fields.Float(default=1.0)
    uom_id = fields.Many2one("uom.uom")
    consume_per_use_default = fields.Float(default=1.0)
    credit_amount_default = fields.Monetary(default=0.0)
    discount_type_default = fields.Selection(
        [("percent", "Percentage"), ("fixed", "Fixed Amount")], default="percent"
    )
    discount_value_default = fields.Float(default=0.0)
    discount_max_amount_default = fields.Monetary(default=0.0)
    allowed_doctor_ids_default = fields.Many2many(
        "clinic.doctor",
        "clinic_package_benefit_doctor_rel",
        "benefit_id",
        "doctor_id",
        check_company=True,
    )
    allowed_room_ids_default = fields.Many2many(
        "clinic.room",
        "clinic_package_benefit_room_rel",
        "benefit_id",
        "room_id",
        check_company=True,
    )
    allowed_device_ids_default = fields.Many2many(
        "clinic.device",
        "clinic_package_benefit_device_rel",
        "benefit_id",
        "device_id",
        check_company=True,
    )
    limit_per_visit_default = fields.Float(default=0.0)
    limit_per_day_default = fields.Float(default=0.0)
    cooldown_days_default = fields.Integer(default=0)
    list_price_default = fields.Monetary(default=0.0)
    cost_price_default = fields.Monetary(default=0.0)
    note = fields.Text()
    internal_note = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Benefit template code must be unique per company.",
    )

    @api.constrains("qty_default", "credit_amount_default", "discount_value_default")
    def _check_values(self):
        for record in self:
            if record.qty_default < 0 or record.credit_amount_default < 0 or record.discount_value_default < 0:
                raise ValidationError(_("Benefit template quantities and values cannot be negative."))

    def _prepare_package_line_vals(self):
        self.ensure_one()
        return {
            "name": self.name,
            "line_type": self.line_type,
            "treatment_id": self.treatment_id.id,
            "treatment_categ_id": self.treatment_categ_id.id,
            "product_id": self.product_id.id,
            "product_categ_id": self.product_categ_id.id,
            "apply_to_all_treatments": self.apply_to_all_treatments,
            "apply_to_all_products": self.apply_to_all_products,
            "qty": self.qty_default,
            "uom_id": self.uom_id.id,
            "consume_per_use": self.consume_per_use_default,
            "credit_amount": self.credit_amount_default,
            "discount_type": self.discount_type_default,
            "discount_value": self.discount_value_default,
            "discount_max_amount": self.discount_max_amount_default,
            "allowed_doctor_ids": [(6, 0, self.allowed_doctor_ids_default.ids)],
            "allowed_room_ids": [(6, 0, self.allowed_room_ids_default.ids)],
            "allowed_device_ids": [(6, 0, self.allowed_device_ids_default.ids)],
            "limit_per_visit": self.limit_per_visit_default,
            "limit_per_day": self.limit_per_day_default,
            "cooldown_days": self.cooldown_days_default,
            "list_price": self.list_price_default,
            "cost_price": self.cost_price_default,
            "note": self.note,
        }

    def action_create_package_line(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Package Component"),
            "res_model": "clinic.package.line",
            "view_mode": "form",
            "target": "current",
            "context": {"default_benefit_id": self.id, **{f"default_{k}": v for k, v in self._prepare_package_line_vals().items() if not isinstance(v, list)}},
        }
