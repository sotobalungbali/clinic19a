# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Bootstrap-safe Referral configuration facade on ``res.company``.

    These three fields deliberately remain non-stored. ``res.company`` is read
    while Odoo builds the web session, so adding stored columns to an already
    installed addon can make the whole web client fail immediately after source
    replacement and before the operator can run the module upgrade.

    Public field names are preserved. Values are persisted per company in
    ``ir.config_parameter`` through explicit compute/inverse methods.
    """

    _inherit = "res.company"

    clinic_referral_default_valid_days = fields.Integer(
        string="Default Referral Validity (Days)",
        compute="_compute_clinic_referral_settings",
        inverse="_inverse_clinic_referral_default_valid_days",
        help=(
            "Days automatically added to Referral Date when Valid Until is "
            "not supplied."
        ),
    )
    clinic_referral_require_source = fields.Boolean(
        string="Require Referral Source on Confirmation",
        compute="_compute_clinic_referral_settings",
        inverse="_inverse_clinic_referral_require_source",
    )
    clinic_referral_require_program_for_reward = fields.Boolean(
        string="Require Referral Program for Rewards",
        compute="_compute_clinic_referral_settings",
        inverse="_inverse_clinic_referral_require_program_for_reward",
    )

    def _clinic_referral_parameter_key(self, setting_name):
        """Return a deterministic, company-scoped Referral config key."""
        self.ensure_one()
        return "clinic_referral.%s.company_%s" % (
            setting_name,
            self.id,
        )

    @staticmethod
    def _clinic_referral_to_bool(value, default=False):
        """Convert an ir.config_parameter value into a Boolean."""
        if value in (None, False, ""):
            return default
        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _compute_clinic_referral_settings(self):
        """Read Referral settings without requiring res_company columns."""
        Parameter = self.env["ir.config_parameter"].sudo()

        for company in self:
            if not company.id:
                company.clinic_referral_default_valid_days = 90
                company.clinic_referral_require_source = False
                company.clinic_referral_require_program_for_reward = True
                continue

            raw_days = Parameter.get_param(
                company._clinic_referral_parameter_key(
                    "default_valid_days"
                ),
                default="90",
            )
            try:
                days = int(raw_days)
            except (TypeError, ValueError):
                days = 90

            company.clinic_referral_default_valid_days = days
            company.clinic_referral_require_source = (
                company._clinic_referral_to_bool(
                    Parameter.get_param(
                        company._clinic_referral_parameter_key(
                            "require_source"
                        ),
                        default="False",
                    ),
                    default=False,
                )
            )
            company.clinic_referral_require_program_for_reward = (
                company._clinic_referral_to_bool(
                    Parameter.get_param(
                        company._clinic_referral_parameter_key(
                            "require_program_for_reward"
                        ),
                        default="True",
                    ),
                    default=True,
                )
            )

    def _inverse_clinic_referral_default_valid_days(self):
        """Validate and persist Referral validity days."""
        Parameter = self.env["ir.config_parameter"].sudo()

        for company in self:
            days = company.clinic_referral_default_valid_days
            if days < 0 or days > 3650:
                raise ValidationError(
                    _(
                        "Default Referral Validity must be between "
                        "0 and 3650 days."
                    )
                )
            if company.id:
                Parameter.set_param(
                    company._clinic_referral_parameter_key(
                        "default_valid_days"
                    ),
                    str(days),
                )

    def _inverse_clinic_referral_require_source(self):
        """Persist source-required governance per company."""
        Parameter = self.env["ir.config_parameter"].sudo()

        for company in self:
            if company.id:
                Parameter.set_param(
                    company._clinic_referral_parameter_key(
                        "require_source"
                    ),
                    "True"
                    if company.clinic_referral_require_source
                    else "False",
                )

    def _inverse_clinic_referral_require_program_for_reward(self):
        """Persist reward-program governance per company."""
        Parameter = self.env["ir.config_parameter"].sudo()

        for company in self:
            if company.id:
                Parameter.set_param(
                    company._clinic_referral_parameter_key(
                        "require_program_for_reward"
                    ),
                    "True"
                    if company.clinic_referral_require_program_for_reward
                    else "False",
                )
