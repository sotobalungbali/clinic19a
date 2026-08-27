# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_category.py
#
# Hierarchical category for treatments:
# - parent/child with _parent_store (parent_path) for efficient child_of queries
# - multi-company aware, tracking key fields
# - smart buttons and counts (direct & recursive)
#
# Integrations:
# - clinic.treatment.catalog (master service) via category_id
# - optional audit model clinic.audit.event (if installed) with safe fallback

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ClinicTreatmentCategory(models.Model):
    _name = "clinic.treatment.category"
    _description = "Clinic Treatment Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _parent_store = True          # enables parent_path for hierarchical queries
    _parent_name = "parent_id"
    _order = "sequence, complete_name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Category Name",
        required=True,
        tracking=True,
        index=True
    )
    complete_name = fields.Char(
        string="Complete Name",
        compute="_compute_complete_name",
        store=True,
        recursive=True
    )
    code = fields.Char(
        string="Code",
        copy=False,
        index=True,
        tracking=True,
        help="Unique code per company (auto from sequence if defined)."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values mean higher priority in lists."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True
    )
    color = fields.Integer(
        string="Color Index",
        help="Kanban color helper."
    )

    # -------------------------------------------------------------------------
    # Hierarchy
    # -------------------------------------------------------------------------
    parent_id = fields.Many2one(
        "clinic.treatment.category",
        string="Parent Category",
        index=True,
        ondelete="restrict",
        domain="[('id','!=',id), ('company_id','in',[False, company_id])]",
        tracking=True
    )
    child_ids = fields.One2many(
        "clinic.treatment.category",
        "parent_id",
        string="Child Categories"
    )
    parent_path = fields.Char(index=True)  # managed by _parent_store

    # -------------------------------------------------------------------------
    # Company
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # -------------------------------------------------------------------------
    # Presentation
    # -------------------------------------------------------------------------
    image_1920 = fields.Image(string="Image", max_width=1920, max_height=1920)
    description = fields.Html(string="Description", sanitize=True)

    # -------------------------------------------------------------------------
    # Counters
    # -------------------------------------------------------------------------
    treatment_count = fields.Integer(
        string="Treatments (Direct)",
        compute="_compute_counts",
        help="Jumlah treatment langsung pada kategori ini (tanpa turunan)."
    )
    treatment_count_recursive = fields.Integer(
        string="Treatments (All Levels)",
        compute="_compute_counts",
        help="Jumlah treatment di kategori ini + seluruh sub-kategori."
    )
    child_count = fields.Integer(
        string="Subcategories",
        compute="_compute_counts",
        help="Jumlah sub-kategori langsung."
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Code must be unique per company.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("name", "parent_id", "parent_id.complete_name")
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = "%s / %s" % (rec.parent_id.complete_name, rec.name)
            else:
                rec.complete_name = rec.name

    def _compute_counts(self):
        Treatment = self.env["clinic.treatment.catalog"]
        # Direct counts via _read_group
        if self.ids:
            groups = Treatment._read_group(
                [("category_id", "in", self.ids)],
                ["category_id"],
                ["__count"],
            )
            direct_map = {category.id: count for category, count in groups if category}
        else:
            direct_map = {}

        for rec in self:
            rec.treatment_count = direct_map.get(rec.id, 0)
            # child_of uses parent_path for performant hierarchy search
            rec.treatment_count_recursive = Treatment.search_count([("category_id", "child_of", rec.id)])
            rec.child_count = len(rec.child_ids)

    # =========================================================================
    # ONCHANGE / CONSTRAINS
    # =========================================================================
    @api.constrains("parent_id")
    def _check_parent_company(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.company_id != rec.company_id:
                raise ValidationError(_("Parent category must belong to the same company."))

    @api.constrains("parent_id")
    def _check_recursion_safe(self):
        if not self._check_recursion():
            raise ValidationError(_("Error! You cannot create recursive categories."))

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq_rec = self.env.ref("clinic_treatment_catalog.seq_treatment_category_code", raise_if_not_found=False)
        for vals in vals_list:
            # default company
            vals.setdefault("company_id", self.env.company.id)
            # sequence for code if not provided
            if not vals.get("code") and seq_rec:
                vals["code"] = seq_rec._next()
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = {"name", "code", "parent_id", "company_id", "active", "sequence"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def unlink(self):
        """Cegah penghapusan kategori yang sedang dipakai atau memiliki turunan."""
        Treatment = self.env["clinic.treatment.catalog"]
        for rec in self:
            if rec.child_ids:
                raise UserError(_("You cannot delete a category that has subcategories. Archive it instead."))
            if Treatment.search_count([("category_id", "=", rec.id)]) > 0:
                raise UserError(_("You cannot delete a category that is assigned to treatments. Archive it instead."))
        return super().unlink()

    # =========================================================================
    # HELPERS & PUBLIC API
    # =========================================================================
    def _audit_event(self, action, changed_fields=None):
        """Log event ke audit model bila ada; fallback ke chatter."""
        self.message_post(body=_("Category %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "category.%s" % action,
                    "model": rec._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {
                        "changed_fields": changed_fields or [],
                        "user_id": self.env.user.id,
                    },
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    def get_descendant_ids(self, include_self=True):
        """Kembalikan list id kategori turunan (memanfaatkan parent_path)."""
        domain = [("id", "child_of", self.ids)]
        ids = self.search(domain).ids
        if not include_self:
            ids = list(set(ids) - set(self.ids))
        return ids

    # =========================================================================
    # ACTIONS / SMART BUTTONS
    # =========================================================================
    def action_open_treatments(self, recursive=False):
        """Buka daftar treatment untuk kategori ini.
        - recursive=False: hanya milik kategori ini
        - recursive=True: termasuk semua sub-kategori
        """
        self.ensure_one()
        domain = [("category_id", "=", self.id)]
        name = _("Treatments in %s") % (self.complete_name,)
        if recursive:
            domain = [("category_id", "child_of", self.id)]
            name = _("Treatments in %s and subcategories") % (self.complete_name,)

        action = self.env.ref("clinic_treatment_catalog.action_treatment_tree", raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res["name"] = name
            res["domain"] = domain
            return res

        # Fallback generic action
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "clinic.treatment.catalog",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_category_id": self.id},
        }

    # =========================================================================
    # NAME GET / SEARCH
    # =========================================================================
    def _clinic_display_label(self):
        self.ensure_one()
        label = self.complete_name or self.name
        return "[%s] %s" % (self.code, label) if self.code else label

    @api.depends("code", "name", "complete_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = ["|", "|", ("code", operator, name), ("name", operator, name), ("complete_name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

