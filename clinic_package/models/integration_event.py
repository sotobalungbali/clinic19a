
# -*- coding: utf-8 -*-
"""Stable integration contract for downstream ClinicOne addons.

This model deliberately stores model/res_id plus JSON payload instead of hard
Many2one fields to future addons. Downstream owners (billing, finance, portal,
API, analytics, etc.) may consume these events without making clinic_package
import their models before those addons exist.
"""

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicPackageIntegrationEvent(models.Model):
    _name = "clinic.package.integration.event"
    _description = "Clinic Package Integration Event"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="/", index=True)
    event_code = fields.Char(required=True, index=True)
    source_model = fields.Char(required=True, index=True)
    source_res_id = fields.Integer(required=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    payload_json = fields.Text(default="{}")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(default=0, readonly=True)
    max_attempts = fields.Integer(default=3, required=True)
    last_attempt_at = fields.Datetime(readonly=True)
    processed_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    note = fields.Text()

    _attempts_check = models.Constraint(
        "CHECK(attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts)",
        "Integration event attempt counters are invalid.",
    )

    @api.constrains("payload_json")
    def _check_payload_json(self):
        for record in self:
            try:
                json.loads(record.payload_json or "{}")
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Integration payload must be valid JSON: %s", error)) from error

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name") in (False, "/", None):
                vals["name"] = sequence.next_by_code("clinic.package.integration.event") or "/"
        return super().create(vals_list)

    @api.model
    def enqueue(self, event_code, source_record, payload=None):
        """Create a durable downstream event without importing the downstream model."""
        source_record.ensure_one()
        payload = dict(payload or {})
        payload.setdefault("source_model", source_record._name)
        payload.setdefault("source_res_id", source_record.id)
        return self.create(
            {
                "event_code": event_code,
                "source_model": source_record._name,
                "source_res_id": source_record.id,
                "company_id": getattr(source_record, "company_id", self.env.company).id,
                "payload_json": json.dumps(payload, default=str, sort_keys=True),
            }
        )

    def action_mark_processing(self):
        for record in self:
            if record.state not in ("pending", "failed"):
                raise UserError(_("Only Pending or Failed events can enter Processing."))
            if record.attempt_count >= record.max_attempts:
                raise UserError(_("Retry limit reached for this integration event."))
            record.write(
                {
                    "state": "processing",
                    "attempt_count": record.attempt_count + 1,
                    "last_attempt_at": fields.Datetime.now(),
                    "last_error": False,
                }
            )
        return True

    def action_mark_done(self):
        self.filtered(lambda event: event.state != "cancelled").write(
            {"state": "done", "processed_at": fields.Datetime.now(), "last_error": False}
        )
        return True

    def action_mark_failed(self):
        for record in self:
            if record.state == "cancelled":
                raise UserError(_("Cancelled events cannot be marked Failed."))
            record.write({"state": "failed", "last_error": record.last_error or _("Manual failure")})
        return True

    def action_retry(self):
        for record in self:
            if record.state != "failed":
                raise UserError(_("Only Failed events can be retried."))
            if record.attempt_count >= record.max_attempts:
                raise UserError(_("Retry limit reached. Investigate the root cause before any further attempt."))
            record.write({"state": "pending", "last_error": False})
        return True

    def action_cancel(self):
        self.filtered(lambda event: event.state != "done").write({"state": "cancelled"})
        return True

    def action_open_source(self):
        self.ensure_one()
        if self.source_model not in self.env:
            raise UserError(_("Source model %s is not available in this database.", self.source_model))
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_("The source record no longer exists."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Record"),
            "res_model": self.source_model,
            "view_mode": "form",
            "res_id": source.id,
        }
