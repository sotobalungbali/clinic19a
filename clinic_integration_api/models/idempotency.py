# -*- coding: utf-8 -*-
from datetime import timedelta
import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicApiIdempotency(models.Model):
    _name = "clinic.api.idempotency"
    _description = "Clinic API Idempotency Record"
    _order = "create_date desc, id desc"

    _client_key_unique = models.Constraint(
        "UNIQUE(client_id, idem_key)",
        "Idempotency key must be unique per API client.",
    )

    client_id = fields.Many2one("clinic.api.client", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="client_id.company_id", store=True, index=True)
    idem_key = fields.Char(string="Idempotency Key", required=True, index=True)
    request_hash = fields.Char(required=True, index=True)
    resource = fields.Char(index=True)
    state = fields.Selection([("processing", "Processing"), ("done", "Done"), ("failed", "Failed")], default="processing", required=True, index=True)
    response_code = fields.Integer()
    response_json = fields.Text(groups="clinic_integration_api.group_api_manager")
    error_message = fields.Char(groups="clinic_integration_api.group_api_manager")
    expires_at = fields.Datetime(required=True, index=True)

    @api.model
    def begin(self, client, key, request_hash, resource):
        if not key or len(key) > 200:
            raise ValidationError(_("A valid Idempotency-Key header is required for mutation requests."))
        lock_key = f"clinic-api:{client.id}:{key}"
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))
        Model = self.sudo()
        rec = Model.search([("client_id", "=", client.id), ("idem_key", "=", key)], limit=1)
        if rec and rec.expires_at and rec.expires_at <= fields.Datetime.now():
            rec.unlink(); rec = Model.browse()
        if rec:
            if rec.request_hash != request_hash:
                raise ValidationError(_("This Idempotency-Key was already used for a different request."))
            if rec.state == "done":
                return rec, json.loads(rec.response_json or "{}")
            if rec.state == "processing":
                raise ValidationError(_("A request with this Idempotency-Key is already processing."))
            rec.write({"state": "processing", "error_message": False})
            return rec, None
        expires_at = fields.Datetime.now() + timedelta(hours=client.idempotency_ttl_hours)
        rec = Model.create({"client_id": client.id, "idem_key": key, "request_hash": request_hash, "resource": resource, "expires_at": expires_at})
        return rec, None

    def mark_done(self, status_code, payload):
        self.sudo().write({"state": "done", "response_code": status_code, "response_json": json.dumps(payload, default=str, separators=(",", ":")), "error_message": False})

    def mark_failed(self, message):
        self.sudo().write({"state": "failed", "error_message": str(message)[:500]})

    @api.model
    def _cron_cleanup_expired(self, limit=500):
        domain = [("expires_at", "<", fields.Datetime.now())]
        records = self.sudo().search(domain, limit=limit)
        count = len(records)
        records.unlink()
        remaining = 0 if count < limit else self.sudo().search_count(domain)
        self.env["ir.cron"]._commit_progress(count, remaining=remaining)
        return count
