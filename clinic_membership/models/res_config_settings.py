


# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettingsMembership(models.TransientModel):
    """Schema-safe, company-scoped Membership settings."""

    _inherit = "res.config.settings"

    membership_require_paid_before_activation = fields.Boolean(
        string="Require Paid Invoice Before Activation",
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )
    membership_default_points_expiry_days = fields.Integer(
        string="Default Points Expiry (Days)",
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )
    membership_points_per_currency = fields.Float(
        string="Default Points per Currency Unit",
        digits=(16, 4),
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )
    membership_allow_negative_points = fields.Boolean(
        string="Allow Negative Point Balance",
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )
    membership_auto_expire_contracts = fields.Boolean(
        string="Automatically Expire Contracts",
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )
    membership_auto_expire_vouchers = fields.Boolean(
        string="Automatically Expire Vouchers",
        compute="_compute_membership_settings",
        inverse="_inverse_membership_settings",
        store=False,
    )

    @api.depends("company_id")
    def _compute_membership_settings(self):
        Service = self.env["membership.config.service"]
        for rec in self:
            company = rec.company_id or self.env.company
            rec.membership_require_paid_before_activation = Service.get_value(
                "require_paid_before_activation", company
            )
            rec.membership_default_points_expiry_days = Service.get_value(
                "default_points_expiry_days", company
            )
            rec.membership_points_per_currency = Service.get_value(
                "points_per_currency", company
            )
            rec.membership_allow_negative_points = Service.get_value(
                "allow_negative_points", company
            )
            rec.membership_auto_expire_contracts = Service.get_value(
                "auto_expire_contracts", company
            )
            rec.membership_auto_expire_vouchers = Service.get_value(
                "auto_expire_vouchers", company
            )

    def _inverse_membership_settings(self):
        Service = self.env["membership.config.service"]
        for rec in self:
            company = rec.company_id or self.env.company
            if rec.membership_default_points_expiry_days < 0:
                raise ValidationError("Default Points Expiry cannot be negative.")
            if rec.membership_points_per_currency < 0:
                raise ValidationError("Points per Currency Unit cannot be negative.")
            Service.set_value(
                "require_paid_before_activation",
                rec.membership_require_paid_before_activation,
                company,
            )
            Service.set_value(
                "default_points_expiry_days",
                rec.membership_default_points_expiry_days,
                company,
            )
            Service.set_value(
                "points_per_currency",
                rec.membership_points_per_currency,
                company,
            )
            Service.set_value(
                "allow_negative_points",
                rec.membership_allow_negative_points,
                company,
            )
            Service.set_value(
                "auto_expire_contracts",
                rec.membership_auto_expire_contracts,
                company,
            )
            Service.set_value(
                "auto_expire_vouchers",
                rec.membership_auto_expire_vouchers,
                company,
            )

