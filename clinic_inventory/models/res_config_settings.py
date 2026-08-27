# -*- coding: utf-8 -*-
# File: models/res_config_settings.py
# Module: clinic_inventory
#
# Purpose
#   Provide admin-facing configuration for Clinic Inventory:
#   - Company-scoped defaults (warehouse policies & product defaults)
#   - Global feature flags via ir.config_parameter (consumed by bridge addons)
#   - Utilities to apply defaults to warehouses and bootstrap standard locations
#
# Notes
#   - All user-facing texts are in English.
#   - Avoid hard dependencies on other clinic_* modules; use flags/hooks instead.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


# =========================================================================
# Extend Company to store multi-company-safe defaults
# =========================================================================
class ResCompany(models.Model):
    _inherit = "res.company"

    # Warehouse defaults (applied to stock.warehouse when marked as clinic warehouse)
    clinic_inventory_default_expiry_policy = fields.Selection(
        selection=[
            ("none", "No Blocking (Allow)"),
            ("warn", "Warn (Allow with Warning)"),
            ("block", "Block (Disallow Operation)"),
        ],
        string="Default Expiration Policy",
        default="warn",
        help="Default expiration handling to apply on clinic warehouses.",
    )
    clinic_inventory_default_replenishment_scope = fields.Selection(
        selection=[
            ("pharmacy_only", "Pharmacy Only"),
            ("rooms_only", "Treatment Rooms Only"),
            ("pharmacy_and_rooms", "Pharmacy and Treatment Rooms"),
        ],
        string="Default Replenishment Scope",
        default="pharmacy_and_rooms",
        help="Default scope for replenishment dashboards and suggestions.",
    )
    clinic_inventory_temperature_monitoring = fields.Boolean(
        string="Enable Temperature Monitoring by Default",
        default=False,
        help="If enabled, clinic warehouses will (by default) validate temperature readings.",
    )
    clinic_inventory_auto_create_room_locations = fields.Boolean(
        string="Auto-create Room Locations by Default",
        default=False,
        help="If enabled, bridges may auto-provision standard treatment room sublocations.",
    )
    clinic_inventory_default_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Default Clinic Warehouse",
        help="Default warehouse used by utilities and as a fallback for clinic operations.",
    )

    # Product/stock policy defaults (read by product/category/ROP helpers)
    clinic_inventory_enforce_fefo = fields.Boolean(
        string="Enforce FEFO by Default",
        default=True,
        help="Default hint to enforce FEFO removal strategy in clinic flows.",
    )
    clinic_inventory_min_shelf_life_days = fields.Integer(
        string="Default Min Remaining Shelf Life (Days)",
        default=0,
        help="Default minimum shelf-life threshold for reservation/replenishment (0 = ignore).",
    )
    clinic_inventory_default_expiration_alert_days = fields.Integer(
        string="Default Product Expiration Alert (Days)",
        default=30,
        help="Default alert threshold used on products to mark 'Expiring Soon'.",
    )
    clinic_inventory_reorder_buffer_percent = fields.Float(
        string="Default Reorder Safety Buffer (%)",
        default=0.0,
        help="Default safety buffer percentage used when suggesting replenishment.",
    )
    clinic_inventory_rounding_mode_default = fields.Selection(
        selection=[
            ("none", "No Rounding"),
            ("ceil_uom", "Ceiling to Product UoM Rounding"),
            ("floor_uom", "Floor to Product UoM Rounding"),
            ("nearest_uom", "Nearest Product UoM Rounding"),
        ],
        string="Default Reorder Rounding Mode",
        default="ceil_uom",
        help="Default rounding mode for suggested replenishment quantities.",
    )

    # Cross-module feature flags (bridges read these via ir.config_parameter OR company fields)
    clinic_inventory_enable_patient_history = fields.Boolean(
        string="Enable Patient Product History",
        default=True,
        help="If enabled, bridges may record product usage into patient history.",
    )
    clinic_inventory_enable_treatment_consumption = fields.Boolean(
        string="Enable Treatment Consumption",
        default=True,
        help="If enabled, clinic treatment flows can consume stock directly.",
    )
    clinic_inventory_allow_expired_exception = fields.Boolean(
        string="Allow Expired Lots on Exception",
        default=False,
        help="If enabled, bridges may allow expired lots with explicit approval and logging.",
    )


