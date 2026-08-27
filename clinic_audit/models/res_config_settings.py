# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_audit_enabled = fields.Boolean(
        string="Enable ClinicOne Audit Trail",
        config_parameter="clinic.audit.enabled",
        default=True,
    )
    clinic_audit_fail_closed = fields.Boolean(
        string="Fail Closed on Audit Error",
        config_parameter="clinic.audit.fail_closed",
        default=True,
        help=(
            "When enabled, a business create/update/delete is rolled back "
            "if mandatory audit evidence cannot be persisted."
        ),
    )
    clinic_audit_value_char_limit = fields.Integer(
        string="Maximum Stored Value Characters",
        config_parameter="clinic.audit.value_char_limit",
        default=2048,
        help=(
            "Longer values are represented by digest and length rather "
            "than duplicated in audit evidence."
        ),
    )

    @api.constrains("clinic_audit_value_char_limit")
    def _check_value_char_limit(self):
        for rec in self:
            if rec.clinic_audit_value_char_limit < 128:
                raise ValidationError(
                    _(
                        "Maximum stored value characters "
                        "must be at least 128."
                    )
                )
