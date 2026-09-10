# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_line.py
# License: LGPL-3
#
# ClinicOne — Clinic Billing
# Core Billing Line (CE-first, no analytic dependency)
#
# Notes:
# - Tidak ada referensi ke account.analytic.* (aman di CE baseline).
# - Hitung subtotal & total memakai engine pajak Odoo (account.tax.compute_all).
# - Section/Note lines didukung via display_type (sesuai pola account.move.line).
# - Komponen lain (commission, treatment/booking refs) ditambahkan lewat file hook terpisah
#   seperti doctor_hook.py & treatment_hook.py (agar modular & tanpa circular dependency).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicBillingLine(models.Model):
    _name = "clinic.billing.line"
    _description = "Clinic Billing Line"
    _order = "invoice_id, sequence, id"
    _check_company_auto = True

    # -- Parent / sequence
    invoice_id = fields.Many2one(
        "clinic.billing.invoice",
        string="Clinic Invoice",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Sequence", default=10)

    # -- Display helpers (section/note compatibility pattern)
    display_type = fields.Selection(
        selection=[("line_section", "Section"), ("line_note", "Note")],
        string="Display Type",
        help="Technical field for layout: Section/Note lines carry no amounts or taxes."
    )

    # -- Basic info
    name = fields.Char(
        string="Description",
        required=False,
        help="Short description printed on invoice."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product/Service",
        domain="[('sale_ok','=',True)]",
        help="Product or service to bill."
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        help="Unit of Measure for the quantity."
    )
    line_type = fields.Selection(
        [
            ("product", "Product"),
            ("service", "Service"),
            ("misc", "Miscellaneous"),
        ],
        string="Line Type",
        compute="_compute_line_type",
        store=True,
        help="Derived from product type; used for reporting/rules."
    )

    # -- Quantity & price
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Billed quantity."
    )
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="List price or negotiated price per unit (before discount)."
    )

    # -- Taxes
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_billing_line_tax_rel",
        "line_id", "tax_id",
        string="Taxes",
        domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]",
        help="Taxes to apply on this line."
    )

    # -- Discounts (per-line)
    discount_percent = fields.Float(
        string="Discount (%)",
        help="Percentage discount applied to (price_unit * qty)."
    )
    discount_amount = fields.Monetary(
        string="Discount (Fixed)",
        currency_field="currency_id",
        help="Fixed discount in document currency, applied per line."
    )

    # -- Amounts
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="invoice_id.currency_id",
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="invoice_id.company_id",
        store=True,
        readonly=True
    )
    subtotal_excl_tax = fields.Monetary(
        string="Subtotal (Excl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    tax_amount = fields.Monetary(
        string="Tax Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )
    total_incl_tax = fields.Monetary(
        string="Total (Incl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True
    )

    # -- CE-friendly analytic placeholders (no dependency)
    analytic_label = fields.Char(
        string="Analytic Label",
        help="Optional free-form label to group lines for internal analysis."
    )
    analytic_notes = fields.Char(
        string="Analytic Notes",
        help="Short internal note used as a lightweight analytic tag."
    )

    # -- Misc
    note = fields.Char(string="Internal Note")

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    @api.constrains("discount_percent")
    def _check_discount_percent(self):
        for rec in self:
            if rec.discount_percent and (rec.discount_percent < 0.0 or rec.discount_percent > 100.0):
                raise ValidationError(_("Discount (%) must be between 0 and 100."))

    @api.constrains("quantity")
    def _check_quantity_non_negative(self):
        for rec in self:
            if rec.display_type in ("line_section", "line_note"):
                continue
            if rec.quantity is not None and rec.quantity < 0:
                raise ValidationError(_("Quantity cannot be negative."))

    # =========================================================================
    # ONCHANGE
    # =========================================================================
    @api.onchange("product_id")
    def _onchange_product_id_set_defaults(self):
        for rec in self:
            if not rec.product_id:
                continue
            # Default description
            if not rec.name:
                rec.name = rec.product_id.display_name
            # Default UoM (match product's uom)
            try:
                if rec.product_id.uom_id:
                    rec.product_uom_id = rec.product_id.uom_id.id
            except Exception:
                pass
            # Default taxes
            try:
                if rec.product_id.taxes_id:
                    rec.tax_ids = [(6, 0, rec.product_id.taxes_id.ids)]
            except Exception:
                pass
            # Default unit price (list price)
            try:
                rec.unit_price = rec.product_id.lst_price
            except Exception:
                pass

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("product_id")
    def _compute_line_type(self):
        for rec in self:
            if rec.product_id:
                try:
                    ptype = rec.product_id.type or "service"
                    rec.line_type = "service" if ptype == "service" else "product"
                except Exception:
                    rec.line_type = "service"
            else:
                rec.line_type = "misc"

    @api.depends(
        "display_type",
        "quantity",
        "unit_price",
        "discount_percent",
        "discount_amount",
        "tax_ids",
        "product_id",
        "product_uom_id",
        "invoice_id.patient_id",
        "invoice_id.fiscal_position_id",
        "invoice_id.currency_id",
        "invoice_id.company_id",
    )
    def _compute_amounts(self):
        Tax = self.env["account.tax"].sudo()
        for rec in self:
            # Section/Note lines carry no amounts
            if rec.display_type in ("line_section", "line_note"):
                rec.subtotal_excl_tax = 0.0
                rec.tax_amount = 0.0
                rec.total_incl_tax = 0.0
                continue

            qty = float(rec.quantity or 0.0)
            unit = float(rec.unit_price or 0.0)

            # Apply percentage & fixed discount to get effective unit
            eff_subtotal = unit * qty
            pct = float(rec.discount_percent or 0.0) / 100.0
            eff_subtotal *= (1.0 - pct)
            eff_subtotal -= float(rec.discount_amount or 0.0)
            if qty and qty != 0:
                eff_unit = eff_subtotal / qty
            else:
                eff_unit = unit  # fallback

            # Compute taxes with Odoo's engine (if taxes exist)
            taxes = rec.tax_ids or Tax.browse([])
            partner = getattr(rec.invoice_id, "patient_id", False)
            product = rec.product_id or False

            res = taxes.compute_all(
                eff_unit,
                currency=rec.currency_id,
                quantity=qty,
                product=product,
                partner=partner,
                is_refund=False,
            ) if taxes else {"total_excluded": eff_subtotal, "total_included": eff_subtotal, "taxes": []}

            rec.subtotal_excl_tax = float(res.get("total_excluded", 0.0))
            rec.total_incl_tax = float(res.get("total_included", rec.subtotal_excl_tax))
            # Sum tax details
            tax_total = 0.0
            try:
                for t in res.get("taxes", []):
                    tax_total += float(t.get("amount", 0.0))
            except Exception:
                pass
            rec.tax_amount = tax_total

    # =========================================================================
    # HELPERS
    # =========================================================================
    def get_effective_unit_price(self):
        """Return effective price unit after discount% and fixed discount."""
        self.ensure_one()
        if self.display_type in ("line_section", "line_note"):
            return 0.0
        qty = float(self.quantity or 0.0)
        unit = float(self.unit_price or 0.0)
        subtotal = unit * qty
        subtotal *= (1.0 - float(self.discount_percent or 0.0) / 100.0)
        subtotal -= float(self.discount_amount or 0.0)
        return (subtotal / qty) if qty else unit

    def write(self, vals):
        locked = self.filtered(lambda rec: rec.invoice_id.move_id and rec.invoice_id.move_id.state == "posted")
        if locked and set(vals).intersection({
            "display_type", "name", "product_id", "product_uom_id", "quantity", "unit_price",
            "tax_ids", "discount_percent", "discount_amount",
        }):
            raise ValidationError(_("Billing lines cannot be changed after the accounting invoice is posted."))
        return super().write(vals)

    def unlink(self):
        locked = self.filtered(lambda rec: rec.invoice_id.move_id and rec.invoice_id.move_id.state == "posted")
        if locked:
            raise ValidationError(_("Billing lines cannot be deleted after the accounting invoice is posted."))
        return super().unlink()



