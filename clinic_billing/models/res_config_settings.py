# -*- coding: utf-8 -*-
# File: clinic_billing/models/res_config_settings.py
# License: LGPL-3

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    """
    Clinic Billing Settings
    -----------------------
    Centralized configuration for ClinicOne Billing module.
    Values are stored in ir.config_parameter and consumed by engines:
    - CommissionEngine, DiscountEngine, VoucherEngine, MembershipEngine, Gateway TX
    - Insurance default hints & settlement journal

    Notes:
    - Most fields use `config_parameter` for persistence (global system-wide).
    - Some Many2one fields also persist as IDs via `config_parameter`.
    - On save, we optionally ensure placeholder service products for discount/voucher/membership.
    """
    _inherit = "res.config.settings"

    # ======================================================================
    # COMMISSION
    # ======================================================================
    commission_default_percent = fields.Float(
        string="Commission Default (%)",
        config_parameter="clinic_billing.commission.default_percent",
        help="Default commission percent used when no rule matches. "
             "Consumed by Clinic Billing Commission Engine."
    )
    commission_base_type = fields.Selection(
        [("subtotal_excl_tax", "Subtotal (Excl. Tax)"),
         ("total_incl_tax", "Total (Incl. Tax)")],
        string="Commission Base Type",
        default="subtotal_excl_tax",
        config_parameter="clinic_billing.commission.base_type",
        help="Base amount used to compute the commission when rules do not override."
    )
    # Optional accounting defaults to aid settlements
    commission_expense_account_id = fields.Many2one(
        "account.account",
        string="Commission Expense Account",
        config_parameter="clinic_billing.commission.expense_account_id",
        domain="[('account_type', '=', 'expense')]",
        check_company=True,
        help="Default expense account to debit during commission settlement journal entry."
    )
    commission_payable_account_id = fields.Many2one(
        "account.account",
        string="Commission Payable Account",
        config_parameter="clinic_billing.commission.payable_account_id",
        domain="[('account_type', '=', 'liability_payable')]",
        check_company=True,
        help="Default payable account to credit during commission settlement journal entry."
    )
    commission_settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Commission Settlement Journal",
        config_parameter="clinic_billing.commission.settlement_journal_id",
        domain="[('company_id', '=', company_id)]",
        help="Default journal used to create commission settlement entries."
    )

    # ======================================================================
    # DISCOUNT
    # ======================================================================
    discount_auto_apply_on_confirm = fields.Boolean(
        string="Auto-apply Discounts on Confirm",
        default=True,
        config_parameter="clinic_billing.discount.auto_apply_on_confirm",
        help="If enabled, Discount Engine will auto-apply rules when a clinic invoice is confirmed."
    )
    discount_product_code = fields.Char(
        string="Discount Placeholder Product Code",
        default="CLINIC-DISCOUNT-PLACEHOLDER",
        config_parameter="clinic_billing.discount.product_code",
        help="Default code for a service product used to create auto-generated invoice discount lines."
    )

    # ======================================================================
    # VOUCHER
    # ======================================================================
    voucher_auto_apply_on_confirm = fields.Boolean(
        string="Auto-apply Vouchers on Confirm",
        default=True,
        config_parameter="clinic_billing.voucher.auto_apply_on_confirm",
        help="If enabled, Voucher Engine will auto-apply vouchers set on the invoice upon confirmation."
    )
    voucher_reserve_on_confirm = fields.Boolean(
        string="Reserve Gift Card on Confirm",
        default=True,
        config_parameter="clinic_billing.voucher.reserve_on_confirm",
        help="If enabled, the voucher engine will reserve gift card balance on invoice confirmation."
    )
    voucher_product_code = fields.Char(
        string="Voucher Placeholder Product Code",
        default="CLINIC-VOUCHER-PLACEHOLDER",
        config_parameter="clinic_billing.voucher.product_code",
        help="Default code for a service product used to create voucher (coupon/gift card) discount lines."
    )

    # ======================================================================
    # MEMBERSHIP WALLET
    # ======================================================================
    membership_auto_apply_on_confirm = fields.Boolean(
        string="Auto-apply Membership on Confirm",
        default=False,
        config_parameter="clinic_billing.membership.auto_apply_on_confirm",
        help="If enabled, Membership Engine will try to apply membership wallet deduction automatically."
    )
    membership_reserve_on_confirm = fields.Boolean(
        string="Reserve Membership on Confirm",
        default=True,
        config_parameter="clinic_billing.membership.reserve_on_confirm",
        help="If enabled, the engine will reserve membership wallet amount on invoice confirmation."
    )
    membership_product_code = fields.Char(
        string="Membership Placeholder Product Code",
        default="CLINIC-MEMBERSHIP-DEDUCT",
        config_parameter="clinic_billing.membership.product_code",
        help="Default code for a service product used to create membership wallet deduction lines."
    )

    # ======================================================================
    # INSURANCE (Hints)
    # ======================================================================
    insurance_default_coverage_percent = fields.Float(
        string="Default Insurance Coverage (%)",
        default=0.0,
        config_parameter="clinic_billing.insurance.default_coverage_percent",
        help="Default coverage percent hint for new insurance claims; can be overridden per invoice/claim."
    )
    insurance_default_copay_percent = fields.Float(
        string="Default Insurance Co-pay (%)",
        default=0.0,
        config_parameter="clinic_billing.insurance.default_copay_percent",
        help="Default co-pay percent hint for new insurance claims; can be overridden per invoice/claim."
    )
    insurance_settlement_journal_id = fields.Many2one(
        "account.journal",
        string="Insurance Settlement Journal",
        config_parameter="clinic_billing.insurance.settlement_journal_id",
        domain="[('company_id', '=', company_id)]",
        help="Default journal used when settling approved insurance claims into clinic billing payment."
    )

    # ======================================================================
    # GATEWAY (Credentials & Policy)
    # ======================================================================
    gateway_enforce_signature = fields.Boolean(
        string="Enforce Webhook Signature",
        default=False,
        config_parameter="clinic_billing.gateway.enforce_signature",
        help="If enabled, webhook signature validation is enforced; otherwise, a failed check won't block processing."
    )
    gateway_midtrans_server_key = fields.Char(
        string="Midtrans Server Key",
        config_parameter="clinic_billing.gateway.midtrans.server_key",
        help="Server key used to validate Midtrans signature."
    )
    gateway_xendit_callback_token = fields.Char(
        string="Xendit Callback Token",
        config_parameter="clinic_billing.gateway.xendit.callback_token",
        help="Callback token used to validate Xendit webhook."
    )
    gateway_stripe_webhook_secret = fields.Char(
        string="Stripe Webhook Secret",
        config_parameter="clinic_billing.gateway.stripe.webhook_secret",
        help="Webhook secret used to validate Stripe events."
    )
    gateway_default_journal_id = fields.Many2one(
        "account.journal",
        string="Gateway Default Journal",
        config_parameter="clinic_billing.gateway.default_journal_id",
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank','cash','general'))]",
        help="Default journal used by Gateway TX to create clinic billing payments when capturing/settling."
    )

    # ======================================================================
    # VALIDATIONS & SIDE-EFFECTS
    # ======================================================================
    @api.constrains(
        "commission_default_percent",
        "insurance_default_coverage_percent",
        "insurance_default_copay_percent",
    )
    def _check_percentages(self):
        for rec in self:
            for field_name, low, high in [
                ("commission_default_percent", 0.0, 1000.0),
                ("insurance_default_coverage_percent", 0.0, 100.0),
                ("insurance_default_copay_percent", 0.0, 100.0),
            ]:
                val = getattr(rec, field_name)
                if val is not None and (val < low or val > high):
                    raise ValidationError(_("%s is out of bounds.") % rec._fields[field_name].string)

    @api.onchange("discount_product_code", "voucher_product_code", "membership_product_code")
    def _onchange_codes_upper(self):
        """Normalize codes to uppercase with no surrounding spaces."""
        for rec in self:
            if rec.discount_product_code:
                rec.discount_product_code = rec.discount_product_code.strip().upper()
            if rec.voucher_product_code:
                rec.voucher_product_code = rec.voucher_product_code.strip().upper()
            if rec.membership_product_code:
                rec.membership_product_code = rec.membership_product_code.strip().upper()

    def set_values(self):
        """
        Persist settings and ensure placeholder products exist
        for discount/voucher/membership engines.
        """
        res = super().set_values()

        # Ensure placeholder products created/updated
        for rec in self:
            # Discount
            if rec.discount_product_code:
                rec._ensure_service_product_by_code(
                    rec.discount_product_code,
                    "Clinic Discount (Auto)"
                )
            # Voucher
            if rec.voucher_product_code:
                rec._ensure_service_product_by_code(
                    rec.voucher_product_code,
                    "Clinic Voucher (Auto)"
                )
            # Membership
            if rec.membership_product_code:
                rec._ensure_service_product_by_code(
                    rec.membership_product_code,
                    "Membership Wallet Deduction (Auto)"
                )

        return res

    # ======================================================================
    # UTILITIES
    # ======================================================================
    def _ensure_service_product_by_code(self, default_code, name):
        """Create (or reuse) a service product with given default_code for current company."""
        Product = self.env["product.product"].sudo()
        company = self.company_id or self.env.company
        # Try to find an existing product in current or global company
        product = Product.search([
            ("default_code", "=", default_code),
            ("company_id", "in", [False, company.id]),
        ], limit=1)
        if product:
            # Ensure the product is a service and has correct display name
            try:
                if product.product_tmpl_id.type != "service":
                    product.product_tmpl_id.write({"type": "service"})
                if not product.name or product.name == default_code:
                    product.product_tmpl_id.write({"name": name})
            except Exception:
                pass
            return product

        # Create a new product template
        tmpl_vals = {
            "name": name,
            "type": "service",
            "default_code": default_code,
            "lst_price": 0.0,
            "company_id": company.id,
            "sale_ok": True,
            "purchase_ok": False,
        }
        try:
            product = Product.create(tmpl_vals)
        except Exception:
            # Fallback: create without company to make it global
            tmpl_vals["company_id"] = False
            product = Product.create(tmpl_vals)
        return product

