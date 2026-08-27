# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicARIntegrationEvent(models.Model):
    _name = "clinic.ar.integration.event"
    _description = "Accounts Receivable Integration Event"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    MAX_ATTEMPTS = 3

    name = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    event_type = fields.Char(required=True, index=True)
    model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    record_reference = fields.Char(compute="_compute_record_reference")
    payload_json = fields.Text(readonly=True)
    state = fields.Selection([
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ], default="pending", required=True, index=True)
    attempt_count = fields.Integer(default=0, readonly=True)
    next_attempt_at = fields.Datetime(index=True)
    processed_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    _event_key_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "AR integration event key must be unique per company.",
    )

    @api.depends("model", "res_id")
    def _compute_record_reference(self):
        for rec in self:
            rec.record_reference = f"{rec.model},{rec.res_id}" if rec.model and rec.res_id else False

    @api.model
    def enqueue(self, event_type, record, company=None, payload=None):
        record.ensure_one()
        company = company or getattr(record, "company_id", False) or self.env.company
        event_key = f"{event_type}:{record._name}:{record.id}:{fields.Datetime.now()}"
        return self.create({
            "name": event_key,
            "event_type": event_type,
            "model": record._name,
            "res_id": record.id,
            "company_id": company.id,
            "payload_json": json.dumps(payload or {}, default=str, ensure_ascii=False, sort_keys=True),
        })

    def action_mark_done(self):
        self.filtered(lambda e: e.state not in {"done", "cancelled"}).write({
            "state": "done",
            "processed_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    def action_retry(self):
        for rec in self:
            if rec.attempt_count >= self.MAX_ATTEMPTS:
                raise UserError(_("Maximum integration retry attempts reached."))
            rec.write({"state": "pending", "next_attempt_at": fields.Datetime.now(), "last_error": False})
        return True

    def action_cancel(self):
        self.filtered(lambda e: e.state != "done").write({"state": "cancelled"})
        return True

    @api.model
    def _cron_process_pending(self):
        now = fields.Datetime.now()
        events = self.search([
            ("state", "=", "pending"),
            ("attempt_count", "<", self.MAX_ATTEMPTS),
            "|", ("next_attempt_at", "=", False), ("next_attempt_at", "<=", now),
        ], order="create_date, id", limit=100)
        # clinic_ar owns the durable outbox, not downstream consumers. Events stay
        # pending until a downstream bridge/consumer marks them done.
        for event in events:
            event.attempt_count += 1
            if event.attempt_count >= self.MAX_ATTEMPTS:
                event.write({"state": "failed", "last_error": _("No downstream consumer acknowledged this event.")})
        return True

