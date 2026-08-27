# -*- coding: utf-8 -*-
"""Schema-safe, company-scoped Treatment Package configuration.

The public ``res.company.clinic_pkg_*`` API is preserved because package
workflows consume it directly.  The fields are intentionally non-stored and
backed by company-qualified ``ir.config_parameter`` keys so replacing source
before an Odoo module upgrade cannot make the global ``res.company`` table
unreadable.
"""

from __future__ import annotations

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


_PARAM_PREFIX = "clinic_package.company"

_CONFIG_SPECS = {
    "clinic_pkg_default_pricing_id": ("default_pricing_id", "many2one", False),
    "clinic_pkg_default_policy_id": ("default_policy_id", "many2one", False),
    "clinic_pkg_voucher_prefix": ("voucher_prefix", "char", "CPK"),
    "clinic_pkg_voucher_code_length": ("voucher_code_length", "int", 12),
    "clinic_pkg_voucher_valid_days": ("voucher_valid_days", "int", 30),
    "clinic_pkg_auto_expire_allocations": ("auto_expire_allocations", "bool", True),
    "clinic_pkg_auto_expire_vouchers": ("auto_expire_vouchers", "bool", True),
}


def _as_bool(value, default=False):
    if value in (None, False, ""):
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value, default=0):
    if value in (None, False, ""):
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


