# -*- coding: utf-8 -*-
# File: models/product_category.py
# Module: clinic_inventory
#
# Purpose
#   Extend product.category for aesthetic clinics:
#   - Category-level clinical defaults (usage type, expiration/storage/tracking)
#   - Replenishment hints for clinic internal locations
#   - Brand/manufacturer scoping at category level
#   - Stock/accounting help-text alignment; no extra hard deps beyond Odoo stock/product
#   - Hook methods for cross-module integrations (doctor/treatment/pricing/eCommerce)
#
# Notes
#   - All user-facing texts are in English as requested.
#   - Avoid circular dependencies; bridges may override *_clinic_hook_* methods.
#   - Category defaults are OPTIONAL: product-specific fields still win when filled.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ProductCategory(models.Model):
    _inherit = "product.category"

    # =========================================================================
    # Clinical defaults (applied when engineering chooses to use them)
    # =========================================================================
    # IMPORTANT:
    # Core di environment kamu belum expose 'product_tmpl_ids' di product.category.
    # Kita definisikan alias ringan ke product.template.categ_id agar
    # dependency @api.depends valid dan komputasinya stabil.
    product_tmpl_ids = fields.One2many(
        comodel_name='product.template',
        inverse_name='categ_id',
        string='Products',
        help="Products directly assigned to this category."
    )
    
    clinic_default_usage_type = fields.Selection(
        selection=[
            ("service", "Service"),
            ("consumable", "Consumable"),
            ("equipment", "Equipment / Device"),
            ("medication", "Medication / Drug"),
            ("skincare", "Skincare / Cosmetic"),
            ("package", "Treatment Package"),
        ],
        string="Default Clinic Usage Type",
        tracking=True,
        help=(
            "Optional default clinical classification suggested for products in this category.\n"
            "Engineering may apply this to new products, or mass-apply via action."
        ),
    )

    clinic_default_has_expiration = fields.Boolean(
        string="Default: Has Expiration",
        tracking=True,
        help="If set, newly created products in this category are suggested to track expiration.",
    )
    clinic_default_shelf_life_days = fields.Integer(
        string="Default: Shelf Life (Days)",
        tracking=True,
        help="Suggested shelf-life in days for products in this category.",
    )
    clinic_default_expiration_alert_days = fields.Integer(
        string="Default: Expiration Alert (Days)",
        tracking=True,
        help="Suggested pre-expiration alert threshold in days.",
    )

    clinic_default_storage_requirement = fields.Selection(
        selection=[
            ("room", "Room Temperature"),
            ("chilled", "Refrigerated (2–8°C)"),
            ("frozen", "Frozen"),
        ],
        string="Default: Storage Requirement",
        tracking=True,
        help="Suggested storage requirement for products in this category.",
    )
    clinic_default_storage_min_c = fields.Float(
        string="Default: Min Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Suggested minimum storage temperature in Celsius.",
    )
    clinic_default_storage_max_c = fields.Float(
        string="Default: Max Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Suggested maximum storage temperature in Celsius.",
    )

    clinic_default_tracking = fields.Selection(
        selection=[
            ("none", "No Tracking"),
            ("lot", "By Lots"),
            ("serial", "By Unique Serial"),
        ],
        string="Default: Lot/Serial Tracking",
        tracking=True,
        help="Suggested tracking policy for products in this category.",
    )

    clinic_default_regulatory_class = fields.Selection(
        selection=[
            ("cosmetic", "Cosmetic"),
            ("med_dev_class_i", "Medical Device Class I"),
            ("med_dev_class_iia", "Medical Device Class IIa"),
            ("med_dev_class_iib", "Medical Device Class IIb"),
            ("med_dev_class_iii", "Medical Device Class III"),
            ("drug_otc", "Drug - OTC"),
            ("drug_rx", "Drug - Prescription"),
        ],
        string="Default: Regulatory Classification",
        tracking=True,
        help="Suggested regulatory classification for products in this category.",
    )

    # =========================================================================
    # Brand / manufacturer scoping (optional governance)
    # =========================================================================
    clinic_allowed_brand_ids = fields.Many2many(
        "res.partner",
        "clinic_category_brand_rel",
        "categ_id",
        "partner_id",
        string="Allowed Brands / Manufacturers",
        domain=[("is_company", "=", True)],
        help=(
            "Optional allowlist of brands/manufacturers for QA/compliance. "
            "Bridges can enforce this during product creation/approval."
        ),
    )

    clinic_restricted_to_allowed_brands = fields.Boolean(
        string="Restrict to Allowed Brands",
        tracking=True,
        help=(
            "If enabled, only brands listed in 'Allowed Brands / Manufacturers' "
            "are considered valid for products in this category."
        ),
    )

    # =========================================================================
    # Replenishment & location hints (hook-driven usage)
    # =========================================================================
    clinic_replenishment_policy = fields.Selection(
        selection=[
            ("manual", "Manual Replenishment"),
            ("min_max", "Min/Max by Location"),
            ("auto_po", "Auto Purchase (Rules)"),
        ],
        string="Replenishment Policy",
        default="min_max",
        tracking=True,
        help=(
            "High-level replenishment strategy used by dashboards and proposals. "
            "Bridges (Purchase/Finance) can implement concrete flows."
        ),
    )

    clinic_default_min_qty = fields.Float(
        string="Default Min Qty (Clinic Scope)",
        help="Suggested minimum quantity across clinic internal locations for products in this category.",
        digits="Product Unit of Measure",
        tracking=True,
    )
    clinic_default_target_qty = fields.Float(
        string="Default Target Qty (Clinic Scope)",
        help="Suggested target quantity across clinic internal locations for products in this category.",
        digits="Product Unit of Measure",
        tracking=True,
    )

    clinic_consumption_location_id = fields.Many2one(
        "stock.location",
        string="Default Consumption Location",
        domain=[("usage", "=", "internal")],
        help=(
            "Optional default internal location representing clinical consumption "
            "(e.g., Pharmacy main, Treatment Room staging). Bridges may override resolution."
        ),
        tracking=True,
    )

    # =========================================================================
    # Analytics & counters
    # =========================================================================
    # Counter klinik: total produk (termasuk sub-kategori)
    clinic_count_products = fields.Integer(
        string='Products (#)',
        compute='_compute_clinic_counts',
        store=False,
        help="Total number of products in this category including its subcategories."
    )
    
    clinic_count_expirable = fields.Integer(
        string="# Expirable Products",
        compute="_compute_clinic_counts",
        help="Products in this category tree that enable expiration tracking.",
    )
    clinic_has_any_expirable = fields.Boolean(
        string="Has Any Expirable",
        compute="_compute_clinic_counts",
        help="True if any product in this category tree tracks expiration.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    # @api.depends("child_id", "product_tmpl_ids", "product_tmpl_ids.has_expiration")
    # def _compute_clinic_counts(self):
    #     for rec in self:
    #         # include children via child_of domain
    #         categs = self.search([("id", "child_of", rec.id)]).ids
    #         prods = self.env["product.template"].search([("categ_id", "in", categs)])
    #         rec.clinic_count_products = len(prods)
    #         expirable = prods.filtered(lambda p: p.has_expiration)
    #         rec.clinic_count_expirable = len(expirable)
    #         rec.clinic_has_any_expirable = bool(expirable)

    # (Opsional) Counter lot/kadaluarsa per kategori bisa ditambahkan jika diperlukan,
    # cukup gunakan read_group di stock.lot terhadap template di child_of kategori.

    @api.depends('product_tmpl_ids', 'child_id')
    def _compute_clinic_counts(self):
        # Gunakan search_count child_of agar menghitung seluruh sub-kategori
        Template = self.env['product.template'].sudo()
        for cat in self:
            cat.clinic_count_products = Template.search_count([('categ_id', 'child_of', cat.id)])

    # IMPORTANT GUARD:
    # Jangan redefinisi field bawaan seperti 'route_ids' di product.category.
    # Jika kamu sebelumnya punya field M2M route_ids kustom, hapus/rename agar
    # tidak tabrakan dengan core 'product.category.route_ids'.

    # =========================================================================
    # VALIDATIONS
    # =========================================================================
    @api.constrains("clinic_default_storage_min_c", "clinic_default_storage_max_c")
    def _check_default_storage_temperature(self):
        for rec in self:
            if rec.clinic_default_storage_min_c and rec.clinic_default_storage_max_c:
                if rec.clinic_default_storage_min_c > rec.clinic_default_storage_max_c:
                    raise ValidationError(_("Default minimum storage temperature cannot exceed maximum storage temperature."))

    @api.constrains("clinic_default_min_qty", "clinic_default_target_qty")
    def _check_default_min_target_qty(self):
        for rec in self:
            if rec.clinic_default_min_qty and rec.clinic_default_target_qty:
                if rec.clinic_default_min_qty > rec.clinic_default_target_qty:
                    raise ValidationError(_("Default Min Qty cannot be greater than Default Target Qty."))

    # =========================================================================
    # DEFAULTS APPLICATION API
    # =========================================================================
    def clinic_get_category_default_template_vals(self):
        """Return a dict of product.template values suggested by this category.

        This does NOT write anything by itself; intended to be used by:
          - product form onchange (categ_id) logic, or
          - mass-apply actions/wizards, or
          - bridge modules during product provisioning/import.
        """
        self.ensure_one()
        vals = {}

        # Usage type & tracking defaults.
        # Category values predate the current product.template taxonomy, so translate
        # them explicitly instead of writing an invalid selection value.
        if self.clinic_default_usage_type:
            usage_map = {
                "service": "service",
                "consumable": "retail",
                "equipment": "device",
                "medication": "medical",
                "skincare": "cosmetic",
                "package": "package",
            }
            vals["usage_type"] = usage_map[self.clinic_default_usage_type]

            if self.clinic_default_usage_type in ("service", "package"):
                vals.update({
                    "type": "service",
                    "is_storable": False,
                    "tracking": "none",
                    "has_expiration": False,
                })
            elif self.clinic_default_usage_type in ("consumable", "skincare", "medication"):
                vals.update({
                    "type": "consu",
                    "is_storable": True,
                    "tracking": "lot",
                })
            elif self.clinic_default_usage_type == "equipment":
                vals.update({
                    "type": "consu",
                    "is_storable": True,
                    "tracking": "serial",
                })

        if self.clinic_default_tracking:
            vals["tracking"] = self.clinic_default_tracking

        # Expiration & storage defaults
        if self.clinic_default_has_expiration:
            vals["has_expiration"] = True
        if self.clinic_default_shelf_life_days:
            vals["shelf_life_days"] = self.clinic_default_shelf_life_days
        if self.clinic_default_expiration_alert_days:
            vals["expiration_alert_days"] = self.clinic_default_expiration_alert_days

        if self.clinic_default_storage_requirement:
            vals["storage_requirement"] = self.clinic_default_storage_requirement
        if self.clinic_default_storage_min_c:
            vals["storage_min_c"] = self.clinic_default_storage_min_c
        if self.clinic_default_storage_max_c:
            vals["storage_max_c"] = self.clinic_default_storage_max_c

        # Regulatory default
        if self.clinic_default_regulatory_class:
            vals["regulatory_class"] = self.clinic_default_regulatory_class

        # Replenishment hints mapped onto product variants (optional)
        if self.clinic_default_min_qty:
            vals["clinic_min_qty"] = self.clinic_default_min_qty
        if self.clinic_default_target_qty:
            vals["clinic_target_qty"] = self.clinic_default_target_qty

        return vals

    def action_apply_defaults_to_products(self):
        """Apply current category defaults to all products in this category tree.

        Safe-guarded: only fills values when product fields are not explicitly set,
        and only affects known defaultable fields.
        """
        self.ensure_one()
        categs = self.search([("id", "child_of", self.id)]).ids
        products = self.env["product.template"].search([("categ_id", "in", categs)])

        default_vals = self.clinic_get_category_default_template_vals()
        if not default_vals:
            raise UserError(_("No defaults are configured on this category to apply."))

        # Only apply a subset that is safe to override when empty or obviously default
        safe_keys = {
            "usage_type",
            "type",
            "tracking",
            "has_expiration",
            "shelf_life_days",
            "expiration_alert_days",
            "storage_requirement",
            "storage_min_c",
            "storage_max_c",
            "regulatory_class",
        }
        write_count = 0
        for p in products:
            vals = {}
            for k in safe_keys:
                if k in default_vals:
                    # Fill if product side is falsy/empty or clearly default
                    cur = getattr(p, k, False)
                    if not cur:
                        vals[k] = default_vals[k]
            if vals:
                p.write(vals)
                write_count += 1

        self.message_post(body=_("Applied clinical defaults to %s product(s).") % write_count)
        return True

    # =========================================================================
    # UI ACTIONS
    # =========================================================================
    def action_view_products_expiring_soon(self):
        """Open products in this category tree that have expiration tracking enabled."""
        self.ensure_one()
        action = self.env.ref("product.product_template_action").read()[0]
        categs = self.search([("id", "child_of", self.id)]).ids
        action["domain"] = [("categ_id", "in", categs), ("has_expiration", "=", True)]
        action["context"] = {"search_default_group_by_categ_id": 1}
        return action

    # =========================================================================
    # HOOKS for Cross-Module Integrations (override in bridges)
    # =========================================================================
    def _clinic_hook_validate_brand(self, brand_partner):
        """Return True if brand is accepted for this category; False or raise to block.

        Default behavior:
            - If restriction is disabled, return True.
            - If restriction enabled and brand provided, check allowlist.
        Bridges may override for advanced rules (certifications, supplier tiers).
        """
        self.ensure_one()
        if not self.clinic_restricted_to_allowed_brands:
            return True
        if not brand_partner:
            return False
        return brand_partner in self.clinic_allowed_brand_ids

    def _clinic_hook_default_consumption_location(self):
        """Return a stock.location used as default consumption location for this category.

        Default behavior:
            - Use 'clinic_consumption_location_id' if set, else None.
        Bridges may override to pick per-room/per-warehouse locations.
        """
        self.ensure_one()
        return self.clinic_consumption_location_id

    # =========================================================================
    # PUBLIC SERVICE APIS (consumed by other modules)
    # =========================================================================
    def clinic_validate_brand(self, brand_partner):
        """Public API used by product provisioning/import to validate brand."""
        self.ensure_one()
        ok = self._clinic_hook_validate_brand(brand_partner)
        if not ok:
            raise UserError(_("Brand '%s' is not allowed for category '%s'.") % (brand_partner.display_name, self.display_name))
        return True

    def clinic_get_default_consumption_location(self):
        """Public API to resolve default consumption location for this category."""
        self.ensure_one()
        return self._clinic_hook_default_consumption_location()

