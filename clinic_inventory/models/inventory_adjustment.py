# -*- coding: utf-8 -*-
# File: models/inventory_adjustment.py
# Module: clinic_inventory
#
# Purpose
#   Clinical-friendly inventory adjustment wrapper:
#   - Define a document with lines (product/lot/location) and counted quantities
#   - Snapshot expected quantities at preparation time (optional)
#   - Compute differences and apply corrections via stock moves to/from an Inventory location
#   - Respect location/category governance and expiration policies (with auto-route to Quarantine)
#   - Multi-warehouse aware; safe hooks for 25 ClinicOne addons (no circular deps)
#
# Notes
#   - All user-facing texts are in English.
#   - We DO NOT rely on 'stock.inventory' model to avoid version differences; we create direct moves.
#   - Valuation/accounting stays in core (stock_account). We only create stock moves.
#
# Flow
#   draft → confirmed → applied (done) / cancel
#
# Integrations
#   - stock_location.py: governance flags & expiration policy helpers
#   - stock_warehouse.py: default Inventory/Quarantine/Pharmacy/Treatment root locs
#   - patient_product_history.py: not used directly here (no patient context)
#   - doctor_allowed_products.py: not relevant to adjustments
#
# Hooks
#   - _clinic_hook_pre_confirm(self)
#   - _clinic_hook_post_apply(self, moves)
#   - line-level: _clinic_hook_before_line_move(self, move_vals) for customization

