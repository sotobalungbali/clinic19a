# -*- coding: utf-8 -*-
# File: models/procurement_group.py
# Module: clinic_inventory
#
# Purpose
#   Extend procurement.group for aesthetic clinics:
#   - Carry clinical context (patient, doctor, treatment reference, appointment date, priority)
#   - Policy hints for FEFO and minimum remaining shelf-life
#   - Replenishment scope & destination hints (pharmacy vs treatment rooms)
#   - Safe helper APIs to propagate clinic context into stock moves / pickings / POs / MOs
#   - Hook methods for 25 ClinicOne addons without circular dependency
#
# Notes
#   - All user-facing strings are in English.
#   - We DO NOT add unknown keys to core models in a way that breaks ORM; helpers return
#     only existing keys to merge safely (name, description_picking, date_deadline, locations).
#   - Core models already link moves to procurement.group via 'group_id'; pickings may or may not.
#
# UI
#   - View moves and pickings linked to this procurement group.
#
# Safety
#   - No hard dependency on other clinic_* modules; treatment uses a Reference field.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

# sudah di remark di __init__.py
class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    # =========================================================================
    # Clinical context
    # =========================================================================
    clinic_patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        domain=[("is_company", "=", False)],
        tracking=True,
        help="Patient associated with the procurement demand (optional).",
    )
    clinic_doctor_id = fields.Many2one(
        "hr.employee",
        string="Doctor",
        tracking=True,
        help="Healthcare professional who requested the items (optional).",
    )
    clinic_treatment_ref = fields.Reference(
        selection=lambda self: self._clinic_treatment_reference_models(),
        string="Treatment Reference",
        tracking=True,
        help="Link to a treatment/appointment/encounter record (optional).",
    )
    clinic_appointment_date = fields.Datetime(
        string="Appointment Date",
        tracking=True,
        help="Intended date when the items are required (used as a soft deadline hint).",
    )
    clinic_priority = fields.Selection(
        selection=[
            ("low", "Low"),
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        string="Priority",
        default="normal",
        tracking=True,
        help="Clinical urgency indicator (advisory).",
    )
    clinic_note = fields.Char(
        string="Clinic Note",
        tracking=True,
        help="Optional short note about clinical context for this group.",
    )

    # =========================================================================
    # Policy hints (advisory, to be enforced by bridges/reservation logic)
    # =========================================================================
    clinic_enforce_fefo = fields.Boolean(
        string="Enforce FEFO (Clinic)",
        default=lambda self: self.env.company.clinic_inventory_enforce_fefo,
        tracking=True,
        help="If enabled, downstream reservation should prioritize First-Expire-First-Out.",
    )
    clinic_min_shelf_life_days = fields.Integer(
        string="Min Remaining Shelf Life (Days)",
        default=lambda self: int(self.env.company.clinic_inventory_min_shelf_life_days or 0),
        tracking=True,
        help="Avoid lots expiring in fewer than this number of days when fulfilling this group's moves.",
    )

    clinic_replenishment_scope = fields.Selection(
        selection=[
            ("warehouse_default", "Warehouse Default"),
            ("pharmacy_only", "Pharmacy Only"),
            ("rooms_only", "Treatment Rooms Only"),
            ("pharmacy_and_rooms", "Pharmacy and Treatment Rooms"),
        ],
        string="Clinic Replenishment Scope",
        default=lambda self: self.env.company.clinic_inventory_default_replenishment_scope or "warehouse_default",
        tracking=True,
        help="Scope for sourcing stock internally when this group triggers moves.",
    )

    clinic_destination_policy = fields.Selection(
        selection=[
            ("rule_dest", "Use Rule Destination"),
            ("pharmacy", "Send to Pharmacy"),
            ("treatment_root", "Send to Treatment Rooms Root"),
        ],
        string="Clinic Destination Policy",
        default="rule_dest",
        tracking=True,
        help="Override the default rule destination for internal moves created under this group.",
    )

    # Optional fixed locations (rarely used; leave blank to let rules decide)
    clinic_src_location_id = fields.Many2one(
        "stock.location",
        string="Preferred Source Location",
        domain="[('usage','=','internal')]",
        help="Preferred source location to pick from (optional).",
    )
    clinic_dest_location_id = fields.Many2one(
        "stock.location",
        string="Preferred Destination Location",
        domain="[('usage','in',('internal','customer','inventory'))]",
        help="Preferred destination location for moves (optional).",
    )

    # =========================================================================
    # Counters / quick navigation
    # =========================================================================
    clinic_move_count = fields.Integer(
        string="# Moves",
        compute="_compute_counts",
        help="Number of stock moves linked to this procurement group.",
    )
    clinic_picking_count = fields.Integer(
        string="# Pickings",
        compute="_compute_counts",
        help="Number of pickings related to moves of this group.",
    )

    # =========================================================================
    # Computes
    # =========================================================================
    def _compute_counts(self):
        Move = self.env["stock.move"]
        for g in self:
            moves = Move.search([("group_id", "=", g.id)])
            g.clinic_move_count = len(moves)
            g.clinic_picking_count = len(moves.mapped("picking_id"))

    # =========================================================================
    # Constraints
    # =========================================================================
    @api.constrains("clinic_min_shelf_life_days")
    def _check_min_shelf_life(self):
        for g in self:
            if g.clinic_min_shelf_life_days and g.clinic_min_shelf_life_days < 0:
                raise ValidationError(_("Min Remaining Shelf Life (Days) cannot be negative."))

    # =========================================================================
    # Reference model discovery (avoid hard deps)
    # =========================================================================
    def _clinic_treatment_reference_models(self):
        candidates = [
            ("clinic.treatment", "Treatment"),
            # ("booking.booking.appointment", "Appointment"),
            ("clinic.room.session", "Room Session"),
        ]
        res = []
        IrModel = self.env["ir.model"].sudo()
        for model, label in candidates:
            if IrModel.search([("model", "=", model)], limit=1):
                res.append((model, label))
        return res

    # =========================================================================
    # Name / Display
    # =========================================================================
    def name_get(self):
        res = []
        for g in self:
            base = g.name or _("Procurement Group")
            parts = [base]
            if g.clinic_patient_id:
                parts.append(g.clinic_patient_id.display_name)
            if g.clinic_priority and g.clinic_priority != "normal":
                parts.append(g.clinic_priority.upper())
            # show soft deadline if present
            if g.clinic_appointment_date:
                parts.append(_("due: %s") % fields.Datetime.to_string(g.clinic_appointment_date))
            res.append((g.id, " | ".join(parts)))
        return res

    # =========================================================================
    # Scoping helpers (domains)
    # =========================================================================
    def clinic_location_domain_for_scope(self, warehouse):
        """Return a stock.quant domain matching this group's scope."""
        self.ensure_one()
        if not warehouse:
            return [("location_id.usage", "=", "internal")]
        scope = self.clinic_replenishment_scope or "warehouse_default"
        if scope == "warehouse_default":
            if hasattr(warehouse, "_clinic_hook_location_domain_for_replenishment"):
                return warehouse._clinic_hook_location_domain_for_replenishment()
            return [("location_id", "child_of", warehouse.view_location_id.id)]
        if scope == "pharmacy_only" and getattr(warehouse, "clinic_pharmacy_location_id", False):
            return [("location_id", "child_of", warehouse.clinic_pharmacy_location_id.id)]
        if scope == "rooms_only" and getattr(warehouse, "clinic_treatment_root_location_id", False):
            return [("location_id", "child_of", warehouse.clinic_treatment_root_location_id.id)]
        if scope == "pharmacy_and_rooms":
            return [("location_id", "child_of", warehouse.view_location_id.id), ("location_id.usage", "=", "internal")]
        return [("location_id", "child_of", warehouse.view_location_id.id)]

    # =========================================================================
    # Destination resolution helper (mirrors stock.rule policy logic)
    # =========================================================================
    def _clinic_resolve_destination_location(self, current_dest, warehouse):
        """Resolve destination location according to group policy & warehouse configuration."""
        self.ensure_one()
        if not self.clinic_destination_policy or self.clinic_destination_policy == "rule_dest":
            return current_dest
        Location = self.env["stock.location"]
        dest = (
            current_dest
            if getattr(current_dest, "_name", None) == "stock.location"
            else Location.browse(current_dest)
        )
        wh = warehouse
        if not wh and dest:
            wh = self.env["stock.warehouse"].search([("view_location_id", "parent_of", dest.id)], limit=1)
        if not wh:
            return dest
        if self.clinic_destination_policy == "pharmacy":
            return getattr(wh, "clinic_pharmacy_location_id", False) or dest
        if self.clinic_destination_policy == "treatment_root":
            return getattr(wh, "clinic_treatment_root_location_id", False) or dest
        return dest

    # =========================================================================
    # MOVE VALUE ENRICHMENT (safe; keys must exist in stock.move)
    # =========================================================================
    def clinic_prepare_move_values(self, move_vals, product=None, warehouse=None):
        """Return adjusted move values incorporating clinic context safely.

        Only modifies existing keys:
          - name / description_picking: appends clinic hints (patient, appointment, FEFO/minSL)
          - date_deadline: soft deadline derived from appointment and/or min shelf-life hint
          - location_id / location_dest_id: overridden by group preferences if set
        """
        self.ensure_one()
        mv = dict(move_vals or {})

        # 1) Names / descriptions
        tags = []
        if self.clinic_patient_id:
            tags.append("PT:%s" % self.clinic_patient_id.display_name)
        if self.clinic_doctor_id:
            tags.append("DR:%s" % self.clinic_doctor_id.display_name)
        if self.clinic_priority and self.clinic_priority != "normal":
            tags.append("prio=%s" % self.clinic_priority)
        if self.clinic_enforce_fefo:
            tags.append("FEFO")
        if self.clinic_min_shelf_life_days:
            tags.append("minSL=%sd" % self.clinic_min_shelf_life_days)

        if tags:
            base_name = mv.get("name") or (product.display_name if product else _("Move"))
            mv["name"] = f"{base_name} [{' | '.join(tags)}]"
            dp = mv.get("description_picking") or ""
            desc_bits = []
            if self.clinic_note:
                desc_bits.append(self.clinic_note)
            if self.clinic_appointment_date:
                desc_bits.append(_("Needed by: %s") % fields.Datetime.to_string(self.clinic_appointment_date))
            if desc_bits:
                mv["description_picking"] = (dp + ("\n" if dp else "") + "\n".join(desc_bits)).strip()

        # 2) Deadline hint
        if not mv.get("date_deadline", False):
            deadline = None
            if self.clinic_appointment_date:
                deadline = self.clinic_appointment_date
            elif self.clinic_min_shelf_life_days:
                deadline = fields.Datetime.now() + timedelta(days=int(self.clinic_min_shelf_life_days))
            if deadline:
                mv["date_deadline"] = deadline

        # 3) Preferred locations (if set on group, override)
        if self.clinic_src_location_id and mv.get("location_id"):
            mv["location_id"] = self.clinic_src_location_id.id
        if self.clinic_dest_location_id and mv.get("location_dest_id"):
            mv["location_dest_id"] = self.clinic_dest_location_id.id
        else:
            # Resolve destination policy if not explicitly overridden
            if mv.get("location_dest_id"):
                mv["location_dest_id"] = self._clinic_resolve_destination_location(
                    current_dest=mv["location_dest_id"],
                    warehouse=warehouse,
                ).id

        # 4) Allow bridges to adjust safely
        mv = self._clinic_hook_adjust_move_values(mv, product=product, warehouse=warehouse)
        return mv

    # =========================================================================
    # PICKING / PURCHASE / MRP value helpers (bridges may call)
    # =========================================================================
    def clinic_prepare_picking_values(self, picking_vals, picking_type=None, partner=None, warehouse=None):
        """Return adjusted picking values (safe keys only)."""
        self.ensure_one()
        vals = dict(picking_vals or {})
        # Enrich 'origin' and 'note'
        origin = vals.get("origin") or self.name or ""
        hints = []
        if self.clinic_patient_id:
            hints.append("PT:%s" % self.clinic_patient_id.display_name)
        if self.clinic_priority and self.clinic_priority != "normal":
            hints.append("PRIO:%s" % self.clinic_priority)
        if hints:
            vals["origin"] = f"{origin} [{' | '.join(hints)}]".strip()
        if self.clinic_note:
            note = vals.get("note") or ""
            vals["note"] = (note + ("\n" if note else "") + self.clinic_note).strip()
        # Soft deadline
        if self.clinic_appointment_date and not vals.get("scheduled_date"):
            vals["scheduled_date"] = self.clinic_appointment_date
        return self._clinic_hook_adjust_picking_values(vals, picking_type=picking_type, partner=partner, warehouse=warehouse)

    def clinic_prepare_purchase_values(self, purchase_vals, vendor=None, warehouse=None):
        """Return adjusted purchase order values (safe keys only)."""
        self.ensure_one()
        vals = dict(purchase_vals or {})
        # Reference on 'origin' or 'partner_ref'
        origin = vals.get("origin") or self.name or ""
        extra = []
        if self.clinic_patient_id:
            extra.append("PT:%s" % self.clinic_patient_id.display_name)
        if self.clinic_priority and self.clinic_priority != "normal":
            extra.append("PRIO:%s" % self.clinic_priority)
        if extra:
            vals["origin"] = f"{origin} [{' | '.join(extra)}]".strip()
        # Notes & deadline
        if self.clinic_note:
            n = vals.get("notes") or vals.get("note") or ""
            vals["notes"] = (n + ("\n" if n else "") + self.clinic_note).strip()
        if self.clinic_appointment_date and not vals.get("date_order"):
            vals["date_order"] = self.clinic_appointment_date
        return self._clinic_hook_adjust_purchase_values(vals, vendor=vendor, warehouse=warehouse)

    def clinic_prepare_mrp_values(self, mo_vals, warehouse=None):
        """Return adjusted manufacturing order values (safe keys only)."""
        self.ensure_one()
        vals = dict(mo_vals or {})
        # Origin & note enrichment
        origin = vals.get("origin") or self.name or ""
        if self.clinic_priority and self.clinic_priority != "normal":
            origin = f"{origin} [PRIO:{self.clinic_priority}]"
        vals["origin"] = origin.strip()
        if self.clinic_note:
            n = vals.get("note") or ""
            vals["note"] = (n + ("\n" if n else "") + self.clinic_note).strip()
        # Deadline
        if self.clinic_appointment_date and not vals.get("date_deadline"):
            vals["date_deadline"] = self.clinic_appointment_date
        return self._clinic_hook_adjust_mrp_values(vals, warehouse=warehouse)

    # =========================================================================
    # UI actions
    # =========================================================================
    def action_view_moves(self):
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("group_id", "=", self.id)]
        action["context"] = {"search_default_group_by_product": 1}
        return action

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        move_ids = self.env["stock.move"].search([("group_id", "=", self.id)]).ids
        picking_ids = self.env["stock.move"].browse(move_ids).mapped("picking_id").ids
        action["domain"] = [("id", "in", picking_ids)]
        return action

    # =========================================================================
    # Hooks for bridges
    # =========================================================================
    def _clinic_hook_adjust_move_values(self, move_vals, product=None, warehouse=None):
        """Override in bridges to add analytic tags, treatment refs, or adjust locations."""
        return move_vals

    def _clinic_hook_adjust_picking_values(self, picking_vals, picking_type=None, partner=None, warehouse=None):
        """Override in bridges to attach clinical docs, approvals, or set custom routes."""
        return picking_vals

    def _clinic_hook_adjust_purchase_values(self, purchase_vals, vendor=None, warehouse=None):
        """Override in bridges to inject analytic accounts, cost centers, or contract references."""
        return purchase_vals

    def _clinic_hook_adjust_mrp_values(self, mo_vals, warehouse=None):
        """Override in bridges to propagate clinic context to manufacturing orders."""
        return mo_vals

