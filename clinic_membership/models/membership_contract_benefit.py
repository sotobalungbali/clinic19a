

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipContractBenefit(models.Model):
    """Immutable entitlement snapshot owned by a Membership Contract."""

    _name = "membership.contract.benefit"
    _description = "Membership Contract Benefit Entitlement"
    _inherit = ["mail.thread"]
    _order = "contract_id, sequence, priority_order desc, id"

    contract_id = fields.Many2one(
        "membership.contract",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source_benefit_id = fields.Many2one(
        "membership.plan.benefit",
        string="Source Plan Benefit",
        ondelete="set null",
        readonly=True,
    )
    plan_id = fields.Many2one(
        related="contract_id.plan_id", store=True, readonly=True, index=True
    )
    company_id = fields.Many2one(
        related="contract_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        related="contract_id.currency_id", store=True, readonly=True
    )

    name = fields.Char(required=True, readonly=True)
    sequence = fields.Integer(default=10, readonly=True)
    active = fields.Boolean(default=True, readonly=True)
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
        readonly=True,
        index=True,
    )
    discount_percent = fields.Float(readonly=True, digits=(16, 4))
    discount_amount = fields.Monetary(
        readonly=True, currency_field="currency_id"
    )
    discount_mode = fields.Selection(
        [("per_line", "Per Line"), ("per_unit", "Per Unit")], readonly=True
    )
    price_floor = fields.Monetary(readonly=True, currency_field="currency_id")
    price_ceiling = fields.Monetary(readonly=True, currency_field="currency_id")

    quota_unit = fields.Selection(
        [
            ("session", "Session"),
            ("treatment", "Treatment"),
            ("unit", "Unit"),
            ("minute", "Minute"),
        ],
        readonly=True,
    )
    quota_value = fields.Float(readonly=True, digits=(16, 2))
    total_term_quota = fields.Float(readonly=True, digits=(16, 2))
    rollover_eligible = fields.Boolean(readonly=True)
    free_qty = fields.Float(readonly=True, digits=(16, 2))
    free_item_mode = fields.Selection(
        [("same", "Same Item"), ("specific_product", "Specific Product")],
        readonly=True,
    )
    free_product_id = fields.Many2one(
        "product.product", readonly=True, ondelete="restrict"
    )
    priority_order = fields.Integer(readonly=True)
    booking_priority_delta = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("vip", "VIP"),
        ],
        readonly=True,
    )

    voucher_on_join_qty = fields.Integer(readonly=True)
    voucher_on_join_type = fields.Selection(
        [("amount", "Amount"), ("percent", "Percent"), ("free_item", "Free Item")],
        readonly=True,
    )
    voucher_value = fields.Float(readonly=True, digits=(16, 2))
    voucher_expiry_days = fields.Integer(readonly=True)

    treatment_id = fields.Many2one("clinic.treatment", readonly=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", readonly=True, ondelete="restrict")
    product_category_id = fields.Many2one(
        "product.category", readonly=True, ondelete="restrict"
    )
    doctor_id = fields.Many2one("clinic.doctor", readonly=True, ondelete="restrict")
    valid_from = fields.Datetime(readonly=True)
    valid_to = fields.Datetime(readonly=True)
    days_of_week = fields.Char(readonly=True)
    time_from = fields.Float(readonly=True)
    time_to = fields.Float(readonly=True)
    min_price = fields.Monetary(readonly=True, currency_field="currency_id")
    max_price = fields.Monetary(readonly=True, currency_field="currency_id")
    min_qty = fields.Float(readonly=True, digits=(16, 2))
    max_qty = fields.Float(readonly=True, digits=(16, 2))
    limit_per_visit = fields.Float(readonly=True, digits=(16, 2))
    limit_per_day = fields.Float(readonly=True, digits=(16, 2))
    limit_per_week = fields.Float(readonly=True, digits=(16, 2))
    limit_per_month = fields.Float(readonly=True, digits=(16, 2))
    limit_per_term = fields.Float(readonly=True, digits=(16, 2))
    stackable = fields.Boolean(readonly=True)
    exclusive_group = fields.Char(readonly=True)

    usage_ids = fields.One2many(
        "membership.usage",
        "contract_benefit_id",
        string="Validated / Cancelled Usage History",
        readonly=True,
    )
    usage_count = fields.Integer(compute="_compute_consumption", store=True)
    consumed_qty = fields.Float(
        compute="_compute_consumption", store=True, digits=(16, 2)
    )
    consumed_discount = fields.Monetary(
        compute="_compute_consumption",
        store=True,
        currency_field="currency_id",
    )
    remaining_quota = fields.Float(
        compute="_compute_consumption", store=True, digits=(16, 2)
    )
    is_depleted = fields.Boolean(
        compute="_compute_consumption", store=True, index=True
    )

    _contract_source_uniq = models.Constraint(
        "UNIQUE(contract_id, source_benefit_id)",
        "A plan benefit can only be snapshotted once per membership contract.",
    )

    @api.depends(
        "benefit_type",
        "quota_value",
        "total_term_quota",
        "usage_ids.state",
        "usage_ids.quota_consumed",
        "usage_ids.discount_amount",
    )
    def _compute_consumption(self):
        for rec in self:
            valid = rec.usage_ids.filtered(lambda usage: usage.state == "validated")
            rec.usage_count = len(valid)
            rec.consumed_qty = sum(valid.mapped("quota_consumed"))
            rec.consumed_discount = sum(valid.mapped("discount_amount"))
            cap = rec.total_term_quota or rec.quota_value or 0.0
            rec.remaining_quota = max(cap - rec.consumed_qty, 0.0) if cap else 0.0
            rec.is_depleted = bool(
                rec.benefit_type == "quota" and cap and rec.remaining_quota <= 1e-9
            )

    @api.model
    def _snapshot_field_names(self):
        return [
            "name", "sequence", "active", "benefit_type",
            "discount_percent", "discount_amount", "discount_mode",
            "price_floor", "price_ceiling", "quota_unit", "quota_value",
            "total_term_quota", "rollover_eligible", "free_qty",
            "free_item_mode", "free_product_id", "priority_order",
            "booking_priority_delta", "voucher_on_join_qty",
            "voucher_on_join_type", "voucher_value", "voucher_expiry_days",
            "treatment_id", "product_id", "product_category_id", "doctor_id",
            "valid_from", "valid_to", "days_of_week", "time_from", "time_to",
            "min_price", "max_price", "min_qty", "max_qty",
            "limit_per_visit", "limit_per_day", "limit_per_week",
            "limit_per_month", "limit_per_term", "stackable", "exclusive_group",
        ]

    @api.model
    def snapshot_values_from_plan_benefit(self, benefit, contract):
        values = {
            "contract_id": contract.id,
            "source_benefit_id": benefit.id,
        }
        for field_name in self._snapshot_field_names():
            field = benefit._fields[field_name]
            value = benefit[field_name]
            if field.type in ("many2one",):
                value = value.id
            values[field_name] = value
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("clinic_membership_snapshot_build"):
            raise UserError(
                _("Contract benefits can only be created by the contract activation snapshot workflow.")
            )
        return super().create(vals_list)

    def write(self, vals):
        immutable = set(self._snapshot_field_names()) | {
            "contract_id", "source_benefit_id"
        }
        if immutable.intersection(vals):
            raise UserError(
                _("Membership entitlement snapshots are immutable after creation.")
            )
        return super().write(vals)

    def unlink(self):
        if any(rec.contract_id.state not in ("draft", "awaiting_payment") for rec in self):
            raise UserError(
                _("Membership entitlement snapshots cannot be removed after activation.")
            )
        return super().unlink()

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
        if treatment and not self.contract_id.plan_id.ensure_treatment_eligibility(treatment):
            return False
        if doctor and not self.contract_id.plan_id.ensure_doctor_eligibility(doctor):
            return False
        if product and not self.contract_id.plan_id.ensure_product_eligibility(product):
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

        when = fields.Datetime.to_datetime(at_datetime or fields.Datetime.now())
        if self.valid_from and when < fields.Datetime.to_datetime(self.valid_from):
            return False
        if self.valid_to and when > fields.Datetime.to_datetime(self.valid_to):
            return False
        weekdays = {
            token.strip().lower()
            for token in (self.days_of_week or "").split(",")
            if token.strip()
        }
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
        if self.is_depleted:
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
            amount = min(amount, max(base - self.price_floor * qty, 0.0))
        return amount

    def action_view_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Usages"),
            "res_model": "membership.usage",
            "view_mode": "list,form",
            "domain": [("contract_benefit_id", "=", self.id)],
            "context": {
                "default_contract_id": self.contract_id.id,
                "default_contract_benefit_id": self.id,
            },
        }

