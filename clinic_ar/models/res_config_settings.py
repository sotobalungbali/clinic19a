# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clinic_ar_default_followup_days = fields.Integer(string="Default Follow-up Delay (Days)", default=7)
    clinic_ar_auto_refresh_aging = fields.Boolean(string="Automatically Refresh AR Aging", default=True)
    clinic_ar_statement_days = fields.Integer(string="Default Statement Lookback (Days)", default=90)
    clinic_ar_writeoff_account_id = fields.Many2one(
        "account.account", related="company_id.ar_writeoff_account_id", readonly=False, check_company=True
    )
    clinic_ar_writeoff_threshold = fields.Monetary(
        related="company_id.ar_writeoff_threshold", readonly=False, currency_field="clinic_ar_company_currency_id"
    )
    clinic_ar_default_general_journal_id = fields.Many2one(
        "account.journal", related="company_id.ar_default_general_journal_id", readonly=False, check_company=True
    )
    clinic_ar_company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")

    def _clinic_ar_key(self, suffix):
        self.ensure_one()
        return f"clinic_ar.company.{self.company_id.id}.{suffix}"

    def get_values(self):
        values = super().get_values()
        params = self.env["ir.config_parameter"].sudo()
        company = self.env.company
        prefix = f"clinic_ar.company.{company.id}."
        values.update({
            "clinic_ar_default_followup_days": int(params.get_param(prefix + "default_followup_days", "7")),
            "clinic_ar_auto_refresh_aging": params.get_param(prefix + "auto_refresh_aging", "True") == "True",
            "clinic_ar_statement_days": int(params.get_param(prefix + "statement_days", "90")),
        })
        return values

    def set_values(self):
        super().set_values()
        self.ensure_one()
        if self.clinic_ar_default_followup_days < 0 or self.clinic_ar_statement_days < 1:
            raise ValidationError(_("AR follow-up delay must be non-negative and statement lookback must be at least one day."))
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(self._clinic_ar_key("default_followup_days"), self.clinic_ar_default_followup_days)
        params.set_param(self._clinic_ar_key("auto_refresh_aging"), self.clinic_ar_auto_refresh_aging)
        params.set_param(self._clinic_ar_key("statement_days"), self.clinic_ar_statement_days)



