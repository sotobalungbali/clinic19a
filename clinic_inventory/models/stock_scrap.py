# -*- coding: utf-8 -*-
# File: models/stock_scrap.py
# Module: clinic_inventory
#
# Purpose
#   Extend stock.scrap for aesthetic clinics:
#   - Clinical scrap dispositions (Scrap / Quarantine / Return to Supplier)
#   - Standardized scrap reasons & notes (expired, damaged, contamination, etc.)
#   - Expiration awareness & location governance checks
#   - Auto-propose quarantine internal transfer when selected
#   - Hooks for 25 ClinicOne addons (treatment/doctor/quality/finance/eCommerce/etc.)
#
# Notes
#   - All user-facing texts are in English.
#   - No hard dependency on other clinic_* modules; bridges may override *_clinic_hook_* methods.
#   - We DO NOT change valuation here (stock_account handles valuation). Bridges may hook for finance detail.

from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    # =========================================================================
    # Clinical Disposition & Metadata
    # =========================================================================
    clinic_disposition = fields.Selection(
        selection=[
            ("scrap", "Scrap (Write-off)"),
            ("quarantine", "Move to Quarantine"),
            ("return_to_supplier", "Return to Supplier"),
        ],
        string="Clinical Disposition",
        default="scrap",
        tracking=True,
        help=(
            "How this item should be dispositioned:\n"
            "- Scrap: remove from inventory via scrap location (write-off).\n"
            "- Move to Quarantine: transfer to quarantine location for further decisions.\n"
            "- Return to Supplier: trigger a vendor return flow (requires bridge module)."
        ),
    )

    clinic_scrap_reason = fields.Selection(
        selection=[
            ("expired", "Expired"),
            ("damaged", "Damaged Packaging"),
            ("contaminated", "Suspected Contamination"),
            ("temperature_excursion", "Temperature Excursion"),
            ("recalled", "Manufacturer Recall"),
            ("patient_return", "Patient Return / Complaint"),
            ("device_waste", "Device-Related Waste"),
            ("other", "Other"),
        ],
        string="Scrap Reason",
        tracking=True,
        help="Standardized clinical reason for scrapping or quarantining the product.",
    )

    clinic_notes = fields.Text(
        string="Clinical Notes",
        tracking=True,
        help="Optional clinical/quality notes describing the issue and handling instructions.",
    )

    clinic_reported_by = fields.Many2one(
        "res.users",
        string="Reported By",
        default=lambda self: self.env.user,
        tracking=True,
        help="User who initially reported the issue or created the scrap record.",
    )
    clinic_reported_date = fields.Datetime(
        string="Reported Date",
        default=fields.Datetime.now,
        tracking=True,
        help="When the issue/scrap was reported.",
    )
    clinic_approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        tracking=True,
        help="Approver of the scrap/quarantine decision (optional; use activities/approvals if needed).",
    )
    clinic_approved_date = fields.Datetime(
        string="Approved Date",
        tracking=True,
        help="When the decision was approved (optional).",
    )

    # Convenience flags from lot/product for UI & validations
    clinic_is_expired_lot = fields.Boolean(
        string="Is Expired Lot",
        compute="_compute_clinic_expiry_flags",
        store=False,
        help="True when selected lot is already expired according to its expiration date.",
    )
    clinic_days_to_expiry = fields.Integer(
        string="Days to Expiry",
        compute="_compute_clinic_expiry_flags",
        store=False,
        help="Number of days until the lot expires. Negative means already expired.",
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
    @api.depends("lot_id", "lot_id.expiration_date")
    def _compute_clinic_expiry_flags(self):
        exp_field = self._get_expiration_field_name()
        today = date.today()
        for rec in self:
            rec.clinic_is_expired_lot = False
            rec.clinic_days_to_expiry = 0
            if rec.lot_id and exp_field:
                ld = getattr(rec.lot_id, exp_field, False)
                if ld:
                    delta = (ld - today).days
                    rec.clinic_days_to_expiry = delta
                    rec.clinic_is_expired_lot = delta < 0

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    @api.constrains("product_id")
    def _check_not_service(self):
        for rec in self:
            if rec.product_id and rec.product_id.type == "service":
                raise ValidationError(_("Services cannot be scrapped."))

    @api.constrains("scrap_qty")
    def _check_positive_qty(self):
        for rec in self:
            if rec.scrap_qty is not None and rec.scrap_qty <= 0.0:
                raise ValidationError(_("Scrap Quantity must be greater than zero."))

    # =========================================================================
    # ONCHANGE
    # =========================================================================
    @api.onchange("clinic_scrap_reason")
    def _onchange_reason_default_disposition(self):
        """Small UX sugar: for 'expired' reason, suggest quarantine or scrap depending on policy."""
        for rec in self:
            if rec.clinic_scrap_reason == "expired" and not rec.clinic_disposition:
                rec.clinic_disposition = "quarantine"

    # =========================================================================
    # GOVERNANCE & POLICY CHECKS
    # =========================================================================
    def _clinic_check_category_governance(self):
        """Ensure product category is allowed at source location (if location is restricted)."""
        self.ensure_one()
        loc = self.location_id
        if loc and getattr(loc, "clinic_restrict_to_allowed_categories", False):
            loc.clinic_validate_product_allowed(self.product_id)

    def _clinic_check_expiration_reason_alignment(self):
        """Align reason with actual lot state (warn but allow mismatch)."""
        self.ensure_one()
        if self.clinic_scrap_reason == "expired" and not self.clinic_is_expired_lot and self.lot_id:
            # Warn user via chatter; we still allow because 'expired soon' might be policy-based.
            self.message_post(body=_("Reason set to 'Expired' but lot is not yet expired (Days to expiry: %s).")
                                   % (self.clinic_days_to_expiry,))

    # =========================================================================
    # ACTION VALIDATE OVERRIDE
    # =========================================================================
    def action_validate(self):
        """Override to add clinical checks & alternate dispositions."""
        for rec in self:
            rec._clinic_pre_validate_checks()

        # Branch by disposition
        quarantine_records = self.filtered(lambda r: r.clinic_disposition == "quarantine")
        return_to_supplier_records = self.filtered(lambda r: r.clinic_disposition == "return_to_supplier")
        standard_scrap_records = self.filtered(lambda r: r.clinic_disposition == "scrap")

        # Handle quarantine dispositions (convert to internal move to quarantine)
        actions = []
        for rec in quarantine_records:
            actions.append(rec._clinic_action_move_to_quarantine())

        # Handle vendor return (delegate to bridge hook)
        for rec in return_to_supplier_records:
            handled = rec._clinic_hook_return_to_supplier()  # bridge should implement
            if not handled:
                raise UserError(_(
                    "Return to Supplier requires a bridge module (e.g., Purchase/Returns). "
                    "No bridge handled this action."
                ))

        # Proceed with standard scrap for the rest
        res = True
        if standard_scrap_records:
            res = super(StockScrap, standard_scrap_records).action_validate()

        # Post hook for all records (including alternate flows)
        for rec in self:
            rec._clinic_hook_post_validate()

        # If we produced any actions (windows) for quarantine, return the first (Odoo can only return one action)
        return actions[0] if actions else res

    def _clinic_pre_validate_checks(self):
        """Run clinical validations prior to executing disposition."""
        self.ensure_one()

        # Governance: category allowlist at source
        self._clinic_check_category_governance()

        # Reason alignment warnings (non-blocking)
        self._clinic_check_expiration_reason_alignment()

        # Policy: if lot is expired and destination (scrap) policy blocks storing expired in scrap location?
        # Typically scrap location is virtual and not policy-restricted; we skip this check.

        # Bridge hook (treatment/quality/finance may enforce rules)
        self._clinic_hook_pre_validate()

    # =========================================================================
    # QUARANTINE FLOW
    # =========================================================================
    def _clinic_action_move_to_quarantine(self):
        """Create an internal picking to move selected qty to quarantine location.

        Returns an action opening the picking tree with context set to the new transfer.
        """
        self.ensure_one()
        if not self.product_id or self.product_id.type == "service":
            raise UserError(_("Services cannot be quarantined."))

        # Resolve source location (scrap's location_id) and warehouse
        src_loc = self.location_id
        if not src_loc:
            raise UserError(_("No source location set for quarantine transfer."))

        # Resolve the quarantine destination via quant/location/warehouse utilities
        dest_loc = self._clinic_resolve_quarantine_location_from_source(src_loc)
        if not dest_loc:
            raise UserError(_("No quarantine location configured for the resolved warehouse."))

        wh = self._clinic_resolve_warehouse_from_location(src_loc)
        if not wh or not getattr(wh, "int_type_id", False):
            raise UserError(_("No internal picking type found for the resolved warehouse."))

        # Suggested name
        move_name = _("Quarantine transfer for %s") % (self.product_id.display_name,)

        # Prepare action to open picking with defaults (user may confirm)
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action.update({
            "context": {
                "default_picking_type_id": wh.int_type_id.id,
                "default_location_id": src_loc.id,
                "default_location_dest_id": dest_loc.id,
                "default_origin": self.name or move_name,
                "default_move_ids_without_package": [(0, 0, {
                    "name": move_name,
                    "product_id": self.product_id.id,
                    "product_uom": self.product_uom_id.id or self.product_id.uom_id.id,
                    "product_uom_qty": self.scrap_qty,
                    "location_id": src_loc.id,
                    "location_dest_id": dest_loc.id,
                    # If a lot is specified, some Odoo versions accept context 'lot_id' or assign on move line later
                })],
                "default_clinic_is_quarantine_transfer": True,
                "default_note": (self.clinic_notes or "")[:2000],
            },
        })
        # Chatter note for traceability
        self.message_post(body=_("Prepared quarantine transfer of %s %s to %s.")
                          % (self.scrap_qty, self.product_uom_id.display_name, dest_loc.display_name))
        return action

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _clinic_resolve_quarantine_location_from_source(self, src_location):
        """Find quarantine location from source location using location/warehouse config."""
        self.ensure_one()
        # Walk up parents to find any quarantine-flagged location
        cur = src_location
        while cur:
            if getattr(cur, "clinic_is_quarantine", False):
                return cur
            cur = cur.location_id

        # Fallback: find warehouse and use its configured quarantine location
        wh = self._clinic_resolve_warehouse_from_location(src_location)
        if wh and getattr(wh, "clinic_quarantine_location_id", False):
            return wh.clinic_quarantine_location_id
        return False

    def _clinic_resolve_warehouse_from_location(self, location):
        """Find a warehouse whose internal view contains the given location."""
        Warehouse = self.env["stock.warehouse"]
        wh = Warehouse.search([("view_location_id", "parent_of", location.id)], limit=1)
        return wh

    # =========================================================================
    # NAME / DISPLAY
    # =========================================================================

    @api.depends("name", "clinic_disposition", "clinic_scrap_reason")
    def _compute_display_name(self):
        """Expose ClinicOne disposition/reason hints in Odoo 19 record labels."""
        super()._compute_display_name()
        for rec in self:
            tags = []
            if rec.clinic_disposition:
                tags.append(dict(rec._fields["clinic_disposition"].selection).get(rec.clinic_disposition))
            if rec.clinic_scrap_reason:
                tags.append(dict(rec._fields["clinic_scrap_reason"].selection).get(rec.clinic_scrap_reason))
            if tags:
                rec.display_name = f"{rec.display_name} [{' / '.join(tag for tag in tags if tag)}]"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
    # =========================================================================
    # HOOKS (override in bridge addons)
    # =========================================================================
    def _clinic_hook_pre_validate(self):
        """Hook called before executing disposition.

        Bridges may:
          - require approvals for certain reasons,
          - check treatment/patient linkage,
          - attach COA/quality documents,
          - adjust analytic accounts/cost centers.
        """
        return

    def _clinic_hook_post_validate(self):
        """Hook called after disposition executed or transfer prepared.

        Bridges may:
          - post finance/accounting side-effects,
          - notify QA/compliance,
          - issue membership/loyalty reversals (if applicable).
        """
        return

    def _clinic_hook_return_to_supplier(self):
        """Hook to execute supplier return flow.

        Should return True if handled (created a return picking/RMA), else False.
        Bridge modules (e.g., Purchase/Returns) should implement this.
        """
        return False




