# -*- coding: utf-8 -*-
# File: clinic_billing/models/billing_commission.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Commission Rule
# =============================================================================
class ClinicBillingCommissionRule(models.Model):
    """
    Commission Rule
    ---------------
    Declarative commission rules to determine the commission percent applied
    to billing lines, based on doctor/provider, product/category, base amount,
    and effective date window.

    Selection logic (simple, overrideable):
    - Filter rules by company, active, date range, optional doctor/product/category.
    - Filter by min_base_amount <= line_base.
    - Sort by (priority desc, min_base_amount desc, specificity score desc).
    - Take the first match; fallback to default percent from config parameter.
    """
    _name = "clinic.billing.commission.rule"
    _description = "Clinic Billing Commission Rule"
    _order = "priority desc, min_base_amount desc, id desc"

    name = fields.Char(string="Rule Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company
    )

    # Targeting
    doctor_partner_id = fields.Many2one(
        "res.partner", string="Doctor", help="Apply only to this doctor (optional)."
    )
    product_id = fields.Many2one(
        "product.product", string="Product", help="Apply only to this product (optional)."
    )
    product_category_id = fields.Many2one(
        "product.category", string="Product Category", help="Apply only to this category (optional)."
    )
    line_type = fields.Selection(
        [("service", "Service"), ("product", "Product"), ("package", "Package")],
        string="Line Type",
        help="Apply only to this line type (optional)."
    )

    # Thresholds & period
    min_base_amount = fields.Monetary(
        string="Minimum Base", help="Minimum base amount for the rule to apply.", currency_field="currency_id"
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency", default=lambda self: self.env.company.currency_id
    )
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")

    # Commission
    percent = fields.Float(
        string="Commission (%)", required=True, digits=(16, 4),
        help="Commission percentage applied on base (subtotal excl. tax by default)."
    )
    fix_amount = fields.Monetary(
        string="Fixed Amount", currency_field="currency_id",
        help="Optional fixed amount added to percentage-based commission."
    )

    # Resolution control
    priority = fields.Integer(
        string="Priority", default=10,
        help="Higher priority wins when multiple rules match."
    )

    note = fields.Char(string="Note")

    # Helper to check validity
    def is_applicable(self, line_base, provider, product, category, line_type, date_ref):
        self.ensure_one()
        if not self.active:
            return False
        if self.company_id != self.env.company:
            return False
        if self.date_start and date_ref and date_ref < self.date_start:
            return False
        if self.date_end and date_ref and date_ref > self.date_end:
            return False
        if self.doctor_partner_id and provider and self.doctor_partner_id != provider:
            return False
        if self.product_id and product and self.product_id != product:
            return False
        if self.product_category_id and category and self.product_category_id != category:
            return False
        if self.line_type and line_type and self.line_type != line_type:
            return False
        if self.min_base_amount and (line_base or 0.0) < self.min_base_amount:
            return False
        return True

    def specificity_score(self):
        """Count how specific this rule is to prefer more constrained rules."""
        self.ensure_one()
        return int(bool(self.doctor_partner_id)) + int(bool(self.product_id)) + int(bool(self.product_category_id)) + int(bool(self.line_type))


