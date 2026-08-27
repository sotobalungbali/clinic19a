# -*- coding: utf-8 -*-
# File: models/stock_quant.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.quant for aesthetic clinics:
#   - Expiration awareness per quant (days to expire, state)
#   - Policy evaluation (location/warehouse allow, warn, block)
#   - Temperature/Category governance helpers
#   - Convenience UI actions (open moves, quarantine suggestion)
#   - Hook methods for 25 ClinicOne addons without circular dependencies
#
# Notes
#   - All user-facing texts are in English.
#   - We inherit mail.thread for auditability of warnings/notes posted by automated checks.
#   - We avoid heavy logic in create/write to keep performance acceptable; checks are targeted.

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    # =========================================================================
    # Related clinic/product metadata (read-only convenience)
    # =========================================================================
    clinic_usage_type = fields.Selection(
        related="product_id.product_tmpl_id.usage_type",
        string="Clinic Usage Type",
        store=True,
        readonly=True,
    )
    clinic_has_expiration = fields.Boolean(
        related="product_id.product_tmpl_id.has_expiration",
        string="Has Expiration",
        store=True,
        readonly=True,
    )
    clinic_expiration_alert_days = fields.Integer(
        related="product_id.product_tmpl_id.expiration_alert_days",
        string="Expiration Alert (Days)",
        store=True,
        readonly=True,
    )
    clinic_storage_requirement = fields.Selection(
        related="product_id.product_tmpl_id.storage_requirement",
        string="Storage Requirement",
        store=True,
        readonly=True,
    )
    clinic_storage_min_c = fields.Float(
        related="product_id.product_tmpl_id.storage_min_c",
        string="Min Temp (°C)",
        store=True,
        readonly=True,
    )
    clinic_storage_max_c = fields.Float(
        related="product_id.product_tmpl_id.storage_max_c",
        string="Max Temp (°C)",
        store=True,
        readonly=True,
    )
    clinic_regulatory_class = fields.Selection(
        related="product_id.product_tmpl_id.regulatory_class",
        string="Regulatory Classification",
        store=True,
        readonly=True,
    )

    # Location flags (read-only convenience)
    clinic_is_treatment_room = fields.Boolean(
        related="location_id.clinic_is_treatment_room",
        string="Treatment Room",
        store=True,
        readonly=True,
    )
    clinic_is_pharmacy = fields.Boolean(
        related="location_id.clinic_is_pharmacy",
        string="Pharmacy Area",
        store=True,
        readonly=True,
    )
    clinic_is_quarantine = fields.Boolean(
        related="location_id.clinic_is_quarantine",
        string="Quarantine Area",
        store=True,
        readonly=True,
    )

    # =========================================================================
    # Expiration awareness per quant
    # =========================================================================
    clinic_days_to_expiry = fields.Integer(
        string="Days to Expiry",
        compute="_compute_clinic_expiry",
        store=False,
        help="Number of days until the lot expires. Negative means already expired.",
    )
    clinic_expiration_state = fields.Selection(
        selection=[
            ("none", "No Expiration"),
            ("ok", "OK"),
            ("soon", "Expiring Soon"),
            ("expired", "Expired"),
        ],
        string="Expiration State",
        compute="_compute_clinic_expiry",
        store=False,
        help="State derived from lot expiration date and product alert threshold.",
    )
    clinic_is_policy_blocked = fields.Boolean(
        string="Blocked by Policy",
        compute="_compute_clinic_policy_block",
        store=False,
        help="True if, given current location/warehouse policy and lot date, this quant would be blocked in operations.",
    )

    # Optional note field for manual remarks (visible in chatter as well)
    clinic_note = fields.Char(
        string="Clinic Note",
        help="Optional short note for this quant (quality remark, hold reason, etc.).",
        tracking=True,
    )

    # =========================================================================
    # Internal helpers
    # =========================================================================
    def _get_expiration_field_name(self):
        Lot = self.env["stock.lot"]
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("lot_id", "lot_id.expiration_date", "product_id", "product_id.product_tmpl_id.expiration_alert_days")
    def _compute_clinic_expiry(self):
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for q in self:
            if not q.product_id or not q.clinic_has_expiration or not q.lot_id or not exp_field:
                q.clinic_days_to_expiry = 0
                q.clinic_expiration_state = "none"
                continue
            ld = getattr(q.lot_id, exp_field, False)
            if not ld:
                q.clinic_days_to_expiry = 0
                q.clinic_expiration_state = "none"
                continue
            delta = (ld - today).days
            q.clinic_days_to_expiry = delta
            if delta < 0:
                q.clinic_expiration_state = "expired"
            else:
                alert = q.clinic_expiration_alert_days or 0
                q.clinic_expiration_state = "soon" if alert and delta <= alert else "ok"

    @api.depends("clinic_expiration_state", "location_id", "lot_id")
    def _compute_clinic_policy_block(self):
        for q in self:
            blocked = False
            if q.clinic_expiration_state == "expired" and q.location_id:
                status, _msg = q._clinic_resolve_location_policy(q.location_id, q.lot_id)
                blocked = (status == "block")
            q.clinic_is_policy_blocked = blocked

    # =========================================================================
    # CONSTRAINTS / OVERRIDES
    # =========================================================================
    @api.constrains("quantity", "product_id", "location_id")
    def _check_clinic_location_governance(self):
        """Lightweight governance: if location restricts categories, ensure product is allowed."""
        for q in self:
            if q.quantity and q.location_id and getattr(q.location_id, "clinic_restrict_to_allowed_categories", False):
                # Only check when positive quantity is present (non-zero)
                q.location_id.clinic_validate_product_allowed(q.product_id)

    def write(self, vals):
        """When moving quant across locations (manual edits), enforce policy/governance sanity."""
        # Detect location change and/or quantity increase into a restricted/blocked location
        moving_to_loc = "location_id" in vals
        qty_change = "quantity" in vals
        res = super().write(vals)

        # Post-check on each record to avoid blocking core flows unnecessarily
        exp_field = self._get_expiration_field_name()
        today = date.today()
        warn_msgs = []
        for q in self:
            # Category governance
            if getattr(q.location_id, "clinic_restrict_to_allowed_categories", False):
                q.location_id.clinic_validate_product_allowed(q.product_id)

            # Expiration policy (if expired and policy blocks at destination)
            if exp_field and q.lot_id:
                ld = getattr(q.lot_id, exp_field, False)
                if ld and ld < today and q.location_id:
                    status, msg = q._clinic_resolve_location_policy(q.location_id, q.lot_id)
                    if status == "block":
                        # Revert is complex; instead, raise to indicate violation.
                        raise UserError(_("Expired lot is not allowed in location '%s': %s")
                                        % (q.location_id.display_name, msg or _("Blocked by policy")))
                    elif status == "warn":
                        warn_msgs.append(_("Expired lot stored in '%s': %s") % (q.location_id.display_name, msg or _("Warning")))

        # Post warnings to chatter (batched)
        if warn_msgs:
            for msg in warn_msgs:
                self.message_post(body=msg)

        # Hook for bridges to react on quant write
        for q in self:
            q._clinic_hook_post_write(vals)

        return res

    # =========================================================================
    # POLICY RESOLUTION
    # =========================================================================
    def _clinic_resolve_location_policy(self, location, lot):
        """Return ('ok'|'warn'|'block', message) using location or warehouse policy."""
        if not location:
            return "ok", None
        if hasattr(location, "clinic_expiration_decision"):
            return location.clinic_expiration_decision(lot)
        # Fallback: find a warehouse that contains the location
        Warehouse = self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", location.id)], limit=1)
        if wh and hasattr(wh, "clinic_expiration_decision"):
            return wh.clinic_expiration_decision(lot)
        return "ok", None

    # =========================================================================
    # UI ACTIONS
    # =========================================================================
    def action_view_moves(self):
        """Open stock moves related to this quant's product within this location subtree."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [
            ("product_id", "=", self.product_id.id),
            "|",
            ("location_id", "child_of", self.location_id.id),
            ("location_dest_id", "child_of", self.location_id.id),
        ]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    def action_view_lot(self):
        """Open the linked lot/serial if any."""
        self.ensure_one()
        if not self.lot_id:
            raise UserError(_("This quant has no lot/serial assigned."))
        action = self.env.ref("stock.action_production_lot_form").read()[0]
        action["domain"] = [("id", "=", self.lot_id.id)]
        return action

    def action_suggest_quarantine_transfer(self):
        """Return an action to create an internal picking to quarantine for this quant.

        The method prepares a context with defaults; user can adjust before confirming.
        """
        self.ensure_one()
        if not self.product_id or self.product_id.type == "service":
            raise UserError(_("Services cannot be transferred to quarantine."))

        dest_loc = self._clinic_get_quarantine_location()
        if not dest_loc:
            raise UserError(_("No quarantine location configured for this warehouse/location."))

        warehouse = self._clinic_resolve_warehouse()
        if not warehouse or not warehouse.int_type_id:
            raise UserError(_("No internal picking type found for the resolved warehouse."))

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        # Prepare defaults for a new internal picking
        action.update({
            "context": {
                "default_picking_type_id": warehouse.int_type_id.id,
                "default_location_id": self.location_id.id,
                "default_location_dest_id": dest_loc.id,
                "default_move_ids_without_package": [(0, 0, {
                    "name": _("Quarantine transfer for %s") % (self.product_id.display_name,),
                    "product_id": self.product_id.id,
                    "product_uom": self.product_id.uom_id.id,
                    "product_uom_qty": max(self.quantity, 0.0),
                    "location_id": self.location_id.id,
                    "location_dest_id": dest_loc.id,
                })],
                "default_clinic_is_quarantine_transfer": True,
            },
        })
        return action

    # =========================================================================
    # NAME / DISPLAY
    # =========================================================================

    @api.depends(
        "product_id",
        "lot_id",
        "location_id",
        "quantity",
        "clinic_expiration_state",
    )
    def _compute_display_name(self):
        """Provide a human-friendly quant label for ClinicOne inventory screens."""
        for quant in self:
            parts = []
            if quant.product_id:
                parts.append(quant.product_id.display_name)
            if quant.lot_id:
                parts.append(quant.lot_id.display_name)
            if quant.location_id:
                parts.append(quant.location_id.display_name)
            parts.append(_("qty: %s %s") % (quant.quantity, quant.product_uom_id.name))
            if quant.clinic_expiration_state == "expired":
                parts.append("[EXPIRED]")
            elif quant.clinic_expiration_state == "soon":
                parts.append("[SOON]")
            elif quant.clinic_expiration_state == "ok":
                parts.append("[OK]")
            quant.display_name = " | ".join(part for part in parts if part)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    # =========================================================================
    # PUBLIC APIS
    # =========================================================================
    def clinic_is_expired(self):
        """Return True if this quant's lot is expired."""
        self.ensure_one()
        return self.clinic_expiration_state == "expired"

    def clinic_should_block_here(self):
        """Return True if policy says this quant should be blocked in its current location."""
        self.ensure_one()
        return bool(self.clinic_is_policy_blocked)

    def clinic_validate_temperature(self, temperature_c=None):
        """Validate a temperature reading for storing this quant in its location."""
        self.ensure_one()
        if temperature_c is None:
            return True, None
        # Prefer location policy; fallback to warehouse
        loc = self.location_id
        if hasattr(loc, "clinic_validate_temperature"):
            return loc.clinic_validate_temperature(product=self.product_id, lot=self.lot_id, temperature_c=temperature_c)
        wh = self._clinic_resolve_warehouse()
        if wh and hasattr(wh, "clinic_validate_temperature"):
            return wh.clinic_validate_temperature(product=self.product_id, lot=self.lot_id, temperature_c=temperature_c)
        return True, None

    # =========================================================================
    # HOOKS (override in bridge addons)
    # =========================================================================
    def _clinic_hook_post_write(self, vals):
        """Hook after write. Bridges may:
           - synchronize with quality records
           - log IoT telemetry association
           - trigger alerts/dashboards
        """
        return

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _clinic_resolve_warehouse(self):
        """Find a warehouse whose internal view contains this quant's location (best-effort)."""
        self.ensure_one()
        Location = self.env["stock.location"]
        Warehouse = self.env["stock.warehouse"]
        loc = self.location_id
        if not loc:
            return self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", loc.id)], limit=1)
        return wh

    def _clinic_get_quarantine_location(self):
        """Resolve the quarantine location using location/warehouse configuration."""
        self.ensure_one()
        # Prefer a quarantine ancestor in the location tree
        cur = self.location_id
        while cur:
            if getattr(cur, "clinic_is_quarantine", False):
                return cur
            cur = cur.location_id

        # Fallback: warehouse-level quarantine
        wh = self._clinic_resolve_warehouse()
        if wh and getattr(wh, "clinic_quarantine_location_id", False):
            return wh.clinic_quarantine_location_id
        return False

