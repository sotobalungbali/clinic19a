# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_discount.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Discount Rule
# =============================================================================
class ClinicBillingDiscountRule(models.Model):
    """
    Discount Rule
    -------------
    Declarative discount rules for Clinic Billing:
    - Scope: line-level or invoice-level (global).
    - Method: percent or fixed amount (invoice-level fixed_total supported).
    - Conditions: doctor, product, category, line type, partner tags, date, min qty, min subtotal,
                  optional discount code requirement, membership hints (soft), etc.
    - Resolution: priority, stackable/exclusive, amount caps.

    Usage limits tracked via clinic.billing.discount.redemption.
    """
    _name = "clinic.billing.discount.rule"
    _description = "Clinic Billing Discount Rule"
    _order = "priority desc, min_subtotal desc, min_qty desc, id desc"

    name = fields.Char(string="Rule Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, default=lambda s: s.env.company.currency_id)

    # Scope & Method
    scope = fields.Selection(
        [("line", "Line"), ("invoice", "Invoice")],
        string="Scope", required=True, default="line",
        help="Whether this rule applies to individual lines or to the invoice as a whole."
    )
    method = fields.Selection(
        [("percent", "Percent"), ("fixed", "Fixed Amount"), ("fixed_total", "Fixed Amount (Invoice Total)")],
        string="Method", required=True, default="percent",
        help="For invoice scope, 'fixed_total' applies as a single negative discount line."
    )
    percent = fields.Float(string="Percent (%)", digits=(16, 4), help="Percent discount (0-100+).")
    amount = fields.Monetary(string="Fixed Amount", currency_field="currency_id", help="Fixed amount discount.")
    base_type = fields.Selection(
        [("subtotal_excl_tax", "Subtotal (Excl. Tax)"), ("total_incl_tax", "Total (Incl. Tax)")],
        string="Base Type", default="subtotal_excl_tax",
        help="Base used to compute the percent discount."
    )

    # Conditions
    doctor_partner_id = fields.Many2one("res.partner", string="Doctor", help="Only apply if invoice doctor matches (optional).")
    product_id = fields.Many2one("product.product", string="Product", help="Only apply for this product (line scope).")
    product_category_id = fields.Many2one("product.category", string="Product Category", help="Only apply for this category (line scope).")
    line_type = fields.Selection(
        [("service", "Service"), ("product", "Product"), ("package", "Package")],
        string="Line Type", help="Only apply for this line type (optional, line scope)."
    )
    partner_category_ids = fields.Many2many("res.partner.category", string="Customer Tags",
                                            help="Only apply if patient has at least one of these tags.")
    branch_id = fields.Many2one("stock.warehouse", string="Clinic Branch", help="Only apply at this branch (optional).")

    # Membership / Hints (soft)
    requires_membership = fields.Boolean(string="Requires Membership", help="Apply only if patient has any membership (soft check).")
    membership_level_key = fields.Char(string="Membership Level Key", help="Optional key to match patient's membership level (soft).")

    # Thresholds & Window
    min_qty = fields.Float(string="Min Quantity", help="Minimum line quantity for line scope (if set).")
    min_subtotal = fields.Monetary(string="Min Subtotal", currency_field="currency_id",
                                   help="Minimum line/invoice subtotal (before tax) to activate this rule.")
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")

    # Stacking & Exclusivity
    stackable = fields.Boolean(string="Stackable", default=True, help="If disabled, this rule is exclusive within its scope.")
    exclusive = fields.Boolean(string="Exclusive (Stop Further Rules)", default=False,
                               help="If enabled and this rule applies, stop evaluating other rules in the same scope.")
    max_discount_per_line = fields.Monetary(string="Max Discount/Line", currency_field="currency_id")
    max_discount_per_invoice = fields.Monetary(string="Max Discount/Invoice", currency_field="currency_id")

    # Code & Usage
    requires_code = fields.Boolean(string="Requires Code", help="Only apply if a matching code is provided on invoice or line.")
    code = fields.Char(string="Discount Code", help="Optional code to trigger this rule.")
    usage_limit_global = fields.Integer(string="Global Usage Limit", help="Max total uses across all patients (0 = unlimited).")
    usage_limit_per_patient = fields.Integer(string="Per-Patient Usage Limit", help="Max uses per patient (0 = unlimited).")

    priority = fields.Integer(string="Priority", default=10, help="Higher priority wins when multiple rules match.")
    note = fields.Char(string="Note")

    # ---- Helper checks -------------------------------------------------------
    def _today(self):
        return fields.Date.context_today(self)

    def _partner_has_required_tags(self, partner):
        if not self.partner_category_ids:
            return True
        if not partner:
            return False
        return bool(self.partner_category_ids & partner.category_id)

    def _within_dates(self, date_ref):
        if self.date_start and date_ref and date_ref < self.date_start:
            return False
        if self.date_end and date_ref and date_ref > self.date_end:
            return False
        return True

    def _check_membership_soft(self, partner):
        """Soft check for membership presence/level without hard dependency."""
        if not self.requires_membership and not self.membership_level_key:
            return True
        if not partner:
            return False
        # Try reading membership context from related models if available
        # - clinic.wallet (balance>0) or partner field hints in other modules
        # Keep it soft: if not found, return False when requires_membership True
        has_any = False
        level_ok = True
        try:
            # Example soft probe via a hypothetical relation
            wallet_model = self.env["clinic.wallet"] if "clinic.wallet" in self.env else False
            if wallet_model:
                wallets = wallet_model.search([("partner_id", "=", partner.id), ("state", "=", "open")], limit=1)
                has_any = bool(wallets)
        except Exception:
            has_any = False
        if self.requires_membership and not has_any:
            return False

        if self.membership_level_key:
            # Try find a key on partner or wallet
            level_ok = False
            if hasattr(partner, "membership_level_key") and partner.membership_level_key:
                level_ok = (partner.membership_level_key == self.membership_level_key)
            elif has_any:
                # assume wallet record has a 'level_key' field
                try:
                    if "membership_tier_id" in wallets._fields:
                        level_ok = any(
                            (wallet.membership_tier_id.display_name or "") == self.membership_level_key
                            or str(wallet.membership_tier_id.id) == self.membership_level_key
                            for wallet in wallets
                        )
                except Exception:
                    level_ok = False
        return level_ok

    def _check_usage_limits(self, patient):
        """Check global & per-patient usage limits using redemption records."""
        Redemption = self.env["clinic.billing.discount.redemption"]
        if self.usage_limit_global:
            total = Redemption.search_count([("rule_id", "=", self.id)])
            if total >= self.usage_limit_global:
                return False
        if self.usage_limit_per_patient and patient:
            used = Redemption.search_count([("rule_id", "=", self.id), ("patient_id", "=", patient.id)])
            if used >= self.usage_limit_per_patient:
                return False
        return True

    # ---- Applicability -------------------------------------------------------
    def is_applicable_to_invoice(self, invoice):
        self.ensure_one()
        if not self.active:
            return False
        if self.scope != "invoice":
            return False
        date_ref = invoice.invoice_date or self._today()
        if not self._within_dates(date_ref):
            return False
        if self.company_id != invoice.company_id:
            return False
        if self.doctor_partner_id and self.doctor_partner_id != invoice.doctor_partner_id:
            return False
        if self.branch_id and self.branch_id != invoice.clinic_warehouse_id:
            return False
        if not self._partner_has_required_tags(invoice.patient_id):
            return False
        if not self._check_membership_soft(invoice.patient_id):
            return False
        if self.requires_code:
            # Match against invoice.voucher_code (or discount_code field if provided)
            code_sources = [invoice.voucher_code, getattr(invoice, "discount_code", False)]
            if self.code and self.code not in code_sources:
                return False
        # Threshold
        base = invoice.amount_untaxed if self.base_type == "subtotal_excl_tax" else invoice.amount_total
        if self.min_subtotal and (base or 0.0) < self.min_subtotal:
            return False
        if not self._check_usage_limits(invoice.patient_id):
            return False
        return True

    def is_applicable_to_line(self, invoice, line):
        self.ensure_one()
        if not self.active:
            return False
        if self.scope != "line":
            return False
        date_ref = invoice.invoice_date or self._today()
        if not self._within_dates(date_ref):
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
        if not self._partner_has_required_tags(invoice.patient_id):
            return False
        if not self._check_membership_soft(invoice.patient_id):
            return False
        # Code requirement
        if self.requires_code:
            code_sources = [line.voucher_code, invoice.voucher_code, getattr(invoice, "discount_code", False)]
            if self.code and self.code not in code_sources:
                return False
        # Thresholds
        qty_ok = (not self.min_qty) or (line.quantity or 0.0) >= self.min_qty
        if not qty_ok:
            return False
        base = (line.subtotal_excl_tax or 0.0) if self.base_type == "subtotal_excl_tax" else (line.total_incl_tax or 0.0)
        if self.min_subtotal and base < self.min_subtotal:
            return False
        if not self._check_usage_limits(invoice.patient_id):
            return False
        return True

    # ---- Compute -------------------------------------------------------------
    def compute_discount_amount_for_line(self, invoice, line):
        """Return (percent, fixed_amount) to apply for this line."""
        base = (line.subtotal_excl_tax or 0.0) if self.base_type == "subtotal_excl_tax" else (line.total_incl_tax or 0.0)
        pct = self.percent or 0.0
        fixed = 0.0
        if self.method == "percent":
            fixed = base * (pct / 100.0)
        elif self.method == "fixed":
            fixed = self.amount or 0.0
        # Cap per-line
        if self.max_discount_per_line:
            fixed = min(fixed, self.max_discount_per_line)
        # Amount cannot exceed base
        fixed = min(fixed, base)
        return pct, fixed

    def compute_discount_amount_for_invoice(self, invoice):
        """Return fixed discount amount for invoice scope."""
        base = invoice.amount_untaxed if self.base_type == "subtotal_excl_tax" else invoice.amount_total
        if self.method == "percent":
            val = (self.percent or 0.0) * base / 100.0
        elif self.method in ("fixed", "fixed_total"):
            val = self.amount or 0.0
        else:
            val = 0.0
        if self.max_discount_per_invoice:
            val = min(val, self.max_discount_per_invoice)
        # Non-negative, not exceeding base
        return max(0.0, min(val, base))


# =============================================================================
# Discount Redemption (usage tracking)
# =============================================================================
class ClinicBillingDiscountRedemption(models.Model):
    _name = "clinic.billing.discount.redemption"
    _description = "Clinic Billing Discount Redemption"
    _order = "id desc"

    rule_id = fields.Many2one("clinic.billing.discount.rule", string="Rule", required=True, index=True)
    invoice_id = fields.Many2one("clinic.billing.invoice", string="Clinic Invoice", required=True, index=True, ondelete="cascade")
    patient_id = fields.Many2one("res.partner", string="Patient", required=True, index=True)
    amount = fields.Monetary(string="Redeemed Amount", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", store=True, readonly=True)
    code_used = fields.Char(string="Code Used")
    date = fields.Datetime(string="Date", default=lambda s: fields.Datetime.now())


# =============================================================================
# Discount Engine (Abstract, can be overridden)
# =============================================================================
class ClinicBillingDiscountEngine(models.AbstractModel):
    """
    Discount Engine
    ---------------
    Centralized discount computation & application:
    - Applies line scope rules (stackable/exclusive).
    - Applies invoice scope rules by creating negative discount lines (engine-tagged).
    - Idempotent: re-applies cleanly by clearing previous auto discount lines first.
    - Records redemptions after the accounting invoice is posted.
    """
    _name = "clinic.billing.discount.engine"
    _description = "Clinic Billing Discount Engine"

    # Parameters
    PARAM_AUTO_APPLY_ON_CONFIRM = "clinic_billing.discount.auto_apply_on_confirm"  # default True
    PARAM_INVOICE_DISCOUNT_PRODUCT_CODE = "clinic_billing.discount.product_code"   # default CLINIC-DISCOUNT-PLACEHOLDER

    # ---------- Public API ----------
    def apply_to_invoice(self, invoice):
        """
        Apply discount rules to a clinic billing invoice (draft/confirmed).
        Returns dict with totals.
        """
        invoice.ensure_one()
        Rule = self.env["clinic.billing.discount.rule"]

        # 1) Clear previous engine-generated invoice discount lines
        self._clear_engine_discount_lines(invoice)

        # 2) Evaluate line scope rules & apply to clinic lines
        line_total_discount = self._apply_line_discounts(invoice, Rule)

        # 3) Evaluate invoice scope rules & create negative discount lines
        invoice_total_discount = self._apply_invoice_discounts(invoice, Rule)

        # 4) Re-push to accounting move if exists and not posted
        if invoice.move_id and invoice.move_id.state != "posted":
            invoice.action_sync_lines_to_account_move()

        # 5) Update invoice summary field (if exists)
        try:
            invoice.write({"discount_total": (line_total_discount + invoice_total_discount)})
        except Exception:
            pass

        return {
            "line_discount_total": line_total_discount,
            "invoice_discount_total": invoice_total_discount,
            "discount_total": line_total_discount + invoice_total_discount,
        }

    def record_redemptions(self, invoice):
        """
        Record discount redemptions after posting (to enforce usage limits).
        """
        invoice.ensure_one()
        Redemption = self.env["clinic.billing.discount.redemption"]
        # From line-level: sum by rule from line.applied_discount_rule_ids and actual discounted amount.
        for bl in invoice.line_ids:
            amount = self._effective_line_discount_amount(bl)
            if amount <= 0:
                continue
            for rule in bl.applied_discount_rule_ids:
                Redemption.create({
                    "rule_id": rule.id,
                    "invoice_id": invoice.id,
                    "patient_id": invoice.patient_id.id,
                    "amount": amount,  # total per line (split among rules is not tracked; can be refined)
                    "code_used": bl.voucher_code or invoice.voucher_code or getattr(invoice, "discount_code", False) or "",
                })

        # From invoice-level: engine-generated discount lines carry engine_rule_id
        for bl in invoice.line_ids.filtered(lambda l: l.is_discount_line and l.engine_rule_id):
            amount = abs(bl.total_incl_tax or bl.subtotal_excl_tax or 0.0)
            if amount <= 0:
                continue
            Redemption.create({
                "rule_id": bl.engine_rule_id.id,
                "invoice_id": invoice.id,
                "patient_id": invoice.patient_id.id,
                "amount": amount,
                "code_used": invoice.voucher_code or getattr(invoice, "discount_code", False) or "",
            })

    # ---------- Internals ----------
    def _apply_line_discounts(self, invoice, Rule):
        """Apply line-scope rules to clinic lines and return total discount applied."""
        total = 0.0
        rules = Rule.search([("active", "=", True), ("company_id", "=", invoice.company_id.id), ("scope", "=", "line")])
        # Sort by priority desc as per model _order
        for bl in invoice.line_ids:
            applicable = [r for r in rules if r.is_applicable_to_line(invoice, bl)]
            if not applicable:
                continue
            applied_rules = []
            discount_amount_acc = 0.0
            # Evaluate by priority respecting exclusivity
            for rule in applicable:
                pct, fixed = rule.compute_discount_amount_for_line(invoice, bl)
                if fixed <= 0 and (rule.method != "percent" or rule.percent <= 0):
                    continue
                # Update line's discount fields (stacking adds to discount_amount; percent is informational)
                # We prioritize fixed amount application; percent is captured for traceability.
                new_discount_amount = (bl.discount_amount or 0.0) + fixed
                # Cap: cannot exceed line base
                base = bl.subtotal_excl_tax or 0.0
                if new_discount_amount > base:
                    fixed = max(0.0, base - (bl.discount_amount or 0.0))
                    new_discount_amount = base
                bl.write({
                    "discount_percent": bl.discount_percent or rule.percent or 0.0,  # keep first percent as display
                    "discount_amount": new_discount_amount,
                })
                applied_rules.append(rule.id)
                discount_amount_acc += fixed
                if rule.exclusive:
                    break
                if not rule.stackable:
                    # If not stackable, stop after first application
                    break
            if applied_rules:
                # Track which rules applied
                bl.applied_discount_rule_ids = [(6, 0, list(set((bl.applied_discount_rule_ids.ids or []) + applied_rules)))]
                total += discount_amount_acc
        return total

    def _apply_invoice_discounts(self, invoice, Rule):
        """
        Create discount lines (negative) for invoice-scope rules.
        Returns total amount applied (positive number).
        """
        total = 0.0
        rules = Rule.search([("active", "=", True), ("company_id", "=", invoice.company_id.id), ("scope", "=", "invoice")])
        for rule in rules:
            if not rule.is_applicable_to_invoice(invoice):
                continue
            amount = rule.compute_discount_amount_for_invoice(invoice)
            if amount <= 0:
                continue
            # Create negative clinic.billing.line representing invoice discount
            product = self._ensure_discount_product(invoice.company_id)
            income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
            if not income_account:
                income_account = self._fallback_income_account(invoice.company_id)

            vals = {
                "invoice_id": invoice.id,
                "sequence": 9000,  # push to bottom
                "name": "%s - %s" % (_("Invoice Discount"), rule.name),
                "product_id": product.id,
                "product_uom_id": product.uom_id.id if product.uom_id else False,
                "line_type": "service",
                "quantity": 1.0,
                "unit_price": -amount,  # negative line
                "discount_percent": 0.0,
                "discount_amount": 0.0,
                "tax_ids": [(6, 0, [])],  # typically no taxes for discount line; override as needed
                "analytic_account_id": False,
                "analytic_tag_ids": [(6, 0, [])],
                "insurance_hint": "",
                "membership_hint": "",
                # Engine markers
                "is_discount_line": True,
                "engine_rule_id": rule.id,
            }
            discount_line = self.env["clinic.billing.line"].create(vals)
            # Mark as applied rule on line for traceability
            discount_line.applied_discount_rule_ids = [(6, 0, [rule.id])]
            total += amount
            if rule.exclusive:
                break
            if not rule.stackable:
                break
        return total

    def _clear_engine_discount_lines(self, invoice):
        """Remove previously auto-generated invoice discount lines (is_discount_line=True) on unposted moves."""
        engine_lines = invoice.line_ids.filtered(lambda l: l.is_discount_line)
        if engine_lines:
            # If invoice already has posted move, forbid deleting; instead raise for manual correction
            if invoice.move_id and invoice.move_id.state == "posted":
                raise UserError(_("Cannot re-apply discounts because accounting invoice is already posted."))
            engine_lines.unlink()

    # ---------- Utilities ----------
    def _ensure_discount_product(self, company):
        """Ensure a 'Clinic Discount (Auto)' service product exists for discount lines."""
        code = self._get_param(self.PARAM_INVOICE_DISCOUNT_PRODUCT_CODE, default="CLINIC-DISCOUNT-PLACEHOLDER")
        Product = self.env["product.product"].sudo()
        product = Product.search([
            ("default_code", "=", code),
            ("company_id", "in", [False, company.id])
        ], limit=1)
        if product:
            return product
        tmpl_vals = {
            "name": "Clinic Discount (Auto)",
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

    def _effective_line_discount_amount(self, bl):
        """
        Effective discount amount realized on the line (excl. taxes).
        Since clinic.billing.line already computes price_effective from unit_price/discounts,
        we consider discount_amount as direct monetary reduction baseline.
        """
        return float(bl.discount_amount or 0.0)


# =============================================================================
# Extension: Clinic Billing Line — store applied rules & engine markers
# =============================================================================
class ClinicBillingLine_DiscountExt(models.Model):
    _inherit = "clinic.billing.line"

    applied_discount_rule_ids = fields.Many2many(
        "clinic.billing.discount.rule",
        "clinic_billing_line_discount_rule_rel",
        "line_id", "rule_id",
        string="Applied Discount Rules",
        help="Discount rules that were applied to this line."
    )
    is_discount_line = fields.Boolean(
        string="Is Discount Line (Engine)",
        default=False,
        help="True if this line is an engine-generated invoice discount line."
    )
    engine_rule_id = fields.Many2one(
        "clinic.billing.discount.rule",
        string="Engine Rule",
        help="The invoice-scope rule used to create this discount line."
    )
    original_unit_price = fields.Monetary(
        string="Original Unit Price",
        currency_field="currency_id",
        help="Optional storage of original unit price before discounts (for audit)."
    )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # Store original_unit_price at creation if not set
        for r in recs:
            if r.original_unit_price in (False, 0.0) and r.unit_price:
                r.original_unit_price = r.unit_price
        return recs


# =============================================================================
# Extension: Clinic Billing Invoice — fields, hooks and actions
# =============================================================================
class ClinicBillingInvoice_DiscountExt(models.Model):
    _inherit = "clinic.billing.invoice"

    discount_total = fields.Monetary(
        string="Total Discount",
        currency_field="currency_id",
        help="Total discount applied on this clinic invoice (line + invoice scope)."
    )
    discount_code = fields.Char(
        string="Discount Code",
        help="Invoice-level discount code (in addition to voucher_code)."
    )

    def _on_after_confirm(self):
        """
        After invoice is confirmed, auto-apply discounts (configurable via ICP).
        """
        super()._on_after_confirm()
        Engine = self.env["clinic.billing.discount.engine"]
        auto_apply = self.env["ir.config_parameter"].sudo().get_param(
            Engine.PARAM_AUTO_APPLY_ON_CONFIRM, default="True"
        )
        if (auto_apply or "").lower() in ("1", "true", "yes"):
            for rec in self:
                try:
                    Engine.apply_to_invoice(rec)
                except Exception as e:
                    rec.message_post(body=_("Discount auto-apply failed: %s") % e)

    def _on_after_move_posted(self, move):
        """
        After accounting invoice is posted, record redemption usages.
        """
        super()._on_after_move_posted(move)
        Engine = self.env["clinic.billing.discount.engine"]
        for rec in self:
            try:
                Engine.record_redemptions(rec)
            except Exception as e:
                rec.message_post(body=_("Discount redemption recording failed: %s") % e)

    # Manual action for UI
    def action_compute_discounts_now(self):
        Engine = self.env["clinic.billing.discount.engine"]
        for rec in self:
            Engine.apply_to_invoice(rec)
        return True