# =============================================================================
# Commission Line
# =============================================================================
class ClinicBillingCommissionLine(models.Model):
    """
    Commission Line
    ---------------
    One commission item computed from a clinic billing line. It stores
    the base, percent, computed commission amount, and the provider (doctor).
    """
    _name = "clinic.billing.commission.line"
    _description = "Clinic Billing Commission Line"
    _order = "invoice_id, id"

    # Linkage
    invoice_id = fields.Many2one("clinic.billing.invoice", string="Clinic Invoice", required=True, index=True)
    billing_line_id = fields.Many2one("clinic.billing.line", string="Billing Line", index=True)
    move_id = fields.Many2one(related="invoice_id.move_id", string="Accounting Invoice", store=True, readonly=True)

    company_id = fields.Many2one(related="invoice_id.company_id", string="Company", store=True, readonly=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", string="Currency", store=True, readonly=True)

    # Provider
    provider_partner_id = fields.Many2one("res.partner", string="Doctor/Therapist", index=True, required=True)
    provider_user_id = fields.Many2one("res.users", string="Internal User")

    # Basis
    base_amount = fields.Monetary(string="Base Amount", currency_field="currency_id", required=True)
    base_type = fields.Selection(
        [("subtotal_excl_tax", "Subtotal (Excl. Tax)"), ("total_incl_tax", "Total (Incl. Tax)")],
        string="Base Type",
        default="subtotal_excl_tax",
        help="Which base was used to compute the commission."
    )

    percent = fields.Float(string="Percent (%)", digits=(16, 4), required=True)
    fixed_amount = fields.Monetary(string="Fixed Amount", currency_field="currency_id", help="Optional fixed commission.")

    amount_commission = fields.Monetary(
        string="Commission Amount", currency_field="currency_id", compute="_compute_amount", store=True
    )

    # State & settlement
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("settled", "Settled"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True
    )
    settlement_id = fields.Many2one("clinic.billing.commission.settlement", string="Settlement", index=True)

    # Details
    line_type = fields.Selection(
        [("service", "Service"), ("product", "Product"), ("package", "Package")],
        string="Line Type"
    )
    product_id = fields.Many2one("product.product", string="Product")
    product_category_id = fields.Many2one("product.category", string="Product Category")

    note = fields.Char(string="Note")

    # Compute
    @api.depends("base_amount", "percent", "fixed_amount", "currency_id")
    def _compute_amount(self):
        for rec in self:
            base = rec.base_amount or 0.0
            pct = (rec.percent or 0.0) / 100.0
            amt = base * pct + (rec.fixed_amount or 0.0)
            rec.amount_commission = max(amt, 0.0)

    # Constraints
    @api.constrains("percent", "base_amount")
    def _check_values(self):
        for rec in self:
            if rec.percent < 0 or rec.percent > 1000:
                raise ValidationError(_("Percent is out of reasonable bounds."))
            if rec.base_amount < 0:
                raise ValidationError(_("Base amount cannot be negative."))


# =============================================================================
# Commission Settlement (Header)
# =============================================================================
class ClinicBillingCommissionSettlement(models.Model):
    """
    Commission Settlement
    ---------------------
    Settlement document to pay out commission lines to a doctor/provider.
    Creates a journal entry for the expense and optionally an account.payment.
    """
    _name = "clinic.billing.commission.settlement"
    _description = "Clinic Billing Commission Settlement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Settlement Number", default="/", copy=False, index=True, tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True, default=lambda self: self.env.company.currency_id)

    provider_partner_id = fields.Many2one("res.partner", string="Doctor/Therapist", required=True, index=True)
    provider_user_id = fields.Many2one("res.users", string="Internal User")

    date = fields.Date(string="Settlement Date", default=lambda self: fields.Date.context_today(self), tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("journaled", "Journaled"), ("paid", "Paid"), ("cancelled", "Cancelled")],
        string="Status", default="draft", tracking=True
    )

    # Lines collected for this settlement
    line_ids = fields.One2many("clinic.billing.commission.line", "settlement_id", string="Commission Lines")
    amount_total = fields.Monetary(string="Total Commission", currency_field="currency_id", compute="_compute_total", store=False)

    # Accounting artifacts
    journal_id = fields.Many2one("account.journal", string="Journal", domain="[('company_id', '=', company_id)]",
                                 help="Journal used for settlement journal entry.")
    expense_account_id = fields.Many2one(
        "account.account",
        string="Expense Account",
        domain="[('account_type', '=', 'expense')]",
        check_company=True,
        help="Commission expense account for the journal entry.",
    )
    payable_account_id = fields.Many2one(
        "account.account",
        string="Payable Account",
        domain="[('account_type', '=', 'liability_payable')]",
        check_company=True,
        help="Partner payable account to credit.",
    )
    move_id = fields.Many2one("account.move", string="Journal Entry", readonly=True, copy=False)
    payment_id = fields.Many2one("account.payment", string="Payment", readonly=True, copy=False)

    note = fields.Char(string="Note")

    @api.depends("line_ids.amount_commission")
    def _compute_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("amount_commission"))

    # Sequence
    def _next_sequence(self):
        return self.env["ir.sequence"].sudo().next_by_code("clinic.billing.commission.settlement") or "/"

    # Lifecycle
    def action_collect_lines(self):
        """
        Collect eligible commission lines for this provider in 'confirmed' state
        without settlement, and attach them to this settlement.
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You can only collect lines in Draft."))
            domain = [
                ("provider_partner_id", "=", rec.provider_partner_id.id),
                ("state", "=", "confirmed"),
                ("settlement_id", "=", False),
                ("company_id", "=", rec.company_id.id),
            ]
            lines = self.env["clinic.billing.commission.line"].search(domain)
            if not lines:
                raise UserError(_("No commission lines to collect."))
            lines.write({"settlement_id": rec.id})
            if rec.name in ("/", False, ""):
                rec.name = rec._next_sequence()
        return True

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.line_ids:
                raise UserError(_("Please collect commission lines first."))
            if rec.name in ("/", False, ""):
                rec.name = rec._next_sequence()
            rec.state = "confirmed"
        return True

    def _resolve_accounts(self):
        Expense = self.expense_account_id
        Payable = self.payable_account_id
        Account = self.env["account.account"].with_company(self.company_id)
        company_domain = Account._check_company_domain(self.company_id)
        if not Expense:
            # Odoo 19 account.account is shared through company_ids.
            Expense = Account.search([
                *company_domain,
                ("account_type", "=", "expense"),
            ], limit=1)
        if not Payable:
            # Prefer the provider's company-dependent payable account, then fall back.
            Payable = self.provider_partner_id.with_company(self.company_id).property_account_payable_id
            if not Payable:
                Payable = Account.search([
                    *company_domain,
                    ("account_type", "=", "liability_payable"),
                ], limit=1)
        if not Expense or not Payable:
            raise UserError(_("Please configure Expense and Payable accounts for commission settlement."))
        return Expense, Payable

    def action_create_journal_entry(self):
        """
        Create a journal entry debiting commission expense and crediting payable to provider.
        """
        for rec in self:
            if rec.state not in ("confirmed", "draft"):
                continue
            if not rec.line_ids:
                raise UserError(_("No commission lines attached."))
            if _is_zero(rec.amount_total, rec.currency_id):
                raise UserError(_("Total commission is zero."))

            Expense, Payable = rec._resolve_accounts()
            journal = rec.journal_id or rec._fallback_general_journal()
            if not journal:
                raise UserError(_("Please set a Journal for the settlement."))

            move_vals = {
                "date": rec.date,
                "journal_id": journal.id,
                "ref": "Commission Settlement %s" % (rec.name or ""),
                "line_ids": [
                    (0, 0, {
                        "name": "Commission Expense",
                        "debit": rec.amount_total,
                        "credit": 0.0,
                        "account_id": Expense.id,
                        "partner_id": False,
                    }),
                    (0, 0, {
                        "name": "Commission Payable to %s" % (rec.provider_partner_id.display_name,),
                        "debit": 0.0,
                        "credit": rec.amount_total,
                        "account_id": Payable.id,
                        "partner_id": rec.provider_partner_id.id,
                    }),
                ],
                "company_id": rec.company_id.id,
                "move_type": "entry",
            }
            move = self.env["account.move"].sudo().create(move_vals)
            move.sudo().action_post()
            rec.move_id = move.id
            rec.state = "journaled"

            # Mark lines as settled and link to this settlement
            rec.line_ids.write({"state": "settled", "settlement_id": rec.id})

        return True

    def _fallback_general_journal(self):
        return self.env["account.journal"].search([
            ("type", "in", ("general", "cash", "bank")),
            ("company_id", "=", self.company_id.id)
        ], limit=1)

    def action_register_payment(self):
        """
        Create an outbound account.payment to pay the provider.
        This is optional, depending on operational practice.
        """
        for rec in self:
            if rec.state != "journaled":
                raise UserError(_("You can only pay a journaled settlement."))
            if not rec.move_id:
                raise UserError(_("No journal entry found."))

            journal = rec.journal_id or rec._fallback_general_journal()
            vals = {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": rec.provider_partner_id.id,
                "amount": rec.amount_total,
                "currency_id": rec.currency_id.id,
                "date": rec.date or fields.Date.context_today(self),
                "memo": "Commission Settlement %s" % (rec.name,),
                "payment_reference": rec.name,
                "journal_id": journal.id,
                "company_id": rec.company_id.id,
            }
            ap = self.env["account.payment"].sudo().create(vals)
            ap.sudo().action_post()
            rec.payment_id = ap.id
            rec.state = "paid"
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state in ("paid",):
                raise UserError(_("Cannot cancel a paid settlement."))
            # If journaled, you may want to reverse the move (manual step recommended)
            rec.state = "cancelled"
        return True


def _is_zero(amount, currency):
    return currency.is_zero(amount) if currency else abs(amount) < 1e-6


# =============================================================================
# Commission Engine (Abstract)
# =============================================================================
class ClinicBillingCommissionEngine(models.AbstractModel):
    """
    Commission Engine
    -----------------
    Encapsulates the computation logic. Other modules can inherit/override.
    """
    _name = "clinic.billing.commission.engine"
    _description = "Clinic Billing Commission Engine"

    # Configuration keys
    PARAM_DEFAULT_PERCENT = "clinic_billing.commission.default_percent"
    PARAM_BASE_TYPE = "clinic_billing.commission.base_type"  # 'subtotal_excl_tax' or 'total_incl_tax'

    @api.model
    def _get_default_percent(self):
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param(self.PARAM_DEFAULT_PERCENT, default="10.0")
        try:
            return float(val)
        except Exception:
            return 10.0

    @api.model
    def _get_base_type(self):
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param(self.PARAM_BASE_TYPE, default="subtotal_excl_tax")
        return base if base in ("subtotal_excl_tax", "total_incl_tax") else "subtotal_excl_tax"

    # ---------- Core API ----------
    def compute_for_billing(self, invoice):
        """
        Compute commission lines for a Clinic Billing Invoice.
        - Remove existing 'draft' commission lines for this invoice (to re-generate).
        - For each clinic.billing.line, choose provider, get base, find rule, create commission line.
        - Mark lines 'confirmed' when accounting invoice is posted; else keep 'draft'.
        """
        if isinstance(invoice, int):
            invoice = self.env["clinic.billing.invoice"].browse(invoice)
        invoice.ensure_one()

        # Clean previous draft lines to avoid duplicates
        draft_lines = self.env["clinic.billing.commission.line"].search([
            ("invoice_id", "=", invoice.id),
            ("state", "in", ("draft",))
        ])
        if draft_lines:
            draft_lines.unlink()

        base_type = self._get_base_type()
        Rule = self.env["clinic.billing.commission.rule"]

        total_commission = 0.0

        # Iterate clinic lines (if not present, fallback to account.move lines is possible, but we keep clinic lines here)
        for bl in invoice.line_ids:
            provider = bl.provider_partner_id or invoice.doctor_partner_id
            if not provider:
                # Skip commission if no provider is set
                continue

            # Determine base
            if base_type == "total_incl_tax":
                base = bl.total_incl_tax or 0.0
            else:
                base = bl.subtotal_excl_tax or 0.0

            product = bl.product_id
            category = product.categ_id if product else False

            # Find best rule
            rule = self._select_rule(Rule, base, provider, product, category, bl.line_type, invoice.invoice_date or fields.Date.context_today(self))
            percent = rule.percent if rule else self._get_default_percent()
            fix_amt = rule.fix_amount if rule else 0.0

            vals = {
                "invoice_id": invoice.id,
                "billing_line_id": bl.id,
                "provider_partner_id": provider.id,
                "provider_user_id": invoice.doctor_user_id.id if invoice.doctor_user_id else False,
                "base_amount": base,
                "base_type": base_type,
                "percent": percent,
                "fixed_amount": fix_amt,
                "line_type": bl.line_type,
                "product_id": product.id if product else False,
                "product_category_id": category.id if category else False,
                "state": "confirmed" if (invoice.move_id and invoice.move_id.state == "posted") else "draft",
                "note": rule.name if rule else "Default commission",
            }
            cl = self.env["clinic.billing.commission.line"].create(vals)
            total_commission += cl.amount_commission

        # Sync total to invoice high-level field (if exists)
        try:
            invoice.write({"commission_amount": total_commission})
        except Exception:
            pass

        return total_commission

    def _select_rule(self, Rule, base, provider, product, category, line_type, date_ref):
        """Pick best matching rule using priority & specificity heuristics."""
        domain = [("active", "=", True), ("company_id", "=", self.env.company.id)]
        rules = Rule.search(domain)
        candidates = []
        for r in rules:
            if r.is_applicable(base, provider, product, category, line_type, date_ref):
                candidates.append(r)
        if not candidates:
            return False
        # Sort: priority desc, min_base desc, specificity desc, id desc
        candidates = sorted(
            candidates,
            key=lambda x: (x.priority, x.min_base_amount or 0.0, x.specificity_score(), x.id),
            reverse=True,
        )
        return candidates[0]


# =============================================================================
# Extension: Add provider on clinic.billing.line (line-level doctor/therapist)
# =============================================================================
class ClinicBillingLine_CommissionExt(models.Model):
    _inherit = "clinic.billing.line"

    provider_partner_id = fields.Many2one(
        "res.partner", string="Provider (Doctor/Therapist)",
        help="If set, this provider will receive commission for this line. "
             "Otherwise, the invoice-level doctor is used."
    )


# =============================================================================
# Extension: Trigger commission on invoice posting
# =============================================================================
class ClinicBillingInvoice_CommissionExt(models.Model):
    _inherit = "clinic.billing.invoice"

    def _on_after_move_posted(self, move):
        """
        After the accounting invoice is posted, compute/confirm commissions.
        """
        super()._on_after_move_posted(move)
        Engine = self.env["clinic.billing.commission.engine"]
        for rec in self:
            try:
                Engine.compute_for_billing(rec)
            except Exception as e:
                # Do not break posting flow; just log on chatter
                rec.message_post(body=_("Commission computation failed: %s") % e)

    def action_compute_commission_now(self):
        """
        Manual action to compute commissions (e.g., after adjusting lines/rules).
        """
        Engine = self.env["clinic.billing.commission.engine"]
        for rec in self:
            Engine.compute_for_billing(rec)
        return True

