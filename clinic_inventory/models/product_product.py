# -*- coding: utf-8 -*-
# File: models/product_product.py
# Module: clinic_inventory
#
# Purpose
#   Extend product.product (variant) for aesthetic clinics:
#   - Expose clinic-specific attributes from product.template via related, stored fields
#   - Per-variant "Next Expiration Date" based on existing lots/serials with quantity
#   - Convenience stock metrics for clinic locations (room/pharmacy) via hooks
#   - Public service APIs and hook points for cross-module integrations (doctor/treatment/pricing/membership/eCommerce/Billing)
#
# Integration Strategy
#   - No hard dependency on other clinic_* modules to avoid circular deps.
#   - Bridge addons (e.g., clinic_inventory_treatment_bridge) can override hook methods
#     to inject links, analytics, validation, pricing, membership, etc.
#
# Conventions
#   - All user-facing texts (field labels, help, error messages) are in English.
#   - Related fields to product.template are stored for easier domain/search/reporting.

from datetime import date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    # =========================================================================
    # Mirror core classification & metadata from product.template (related + store)
    # =========================================================================
    
    usage_type = fields.Selection(
        related="product_tmpl_id.usage_type",
        string="Usage Type",
        store=True,          # simpan di varian agar mudah difilter/report
        readonly=False,      # dapat diedit di varian -> akan menulis ke template
    )
    is_medication = fields.Boolean(
        related="product_tmpl_id.is_medication",
        string="Is Medication",
        store=True,
        readonly=True,
    )
    is_cosmetic = fields.Boolean(
        related="product_tmpl_id.is_cosmetic",
        string="Is Skincare/Cosmetic",
        store=True,
        readonly=True,
    )
    is_service_flag = fields.Boolean(
        related="product_tmpl_id.is_service_flag",
        string="Is Service",
        store=True,
        readonly=True,
    )
    is_stockable_flag = fields.Boolean(
        related="product_tmpl_id.is_stockable_flag",
        string="Is Stock-Tracked",
        store=True,
        readonly=True,
    )

    brand_partner_id = fields.Many2one(
        related="product_tmpl_id.brand_partner_id",
        string="Brand / Manufacturer",
        store=True,
        readonly=True,
    )
    regulatory_class = fields.Selection(
        related="product_tmpl_id.regulatory_class",
        string="Regulatory Classification",
        store=True,
        readonly=True,
    )

    dosage_form = fields.Selection(
        related="product_tmpl_id.dosage_form",
        string="Dosage Form",
        store=True,
        readonly=True,
    )
    active_ingredients = fields.Char(
        related="product_tmpl_id.active_ingredients",
        string="Active Ingredients",
        store=True,
        readonly=True,
    )
    dosage_strength = fields.Char(
        related="product_tmpl_id.dosage_strength",
        string="Dosage Strength",
        store=True,
        readonly=True,
    )
    volume_ml = fields.Float(
        related="product_tmpl_id.volume_ml",
        string="Volume (mL)",
        store=True,
        readonly=True,
    )
    weight_g = fields.Float(
        related="product_tmpl_id.weight_g",
        string="Weight (g)",
        store=True,
        readonly=True,
    )

    has_expiration = fields.Boolean(
        related="product_tmpl_id.has_expiration",
        string="Has Expiration",
        store=True,
        readonly=True,
    )
    shelf_life_days = fields.Integer(
        related="product_tmpl_id.shelf_life_days",
        string="Shelf Life (Days)",
        store=True,
        readonly=True,
    )
    expiration_alert_days = fields.Integer(
        related="product_tmpl_id.expiration_alert_days",
        string="Expiration Alert (Days)",
        store=True,
        readonly=True,
    )
    storage_requirement = fields.Selection(
        related="product_tmpl_id.storage_requirement",
        string="Storage Requirement",
        store=True,
        readonly=True,
    )
    storage_min_c = fields.Float(
        related="product_tmpl_id.storage_min_c",
        string="Min Temp (°C)",
        store=True,
        readonly=True,
    )
    storage_max_c = fields.Float(
        related="product_tmpl_id.storage_max_c",
        string="Max Temp (°C)",
        store=True,
        readonly=True,
    )

    contraindications = fields.Text(
        related="product_tmpl_id.contraindications",
        string="Contraindications / Warnings",
        store=True,
        readonly=True,
    )
    instructions = fields.Text(
        related="product_tmpl_id.instructions",
        string="Usage Instructions",
        store=True,
        readonly=True,
    )

    membership_pricing_policy = fields.Selection(
        related="product_tmpl_id.membership_pricing_policy",
        string="Membership Pricing Policy",
        store=True,
        readonly=True,
    )
    ecommerce_is_sellable = fields.Boolean(
        related="product_tmpl_id.ecommerce_is_sellable",
        string="Sellable on eCommerce",
        store=True,
        readonly=True,
    )
    additional_barcodes = fields.Char(
        related="product_tmpl_id.additional_barcodes",
        string="Additional Barcodes",
        store=True,
        readonly=True,
    )

    # =========================================================================
    # Variant-level expiration snapshot
    # =========================================================================
    next_expiration_date_variant = fields.Date(
        string="Next Expiration Date (Variant)",
        compute="_compute_next_expiration_date_variant",
        store=False,
        help=(
            "Earliest upcoming lot/serial end-of-life date for THIS variant only, "
            "considering lots with on-hand quantity."
        ),
    )

    # =========================================================================
    # Convenience stock metrics for clinic locations (hook-driven)
    # =========================================================================
    clinic_onhand_qty = fields.Float(
        string="On Hand (Clinic Locations)",
        compute="_compute_clinic_stock_metrics",
        store=False,
        help="Available on-hand quantity across clinic internal locations (rooms/pharmacy) per hook.",
    )
    clinic_incoming_qty = fields.Float(
        string="Incoming (Clinic Locations)",
        compute="_compute_clinic_stock_metrics",
        store=False,
        help="Incoming quantity to clinic internal locations per hook.",
    )
    clinic_outgoing_qty = fields.Float(
        string="Outgoing (Clinic Locations)",
        compute="_compute_clinic_stock_metrics",
        store=False,
        help="Outgoing quantity from clinic internal locations per hook.",
    )

    # Optional per-variant reorder/thresholds (used by alerts/dashboards)
    clinic_min_qty = fields.Float(
        string="Clinic Min Qty",
        help="Minimum desired quantity across clinic locations for this variant. Used by replenishment alerts.",
        digits="Product Unit of Measure",
    )
    clinic_target_qty = fields.Float(
        string="Clinic Target Qty",
        help="Target quantity across clinic locations for this variant. Used by replenishment proposals.",
        digits="Product Unit of Measure",
    )

    # =========================================================================
    # Helpers to locate expiration field on stock.lot
    # =========================================================================
    def _get_expiration_field_name(self):
        lot = self.env["stock.lot"]
        if "life_date" in lot._fields:
            return "life_date"
        if "expiration_date" in lot._fields:
            return "expiration_date"
        return None

    # =========================================================================
    # COMPUTES
    # =========================================================================
    # @api.depends("id")
    def _compute_next_expiration_date_variant(self):
        """Compute earliest future expiration date across lots with positive on-hand for this variant."""
        Lot = self.env["stock.lot"]
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for rec in self:
            next_date = False
            if exp_field:
                lots = Lot.search([
                    ("product_id", "=", rec.id),
                    (exp_field, "!=", False),
                    ("product_qty", ">", 0.0),
                ], limit=2000)
                future_dates = [
                    getattr(l, exp_field)
                    for l in lots
                    if getattr(l, exp_field) and getattr(l, exp_field) >= today
                ]
                if future_dates:
                    next_date = min(future_dates)
            rec.next_expiration_date_variant = next_date

    @api.depends("qty_available", "incoming_qty", "outgoing_qty")
    def _compute_clinic_stock_metrics(self):
        """Compute on-hand/incoming/outgoing restricted to clinic internal locations via hook domain."""
        Quant = self.env["stock.quant"]
        for rec in self:
            domain = [("product_id", "=", rec.id)]
            # Let hooks supply location domain for clinic internal locations
            domain_loc = rec._clinic_hook_quant_location_domain()
            if domain_loc:
                domain += domain_loc
            # Aggregate quants for onhand
            qty = 0.0
            for q in Quant.read_group(domain, ["quantity:sum"], ["product_id"]):
                qty += q.get("quantity", 0.0) or 0.0
            rec.clinic_onhand_qty = qty

            # Incoming/outgoing approximations via moves if hooks provide domains
            inc_domain, out_domain = rec._clinic_hook_move_domains_for_location_scope()
            Move = self.env["stock.move"]
            incoming = 0.0
            outgoing = 0.0
            if inc_domain:
                for r in Move.read_group(inc_domain + [("product_id", "=", rec.id)], ["product_uom_qty:sum"], []):
                    incoming += r.get("product_uom_qty", 0.0) or 0.0
            if out_domain:
                for r in Move.read_group(out_domain + [("product_id", "=", rec.id)], ["product_uom_qty:sum"], []):
                    outgoing += r.get("product_uom_qty", 0.0) or 0.0
            rec.clinic_incoming_qty = incoming
            rec.clinic_outgoing_qty = outgoing

    # =========================================================================
    # ACTIONS (UI helpers)
    # =========================================================================
    def action_view_expiring_lots(self):
        """Open lots nearing expiration for this variant."""
        self.ensure_one()
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            raise UserError(_("No expiration field available on lots. Please install the Stock Expiration feature."))
        action = self.env.ref("stock.action_production_lot_form").read()[0]
        action["domain"] = [
            ("product_id", "=", self.id),
            (exp_field, "!=", False),
        ]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    def action_view_stock_moves(self):
        """Open stock moves related to this variant."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("product_id", "=", self.id)]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    # =========================================================================
    # NAME & DISPLAY
    # =========================================================================
    @api.depends("name", "default_code", "usage_type", "dosage_strength")
    def _compute_display_name(self):
        """Extend Odoo 19 variant labels with ClinicOne dosage strength."""
        super()._compute_display_name()
        for rec in self:
            if rec.usage_type in ("medical", "cosmetic") and rec.dosage_strength:
                rec.display_name = f"{rec.display_name} ({rec.dosage_strength})"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    # =========================================================================
    # PUBLIC SERVICE APIS (variant-level) — bridge addons can override
    # =========================================================================
    def clinic_is_sellable_online(self):
        """Public API used by portal/eCommerce/marketing modules."""
        self.ensure_one()
        return self.product_tmpl_id.clinic_is_sellable_online()

    def clinic_get_membership_price(self, partner, pricelist=None, quantity=1.0, date_order=None, uom=None, **kwargs):
        """Public API to compute membership price if any; returns None for default engine."""
        self.ensure_one()
        return self.product_tmpl_id.clinic_get_membership_price(
            partner=partner, pricelist=pricelist, quantity=quantity, date_order=date_order, uom=uom, **kwargs
        )

    def clinic_get_pricing_context(self, partner=None, **kwargs):
        """Public API to provide extra pricing context (delegated to template)."""
        self.ensure_one()
        # Ensure UoM is variant's uom_id by default
        base_kwargs = {"uom": kwargs.get("uom") or self.uom_id, **kwargs}
        return self.product_tmpl_id.clinic_get_pricing_context(partner=partner, **base_kwargs)

    def clinic_prepare_consumption_move_vals(self, qty, uom=None, treatment=None, patient=None, location=None, **kwargs):
        """Prepare stock move vals for clinical consumption of THIS variant."""
        self.ensure_one()
        # Get template-prepared defaults, then override product-specific keys
        vals = self.product_tmpl_id.clinic_prepare_consumption_move_vals(
            qty=qty, uom=uom or self.uom_id, treatment=treatment, patient=patient, location=location, **kwargs
        )
        vals.update({
            "product_id": self.id,
            "product_uom": (uom or self.uom_id).id,
            "name": vals.get("name") or _("Clinical consumption of %s") % (self.display_name,),
        })
        # Hooks may further adjust
        vals = self._clinic_hook_finalize_consumption_vals(vals, treatment=treatment, patient=patient, location=location, **kwargs)
        # Sanity check
        required_keys = {"product_id", "product_uom_qty", "product_uom", "name"}
        missing = required_keys - set(vals.keys())
        if missing:
            raise UserError(_("Consumption move is missing required keys: %s") % ", ".join(sorted(missing)))
        return vals

    def clinic_validate_usage_for_operation(self, operation="consume"):
        """Basic guardrails reused by treatment/doctor modules (variant-level)."""
        self.ensure_one()
        self.product_tmpl_id.clinic_validate_usage_for_operation(operation=operation)

    # =========================================================================
    # SEARCH HELPERS
    # =========================================================================
    @api.model
    def clinic_domain_expiring_soon_by_variant(self, within_days=30):
        """Return domain for variants having lots expiring within 'within_days' (approximation)."""
        # We cannot express lot-based aggregation purely in a static domain against product.product,
        # so this is a helper that bridges may use with computed sets.
        return [("has_expiration", "=", True)]

    # =========================================================================
    # HOOKS (override in bridge addons)
    # =========================================================================
    def _clinic_hook_quant_location_domain(self):
        """Return a list domain expressing 'clinic internal locations' for quant queries.

        Default: restrict to internal usage locations (usage = 'internal').
        Bridges (room/pharmacy modules) may further restrict by parent locations or tags.
        Example return: [("location_id.usage", "=", "internal")]
        """
        return [("location_id.usage", "=", "internal")]

    def _clinic_hook_move_domains_for_location_scope(self):
        """Return incoming/outgoing move domains for clinic location scope.

        Returns:
            (incoming_domain, outgoing_domain)
        Default:
            - Incoming: to internal usage locations, not done/cancel
            - Outgoing: from internal usage locations, not done/cancel
        Bridges may refine by specific locations (treatment rooms, pharmacy).
        """
        incoming = [
            ("state", "not in", ["done", "cancel"]),
            ("location_dest_id.usage", "=", "internal"),
        ]
        outgoing = [
            ("state", "not in", ["done", "cancel"]),
            ("location_id.usage", "=", "internal"),
        ]
        return incoming, outgoing

    def _clinic_hook_finalize_consumption_vals(self, vals, treatment=None, patient=None, location=None, **kwargs):
        """Final adjustment hook for consumption move values before create.

        Bridges can add:
            - links to treatment/patient models,
            - analytic accounts/tags,
            - cost center, department, doctor info,
            - location_src/dest based on room/workflow.
        """
        return vals

    # =========================================================================
    # VALIDATIONS
    # =========================================================================
    @api.constrains("clinic_min_qty", "clinic_target_qty")
    def _check_min_target_qty(self):
        for rec in self:
            if rec.clinic_min_qty and rec.clinic_target_qty and rec.clinic_min_qty > rec.clinic_target_qty:
                raise ValidationError(_("Clinic Min Qty cannot be greater than Clinic Target Qty."))

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def clinic_has_sufficient_stock(self, required_qty=1.0, within_days=None):
        """Quick check for stock sufficiency in clinic scope.

        Args:
            required_qty (float): required quantity in product's UoM.
            within_days (int|None): if provided and product has expiration,
                consider only lots expiring after 'today + within_days'.

        Returns:
            bool
        """
        self.ensure_one()
        if self.is_service_flag or self.type == "service":
            return False  # services are not stock-tracked

        Quant = self.env["stock.quant"]
        domain = [("product_id", "=", self.id)]
        domain += self._clinic_hook_quant_location_domain()

        # Filter by expiration window if requested
        if within_days is not None and self.has_expiration:
            exp_field = self._get_expiration_field_name()
            if exp_field:
                Lot = self.env["stock.lot"]
                limit_date = date.today() + timedelta(days=max(0, within_days))
                valid_lots = Lot.search([
                    ("product_id", "=", self.id),
                    ("product_qty", ">", 0.0),
                    (exp_field, ">=", limit_date),
                ]).ids
                if valid_lots:
                    domain.append(("lot_id", "in", valid_lots))
                else:
                    return False

        qty = 0.0
        for q in Quant.read_group(domain, ["quantity:sum"], []):
            qty += q.get("quantity", 0.0) or 0.0
        return qty >= (required_qty or 0.0)