class ResCompany(models.Model):
    _inherit = "res.company"

    clinic_pkg_default_pricing_id = fields.Many2one(
        "clinic.package.pricing",
        string="Default Package Pricing",
        compute="_compute_clinic_pkg_configuration",
        store=False,
        check_company=True,
    )
    clinic_pkg_default_policy_id = fields.Many2one(
        "clinic.package.policy",
        string="Default Package Policy",
        compute="_compute_clinic_pkg_configuration",
        store=False,
        check_company=True,
    )
    clinic_pkg_voucher_prefix = fields.Char(
        string="Voucher Prefix",
        compute="_compute_clinic_pkg_configuration",
        store=False,
    )
    clinic_pkg_voucher_code_length = fields.Integer(
        string="Voucher Token Length",
        compute="_compute_clinic_pkg_configuration",
        store=False,
    )
    clinic_pkg_voucher_valid_days = fields.Integer(
        string="Default Voucher Validity (days)",
        compute="_compute_clinic_pkg_configuration",
        store=False,
    )
    clinic_pkg_auto_expire_allocations = fields.Boolean(
        string="Auto-expire Package Allocations",
        compute="_compute_clinic_pkg_configuration",
        store=False,
    )
    clinic_pkg_auto_expire_vouchers = fields.Boolean(
        string="Auto-expire Package Vouchers",
        compute="_compute_clinic_pkg_configuration",
        store=False,
    )

    def _clinic_pkg_parameter_key(self, suffix):
        self.ensure_one()
        return f"{_PARAM_PREFIX}.{self.id}.{suffix}" if self.id else False

    def _clinic_pkg_read_parameter_values(self):
        self.ensure_one()
        defaults = {
            "clinic_pkg_default_pricing_id": self.env["clinic.package.pricing"],
            "clinic_pkg_default_policy_id": self.env["clinic.package.policy"],
            "clinic_pkg_voucher_prefix": "CPK",
            "clinic_pkg_voucher_code_length": 12,
            "clinic_pkg_voucher_valid_days": 30,
            "clinic_pkg_auto_expire_allocations": True,
            "clinic_pkg_auto_expire_vouchers": True,
        }
        if not self.id:
            return defaults

        Param = self.env["ir.config_parameter"].sudo()

        def get(field_name):
            suffix = _CONFIG_SPECS[field_name][0]
            return Param.get_param(self._clinic_pkg_parameter_key(suffix))

        pricing_id = max(_as_int(get("clinic_pkg_default_pricing_id"), 0), 0)
        pricing = self.env["clinic.package.pricing"].sudo().browse(pricing_id).exists()
        if pricing and pricing.company_id != self:
            pricing = self.env["clinic.package.pricing"]

        policy_id = max(_as_int(get("clinic_pkg_default_policy_id"), 0), 0)
        policy = self.env["clinic.package.policy"].sudo().browse(policy_id).exists()
        if policy and policy.company_id != self:
            policy = self.env["clinic.package.policy"]

        prefix = (get("clinic_pkg_voucher_prefix") or "CPK").strip() or "CPK"

        return {
            "clinic_pkg_default_pricing_id": pricing,
            "clinic_pkg_default_policy_id": policy,
            "clinic_pkg_voucher_prefix": prefix,
            "clinic_pkg_voucher_code_length": max(
                _as_int(get("clinic_pkg_voucher_code_length"), 12), 8
            ),
            "clinic_pkg_voucher_valid_days": max(
                _as_int(get("clinic_pkg_voucher_valid_days"), 30), 1
            ),
            "clinic_pkg_auto_expire_allocations": _as_bool(
                get("clinic_pkg_auto_expire_allocations"), True
            ),
            "clinic_pkg_auto_expire_vouchers": _as_bool(
                get("clinic_pkg_auto_expire_vouchers"), True
            ),
        }

    def _clinic_pkg_write_parameter_values(self, values):
        allowed = set(_CONFIG_SPECS)
        unknown = set(values) - allowed
        if unknown:
            raise ValidationError(
                _("Unsupported package configuration key(s): %s")
                % ", ".join(sorted(unknown))
            )

        Param = self.env["ir.config_parameter"].sudo()
        for company in self:
            if not company.id:
                continue

            pricing = False
            if "clinic_pkg_default_pricing_id" in values:
                value = values["clinic_pkg_default_pricing_id"]
                pricing = (
                    self.env["clinic.package.pricing"].browse(value)
                    if isinstance(value, int)
                    else value
                )
                pricing = pricing.exists() if pricing else self.env["clinic.package.pricing"]
                if pricing and pricing.company_id != company:
                    raise ValidationError(
                        _("Default package pricing must belong to company %s.")
                        % company.display_name
                    )
                Param.set_param(
                    company._clinic_pkg_parameter_key("default_pricing_id"),
                    pricing.id if pricing else "",
                )

            policy = False
            if "clinic_pkg_default_policy_id" in values:
                value = values["clinic_pkg_default_policy_id"]
                policy = (
                    self.env["clinic.package.policy"].browse(value)
                    if isinstance(value, int)
                    else value
                )
                policy = policy.exists() if policy else self.env["clinic.package.policy"]
                if policy and policy.company_id != company:
                    raise ValidationError(
                        _("Default package policy must belong to company %s.")
                        % company.display_name
                    )
                Param.set_param(
                    company._clinic_pkg_parameter_key("default_policy_id"),
                    policy.id if policy else "",
                )

            if "clinic_pkg_voucher_prefix" in values:
                prefix = (values["clinic_pkg_voucher_prefix"] or "CPK").strip()
                if not prefix:
                    prefix = "CPK"
                if len(prefix) > 16:
                    raise ValidationError(_("Voucher prefix cannot exceed 16 characters."))
                Param.set_param(
                    company._clinic_pkg_parameter_key("voucher_prefix"),
                    prefix,
                )

            if "clinic_pkg_voucher_code_length" in values:
                length = _as_int(values["clinic_pkg_voucher_code_length"], 12)
                if length < 8 or length > 32:
                    raise ValidationError(
                        _("Voucher token length must be between 8 and 32 characters.")
                    )
                Param.set_param(
                    company._clinic_pkg_parameter_key("voucher_code_length"),
                    str(length),
                )

            if "clinic_pkg_voucher_valid_days" in values:
                days = _as_int(values["clinic_pkg_voucher_valid_days"], 30)
                if days <= 0:
                    raise ValidationError(
                        _("Default voucher validity must be greater than zero days.")
                    )
                Param.set_param(
                    company._clinic_pkg_parameter_key("voucher_valid_days"),
                    str(days),
                )

            for field_name in (
                "clinic_pkg_auto_expire_allocations",
                "clinic_pkg_auto_expire_vouchers",
            ):
                if field_name not in values:
                    continue
                suffix = _CONFIG_SPECS[field_name][0]
                Param.set_param(
                    company._clinic_pkg_parameter_key(suffix),
                    "1" if bool(values[field_name]) else "0",
                )

            company.invalidate_recordset(list(_CONFIG_SPECS))
        return True

    @api.depends_context("uid")
    def _compute_clinic_pkg_configuration(self):
        for company in self:
            values = company._clinic_pkg_read_parameter_values()
            company.clinic_pkg_default_pricing_id = values[
                "clinic_pkg_default_pricing_id"
            ]
            company.clinic_pkg_default_policy_id = values[
                "clinic_pkg_default_policy_id"
            ]
            company.clinic_pkg_voucher_prefix = values[
                "clinic_pkg_voucher_prefix"
            ]
            company.clinic_pkg_voucher_code_length = values[
                "clinic_pkg_voucher_code_length"
            ]
            company.clinic_pkg_voucher_valid_days = values[
                "clinic_pkg_voucher_valid_days"
            ]
            company.clinic_pkg_auto_expire_allocations = values[
                "clinic_pkg_auto_expire_allocations"
            ]
            company.clinic_pkg_auto_expire_vouchers = values[
                "clinic_pkg_auto_expire_vouchers"
            ]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_pkg_default_pricing_id = fields.Many2one(
        "clinic.package.pricing",
        string="Default Package Pricing",
        check_company=True,
    )
    clinic_pkg_default_policy_id = fields.Many2one(
        "clinic.package.policy",
        string="Default Package Policy",
        check_company=True,
    )
    clinic_pkg_voucher_prefix = fields.Char(string="Voucher Prefix")
    clinic_pkg_voucher_code_length = fields.Integer(string="Voucher Token Length")
    clinic_pkg_voucher_valid_days = fields.Integer(
        string="Default Voucher Validity (days)"
    )
    clinic_pkg_auto_expire_allocations = fields.Boolean(
        string="Auto-expire Package Allocations"
    )
    clinic_pkg_auto_expire_vouchers = fields.Boolean(
        string="Auto-expire Package Vouchers"
    )

    @api.model
    def get_values(self):
        values = super().get_values()
        company = self.env.company
        config = company._clinic_pkg_read_parameter_values()
        values.update(
            {
                "clinic_pkg_default_pricing_id": (
                    config["clinic_pkg_default_pricing_id"].id
                    if config["clinic_pkg_default_pricing_id"]
                    else False
                ),
                "clinic_pkg_default_policy_id": (
                    config["clinic_pkg_default_policy_id"].id
                    if config["clinic_pkg_default_policy_id"]
                    else False
                ),
                "clinic_pkg_voucher_prefix": config[
                    "clinic_pkg_voucher_prefix"
                ],
                "clinic_pkg_voucher_code_length": config[
                    "clinic_pkg_voucher_code_length"
                ],
                "clinic_pkg_voucher_valid_days": config[
                    "clinic_pkg_voucher_valid_days"
                ],
                "clinic_pkg_auto_expire_allocations": config[
                    "clinic_pkg_auto_expire_allocations"
                ],
                "clinic_pkg_auto_expire_vouchers": config[
                    "clinic_pkg_auto_expire_vouchers"
                ],
            }
        )
        return values

    def set_values(self):
        super().set_values()
        if (
            not self.env.is_superuser()
            and not self.env.user.has_group("base.group_system")
            and not self.env.user.has_group(
                "clinic_package.group_clinic_package_manager"
            )
        ):
            raise AccessError(
                _("Only a Package Manager or Settings administrator may change package settings.")
            )

        for wizard in self:
            company = wizard.company_id or self.env.company
            company._clinic_pkg_write_parameter_values(
                {
                    "clinic_pkg_default_pricing_id": wizard.clinic_pkg_default_pricing_id,
                    "clinic_pkg_default_policy_id": wizard.clinic_pkg_default_policy_id,
                    "clinic_pkg_voucher_prefix": wizard.clinic_pkg_voucher_prefix,
                    "clinic_pkg_voucher_code_length": wizard.clinic_pkg_voucher_code_length,
                    "clinic_pkg_voucher_valid_days": wizard.clinic_pkg_voucher_valid_days,
                    "clinic_pkg_auto_expire_allocations": wizard.clinic_pkg_auto_expire_allocations,
                    "clinic_pkg_auto_expire_vouchers": wizard.clinic_pkg_auto_expire_vouchers,
                }
            )
        return True