from datetime import date
from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Master: Clinical Inventory Adjustment
# =============================================================================
class ClinicInventoryAdjustment(models.Model):
    _name = "clinic.inventory.adjustment"
    _description = "Clinical Inventory Adjustment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    # Identity & state ---------------------------------------------------------
    name = fields.Char(
        string="Reference",
        default="/",
        readonly=True,
        copy=False,
        help="Auto-generated adjustment reference."
    )
    date = fields.Datetime(
        string="Adjustment Date",
        default=fields.Datetime.now,
        tracking=True,
        help="Date and time when the count/correction is performed."
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("applied", "Applied"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    # Company / warehouse / scope ---------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        domain="[('company_id','=',company_id)]",
        tracking=True,
        help="Warehouse context for this adjustment."
    )
    root_location_id = fields.Many2one(
        "stock.location",
        string="Root Location",
        domain="[('usage','=','internal'), ('id','child_of', warehouse_id.view_location_id)]",
        tracking=True,
        help="Internal location (root) where counting happens (includes children)."
    )
    include_zero_expected = fields.Boolean(
        string="Include Zero-Expected Lines",
        default=False,
        help="If checked, you can add lines for products not currently on-hand at the selected scope."
    )

    # Policy controls ----------------------------------------------------------
    use_snapshot = fields.Boolean(
        string="Use Snapshot at Preparation",
        default=True,
        help="If enabled, differences are computed against the snapshot quantities captured at 'Prepare Lines'."
    )
    snapshot_at = fields.Datetime(
        string="Snapshot Time",
        readonly=True,
        help="When expected quantities were captured into snapshot fields."
    )
    route_expired_to_quarantine = fields.Boolean(
        string="Route Expired Surplus to Quarantine",
        default=True,
        help="When counting surplus of an expired lot, route incoming move to Quarantine if policy blocks the location."
    )
    enforce_governance = fields.Boolean(
        string="Enforce Location Governance",
        default=True,
        help="If enabled, category allowlist at locations is validated before applying moves."
    )

    # Lines & counters ---------------------------------------------------------
    line_ids = fields.One2many(
        "clinic.inventory.adjustment.line",
        "adjustment_id",
        string="Lines",
        copy=True
    )
    total_lines = fields.Integer(
        string="# Lines",
        compute="_compute_totals",
        store=False
    )
    total_diff_qty = fields.Float(
        string="Total Difference",
        compute="_compute_totals",
        store=False,
        help="Sum of line differences (counted - expected, using snapshot or current based on setting)."
    )
    move_ids = fields.One2many(
        comodel_name="stock.move",
        inverse_name="clinic_adjustment_id",
        string="Generated Moves",
        readonly=True,
        copy=False,
        help="Moves created when applying this adjustment."
    )
    generated_move_count = fields.Integer(
        string="# Moves",
        compute="_compute_move_count",
        store=False
    )

    # Responsibility -----------------------------------------------------------
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )
    note = fields.Char(
        string="Note",
        help="Optional short note (visible in chatter)."
    )

    # --- use stock.lot instead of stock.lot ---
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('product_id','=',product_id)]",
        help="Lot/serial being counted (if the product is tracked)."
    )

    # --- robust helper: prefer expiration_date, fallback life_date if present ---
    def _get_expiration_field_name(self):
        Lot = self.env["stock.lot"]
        # prefer Odoo 18 CE field name
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        # compatibility (jika environment lama / modul lain masih inject life_date)
        if "life_date" in Lot._fields:
            return "life_date"
        return None

    # --- depends: JANGAN refer ke sub-field yang opsional; cukup lot_id saja ---
    @api.depends("lot_id")
    def _compute_expired_flag(self):
        today = date.today()
        exp_field = self._get_expiration_field_name()
        for line in self:
            flag = False
            if line.lot_id and exp_field:
                # access dynamically: no hard depends on specific sub-field
                expiry = getattr(line.lot_id, exp_field, False)
                flag = bool(expiry and expiry < today)
            line.is_expired = flag

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("line_ids", "line_ids.diff_qty_snapshot", "line_ids.diff_qty_current", "use_snapshot")
    def _compute_totals(self):
        for adj in self:
            adj.total_lines = len(adj.line_ids)
            if adj.use_snapshot:
                adj.total_diff_qty = sum(l.diff_qty_snapshot for l in adj.line_ids)
            else:
                adj.total_diff_qty = sum(l.diff_qty_current for l in adj.line_ids)

    def _compute_move_count(self):
        for adj in self:
            adj.generated_move_count = len(adj.move_ids)

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.inventory.adjustment") or "/"
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # PREPARE & STATE
    # -------------------------------------------------------------------------
    def action_view_moves(self):
        """Open stock moves generated by this inventory adjustment."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Stock Moves"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.move_ids.ids)],
            "context": {"create": False},
        }

    def action_prepare_lines(self):
        """Snapshot expected quantities and (optionally) auto-build lines from quants within scope."""
        Quant = self.env["stock.quant"]
        for adj in self:
            if not adj.warehouse_id:
                raise UserError(_("Please set a Warehouse first."))
            if not adj.root_location_id:
                adj.root_location_id = adj.warehouse_id.view_location_id
            if not adj.root_location_id:
                raise UserError(_("Could not resolve a Root Location."))

            # Snapshot current expected quantities for existing lines
            for line in adj.line_ids:
                line._snapshot_expected()

            # Auto-build lines from existing quants if no lines present
            if not adj.line_ids:
                domain = [
                    ("location_id", "child_of", adj.root_location_id.id),
                    ("quantity", ">", 0),
                ]
                rows = Quant.read_group(
                    domain, ["product_id", "location_id", "lot_id", "quantity:sum", "product_uom_id"], ["product_id", "location_id", "lot_id"]
                )
                new_lines = []
                for r in rows:
                    product_id = r["product_id"][0]
                    location_id = r["location_id"][0]
                    lot_id = r["lot_id"][0] if r.get("lot_id") else False
                    qty = r.get("quantity", 0.0) or 0.0
                    uom_id = r.get("product_uom_id", False) or self.env["product.product"].browse(product_id).uom_id.id
                    new_lines.append((0, 0, {
                        "product_id": product_id,
                        "product_uom": uom_id,
                        "location_id": location_id,
                        "lot_id": lot_id,
                        "expected_qty_current": qty,
                        "snapshot_qty": qty,  # initial snapshot equals current
                    }))
                if new_lines:
                    adj.write({"line_ids": new_lines})

            # Mark snapshot time
            adj.snapshot_at = fields.Datetime.now()
            # Move to confirmed (ready to count)
            adj.state = "confirmed"
            adj.message_post(body=_("Lines prepared and snapshot captured at %s.") % (fields.Datetime.to_string(adj.snapshot_at),))
        return True

    def action_confirm(self):
        for adj in self:
            if adj.state not in ("draft", "confirmed"):
                continue
            if not adj.line_ids:
                raise UserError(_("Please add lines or use 'Prepare Lines' first."))
            adj._clinic_hook_pre_confirm()
            adj.state = "confirmed"
            adj.message_post(body=_("Adjustment confirmed."))
        return True

    def action_cancel(self):
        for adj in self:
            if adj.state == "applied" and adj.move_ids:
                raise UserError(_("Cannot cancel an applied adjustment with generated moves. Please manage reversals manually."))
            adj.state = "cancel"
            adj.message_post(body=_("Adjustment cancelled."))
        return True

    def action_reset_to_draft(self):
        for adj in self:
            if adj.move_ids:
                raise UserError(_("Cannot reset to Draft after moves have been created."))
            adj.state = "draft"
        return True

    # -------------------------------------------------------------------------
    # APPLY (create moves)
    # -------------------------------------------------------------------------
    def action_apply(self):
        """Create and complete stock moves for all differences."""
        Move = self.env["stock.move"]
        for adj in self:
            if adj.state != "confirmed":
                raise UserError(_("Adjustment must be in Confirmed state to apply."))
            if not adj.line_ids:
                raise UserError(_("No lines to apply."))

            inv_loc = adj._resolve_inventory_location()
            if not inv_loc:
                raise UserError(_("No Inventory location found under the selected Warehouse."))

            moves = self.env["stock.move"].browse()

            # Validate governance (category allowlist) if enabled
            if adj.enforce_governance:
                for line in adj.line_ids:
                    if getattr(line.location_id, "clinic_restrict_to_allowed_categories", False):
                        line.location_id.clinic_validate_product_allowed(line.product_id)

            # Build and post moves
            for line in adj.line_ids:
                diff = line.diff_qty_snapshot if adj.use_snapshot else line.diff_qty_current
                if abs(diff) < 1e-9:
                    continue  # no change

                move_vals = {
                    "name": _("Clinical inventory adjustment for %s") % (line.product_id.display_name,),
                    "company_id": adj.company_id.id,
                    "product_id": line.product_id.id,
                    "product_uom": line.product_uom.id,
                    "product_uom_qty": abs(diff),
                    "date": adj.date or fields.Datetime.now(),
                }

                # Direction: deficit -> internal→inventory; surplus -> inventory→internal (or quarantine if policy blocks)
                src = None
                dst = None
                if diff < 0:  # deficit (counted < expected) → decrease stock at location
                    src = line.location_id
                    dst = inv_loc
                else:        # surplus (counted > expected) → increase stock at location
                    # If expired and policy blocks at target location, route to quarantine when enabled
                    dst_candidate = line.location_id
                    src_candidate = inv_loc
                    if line._is_lot_expired():
                        status, msg = adj._resolve_location_policy(dst_candidate, line.lot_id)
                        if status == "block":
                            if adj.route_expired_to_quarantine:
                                qloc = adj._resolve_quarantine_location(line.location_id)
                                if not qloc:
                                    raise UserError(_("Expired lot surplus cannot be stored at '%s' and no Quarantine is configured.")
                                                    % dst_candidate.display_name)
                                dst_candidate = qloc
                                # Post notice
                                adj.message_post(body=_("Surplus expired lot routed to Quarantine: %s") %
                                                     (line.lot_id.display_name if line.lot_id else line.product_id.display_name))
                            else:
                                raise UserError(_("Expired lot surplus is blocked by policy at '%s'. %s")
                                                % (dst_candidate.display_name, msg or ""))
                        elif status == "warn":
                            adj.message_post(body=_("Surplus expired lot stored at '%s': %s") %
                                                 (dst_candidate.display_name, msg or _("Warning")))
                    src = src_candidate
                    dst = dst_candidate

                move_vals.update({
                    "location_id": src.id,
                    "location_dest_id": dst.id,
                })

                # Allow line-level customization before creation
                move_vals = line._clinic_hook_before_line_move(move_vals)

                move = Move.create(move_vals)
                # Move line with lot if given
                ml_vals = {
                    "move_id": move.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_uom.id,
                    "quantity": abs(diff),
                    "location_id": src.id,
                    "location_dest_id": dst.id,
                }
                if line.lot_id:
                    ml_vals["lot_id"] = line.lot_id.id
                move.move_line_ids = [(0, 0, ml_vals)]

                # Link back to this adjustment (dynamic field ensured by _register_hook)
                if "clinic_adjustment_id" in move._fields:
                    move.clinic_adjustment_id = adj.id

                moves |= move

            if not moves:
                raise UserError(_("No differences detected; nothing to apply."))

            # Confirm & done
            moves._action_confirm()
            moves._action_done()

            # Post-hook
            adj._clinic_hook_post_apply(moves)
            adj.state = "applied"
            adj.message_post(body=_("Adjustment applied: %s move(s).") % len(moves))
        return True

    # -------------------------------------------------------------------------
    # RESOLUTION HELPERS
    # -------------------------------------------------------------------------
    def _resolve_inventory_location(self):
        """Find an 'inventory' usage location under the warehouse view."""
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        wh = self.warehouse_id
        if not wh:
            return False
        inv = Location.search([
            ("usage", "=", "inventory"),
            ("id", "child_of", wh.view_location_id.id),
        ], limit=1)
        if inv:
            return inv
        # As a last resort, any inventory location
        return Location.search([("usage", "=", "inventory")], limit=1)

    def _resolve_quarantine_location(self, base_location):
        """Find a quarantine location walking up the tree or from warehouse config."""
        self.ensure_one()
        # Walk up parents
        cur = base_location
        while cur:
            if getattr(cur, "clinic_is_quarantine", False):
                return cur
            cur = cur.location_id
        # Warehouse-level config
        wh = self.warehouse_id
        if wh and getattr(wh, "clinic_quarantine_location_id", False):
            return wh.clinic_quarantine_location_id
        return False

    def _resolve_location_policy(self, location, lot):
        """Return ('ok'|'warn'|'block', message) for storing a lot at location."""
        if not location:
            return "ok", None
        if hasattr(location, "clinic_expiration_decision"):
            return location.clinic_expiration_decision(lot or False)
        wh = self.warehouse_id
        if wh and hasattr(wh, "clinic_expiration_decision"):
            return wh.clinic_expiration_decision(lot or False)
        return "ok", None

    # -------------------------------------------------------------------------
    # HOOKS (override in bridge addons)
    # -------------------------------------------------------------------------
    def _clinic_hook_pre_confirm(self):
        """Called before transitioning to Confirmed state."""
        return

    def _clinic_hook_post_apply(self, moves):
        """Called after moves are completed."""
        return


# =============================================================================
# Lines: Clinical Inventory Adjustment Line
# =============================================================================
class ClinicInventoryAdjustmentLine(models.Model):
    _name = "clinic.inventory.adjustment.line"
    _description = "Clinical Inventory Adjustment Line"
    _order = "sequence, id"

    # Link & ordering ----------------------------------------------------------
    adjustment_id = fields.Many2one(
        "clinic.inventory.adjustment",
        string="Adjustment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    # Product / UoM / Lot / Location -----------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain="[('type','!=','service')]",
        help="Product being counted at the selected location."
    )
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
        default=lambda self: self.env.ref("uom.product_uom_unit"),
        help="Unit of measure for quantities on this line."
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('product_id','=',product_id)]",
        help="Lot/serial being counted (if the product is tracked)."
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        required=True,
        domain=lambda self: self._domain_location_internal(),
        help="Concrete internal location where the counting occurs."
    )

    # Expected / Snapshot / Counted -------------------------------------------
    expected_qty_current = fields.Float(
        string="Expected (Current)",
        compute="_compute_expected_current",
        store=False,
        digits="Product Unit of Measure",
        help="On-hand quantity right now at the location scope (best-effort from quants)."
    )
    snapshot_qty = fields.Float(
        string="Expected (Snapshot)",
        help="Snapshot of expected quantity captured at 'Prepare Lines'."
    )
    counted_qty = fields.Float(
        string="Counted",
        digits="Product Unit of Measure",
        help="Quantity counted physically at this location."
    )

    # Differences --------------------------------------------------------------
    diff_qty_current = fields.Float(
        string="Difference (vs Current)",
        compute="_compute_differences",
        store=False,
        help="counted - expected_current"
    )
    diff_qty_snapshot = fields.Float(
        string="Difference (vs Snapshot)",
        compute="_compute_differences",
        store=False,
        help="counted - snapshot"
    )

    # UI / Flags ---------------------------------------------------------------
    is_expired = fields.Boolean(
        string="Expired Lot",
        compute="_compute_expired_flag",
        search="_search_is_expired",
        store=False,
        help="True if the selected lot is already expired."
    )
    note = fields.Char(
        string="Note",
        help="Optional short note."
    )

    # -------------------------------------------------------------------------
    # DOMAINS
    # -------------------------------------------------------------------------
    def _domain_location_internal(self):
        # Domain can't capture warehouse here (depends on parent), so keep generic internal filter
        return [("usage", "=", "internal")]

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("product_id", "lot_id", "location_id")
    def _compute_expected_current(self):
        Quant = self.env["stock.quant"]
        for line in self:
            qty = 0.0
            if line.product_id and line.location_id:
                domain = [
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "child_of", line.location_id.id),
                ]
                if line.lot_id:
                    domain.append(("lot_id", "=", line.lot_id.id))
                for r in Quant.read_group(domain, ["quantity:sum"], []):
                    qty += r.get("quantity", 0.0) or 0.0
            line.expected_qty_current = qty

    @api.depends("counted_qty", "expected_qty_current", "snapshot_qty")
    def _compute_differences(self):
        for line in self:
            counted = line.counted_qty or 0.0
            line.diff_qty_current = counted - (line.expected_qty_current or 0.0)
            line.diff_qty_snapshot = counted - (line.snapshot_qty or 0.0)

    def _get_expiration_field_name(self):
        Lot = self.env["stock.lot"]
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    @api.depends("lot_id", "lot_id.expiration_date")
    def _compute_expired_flag(self):
        today = date.today()
        exp_field = self._get_expiration_field_name()
        for line in self:
            flag = False
            if line.lot_id and exp_field:
                ld = getattr(line.lot_id, exp_field, False)
                flag = bool(ld and ld < today)
            line.is_expired = flag

    def _search_is_expired(self, operator, value):
        """
        Make the non-stored ``is_expired`` helper searchable.

        Odoo validates search-view domains when the view is loaded.  A
        non-stored computed field therefore needs an explicit search method.
        We translate the Boolean condition to the real searchable expiration
        field on ``stock.lot`` and keep the compatibility fallback dynamic.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                _("Expired Lot can only be searched with '=' or '!=' and a Boolean value.")
            )

        want_expired = value if operator == "=" else not value
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            return Domain.FALSE if want_expired else Domain.TRUE

        today = fields.Date.context_today(self)
        expired_domain = Domain(f"lot_id.{exp_field}", "<", today)
        return expired_domain if want_expired else ~expired_domain

    # -------------------------------------------------------------------------
    # SNAPSHOT
    # -------------------------------------------------------------------------
    def action_open_adjustment(self):
        """Open the parent adjustment from an embedded One2many line."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventory Adjustment"),
            "res_model": "clinic.inventory.adjustment",
            "view_mode": "form",
            "res_id": self.adjustment_id.id,
            "target": "current",
        }

    def _snapshot_expected(self):
        """Write current expected value into snapshot."""
        for line in self:
            line.snapshot_qty = line.expected_qty_current

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("product_id")
    def _check_not_service(self):
        for l in self:
            if l.product_id and l.product_id.type == "service":
                raise ValidationError(_("Services cannot be adjusted in inventory."))

    @api.constrains("product_uom", "product_id")
    def _check_uom_category(self):
        for l in self:
            if l.product_id and l.product_uom and l.product_uom.category_id != l.product_id.uom_id.category_id:
                raise ValidationError(_("The line UoM must belong to the same category as the product UoM."))

    @api.constrains("counted_qty")
    def _check_counted_non_negative(self):
        for l in self:
            if l.counted_qty is not None and l.counted_qty < 0.0:
                raise ValidationError(_("Counted quantity cannot be negative."))

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def _is_lot_expired(self):
        self.ensure_one()
        return bool(self.is_expired)

    # Hook per-line before creating move values
    def _clinic_hook_before_line_move(self, move_vals):
        """Bridges may adjust name/analytics/ownership here. Keep keys core-safe."""
        return move_vals


# =============================================================================
# Dynamic link field on stock.move (back-reference to adjustment)
# =============================================================================
def _ensure_clinic_adjustment_field_on_move(env):
    """Dynamically add Many2one field 'clinic_adjustment_id' on stock.move if missing."""
    Move = env["stock.move"]
    if "clinic_adjustment_id" in Move._fields:
        return
    from odoo.fields import Many2one
    Move._add_field(
        "clinic_adjustment_id",
        Many2one(
            comodel_name="clinic.inventory.adjustment",
            string="Clinical Adjustment",
            help="Back-reference to the clinical inventory adjustment document.",
            ondelete="set null",
        ),
    )


def _register_hook(env):
    _ensure_clinic_adjustment_field_on_move(env)

