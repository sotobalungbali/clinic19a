from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicAPLine(models.Model):
    _name = "clinic.ap.line"
    _description = "Clinic AP Line"
    _order = "sequence, id"
    _check_company_auto = True

    _quantity_positive = models.Constraint(
        "CHECK(quantity > 0)",
        "AP line quantity must be greater than zero.",
    )
    _discount_range = models.Constraint(
        "CHECK(discount >= 0 AND discount <= 100)",
        "AP line discount must be between 0 and 100 percent.",
    )
    _price_non_negative = models.Constraint(
        "CHECK(price_unit >= 0)",
        "AP line unit price cannot be negative.",
    )

    ap_id = fields.Many2one("clinic.ap", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="ap_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="ap_id.currency_id", store=True)
    vendor_id = fields.Many2one(related="ap_id.vendor_id", store=True, index=True)
    state = fields.Selection(related="ap_id.state", store=True, index=True)

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description", required=True)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('purchase_ok', '=', True)]",
        ondelete="restrict",
        index=True,
    )
    product_uom_id = fields.Many2one("uom.uom", string="UoM", ondelete="restrict")
    quantity = fields.Float(default=1.0, digits="Product Unit of Measure")
    price_unit = fields.Monetary(currency_field="currency_id", default=0.0)
    discount = fields.Float(default=0.0)
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_ap_line_tax_rel",
        "ap_line_id",
        "tax_id",
        string="Taxes",
        domain="[('type_tax_use', 'in', ('purchase', 'none'))]",
        check_company=True,
    )
    analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account", check_company=True)

    purchase_line_id = fields.Many2one("purchase.order.line", check_company=True, ondelete="restrict", index=True)
    stock_move_id = fields.Many2one("stock.move", check_company=True, ondelete="restrict", index=True)

    billing_invoice_id = fields.Many2one("clinic.billing.invoice", string="Billing Invoice", check_company=True, ondelete="set null")
    billing_line_id = fields.Many2one("clinic.billing.line", string="Billing Line", check_company=True, ondelete="set null")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment", ondelete="set null")
    patient_id = fields.Many2one("res.partner", string="Patient / Cost Beneficiary", ondelete="set null")
    allocation_method = fields.Selection(
        [("none", "None"), ("amount", "Amount"), ("quantity", "Quantity"), ("full", "Full Line")],
        default="none",
    )
    allocated_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    allocated_qty = fields.Float(default=0.0, digits="Product Unit of Measure")
    allocation_locked = fields.Boolean(default=False)

    price_subtotal = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    price_tax = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    price_total = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")

    company_currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    price_unit_company = fields.Monetary(compute="_compute_company_amounts", currency_field="company_currency_id")
    line_total_company = fields.Monetary(compute="_compute_company_amounts", currency_field="company_currency_id")

    match_state = fields.Selection(
        [
            ("no_po", "No PO"),
            ("matched", "Matched"),
            ("qty_mismatch", "Quantity Mismatch"),
            ("price_mismatch", "Price Mismatch"),
            ("receipt_missing", "Receipt Missing"),
        ],
        compute="_compute_match_state",
        search="_search_match_state",
        string="3-Way Match",
    )
    qty_variance = fields.Float(compute="_compute_match_state", digits="Product Unit of Measure")
    price_variance = fields.Monetary(compute="_compute_match_state", currency_field="currency_id")
    stock_valuation_value = fields.Monetary(
        string="Receipt Valuation",
        compute="_compute_stock_valuation",
        currency_field="currency_id",
        help="Current Odoo 19 stock.move valuation converted to the AP document currency.",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.display_name
            # Odoo 19 removed the separate purchase-UoM field. Purchasing,
            # supplier info, stock, and invoice lines share product.uom_id.
            line.product_uom_id = line.product_id.uom_id
            line.tax_ids = line.product_id.supplier_taxes_id.filtered(
                lambda tax: tax.company_id == line.company_id
            )
            seller = line.product_id._select_seller(
                partner_id=line.vendor_id,
                quantity=line.quantity or 1.0,
                date=line.ap_id.invoice_date or fields.Date.context_today(line),
                uom_id=line.product_uom_id,
            )
            if seller:
                price = seller.price
                if seller.currency_id and seller.currency_id != line.currency_id:
                    price = seller.currency_id._convert(
                        price,
                        line.currency_id,
                        line.company_id,
                        line.ap_id.invoice_date or fields.Date.context_today(line),
                    )
                line.price_unit = price

    @api.depends("quantity", "price_unit", "discount", "tax_ids", "currency_id", "product_id", "vendor_id")
    def _compute_amounts(self):
        for line in self:
            discounted_price = (line.price_unit or 0.0) * (1.0 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_ids.compute_all(
                discounted_price,
                currency=line.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.vendor_id,
                is_refund=False,
            )
            line.price_subtotal = taxes["total_excluded"]
            line.price_total = taxes["total_included"]
            line.price_tax = line.price_total - line.price_subtotal

    @api.depends("price_unit", "price_total", "currency_id", "company_currency_id", "ap_id.invoice_date")
    def _compute_company_amounts(self):
        for line in self:
            if not line.currency_id or line.currency_id == line.company_currency_id:
                line.price_unit_company = line.price_unit
                line.line_total_company = line.price_total
            else:
                date = line.ap_id.invoice_date or fields.Date.context_today(line)
                line.price_unit_company = line.currency_id._convert(line.price_unit, line.company_currency_id, line.company_id, date)
                line.line_total_company = line.currency_id._convert(line.price_total, line.company_currency_id, line.company_id, date)

    @api.depends(
        "purchase_line_id",
        "purchase_line_id.product_qty",
        "purchase_line_id.qty_received",
        "purchase_line_id.price_unit",
        "quantity",
        "price_unit",
        "stock_move_id.state",
    )
    @api.model
    def _search_match_state(self, operator, value):
        """Provide a search contract for the live, non-stored three-way-match state."""
        records = self.search([])
        if operator in ("=", "=="):
            matched = records.filtered(lambda rec: rec.match_state == value)
        elif operator == "!=":
            matched = records.filtered(lambda rec: rec.match_state != value)
        elif operator == "in":
            values = set(value or [])
            matched = records.filtered(lambda rec: rec.match_state in values)
        elif operator == "not in":
            values = set(value or [])
            matched = records.filtered(lambda rec: rec.match_state not in values)
        else:
            raise ValueError(f"Unsupported operator for match state: {operator}")
        return [("id", "in", matched.ids)]

    def _compute_match_state(self):
        for line in self:
            line.qty_variance = 0.0
            line.price_variance = 0.0
            if not line.purchase_line_id:
                line.match_state = "no_po"
                continue

            po_line = line.purchase_line_id
            line.qty_variance = line.quantity - po_line.product_qty
            line.price_variance = line.price_unit - po_line.price_unit

            if line.ap_id.company_id.ap_enforce_receipt_before_post and po_line.product_id.type != "service":
                if not line.stock_move_id or line.stock_move_id.state != "done":
                    line.match_state = "receipt_missing"
                    continue

            qty_base = abs(po_line.product_qty) or 1.0
            qty_pct = abs(line.qty_variance) / qty_base * 100.0
            price_base = abs(po_line.price_unit) or 1.0
            price_pct = abs(line.price_variance) / price_base * 100.0
            if qty_pct > (line.company_id.ap_qty_tolerance_percent or 0.0):
                line.match_state = "qty_mismatch"
            elif price_pct > (line.company_id.ap_price_tolerance_percent or 0.0):
                line.match_state = "price_mismatch"
            else:
                line.match_state = "matched"

    @api.depends(
        "stock_move_id",
        "stock_move_id.value",
        "currency_id",
        "company_currency_id",
        "ap_id.invoice_date",
    )
    def _compute_stock_valuation(self):
        """Expose receipt valuation using the native Odoo 19 stock.move contract.

        Odoo 19 no longer exposes the pre-19 ``stock.valuation.layer`` model/
        ``stock_move.stock_valuation_layer_ids`` contract used by older ClinicOne
        drafts.  The stock accounting engine stores the current valuation directly
        on ``stock.move.value`` in company currency.  AP keeps the traceability on
        ``stock_move_id`` and converts that value to the AP document currency.
        """
        for line in self:
            move = line.stock_move_id
            value = move.value if move else 0.0
            if (
                move
                and line.company_currency_id
                and line.currency_id
                and line.company_currency_id != line.currency_id
            ):
                value = line.company_currency_id._convert(
                    value,
                    line.currency_id,
                    line.company_id,
                    line.ap_id.invoice_date or fields.Date.context_today(line),
                )
            line.stock_valuation_value = value

    @api.constrains("company_id", "purchase_line_id", "stock_move_id", "billing_invoice_id", "billing_line_id")
    def _check_company_links(self):
        for line in self:
            linked = [line.purchase_line_id.order_id, line.stock_move_id, line.billing_invoice_id]
            if line.billing_line_id:
                linked.append(line.billing_line_id.invoice_id)
            for record in linked:
                if record and "company_id" in record._fields and record.company_id != line.company_id:
                    raise ValidationError(_("All linked records must belong to the AP company."))

    @api.constrains("allocated_amount", "allocated_qty")
    def _check_allocation(self):
        for line in self:
            if line.allocated_amount < 0 or line.allocated_qty < 0:
                raise ValidationError(_("Allocated amount and quantity cannot be negative."))
            if line.allocated_amount > line.price_total:
                raise ValidationError(_("Allocated amount cannot exceed AP line total."))

    def _prepare_vendor_bill_line_vals(self):
        self.ensure_one()
        vals = {
            "product_id": self.product_id.id or False,
            "name": self.name or "/",
            "quantity": self.quantity,
            "product_uom_id": self.product_uom_id.id or False,
            "price_unit": self.price_unit,
            "discount": self.discount,
            "tax_ids": [(6, 0, self.tax_ids.ids)],
            "purchase_line_id": self.purchase_line_id.id or False,
        }
        if self.analytic_account_id:
            vals["analytic_distribution"] = {str(self.analytic_account_id.id): 100.0}
        return vals

    def action_view_stock_move(self):
        self.ensure_one()
        if not self.stock_move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Move"),
            "res_model": "stock.move",
            "view_mode": "form",
            "res_id": self.stock_move_id.id,
            "context": {"create": False},
        }

    def action_view_billing(self):
        self.ensure_one()
        target = self.billing_line_id or self.billing_invoice_id
        if not target:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Billing Source"),
            "res_model": target._name,
            "view_mode": "form",
            "res_id": target.id,
            "context": {"create": False},
        }

    def write(self, vals):
        financial = {"product_id", "quantity", "product_uom_id", "price_unit", "discount", "tax_ids", "analytic_account_id"}
        if financial.intersection(vals) and any(rec.state in ("posted", "partial", "paid") for rec in self):
            raise UserError(_("Financial AP lines cannot be changed after posting."))
        if "allocation_locked" in self._fields and any(rec.allocation_locked for rec in self) and {
            "billing_invoice_id", "billing_line_id", "allocated_amount", "allocated_qty", "allocation_method"
        }.intersection(vals):
            raise UserError(_("Locked billing allocations cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state in ("posted", "partial", "paid") for rec in self):
            raise UserError(_("Posted AP lines cannot be deleted."))
        return super().unlink()
