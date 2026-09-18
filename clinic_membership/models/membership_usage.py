


# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipUsage(models.Model):
    """Auditable application of one membership entitlement."""

    _name = "membership.usage"
    _description = "Membership Benefit Usage"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Usage Reference",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._next_name(),
        tracking=True,
    )
    contract_id = fields.Many2one(
        "membership.contract",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
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
    partner_id = fields.Many2one(
        related="contract_id.partner_id", store=True, readonly=True, index=True
    )
    patient_id = fields.Many2one(
        related="contract_id.patient_id", store=True, readonly=True, index=True
    )

    date = fields.Datetime(
        string="Usage Datetime",
        default=fields.Datetime.now,
        required=True,
        index=True,
        tracking=True,
    )
    treatment_id = fields.Many2one("clinic.treatment", ondelete="restrict")
    doctor_id = fields.Many2one("clinic.doctor", ondelete="restrict")
    product_id = fields.Many2one(
        "product.product",
        domain="[('sale_ok', '=', True)]",
        ondelete="restrict",
    )
    product_category_id = fields.Many2one(
        related="product_id.categ_id", store=True, readonly=True
    )
    qty = fields.Float(default=1.0, digits=(16, 2), required=True)
    uom_id = fields.Many2one("uom.uom", ondelete="restrict")
    unit_price = fields.Monetary(currency_field="currency_id")
    amount_before = fields.Monetary(
        compute="_compute_amounts", store=True, currency_field="currency_id"
    )

    contract_benefit_id = fields.Many2one(
        "membership.contract.benefit",
        string="Applied Entitlement",
        ondelete="restrict",
        domain="[('contract_id', '=', contract_id), ('active', '=', True), ('is_depleted', '=', False)]",
        tracking=True,
    )
    benefit_id = fields.Many2one(
        related="contract_benefit_id.source_benefit_id",
        string="Source Plan Benefit",
        store=True,
        readonly=True,
    )
    benefit_type = fields.Selection(
        related="contract_benefit_id.benefit_type",
        store=True,
        readonly=True,
    )
    discount_mode = fields.Selection(
        [
            ("none", "None"),
            ("percent", "Percent"),
            ("per_line", "Per Line"),
            ("per_unit", "Per Unit"),
        ],
        default="none",
        readonly=True,
    )
    discount_percent = fields.Float(digits=(16, 4), readonly=True)
    discount_amount = fields.Monetary(
        currency_field="currency_id", readonly=True
    )
    amount_after = fields.Monetary(
        compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    quota_unit = fields.Selection(
        [
            ("session", "Session"),
            ("treatment", "Treatment"),
            ("unit", "Unit"),
            ("minute", "Minute"),
        ],
        readonly=True,
    )
    quota_consumed = fields.Float(digits=(16, 2), readonly=True)
    stack_group = fields.Char(readonly=True)
    stackable = fields.Boolean(readonly=True)
    priority_order = fields.Integer(readonly=True)

    # Typed ClinicOne traceability.
    booking_id = fields.Many2one("booking.booking", ondelete="set null", index=True)
    encounter_id = fields.Many2one("clinic.encounter", ondelete="set null", index=True)
    treatment_session_id = fields.Many2one(
        "clinic.treatment.session", ondelete="set null", index=True
    )
    care_plan_id = fields.Many2one("clinic.care.plan", ondelete="set null")
    care_plan_line_id = fields.Many2one("clinic.care.plan.line", ondelete="set null")
    package_allocation_id = fields.Many2one(
        "clinic.package.allocation", ondelete="set null"
    )
    package_usage_id = fields.Many2one("clinic.package.usage", ondelete="set null")
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration", ondelete="set null"
    )
    sale_order_id = fields.Many2one("sale.order", ondelete="set null")
    sale_line_id = fields.Many2one("sale.order.line", ondelete="set null")
    move_id = fields.Many2one(
        "account.move", string="Accounting Invoice", ondelete="set null"
    )
    move_line_id = fields.Many2one(
        "account.move.line", string="Accounting Line", ondelete="set null"
    )

    # Generic extension point for future Billing/AR/Wallet/Portal/etc.
    source_model = fields.Char(index=True)
    source_res_id = fields.Integer(index=True)
    source_reference = fields.Char(index=True)

    state = fields.Selection(
        [("draft", "Draft"), ("validated", "Validated"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    recorded_by = fields.Many2one(
        "res.users", default=lambda self: self.env.user, readonly=True
    )
    validated_by = fields.Many2one("res.users", readonly=True)
    validated_on = fields.Datetime(readonly=True)
    cancelled_by = fields.Many2one("res.users", readonly=True)
    cancelled_on = fields.Datetime(readonly=True)
    notes = fields.Text()

    _reference_company_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "Membership usage reference must be unique per company.",
    )
    _qty_positive = models.Constraint(
        "CHECK(qty > 0)",
        "Membership usage quantity must be greater than zero.",
    )
    _prices_non_negative = models.Constraint(
        "CHECK(unit_price >= 0 AND discount_amount >= 0 AND quota_consumed >= 0)",
        "Membership usage prices, discounts and quota consumption cannot be negative.",
    )

    @api.model
    def _next_name(self):
        return self.env["ir.sequence"].next_by_code("membership.usage") or "/"

    @api.depends("qty", "unit_price", "discount_amount")
    def _compute_amounts(self):
        for rec in self:
            rec.amount_before = max((rec.qty or 0.0) * (rec.unit_price or 0.0), 0.0)
            rec.amount_after = max(
                rec.amount_before - (rec.discount_amount or 0.0), 0.0
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.lst_price

    @api.onchange("contract_id")
    def _onchange_contract(self):
        if self.contract_id and self.contract_id.state != "active":
            return {
                "warning": {
                    "title": _("Membership Contract"),
                    "message": _("The selected membership contract is not Active."),
                }
            }
        return {}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("name", self._next_name())
        return super().create(vals_list)

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        protected = {
            "contract_id", "date", "treatment_id", "doctor_id", "product_id",
            "qty", "uom_id", "unit_price", "contract_benefit_id",
            "discount_mode", "discount_percent", "discount_amount",
            "quota_unit", "quota_consumed", "booking_id", "encounter_id",
            "treatment_session_id", "care_plan_id", "care_plan_line_id",
            "package_allocation_id", "package_usage_id", "emar_administration_id",
            "sale_order_id", "sale_line_id", "move_id", "move_line_id",
            "source_model", "source_res_id", "source_reference",
        }
        if protected.intersection(vals) and any(rec.state == "validated" for rec in self):
            raise UserError(
                _("Validated membership usage is immutable. Cancel it and create a corrected usage record.")
            )
        return super().write(vals)

    def unlink(self):
        if any(rec.state == "validated" for rec in self):
            raise UserError(_("Validated membership usage cannot be deleted."))
        return super().unlink()

    def _ensure_contract_eligibility(self):
        self.ensure_one()
        contract = self.contract_id
        when = fields.Datetime.to_datetime(self.date or fields.Datetime.now())
        usage_date = when.date()
        if contract.state != "active":
            raise UserError(_("Only an Active membership contract can be used."))
        if contract.start_date and usage_date < contract.start_date:
            raise UserError(_("Usage is before the membership start date."))
        if contract.end_date and usage_date > contract.end_date:
            raise UserError(_("Usage is after the membership end date."))
        if self.doctor_id and not contract.plan_id.ensure_doctor_eligibility(self.doctor_id):
            raise UserError(_("The selected doctor is not eligible for this membership plan."))
        if self.treatment_id and not contract.plan_id.ensure_treatment_eligibility(self.treatment_id):
            raise UserError(_("The selected treatment is not eligible for this membership plan."))
        if self.product_id and not contract.plan_id.ensure_product_eligibility(self.product_id):
            raise UserError(_("The selected product category is not eligible for this membership plan."))
        if self.booking_id:
            if self.booking_id.patient_id and self.booking_id.patient_id != contract.partner_id:
                raise UserError(_("The Booking patient does not match the membership member."))
            if self.booking_id.doctor_id and self.doctor_id and self.booking_id.doctor_id != self.doctor_id:
                raise UserError(_("The Booking doctor does not match this membership usage."))
            if self.booking_id.treatment_id and self.treatment_id and self.booking_id.treatment_id != self.treatment_id:
                raise UserError(_("The Booking treatment does not match this membership usage."))
        return True

    def _best_entitlement(self):
        self.ensure_one()
        entitlements = self.contract_id.get_applicable_entitlements(
            treatment=self.treatment_id,
            product=self.product_id,
            doctor=self.doctor_id,
            qty=self.qty,
            unit_price=self.unit_price,
            at_datetime=self.date,
        )
        return entitlements[:1]

    def _quota_consumption_for(self, entitlement):
        self.ensure_one()
        if entitlement.benefit_type != "quota":
            return 0.0
        if entitlement.quota_unit in ("session", "treatment"):
            return 1.0
        return self.qty or 0.0

    def _apply_entitlement(self, entitlement):
        self.ensure_one()
        if not entitlement:
            raise UserError(_("No applicable membership entitlement was found."))
        if entitlement.contract_id != self.contract_id:
            raise ValidationError(_("The entitlement belongs to another membership contract."))
        if not entitlement.is_scope_applicable(
            treatment=self.treatment_id,
            product=self.product_id,
            doctor=self.doctor_id,
            qty=self.qty,
            unit_price=self.unit_price,
            at_datetime=self.date,
        ):
            raise UserError(_("The selected entitlement does not apply to this usage context."))

        discount = entitlement.compute_discount(self.qty, self.unit_price)
        if entitlement.benefit_type == "discount_percent":
            discount_mode = "percent"
        elif entitlement.benefit_type == "discount_amount":
            discount_mode = entitlement.discount_mode
        else:
            discount_mode = "none"
        self.write(
            {
                "contract_benefit_id": entitlement.id,
                "discount_mode": discount_mode,
                "discount_percent": (
                    entitlement.discount_percent
                    if entitlement.benefit_type == "discount_percent"
                    else 0.0
                ),
                "discount_amount": discount,
                "quota_unit": entitlement.quota_unit,
                "quota_consumed": self._quota_consumption_for(entitlement),
                "stack_group": entitlement.exclusive_group,
                "stackable": entitlement.stackable,
                "priority_order": entitlement.priority_order,
            }
        )
        return True

    def action_apply_best_benefit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Benefits can only be applied to Draft usage records."))
            rec._ensure_contract_eligibility()
            rec._apply_entitlement(rec._best_entitlement())
        return True

    def action_clear_benefit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only Draft usage records can clear their entitlement."))
            rec.write(
                {
                    "contract_benefit_id": False,
                    "discount_mode": "none",
                    "discount_percent": 0.0,
                    "discount_amount": 0.0,
                    "quota_unit": False,
                    "quota_consumed": 0.0,
                    "stack_group": False,
                    "stackable": False,
                    "priority_order": 0,
                }
            )
        return True

    def _period_bounds(self, period):
        self.ensure_one()
        day = fields.Datetime.to_datetime(self.date).date()
        if period == "day":
            return day, day
        if period == "week":
            start = day - timedelta(days=day.weekday())
            return start, start + timedelta(days=6)
        if period == "month":
            start = day.replace(day=1)
            end = start + relativedelta(months=1, days=-1)
            return start, end
        return self.contract_id.start_date, self.contract_id.end_date

    def _period_consumed(self, period):
        self.ensure_one()
        if not self.contract_benefit_id:
            return 0.0
        start, end = self._period_bounds(period)
        domain = [
            ("id", "!=", self.id),
            ("contract_benefit_id", "=", self.contract_benefit_id.id),
            ("state", "=", "validated"),
        ]
        if start:
            domain.append(
                ("date", ">=", fields.Datetime.to_string(datetime.combine(start, time.min)))
            )
        if end:
            domain.append(
                ("date", "<=", fields.Datetime.to_string(datetime.combine(end, time.max)))
            )
        return sum(self.search(domain).mapped("quota_consumed"))

    def _visit_consumed(self):
        self.ensure_one()
        if not self.contract_benefit_id:
            return 0.0
        source_field = None
        source_id = None
        for name in ("encounter_id", "treatment_session_id", "booking_id", "care_plan_id"):
            value = self[name]
            if value:
                source_field = name
                source_id = value.id
                break
        if not source_field:
            return 0.0
        return sum(
            self.search(
                [
                    ("id", "!=", self.id),
                    ("contract_benefit_id", "=", self.contract_benefit_id.id),
                    ("state", "=", "validated"),
                    (source_field, "=", source_id),
                ]
            ).mapped("quota_consumed")
        )

    def _check_caps(self):
        self.ensure_one()
        entitlement = self.contract_benefit_id
        if not entitlement or entitlement.benefit_type != "quota":
            return True
        consumption = self.quota_consumed or 0.0
        checks = [
            ("Visit", entitlement.limit_per_visit, self._visit_consumed()),
            ("Day", entitlement.limit_per_day, self._period_consumed("day")),
            ("Week", entitlement.limit_per_week, self._period_consumed("week")),
            ("Month", entitlement.limit_per_month, self._period_consumed("month")),
            ("Term", entitlement.limit_per_term, self._period_consumed("term")),
        ]
        absolute_term_cap = entitlement.total_term_quota or entitlement.quota_value
        if absolute_term_cap:
            checks.append(
                (
                    "Entitlement",
                    absolute_term_cap,
                    entitlement.consumed_qty,
                )
            )
        for label, limit, consumed in checks:
            if limit and consumed + consumption > limit + 1e-9:
                raise UserError(
                    _("%s membership quota limit exceeded. Limit: %.2f, already consumed: %.2f, requested: %.2f")
                    % (label, limit, consumed, consumption)
                )
        return True

    @api.constrains("discount_amount", "amount_before")
    def _check_discount_not_above_base(self):
        for rec in self:
            if rec.discount_amount > rec.amount_before + 1e-9:
                raise ValidationError(_("Membership discount cannot exceed the source amount."))

    @api.constrains("source_model", "source_res_id")
    def _check_generic_source_pair(self):
        for rec in self:
            if bool(rec.source_model) != bool(rec.source_res_id):
                raise ValidationError(
                    _("Generic source model and source record ID must be provided together.")
                )

    def action_validate(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec._ensure_contract_eligibility()
            if not rec.contract_benefit_id:
                rec.action_apply_best_benefit()
            rec._check_caps()
            rec._membership_write_state(
                {
                    "state": "validated",
                    "validated_by": rec.env.user.id,
                    "validated_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "usage.validated",
                {
                    "usage_id": rec.id,
                    "contract_id": rec.contract_id.id,
                    "discount_amount": rec.discount_amount,
                    "quota_consumed": rec.quota_consumed,
                    "source_model": rec.source_model,
                    "source_res_id": rec.source_res_id,
                },
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "cancelled":
                continue
            rec._membership_write_state(
                {
                    "state": "cancelled",
                    "cancelled_by": rec.env.user.id,
                    "cancelled_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "usage.cancelled",
                {"usage_id": rec.id, "contract_id": rec.contract_id.id},
            )
        return True

    def action_view_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "res_id": self.contract_id.id,
        }


