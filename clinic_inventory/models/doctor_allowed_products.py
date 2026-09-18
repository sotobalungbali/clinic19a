# -*- coding: utf-8 -*-
# File: models/doctor_allowed_products.py
# Module: clinic_inventory
#
# Purpose
#   Define doctor-specific allow/deny rules for clinical product usage:
#   - Product-level or Category-level rules
#   - Allow/Deny actions with priority, validity dates, and archiving
#   - Public APIs to check permission and to build allowed product domains
#   - hr.employee helpers & UI actions to manage a doctor's allowed list
#
# Notes
#   - All user-facing strings are in English.
#   - Depends only on Odoo core models: hr.employee, product.product/category.
#   - Designed to be consumed by other ClinicOne modules without circular deps.

from datetime import date
from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import ValidationError, UserError


# ============================================================================
# Main rule model
# ============================================================================
class ClinicDoctorAllowedProduct(models.Model):
    _name = "clinic.doctor.allowed.product"
    _description = "Doctor Allowed Product Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "doctor_id, priority desc, action asc, rule_type asc, id desc"

    # Identity / ownership -----------------------------------------------------
    name = fields.Char(
        string="Rule Name",
        compute="_compute_name",
        store=True,
        help="Auto-generated label combining doctor, action, and target."
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        required=True,
        index=True,
        tracking=True,
        help="Doctor for whom this rule applies."
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        help="Company scope for this rule."
    )

    # Rule target --------------------------------------------------------------
    rule_type = fields.Selection(
        selection=[("product", "Product"), ("category", "Category")],
        string="Rule Type",
        required=True,
        default="product",
        tracking=True,
        help="Target type of this rule (a specific product or a whole product category)."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('type','!=','service')]",
        help="Target product for PRODUCT rule."
    )
    category_id = fields.Many2one(
        "product.category",
        string="Category",
        help="Target category for CATEGORY rule (includes its subcategories)."
    )

    # Behavior -----------------------------------------------------------------
    action = fields.Selection(
        selection=[("allow", "Allow"), ("deny", "Deny")],
        string="Action",
        required=True,
        default="allow",
        tracking=True,
        help="Whether to allow or deny the usage of the target product(s)."
    )
    priority = fields.Integer(
        string="Priority",
        default=10,
        tracking=True,
        help="Higher priority rules take precedence when conflicts happen between rules at the same scope."
    )
    date_start = fields.Date(
        string="Valid From",
        help="Optional start date for this rule's validity window."
    )
    date_end = fields.Date(
        string="Valid Until",
        help="Optional end date for this rule's validity window."
    )
    archived = fields.Boolean(
        string="Archived",
        default=False,
        tracking=True,
        help="If checked, this rule is inactive regardless of the validity dates."
    )
    is_active = fields.Boolean(
        string="Active (Computed)",
        compute="_compute_is_active",
        search="_search_is_active",
        store=False,
        help="True if today is within the rule's validity window and rule is not archived."
    )

    note = fields.Char(
        string="Note",
        help="Optional short note describing this rule."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("doctor_id", "action", "rule_type", "product_id", "category_id")
    def _compute_name(self):
        for r in self:
            doc = r.doctor_id.display_name or "Doctor"
            act = dict(self._fields["action"].selection).get(r.action or "allow")
            tgt = "-"
            if r.rule_type == "product" and r.product_id:
                tgt = r.product_id.display_name
            elif r.rule_type == "category" and r.category_id:
                tgt = r.category_id.display_name
            r.name = f"{doc}: {act} {tgt}"

    def _today(self):
        return date.today()

    def _in_validity_window(self):
        """Return True if today within [date_start, date_end] (open bounds allowed)."""
        today = self._today()
        for r in self:
            if r.archived:
                return False
            if r.date_start and today < r.date_start:
                return False
            if r.date_end and today > r.date_end:
                return False
        return True

    def _compute_is_active(self):
        for r in self:
            r.is_active = False if r.archived else r._in_validity_window()

    def _search_is_active(self, operator, value):
        """
        Translate searches on the non-stored Active helper to stored fields.

        This keeps the Search view filter reliable without storing a
        date-relative Boolean that would become stale when the calendar day
        changes.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                _("Active can only be searched with '=' or '!=' and a Boolean value.")
            )

        want_active = value if operator == "=" else not value
        today = fields.Date.context_today(self)

        active_domain = (
            Domain("archived", "=", False)
            & (Domain("date_start", "=", False) | Domain("date_start", "<=", today))
            & (Domain("date_end", "=", False) | Domain("date_end", ">=", today))
        )
        return active_domain if want_active else ~active_domain

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("rule_type", "product_id", "category_id")
    def _check_target_presence(self):
        for r in self:
            if r.rule_type == "product" and not r.product_id:
                raise ValidationError(_("For PRODUCT rule type, a Product must be set."))
            if r.rule_type == "category" and not r.category_id:
                raise ValidationError(_("For CATEGORY rule type, a Category must be set."))
            if r.rule_type == "product" and r.category_id:
                raise ValidationError(_("PRODUCT rule must not have a Category set."))
            if r.rule_type == "category" and r.product_id:
                raise ValidationError(_("CATEGORY rule must not have a Product set."))

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for r in self:
            if r.date_start and r.date_end and r.date_end < r.date_start:
                raise ValidationError(_("Valid Until cannot be earlier than Valid From."))

    _uniq_doctor_product_company = models.Constraint(
        "UNIQUE(doctor_id, company_id, product_id)",
        "Duplicate PRODUCT rule detected for the same doctor, company, and product.",
    )
    _uniq_doctor_category_company = models.Constraint(
        "UNIQUE(doctor_id, company_id, category_id)",
        "Duplicate CATEGORY rule detected for the same doctor, company, and category.",
    )

    # -------------------------------------------------------------------------
    # Core matching logic
    # -------------------------------------------------------------------------
    def _matches_product(self, product):
        """Return True if this rule applies to the given product."""
        self.ensure_one()
        if self.rule_type == "product":
            return product and product.id == self.product_id.id
        if self.rule_type == "category":
            if not product:
                return False
            categ = product.categ_id
            return bool(categ and categ.id and self.category_id and categ.id in self.category_id.search(
                [("id", "child_of", self.category_id.id)]
            ).ids)
        return False

    # -------------------------------------------------------------------------
    # Public APIs
    # -------------------------------------------------------------------------
    @api.model
    def clinic_doctor_can_use_product(self, doctor, product, on_date=None):
        """Return (allowed: bool, reason: str).

        Precedence:
          1) DENY rules that match (and are active) → block.
          2) ALLOW rules that match (and are active) → allow.
          3) If no rules match, default = ALLOW (soft default).
             Bridges may override this policy based on settings.
        """
        if not doctor or not product:
            return True, None

        company = doctor.company_id or self.env.company
        on_date = on_date or date.today()

        # Fetch rules for this doctor & company once
        rules = self.search([("doctor_id", "=", doctor.id),
                             ("company_id", "=", company.id),
                             ("archived", "=", False)])

        matched_deny = []
        matched_allow = []
        for r in rules:
            # check validity window
            within = True
            if r.date_start and on_date < r.date_start:
                within = False
            if r.date_end and on_date > r.date_end:
                within = False
            if not within:
                continue
            if r._matches_product(product):
                if r.action == "deny":
                    matched_deny.append(r)
                else:
                    matched_allow.append(r)

        if matched_deny:
            # Take highest priority for message
            top = sorted(matched_deny, key=lambda x: x.priority, reverse=True)[0]
            return False, _("Denied by rule: %s") % (top.display_name or top.name)

        if matched_allow:
            top = sorted(matched_allow, key=lambda x: x.priority, reverse=True)[0]
            return True, _("Allowed by rule: %s") % (top.display_name or top.name)

        # Default soft allow
        return True, _("No matching rule; default allow.")

    @api.model
    def clinic_allowed_product_domain(self, doctor):
        """Return a product domain representing what the doctor may use (approximation).

        Domain logic:
          - If any DENY rules exist: exclude those products/categories.
          - If any ALLOW rules exist: include union of allowed products/categories.
          - If no rules exist: return domain allowing non-service products.
        """
        Product = self.env["product.product"]
        if not doctor:
            return [("type", "!=", "service")]

        rules = self.search([("doctor_id", "=", doctor.id),
                             ("company_id", "=", doctor.company_id.id if doctor.company_id else self.env.company.id),
                             ("archived", "=", False)])
        if not rules:
            return [("type", "!=", "service")]

        allow_products = set()
        allow_categs = set()
        deny_products = set()
        deny_categs = set()

        today = date.today()
        for r in rules:
            # validity check
            if r.date_start and today < r.date_start:
                continue
            if r.date_end and today > r.date_end:
                continue
            if r.rule_type == "product" and r.product_id:
                (deny_products if r.action == "deny" else allow_products).add(r.product_id.id)
            elif r.rule_type == "category" and r.category_id:
                (deny_categs if r.action == "deny" else allow_categs).add(r.category_id.id)

        # Build domain pieces
        dom_allow = []
        if allow_products or allow_categs:
            sub = []
            if allow_products:
                sub.append(("id", "in", list(allow_products)))
            if allow_categs:
                sub.append(("categ_id", "child_of", list(allow_categs)))
            # Combine OR between product and category subconditions
            if len(sub) == 2:
                dom_allow = ["|"] + sub
            elif len(sub) == 1:
                dom_allow = sub
        else:
            # If no explicit ALLOW, start from all non-service
            dom_allow = [("type", "!=", "service")]

        dom_deny = []
        if deny_products or deny_categs:
            sub = []
            if deny_products:
                sub.append(("id", "not in", list(deny_products)))
            if deny_categs:
                sub.append(("categ_id", "not child_of", list(deny_categs)))
            # Combine AND between deny conditions
            dom_deny = sub

        # Final domain = allow AND deny
        return dom_allow + dom_deny

    # Backward-compat shim for simplistic checks used by some modules
    @api.model
    def is_product_explicitly_allowed(self, doctor, product):
        """Return True if a PRODUCT-level ALLOW rule exists (ignores category rules)."""
        if not doctor or not product:
            return True
        return bool(self.search_count([
            ("doctor_id", "=", doctor.id),
            ("company_id", "=", doctor.company_id.id if doctor.company_id else self.env.company.id),
            ("rule_type", "=", "product"),
            ("product_id", "=", product.id),
            ("action", "=", "allow"),
            ("archived", "=", False),
        ]))

    # -------------------------------------------------------------------------
    # UI ACTIONS
    # -------------------------------------------------------------------------
    def action_view_allowed_products(self):
        """Open product view filtered by this doctor's allowed domain."""
        self.ensure_one()
        action = self.env.ref("product.product_normal_action").read()[0]
        action["domain"] = self.clinic_allowed_product_domain(self.doctor_id)
        return action

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "archived")
    def _compute_display_name(self):
        """Odoo 19 display label, preserving the existing archived marker."""
        for rec in self:
            label = rec.name or _("Rule")
            rec.display_name = f"{label} [ARCHIVED]" if rec.archived else label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]


