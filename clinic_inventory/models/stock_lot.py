# -*- coding: utf-8 -*-
# File: models/stock_lot.py
# Module: clinic_inventory

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    # =========================================================================
    # Additional clinical metadata
    # =========================================================================
    clinic_supplier_batch = fields.Char(
        string="Supplier Batch/Ref",
        tracking=True,
        help="Optional supplier-provided batch/reference number printed on packaging or COA.",
    )
    clinic_manufacture_date = fields.Date(
        string="Manufacturing Date",
        tracking=True,
        help="Optional manufacturing/production date for this lot.",
    )
    clinic_received_date = fields.Date(
        string="Received Date",
        tracking=True,
        help="Date this lot was received into the clinic (first receipt).",
    )
    clinic_quality_state = fields.Selection(
        selection=[
            ("released", "Released"),
            ("on_hold", "On Hold"),
            ("rejected", "Rejected"),
        ],
        string="Quality State",
        default="released",
        tracking=True,
        help="Operational quality disposition for this lot.",
    )
    clinic_quarantine_reason = fields.Text(
        string="Quarantine/Hold Reason",
        tracking=True,
        help="Optional reason when this lot is quarantined or placed on hold.",
    )

    # =========================================================================
    # Expiration awareness
    # =========================================================================
    clinic_expiration_alert_days = fields.Integer(
        related="product_id.product_tmpl_id.expiration_alert_days",
        string="Expiration Alert (Days)",
        store=True,
        readonly=True,
    )

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
        help="State derived from expiration date and product alert threshold.",
    )
    clinic_is_expired = fields.Boolean(
        string="Is Expired",
        compute="_compute_clinic_expiry",
        store=False,
        help="True when the lot's expiration date is earlier than today.",
    )

    # =========================================================================
    # Counters & convenience
    # =========================================================================
    clinic_quants_count = fields.Integer(
        string="# Quants",
        compute="_compute_clinic_counters",
        help="Number of quants associated with this lot across all locations.",
    )
    clinic_onhand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_clinic_counters",
        help="Total on-hand quantity across all locations for this lot (equals 'product_qty').",
    )
    clinic_primary_location_id = fields.Many2one(
        "stock.location",
        string="Primary Location",
        compute="_compute_clinic_counters",
        help="Internal location with the highest on-hand quantity for this lot (best-effort).",
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_expiration_field_name(self):
        if "life_date" in self._fields:
            return "life_date"
        if "expiration_date" in self._fields:
            return "expiration_date"
        return None

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("expiration_date", "product_id.product_tmpl_id.expiration_alert_days")
    def _compute_clinic_expiry(self):
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for lot in self:
            if not exp_field:
                lot.clinic_days_to_expiry = 0
                lot.clinic_expiration_state = "none"
                lot.clinic_is_expired = False
                continue
            ld = getattr(lot, exp_field, False)
            if not ld:
                lot.clinic_days_to_expiry = 0
                lot.clinic_expiration_state = "none"
                lot.clinic_is_expired = False
                continue
            delta = (ld - today).days
            lot.clinic_days_to_expiry = delta
            lot.clinic_is_expired = delta < 0
            if delta < 0:
                lot.clinic_expiration_state = "expired"
            else:
                alert = lot.clinic_expiration_alert_days or 0
                lot.clinic_expiration_state = "soon" if alert and delta <= alert else "ok"

    def _compute_clinic_counters(self):
        Quant = self.env["stock.quant"]
        for lot in self:
            quants = Quant.search([("lot_id", "=", lot.id)])
            lot.clinic_quants_count = len(quants)
            onhand = 0.0
            per_loc = {}
            for q in quants:
                qty = q.quantity or 0.0
                onhand += qty
                per_loc[q.location_id] = per_loc.get(q.location_id, 0.0) + qty
            lot.clinic_onhand_qty = onhand
            best_loc = False
            best_qty = 0.0
            for loc, qty in per_loc.items():
                if loc.usage == "internal" and qty > best_qty:
                    best_qty = qty
                    best_loc = loc
            lot.clinic_primary_location_id = best_loc or False

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("product_id", "expiration_date")
    def _check_expiration_presence_when_required(self):
        exp_field = self._get_expiration_field_name()
        for lot in self:
            has_exp = getattr(lot.product_id.product_tmpl_id, "has_expiration", False)
            if has_exp and exp_field and not getattr(lot, exp_field, False):
                raise ValidationError(_("This product requires expiration tracking; please set the lot expiration date."))

    @api.constrains("clinic_manufacture_date", "expiration_date")
    def _check_mfg_before_expiry(self):
        exp_field = self._get_expiration_field_name()
        for lot in self:
            mfg = lot.clinic_manufacture_date
            if mfg and exp_field and getattr(lot, exp_field, False):
                if mfg > getattr(lot, exp_field):
                    raise ValidationError(_("Manufacturing Date cannot be later than the expiration date."))

    @api.constrains("clinic_received_date", "clinic_manufacture_date")
    def _check_received_after_mfg(self):
        for lot in self:
            if lot.clinic_received_date and lot.clinic_manufacture_date:
                if lot.clinic_received_date < lot.clinic_manufacture_date:
                    raise ValidationError(_("Received Date cannot be earlier than Manufacturing Date."))

    # -------------------------------------------------------------------------
    # WRITE OVERRIDE
    # -------------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        exp_field = self._get_expiration_field_name()
        if exp_field and (exp_field in vals):
            for lot in self:
                lot.message_post(body=_("Expiration date updated to %s.") % (fields.Date.to_string(getattr(lot, exp_field)) or "-"))
        for lot in self:
            lot._clinic_hook_post_write(vals)
        return res

    # -------------------------------------------------------------------------
    # POLICY HELPERS
    # -------------------------------------------------------------------------
    def _clinic_resolve_location_policy(self, location):
        self.ensure_one()
        if not location:
            return "ok", None
        if hasattr(location, "clinic_expiration_decision"):
            return location.clinic_expiration_decision(self)
        Warehouse = self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", location.id)], limit=1)
        if wh and hasattr(wh, "clinic_expiration_decision"):
            return wh.clinic_expiration_decision(self)
        return "ok", None

    # -------------------------------------------------------------------------
    # UI ACTIONS
    # -------------------------------------------------------------------------
    def action_view_quants(self):
        self.ensure_one()
        action = self.env.ref("stock.quants_action").read()[0]
        action["domain"] = [("lot_id", "=", self.id)]
        return action

    def action_view_moves(self):
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("move_line_ids.lot_id", "=", self.id)]
        return action

    def action_suggest_quarantine_transfer(self):
        self.ensure_one()
        if not self.product_id or self.product_id.type == "service":
            raise UserError(_("Services cannot be transferred to quarantine."))

        Quant = self.env["stock.quant"]
        rows = Quant.read_group(
            [("lot_id", "=", self.id), ("location_id.usage", "=", "internal")],
            ["location_id", "quantity:sum"], ["location_id"]
        )
        if not rows:
            raise UserError(_("No on-hand quantity in internal locations for this lot."))

        src_loc_id = max(rows, key=lambda r: r.get("quantity", 0.0) or 0.0)["location_id"][0]
        src_loc = self.env["stock.location"].browse(src_loc_id)

        Warehouse = self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", src_loc.id)], limit=1)
        if not wh:
            raise UserError(_("No warehouse found for the source location."))

        dest_loc = False
        if getattr(wh, "clinic_quarantine_location_id", False):
            dest_loc = wh.clinic_quarantine_location_id
        else:
            cur = src_loc
            while cur and not dest_loc:
                if getattr(cur, "clinic_is_quarantine", False):
                    dest_loc = cur
                    break
                cur = cur.location_id
        if not dest_loc:
            raise UserError(_("No quarantine location configured for the resolved warehouse."))
        if not wh.int_type_id:
            raise UserError(_("No internal picking type found for the resolved warehouse."))

        qty_at_src = 0.0
        for r in rows:
            if r["location_id"][0] == src_loc.id:
                qty_at_src = r.get("quantity", 0.0) or 0.0
                break
        if qty_at_src <= 0.0:
            raise UserError(_("No quantity available at the chosen source location."))

        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action.update({
            "context": {
                "default_picking_type_id": wh.int_type_id.id,
                "default_location_id": src_loc.id,
                "default_location_dest_id": dest_loc.id,
                "default_move_ids_without_package": [(0, 0, {
                    "name": _("Quarantine transfer for %s (Lot: %s)") % (self.product_id.display_name, self.display_name),
                    "product_id": self.product_id.id,
                    "product_uom": self.product_id.uom_id.id,
                    "product_uom_qty": qty_at_src,
                    "location_id": src_loc.id,
                    "location_dest_id": dest_loc.id,
                })],
                "default_clinic_is_quarantine_transfer": True,
                "default_lot_id": self.id,
                "lot_id": self.id,
            },
        })
        return action

    # -------------------------------------------------------------------------
    # NAME / PUBLIC APIS / HOOKS
    # -------------------------------------------------------------------------

    # IMPORTANT (Odoo 19): ``life_date`` is only a compatibility fallback in
    # ``_get_expiration_field_name()``. Optional/fallback field names must not
    # be declared in @api.depends because the registry resolves every dependency
    # eagerly and aborts module installation when that field is absent.
    # ``clinic_expiration_state`` already depends on ``expiration_date``, so it
    # safely invalidates this display name when the expiration date changes.
    @api.depends(
        "name",
        "product_id",
        "clinic_expiration_state",
    )
    def _compute_display_name(self):
        """Show lot identity, product and expiry status in Odoo 19."""
        super()._compute_display_name()
        for lot in self:
            parts = [lot.name or ""]
            if lot.product_id:
                parts.append(lot.product_id.display_name)
            exp_field = lot._get_expiration_field_name()
            exp_value = getattr(lot, exp_field, False) if exp_field else False
            if exp_value:
                parts.append(_("exp: %s") % fields.Date.to_string(exp_value))
            if lot.clinic_expiration_state == "expired":
                parts.append("[EXPIRED]")
            elif lot.clinic_expiration_state == "soon":
                parts.append("[SOON]")
            lot.display_name = " | ".join(part for part in parts if part)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    def clinic_get_is_expired(self):
        """Return the computed expiration flag without colliding with the field name.

        ``clinic_is_expired`` is a Boolean field.  Python class namespaces cannot
        safely contain a field and a method with the same name: the later method
        definition replaces the field object before Odoo builds the model.
        """
        self.ensure_one()
        return bool(self.clinic_is_expired)

    def clinic_days_until_expiry(self):
        self.ensure_one()
        return int(self.clinic_days_to_expiry or 0)

    def clinic_policy_status_in_location(self, location):
        self.ensure_one()
        return self._clinic_resolve_location_policy(location)

    def _clinic_hook_post_write(self, vals):
        return

