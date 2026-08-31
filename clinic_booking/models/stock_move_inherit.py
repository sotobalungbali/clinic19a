
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/stock_move_inherit.py
#
# Purpose
# -------
# Make Inventory (Stock) aware of Bookings:
# - Link stock moves & pickings with booking and booking lines
# - Provide helpers to load consumption moves from booking and resources
# - Keep company/partner consistency with booking patient/company
# - Post informative chatter messages on Booking when pickings are validated
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking / booking.line  : primary linkage
# - booking.resource                : optional, line/resource-level consumption helpers
# - clinic.treatment / clinic.doctor: related shortcuts for reporting
#
# Notes
# -----
# - This file assumes 'stock' is available (declared in module depends).
# - All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# stock.move — Inherit
# =============================================================================
class StockMove(models.Model):
    _inherit = "stock.move"

    # -------------------------------------------------------------------------
    # BOOKING LINKS
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Booking associated with this stock move.",
        copy=False,
    )
    booking_line_id = fields.Many2one(
        "booking.line",
        string="Booking Line",
        index=True,
        help="Booking line associated with this move, if any.",
        copy=False,
    )
    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        help="Resource that triggers this consumption (optional).",
        copy=False,
    )

    # Convenience related fields (for filters/reports)
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )

    # Labeling flag if this move is directly tied to a booking consumption
    is_booking_consumption = fields.Boolean(
        string="Is Booking Consumption",
        help="Enable to mark this move as a consumption generated for a booking.",
        default=False,
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_line_id")
    def _onchange_booking_line_id(self):
        """
        When selecting a booking line, prefill product, uom, quantity, and name.
        """
        for rec in self:
            bl = rec.booking_line_id
            if not bl:
                continue

            rec.booking_id = bl.booking_id.id
            # Product / UoM / Qty
            if bl.product_id:
                rec.product_id = bl.product_id.id
                rec.product_uom = bl.product_uom.id or bl.product_id.uom_id.id
            if bl.product_uom_qty:
                rec.product_uom_qty = bl.product_uom_qty
            # Description
            if bl.name:
                rec.name = bl.name

            # Company alignment (if move has no company yet, fill it)
            if not rec.company_id and bl.booking_id and bl.booking_id.company_id:
                rec.company_id = bl.booking_id.company_id.id

            # Default to mark as consumption
            rec.is_booking_consumption = True

    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        On choosing booking, help fill name/origin and company if empty.
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            if not rec.reference and getattr(rec, "reference", False) is not None:
                rec.reference = b.name
            if not rec.name:
                rec.name = _("Consumption for %s") % (b.name,)
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_line_id", "booking_id")
    def _check_booking_line_header(self):
        for rec in self:
            if rec.booking_line_id and rec.booking_id and rec.booking_line_id.booking_id != rec.booking_id:
                raise ValidationError(_("The selected Booking Line does not belong to the chosen Booking."))

    @api.constrains("booking_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    # -------------------------------------------------------------------------
    # HELPERS — PREPARE MOVE VALS FROM BOOKING LINE
    # -------------------------------------------------------------------------
    def _prepare_move_vals_from_booking_line(self, booking_line, picking=None, resource=None):
        """
        Return a dict of stock.move values prepared from a booking line,
        suitable for use in create() (optionally attached to a picking).
        """
        self.ensure_one() if self else None
        if not booking_line or not booking_line.product_id:
            return {}

        product = booking_line.product_id
        company = booking_line.booking_id.company_id if booking_line.booking_id else (picking.company_id if picking else self.env.company)
        uom = booking_line.product_uom or product.uom_id

        vals = {
            "name": booking_line.name or product.display_name or _("Booking Line"),
            "product_id": product.id,
            "product_uom": uom.id,
            "product_uom_qty": booking_line.product_uom_qty or 1.0,
            "company_id": company.id,
            "booking_id": booking_line.booking_id.id if booking_line.booking_id else False,
            "booking_line_id": booking_line.id,
            "is_booking_consumption": True,
        }
        if picking:
            vals.update({
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            })
        if resource:
            vals["resource_id"] = resource.id
        return vals


# =============================================================================
# stock.picking — Inherit
# =============================================================================
class StockPicking(models.Model):
    _inherit = "stock.picking"

    # -------------------------------------------------------------------------
    # BOOKING LINKS
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Booking related to this transfer.",
        copy=False,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )

    # Labeling
    is_booking_consumption = fields.Boolean(
        string="Is Booking Consumption",
        help="Enable to mark this picking as a transfer generated for a booking.",
        default=False,
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        Keep partner (patient), origin, and company aligned when a booking is selected.
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            # Partner is the patient
            if not rec.partner_id and b.patient_id:
                rec.partner_id = b.patient_id.id
            # Origin reference
            if not rec.origin:
                rec.origin = b.name
            # Company alignment
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id
            # Label
            rec.is_booking_consumption = True

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_id", "company_id")
    def _check_booking_company(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    @api.constrains("booking_id", "move_ids_without_package")
    def _check_moves_booking_link(self):
        """
        If picking has a booking, ensure all moves (with booking set) point to the same booking.
        """
        for rec in self:
            if not rec.booking_id:
                continue
            wrong = rec.move_ids_without_package.filtered(lambda m: m.booking_id and m.booking_id != rec.booking_id)
            if wrong:
                raise ValidationError(_("All moves in this picking must belong to the same Booking."))

    # -------------------------------------------------------------------------
    # ACTIONS — LOAD MOVES FROM BOOKING
    # -------------------------------------------------------------------------
    def action_load_moves_from_booking(self, include_booking_lines=True, include_resource_consumption=True):
        """
        Create stock moves from the linked booking:
        - If include_booking_lines: convert each booking.line with a product to a stock move.
        - If include_resource_consumption: ask each booking.line to prepare resource moves (if any),
          and attach/infer missing locations from this picking.
        """
        for picking in self:
            if not picking.booking_id:
                raise UserError(_("Please link a Booking first."))
            if picking.state not in ("draft", "confirmed", "assigned"):
                raise UserError(_("You can only load moves on a draft/confirmed/assigned transfer."))

            Move = self.env["stock.move"]
            new_moves = []

            # 1) From booking lines
            if include_booking_lines:
                for bline in picking.booking_id.line_ids:
                    if not bline.product_id:
                        continue
                    vals = Move._prepare_move_vals_from_booking_line(bline, picking=picking)
                    if vals:
                        new_moves.append(vals)

            # 2) From resource consumption (delegation to booking.line → booking.resource)
            if include_resource_consumption:
                for bline in picking.booking_id.line_ids:
                    if hasattr(bline, "prepare_resource_consumption"):
                        move_vals_list = bline.prepare_resource_consumption() or []
                        for mv in move_vals_list:
                            # Ensure minimum fields exist and bind to current picking
                            mv.setdefault("name", bline.name or _("Resource Consumption"))
                            mv.setdefault("company_id", picking.company_id.id)
                            mv["picking_id"] = picking.id
                            mv.setdefault("booking_id", picking.booking_id.id)
                            mv.setdefault("booking_line_id", bline.id)
                            mv.setdefault("is_booking_consumption", True)
                            # Default locations from picking if not provided by resource
                            mv.setdefault("location_id", picking.location_id.id)
                            mv.setdefault("location_dest_id", picking.location_dest_id.id)
                            # Optional resource link carried by the resource helper
                            new_moves.append(mv)

            if not new_moves:
                raise UserError(_("No stock moves to create from this booking."))

            Move.create(new_moves)

            picking.message_post(body=_("Loaded %d move(s) from Booking %s.") % (len(new_moves), picking.booking_id.name))

        return True

    # -------------------------------------------------------------------------
    # VALIDATION HOOK — POST BACK TO BOOKING CHATTER
    # -------------------------------------------------------------------------
    def button_validate(self):
        """
        After validating the picking, post a summary message to the related booking (if any).
        """
        res = super().button_validate()
        for picking in self:
            if not picking.booking_id:
                continue
            try:
                # Build a small summary of products & done quantities
                lines = []
                for m in picking.move_ids:
                    if m.state in ("done",) and m.product_id:
                        qty = 0.0
                        # In modern stock, the 'quantity_done' is on move line(s)
                        if m.move_line_ids:
                            qty = sum(m.move_line_ids.mapped("quantity"))
                        else:
                            qty = m.quantity or 0.0
                        if qty:
                            lines.append(f"- {m.product_id.display_name}: {qty} {m.product_uom.display_name}")
                details = "<br/>".join(lines) if lines else _("No quantities validated.")
                picking.booking_id.message_post(
                    body=_("Inventory transfer validated: <b>%s</b><br/>%s") % (picking.name or picking.id, details)
                )
            except Exception:
                # Never block validation due to chatter issues
                pass
        return res

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("This transfer is not linked to any booking."))
        return {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
            "target": "current",
        }