# ============================================================================
# hr.employee extension (lightweight helpers)
# ============================================================================
class HREmployee(models.Model):
    _inherit = "hr.employee"

    clinic_allowed_rule_ids = fields.One2many(
        "clinic.doctor.allowed.product",
        "doctor_id",
        string="Allowed Product Rules",
        help="Allow/Deny rules that apply to this doctor."
    )
    clinic_allowed_rules_count = fields.Integer(
        string="# Rules",
        compute="_compute_clinic_rules_count",
        help="Number of active allow/deny rules for this doctor."
    )

    def _compute_clinic_rules_count(self):
        Model = self.env["clinic.doctor.allowed.product"].sudo()
        for emp in self:
            emp.clinic_allowed_rules_count = Model.search_count([("doctor_id", "=", emp.id), ("archived", "=", False)])

    def action_view_allowed_rules(self):
        """Open the rules list for this doctor."""
        self.ensure_one()
        action = self.env.ref("base.action_rule").sudo() if False else None  # placeholder; fall back to generic list
        # Fallback to our own model's list/form
        action = self.env["ir.actions.act_window"]._for_xml_id("base.action_partner_form") if False else {
            "name": _("Allowed Products"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.doctor.allowed.product",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id, "search_default_archived": 0},
        }
        return action

    # Public shortcut APIs -----------------------------------------------------
    def clinic_is_product_allowed(self, product):
        """Shortcut: (allowed, reason) using the rule engine."""
        self.ensure_one()
        return self.env["clinic.doctor.allowed.product"].clinic_doctor_can_use_product(self, product)

    def clinic_allowed_product_domain(self):
        """Shortcut: product domain of items this doctor may use."""
        self.ensure_one()
        return self.env["clinic.doctor.allowed.product"].clinic_allowed_product_domain(self)