# =========================================================================
# ResConfigSettings UI (admin settings)
# =========================================================================
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- Company-related fields (editable in Settings; stored on res.company)
    clinic_default_warehouse_id = fields.Many2one(
        related="company_id.clinic_inventory_default_warehouse_id",
        comodel_name="stock.warehouse",
        string="Default Clinic Warehouse",
        readonly=False,
    )
    clinic_default_expiry_policy = fields.Selection(
        related="company_id.clinic_inventory_default_expiry_policy",
        readonly=False,
        string="Default Expiration Policy",
    )
    clinic_default_replenishment_scope = fields.Selection(
        related="company_id.clinic_inventory_default_replenishment_scope",
        readonly=False,
        string="Default Replenishment Scope",
    )
    clinic_enable_temperature_monitoring = fields.Boolean(
        related="company_id.clinic_inventory_temperature_monitoring",
        readonly=False,
        string="Enable Temperature Monitoring by Default",
    )
    clinic_auto_create_room_locations = fields.Boolean(
        related="company_id.clinic_inventory_auto_create_room_locations",
        readonly=False,
        string="Auto-create Room Locations by Default",
    )

    clinic_enforce_fefo = fields.Boolean(
        related="company_id.clinic_inventory_enforce_fefo",
        readonly=False,
        string="Enforce FEFO by Default",
    )
    clinic_min_shelf_life_days = fields.Integer(
        related="company_id.clinic_inventory_min_shelf_life_days",
        readonly=False,
        string="Default Min Remaining Shelf Life (Days)",
    )
    clinic_default_expiration_alert_days = fields.Integer(
        related="company_id.clinic_inventory_default_expiration_alert_days",
        readonly=False,
        string="Default Product Expiration Alert (Days)",
    )
    clinic_reorder_buffer_percent = fields.Float(
        related="company_id.clinic_inventory_reorder_buffer_percent",
        readonly=False,
        string="Default Reorder Safety Buffer (%)",
    )
    clinic_rounding_mode_default = fields.Selection(
        related="company_id.clinic_inventory_rounding_mode_default",
        readonly=False,
        string="Default Reorder Rounding Mode",
    )

    clinic_enable_patient_history = fields.Boolean(
        related="company_id.clinic_inventory_enable_patient_history",
        readonly=False,
        string="Enable Patient Product History",
    )
    clinic_enable_treatment_consumption = fields.Boolean(
        related="company_id.clinic_inventory_enable_treatment_consumption",
        readonly=False,
        string="Enable Treatment Consumption",
    )
    clinic_allow_expired_exception = fields.Boolean(
        related="company_id.clinic_inventory_allow_expired_exception",
        readonly=False,
        string="Allow Expired Lots on Exception",
    )

    # --- Global config parameters (system-wide flags; not company-specific)
    clinic_block_incoming_without_temperature = fields.Boolean(
        string="Block Incoming Without Temperature Reading",
        config_parameter="clinic_inventory.block_incoming_without_temperature",
        help="If enabled, incoming pickings will be blocked unless a receipt temperature is provided.",
    )
    clinic_quality_require_approval_for_scrap = fields.Boolean(
        string="Require Approval for Clinical Scrap",
        config_parameter="clinic_inventory.quality.require_approval_for_scrap",
        help="If enabled, scrapping (or quarantine transfer) requires an approval step from a designated role.",
    )
    clinic_portal_enable_inventory = fields.Boolean(
        string="Enable Inventory Portal",
        config_parameter="clinic_inventory.portal.enable",
        help="If enabled, exposes limited inventory info in the patient/partner portal (bridge required).",
    )

    # --- Dashboard counters (computed, read-only)
    clinic_warehouse_count = fields.Integer(
        string="Clinic Warehouses",
        compute="_compute_clinic_warehouse_count",
        help="Number of warehouses flagged as clinic warehouses in this company.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _compute_clinic_warehouse_count(self):
        Warehouse = self.env["stock.warehouse"].sudo()
        for rec in self:
            rec.clinic_warehouse_count = Warehouse.search_count([
                ("company_id", "=", rec.company_id.id),
                ("is_clinic_warehouse", "=", True),
            ])

    # =========================================================================
    # ACTIONS (utility buttons)
    # =========================================================================
    def action_apply_defaults_to_clinic_warehouses(self):
        """Apply company defaults to all clinic warehouses of this company."""
        self.ensure_one()
        company = self.company_id
        Warehouse = self.env["stock.warehouse"].sudo()
        whs = Warehouse.search([("company_id", "=", company.id), ("is_clinic_warehouse", "=", True)])
        for wh in whs:
            vals = {
                "clinic_expiry_blocking_policy": company.clinic_inventory_default_expiry_policy or "warn",
                "clinic_replenishment_scope": company.clinic_inventory_default_replenishment_scope or "pharmacy_and_rooms",
                "clinic_temperature_monitoring": bool(company.clinic_inventory_temperature_monitoring),
                "clinic_auto_create_room_locations": bool(company.clinic_inventory_auto_create_room_locations),
            }
            wh.write(vals)
        # Post feedback
        msg = _("Applied clinic inventory defaults to %s warehouse(s).") % len(whs)
        self.env.user.notify_success(message=msg)
        return True

    def action_bootstrap_clinic_locations(self):
        """Ensure standard clinic locations (Pharmacy, Treatment Root, Quarantine) exist on default warehouse.

        - Creates internal child locations under the warehouse view if missing.
        - Assigns them into warehouse fields: clinic_pharmacy_location_id, clinic_treatment_root_location_id, clinic_quarantine_location_id.
        """
        self.ensure_one()
        company = self.company_id
        wh = company.clinic_inventory_default_warehouse_id
        if not wh:
            raise UserError(_("Please set a Default Clinic Warehouse first."))

        Location = self.env["stock.location"].sudo()
        created = []

        def _ensure_loc(name, code, extra_vals=None):
            # Search by exact name under view location; if not found, create
            domain = [
                ("name", "=", name),
                ("usage", "=", "internal"),
                ("id", "child_of", wh.view_location_id.id),
            ]
            loc = Location.search(domain, limit=1)
            if not loc:
                vals = {
                    "name": name,
                    "usage": "internal",
                    "location_id": wh.view_location_id.id,
                }
                if extra_vals:
                    vals.update(extra_vals)
                loc = Location.create(vals)
                created.append(loc)
            return loc

        # Pharmacy
        pharm = wh.clinic_pharmacy_location_id or _ensure_loc(
            name=_("%s - Pharmacy") % wh.name,
            code="PHARM",
            extra_vals={"clinic_is_pharmacy": True, "clinic_location_code": "PHARM"},
        )
        # Treatment Rooms Root
        rooms = wh.clinic_treatment_root_location_id or _ensure_loc(
            name=_("%s - Treatment Rooms") % wh.name,
            code="ROOMS",
            extra_vals={"clinic_is_treatment_room": False, "clinic_location_code": "ROOMS"},
        )
        # Quarantine
        quarant = wh.clinic_quarantine_location_id or _ensure_loc(
            name=_("%s - Quarantine") % wh.name,
            code="QUAR",
            extra_vals={"clinic_is_quarantine": True, "clinic_location_code": "QUAR"},
        )

        # Assign to warehouse if not set
        updates = {}
        if not wh.clinic_pharmacy_location_id and pharm:
            updates["clinic_pharmacy_location_id"] = pharm.id
        if not wh.clinic_treatment_root_location_id and rooms:
            updates["clinic_treatment_root_location_id"] = rooms.id
        if not wh.clinic_quarantine_location_id and quarant:
            updates["clinic_quarantine_location_id"] = quarant.id
        if updates:
            wh.write(updates)

        # Notify result
        txt = []
        if created:
            txt.append(_("Created %s new location(s).") % len(created))
        txt.append(_("Clinic locations are set on warehouse '%s'.") % wh.display_name)
        self.env.user.notify_success(message=" ".join(txt))
        return True

    def action_apply_product_defaults(self):
        """Apply product-level defaults (alert days) to existing products without explicit values."""
        self.ensure_one()
        Product = self.env["product.template"].sudo()
        company = self.company_id
        alert_days = int(company.clinic_inventory_default_expiration_alert_days or 0)
        if alert_days <= 0:
            raise UserError(_("Default Product Expiration Alert (Days) must be greater than zero."))

        # Only update those with has_expiration=True and empty alert value
        prods = Product.search([("has_expiration", "=", True), "|", ("expiration_alert_days", "=", 0), ("expiration_alert_days", "=", False)])
        count = 0
        for p in prods:
            p.write({"expiration_alert_days": alert_days})
            count += 1
        self.env.user.notify_success(message=_("Applied expiration alert days to %s product(s).") % count)
        return True

    # =========================================================================
    # OPTIONAL: override set_values to mirror some company flags into config params
    # (kept minimal; config_parameter fields are handled automatically by Odoo)
    # =========================================================================
    def set_values(self):
        res = super().set_values()
        # Mirror a few company flags to ir.config_parameter for bridges that don't read company fields
        ICP = self.env["ir.config_parameter"].sudo()
        for rec in self:
            ICP.set_param("clinic_inventory.allow_expired_exception", "1" if rec.clinic_allow_expired_exception else "0")
            ICP.set_param("clinic_inventory.enforce_fefo_default", "1" if rec.clinic_enforce_fefo else "0")
            ICP.set_param("clinic_inventory.min_shelf_life_days_default", str(int(rec.clinic_min_shelf_life_days or 0)))
        return res

    # =========================================================================
    # SUPPORT: convenience getters for bridges
    # =========================================================================
    @api.model
    def clinic_get_company_defaults(self, company=None):
        """Return a dict of clinic inventory defaults for the given or current company."""
        company = company or self.env.company
        return {
            "expiry_policy": company.clinic_inventory_default_expiry_policy,
            "replenishment_scope": company.clinic_inventory_default_replenishment_scope,
            "temperature_monitoring": bool(company.clinic_inventory_temperature_monitoring),
            "auto_create_rooms": bool(company.clinic_inventory_auto_create_room_locations),
            "default_warehouse_id": company.clinic_inventory_default_warehouse_id.id if company.clinic_inventory_default_warehouse_id else False,
            "enforce_fefo": bool(company.clinic_inventory_enforce_fefo),
            "min_shelf_life_days": int(company.clinic_inventory_min_shelf_life_days or 0),
            "prod_exp_alert_days": int(company.clinic_inventory_default_expiration_alert_days or 0),
            "reorder_buffer_percent": float(company.clinic_inventory_reorder_buffer_percent or 0.0),
            "rounding_mode": company.clinic_inventory_rounding_mode_default,
            "enable_patient_history": bool(company.clinic_inventory_enable_patient_history),
            "enable_treatment_consumption": bool(company.clinic_inventory_enable_treatment_consumption),
            "allow_expired_exception": bool(company.clinic_inventory_allow_expired_exception),
        }

