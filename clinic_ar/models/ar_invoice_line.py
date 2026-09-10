# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicARInvoiceLine(models.Model):
    _name = "clinic.ar.invoice.line"
    _description = "Accounts Receivable Invoice Line"
    _order = "sequence, id"
    _check_company_auto = True

    invoice_id = fields.Many2one(
        "clinic.ar.invoice",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        related="invoice_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="invoice_id.currency_id",
        store=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="invoice_id.partner_id",
        store=True,
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        related="invoice_id.patient_id",
        store=True,
        index=True,
    )
    billing_line_id = fields.Many2one(
        "clinic.billing.line",
        string="Billing Line",
        index=True,
        check_company=True,
        ondelete="restrict",
    )

    name = fields.Char(required=True)
    product_id = fields.Many2one("product.product", index=True)
    product_uom_id = fields.Many2one("uom.uom", string="UoM")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(currency_field="currency_id", required=True)
    discount = fields.Float(string="Discount (%)", default=0.0)
    taxes_id = fields.Many2many(
        "account.tax",
        "clinic_ar_invoice_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        check_company=True,
    )
    income_account_id = fields.Many2one(
        "account.account",
        string="Income Account",
        check_company=True,
        domain="[('account_type', 'in', ('income', 'income_other'))]",
    )

    discount_amount = fields.Monetary(
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
    )
    price_subtotal = fields.Monetary(
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
    )
    price_tax = fields.Monetary(
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
    )
    price_total = fields.Monetary(
        compute="_compute_amount",
        store=True,
        currency_field="currency_id",
    )

    @api.depends(
        "quantity", "price_unit", "discount", "taxes_id",
        "product_id", "invoice_id.partner_id", "currency_id",
    )
    def _compute_amount(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id
            gross = line.quantity * line.price_unit
            discount_amount = gross * max(line.discount, 0.0) / 100.0
            effective_unit = line.price_unit * (1.0 - max(line.discount, 0.0) / 100.0)
            if line.taxes_id:
                taxes = line.taxes_id.compute_all(
                    effective_unit,
                    currency=currency,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.partner_id,
                )
                subtotal = taxes["total_excluded"]
                total = taxes["total_included"]
            else:
                subtotal = line.quantity * effective_unit
                total = subtotal
            line.discount_amount = currency.round(discount_amount)
            line.price_subtotal = currency.round(subtotal)
            line.price_tax = currency.round(total - subtotal)
            line.price_total = currency.round(total)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.display_name
            line.product_uom_id = line.product_id.uom_id
            line.price_unit = line.product_id.lst_price
            line.taxes_id = line.product_id.taxes_id
            accounts = line.product_id.product_tmpl_id.get_product_accounts()
            income = accounts.get("income")
            if income:
                line.income_account_id = income

    @api.constrains("quantity", "price_unit", "discount")
    def _check_financial_values(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError(_("Quantity cannot be negative."))
            if line.price_unit < 0:
                raise ValidationError(_("Unit Price cannot be negative."))
            if line.discount < 0 or line.discount > 100:
                raise ValidationError(_("Discount must be between 0 and 100 percent."))

    @api.constrains("income_account_id", "company_id")
    def _check_income_account_company(self):
        for line in self:
            if (
                line.income_account_id
                and line.company_id
                and line.company_id not in line.income_account_id.sudo().company_ids
            ):
                raise ValidationError(_("Income Account is not available to the AR Line company."))

    def write(self, vals):
        for line in self:
            if line.invoice_id.state != "draft":
                raise UserError(_("AR lines cannot be modified after the AR Invoice is posted."))
        return super().write(vals)

    def unlink(self):
        if any(line.invoice_id.state != "draft" for line in self):
            raise UserError(_("AR lines cannot be deleted after the AR Invoice is posted."))
        return super().unlink()

    def action_open_billing_line(self):
        self.ensure_one()
        if not self.billing_line_id:
            raise UserError(_("This AR Line is not linked to a Billing Line."))
        return self.billing_line_id._get_records_action(name=_("Billing Line"))



