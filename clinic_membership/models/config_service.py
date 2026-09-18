


# -*- coding: utf-8 -*-
from odoo import api, models


class MembershipConfigService(models.AbstractModel):
    """Company-scoped configuration without adding columns to ``res.company``.

    This avoids the source/schema skew failure mode where loading a new addon
    version can make every generic ``res.company`` read fail before the module
    upgrade has had a chance to create columns.
    """

    _name = "membership.config.service"
    _description = "Membership Company Configuration Service"

    DEFAULTS = {
        "require_paid_before_activation": True,
        "default_points_expiry_days": 365,
        "points_per_currency": 1.0,
        "allow_negative_points": False,
        "auto_expire_contracts": True,
        "auto_expire_vouchers": True,
    }

    @api.model
    def _key(self, company, name):
        return f"clinic_membership.company.{company.id}.{name}"

    @api.model
    def get_value(self, name, company=None):
        company = company or self.env.company
        default = self.DEFAULTS.get(name)
        raw = self.env["ir.config_parameter"].sudo().get_param(
            self._key(company, name)
        )
        if raw is None:
            return default
        if isinstance(default, bool):
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(default, int):
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default
        if isinstance(default, float):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default
        return raw

    @api.model
    def set_value(self, name, value, company=None):
        company = company or self.env.company
        self.env["ir.config_parameter"].sudo().set_param(
            self._key(company, name), value
        )
        return True


