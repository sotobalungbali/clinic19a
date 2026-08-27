# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_public.py
#
# Purpose
# -------
# Provide a compatibility/public-facing model `clinic.treatment` that delegates
# ALL business fields and logic to `clinic.treatment.catalog` via `_inherits`.
#
# Why?
# ----
# - Other ClinicOne modules (e.g., clinic_booking) may `_inherit` or reference
#   `clinic.treatment`.
# - Inside this addon, the canonical model is `clinic.treatment.catalog`.
# - We avoid duplication/overlap by delegating through `_inherits` and adding
#   thin method proxies only when useful for cross-module integrations.
#
# Design
# ------
# - No field is redefined: the data/table of business fields remain in
#   `clinic.treatment.catalog`.
# - `clinic.treatment` holds only `catalog_id` (Many2one, cascade delete) and a
#   few safe helpers/proxies.
# - Company consistency is enforced with a constraint.
# - Create/Write handle delegated values: if delegated fields are passed to
#   `clinic.treatment.create/write`, they are routed to the underlying catalog.
#
# Notes on chatter:
# -----------------
# The delegated parent (`clinic.treatment.catalog`) already inherits
# `mail.thread`/`mail.activity.mixin`. We DO NOT add those mixins here to avoid
# field name collisions. We provide a light `message_post` proxy.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class ClinicTreatmentPublic(models.Model):
    _name = "clinic.treatment"
    _description = "Clinic Treatment (Public Model, delegates to Catalog)"
    _inherits = {"clinic.treatment.catalog": "catalog_id"}
    _order = "name, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Link to the canonical catalog record
    # -------------------------------------------------------------------------
    catalog_id = fields.Many2one(
        "clinic.treatment.catalog",
        string="Catalog Record",
        required=True,
        ondelete="cascade",
        index=True,
        help="Underlying catalog record that holds all business fields."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="catalog_id.company_id",
        store=True,
        readonly=True
    )

    active = fields.Boolean(
        string="Active",
        related="catalog_id.active",
        store=True,
        readonly=False,
        help="Convenience toggle delegated to the catalog record."
    )

    # Ensure strict 1-1 between public and catalog (one public per catalog)
    _catalog_unique = models.Constraint(
        "unique(catalog_id)",
        "Each Catalog record can be linked to only one Treatment.",
    )

    # -------------------------------------------------------------------------
    # CREATE / WRITE: route delegated fields safely to the catalog
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Catalog = self.env["clinic.treatment.catalog"]
        parent_fields = set(Catalog._fields.keys())
        new_vals_list = []

        for vals in vals_list:
            vals = dict(vals)  # copy
            cat_id = vals.get("catalog_id")
            delegated = {k: vals.pop(k) for k in list(vals.keys()) if k in parent_fields}

            if cat_id:
                # Ensure catalog exists and optionally apply delegated updates first
                catalog = Catalog.browse(cat_id)
                if not catalog.exists():
                    raise ValidationError(_("Invalid Catalog Record."))
                if delegated:
                    catalog.write(delegated)
            else:
                # No catalog provided -> create one from delegated values
                # Default company safety handled by parent model
                catalog = Catalog.create(delegated or {})
                vals["catalog_id"] = catalog.id

            new_vals_list.append(vals)

        return super().create(new_vals_list)

    def write(self, vals):
        Catalog = self.env["clinic.treatment.catalog"]
        parent_fields = set(Catalog._fields.keys())
        delegated = {k: vals.pop(k) for k in list(vals.keys()) if k in parent_fields}

        # Apply updates to public (child) first for fields like catalog_id (rare)
        res = super().write(vals)

        # Then route delegated fields to the linked catalog records
        if delegated:
            self.mapped("catalog_id").write(delegated)
        return res

    def unlink(self):
        """
        Deleting the public record will cascade to the catalog due to ondelete='cascade'
        on the `catalog_id` field. This is intentional to keep 1-1 lifecycle.
        Archive instead of delete if you need to preserve history.
        """
        return super().unlink()

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("catalog_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.catalog_id and rec.company_id and rec.catalog_id.company_id != rec.company_id:
                raise ValidationError(_("Company mismatch between Treatment and Catalog record."))

    # -------------------------------------------------------------------------
    # PROXIES (commonly used by other modules)
    # -------------------------------------------------------------------------
    def message_post(self, **kwargs):
        """Proxy chatter posting to the underlying catalog record."""
        self.ensure_one()
        return self.catalog_id.message_post(**kwargs)

    # Pricing & product helpers (mirror common API used by other modules)
    def get_service_product(self):
        self.ensure_one()
        return self.catalog_id.get_service_product()

    def get_default_price(self):
        self.ensure_one()
        return self.catalog_id.get_default_price()

    def get_minimum_price(self):
        self.ensure_one()
        return self.catalog_id.get_minimum_price()

    def prepare_invoice_line_vals(self, **kwargs):
        self.ensure_one()
        return self.catalog_id.prepare_invoice_line_vals(**kwargs)

    # Optional: forward a common action (smart button)
    def action_open_pricelist_items(self):
        self.ensure_one()
        return self.catalog_id.action_open_pricelist_items()

    # Convenience: open underlying catalog record
    def action_open_catalog_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Catalog Record"),
            "res_model": "clinic.treatment.catalog",
            "res_id": self.catalog_id.id,
            "view_mode": "form",
        }

    # -------------------------------------------------------------------------
    # NAME GET / SEARCH (delegate to catalog for consistent UX)
    # -------------------------------------------------------------------------
    @api.depends("catalog_id.display_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.catalog_id.display_name if rec.catalog_id else _("(No Catalog)")

    def name_get(self):
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        Catalog = self.env["clinic.treatment.catalog"]
        criteria = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        cats = Catalog.search(criteria, limit=limit) if criteria else Catalog.search([], limit=limit)
        if not cats:
            return []
        pubs = self.search([("catalog_id", "in", cats.ids)] + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in pubs.sudo()]

