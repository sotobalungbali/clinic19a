# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_voucher.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Voucher Program (Campaign/Rule Holder)
# =============================================================================
class ClinicBillingVoucherProgram(models.Model):
    """
    Voucher Program
    ---------------
    High-level configuration for voucher issuance and application:
    - voucher_type: coupon (code with usage count) or gift_card (prepaid balance).
    - scope: line-level or invoice-level application.
    - method: percent or fixed for coupon; gift_card consumes balance (treated as fixed up to balance).
    - conditions: doctor, product/category, line type, branch, partner tags, dates, thresholds.
    - stacking: stackable/exclusive with other vouchers/discounts.
    """
    _name = "clinic.billing.voucher.program"
    _description = "Clinic Billing Voucher Program"
    _order = "priority desc, id desc"

    name = fields.Char(string="Program Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, default=lambda s: s.env.company.currency_id)

    voucher_type = fields.Selection(
        [("coupon", "Coupon"), ("gift_card", "Gift Card")],
        string="Voucher Type", required=True, default="coupon",
        help="Coupon uses percent/fixed rules and usage limits; Gift Card consumes balance."
    )
    scope = fields.Selection(
        [("line", "Line"), ("invoice", "Invoice")],
        string="Scope", required=True, default="invoice",
        help="Where the voucher applies (per line or the entire invoice)."
    )
    method = fields.Selection(
        [("percent", "Percent"), ("fixed", "Fixed Amount")],
        string="Method", default="percent",
        help="For coupon type. Gift Card ignores this and consumes its balance."
    )
    percent = fields.Float(string="Percent (%)", digits=(16, 4))
    amount = fields.Monetary(string="Fixed Amount", currency_field="currency_id")
    base_type = fields.Selection(
        [("subtotal_excl_tax", "Subtotal (Excl. Tax)"), ("total_incl_tax", "Total (Incl. Tax)")],
        string="Base Type", default="subtotal_excl_tax"
    )

    # Conditions
    doctor_partner_id = fields.Many2one("res.partner", string="Doctor")
    product_id = fields.Many2one("product.product", string="Product")
    product_category_id = fields.Many2one("product.category", string="Product Category")
    line_type = fields.Selection(
        [("service", "Service"), ("product", "Product"), ("package", "Package")],
        string="Line Type"
    )
    partner_category_ids = fields.Many2many("res.partner.category", string="Customer Tags")
    branch_id = fields.Many2one("stock.warehouse", string="Clinic Branch")

    # Thresholds & Dates
    min_qty = fields.Float(string="Min Quantity")
    min_subtotal = fields.Monetary(string="Min Subtotal", currency_field="currency_id")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")

    # Stacking & Exclusivity
    stackable = fields.Boolean(string="Stackable", default=True)
    exclusive = fields.Boolean(string="Exclusive (Stop Further Vouchers)", default=False)
    max_discount_per_line = fields.Monetary(string="Max Discount/Line", currency_field="currency_id")
    max_discount_per_invoice = fields.Monetary(string="Max Discount/Invoice", currency_field="currency_id")

    # Code generation
    code_prefix = fields.Char(string="Code Prefix", help="Static prefix for generated codes (e.g., CLINIC).")
    code_length = fields.Integer(string="Code Length", default=10, help="Length of the random portion (not including prefix).")
    code_uppercase = fields.Boolean(string="Uppercase", default=True)
    code_use_alnum = fields.Boolean(string="Alphanumeric", default=True)

    # Usage
    usage_limit_global = fields.Integer(string="Global Usage Limit", help="Max total usage across all vouchers in this program (0=unlimited).")
    usage_count_global = fields.Integer(string="Global Usage Count", readonly=True, help="Auto-tracked from redemptions.")
    default_usage_limit_per_voucher = fields.Integer(
        string="Default Uses per Voucher", default=1,
        help="Default number of uses for issued coupons (ignored for gift cards)."
    )

    priority = fields.Integer(string="Priority", default=10)
    note = fields.Char(string="Note")

    # -------- helper checks --------
    def _within_dates(self, date_ref):
        if self.date_start and date_ref and date_ref < self.date_start:
            return False
        if self.date_end and date_ref and date_ref > self.date_end:
            return False
        return True

    def _partner_has_tags(self, partner):
        if not self.partner_category_ids:
            return True
        if not partner:
            return False
        return bool(self.partner_category_ids & partner.category_id)

    def _base_value(self, invoice):
        return invoice.amount_untaxed if self.base_type == "subtotal_excl_tax" else invoice.amount_total

    def is_applicable_to_invoice(self, invoice):
        self.ensure_one()
        if not self.active:
            return False
        if not self._within_dates(invoice.invoice_date or fields.Date.context_today(self)):
            return False
        if self.company_id != invoice.company_id:
            return False
        if self.doctor_partner_id and self.doctor_partner_id != invoice.doctor_partner_id:
            return False
        if self.branch_id and self.branch_id != invoice.clinic_warehouse_id:
            return False
        if not self._partner_has_tags(invoice.patient_id):
            return False
        base = self._base_value(invoice) or 0.0
        if self.min_subtotal and base < self.min_subtotal:
            return False
        return True

    def is_applicable_to_line(self, invoice, line):
        self.ensure_one()
        if not self.active:
            return False
        if not self._within_dates(invoice.invoice_date or fields.Date.context_today(self)):
            return False
        if self.company_id != invoice.company_id:
            return False
        if self.doctor_partner_id and self.doctor_partner_id != (invoice.doctor_partner_id or line.invoice_id.doctor_partner_id):
            return False
        if self.line_type and self.line_type != line.line_type:
            return False
        if self.product_id and self.product_id != line.product_id:
            return False
        if self.product_category_id and line.product_id and self.product_category_id != line.product_id.categ_id:
            return False
        if self.branch_id and self.branch_id != invoice.clinic_warehouse_id:
            return False
        if not self._partner_has_tags(invoice.patient_id):
            return False
        if self.min_qty and (line.quantity or 0.0) < self.min_qty:
            return False
        base = (line.subtotal_excl_tax or 0.0) if self.base_type == "subtotal_excl_tax" else (line.total_incl_tax or 0.0)
        if self.min_subtotal and base < self.min_subtotal:
            return False
        return True

    # -------- issuance helpers --------
    def _generate_code(self):
        import random
        import string
        prefix = (self.code_prefix or "").strip()
        length = max(4, self.code_length or 10)
        if self.code_use_alnum:
            pool = string.ascii_uppercase + string.digits if self.code_uppercase else string.ascii_letters + string.digits
        else:
            pool = string.digits
        body = "".join(random.choice(pool) for _ in range(length))
        code = (prefix + body).upper() if self.code_uppercase else (prefix + body)
        return code

    def action_generate_vouchers(self, count=1, owner_partner_id=False, initial_balance=0.0):
        """
        Issue `count` vouchers for this program.
        - For coupon: usage_limit_per_voucher defaults from program (>=1).
        - For gift_card: initial_balance is required (>0).
        """
        self.ensure_one()
        if count <= 0:
            raise UserError(_("Count must be positive."))
        vouchers = self.env["clinic.billing.voucher"]
        for _ in range(count):
            code = self._generate_code()
            vals = {
                "program_id": self.id,
                "code": code,
                "company_id": self.company_id.id,
                "currency_id": self.currency_id.id,
                "owner_partner_id": owner_partner_id or False,
                "state": "active",
                "date_start": self.date_start,
                "date_end": self.date_end,
            }
            if self.voucher_type == "coupon":
                vals["usage_limit"] = max(1, self.default_usage_limit_per_voucher or 1)
                vals["balance_amount"] = 0.0
                vals["initial_balance_amount"] = 0.0
            else:
                if initial_balance <= 0:
                    raise UserError(_("Initial balance must be > 0 for Gift Card."))
                vals["usage_limit"] = 0  # unlimited uses until balance exhausted
                vals["balance_amount"] = initial_balance
                vals["initial_balance_amount"] = initial_balance
            vouchers |= self.env["clinic.billing.voucher"].create(vals)
        return vouchers


# =============================================================================
# Voucher Instance (Issuance)
# =============================================================================
class ClinicBillingVoucher(models.Model):
    _name = "clinic.billing.voucher"
    _description = "Clinic Billing Voucher"
    _order = "id desc"
    _rec_name = "code"

    program_id = fields.Many2one("clinic.billing.voucher.program", string="Program", required=True, index=True)
    code = fields.Char(string="Code", required=True, index=True, copy=False)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, default=lambda s: s.env.company.currency_id)

    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("blocked", "Blocked"), ("expired", "Expired"), ("exhausted", "Exhausted")],
        string="Status", default="active", index=True
    )
    owner_partner_id = fields.Many2one("res.partner", string="Owner (Optional)")

    date_start = fields.Date(string="Valid From")
    date_end = fields.Date(string="Valid Until")

    # For coupon: usage-based. For gift card: balance-based.
    usage_limit = fields.Integer(string="Usage Limit (Coupon)", default=1, help="0 = unlimited (use with caution).")
    usage_count = fields.Integer(string="Usage Count", readonly=True)
    initial_balance_amount = fields.Monetary(string="Initial Balance", currency_field="currency_id", readonly=True)
    balance_amount = fields.Monetary(string="Current Balance", currency_field="currency_id")

    # Reservation (optional): lock part of balance to an invoice before posting
    reserved_amount = fields.Monetary(string="Reserved Amount", currency_field="currency_id", readonly=True)
    reserved_invoice_id = fields.Many2one("clinic.billing.invoice", string="Reserved For Invoice", readonly=True)

    # Notes
    note = fields.Char(string="Note")

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Voucher code must be unique per company.",
    )

    # ---- Validity checks ----
    def _is_within_dates(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_start and rec.date_start > today:
                return False
            if rec.date_end and rec.date_end < today:
                return False
        return True

    def _ensure_active(self):
        for rec in self:
            if rec.state in ("expired", "blocked"):
                raise UserError(_("Voucher is not active."))
            if not rec._is_within_dates():
                rec.state = "expired"
                raise UserError(_("Voucher is expired."))
            if rec.program_id.voucher_type == "coupon":
                # if usage limit reached
                if rec.usage_limit and rec.usage_count >= rec.usage_limit:
                    rec.state = "exhausted"
                    raise UserError(_("Voucher usage limit has been reached."))
            else:
                # gift card: balance check
                if (rec.balance_amount or 0.0) <= 0.0:
                    rec.state = "exhausted"
                    raise UserError(_("Voucher balance is exhausted."))

    # ---- Reservation helpers (optional) ----
    def reserve_amount(self, invoice, amount):
        """
        Reserve amount for the invoice (gift card only). Safe to call multiple times.
        """
        self.ensure_one()
        if self.program_id.voucher_type != "gift_card":
            return False
        self._ensure_active()
        amount = max(0.0, amount or 0.0)
        if amount <= 0:
            return False
        if self.balance_amount - (self.reserved_amount or 0.0) < amount:
            # Reserve what we can
            amount = max(0.0, self.balance_amount - (self.reserved_amount or 0.0))
        self.write({
            "reserved_amount": (self.reserved_amount or 0.0) + amount,
            "reserved_invoice_id": invoice.id,
        })
        return True

    def release_reservation(self, invoice):
        self.ensure_one()
        if self.reserved_invoice_id and self.reserved_invoice_id == invoice:
            self.write({"reserved_amount": 0.0, "reserved_invoice_id": False})

    # ---- Apply & Finalize (called by engine) ----
    def consume_on_post(self, amount):
        """
        Finalize consumption: decrease usage/balance on posting.
        """
        self.ensure_one()
        if self.program_id.voucher_type == "coupon":
            self.write({"usage_count": (self.usage_count or 0) + 1})
            # Update state if limit reached
            if self.usage_limit and self.usage_count >= self.usage_limit:
                self.state = "exhausted"
        else:
            amt = max(0.0, amount or 0.0)
            # release reservation and deduct
            reserved = self.reserved_amount or 0.0
            new_balance = (self.balance_amount or 0.0) - amt
            if new_balance < 0:
                new_balance = 0.0
            self.write({
                "balance_amount": new_balance,
                "reserved_amount": max(0.0, reserved - amt),
                "reserved_invoice_id": False if reserved - amt <= 0 else self.reserved_invoice_id.id,
            })
            if new_balance <= 0.0:
                self.state = "exhausted"


# =============================================================================
# Voucher Redemption (Audit Trail)
# =============================================================================
class ClinicBillingVoucherRedemption(models.Model):
    _name = "clinic.billing.voucher.redemption"
    _description = "Clinic Billing Voucher Redemption"
    _order = "id desc"

    voucher_id = fields.Many2one("clinic.billing.voucher", string="Voucher", required=True, index=True)
    program_id = fields.Many2one(related="voucher_id.program_id", string="Program", store=True, readonly=True)
    invoice_id = fields.Many2one("clinic.billing.invoice", string="Clinic Invoice", required=True, index=True, ondelete="cascade")
    line_id = fields.Many2one("clinic.billing.line", string="Billing Line")
    patient_id = fields.Many2one(related="invoice_id.patient_id", string="Patient", store=True, readonly=True)
    company_id = fields.Many2one(related="invoice_id.company_id", string="Company", store=True, readonly=True)

    amount = fields.Monetary(string="Amount Applied", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", store=True, readonly=True)

    code_used = fields.Char(string="Code Used")
    date = fields.Datetime(string="Date", default=lambda s: fields.Datetime.now())
    note = fields.Char(string="Note")


# =============================================================================
# Voucher Engine
# =============================================================================
class ClinicBillingVoucherEngine(models.AbstractModel):
    """
    Voucher Engine
    --------------
    Applies vouchers to Clinic Billing Invoices and Lines.
    - Invoice-scope: create negative 'voucher lines' on clinic.billing.line (tagged).
    - Line-scope: increase discount_amount on matching clinic.billing.line.
    - Gift card: consume up to balance; optional reservation before posting.
    - Idempotent: remove previous voucher lines before re-apply (if invoice not posted).
    """
    _name = "clinic.billing.voucher.engine"
    _description = "Clinic Billing Voucher Engine"

    PARAM_AUTO_APPLY_ON_CONFIRM = "clinic_billing.voucher.auto_apply_on_confirm"   # default True
    PARAM_VOUCHER_PRODUCT_CODE = "clinic_billing.voucher.product_code"            # default CLINIC-VOUCHER-PLACEHOLDER
    PARAM_RESERVE_GIFTCARD = "clinic_billing.voucher.reserve_on_confirm"          # default True

    # -------- Public API --------
    def apply_to_invoice(self, invoice, vouchers=None):
        """
        Apply given vouchers (or invoice.voucher_ids / invoice.voucher_code) to the invoice.
        Returns a dict with totals and details.
        """
        invoice.ensure_one()

        if invoice.move_id and invoice.move_id.state == "posted":
            raise UserError(_("Cannot apply vouchers: accounting invoice has been posted."))

        # Resolve vouchers: M2M + code (Char) → match active voucher
        vouchers = vouchers or invoice.voucher_ids
        if invoice.voucher_code:
            code_v = self._find_active_voucher_by_code(invoice, invoice.voucher_code)
            if code_v and code_v not in vouchers:
                vouchers |= code_v

        # Pre-clean previous voucher-generated discount lines
        self._clear_engine_voucher_lines(invoice)

        if not vouchers:
            return {"applied": False, "total": 0.0, "details": []}

        # Compute & apply each voucher
        applied_total = 0.0
        details = []
        for v in vouchers:
            try:
                v._ensure_active()
            except UserError as e:
                # Skip invalid/expired voucher with a note
                details.append({"voucher": v.code, "applied": 0.0, "reason": str(e)})
                continue

            amount = 0.0
            if v.program_id.voucher_type == "gift_card":
                amount = self._apply_gift_card(invoice, v)
            else:
                amount = self._apply_coupon(invoice, v)

            applied_total += max(0.0, amount)
            details.append({"voucher": v.code, "applied": amount})

            # Reservation (gift card)
            if amount > 0 and v.program_id.voucher_type == "gift_card":
                reserve_flag = self._get_param_bool(self.PARAM_RESERVE_GIFTCARD, default=True)
                if reserve_flag:
                    v.reserve_amount(invoice, amount)

            # Exclusivity handling
            if v.program_id.exclusive:
                break
            if not v.program_id.stackable:
                break

        # Push to accounting move if exists and not posted
        if invoice.move_id and invoice.move_id.state != "posted":
            invoice.action_sync_lines_to_account_move()

        # Try update invoice summary field (if any)
        try:
            current = invoice.read(["discount_total"])[0].get("discount_total") or 0.0
            invoice.write({"discount_total": current + applied_total})
        except Exception:
            pass

        return {"applied": True, "total": applied_total, "details": details}

    def finalize_on_post(self, invoice):
        """
        After the accounting invoice is posted, create redemption logs and actually
        consume voucher usage/balance.
        """
        invoice.ensure_one()
        Redem = self.env["clinic.billing.voucher.redemption"]

        # Voucher lines (engine-generated): log by line & voucher
        for bl in invoice.line_ids.filtered(lambda l: l.is_voucher_line and l.voucher_id):
            amount = abs(bl.total_incl_tax or bl.subtotal_excl_tax or 0.0)
            if amount <= 0:
                continue
            v = bl.voucher_id
            Redem.create({
                "voucher_id": v.id,
                "invoice_id": invoice.id,
                "line_id": bl.id,
                "amount": amount,
                "code_used": v.code,
                "note": "Voucher applied on posting.",
            })
            v.consume_on_post(amount)

        # For coupon line-scope (which increased discount_amount on normal lines),
        # we record redemptions per voucher with amount estimation per line.
        for bl in invoice.line_ids.filtered(lambda l: not l.is_voucher_line and l.voucher_id):
            amount = float(bl.discount_amount or 0.0)
            if amount <= 0:
                continue
            v = bl.voucher_id
            Redem.create({
                "voucher_id": v.id,
                "invoice_id": invoice.id,
                "line_id": bl.id,
                "amount": amount,
                "code_used": v.code,
                "note": "Voucher (line scope) realized on posting.",
            })
            v.consume_on_post(amount)

    # -------- Internals --------
    def _apply_coupon(self, invoice, voucher):
        """
        Apply coupon voucher (percent/fixed) per program scope.
        Returns positive amount applied (absolute value).
        """
        prog = voucher.program_id
        if prog.scope == "invoice":
            amt = self._compute_coupon_amount_for_invoice(invoice, prog)
            if amt <= 0:
                return 0.0
            # Create negative voucher line
            product = self._ensure_voucher_product(invoice.company_id)
            income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
            if not income_account:
                income_account = self._fallback_income_account(invoice.company_id)

            vals = {
                "invoice_id": invoice.id,
                "sequence": 8500,
                "name": "%s - %s" % (_("Voucher"), voucher.code),
                "product_id": product.id,
                "product_uom_id": product.uom_id.id if product.uom_id else False,
                "line_type": "service",
                "quantity": 1.0,
                "unit_price": -amt,  # negative line
                "discount_percent": 0.0,
                "discount_amount": 0.0,
                "tax_ids": [(6, 0, [])],  # typically not taxed
                "analytic_account_id": False,
                "analytic_tag_ids": [(6, 0, [])],
                # Engine markers:
                "is_voucher_line": True,
                "voucher_id": voucher.id,
            }
            self.env["clinic.billing.line"].create(vals)
            return amt

        # scope == "line" : augment discount_amount on eligible lines
        total = 0.0
        for bl in invoice.line_ids:
            if not prog.is_applicable_to_line(invoice, bl):
                continue
            # Compute per-line amount
            base = (bl.subtotal_excl_tax or 0.0) if prog.base_type == "subtotal_excl_tax" else (bl.total_incl_tax or 0.0)
            if prog.method == "percent":
                fixed = base * (prog.percent or 0.0) / 100.0
            else:
                fixed = prog.amount or 0.0
            if prog.max_discount_per_line:
                fixed = min(fixed, prog.max_discount_per_line)
            # Do not exceed base minus existing discount
            fixed = min(fixed, max(0.0, base - (bl.discount_amount or 0.0)))

            if fixed <= 0:
                continue
            bl.write({
                "discount_amount": (bl.discount_amount or 0.0) + fixed,
                "voucher_id": voucher.id,  # mark for redemption at posting
            })
            total += fixed

            if prog.exclusive:
                break
            if not prog.stackable:
                break

        # Cap invoice total if needed
        if prog.max_discount_per_invoice and total > prog.max_discount_per_invoice:
            # Reduce by adjusting last affected line
            overflow = total - prog.max_discount_per_invoice
            for bl in reversed(invoice.line_ids):
                if bl.voucher_id == voucher:
                    new_disc = max(0.0, (bl.discount_amount or 0.0) - overflow)
                    overflow -= (bl.discount_amount or 0.0) - new_disc
                    bl.discount_amount = new_disc
                    if overflow <= 0:
                        break
            total = prog.max_discount_per_invoice

        return total

    def _apply_gift_card(self, invoice, voucher):
        """
        Apply gift card as a negative invoice line up to available balance and program caps.
        """
        prog = voucher.program_id
        # Determine how much we can apply
        base = prog._base_value(invoice) or 0.0
        if prog.max_discount_per_invoice:
            max_for_invoice = min(base, prog.max_discount_per_invoice)
        else:
            max_for_invoice = base

        available = voucher.balance_amount - (voucher.reserved_amount or 0.0)
        apply_amt = max(0.0, min(max_for_invoice, available))
        if apply_amt <= 0:
            return 0.0

        # Create negative voucher line
        product = self._ensure_voucher_product(invoice.company_id)
        income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        if not income_account:
            income_account = self._fallback_income_account(invoice.company_id)

        vals = {
            "invoice_id": invoice.id,
            "sequence": 8400,
            "name": "%s - %s" % (_("Gift Card"), voucher.code),
            "product_id": product.id,
            "product_uom_id": product.uom_id.id if product.uom_id else False,
            "line_type": "service",
            "quantity": 1.0,
            "unit_price": -apply_amt,  # negative
            "discount_percent": 0.0,
            "discount_amount": 0.0,
            "tax_ids": [(6, 0, [])],
            "analytic_account_id": False,
            "analytic_tag_ids": [(6, 0, [])],
            "is_voucher_line": True,
            "voucher_id": voucher.id,
        }
        self.env["clinic.billing.line"].create(vals)
        return apply_amt

    def _compute_coupon_amount_for_invoice(self, invoice, prog):
        base = prog._base_value(invoice) or 0.0
        if base <= 0:
            return 0.0
        if prog.method == "percent":
            amount = (prog.percent or 0.0) * base / 100.0
        else:
            amount = prog.amount or 0.0
        if prog.max_discount_per_invoice:
            amount = min(amount, prog.max_discount_per_invoice)
        amount = max(0.0, min(amount, base))
        return amount

    def _clear_engine_voucher_lines(self, invoice):
        """Remove prior voucher-generated lines if move is not posted."""
        engine_lines = invoice.line_ids.filtered(lambda l: l.is_voucher_line)
        if engine_lines:
            if invoice.move_id and invoice.move_id.state == "posted":
                raise UserError(_("Cannot re-apply vouchers because accounting invoice is already posted."))
            engine_lines.unlink()

    # -------- Utilities --------
    def _ensure_voucher_product(self, company):
        code = self._get_param(self.PARAM_VOUCHER_PRODUCT_CODE, default="CLINIC-VOUCHER-PLACEHOLDER")
        Product = self.env["product.product"].sudo()
        product = Product.search([
            ("default_code", "=", code),
            ("company_id", "in", [False, company.id])
        ], limit=1)
        if product:
            return product
        tmpl_vals = {
            "name": "Clinic Voucher (Auto)",
            "type": "service",
            "default_code": code,
            "lst_price": 0.0,
            "company_id": company.id,
        }
        return Product.create(tmpl_vals)

    def _fallback_income_account(self, company):
        Account = self.env["account.account"].sudo().with_company(company)
        acc = Account.search([
            *Account._check_company_domain(company),
            ("account_type", "=", "income"),
        ], limit=1)
        if not acc:
            raise UserError(_("No income account found for company %s. Configure chart of accounts.") % company.display_name)
        return acc

    def _get_param(self, key, default=None):
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param(key)
        return val if val is not None else default

    def _get_param_bool(self, key, default=False):
        v = self._get_param(key, default=str(bool(default)))
        return str(v).lower() in ("1", "true", "yes")

    def _find_active_voucher_by_code(self, invoice, code):
        V = self.env["clinic.billing.voucher"]
        v = V.search([("code", "=", (code or "").strip()), ("company_id", "=", invoice.company_id.id)], limit=1)
        if not v:
            return False
        try:
            v._ensure_active()
        except UserError:
            return False
        return v


# =============================================================================
# Extensions: Clinic Billing Line & Invoice
# =============================================================================
class ClinicBillingLine_VoucherExt(models.Model):
    _inherit = "clinic.billing.line"

    is_voucher_line = fields.Boolean(
        string="Is Voucher Line (Engine)",
        default=False,
        help="True if this line was auto-generated by the Voucher Engine."
    )
    voucher_id = fields.Many2one(
        "clinic.billing.voucher",
        string="Voucher",
        help="Voucher associated with this line or applied to this line discount."
    )


class ClinicBillingInvoice_VoucherExt(models.Model):
    _inherit = "clinic.billing.invoice"

    voucher_ids = fields.Many2many(
        "clinic.billing.voucher",
        "clinic_billing_inv_voucher_rel",
        "invoice_id", "voucher_id",
        string="Vouchers",
        help="Vouchers to be applied on this invoice."
    )

    def action_apply_voucher_codes(self):
        """
        Apply vouchers currently set (voucher_ids) and/or the single voucher_code string.
        """
        Engine = self.env["clinic.billing.voucher.engine"]
        for rec in self:
            Engine.apply_to_invoice(rec)
        return True

    def action_remove_voucher_lines(self):
        """
        Remove previously auto-generated voucher discount lines (if not posted).
        """
        Engine = self.env["clinic.billing.voucher.engine"]
        for rec in self:
            Engine._clear_engine_voucher_lines(rec)
            # Also remove per-line voucher flags (keep discount values as is)
            for bl in rec.line_ids.filtered(lambda l: not l.is_voucher_line and l.voucher_id):
                bl.voucher_id = False
        # If move exists and not posted, resync
        for rec in self:
            if rec.move_id and rec.move_id.state != "posted":
                rec.action_sync_lines_to_account_move()
        return True

    def _on_after_confirm(self):
        """
        Auto-apply vouchers on confirm (configurable).
        """
        super()._on_after_confirm()
        Engine = self.env["clinic.billing.voucher.engine"]
        auto_apply = self.env["ir.config_parameter"].sudo().get_param(
            Engine.PARAM_AUTO_APPLY_ON_CONFIRM, default="True"
        )
        if (auto_apply or "").lower() in ("1", "true", "yes"):
            for rec in self:
                try:
                    Engine.apply_to_invoice(rec)
                except Exception as e:
                    rec.message_post(body=_("Voucher auto-apply failed: %s") % e)

    def _on_after_move_posted(self, move):
        """
        After posting the accounting invoice, finalize voucher redemptions.
        """
        super()._on_after_move_posted(move)
        Engine = self.env["clinic.billing.voucher.engine"]
        for rec in self:
            try:
                Engine.finalize_on_post(rec)
            except Exception as e:
                rec.message_post(body=_("Voucher redemption recording failed: %s") % e)

