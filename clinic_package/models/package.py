
# -*- coding: utf-8 -*-
"""Treatment package catalog and lifecycle."""

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicPackageTag(models.Model):
    _name = "clinic.package.tag"
    _description = "Clinic Package Tag"
    _order = "name, id"

    name = fields.Char(required=True, translate=True, index=True)
    color = fields.Integer(default=0)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "A package tag with the same name already exists in this company.",
    )


class ClinicPackage(models.Model):
    _name = "clinic.package"
    _description = "Clinic Treatment Package"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(readonly=True, copy=False, index=True, tracking=True, default="/")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    color = fields.Integer(default=0)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    tag_ids = fields.Many2many(
        "clinic.package.tag",
        "clinic_package_tag_rel",
        "package_id",
        "tag_id",
        string="Tags",
        check_company=True,
    )

    list_price = fields.Monetary(string="Base Sales Price", tracking=True)
    cost_price = fields.Monetary(string="Estimated Cost")
    margin_amount = fields.Monetary(compute="_compute_margin", store=True)
    margin_percent = fields.Float(compute="_compute_margin", store=True)
    pricing_id = fields.Many2one(
        "clinic.package.pricing",
        string="Pricing Profile",
        check_company=True,
        tracking=True,
    )
    policy_id = fields.Many2one(
        "clinic.package.policy",
        string="Policy Profile",
        check_company=True,
        tracking=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="Service Product",
        domain="[('type', '=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
        help="Optional commercial product used by later billing/eCommerce flows.",
    )

    valid_from = fields.Date(tracking=True)
    valid_to = fields.Date(tracking=True)
    duration_value = fields.Integer(default=12, required=True)
    duration_uom = fields.Selection(
        [("day", "Days"), ("week", "Weeks"), ("month", "Months"), ("year", "Years")],
        default="month",
        required=True,
    )
    duration_days = fields.Integer(compute="_compute_duration_days", store=True)

    allow_pause = fields.Boolean(related="policy_id.allow_pause", readonly=True, store=True)
    allow_transfer = fields.Boolean(related="policy_id.allow_transfer", readonly=True, store=True)
    allow_refund = fields.Boolean(related="policy_id.allow_refund", readonly=True, store=True)
    allow_upgrade = fields.Boolean(related="policy_id.allow_upgrade", readonly=True, store=True)
    allow_usage_when_paused = fields.Boolean(
        default=False,
        help="Allow redemptions while an allocation is paused. Normally disabled.",
    )

    line_ids = fields.One2many(
        "clinic.package.line", "package_id", string="Package Components", copy=True
    )
    line_count = fields.Integer(compute="_compute_counts")
    allocation_count = fields.Integer(compute="_compute_counts")
    usage_count = fields.Integer(compute="_compute_counts")
    voucher_count = fields.Integer(compute="_compute_counts")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    description = fields.Html(sanitize=True)
    terms = fields.Html(string="Terms & Conditions", sanitize=True)
    internal_note = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Package code must be unique per company.",
    )
    _nonnegative_price = models.Constraint(
        "CHECK(list_price >= 0 AND cost_price >= 0)",
        "Package price and estimated cost must be zero or positive.",
    )
    _duration_positive = models.Constraint(
        "CHECK(duration_value > 0)",
        "Package duration must be greater than zero.",
    )

    @api.depends("list_price", "cost_price")
    def _compute_margin(self):
        for record in self:
            record.margin_amount = (record.list_price or 0.0) - (record.cost_price or 0.0)
            record.margin_percent = (
                record.margin_amount / record.list_price * 100.0 if record.list_price else 0.0
            )

    @api.depends("duration_value", "duration_uom")
    def _compute_duration_days(self):
        for record in self:
            value = max(record.duration_value or 0, 0)
            multiplier = {"day": 1, "week": 7, "month": 30, "year": 365}
            record.duration_days = value * multiplier.get(record.duration_uom, 0)

    def _compute_counts(self):
        Allocation = self.env["clinic.package.allocation"]
        Usage = self.env["clinic.package.usage"]
        Voucher = self.env["clinic.package.voucher"]
        for record in self:
            record.line_count = len(record.line_ids)
            record.allocation_count = Allocation.search_count([("package_id", "=", record.id)])
            record.usage_count = Usage.search_count([("package_id", "=", record.id)])
            record.voucher_count = Voucher.search_count([("package_id", "=", record.id)])

    @api.constrains("valid_from", "valid_to")
    def _check_validity_dates(self):
        for record in self:
            if record.valid_from and record.valid_to and record.valid_to < record.valid_from:
                raise ValidationError(_("Package Valid To cannot be before Valid From."))

    @api.constrains("pricing_id", "policy_id", "company_id")
    def _check_profile_company(self):
        for record in self:
            if record.pricing_id and record.pricing_id.company_id != record.company_id:
                raise ValidationError(_("Pricing profile must belong to the package company."))
            if record.policy_id and record.policy_id.company_id != record.company_id:
                raise ValidationError(_("Policy profile must belong to the package company."))

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" and not self.env.context.get("clinic_package_state_change"):
                raise UserError(_("Treatment packages must be created in Draft and activated through the approved action."))
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("code") in (False, "/", None):
                vals["code"] = sequence.next_by_code("clinic.package") or "/"
            if not vals.get("policy_id"):
                company = self.env["res.company"].browse(vals["company_id"])
                vals["policy_id"] = company.clinic_pkg_default_policy_id.id or False
            if not vals.get("pricing_id"):
                company = self.env["res.company"].browse(vals["company_id"])
                vals["pricing_id"] = company.clinic_pkg_default_pricing_id.id or False
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_package_state_change"):
            raise UserError(_("Package status can only be changed through workflow actions."))
        protected = {"line_ids", "company_id", "currency_id"}
        if protected.intersection(vals) and any(record.state not in ("draft", "paused") for record in self):
            raise UserError(_("Package structure can only be changed in Draft or Paused status."))
        return super().write(vals)

    def _get_expiry_date(self, start_date):
        self.ensure_one()
        if not start_date:
            return False
        start_date = fields.Date.to_date(start_date)
        value = self.duration_value
        if self.duration_uom == "day":
            return start_date + relativedelta(days=value)
        if self.duration_uom == "week":
            return start_date + relativedelta(weeks=value)
        if self.duration_uom == "month":
            return start_date + relativedelta(months=value)
        if self.duration_uom == "year":
            return start_date + relativedelta(years=value)
        return start_date

    def _ensure_ready_for_activation(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_("Add at least one package component before activation."))
            if any(not line.active for line in record.line_ids):
                raise UserError(_("Archive unwanted component lines before activation or remove them."))
            if record.valid_from and record.valid_to and record.valid_to < fields.Date.context_today(record):
                raise UserError(_("An already expired package cannot be activated."))
        return True

    def action_activate(self):
        self._ensure_ready_for_activation()
        self.with_context(clinic_package_state_change=True).write({"state": "active", "active": True})
        for record in self:
            record._enqueue_integration_event("package.activated")
        return True

    def action_pause(self):
        for record in self:
            if record.state != "active":
                raise UserError(_("Only active packages can be paused."))
        self.with_context(clinic_package_state_change=True).write({"state": "paused"})
        for record in self:
            record._enqueue_integration_event("package.paused")
        return True

    def action_resume(self):
        for record in self:
            if record.state != "paused":
                raise UserError(_("Only paused packages can be resumed."))
        self.with_context(clinic_package_state_change=True).write({"state": "active"})
        for record in self:
            record._enqueue_integration_event("package.resumed")
        return True

    def action_close(self):
        for record in self:
            if record.state not in ("active", "paused"):
                raise UserError(_("Only active or paused packages can be closed."))
        self.with_context(clinic_package_state_change=True).write({"state": "closed"})
        return True

    def action_cancel(self):
        for record in self:
            if record.allocation_count:
                active_allocations = self.env["clinic.package.allocation"].search_count(
                    [("package_id", "=", record.id), ("state", "in", ["active", "paused"])]
                )
                if active_allocations:
                    raise UserError(_("Close or cancel active allocations before cancelling this package."))
        self.with_context(clinic_package_state_change=True).write({"state": "cancelled", "active": False})
        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.state not in ("cancelled", "closed"):
                raise UserError(_("Only closed or cancelled packages can be reset to Draft."))
        self.with_context(clinic_package_state_change=True).write({"state": "draft", "active": True})
        return True

    def action_create_service_product(self):
        self.ensure_one()
        if self.product_template_id:
            return self.action_view_service_product()
        product = self.env["product.template"].create(
            {
                "name": self.name,
                "default_code": self.code,
                "type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": self.list_price,
                "company_id": self.company_id.id,
            }
        )
        self.product_template_id = product
        return self.action_view_service_product()

    def action_view_service_product(self):
        self.ensure_one()
        if not self.product_template_id:
            raise UserError(_("No service product is linked to this package."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Service Product"),
            "res_model": "product.template",
            "view_mode": "form",
            "res_id": self.product_template_id.id,
        }

    def action_view_allocations(self):
        self.ensure_one()
        return self._related_action("clinic.package.allocation", [("package_id", "=", self.id)], _("Allocations"))

    def action_view_usages(self):
        self.ensure_one()
        return self._related_action("clinic.package.usage", [("package_id", "=", self.id)], _("Redemptions"))

    def action_view_vouchers(self):
        self.ensure_one()
        return self._related_action("clinic.package.voucher", [("package_id", "=", self.id)], _("Vouchers"))

    def _related_action(self, model, domain, name):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_package_id": self.id},
        }

    def _enqueue_integration_event(self, event_code, payload=None):
        self.ensure_one()
        return self.env["clinic.package.integration.event"].enqueue(event_code, self, payload=payload)
