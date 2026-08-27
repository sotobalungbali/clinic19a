# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_line.py
#
# Purpose
# -------
# Line items for a Booking:
# - Products/services/consumables tied to a booking
# - Tax/amount computations (subtotal, tax, total) similar to sale.order.line
# - Optional linkage to treatments and resources
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (reverse O2M: line_ids)
# - product.product / uom.uom / account.tax
# - clinic.treatment (reference)
# - booking.resource (optional line-level resources, in addition to booking-level)
# - account.move creation is done by booking via _prepare_invoice_line_from_booking_line()
#
# All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingLine(models.Model):
    _name = "booking.line"
    _description = "Booking Line"
    _order = "sequence, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ---------------------------------------------------------------------
    # RELATIONS / CONTEXT
    # ---------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent booking document.",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="booking_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="booking_id.currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        related="booking_id.state",
        string="Booking Status",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )

    # ---------------------------------------------------------------------
    # DISPLAY / CLASSIFICATION
    # ---------------------------------------------------------------------
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear first.",
    )

    display_type = fields.Selection(
        selection=[("line_section", "Section"), ("line_note", "Note")],
        string="Display Type",
        help="Technical field for UX sections/notes. Non-commercial line (no amount).",
    )
    is_display_type = fields.Boolean(
        string="Is Display Type",
        compute="_compute_is_display_type",
        help="Technical helper to flag section/note lines.",
        store=True,
    )

    tag_ids = fields.Many2many(
        "booking.tag",
        "booking_line_tag_rel",
        "line_id",
        "tag_id",
        string="Tags",
        help="Optional tags for search and reporting.",
    )

    # ---------------------------------------------------------------------
    # PRODUCT / TREATMENT / RESOURCES
    # ---------------------------------------------------------------------
    name = fields.Text(
        string="Description",
        required=False,
        help="Line description shown on documents.",
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("sale_ok", "=", True)],
        help="Product/service for this booking line.",
        tracking=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Optional treatment reference for this line.",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_line_resource_rel",
        "line_id",
        "resource_id",
        string="Resources",
        help="Resources used for this specific line (optional, complements booking-level resources).",
    )

    # UoM / Quantity / Pricing
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of Measure for the product.",
    )
    product_uom_qty = fields.Float(
        string="Quantity",
        default=1.0,
        help="Ordered quantity for this line.",
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price before discount and taxes.",
    )
    discount = fields.Float(
        string="Discount (%)",
        help="Discount percentage to apply on the unit price.",
        default=0.0,
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "booking_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Customer taxes applied to this line.",
    )

    # Amounts (computed)
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Subtotal without taxes.",
    )
    price_tax = fields.Monetary(
        string="Tax",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Tax amount for this line.",
    )
    price_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Total including taxes.",
    )

    # Accounting helpers (for future extensions)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        help="Optional analytic account for this line.",
    )
    # analytic_tag_ids = fields.Many2many(
    #     "account.analytic.tag",
    #     string="Analytic Tags",
    #     help="Optional analytic tags for this line.",
    # )

    # ---------------------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------------------
    @api.depends("display_type")
    def _compute_is_display_type(self):
        for rec in self:
            rec.is_display_type = bool(rec.display_type)

    @api.depends(
        "product_uom_qty",
        "discount",
        "price_unit",
        "tax_ids",
        "currency_id",
        "product_id",
        "booking_id.patient_id",
    )
    def _compute_amount(self):
        """
        Compute price_subtotal, price_tax, price_total using account.tax.compute_all,
        similar to sale.order.line logic.
        """
        for rec in self:
            if rec.is_display_type:
                rec.price_subtotal = 0.0
                rec.price_tax = 0.0
                rec.price_total = 0.0
                continue

            qty = rec.product_uom_qty or 0.0
            unit = rec.price_unit or 0.0
            disc = rec.discount or 0.0

            # Apply percentage discount
            effective_unit = unit * (1.0 - (disc / 100.0))

            taxes = rec.tax_ids
            currency = rec.currency_id or (rec.booking_id and rec.booking_id.currency_id)
            partner = rec.booking_id and rec.booking_id.patient_id or False

            if taxes:
                tax_res = taxes._origin.compute_all(
                    effective_unit,
                    currency=currency,
                    quantity=qty,
                    product=rec.product_id,
                    partner=partner,
                )
                rec.price_subtotal = tax_res["total_excluded"]
                rec.price_total = tax_res["total_included"]
                rec.price_tax = rec.price_total - rec.price_subtotal
            else:
                rec.price_subtotal = effective_unit * qty
                rec.price_total = rec.price_subtotal
                rec.price_tax = 0.0

    # ---------------------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        """
        Prefill UoM, taxes, description, and unit price from the selected product.
        We keep it simple: use product's sales description, list price, and customer taxes.
        """
        for rec in self:
            if not rec.product_id:
                continue

            product = rec.product_id.with_context(lang=self.env.user.lang or "en_US")
            # Description
            name = product.display_name or ""
            if product.description_sale:
                name += "\n" + product.description_sale
            rec.name = name

            # UoM
            rec.product_uom = product.uom_id

            # Taxes (customer taxes)
            company = rec.company_id or self.env.company
            if company and product.taxes_id:
                rec.tax_ids = product.taxes_id.filtered(lambda t: t.company_id == company)
            else:
                rec.tax_ids = [(5, 0, 0)]

            # Price Unit (basic strategy: list price; pricing engine can override externally)
            rec.price_unit = product.lst_price or 0.0

            # If treatment default exists, try to suggest
            if not rec.treatment_id and hasattr(product, "treatment_id") and product.treatment_id:
                rec.treatment_id = product.treatment_id.id

    @api.onchange("product_uom", "product_uom_qty")
    def _onchange_qty_uom(self):
        """
        Basic guardrails; more complex UoM pricelist logic is intentionally left out
        to keep module lightweight (sale module handles it in its own domain).
        """
        for rec in self:
            if rec.product_uom_qty is not None and rec.product_uom_qty < 0:
                return {
                    "warning": {
                        "title": _("Quantity Warning"),
                        "message": _("Quantity should not be negative."),
                    }
                }
        return {}

    # ---------------------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------------------
    @api.constrains("product_uom_qty", "price_unit", "discount")
    def _check_numbers(self):
        for rec in self:
            if rec.is_display_type:
                continue
            if rec.product_uom_qty is None or rec.product_uom_qty <= 0.0:
                raise ValidationError(_("Quantity must be greater than 0."))
            if rec.price_unit is None or rec.price_unit < 0.0:
                raise ValidationError(_("Unit Price cannot be negative."))
            if rec.discount is not None and (rec.discount < 0.0 or rec.discount > 100.0):
                raise ValidationError(_("Discount must be between 0 and 100."))

    @api.constrains("product_id", "name")
    def _check_content_presence(self):
        """
        Require at least a product or a non-empty description for commercial lines.
        """
        for rec in self:
            if rec.is_display_type:
                continue
            if not rec.product_id and not rec.name:
                raise ValidationError(_("Please set a Product or a Description for the line."))

    # ---------------------------------------------------------------------
    # HELPERS — INVOICING & STOCK
    # ---------------------------------------------------------------------
    # def prepare_invoice_line_vals(self):
    #     """
    #     Optional helper if callers want to use line's own mapping.
    #     The booking currently calls its own mapper; this mirrors that structure.
    #     """
    #     self.ensure_one()
    #     taxes = self.tax_ids
    #     return {
    #         "name": self.name or (self.product_id and self.product_id.display_name) or _("Booking Line"),
    #         "product_id": self.product_id.id if self.product_id else False,
    #         "quantity": self.product_uom_qty or 1.0,
    #         "price_unit": self.price_unit or 0.0,
    #         "discount": self.discount or 0.0,
    #         "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
    #         "currency_id": self.currency_id.id,
    #         "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
    #         "analytic_tag_ids": [(6, 0, self.analytic_tag_ids.ids)] if self.analytic_tag_ids else False,
    #     }

    # ... lalu di prepare_invoice_line_vals():
    def prepare_invoice_line_vals(self):
        self.ensure_one()
        taxes = self.tax_ids
        return {
            "name": self.name or (self.product_id and self.product_id.display_name) or _("Booking Line"),
            "product_id": self.product_id.id if self.product_id else False,
            "quantity": self.product_uom_qty or 1.0,
            "price_unit": self.price_unit or 0.0,
            "discount": self.discount or 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "currency_id": self.currency_id.id,
            # "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
            # "analytic_tag_ids": [(6, 0, self.analytic_tag_ids.ids)] if self.analytic_tag_ids else False,
        }

    def prepare_resource_consumption(self):
        """
        Prepare stock moves for resource consumption at line level (optional).
        This delegates to each resource's prepare_stock_moves().
        """
        moves = []
        for rec in self:
            if not rec.resource_ids:
                continue
            for resource in rec.resource_ids:
                qty = None
                # If the product equals the resource.product, you might derive qty from line qty
                if resource.track_consumption and resource.product_id and rec.product_id == resource.product_id:
                    qty = rec.product_uom_qty
                mv_vals = resource.prepare_stock_moves(booking=rec.booking_id, qty=qty)
                moves += mv_vals
        return moves

    # ---------------------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------------------
    def action_view_booking(self):
        self.ensure_one()
        action = {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
        }
        return action

    # ---------------------------------------------------------------------
    # COPY / DEFAULTS
    # ---------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If created from booking form, booking_id is in context
        if not res.get("booking_id"):
            ctx_booking = self.env.context.get("default_booking_id")
            if ctx_booking:
                res["booking_id"] = ctx_booking
        return res

    def copy_data(self, default=None):
        """
        Keep a sensible copy, reset amounts (recompute), keep the same product/taxes.
        """
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("price_subtotal", 0.0)
        default.setdefault("price_tax", 0.0)
        default.setdefault("price_total", 0.0)
        return super().copy_data(default)
