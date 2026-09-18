# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    account_wallet_liability_id = fields.Many2one(
        "account.account",
        string="Wallet Liability Account",
        check_company=True,
        help="Liability/deferred-revenue account credited when a patient tops up a wallet.",
    )
    wallet_journal_id = fields.Many2one(
        "account.journal",
        string="Wallet Journal",
        check_company=True,
        domain="[('company_id', '=', id), ('type', 'in', ('bank','cash','general'))]",
    )
    account_wallet_adjust_in_id = fields.Many2one(
        "account.account", string="Wallet Adjustment-In Account", check_company=True
    )
    account_wallet_adjust_out_id = fields.Many2one(
        "account.account", string="Wallet Adjustment-Out Account", check_company=True
    )
    account_wallet_redeem_clearing_id = fields.Many2one(
        "account.account", string="Wallet Redeem Clearing Account", check_company=True
    )

    wallet_default_expiry_months = fields.Integer(
        string="Default Wallet Expiry (Months)",
        default=0,
        help="0 means no automatic expiry date.",
    )
    wallet_default_expiry_policy = fields.Selection(
        [
            ("block", "Block usage on expiry"),
            ("warn", "Warn only"),
            ("none", "No expiry control"),
        ],
        default="warn",
        required=True,
    )
    wallet_redeem_post_accounting = fields.Boolean(
        string="Post Accounting Entry on Wallet Redeem",
        default=False,
        help="Enable only when Billing is not already responsible for the redeem accounting entry.",
    )
    wallet_expiry_notify_days_before = fields.Integer(default=7)
    wallet_expiry_notify_days_after = fields.Integer(default=1)
    wallet_auto_open_on_create = fields.Boolean(default=True)

    @api.constrains(
        "wallet_default_expiry_months",
        "wallet_expiry_notify_days_before",
        "wallet_expiry_notify_days_after",
    )
    def _check_wallet_non_negative_settings(self):
        for company in self:
            if company.wallet_default_expiry_months < 0:
                raise ValidationError(_("Default wallet expiry months cannot be negative."))
            if company.wallet_expiry_notify_days_before < 0 or company.wallet_expiry_notify_days_after < 0:
                raise ValidationError(_("Wallet expiry notification windows cannot be negative."))


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    account_wallet_liability_id = fields.Many2one(
        related="company_id.account_wallet_liability_id", readonly=False,
        domain="[('company_ids', 'in', [company_id])]",
    )
    wallet_journal_id = fields.Many2one(
        related="company_id.wallet_journal_id", readonly=False,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank','cash','general'))]",
    )
    account_wallet_adjust_in_id = fields.Many2one(
        related="company_id.account_wallet_adjust_in_id", readonly=False,
        domain="[('company_ids', 'in', [company_id])]",
    )
    account_wallet_adjust_out_id = fields.Many2one(
        related="company_id.account_wallet_adjust_out_id", readonly=False,
        domain="[('company_ids', 'in', [company_id])]",
    )
    account_wallet_redeem_clearing_id = fields.Many2one(
        related="company_id.account_wallet_redeem_clearing_id", readonly=False,
        domain="[('company_ids', 'in', [company_id])]",
    )
    wallet_default_expiry_months = fields.Integer(
        related="company_id.wallet_default_expiry_months", readonly=False
    )
    wallet_default_expiry_policy = fields.Selection(
        related="company_id.wallet_default_expiry_policy", readonly=False
    )
    wallet_redeem_post_accounting = fields.Boolean(
        related="company_id.wallet_redeem_post_accounting", readonly=False
    )
    wallet_expiry_notify_days_before = fields.Integer(
        related="company_id.wallet_expiry_notify_days_before", readonly=False
    )
    wallet_expiry_notify_days_after = fields.Integer(
        related="company_id.wallet_expiry_notify_days_after", readonly=False
    )
    wallet_auto_open_on_create = fields.Boolean(
        related="company_id.wallet_auto_open_on_create", readonly=False
    )
    # ------------------------------------------------------------------
    # Compatibility field names retained from the original Wallet addon.
    # They now delegate to company-owned settings instead of global ICP.
    # ``company_id`` is deliberately not redeclared: Odoo 19 already owns it
    # on res.config.settings and Wallet must not shadow that core field.
    # ------------------------------------------------------------------
    redeem_post_accounting = fields.Boolean(
        related="company_id.wallet_redeem_post_accounting",
        readonly=False,
        string="Post Accounting for Redeem Here",
    )
    expiry_notify_days_before = fields.Integer(
        related="company_id.wallet_expiry_notify_days_before",
        readonly=False,
        string="Notify X days before expiry",
    )
    expiry_notify_days_after = fields.Integer(
        related="company_id.wallet_expiry_notify_days_after",
        readonly=False,
        string="Notify X days after expiry",
    )

    @api.model
    def get_values(self):
        """Retain the historical API; Odoo loads related company fields natively."""
        return super().get_values()

    def set_values(self):
        """Retain the historical API; related company fields persist natively."""
        return super().set_values()

    def _get_int(self, key, default=0):
        """Compatibility reader for legacy integer configuration parameters."""
        raw = self.env["ir.config_parameter"].sudo().get_param(key, default=str(default))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _get_bool(self, key, default=False):
        """Compatibility reader for legacy boolean configuration parameters."""
        raw = self.env["ir.config_parameter"].sudo().get_param(
            key, default="1" if default else "0"
        )
        return str(raw).lower() in ("1", "true", "yes")

    def _set_int(self, key, value):
        """Compatibility writer retained for external customizations; new Wallet settings are company fields."""
        self.env["ir.config_parameter"].sudo().set_param(key, str(int(value or 0)))
        return True

    def _set_bool(self, key, value):
        """Compatibility writer retained for external customizations; new Wallet settings are company fields."""
        self.env["ir.config_parameter"].sudo().set_param(key, "1" if bool(value) else "0")
        return True

    def _set_m2o_param(self, key, record):
        """Compatibility writer for legacy Many2one parameter keys."""
        record_id = record.id if record and record.exists() else 0
        self.env["ir.config_parameter"].sudo().set_param(key, str(record_id))
        return True

    def _get_m2o_from_param(self, key, model_name):
        """
        Read a legacy Wallet configuration parameter when migration/custom code
        explicitly asks for it. New Wallet code never stores account ownership
        in ir.config_parameter.
        """
        raw = self.env["ir.config_parameter"].sudo().get_param(key)
        try:
            record_id = int(raw or 0)
        except (TypeError, ValueError):
            record_id = 0
        return self.env[model_name].browse(record_id).exists().id if record_id else False

    def _upsert_wallet_liability_property(self, company, account):
        """
        Compatibility shim for the historical method name.
        Odoo 19 Wallet stores the liability account directly on res.company;
        no legacy property record is created.
        """
        company.account_wallet_liability_id = account
        return True




