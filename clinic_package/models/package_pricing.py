
# -*- coding: utf-8 -*-
"""Reusable package pricing profiles and ordered pricing rules."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round


class ClinicPackagePricing(models.Model):
    _name = "clinic.package.pricing"
    _description = "Clinic Package Pricing Profile"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    rule_ids = fields.One2many(
        "clinic.package.pricing.rule", "pricing_id", string="Pricing Rules", copy=True
    )
    floor_price = fields.Monetary(
        help="Optional minimum final price after all pricing rules. Use 0 to disable the floor."
    )
    ceiling_price = fields.Monetary(
        help="Optional maximum final price after all pricing rules. Use 0 to disable the ceiling."
    )
    allow_stack = fields.Boolean(
        default=False,
        help="When enabled, multiple matching non-exclusive rules may be applied in priority order.",
    )
    note = fields.Text()

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "A package pricing profile with the same name already exists in this company.",
    )
    _price_bounds_check = models.Constraint(
        "CHECK(floor_price >= 0 AND ceiling_price >= 0)",
        "Pricing floor and ceiling must be zero or positive.",
    )

    @api.constrains("floor_price", "ceiling_price")
    def _check_price_range(self):
        for record in self:
            if record.ceiling_price and record.floor_price > record.ceiling_price:
                raise ValidationError(_("Pricing floor cannot be greater than pricing ceiling."))

    def compute_package_price(
        self,
        package,
        partner=False,
        quantity=1.0,
        pricing_date=False,
        channel=False,
    ):
        """Return a transparent pricing result for one package.

        This method is deliberately independent from membership/promotion addons. Future
        addons can extend it or consume the integration-event payload without creating
        a reverse dependency from clinic_package.
        """
        self.ensure_one()
        package.ensure_one()
        pricing_date = fields.Date.to_date(pricing_date or fields.Date.context_today(self))
        quantity = max(float(quantity or 0.0), 0.0)
        base_unit = package.list_price or 0.0
        base_total = base_unit * quantity
        amount = base_total
        applied = []

        matching_rules = self.rule_ids.filtered(
            lambda rule: rule.active and rule._matches(package, partner, quantity, pricing_date, channel)
        ).sorted(key=lambda rule: (rule.priority, rule.id))

        for rule in matching_rules:
            previous = amount
            amount = rule._apply_amount(amount, quantity)
            if rule.max_discount_amount:
                discount = min(max(previous - amount, 0.0), rule.max_discount_amount)
                amount = previous - discount
            amount = max(amount, 0.0)
            applied.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "amount_before": previous,
                    "amount_after": amount,
                }
            )
            if rule.exclusive or rule.stop_further or not self.allow_stack:
                break

        if self.floor_price:
            amount = max(amount, self.floor_price * quantity)
        if self.ceiling_price:
            amount = min(amount, self.ceiling_price * quantity)

        amount = float_round(amount, precision_rounding=self.currency_id.rounding)
        discount_amount = max(base_total - amount, 0.0)
        discount_pct = (discount_amount / base_total * 100.0) if base_total else 0.0
        return {
            "base_unit_price": base_unit,
            "base_total": base_total,
            "final_total": amount,
            "discount_amount": discount_amount,
            "discount_pct": discount_pct,
            "applied_rules": applied,
        }


class ClinicPackagePricingRule(models.Model):
    _name = "clinic.package.pricing.rule"
    _description = "Clinic Package Pricing Rule"
    _order = "priority, id"

    pricing_id = fields.Many2one(
        "clinic.package.pricing", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", related="pricing_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="pricing_id.currency_id", store=True, readonly=True
    )
    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    priority = fields.Integer(default=10)
    rule_type = fields.Selection(
        [
            ("percent", "Percentage Discount"),
            ("fixed_discount", "Fixed Discount"),
            ("set_total", "Set Package Total"),
        ],
        required=True,
        default="percent",
    )
    percent_value = fields.Float(string="Discount %", default=0.0)
    fixed_amount = fields.Monetary(string="Fixed Discount")
    set_total_amount = fields.Monetary(string="Set Total")
    max_discount_amount = fields.Monetary(string="Maximum Discount")
    stop_further = fields.Boolean(default=False)
    exclusive = fields.Boolean(
        default=False,
        help="An exclusive rule terminates evaluation after it is applied.",
    )

    date_start = fields.Date()
    date_end = fields.Date()
    channel = fields.Selection(
        [
            ("any", "Any Channel"),
            ("frontdesk", "Front Desk"),
            ("online", "Online"),
            ("campaign", "Campaign"),
            ("voucher", "Voucher"),
        ],
        default="any",
        required=True,
    )
    min_qty = fields.Float(default=0.0)
    max_qty = fields.Float(default=0.0)
    partner_ids = fields.Many2many(
        "res.partner",
        "clinic_package_pricing_rule_partner_rel",
        "rule_id",
        "partner_id",
        string="Specific Customers",
    )
    partner_category_ids = fields.Many2many(
        "res.partner.category",
        "clinic_package_pricing_rule_partner_category_rel",
        "rule_id",
        "category_id",
        string="Customer Tags",
    )
    package_id = fields.Many2one("clinic.package", ondelete="cascade", index=True)
    package_tag_ids = fields.Many2many(
        "clinic.package.tag",
        "clinic_package_pricing_rule_package_tag_rel",
        "rule_id",
        "tag_id",
        string="Package Tags",
    )
    package_code_prefix = fields.Char()
    note = fields.Text()

    _amounts_nonnegative = models.Constraint(
        "CHECK(fixed_amount >= 0 AND set_total_amount >= 0 AND max_discount_amount >= 0)",
        "Pricing rule amounts must be zero or positive.",
    )

    @api.constrains(
        "rule_type",
        "percent_value",
        "fixed_amount",
        "set_total_amount",
        "date_start",
        "date_end",
        "min_qty",
        "max_qty",
    )
    def _check_values(self):
        for record in self:
            if record.rule_type == "percent" and not 0.0 <= record.percent_value <= 100.0:
                raise ValidationError(_("Percentage discount must be between 0 and 100."))
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_("Pricing rule End Date cannot be before Start Date."))
            if record.min_qty < 0 or record.max_qty < 0:
                raise ValidationError(_("Pricing quantity thresholds cannot be negative."))
            if record.max_qty and record.max_qty < record.min_qty:
                raise ValidationError(_("Maximum quantity cannot be lower than minimum quantity."))

    def _matches(self, package, partner, quantity, pricing_date, channel):
        self.ensure_one()
        if self.date_start and pricing_date < self.date_start:
            return False
        if self.date_end and pricing_date > self.date_end:
            return False
        if self.channel != "any" and channel and self.channel != channel:
            return False
        if self.min_qty and quantity < self.min_qty:
            return False
        if self.max_qty and quantity > self.max_qty:
            return False
        if self.package_id and self.package_id != package:
            return False
        if self.package_tag_ids and not (self.package_tag_ids & package.tag_ids):
            return False
        if self.package_code_prefix and not (package.code or "").startswith(self.package_code_prefix):
            return False
        if self.partner_ids and (not partner or partner not in self.partner_ids):
            return False
        if self.partner_category_ids and partner and not (self.partner_category_ids & partner.category_id):
            return False
        return True

    def _apply_amount(self, current_amount, quantity):
        self.ensure_one()
        if self.rule_type == "percent":
            return current_amount * (1.0 - (self.percent_value / 100.0))
        if self.rule_type == "fixed_discount":
            return current_amount - self.fixed_amount
        if self.rule_type == "set_total":
            return self.set_total_amount * max(quantity, 1.0)
        return current_amount
