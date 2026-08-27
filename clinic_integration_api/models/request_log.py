# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ClinicApiRequestLog(models.Model):
    """Sanitized request telemetry. Raw clinical request/response bodies are never logged here."""

    _name = "clinic.api.request.log"
    _description = "Clinic API Request Log"
    _order = "requested_at desc, id desc"

    client_id = fields.Many2one("clinic.api.client", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict", index=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    request_id = fields.Char(required=True, index=True)
    method = fields.Char(required=True, size=12)
    route = fields.Char(required=True)
    resource = fields.Char(index=True)
    status_code = fields.Integer(index=True)
    duration_ms = fields.Integer()
    remote_addr = fields.Char(groups="clinic_integration_api.group_api_manager")
    error_code = fields.Char(groups="clinic_integration_api.group_api_manager")
    error_message = fields.Char(groups="clinic_integration_api.group_api_manager")

    @api.model
    def log_request(self, values):
        allowed = {"client_id", "company_id", "user_id", "requested_at", "request_id", "method", "route", "resource", "status_code", "duration_ms", "remote_addr", "error_code", "error_message"}
        clean = {key: value for key, value in values.items() if key in allowed}
        if clean.get("error_message"):
            clean["error_message"] = str(clean["error_message"])[:500]
        return self.sudo().create(clean)
