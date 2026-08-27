
# -*- coding: utf-8 -*-
# File: clinic_doctor/models/specialty.py
# Module: clinic_doctor
#
# ClinicOne — Specialty catalog (Odoo 18/19 CE ready)
#
# Purpose
# -------
# Centralized catalog of doctor specialties used across the ClinicOne suite:
# - Assign specialties to doctors (via hr.employee + is_doctor)
# - (Optionally) scope treatments/services/pricing by specialty
# - Support search, hierarchy, KPIs, and navigation actions
#
# Integration
# -----------
# This model is intentionally lightweight with *optional* cross-module hooks.
# It does NOT hard-depend on the other modules; instead it checks presence via `"model" in self.env`.
#
# Notes
# -----
# - All field labels, help, and messages are in English (product requirement).
# - Designed for multi-company environments with company-scoped uniqueness.
# - Uses mail.thread/activity for collaboration and auditability.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicSpecialty(models.Model):
    _name = "clinic.specialty"
    _description = "Doctor Specialty"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _parent_name = "parent_id"
    _parent_store = True
    _order = "sequence, complete_name, id"
    _rec_name = "complete_name"

    # -------------------------------------------------------------------------
    # IDENTITY & PRESENTATION
    # -------------------------------------------------------------------------
    name = fields.Char(
        required=True,
        tracking=True,
        translate=True,
        help="Specialty name, e.g., Dermatology, Aesthetic Medicine, Dentistry."
    )
    code = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Short unique code for the specialty within the company, e.g., DERM, AESTH."
    )
    description = fields.Text(
        tracking=False,
        help="Internal description or notes about the scope of this specialty."
    )
    image_1920 = fields.Image(
        help="Optional icon or representative image for this specialty."
    )
    color = fields.Integer(
        help="Color index to visually distinguish specialties in list/kanban."
    )
    sequence = fields.Integer(
        default=10,
        help="Display order of specialties."
    )
    active = fields.Boolean(
        default=True,
        help="Disable a specialty to hide it from selection without deleting historical data."
    )

    # -------------------------------------------------------------------------
    # COMPANY SCOPE
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Company that this specialty belongs to."
    )

    # -------------------------------------------------------------------------
    # HIERARCHY
    # -------------------------------------------------------------------------
    parent_id = fields.Many2one(
        "clinic.specialty",
        index=True,
        ondelete="restrict",
        help="Parent specialty in the hierarchy."
    )
    child_ids = fields.One2many(
        "clinic.specialty",
        "parent_id",
        string="Subspecialties",
        help="Subspecialties under this specialty."
    )
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(
        compute="_compute_complete_name",
        store=True,
        help="Full hierarchical path, e.g., 'Aesthetics / Injectables'."
    )

    # -------------------------------------------------------------------------
    # RELATIONS (Doctor linkage via hr.employee)
    # -------------------------------------------------------------------------
    employee_ids = fields.Many2many(
        "hr.employee",
        relation="clinic_specialty_employee_rel",
        column1="specialty_id",   # mirror of hr.employee.specialty_ids (employee_id <-> specialty_id)
        column2="employee_id",
        string="Doctors",
        help="Doctors (employees) who practice this specialty.",
    )

    # -------------------------------------------------------------------------
    # KPIs (optional; populated by reporting jobs)
    # -------------------------------------------------------------------------
    kpi_monthly_revenue = fields.Monetary(
        currency_field="currency_id",
        help="Monthly revenue attributed to this specialty (populated by reporting jobs)."
    )
    kpi_monthly_volume = fields.Integer(
        help="Monthly count of services for this specialty (populated by reporting jobs)."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency for KPI monetary values."
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "UNIQUE (code, company_id)",
        "Specialty code must be unique per company.",
    )
    _name_company_uniq = models.Constraint(
        "UNIQUE (name, company_id)",
        "Specialty name must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("name", "parent_id", "parent_id.complete_name")
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                parent = rec.parent_id.complete_name or rec.parent_id.name or ""
                rec.complete_name = "%s / %s" % (parent, rec.name or "")
            else:
                rec.complete_name = rec.name or ""

    # -------------------------------------------------------------------------
    # PY CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("parent_id")
    def _check_recursion(self):
        if not self._check_m2o_recursion("parent_id"):
            raise ValidationError(_("You cannot create a recursive specialty hierarchy."))

    @api.constrains("code")
    def _check_code_format(self):
        for rec in self:
            if rec.code and " " in rec.code:
                # Format guideline for simplicity; change to regex if needed by policy
                raise ValidationError(_("Specialty code should not contain spaces."))

    @api.onchange("code")
    def _onchange_code(self):
        if self.code:
            self.code = self.code.strip().upper()

    # -------------------------------------------------------------------------
    # SEARCH UX
    # -------------------------------------------------------------------------
    @api.depends("complete_name", "name", "code")
    def _compute_display_name(self):
        """Preserve hierarchical specialty labels through the Odoo 19 display-name API."""
        for rec in self:
            label = rec.complete_name or rec.name or _("Unnamed")
            if rec.code:
                label = f"{label} [{rec.code}]"
            rec.display_name = label

    def name_get(self):
        """Compatibility wrapper for existing ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = list(domain or [])
        if name:
            domain = ["|", ("code", operator, name), ("complete_name", operator, name)] + domain
        recs = self.search(domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

    # -------------------------------------------------------------------------
    # ACTIONS (NAVIGATION HELPERS)
    # -------------------------------------------------------------------------
    def action_view_doctors(self):
        """Open doctors (employees) associated with this specialty."""
        self.ensure_one()
        # Use the relation owned by this model.  Do not require optional
        # hr.employee extension fields from another ClinicOne addon.
        context = {}
        if "is_doctor" in self.env["hr.employee"]._fields:
            context["default_is_doctor"] = True
        return {
            "type": "ir.actions.act_window",
            "name": _("Doctors"),
            "res_model": "hr.employee",
            "view_mode": "list,form,kanban,pivot,graph",
            "domain": [("id", "in", self.employee_ids.ids)],
            "context": context,
            "target": "current",
        }
