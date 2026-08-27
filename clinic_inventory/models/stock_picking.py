# -*- coding: utf-8 -*-
# File: models/stock_picking.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.picking for aesthetic clinics:
#   - Expiration policy check (warehouse/location: block/warn/allow)
#   - Optional receipt temperature validation for incoming shipments
#   - Category governance per-location (allowlist)
#   - Scopes & helpers to navigate clinical locations
#   - Hook methods for cross-module integrations (treatment, room-device, IoT, pricing, billing, etc.)
#
# Notes
#   - All user-facing texts are in English.
#   - No hard dependency on other clinic_* modules; bridges may override *_clinic_hook_* methods.
#   - We do NOT change stock valuation or move accounting here.

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # =========================================================================
    # Convenience fields
    # =========================================================================
    clinic_operation_type = fields.Selection(
        selection=[
            ('incoming', 'Incoming'),
            ('outgoing', 'Outgoing'),
            ('internal', 'Internal'),
        ],
        string="Clinic Operation Type",
        compute="_compute_clinic_operation_type",
        store=False,
        help="Convenience mapping from picking type code for clinical rules.",
    )

    clinic_receipt_temperature_c = fields.Float(
        string="Measured Receipt Temperature (°C)",
        help=(
            "Optional measured temperature for incoming goods validation. "
            "Warehouse/location policies may validate this against storage thresholds."
        ),
        digits=(16, 2),
        tracking=True,
    )

    clinic_is_quarantine_transfer = fields.Boolean(
        string="Quarantine Transfer",
        help="Flag this picking as a quarantine/hold transfer (damaged/expired/suspect items).",
        tracking=True,
    )

    clinic_notes = fields.Text(
        string="Clinic Notes",
        help="Optional clinical notes for this transfer (context, safety, special handling).",
        tracking=True,
    )

    clinic_has_expired_lines = fields.Boolean(
        string="Has Expired Lot Lines",
        compute="_compute_clinic_expired_flags",
        store=False,
        help="True if any move line uses a lot that is already expired (based on expiration field).",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _get_expiration_field_name(self):
        """Return the lot field used as end-of-life date."""
        Lot = self.env["stock.lot"]
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    @api.depends("picking_type_id.code")
    def _compute_clinic_operation_type(self):
        for p in self:
            code = (p.picking_type_id and p.picking_type_id.code) or ""
            if code == "incoming":
                p.clinic_operation_type = "incoming"
            elif code == "outgoing":
                p.clinic_operation_type = "outgoing"
            else:
                p.clinic_operation_type = "internal"

    @api.depends("move_line_ids", "move_line_ids.lot_id", "move_line_ids.lot_id", "move_line_ids.lot_id.expiration_date")
    def _compute_clinic_expired_flags(self):
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for p in self:
            expired = False
            if exp_field:
                for ml in p.move_line_ids:
                    lot = ml.lot_id
                    if lot:
                        ld = getattr(lot, exp_field, False)
                        if ld and ld < today:
                            expired = True
                            break
            p.clinic_has_expired_lines = expired

    # =========================================================================
    # ONCHANGE / VALIDATIONS
    # =========================================================================
    @api.constrains("clinic_receipt_temperature_c")
    def _check_receipt_temperature_range(self):
        for p in self:
            # No strict constraint; bridges may add policy-based hard limits
            if p.clinic_receipt_temperature_c and abs(p.clinic_receipt_temperature_c) > 200:
                raise ValidationError(_("Measured temperature looks invalid (|°C| > 200). Please recheck."))

    @api.constrains("clinic_is_quarantine_transfer", "location_dest_id")
    def _check_quarantine_dest(self):
        for p in self:
            if p.clinic_is_quarantine_transfer and p.location_dest_id:
                # If destination location has 'quarantine' flag, it's fine; otherwise warn by raising explicit error
                if "clinic_is_quarantine" in p.location_dest_id._fields and not p.location_dest_id.clinic_is_quarantine:
                    raise ValidationError(_("Quarantine Transfer requires destination location flagged as Quarantine."))

    # =========================================================================
    # MAIN OVERRIDES: pre/post validations around transfer
    # =========================================================================
    def button_validate(self):
        """Override to run clinical validations before Odoo validates the picking."""
        for picking in self:
            picking._clinic_validate_before_button_validate()
        # Run standard flow (may open immediate transfer wizard)
        res = super().button_validate()
        # If transfer is completed, run post hooks
        for picking in self:
            picking._clinic_post_transfer_hook()
        return res

    # =========================================================================
    # CORE CLINICAL VALIDATIONS
    # =========================================================================
    def _clinic_validate_before_button_validate(self):
        """Run clinical checks: category allowlist, expiration policy, temperature."""
        self.ensure_one()
        # Category governance per location
        self._clinic_check_category_governance()

        # Expiration policy checks
        warn_msgs = self._clinic_check_expiration_policy()
        for msg in warn_msgs:
            self.message_post(body=msg)

        # Temperature check for incoming receipts (optional)
        if self.clinic_operation_type == "incoming":
            self._clinic_check_temperature_at_receipt()

        # Bridge hook for add-on logic (treatment, membership, etc.)
        self._clinic_hook_pre_validate()

    def _clinic_check_category_governance(self):
        """Ensure product category is allowed at source/destination locations (if restricted)."""
        # Optimize: only check once per distinct (loc, product)
        pairs_checked = set()
        for ml in self.move_line_ids:
            product = ml.product_id
            for loc in filter(None, [ml.location_id, ml.location_dest_id]):
                key = (loc.id, product.id)
                if key in pairs_checked:
                    continue
                pairs_checked.add(key)

                # Many2one locations are already Odoo recordsets. Validate the
                # optional ClinicOne field contract directly instead of using
                # isinstance() with an env model proxy.
                if "clinic_restrict_to_allowed_categories" in loc._fields:
                    if loc.clinic_restrict_to_allowed_categories:
                        loc.clinic_validate_product_allowed(product)

    def _clinic_check_expiration_policy(self):
        """Evaluate expiration decisions for each lot moved through the picking.

        Returns:
            list of warning messages to be posted on the document.
        Raises:
            UserError if any location/gudang policy blocks the operation.
        """
        exp_field = self._get_expiration_field_name()
        if not exp_field:
            return []  # Expiration tracking not installed

        today = date.today()
        warn_msgs = []
        for ml in self.move_line_ids:
            lot = ml.lot_id
            if not lot:
                # For incoming receipts, a new lot may be created via 'lot_name' later.
                # We cannot evaluate expiration until lot exists; bridges may enforce via wizards.
                continue

            ld = getattr(lot, exp_field, False)
            if not ld:
                continue

            # If already expired, ask source/dest policy
            if ld < today:
                src_status, src_msg = self._clinic_resolve_location_policy(ml.location_id, lot)
                dest_status, dest_msg = self._clinic_resolve_location_policy(ml.location_dest_id, lot)

                # Aggregate statuses: if any 'block' => block; elif any 'warn' => warn; else ok
                statuses = [src_status, dest_status]
                messages = list(filter(None, [src_msg, dest_msg]))
                if "block" in statuses:
                    raise UserError(_("Expired lot cannot be moved due to policy: %s") % ("; ".join(messages) or "-"))
                elif "warn" in statuses:
                    warn_msgs.append(_("Moving expired lot: %s. %s") % (lot.display_name, "; ".join(messages)))

        return warn_msgs

    def _clinic_check_temperature_at_receipt(self):
        """Validate measured receipt temperature against location/warehouse thresholds (incoming only)."""
        self.ensure_one()
        if not self.clinic_receipt_temperature_c:
            return  # no data provided → skip

        # Prefer destination location policy; if not present, fallback to warehouse
        dest = self.location_dest_id
        product_set = {ml.product_id for ml in self.move_line_ids if ml.product_id and ml.product_id.type != "service"}
        ok_all = True
        notes = []
        for product in product_set:
            if hasattr(dest, "clinic_validate_temperature"):
                ok, msg = dest.clinic_validate_temperature(product=product, lot=None, temperature_c=self.clinic_receipt_temperature_c)
            else:
                # Fallback via warehouse if available
                wh = getattr(self.picking_type_id, "warehouse_id", False)
                if wh and hasattr(wh, "clinic_validate_temperature"):
                    ok, msg = wh.clinic_validate_temperature(product=product, lot=None, temperature_c=self.clinic_receipt_temperature_c)
                else:
                    ok, msg = True, None

            if not ok:
                ok_all = False
                notes.append(msg or _("Measured temperature is out of allowed range."))

        if not ok_all:
            raise UserError(_("Receipt temperature validation failed: %s") % ("; ".join(notes)))
        elif notes:
            # There were non-blocking notes (unlikely in this base), post them
            for n in notes:
                if n:
                    self.message_post(body=n)

    # =========================================================================
    # POLICY RESOLUTION HELPERS
    # =========================================================================
    def _clinic_resolve_location_policy(self, location, lot):
        """Return ('ok'|'warn'|'block', message) for a given location."""
        if not location:
            return "ok", None
        # If location implements clinical policy, ask it. Else ask warehouse.
        if hasattr(location, "clinic_expiration_decision"):
            return location.clinic_expiration_decision(lot)
        wh = getattr(self.picking_type_id, "warehouse_id", False)
        if wh and hasattr(wh, "clinic_expiration_decision"):
            return wh.clinic_expiration_decision(lot)
        return "ok", None

    # =========================================================================
    # POST TRANSFER HOOK
    # =========================================================================
    def _clinic_post_transfer_hook(self):
        """Executed after standard validation when transfer is done or partially done.

        Bridges can override via _clinic_hook_post_validate to:
            - Log treatment consumption
            - Trigger membership points
            - Send finance/accounting side-effects
            - Update device maintenance counters
        """
        self.ensure_one()
        self._clinic_hook_post_validate()

    # =========================================================================
    # UI ACTION HELPERS
    # =========================================================================
    def action_view_quarantine_destination(self):
        """Open destination location if marked as quarantine transfer."""
        self.ensure_one()
        if not self.clinic_is_quarantine_transfer or not self.location_dest_id:
            raise UserError(_("This picking is not flagged as a Quarantine Transfer or has no destination."))
        action = self.env.ref("stock.action_location_form").read()[0]
        action["domain"] = [("id", "=", self.location_dest_id.id)]
        return action

    # =========================================================================
    # NAME / DISPLAY
    # =========================================================================

    @api.depends("name", "clinic_is_quarantine_transfer")
    def _compute_display_name(self):
        """Preserve the ClinicOne quarantine marker in Odoo 19."""
        super()._compute_display_name()
        for picking in self:
            if picking.clinic_is_quarantine_transfer:
                picking.display_name = f"{picking.display_name} [Quarantine]"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    # =========================================================================
    # PUBLIC APIS
    # =========================================================================
    def clinic_has_any_expired_lot(self):
        """Public helper to check if any move line uses an expired lot."""
        self.ensure_one()
        return bool(self.clinic_has_expired_lines)

    # =========================================================================
    # HOOKS for Cross-Module Integrations (override in bridge addons)
    # =========================================================================
    def _clinic_hook_pre_validate(self):
        """Hook called before button_validate core logic.

        Bridges may:
          - Check treatment/patient linkage completeness
          - Enforce doctor permissions for medication
          - Create analytical tags/cost centers
          - Route to special room locations
        """
        return

    def _clinic_hook_post_validate(self):
        """Hook called after successful validation (transfer done).

        Bridges may:
          - Record clinical consumption entries
          - Issue membership rewards/points
          - Emit billing/AR events
          - Trigger IoT/device updates
        """
        return

