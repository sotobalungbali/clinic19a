# -*- coding: utf-8 -*-
# File: models/stock_reorderpoint.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.warehouse.orderpoint (Reorder Point) for aesthetic clinics:
#   - Clinic replenishment scope (pharmacy / treatment rooms / both / warehouse default)
#   - Shelf-life–aware "usable on-hand" (exclude lots expiring too soon)
#   - Buffer percentage and UoM rounding policy for suggested quantity
#   - Convenience stock metrics (on hand/incoming/outgoing/virtual) computed in scope
#   - Actions & hooks to trigger procurement flows without hard-depending on other addons
#
# Notes
#   - All user-facing texts are in English.
#   - We avoid hard dependency on clinic_* modules; bridges may override *_clinic_hook_* methods.
#   - Compatible with Odoo core by NOT adding unknown keys to core models in actions.
#
# Model reference
#   Historically, Odoo uses 'stock.warehouse.orderpoint' for reorder points.
#   If in your Odoo build the model is named differently, adapt the _inherit target.

from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    # =========================================================================
    # Clinic policy fields
    # =========================================================================
    clinic_scope = fields.Selection(
        selection=[
            ("warehouse_default", "Warehouse Default"),
            ("pharmacy_only", "Pharmacy Only"),
            ("rooms_only", "Treatment Rooms Only"),
            ("pharmacy_and_rooms", "Pharmacy and Treatment Rooms"),
        ],
        string="Clinic Replenishment Scope",
        default="warehouse_default",
        tracking=True,
        help=(
            "Where the reorder metrics should be computed within the warehouse:\n"
            "- Warehouse Default: use the warehouse's own scope setting.\n"
            "- Pharmacy Only: restrict to the configured Pharmacy location subtree.\n"
            "- Treatment Rooms Only: restrict to the Treatment Rooms root subtree.\n"
            "- Pharmacy and Treatment Rooms: both subtrees."
        ),
    )

    clinic_min_shelf_life_days = fields.Integer(
        string="Min Remaining Shelf Life (Days)",
        default=0,
        tracking=True,
        help=(
            "Exclude lots that would expire in fewer than this number of days when computing "
            "usable on-hand for replenishment suggestions. 0 means ignore shelf-life."
        ),
    )

    clinic_buffer_percent = fields.Float(
        string="Safety Buffer (%)",
        default=0.0,
        tracking=True,
        help="Optional safety buffer as a percentage of the target quantity (0–100).",
    )

    clinic_rounding_mode = fields.Selection(
        selection=[
            ("none", "No Rounding"),
            ("ceil_uom", "Ceiling to Product UoM Rounding"),
            ("floor_uom", "Floor to Product UoM Rounding"),
            ("nearest_uom", "Nearest Product UoM Rounding"),
        ],
        string="Rounding Mode",
        default="ceil_uom",
        tracking=True,
        help=(
            "How the suggested quantity should be rounded relative to the product's UoM rounding."
        ),
    )

    clinic_note = fields.Char(
        string="Clinic Note",
        tracking=True,
        help="Optional short note regarding this reorder point policy.",
    )

    # =========================================================================
    # Computed stock metrics (scoped)
    # =========================================================================
    clinic_onhand_qty = fields.Float(
        string="On Hand (Scope)",
        compute="_compute_clinic_metrics",
        store=False,
        help="Sum of on-hand quantity across locations matching the clinic scope.",
    )
    clinic_usable_onhand_qty = fields.Float(
        string="Usable On Hand (Scope)",
        compute="_compute_clinic_metrics",
        store=False,
        help="On-hand quantity excluding lots whose remaining shelf-life is below the threshold.",
    )
    clinic_incoming_qty = fields.Float(
        string="Incoming (Scope)",
        compute="_compute_clinic_metrics",
        store=False,
        help="Incoming quantity into the scoped locations (not done/cancel).",
    )
    clinic_outgoing_qty = fields.Float(
        string="Outgoing (Scope)",
        compute="_compute_clinic_metrics",
        store=False,
        help="Outgoing quantity from the scoped locations (not done/cancel).",
    )
    clinic_virtual_available_qty = fields.Float(
        string="Virtual Available (Scope)",
        compute="_compute_clinic_metrics",
        store=False,
        help="Usable on-hand + incoming - outgoing in the scoped locations.",
    )

    clinic_suggested_qty = fields.Float(
        string="Suggested Qty",
        compute="_compute_clinic_suggestion",
        store=False,
        help="Suggested replenishment quantity considering min/target, buffer, and rounding policy.",
    )
    clinic_last_suggested_on = fields.Datetime(
        string="Last Suggested On",
        help="Timestamp when the suggestion was last computed/executed (audit only).",
    )
    clinic_last_run_by = fields.Many2one(
        "res.users",
        string="Last Run By",
        help="User who last executed the replenishment action (audit only).",
    )

    # =========================================================================
    # Validation
    # =========================================================================
    @api.constrains("clinic_buffer_percent")
    def _check_buffer_percent(self):
        for r in self:
            if r.clinic_buffer_percent < 0.0 or r.clinic_buffer_percent > 100.0:
                raise ValidationError(_("Safety Buffer must be between 0 and 100 percent."))

    @api.constrains("clinic_min_shelf_life_days")
    def _check_min_shelf_life(self):
        for r in self:
            if r.clinic_min_shelf_life_days is not None and r.clinic_min_shelf_life_days < 0:
                raise ValidationError(_("Min Remaining Shelf Life (Days) cannot be negative."))

    # =========================================================================
    # Helpers to adapt to field names across Odoo versions
    # =========================================================================
    def _rop_field_name_min(self):
        return "product_min_qty" if "product_min_qty" in self._fields else "qty_min"

    def _rop_field_name_max(self):
        return "product_max_qty" if "product_max_qty" in self._fields else "qty_max"

    # =========================================================================
    # Scope resolution
    # =========================================================================
    def _clinic_location_domain(self):
        """Return a quants domain for this ROP's scope within its warehouse."""
        self.ensure_one()
        warehouse = self.warehouse_id
        if not warehouse:
            # Fallback: constrain to internal locations
            return [("location_id.usage", "=", "internal")]
        # Warehouse default
        if self.clinic_scope == "warehouse_default":
            if hasattr(warehouse, "_clinic_hook_location_domain_for_replenishment"):
                return warehouse._clinic_hook_location_domain_for_replenishment()
            return [("location_id", "child_of", warehouse.view_location_id.id)]

        # Explicit scopes
        if self.clinic_scope == "pharmacy_only" and getattr(warehouse, "clinic_pharmacy_location_id", False):
            return [("location_id", "child_of", warehouse.clinic_pharmacy_location_id.id)]
        if self.clinic_scope == "rooms_only" and getattr(warehouse, "clinic_treatment_root_location_id", False):
            return [("location_id", "child_of", warehouse.clinic_treatment_root_location_id.id)]
        if self.clinic_scope == "pharmacy_and_rooms":
            domain = [("location_id", "child_of", warehouse.view_location_id.id), ("location_id.usage", "=", "internal")]
            return domain

        # Final fallback: internal under warehouse
        return [("location_id", "child_of", warehouse.view_location_id.id)]

    def _clinic_move_domains(self):
        """Return (incoming_domain, outgoing_domain) for stock.moves in this scope."""
        self.ensure_one()
        loc_domain = self._clinic_location_domain()
        # Translate quant domain ["location_id", "child_of", X] into move domains
        # Simpler approach: use child_of warehouse.view_location_id AND direction flags
        wh = self.warehouse_id
        base = [("state", "not in", ["done", "cancel"])]
        if wh:
            subtree = [("id", "child_of", wh.view_location_id.id)]
            incoming = base + [("location_dest_id", "in", self.env["stock.location"].search(subtree).ids)]
            outgoing = base + [("location_id", "in", self.env["stock.location"].search(subtree).ids)]
            return incoming, outgoing
        # Fallback: internal usage
        incoming = base + [("location_dest_id.usage", "=", "internal")]
        outgoing = base + [("location_id.usage", "=", "internal")]
        return incoming, outgoing

    def _clinic_get_expiration_field(self):
        Lot = self.env["stock.lot"]
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    # =========================================================================
    # Computes
    # =========================================================================
    @api.depends(
        "product_id",
        "warehouse_id",
        "clinic_scope",
        "clinic_min_shelf_life_days",
    )
    def _compute_clinic_metrics(self):
        Quant = self.env["stock.quant"]
        Move = self.env["stock.move"]
        Lot = self.env["stock.lot"]
        today = date.today()
        for rop in self:
            if not rop.product_id:
                rop.clinic_onhand_qty = 0.0
                rop.clinic_usable_onhand_qty = 0.0
                rop.clinic_incoming_qty = 0.0
                rop.clinic_outgoing_qty = 0.0
                rop.clinic_virtual_available_qty = 0.0
                continue

            # Quant domain in scope
            q_domain = rop._clinic_location_domain() + [("product_id", "=", rop.product_id.id)]

            # On hand
            onhand = 0.0
            for row in Quant.read_group(q_domain, ["quantity:sum"], []):
                onhand += row.get("quantity", 0.0) or 0.0
            rop.clinic_onhand_qty = onhand

            # Usable (shelf-life filter)
            usable = onhand
            min_days = int(rop.clinic_min_shelf_life_days or 0)
            exp_field = rop._clinic_get_expiration_field()
            if min_days > 0 and exp_field:
                # Sum only quants whose lot life_date >= today + min_days
                limit_date = today + timedelta(days=min_days)
                valid_lot_ids = Lot.search([
                    ("product_id", "=", rop.product_id.id),
                    (exp_field, ">=", limit_date),
                ]).ids
                usable = 0.0
                dom_usable = list(q_domain)
                if valid_lot_ids:
                    dom_usable.append(("lot_id", "in", valid_lot_ids))
                    for row in Quant.read_group(dom_usable, ["quantity:sum"], []):
                        usable += row.get("quantity", 0.0) or 0.0
                else:
                    usable = 0.0
            rop.clinic_usable_onhand_qty = usable

            # Incoming / Outgoing (approximate)
            inc_domain, out_domain = rop._clinic_move_domains()
            incoming = 0.0
            outgoing = 0.0
            for r in Move.read_group(inc_domain + [("product_id", "=", rop.product_id.id)], ["product_uom_qty:sum"], []):
                incoming += r.get("product_uom_qty", 0.0) or 0.0
            for r in Move.read_group(out_domain + [("product_id", "=", rop.product_id.id)], ["product_uom_qty:sum"], []):
                outgoing += r.get("product_uom_qty", 0.0) or 0.0
            rop.clinic_incoming_qty = incoming
            rop.clinic_outgoing_qty = outgoing

            rop.clinic_virtual_available_qty = usable + incoming - outgoing

    @api.depends(
        "product_id",
        "warehouse_id",
        "clinic_onhand_qty",
        "clinic_usable_onhand_qty",
        "clinic_virtual_available_qty",
        "clinic_buffer_percent",
        "clinic_rounding_mode",
    )
    def _compute_clinic_suggestion(self):
        for rop in self:
            suggested = 0.0
            if not rop.product_id:
                rop.clinic_suggested_qty = 0.0
                continue

            # Resolve min/target (compat across versions)
            min_field = rop._rop_field_name_min()
            max_field = rop._rop_field_name_max()
            min_qty = getattr(rop, min_field, 0.0) or 0.0
            target_qty = getattr(rop, max_field, 0.0) or 0.0

            usable = rop.clinic_usable_onhand_qty
            # Base rule: if under min, raise to target; else 0
            if target_qty and usable < target_qty:
                suggested = max(0.0, target_qty - usable)
            elif min_qty and usable < min_qty:
                suggested = max(0.0, min_qty - usable)

            # Safety buffer on target (increase suggestion)
            if suggested > 0.0 and rop.clinic_buffer_percent:
                suggested = suggested * (1.0 + (rop.clinic_buffer_percent / 100.0))

            # Apply UoM rounding
            suggested = rop._clinic_apply_rounding(suggested)

            rop.clinic_suggested_qty = max(0.0, suggested)

    # =========================================================================
    # Rounding
    # =========================================================================
    def _clinic_apply_rounding(self, qty):
        """Round qty according to product UoM rounding and clinic_rounding_mode."""
        self.ensure_one()
        if not qty or self.clinic_rounding_mode == "none" or not self.product_uom:
            return qty or 0.0
        rounding = self.product_uom.rounding or 0.0
        if rounding <= 0.0:
            return qty
        if self.clinic_rounding_mode == "ceil_uom":
            # Round up to nearest multiple
            mult = int((qty + (rounding - 1e-9)) / rounding)
            return float(mult * rounding)
        if self.clinic_rounding_mode == "floor_uom":
            mult = int(qty / rounding)
            return float(mult * rounding)
        if self.clinic_rounding_mode == "nearest_uom":
            mult = int((qty / rounding) + 0.5)
            return float(mult * rounding)
        return qty

    # =========================================================================
    # Actions
    # =========================================================================
    def action_view_scope_quants(self):
        """Open quants in the clinic scope for this product."""
        self.ensure_one()
        action = self.env.ref("stock.quants_action").read()[0]
        domain = self._clinic_location_domain() + [("product_id", "=", self.product_id.id)]
        action["domain"] = domain
        return action

    def action_view_scope_moves(self):
        """Open moves in the clinic scope for this product (incoming/outgoing)."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        wh = self.warehouse_id
        if wh:
            action["domain"] = [
                ("product_id", "=", self.product_id.id),
                "|",
                ("location_id", "child_of", wh.view_location_id.id),
                ("location_dest_id", "child_of", wh.view_location_id.id),
            ]
        else:
            action["domain"] = [("product_id", "=", self.product_id.id)]
        return action

    def action_execute_replenishment(self):
        """Execute replenishment according to clinic policy.

        Default behavior:
            - If suggested qty <= 0 → raise a soft error.
            - Delegate to hooks (purchase/internal/manufacturing) and post messages.
        """
        for rop in self:
            qty = rop.clinic_suggested_qty
            if qty <= 0.0:
                raise UserError(_("Suggested quantity is zero. Nothing to replenish for %s.") % rop.product_id.display_name)

            # Delegate to bridges; return True if any handled
            handled = False
            handled = handled or rop._clinic_hook_replenish_via_internal_transfer(qty)
            handled = handled or rop._clinic_hook_replenish_via_purchase(qty)
            handled = handled or rop._clinic_hook_replenish_via_manufacturing(qty)

            if not handled:
                # As a minimal fallback, post a note and open quants/moves for manual action
                rop.message_post(body=_("No bridge handled automatic replenishment. Please process manually."))
            else:
                rop.clinic_last_suggested_on = fields.Datetime.now()
                rop.clinic_last_run_by = self.env.user
                rop.message_post(body=_("Replenishment executed for %s: %s %s.")
                                      % (rop.product_id.display_name, qty, rop.product_uom.display_name))
        return True

    # =========================================================================
    # Hooks (override in bridge addons)
    # =========================================================================
    def _clinic_hook_replenish_via_internal_transfer(self, qty):
        """Try to create an internal picking from a central stock to the scope.

        Bridges may:
            - Determine source location (warehouse input/stock or central DC)
            - Choose destination (pharmacy/treatment root) according to policy
            - Create picking/moves and return True if handled
        Default: not handled.
        """
        return False

    def _clinic_hook_replenish_via_purchase(self, qty):
        """Try to create a Purchase RFQ/Order for the suggested quantity.

        Bridges (Purchase/AP/Finance) should implement this and return True if handled.
        Default: not handled.
        """
        return False

    def _clinic_hook_replenish_via_manufacturing(self, qty):
        """Try to create a Manufacturing Order to produce this product (if applicable).

        Bridges (MRP) should implement this and return True if handled.
        Default: not handled.
        """
        return False

    # =========================================================================
    # Name / Display
    # =========================================================================

    @api.depends(
        "product_id",
        "clinic_scope",
        "clinic_min_shelf_life_days",
        "clinic_buffer_percent",
        "clinic_rounding_mode",
    )
    def _compute_display_name(self):
        """Append ClinicOne replenishment policy hints to the Odoo 19 label."""
        super()._compute_display_name()
        for rec in self:
            label = rec.display_name or rec.product_id.display_name
            tags = [f"scope={(rec.clinic_scope or 'warehouse_default').replace('_', '-')}"]
            if rec.clinic_min_shelf_life_days:
                tags.append(f"minSL={rec.clinic_min_shelf_life_days}d")
            if rec.clinic_buffer_percent:
                tags.append(f"buf={int(rec.clinic_buffer_percent)}%")
            if rec.clinic_rounding_mode and rec.clinic_rounding_mode != "none":
                tags.append(rec.clinic_rounding_mode)
            rec.display_name = f"{label} [{' | '.join(tags)}]"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    # =========================================================================
    # Public APIs (for other modules)
    # =========================================================================
    def clinic_get_suggestion(self):
        """Return current suggestion info as a dict for this reorder point."""
        self.ensure_one()
        # Resolve min/target
        min_qty = getattr(self, self._rop_field_name_min(), 0.0) or 0.0
        target_qty = getattr(self, self._rop_field_name_max(), 0.0) or 0.0
        return {
            "product_id": self.product_id.id,
            "product_uom_id": self.product_uom.id,
            "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
            "min_qty": min_qty,
            "target_qty": target_qty,
            "onhand": self.clinic_onhand_qty,
            "usable_onhand": self.clinic_usable_onhand_qty,
            "incoming": self.clinic_incoming_qty,
            "outgoing": self.clinic_outgoing_qty,
            "virtual_available": self.clinic_virtual_available_qty,
            "suggested_qty": self.clinic_suggested_qty,
            "scope": self.clinic_scope,
            "min_shelf_life_days": self.clinic_min_shelf_life_days,
            "buffer_percent": self.clinic_buffer_percent,
            "rounding_mode": self.clinic_rounding_mode,
        }




