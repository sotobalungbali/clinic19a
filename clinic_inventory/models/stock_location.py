# -*- coding: utf-8 -*-
# File: models/stock_location.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.location for aesthetic clinics:
#   - Flags for treatment rooms/pharmacy/quarantine and room metadata
#   - Location-level temperature thresholds & expiration policy
#   - Category allowlist to restrict what products can be stored/consumed here
#   - Warehouse resolution & clinic-scoped stock counters
#   - UI actions to navigate quants/moves/pickings for this location
#   - Hook methods for cross-module integrations (room-device, treatment, IoT, pricing, etc.)
#
# Notes
#   - All user-facing texts are in English (fields, help, errors).
#   - No hard dependency on other clinic_* modules; bridges may override *_clinic_hook_* methods.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockLocation(models.Model):
    _inherit = "stock.location"

    # =========================================================================
    # Identity & Role Flags
    # =========================================================================
    clinic_location_code = fields.Char(
        string="Clinic Location Code",
        tracking=True,
        help="Short code used in UI and documents (e.g., 'RM-01', 'PHARM-01').",
    )
    clinic_is_treatment_room = fields.Boolean(
        string="Treatment Room",
        tracking=True,
        help="Mark this internal location as a treatment room/station.",
    )
    clinic_is_pharmacy = fields.Boolean(
        string="Pharmacy Area",
        tracking=True,
        help="Mark this internal location as a pharmacy/store area.",
    )
    clinic_is_quarantine = fields.Boolean(
        string="Quarantine Area",
        tracking=True,
        help="Mark this internal location as a quarantine/hold area for damaged/expired/suspect items.",
    )

    clinic_room_capacity = fields.Integer(
        string="Room Capacity",
        tracking=True,
        help="Optional capacity hints (e.g., number of concurrent treatments) for scheduling dashboards.",
    )
    clinic_room_notes = fields.Text(
        string="Room Notes",
        tracking=True,
        help="Optional notes about this room/location (equipment, preparation, restrictions).",
    )

    # =========================================================================
    # Temperature & Expiration Policy (Location-level)
    # =========================================================================
    clinic_temperature_monitoring = fields.Boolean(
        string="Enable Temperature Monitoring",
        tracking=True,
        help="If enabled, IoT bridges may record temperature compliance at this location.",
    )
    clinic_temp_min_c = fields.Float(
        string="Min Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Minimum allowed storage temperature in Celsius (location-level).",
    )
    clinic_temp_max_c = fields.Float(
        string="Max Temp (°C)",
        digits=(16, 2),
        tracking=True,
        help="Maximum allowed storage temperature in Celsius (location-level).",
    )

    clinic_expiry_policy = fields.Selection(
        selection=[
            ("inherit", "Inherit Warehouse Policy"),
            ("none", "No Blocking (Allow)"),
            ("warn", "Warn (Allow with Warning)"),
            ("block", "Block (Disallow Operation)"),
        ],
        string="Expiration Policy (Location)",
        default="inherit",
        tracking=True,
        help=(
            "How this location handles expired lots. If set to 'Inherit', the warehouse policy applies.\n"
            "Other options override warehouse behavior for operations involving this location."
        ),
    )

    # =========================================================================
    # Product Category Allowlist (optional governance)
    # =========================================================================
    clinic_restrict_to_allowed_categories = fields.Boolean(
        string="Restrict to Allowed Categories",
        tracking=True,
        help="If enabled, only products whose category is in 'Allowed Categories' may be stored/consumed here.",
    )
    clinic_allowed_categ_ids = fields.Many2many(
        "product.category",
        "clinic_location_allowed_categ_rel",
        "location_id",
        "categ_id",
        string="Allowed Categories",
        help="Allowlist of product categories permitted for this location.",
    )

    # =========================================================================
    # Warehouse resolution & stock analytics
    # =========================================================================
    clinic_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Clinic Warehouse",
        compute="_compute_clinic_warehouse",
        store=True,
        index=True,
        readonly=True,
        help="Closest warehouse whose internal view contains this location.",
    )

    clinic_onhand_qty = fields.Float(
        string="On Hand (This Location Tree)",
        compute="_compute_clinic_stock_counters",
        store=False,
        help="Sum of on-hand quantity across this location and all its children.",
    )
    clinic_waiting_in_moves = fields.Integer(
        string="Waiting Incoming Moves",
        compute="_compute_clinic_stock_counters",
        store=False,
        help="Number of incoming stock moves not done/cancel into this location tree.",
    )
    clinic_waiting_out_moves = fields.Integer(
        string="Waiting Outgoing Moves",
        compute="_compute_clinic_stock_counters",
        store=False,
        help="Number of outgoing stock moves not done/cancel from this location tree.",
    )

    # =========================================================================
    # Constraints
    # =========================================================================
    @api.constrains("clinic_is_treatment_room", "clinic_is_pharmacy", "clinic_is_quarantine", "usage")
    def _check_internal_usage_for_roles(self):
        for loc in self:
            if (loc.clinic_is_treatment_room or loc.clinic_is_pharmacy or loc.clinic_is_quarantine) and loc.usage != "internal":
                raise ValidationError(_("Treatment/Pharmacy/Quarantine flags require location usage = 'internal'."))

    @api.constrains("clinic_temp_min_c", "clinic_temp_max_c")
    def _check_temperature_range(self):
        for loc in self:
            if loc.clinic_temp_min_c and loc.clinic_temp_max_c and loc.clinic_temp_min_c > loc.clinic_temp_max_c:
                raise ValidationError(_("Minimum temperature cannot exceed maximum temperature."))

    # =========================================================================
    # Onchange helpers
    # =========================================================================
    @api.onchange("clinic_is_treatment_room", "clinic_is_pharmacy", "clinic_is_quarantine")
    def _onchange_location_role(self):
        for loc in self:
            if (loc.clinic_is_treatment_room or loc.clinic_is_pharmacy or loc.clinic_is_quarantine) and loc.usage != "internal":
                loc.usage = "internal"

    # =========================================================================
    # Computes
    # =========================================================================
    # @api.depends("id", "location_id", "location_id.parent_left", "location_id.parent_right", "company_id")
    # @api.depends("location_id", "location_id.parent_left", "location_id.parent_right", "company_id")
    # @api.depends("location_id", "location_id.parent_path", "company_id")
    # def _compute_clinic_warehouse(self):
    #     Warehouse = self.env["stock.warehouse"]
    #     for loc in self:
    #         wh = Warehouse.search([("view_location_id", "child_of", loc.id)], limit=1)
    #         if not wh:
    #             # fallback: find any warehouse whose internal view is ancestor of this location
    #             wh = Warehouse.search([("view_location_id", "parent_of", loc.id)], limit=1)
    #         loc.clinic_warehouse_id = wh or False

    @api.depends('parent_path', 'location_id', 'company_id')
    def _compute_clinic_warehouse(self):
        Warehouse = self.env['stock.warehouse'].sudo()
        # ambil semua warehouse sekali saja untuk efisiensi
        warehouses = Warehouse.search([])
        by_view_loc = {w.view_location_id.id: w for w in warehouses}
        for loc in self:
            wh = False
            cur = loc
            # naik ke atas hingga ketemu view_location warehouse
            while cur:
                wh = by_view_loc.get(cur.id)
                if wh and (not loc.company_id or wh.company_id == loc.company_id):
                    break
                cur = cur.location_id
            self.clinic_warehouse_id = wh.id if wh else False

    # @api.depends("id", "location_id", "location_id.parent_left", "location_id.parent_right")
    # @api.depends("location_id", "location_id.parent_left", "location_id.parent_right")
    @api.depends("location_id", "location_id.parent_path")
    def _compute_clinic_stock_counters(self):
        Quant = self.env["stock.quant"]
        Move = self.env["stock.move"]
        for loc in self:
            # On-hand across this location subtree
            onhand = 0.0
            for row in Quant.read_group([("location_id", "child_of", loc.id)], ["quantity:sum"], []):
                onhand += row.get("quantity", 0.0) or 0.0
            loc.clinic_onhand_qty = onhand

            # Incoming moves (to this tree), outgoing moves (from this tree)
            inc = Move.search_count([
                ("state", "not in", ["done", "cancel"]),
                ("location_dest_id", "child_of", loc.id),
            ])
            out = Move.search_count([
                ("state", "not in", ["done", "cancel"]),
                ("location_id", "child_of", loc.id),
            ])
            loc.clinic_waiting_in_moves = inc
            loc.clinic_waiting_out_moves = out

    # =========================================================================
    # UI Actions
    # =========================================================================
    def action_view_quants(self):
        """Open quants scoped to this location subtree."""
        self.ensure_one()
        action = self.env.ref("stock.quants_action").read()[0]
        action["domain"] = [("location_id", "child_of", self.id)]
        action["context"] = {"default_location_id": self.id}
        return action

    def action_view_moves(self):
        """Open stock moves scoped to this location subtree."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [
            "|",
            ("location_id", "child_of", self.id),
            ("location_dest_id", "child_of", self.id),
        ]
        return action

    def action_view_pickings(self):
        """Open pickings linked to this location subtree via picking types or move lines."""
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        # Broad domain: any picking with moves to/from this location tree
        action["domain"] = [
            "|",
            ("move_lines.location_id", "child_of", self.id),
            ("move_lines.location_dest_id", "child_of", self.id),
        ]
        return action

    # =========================================================================
    # Name & Display
    # =========================================================================

    @api.depends(
        "name",
        "complete_name",
        "clinic_location_code",
        "clinic_is_treatment_room",
        "clinic_is_pharmacy",
        "clinic_is_quarantine",
    )
    def _compute_display_name(self):
        """Preserve ClinicOne location labels using the Odoo 19 display-name API."""
        super()._compute_display_name()
        for loc in self:
            label = loc.display_name or loc.name or ""
            code = (loc.clinic_location_code or "").strip()
            if code and not label.startswith(f"[{code}]"):
                label = f"[{code}] {label}"
            if loc.clinic_is_treatment_room:
                label = f"{label} (Treatment Room)"
            elif loc.clinic_is_pharmacy:
                label = f"{label} (Pharmacy)"
            elif loc.clinic_is_quarantine:
                label = f"{label} (Quarantine)"
            loc.display_name = label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    # =========================================================================
    # Expiration & Temperature Policies
    # =========================================================================
    def clinic_expiration_decision(self, lot):
        """Return ('ok'|'warn'|'block', message) for an expiration check at this location.

        Behavior:
          - If this location has a specific policy (none/warn/block), use it.
          - Otherwise inherit from the resolved warehouse policy.
        """
        self.ensure_one()
        policy = self.clinic_expiry_policy or "inherit"
        if policy == "block":
            return "block", _("Expired lots are blocked by location policy.")
        if policy == "warn":
            return "warn", _("Expired lots will raise a warning by location policy.")
        if policy == "none":
            return "ok", None

        # Inherit from warehouse
        wh = self._clinic_resolve_warehouse()
        if not wh:
            return "ok", None
        status, msg = wh.clinic_expiration_decision(lot)
        return status, msg

    def clinic_validate_temperature(self, product, lot=None, temperature_c=None):
        """Return (ok: bool, message: str|None) for temperature validation at this location.

        Behavior:
          - If location monitoring disabled and no thresholds set, defer to warehouse.
          - If thresholds exist and measurement provided, validate range.
          - If ok or no data, defer to warehouse for additional checks (e.g., IoT trends).
        """
        self.ensure_one()
        if self.clinic_temperature_monitoring and temperature_c is not None:
            min_c = self.clinic_temp_min_c
            max_c = self.clinic_temp_max_c
            # Validate only if explicit thresholds are set
            if min_c or max_c:
                if min_c and temperature_c < min_c:
                    return False, _("Measured temperature %(t).2f°C below location minimum %(m).2f°C.") % {
                        "t": temperature_c, "m": min_c
                    }
                if max_c and temperature_c > max_c:
                    return False, _("Measured temperature %(t).2f°C above location maximum %(m).2f°C.") % {
                        "t": temperature_c, "m": max_c
                    }

        # Delegate further checks to warehouse (if any)
        wh = self._clinic_resolve_warehouse()
        if wh:
            return wh.clinic_validate_temperature(product=product, lot=lot, temperature_c=temperature_c)
        return True, None

    # =========================================================================
    # Product Governance
    # =========================================================================
    def clinic_validate_product_allowed(self, product):
        """Raise if product is not allowed in this location based on category allowlist."""
        self.ensure_one()
        if not self.clinic_restrict_to_allowed_categories:
            return True
        if not product:
            raise UserError(_("No product provided to validate for this location."))
        categ = getattr(product, "categ_id", False) or getattr(product, "product_tmpl_id", False) and product.product_tmpl_id.categ_id
        if not categ:
            return True  # cannot determine → allow
        if categ not in self.clinic_allowed_categ_ids:
            raise UserError(_("Product category '%s' is not allowed in location '%s'.") % (categ.display_name, self.display_name))
        return True

    # =========================================================================
    # Hooks (override in bridge addons)
    # =========================================================================
    def _clinic_hook_is_valid_for_operation(self, product, qty=0.0, operation="store", **kwargs):
        """Return True/False or raise to validate a product operation at this location.

        Default behavior:
          - Ensure product category is allowed (if restriction enabled).
          - Additional rules can be implemented by bridges (e.g., medication-only rooms).
        """
        self.clinic_validate_product_allowed(product)
        return True

    # =========================================================================
    # Utilities
    # =========================================================================
    def _clinic_resolve_warehouse(self):
        """Find a warehouse whose internal view contains this location (best-effort)."""
        self.ensure_one()
        if self.clinic_warehouse_id:
            return self.clinic_warehouse_id
        Warehouse = self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", self.id)], limit=1)
        return wh

    def clinic_room_path(self):
        """Return a human-readable path of this location within its warehouse."""
        self.ensure_one()
        parts = []
        cur = self
        # Walk up parents until top
        while cur:
            label = cur.name
            if cur.clinic_location_code:
                label = f"[{cur.clinic_location_code}] {label}"
            parts.append(label)
            cur = cur.location_id
        return " / ".join(reversed(parts))




