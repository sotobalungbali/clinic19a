# -*- coding: utf-8 -*-
# File: models/product_template.py
# Module: clinic_inventory
#
# Purpose
#   Extend product.template for aesthetic clinics:
#   - Clinical usage classification (service/consumable/medication/skincare/equipment/package)
#   - Regulatory/compliance metadata, dosage/pack info
#   - Expiration & storage handling, next-expiration helper
#   - Extensible hooks for cross-module integration (doctor/treatment/pricing/membership/eCommerce/billing)
#
# Integration Strategy
#   - No hard depends on other clinic_* modules here to avoid circular deps.
#   - Bridge addons (e.g., clinic_inventory_treatment_bridge) may override the *_hook_* methods
#     and add fields/relations to their own models.
#
# Conventions
#   - All user-facing texts (field labels, help, error messages) are in English.
#   - Computed flags help downstream logic (UI filters, security, reporting).
#   - Keep business rules sane for stock/tracking/expiration alignment.

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # =========================================================================
    # Core clinical classification
    # =========================================================================
    usage_type = fields.Selection(
        selection=[
            ("medical", "Medical Consumable"),
            ("cosmetic", "Cosmetic Product"),
            ("device", "Medical Device / Equipment"),
            ("package", "Treatment Package / Bundle"),
            ("service", "Service (Non-Stock)"),
            ("retail", "Retail Merchandise"),
        ],
        string="Usage Type",
        default=False,
        help=(
            "Optional ClinicOne classification. Leave empty for ordinary Odoo products. "
            "Classifies how this product is used in the clinic workflow. "
            "It affects FEFO checks, expiry policies, treatment consumption, "
            "and which locations (pharmacy/treatment rooms) are relevant."
        ),
        tracking=True,
    )


    # Convenience flags
    is_medication = fields.Boolean(
        string="Is Medication",
        compute="_compute_flags",
        store=True,
        help="True when Clinic Usage Type is 'Medication / Drug'.",
    )
    is_cosmetic = fields.Boolean(
        string="Is Skincare/Cosmetic",
        compute="_compute_flags",
        store=True,
        help="True when Clinic Usage Type is 'Skincare / Cosmetic'.",
    )
    is_service_flag = fields.Boolean(
        string="Is Service",
        compute="_compute_flags",
        store=True,
        help="True when product is a 'Service' or 'Treatment Package'.",
    )
    is_stockable_flag = fields.Boolean(
        string="Is Stock-Tracked",
        compute="_compute_flags",
        store=True,
        help="True for stock-tracked goods (consumable/equipment/medication/skincare).",
    )

    # =========================================================================
    # Brand & regulatory metadata
    # =========================================================================
    brand_partner_id = fields.Many2one(
        "res.partner",
        string="Brand / Manufacturer",
        domain=[("is_company", "=", True)],
        tracking=True,
        help="Brand owner or manufacturer (company partner).",
    )

    regulatory_class = fields.Selection(
        selection=[
            ("cosmetic", "Cosmetic"),
            ("med_dev_class_i", "Medical Device Class I"),
            ("med_dev_class_iia", "Medical Device Class IIa"),
            ("med_dev_class_iib", "Medical Device Class IIb"),
            ("med_dev_class_iii", "Medical Device Class III"),
            ("drug_otc", "Drug - OTC"),
            ("drug_rx", "Drug - Prescription"),
        ],
        string="Regulatory Classification",
        tracking=True,
        help="High-level regulatory classification used for compliance and reporting.",
    )

    # =========================================================================
    # Pharmaceutical / cosmetic specifics
    # =========================================================================
    dosage_form = fields.Selection(
        selection=[
            ("cream", "Cream"),
            ("gel", "Gel"),
            ("lotion", "Lotion"),
            ("serum", "Serum"),
            ("solution", "Solution"),
            ("spray", "Spray"),
            ("tablet", "Tablet"),
            ("capsule", "Capsule"),
            ("injection", "Injection"),
            ("other", "Other"),
        ],
        string="Dosage Form",
        tracking=True,
        help="Pharmaceutical/cosmetic form used in practice or retail.",
    )
    active_ingredients = fields.Char(
        string="Active Ingredients",
        tracking=True,
        help="List of active ingredients (comma-separated or short description).",
    )
    dosage_strength = fields.Char(
        string="Dosage Strength",
        tracking=True,
        help="Strength (e.g., '2%', '500 mg', '10 mg/mL').",
    )
    volume_ml = fields.Float(
        string="Volume (mL)",
        digits="Product Unit of Measure",
        tracking=True,
        help="Primary pack volume in milliliters, if applicable.",
    )
    weight_g = fields.Float(
        string="Weight (g)",
        digits="Product Unit of Measure",
        tracking=True,
        help="Primary pack weight in grams, if applicable.",
    )

    # =========================================================================
    # Expiration & storage controls
    # =========================================================================
    has_expiration = fields.Boolean(
        string="Has Expiration",
        tracking=True,
        help="Enable shelf-life tracking and expiry alerts for this product.",
    )
    shelf_life_days = fields.Integer(
        string="Shelf Life (Days)",
        tracking=True,
        help="Expected shelf life from receipt/manufacture to end-of-life.",
    )
    expiration_alert_days = fields.Integer(
        string="Expiration Alert (Days)",
        tracking=True,
        help="Days before expiration to trigger alert/notification.",
    )
    storage_requirement = fields.Selection(
        selection=[
            ("room", "Room Temperature"),
            ("chilled", "Refrigerated (2–8°C)"),
            ("frozen", "Frozen"),
        ],
        string="Storage Requirement",
        tracking=True,
        help="Recommended storage condition.",
    )
    storage_min_c = fields.Float(
        string="Min Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Minimum recommended storage temperature in Celsius.",
    )
    storage_max_c = fields.Float(
        string="Max Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Maximum recommended storage temperature in Celsius.",
    )

    next_expiration_date = fields.Date(
        string="Next Expiration Date",
        compute="_compute_next_expiration_date",
        store=False,
        help=(
            "Earliest upcoming lot/serial end-of-life date across all variants with on-hand quantity. "
            "Requires Stock Expiration features to be installed."
        ),
    )

    # =========================================================================
    # Safety & usage guidance
    # =========================================================================
    contraindications = fields.Text(
        string="Contraindications / Warnings",
        tracking=True,
        help="Important safety notes, contraindications, precautions, or usage warnings.",
    )
    instructions = fields.Text(
        string="Usage Instructions",
        tracking=True,
        help="Instructions for use during treatment or patient home-care.",
    )

    # =========================================================================
    # eCommerce / Membership policies (no hard dependency)
    # =========================================================================
    membership_pricing_policy = fields.Selection(
        selection=[
            ("none", "No Membership Pricing"),
            ("member_only", "Member-only Pricing"),
            ("tiered", "Tiered by Membership Level"),
            ("coupon_required", "Coupon Required"),
        ],
        string="Membership Pricing Policy",
        default="none",
        tracking=True,
        help=(
            "How membership affects pricing for this product in POS/eCommerce/Billing. "
            "Actual pricing rules are implemented by Pricing/Membership/POS modules via hooks."
        ),
    )
    ecommerce_is_sellable = fields.Boolean(
        string="Sellable on eCommerce",
        default=False,
        tracking=True,
        help="If enabled, the product can be listed/sold in the online store.",
    )

    # =========================================================================
    # Auxiliary
    # =========================================================================
    additional_barcodes = fields.Char(
        string="Additional Barcodes",
        tracking=True,
        help="Optional comma-separated extra barcodes for scanning convenience.",
    )

    # =========================================================================
    # SQL Constraints
    # =========================================================================
    _default_code_unique = models.Constraint(
        "UNIQUE(default_code)",
        "Internal Reference (SKU) must be unique.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.constrains("usage_type", "type", "is_storable")
    def _check_usage_type_vs_type(self):
        """Keep ClinicOne classification aligned with Odoo 19 stock semantics."""
        for rec in self:
            if rec.usage_type == "device" and (rec.type != "consu" or not rec.is_storable):
                raise ValidationError(_("Medical devices must be configured as inventory-tracked goods."))

    @api.depends("usage_type", "type", "is_storable")
    def _compute_flags(self):
        """Expose stable convenience flags from the existing ClinicOne usage taxonomy."""
        for rec in self:
            rec.is_medication = rec.usage_type == "medical"
            rec.is_cosmetic = rec.usage_type == "cosmetic"
            rec.is_service_flag = rec.usage_type in ("service", "package")
            rec.is_stockable_flag = rec.type == "consu" and rec.is_storable

    def _get_expiration_field_name(self):
        """Return the lot field used as product's end-of-life date."""
        lot = self.env["stock.lot"]
        # Odoo Stock Expiration commonly uses 'life_date'
        if "life_date" in lot._fields:
            return "life_date"
        # Fallbacks if different naming is present
        if "expiration_date" in lot._fields:
            return "expiration_date"
        return None

    @api.depends("product_variant_ids")
    def _compute_next_expiration_date(self):
        Lot = self.env["stock.lot"]
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for rec in self:
            next_date = False
            if exp_field and rec.product_variant_ids:
                lots = Lot.search([
                    ("product_id", "in", rec.product_variant_ids.ids),
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
            rec.next_expiration_date = next_date

    # =========================================================================
    # ONCHANGE RULES
    # =========================================================================
    @api.onchange("usage_type")
    def _onchange_usage_type(self):
        """Map the existing ClinicOne usage taxonomy to Odoo 19 product stock fields."""
        for rec in self:
            if rec.usage_type in ("service", "package"):
                rec.type = "service"
                rec.is_storable = False
                rec.tracking = "none"
                rec.has_expiration = False
            elif rec.usage_type == "medical":
                rec.type = "consu"
                rec.is_storable = True
                if rec.tracking in (False, "none"):
                    rec.tracking = "lot"
                rec.has_expiration = True
                if not rec.expiration_alert_days:
                    rec.expiration_alert_days = 90
            elif rec.usage_type == "cosmetic":
                rec.type = "consu"
                rec.is_storable = True
                if rec.tracking in (False, "none"):
                    rec.tracking = "lot"
                rec.has_expiration = True
            elif rec.usage_type == "device":
                rec.type = "consu"
                rec.is_storable = True
                if rec.tracking in (False, "none", "lot"):
                    rec.tracking = "serial"
                rec.has_expiration = False
            elif rec.usage_type == "retail":
                rec.type = "consu"
                rec.is_storable = True

    @api.onchange("has_expiration")
    def _onchange_has_expiration(self):
        for rec in self:
            if rec.has_expiration and rec.tracking in (False, "none"):
                rec.tracking = "lot"
            if not rec.has_expiration:
                rec.shelf_life_days = 0
                rec.expiration_alert_days = 0

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    @api.constrains("storage_min_c", "storage_max_c")
    def _check_storage_temperature(self):
        for rec in self:
            if rec.storage_min_c and rec.storage_max_c and rec.storage_min_c > rec.storage_max_c:
                raise ValidationError(_("Minimum storage temperature cannot exceed maximum storage temperature."))

    @api.constrains("has_expiration", "shelf_life_days", "type")
    def _check_expiration_rules(self):
        for rec in self:
            if rec.type == "service" and rec.has_expiration:
                raise ValidationError(_("Services cannot be configured with expiration tracking."))
            if rec.has_expiration and (rec.shelf_life_days is None or rec.shelf_life_days <= 0):
                raise ValidationError(_("Shelf Life (Days) must be a positive integer when expiration tracking is enabled."))

    @api.constrains("usage_type", "type", "is_storable")
    def _check_usage_type_vs_product_type(self):
        for rec in self:
            # ClinicOne rules are opt-in. Native Odoo products (including demo data
            # from modules such as project_purchase) must keep their own product
            # semantics when no Clinic Usage Type has been explicitly assigned.
            if not rec.usage_type:
                continue
            if rec.usage_type in ("service", "package") and rec.type != "service":
                raise ValidationError(_("Treatment packages and services must use Product Type = Service."))
            if rec.usage_type in ("medical", "cosmetic", "device", "retail"):
                if rec.type != "consu" or not rec.is_storable:
                    raise ValidationError(_("Clinical goods must use Odoo 19 inventory-tracked Goods configuration."))

    # =========================================================================
    # WRITE-AUDIT & TRACKING
    # =========================================================================
    def write(self, vals):
        tracked = {"usage_type", "has_expiration", "tracking", "storage_requirement"}
        before = {r.id: {k: getattr(r, k) for k in tracked} for r in self}
        res = super().write(vals)
        for rec in self:
            after = {k: getattr(rec, k) for k in tracked}
            if before.get(rec.id) != after:
                changes = []
                for k in sorted(tracked):
                    if before[rec.id].get(k) != after.get(k):
                        changes.append(f"{k}: {before[rec.id].get(k)} → {after.get(k)}")
                if changes:
                    rec.message_post(body=_("Clinic product settings updated: %s") % ", ".join(changes))
            # Hook for bridge modules to react on write
            rec._clinic_hook_post_write(vals)
        return res

    # =========================================================================
    # ACTIONS (UI helpers)
    # =========================================================================
    def action_view_expiring_lots(self):
        """Open lots nearing expiration for this product template."""
        self.ensure_one()
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            raise UserError(_("No expiration field available on lots. Please install the Stock Expiration feature."))

        action = self.env.ref("stock.action_production_lot_form").read()[0]
        action["domain"] = [
            ("product_id", "in", self.product_variant_ids.ids),
            (exp_field, "!=", False),
        ]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    def action_view_stock_moves(self):
        """Open stock moves related to this product template."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("product_id", "in", self.product_variant_ids.ids)]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    # =========================================================================
    # NAME & DISPLAY
    # =========================================================================
    @api.depends("name", "default_code", "usage_type", "dosage_strength")
    def _compute_display_name(self):
        """Extend Odoo 19 product labels with ClinicOne dosage strength."""
        super()._compute_display_name()
        for rec in self:
            if rec.usage_type in ("medical", "cosmetic") and rec.dosage_strength:
                rec.display_name = f"{rec.display_name} ({rec.dosage_strength})"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    # =========================================================================
    # HOOKS for Cross-Module Integrations (override in bridge addons)
    # =========================================================================
    def _clinic_hook_is_doctor_allowed(self, doctor):
        """Return True if the given doctor is allowed to use/prescribe this product.

        Arguments:
            doctor: record of model provided by clinic_doctor (e.g., 'clinic.doctor').

        Default behavior:
            - Always True (no restriction).
        Bridge addons may override to enforce allowlists/role-based rules.
        """
        self.ensure_one()
        return True

    def _clinic_hook_allowed_treatments(self):
        """Return recordset of treatments where this product is allowed/typical.

        Default behavior:
            - Return an empty recordset. A bridge can override to return 'clinic.treatment' records.
        """
        return self.env[self._clinic_hook_treatment_model_name()].browse([])

    def _clinic_hook_treatment_model_name(self):
        """Name of treatment model (to be defined by treatment module)."""
        # Bridge addons override to return something like "clinic.treatment".
        return "ir.ui.view"  # dummy model to keep a valid env reference

    def _clinic_hook_membership_price(self, partner, pricelist=None, quantity=1.0, date_order=None, uom=None, **kwargs):
        """Return a membership-adjusted unit price or None to fallback to standard pricing.

        Bridges (membership/pricing) can inject tiered/member/coupon logic here.
        """
        return None

    def _clinic_hook_pricing_context(self, partner=None, **kwargs):
        """Return extra pricing context dict for pricelist engine (POS/eCommerce/Sales)."""
        return {}

    def _clinic_hook_is_sellable_online(self):
        """Decide if product is sellable online considering global/portal rules."""
        # Base decision: checkbox on the product itself.
        return bool(self.ecommerce_is_sellable)

    def _clinic_hook_prepare_consumption_vals(self, qty, uom=None, treatment=None, patient=None, location=None, **kwargs):
        """Prepare values for a stock move/scrap to represent clinical consumption.

        Bridges can enrich (e.g., link to treatment/patient, analytic tags, cost centers).
        """
        self.ensure_one()
        product = self.product_variant_id
        return {
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": (uom or product.uom_id).id,
            "name": _("Clinical consumption of %s") % (self.display_name,),
        }

    def _clinic_hook_post_write(self, vals):
        """Post-write hook for bridges (e.g., invalidate caches, sync mappings)."""
        return

    # =========================================================================
    # SERVICE APIS (callable by other modules; bridges may override/extend)
    # =========================================================================
    def clinic_is_sellable_online(self):
        """Public API used by portal/eCommerce/marketing modules."""
        self.ensure_one()
        return self._clinic_hook_is_sellable_online()

    def clinic_get_membership_price(self, partner, pricelist=None, quantity=1.0, date_order=None, uom=None, **kwargs):
        """Public API to compute membership price if any; returns None for default engine."""
        self.ensure_one()
        return self._clinic_hook_membership_price(
            partner=partner,
            pricelist=pricelist,
            quantity=quantity,
            date_order=date_order,
            uom=uom,
            **kwargs,
        )

    def clinic_get_pricing_context(self, partner=None, **kwargs):
        """Public API to provide extra pricing context."""
        self.ensure_one()
        base = {
            "uom": kwargs.get("uom") or self.uom_id,
            "date": kwargs.get("date_order"),
            "quantity": kwargs.get("quantity", 1.0),
        }
        base.update(self._clinic_hook_pricing_context(partner=partner, **kwargs))
        return base

    def clinic_prepare_consumption_move_vals(self, qty, uom=None, treatment=None, patient=None, location=None, **kwargs):
        """Public API to prepare stock move values for clinical consumption."""
        self.ensure_one()
        vals = self._clinic_hook_prepare_consumption_vals(
            qty=qty, uom=uom, treatment=treatment, patient=patient, location=location, **kwargs
        )
        # Ensure minimal required keys exist; let bridges add links/analytics
        required_keys = {"product_id", "product_uom_qty", "product_uom", "name"}
        missing = required_keys - set(vals.keys())
        if missing:
            raise UserError(_("Consumption move is missing required keys: %s") % ", ".join(sorted(missing)))
        return vals

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def clinic_validate_usage_for_operation(self, operation="consume"):
        """Basic guardrails that can be reused by treatment/doctor modules."""
        self.ensure_one()
        if operation == "consume" and (self.is_service_flag or self.type == "service"):
            raise UserError(_("Services cannot be consumed from stock. Please choose a stock-tracked product."))

    # =========================================================================
    # SEARCH HELPERS (useful for filters & domains)
    # =========================================================================
    @api.model
    def clinic_domain_expiring_soon(self, within_days=30):
        """Return domain to filter products having any lot expiring within 'within_days'."""
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            return [("id", "=", 0)]  # no expiration tracking available
        # We do not compute exact dates here; bridges may add company-specific logic
        return [("has_expiration", "=", True)]

