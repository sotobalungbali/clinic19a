# -*- coding: utf-8 -*-
# File: clinic_billing/models/patient_hook.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ============================================================================
# Patient (res.partner) — Billing Hooks & Defaults
# ============================================================================
class ResPartnerClinicBilling(models.Model):
    """
    Extend res.partner (Patient) with billing-related defaults, policies, and KPIs.
    This avoids hard-dependency on clinic_patient while still providing
    patient-level configuration for the Clinic Billing module.
    """
    _inherit = "res.partner"

    # -----------------------------
    # Billing policy & credit
    # -----------------------------
    billing_policy = fields.Selection(
        [
            ("pay_now", "Pay Now"),
            ("allow_credit", "Allow Credit"),
            ("membership_only", "Membership Only"),
            ("prepaid_only", "Prepaid/Voucher Only"),
        ],
        string="Billing Policy",
        help="Defines how this patient is allowed to pay and whether credit is allowed."
    )
    # Odoo 19 contract: ``res.partner.credit_limit`` is owned by ``account``.
    # It is a company-dependent Float stored as JSONB.  ClinicOne must not
    # redeclare it as Monetary/non-company-dependent because doing so corrupts
    # the shared res_partner schema and breaks future module upgrades.
    #
    # Billing workflows below intentionally continue to read ``partner.credit_limit``
    # so the functional credit-control feature is preserved while ownership stays
    # with Odoo's accounting model.
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        default=lambda self: self.env.company.currency_id,
        readonly=True
    )

    is_billing_blocked = fields.Boolean(
        string="Blocked for Billing",
        help="If enabled, new billing confirmations will be blocked (policy controlled by settings)."
    )
    billing_block_reason = fields.Char(string="Block Reason")

    default_payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Default Payment Terms",
        help="Default payment terms applied to clinic billing invoices for this patient."
    )

    # -----------------------------
    # Insurance defaults (hints)
    # -----------------------------
    insurer_partner_id = fields.Many2one(
        "res.partner",
        string="Default Insurer",
        help="Default insurance company for new claims/invoices."
    )
    insurance_policy_number = fields.Char(
        string="Default Policy Number",
        help="Default insurance policy number suggested to billing."
    )
    insurance_coverage_percent = fields.Float(
        string="Default Coverage (%)",
        help="Default insurance coverage percent for new claims/invoices."
    )
    insurance_copay_percent = fields.Float(
        string="Default Co-pay (%)",
        help="Default patient co-pay percent for new claims/invoices."
    )

    # -----------------------------
    # Membership / Wallet hints
    # -----------------------------
    membership_reference = fields.Char(
        string="Membership Reference",
        help="External membership wallet reference/code (soft dependency)."
    )
    membership_level_key = fields.Char(
        string="Membership Level Key",
        help="Optional level key to match discount/privilege rules."
    )
    membership_wallet_balance = fields.Monetary(
        string="Wallet Balance (Soft)",
        currency_field="company_currency_id",
        compute="_compute_membership_wallet_balance",
        help="Membership wallet balance (soft-read; requires membership module)."
    )

    # -----------------------------
    # Voucher preferences
    # -----------------------------
    preferred_voucher_id = fields.Many2one(
        "clinic.billing.voucher",
        string="Preferred Voucher",
        help="Preferred voucher to suggest on invoice (if active)."
    )

    # -----------------------------
    # Receivables KPIs (company currency)
    # -----------------------------
    outstanding_amount = fields.Monetary(
        string="Outstanding Receivable",
        currency_field="company_currency_id",
        compute="_compute_ar_metrics",
        help="Estimated outstanding receivable in company currency (absolute)."
    )
    last_invoice_date = fields.Date(
        string="Last Invoice Date",
        compute="_compute_ar_metrics"
    )
    last_payment_date = fields.Date(
        string="Last Payment Date",
        compute="_compute_ar_metrics"
    )

    # -----------------------------
    # VALIDATIONS
    # -----------------------------
    @api.constrains("insurance_coverage_percent", "insurance_copay_percent")
    def _check_insurance_percentages(self):
        for rec in self:
            if rec.insurance_coverage_percent and (rec.insurance_coverage_percent < 0 or rec.insurance_coverage_percent > 100):
                raise ValidationError(_("Default Coverage (%) must be between 0 and 100."))
            if rec.insurance_copay_percent and (rec.insurance_copay_percent < 0 or rec.insurance_copay_percent > 100):
                raise ValidationError(_("Default Co-pay (%) must be between 0 and 100."))

    @api.onchange("is_billing_blocked")
    def _onchange_is_billing_blocked(self):
        for rec in self:
            if rec.is_billing_blocked and rec.billing_policy == "allow_credit" and not rec.billing_block_reason:
                rec.billing_block_reason = "Temporarily blocked; review outstanding balance or profile."

    # -----------------------------
    # COMPUTES
    # -----------------------------
    def _safe_company_currency(self):
        return self.env.company.currency_id

    def _compute_membership_wallet_balance(self):
        """
        Soft query balance from clinic.wallet (if module available).
        """
        WalletModel = "clinic.wallet"
        for rec in self:
            balance = 0.0
            if WalletModel in self.env:
                Wallet = self.env[WalletModel].sudo()
                domain = [("state", "=", "open"), ("partner_id", "=", rec.id)]
                if rec.membership_reference:
                    wallet = Wallet.search([("name", "=", rec.membership_reference)] + domain, limit=1) \
                             or Wallet.search([("name", "=", rec.membership_reference)] + domain, limit=1)
                else:
                    wallet = Wallet.search(domain, limit=1)
                try:
                    balance = float(wallet.balance or 0.0) if wallet else 0.0
                except Exception:
                    balance = 0.0
            rec.membership_wallet_balance = balance

    def _compute_ar_metrics(self):
        """
        Compute outstanding receivable and last invoice/payment dates.
        Uses account.move (customer invoices) and account.payment (inbound; optional).
        """
        Move = self.env["account.move"].sudo()
        Payment = self.env["account.payment"].sudo()
        for rec in self:
            if not rec.id:
                rec.outstanding_amount = 0.0
                rec.last_invoice_date = False
                rec.last_payment_date = False
                continue
            # Posted customer invoices/credit notes with residual
            moves = Move.search([
                ("partner_id", "=", rec.id),
                ("company_id", "=", rec.company_id.id if rec.company_id else self.env.company.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "in", ("in_process", "paid")),
                ("payment_state", "in", ("not_paid", "partial")),
            ])
            # Use amount_residual_signed (company currency) absolute sum
            total_out = 0.0
            for m in moves:
                try:
                    # amount_residual_signed may be negative for credit notes; take absolute
                    total_out += abs(float(m.amount_residual_signed or 0.0))
                except Exception:
                    # fallback if not present
                    total_out += abs(float(m.amount_residual or 0.0))
            rec.outstanding_amount = total_out

            # Last invoice date
            last_inv = Move.search([
                ("partner_id", "=", rec.id),
                ("company_id", "=", rec.company_id.id if rec.company_id else self.env.company.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "in", ("in_process", "paid")),
            ], order="invoice_date desc, id desc", limit=1)
            rec.last_invoice_date = last_inv.invoice_date if last_inv else False

            # Last inbound payment date (optional)
            pay = Payment.search([
                ("partner_id", "=", rec.id),
                ("company_id", "=", rec.company_id.id if rec.company_id else self.env.company.id),
                ("payment_type", "=", "inbound"),
                ("state", "in", ("in_process", "paid")),
            ], order="date desc, id desc", limit=1)
            rec.last_payment_date = pay.date if pay else False

    # -----------------------------
    # ACTIONS / NAVIGATION
    # -----------------------------
    def action_open_patient_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "=", self.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "in", ("in_process", "paid")),
            ],
            "context": {"search_default_unpaid": 1},
        }

    def action_open_patient_billing(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Billing"),
            "res_model": "clinic.billing.invoice",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_open_patient_vouchers(self):
        self.ensure_one()
        if "clinic.billing.voucher" not in self.env:
            raise UserError(_("Voucher model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Vouchers"),
            "res_model": "clinic.billing.voucher",
            "view_mode": "list,form",
            "domain": ["|", ("owner_partner_id", "=", self.id), ("company_id", "=", self.env.company.id)],
            "context": {"default_owner_partner_id": self.id},
        }

    def action_open_patient_wallet(self):
        self.ensure_one()
        Model = "clinic.wallet"
        if Model not in self.env:
            raise UserError(_("Membership Wallet model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Wallet"),
            "res_model": Model,
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_open_patient_claims(self):
        self.ensure_one()
        Model = "clinic.insurance.claim"
        if Model not in self.env:
            raise UserError(_("Insurance Claim model is not available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Claims"),
            "res_model": Model,
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {},
        }

    # -----------------------------
    # UTILITIES
    # -----------------------------
    def get_billing_defaults(self):
        """
        Return a dict of suggested defaults to be used by Clinic Billing Invoice:
        - insurance defaults
        - membership reference/level
        - default payment terms
        - preferred voucher (code)
        """
        self.ensure_one()
        d = {
            "insurer_partner_id": self.insurer_partner_id.id or False,
            "insurance_policy_number": self.insurance_policy_number or "",
            "insurance_coverage_percent": self.insurance_coverage_percent or 0.0,
            "insurance_copay_percent": self.insurance_copay_percent or 0.0,
            "membership_reference": self.membership_reference or "",
            "membership_level_key": self.membership_level_key or "",
            "payment_term_id": self.default_payment_term_id.id or False,
            "voucher_code": self.preferred_voucher_id.code if self.preferred_voucher_id else "",
        }
        return d


# ============================================================================
# Clinic Billing Invoice — Patient Bridge
# ============================================================================
class ClinicBillingInvoice_PatientBridge(models.Model):
    """
    Bridge methods that copy patient defaults to billing invoice and enforce
    patient-level credit/block policy at confirmation time.
    """
    _inherit = "clinic.billing.invoice"

    # Mirror fields on invoice (if not already defined in the base model)
    patient_outstanding_amount = fields.Monetary(
        string="Patient Outstanding",
        currency_field="currency_id",
        compute="_compute_patient_kpis",
        help="Snapshot of patient's outstanding receivable when editing this invoice."
    )
    patient_last_payment_date = fields.Date(
        string="Patient Last Payment",
        compute="_compute_patient_kpis"
    )

    @api.depends("patient_id")
    def _compute_patient_kpis(self):
        for rec in self:
            amt = 0.0
            last_pay = False
            if rec.patient_id:
                try:
                    # res.partner fields added above
                    company_cur = rec.company_id.currency_id
                    partner_cur = rec.patient_id.company_currency_id or company_cur
                    # Convert from partner company currency to this invoice currency if different
                    partner_out = float(rec.patient_id.outstanding_amount or 0.0)
                    if partner_cur and rec.currency_id and partner_cur != rec.currency_id:
                        amt = partner_cur._convert(partner_out, rec.currency_id, rec.company_id, rec.invoice_date or fields.Date.context_today(self))
                    else:
                        amt = partner_out if (rec.currency_id == partner_cur or not partner_cur) else partner_out
                    last_pay = rec.patient_id.last_payment_date
                except Exception:
                    amt = 0.0
                    last_pay = False
            rec.patient_outstanding_amount = amt
            rec.patient_last_payment_date = last_pay

    # ------------------------------------------------------
    # Defaulting from Patient
    # ------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient_id_apply_defaults(self):
        for rec in self:
            if not rec.patient_id:
                continue
            defaults = rec.patient_id.get_billing_defaults()
            # Apply insurance & membership hints
            if not rec.insurer_partner_id and defaults.get("insurer_partner_id"):
                rec.insurer_partner_id = defaults["insurer_partner_id"]
            if not rec.insurance_policy_number and defaults.get("insurance_policy_number"):
                rec.insurance_policy_number = defaults["insurance_policy_number"]
            if not rec.insurance_coverage_percent and defaults.get("insurance_coverage_percent"):
                rec.insurance_coverage_percent = defaults["insurance_coverage_percent"]
            if not rec.insurance_copay_percent and defaults.get("insurance_copay_percent"):
                rec.insurance_copay_percent = defaults["insurance_copay_percent"]
            if not rec.membership_reference and defaults.get("membership_reference"):
                rec.membership_reference = defaults["membership_reference"]
            if not getattr(rec, "membership_level_key", False) and defaults.get("membership_level_key"):
                try:
                    rec.membership_level_key = defaults["membership_level_key"]
                except Exception:
                    pass
            # Payment term
            if not rec.payment_term_id and defaults.get("payment_term_id"):
                rec.payment_term_id = defaults["payment_term_id"]
            # Voucher code hint (do not overwrite if already set)
            code = defaults.get("voucher_code")
            if code:
                try:
                    if not rec.voucher_code:
                        rec.voucher_code = code
                except Exception:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        """
        On create, apply patient defaults if fields are empty in incoming vals.
        """
        for vals in vals_list:
            pid = vals.get("patient_id")
            if pid:
                partner = self.env["res.partner"].browse(pid)
                defaults = partner.get_billing_defaults()
                # Only set if not provided
                for key_src, key_dst in [
                    ("insurer_partner_id", "insurer_partner_id"),
                    ("insurance_policy_number", "insurance_policy_number"),
                    ("insurance_coverage_percent", "insurance_coverage_percent"),
                    ("insurance_copay_percent", "insurance_copay_percent"),
                    ("membership_reference", "membership_reference"),
                    ("payment_term_id", "payment_term_id"),
                ]:
                    if key_dst not in vals and defaults.get(key_src):
                        vals[key_dst] = defaults[key_src]
                # Voucher hint (do not force)
                if "voucher_code" not in vals and defaults.get("voucher_code"):
                    vals["voucher_code"] = defaults["voucher_code"]
        recs = super().create(vals_list)
        return recs

    # ------------------------------------------------------
    # Credit & Block Policy Enforcement
    # ------------------------------------------------------
    def _get_param_bool(self, key, default=False):
        v = self.env["ir.config_parameter"].sudo().get_param(key, default=str(bool(default)))
        return str(v).lower() in ("1", "true", "yes")

    def _get_param_int(self, key, default=0):
        v = self.env["ir.config_parameter"].sudo().get_param(key, default=str(int(default)))
        try:
            return int(v)
        except Exception:
            return default

    def _check_patient_credit_policy(self):
        """
        Enforce patient-level billing block & credit limit if settings require it.
        """
        enforce_block = self._get_param_bool("clinic_billing.enforce_patient_block", True)
        enforce_credit = self._get_param_bool("clinic_billing.enforce_credit_limit", False)
        overdue_days_limit = self._get_param_int("clinic_billing.ar_overdue_days_limit", 0)

        for rec in self:
            p = rec.patient_id
            if not p:
                continue

            # Block flag
            if enforce_block and p.is_billing_blocked:
                reason = p.billing_block_reason or _("Patient is blocked for billing.")
                raise UserError(_("Billing blocked for patient '%s': %s") % (p.display_name, reason))

            # Credit limit
            if enforce_credit and (p.billing_policy == "allow_credit" or not p.billing_policy):
                # Compare outstanding + this invoice total against limit
                limit = float(p.credit_limit or 0.0)
                if limit > 0:
                    # Convert patient outstanding to this invoice currency if needed
                    outstanding = rec.patient_outstanding_amount or 0.0
                    # Add this invoice amount_total (pre-post, approximate)
                    current_total = float(rec.amount_total or 0.0)
                    if (outstanding + current_total) > limit + 1e-6:
                        raise UserError(
                            _("Credit limit exceeded for '%(p)s'. Limit: %(lim).2f, "
                              "Outstanding: %(out).2f, Current: %(cur).2f") % {
                                "p": p.display_name,
                                "lim": limit,
                                "out": outstanding,
                                "cur": current_total,
                            }
                        )

            # Optional: simple overdue guard (soft check via last payment date)
            if overdue_days_limit and p.last_payment_date:
                try:
                    from datetime import date
                    delta = (date.today() - p.last_payment_date).days
                    if delta > overdue_days_limit and enforce_credit:
                        raise UserError(
                            _("Patient '%s' is overdue by %d days. Please review before confirming.")
                            % (p.display_name, delta)
                        )
                except Exception:
                    # Ignore parse errors
                    pass

    def action_confirm(self):
        """
        Override to enforce patient block & credit policy before confirm.
        """
        self._check_patient_credit_policy()
        return super().action_confirm()

    # ------------------------------------------------------
    # Smart buttons / helpers
    # ------------------------------------------------------
    def action_open_patient_profile(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.patient_id.id,
            "target": "current",
        }



