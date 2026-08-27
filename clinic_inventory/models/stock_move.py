# -*- coding: utf-8 -*-
# File: models/stock_move.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.move for aesthetic clinics:
#   - Category governance per-location (allowlist) at move-level
#   - Expiration policy enforcement for reserved/used lots (FEFO-friendly, but policy-driven)
#   - Convenience fields for clinical operation awareness
#   - UI helpers to review lots/move lines within clinical scope
#   - Hook methods so bridge addons (treatment/doctor/IoT/pricing/billing/etc.) can extend logic
#
# Notes
#   - All user-facing texts are in English.
#   - No hard dependency on other clinic_* modules; bridges may override *_clinic_hook_* methods.
#   - We don't change valuation/accounting here (kept in stock/account modules).

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    # =========================================================================
    # Convenience fields & flags
    # =========================================================================
    # Link back ke Clinical Treatment Product Usage
    # Link back to Clinic Inventory Adjustment (inverse for One2many on adjustment)
    clinic_adjustment_id = fields.Many2one(
        "clinic.inventory.adjustment",
        string="Inventory Adjustment (Clinic)",
        index=True,
        ondelete="set null",
        help="Adjustment document that generated this move, if any."
    )

    # (opsional tapi direkomendasikan, untuk menghindari error serupa pada usage)
    clinic_usage_id = fields.Many2one(
        "clinic.treatment.product.usage",
        string="Clinical Usage",
        index=True,
        ondelete="set null",
        help="Clinical usage record that generated this move, if any."
    )
    
    clinic_operation_type = fields.Selection(
        selection=[
            ('incoming', 'Incoming'),
            ('outgoing', 'Outgoing'),
            ('internal', 'Internal'),
        ],
        string="Clinic Operation Type",
        compute="_compute_clinic_operation_type",
        store=False,
        help="Convenience mapping inferred from picking type or locations to apply clinical rules."
    )

    clinic_notes = fields.Text(
        string="Clinic Notes",
        tracking=True,
        help="Optional clinical notes for this move (context, safety, special handling)."
    )

    clinic_has_expired_reserved = fields.Boolean(
        string="Has Expired Reserved Lots",
        compute="_compute_clinic_has_expired_reserved",
        store=False,
        help="True if any reserved lot on move lines is already expired according to lot's expiration date."
    )

    clinic_is_quarantine_move = fields.Boolean(
        string="Quarantine Move",
        compute="_compute_clinic_is_quarantine_move",
        store=False,
        help="True if either source or destination belongs to a Quarantine location subtree."
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _get_expiration_field_name(self):
        Lot = self.env["stock.lot"]
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    @api.depends("picking_id.picking_type_id.code", "location_id.usage", "location_dest_id.usage")
    def _compute_clinic_operation_type(self):
        for m in self:
            code = getattr(getattr(m.picking_id, "picking_type_id", False), "code", False)
            if code in ("incoming", "outgoing", "internal"):
                m.clinic_operation_type = code
            else:
                # Fallback by locations
                src = (m.location_id and m.location_id.usage) or ""
                dst = (m.location_dest_id and m.location_dest_id.usage) or ""
                if src in ("supplier", "transit") or dst == "internal":
                    m.clinic_operation_type = "incoming"
                elif src == "internal" and dst in ("customer", "transit"):
                    m.clinic_operation_type = "outgoing"
                else:
                    m.clinic_operation_type = "internal"

    @api.depends(
        "move_line_ids",
        "move_line_ids.lot_id",
        # "move_line_ids.lot_id.life_date",
        # "move_line_ids.lot_id.expiration_date",
    )
    def _compute_clinic_has_expired_reserved(self):
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for m in self:
            expired = False
            if exp_field:
                for ml in m.move_line_ids:
                    lot = ml.lot_id
                    if lot:
                        ld = getattr(lot, exp_field, False)
                        if ld and ld < today:
                            expired = True
                            break
            m.clinic_has_expired_reserved = expired

    @api.depends("location_id", "location_dest_id")
    def _compute_clinic_is_quarantine_move(self):
        for m in self:
            flag = False
            for loc in filter(None, [m.location_id, m.location_dest_id]):
                if "clinic_is_quarantine" in loc._fields and loc.clinic_is_quarantine:
                    flag = True
                    break
            m.clinic_is_quarantine_move = flag

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    @api.constrains("product_id", "product_uom_qty")
    def _check_service_product_not_moved(self):
        for m in self:
            if m.product_id and m.product_id.type == "service":
                raise ValidationError(_("Services cannot be moved in stock operations. Please use service lines instead."))

    # =========================================================================
    # OVERRIDES: Confirm / Assign / Done
    # =========================================================================
    def _action_confirm(self, merge=True, merge_into=False):
        """Pre-validate governance before confirming."""
        for move in self:
            move._clinic_pre_confirm_checks()
        res = super()._action_confirm(merge=merge, merge_into=merge_into)
        for move in self:
            move._clinic_hook_post_confirm()
        return res

    def _action_assign(self):
        """After reservation, verify expiration policy of reserved lots."""
        res = super()._action_assign()
        # Validate lots after standard reservation
        for move in self:
            move._clinic_validate_expiration_on_reserved_lots()
        return res

    def _action_done(self, cancel_backorder=False):
        """Final checks before marking done; then post hooks."""
        for move in self:
            move._clinic_pre_done_checks()
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in self:
            move._clinic_hook_post_done()
        return res

    # =========================================================================
    # PRE-CHECKS
    # =========================================================================
    def _clinic_pre_confirm_checks(self):
        """Run clinical checks before move confirm (category governance)."""
        self.ensure_one()
        self._clinic_check_category_governance()

    def _clinic_pre_done_checks(self):
        """Run clinical checks before move done (expiration+governance)."""
        self.ensure_one()
        self._clinic_check_category_governance()
        self._clinic_validate_expiration_on_reserved_lots()

    # =========================================================================
    # CATEGORY GOVERNANCE
    # =========================================================================
    def _clinic_check_category_governance(self):
        """Ensure product category is allowed in both source & destination if restricted."""
        self.ensure_one()
        product = self.product_id
        for loc in filter(None, [self.location_id, self.location_dest_id]):
            # Many2one values are already Odoo recordsets. ``self.env[...]``
            # returns a model recordset/proxy, not a Python class, so it must
            # never be passed as the second argument of isinstance().
            if "clinic_restrict_to_allowed_categories" in loc._fields:
                if loc.clinic_restrict_to_allowed_categories:
                    loc.clinic_validate_product_allowed(product)

    # =========================================================================
    # EXPIRATION POLICY VALIDATION
    # =========================================================================
    def _clinic_validate_expiration_on_reserved_lots(self):
        """Evaluate expiration policy for each reserved lot on move lines.

        - If any policy returns 'block' → raise UserError (operation halted).
        - If any policy returns 'warn'  → post chatter message on the move.
        """
        self.ensure_one()
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            return  # Stock Expiration module not present

        today = date.today()
        warnings = []
        for ml in self.move_line_ids:
            lot = ml.lot_id
            if not lot:
                continue
            ld = getattr(lot, exp_field, False)
            if not ld:
                continue
            if ld >= today:
                continue  # not expired

            src_status, src_msg = self._clinic_resolve_location_policy(self.location_id, lot)
            dst_status, dst_msg = self._clinic_resolve_location_policy(self.location_dest_id, lot)

            statuses = [src_status, dst_status]
            messages = list(filter(None, [src_msg, dst_msg]))
            if "block" in statuses:
                # Unreserve this move to avoid inconsistent state, then error out
                self._do_unreserve()
                raise UserError(_("Expired lot cannot be reserved due to policy: %s") % ("; ".join(messages) or "-"))
            elif "warn" in statuses:
                warnings.append(_("Reserved expired lot: %s. %s") % (lot.display_name, "; ".join(messages)))

        for msg in warnings:
            self.message_post(body=msg)

    def _clinic_resolve_location_policy(self, location, lot):
        """Return ('ok'|'warn'|'block', message) by asking location or warehouse policy."""
        if not location:
            return "ok", None
        if hasattr(location, "clinic_expiration_decision"):
            return location.clinic_expiration_decision(lot)
        # Fallback via picking's warehouse if available
        picking = self.picking_id
        warehouse = getattr(getattr(picking, "picking_type_id", False), "warehouse_id", False)
        if warehouse and hasattr(warehouse, "clinic_expiration_decision"):
            return warehouse.clinic_expiration_decision(lot)
        return "ok", None

    # =========================================================================
    # UI ACTION HELPERS
    # =========================================================================
    def action_view_move_lines(self):
        """Open move lines for this move."""
        self.ensure_one()
        action = self.env.ref("stock.stock_move_line_action").read()[0]
        action["domain"] = [("move_id", "=", self.id)]
        action["context"] = {"search_default_move_id": self.id}
        return action

    def action_view_reserved_lots(self):
        """Open reserved lots for this move."""
        self.ensure_one()
        action = self.env.ref("stock.action_production_lot_form").read()[0]
        lot_ids = self.move_line_ids.mapped("lot_id").ids
        action["domain"] = [("id", "in", lot_ids)]
        return action

    # =========================================================================
    # PUBLIC APIS (for other modules)
    # =========================================================================
    def clinic_is_quarantine_related(self):
        """Return True if move is related to quarantine (src/dst in quarantine subtree)."""
        self.ensure_one()
        return self.clinic_is_quarantine_move

    def clinic_collect_reserved_expired_lots(self):
        """Return recordset of expired lots reserved on this move (best-effort)."""
        self.ensure_one()
        Lot = self.env["stock.lot"]
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            return Lot.browse()
        today = date.today()
        lots = Lot.browse()
        for ml in self.move_line_ids:
            lot = ml.lot_id
            if lot:
                ld = getattr(lot, exp_field, False)
                if ld and ld < today:
                    lots |= lot
        return lots

    # =========================================================================
    # HOOKS (override in bridge addons)
    # =========================================================================
    def _clinic_hook_post_confirm(self):
        """Called after _action_confirm. Bridges may:
           - attach clinical references (treatment/patient/doctor)
           - create analytical tags/cost centers
           - adjust routes by department/room
        """
        return

    def _clinic_hook_post_done(self):
        """Called after _action_done. Bridges may:
           - record clinical consumption
           - post membership rewards
           - trigger billing/finance signals
           - update device maintenance counters
        """
        return

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _do_unreserve(self):
        """Unreserve this move safely (wrapper for readability)."""
        # In recent Odoo versions, calling 'do_unreserve' on the move's picking often unreserves all moves.
        # Here we keep it scoped when possible.
        try:
            super(StockMove, self).do_unreserve()
        except Exception:
            # Fallback: call on picking if available
            if self.picking_id:
                self.picking_id.do_unreserve()
        return True

