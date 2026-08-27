

# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipPlanBenefit(models.Model):
    """Reusable rule attached to a Membership Plan.

    This is master policy. Operational contracts never consume this row directly;
    activation copies it to ``membership.contract.benefit`` so history remains
    stable even when a future plan version changes.
    """

    _name = "membership.plan.benefit"
    _description = "Membership Plan Benefit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "plan_id, sequence, priority_order desc, id"

    plan_id = fields.Many2one(
        "membership.plan",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        related="plan_id.currency_id", store=True, readonly=True
    )

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    benefit_type = fields.Selection(
        [
            ("discount_percent", "Percentage Discount"),
            ("discount_amount", "Fixed Discount"),
            ("quota", "Quota / Allowance"),
            ("free_item", "Free Item"),
            ("priority", "Booking Priority"),
            ("voucher_on_join", "Voucher on Join"),
        ],
        required=True,
        default="discount_percent",
        tracking=True,
        index=True,
    )

    discount_percent = fields.Float(string="Discount (%)", digits=(16, 4))
    discount_amount = fields.Monetary(currency_field="currency_id")
    discount_mode = fields.Selection(
        [("per_line", "Per Line"), ("per_unit", "Per Unit")],
        default="per_line",
    )
    price_floor = fields.Monetary(currency_field="currency_id")
    price_ceiling = fields.Monetary(currency_field="currency_id")

    quota_unit = fields.Selection(
        [
            ("session", "Session"),
            ("treatment", "Treatment"),
            ("unit", "Unit"),
            ("minute", "Minute"),
        ],
        default="session",
    )
    quota_value = fields.Float(digits=(16, 2))
    total_term_quota = fields.Float(digits=(16, 2))
    rollover_eligible = fields.Boolean(default=False)

    free_qty = fields.Float(digits=(16, 2))
    free_item_mode = fields.Selection(
        [("same", "Same Item"), ("specific_product", "Specific Product")],
        default="same",
    )
    free_product_id = fields.Many2one(
        "product.product",
        domain="[('sale_ok', '=', True)]",
        ondelete="restrict",
    )

    priority_order = fields.Integer(default=0)
    booking_priority_delta = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("vip", "VIP"),
        ],
        default="none",
    )

    voucher_on_join_qty = fields.Integer(default=0)
    voucher_on_join_type = fields.Selection(
        [("amount", "Amount"), ("percent", "Percent"), ("free_item", "Free Item")],
        default="amount",
    )
    voucher_value = fields.Float(digits=(16, 2))
    voucher_expiry_days = fields.Integer(default=90)

    treatment_id = fields.Many2one("clinic.treatment", ondelete="restrict")
    product_id = fields.Many2one(
        "product.product",
        domain="[('sale_ok', '=', True)]",
        ondelete="restrict",
    )
    product_category_id = fields.Many2one("product.category", ondelete="restrict")
    doctor_id = fields.Many2one("clinic.doctor", ondelete="restrict")

    valid_from = fields.Datetime()
    valid_to = fields.Datetime()
    days_of_week = fields.Char(
        help="Comma-separated ISO weekday keys: mon,tue,wed,thu,fri,sat,sun."
    )
    time_from = fields.Float(help="Decimal hour, for example 9.5 = 09:30.")
    time_to = fields.Float(help="Decimal hour, for example 18.0 = 18:00.")

    min_price = fields.Monetary(currency_field="currency_id")
    max_price = fields.Monetary(currency_field="currency_id")
    min_qty = fields.Float(digits=(16, 2))
    max_qty = fields.Float(digits=(16, 2))

    limit_per_visit = fields.Float(digits=(16, 2))
    limit_per_day = fields.Float(digits=(16, 2))
    limit_per_week = fields.Float(digits=(16, 2))
    limit_per_month = fields.Float(digits=(16, 2))
    limit_per_term = fields.Float(digits=(16, 2))
    stackable = fields.Boolean(default=False)
    exclusive_group = fields.Char(index=True)

    summary = fields.Text(compute="_compute_summary")

    _discount_percent_range = models.Constraint(
        "CHECK(discount_percent >= 0 AND discount_percent <= 100)",
        "Percentage discount must be between 0 and 100.",
    )
    _non_negative_values = models.Constraint(
        """CHECK(
            discount_amount >= 0
            AND quota_value >= 0
            AND total_term_quota >= 0
            AND free_qty >= 0
            AND voucher_on_join_qty >= 0
            AND voucher_value >= 0
            AND voucher_expiry_days >= 0
            AND min_price >= 0
            AND max_price >= 0
            AND min_qty >= 0
            AND max_qty >= 0
            AND limit_per_visit >= 0
            AND limit_per_day >= 0
            AND limit_per_week >= 0
            AND limit_per_month >= 0
            AND limit_per_term >= 0
        )""",
        "Membership benefit quantities, values and limits cannot be negative.",
    )

    @api.depends(
        "benefit_type",
        "discount_percent",
        "discount_amount",
        "discount_mode",
        "quota_unit",
        "quota_value",
        "free_qty",
        "free_item_mode",
        "free_product_id",
        "booking_priority_delta",
        "voucher_on_join_qty",
        "voucher_on_join_type",
        "voucher_value",
        "treatment_id",
        "product_id",
        "product_category_id",
        "doctor_id",
        "valid_from",
        "valid_to",
        "exclusive_group",
    )
    def _compute_summary(self):
        for rec in self:
            parts = []
            if rec.benefit_type == "discount_percent":
                parts.append(_("%.2f%% discount") % (rec.discount_percent or 0.0))
            elif rec.benefit_type == "discount_amount":
                parts.append(
                    _("%s fixed discount")
                    % f"{(rec.discount_amount or 0.0):,.2f} {rec.currency_id.name or ''}"
                )
            elif rec.benefit_type == "quota":
                parts.append(
                    _("Quota %.2f %s")
                    % (rec.quota_value or 0.0, rec.quota_unit or "")
                )
            elif rec.benefit_type == "free_item":
                target = (
                    rec.free_product_id.display_name
                    if rec.free_item_mode == "specific_product" and rec.free_product_id
                    else _("same item")
                )
                parts.append(_("Free %.2f × %s") % (rec.free_qty or 0.0, target))
            elif rec.benefit_type == "priority":
                parts.append(
                    _("Booking priority: %s")
                    % dict(rec._fields["booking_priority_delta"].selection).get(
                        rec.booking_priority_delta, rec.booking_priority_delta
                    )
                )
            elif rec.benefit_type == "voucher_on_join":
                parts.append(
                    _("%s voucher(s) on join")
                    % (rec.voucher_on_join_qty or 0)
                )
            scopes = []
            if rec.treatment_id:
                scopes.append(rec.treatment_id.display_name)
            if rec.product_id:
                scopes.append(rec.product_id.display_name)
            if rec.product_category_id:
                scopes.append(rec.product_category_id.display_name)
            if rec.doctor_id:
                scopes.append(rec.doctor_id.display_name)
            if scopes:
                parts.append(_("Scope: %s") % ", ".join(scopes))
            if rec.exclusive_group:
                parts.append(_("Exclusive: %s") % rec.exclusive_group)
            rec.summary = " · ".join(parts)

    @api.constrains("valid_from", "valid_to")
    def _check_validity_window(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_to < rec.valid_from:
                raise ValidationError(_("Valid To cannot be earlier than Valid From."))

    @api.constrains("time_from", "time_to")
    def _check_time_window(self):
        for rec in self:
            for value in (rec.time_from, rec.time_to):
                if value and not 0.0 <= value <= 24.0:
                    raise ValidationError(_("Time limits must be between 0 and 24."))
            if rec.time_from and rec.time_to and rec.time_to < rec.time_from:
                raise ValidationError(_("Time To cannot be earlier than Time From."))

    @api.constrains("min_price", "max_price", "min_qty", "max_qty")
    def _check_min_max(self):
        for rec in self:
            if rec.max_price and rec.min_price and rec.max_price < rec.min_price:
                raise ValidationError(_("Maximum price cannot be lower than minimum price."))
            if rec.max_qty and rec.min_qty and rec.max_qty < rec.min_qty:
                raise ValidationError(_("Maximum quantity cannot be lower than minimum quantity."))

    @api.constrains(
        "benefit_type",
        "discount_percent",
        "discount_amount",
        "quota_value",
        "free_qty",
        "voucher_on_join_qty",
        "voucher_value",
        "free_item_mode",
        "free_product_id",
    )
    def _check_type_values(self):
        for rec in self:
            if rec.benefit_type == "discount_percent" and rec.discount_percent <= 0:
                raise ValidationError(_("Percentage benefits require Discount (%) greater than zero."))
            if rec.benefit_type == "discount_amount" and rec.discount_amount <= 0:
                raise ValidationError(_("Fixed discount benefits require a positive amount."))
            if rec.benefit_type == "quota" and rec.quota_value <= 0:
                raise ValidationError(_("Quota benefits require a positive quota value."))
            if rec.benefit_type == "free_item" and rec.free_qty <= 0:
                raise ValidationError(_("Free-item benefits require Free Quantity greater than zero."))
            if (
                rec.benefit_type == "free_item"
                and rec.free_item_mode == "specific_product"
                and not rec.free_product_id
            ):
                raise ValidationError(_("Select a Free Product for Specific Product mode."))
            if rec.benefit_type == "voucher_on_join":
                if rec.voucher_on_join_qty <= 0:
                    raise ValidationError(_("Voucher-on-join benefits require at least one voucher."))
                if rec.voucher_on_join_type != "free_item" and rec.voucher_value <= 0:
                    raise ValidationError(_("Voucher value must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.plan_id.state == "active":
                raise UserError(
                    _("Benefits cannot be added to an active plan. Duplicate or reset the plan first.")
                )
        return records

    def write(self, vals):
        if any(rec.plan_id.state == "active" for rec in self):
            raise UserError(
                _("Benefits on an active plan are policy-frozen. Duplicate or reset the plan first.")
            )
        return super().write(vals)

    def unlink(self):
        if any(rec.plan_id.state == "active" for rec in self):
            raise UserError(_("Benefits on an active plan cannot be deleted."))
        return super().unlink()

    def _normalized_weekdays(self):
        self.ensure_one()
        return {
            token.strip().lower()
            for token in (self.days_of_week or "").split(",")
            if token.strip()
        }

    def is_scope_applicable(
        self,
        *,
        treatment=None,
        product=None,
        doctor=None,
        qty=1.0,
        unit_price=0.0,
        at_datetime=None,
    ):
        self.ensure_one()
        if not self.active:
            return False
        if treatment and not self.plan_id.ensure_treatment_eligibility(treatment):
            return False
        if doctor and not self.plan_id.ensure_doctor_eligibility(doctor):
            return False
        if product and not self.plan_id.ensure_product_eligibility(product):
            return False
        if self.treatment_id and treatment != self.treatment_id:
            return False
        if self.product_id and product != self.product_id:
            return False
        if self.product_category_id and (
            not product or product.categ_id != self.product_category_id
        ):
            return False
        if self.doctor_id and doctor != self.doctor_id:
            return False

        when = at_datetime or fields.Datetime.now()
        when = fields.Datetime.to_datetime(when)
        if self.valid_from and when < fields.Datetime.to_datetime(self.valid_from):
            return False
        if self.valid_to and when > fields.Datetime.to_datetime(self.valid_to):
            return False

        weekdays = self._normalized_weekdays()
        weekday_key = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[when.weekday()]
        if weekdays and weekday_key not in weekdays:
            return False

        hour = when.hour + when.minute / 60.0
        if self.time_from and hour < self.time_from:
            return False
        if self.time_to and hour > self.time_to:
            return False

        qty = float(qty or 0.0)
        unit_price = float(unit_price or 0.0)
        if self.min_qty and qty < self.min_qty:
            return False
        if self.max_qty and qty > self.max_qty:
            return False
        if self.min_price and unit_price < self.min_price:
            return False
        if self.max_price and unit_price > self.max_price:
            return False
        if self.price_ceiling and unit_price > self.price_ceiling:
            return False
        return True

    def compute_discount(self, qty=1.0, unit_price=0.0):
        self.ensure_one()
        qty = max(float(qty or 0.0), 0.0)
        unit_price = max(float(unit_price or 0.0), 0.0)
        base = qty * unit_price
        if self.benefit_type == "discount_percent":
            amount = base * (self.discount_percent or 0.0) / 100.0
        elif self.benefit_type == "discount_amount":
            amount = (
                (self.discount_amount or 0.0) * qty
                if self.discount_mode == "per_unit"
                else (self.discount_amount or 0.0)
            )
        else:
            amount = 0.0
        amount = min(max(amount, 0.0), base)
        if self.price_floor and qty:
            amount = min(amount, max(base - (self.price_floor * qty), 0.0))
        return amount

    def action_open_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Plan"),
            "res_model": "membership.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
        }

