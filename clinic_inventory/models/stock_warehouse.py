# -*- coding: utf-8 -*-
# File: models/stock_warehouse.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.warehouse for aesthetic clinics:
#   - Define clinic-aware locations (pharmacy, treatment rooms, quarantine)
#   - Warehouse-level policies (expiration blocking, replenishment scope)
#   - Helper domains for internal locations, room/pharmacy scopes
#   - Simple replenishment suggestions (min/target) using product-level settings
#   - Actions to navigate quants/moves/pickings constrained to warehouse scope
#   - Hooks for 25 ClinicOne addons (doctor/treatment/room-device/pricing/finance/etc.)
#
# Notes
#   - All user-facing texts are in English.
#   - No hard dependency on other clinic_* modules to avoid circular deps.
#   - Bridges may override *_clinic_hook_* methods to enrich behavior.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    # =========================================================================
    # Clinic identity & key locations
    # =========================================================================
    is_clinic_warehouse = fields.Boolean(
        string="Clinic Warehouse",
        tracking=True,
        help="Enable clinic-specific policies and dashboards on this warehouse."
    )

    clinic_pharmacy_location_id = fields.Many2one(
        "stock.location",
        string="Pharmacy Location",
        domain="[('usage', '=', 'internal'), ('id', 'child_of', view_location_id)]",
        tracking=True,
        help="Primary internal location that represents the clinic pharmacy/store for this warehouse."
    )

    clinic_treatment_root_location_id = fields.Many2one(
        "stock.location",
        string="Treatment Rooms Root",
        domain="[('usage', '=', 'internal'), ('id', 'child_of', view_location_id)]",
        tracking=True,
        help="Root/internal location under which treatment rooms/stations are organized."
    )

    clinic_quarantine_location_id = fields.Many2one(
        "stock.location",
        string="Quarantine Location",
        domain="[('usage', '=', 'internal'), ('id', 'child_of', view_location_id)]",
        tracking=True,
        help="Internal location for quarantining damaged/expired/suspect items pending decisions."
    )

    # =========================================================================
    # Warehouse-level policies
    # =========================================================================
    clinic_expiry_blocking_policy = fields.Selection(
        selection=[
            ("none", "No Blocking (Allow)"),
            ("warn", "Warn (Allow with Warning)"),
            ("block", "Block (Disallow Operation)"),
        ],
        string="Expiration Policy",
        default="warn",
        tracking=True,
        help=(
            "Controls how operations handle expired lots in this warehouse:\n"
            "- No Blocking: allow moves with expired lots (not recommended).\n"
            "- Warn: show warning but allow operation.\n"
            "- Block: disallow operations that pick/consume expired lots."
        ),
    )

    clinic_replenishment_scope = fields.Selection(
        selection=[
            ("pharmacy_only", "Pharmacy Only"),
            ("rooms_only", "Treatment Rooms Only"),
            ("pharmacy_and_rooms", "Pharmacy and Treatment Rooms"),
        ],
        string="Replenishment Scope",
        default="pharmacy_and_rooms",
        tracking=True,
        help="Define where replenishment dashboards look for shortages in this warehouse."
    )

    clinic_temperature_monitoring = fields.Boolean(
        string="Enable Temperature Monitoring",
        tracking=True,
        help="If enabled, IoT/sensor bridges may enforce temperature compliance at reception/storage."
    )

    clinic_auto_create_room_locations = fields.Boolean(
        string="Auto-create Room Locations",
        tracking=True,
        help="If enabled, bridges may auto-provision standard room sublocations when departments/rooms are created."
    )

    # =========================================================================
    # Counters & analytics
    # =========================================================================
    clinic_count_internal_locations = fields.Integer(
        string="# Internal Locations",
        compute="_compute_clinic_counts",
        help="Number of internal locations under this warehouse's internal view."
    )
    clinic_count_treatment_rooms = fields.Integer(
        string="# Treatment Rooms",
        compute="_compute_clinic_counts",
        help="Count of internal locations flagged as treatment rooms (if the flag exists)."
    )
    clinic_count_quarantine_stock = fields.Float(
        string="Quarantine On-hand",
        compute="_compute_clinic_counts",
        help="Approximate on-hand quantity in quarantine location (sum of quants)."
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("view_location_id", "clinic_quarantine_location_id")
    def _compute_clinic_counts(self):
        Quant = self.env["stock.quant"]
        Location = self.env["stock.location"]
        has_room_flag = "clinic_is_treatment_room" in Location._fields
        for wh in self:
            ilocs = Location.search([("usage", "=", "internal"), ("id", "child_of", wh.view_location_id.id)])
            wh.clinic_count_internal_locations = len(ilocs)

            # Treatment room count
            if has_room_flag:
                rooms = ilocs.filtered(lambda l: getattr(l, "clinic_is_treatment_room", False))
                wh.clinic_count_treatment_rooms = len(rooms)
            else:
                wh.clinic_count_treatment_rooms = 0

            # Quarantine stock sum
            q_qty = 0.0
            if wh.clinic_quarantine_location_id:
                for row in Quant.read_group(
                    [("location_id", "child_of", wh.clinic_quarantine_location_id.id)], ["quantity:sum"], []
                ):
                    q_qty += row.get("quantity", 0.0) or 0.0
            wh.clinic_count_quarantine_stock = q_qty

    # =========================================================================
    # VALIDATIONS
    # =========================================================================
    @api.constrains("clinic_pharmacy_location_id", "clinic_treatment_root_location_id", "clinic_quarantine_location_id")
    def _check_locations_under_warehouse(self):
        for wh in self:
            for loc in [
                wh.clinic_pharmacy_location_id,
                wh.clinic_treatment_root_location_id,
                wh.clinic_quarantine_location_id,
            ]:
                if loc and not wh._clinic_is_child_of_view(loc):
                    raise ValidationError(
                        _("Location '%(loc)s' must be a child of the warehouse internal view '%(view)s'.") % {
                            "loc": loc.display_name,
                            "view": wh.view_location_id.display_name,
                        }
                    )

    # =========================================================================
    # ONCHANGE / HELPERS
    # =========================================================================
    def _clinic_is_child_of_view(self, location):
        """Return True if location is under this warehouse's internal view."""
        self.ensure_one()
        if not location or not self.view_location_id:
            return False
        return location.id in location.search([("id", "child_of", self.view_location_id.id)]).ids

    @api.onchange("is_clinic_warehouse")
    def _onchange_is_clinic_warehouse(self):
        """Suggest policy defaults when toggled on."""
        for wh in self:
            if wh.is_clinic_warehouse:
                if not wh.clinic_expiry_blocking_policy:
                    wh.clinic_expiry_blocking_policy = "warn"
                if not wh.clinic_replenishment_scope:
                    wh.clinic_replenishment_scope = "pharmacy_and_rooms"

    # =========================================================================
    # ACTIONS (UI helpers)
    # =========================================================================
    def action_view_internal_locations(self):
        """Open internal locations under this warehouse view."""
        self.ensure_one()
        action = self.env.ref("stock.action_location_form").read()[0]
        action["domain"] = [("usage", "=", "internal"), ("id", "child_of", self.view_location_id.id)]
        action["context"] = {"search_default_child_of_location_id": self.view_location_id.id}
        return action

    def action_view_quants(self):
        """Open quants scoped to this warehouse internal view."""
        self.ensure_one()
        action = self.env.ref("stock.quants_action").read()[0]
        action["domain"] = [("location_id", "child_of", self.view_location_id.id)]
        action["context"] = {"default_location_id": self.lot_stock_id.id}
        return action

    def action_view_pickings(self):
        """Open pickings scoped to this warehouse."""
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        # Odoo links stock.picking to picking_type_id which is tied to a warehouse; we filter by types of this WH
        picking_types = self._get_related_picking_type_ids()
        action["domain"] = [("picking_type_id", "in", picking_types)]
        return action

    def action_view_moves(self):
        """Open stock moves scoped to this warehouse's internal view."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [
            "|",
            ("location_id", "child_of", self.view_location_id.id),
            ("location_dest_id", "child_of", self.view_location_id.id),
        ]
        return action

    def _get_related_picking_type_ids(self):
        """Helper to gather picking types associated to this warehouse."""
        self.ensure_one()
        ptypes = self.env["stock.picking.type"]
        for name in ("in_type_id", "out_type_id", "int_type_id", "pick_type_id", "pack_type_id"):
            pt = getattr(self, name, False)
            if pt:
                ptypes |= pt
        # Also include any picking types explicitly linked to this WH
        ptypes |= self.env["stock.picking.type"].search([("warehouse_id", "=", self.id)])
        return ptypes.ids

    # =========================================================================
    # REPLENISHMENT SUGGESTIONS (read-only proposal)
    # =========================================================================
    def clinic_compute_replenishment_suggestions(self, products=None):
        """Return replenishment suggestions for this warehouse.

        Args:
            products (recordset product.product|None): optional scope; if None, consider all stockable clinic products.

        Returns:
            list of dict items with keys:
                product_id, uom_id, onhand, min_qty, target_qty, deficit, suggested_qty, scope
        """
        self.ensure_one()
        Prod = self.env["product.product"]
        Quant = self.env["stock.quant"]

        # Scope products
        if products is None:
            products = Prod.search([("is_stockable_flag", "=", True), ("type", "!=", "service")])

        # Build location domain according to replenishment scope
        loc_domain = self._clinic_hook_location_domain_for_replenishment()
        # Always constrain to this warehouse's internal view
        loc_domain = loc_domain + [("location_id", "child_of", self.view_location_id.id)]

        # Aggregate on-hand by product
        onhand_map = {}
        for row in Quant.read_group(loc_domain + [("product_id", "in", products.ids)],
                                    ["product_id", "quantity:sum"], ["product_id"]):
            pid = row["product_id"][0]
            onhand_map[pid] = (onhand_map.get(pid, 0.0) + (row.get("quantity", 0.0) or 0.0))

        # Prepare suggestions
        result = []
        for p in products:
            onhand = onhand_map.get(p.id, 0.0)
            min_q = p.clinic_min_qty or 0.0
            tgt_q = p.clinic_target_qty or 0.0
            deficit = max(0.0, (min_q - onhand)) if min_q else 0.0
            suggested = 0.0
            if tgt_q and onhand < tgt_q:
                suggested = tgt_q - onhand
            elif deficit:
                suggested = deficit

            result.append({
                "product_id": p.id,
                "uom_id": p.uom_id.id,
                "onhand": onhand,
                "min_qty": min_q,
                "target_qty": tgt_q,
                "deficit": deficit,
                "suggested_qty": suggested,
                "scope": self.clinic_replenishment_scope,
            })
        return result

    # =========================================================================
    # EXPIRATION POLICY (read-only evaluation)
    # =========================================================================
    def clinic_should_block_expired(self):
        """Return True if warehouse is configured to block operations with expired lots."""
        self.ensure_one()
        return self.clinic_expiry_blocking_policy == "block"

    def clinic_should_warn_expired(self):
        """Return True if warehouse is configured to warn (but allow) operations with expired lots."""
        self.ensure_one()
        return self.clinic_expiry_blocking_policy == "warn"

    # =========================================================================
    # HOOKS (override in bridge addons)
    # =========================================================================
    def _clinic_hook_location_domain_for_replenishment(self):
        """Return a domain on stock.quant for 'clinic' replenishment scope.

        Default behavior (based on clinic_replenishment_scope):
            - pharmacy_only: restrict to pharmacy_location child tree
            - rooms_only: restrict to treatment_root_location child tree
            - pharmacy_and_rooms: internal locations under warehouse view (default)
        Bridges (room-device module) can refine to specific tagged rooms/areas.
        """
        self.ensure_one()
        if self.clinic_replenishment_scope == "pharmacy_only" and self.clinic_pharmacy_location_id:
            return [("location_id", "child_of", self.clinic_pharmacy_location_id.id)]
        if self.clinic_replenishment_scope == "rooms_only" and self.clinic_treatment_root_location_id:
            return [("location_id", "child_of", self.clinic_treatment_root_location_id.id)]
        # Default: full internal scope of the warehouse
        return [("location_id.usage", "=", "internal")]

    def _clinic_hook_validate_temperature(self, product, lot=None, temperature_c=None):
        """Return (ok: bool, message: str|None) for temperature validation at reception/storage.

        Default behavior:
            - If monitoring disabled or product has no storage range, accept.
            - If storage_min/max exist and a measurement is provided, verify range.

        Bridges (IoT) may override to fetch live readings, tolerate brief excursions, or log trends.
        """
        self.ensure_one()
        if not self.clinic_temperature_monitoring:
            return True, None
        min_c = getattr(product, "storage_min_c", False)
        max_c = getattr(product, "storage_max_c", False)
        if temperature_c is None or (not min_c and not max_c):
            return True, None
        if min_c and temperature_c < min_c:
            return False, _("Measured temperature %(t).2f°C below minimum %(m).2f°C.") % {"t": temperature_c, "m": min_c}
        if max_c and temperature_c > max_c:
            return False, _("Measured temperature %(t).2f°C above maximum %(m).2f°C.") % {"t": temperature_c, "m": max_c}
        return True, None

    def _clinic_hook_expiration_check(self, lot):
        """Return ('ok'|'warn'|'block', message) for an expiration check decision.

        Default behavior uses warehouse policy only.
        Bridges can include grace periods or membership rules, etc.
        """
        self.ensure_one()
        status = "ok"
        msg = None
        # We don't evaluate actual dates here; bridges can implement it.
        if self.clinic_expiry_blocking_policy == "block":
            status, msg = "block", _("Expired lots are blocked by warehouse policy.")
        elif self.clinic_expiry_blocking_policy == "warn":
            status, msg = "warn", _("Expired lots will raise a warning by warehouse policy.")
        return status, msg

    # =========================================================================
    # PUBLIC SERVICE APIS (consumed by other modules)
    # =========================================================================
    def clinic_get_internal_location_domain(self):
        """Public API: return a domain for internal locations of this warehouse."""
        self.ensure_one()
        return [("usage", "=", "internal"), ("id", "child_of", self.view_location_id.id)]

    def clinic_get_room_location_domain(self):
        """Public API: domain for treatment rooms under this warehouse (best-effort)."""
        self.ensure_one()
        Location = self.env["stock.location"]
        if "clinic_is_treatment_room" in Location._fields:
            return [("usage", "=", "internal"), ("clinic_is_treatment_room", "=", True),
                    ("id", "child_of", self.view_location_id.id)]
        # Fallback: if a root is configured, use it
        if self.clinic_treatment_root_location_id:
            return [("usage", "=", "internal"), ("id", "child_of", self.clinic_treatment_root_location_id.id)]
        # Minimal fallback
        return [("usage", "=", "internal"), ("id", "child_of", self.view_location_id.id)]

    def clinic_validate_temperature(self, product, lot=None, temperature_c=None):
        """Public API wrapper for temperature validation at reception/storage."""
        self.ensure_one()
        return self._clinic_hook_validate_temperature(product=product, lot=lot, temperature_c=temperature_c)

    def clinic_expiration_decision(self, lot):
        """Public API wrapper for expiration policy decision."""
        self.ensure_one()
        return self._clinic_hook_expiration_check(lot)

    def clinic_location_for_consumption(self, product=None, category=None):
        """Resolve a default consumption location for clinical use within this warehouse.

        Order of resolution:
            1) Treatment Rooms Root (if set)
            2) Category default consumption location (if provided by product.category)
            3) Pharmacy Location
            4) Warehouse lot_stock_id (generic stock)
        """
        self.ensure_one()
        if self.clinic_treatment_root_location_id:
            return self.clinic_treatment_root_location_id

        # Ask category helper if available
        if category:
            try:
                loc = category.clinic_get_default_consumption_location()
                if loc:
                    return loc
            except Exception:
                # If category API not available, ignore silently
                pass

        if self.clinic_pharmacy_location_id:
            return self.clinic_pharmacy_location_id
        return self.lot_stock_id




