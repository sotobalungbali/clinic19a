# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/account_move_inherit.py
#
# Purpose
# -------
# Extend accounting documents to be aware of Bookings:
# - Link invoice/bill (account.move) to a booking
# - Pull lines from booking lines (on demand)
# - Enforce patient/partner and company consistency with the booking
# - Optional deposit/fee labeling for analytics (deposit, cancellation fee, no-show fee, reschedule fee)
# - Gentle back-linking to booking.invoice_id on post
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking  (M2O link; push/pull lines; handshake on post)
# - booking.line     (per-line link on account.move.line)
# - clinic.treatment (indirect via booking lines/products)
# - booking.policy   (deposit/cancellation/no-show semantics live there; here we only tag/account them)
#
# Notes
# -----
# - All user-facing strings are in English.
# - We avoid enforcing "one invoice per booking" because deposits and follow-up
#   charges may require multiple invoices; the booking header already stores one
#   primary invoice_id (usually the "final" invoice).
# - No hard dependency on controllers or wizards; helpers are callable from UIs or server actions.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# account.move — Inherit
# =============================================================================
class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # RELATIONS WITH BOOKING
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="The booking this invoice is related to.",
        copy=False,
    )
    booking_state = fields.Selection( # 002
        related="booking_id.state",
        string="Booking Status",
        store=True,
        readonly=True,
    )
    booking_patient_id = fields.Many2one(
        "res.partner",
        related="booking_id.patient_id",
        string="Patient",
        store=True,
        readonly=True,
    )

    # Labeling for analytics/reporting (optional)
    booking_charge_kind = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("deposit", "Deposit"),
            ("cancellation_fee", "Cancellation Fee"),
            ("no_show_fee", "No-show Fee"),
            ("reschedule_fee", "Reschedule Fee"),
        ],
        string="Booking Charge Kind",
        default="standard",
        help="Label this invoice for reporting. Does not affect accounting logic.",
    )
    booking_deposit_amount = fields.Monetary(
        string="Deposit Amount",
        currency_field="currency_id",
        compute="_compute_booking_deposit_amount",
        store=True,
        help="Total untaxed amount when this invoice is labeled as a Deposit.",
    )

    # Convenience copy of channel/policy (not enforced; filled from booking if present)
    booking_channel_id = fields.Many2one(
        "booking.channel",
        string="Booking Channel",
        help="Channel context copied from the booking for reporting.",
        copy=False,
    )
    booking_policy_id = fields.Many2one(
        "booking.policy",
        string="Booking Policy",
        help="Policy context copied from the booking for reporting.",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        When a booking is selected:
        - Ensure partner is the patient (if empty), and set invoice_origin
        - Copy channel/policy for reporting
        - Align company to booking's company if not set (common in draft)
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            # Partner
            if not rec.partner_id and b.patient_id:
                rec.partner_id = b.patient_id.id
            # Origin reference
            if not rec.invoice_origin:
                rec.invoice_origin = b.name
            # Company (only if empty; otherwise enforce via constraint)
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id
            # Channel/Policy snapshot
            if b.channel_id:
                rec.booking_channel_id = b.channel_id.id
            if b.policy_id:
                rec.booking_policy_id = b.policy_id.id

    @api.onchange("partner_id")
    def _onchange_partner_id_booking_guard(self):
        """
        Guard: If booking is selected and partner differs from patient,
        keep it but show a warning (hard enforcement is done via constraint).
        """
        for rec in self:
            if rec.booking_id and rec.partner_id and rec.partner_id != rec.booking_id.patient_id:
                return {
                    "warning": {
                        "title": _("Partner / Patient Mismatch"),
                        "message": _(
                            "Selected partner differs from the booking patient (%s). "
                            "You can keep it, but posting will enforce consistency."
                        ) % (rec.booking_id.patient_id.display_name,),
                    }
                }
        return {}

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_id", "partner_id")
    def _check_partner_patient_consistency(self):
        """
        When a booking is linked, partner must be that booking's patient.
        """
        for rec in self:
            if rec.booking_id and rec.partner_id and rec.partner_id != rec.booking_id.patient_id:
                raise ValidationError(_("Partner must match the Booking's Patient."))

    @api.constrains("booking_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("booking_charge_kind", "invoice_line_ids.price_subtotal", "move_type")
    def _compute_booking_deposit_amount(self):
        for rec in self:
            if rec.booking_charge_kind == "deposit" and rec.is_invoice(include_receipts=True):
                # Sum untaxed line amounts (same as 'amount_untaxed' but kept independent)
                rec.booking_deposit_amount = sum(rec.invoice_line_ids.mapped("price_subtotal"))
            else:
                rec.booking_deposit_amount = 0.0

    # -------------------------------------------------------------------------
    # ACTIONS / HOOKS
    # -------------------------------------------------------------------------
    def action_post(self):
        """
        On posting:
        - Ensure Booking link handshake (set booking.invoice_id if empty)
        - Post a message on the booking for traceability
        """
        res = super().action_post()
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            try:
                # Handshake: set booking.invoice_id if empty
                if not b.invoice_id:
                    b.invoice_id = rec.id
                # Chatter note on booking
                b.message_post(
                    body=_("Invoice posted: <a href='#' data-oe-model='account.move' data-oe-id='%d'>%s</a>")
                         % (rec.id, rec.name or rec.ref or rec.id)
                )
            except Exception:
                # Never block posting due to handshake issues
                pass
        return res

    def action_pull_lines_from_booking(self):
        """
        Create invoice lines from linked booking lines.
        Safe-guard:
        - Does nothing if no booking or there are already non-display invoice lines
        - Raises if move is not draft
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You can only pull lines on a draft invoice."))
            if not rec.booking_id:
                raise UserError(_("Please link a Booking first."))
            if any(not l.display_type for l in rec.invoice_line_ids):
                raise UserError(_("This invoice already has commercial lines."))

            inv_lines_vals = []
            for bline in rec.booking_id.line_ids:
                vals = rec._prepare_invoice_line_from_booking_line(bline)
                if vals:
                    inv_lines_vals.append((0, 0, vals))
            if not inv_lines_vals and rec.booking_id.treatment_id and hasattr(rec.booking_id.treatment_id, "product_id"):
                # Fallback: use treatment's product
                product = rec.booking_id.treatment_id.product_id
                if product:
                    inv_lines_vals.append((0, 0, {
                        "name": product.display_name or rec.booking_id.treatment_id.name or _("Treatment"),
                        "product_id": product.id,
                        "quantity": 1.0,
                        "price_unit": product.lst_price,
                        "tax_ids": [(6, 0, product.taxes_id.ids)],
                        "booking_line_id": False,
                    }))

            if not inv_lines_vals:
                raise UserError(_("No billable booking lines or treatment found."))

            rec.write({"invoice_line_ids": inv_lines_vals})

            # Copy channel/policy snapshot if missing
            if rec.booking_id.channel_id and not rec.booking_channel_id:
                rec.booking_channel_id = rec.booking_id.channel_id.id
            if rec.booking_id.policy_id and not rec.booking_policy_id:
                rec.booking_policy_id = rec.booking_id.policy_id.id

    def _prepare_invoice_line_from_booking_line(self, bline):
        """
        Map booking.line to account.move.line values.
        This is similar to booking_booking._prepare_invoice_line_from_booking_line,
        but includes a back-link (booking_line_id) for analytics.
        """
        product = getattr(bline, "product_id", False)
        quantity = getattr(bline, "product_uom_qty", 1.0) or 1.0
        name = getattr(bline, "name", False) or (product and product.display_name) or _("Booking Line")
        price_unit = getattr(bline, "price_unit", product and product.lst_price or 0.0)
        taxes = getattr(bline, "tax_ids", self.env["account.tax"])
        return {
            "name": name,
            "product_id": product.id if product else False,
            "quantity": quantity,
            "price_unit": price_unit or 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "booking_line_id": bline.id,
        }

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_booking(self):
        """
        Open the linked booking (convenience from invoice).
        """
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("This document is not linked to any booking."))
        return {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
            "target": "current",
        }


# =============================================================================
# account.move.line — Inherit
# =============================================================================
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Link back to Booking & Booking Line
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        related="move_id.booking_id",
        store=True,
        readonly=True,
    )
    booking_line_id = fields.Many2one(
        "booking.line",
        string="Booking Line",
        index=True,
        help="Original booking line this invoice line corresponds to.",
        copy=False,
    )

    # Fee labeling at line level (optional, for analytics; does not alter accounting)
    is_booking_fee = fields.Boolean(
        string="Is Booking Fee",
        help="Enable to mark this line as a fee (e.g., cancellation, no-show, reschedule).",
        default=False,
    )
    booking_fee_type = fields.Selection(
        selection=[
            ("deposit", "Deposit"),
            ("cancellation_fee", "Cancellation Fee"),
            ("no_show_fee", "No-show Fee"),
            ("reschedule_fee", "Reschedule Fee"),
            ("other", "Other"),
        ],
        string="Booking Fee Type",
        help="Type of fee represented by this line (for reporting).",
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_line_id")
    def _onchange_booking_line_id(self):
        """
        When a booking line is selected, prefill product/qty/price/taxes/description.
        """
        for rec in self:
            bl = rec.booking_line_id
            if not bl:
                continue
            product = bl.product_id
            rec.name = bl.name or (product and product.display_name) or _("Booking Line")
            rec.product_id = product.id if product else False
            rec.quantity = bl.product_uom_qty or 1.0
            rec.price_unit = (bl.price_unit or (product and product.lst_price) or 0.0)
            rec.tax_ids = [(6, 0, bl.tax_ids.ids)] if bl.tax_ids else False

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_line_id", "move_id")
    def _check_booking_line_company_and_header(self):
        """
        Ensure the booking line belongs to the same booking as the invoice header.
        """
        for rec in self:
            if rec.booking_line_id and rec.move_id and rec.move_id.booking_id:
                if rec.booking_line_id.booking_id != rec.move_id.booking_id:
                    raise ValidationError(
                        _("The selected Booking Line does not belong to the invoice's Booking.")
                    )
