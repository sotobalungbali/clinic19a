


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipPlan(models.Model):
    """Published membership commercial policy.

    A plan is mutable while Draft. Activation freezes the policy for operational
    use. Every contract snapshots commercial values and every benefit into
    ``membership.contract.benefit`` at activation, so future plan revisions can
    never rewrite historical member entitlements.
    """

    _name = "membership.plan"
    _description = "Membership Plan"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "sequence, tier, name, id"

    name = fields.Char(required=True, index=True, tracking=True)
    code = fields.Char(
        string="Internal Code",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._next_code(),
        tracking=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("retired", "Retired"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    tier = fields.Selection(
        [
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
            ("diamond", "Diamond"),
        ],
        default="silver",
        required=True,
        index=True,
        tracking=True,
    )
    description = fields.Html(sanitize=True)
    internal_notes = fields.Text()

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    list_price = fields.Monetary(
        string="Plan Price",
        currency_field="currency_id",
        default=0.0,
        required=True,
        tracking=True,
    )
    join_fee = fields.Monetary(
        string="Join Fee",
        currency_field="currency_id",
        default=0.0,
        required=True,
    )
    renewal_fee = fields.Monetary(
        string="Renewal Fee",
        currency_field="currency_id",
        default=0.0,
        required=True,
    )
    upfront_total = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_upfront_total",
        store=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Plan Product",
        domain="[('type', '=', 'service')]",
        ondelete="restrict",
    )
    pricelist_id = fields.Many2one("product.pricelist", string="Preferred Pricelist")
    income_account_id = fields.Many2one(
        "account.account",
        string="Income Account",
        # Odoo 19 account.account is multi-company through company_ids, not
        # a legacy company_id column. check_company=True delegates the
        # company compatibility domain/check to account.account itself.
        check_company=True,
        domain="[('account_type', '=', 'income')]",
        ondelete="restrict",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        domain="[('company_id', '=', company_id)]",
    )

    duration_value = fields.Integer(default=12, required=True)
    duration_unit = fields.Selection(
        [("day", "Day(s)"), ("month", "Month(s)"), ("year", "Year(s)")],
        default="month",
        required=True,
    )
    duration_human = fields.Char(compute="_compute_duration_human", store=True)

    allow_hold = fields.Boolean(default=True)
    max_hold_days_per_term = fields.Integer(default=30)
    rollover_enabled = fields.Boolean(default=False)
    priority_level = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("vip", "VIP"),
        ],
        default="normal",
        required=True,
    )
    max_concurrent_bookings = fields.Integer(default=0)

    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "membership_plan_doctor_rel",
        "plan_id",
        "doctor_id",
        string="Eligible Doctors",
    )
    allowed_treatment_ids = fields.Many2many(
        "clinic.treatment",
        "membership_plan_treatment_rel",
        "plan_id",
        "treatment_id",
        string="Eligible Treatments",
    )
    excluded_treatment_ids = fields.Many2many(
        "clinic.treatment",
        "membership_plan_treatment_excl_rel",
        "plan_id",
        "treatment_id",
        string="Excluded Treatments",
    )
    allowed_product_category_ids = fields.Many2many(
        "product.category",
        "membership_plan_product_categ_rel",
        "plan_id",
        "categ_id",
        string="Eligible Product Categories",
    )

    benefit_ids = fields.One2many(
        "membership.plan.benefit", "plan_id", string="Benefits", copy=True
    )
    contract_ids = fields.One2many(
        "membership.contract", "plan_id", string="Contracts", readonly=True
    )
    benefit_count = fields.Integer(compute="_compute_contract_counts")
    contract_count = fields.Integer(compute="_compute_contract_counts")
    active_contract_count = fields.Integer(compute="_compute_contract_counts")

    _code_company_uniq = models.Constraint(
        "UNIQUE(company_id, code)",
        "Membership plan code must be unique per company.",
    )
    _price_non_negative = models.Constraint(
        "CHECK(list_price >= 0 AND join_fee >= 0 AND renewal_fee >= 0)",
        "Plan price, join fee and renewal fee cannot be negative.",
    )
    _duration_positive = models.Constraint(
        "CHECK(duration_value > 0)",
        "Membership duration must be greater than zero.",
    )
    _hold_days_non_negative = models.Constraint(
        "CHECK(max_hold_days_per_term >= 0)",
        "Maximum hold days cannot be negative.",
    )
    _booking_limit_non_negative = models.Constraint(
        "CHECK(max_concurrent_bookings >= 0)",
        "Maximum concurrent bookings cannot be negative.",
    )

    @api.depends("list_price", "join_fee")
    def _compute_upfront_total(self):
        for rec in self:
            rec.upfront_total = (rec.list_price or 0.0) + (rec.join_fee or 0.0)

    @api.depends("duration_value", "duration_unit")
    def _compute_duration_human(self):
        labels = dict(self._fields["duration_unit"].selection)
        for rec in self:
            rec.duration_human = (
                f"{rec.duration_value} {labels.get(rec.duration_unit, '')}"
                if rec.duration_value and rec.duration_unit
                else ""
            )

    @api.depends("contract_ids.state", "benefit_ids.active")
    def _compute_contract_counts(self):
        Contract = self.env["membership.contract"]
        for rec in self:
            if not rec.id:
                rec.benefit_count = 0
                rec.contract_count = 0
                rec.active_contract_count = 0
                continue
            rec.benefit_count = len(rec.benefit_ids)
            rec.contract_count = Contract.search_count([("plan_id", "=", rec.id)])
            rec.active_contract_count = Contract.search_count(
                [
                    ("plan_id", "=", rec.id),
                    ("state", "in", ("active", "on_hold")),
                ]
            )

    @api.model
    def _next_code(self):
        return self.env["ir.sequence"].next_by_code("membership.plan") or "/"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("code", self._next_code())
            vals.setdefault("company_id", self.env.company.id)
        records = super().create(vals_list)
        records._mirror_price_to_product()
        return records

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        commercial_fields = {
            "name", "tier", "currency_id", "list_price", "join_fee", "renewal_fee",
            "duration_value", "duration_unit", "allow_hold", "max_hold_days_per_term",
            "rollover_enabled", "priority_level", "max_concurrent_bookings",
            "allowed_doctor_ids", "allowed_treatment_ids", "excluded_treatment_ids",
            "allowed_product_category_ids", "product_id", "income_account_id",
            "analytic_account_id",
        }
        if commercial_fields.intersection(vals) and any(rec.state == "active" for rec in self):
            raise UserError(
                _("Active membership plans are policy-frozen. Retire or duplicate the plan before changing commercial policy.")
            )
        result = super().write(vals)
        if {"list_price", "currency_id", "product_id"}.intersection(vals):
            self._mirror_price_to_product()
        return result

    @api.constrains("allow_hold", "max_hold_days_per_term")
    def _check_hold_policy(self):
        for rec in self:
            if rec.allow_hold and rec.max_hold_days_per_term <= 0:
                raise ValidationError(
                    _("Maximum hold days must be greater than zero when Hold/Freeze is enabled.")
                )

    @api.constrains("allowed_treatment_ids", "excluded_treatment_ids")
    def _check_treatment_scope_overlap(self):
        for rec in self:
            overlap = rec.allowed_treatment_ids & rec.excluded_treatment_ids
            if overlap:
                raise ValidationError(
                    _("A treatment cannot be both eligible and excluded: %s")
                    % ", ".join(overlap.mapped("display_name"))
                )

    @api.constrains("product_id")
    def _check_plan_product(self):
        for rec in self:
            if rec.product_id and rec.product_id.type != "service":
                raise ValidationError(_("Plan Product must be a service product."))

    @api.constrains("income_account_id", "company_id")
    def _check_income_account_company(self):
        """Keep the configured revenue account compatible with the plan company.

        Odoo 19 account.account can belong to more than one company through
        company_ids. The explicit backend constraint complements the UI domain
        and prevents RPC/import writes from bypassing the company boundary.
        """
        for rec in self:
            if (
                rec.income_account_id
                and rec.company_id
                and rec.company_id not in rec.income_account_id.sudo().company_ids
            ):
                raise ValidationError(
                    _(
                        "Income Account %(account)s is not available for company %(company)s.",
                        account=rec.income_account_id.display_name,
                        company=rec.company_id.display_name,
                    )
                )

    def _mirror_price_to_product(self):
        """Preserve the legacy convenience without silently converting currency."""
        for rec in self:
            if (
                rec.product_id
                and rec.currency_id == rec.company_id.currency_id
                and rec.product_id.lst_price != rec.list_price
            ):
                rec.product_id.with_context(clinic_membership_price_sync=True).write(
                    {"lst_price": rec.list_price}
                )

    def ensure_doctor_eligibility(self, doctor):
        self.ensure_one()
        return not self.allowed_doctor_ids or (
            doctor and doctor in self.allowed_doctor_ids
        )

    def ensure_treatment_eligibility(self, treatment):
        self.ensure_one()
        if treatment and treatment in self.excluded_treatment_ids:
            return False
        return not self.allowed_treatment_ids or (
            treatment and treatment in self.allowed_treatment_ids
        )

    def ensure_product_eligibility(self, product):
        self.ensure_one()
        if not self.allowed_product_category_ids:
            return True
        return bool(product and product.categ_id in self.allowed_product_category_ids)

    def action_activate(self):
        for rec in self:
            if rec.state == "active":
                continue
            if not rec.benefit_ids:
                raise UserError(_("Add at least one benefit before activating the plan."))
            rec._membership_write_state({"state": "active", "active": True})
            rec._membership_publish_event("plan.activated", {"plan_id": rec.id})
        return True

    def action_retire(self):
        for rec in self:
            if rec.state != "active":
                raise UserError(_("Only active plans can be retired."))
            rec._membership_write_state({"state": "retired", "active": False})
            rec._membership_publish_event("plan.retired", {"plan_id": rec.id})
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.active_contract_count:
                raise UserError(
                    _("A plan with active/on-hold contracts cannot be reset to Draft.")
                )
            rec._membership_write_state({"state": "draft", "active": True})
        return True

    def action_open_benefits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Plan Benefits"),
            "res_model": "membership.plan.benefit",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    def action_open_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contracts"),
            "res_model": "membership.contract",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.update({
            "name": _("%s (Copy)") % self.name,
            "code": self._next_code(),
            "state": "draft",
            "active": True,
        })
        return super().copy(default)

